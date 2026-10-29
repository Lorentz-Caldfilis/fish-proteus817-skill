"""Domain composition and security boundaries; native test doubles never open a GUI."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from fish_proteus.design_cli import ACTIONS, FILE_ACTIONS, ACTION_FIELDS, EDIT_FIELDS, STEP_FIELDS, ASSERT_FIELDS, DesignTask, validate_request
from fish_proteus.firmware import firmware_info, gpio_events
from fish_proteus._vendor.proteus_auto.measurements import parse_graph_csv, sample
from tools.design_gate import descendant
from runtime_adaptation.profile817 import PROFILE817
from runtime_adaptation.generic import Session as RuntimeSession, Simulation as RuntimeSimulation


class MemoryCircuit:
    """Original synthetic circuit storage, not a Proteus fixture or emulator."""
    saves = 0

    def __init__(self, template_project=None, config=None):
        self.parts, self.edges, self.power = [], [], {}

    @classmethod
    def open(cls, path, config=None):
        value = json.loads(Path(path).read_text(encoding="utf8"))
        obj = cls()
        obj.parts, obj.edges, obj.power = value["parts"], value["edges"], value["power"]
        return obj

    @property
    def revision(self):
        return hashlib.sha256(json.dumps([self.parts, self.edges, self.power], sort_keys=True).encode()).hexdigest()

    def save(self, destination, title=None, overwrite=False):
        self.__class__.saves += 1
        path = Path(destination)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"parts": self.parts, "edges": self.edges, "power": self.power}), encoding="utf8")
        return path

    def components(self):
        return copy.deepcopy(self.parts)

    def pins(self, ref):
        return [{"name": "A", "number": "1", "position": [0, 0]}, {"name": "B", "number": "2", "position": [100000, 0]}]

    def wire_labels(self):
        return []

    def inspect(self):
        return {"revision": self.revision, "components": self.components(), "pins": {p["ref"]: self.pins(p["ref"]) for p in self.parts},
                "connections": self.edges, "nets": self.nets(), "terminals": [], "power_rails": self.power,
                "coordinate_unit": "proteus_native_integer", "units_per_mm": 100000}

    def add(self, device, ref, value, x, y, **options):
        if any(p["ref"] == ref for p in self.parts):
            raise ValueError("Duplicate reference")
        self.parts.append({"device": device, "ref": ref, "value": value, "position": {"x": x, "y": y}, "properties": options.get("properties", {})})
        return self

    def update(self, ref, **changes):
        found = next(x for x in self.parts if x["ref"] == ref)
        found.update(changes)
        return self

    def import_device(self, name, library=None, donor_project=None):
        return name

    def connect(self, first, second, points=None):
        first, second = first.rsplit(".", 1), second.rsplit(".", 1)
        if not all(any(p["ref"] == pin[0] for p in self.parts) for pin in (first, second)):
            raise ValueError("Unknown endpoint")
        self.edges.append([first, second])
        return self

    def nets(self):
        groups = [{(p["ref"], name)} for p in self.parts for name in ("A", "B")]
        for edge in self.edges:
            touched = [g for g in groups if any(tuple(pin) in g for pin in edge)]
            groups = [g for g in groups if g not in touched] + [set().union(*touched)]
        return [sorted(group) for group in groups]

    def set_properties(self, ref, **properties):
        found = next(x for x in self.parts if x["ref"] == ref)
        found["properties"].update(properties)
        return self


class MemoryLibrary:
    def __init__(self, config=None):
        pass

    def search(self, query="", limit=30):
        return [{"name": "TEST-RES", "library": "SYNTHETIC", "device_id": "SYNTHETIC:TEST-RES"}][:limit]

    def get(self, name, library=None):
        return {"name": name, "library": library, "simulation_verified": False, "pins": [["A", "1"], ["B", "2"]]}


class NativeSessionDouble(RuntimeSession):
    instances = []
    abnormal_close = False

    def __init__(self, project, config=None, logfile=None):
        self.pid = 6789
        self.identity = {"session_id": "synthetic-native-session", "pid": self.pid, "process_creation_time": 123}
        self.native_profile = PROFILE817  # the actual frozen dataclass/MappingProxyType shape
        self.project = Path(project)
        self.calls = []
        self.closed = False
        self.normal_closed = False
        self.logfile = Path(logfile) if logfile is not None else None
        self.final_logfile_sha256 = None
        self.log_metadata = {"complete": False, "finalized_after_process_close": False}
        self._final_log_text = None
        self.last_active_status = None
        if self.logfile is not None:
            self.logfile.write_text("#T:[GPIO] drive PIO0.1 = 0\n%T=0\n", encoding="utf8")
        self.__class__.instances.append(self)

    def save(self):
        self.calls.append("save")
        return self.project

    def close(self):
        self.calls.append("close")
        self.closed = True
        self.normal_closed = not self.abnormal_close
        if self.normal_closed and self.logfile is not None:
            # Original native-message syntax; metadata is incomplete while live
            # and final bytes appear only at close, like the real buffered file.
            self._final_log_text = "".join(
                f"#T:[GPIO] drive PIO0.1 = {value}\n%T={seconds}\n%S=U1_SYSINTERFACE\n%E=00000001\n"
                for value, seconds in ((0, 0), (1, .01), (0, .02)))
            self.logfile.write_text(self._final_log_text, encoding="utf8")
        if self.logfile is not None:
            self.final_logfile_sha256 = hashlib.sha256(self.logfile.read_bytes()).hexdigest()
            self.log_metadata = {"complete": self.normal_closed, "finalized_after_process_close": True,
                                 "sha256": self.final_logfile_sha256, "encoding": "utf-8",
                                 "last_active_status": self.last_active_status}
        return 0 if self.normal_closed else 1

    def export_netlist(self, destination):
        Path(destination).write_text("original synthetic native capture marker", encoding="ascii")
        circuit = MemoryCircuit.open(self.project)
        return {"parts": {p["ref"]: p for p in circuit.parts},
                "nets": [{"pins": [{"ref": ref, "pin": pin} for ref, pin in net]} for net in circuit.nets()]}


class NativeSimulationDouble(RuntimeSimulation):
    verify_time = False
    fail_press = False

    def __init__(self, session):
        super().__init__(session)  # actual public Session type check and closed-log methods
        self.state, self.time = "stopped", 0.0

    def status(self):
        verified = self.verify_time and self.state in {"paused", "running"}
        data = {"state": self.state, "simulation_seconds": self.time if verified else None,
                "actual_time_verified": verified, "clock_initialized": verified, "pid": self.session.pid}
        if verified:
            self.session.last_active_status = data
        return data

    def start(self):
        self.state = "running"; self.session.calls.append("start")
        return self.status()

    def pause(self):
        self.state = "paused"; self.session.calls.append("pause")
        return self.status()

    def stop(self):
        self.state = "stopped"; self.session.calls.append("stop")
        self.time = 0.0
        return self.status()

    def run_for(self, seconds, **options):
        self.state = "paused"; self.session.calls.append("run_for")
        self.time += seconds
        return {**self.status(), "requested_seconds": seconds, "actual_time_verified": self.verify_time,
                "actual_elapsed_seconds": seconds if self.verify_time else None,
                "simulation_seconds": self.time if self.verify_time else None}

    def press(self, ref):
        self.session.calls.append("press")
        if self.fail_press:
            raise RuntimeError("Synthetic incompatible control")
        return {"ref": ref, "state": 1}

    def release(self, ref):
        self.session.calls.append("release")
        return {"ref": ref, "state": 0}

class DesignToolTests(unittest.TestCase):
    def setUp(self):
        work = Path(__file__).resolve().parents[1] / ".work" / "design-unit-tests"
        work.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=work)
        self.root = Path(self.temp.name).resolve()
        self.assertTrue(self.root.is_relative_to(work.resolve()))
        self.addCleanup(self.temp.cleanup)
        self.task_root = self.root / "task"
        self.original = self.root / "original.pdsprj"
        self.original.write_text(json.dumps({"parts": [], "edges": [], "power": {}}), encoding="utf8")
        self.original_hash = hashlib.sha256(self.original.read_bytes()).hexdigest()
        self.inputs = {"projects": {"original": str(self.original)}}
        self.api = SimpleNamespace(Circuit=MemoryCircuit, Library=MemoryLibrary, parse_graph_csv=parse_graph_csv,
                                   sample_graph=sample, gpio_events=gpio_events, capability_report=lambda config: {"domains": {"file": {"implemented": True, "runtime_verified": False}}})
        self.runtime = SimpleNamespace(Session=NativeSessionDouble, Simulation=NativeSimulationDouble)
        self.task = DesignTask(self.task_root, self.inputs, api=self.api, runtime=self.runtime)
        self.task.config = lambda: SimpleNamespace()
        MemoryCircuit.saves = 0
        NativeSessionDouble.instances = []
        NativeSessionDouble.abnormal_close = False
        NativeSimulationDouble.verify_time = False
        NativeSimulationDouble.fail_press = False

    def request(self, action, **arguments):
        return self.task.handle({"action": action, **arguments})

    def revision(self):
        return self.task.state["current"]["revision"]

    def create(self):
        result = self.request("create")
        self.assertEqual(result["status"], "file_verified", result)
        return result

    def add_pair(self):
        self.create()
        result = self.request("edit", expected_revision=self.revision(), operations=[
            {"op": "import_device", "name": "TEST-RES"},
            {"op": "add", "device": "TEST-RES", "ref": "R1", "value": "10k", "x": 100000, "y": 0},
            {"op": "add", "device": "TEST-RES", "ref": "R2", "value": "20k", "x": 200000, "y": 0},
            {"op": "connect", "first": "R1.B", "second": "R2.A"}])
        self.assertEqual(result["status"], "file_verified", result)

    def test_closed_actions_reject_code_paths_and_nested_injection(self):
        invalid = [
            {"action": "eval", "code": "1+1"},
            {"action": "library_search", "command": "whoami"},
            {"action": "open", "input_id": "../../secret"},
            {"action": "library_get", "name": "X", "library": "C:\\secret\\X.LIB"},
            {"action": "edit", "expected_revision": "a"*64, "operations": [{"op": "__getattribute__", "name": "x"}]},
            {"action": "edit", "expected_revision": "a"*64, "operations": [{"op": "add", "device": "RES", "ref": "R1", "value": "1k", "x": True, "y": 0}]},
            {"action": "edit", "expected_revision": "a"*64, "operations": [{"op": "set_properties", "ref": "U1", "properties": {"PROGRAM": "C:\\secret.hex"}}]},
            {"action": "edit", "expected_revision": "a"*64, "operations": [{"op": "set_properties", "ref": "U1", "properties": {"LOGFILE": "C:\\outside.log"}}]},
            {"action": "run_sequence", "expected_revision": "a"*64, "steps": [{"op": "set_properties", "ref": "U1", "properties": {"LOGFILENAME": "C:\\outside.log"}}]},
            {"action": "edit", "expected_revision": "a"*64, "operations": [{"op": "update", "ref": "U1", "changes": {"python": "evil"}}]},
            {"action": "run_sequence", "expected_revision": "a"*64, "steps": [{"op": "run_for", "seconds": float("nan")}]},
        ]
        for payload in invalid:
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                validate_request(payload)

    def test_disabled_runtime_is_rejected_before_a_session_is_created(self):
        with self.assertRaisesRegex(ValueError, "not enabled"):
            self.task.handle({"action": "run_sequence", "expected_revision": "a"*64, "steps": [{"op": "start"}]}, FILE_ACTIONS)
        self.assertEqual(NativeSessionDouble.instances, [])

    def test_bounded_help_exposes_signatures_without_file_path_arguments(self):
        result = self.request("help", topic="edits")
        self.assertEqual(result["status"], "prepared")
        self.assertIn("add_wire_label", result["data"].get("content", str(result["data"])))
        with self.assertRaises(ValueError):
            validate_request({"action": "help", "topic": "../../credentials"})

    def test_wheel_help_falls_back_to_closed_embedded_contract(self):
        with patch("fish_proteus.design_cli.REFERENCE_ROOT", self.root / "absent-skill-resources"):
            result = self.request("help", topic="edits")
            workflow = self.request("help", topic="workflow")
        self.assertEqual(result["data"]["source"], "embedded-contract")
        self.assertEqual(set(result["data"]["fields"]), set(EDIT_FIELDS))
        self.assertEqual(workflow["data"]["source"], "embedded-contract")
        self.assertTrue(workflow["data"]["workflow"])

    def test_composed_edit_preserves_original_and_uses_native_units(self):
        self.add_pair()
        inspected = self.request("inspect", ref="R1")
        self.assertEqual(inspected["data"]["components"][0]["position"]["x"], 100000)
        self.assertEqual(inspected["data"]["units_per_mm"], 100000)
        verified = self.request("verify", expected_revision=self.revision(), assertions=[
            {"type": "connected", "pins": ["R1.B", "R2.A"]},
            {"type": "isolated", "first": "R1.A", "second": "R2.B"}])
        self.assertEqual(verified["status"], "file_verified", verified)
        self.assertEqual(hashlib.sha256(self.original.read_bytes()).hexdigest(), self.original_hash)

    def test_failed_edit_batch_does_not_save_or_commit_partial_changes(self):
        self.add_pair()
        current, saves = copy.deepcopy(self.task.state["current"]), MemoryCircuit.saves
        result = self.request("edit", expected_revision=self.revision(), operations=[
            {"op": "update", "ref": "R1", "changes": {"value": "999k"}},
            {"op": "add", "device": "TEST-RES", "ref": "R1", "value": "duplicate", "x": 0, "y": 0}])
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(self.task.state["current"], current)
        self.assertEqual(MemoryCircuit.saves, saves)
        inspected = self.request("inspect", ref="R1")
        self.assertEqual(inspected["data"]["components"][0]["value"], "10k")

    def test_stale_revision_and_tampered_project_are_rejected(self):
        self.create()
        result = self.request("edit", expected_revision="0"*64, operations=[{"op": "import_device", "name": "X"}])
        self.assertEqual(result["status"], "blocked")
        self.task.current().write_text("modified externally", encoding="utf8")
        result = self.request("inspect")
        self.assertEqual(result["status"], "blocked")

    def test_host_original_fingerprint_change_and_escape_are_rejected(self):
        self.create()
        self.original.write_text("changed original", encoding="utf8")
        with self.assertRaisesRegex(ValueError, "original changed"):
            self.request("inspect")
        for path in (self.task_root.parent, self.task_root / ".." / "outside"):
            with self.assertRaises(ValueError):
                descendant(path, self.task_root)
        for name in ("../../secret", "C:\\Windows\\secret", "folder\\..\\secret", "x:stream"):
            with self.assertRaises(ValueError):
                self.task.path(name)

    def test_request_id_replay_is_idempotent_and_payload_bound(self):
        first = self.request("create", request_id="first-create")
        saves = MemoryCircuit.saves
        second = self.request("create", request_id="first-create")
        self.assertTrue(second["replayed"])
        self.assertEqual(first["current"], second["current"])
        self.assertEqual(MemoryCircuit.saves, saves)
        with self.assertRaisesRegex(ValueError, "different request"):
            self.request("create", request_id="first-create", title="different")

    def test_modified_recorded_response_cannot_be_replayed_as_success(self):
        self.request("create", request_id="first-create")
        record = self.task.path("requests/first-create.json")
        record.write_text('{"status":"runtime_verified"}', encoding="utf8")
        with self.assertRaisesRegex(ValueError, "response identity"):
            self.request("create", request_id="first-create")

    def test_one_native_sequence_keeps_one_session_and_preserves_unverified_time(self):
        self.create()
        result = self.request("run_sequence", expected_revision=self.revision(), steps=[
            {"op": "start"}, {"op": "run_for", "seconds": .01}, {"op": "press", "ref": "SW1"},
            {"op": "run_for", "seconds": .01}, {"op": "release", "ref": "SW1"}, {"op": "gpio_events"}])
        self.assertEqual(result["status"], "blocked", result)
        self.assertEqual(len(NativeSessionDouble.instances), 1)
        session = NativeSessionDouble.instances[0]
        self.assertTrue(session.closed)
        self.assertEqual(session.calls[-3:], ["stop", "save", "close"])
        self.assertFalse(result["data"]["actual_time_verified"])
        self.assertIsNone(result["data"]["simulation_seconds"])
        run = result["data"]["run_artifact_id"]
        checked = self.request("verify", expected_revision=self.revision(), assertions=[
            {"type": "simulation_time", "artifact_id": run, "step": 1, "seconds": .01, "tolerance_seconds": .003}])
        self.assertEqual(checked["status"], "blocked")

    def test_gpio_and_verified_time_use_native_artifacts_not_commands(self):
        self.create()
        NativeSimulationDouble.verify_time = True
        result = self.request("run_sequence", expected_revision=self.revision(), steps=[
            {"op": "run_for", "seconds": .03}, {"op": "gpio_events"}])
        gpio = next(x["artifact_id"] for x in result["evidence_refs"] if x["kind"] == "gpio_events")
        checked = self.request("verify", expected_revision=self.revision(), assertions=[
            {"type": "gpio_sequence", "artifact_id": gpio, "ref": "U1", "port": 0, "pin": 1, "values": [0, 1, 0]},
            {"type": "simulation_time", "artifact_id": result["data"]["run_artifact_id"], "step": 0, "seconds": .03, "tolerance_seconds": .003}])
        self.assertEqual(checked["status"], "runtime_verified", checked)
        self.assertEqual(result["data"]["simulation_seconds"], .03)  # not stop()'s reset clock
        self.assertEqual(result["data"]["native_profile"], PROFILE817.describe())

    def test_deferred_gpio_uses_request_clocks_and_final_raw_log_without_hash_rewrites(self):
        self.create()
        NativeSimulationDouble.verify_time = True
        result = self.request("run_sequence", expected_revision=self.revision(), steps=[
            {"op": "run_for", "seconds": .005}, {"op": "gpio_events"},
            {"op": "run_for", "seconds": .010}, {"op": "gpio_events"},
            {"op": "run_for", "seconds": .010}, {"op": "gpio_events"}, {"op": "errors"}])
        self.assertEqual(result["status"], "runtime_observed", result)
        self.assertTrue(result["data"]["log_complete"])
        steps = [x for x in result["data"]["steps"] if x["op"] == "gpio_events"]
        self.assertEqual([[event["value"] for event in x["data"]["events"]] for x in steps], [[0], [0, 1], [0, 1, 0]])
        for step, cutoff in zip(steps, (.005, .015, .025)):
            self.assertAlmostEqual(step["data"]["through_simulation_seconds"], cutoff)
            self.assertTrue(step["data"]["collected_after_close"])
            self.assertTrue(step["data"]["log_complete"])
        for record in result["evidence_refs"]:
            path = self.task.path(record["path"])
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), record["sha256"])
        # The real public cached-reader implementation still works after the
        # host removes its temporary file. Live reads would have raised.
        session = NativeSessionDouble.instances[0]
        self.assertFalse(session.logfile.parent.exists())
        reader = RuntimeSimulation(session)
        self.assertEqual([event["value"] for event in reader.gpio_events()], [0, 1, 0])
        self.assertEqual(reader.errors()["messages"], [])
        checked = self.request("verify", expected_revision=self.revision(), assertions=[
            {"type": "no_errors", "artifact_id": result["data"]["final_errors_artifact_id"]}])
        self.assertEqual(checked["status"], "native_verified", checked)

    def test_abnormal_close_keeps_incomplete_raw_evidence_and_blocks_gpio_verification(self):
        self.create()
        NativeSimulationDouble.verify_time = True
        NativeSessionDouble.abnormal_close = True
        result = self.request("run_sequence", expected_revision=self.revision(), steps=[
            {"op": "run_for", "seconds": .03}, {"op": "gpio_events"}, {"op": "errors"}])
        self.assertEqual(result["status"], "blocked")
        raw = next(x for x in result["evidence_refs"] if x["kind"] == "simulation_log_raw")
        self.assertFalse(raw["log_complete"])
        self.assertFalse(result["data"]["log_complete"])
        gpio = next(x for x in result["evidence_refs"] if x["kind"] == "gpio_events")
        checked = self.request("verify", expected_revision=self.revision(), assertions=[
            {"type": "gpio_sequence", "artifact_id": gpio["artifact_id"], "ref": "U1", "port": 0, "pin": 1, "values": [0, 1, 0]}])
        self.assertEqual(checked["status"], "blocked")

    def test_raw_log_tampering_blocks_otherwise_valid_derived_gpio(self):
        self.create()
        NativeSimulationDouble.verify_time = True
        result = self.request("run_sequence", expected_revision=self.revision(), steps=[
            {"op": "run_for", "seconds": .03}, {"op": "gpio_events"}])
        self.assertEqual(result["status"], "runtime_observed", result)
        raw = next(x for x in result["evidence_refs"] if x["kind"] == "simulation_log_raw")
        with self.task.path(raw["path"]).open("ab") as output:
            output.write(b"changed after acquisition\n")
        gpio = next(x for x in result["evidence_refs"] if x["kind"] == "gpio_events")
        checked = self.request("verify", expected_revision=self.revision(), assertions=[
            {"type": "gpio_sequence", "artifact_id": gpio["artifact_id"], "ref": "U1", "port": 0, "pin": 1, "values": [0, 1, 0]}])
        self.assertEqual(checked["status"], "blocked")

    def test_final_active_clock_survives_an_explicit_stop_before_cleanup(self):
        self.create()
        NativeSimulationDouble.verify_time = True
        result = self.request("run_sequence", expected_revision=self.revision(), steps=[
            {"op": "run_for", "seconds": .03}, {"op": "gpio_events"}, {"op": "stop"}])
        self.assertEqual(result["status"], "runtime_observed", result)
        self.assertEqual(result["data"]["final_active_clock"], .03)
        self.assertEqual(result["data"]["simulation_seconds"], .03)
        self.assertTrue(result["data"]["final_active_clock_capture"]["captured_before_stop"])

    def test_traced_sequence_rejects_reset_and_stop_restart_before_launch(self):
        for operations in (
            [{"op": "run_for", "seconds": .01}, {"op": "reset"}, {"op": "gpio_events"}],
            [{"op": "start"}, {"op": "stop"}, {"op": "run_for", "seconds": .01}, {"op": "errors"}],
        ):
            with self.subTest(operations=operations), self.assertRaisesRegex(ValueError, "one engine epoch"):
                validate_request({"action": "run_sequence", "expected_revision": "a"*64, "steps": operations})
        # A separate reset-only control/timing acceptance path remains available.
        validate_request({"action": "run_sequence", "expected_revision": "a"*64,
                          "steps": [{"op": "start"}, {"op": "reset"}, {"op": "run_for", "seconds": .01}]})

    def test_native_failure_still_cleans_owned_session_and_keeps_failed_run(self):
        self.create()
        NativeSimulationDouble.fail_press = True
        result = self.request("run_sequence", expected_revision=self.revision(), steps=[{"op": "press", "ref": "SW1"}])
        self.assertEqual(result["status"], "blocked")
        self.assertTrue(NativeSessionDouble.instances[0].closed)
        self.assertTrue(any(x["kind"] == "native_run" for x in result["evidence_refs"]))
        self.assertEqual(result["data"]["steps"][0]["status"], "blocked")

    def test_csv_duplicates_bounds_and_stale_evidence_are_enforced(self):
        self.create()
        csv = self.task.path("synthetic-graph.csv")
        csv.write_text("Time,V(out),V(out)\n0,1,5\n1,3,7\n", encoding="ascii")
        artifact = self.task.record(csv, "graph_csv", simulated=True, run_status="runtime_observed")
        # Persist the explicit synthetic raw-data fixture in the task registry.
        from fish_proteus.design_cli import _write
        _write(self.task.manifest, self.task.state)
        sampled = self.request("graph_sample", artifact_id=artifact["artifact_id"], trace="V(out)", x=.5, occurrence=1)
        self.assertEqual(sampled["data"]["value"], 6)
        outside = self.request("graph_sample", artifact_id=artifact["artifact_id"], trace="V(out)", x=2)
        self.assertEqual(outside["status"], "blocked")
        self.request("edit", expected_revision=self.revision(), operations=[{"op": "add", "device": "TEST-RES", "ref": "R1", "value": "1k", "x": 0, "y": 0}])
        stale = self.request("graph_sample", artifact_id=artifact["artifact_id"], trace="V(out)", x=.5)
        self.assertEqual(stale["status"], "blocked")

    def test_opaque_stage_is_explicit_and_never_reconstructed(self):
        result = self.request("stage", input_id="original")
        self.assertEqual(result["status"], "prepared")
        result = self.request("edit", expected_revision=self.revision(), operations=[{"op": "import_device", "name": "X"}])
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(MemoryCircuit.saves, 0)

    def test_registered_firmware_uses_persistent_ascii_relative_program(self):
        firmware = self.root / "source.hex"
        firmware.write_text(":0100000001FE\n:00000001FF\n", encoding="ascii")
        self.inputs["firmware"] = {"follow": str(firmware)}
        self.task = DesignTask(self.task_root, self.inputs, api=self.api, runtime=self.runtime)
        self.task.config = lambda: SimpleNamespace()
        self.api.firmware_info = firmware_info
        self.add_pair()
        result = self.request("edit", expected_revision=self.revision(), operations=[
            {"op": "assign_firmware", "ref": "R1", "firmware_id": "follow"}])
        self.assertEqual(result["status"], "file_verified", result)
        current = self.task.current()
        program = MemoryCircuit.open(current).parts[0]["properties"]["PROGRAM"]
        self.assertTrue(program.isascii())
        self.assertFalse(Path(program).is_absolute())
        staged = (current.parent / program).resolve()
        self.assertTrue(staged.is_relative_to(self.task_root))
        self.assertEqual(staged.read_bytes(), firmware.read_bytes())

    @unittest.skipUnless(shutil.which("node"), "Node is needed to inspect the DSH plugin's actual schema export")
    def test_javascript_tool_schema_covers_the_python_domain_contract(self):
        repository = Path(__file__).resolve().parents[1]
        script = "import('./tools/dsh_design_tool.mjs').then(m=>console.log(JSON.stringify(m.parameters(" + json.dumps(sorted(ACTIONS)) + "))));"
        process = subprocess.run([shutil.which("node"), "--input-type=module", "-e", script], cwd=repository,
                                 capture_output=True, encoding="utf8", timeout=15, check=True)
        schema = json.loads(process.stdout)
        self.assertEqual(set(schema["action"]["enum"]), set(ACTIONS))
        for action, (required, optional) in ACTION_FIELDS.items():
            with self.subTest(action=action):
                self.assertTrue((required | optional) <= schema.keys())
        for field, table, discriminator in (("operations", EDIT_FIELDS, "op"), ("steps", STEP_FIELDS, "op"), ("assertions", ASSERT_FIELDS, "type")):
            properties = schema[field]["items"]["properties"]
            self.assertEqual(set(properties[discriminator]["enum"]), set(table))
            for operation, (required, optional) in table.items():
                with self.subTest(field=field, operation=operation):
                    self.assertTrue((required | optional) <= properties.keys())


if __name__ == "__main__":
    unittest.main()
