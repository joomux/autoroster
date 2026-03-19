"""Parser module: convert raw OCR shift data into structured calendar Event objects.

Shift definitions (12.5-hour model):
    A  — Day Shift     07:00–19:30
    N  — Night Shift   19:00–07:30 (next day)
    P  — Afternoon     15:00–23:00
    DO — Day Off       (not added to calendar)
"""

from __future__ import annotations

import calendar
from datetime import date, datetime, timedelta
from typing import Optional

# Default shift times used when the OCR cannot extract explicit times from the image.
# end_hour/end_minute is the clock time the shift ends; if it is earlier than
# start_hour/start_minute (i.e. N shift crossing midnight) the end date is +1 day.
SHIFT_DEFINITIONS: dict[str, dict] = {
    "A": {
        "label": "Day Shift",
        "start_hour": 7,
        "start_minute": 0,
        "end_hour": 19,
        "end_minute": 30,
    },
    "N": {
        "label": "Night Shift",
        "start_hour": 19,
        "start_minute": 0,
        "end_hour": 7,
        "end_minute": 30,
    },
    "P": {
        "label": "Afternoon Shift",
        "start_hour": 15,
        "start_minute": 0,
        "end_hour": 23,
        "end_minute": 0,
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


def _parse_time(time_str: str) -> tuple[int, int]:
    """Parse 'HH:MM' into (hour, minute)."""
    h, m = time_str.split(":")
    return int(h), int(m)


def extract_events(raw: dict) -> list[Event]:
    """Convert raw OCR data into a sorted list of Event objects.

    Args:
        raw: Dict from ``vision.parse_calendar_image`` with keys
             ``year``, ``month``, ``months``, and ``shifts``.

    Returns:
        List of Event objects, sorted by start datetime.
    """
    year: Optional[int] = raw.get("year")
    months: list[int] = raw.get("months") or (
        [raw["month"]] if raw.get("month") else []
    )
    shifts: dict = raw.get("shifts", {})

    today = date.today()
    if not year:
        year = today.year
    if not months:
        months = [today.month]

    # Map each month to the correct year, handling a Dec→Jan boundary.
    month_years: dict[int, int] = {}
    for i, m in enumerate(months):
        if i > 0 and m < months[i - 1]:
            month_years[m] = year + 1
        else:
            month_years[m] = year

    events: list[Event] = []
    for key, shift_info in shifts.items():
        # key is (month, day) from the updated vision module
        if isinstance(key, tuple):
            month, day_num = key
        else:
            # Legacy format: key is just a day integer
            month = months[0]
            day_num = int(key)

        if isinstance(shift_info, dict):
            shift_code = shift_info.get("code", "")
            ocr_start = shift_info.get("start_time")
            ocr_end = shift_info.get("end_time")
        else:
            # Legacy format: shift_info is just the code string
            shift_code = shift_info
            ocr_start = ocr_end = None

        if shift_code == "DO":
            continue
        if shift_code not in SHIFT_DEFINITIONS:
            continue

        event_year = month_years.get(month, year) if month else year
        if month is None:
            month = months[0]

        max_day = calendar.monthrange(event_year, month)[1]
        if not (1 <= day_num <= max_day):
            continue  # OCR artefact — out of range for this month

        defn = SHIFT_DEFINITIONS[shift_code]

        # Use OCR-detected times when available, fall back to defaults
        if ocr_start:
            sh, sm = _parse_time(ocr_start)
        else:
            sh, sm = defn["start_hour"], defn["start_minute"]

        if ocr_end:
            eh, em = _parse_time(ocr_end)
        else:
            eh, em = defn["end_hour"], defn["end_minute"]

        event_date = date(event_year, month, day_num)
        start_dt = datetime(event_year, month, day_num, sh, sm)
        end_dt = datetime(event_year, month, day_num, eh, em)

        # If end time-of-day is not after start time-of-day, shift crosses midnight
        if eh * 60 + em <= sh * 60 + sm:
            end_dt += timedelta(days=1)

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
