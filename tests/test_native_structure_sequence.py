"""Native structure requests opt out of log capture; requested logs stay strict."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from fish_proteus.design_cli import DesignTask
from fish_proteus.firmware import gpio_events
from test_design_tool import MemoryCircuit, MemoryLibrary, NativeSessionDouble, NativeSimulationDouble


class UnloggedSessionDouble(NativeSessionDouble):
    """Any attempted metadata read in an unlogged sequence is a test failure."""

    @property
    def log_metadata(self):
        raise AssertionError("An unlogged sequence must not collect log metadata")

    @log_metadata.setter
    def log_metadata(self, value):
        pass


class MissingLogSessionDouble(NativeSessionDouble):
    def close(self):
        self.calls.append("close")
        self.closed = self.normal_closed = True
        if self.logfile is not None:
            self.logfile.unlink(missing_ok=True)
        self.log_metadata = {"complete": False, "finalized_after_process_close": True}
        return 0


class MismatchedLogSessionDouble(NativeSessionDouble):
    def close(self):
        code = super().close()
        self.final_logfile_sha256 = "0" * 64
        return code


class NativeStructureSequenceTests(unittest.TestCase):
    def setUp(self):
        base = Path(__file__).resolve().parents[1] / ".work" / "native-structure-unit-tests"
        base.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=base)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.api = SimpleNamespace(Circuit=MemoryCircuit, Library=MemoryLibrary, gpio_events=gpio_events)
        self.runtime = SimpleNamespace(Session=NativeSessionDouble, Simulation=NativeSimulationDouble)
        self.task = DesignTask(self.root / "task", api=self.api, runtime=self.runtime)
        self.task.config = lambda: SimpleNamespace()
        NativeSessionDouble.instances = []
        NativeSessionDouble.abnormal_close = False
        NativeSimulationDouble.verify_time = False
        NativeSimulationDouble.fail_press = False
        result = self.task.handle({"action": "create"})
        self.assertEqual(result["status"], "file_verified", result)

    def sequence(self, steps, **options):
        return self.task.handle({"action": "run_sequence",
            "expected_revision": self.task.state["current"]["revision"], "steps": steps,
            "save_project": False, **options})

    def test_netlist_only_closes_normally_without_logfile_or_raw_log_artifact(self):
        self.runtime.Session = UnloggedSessionDouble
        project = self.task.current()
        before = hashlib.sha256(project.read_bytes()).hexdigest()
        with patch("fish_proteus.design_cli._make_log_directory",
                   side_effect=AssertionError("Structure-only requests must not allocate LOGFILE")):
            result = self.sequence([{"op": "netlist"}])
        self.assertEqual(result["status"], "runtime_observed", result)
        session = NativeSessionDouble.instances[0]
        self.assertIsNone(session.logfile)
        self.assertTrue(session.closed)
        self.assertTrue(session.normal_closed)
        self.assertEqual(session.calls, ["stop", "close"])
        self.assertEqual(hashlib.sha256(project.read_bytes()).hexdigest(), before)
        self.assertFalse(result["data"]["log_capture_requested"])
        self.assertFalse(result["side_effects"]["native_logfile_host_selected"])
        self.assertNotIn("log_collection_error", result["data"])
        self.assertNotIn("raw_log_artifact_id", result["data"])
        self.assertNotIn("log_metadata", result["data"])
        kinds = {item["kind"] for item in result["evidence_refs"]}
        self.assertIn("native_sdf", kinds)
        self.assertIn("native_netlist", kinds)
        self.assertNotIn("simulation_log_raw", kinds)
        self.assertNotIn("simulation_errors", kinds)
        self.assertFalse(result["data"]["actual_time_verified"])

    def test_status_and_explicit_save_do_not_enable_log_capture(self):
        with patch("fish_proteus.design_cli._make_log_directory",
                   side_effect=AssertionError("No trace step requested")):
            result = self.sequence([{"op": "status"}, {"op": "save"}])
        self.assertEqual(result["status"], "runtime_observed", result)
        self.assertTrue(result["side_effects"]["saved_project"])
        self.assertFalse(result["side_effects"]["native_logfile_host_selected"])
        session = NativeSessionDouble.instances[0]
        self.assertEqual(session.calls, ["save", "stop", "close"])
        self.assertIsNone(session.logfile)
        self.assertFalse(any(item["kind"] == "simulation_log_raw" for item in result["evidence_refs"]))

    def test_requested_log_errors_and_gpio_still_require_a_complete_final_file(self):
        NativeSimulationDouble.verify_time = True
        self.runtime.Session = MissingLogSessionDouble
        for operation in ("log", "errors", "gpio_events"):
            with self.subTest(operation=operation):
                result = self.sequence([{"op": "run_for", "seconds": .03}, {"op": operation}])
                self.assertEqual(result["status"], "blocked", result)
                self.assertTrue(result["data"]["log_capture_requested"])
                self.assertTrue(result["side_effects"]["native_logfile_host_selected"])
                self.assertFalse(result["data"]["log_complete"])
                self.assertEqual(result["data"]["steps"][-1]["status"], "blocked")
                self.assertIn("complete logfile", result["data"]["log_collection_error"]["message"])
                self.assertFalse(any(item["kind"] == "simulation_log_raw" for item in result["evidence_refs"]))

    def test_requested_gpio_hash_mismatch_blocks_collection_and_behavior_verification(self):
        NativeSimulationDouble.verify_time = True
        self.runtime.Session = MismatchedLogSessionDouble
        result = self.sequence([{"op": "run_for", "seconds": .03}, {"op": "gpio_events"}])
        self.assertEqual(result["status"], "blocked", result)
        self.assertTrue(result["side_effects"]["native_logfile_host_selected"])
        raw = next(item for item in result["evidence_refs"] if item["kind"] == "simulation_log_raw")
        self.assertFalse(raw["log_complete"])
        self.assertIn("hash does not match", result["data"]["log_collection_error"]["message"])
        gpio = next(item for item in result["evidence_refs"] if item["kind"] == "gpio_events")
        checked = self.task.handle({"action": "verify",
            "expected_revision": self.task.state["current"]["revision"], "assertions": [
                {"type": "gpio_sequence", "artifact_id": gpio["artifact_id"], "ref": "U1",
                 "port": 0, "pin": 1, "values": [0, 1, 0]}]})
        self.assertEqual(checked["status"], "blocked", checked)


if __name__ == "__main__":
    unittest.main()
