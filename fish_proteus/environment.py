"""Read-only environment discovery. Never returns credentials or license data."""

from __future__ import annotations

import ctypes
import hashlib
import os
from pathlib import Path
import platform
import shutil
import sys


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def file_version(path: Path) -> str | None:
    if sys.platform != "win32" or not path.is_file():
        return None
    version = ctypes.WinDLL("version", use_last_error=True)
    version.GetFileVersionInfoSizeW.argtypes = [ctypes.c_wchar_p, ctypes.POINTER(ctypes.c_uint)]
    version.GetFileVersionInfoSizeW.restype = ctypes.c_uint
    version.GetFileVersionInfoW.argtypes = [ctypes.c_wchar_p, ctypes.c_uint, ctypes.c_uint, ctypes.c_void_p]
    version.GetFileVersionInfoW.restype = ctypes.c_int
    version.VerQueryValueW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(ctypes.c_uint)]
    version.VerQueryValueW.restype = ctypes.c_int
    ignored = ctypes.c_uint()
    size = version.GetFileVersionInfoSizeW(str(path), ctypes.byref(ignored))
    if not size:
        return None
    data = ctypes.create_string_buffer(size)
    if not version.GetFileVersionInfoW(str(path), 0, size, data):
        return None
    pointer, length = ctypes.c_void_p(), ctypes.c_uint()
    if not version.VerQueryValueW(data, "\\", ctypes.byref(pointer), ctypes.byref(length)) or length.value < 16:
        return None
    fields = ctypes.cast(pointer, ctypes.POINTER(ctypes.c_uint32))
    high, low = fields[2], fields[3]
    return ".".join(map(str, (high >> 16, high & 65535, low >> 16, low & 65535)))


_NOMINAL_TIMEOUTS = {"launch": 45, "wait": 15, "run_for": 60, "run_timed": 120, "ocr": 40, "nasm": 30}


def _native_profile_report(executable: Path | None, *, discovery_error: str | None) -> dict:
    from runtime_adaptation.profile817 import PROFILE817, CompatibilityError, profile_for
    report = {
        "ok": False,
        "expected_id": PROFILE817.identifier,
        "expected_product": "Proteus 8.17 SP2",
        "expected_pds_file_version": "8.17.37159",
        "expected_pds_sha256": PROFILE817.pds_sha256,
        "expected_modules": sorted(PROFILE817.hashes),
        "reason": discovery_error or "Proteus PDS.EXE was not found",
        "note": "Native simulation keeps this exact-file check. doctor only reports it.",
    }
    if executable is None or not executable.is_file():
        return report
    try:
        profile = profile_for(executable)
    except (OSError, CompatibilityError) as exc:
        report["reason"] = f"{type(exc).__name__}: {exc}"
        return report
    report.update(ok=True, reason=None, profile=profile.describe())
    return report


def _timeout_report() -> dict:
    from .timeouts import ENV, timeout_scale
    try:
        scale = timeout_scale()
    except ValueError as exc:
        return {"variable": ENV, "value": None, "error": str(exc),
                "nominal_seconds": dict(_NOMINAL_TIMEOUTS), "effective_seconds": None}
    return {"variable": ENV, "value": scale, "error": None,
            "nominal_seconds": dict(_NOMINAL_TIMEOUTS),
            "effective_seconds": {name: seconds * scale for name, seconds in _NOMINAL_TIMEOUTS.items()},
            "note": "1 keeps the built-in deadlines. Increase it on a slow PC. It does not change simulated seconds."}


def _nasm_path() -> str | None:
    from .workdir import nasm_executables
    nasm = os.environ.get("FISH_PROTEUS_NASM") or shutil.which("nasm")
    if nasm:
        return nasm
    for candidate in nasm_executables():
        if candidate.is_file():
            return str(candidate)
    return None


def discover(proteus: str | None = None) -> dict:
    """Read-only report. Uses ProteusConfig discovery, then the 8.17 hash check."""
    from .config import ProteusConfig
    from .workdir import work_report
    executable = None
    discovery_error = None
    try:
        executable = ProteusConfig.discover(executable=proteus).executable
    except (OSError, ValueError) as exc:
        discovery_error = f"{type(exc).__name__}: {exc}"
        hinted = proteus or os.environ.get("FISH_PROTEUS_EXE")
        if hinted:
            executable = Path(hinted).expanduser()
    present = bool(executable and executable.is_file() and executable.name.upper() == "PDS.EXE")
    modules = []
    if present:
        for name in ("PDS.EXE", "ISIS.DLL", "NETLIST.DLL", "PRIMS.DLL", "WINCORE.DLL", "VSMDEBUG.DLL"):
            path = executable.parent / name
            if path.is_file():
                modules.append({"name": name, "bytes": path.stat().st_size, "sha256": sha256(path),
                                "file_version": file_version(path)})
    return {
        "schema_version": 1,
        "command": "doctor",
        "platform": platform.system(),
        "python": {"executable": sys.executable, "version": platform.python_version()},
        "proteus": {
            "executable": str(executable) if executable is not None else None,
            "present": present,
            "file_version": file_version(executable) if present else None,
            "modules": modules,
            "discovery_error": discovery_error,
            "native_profile": _native_profile_report(executable if present else None, discovery_error=discovery_error),
        },
        "toolchain": {"nasm": _nasm_path(), "builtin_course_subset": True},
        "timeouts": _timeout_report(),
        "work": work_report(),
        "requirements": {
            "interface_language": "English",
            "native_simulation": "Proteus 8.17 SP2 build 8.17.37159, exact PDS.EXE and module hashes",
            "ocr": "powershell.exe -ExecutionPolicy Bypass. A policy that ignores Bypass blocks OCR.",
            "scope_timebase": "Dial box is fixed on the 1380x900 scope window and scales only for a uniform DPI capture.",
        },
        "runtime_status": "not_run",
        "note": "Discovery does not start Proteus. native_profile.ok is the hash check simulation will enforce.",
    }
