"""Actual image bytes and corrupt containers; does not imply CPU execution."""
import hashlib
from pathlib import Path
import struct
import tempfile
import unittest
import zipfile

from fish_proteus.firmware import firmware_info, extract_firmware, gpio_events


def ihex(address, kind, data=b""):
    body = bytes([len(data)]) + address.to_bytes(2, "big") + bytes([kind]) + data
    return ":" + (body + bytes([-sum(body) % 256])).hex().upper() + "\n"


class FirmwareIdentityTests(unittest.TestCase):
    def setUp(self):
        work = Path(__file__).resolve().parents[1] / ".work" / "firmware-tests"
        work.mkdir(parents=True, exist_ok=True)
        temporary = tempfile.TemporaryDirectory(dir=work)
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def write(self, name, data):
        path = self.root / name
        path.write_bytes(data.encode("ascii") if isinstance(data, str) else data)
        return path

    def test_valid_extended_hex_preserves_actual_content_identity(self):
        data = ihex(0, 4, b"\x08\x00") + ihex(0, 0, b"\x00\x20\x00\x20") + ihex(0, 1)
        path = self.write("program.hex", data)
        result = firmware_info(path)
        self.assertTrue(result["checksum_verified"])
        self.assertEqual(result["sha256"], hashlib.sha256(path.read_bytes()).hexdigest())
        self.assertEqual(result["address_range"], [0x08000000, 0x08000004])

    def test_checksum_overlapping_and_control_record_errors_are_rejected(self):
        cases = [":0100000000FE\n" + ihex(0, 1),
                 ihex(0, 0, b"1234") + ihex(2, 0, b"56") + ihex(0, 1),
                 ihex(1, 4, b"\x08\x00") + ihex(0, 1),
                 ihex(0, 0, b"x") + ihex(0, 1) + ihex(0, 0, b"y"),
                 ihex(0, 0, b"x")]
        for index, data in enumerate(cases):
            with self.subTest(index=index), self.assertRaises(ValueError):
                firmware_info(self.write(f"bad{index}.hex", data))

    def test_elf_segments_are_checked_against_real_file_bounds(self):
        data = bytearray(88)
        data[:7] = b"\x7fELF\x01\x01\x01"
        struct.pack_into("<HHIIIIIHHHHHH", data, 16, 2, 40, 1, 0x08000001, 52, 0, 0,
                         52, 32, 1, 40, 0, 0)
        struct.pack_into("<IIIIIIII", data, 52, 1, 84, 0x08000000, 0x08000000, 4, 4, 5, 4)
        result = firmware_info(self.write("program.elf", data))
        self.assertEqual(result["machine"], 40)
        struct.pack_into("<I", data, 52 + 16, 1000)
        with self.assertRaisesRegex(ValueError, "segment outside"):
            firmware_info(self.write("corrupt.elf", data))

    def test_embedded_ambiguity_and_invalid_firmware_leave_no_output(self):
        project, destination = self.root / "source.pdsprj", self.root / "program.hex"
        with zipfile.ZipFile(project, "w") as archive:
            archive.writestr("FIRMWARE/a.hex", ihex(0, 0, b"x") + ihex(0, 1))
            archive.writestr("FIRMWARE/b.hex", "invalid")
        with self.assertRaisesRegex(ValueError, "exact firmware"):
            extract_firmware(project, destination)
        with self.assertRaises(ValueError):
            extract_firmware(project, destination, "FIRMWARE/b.hex")
        self.assertFalse(destination.exists())
        result = extract_firmware(project, destination, "FIRMWARE/a.hex")
        self.assertTrue(result["format_verified"])
        with self.assertRaises(FileExistsError):
            extract_firmware(project, destination, "FIRMWARE/a.hex")

    def test_gpio_parser_filters_real_event_fields_without_inventing_clock(self):
        log = ("[GPIO] drive PIO0.5 = 0 [U1_SYSINTERFACE] @00:00:00.000\n"
               "[GPIO] drive PIO0.5 = 1 [U1_SYSINTERFACE] @1.250000s\n"
               "[GPIO] drive PIO1.5 = 1 [U2_SYSINTERFACE] @1.250001s\n")
        events = gpio_events(log, ref="U1", port=0, pin=5)
        self.assertEqual([(x["value"], x["seconds"]) for x in events], [(0, 0), (1, 1.25)])

    def test_native_logfile_metadata_applies_to_preceding_message(self):
        log = ("#T:[GPIO] drive PIO0.5 = 0\r\n%T=0.002507375\r\n%S=U1_SYSINTERFACE\r\n%E=0001\r\n"
               "#T:[GPIO] drive PIO0.5 = 1\r\n%T=1.00003e-1\r\n%S=U1_SYSINTERFACE\r\n%E=0001\r\n"
               "#T:[GPIO] drive PIO0.5 = 0\r\n%T=0.200002375\r\n%S=U1_SYSINTERFACE\r\n%E=0001\r\n")
        result = gpio_events(log, ref='U1', port=0, pin=5)
        self.assertEqual([x['value'] for x in result], [0, 1, 0])
        self.assertEqual([x['seconds'] for x in result], [.002507375, .100003, .200002375])

    def test_partial_native_event_never_inherits_previous_time_or_source(self):
        log = ("#T:[GPIO] drive PIO0.5 = 0\n%T=0.01\n%S=U1_SYSINTERFACE\n%E=0001\n"
               "#T:[GPIO] drive PIO0.5 = 1\n%S=U1_SYSINTERFACE\n%E=0001\n"
               "#T:[GPIO] drive PIO0.5 = 0\n%T=0.03\n%S=U1_SYSINTERFACE\n")
        self.assertEqual([x['value'] for x in gpio_events(log)], [0])


if __name__ == "__main__":
    unittest.main()
