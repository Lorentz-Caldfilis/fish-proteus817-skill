"""Real 8086 assembly and MZ linking for the course's one-segment programs.

NASM is preferred when available. The offline encoder intentionally supports a
small documented instruction subset; an unknown directive/instruction is an
error, never silently omitted. Neither backend runs the generated executable.
"""
from __future__ import annotations

import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from typing import Any

from .artifacts import describe_mz, mz_image, read_json, sha256_file, write_json


class BuildError(ValueError):
    pass


_REG8 = {name: i for i, name in enumerate(("AL", "CL", "DL", "BL", "AH", "CH", "DH", "BH"))}
_REG16 = {name: i for i, name in enumerate(("AX", "CX", "DX", "BX", "SP", "BP", "SI", "DI"))}
_JCC = {"JZ": 0x74, "JE": 0x74, "JNZ": 0x75, "JNE": 0x75, "JC": 0x72, "JNC": 0x73}
_ACC_IMMEDIATE = {"ADD": (0x04, 0x05), "OR": (0x0C, 0x0D), "AND": (0x24, 0x25),
                  "SUB": (0x2C, 0x2D), "XOR": (0x34, 0x35), "CMP": (0x3C, 0x3D), "TEST": (0xA8, 0xA9)}


def discover_nasm(explicit: str | Path | None = None) -> Path | None:
    candidates = [explicit, os.environ.get("FISH_PROTEUS_NASM"), shutil.which("nasm")]
    repository = Path(__file__).resolve().parent.parent
    candidates.extend((repository / ".tools/nasm/nasm.exe", repository / ".tools/nasm/nasm"))
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return Path(candidate).resolve()
    if explicit:
        raise BuildError(f"NASM executable not found: {explicit}")
    return None


def _decode_source(data: bytes) -> str:
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return data.decode("gb18030")


def _number(token: str) -> int:
    text = token.strip().upper()
    try:
        if text.startswith("0X"):
            return int(text, 16)
        if re.fullmatch(r"[0-9][0-9A-F]*H", text):
            return int(text[:-1], 16)
        if text.endswith("B") and re.fullmatch(r"[01]+B", text):
            return int(text[:-1], 2)
        if text.endswith("D"):
            return int(text[:-1], 10)
        return int(text, 10)
    except ValueError as error:
        raise BuildError(f"Unsupported immediate: {token}") from error


