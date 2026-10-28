"""Measure clean two-level Proteus scope traces from PNG pixels, without a model.

The visible adjacent green grid lines are treated as one horizontal division.
Only an unrotated, unobscured scope plot with at least four grid lines per axis
and resolved yellow (A) or cyan (B) rails is supported. Timebase text must come
from the UI; this module neither reads a job's expectations nor infers a divisor.
PNG support is deliberately limited to non-interlaced 8-bit RGB/RGBA captures.
"""
from __future__ import annotations

import hashlib
import math
from pathlib import Path
import re
import statistics
import struct
from typing import Any
import zlib


METHOD = "scope-pixels-green-grid-same-direction-edges-v1"


class WaveformError(ValueError):
    """A screenshot cannot support a frequency measurement; details are evidence."""

    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.details = details or {}


def _timebase(text: str) -> float:
    if not isinstance(text, str):
        raise WaveformError("Timebase must be UI text with an explicit time unit")
    match = re.fullmatch(r"\s*(\d+(?:\.\d*)?|\.\d+)\s*(n|u|µ|μ|m|s)(?:s)?\s*(?:/\s*div)?\s*", text)
    if not match:
        raise WaveformError("Unsupported timebase: use explicit units such as 1u, 500ns, 2ms or 1s")
    unit = match.group(2)
    if unit == "s" and re.search(r"ss", text):
        raise WaveformError("Unsupported timebase unit")
    value = float(match.group(1)) * {"n": 1e-9, "u": 1e-6, "µ": 1e-6, "μ": 1e-6, "m": 1e-3, "s": 1}[unit]
    if not math.isfinite(value) or value <= 0:
        raise WaveformError("Timebase must be positive and finite")
    return value


def _png_rgb(data: bytes) -> tuple[int, int, list[bytes]]:
    """Decode PNG filters 0..4 using the standard library; check the CRCs."""
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise WaveformError("Not a PNG image")
    cursor, header, compressed, ended = 8, None, bytearray(), False
    while cursor < len(data):
        if cursor + 12 > len(data):
            raise WaveformError("Truncated PNG chunk")
        length = struct.unpack_from(">I", data, cursor)[0]
        kind = data[cursor+4:cursor+8]
        end = cursor + 12 + length
        if end > len(data):
            raise WaveformError("Truncated PNG chunk payload")
        payload = data[cursor+8:cursor+8+length]
        crc = struct.unpack_from(">I", data, cursor+8+length)[0]
        if zlib.crc32(kind + payload) & 0xffffffff != crc:
            raise WaveformError("PNG CRC mismatch")
        if kind == b"IHDR":
            if header is not None or len(payload) != 13:
                raise WaveformError("Invalid PNG header")
            header = struct.unpack(">IIBBBBB", payload)
        elif kind == b"IDAT":
            compressed.extend(payload)
        elif kind == b"IEND":
            ended = True
            break
        cursor = end
    if header is None or not ended:
        raise WaveformError("Incomplete PNG image")
    width, height, depth, color, compression, filtering, interlace = header
    if depth != 8 or color not in (2, 6) or compression or filtering or interlace:
        raise WaveformError("Only non-interlaced 8-bit RGB/RGBA PNG captures are supported")
    if width < 32 or height < 32 or width * height > 12_000_000:
        raise WaveformError("Unsupported PNG dimensions")
    components = 3 if color == 2 else 4
    stride = width * components
    expected_size = height * (stride + 1)
    try:
        decoder = zlib.decompressobj()
        raw = decoder.decompress(bytes(compressed), expected_size + 1)
    except zlib.error as error:
        raise WaveformError("Invalid PNG compressed data") from error
    if len(raw) != expected_size or not decoder.eof or decoder.unused_data:
        raise WaveformError("PNG decoded length does not match its dimensions")
    previous, rows = bytes(stride), []
    for y in range(height):
        offset = y * (stride + 1)
        filter_type = raw[offset]
        row = bytearray(raw[offset+1:offset+1+stride])
        if filter_type not in range(5):
            raise WaveformError("Unsupported PNG row filter")
        if filter_type:
            for i in range(stride):
                left = row[i-components] if i >= components else 0
                above = previous[i]
                upper_left = previous[i-components] if i >= components else 0
                if filter_type == 1:
                    predictor = left
                elif filter_type == 2:
                    predictor = above
                elif filter_type == 3:
                    predictor = (left + above) // 2
                else:
                    p = left + above - upper_left
                    pa, pb, pc = abs(p-left), abs(p-above), abs(p-upper_left)
                    predictor = left if pa <= pb and pa <= pc else above if pb <= pc else upper_left
                row[i] = (row[i] + predictor) & 255
        previous = bytes(row)
        if components == 3:
            rows.append(previous)
        else:
            rgb = bytearray(width * 3)
            # Composite transparency onto black; invisible colors cannot be evidence.
            for x in range(width):
                a = row[x*4+3]
                for c in range(3):
                    rgb[x*3+c] = row[x*4+c] * a // 255
            rows.append(bytes(rgb))
    return width, height, rows


