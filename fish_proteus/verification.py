"""Conservative verification of recorded observations, never an observation source."""

from __future__ import annotations

from fractions import Fraction
import math
from pathlib import Path
from typing import Any

from .artifacts import read_json, sha256_file, write_json
from .course import normalize_parameters


def _number(value: Any) -> bool:
    return not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(value)


def _led_connections(netlist: dict[str, Any]) -> list[dict[str, Any]]:
    """Check the positive LED mapping in an actual native SDF graph."""
    parts, nets = netlist.get("parts", {}), netlist.get("nets", [])
    if not isinstance(parts, dict) or not isinstance(nets, list):
        raise ValueError("Invalid native netlist graph")

    def endpoints(net):
        return {(pin.get("ref"), pin.get("pin")) for pin in net.get("pins", [])}

    grounds = [net for net in nets if net.get("name") == "GND"]
    if len(grounds) != 1:
        raise ValueError("Expected one actual GND net")
    grounded = endpoints(grounds[0])
    result = []
    for bit in range(8):
        led, port = f"D{bit}", f"PB{bit}"
        part = parts.get(led, {})
        if part.get("device") != "LED-GREEN" or str(part.get("properties", {}).get("DRIVE")) != "1":
            raise ValueError(f"{led} is not the expected positive-drive LED model")
        anode = [net for net in nets if ("U8", port) in endpoints(net)]
        if len(anode) != 1 or endpoints(anode[0]) != {("U8", port), (led, "A")}:
            raise ValueError(f"Actual {port} is not uniquely connected to {led}.A")
        cathode = [net for net in nets if (led, "K") in endpoints(net)]
        if len(cathode) != 1:
            raise ValueError(f"No unique cathode connection for {led}")
        other = endpoints(cathode[0]) - {(led, "K")}
        if len(other) != 1:
            raise ValueError(f"Unexpected cathode branch for {led}")
        resistor, pin = next(iter(other))
        if parts.get(resistor, {}).get("device") != "RES" or pin not in ("1", "2"):
            raise ValueError(f"{led} cathode is not connected through a known resistor")
        if (resistor, "2" if pin == "1" else "1") not in grounded:
            raise ValueError(f"{led} resistor return is not grounded")
        result.append({"bit": bit, "port": f"U8.{port}", "led_anode": f"{led}.A", "resistor": resistor, "return": "GND"})
    return result


