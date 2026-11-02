"""Timeout scale, doctor discovery, and writable-workdir redirection. No Proteus GUI."""
import ast
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fish_proteus.design_cli import _make_log_directory
from fish_proteus.environment import discover
from fish_proteus.timeouts import scaled, timeout_scale
from fish_proteus.workdir import make_temp_directory, staging_parent, work_report
from runtime_adaptation.diagnostics import launch_blocked_message
from runtime_adaptation.runner import _cleanup_stage, resolve_proteus_executable
from runtime_adaptation.scope_ocr import scope_timebase, timebase_box


ROOT = Path(__file__).resolve().parents[1]


def _word(text, x, y):
    return {"Text": text, "X": x, "Y": y, "Width": 10, "Height": 10}


def _ocr(*words):
    return {"Lines": [{"Text": "", "Words": list(words)}]}


class TimeoutScaleTests(unittest.TestCase):
    def test_unset_scale_keeps_nominal_deadlines(self):
        with patch.dict(os.environ, {"FISH_PROTEUS_TIMEOUT_SCALE": ""}):
            self.assertEqual(timeout_scale(), 1.0)
            self.assertEqual(scaled(45), 45)
            self.assertEqual(scaled(15), 15)
            self.assertEqual(scaled(60), 60)
            self.assertEqual(scaled(120), 120)
            self.assertEqual(scaled(40), 40)
            self.assertEqual(scaled(30), 30)

    def test_scale_multiplies_once(self):
        with patch.dict(os.environ, {"FISH_PROTEUS_TIMEOUT_SCALE": "3"}):
            self.assertEqual(timeout_scale(), 3)
            self.assertEqual(scaled(45), 135)
            self.assertEqual(scaled(40), 120)
            self.assertEqual(scaled(30), 90)

    def test_invalid_scale_names_the_variable(self):
        for raw in ("nope", "0", "-2", "inf", "31"):
            with self.subTest(raw=raw), patch.dict(os.environ, {"FISH_PROTEUS_TIMEOUT_SCALE": raw}):
                with self.assertRaises(ValueError) as caught:
                    timeout_scale()
                self.assertIn("FISH_PROTEUS_TIMEOUT_SCALE", str(caught.exception))


class DoctorDiscoveryTests(unittest.TestCase):
    def setUp(self):
        work = ROOT / ".work" / "portability-tests"
        work.mkdir(parents=True, exist_ok=True)
        temporary = tempfile.TemporaryDirectory(dir=work)
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()

    def _exe(self, folder):
        path = folder / "PDS.EXE"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"MZ-not-the-pinned-build")
        path.chmod(0o755)
        return path

    def test_explicit_executable_is_fingerprinted_without_a_hardcoded_drive(self):
        exe = self._exe(self.root / "Lab" / "BIN")
        with patch.dict(os.environ, {"FISH_PROTEUS_EXE": str(exe), "FISH_PROTEUS_TIMEOUT_SCALE": "2"}):
            report = discover()
        self.assertEqual(Path(report["proteus"]["executable"]), exe.resolve())
        self.assertTrue(report["proteus"]["present"])
        profile = report["proteus"]["native_profile"]
        self.assertFalse(profile["ok"])
        self.assertIn("Unsupported PDS", profile["reason"])
        self.assertEqual(profile["expected_id"], "proteus-8.17-sp2-37159")
        self.assertEqual(report["timeouts"]["value"], 2)
        self.assertEqual(report["timeouts"]["effective_seconds"]["launch"], 90)
        self.assertEqual(report["timeouts"]["nominal_seconds"]["launch"], 45)
        self.assertIn("English", report["requirements"]["interface_language"])

    def test_program_files_discovery_matches_runtime(self):
        exe = self._exe(self.root / "pf" / "Labcenter Electronics" / "Proteus 8 Professional" / "BIN")
        empty = self.root / "empty-path"
        empty.mkdir()
        with patch.dict(os.environ, {"FISH_PROTEUS_EXE": "", "ProgramFiles": str(self.root / "pf"),
                                     "ProgramFiles(x86)": "", "PATH": str(empty)}):
            found = resolve_proteus_executable()
            report = discover()
        self.assertEqual(found, exe.resolve())
        self.assertEqual(Path(report["proteus"]["executable"]), exe.resolve())

    def test_missing_proteus_is_a_report_not_a_crash(self):
        empty = self.root / "nowhere"
        empty.mkdir()
        with patch.dict(os.environ, {"FISH_PROTEUS_EXE": "", "ProgramFiles": str(empty),
                                     "ProgramFiles(x86)": "", "PATH": str(empty),
                                     "FISH_PROTEUS_TIMEOUT_SCALE": "nope"}):
            report = discover()
        self.assertFalse(report["proteus"]["present"])
        self.assertIsNone(report["proteus"]["executable"])
        self.assertFalse(report["proteus"]["native_profile"]["ok"])
        self.assertIn("FISH_PROTEUS_TIMEOUT_SCALE", report["timeouts"]["error"])
        self.assertIsNone(report["timeouts"]["value"])

    def test_session_launch_default_is_discovery_not_a_fixed_drive(self):
        tree = ast.parse((ROOT / "runtime_adaptation" / "session.py").read_text(encoding="utf-8"))
        defaults = []
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "__init__":
                for arg, default in zip(node.args.args[-len(node.args.defaults):], node.args.defaults):
                    if arg.arg == "executable":
                        defaults.append(default)
        self.assertEqual(len(defaults), 1)
        self.assertIsInstance(defaults[0], ast.Constant)
        self.assertIsNone(defaults[0].value)


