"""Independent synthetic OCR/colored-pin fixtures, not runtime evidence."""
import copy
import hashlib
import json
from pathlib import Path
import struct
import tempfile
import unittest
import zlib

from fish_proteus.pin_observation import PinObservationError, observe_8255


def write_rgb_png(path, rows):
    height, width = len(rows), len(rows[0])//3
    def chunk(kind, payload):
        return struct.pack(">I", len(payload))+kind+payload+struct.pack(">I", zlib.crc32(kind+payload)&0xffffffff)
    raw = b"".join(b"\0"+bytes(row) for row in rows)
    path.write_bytes(b"\x89PNG\r\n\x1a\n"+chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
                     +chunk(b"IDAT", zlib.compress(raw))+chunk(b"IEND", b""))


def schematic(path, port_b, input_bit, *, scale=1, aliases=False, split=False, bad_pin=None, mixed=False):
    width, height = round(480*scale), round(620*scale)
    rows = [bytearray(bytes((225, 225, 210))*width) for _ in range(height)]
    def rectangle(x, y, w, h, rgb):
        left, top, right, bottom = map(lambda v: round(v*scale), (x, y, x+w, y+h))
        for py in range(top, bottom):
            rows[py][left*3:right*3] = bytes(rgb)*(right-left)
    rectangle(80, 50, 171, 501, (128, 0, 0))
    rectangle(82, 52, 167, 497, (198, 198, 174))
    lines = []
    def word(text, x, y, w, h):
        return {"Text": text, "X": x*scale, "Y": y*scale, "Width": w*scale, "Height": h*scale}
    lines.append({"Text": "U8", "Words": [word("U8", 80, 28, 22, 14)]})
    for name, y, value in [("PA0", 60, input_bit), *[(f"PB{bit}", 222+18*bit, (port_b>>bit)&1) for bit in range(8)]]:
        text = name[:-1]+"O" if aliases and name in ("PA0", "PB0") else name
        words = [word(text, 215, y, 27, 10)]
        if split and name == "PB1":
            words = [word("PB", 215, y, 18, 10), word("1", 236, y, 4, 10)]
        lines.append({"Text": text, "Words": words})
        rectangle(215, y, 24, 2, (0, 0, 0))
        rgb = (255, 64, 64) if value else (64, 64, 255)
        if name == bad_pin:
            rgb = (128, 128, 128)
        rectangle(258, y-8, 7, 7, rgb)
        if mixed and name == "PB3":
            rectangle(258, y-8, 3, 7, (255, 64, 64))
            rectangle(261, y-8, 4, 7, (64, 64, 255))
    # An unrelated source net and marker must not be mistaken for a PB pin.
    lines.append({"Text": "PBY0", "Words": [word("PBY0", 350, 222, 35, 10)]})
    rectangle(400, 214, 7, 7, (255, 64, 64))
    write_rgb_png(path, rows)
    return {"Text": "synthetic", "Lines": lines}


class PinObservationTests(unittest.TestCase):
    def setUp(self):
        workspace = Path(__file__).resolve().parents[1] / ".work" / "forward-review" / "pin-tests"
        workspace.mkdir(parents=True, exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(dir=workspace)
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.image = self.root / "synthetic.png"

    def test_real_bit_order_for_patterns_and_both_inputs(self):
        for byte in (0x33, 0xCC, 0x96, 0x81, 0x05):
            for input_bit in (0, 1):
                with self.subTest(byte=hex(byte), input_bit=input_bit):
                    ocr = schematic(self.image, byte, input_bit)
                    result = observe_8255(self.image, ocr)
                    self.assertEqual(result["input_bit"], input_bit)
                    self.assertEqual(result["port_b"], byte)
                    self.assertEqual(result["port_b_bits_lsb_first"], [(byte>>i)&1 for i in range(8)])
                    self.assertEqual(result["image_sha256"], hashlib.sha256(self.image.read_bytes()).hexdigest())
                    self.assertEqual(len(result["pins"]), 9)
                    self.assertIn(result["pins"]["PB0"]["sample_rgb"], ([255, 64, 64], [64, 64, 255]))

    def test_zoom_scaled_coordinates_aliases_and_split_tokens(self):
        for scale in (.8, 1.5, 2):
            with self.subTest(scale=scale):
                ocr = schematic(self.image, 0xA6, 1, scale=scale, aliases=True, split=True)
                result = observe_8255(self.image, ocr)
                self.assertEqual(result["port_b"], 0xA6)
                self.assertEqual(result["input_bit"], 1)
                self.assertEqual(result["pins"]["PB0"]["ocr_text"], "PBO")
                self.assertEqual(result["pins"]["PB1"]["ocr_text"], "PB1")

    def test_json_path_input(self):
        ocr = schematic(self.image, 0x59, 0)
        path = self.root / "ocr.json"
        path.write_text(json.dumps(ocr), encoding="utf-8")
        result = observe_8255(self.image, path)
        self.assertEqual(result["port_b"], 0x59)
        self.assertEqual(result["ocr_sha256"], hashlib.sha256(path.read_bytes()).hexdigest())

    def test_missing_pb_label_is_not_interpolated(self):
        ocr = schematic(self.image, 0x33, 0)
        ocr["Lines"] = [line for line in ocr["Lines"] if line["Text"] != "PB4"]
        with self.assertRaisesRegex(PinObservationError, "missing") as caught:
            observe_8255(self.image, ocr)
        self.assertIn("PB4", str(caught.exception.details))
        self.assertIn("image_sha256", caught.exception.details)

    def test_u8_reference_and_pa0_are_required(self):
        for missing in ("U8", "PA0"):
            with self.subTest(missing=missing):
                ocr = schematic(self.image, 0xCC, 1)
                ocr["Lines"] = [line for line in ocr["Lines"] if line["Text"] != missing]
                with self.assertRaises(PinObservationError):
                    observe_8255(self.image, ocr)

    def test_unknown_and_mixed_marker_colors_are_rejected(self):
        for kwargs in ({"bad_pin": "PB5"}, {"mixed": True}):
            with self.subTest(kwargs=kwargs):
                ocr = schematic(self.image, 0xCC, 1, **kwargs)
                with self.assertRaisesRegex(PinObservationError, "marker"):
                    observe_8255(self.image, ocr)

    def test_duplicate_or_misordered_labels_are_rejected(self):
        ocr = schematic(self.image, 0x69, 0)
        duplicated = copy.deepcopy(ocr)
        duplicated["Lines"].append(copy.deepcopy(duplicated["Lines"][4]))
        with self.assertRaises(PinObservationError):
            observe_8255(self.image, duplicated)
        pb2, pb3 = ocr["Lines"][4], ocr["Lines"][5]
        pb2["Words"][0]["Y"], pb3["Words"][0]["Y"] = pb3["Words"][0]["Y"], pb2["Words"][0]["Y"]
        with self.assertRaises(PinObservationError):
            observe_8255(self.image, ocr)

    def test_malformed_or_unmapped_ocr_is_rejected(self):
        ocr = schematic(self.image, 0x33, 0)
        for malformed in ({"Text": "no coordinates"}, {"Lines": [None]}, {"Lines": [{"Words": [None]}]}):
            with self.subTest(malformed=malformed):
                with self.assertRaises(PinObservationError):
                    observe_8255(self.image, malformed)
        ocr["Lines"][2]["Words"][0]["X"] = 99999
        with self.assertRaises(PinObservationError):
            observe_8255(self.image, ocr)


if __name__ == "__main__":
    unittest.main()