def _groups(values: list[int]) -> list[list[int]]:
    result: list[list[int]] = []
    for value in values:
        if not result or value > result[-1][-1] + 1:
            result.append([value])
        else:
            result[-1].append(value)
    return result


def _grid_spacing(positions: list[float]) -> float:
    if len(positions) < 4:
        raise WaveformError("Cannot calibrate green grid: fewer than four lines")
    gaps = [b-a for a, b in zip(positions, positions[1:])]
    spacing = statistics.median(gaps)
    if spacing < 4 or sum(abs(g-spacing) <= max(1.5, spacing*.06) for g in gaps) < 2:
        raise WaveformError("Cannot calibrate green grid spacing")
    if any(abs(g - round(g/spacing)*spacing) > max(1.5, spacing*.06) for g in gaps):
        raise WaveformError("Cannot calibrate an irregular green grid")
    return spacing


def _grid(width: int, height: int, rows: list[bytes]) -> dict[str, Any]:
    green_by_row: list[list[int]] = []
    for row in rows:
        pixels = []
        for x in range(width):
            r, g, b = row[x*3:x*3+3]
            if g >= 24 and g > r * 1.8 and g > b * 1.8:
                pixels.append(x)
        green_by_row.append(pixels)
    largest_row = max(map(len, green_by_row), default=0)
    if largest_row < 48:
        raise WaveformError("Cannot calibrate: no visible green scope grid")
    y_lines = [statistics.median(group) for group in _groups([
        y for y, pixels in enumerate(green_by_row) if len(pixels) >= max(48, largest_row*.65)
    ])]
    _grid_spacing(y_lines)
    top, bottom = math.ceil(y_lines[0]), math.floor(y_lines[-1])
    columns = [0] * width
    for y in range(top, bottom+1):
        for x in green_by_row[y]:
            columns[x] += 1
    threshold = (bottom-top+1) * .65
    x_lines = [statistics.median(group) for group in _groups([
        x for x, count in enumerate(columns) if count >= threshold
    ])]
    spacing = _grid_spacing(x_lines)
    left, right = math.ceil(x_lines[0]), math.floor(x_lines[-1])
    if right-left < spacing*3:
        raise WaveformError("Visible scope grid is too narrow")
    return {"crop_xyxy": [left, top, right+1, bottom+1], "grid_x": x_lines,
            "grid_y": y_lines, "pixels_per_div": spacing}


