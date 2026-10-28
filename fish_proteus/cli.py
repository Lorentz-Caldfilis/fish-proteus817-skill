"""JSON command-line boundary used by DSH skills and human operators."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

from . import __version__


class ArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise ValueError(message)


def engineering_integer(value: str) -> int:
    """Accept ordinary decimal and explicitly prefixed hexadecimal/binary values."""
    text = value.strip()
    base = 0 if text.lstrip("+-").lower().startswith(("0x", "0b", "0o")) else 10
    return int(text, base)


def parser() -> argparse.ArgumentParser:
    result = ArgumentParser(prog="fish-proteus", description="8086 course workflows for Proteus 8.17 SP2")
    result.add_argument("--version", action="version", version=__version__)
    commands = result.add_subparsers(dest="command", required=True)
    doctor = commands.add_parser("doctor", help="Read-only environment report")
    doctor.add_argument("--proteus")
    importer = commands.add_parser("import-course", help="Copy and hash original course materials into a private local library")
    importer.add_argument("--source", required=True)
    importer.add_argument("--destination", required=True)
    prepare = commands.add_parser("prepare", help="Generate an independent job from an imported course template")
    prepare.add_argument("--library", required=True)
    prepare.add_argument("--case", choices=("divider", "cascade", "switch"), required=True)
    prepare.add_argument("--output", required=True)
    prepare.add_argument("--divisor", type=engineering_integer)
    prepare.add_argument("--divisor0", type=engineering_integer)
    prepare.add_argument("--divisor1", type=engineering_integer)
    prepare.add_argument("--on-value", type=engineering_integer, help="Byte value, decimal or prefixed hexadecimal such as 0x33")
    prepare.add_argument("--off-value", type=engineering_integer, help="Byte value, decimal or prefixed hexadecimal such as 0xCC")
    prepare.add_argument("--invert", action="store_true", default=None)
    build = commands.add_parser("build", help="Assemble a fresh 8086 MZ executable")
    build.add_argument("--manifest", required=True)
    build.add_argument("--toolchain", choices=("auto", "builtin", "nasm"), default="auto")
    build.add_argument("--nasm")
    run = commands.add_parser("run", help="Run and observe a job in the installed Proteus")
    run.add_argument("--manifest", required=True)
    run.add_argument("--seconds", type=float)
    run.add_argument("--proteus")
    verify = commands.add_parser("verify", help="Compare recorded runtime observations with the independent expected result")
    verify.add_argument("--manifest", required=True)
    verify.add_argument("--runtime")
    return result


def read_manifest(path: str | Path) -> tuple[Path, dict]:
    manifest_path = Path(path).expanduser().resolve(strict=True)
    with manifest_path.open(encoding="utf-8-sig") as stream:
        manifest = json.load(stream)
    if not isinstance(manifest, dict):
        raise ValueError("Job manifest must be a JSON object")
    return manifest_path, manifest


def execute(args: argparse.Namespace) -> tuple[dict, int]:
    if args.command == "doctor":
        from .environment import discover
        return discover(args.proteus), 0
    if args.command == "import-course":
        from .course import import_course
        imported = import_course(Path(args.source), Path(args.destination))
        return {"schema": imported["schema"], "status": imported["status"], "library": imported["import_root"], "manifest": str(Path(imported["import_root"]) / "manifest.json"), "source_file_count": imported["source_file_count"], "cases": sorted(imported["cases"]), "originals_unchanged": imported["originals_unchanged"]}, 0
    if args.command == "prepare":
        from .course import generate_variant
        parameters = {
            name: value for name in ("divisor", "divisor0", "divisor1", "on_value", "off_value", "invert")
            if (value := getattr(args, name)) is not None
        }
        allowed = {"divider": {"divisor"}, "cascade": {"divisor0", "divisor1"}, "switch": {"on_value", "off_value", "invert"}}[args.case]
        if extra := parameters.keys() - allowed:
            raise ValueError(f"Parameters do not apply to {args.case}: {', '.join(sorted(extra))}")
        return generate_variant(Path(args.library), args.case, Path(args.output), **parameters), 0
    manifest_path, manifest = read_manifest(args.manifest)
    if args.command == "build":
        from .build import build_job
        if args.nasm:
            os.environ["FISH_PROTEUS_NASM"] = str(Path(args.nasm).resolve(strict=True))
        built = build_job(manifest_path, toolchain=args.toolchain)
        report = built["build"]
        report_path = manifest_path.parent / "build.json"
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return report, 0
    if args.command == "run":
        from runtime_adaptation.runner import run_job
        if args.proteus:
            os.environ["FISH_PROTEUS_EXE"] = str(Path(args.proteus).resolve(strict=True))
        if args.seconds is not None and not 0 < args.seconds <= 60:
            raise ValueError("--seconds must be greater than zero and at most 60")
        seconds = args.seconds if args.seconds is not None else (2.2 if manifest["case_id"] == "cascade" else 0.05)
        report = run_job(manifest_path, seconds=seconds)
        status = report.get("status", report.get("runtime_status", "unknown"))
        return report, 0 if status in ("runtime_observed", "runtime_verified", "observed", "completed", "passed") else 3
    if args.command == "verify":
        from .verification import verify_job
        report = verify_job(manifest_path, Path(args.runtime) if args.runtime else None)
        return report, 0 if report["status"] == "passed" else 4
    raise ValueError(f"Unknown command: {args.command}")


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    command = None
    try:
        args = parser().parse_args(argv)
        command = args.command
        payload, code = execute(args)
    except (OSError, ValueError, KeyError, RuntimeError, ImportError) as error:
        payload = {"schema_version": 1, "command": command, "status": "blocked", "error_type": type(error).__name__, "error": str(error)}
        code = 2
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
