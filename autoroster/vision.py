"""Vision module: load a roster screenshot and extract raw shift data via OCR.

Uses only native Python libraries (Pillow, pytesseract, opencv-python).
No AI APIs or cloud services are used.
"""

from __future__ import annotations

import re
from typing import Optional

import cv2
import numpy as np
import pytesseract
from PIL import Image, ImageEnhance

SHIFT_CODES = {"A", "N", "P", "DO"}

# Map OCR noise patterns to correct codes
OCR_CORRECTIONS = {
    "D0": "DO",   # digit zero mistaken for letter O
    "D°": "DO",
    "0O": "DO",
    "DQ": "DO",
    "DN": "DO",  # rare but seen
}

MONTH_NAMES = [
    "january", "february", "march", "april", "may", "june",
    "july", "august", "september", "october", "november", "december",
]
MONTH_ABBREVS = [m[:3] for m in MONTH_NAMES]


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
        ``shifts`` ({date_int: shift_code}).

    Raises:
        ValueError: If the image does not appear to be a roster calendar.
    """
    pil_img = _load_and_enhance(image_path)
    full_text = pytesseract.image_to_string(pil_img)
    ocr_data = pytesseract.image_to_data(pil_img, output_type=pytesseract.Output.DICT)

    month = month_hint or _detect_month(full_text)
    year = year_hint or _detect_year(full_text)

    shifts = _extract_shifts(ocr_data, pil_img.size)

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

    return {"year": year, "month": month, "shifts": shifts}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _load_and_enhance(image_path: str) -> Image.Image:
    """Load the image and apply preprocessing to improve OCR accuracy."""
    # Use OpenCV to deskew and sharpen, then hand off to Pillow/pytesseract
    cv_img = cv2.imread(image_path)
    gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)

    # CLAHE contrast enhancement
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    gray = clahe.apply(gray)

    # Mild sharpening kernel
    kernel = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]], dtype=np.float32)
    gray = cv2.filter2D(gray, -1, kernel)

    pil_img = Image.fromarray(gray).convert("RGB")

    # Additional Pillow contrast boost
    enhancer = ImageEnhance.Contrast(pil_img)
    pil_img = enhancer.enhance(1.5)

    return pil_img


def _detect_month(text: str) -> Optional[int]:
    """Return a month number (1–12) found in OCR text, or None."""
    text_lower = text.lower()
    for i, name in enumerate(MONTH_NAMES):
        if name in text_lower or MONTH_ABBREVS[i] in text_lower:
            return i + 1
    return None


def _detect_year(text: str) -> Optional[int]:
    """Return the first 4-digit year found in OCR text, or None."""
    matches = re.findall(r"\b(20\d{2})\b", text)
    return int(matches[0]) if matches else None


def _clean_token(raw: str) -> str:
    """Normalise a single OCR token to a canonical shift code or date string."""
    upper = raw.strip().upper().strip(".,;:!?-_'\"")
    return OCR_CORRECTIONS.get(upper, upper)


def _extract_shifts(data: dict, image_size: tuple[int, int]) -> dict[int, str]:
    """Match shift codes to their associated date numbers using bounding-box positions.

    Strategy:
    - Collect all words with high enough confidence.
    - Classify each word as a date (1–31) or shift code.
    - For each shift code, find the nearest date that is above it or at
      the same vertical level, within a horizontal distance of one cell width.
    """
    img_w, _ = image_size
    # Estimate one calendar-cell width: 7 columns (Mon–Sun) with some margin
    cell_w = img_w / 7.5

    words: list[dict] = []
    for i in range(len(data["text"])):
        raw = data["text"][i]
        conf = int(data["conf"][i])
        if conf < 25 or not raw.strip():
            continue

        token = _clean_token(raw)
        if not token:
            continue

        left = data["left"][i]
        top = data["top"][i]
        w = data["width"][i]
        h = data["height"][i]

        words.append(
            {
                "token": token,
                "cx": left + w // 2,
                "cy": top + h // 2,
            }
        )

    dates = [w for w in words if w["token"].isdigit() and 1 <= int(w["token"]) <= 31]
    shifts = [w for w in words if w["token"] in SHIFT_CODES]

    result: dict[int, str] = {}

    for shift_w in shifts:
        best_date = None
        best_score = float("inf")

        for date_w in dates:
            dx = abs(shift_w["cx"] - date_w["cx"])
            dy = shift_w["cy"] - date_w["cy"]  # positive = shift is below date

            # Shift code must not be significantly above the date in its cell
            if dy < -40:
                continue
            # Must be in roughly the same column
            if dx > cell_w:
                continue

            score = dx + max(0.0, dy) * 0.3
            if score < best_score:
                best_score = score
                best_date = date_w

        if best_date and best_score < cell_w * 2:
            date_num = int(best_date["token"])
            if date_num not in result:  # first (closest) match wins
                result[date_num] = shift_w["token"]

    return result