def _immediate(token: str, width: int) -> bytes:
    value = _number(token)
    if not -(1 << (width - 1)) <= value < 1 << width:
        raise BuildError(f"Immediate {token} does not fit {width} bits")
    return (value & ((1 << width) - 1)).to_bytes(width // 8, "little")


def _parse(source: str) -> tuple[list[tuple[int, str | None, str, list[str]]], str]:
    instructions = []
    entry = "START"
    for line_number, raw in enumerate(source.splitlines(), 1):
        line = raw.split(";", 1)[0].strip()
        if not line:
            continue
        upper = line.upper()
        if re.fullmatch(r"[A-Z_]\w*\s+SEGMENT(?:\s+PUBLIC\s+'CODE')?", upper) or re.fullmatch(r"[A-Z_]\w*\s+ENDS", upper):
            continue
        if re.fullmatch(r"ASSUME\s+CS\s*:\s*[A-Z_]\w*", upper):
            continue
        if upper.startswith("END "):
            entry = upper.split()[1]
            continue
        if upper in ("BITS 16", "CPU 8086", "ORG 0"):
            continue
        label = None
        if ":" in line:
            label, line = line.split(":", 1)
            label = label.strip().upper()
            if not re.fullmatch(r"[A-Z_]\w*", label):
                raise BuildError(f"Line {line_number}: invalid label")
            line = line.strip()
        if not line:
            instructions.append((line_number, label, "", []))
            continue
        pieces = line.split(None, 1)
        operation = pieces[0].upper()
        arguments = [v.strip().upper() for v in pieces[1].split(",")] if len(pieces) == 2 else []
        instructions.append((line_number, label, operation, arguments))
    return instructions, entry


def _encode(operation: str, args: list[str], labels: dict[str, int], offset: int, resolving: bool) -> bytes:
    if not operation:
        return b""
    if operation == "MOV" and len(args) == 2:
        destination, value = args
        if destination in _REG8:
            if value in _REG8:
                return bytes((0x8A, 0xC0 | (_REG8[destination] << 3) | _REG8[value]))
            return bytes((0xB0 + _REG8[destination],)) + _immediate(value, 8)
        if destination in _REG16:
            if value in _REG16:
                return bytes((0x8B, 0xC0 | (_REG16[destination] << 3) | _REG16[value]))
            return bytes((0xB8 + _REG16[destination],)) + _immediate(value, 16)
    if operation in ("IN", "OUT") and len(args) == 2:
        table = {("IN", "AL", "DX"): 0xEC, ("IN", "AX", "DX"): 0xED,
                 ("OUT", "DX", "AL"): 0xEE, ("OUT", "DX", "AX"): 0xEF}
        key = (operation, *args)
        if key in table:
            return bytes((table[key],))
    if operation in _ACC_IMMEDIATE and len(args) == 2 and args[0] in ("AL", "AX"):
        width = 8 if args[0] == "AL" else 16
        opcode = _ACC_IMMEDIATE[operation][width == 16]
        return bytes((opcode,)) + _immediate(args[1], width)
    if operation in ("JMP", *_JCC) and len(args) == 1:
        target = args[0]
        if not re.fullmatch(r"[A-Z_]\w*", target):
            raise BuildError("Branches require a plain named label")
        if resolving and target not in labels:
            raise BuildError(f"Unknown branch label: {target}")
        relative = labels.get(target, offset + 2) - offset - 2
        if resolving and not -128 <= relative <= 127:
            raise BuildError("Offline backend only supports signed 8-bit branches; use NASM")
        return bytes((0xEB if operation == "JMP" else _JCC[operation], relative & 0xFF))
    if operation in ("NOP", "HLT", "CLI", "STI") and not args:
        return bytes(({"NOP": 0x90, "HLT": 0xF4, "CLI": 0xFA, "STI": 0xFB}[operation],))
    raise BuildError(f"Unsupported offline instruction or operands: {operation} {','.join(args)}")


def assemble_builtin(source: str) -> tuple[bytes, int]:
    parsed, entry = _parse(source)
    labels: dict[str, int] = {}
    offset = 0
    for line_number, label, operation, arguments in parsed:
        if label:
            if label in labels:
                raise BuildError(f"Line {line_number}: duplicate label {label}")
            labels[label] = offset
        try:
            offset += len(_encode(operation, arguments, labels, offset, False))
        except BuildError as error:
            raise BuildError(f"Line {line_number}: {error}") from error
    if entry not in labels:
        raise BuildError(f"Entry label not found: {entry}")
    result = bytearray()
    for line_number, _, operation, arguments in parsed:
        try:
            result.extend(_encode(operation, arguments, labels, len(result), True))
        except BuildError as error:
            raise BuildError(f"Line {line_number}: {error}") from error
    return bytes(result), labels[entry]


def _to_nasm(source: str) -> str:
    # Validate the MASM compatibility envelope. Native NASM syntax can instead
    # be provided as a .nasm file, with mandatory CPU 8086/BITS 16 prepended.
    parsed, entry = _parse(source)
    lines = ["CPU 8086", "BITS 16", "ORG 0"]
    for _, label, operation, arguments in parsed:
        if label:
            lines.append(label + ":")
        if operation:
            if operation in ("CPU", "BITS", "ORG", "SECTION", "SEGMENT", "ABSOLUTE", "INCBIN") or operation.startswith(("%", "[")):
                raise BuildError(f"Directive {operation} is outside the one-segment 8086 build contract")
            converted = []
            for value in arguments:
                if value in _REG8 or value in _REG16:
                    pass
                elif re.fullmatch(r"[0-9][0-9A-F]*H", value):
                    value = "0x" + value[:-1]
                elif re.fullmatch(r"[01]+B", value):
                    value = "0b" + value[:-1]
                converted.append(value)
            lines.append("    " + operation + " " + ", ".join(converted))
    # These course programs enter at START, offset zero. Entry elsewhere is
    # supported by the builtin backend but intentionally not guessed for NASM.
    nonempty = next((label for _, label, op, _ in parsed if label or op), None)
    if entry != nonempty:
        raise BuildError("NASM/MASM translation requires the entry label at offset zero")
    return "\n".join(lines) + "\n"


def _native_nasm_source(source: str) -> str:
    for raw in source.splitlines():
        line = raw.split(";", 1)[0].strip().strip("[]").strip().upper()
        if not line:
            continue
        operation = line.split(None, 1)[0]
        if operation in ("CPU", "BITS", "ORG"):
            if line not in ("CPU 8086", "BITS 16", "ORG 0"):
                raise BuildError("Native NASM source cannot override CPU 8086, BITS 16, or ORG 0")
        if operation in ("SECTION", "SEGMENT", "ABSOLUTE", "INCBIN") or operation.startswith("%"):
            raise BuildError("Native NASM input is limited to one flat segment without external includes")
    return "CPU 8086\nBITS 16\nORG 0\n" + source


def build_program(asm_path: str | Path, output_exe: str | Path, toolchain: str = "auto",
                  nasm: str | Path | None = None, overwrite: bool = False,
                  timeout: float = 30.0) -> dict[str, Any]:
    source_path, target = Path(asm_path).resolve(), Path(output_exe).resolve()
    if not source_path.is_file():
        raise BuildError(f"Source does not exist: {source_path}")
    if target == source_path:
        raise BuildError("Source and executable paths must differ")
    if target.exists() and not overwrite:
        raise BuildError(f"Refusing to overwrite existing executable: {target}")
    if toolchain not in ("auto", "builtin", "nasm"):
        raise BuildError("toolchain must be auto, builtin, or nasm")
    target.parent.mkdir(parents=True, exist_ok=True)
    source_data = source_path.read_bytes()
    source = _decode_source(source_data)
    chosen_nasm = discover_nasm(nasm) if toolchain != "builtin" else None
    if toolchain == "nasm" and chosen_nasm is None:
        raise BuildError("NASM not found; set FISH_PROTEUS_NASM or run tools/bootstrap_nasm.py")
    result: dict[str, Any] = {
        "source": str(source_path), "source_sha256": sha256_file(source_path),
        "executable": str(target), "host_execution": False,
        "architecture": "8086", "debug_symbols": False,
    }
    if chosen_nasm:
        with tempfile.TemporaryDirectory(prefix="fish-nasm-", dir=target.parent) as temporary:
            work = Path(temporary)
            if not work.resolve().is_relative_to(target.parent.resolve()):
                raise BuildError("Unexpected temporary build directory")
            translated = work / "program.asm"
            if source_path.suffix.lower() == ".nasm":
                translated.write_text(_native_nasm_source(source), encoding="utf-8")
            else:
                translated.write_text(_to_nasm(source), encoding="utf-8")
            flat, listing = work / "program.bin", work / "program.lst"
            command = [str(chosen_nasm), "-f", "bin", "-o", str(flat), "-l", str(listing), str(translated)]
            try:
                completed = subprocess.run(command, shell=False, capture_output=True, text=True, errors="replace", timeout=timeout)
                version = subprocess.run([str(chosen_nasm), "-v"], shell=False, capture_output=True, text=True, errors="replace", timeout=timeout)
            except (subprocess.TimeoutExpired, OSError) as error:
                raise BuildError(f"NASM could not complete: {error}") from error
            if completed.returncode or not flat.is_file():
                raise BuildError(f"NASM failed ({completed.returncode}): {completed.stderr.strip()}")
            code, entry = flat.read_bytes(), 0
            target.with_suffix(".nasm.asm").write_text(translated.read_text(encoding="utf-8"), encoding="utf-8")
            target.with_suffix(".lst").write_text(listing.read_text(encoding="utf-8", errors="replace"), encoding="utf-8")
            result.update(toolchain="nasm", tool_version=version.stdout.strip(), tool_path=str(chosen_nasm),
                          command=[str(chosen_nasm), "-f", "bin", "<generated-source>"],
                          stdout=completed.stdout, stderr=completed.stderr, returncode=completed.returncode)
    else:
        code, entry = assemble_builtin(source)
        result.update(toolchain="builtin-8086-subset", tool_version="1", returncode=0,
                      limitations="Single code segment; register/immediate MOV, DX-port IN/OUT, accumulator arithmetic/TEST, short branches, NOP/HLT/CLI/STI only")
    image = mz_image(code, entry)
    # Only replace the target once the complete image has been generated.
    with tempfile.NamedTemporaryFile(prefix=".fish-mz-", dir=target.parent, delete=False) as output:
        temporary_name = output.name
        output.write(image)
    try:
        if target.exists() and not overwrite:
            raise BuildError(f"Output appeared during build: {target}")
        os.replace(temporary_name, target)
    finally:
        if os.path.exists(temporary_name):
            os.unlink(temporary_name)
    result.update(status="built", machine_code_hex=code.hex(), artifact=describe_mz(target))
    write_json(target.with_suffix(".build.json"), result)
    return result


def build_job(job: str | Path | dict[str, Any], **options: Any) -> dict[str, Any]:
    if isinstance(job, dict):
        manifest = dict(job)
        job_path = Path(manifest["job_file"]) if manifest.get("job_file") else None
    else:
        job_path = Path(job)
        if job_path.is_dir():
            job_path /= "job.json"
        manifest = read_json(job_path)
    root = Path(manifest.get("job_root", Path(manifest["project"]).parent)).resolve()
    for field in ("project", "source", "executable"):
        if not Path(manifest[field]).resolve().is_relative_to(root):
            raise BuildError(f"Job {field} escapes its work directory")
    source_root = manifest.get("source_provenance", {}).get("original_root")
    if source_root and root.is_relative_to(Path(source_root).resolve()):
        raise BuildError("Refusing to build inside teacher originals")
    options.setdefault("overwrite", True)
    built = build_program(manifest["source"], manifest["executable"], **options)
    manifest.update(status="built", build=built)
    if job_path:
        write_json(job_path, manifest)
    return manifest
