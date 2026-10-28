"""Synthetic pixel fixtures test measurement, not actual Proteus behavior."""
import hashlib
import os
from pathlib import Path
import struct
import tempfile
import unittest
import zlib

from fish_proteus.waveform import WaveformError, measure_scope


def write_png(path, rows, *, filter_up=False):
    height, width = len(rows), len(rows[0]) // 3
    previous, raw = bytes(width*3), bytearray()
    for row in rows:
        raw.append(2 if filter_up else 0)
        raw.extend(bytes((value-before) & 255 for value, before in zip(row, previous)) if filter_up else row)
        previous = row
    def chunk(kind, payload):
        return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", zlib.crc32(kind+payload) & 0xffffffff)
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
                     + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


def scope_rows(*, period=80, spacing=40, channel="A", phase=0, grid=True, waveform=True,
               width=540, height=340, bounds=(20, 20, 500, 300), irregular=False):
    rows = [bytearray(bytes((145, 145, 145)) * width) for _ in range(height)]
    left, top, right, bottom = bounds
    for y in range(top, bottom+1):
        rows[y][left*3:(right+1)*3] = bytes((0, 0, 0)) * (right-left+1)
    def pixel(x, y, color):
        rows[y][x*3:x*3+3] = bytes(color)
    if grid:
        xs = [left, left+25, left+80, left+120, left+215, left+290, right] if irregular else range(left, right+1, spacing)
        for x in xs:
            for y in range(top, bottom+1):
                pixel(x, y, (0, 64, 0))
        for y in range(top, bottom+1, spacing):
            for x in range(left, right+1):
                pixel(x, y, (0, 64, 0))
    if waveform:
        color = (190, 190, 0) if channel == "A" else (0, 190, 190)
        high, low = top+60, top+120
        previous = None
        for x in range(left, right+1):
            y = high if ((x-left-phase) % period) < period/2 else low
            pixel(x, y, color)
            if previous is not None and y != previous:
                for intermediate in range(high, low+1):
                    pixel(x, intermediate, color)
            previous = y
    return rows


class WaveformTests(unittest.TestCase):
    def setUp(self):
        workspace = Path(__file__).resolve().parents[1] / ".work" / "forward-review" / "waveform-tests"
        workspace.mkdir(parents=True, exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(dir=workspace)
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def capture(self, **kwargs):
        path = self.root / "synthetic.png"
        write_png(path, scope_rows(**kwargs))
        return path

    def test_periods_calibrated_from_varied_grids_and_units(self):
        for period, spacing, unit, seconds in [(80, 40, "1u", 1e-6), (72, 20, "2ms", .002), (120, 40, "500ns", 5e-7)]:
            with self.subTest(period=period, spacing=spacing, unit=unit):
                path = self.capture(period=period, spacing=spacing, phase=7)
                result = measure_scope(path, unit)
                self.assertAlmostEqual(result["period_pixels"], period)
                self.assertAlmostEqual(result["pixels_per_div"], spacing)
                self.assertAlmostEqual(result["frequency_hz"], spacing/period/seconds)
                self.assertGreaterEqual(len(result["edge_x"]), 2)
                self.assertEqual(result["image_sha256"], hashlib.sha256(path.read_bytes()).hexdigest())

    def test_cyan_channel_with_offset_plot(self):
        path = self.capture(period=96, spacing=32, channel="B", width=640, height=380,
                            bounds=(65, 47, 577, 335))
        result = measure_scope(path, "2µs/div", channel="B")
        self.assertAlmostEqual(result["period_pixels"], 96)
        self.assertAlmostEqual(result["pixels_per_div"], 32)
        self.assertAlmostEqual(result["frequency_hz"], 1/(3*2e-6))
        self.assertGreater(result["crop_xyxy"][0], 50)

    def test_up_filtered_png_is_decoded(self):
        path = self.root / "filtered.png"
        write_png(path, scope_rows(period=64, spacing=32), filter_up=True)
        self.assertAlmostEqual(measure_scope(path, "1m")["frequency_hz"], 500)

    def test_black_white_and_empty_grid_are_rejected(self):
        for value in (0, 255):
            with self.subTest(value=value):
                path = self.root / "blank.png"
                write_png(path, [bytes((value, value, value))*200 for _ in range(200)])
                with self.assertRaisesRegex(WaveformError, "grid"):
                    measure_scope(path, "1u")
        with self.assertRaisesRegex(WaveformError, "waveform"):
            measure_scope(self.capture(waveform=False), "1u")

    def test_less_than_two_same_direction_edges_is_rejected(self):
        for period, phase in ((1000, -300), (1000, -200), (400, 0)):
            with self.subTest(period=period):
                path = self.capture(period=period, phase=phase, bounds=(20, 20, 420, 300))
                with self.assertRaisesRegex(WaveformError, "same-direction") as caught:
                    measure_scope(path, "1u")
                self.assertIn("rising_edges_x", caught.exception.details)
                self.assertIn("image_sha256", caught.exception.details)

    def test_no_grid_and_irregular_grid_are_rejected(self):
        for options in ({"grid": False}, {"irregular": True}):
            with self.subTest(options=options):
                with self.assertRaisesRegex(WaveformError, "grid"):
                    measure_scope(self.capture(**options), "1u")

    def test_bad_or_unitless_timebase_is_rejected(self):
        path = self.capture()
        for text in ("", "1", "0u", "-1u", "nan", "1V", "1ss", None):
            with self.subTest(text=text):
                with self.assertRaises(WaveformError):
                    measure_scope(path, text)

    def test_wrong_channel_and_corrupt_png_are_rejected(self):
        path = self.capture()
        with self.assertRaisesRegex(WaveformError, "Cannot read"):
            measure_scope(self.root / "missing.png", "1u")
        with self.assertRaises(WaveformError):
            measure_scope(path, "1u", channel="C")
        path.write_bytes(path.read_bytes()[:-8])
        with self.assertRaisesRegex(WaveformError, "PNG"):
            measure_scope(path, "1u")

    @unittest.skipUnless(os.environ.get("FISH_SCOPE_TEST_PNG"), "Optional local runtime capture is not bundled")
    def test_optional_local_runtime_capture(self):
        result = measure_scope(os.environ["FISH_SCOPE_TEST_PNG"], os.environ.get("FISH_SCOPE_TEST_TIMEBASE", "1u"),
                               os.environ.get("FISH_SCOPE_TEST_CHANNEL", "A"))
        self.assertGreater(result["frequency_hz"], 0)
        self.assertGreaterEqual(len(result["edge_x"]), 2)


if __name__ == "__main__":
    unittest.main()
