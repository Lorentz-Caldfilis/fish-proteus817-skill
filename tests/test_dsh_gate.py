"""Security and hardware-boundary contracts for the model-facing DSH gate."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from tools.dsh_cli_gate import arguments, descendant


class DshGateTests(unittest.TestCase):
    def setUp(self):
        test_root = Path(__file__).resolve().parents[1] / ".work" / "dsh-gate-tests"
        test_root.mkdir(parents=True, exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(dir=test_root)
        self.workspace = Path(self.temporary.name).resolve()
        self.assertTrue(self.workspace.is_relative_to(test_root.resolve()))
        self.addCleanup(self.temporary.cleanup)
        self.library = self.workspace / ".local" / "course"
        self.job = self.workspace / ".work" / "job"
        self.job.mkdir(parents=True)
        self.allowed = frozenset({"doctor", "prepare", "build"})

    def command(self, payload, allowed=None):
        return arguments(payload, self.workspace, self.library, self.job, allowed or self.allowed)

    def manifest(self, **overrides):
        value = {
            "project": str(self.job / "project.pdsprj"),
            "source": str(self.job / "8086" / "main.asm"),
            "executable": str(self.job / "8086" / "Debug" / "Debug.exe"),
            **overrides,
        }
        (self.job / "job.json").write_text(json.dumps(value), encoding="utf-8")

    def test_string_injection_and_arbitrary_command_fields_are_rejected(self):
        for payload in (
            {"operation": "doctor", "command": "whoami"},
            {"operation": "doctor", "executable": "cmd.exe"},
            {"operation": "prepare", "case": "divider", "divisor": "10; whoami"},
            {"operation": "prepare", "case": "divider", "divisor": "$(Get-Content secret)"},
            {"operation": "prepare", "case": "divider", "divisor": 10, "output": "../../outside"},
        ):
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                self.command(payload)

    def test_unknown_and_disabled_operations_are_rejected_before_execution(self):
        for operation in ("powershell", "import-course", "doctor; calc.exe", "run", "verify", [], None):
            with self.subTest(operation=operation), self.assertRaises(ValueError):
                self.command({"operation": operation})

    def test_hardware_zero_encoding_count_is_admitted_without_rounding(self):
        command = self.command({"operation": "prepare", "case": "divider", "divisor": 65536})
        self.assertEqual(command[command.index("--divisor") + 1], "65536")
        command = self.command({"operation": "prepare", "case": "cascade", "divisor0": 2, "divisor1": 65536})
        self.assertEqual(command[command.index("--divisor1") + 1], "65536")

    def test_invalid_counter_and_byte_values_are_rejected(self):
        for value in (1, 65537, -1, 2.5, True):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.command({"operation": "prepare", "case": "divider", "divisor": value})
        for value in (-1, 256, False):
            with self.subTest(byte=value), self.assertRaises(ValueError):
                self.command({"operation": "prepare", "case": "switch", "on_value": value})

    def test_case_specific_parameters_cannot_leak_into_other_operations(self):
        with self.assertRaises(ValueError):
            self.command({"operation": "prepare", "case": "divider", "on_value": 255})
        with self.assertRaises(ValueError):
            self.command({"operation": "build", "divisor": 5})

    def test_workspace_and_job_path_escapes_are_rejected(self):
        for path in (self.workspace, self.workspace.parent / "outside", self.workspace / ".." / "outside"):
            with self.subTest(path=str(path)), self.assertRaises(ValueError):
                descendant(path, self.workspace)
        self.assertEqual(descendant(self.job, self.workspace), self.job)
        for field in ("project", "source", "executable"):
            with self.subTest(field=field):
                self.manifest(**{field: str(self.workspace / "outside-the-job")})
                with self.assertRaises(ValueError):
                    self.command({"operation": "build"})

    def test_build_is_bound_to_fixed_manifest(self):
        self.manifest()
        self.assertEqual(self.command({"operation": "build"}), ["build", "--manifest", str(self.job / "job.json")])

    def test_runtime_duration_is_bounded_when_runtime_is_explicitly_enabled(self):
        self.manifest()
        allowed = self.allowed | {"run"}
        self.assertEqual(self.command({"operation": "run", "seconds": 2.2}, allowed)[-2:], ["--seconds", "2.2"])
        for value in (0, -1, 20.1, True, float("nan"), "2; whoami"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.command({"operation": "run", "seconds": value}, allowed)


if __name__ == "__main__":
    unittest.main()
