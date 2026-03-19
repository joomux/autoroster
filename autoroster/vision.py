"""Vision module: extract raw shift data from a roster screenshot.

Uses Google Cloud Vision API for robust OCR that handles coloured cell
backgrounds, varied fonts, and mixed layouts without manual preprocessing.
No other AI APIs or cloud services are used.
"""

from __future__ import annotations

import re
from typing import Optional

from google.cloud import vision
from PIL import Image

SHIFT_CODES = {"A", "N", "P", "DO"}

# Map common OCR noise patterns to correct codes
OCR_CORRECTIONS = {
    "D0": "DO",   # digit zero mistaken for letter O
    "D°": "DO",
    "0O": "DO",
    "DQ": "DO",
    "DN": "DO",
}

MONTH_NAMES = [
    "january", "february", "march", "april", "may", "june",
    "july", "august", "september", "october", "november", "december",
]
MONTH_ABBREVS = [m[:3] for m in MONTH_NAMES]

TIME_RE = re.compile(r"^\d{1,2}:\d{2}$")


def parse_calendar_image(
    image_path: str,
    month_hint: Optional[int] = None,
    year_hint: Optional[int] = None,
) -> dict:
    """Parse a roster calendar screenshot and return raw shift data.

    Args:
        image_path: Path to the image file.
        month_hint: Optional month number (1–12) to override OCR detection.
        year_hint: Optional 4-digit year to override OCR detection.

    Returns:
        Dict with keys: ``year`` (int|None), ``month`` (int|None),
        ``months`` (list[int]), ``shifts`` ({(month, day): {code, start_time, end_time}}).

    Raises:
        ValueError: If the image does not appear to be a roster calendar.
    """
    words, image_size, full_text = _call_vision_api(image_path)

    detected_months = _detect_months(full_text)
    months = detected_months if detected_months else ([month_hint] if month_hint else [])

    year = year_hint or _detect_year(full_text)

    shifts = _extract_shifts(words, image_size, months)

    if not shifts:
        raise ValueError(
            "No shift codes (A, N, P, DO) were found in the image. "
            "Please check that the screenshot shows a roster calendar."
        )
    if len(shifts) < 3:
        raise ValueError(
            "Only a small number of shifts were detected. "
            "Ensure the full calendar is visible and the image is clear."
        )

    return {
        "year": year,
        "month": months[0] if months else None,
        "months": months,
        "shifts": shifts,
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _call_vision_api(image_path: str) -> tuple[list[dict], tuple[int, int], str]:
    """Send the image to Google Cloud Vision and return (words, image_size, full_text).

    Uses document_text_detection which preserves word-level bounding boxes and
    handles dense, structured text (such as calendar grids) better than the
    basic text_detection endpoint.
    """
    client = vision.ImageAnnotatorClient()

    with open(image_path, "rb") as f:
        content = f.read()

    response = client.document_text_detection(image=vision.Image(content=content))

    if response.error.message:
        raise ValueError(f"Google Vision API error: {response.error.message}")

    if not response.full_text_annotation.pages:
        return [], _pil_size(image_path), ""

    full_text = response.full_text_annotation.text or ""
    page = response.full_text_annotation.pages[0]

    # page.width/height are 0 when Vision can't determine them — fall back to PIL.
    if page.width and page.height:
        image_size: tuple[int, int] = (page.width, page.height)
    else:
        image_size = _pil_size(image_path)

    words: list[dict] = []
    for block in page.blocks:
        for paragraph in block.paragraphs:
            for word in paragraph.words:
                text = "".join(s.text for s in word.symbols)
                token = _clean_token(text)
                if not token:
                    continue
                verts = word.bounding_box.vertices
                xs = [v.x for v in verts]
                ys = [v.y for v in verts]
                words.append({
                    "token": token,
                    "cx": sum(xs) // 4,
                    "cy": sum(ys) // 4,
                    "top": min(ys),
                    "left": min(xs),
                })

    return words, image_size, full_text


def _pil_size(image_path: str) -> tuple[int, int]:
    with Image.open(image_path) as img:
        return img.size


def _detect_months(text: str) -> list[int]:
    """Return month numbers (1–12) found in OCR text, in the order they appear."""
    text_lower = text.lower()
    positions: list[tuple[int, int]] = []
    for i, name in enumerate(MONTH_NAMES):
        for pattern in [name, MONTH_ABBREVS[i]]:
            idx = text_lower.find(pattern)
            if idx != -1:
                positions.append((idx, i + 1))
                break
    positions.sort()
    seen: set[int] = set()
    result: list[int] = []
    for _, month_num in positions:
        if month_num not in seen:
            result.append(month_num)
            seen.add(month_num)
    return result


def _detect_year(text: str) -> Optional[int]:
    """Return the first 4-digit year found in OCR text, or None."""
    matches = re.findall(r"\b(20\d{2})\b", text)
    return int(matches[0]) if matches else None


def _clean_token(raw: str) -> str:
    """Normalise a single OCR token to a canonical shift code or date string."""
    upper = raw.strip().upper().strip(".,;:!?-_'\"")
    return OCR_CORRECTIONS.get(upper, upper)


def _find_nearby_times(
    shift_w: dict, time_words: list[dict], cell_w: float
) -> tuple[Optional[str], Optional[str]]:
    """Return (start_time, end_time) strings found within the same cell as shift_w."""
    nearby: list[tuple[int, str]] = []
    for tw in time_words:
        dx = abs(shift_w["cx"] - tw["cx"])
        dy = tw["cy"] - shift_w["cy"]  # positive = time word is below shift code
        if dx <= cell_w and -20 <= dy <= cell_w * 1.5:
            nearby.append((tw["left"], tw["token"]))
    nearby.sort()
    tokens = [t for _, t in nearby]
    if len(tokens) >= 2:
        return tokens[0], tokens[1]
    if len(tokens) == 1:
        return tokens[0], None
    return None, None


def _extract_shifts(
    words: list[dict], image_size: tuple[int, int], months: list[int]
) -> dict[tuple[Optional[int], int], dict]:
    """Match shift codes to their associated (month, day) using bounding-box positions.

    Returns:
        Dict mapping (month, day) → {"code": str, "start_time": str|None, "end_time": str|None}.
        Month is None if it could not be determined.
    """
    img_w, _ = image_size
    cell_w = img_w / 7.5

    dates = [w for w in words if w["token"].isdigit() and 1 <= int(w["token"]) <= 31]
    shift_words = [w for w in words if w["token"] in SHIFT_CODES]
    time_words = [w for w in words if TIME_RE.match(w["token"])]

    # Assign a month to each date word by walking top→bottom, left→right.
    # When the day number resets (e.g. 28 → 1) we advance to the next month.
    sorted_dates = sorted(dates, key=lambda w: (w["top"], w["left"]))
    month_for_pos: dict[tuple[int, int], Optional[int]] = {}
    current_month_idx = 0
    prev_day = -1
    for dw in sorted_dates:
        day = int(dw["token"])
        if day < prev_day - 15 and current_month_idx + 1 < len(months):
            current_month_idx += 1
        month = months[current_month_idx] if months else None
        month_for_pos[(dw["cx"], dw["cy"])] = month
        prev_day = day

    result: dict[tuple[Optional[int], int], dict] = {}

    for shift_w in shift_words:
        best_date = None
        best_score = float("inf")
        max_above = cell_w * 0.5  # shift code may sit above the date number

        for date_w in dates:
            dx = abs(shift_w["cx"] - date_w["cx"])
            dy = shift_w["cy"] - date_w["cy"]  # positive = shift below date

            if dy < -max_above:
                continue
            if dx > cell_w:
                continue

            score = dx + max(0.0, dy) * 0.3
            if score < best_score:
                best_score = score
                best_date = date_w

        if best_date and best_score < cell_w * 2:
            day_num = int(best_date["token"])
            month = month_for_pos.get((best_date["cx"], best_date["cy"]))
            key = (month, day_num)
            if key not in result:
                start_t, end_t = _find_nearby_times(shift_w, time_words, cell_w)
                result[key] = {
                    "code": shift_w["token"],
                    "start_time": start_t,
                    "end_time": end_t,
                }

    return result
