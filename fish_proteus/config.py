"""Discover installed resources without launching or reconfiguring Proteus."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import shutil


def _resolved(path: str | Path) -> Path:
    return Path(path).expanduser().resolve()


@dataclass(frozen=True)
class ProteusConfig:
    """Explicit, immutable resource paths; all installed inputs remain read-only.

    Discovery precedence is explicit argument, FISH_PROTEUS_* environment,
    then the installed executable and its DATA directory. Discovery does not
    assert that any library device can be imported or simulated.
    """

    executable: Path
    library_root: Path
    samples_root: Path
    template_project: Path

    def __post_init__(self):
        for name in ("executable", "library_root", "samples_root", "template_project"):
            object.__setattr__(self, name, _resolved(getattr(self, name)))

    @classmethod
    def discover(cls, *, executable=None, library_root=None, samples_root=None,
                 template_project=None) -> "ProteusConfig":
        executable = executable or os.environ.get("FISH_PROTEUS_EXE") or shutil.which("PDS.EXE")
        if executable is None:
            roots = [os.environ.get("ProgramFiles(x86)"), os.environ.get("ProgramFiles")]
            candidates = [Path(root) / "Labcenter Electronics" / "Proteus 8 Professional" / "BIN" / "PDS.EXE"
                          for root in roots if root]
            executable = next((path for path in candidates if path.is_file()), None)
        if executable is None:
            raise FileNotFoundError("Proteus PDS.EXE not found; pass executable or set FISH_PROTEUS_EXE")
        executable = _resolved(executable)
        data = executable.parent.parent / "DATA"
        library_root = library_root or os.environ.get("FISH_PROTEUS_LIBRARY") or data / "LIBRARY"
        samples_root = samples_root or os.environ.get("FISH_PROTEUS_SAMPLES") or data / "SAMPLES"
        template_project = (template_project or os.environ.get("FISH_PROTEUS_TEMPLATE") or
                            Path(samples_root) / "Graph Based Simulation" / "Rescap.pdsprj")
        return cls(executable, library_root, samples_root, template_project)

    def require(self, *resources: str) -> None:
        for name in resources:
            if name not in ("executable", "library_root", "samples_root", "template_project"):
                raise ValueError(f"Unknown Proteus resource: {name}")
            path = getattr(self, name)
            exists = path.is_dir() if name.endswith("_root") else path.is_file()
            if not exists:
                raise FileNotFoundError(f"Missing Proteus {name}: {path}")

    def describe(self, *, fingerprint=False) -> dict:
        result = {name: {"path": str(getattr(self, name)), "exists": getattr(self, name).exists()}
                  for name in ("executable", "library_root", "samples_root", "template_project")}
        if fingerprint and self.executable.is_file():
            result["executable"]["sha256"] = hashlib.sha256(self.executable.read_bytes()).hexdigest()
        return result

    def check_destination(self, destination: str | Path) -> Path:
        path = _resolved(destination)
        protected = (self.executable.parent.parent, self.library_root, self.samples_root)
        if any(path == root or root in path.parents for root in protected):
            raise ValueError("Generated projects must be saved outside installed Proteus resources")
        return path
