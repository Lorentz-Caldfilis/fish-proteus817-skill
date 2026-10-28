"""Reproduce the course acceptance matrix; runtime is explicit and serial."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
import sys

REPOSITORY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY))

from fish_proteus.artifacts import write_json
from fish_proteus.build import build_job
from fish_proteus.course import generate_variant, import_course, load_import, verify_import
from fish_proteus.environment import discover


def acceptance(source: Path | None, library: Path | None, output: Path, runtime: bool, repeat: int) -> dict:
    output = output.resolve()
    if output.exists():
        raise ValueError("Choose an unused --output directory; existing acceptance results are immutable")
    if not 1 <= repeat <= 5:
        raise ValueError("--repeat must be between 1 and 5")
    if source is None and library is None:
        raise ValueError("Provide --source or an already imported --library")
    protected = [source.resolve()] if source is not None else []
    if library is not None:
        imported = load_import(library)
        protected += [Path(imported[key]).resolve() for key in ("source_root", "import_root")]
    if any(output.is_relative_to(path) or path.is_relative_to(output) for path in protected):
        raise ValueError("Acceptance output must be separate from the original and imported course trees")
    if library is None:
        library = output / "private-course-library"
        import_course(source, library)
    protected_before = verify_import(library)
    if protected_before["status"] != "verified":
        raise ValueError("The protected course library/originals failed integrity verification")
    output.mkdir(parents=True, exist_ok=True)
    environment = discover()
    write_json(output / "environment.json", environment)
    scenarios = [
        ("divider-5", "divider", {"divisor": 5}),
        ("divider-10", "divider", {"divisor": 10}),
        ("cascade-1hz", "cascade", {"divisor0": 1000, "divisor1": 1000}),
        ("cascade-2hz", "cascade", {"divisor0": 1000, "divisor1": 500}),
        ("switch-default", "switch", {"on_value": 255, "off_value": 0, "invert": False}),
        ("switch-pattern", "switch", {"on_value": 51, "off_value": 204, "invert": False}),
    ]
    scenarios += [(f"divider-10-repeat-{index}", "divider", {"divisor": 10}) for index in range(2, repeat + 1)]
    results = []
    for name, case_id, parameters in scenarios:
        result = {"name": name, "case_id": case_id, "parameters": parameters, "runtime_status": "not_run"}
        try:
            job = generate_variant(library, case_id, output / name, **parameters)
            job = build_job(job["job_file"])
            result.update(job_file=job["job_file"], build_status=job["build"]["status"], executable_sha256=job["build"]["artifact"]["sha256"], expected=job["expected"])
            if runtime:
                from runtime_adaptation.runner import run_job
                from fish_proteus.verification import verify_job
                observation = run_job(Path(job["job_file"]), seconds=2.2 if case_id == "cascade" else 0.1)
                verified = verify_job(job["job_file"])
                result.update(runtime_status=observation.get("status"), observed=observation.get("observed"), verification_status=verified["status"], verification_file=str(output / name / "verification.json"))
        except Exception as error:
            result.update(status="blocked", error_type=type(error).__name__, error=str(error))
        results.append(result)
        write_json(output / "progress.json", {"results": results})
    protected_after = verify_import(library)
    built_ok = all(item.get("build_status") == "built" for item in results)
    runtime_ok = runtime and all(item.get("verification_status") == "passed" for item in results)
    status = "passed" if runtime_ok and protected_after["status"] == "verified" else ("build_only" if built_ok and not runtime and protected_after["status"] == "verified" else "incomplete")
    summary = {"schema": "fish-proteus.acceptance.v1", "recorded_utc": datetime.now(timezone.utc).isoformat(), "status": status, "runtime_requested": runtime, "all_builds_passed": built_ok, "all_runtime_checks_passed": bool(runtime_ok), "originals_before": protected_before, "originals_after": protected_after, "results": results}
    write_json(output / "acceptance.json", summary)
    return summary


def main() -> int:
    import json
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path)
    parser.add_argument("--library", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--runtime", action="store_true", help="Start serial Proteus sessions on the current Windows desktop")
    parser.add_argument("--repeat", type=int, default=3, help="Total fresh divider-10 jobs; default 3")
    args = parser.parse_args()
    try:
        summary = acceptance(args.source, args.library, args.output, args.runtime, args.repeat)
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0 if summary["status"] in ("passed", "build_only") else 1
    except (OSError, ValueError) as error:
        print(json.dumps({"status": "blocked", "error": str(error)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