def _trace(rows: list[bytes], grid: dict[str, Any], channel: str) -> dict[str, Any]:
    left, top, right, bottom = grid["crop_xyxy"]
    # Exclude the border from waveform detection; reported edge positions stay absolute.
    left, top, right, bottom = left+1, top+1, right-1, bottom-1
    by_column: list[list[int]] = [[] for _ in range(right-left)]
    histogram = [0] * (bottom-top)
    for y in range(top, bottom):
        row = rows[y]
        for x in range(left, right):
            r, g, b = row[x*3:x*3+3]
            visible = (r >= 100 and g >= 100 and b <= min(r, g)*.45) if channel == "A" else (
                g >= 100 and b >= 100 and r <= min(g, b)*.45)
            if visible:
                by_column[x-left].append(y)
                histogram[y-top] += 1
    maximum = max(histogram, default=0)
    if maximum < 8:
        raise WaveformError(f"No resolved channel {channel} waveform")
    rails = _groups([y+top for y, count in enumerate(histogram) if count >= max(4, maximum*.20)])
    if len(rails) != 2 or rails[1][0]-rails[0][-1] < 4:
        raise WaveformError("Waveform does not have two resolved horizontal levels")
    high_y, low_y = statistics.median(rails[0]), statistics.median(rails[1])
    high_band = (rails[0][0]-1, rails[0][-1]+1)
    low_band = (rails[1][0]-1, rails[1][-1]+1)
    rising, falling = [], []
    previous_state = previous_x = None
    definite, discontinuities = 0, 0
    for i, ys in enumerate(by_column):
        high = any(high_band[0] <= y <= high_band[1] for y in ys)
        low = any(low_band[0] <= y <= low_band[1] for y in ys)
        if high == low:
            continue
        x, state = i+left, int(high)
        definite += 1
        if previous_state is not None:
            if x-previous_x > 5:
                discontinuities += 1
            elif state != previous_state:
                (rising if state else falling).append((previous_x+x)/2)
        previous_x, previous_state = x, state
    details = {"rising_edges_x": rising, "falling_edges_x": falling,
               "rail_y": [high_y, low_y], "trace_coverage": definite / max(1, right-left)}
    if discontinuities or details["trace_coverage"] < .75:
        raise WaveformError("Waveform is discontinuous or too poorly resolved", details)
    # Prefer the direction with more complete repeated edges; never mix directions.
    direction, edges = ("rising", rising) if len(rising) >= len(falling) else ("falling", falling)
    if len(edges) < 2:
        raise WaveformError("Fewer than two same-direction waveform edges; no period can be measured", details)
    periods = [b-a for a, b in zip(edges, edges[1:])]
    period = statistics.median(periods)
    if period < 8 or any(abs(p-period) > max(2.0, period*.05) for p in periods):
        raise WaveformError("Waveform periods are unresolved or inconsistent", {**details, "period_samples_pixels": periods})
    return {**details, "edge_direction": direction, "edge_x": edges,
            "period_samples_pixels": periods, "period_pixels": period,
            "period_spread_pixels": max(periods)-min(periods)}


def measure_scope(path: str | Path, timebase_text: str, channel: str = "A") -> dict[str, Any]:
    """Return screenshot-derived frequency, or raise WaveformError with evidence.

    ``timebase_seconds`` means seconds per visible grid division. ``edge_x`` is
    the absolute screenshot x coordinate of every selected same-direction edge.
    Pixel quantization, finite capture length and the supplied UI timebase limit
    precision; a result is a screenshot measurement, not a direct simulator probe.
    """
    image_path = Path(path)
    evidence: dict[str, Any] = {"method": METHOD, "image_path": str(image_path.resolve()),
                                "timebase_text": timebase_text, "channel": channel}
    try:
        data = image_path.read_bytes()
    except OSError as error:
        raise WaveformError(f"Cannot read scope PNG: {error}", evidence) from error
    evidence["image_sha256"] = hashlib.sha256(data).hexdigest()
    try:
        if channel not in ("A", "B"):
            raise WaveformError("Only yellow channel A and cyan channel B are supported")
        seconds = _timebase(timebase_text)
        width, height, rows = _png_rgb(data)
        evidence.update({"image_size": [width, height], "timebase_seconds": seconds})
        grid = _grid(width, height, rows)
        evidence.update(grid)
        trace = _trace(rows, grid, channel)
        period_seconds = trace["period_pixels"] / grid["pixels_per_div"] * seconds
        if not math.isfinite(period_seconds) or period_seconds <= 0:
            raise WaveformError("Measured time interval is outside the numeric range", trace)
        return {**evidence, **trace, "period_seconds": period_seconds,
                "frequency_hz": 1 / period_seconds,
                "limitations": "Screenshot pixel measurement; adjacent visible green lines define one division; clean two-level trace required"}
    except WaveformError as error:
        error.details = {**evidence, **error.details}
        raise
