"""Install this repository's skill into one project's DSH discovery directory."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import sys


REPOSITORY = Path(__file__).resolve().parents[1]


def _inventory(directory: Path) -> dict[str, str]:
    return {
        str(path.relative_to(directory)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(directory.rglob("*"))
        if path.is_file()
    }


def install_skill(workspace: Path, *, update: bool = False) -> dict:
    workspace = workspace.expanduser().resolve(strict=True)
    if not workspace.is_dir():
        raise ValueError("The workspace must be an existing directory.")
    if not (workspace / ".git").exists():
        containing_git = next((p for p in workspace.parents if (p / ".git").exists()), None)
        if containing_git is not None:
            raise ValueError(
                f"DSH would discover skills from the containing Git root {containing_git}; "
                "select that root explicitly instead of writing outside the requested workspace."
            )
    source = REPOSITORY / "skills" / "fish-proteus817"
    destination = workspace / ".dsh" / "skills" / "fish-proteus817"
    if workspace not in destination.resolve().parents:
        raise ValueError("The skill destination escapes the requested workspace.")
    expected = _inventory(source)
    if not expected or "SKILL.md" not in expected:
        raise ValueError("The repository skill is incomplete.")
    backup = None
    if destination.exists():
        present = _inventory(destination)
        if present == expected:
            return {"status": "unchanged", "skill": str(destination), "files": expected}
        if not update:
            raise ValueError("A different skill already exists; --update preserves a backup first.")
        unknown = set(present) - set(expected)
        if unknown:
            raise ValueError("The installed skill contains extra files; refusing to overwrite it.")
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        backup = workspace / ".work" / "skill-install-backups" / stamp / destination.name
        if workspace not in backup.resolve().parents:
            raise ValueError("The backup escapes the requested workspace.")
        shutil.copytree(destination, backup)
    shutil.copytree(source, destination, dirs_exist_ok=destination.exists())
    if _inventory(destination) != expected:
        raise ValueError("The installed skill failed its content-hash check.")
    return {
        "status": "updated" if backup else "installed",
        "skill": str(destination),
        "backup": str(backup) if backup else None,
        "files": expected,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=REPOSITORY)
    parser.add_argument("--update", action="store_true", help="Back up a differing installation before updating.")
    args = parser.parse_args()
    try:
        print(json.dumps(install_skill(args.workspace, update=args.update), ensure_ascii=False, indent=2))
    except (OSError, ValueError) as exc:
        print(json.dumps({"status": "error", "message": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    raise SystemExit(main())
