"""Exercise user-facing parsing through the real Python module entrypoint."""

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from fish_proteus.artifacts import mz_code
from fish_proteus.course import import_course
from test_build import observe_io
from test_course import make_course_fixture


class CliTests(unittest.TestCase):
    def setUp(self):
        self.repository = Path(__file__).resolve().parents[1]
        work = self.repository / ".work" / "cli-tests"
        work.mkdir(parents=True, exist_ok=True)
        temporary = tempfile.TemporaryDirectory(dir=work)
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.assertTrue(self.root.is_relative_to(work.resolve()))
        source = self.root / "teacher"
        make_course_fixture(source)
        import_course(source, self.root / "library")

    def cli(self, *arguments):
        result = subprocess.run([sys.executable, "-B", "-m", "fish_proteus", *map(str, arguments)], cwd=self.repository, capture_output=True, encoding="utf-8", timeout=30)
        self.assertNotIn("Traceback", result.stderr)
        return result.returncode, json.loads(result.stdout)

    def test_hexadecimal_user_request_builds_the_requested_port_response(self):
        code, job = self.cli("prepare", "--library", self.root / "library", "--case", "switch", "--on-value", "0x33", "--off-value", "0xCC", "--output", self.root / "job")
        self.assertEqual(code, 0)
        code, built = self.cli("build", "--manifest", job["job_file"], "--toolchain", "builtin")
        self.assertEqual(code, 0)
        self.assertEqual(observe_io(mz_code(built["executable"]), (0, 1, 0), 4), [(646, 144), (642, 51), (642, 204), (642, 51)])

    def test_wrong_case_parameters_fail_before_creating_work(self):
        output = self.root / "invalid"
        code, report = self.cli("prepare", "--library", self.root / "library", "--case", "divider", "--on-value", "0x33", "--output", output)
        self.assertEqual(code, 2)
        self.assertEqual(report["status"], "blocked")
        self.assertFalse(output.exists())

    def test_help_errors_are_machine_readable(self):
        code, report = self.cli("prepare", "--case", "unknown")
        self.assertEqual(code, 2)
        self.assertEqual(report["status"], "blocked")


if __name__ == "__main__":
    unittest.main()
