from pathlib import Path
import tempfile
import unittest
import zipfile

from fish_proteus.artifacts import read_json, sha256_file
from fish_proteus.course import (CASE_DIRECTORIES, CourseError, expected_result,
                                generate_variant, import_course, normalize_parameters, verify_import)


def make_course_fixture(root):
    """Create original minimal format fixtures, not copies of course designs."""
    for case_id, name in CASE_DIRECTORIES.items():
        directory = root / name / ("T8255" if case_id == "switch" else "T8253")
        source = directory / "8086/main.asm"
        source.parent.mkdir(parents=True)
        source.write_text("; an external teacher source, preserved by import\n", encoding="utf-8")
        original = "D:\\T8255\\8086\\Debug\\Debug.exe" if case_id == "switch" else "8086\\Debug\\Debug.exe"
        with zipfile.ZipFile(directory / "fixture.pdsprj", "w") as zipped:
            for record in ("ROOT.CDB", "ROOT.DSN"):
                zipped.writestr(record, b"unknown-binary\x00{PROGRAM=" + original.encode("ascii") + b"}\x00preserve-layout")
            zipped.writestr("PROJECT.XML", '<PROJECT><TIMESTAMP FILEVER="830"/></PROJECT>')
            zipped.writestr("FIRMWARE/8086.XML", '<PROJECT BUILDPATH="D:/T8253/8086"><CONTROLLER TYPE="8086"/><FILES><FILE NAME="8086/Debug/Debug.exe" FIRMWARE="1"/></FILES></PROJECT>')
            zipped.writestr("FIRMWARE.XML", '<FIRMWARE FAMILY="8086"/>')


class CourseTests(unittest.TestCase):
    def setUp(self):
        work = Path(__file__).resolve().parents[1] / ".work"
        work.mkdir(exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(prefix="test-course-", dir=work)
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.teacher = self.directory / "teacher"
        make_course_fixture(self.teacher)
        self.imported = import_course(self.teacher, self.directory / "imported")

    def test_import_and_prepare_preserve_all_original_hashes(self):
        before = {str(p): sha256_file(p) for p in self.teacher.rglob("*") if p.is_file()}
        for case_id in CASE_DIRECTORIES:
            result = generate_variant(self.imported, case_id, self.directory / case_id)
            self.assertTrue(Path(result["project"]).is_file())
            self.assertTrue(Path(result["source"]).is_file())
            self.assertFalse(Path(result["executable"]).exists(), "prepare must not reuse supplied executable")
            self.assertEqual(read_json(result["job_file"])["runtime"]["status"], "not_run")
        after = {str(p): sha256_file(p) for p in self.teacher.rglob("*") if p.is_file()}
        self.assertEqual(before, after)
        self.assertEqual(verify_import(self.imported)["status"], "verified")

    def test_switch_rebase_preserves_binary_record_lengths_and_other_bytes(self):
        original = Path(self.imported["cases"]["switch"]["project"])
        job = generate_variant(self.imported, "switch", self.directory / "switch-job")
        with zipfile.ZipFile(original) as reference, zipfile.ZipFile(job["project"]) as actual:
            for name in ("ROOT.CDB", "ROOT.DSN"):
                before, after = reference.read(name), actual.read(name)
                self.assertEqual(len(before), len(after))
                self.assertEqual(after, before.replace(b"D:\\T8255\\8086\\Debug\\Debug.exe", b"8086\\Debug\\generated-8086.exe"))
            self.assertEqual(actual.read("PROJECT.XML"), reference.read("PROJECT.XML"))
            self.assertIsNone(actual.testzip())

    def test_import_detects_modified_original_and_tampered_copy(self):
        case = self.imported["cases"]["divider"]
        Path(case["source"]).write_text("tampered", encoding="utf-8")
        self.assertEqual(verify_import(self.imported)["status"], "failed")
        with self.assertRaises(CourseError):
            generate_variant(self.imported, "divider", self.directory / "blocked")

    def test_protected_paths_and_existing_destination_are_rejected(self):
        for destination in (self.teacher, self.teacher / "nested", self.directory):
            with self.subTest(destination=destination), self.assertRaises(CourseError):
                import_course(self.teacher, destination)
        with self.assertRaises(CourseError):
            generate_variant(self.imported, "divider", self.teacher / "new-job")
        existing = self.directory / "existing"
        existing.mkdir()
        sentinel = existing / "manual.txt"
        sentinel.write_text("preserve", encoding="utf-8")
        with self.assertRaises(CourseError):
            generate_variant(self.imported, "divider", existing)
        self.assertEqual(sentinel.read_text(), "preserve")

    def test_parameter_boundaries_and_invalid_types(self):
        for value in (1, 0, -1, 65537, True, 5.0, "5"):
            with self.subTest(value=value), self.assertRaises(CourseError):
                normalize_parameters("divider", divisor=value)
        self.assertEqual(normalize_parameters("divider", divisor=65536)["divisor"], 65536)
        for values in ({"on_value": 256}, {"off_value": -1}, {"invert": 1}, {"unexpected": 42}):
            with self.subTest(values=values), self.assertRaises(CourseError):
                normalize_parameters("switch", **values)

    def test_analytical_expectations_are_explicitly_not_runtime_measurements(self):
        frequency = expected_result("cascade", {"divisor0": 25, "divisor1": 40000})
        self.assertEqual(frequency["output_hz"], 1.0)
        self.assertEqual(frequency["divide_by"], 1000000)
        self.assertIn("not an observed", frequency["basis"])
        response = expected_result("switch", {"on_value": 255, "off_value": 0, "invert": True})
        self.assertEqual(response["port_b_by_input_bit"], {"0": 0, "1": 255})


if __name__ == "__main__":
    unittest.main()
