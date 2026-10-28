"""A bounded DSH bridge: fixed project CLI, fixed library and one fixed job.

The model supplies typed case parameters, never a shell command, executable,
module name, file path, environment assignment or arbitrary Python code.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


OPERATIONS = frozenset({"doctor", "prepare", "build", "run", "verify"})
FIELDS = {
    "doctor": frozenset({"operation"}),
    "prepare": frozenset({"operation", "case", "divisor", "divisor0", "divisor1", "on_value", "off_value", "invert"}),
    "build": frozenset({"operation"}),
    "run": frozenset({"operation", "seconds"}),
    "verify": frozenset({"operation"}),
}


def descendant(path: Path, root: Path) -> Path:
    resolved = path.expanduser().resolve()
    if resolved == root or root not in resolved.parents:
        raise ValueError("The selected path is not a child of its permitted directory.")
    return resolved


def arguments(payload: dict, workspace: Path, library: Path, job: Path, allowed: frozenset[str]) -> list[str]:
    if not isinstance(payload, dict):
        raise ValueError("The tool payload must be a JSON object.")
    operation = payload.get("operation")
    if not isinstance(operation, str) or operation not in OPERATIONS or operation not in allowed:
        raise ValueError("This operation is not enabled for the current DSH task.")
    if set(payload) - FIELDS[operation]:
        raise ValueError("Unexpected fields are not accepted by the project tool.")
    if operation == "doctor":
        return ["doctor"]
    if operation == "prepare":
        case = payload.get("case")
        permitted = {
            "divider": {"divisor"},
            "cascade": {"divisor0", "divisor1"},
            "switch": {"on_value", "off_value", "invert"},
        }
        if not isinstance(case, str) or case not in permitted:
            raise ValueError("Select divider, cascade or switch.")
        if set(payload) - {"operation", "case"} - permitted[case]:
            raise ValueError("A supplied parameter does not apply to the chosen case.")
        result = ["prepare", "--library", str(library), "--case", case, "--output", str(job)]
        for key in ("divisor", "divisor0", "divisor1", "on_value", "off_value"):
            if key not in payload:
                continue
            value = payload[key]
            if isinstance(value, bool) or not isinstance(value, int):
                raise ValueError("Counter and output values must be integers.")
            lower, upper = (2, 65536) if key.startswith("divisor") else (0, 255)
            if not lower <= value <= upper:
                raise ValueError("A numerical parameter is outside the supported range.")
            result += ["--" + key.replace("_", "-"), str(value)]
        if "invert" in payload:
            if not isinstance(payload["invert"], bool):
                raise ValueError("invert must be boolean.")
            if payload["invert"]:
                result.append("--invert")
        return result
    manifest = descendant(job / "job.json", job)
    if not manifest.is_file():
        raise ValueError("Prepare the fixed job before building, running or verifying it.")
    record = json.loads(manifest.read_text(encoding="utf-8-sig"))
    for key in ("project", "source", "executable"):
        value = record.get(key)
        if not isinstance(value, str):
            raise ValueError("The job manifest has a missing or invalid artifact path.")
        path = Path(value)
        descendant(path if path.is_absolute() else job / path, job)
    result = [operation, "--manifest", str(manifest)]
    if operation == "run" and "seconds" in payload:
        seconds = payload["seconds"]
        if isinstance(seconds, bool) or not isinstance(seconds, (int, float)) or not 0 < seconds <= 20:
            raise ValueError("The bounded tool allows an observation duration above zero and at most 20 seconds.")
        result += ["--seconds", str(seconds)]
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--library", type=Path, required=True)
    parser.add_argument("--job-directory", type=Path, required=True)
    parser.add_argument("--allowed", nargs="+", choices=sorted(OPERATIONS), required=True)
    args = parser.parse_args()
    try:
        workspace = args.workspace.resolve(strict=True)
        if Path(__file__).resolve().parents[1] != workspace:
            raise ValueError("The gate may only execute the package in its own repository.")
        library = descendant(args.library, workspace)
        job = descendant(args.job_directory, workspace / ".work")
        payload = json.load(sys.stdin)
        argv = arguments(payload, workspace, library, job, frozenset(args.allowed))
        # -I ignores model-controlled Python search environment. Only the fixed
        # trusted repository is added for this project's package import.
        sys.path.insert(0, str(workspace))
        from fish_proteus.cli import main as cli_main
        return cli_main(argv)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({"status": "blocked", "stage": "bounded_tool", "error": str(exc)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    raise SystemExit(main())