def verify_job(manifest_path: str | Path, runtime_path: str | Path | None = None) -> dict[str, Any]:
    job_path = Path(manifest_path).resolve(strict=True)
    job = read_json(job_path)
    if job.get("schema") != "fish-proteus.job.v1":
        raise ValueError("Unsupported job manifest")
    root = job_path.parent
    runtime_file = Path(runtime_path).resolve() if runtime_path else root / "runtime.json"
    checks: list[dict[str, Any]] = []

    def check(name: str, passed: bool, detail: Any, missing: bool = False) -> None:
        checks.append({"name": name, "status": "passed" if passed else ("blocked" if missing else "failed"), "detail": detail})

    values = normalize_parameters(job["case_id"], **job["parameters"])
    build = job.get("build", {})
    check("fresh_build_record", build.get("status") == "built", build.get("status", "missing"), missing=not build)
    for field, expected_hash in (("source", build.get("source_sha256")), ("executable", build.get("artifact", {}).get("sha256"))):
        path = Path(job[field]).resolve()
        if not path.is_relative_to(root):
            check(field + "_identity", False, "Job file escapes its work directory")
        elif not path.is_file() or not expected_hash:
            check(field + "_identity", False, "File or build identity missing", missing=True)
        else:
            check(field + "_identity", sha256_file(path) == expected_hash, {"current_sha256": sha256_file(path), "built_sha256": expected_hash})

    report: dict[str, Any] = {"schema": "fish-proteus.verification.v1", "job_file": str(job_path), "case_id": job["case_id"], "checks": checks}
    if not runtime_file.is_file():
        check("runtime_observations", False, "No runtime.json; building a program is not running Proteus", missing=True)
        return _finish(root, report)
    runtime = read_json(runtime_file)
    check("runtime_status", runtime.get("status") in ("runtime_observed", "runtime_verified"), runtime.get("status", "missing"), missing=runtime.get("status") in (None, "blocked", "not_run"))
    check("runtime_errors", not runtime.get("errors"), runtime.get("errors", []))
    for field in ("source", "executable"):
        actual = runtime.get(field + "_sha256")
        built = build.get("source_sha256") if field == "source" else build.get("artifact", {}).get("sha256")
        check("runtime_" + field + "_identity", bool(actual and built and actual == built), {"runtime_sha256": actual, "built_sha256": built}, missing=not actual or not built)
    project = Path(job["project"])
    project_hash = runtime.get("project_sha256")
    check("runtime_project_identity", bool(project_hash and project.is_file() and sha256_file(project) == project_hash), project_hash, missing=not project_hash or not project.is_file())
    staged_hash = runtime.get("staged_executable_sha256")
    built_hash = build.get("artifact", {}).get("sha256")
    check("loaded_staging_artifact_identity", bool(staged_hash and built_hash and staged_hash == built_hash), {"staged_sha256": staged_hash, "built_sha256": built_hash}, missing=not staged_hash or not built_hash)
    check("owned_process_closed", runtime.get("process_closed") is True, runtime.get("process_closed"), missing="process_closed" not in runtime)

    raw_artifacts = runtime.get("raw_artifacts", [])
    valid_artifacts = 0
    for item in raw_artifacts:
        if not isinstance(item, dict) or not item.get("path") or not item.get("sha256"):
            check("raw_artifact", False, "Artifact requires path and SHA-256", missing=True)
            continue
        path = Path(item["path"])
        if not path.is_absolute():
            path = runtime_file.parent / path
        valid = path.is_file() and sha256_file(path) == item["sha256"]
        check("raw_artifact_identity", valid, {"path": str(path), "sha256": item["sha256"]})
        valid_artifacts += int(valid)
    check("raw_artifact_present", valid_artifacts > 0, {"valid_artifacts": valid_artifacts}, missing=valid_artifacts == 0)

    observed = runtime.get("observed", {})
    if not isinstance(observed, dict):
        observed = {}
    check("observation_method", bool(observed.get("method")), observed.get("method", "missing"), missing=not observed.get("method"))
    if job["case_id"] in ("divider", "cascade"):
        counts = [values["divisor"]] if job["case_id"] == "divider" else [values["divisor0"], values["divisor1"]]
        divisor = math.prod(counts)
        expected = float(Fraction(1_000_000, divisor))
        declared = job.get("expected", {}).get("output_hz")
        check("expected_frequency_consistency", _number(declared) and math.isclose(declared, expected, rel_tol=1e-12), {"recomputed_hz": expected, "manifest_hz": declared})
        measured = observed.get("output_hz")
        check("measured_output_frequency", _number(measured) and measured > 0, measured, missing=not _number(measured))
        if _number(measured) and measured > 0:
            error = abs(measured - expected) / expected
            check("output_frequency_matches", error <= 0.01, {"measured_hz": measured, "expected_hz": expected, "relative_error": error, "allowed_relative_error": 0.01})
        if "input_hz" in observed:
            measured_input = observed["input_hz"]
            check("input_frequency_matches", _number(measured_input) and abs(measured_input - 1_000_000) <= 10_000, measured_input)
    else:
        low, high = values["on_value"], values["off_value"]
        if values["invert"]:
            low, high = high, low
        expected_ports = {0: low, 1: high}
        declared = job.get("expected", {}).get("port_b_by_input_bit", {})
        check("expected_port_consistency", declared == {str(k): v for k, v in expected_ports.items()}, {"recomputed": expected_ports, "manifest": declared})
        led_mode = observed.get("output_observation") == "led-display"
        if led_mode:
            report["output_observation"] = "LED display, not a direct PB register read"
            wiring = observed.get("led_wiring", {})
            try:
                wiring_path = Path(wiring["path"])
                if not wiring_path.is_absolute():
                    wiring_path = runtime_file.parent / wiring_path
                identity_ok = wiring_path.is_file() and sha256_file(wiring_path) == wiring.get("sha256")
                if not identity_ok:
                    raise ValueError("Native LED wiring evidence is missing or changed")
                if not any(item.get("sha256") == wiring.get("sha256") for item in raw_artifacts if isinstance(item, dict)):
                    raise ValueError("Native LED wiring graph is not a captured raw artifact")
                mapping = _led_connections(read_json(wiring_path))
                check("native_led_wiring", True, mapping)
            except (KeyError, OSError, ValueError, TypeError) as error:
                check("native_led_wiring", False, str(error), missing=not wiring)
        samples = observed.get("samples", [])
        if not isinstance(samples, list):
            samples = []
        bits = []
        for index, sample in enumerate(samples):
            if not isinstance(sample, dict):
                check("port_sample", False, {"index": index, "error": "Sample is not an object"})
                continue
            bit, output = sample.get("input_bit"), sample.get("led_mask" if led_mode else "port_b")
            valid_bit = type(bit) is int and bit in (0, 1)
            valid_output = type(output) is int and 0 <= output <= 255
            label = "led_mask" if led_mode else "port_b"
            check("led_sample" if led_mode else "port_sample", valid_bit and valid_output and output == expected_ports.get(bit), {"index": index, "input_bit": bit, "observed_" + label: output, "expected_" + label: expected_ports.get(bit)})
            if valid_bit and valid_output:
                bits.append(bit)
        check("both_input_states_observed", set(bits) == {0, 1}, bits, missing=set(bits) != {0, 1})
        transitions = [bit for index, bit in enumerate(bits) if index == 0 or bit != bits[index - 1]]
        check("input_transition_and_recovery", len(transitions) >= 3, transitions, missing=len(transitions) < 3)
    report["runtime_file"] = str(runtime_file)
    return _finish(root, report)


def _finish(root: Path, report: dict[str, Any]) -> dict[str, Any]:
    statuses = {item["status"] for item in report["checks"]}
    report["status"] = "failed" if "failed" in statuses else ("blocked" if "blocked" in statuses else "passed")
    report["meaning"] = "Recorded runtime observations meet the documented checks" if report["status"] == "passed" else "No successful behavior claim is justified by this report"
    write_json(root / "verification.json", report)
    return report
