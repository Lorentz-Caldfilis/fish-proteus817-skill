"""Read-only teacher import and controlled 8086 course variants."""
from __future__ import annotations

from datetime import datetime, timezone
from fractions import Fraction
from pathlib import Path
import re
import shutil
from typing import Any
import xml.etree.ElementTree as ET
import zipfile

from .artifacts import read_json, sha256_file, write_json


class CourseError(ValueError):
    pass


CASE_DIRECTORIES = {
    "divider": "T8253_v1信号1MHz五分频",
    "cascade": "T8253_v2两个CNT级联",
    "switch": "T8255_v1用K0控制LED全亮或全灭",
}
INPUT_HZ = 1_000_000


def _snapshot(root: Path) -> list[dict[str, Any]]:
    result = []
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise CourseError(f"Symbolic links are not accepted in teacher imports: {path}")
        if path.is_file():
            result.append({"path": path.relative_to(root).as_posix(), "bytes": path.stat().st_size,
                           "sha256": sha256_file(path)})
    return result


def _isolated_destination(destination: Path, protected: Path) -> None:
    if destination == protected or destination.is_relative_to(protected) or protected.is_relative_to(destination):
        raise CourseError("Destination must be separate from the protected original/import tree")


def import_course(source_root: str | Path, destination: str | Path) -> dict[str, Any]:
    source, target = Path(source_root).resolve(), Path(destination).resolve()
    if not source.is_dir():
        raise CourseError(f"Course reference directory not found: {source}")
    _isolated_destination(target, source)
    if target.exists():
        raise CourseError(f"Import destination already exists; choose a new directory: {target}")
    before = _snapshot(source)
    cases = {}
    planned = []
    for case_id, name in CASE_DIRECTORIES.items():
        original = source / name
        projects = list(original.rglob("*.pdsprj")) if original.is_dir() else []
        sources = list(original.rglob("main.asm")) if original.is_dir() else []
        if len(projects) != 1 or len(sources) != 1:
            raise CourseError(f"{case_id} needs exactly one .pdsprj and main.asm under {original}")
        with zipfile.ZipFile(projects[0]) as archive:
            required = {"ROOT.DSN", "ROOT.CDB", "PROJECT.XML", "FIRMWARE/8086.XML"}
            if not required.issubset(archive.namelist()):
                raise CourseError(f"Unexpected Proteus project structure: {projects[0]}")
            firmware = ET.fromstring(archive.read("FIRMWARE/8086.XML"))
            controllers = firmware.findall(".//CONTROLLER")
            if not controllers or any(node.get("TYPE") != "8086" for node in controllers):
                raise CourseError(f"Not an 8086 course project: {projects[0]}")
        copied = target / "cases" / case_id
        cases[case_id] = {
            "directory": str(copied), "original_directory": name,
            "project": str(copied / projects[0].relative_to(original)),
            "source": str(copied / sources[0].relative_to(original)),
            "original_project_sha256": sha256_file(projects[0]),
            "original_source_sha256": sha256_file(sources[0]),
        }
        planned.append((original, copied))
    target.mkdir(parents=True)
    for original, copied in planned:
        shutil.copytree(original, copied)
    if _snapshot(source) != before:
        raise CourseError("Teacher files changed during import; results require a fresh import")
    copied_files = []
    for original, copied in planned:
        if _snapshot(original) != _snapshot(copied):
            raise CourseError(f"Import verification failed for {original.name}")
        for item in _snapshot(copied):
            copied_files.append({**item, "path": f"cases/{next(k for k, v in cases.items() if v['directory'] == str(copied))}/{item['path']}"})
    manifest = {
        "schema": "fish-proteus.course.v1", "status": "imported",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "source_root": str(source), "import_root": str(target),
        "source_file_count": len(before), "source_files": before,
        "imported_files": copied_files, "cases": cases,
        "provenance": "Teacher-provided external reference; no redistribution license asserted",
        "originals_unchanged": True,
    }
    write_json(target / "manifest.json", manifest)
    return manifest


def load_import(imported: str | Path | dict[str, Any]) -> dict[str, Any]:
    if isinstance(imported, dict):
        manifest = imported
    else:
        path = Path(imported)
        manifest = read_json(path / "manifest.json" if path.is_dir() else path)
    if manifest.get("schema") != "fish-proteus.course.v1":
        raise CourseError("Unsupported course manifest")
    return manifest


def verify_import(imported: str | Path | dict[str, Any], check_originals: bool = True) -> dict[str, Any]:
    manifest = load_import(imported)
    imported_root = Path(manifest["import_root"])
    mismatches = []
    for item in manifest["imported_files"]:
        path = imported_root / item["path"]
        if not path.is_file() or path.stat().st_size != item["bytes"] or sha256_file(path) != item["sha256"]:
            mismatches.append(item["path"])
    original_unchanged = None
    if check_originals:
        original_root = Path(manifest["source_root"])
        original_unchanged = original_root.is_dir() and _snapshot(original_root) == manifest["source_files"]
    return {"status": "verified" if not mismatches and original_unchanged is not False else "failed",
            "import_mismatches": mismatches, "originals_unchanged": original_unchanged,
            "imported_file_count": len(manifest["imported_files"])}


