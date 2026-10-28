"""Unit tests use synthetic observation fixtures, not a Proteus runtime claim."""

import json
from pathlib import Path
import tempfile
import unittest

from fish_proteus.artifacts import sha256_file, write_json
from fish_proteus.build import build_job
from fish_proteus.course import expected_result, generated_source, normalize_parameters
from fish_proteus.verification import verify_job


class VerificationTests(unittest.TestCase):
    def setUp(self):
        workspace = Path(__file__).resolve().parents[1] / ".work" / "verification-tests"
        workspace.mkdir(parents=True, exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(dir=workspace)
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.assertTrue(self.root.is_relative_to(workspace.resolve()))

    def job(self, case="divider"):
        parameters = normalize_parameters(case)
        source = self.root / "main.asm"
        source.write_text(generated_source(case, parameters), encoding="utf-8")
        project = self.root / "test.pdsprj"
        project.write_bytes(b"unit-test-only")
        manifest = {"schema": "fish-proteus.job.v1", "case_id": case, "parameters": parameters, "expected": expected_result(case, parameters), "source": str(source), "project": str(project), "executable": str(self.root / "program.exe"), "job_root": str(self.root), "job_file": str(self.root / "job.json")}
        write_json(self.root / "job.json", manifest)
        return build_job(self.root / "job.json", toolchain="builtin")

    def runtime(self, job, observed):
        raw = self.root / "fixture.txt"
        raw.write_text("Synthetic observer fixture for verifier unit tests; not an actual simulation", encoding="utf-8")
        report = {"status": "runtime_observed", "source_sha256": job["build"]["source_sha256"], "executable_sha256": job["build"]["artifact"]["sha256"], "staged_executable_sha256": job["build"]["artifact"]["sha256"], "project_sha256": sha256_file(job["project"]), "process_closed": True, "observed": {"method": "synthetic-unit-fixture", **observed}, "raw_artifacts": [{"path": str(raw), "sha256": sha256_file(raw)}]}
        write_json(self.root / "runtime.json", report)

    def test_build_only_is_blocked(self):
        self.job()
        self.assertEqual(verify_job(self.root / "job.json")["status"], "blocked")

    def test_frequency_fixture_checks_expected_and_actual(self):
        job = self.job()
        self.runtime(job, {"output_hz": 200000.0})
        self.assertEqual(verify_job(self.root / "job.json")["status"], "passed")
        self.runtime(job, {"output_hz": 100000.0})
        self.assertEqual(verify_job(self.root / "job.json")["status"], "failed")

    def test_modified_executable_invalidates_matching_observation(self):
        job = self.job()
        self.runtime(job, {"output_hz": 200000.0})
        with Path(job["executable"]).open("ab") as stream:
            stream.write(b"changed")
        self.assertEqual(verify_job(self.root / "job.json")["status"], "failed")

    def test_declared_success_without_measurements_is_blocked(self):
        job = self.job()
        self.runtime(job, {})
        self.assertEqual(verify_job(self.root / "job.json")["status"], "blocked")

    def test_changed_project_and_wrong_loaded_artifact_are_rejected(self):
        job = self.job()
        self.runtime(job, {"output_hz": 200000.0})
        Path(job["project"]).write_bytes(b"a different circuit")
        self.assertEqual(verify_job(self.root / "job.json")["status"], "failed")
        self.runtime(job, {"output_hz": 200000.0})
        raw = json.loads((self.root / "runtime.json").read_text(encoding="utf-8"))
        raw["staged_executable_sha256"] = "0" * 64
        write_json(self.root / "runtime.json", raw)
        self.assertEqual(verify_job(self.root / "job.json")["status"], "failed")

    def test_missing_or_altered_raw_evidence_is_not_accepted(self):
        job = self.job()
        self.runtime(job, {"output_hz": 200000.0})
        (self.root / "fixture.txt").write_text("changed", encoding="utf-8")
        self.assertNotEqual(verify_job(self.root / "job.json")["status"], "passed")

    def test_switch_requires_both_inputs_and_recovery(self):
        job = self.job("switch")
        self.runtime(job, {"samples": [{"input_bit": 1, "port_b": 0}]})
        self.assertEqual(verify_job(self.root / "job.json")["status"], "blocked")
        self.runtime(job, {"samples": [{"input_bit": 1, "port_b": 0}, {"input_bit": 0, "port_b": 255}, {"input_bit": 1, "port_b": 0}]})
        self.assertEqual(verify_job(self.root / "job.json")["status"], "passed")

    def test_boolean_is_not_a_frequency_measurement(self):
        job = self.job()
        self.runtime(job, {"output_hz": True})
        self.assertEqual(verify_job(self.root / "job.json")["status"], "blocked")

    def test_led_observations_require_actual_positive_wiring(self):
        job = self.job("switch")
        graph = {"parts": {}, "nets": []}
        ground = {"name": "GND", "pins": []}
        for bit in range(8):
            graph["parts"][f"D{bit}"] = {"device": "LED-GREEN", "properties": {"DRIVE": "1"}}
            graph["parts"][f"R{bit}"] = {"device": "RES"}
            graph["nets"] += [{"name": f"PB{bit}", "pins": [{"ref": "U8", "pin": f"PB{bit}"}, {"ref": f"D{bit}", "pin": "A"}]}, {"name": f"K{bit}", "pins": [{"ref": f"D{bit}", "pin": "K"}, {"ref": f"R{bit}", "pin": "1"}]}]
            ground["pins"].append({"ref": f"R{bit}", "pin": "2"})
        graph["nets"].append(ground)
        wiring = self.root / "native-netlist.json"
        write_json(wiring, graph)
        self.runtime(job, {"output_observation": "led-display", "led_wiring": {"path": str(wiring), "sha256": sha256_file(wiring)}, "samples": [{"input_bit": 1, "led_mask": 0}, {"input_bit": 0, "led_mask": 255}, {"input_bit": 1, "led_mask": 0}]})
        runtime = json.loads((self.root / "runtime.json").read_text(encoding="utf-8"))
        runtime["raw_artifacts"].append({"path": str(wiring), "sha256": sha256_file(wiring)})
        write_json(self.root / "runtime.json", runtime)
        self.assertEqual(verify_job(self.root / "job.json")["status"], "passed")
        graph["nets"][0]["pins"][1]["pin"] = "K"
        write_json(wiring, graph)
        runtime["observed"]["led_wiring"]["sha256"] = sha256_file(wiring)
        runtime["raw_artifacts"][-1]["sha256"] = sha256_file(wiring)
        write_json(self.root / "runtime.json", runtime)
        self.assertEqual(verify_job(self.root / "job.json")["status"], "failed")


if __name__ == "__main__":
    unittest.main()
