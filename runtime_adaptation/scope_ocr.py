"""Read the oscilloscope time/div dial from a Windows OCR result.

``open_scope`` asks for a 1380 by 900 window. The dial sits in a fixed box on
that bitmap. A uniform scale (a higher DPI capture of the same window) moves
the box with the bitmap. A different aspect ratio keeps the original box and
still has to match a timebase token, so a wrong crop fails closed.
"""
from __future__ import annotations

import re
import unicodedata


REFERENCE_WINDOW = (1380, 900)
REFERENCE_BOX = (866, 947, 850, 880)


def timebase_box(image_size=None) -> tuple[float, float, float, float]:
    x0, x1, y0, y1 = REFERENCE_BOX
    if not image_size:
        return float(x0), float(x1), float(y0), float(y1)
    width, height = image_size
    ref_w, ref_h = REFERENCE_WINDOW
    if width <= 0 or height <= 0:
        return float(x0), float(x1), float(y0), float(y1)
    scale_x, scale_y = width / ref_w, height / ref_h
    if scale_x <= 0 or scale_y <= 0 or abs(scale_x - scale_y) / max(scale_x, scale_y) > 0.02:
        return float(x0), float(x1), float(y0), float(y1)
    return x0 * scale_x, x1 * scale_x, y0 * scale_y, y1 * scale_y


def scope_timebase(ocr, image_size=None) -> str:
    words = [word for line in ocr.get("Lines", []) for word in line.get("Words", [])]
    x0, x1, y0, y1 = timebase_box(image_size)
    selected = sorted((word for word in words if x0 <= word["X"] <= x1 and y0 <= word["Y"] <= y1),
                      key=lambda word: word["X"])
    text = unicodedata.normalize("NFKC", "".join(word["Text"] for word in selected)).replace(" ", "").replace(",", ".")
    if not re.fullmatch(r"(?:\d+(?:\.\d*)?|\.\d+)(?:[munpµμ]?s?)?", text):
        raise RuntimeError(f"Oscilloscope timebase could not be read reliably: {text!r}")
    return text
