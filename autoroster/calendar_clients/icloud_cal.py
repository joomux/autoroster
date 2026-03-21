"""iCloud Calendar client via CalDAV.

iCloud CalDAV requires an app-specific password, not a regular Apple ID
password. Users must generate one at https://appleid.apple.com > Security >
App-Specific Passwords.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

import caldav

if TYPE_CHECKING:
    from autoroster.parser import Event

ICLOUD_CALDAV_URL = "https://caldav.icloud.com"


def _client(credentials: dict) -> caldav.DAVClient:
    return caldav.DAVClient(
        url=ICLOUD_CALDAV_URL,
        username=credentials["username"],
        password=credentials["password"],
    )


def verify_credentials(username: str, password: str) -> None:
    """Raise an exception if the credentials are invalid."""
    client = caldav.DAVClient(url=ICLOUD_CALDAV_URL, username=username, password=password)
    principal = client.principal()
    principal.calendars()  # Will raise if auth fails


def get_calendars(credentials: dict) -> list[dict]:
    """Return a list of the user's iCloud calendars as {id, name} dicts."""
    client = _client(credentials)
    principal = client.principal()
    cals = principal.calendars()
    return [{"id": str(cal.url), "name": cal.name or str(cal.url)} for cal in cals]


def create_events(credentials: dict, calendar_url: str, events: list[Event]) -> list[str]:
    """Create events in the specified iCloud calendar. Returns list of created event UIDs."""
    client = _client(credentials)
    calendar = client.calendar(url=calendar_url)
    uids: list[str] = []
    for event in events:
        uid = str(uuid.uuid4())
        fmt = "%Y%m%dT%H%M%S"
        dtstart = event.start.strftime(fmt)
        dtend = event.end.strftime(fmt)
        dtstamp = datetime.utcnow().strftime(fmt) + "Z"
        ical = (
            "BEGIN:VCALENDAR\r\n"
            "VERSION:2.0\r\n"
            "PRODID:-//autoroster//autoroster//EN\r\n"
            "BEGIN:VEVENT\r\n"
            f"UID:{uid}\r\n"
            f"DTSTAMP:{dtstamp}\r\n"
            f"DTSTART:{dtstart}\r\n"
            f"DTEND:{dtend}\r\n"
            f"SUMMARY:{event.title}\r\n"
            "END:VEVENT\r\n"
            "END:VCALENDAR\r\n"
        )
        calendar.save_event(ical)
        uids.append(uid)
    return uids


def get_events_in_range(credentials: dict, calendar_url: str, start_date, end_date) -> list[dict]:
    """Return all events in [start_date, end_date] as {id, title, start, end} dicts."""
    from datetime import datetime as _dt
    client = _client(credentials)
    calendar = client.calendar(url=calendar_url)
    results = calendar.date_search(
        start=_dt(start_date.year, start_date.month, start_date.day),
        end=_dt(end_date.year, end_date.month, end_date.day, 23, 59, 59),
        expand=True,
    )
    events = []
    for obj in results:
        try:
            vevent = obj.vobject_instance.vevent
            uid = str(vevent.uid.value)
            title = str(vevent.summary.value) if hasattr(vevent, "summary") else ""
            dtstart = vevent.dtstart.value
            dtend = vevent.dtend.value
            events.append({
                "id": uid,
                "title": title,
                "start": dtstart.isoformat() if hasattr(dtstart, "isoformat") else str(dtstart),
                "end": dtend.isoformat() if hasattr(dtend, "isoformat") else str(dtend),
            })
        except Exception:
            continue
    return events


def delete_events(credentials: dict, calendar_url: str, uids: list[str]) -> None:
    """Delete events from iCloud calendar by UID. Best-effort: ignores individual failures."""
    client = _client(credentials)
    calendar = client.calendar(url=calendar_url)
    for uid in uids:
        try:
            obj = calendar.calendar_object_by_uid(uid)
            obj.delete()
        except Exception:
            pass
