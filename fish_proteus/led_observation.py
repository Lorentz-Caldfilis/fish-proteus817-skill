"""Observe D0..D7 illumination and PA0 separately, never infer a PB value.

This supports the supplied upright schematic's green circular LEDs with red
outlines, using complete OCR device references and actual pixels. Mask bit n is
the visible state of Dn; it is not an electrical level or an 8255 register bit.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import re
import statistics
from typing import Any

from .pin_observation import _bbox, _ocr_labels, _port_group, _read_pin
from .waveform import _png_rgb


LED_METHOD = "d0-d7-ocr-circular-led-green-fill-black-off-v1"
PA0_METHOD = "8255-u8-ocr-pa0-red-blue-pin-marker-v1"


class LedObservationError(ValueError):
    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.details = details or {}


def _load(image: str | Path, ocr: dict[str, Any] | str | Path, method: str):
    path = Path(image)
    evidence: dict[str, Any] = {"method": method, "image_path": str(path.resolve())}
    try:
        data = path.read_bytes()
        evidence["image_sha256"] = hashlib.sha256(data).hexdigest()
        if isinstance(ocr, dict):
            document = ocr
            raw_ocr = json.dumps(ocr, sort_keys=True, ensure_ascii=False).encode("utf-8")
        else:
            ocr_path = Path(ocr)
            raw_ocr = ocr_path.read_bytes()
            document = json.loads(raw_ocr.decode("utf-8-sig"))
            evidence["ocr_path"] = str(ocr_path.resolve())
        evidence["ocr_sha256"] = hashlib.sha256(raw_ocr).hexdigest()
        width, height, rows = _png_rgb(data)
        evidence["image_size"] = [width, height]
        if not isinstance(document, dict):
            raise ValueError("OCR JSON must be an object")
        return document, rows, width, height, evidence
    except (OSError, ValueError, TypeError) as error:
        raise LedObservationError(f"Cannot load observation inputs: {error}", evidence) from error


def _labels(document: dict[str, Any]) -> list[dict[str, Any]]:
    lines = document.get("Lines")
    if not isinstance(lines, list):
        raise LedObservationError("OCR requires Lines/Words in original-image coordinates")
    result = []
    for line in lines:
        if not isinstance(line, dict) or not isinstance(line.get("Words", []), list):
            raise LedObservationError("Invalid OCR line")
        words = line.get("Words", [])
        if any(not isinstance(word, dict) for word in words):
            raise LedObservationError("Invalid OCR word")
        words = sorted(words, key=lambda word: word.get("X", 0))
        candidates = []
        for i, word in enumerate(words):
            text = str(word.get("Text", "")).strip().upper()
            candidates.append((text, [word]))
            if text == "D" and i+1 < len(words):
                suffix = str(words[i+1].get("Text", "")).strip().upper()
                if re.fullmatch(r"[0-7OI]", suffix):
                    a, b = _bbox(word), _bbox(words[i+1])
                    if -.1*a[3] <= b[0]-a[0]-a[2] <= .7*a[3] and abs(a[1]-b[1]) <= .35*max(a[3], b[3]):
                        candidates.append((text+suffix, [word, words[i+1]]))
        for text, source in candidates:
            if not re.fullmatch(r"D[0-7OI]", text):
                continue
            boxes = [_bbox(word) for word in source]
            x, y = min(b[0] for b in boxes), min(b[1] for b in boxes)
            right, bottom = max(b[0]+b[2] for b in boxes), max(b[1]+b[3] for b in boxes)
            result.append({"name": {"DO": "D0", "DI": "D1"}.get(text, text), "ocr_text": text,
                           "bbox_xywh": [x, y, right-x, bottom-y]})
    return result


def _label_groups(labels: list[dict[str, Any]]) -> list[dict[str, dict[str, Any]]]:
    columns: list[list[dict[str, Any]]] = []
    for label in sorted(labels, key=lambda item: item["bbox_xywh"][0]):
        x, _, _, h = label["bbox_xywh"]
        for column in columns:
            if abs(x-statistics.median(item["bbox_xywh"][0] for item in column)) <= max(2, h*.7):
                column.append(label)
                break
        else:
            columns.append([label])
    result = []
    for column in columns:
        if len(column) != 8 or {item["name"] for item in column} != {f"D{i}" for i in range(8)}:
            continue
        group = {item["name"]: item for item in column}
        h = statistics.median(item["bbox_xywh"][3] for item in column)
        ys = [group[f"D{i}"]["bbox_xywh"][1] for i in range(8)]
        gaps = [b-a for a, b in zip(ys, ys[1:])]
        pitch = statistics.median(gaps)
        if 1.5*h <= pitch <= 5*h and all(abs(g-pitch) <= max(2, pitch*.15) for g in gaps):
            result.append(group)
    if not result:
        raise LedObservationError("Missing, duplicate or unordered D0..D7 labels; no complete LED group",
                                  {"recognized_labels": [label["name"] for label in labels]})
    return result


def _red(rgb) -> bool:
    r, g, b = rgb
    return r >= 70 and r > g*1.8 and r > b*1.8


def _led(rows, width, height, label):
    x, y, w, h = label["bbox_xywh"]
    if x+w > width or y+h > height:
        raise LedObservationError("LED label coordinates are not in the original image")
    roi = [max(0, math.floor(x-4.5*h)), max(0, math.floor(y-.3*h)),
           min(width, math.ceil(x+.3*h)), min(height, math.ceil(y+3.3*h))]
    red = set()
    for py in range(roi[1], roi[3]):
        for px in range(roi[0], roi[2]):
            if _red(rows[py][px*3:px*3+3]):
                red.add((px, py))
    candidates = []
    while red:
        pending, points = [red.pop()], set()
        while pending:
            point = pending.pop()
            points.add(point)
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    neighbor = (point[0]+dx, point[1]+dy)
                    if neighbor in red:
                        red.remove(neighbor)
                        pending.append(neighbor)
        bx, by = min(p[0] for p in points), min(p[1] for p in points)
        bw, bh = max(p[0] for p in points)-bx+1, max(p[1] for p in points)-by+1
        # Real Proteus LED symbols join the red circle to horizontal red leads.
        # The vertical span and outer row centers identify the circle, whereas
        # the connected component's full width includes those leads.
        if not (1.8*h <= bh <= 3.3*h and bw >= .8*bh):
            continue
        cy, radius = by+(bh-1)/2, (bh-1)/2
        outer_rows = [py for py in range(by, by+bh) if abs(py-cy) > radius*.3]
        row_centers = [(min(px for px, yrow in points if yrow == py)+max(px for px, yrow in points if yrow == py))/2
                       for py in outer_rows if any(yrow == py for _, yrow in points)]
        if not row_centers:
            continue
        cx = statistics.median(row_centers)
        if cx-radius < roi[0] or cx+radius >= roi[2]:
            continue
        tolerance = max(2, radius*.12)
        supported = 0
        for angle in (i*math.pi/4 for i in range(8)):
            target = (cx+math.cos(angle)*radius, cy+math.sin(angle)*radius)
            supported += any((px-target[0])**2+(py-target[1])**2 <= tolerance**2 for px, py in points)
        if supported >= 7:
            candidates.append((cx, cy, radius, [cx-radius, by, bh, bh]))
    details = {"label": label["name"], "ocr_text": label["ocr_text"], "label_bbox_xywh": label["bbox_xywh"], "search_roi_xyxy": roi}
    if len(candidates) != 1:
        raise LedObservationError(f"{label['name']}: no unique red circular LED outline", {**details, "candidate_count": len(candidates)})
    cx, cy, radius, box = candidates[0]
    counts = {"green": 0, "black": 0, "other": 0}
    points = {"green": [], "black": []}
    for py in range(math.ceil(cy-radius*.78), math.floor(cy+radius*.78)+1):
        for px in range(math.ceil(cx-radius*.78), math.floor(cx+radius*.78)+1):
            if (px-cx)**2+(py-cy)**2 > (radius*.78)**2:
                continue
            rgb = rows[py][px*3:px*3+3]
            r, g, b = rgb
            kind = "green" if g >= 90 and r < g*.45 and b < g*.45 else "black" if max(rgb) <= 35 else "other"
            counts[kind] += 1
            if kind in points:
                points[kind].append((px, py))
    total = sum(counts.values())
    green, black = counts["green"]/total, counts["black"]/total
    if green >= .35 and black <= .08:
        on, color = 1, "green"
    elif black >= .50 and green <= .02:
        on, color = 0, "black"
    else:
        raise LedObservationError(f"{label['name']}: ambiguous LED interior colors",
                                  {**details, "circle_bbox_xywh": box, "interior_counts": counts})
    sample = min(points[color], key=lambda p: (p[0]-cx)**2+(p[1]-cy)**2)
    return {**details, "on": on, "circle_bbox_xywh": box, "center_xy": [cx, cy], "radius_pixels": radius,
            "interior_counts": counts, "green_fraction": green, "black_fraction": black,
            "sample_xy": list(sample), "sample_rgb": list(rows[sample[1]][sample[0]*3:sample[0]*3+3])}


def observe_leds(image: str | Path, ocr: dict[str, Any] | str | Path) -> dict[str, Any]:
    """Observe only LED display states: bit n in led_mask denotes Dn illumination."""
    document, rows, width, height, evidence = _load(image, ocr, LED_METHOD)
    try:
        groups = _label_groups(_labels(document))
        accepted, failures = [], []
        for group in groups:
            try:
                leds = {f"D{i}": _led(rows, width, height, group[f"D{i}"]) for i in range(8)}
                centers = [value["center_xy"][0] for value in leds.values()]
                h = statistics.median(label["bbox_xywh"][3] for label in group.values())
                if max(centers)-min(centers) > max(2, h*.5):
                    raise LedObservationError("LED circles do not share one column")
                accepted.append(leds)
            except LedObservationError as error:
                failures.append({"error": str(error), **error.details})
        if len(accepted) != 1:
            raise LedObservationError("No unique complete D0..D7 LED observation", {"candidate_failures": failures})
        leds = accepted[0]
        bits = [leds[f"D{i}"]["on"] for i in range(8)]
        return {**evidence, "led_mask": sum(value << i for i, value in enumerate(bits)),
                "led_bits": bits, "led_bits_lsb_first": bits, "leds": leds,
                "limitations": "LED display only: mask bit n denotes Dn illumination, not an 8255 port register or pin level; port mapping requires separate circuit evidence"}
    except (ValueError, TypeError) as error:
        details = error.details if isinstance(error, LedObservationError) else {}
        raise LedObservationError(str(error), {**evidence, **details}) from error


def observe_pa0(image: str | Path, pin_ocr: dict[str, Any] | str | Path) -> dict[str, Any]:
    """Read PA0's actual red/blue marker without assigning values to grey PB pins."""
    document, rows, width, height, evidence = _load(image, pin_ocr, PA0_METHOD)
    try:
        reference, group = _port_group(_ocr_labels(document))
        pin = _read_pin(rows, width, height, group["PA0"])
        return {**evidence, "input_bit": pin["bit"], "pin": pin,
                "component_label_bbox_xywh": reference["bbox_xywh"],
                "limitations": "Reads PA0 only; no PB electrical state or register value is inferred"}
    except (ValueError, TypeError) as error:
        raise LedObservationError(str(error), {**evidence, **getattr(error, "details", {})}) from error
