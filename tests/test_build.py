"""Independent machine-code observations, not checks of generated prose."""
from pathlib import Path
import struct
import tempfile
import unittest

from fish_proteus.artifacts import describe_mz, mz_code, mz_image
from fish_proteus.build import BuildError, assemble_builtin, build_program, discover_nasm
from fish_proteus.course import generated_source, normalize_parameters


def observe_io(code, inputs=(), output_limit=None, max_steps=20000):
    """A tiny test-only instruction interpreter, independently reads x86 bytes.

    This oracle checks port writes and branches; it does not emulate Proteus,
    the physical circuit, propagation, timers, or LED voltages.
    """
    registers = [0] * 8
    pc, zero = 0, False
    values = iter(inputs)
    events = []

    def get8(index):
        return (registers[index & 3] >> (8 if index > 3 else 0)) & 255

    def put8(index, value):
        shift = 8 if index > 3 else 0
        register = index & 3
        registers[register] = (registers[register] & ~(255 << shift)) | ((value & 255) << shift)

    def signed8(value):
        return value if value < 128 else value - 256

    for _ in range(max_steps):
        start = pc
        if not 0 <= pc < len(code):
            raise AssertionError("Control flow escaped code")
        opcode = code[pc]
        pc += 1
        if 0xB8 <= opcode <= 0xBF:
            registers[opcode - 0xB8] = int.from_bytes(code[pc:pc+2], "little")
            pc += 2
        elif 0xB0 <= opcode <= 0xB7:
            put8(opcode - 0xB0, code[pc])
            pc += 1
        elif opcode in (0x88, 0x8A):
            modrm = code[pc]
            pc += 1
            if modrm >> 6 != 3:
                raise AssertionError("Test oracle only supports register MOV")
            register, rm = (modrm >> 3) & 7, modrm & 7
            if opcode == 0x8A:
                put8(register, get8(rm))
            else:
                put8(rm, get8(register))
        elif opcode == 0xEE:
            events.append((registers[2], get8(0)))
            if output_limit and len(events) >= output_limit:
                return events
        elif opcode == 0xEC:
            put8(0, next(values))
        elif opcode == 0xA8:
            zero = get8(0) & code[pc] == 0
            pc += 1
        elif opcode in (0xEB, 0x74, 0x75):
            relative = signed8(code[pc])
            pc += 1
            if opcode == 0xEB or opcode == 0x74 and zero or opcode == 0x75 and not zero:
                pc += relative
            if pc == start:
                return events
        elif opcode == 0x90:
            pass
        else:
            raise AssertionError(f"Unexpected opcode {opcode:02x} at {start}")
    raise AssertionError("Test instruction budget exceeded")


