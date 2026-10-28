"""Read U8's PA0 and PB0..PB7 from actual OCR positions and pin-marker colors.

This supports the supplied, upright 8255 schematic layout. OCR must identify U8,
PA0 and every PB bit; source-net names such as PBY0 do not identify PB0. A split
``PB`` / ``1`` token may be joined, and PAO/PBO may denote zero only after the
complete aligned U8 port group is established. No missing bit is interpolated.
The small pin-state squares are red=1 / blue=0; LED appearance is not sampled.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import re
import statistics
from typing import Any

from .waveform import WaveformError, _png_rgb


METHOD = "8255-u8-ocr-labels-adjacent-red-blue-pin-markers-v1"


class PinObservationError(ValueError):
    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.details = details or {}


def _bbox(word: dict[str, Any]) -> list[float]:
    values = [word.get(key) for key in ("X", "Y", "Width", "Height")]
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in values):
        raise PinObservationError("OCR word has invalid image coordinates")
    x, y, width, height = values
    if x < 0 or y < 0 or width <= 0 or height <= 0:
        raise PinObservationError("OCR word has invalid bounds")
    return [float(v) for v in values]


def _ocr_labels(document: dict[str, Any]) -> list[dict[str, Any]]:
    lines = document.get("Lines")
    if not isinstance(lines, list):
        raise PinObservationError("OCR must contain Lines with Words in original-image coordinates")
    labels = []
    for line in lines:
        if not isinstance(line, dict):
            raise PinObservationError("Invalid OCR line object")
        words = line.get("Words", [])
        if not isinstance(words, list) or any(not isinstance(word, dict) for word in words):
            raise PinObservationError("Invalid OCR Words list")
        words = sorted(words, key=lambda word: word.get("X", 0))
        candidates = []
        for i, word in enumerate(words):
            text = str(word.get("Text", "")).strip().upper()
            candidates.append((text, [word]))
            if text in ("PA", "PB", "U") and i+1 < len(words):
                next_word = words[i+1]
                suffix = str(next_word.get("Text", "")).strip().upper()
                if re.fullmatch(r"[0-8O]", suffix):
                    a, b = _bbox(word), _bbox(next_word)
                    gap = b[0]-(a[0]+a[2])
                    if -.1*a[3] <= gap <= .7*a[3] and abs(a[1]-b[1]) <= .35*max(a[3], b[3]):
                        candidates.append((text+suffix, [word, next_word]))
        for text, source_words in candidates:
            if text != "U8" and not re.fullmatch(r"P[AB][0-7O]", text):
                continue
            boxes = [_bbox(word) for word in source_words]
            x, y = min(b[0] for b in boxes), min(b[1] for b in boxes)
            right, bottom = max(b[0]+b[2] for b in boxes), max(b[1]+b[3] for b in boxes)
            normalized = text[:-1]+"0" if text in ("PAO", "PBO") else text
            labels.append({"name": normalized, "ocr_text": text,
                           "bbox_xywh": [x, y, right-x, bottom-y],
                           "source_words": source_words})
    return labels


def _port_group(labels: list[dict[str, Any]]) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    references = [label for label in labels if label["name"] == "U8"]
    if len(references) != 1:
        raise PinObservationError("OCR must identify exactly one U8 component reference", {"u8_reference_count": len(references)})
    reference = references[0]
    rx, ry, _, _ = reference["bbox_xywh"]
    pb_labels = [label for label in labels if label["name"].startswith("PB")]
    groups: list[list[dict[str, Any]]] = []
    for label in sorted(pb_labels, key=lambda item: item["bbox_xywh"][0]):
        x, y, _, height = label["bbox_xywh"]
        if not (2*height < x-rx < 25*height and 5*height < y-ry < 45*height):
            continue
        for group in groups:
            if abs(x-statistics.median(item["bbox_xywh"][0] for item in group)) <= max(2, height*.6):
                group.append(label)
                break
        else:
            groups.append([label])
    accepted, failures = [], []
    required = {f"PB{bit}" for bit in range(8)}
    for group in groups:
        names = [label["name"] for label in group]
        missing = sorted(required-set(names))
        if missing or len(names) != 8:
            failures.append({"missing": missing, "found": names})
            continue
        pins = {label["name"]: label for label in group}
        height = statistics.median(label["bbox_xywh"][3] for label in group)
        ys = [pins[f"PB{bit}"]["bbox_xywh"][1] for bit in range(8)]
        gaps = [b-a for a, b in zip(ys, ys[1:])]
        pitch = statistics.median(gaps)
        if not (1.1*height <= pitch <= 3*height) or any(abs(g-pitch) > max(1.5, pitch*.15) for g in gaps):
            failures.append({"error": "PB0..PB7 labels do not form an ordered regular port group"})
            continue
        px = statistics.median(label["bbox_xywh"][0] for label in group)
        pa0 = [label for label in labels if label["name"] == "PA0"
               and abs(label["bbox_xywh"][0]-px) <= max(2, height*.6)
               and ry < label["bbox_xywh"][1] < ys[0]
               and 7.5*pitch <= ys[0]-label["bbox_xywh"][1] <= 10.5*pitch]
        if len(pa0) != 1:
            failures.append({"error": "PA0 is missing or ambiguous in the aligned U8 port column"})
            continue
        pins["PA0"] = pa0[0]
        accepted.append(pins)
    if len(accepted) != 1:
        raise PinObservationError("Cannot locate one complete U8 PA0/PB0..PB7 label group; missing or ambiguous labels",
                                  {"accepted_port_groups": len(accepted), "label_group_failures": failures,
                                   "recognized_labels": [label["name"] for label in labels]})
    return reference, accepted[0]


def _state(rgb: tuple[int, int, int]) -> int | None:
    r, g, b = rgb
    if r >= 110 and r > g*1.6 and r > b*1.6:
        return 1
    if b >= 110 and b > r*1.6 and b > g*1.6:
        return 0
    return None


def _read_pin(rows: list[bytes], width: int, height: int, label: dict[str, Any]) -> dict[str, Any]:
    x, y, text_width, text_height = label["bbox_xywh"]
    if x+text_width > width or y+text_height > height:
        raise PinObservationError("OCR coordinates extend outside the original screenshot")
    left = max(0, math.floor(x+text_width+.3*text_height))
    right = min(width, math.ceil(x+text_width+4*text_height))
    top = max(0, math.floor(y-1.25*text_height))
    bottom = min(height, math.ceil(y+.6*text_height))
    colored: dict[tuple[int, int], int] = {}
    for py in range(top, bottom):
        for px in range(left, right):
            value = _state(tuple(rows[py][px*3:px*3+3]))
            if value is not None:
                colored[(px, py)] = value
    remaining, candidates = set(colored), []
    while remaining:
        pending, points = [remaining.pop()], []
        while pending:
            point = pending.pop()
            points.append(point)
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    neighbor = (point[0]+dx, point[1]+dy)
                    if neighbor in remaining:
                        remaining.remove(neighbor)
                        pending.append(neighbor)
        xs, ys = [p[0] for p in points], [p[1] for p in points]
        bx, by, bw, bh = min(xs), min(ys), max(xs)-min(xs)+1, max(ys)-min(ys)+1
        if (max(2, text_height*.25) <= min(bw, bh) and max(bw, bh) <= text_height*1.2
                and .55 <= bw/bh <= 1.8 and len(points)/(bw*bh) >= .65):
            candidates.append((points, [bx, by, bw, bh]))
    evidence = {"label": label["name"], "ocr_text": label["ocr_text"],
                "label_bbox_xywh": label["bbox_xywh"], "search_roi_xyxy": [left, top, right, bottom]}
    if len(candidates) != 1:
        raise PinObservationError(f"{label['name']}: no unique compact red/blue pin marker", {**evidence, "candidate_count": len(candidates)})
    points, box = candidates[0]
    states = {colored[point] for point in points}
    if len(states) != 1:
        raise PinObservationError(f"{label['name']}: mixed red/blue pin marker", evidence)
    center_x = statistics.mean(p[0] for p in points)
    center_y = statistics.mean(p[1] for p in points)
    sample = min(points, key=lambda p: (p[0]-center_x)**2+(p[1]-center_y)**2)
    samples = sorted(set([sample, min(points), max(points), min(points, key=lambda p: p[1]), max(points, key=lambda p: p[1])]))
    return {**evidence, "bit": next(iter(states)), "marker_bbox_xywh": box,
            "marker_center_xy": [center_x, center_y], "sample_xy": list(sample),
            "sample_rgb": list(rows[sample[1]][sample[0]*3:sample[0]*3+3]),
            "colored_pixel_count": len(points),
            "pixel_samples": [{"xy": list(p), "rgb": list(rows[p[1]][p[0]*3:p[0]*3+3])} for p in samples]}


def observe_8255(image_path: str | Path, ocr_json_or_path: dict[str, Any] | str | Path) -> dict[str, Any]:
    """Read PA0 and the PB byte; reject missing labels or uncertain colors.

    OCR coordinates must address the original image. If OCR was run on a crop or
    enlarged copy, the caller must preserve that evidence and map coordinates
    back first. Marker search distances scale with the observed label height.
    """
    path = Path(image_path)
    evidence: dict[str, Any] = {"method": METHOD, "image_path": str(path.resolve())}
    try:
        data = path.read_bytes()
        evidence["image_sha256"] = hashlib.sha256(data).hexdigest()
        if isinstance(ocr_json_or_path, dict):
            document = ocr_json_or_path
            ocr_data = json.dumps(document, ensure_ascii=False, sort_keys=True).encode("utf-8")
        else:
            ocr_path = Path(ocr_json_or_path)
            ocr_data = ocr_path.read_bytes()
            document = json.loads(ocr_data.decode("utf-8-sig"))
            evidence["ocr_path"] = str(ocr_path.resolve())
        evidence["ocr_sha256"] = hashlib.sha256(ocr_data).hexdigest()
        width, height, rows = _png_rgb(data)
        evidence["image_size"] = [width, height]
        if not isinstance(document, dict):
            raise PinObservationError("OCR JSON must be an object")
        labels = _ocr_labels(document)
        reference, group = _port_group(labels)
        evidence["component_reference"] = "U8"
        evidence["component_label_bbox_xywh"] = reference["bbox_xywh"]
        pins: dict[str, dict[str, Any]] = {}
        for name in ["PA0", *(f"PB{bit}" for bit in range(8))]:
            pins[name] = _read_pin(rows, width, height, group[name])
        centers_x = [pin["marker_center_xy"][0] for pin in pins.values()]
        label_height = statistics.median(label["bbox_xywh"][3] for label in group.values())
        if max(centers_x)-min(centers_x) > max(2, label_height*.6):
            raise PinObservationError("Observed pin markers do not share the U8 port edge", {"pins": pins})
        bits = [pins[f"PB{bit}"]["bit"] for bit in range(8)]
        return {**evidence, "input_bit": pins["PA0"]["bit"], "port_b": sum(value << bit for bit, value in enumerate(bits)),
                "port_b_bits_lsb_first": bits, "raw_bits": {name: pin["bit"] for name, pin in pins.items()},
                "pins": pins,
                "limitations": "Visible Proteus pin-state colors; requires upright U8 and complete OCR labels; does not infer LED polarity"}
    except PinObservationError as error:
        error.details = {**evidence, **error.details}
        raise
    except (OSError, ValueError, TypeError, WaveformError) as error:
        raise PinObservationError(f"Cannot observe 8255: {error}", evidence) from error
