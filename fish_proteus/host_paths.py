"""Host-owned writable paths. Never discover a root from HOME or system TEMP.

This is application preflight, not a sandbox for third-party Windows programs.
"""
from __future__ import annotations

import math
import os
from pathlib import Path, PureWindowsPath
import tempfile


def validate_location(value, *, ascii_only=False, windows=None, environ=None):
    """Pure location check, also used by platform-independent policy tests."""
    env = os.environ if environ is None else environ
    windows = os.name == "nt" if windows is None else windows
    strict = env.get("FISH_PROTEUS_STRICT_NON_SYSTEM_DRIVE", "1")
    if strict not in ("0", "1"):
        raise ValueError("FISH_PROTEUS_STRICT_NON_SYSTEM_DRIVE must be 0 or 1")
    raw = str(value)
    if not raw or "\0" in raw:
        raise ValueError("A writable path is required")
    if ascii_only and (not raw.isascii() or any(ord(char) < 32 for char in raw)):
        raise ValueError("Temporary/LOGFILE paths must be ASCII; set FISH_PROTEUS_TEMP_DIR")
    if windows and strict == "1":
        parsed = PureWindowsPath(raw)
        drive = parsed.drive
        system = (env.get("SystemDrive") or env.get("SYSTEMDRIVE") or "C:").rstrip("\\/")
        if len(system) != 2 or not system[0].isalpha() or system[1] != ":":
            raise ValueError("SystemDrive is invalid; cannot establish a non-system destination")
        if not parsed.is_absolute() or len(drive) != 2 or not drive[0].isalpha() or drive[1] != ":":
            raise ValueError("Writable paths require a local non-system drive")
        if drive.casefold() == system.casefold():
            raise ValueError("Writable path is on the system drive; choose a non-system drive")


def check_path(path, *, ascii_only=False):
    """Resolve links and check before any mkdir/write probe."""
    resolved = Path(path).expanduser().resolve()
    validate_location(resolved, ascii_only=ascii_only)
    return resolved


def writable_directory(path, *, ascii_only=False, probe=True):
    root = check_path(path, ascii_only=ascii_only)
    if probe:
        root.mkdir(parents=True, exist_ok=True)
        # Recheck junction/symlink resolution before probing the created root.
        root = check_path(root, ascii_only=ascii_only)
        descriptor, name = tempfile.mkstemp(prefix=".fish-write-probe-", dir=root)
        try:
            os.write(descriptor, b"fish")
        finally:
            os.close(descriptor)
            Path(name).unlink()
    return root


def writable_file(path):
    target = check_path(path)
    writable_directory(target.parent)
    return target


def temp_root(anchor=None, *, configured=None, probe=True):
    """Environment > saved configuration > owned anchor/.work; fail closed.

    A bad explicit setting is an error, never permission to try another root.
    Chinese repository names remain supported by selecting an ASCII temp root.
    """
    selected = os.environ.get("FISH_PROTEUS_TEMP_DIR") or configured
    if selected is None:
        if anchor is None:
            raise ValueError("No temporary root; set FISH_PROTEUS_TEMP_DIR to a writable ASCII non-system directory")
        selected = Path(anchor) / ".work" / "fish-proteus-temp"
    if not Path(selected).is_absolute():
        raise ValueError("FISH_PROTEUS_TEMP_DIR must be absolute")
    return writable_directory(selected, ascii_only=True, probe=probe)


def child_environment(anchor=None, *, base=None, configured=None):
    env = dict(os.environ if base is None else base)
    root = str(temp_root(anchor, configured=configured))
    env.update(TEMP=root, TMP=root, FISH_PROTEUS_TEMP_DIR=root, PYTHONDONTWRITEBYTECODE="1")
    return env


def timeout_scale():
    value = float(os.environ.get("FISH_PROTEUS_TIMEOUT_SCALE", "1"))
    if not math.isfinite(value) or not 1 <= value <= 20:
        raise ValueError("FISH_PROTEUS_TIMEOUT_SCALE must be finite, between 1 and 20")
    return value
