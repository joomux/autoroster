"""Google Calendar API client."""

from __future__ import annotations

from typing import TYPE_CHECKING

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

if TYPE_CHECKING:
    from autoroster.parser import Event

LOCAL_TIMEZONE = "Australia/Sydney"  # Update via env var if needed


def _build_service(credentials_dict: dict):
    creds = Credentials(
        token=credentials_dict["token"],
        refresh_token=credentials_dict.get("refresh_token"),
        token_uri=credentials_dict["token_uri"],
        client_id=credentials_dict["client_id"],
        client_secret=credentials_dict["client_secret"],
        scopes=credentials_dict.get("scopes"),
    )
    return build("calendar", "v3", credentials=creds)


def get_calendars(credentials_dict: dict) -> list[dict]:
    """Return a list of the user's calendars as {id, name} dicts."""
    service = _build_service(credentials_dict)
    result = service.calendarList().list().execute()
    return [
        {"id": cal["id"], "name": cal.get("summary", cal["id"])}
        for cal in result.get("items", [])
        if cal.get("accessRole") in ("owner", "writer")
    ]


def create_events(credentials_dict: dict, calendar_id: str, events: list[Event]) -> int:
    """Insert events into the specified Google Calendar. Returns count created."""
    import os

    tz = os.environ.get("TIMEZONE", LOCAL_TIMEZONE)
    service = _build_service(credentials_dict)
    count = 0
    for event in events:
        body = {
            "summary": event.title,
            "start": {"dateTime": event.start.isoformat(), "timeZone": tz},
            "end": {"dateTime": event.end.isoformat(), "timeZone": tz},
        }
        service.events().insert(calendarId=calendar_id, body=body).execute()
        count += 1
    return count