class BuildTests(unittest.TestCase):
    def setUp(self):
        work = Path(__file__).resolve().parents[1] / ".work"
        work.mkdir(exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(prefix="test-build-", dir=work)
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)

    def compile(self, source, backend="builtin"):
        path = self.directory / (backend + ".asm")
        executable = self.directory / (backend + ".exe")
        path.write_text(source, encoding="utf-8")
        report = build_program(path, executable, toolchain=backend, overwrite=True)
        return mz_code(executable), report

    def test_divider_programs_mode_and_both_count_bytes(self):
        source = generated_source("divider", {"divisor": 258})
        code, report = self.compile(source)
        # Original semantic fixture: mode 3, then low/high bytes of 0x0102.
        self.assertEqual(observe_io(code), [(646, 54), (640, 2), (640, 1)])
        self.assertEqual(report["artifact"]["cs"], 0)
        self.assertEqual(report["artifact"]["ip"], 0)
        self.assertEqual(report["artifact"]["relocation_count"], 0)

    def test_cascade_has_correct_16bit_count_bytes(self):
        code, _ = self.compile(generated_source("cascade", {"divisor0": 1000, "divisor1": 1000}))
        self.assertEqual(observe_io(code), [(646, 54), (640, 232), (640, 3),
                                           (646, 118), (642, 232), (642, 3)])

    def test_divisor_65536_encodes_two_zero_bytes(self):
        code, _ = self.compile(generated_source("divider", {"divisor": 65536}))
        self.assertEqual(observe_io(code), [(646, 54), (640, 0), (640, 0)])

    def test_switch_response_all_input_bytes_and_inverted_mapping(self):
        for invert in (False, True):
            parameters = {"on_value": 170, "off_value": 85, "invert": invert}
            code, _ = self.compile(generated_source("switch", parameters))
            events = observe_io(code, range(256), output_limit=257)
            self.assertEqual(events[0], (646, 144))
            expected = [(642, (170 if value & 1 == 0 else 85) if not invert
                         else (85 if value & 1 == 0 else 170)) for value in range(256)]
            self.assertEqual(events[1:], expected)

    @unittest.skipUnless(discover_nasm(), "Portable NASM is optional; run tools/bootstrap_nasm.py for this cross-check")
    def test_nasm_and_builtin_observe_the_same_port_writes(self):
        cases = (("divider", {"divisor": 5}), ("divider", {"divisor": 1000}),
                 ("divider", {"divisor": 65536}),
                 ("cascade", {"divisor0": 25, "divisor1": 40000}),
                 ("switch", {"on_value": 0xA5, "off_value": 0x5A, "invert": False}))
        for case, parameters in cases:
            with self.subTest(case=case, parameters=parameters):
                source = generated_source(case, parameters)
                reference, _ = self.compile(source, "builtin")
                actual, report = self.compile(source, "nasm")
                if case == "switch":
                    self.assertEqual(observe_io(actual, (1, 0, 1), 4), [(646, 144), (642, 90), (642, 165), (642, 90)])
                    self.assertEqual(observe_io(actual, (1, 0, 1), 4), observe_io(reference, (1, 0, 1), 4))
                else:
                    self.assertEqual(observe_io(actual), observe_io(reference))
                self.assertEqual(report["returncode"], 0)
                self.assertEqual(report["artifact"]["architecture"], "8086")

    @unittest.skipUnless(discover_nasm(), "NASM cross-check unavailable")
    def test_nasm_register_ah_ch_bh_dh_are_never_hex_literals(self):
        source = """CODE SEGMENT
ASSUME CS:CODE
START:
MOV DX,280H
MOV AX,1234H
MOV AL,AH
OUT DX,AL
MOV CX,5678H
MOV AL,CH
OUT DX,AL
MOV BX,0DEF0H
MOV AL,BH
OUT DX,AL
MOV DX,9ABCH
MOV AL,DH
MOV DX,280H
OUT DX,AL
N1: JMP N1
CODE ENDS
END START
"""
        for backend in ("builtin", "nasm"):
            code, _ = self.compile(source, backend)
            self.assertEqual(observe_io(code), [(640, 0x12), (640, 0x56), (640, 0xDE), (640, 0x9A)])

    def test_unknown_instruction_undefined_label_overflow_are_errors(self):
        for source in ("START: THISISNOT8086\nEND START", "START: JMP MISSING\nEND START",
                       "START: MOV AL,256\nEND START", "START: TEST AL,AH\nEND START"):
            with self.subTest(source=source), self.assertRaises(BuildError):
                assemble_builtin(source)

    def test_build_refuses_to_overwrite_existing_file(self):
        source = self.directory / "source.asm"
        target = self.directory / "result.exe"
        source.write_text("START: JMP START\nEND START", encoding="utf-8")
        target.write_bytes(b"preserve-me")
        with self.assertRaises(BuildError):
            build_program(source, target)
        self.assertEqual(target.read_bytes(), b"preserve-me")

    @unittest.skipUnless(discover_nasm(), "NASM cross-check unavailable")
    def test_nasm_cannot_override_the_8086_flat_image_contract(self):
        for extension in (".asm", ".nasm"):
            for directive in ("CPU 386", "BITS 32", "[CPU 386]", "[BITS 32]", "ORG 256", '%include "outside.asm"'):
                with self.subTest(extension=extension, directive=directive):
                    source = self.directory / ("invalid" + extension)
                    source.write_text(directive + "\nSTART: JMP START\nEND START\n", encoding="utf-8")
                    with self.assertRaises(BuildError):
                        build_program(source, self.directory / "forbidden.exe", toolchain="nasm")

    def test_mz_parser_rejects_truncated_or_invalid_entry(self):
        target = self.directory / "invalid.exe"
        target.write_bytes(mz_image(b"\xEB\xFE")[:-1])
        with self.assertRaises(ValueError):
            describe_mz(target)
        with self.assertRaises(ValueError):
            mz_image(b"\x90", 1)


if __name__ == "__main__":
    unittest.main()
