"""Redirect skill-owned writes off a frozen system drive.

Unset ``FISH_PROTEUS_WORKDIR`` keeps the defaults: the process temporary
directory, ``<repo>/.work/desktop``, and ``<repo>/.tools/nasm``. When it is
set, staging, native-log directories, the desktop task store, the installer
plugin cache, and portable NASM are created under that folder.

A path the user names (a saved project, a course ``--output``, an export
destination) stays where they put it. Python and Windows tools that this
process does not wrap still use ``TEMP`` and ``TMP``. The DeepSeek Harness
profile stays in Harness's own home.
"""
from __future__ import annotations

import os
from pathlib import Path
import tempfile
import uuid


ENV = "FISH_PROTEUS_WORKDIR"


def configured_workdir() -> Path | None:
    """The raw configured folder, or None when the variable is unset or blank."""
    raw = os.environ.get(ENV, "").strip()
    if not raw:
        return None
    return Path(raw).expanduser()


def resolve_workdir() -> Path | None:
    path = configured_workdir()
    if path is None:
        return None
    return path.resolve()


def write_error(path: str | Path, exc: BaseException, *, purpose: str) -> str:
    return (
        f"{purpose} is not writable: {path}. "
        f"Set {ENV} to a folder on a writable drive (school PCs often freeze C:), "
        f"or set TEMP and TMP to that drive. {type(exc).__name__}: {exc}"
    )


def probe_directory(path: str | Path) -> dict:
    """Check that a directory exists and accepts a file. Does not create it."""
    target = Path(path)
    record = {"path": str(target), "writable": False, "error": None}
    if not target.exists():
        record["error"] = f"directory does not exist: {target}"
        return record
    if not target.is_dir():
        record["error"] = f"not a directory: {target}"
        return record
    probe = target / f".fish-write-{uuid.uuid4().hex}"
    try:
        with probe.open("xb") as stream:
            stream.write(b"")
        probe.unlink()
    except OSError as exc:
        record["error"] = f"{type(exc).__name__}: {exc}"
        try:
            if probe.exists():
                probe.unlink()
        except OSError:
            pass
        return record
    record["writable"] = True
    return record


def require_writable(path: str | Path, *, purpose: str) -> Path:
    """Create the directory if needed, then prove this process can write a file there."""
    target = Path(path).expanduser().resolve()
    try:
        target.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise OSError(write_error(target, exc, purpose=purpose)) from exc
    report = probe_directory(target)
    if not report["writable"]:
        raise OSError(
            f"{purpose} is not writable: {target}. "
            f"Set {ENV} to a folder on a writable drive (school PCs often freeze C:), "
            f"or set TEMP and TMP to that drive. {report['error']}"
        )
    return target


def staging_parent() -> Path:
    """The only parent ``fish-pds-*`` staging directories may be deleted from."""
    root = resolve_workdir()
    if root is not None:
        return root
    return Path(tempfile.gettempdir()).resolve()


def make_temp_directory(prefix: str, *, purpose: str) -> Path:
    """Private directory. Honors ``FISH_PROTEUS_WORKDIR`` when it is set."""
    root = resolve_workdir()
    if root is not None:
        base = require_writable(root, purpose=f"{ENV} for {purpose}")
        try:
            return Path(tempfile.mkdtemp(prefix=prefix, dir=base)).resolve()
        except OSError as exc:
            raise OSError(write_error(base, exc, purpose=purpose)) from exc
    try:
        return Path(tempfile.mkdtemp(prefix=prefix)).resolve()
    except OSError as exc:
        temp = Path(tempfile.gettempdir()).resolve()
        raise OSError(
            f"{purpose} could not be created in the process temporary directory {temp}. "
            f"Set {ENV} to a writable folder, or set TEMP and TMP off the frozen drive. "
            f"{type(exc).__name__}: {exc}"
        ) from exc


def default_nasm_directory() -> Path:
    root = resolve_workdir()
    if root is not None:
        return root / "nasm"
    return Path(__file__).resolve().parent.parent / ".tools" / "nasm"


def nasm_executables() -> list[Path]:
    """Portable NASM candidates. The workdir copy is preferred when configured."""
    repository = Path(__file__).resolve().parent.parent
    roots = []
    work = resolve_workdir()
    if work is not None:
        roots.append(work / "nasm")
    roots.append(repository / ".tools" / "nasm")
    return [root / name for root in roots for name in ("nasm.exe", "nasm")]


def desktop_layout(repository: str | Path) -> dict[str, Path]:
    """Where the installer and the desktop tool keep their own files.

    The default layout stays under the clone. A configured workdir replaces
    only those skill-owned directories.
    """
    repository = Path(repository).resolve()
    work = resolve_workdir()
    if work is None:
        state = repository / ".work" / "desktop"
        return {"confine": repository, "state_root": state, "plugins": state / "plugins",
                "nasm": repository / ".tools" / "nasm"}
    return {"confine": work, "state_root": work / "desktop", "plugins": work / "plugins",
            "nasm": work / "nasm"}


def _usable(path: Path) -> dict:
    """Report a directory, walking up to an existing ancestor when it is not created yet."""
    current = path
    while not current.exists():
        if current.parent == current:
            return probe_directory(path)
        current = current.parent
    report = probe_directory(current)
    if report["writable"]:
        return {"path": str(path), "writable": True, "error": None, "creates_under": str(current)}
    return {"path": str(path), "writable": False,
            "error": report["error"] or f"cannot create {path}", "parent": report}


def work_report(repository: str | Path | None = None) -> dict:
    """Writability of the directories a demo will actually fill."""
    repository = Path(repository or Path(__file__).resolve().parent.parent).resolve()
    layout = desktop_layout(repository)
    configured = configured_workdir()
    temp = Path(tempfile.gettempdir()).resolve()
    staging = layout["confine"] if configured is not None else temp
    return {
        "variable": ENV,
        "configured": str(configured) if configured is not None else None,
        "temp": probe_directory(temp),
        "staging": probe_directory(staging) if (configured is None or staging.exists()) else _usable(staging),
        "desktop_store": _usable(layout["state_root"]),
        "nasm_directory": {"path": str(layout["nasm"]),
                           "note": "Created by tools/bootstrap_nasm.py, not by doctor."},
        "note": (
            f"Unset {ENV} keeps the system temporary directory and <repo>/.work/desktop. "
            "Setting it redirects skill-owned staging, native logs, the desktop task store, "
            "the plugin cache, and portable NASM. A path you pass yourself is not moved. "
            "Python and other Windows tools still honor TEMP and TMP. "
            "The Harness profile stays in its own home (default ~/.dsh); "
            "pass --dsh-home only when Harness is using that same home."
        ),
    }