def _integer(value: Any, name: str, lower: int, upper: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not lower <= value <= upper:
        raise CourseError(f"{name} must be an integer from {lower} to {upper}")
    return value


def normalize_parameters(case_id: str, **parameters: Any) -> dict[str, Any]:
    if case_id == "divider":
        defaults = {"divisor": 5}
        allowed = set(defaults)
    elif case_id == "cascade":
        defaults = {"divisor0": 1000, "divisor1": 1000}
        allowed = set(defaults)
    elif case_id == "switch":
        defaults = {"on_value": 255, "off_value": 0, "invert": False}
        allowed = set(defaults)
    else:
        raise CourseError(f"Unknown case: {case_id}; choose divider, cascade, or switch")
    unexpected = set(parameters) - allowed
    if unexpected:
        raise CourseError("Unsupported parameters: " + ", ".join(sorted(unexpected)))
    values = {**defaults, **{k: v for k, v in parameters.items() if v is not None}}
    for key, value in values.items():
        if key == "invert":
            if not isinstance(value, bool):
                raise CourseError("invert must be a Boolean")
        elif key.startswith("divisor"):
            # Mode 3 cannot use count 1; count 65536 is encoded as 0.
            _integer(value, key, 2, 65536)
        else:
            _integer(value, key, 0, 255)
    return values


def expected_result(case_id: str, parameters: dict[str, Any]) -> dict[str, Any]:
    if case_id in ("divider", "cascade"):
        counts = [parameters["divisor"]] if case_id == "divider" else [parameters["divisor0"], parameters["divisor1"]]
        total = 1
        for count in counts:
            total *= count
        frequency = Fraction(INPUT_HZ, total)
        return {
            "kind": "frequency", "input_hz": INPUT_HZ, "divisors": counts,
            "divide_by": total, "output_hz": float(frequency),
            "output_hz_exact": str(frequency), "period_seconds": total / INPUT_HZ,
            "mode": 3, "port_control": 0x286,
            "counter_ports": [0x280] if case_id == "divider" else [0x280, 0x282],
            "expected_control_words": [0x36] if case_id == "divider" else [0x36, 0x76],
            "counter0_output_hz": INPUT_HZ / counts[0],
            "count_encoding": [n & 0xFFFF for n in counts],
            "basis": "Calculated from the requested counts and the course circuit's 1 MHz input; not an observed simulation result",
        }
    zero_value, one_value = parameters["on_value"], parameters["off_value"]
    if parameters["invert"]:
        zero_value, one_value = one_value, zero_value
    return {
        "kind": "port-response", "input_port": 0x280, "input_mask": 1,
        "output_port": 0x282, "port_control": 0x286, "control_word": 0x90,
        "port_b_by_input_bit": {"0": zero_value, "1": one_value},
        "samples": [{"input_bit": 1, "expected_port_b": one_value},
                    {"input_bit": 0, "expected_port_b": zero_value},
                    {"input_bit": 1, "expected_port_b": one_value}],
        "basis": "Requested K0/PA0-to-PB mapping; LED voltage/polarity must be observed separately",
    }


def generated_source(case_id: str, parameters: dict[str, Any]) -> str:
    lines = ["; Generated by FishForProteus8.17sp2 for the imported course circuit.",
             "; Target: 8086, one code segment. Port mapping follows the teacher circuit.",
             "; This source is assembled anew; no supplied Debug.exe is reused.",
             "CODE SEGMENT", "ASSUME CS:CODE", "START:"]
    if case_id in ("divider", "cascade"):
        counts = [parameters["divisor"]] if case_id == "divider" else [parameters["divisor0"], parameters["divisor1"]]
        for index, count in enumerate(counts):
            lines.extend((f"    ; CNT{index}: mode 3, divide by {count}", "    MOV DX, 286H",
                          f"    MOV AL, {0x36 + 0x40 * index:02X}H", "    OUT DX, AL",
                          f"    MOV DX, {0x280 + index * 2:03X}H", f"    MOV AX, {count & 0xFFFF}",
                          "    OUT DX, AL", "    MOV AL, AH", "    OUT DX, AL"))
        lines.extend(("N1:", "    JMP N1"))
    else:
        low, high = parameters["on_value"], parameters["off_value"]
        if parameters["invert"]:
            low, high = high, low
        lines.extend(("    MOV DX, 286H", "    MOV AL, 10010000B", "    OUT DX, AL", "AGAIN:",
                      "    MOV DX, 280H", "    IN AL, DX", "    TEST AL, 00000001B", "    JZ INPUT_LOW",
                      f"    MOV AL, {high}", "    JMP WRITE_OUTPUT", "INPUT_LOW:", f"    MOV AL, {low}",
                      "WRITE_OUTPUT:", "    MOV DX, 282H", "    OUT DX, AL", "    JMP AGAIN"))
    lines.extend(("CODE ENDS", "END START", ""))
    return "\n".join(lines)


def _prepared_project(source: Path, target: Path, job_root: Path, executable_relative: str) -> dict[str, Any]:
    edits = []
    with zipfile.ZipFile(source) as archive:
        records = [(info, archive.read(info.filename)) for info in archive.infolist()]
    updated = []
    new_program = executable_relative.replace("/", "\\").encode("ascii")
    for info, data in records:
        if info.filename in ("ROOT.CDB", "ROOT.DSN"):
            matches = list(re.finditer(rb"\{PROGRAM=([^}\r\n]+)\}", data))
            values = [m.group(1) for m in matches if m.group(1).lower().endswith(b".exe")]
            if len(values) != 1:
                raise CourseError(f"Expected one executable PROGRAM property in {info.filename}")
            old = values[0]
            if len(old) != len(new_program):
                raise CourseError(f"Refusing unknown binary record length change in {info.filename}")
            if old != new_program:
                old_record, new_record = b"{PROGRAM=" + old + b"}", b"{PROGRAM=" + new_program + b"}"
                if data.count(old_record) != 1:
                    raise CourseError("PROGRAM property is ambiguous")
                data = data.replace(old_record, new_record)
                edits.append({"entry": info.filename, "property": "PROGRAM", "method": "equal-byte-length replacement",
                              "new": executable_relative})
        if info.filename == "FIRMWARE/8086.XML":
            firmware = ET.fromstring(data)
            firmware.set("BUILDPATH", str(job_root / "8086").replace("\\", "/"))
            for element in firmware.findall(".//FILE"):
                name = element.get("NAME", "")
                if name.lower().endswith("debug/debug.exe"):
                    element.set("NAME", executable_relative)
            data = ET.tostring(firmware, encoding="utf-8", xml_declaration=True)
            edits.append({"entry": info.filename, "property": "BUILDPATH/firmware file", "method": "XML update"})
        updated.append((info, data))
    with zipfile.ZipFile(target, "w") as archive:
        for info, data in updated:
            archive.writestr(info, data)
    with zipfile.ZipFile(target) as archive:
        if archive.testzip() is not None:
            raise CourseError("Generated project archive CRC check failed")
    return {"method": "copy existing circuit; rebase existing firmware references only", "edits": edits}


def generate_variant(imported: str | Path | dict[str, Any], case_id: str,
                     output_dir: str | Path, **parameters: Any) -> dict[str, Any]:
    manifest = load_import(imported)
    values = normalize_parameters(case_id, **parameters)
    check = verify_import(manifest)
    if check["status"] != "verified":
        raise CourseError(f"Originals or imported template changed: {check}")
    output = Path(output_dir).resolve()
    _isolated_destination(output, Path(manifest["import_root"]).resolve())
    _isolated_destination(output, Path(manifest["source_root"]).resolve())
    if output.exists():
        raise CourseError(f"Work directory already exists; choose a new directory: {output}")
    case = manifest["cases"][case_id]
    # The switch project originally stores a 29-byte absolute PROGRAM path.
    # This 29-byte relative replacement preserves the unknown binary format.
    executable_relative = "8086/Debug/generated-8086.exe" if case_id == "switch" else "8086/Debug/Debug.exe"
    output.mkdir(parents=True)
    project = output / Path(case["project"]).name
    source = output / "8086/main.asm"
    executable = output / executable_relative
    source.parent.mkdir(parents=True)
    executable.parent.mkdir(parents=True)
    source.write_text(generated_source(case_id, values), encoding="utf-8", newline="\n")
    preparation = _prepared_project(Path(case["project"]), project, output, executable_relative)
    job = {
        "schema": "fish-proteus.job.v1", "status": "prepared", "case_id": case_id,
        "job_root": str(output), "job_file": str(output / "job.json"),
        "project": str(project), "source": str(source), "executable": str(executable),
        "parameters": values, "expected": expected_result(case_id, values),
        "source_provenance": {"original_root": manifest["source_root"],
                              "original_case": case["original_directory"],
                              "project_sha256": case["original_project_sha256"],
                              "source_sha256": case["original_source_sha256"],
                              "import_manifest": str(Path(manifest["import_root"]) / "manifest.json")},
        "project_preparation": preparation, "runtime": {"status": "not_run"},
    }
    write_json(output / "job.json", job)
    return job
