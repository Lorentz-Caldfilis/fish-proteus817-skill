"""Desktop task persistence and real typed-service dispatch, without a GUI."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from fish_proteus.desktop import execute_desktop_request, file_lock
from fish_proteus.firmware import firmware_info, gpio_events
from fish_proteus._vendor.proteus_auto.measurements import parse_graph_csv, sample
from test_design_tool import MemoryCircuit, MemoryLibrary, NativeSessionDouble, NativeSimulationDouble


class DesktopTaskTests(unittest.TestCase):
    def setUp(self):
        base = Path(__file__).resolve().parents[1] / ".work" / "desktop-unit-tests"
        base.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=base)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.cwd = self.root / "workspace"
        self.cwd.mkdir()
        self.store = self.root / "state"
        program = self.root / "program" / "BIN" / "PDS.EXE"
        program.parent.mkdir(parents=True)
        program.write_bytes(b"synthetic executable identity, never executed")
        samples, library = self.root / "samples", self.root / "library"
        samples.mkdir()
        library.mkdir()
        template = samples / "template.pdsprj"
        template.write_text(json.dumps({"parts": [], "edges": [], "power": {}}), encoding="utf8")
        self.config = {"executable": str(program), "samples_root": str(samples),
                       "library_root": str(library), "template_project": str(template)}
        self.api = SimpleNamespace(Circuit=MemoryCircuit, Library=MemoryLibrary,
            parse_graph_csv=parse_graph_csv, sample_graph=sample, gpio_events=gpio_events,
            firmware_info=firmware_info,
            capability_report=lambda config: {"domains": {"file": {"implemented": True, "runtime_verified": False}}})
        self.runtime = SimpleNamespace(Session=NativeSessionDouble, Simulation=NativeSimulationDouble)
        NativeSessionDouble.instances = []
        NativeSessionDouble.abnormal_close = False
        NativeSimulationDouble.verify_time = False
        NativeSimulationDouble.fail_press = False

    def call(self, action, *, session="desktop-session-a", **arguments):
        return execute_desktop_request({"action": action, **arguments}, store_root=self.store,
            session_id=session, working_directory=self.cwd, config=self.config,
            api=self.api, runtime=self.runtime)

    def create(self, session="desktop-session-a"):
        result = self.call("create", session=session, title="Desktop smoke")
        self.assertEqual(result["status"], "file_verified", result)
        return result

    def pair(self):
        return self.call("edit", operations=[
            {"op": "add", "device": "TEST-RES", "ref": "R1", "value": "1k", "x": 0, "y": 0},
            {"op": "add", "device": "TEST-RES", "ref": "R2", "value": "2k", "x": 300000, "y": 0},
            {"op": "connect", "first": "R1.B", "second": "R2.A"}])

    def test_automatic_task_persists_and_sessions_do_not_share_projects(self):
        created = self.create()
        first = created["desktop"]
        again = self.call("task_current")
        self.assertEqual(again["desktop"]["task_id"], first["task_id"])
        self.assertEqual(again["desktop"]["project_path"], first["project_path"])
        second = self.create(session="desktop-session-b")
        self.assertNotEqual(second["desktop"]["task_id"], first["task_id"])
        self.assertNotEqual(second["desktop"]["task_root"], first["task_root"])
        denied = self.call("task_select", session="desktop-session-b", task_id=first["task_id"])
        self.assertEqual(denied["status"], "blocked")
        self.assertEqual(self.call("task_current", session="desktop-session-b")["desktop"]["task_id"], second["desktop"]["task_id"])

    def test_multiple_tasks_recover_the_selected_project(self):
        original = self.create()
        self.assertEqual(self.pair()["status"], "file_verified")
        first = self.call("task_current")
        second = self.call("task_create", label="Second goal")
        self.assertNotEqual(first["desktop"]["task_id"], second["desktop"]["task_id"])
        self.assertEqual(self.call("inspect")["status"], "blocked")
        self.create()
        listed = self.call("task_list")
        self.assertEqual(len(listed["data"]["tasks"]), 2)
        self.call("task_select", task_id=original["desktop"]["task_id"])
        checked = self.call("inspect", sections=["components"])
        self.assertEqual([part["ref"] for part in checked["data"]["components"]], ["R1", "R2"])

    def test_task_create_replay_is_session_scoped_and_keeps_original_context(self):
        first = self.call("task_create", request_id="new-task-1", label="Original goal")
        self.assertEqual(first["status"], "prepared", first)
        second = self.call("task_create", label="Later goal")
        replayed = self.call("task_create", request_id="new-task-1", label="Original goal")
        self.assertTrue(replayed["replayed"])
        self.assertEqual(replayed["data"], first["data"])
        self.assertEqual(replayed["desktop"], first["desktop"])
        listed = self.call("task_list")
        self.assertEqual(len(listed["data"]["tasks"]), 2)
        self.assertEqual(listed["data"]["current_task"], second["desktop"]["task_id"])
        other = self.call("task_create", session="other-session", request_id="new-task-1", label="Original goal")
        self.assertEqual(other["status"], "prepared", other)
        self.assertNotEqual(other["desktop"]["task_id"], first["desktop"]["task_id"])

    def test_management_id_conflicts_across_payloads_and_actions_without_mutating_tasks(self):
        first = self.call("task_create", request_id="management-1", label="First")
        for action, arguments in [("task_create", {"label": "Changed"}), ("task_list", {})]:
            with self.subTest(action=action):
                result = self.call(action, request_id="management-1", **arguments)
                self.assertEqual(result["status"], "blocked", result)
                self.assertIn("different desktop management request", result["error"]["message"])
        listed = self.call("task_list")
        self.assertEqual(len(listed["data"]["tasks"]), 1)
        self.assertEqual(listed["data"]["current_task"], first["desktop"]["task_id"])

    def test_management_cache_commit_failure_does_not_commit_task_selection(self):
        from fish_proteus import desktop as module
        original_write = module._write
        def fail_session_commit(path, value):
            if Path(path).name == "session.json" and "desktop_requests" in value:
                raise OSError("synthetic interrupted atomic session replace")
            return original_write(path, value)
        with patch("fish_proteus.desktop._write", side_effect=fail_session_commit):
            failed = self.call("task_create", request_id="atomic-task-1", label="Atomic goal")
        self.assertEqual(failed["status"], "blocked", failed)
        self.assertEqual(self.call("task_list")["data"]["tasks"], [])
        retry = self.call("task_create", request_id="atomic-task-1", label="Atomic goal")
        self.assertEqual(retry["status"], "prepared", retry)
        listed = self.call("task_list")
        self.assertEqual(len(listed["data"]["tasks"]), 1)
        self.assertEqual(listed["data"]["current_task"], retry["desktop"]["task_id"])

    def test_missing_revision_is_host_supplied_and_actual_file_is_reopened(self):
        self.create()
        edited = self.pair()
        self.assertEqual(edited["status"], "file_verified", edited)
        path = Path(edited["desktop"]["project_path"])
        stored = json.loads(path.read_text(encoding="utf8"))
        self.assertEqual([part["value"] for part in stored["parts"]], ["1k", "2k"])
        checked = self.call("verify", assertions=[
            {"type": "component", "ref": "R1", "fields": {"value": "1k"}},
            {"type": "component", "ref": "R2", "fields": {"value": "2k"}},
            {"type": "connected", "pins": ["R1.B", "R2.A"]}])
        self.assertEqual(checked["status"], "file_verified", checked)
        self.assertTrue(checked["data"]["passed"])
        self.assertEqual(len(checked["data"]["checks"]), 3)

    def test_explicit_stale_revision_is_rejected_without_changing_current(self):
        first = self.create()
        self.pair()
        current = self.call("task_current")["data"]["current"]
        rejected = self.call("edit", expected_revision=first["current"]["revision"], operations=[
            {"op": "update", "ref": "R1", "changes": {"value": "9k"}}])
        self.assertEqual(rejected["status"], "blocked")
        self.assertIn("Stale", rejected["error"]["message"])
        self.assertEqual(self.call("task_current")["data"]["current"], current)

    def test_missing_revision_replay_keeps_the_first_effective_revision(self):
        self.create()
        payload = {"request_id": "desktop-retry-1", "operations": [
            {"op": "add", "device": "TEST-RES", "ref": "R1", "value": "1k", "x": 0, "y": 0}]}
        first = self.call("edit", **payload)
        second = self.call("edit", **payload)
        self.assertEqual(first["status"], "file_verified", first)
        self.assertEqual(second["status"], "file_verified", second)
        self.assertTrue(second["replayed"])
        self.assertEqual(first["current"], second["current"])
        changed = dict(payload, operations=[{"op": "add", "device": "TEST-RES", "ref": "R2", "value": "2k", "x": 0, "y": 0}])
        self.assertEqual(self.call("edit", **changed)["status"], "blocked")

    def test_new_original_can_be_registered_after_the_project_already_exists(self):
        self.create()
        self.pair()
        source = self.cwd / "donor.pdsprj"
        source.write_text(json.dumps({"parts": [], "edges": [], "power": {}}), encoding="utf8")
        before = source.read_bytes()
        registered = self.call("resource_register", kind="project", path="donor.pdsprj")
        self.assertEqual(registered["status"], "prepared", registered)
        self.assertEqual(self.call("inspect")["status"], "file_verified")
        firmware = self.cwd / "own.hex"
        firmware.write_text(":0100000001FE\n:00000001FF\n", encoding="ascii")
        added = self.call("resource_register", kind="firmware", path=str(firmware))
        result = self.call("firmware_info", firmware_id=added["data"]["input_id"])
        self.assertEqual(result["status"], "file_verified", result)
        self.assertEqual(source.read_bytes(), before)
        listed = self.call("resources")
        self.assertEqual(len(listed["data"]["resources"]), 2)
        same = self.call("resource_register", kind="project", path=str(source))
        self.assertTrue(same["data"]["reused"])
        self.assertEqual(same["data"]["input_id"], registered["data"]["input_id"])

    def test_changed_original_blocks_use_and_is_not_silently_rehashed(self):
        source = self.cwd / "original.pdsprj"
        source.write_text(json.dumps({"parts": [], "edges": [], "power": {}}), encoding="utf8")
        added = self.call("resource_register", kind="project", path=str(source))
        opened = self.call("open", input_id=added["data"]["input_id"])
        self.assertEqual(opened["status"], "file_verified", opened)
        source.write_text("changed by another actor", encoding="utf8")
        failed = self.call("inspect")
        self.assertEqual(failed["status"], "blocked")
        self.assertIn("registered original changed", failed["error"]["message"])
        self.assertEqual(source.read_text(encoding="utf8"), "changed by another actor")

    def test_candidates_register_without_model_host_paths_and_are_session_scoped(self):
        source = self.cwd / "example.pdsprj"
        source.write_bytes(b"file candidate, not format validation")
        found = self.call("resource_find", kind="project", query="example")
        candidate = found["data"]["matches"][0]
        self.assertNotIn("path", candidate)
        registered = self.call("resource_register", kind="project", candidate_id=candidate["candidate_id"])
        self.assertEqual(registered["status"], "prepared", registered)
        other = self.call("resource_register", session="other-session", kind="project", candidate_id=candidate["candidate_id"])
        self.assertEqual(other["status"], "blocked")
        self.assertEqual(registered["data"]["sha256"], hashlib.sha256(source.read_bytes()).hexdigest())

    def test_resource_search_is_bounded_and_does_not_search_state_or_follow_links(self):
        for index in range(5):
            (self.cwd / f"example-{index}.pdsprj").write_bytes(b"fixture")
        result = self.call("resource_find", kind="project", limit=2)
        self.assertEqual(len(result["data"]["matches"]), 2)
        self.assertTrue(result["data"]["truncated"])
        self.assertLessEqual(result["data"]["scanned_entries"], 5000)
        outside = self.call("resource_find", scope="home")
        self.assertEqual(outside["status"], "blocked")
        samples = self.call("resource_find", scope="samples", kind="project")
        self.assertEqual(samples["data"]["matches"][0]["name"], "template.pdsprj")

    def test_resource_paths_and_kind_are_checked_without_modifying_inputs(self):
        file = self.cwd / "notes.txt"
        file.write_text("untouched", encoding="utf8")
        for request in [
            {"kind": "project", "path": "notes.txt"},
            {"kind": "firmware", "path": "missing.hex"},
            {"kind": "project", "path": "\\\\server\\share\\source.pdsprj"},
            {"kind": "project", "path": "notes.txt", "candidate_id": "both"},
            {"kind": "script", "path": "notes.txt"},
        ]:
            with self.subTest(request=request):
                self.assertEqual(self.call("resource_register", **request)["status"], "blocked")
        self.assertEqual(file.read_text(encoding="utf8"), "untouched")

    def test_native_engine_lock_rejects_concurrent_sessions_and_releases_after_error(self):
        self.create()
        with file_lock(self.store / ".native.lock"):
            busy = self.call("run_sequence", steps=[{"op": "status"}], save_project=False)
        self.assertEqual(busy["status"], "blocked")
        self.assertIn("native engine", busy["error"]["message"])
        self.assertEqual(NativeSessionDouble.instances, [])
        # A failed request did not keep the session lock.
        self.assertEqual(self.call("inspect")["status"], "file_verified")

    def test_stm32_gpio_missing_and_zero_trace_block_before_native_and_preserve_revision(self):
        for index, value in enumerate([None, "0", 0, "0x0", "0.0"]):
            with self.subTest(value=value):
                session = f"trace-missing-{index}"
                self.create(session=session)
                operation = {"op": "add", "device": "STM32F103R6", "ref": "U1", "value": "MCU",
                             "x": 0, "y": 0}
                if value is not None:
                    operation["properties"] = {"TRACE_GPIO": value}
                added = self.call("edit", session=session, operations=[operation])
                self.assertEqual(added["status"], "file_verified", added)
                before = self.call("task_current", session=session)["data"]["current"]
                with patch("fish_proteus.desktop.execute_request",
                           side_effect=AssertionError("Preflight must reject before native/backend execution")):
                    result = self.call("run_sequence", session=session,
                        steps=[{"op": "start"}, {"op": "gpio_events", "ref": "U1", "port": 0, "pin": 5}])
                self.assertEqual(result["status"], "blocked", result)
                self.assertEqual(result["error"]["type"], "GPIOTraceConfigurationError")
                self.assertIn('properties={"TRACE_GPIO":"3"}', result["error"]["message"])
                self.assertEqual(self.call("task_current", session=session)["data"]["current"], before)
                self.assertEqual(NativeSessionDouble.instances, [])

    def test_stm32_nonzero_masks_pass_preflight_without_being_forced_to_three(self):
        for index, value in enumerate(["1", "3", "4", "0x20", 8]):
            with self.subTest(value=value):
                session = f"trace-enabled-{index}"
                self.create(session=session)
                self.call("edit", session=session, operations=[
                    {"op": "add", "device": "STM32F103R6", "ref": "U1", "value": "MCU",
                     "x": 0, "y": 0, "properties": {"TRACE_GPIO": value}}])
                with patch("fish_proteus.desktop.execute_request", return_value={"status": "prepared"}) as dispatch:
                    result = self.call("run_sequence", session=session,
                        steps=[{"op": "start"}, {"op": "gpio_events", "ref": "U1"}])
                self.assertEqual(result["status"], "prepared", result)
                dispatch.assert_called_once()
                part = self.call("inspect", session=session)["data"]["components"][0]
                self.assertEqual(part["properties"]["TRACE_GPIO"], value)

    def test_gpio_trace_preflight_targets_actual_stm32_refs_and_skips_other_models(self):
        self.create()
        self.call("edit", operations=[
            {"op": "add", "device": "STM32F103R6", "ref": "U1", "value": "MCU", "x": 0, "y": 0},
            {"op": "add", "device": "OTHER-MCU", "ref": "U2", "value": "MCU", "x": 300000, "y": 0}])
        with patch("fish_proteus.desktop.execute_request", return_value={"status": "prepared"}) as dispatch:
            other = self.call("run_sequence", steps=[{"op": "gpio_events", "ref": "U2"}])
            self.assertEqual(other["status"], "prepared", other)
            dispatch.assert_called_once()
        unfiltered = self.call("run_sequence", steps=[{"op": "gpio_events"}])
        self.assertEqual(unfiltered["error"]["type"], "GPIOTraceConfigurationError")
        with patch("fish_proteus.desktop.execute_request", return_value={"status": "prepared"}) as dispatch:
            structure = self.call("run_sequence", steps=[{"op": "netlist"}, {"op": "status"}])
            self.assertEqual(structure["status"], "prepared", structure)
            dispatch.assert_called_once()

    def test_gpio_trace_preflight_does_not_infer_opaque_staged_projects(self):
        source = self.cwd / "opaque.pdsprj"
        source.write_bytes(b"opaque project fixture")
        resource = self.call("resource_register", kind="project", path=str(source))
        staged = self.call("stage", input_id=resource["data"]["input_id"])
        self.assertEqual(staged["status"], "prepared", staged)
        with patch("fish_proteus.desktop.execute_request", return_value={"status": "prepared"}) as dispatch:
            result = self.call("run_sequence", steps=[{"op": "gpio_events"}])
            self.assertEqual(result["status"], "prepared", result)
            dispatch.assert_called_once()

    def test_gpio_preflight_preserves_core_replay_after_a_later_trace_change(self):
        self.create()
        added = self.call("edit", operations=[
            {"op": "add", "device": "STM32F103R6", "ref": "U1", "value": "MCU",
             "x": 0, "y": 0, "properties": {"TRACE_GPIO": "3"}}])
        self.assertEqual(added["status"], "file_verified", added)
        NativeSimulationDouble.verify_time = True
        arguments = {"request_id": "gpio-history-1", "save_project": False,
            "steps": [{"op": "run_for", "seconds": .03},
                      {"op": "gpio_events", "ref": "U1", "port": 0, "pin": 1}]}
        first = self.call("run_sequence", **arguments)
        self.assertEqual(first["status"], "runtime_observed", first)
        self.assertEqual(len(NativeSessionDouble.instances), 1)
        changed = self.call("edit", operations=[
            {"op": "set_properties", "ref": "U1", "properties": {"TRACE_GPIO": "0"}}])
        self.assertEqual(changed["status"], "file_verified", changed)
        replayed = self.call("run_sequence", **arguments)
        self.assertEqual(replayed["status"], "runtime_observed", replayed)
        self.assertTrue(replayed["replayed"])
        self.assertEqual(replayed["data"], first["data"])
        self.assertEqual(len(NativeSessionDouble.instances), 1)

    def test_interrupted_core_lock_recovers_only_after_its_owner_exited(self):
        current = self.create()
        root = Path(current["desktop"]["task_root"])
        lock = root / ".design.lock"
        lock.write_text(str(os.getpid()), encoding="ascii")
        busy = self.call("inspect")
        self.assertEqual(busy["status"], "blocked")
        self.assertTrue(lock.is_file())
        process = subprocess.Popen([sys.executable, "-I", "-B", "-c",
            "import os,sys,time; from pathlib import Path; "
            "Path(sys.argv[1]).write_text(str(os.getpid()),encoding='ascii'); "
            "print('lock-created',flush=True); time.sleep(30)", str(lock)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf8")
        try:
            self.assertEqual(process.stdout.readline().strip(), "lock-created")
            process.kill()
            process.communicate(timeout=20)
            self.assertNotEqual(process.returncode, 0)
            self.assertTrue(lock.exists())
            recovered = self.call("inspect")
            self.assertEqual(recovered["status"], "file_verified", recovered)
            self.assertFalse(lock.exists())
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate(timeout=20)

    def test_session_os_lock_releases_when_its_process_exits(self):
        current = self.create()
        session_root = Path(current["desktop"]["task_root"]).parent.parent
        command = [sys.executable, "-B", "-c",
            "from fish_proteus.desktop import file_lock; import os,sys; "
            "lock=file_lock(sys.argv[1]); lock.__enter__(); os._exit(0)",
            str(session_root / ".session.lock")]
        process = subprocess.run(command, cwd=Path(__file__).resolve().parents[1],
            capture_output=True, text=True, encoding="utf8", timeout=20)
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertEqual(self.call("inspect")["status"], "file_verified")

    def test_export_preserves_project_and_firmware_layout_without_changing_revision(self):
        self.create()
        self.pair()
        current = self.call("task_current")
        task_root = Path(current["desktop"]["task_root"])
        for directory, name in [("inputs", "own.hex"), ("firmware", "extracted.elf")]:
            target = task_root / directory / name
            target.parent.mkdir()
            target.write_bytes(b"owned dependency bytes")
        destination = self.cwd / "delivered-design"
        result = self.call("project_export", destination=str(destination))
        self.assertEqual(result["status"], "file_verified", result)
        self.assertEqual(result["desktop"]["export_path"], result["data"]["project"])
        project = Path(result["data"]["project"])
        self.assertEqual(project.read_bytes(), Path(current["desktop"]["project_path"]).read_bytes())
        self.assertEqual((destination / "inputs" / "own.hex").read_bytes(), b"owned dependency bytes")
        self.assertEqual((destination / "firmware" / "extracted.elf").read_bytes(), b"owned dependency bytes")
        self.assertEqual(self.call("task_current")["data"]["current"], current["data"]["current"])
        self.assertEqual(self.call("project_export", destination=str(destination))["status"], "blocked")

    def test_export_rejects_install_and_task_storage_destinations(self):
        self.create()
        for path in [self.store / "export", Path(self.config["samples_root"]) / "export",
                     Path(self.config["executable"]).parent.parent / "export"]:
            with self.subTest(path=path):
                result = self.call("project_export", destination=str(path))
                self.assertEqual(result["status"], "blocked", result)
                self.assertFalse(path.exists())

    def test_export_replay_returns_original_result_after_switching_tasks(self):
        self.create()
        self.pair()
        destination = self.cwd / "replayed-export"
        first = self.call("project_export", request_id="export-request-1", destination=str(destination))
        self.assertEqual(first["status"], "file_verified", first)
        before = Path(first["data"]["project"]).read_bytes()
        later = self.call("task_create", label="Unrelated later goal")
        replayed = self.call("project_export", request_id="export-request-1", destination=str(destination))
        self.assertEqual(replayed["status"], "file_verified", replayed)
        self.assertTrue(replayed["replayed"])
        self.assertEqual(replayed["data"], first["data"])
        self.assertEqual(replayed["desktop"], first["desktop"])
        self.assertEqual(self.call("task_current")["desktop"]["task_id"], later["desktop"]["task_id"])
        self.assertEqual(Path(first["data"]["project"]).read_bytes(), before)
        conflict = self.call("project_export", request_id="export-request-1", destination=str(self.cwd / "different"))
        self.assertEqual(conflict["status"], "blocked", conflict)
        self.assertFalse((self.cwd / "different").exists())

    def test_host_context_is_not_accepted_from_model_payload(self):
        for extra in [{"session_id": "somebody-else"}, {"store_root": "outside"},
                      {"working_directory": "outside"}, {"config": {"executable": "other"}}]:
            with self.subTest(extra=extra):
                result = self.call("task_current", **extra)
                self.assertEqual(result["status"], "blocked", result)
        self.assertEqual(self.call("task_list")["data"]["tasks"], [])

    def test_gate_uses_only_its_own_repository_and_returns_one_json(self):
        repository = Path(__file__).resolve().parents[1]
        config = self.root / "config.json"
        config.write_text(json.dumps(self.config), encoding="utf8")
        command = [sys.executable, "-I", "-B", str(repository / "tools" / "desktop_gate.py"),
            "--workspace", str(repository), "--store-root", str(self.store),
            "--session-id", "gate-session", "--working-directory", str(self.cwd),
            "--config-file", str(config)]
        result = subprocess.run(command, input=json.dumps({"action": "task_current"}),
            capture_output=True, text=True, encoding="utf8", timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        value = json.loads(result.stdout)
        self.assertEqual(value["desktop"]["session_id"], "gate-session")
        self.assertEqual(value["status"], "prepared")
        bad = list(command)
        bad[bad.index("--workspace") + 1] = str(self.cwd)
        result = subprocess.run(bad, input='{"action":"task_current"}', capture_output=True,
            text=True, encoding="utf8", timeout=20)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(json.loads(result.stdout)["status"], "blocked")


if __name__ == "__main__":
    unittest.main()
