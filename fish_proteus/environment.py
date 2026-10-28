"""Read-only environment discovery. Never returns credentials or license data."""

from __future__ import annotations

import ctypes
import hashlib
import os
from pathlib import Path
import platform
import shutil
import sys


DEFAULT_PROTEUS = Path(
    r"C:\Program Files (x86)\Labcenter Electronics\Proteus 8 Professional\BIN\PDS.EXE"
)


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


def discover(proteus: str | None = None) -> dict:
    executable = Path(proteus or os.environ.get("FISH_PROTEUS_EXE", str(DEFAULT_PROTEUS))).expanduser().resolve()
    modules = []
    for name in ("PDS.EXE", "ISIS.DLL", "NETLIST.DLL", "PRIMS.DLL", "WINCORE.DLL", "VSMDEBUG.DLL"):
        path = executable.parent / name
        if path.is_file():
            modules.append({"name": name, "bytes": path.stat().st_size, "sha256": sha256(path), "file_version": file_version(path)})
    portable_nasm = Path(__file__).resolve().parent.parent / ".tools" / "nasm" / "nasm.exe"
    nasm = os.environ.get("FISH_PROTEUS_NASM") or shutil.which("nasm")
    if not nasm and portable_nasm.is_file():
        nasm = str(portable_nasm)
    return {
        "schema_version": 1,
        "command": "doctor",
        "platform": platform.system(),
        "python": {"executable": sys.executable, "version": platform.python_version()},
        "proteus": {"executable": str(executable), "present": executable.is_file(), "file_version": file_version(executable), "modules": modules},
        "toolchain": {"nasm": nasm, "builtin_course_subset": True},
        "runtime_status": "not_run",
        "note": "Discovery does not start Proteus or prove simulation compatibility.",
    }
