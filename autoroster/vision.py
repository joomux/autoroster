"""Vision module: extract raw shift data from a roster screenshot using Claude.

Claude's vision capabilities understand calendar grid layouts contextually,
handling coloured cell backgrounds, varied fonts, and mixed text without any
image preprocessing or spatial bounding-box logic.
"""

from __future__ import annotations

from typing import Optional

import anthropic
from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Structured output schema
# ---------------------------------------------------------------------------

class _ShiftEntry(BaseModel):
    month: int
    day: int
    code: str                        # "A", "N", "P", or "DO"
    start_time: Optional[str] = None  # 24-hour HH:MM, or null
    end_time: Optional[str] = None    # 24-hour HH:MM, or null


class _RosterData(BaseModel):
    year: Optional[int] = None
    months: list[int]                 # month numbers 1–12, in order of appearance
    shifts: list[_ShiftEntry]


# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

_SYSTEM = """\
You are a data-extraction assistant for shift-worker roster calendar screenshots.

Extract ALL days that show a shift code. The recognised shift codes are:
  A  — day shift
  N  — night shift
  P  — afternoon/PM shift
  DO — day off

For each day with a shift code, extract:
  month      — month number 1–12
  day        — day-of-month 1–31
  code       — exactly one of: A, N, P, DO
  start_time — shift start in 24-hour HH:MM format, or null if not shown
  end_time   — shift end in 24-hour HH:MM format, or null if not shown

Also extract:
  year   — 4-digit year visible in the calendar, or null
  months — all month numbers shown, in the order they appear left-to-right / top-to-bottom

Notes:
• Include DO (day off) entries — do not skip them.
• If a cell shows only "A 12hr" or "N 12hr" without explicit times, set both times to null.
• Times must be in 24-hour HH:MM format (e.g. 07:00, 19:30).
• If a shift spans midnight the end time is still given as a clock time (e.g. 07:30),
  not as a duration.\
"""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_calendar_image(
    image_path: str,
    month_hint: Optional[int] = None,
    year_hint: Optional[int] = None,
) -> dict:
    """Parse a roster calendar screenshot and return raw shift data.

    Args:
        image_path: Path to the image file (PNG or JPEG).
        month_hint: Optional month number (1–12) to supplement Claude's detection.
        year_hint: Optional 4-digit year to override Claude's detection.

    Returns:
        Dict with keys: ``year`` (int|None), ``month`` (int|None),
        ``months`` (list[int]), ``shifts`` ({(month, day): {code, start_time, end_time}}).

    Raises:
        ValueError: If no work shifts are found.
        anthropic.APIError: On API communication failures.
    """
    ext = image_path.rsplit(".", 1)[-1].lower()
    media_type = "image/jpeg" if ext in ("jpg", "jpeg") else "image/png"

    with open(image_path, "rb") as f:
        import base64
        image_b64 = base64.standard_b64encode(f.read()).decode()

    client = anthropic.Anthropic()

    response = client.messages.parse(
        model="claude-opus-4-6",
        max_tokens=2048,
        system=_SYSTEM,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": image_b64,
                        },
                    },
                    {
                        "type": "text",
                        "text": "Extract all shift data from this roster calendar.",
                    },
                ],
            }
        ],
        output_format=_RosterData,
    )

    roster: _RosterData = response.parsed_output

    year = year_hint or roster.year
    months = roster.months
    if month_hint and month_hint not in months:
        months = [month_hint] + months

    # Convert the list of ShiftEntry objects into the (month, day) keyed dict
    # that parser.extract_events expects.
    shifts: dict[tuple[int, int], dict] = {}
    for entry in roster.shifts:
        key = (entry.month, entry.day)
        if key not in shifts:  # first occurrence wins
            shifts[key] = {
                "code": entry.code,
                "start_time": entry.start_time,
                "end_time": entry.end_time,
            }

    non_do = [v for v in shifts.values() if v["code"] != "DO"]
    if not non_do:
        raise ValueError(
            "No work shifts (A, N, P) were found in the image. "
            "Please check that the screenshot shows a roster calendar with shift codes."
        )

    return {
        "year": year,
        "month": months[0] if months else None,
        "months": months,
        "shifts": shifts,
    }
