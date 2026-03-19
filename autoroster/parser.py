"""Parser module: convert raw OCR shift data into structured calendar Event objects.

Shift definitions (12-hour model):
    A  — Day Shift     07:00–19:00
    N  — Night Shift   19:00–07:00 (next day)
    P  — Afternoon     15:00–23:00
    DO — Day Off       (not added to calendar)
"""

from __future__ import annotations

import calendar
from datetime import date, datetime, timedelta
from typing import Optional

SHIFT_DEFINITIONS: dict[str, dict] = {
    "A": {
        "label": "Day Shift",
        "start_hour": 7,
        "start_minute": 0,
        "duration_hours": 12,
    },
    "N": {
        "label": "Night Shift",
        "start_hour": 19,
        "start_minute": 0,
        "duration_hours": 12,
    },
    "P": {
        "label": "Afternoon Shift",
        "start_hour": 15,
        "start_minute": 0,
        "duration_hours": 8,
    },
}

# DO = Day Off — skipped entirely


class Event:
    """A single calendar event derived from a roster shift."""

    def __init__(
        self,
        date: date,
        shift_code: str,
        title: str,
        start: datetime,
        end: datetime,
    ) -> None:
        self.date = date
        self.shift_code = shift_code
        self.title = title
        self.start = start
        self.end = end

    def to_dict(self) -> dict:
        return {
            "date": self.date.isoformat(),
            "shift_code": self.shift_code,
            "title": self.title,
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Event":
        return cls(
            date=date.fromisoformat(d["date"]),
            shift_code=d["shift_code"],
            title=d["title"],
            start=datetime.fromisoformat(d["start"]),
            end=datetime.fromisoformat(d["end"]),
        )

    @property
    def start_time_display(self) -> str:
        return self.start.strftime("%-I:%M %p")

    @property
    def end_time_display(self) -> str:
        return self.end.strftime("%-I:%M %p")

    @property
    def date_display(self) -> str:
        return self.date.strftime("%a %-d %b %Y")


def extract_events(raw: dict) -> list[Event]:
    """Convert raw OCR data into a sorted list of Event objects.

    Args:
        raw: Dict from ``vision.parse_calendar_image`` with keys
             ``year``, ``month``, and ``shifts``.

    Returns:
        List of Event objects, sorted by start datetime.
    """
    year: Optional[int] = raw.get("year")
    month: Optional[int] = raw.get("month")
    shifts: dict[int, str] = raw.get("shifts", {})

    # Use current year/month as fallback if OCR couldn't detect them
    if not year or not month:
        today = date.today()
        year = year or today.year
        month = month or today.month

    # Validate month/year
    max_day = calendar.monthrange(year, month)[1]

    events: list[Event] = []
    for day_num, shift_code in shifts.items():
        if shift_code == "DO":
            continue  # Day Off — not added to calendar
        if shift_code not in SHIFT_DEFINITIONS:
            continue  # Unknown code — skip
        if not (1 <= day_num <= max_day):
            continue  # OCR artefact — out of range for this month

        defn = SHIFT_DEFINITIONS[shift_code]
        event_date = date(year, month, day_num)
        start_dt = datetime(
            year, month, day_num, defn["start_hour"], defn["start_minute"]
        )
        end_dt = start_dt + timedelta(hours=defn["duration_hours"])

        events.append(
            Event(
                date=event_date,
                shift_code=shift_code,
                title=defn["label"],
                start=start_dt,
                end=end_dt,
            )
        )

    events.sort(key=lambda e: e.start)
    return events