class WorkdirTests(unittest.TestCase):
    def setUp(self):
        work = ROOT / ".work" / "portability-tests"
        work.mkdir(parents=True, exist_ok=True)
        temporary = tempfile.TemporaryDirectory(dir=work)
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()

    def test_staging_and_cleanup_follow_the_workdir(self):
        folder = self.root / "D" / "fish"
        folder.mkdir(parents=True)
        with patch.dict(os.environ, {"FISH_PROTEUS_WORKDIR": str(folder)}):
            stage = make_temp_directory("fish-pds-", purpose="Proteus project staging")
            self.assertEqual(stage.parent, staging_parent())
            self.assertTrue(stage.name.startswith("fish-pds-"))
            marker = stage / "kept.txt"
            marker.write_text("synthetic", encoding="utf-8")
            _cleanup_stage(stage)
        self.assertFalse(stage.exists())

    def test_unwritable_workdir_names_the_path(self):
        blocked = self.root / "not-a-directory"
        blocked.write_text("x", encoding="utf-8")
        with patch.dict(os.environ, {"FISH_PROTEUS_WORKDIR": str(blocked)}):
            with self.assertRaises(OSError) as caught:
                make_temp_directory("fish-pds-", purpose="Proteus project staging")
            report = work_report(repository=self.root)
        self.assertIn(str(blocked.resolve()), str(caught.exception))
        self.assertIn("FISH_PROTEUS_WORKDIR", str(caught.exception))
        self.assertFalse(report["desktop_store"]["writable"])
        self.assertIn(str(blocked.resolve()), report["desktop_store"]["error"] + report["desktop_store"]["path"])

    def test_native_log_staging_uses_an_ascii_workdir(self):
        folder = self.root / "ascii-work"
        folder.mkdir()
        task = self.root / "用户" / "task"
        task.mkdir(parents=True)
        with patch.dict(os.environ, {"FISH_PROTEUS_WORKDIR": str(folder)}):
            directory = _make_log_directory(task)
        self.assertTrue(str(directory).isascii())
        self.assertTrue(directory.is_relative_to(folder.resolve()))
        directory.rmdir()

    def test_non_ascii_workdir_is_refused_by_name(self):
        folder = self.root / "工作区"
        folder.mkdir()
        task = self.root / "task"
        task.mkdir()
        with patch.dict(os.environ, {"FISH_PROTEUS_WORKDIR": str(folder)}):
            with self.assertRaises(ValueError) as caught:
                _make_log_directory(task)
        self.assertIn(str(folder.resolve()), str(caught.exception))
        self.assertIn("ASCII", str(caught.exception))


class ScopeAndLaunchTests(unittest.TestCase):
    def test_timebase_box_is_unchanged_at_the_requested_window_size(self):
        self.assertEqual(timebase_box((1380, 900)), (866, 947, 850, 880))
        text = scope_timebase(_ocr(_word("500", 900, 860), _word("ns", 930, 860), _word("1V", 100, 100)))
        self.assertEqual(text, "500ns")

    def test_timebase_box_scales_with_a_uniform_capture(self):
        box = timebase_box((2760, 1800))
        self.assertEqual(box, (1732, 1894, 1700, 1760))
        text = scope_timebase(_ocr(_word("1", 1800, 1720), _word("us", 1860, 1720)), (2760, 1800))
        self.assertEqual(text, "1us")
        with self.assertRaises(RuntimeError):
            scope_timebase(_ocr(_word("500", 900, 860)), (2760, 1800))

    def test_launch_timeout_lists_blocking_titles_and_the_hidden_start(self):
        message = launch_blocked_message(
            pid=42, project_stem="filter", budget_seconds=45,
            windows=[{"title": "License", "children": [{"title": "Activate Proteus"}]},
                     {"title": "", "children": [{"title": "OK"}]}],
        )
        self.assertIn("filter - ...", message)
        self.assertIn("45s", message)
        self.assertIn("hidden", message)
        self.assertIn("License", message)
        self.assertIn("Activate Proteus", message)
        self.assertIn("FISH_PROTEUS_TIMEOUT_SCALE", message)
        self.assertIn("English", message)


if __name__ == "__main__":
    unittest.main()
