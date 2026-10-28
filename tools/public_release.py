"""Build or audit a public source distribution from an explicit file allowlist.

This tool does not change Git history, repository visibility, or publish files.
Install the project's ``dsh`` extra for YAML frontmatter validation.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import sys
from urllib.parse import unquote
import zipfile

REPOSITORY = Path(__file__).resolve().parents[1]
CONFIG = "public-release.json"
MANIFEST = "PUBLIC_MANIFEST.json"
SKILL = "skills/fish-proteus817"
FORBIDDEN = {".git", ".local", ".tools", ".work", ".dsh", ".venv", "evidence", "reference", "work", "deliverables", "__pycache__", "build", "dist"}
TEXT_SUFFIXES = {".py", ".md", ".txt", ".toml", ".json", ".yaml", ".yml", ".mjs", ".ps1", ".c", ".s", ".ld"}
SPECIAL_FILES = {"LICENSE", "LICENSE.upstream", "MANIFEST.in", ".gitignore", ".gitattributes", ".editorconfig"}


def _json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("Expected a JSON object")
    return value


def _encoded(value: dict) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _safe_name(value: str) -> str:
    if not isinstance(value, str) or not value or "\\" in value or ":" in value:
        raise ValueError("Publication paths must be relative POSIX file names")
    path = PurePosixPath(value)
    if path.is_absolute() or path.as_posix() != value or any(p in (".", "..") for p in path.parts):
        raise ValueError("Publication path is not canonical or escapes the source tree")
    if any(p.casefold() in FORBIDDEN or p.endswith(".egg-info") for p in path.parts):
        raise ValueError("Private/development directories are not publishable")
    if path.suffix.casefold() not in TEXT_SUFFIXES and path.name not in SPECIAL_FILES:
        raise ValueError("Only reviewed source and documentation text files are publishable")
    return value


def _config(root: Path) -> dict:
    config = _json(root / CONFIG)
    if config.get("schema") != "fish-proteus.public-source.v1" or not re.fullmatch(r"\d+\.\d+\.\d+", str(config.get("version", ""))):
        raise ValueError("Unsupported publication configuration/version")
    files = config.get("files")
    if not isinstance(files, list) or not files:
        raise ValueError("Publication requires an explicit nonempty file allowlist")
    names = [_safe_name(p) for p in files]
    if len({n.casefold() for n in names}) != len(names):
        raise ValueError("Duplicate or case-colliding publication path")
    required = {CONFIG, "README.md", "README.zh-CN.md", "LICENSE", "THIRD_PARTY_NOTICES.md", f"{SKILL}/SKILL.md", f"{SKILL}/LICENSE.txt"}
    if not required.issubset(names) or MANIFEST in names:
        raise ValueError("Publication must contain bilingual entrypoints and bundled licenses; manifest is generated")
    return config


def _source_bytes(root: Path, name: str) -> bytes:
    path = root / name
    if not path.resolve(strict=True).is_relative_to(root):
        raise ValueError("Publication source escapes the source tree")
    if any(parent.is_symlink() for parent in (path, *path.parents) if parent != root and parent.is_relative_to(root)):
        raise ValueError("Publication does not follow symlinks")
    text = path.read_bytes().decode("utf-8-sig")
    if "\0" in text:
        raise ValueError("NUL bytes are not allowed in a public text distribution")
    return text.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")


def _frontmatter(root: Path, version: str) -> None:
    try:
        import yaml
    except ImportError:
        raise ValueError("Frontmatter validation requires PyYAML; install this project with .[dsh]") from None
    text = (root / SKILL / "SKILL.md").read_text(encoding="utf-8")
    match = re.match(r"\A---\s*\n(.*?)\n---(?:\n|$)", text, re.S)
    if not match:
        raise ValueError("SKILL.md needs YAML frontmatter")
    try:
        data = yaml.safe_load(match[1])
    except yaml.YAMLError:
        raise ValueError("Skill frontmatter is not valid YAML") from None
    if not isinstance(data, dict):
        raise ValueError("Skill frontmatter must be a mapping")
    name = data.get("name")
    if name != Path(SKILL).name or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name) or len(name) > 64:
        raise ValueError("Skill name must match its directory and the Agent Skills naming rules")
    description = data.get("description")
    if not isinstance(description, str) or not 1 <= len(description) <= 1024:
        raise ValueError("Skill description must contain 1-1024 characters")
    compatibility = data.get("compatibility")
    if not isinstance(compatibility, str) or not 1 <= len(compatibility) <= 500:
        raise ValueError("This Windows desktop skill must declare its compatibility requirements")
    metadata = data.get("metadata")
    if not isinstance(metadata, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in metadata.items()):
        raise ValueError("Skill metadata must map strings to strings")
    if data.get("license") != "MIT" or metadata.get("version") != version:
        raise ValueError("Skill license/version differs from publication metadata")
    if (root / "LICENSE").read_bytes() != (root / SKILL / "LICENSE.txt").read_bytes():
        raise ValueError("The standalone skill must carry the same MIT license as the repository")


def check_tree(root: Path) -> dict:
    root = root.resolve(strict=True)
    config = _config(root)
    manifest = _json(root / MANIFEST)
    if manifest.get("version") != config["version"] or manifest.get("schema") != "fish-proteus.public-manifest.v1":
        raise ValueError("Public manifest identity does not match configuration")
    expected = set(config["files"])
    rows = manifest.get("files", [])
    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        raise ValueError("Public manifest files must be a list of records")
    if len(rows) != len(expected) or {r.get("path") for r in rows} != expected:
        raise ValueError("Public manifest does not exactly cover the allowlist")
    for row in rows:
        path = root / _safe_name(row["path"])
        if path.is_symlink() or not path.resolve(strict=True).is_relative_to(root):
            raise ValueError("Public artifact escapes the exported tree")
        data = path.read_bytes()
        if len(data) != row.get("bytes") or _digest(data) != row.get("sha256"):
            raise ValueError("Public file identity changed: " + row["path"])
    actual = {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file() and ".git" not in p.relative_to(root).parts}
    if actual != expected | {MANIFEST}:
        raise ValueError("Public tree contains missing or unlisted files")
    _frontmatter(root, config["version"])
    broken = []
    for name in sorted(expected):
        path = root / name
        if path.suffix == ".py":
            ast.parse(path.read_text(encoding="utf-8"), filename=name)
        if path.suffix != ".md":
            continue
        for link in re.findall(r"\]\(([^)]+)\)", path.read_text(encoding="utf-8")):
            target = unquote(link.strip("<>").split("#", 1)[0])
            if not target or re.match(r"[a-zA-Z][a-zA-Z0-9+.-]*:", target):
                continue
            resolved = (path.parent / target).resolve()
            if not resolved.is_relative_to(root) or not resolved.exists():
                broken.append(name + " -> " + target)
    if broken:
        raise ValueError("Broken public documentation links: " + "; ".join(broken[:8]))
    return {"status": "passed", "version": config["version"], "files": len(expected), "manifest_sha256": _digest((root / MANIFEST).read_bytes())}


def export_public(root: Path, output: Path) -> dict:
    root = root.resolve(strict=True)
    output = output.resolve()
    work = (root / ".work").resolve()
    if output.exists() or output == work or not output.is_relative_to(work) or not work.is_relative_to(root):
        raise ValueError("Choose an unused output directory beneath this checkout's .work")
    config = _config(root)
    # Read and validate every input before creating any output.
    files = {name: _source_bytes(root, name) for name in config["files"]}
    tree = output / "repository"
    tree.mkdir(parents=True)
    rows = []
    for name, data in sorted(files.items()):
        target = tree / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        rows.append({"path": name, "bytes": len(data), "sha256": _digest(data)})
    (tree / MANIFEST).write_bytes(_encoded({"schema": "fish-proteus.public-manifest.v1", "version": config["version"], "files": rows}))
    checked = check_tree(tree)
    archive_path = output / ("fish-proteus817-" + config["version"] + "-source.zip")
    prefix = "fish-proteus817-" + config["version"] + "/"
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name in sorted([*files, MANIFEST]):
            info = zipfile.ZipInfo(prefix + name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            archive.writestr(info, (tree / name).read_bytes())
    archive_hash = _digest(archive_path.read_bytes())
    (output / "SHA256SUMS").write_bytes((archive_hash + "  " + archive_path.name + "\n").encode("utf-8"))
    result = {**checked, "status": "exported", "tree": str(tree), "archive": str(archive_path), "archive_sha256": archive_hash}
    (output / "release.json").write_bytes(_encoded(result))
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--output", type=Path, help="New distribution directory below this checkout's .work")
    mode.add_argument("--check", type=Path, help="Read-only audit of an exported repository tree")
    args = parser.parse_args()
    try:
        result = check_tree(args.check) if args.check else export_public(REPOSITORY, args.output)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, KeyError, TypeError, SyntaxError) as error:
        print(json.dumps({"status": "blocked", "error": str(error)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
