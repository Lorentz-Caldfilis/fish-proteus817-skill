"""One multiplier for automation deadlines. The default scale is 1.

``FISH_PROTEUS_TIMEOUT_SCALE`` stretches wall-clock waits (launch, menus,
timed runs, OCR, NASM). It does not change a requested simulation duration,
a tolerance, or the 1..60 second limit on simulated time. Unset or ``1``
keeps every built-in deadline.
"""
from __future__ import annotations

import math
import os


ENV = "FISH_PROTEUS_TIMEOUT_SCALE"
MAX_SCALE = 30.0


def timeout_scale() -> float:
    """Return the positive multiplier, or 1 when the variable is unset."""
    raw = os.environ.get(ENV, "").strip()
    if not raw:
        return 1.0
    try:
        value = float(raw)
    except ValueError as exc:
        raise ValueError(f"{ENV} must be a positive number (for example 3), got {raw!r}") from exc
    if not math.isfinite(value) or value <= 0 or value > MAX_SCALE:
        raise ValueError(f"{ENV} must be greater than 0 and at most {MAX_SCALE:g}, got {raw!r}")
    return value


def scaled(seconds: float) -> float:
    """Apply the multiplier once. Callers pass the nominal deadline."""
    return float(seconds) * timeout_scale()
