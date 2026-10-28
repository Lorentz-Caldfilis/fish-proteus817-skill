"""Synthetic illumination masks independently test D0..D7 ordering."""
import copy
from pathlib import Path
import tempfile
import unittest

from fish_proteus.led_observation import LedObservationError, observe_leds, observe_pa0
from tests.test_pin_observation import schematic, write_rgb_png


def led_image(path, mask, *, scale=1, aliases=False, ambiguous=False, no_outline=False):
    width, height = round(420*scale), round(470*scale)
    rows = [bytearray(bytes((225, 225, 210))*width) for _ in range(height)]
    lines = []
    for bit in range(8):
        cx, cy, radius = 190*scale, (45+54*bit)*scale, 19*scale
        for py in range(round(cy-radius-1), round(cy+radius+1)):
            for px in range(round(cx-radius-1), round(cx+radius+1)):
                distance = ((px-cx)**2+(py-cy)**2)**.5
                if distance <= radius:
                    rgb = (128, 0, 0) if not no_outline and distance >= radius-2*scale else ((0, 128, 0) if (mask>>bit)&1 else (0, 0, 0))
                    if distance < radius*.5 and abs(px-cx) < 1.5*scale:
                        rgb = (128, 0, 0)
                    if ambiguous and bit == 3 and distance < radius-2*scale:
                        rgb = (0, 128, 0) if px < cx else (0, 0, 0)
                    rows[py][px*3:px*3+3] = bytes(rgb)
        # The actual schematic's horizontal red leads connect to the outline.
        for py in range(round(cy-scale), round(cy+scale)+1):
            for px in range(round(cx-radius*1.8), round(cx+radius*1.8)):
                rows[py][px*3:px*3+3] = bytes((128, 0, 0))
        text = "DO" if aliases and bit == 0 else "DI" if aliases and bit == 1 else f"D{bit}"
        lines.append({"Text": text, "Words": [{"Text": text, "X": 220*scale, "Y": (22+54*bit)*scale, "Width": 24*scale, "Height": 15*scale}]})
    write_rgb_png(path, rows)
    return {"Lines": lines}


class LedObservationTests(unittest.TestCase):
    def setUp(self):
        workspace = Path(__file__).resolve().parents[1]/".work"/"forward-review"/"led-tests"
        workspace.mkdir(parents=True, exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(dir=workspace)
        self.addCleanup(self.temporary.cleanup)
        self.image = Path(self.temporary.name)/"leds.png"

    def test_non_symmetric_and_complementary_masks(self):
        for mask in (0x33, 0xCC, 0x96, 0x81, 0x05, 0, 255):
            with self.subTest(mask=hex(mask)):
                result = observe_leds(self.image, led_image(self.image, mask))
                self.assertEqual(result["led_mask"], mask)
                self.assertEqual(result["led_bits_lsb_first"], [(mask>>i)&1 for i in range(8)])
                self.assertNotIn("port_b", result)
                self.assertIn("not an 8255", result["limitations"])

    def test_zoom_and_contextual_ocr_aliases(self):
        for scale in (.8, 1.5, 2):
            with self.subTest(scale=scale):
                result = observe_leds(self.image, led_image(self.image, 0x69, scale=scale, aliases=True))
                self.assertEqual(result["led_mask"], 0x69)

    def test_missing_duplicate_or_out_of_order_labels_are_rejected(self):
        ocr = led_image(self.image, 0x33)
        for changed in (dict(Lines=ocr["Lines"][:4]+ocr["Lines"][5:]), dict(Lines=ocr["Lines"]+[ocr["Lines"][0]])):
            with self.assertRaises(LedObservationError):
                observe_leds(self.image, changed)
        changed = copy.deepcopy(ocr)
        changed["Lines"][2]["Words"][0]["Text"] = "D3"
        changed["Lines"][3]["Words"][0]["Text"] = "D2"
        with self.assertRaises(LedObservationError):
            observe_leds(self.image, changed)

    def test_ambiguous_interiors_and_no_circle_are_rejected(self):
        for kwargs in ({"ambiguous": True}, {"no_outline": True}):
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(LedObservationError):
                    observe_leds(self.image, led_image(self.image, 0xCC, **kwargs))

    def test_pa0_reads_both_values_independent_of_pb_marker_colors(self):
        for input_bit in (0, 1):
            with self.subTest(input_bit=input_bit):
                ocr = schematic(self.image, 0x96, input_bit, bad_pin="PB0")
                result = observe_pa0(self.image, ocr)
                self.assertEqual(result["input_bit"], input_bit)
                self.assertNotIn("port_b", result)
                self.assertIn("sample_rgb", result["pin"])


if __name__ == "__main__":
    unittest.main()
