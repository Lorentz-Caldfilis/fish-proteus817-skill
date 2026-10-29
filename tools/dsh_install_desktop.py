"""Install the Proteus tool once into the user's existing DSH desktop profile.

Only a marked local-plugin entry and this skill are managed. Other profile
bytes, model settings, account data and application archives are left alone.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import uuid


REPOSITORY = Path(__file__).resolve().parents[1]
PLUGIN_ID = "fish-proteus-desktop-tool"
BOOTSTRAP_ID = PLUGIN_ID + "-bootstrap-v1"
BEGIN = b"# >>> fish-proteus817 desktop integration >>>"
END = b"# <<< fish-proteus817 desktop integration <<<"
SCHEMA = "fish-proteus.desktop-install.v1"


def _below(path: Path, root: Path) -> Path:
    path, root = path.resolve(), root.resolve()
    if path == root or root not in path.parents:
        raise ValueError(f"Installer target escapes its selected root: {path}")
    return path


def _inventory(directory: Path) -> dict[str, str]:
    result = {}
    for path in sorted(directory.rglob("*")):
        if path.is_symlink():
            raise ValueError(f"Skill symlinks are not managed: {path}")
        if path.is_file():
            result[path.relative_to(directory).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def _read(path: Path) -> bytes | None:
    return path.read_bytes() if path.exists() else None


def _atomic_write(path: Path, data: bytes, *, expected: bytes | None) -> None:
    """Reject concurrent edits instead of overwriting a newer profile."""
    if _read(path) != expected:
        raise ValueError(f"File changed while preparing installation: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.fish-{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("xb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        if _read(path) != expected:
            raise ValueError(f"File changed while preparing installation: {path}")
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _bounds(content: bytes) -> tuple[int, int] | None:
    if BEGIN not in content and END not in content:
        return None
    if content.count(BEGIN) != 1 or content.count(END) != 1:
        raise ValueError("The managed desktop block has missing or duplicate markers")
    start = content.index(BEGIN)
    end = content.index(END)
    finish = end + len(END)
    if end < start or (start and content[start - 1:start] != b"\n"):
        raise ValueError("The managed desktop block is malformed")
    if content[finish:finish + 2] == b"\r\n":
        finish += 2
    elif content[finish:finish + 1] == b"\n":
        finish += 1
    elif finish != len(content):
        raise ValueError("The managed desktop block has an invalid end marker")
    return start, finish


def _block(config: dict, newline: bytes, *, plugin_id: str = PLUGIN_ID) -> bytes:
    # JSON scalar strings are valid YAML and preserve Windows paths literally.
    lines = [BEGIN.decode(), "- insert:", f"  - id: {plugin_id}",
             "    name: " + json.dumps(config.pop("plugin"), ensure_ascii=False), "    config:"]
    lines += [f"      {key}: " + json.dumps(value, ensure_ascii=False) for key, value in config.items()]
    lines.append(END.decode())
    return newline.join(line.encode("utf-8") for line in lines) + newline


def _convert_empty_flow_profile(content: bytes) -> bytes | None:
    """Make an empty flow-list root extensible without reserializing YAML.

    Only empty flow documents are converted. Keep their comments and whitespace
    byte-for-byte, removing the two root brackets and document/directive syntax.
    Ordinary block profiles (including Cordis !!js tags) are never constructed
    or dumped by this function.
    """
    text = content.decode("utf-8-sig")
    first = None
    for line in text.splitlines():
        stripped = line.lstrip(" \t")
        if not stripped or stripped.startswith(("#", "%", "...")):
            continue
        if stripped.startswith("---") and (len(stripped) == 3 or stripped[3] in " \t#"):
            stripped = stripped[3:].lstrip(" \t")
            if not stripped or stripped.startswith("#"):
                continue
        first = stripped
        break
    if first is None or not first.startswith("["):
        return None
    import yaml
    try:
        node = yaml.compose(text, Loader=yaml.SafeLoader)
    except yaml.YAMLError as exc:
        raise ValueError("The flow-style desktop profile is not one valid YAML document") from exc
    if not isinstance(node, yaml.SequenceNode) or not node.flow_style or node.value:
        raise ValueError("A non-empty flow-style desktop profile must be converted to a block list before setup")
    start, end = node.start_mark.index, node.end_mark.index
    if text[start:start + 1] != "[" or text[end - 1:end] != "]":
        raise ValueError("A tagged empty-flow desktop profile needs explicit conversion before setup")
    removed = {start, end - 1}
    for match in re.finditer(r"(?m)^[ \t]*(---|\.\.\.)(?=[ \t\r\n#]|$)", text):
        removed.update(range(match.start(1), match.end(1)))
    for match in re.finditer(r"(?m)^%[^\r\n]*", text):
        comment = re.search(r"[ \t]+#", match.group())
        finish = match.start() + comment.end() - 1 if comment else match.end()
        removed.update(range(match.start(), finish))
    converted = "".join(character for index, character in enumerate(text) if index not in removed).encode("utf-8")
    if content.startswith(b"\xef\xbb\xbf"):
        converted = b"\xef\xbb\xbf" + converted
    return converted


def _dsh_candidates() -> list[Path]:
    candidates = []
    if os.environ.get("DSH_DESKTOP_EXE"):
        candidates.append(Path(os.environ["DSH_DESKTOP_EXE"]))
    for key in ("LOCALAPPDATA", "ProgramFiles", "ProgramFiles(x86)"):
        if os.environ.get(key):
            base = Path(os.environ[key])
            for suffix in ("Programs/DeepSeek Harness/DeepSeek Harness.exe", "DeepSeek Harness/DeepSeek Harness.exe"):
                candidates.append(base / suffix)
    if sys.platform == "win32":
        import winreg
        for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
            for registry in (r"Software\Microsoft\Windows\CurrentVersion\Uninstall",
                             r"Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"):
                try:
                    with winreg.OpenKey(hive, registry) as parent:
                        for index in range(winreg.QueryInfoKey(parent)[0]):
                            try:
                                with winreg.OpenKey(parent, winreg.EnumKey(parent, index)) as key:
                                    name = winreg.QueryValueEx(key, "DisplayName")[0]
                                    if "deepseek harness" not in str(name).lower():
                                        continue
                                    for field in ("InstallLocation", "DisplayIcon"):
                                        try:
                                            value = str(winreg.QueryValueEx(key, field)[0])
                                            if field == "InstallLocation":
                                                candidates.append(Path(value) / "DeepSeek Harness.exe")
                                            else:
                                                match = re.match(r'^"?(.+?\.exe)(?:"|,|$)', value, re.I)
                                                if match:
                                                    candidates.append(Path(match.group(1)))
                                        except OSError:
                                            pass
                            except OSError:
                                pass
                except OSError:
                    pass
        # Read executable paths only; command lines can contain unrelated data.
        try:
            query = ("[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false); "
                     "Get-CimInstance Win32_Process -Filter \"Name = 'DeepSeek Harness.exe'\" "
                     "| Select-Object -ExpandProperty ExecutablePath")
            result = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", query],
                                    capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=15,
                                    creationflags=subprocess.CREATE_NO_WINDOW)
            candidates += [Path(line.strip()) for line in result.stdout.splitlines() if line.strip()]
        except (OSError, subprocess.SubprocessError):
            pass
    return candidates


def find_dsh(executable: Path | None = None) -> Path:
    candidates = [executable] if executable else _dsh_candidates()
    for candidate in candidates:
        path = candidate.expanduser().resolve()
        if path.is_file() and (path.parent / "resources" / "app.asar").is_file():
            return path
    raise FileNotFoundError("DSH desktop not found; pass --dsh-executable to its existing executable once")


def _runtime_diagnostics(repository: Path) -> dict:
    errors = []
    if sys.version_info < (3, 10):
        errors.append("Python 3.10 or newer is required")
    has_yaml = importlib.util.find_spec("yaml") is not None
    if not has_yaml:
        errors.append(f'Install this interpreter dependency once: "{sys.executable}" -m pip install "PyYAML>=6,<7"')
    resources = None
    try:
        sys.path.insert(0, str(repository))
        from fish_proteus.config import ProteusConfig
        config = ProteusConfig.discover()
        resources = config.describe()
        config.require("executable", "library_root", "samples_root", "template_project")
    except (OSError, ValueError, ImportError) as exc:
        errors.append(str(exc))
    finally:
        if sys.path and sys.path[0] == str(repository):
            sys.path.pop(0)
    return {"python": str(Path(sys.executable).resolve()), "pyyaml": has_yaml,
            "proteus": resources, "errors": errors}


def _json_bytes(value: dict) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _source_identity(repository: Path) -> dict:
    """Identify the reviewed implementation closure, never local runtime data.

    New desktop entry points are listed explicitly until the public allowlist is
    updated. The remaining backend/runtime/skill closure follows that allowlist.
    A changed identity changes the Cordis config, so reinstall can reconcile a
    loaded external plugin even when its source path remains the same.
    """
    explicit = {
        "tools/dsh_desktop_tool.mjs", "tools/dsh_design_tool.mjs", "tools/desktop_gate.py",
        "fish_proteus/desktop.py", "skills/fish-proteus817/SKILL.md",
        "skills/fish-proteus817/references/desktop-workflow.md",
    }
    allowlist = repository / "public-release.json"
    reviewed = json.loads(allowlist.read_text(encoding="utf-8")).get("files", []) if allowlist.exists() else []
    if not isinstance(reviewed, list) or not all(isinstance(name, str) for name in reviewed):
        raise ValueError("The public implementation allowlist must contain file paths")
    selected = set(explicit)
    for name in reviewed:
        if ((name.startswith("fish_proteus/") and name.endswith(".py"))
                or (name.startswith("runtime_adaptation/") and name.endswith((".py", ".ps1")))
                or name.startswith("skills/fish-proteus817/")):
            selected.add(name)
    inventory = {}
    for name in sorted(selected):
        if PurePosixPath(name).is_absolute() or "\\" in name or ".." in PurePosixPath(name).parts:
            raise ValueError("Implementation path escapes its reviewed source location")
        path = _below(repository / name, repository)
        if path.relative_to(repository).as_posix() != name:
            raise ValueError("Implementation path escapes its reviewed source location through a link")
        if path.is_file():
            inventory[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    identity = hashlib.sha256(json.dumps(inventory, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return {"sha256": identity, "files": inventory}


def _project_skill_diagnostics(repository: Path, expected: dict[str, str]) -> dict:
    path = _below(repository / ".dsh" / "skills" / "fish-proteus817", repository)
    present = _inventory(path) if path.is_dir() else None
    differs = present is not None and present != expected
    return {"path": str(path), "exists": present is not None,
            "matches_source": present == expected if present is not None else None,
            "project_skill_update_required": differs,
            "unknown_files": sorted(set(present or {}) - set(expected)),
            "update_command": (f'"{sys.executable}" "{repository / "tools" / "dsh_install_skill.py"}" --update'
                               if differs else None)}


def _plugin_cache_plan(repository: Path, identity: dict) -> dict:
    """ESM source URLs must change when the reviewed implementation changes."""
    directory = _below(repository / ".work" / "desktop" / "plugins" / identity["sha256"], repository)
    files = {name: identity["files"].get("tools/" + name)
             for name in ("dsh_desktop_tool.mjs", "dsh_design_tool.mjs")}
    ready = False
    if directory.exists():
        if not directory.is_dir() or _inventory(directory) != files:
            raise ValueError("The existing content-addressed plugin cache differs; it was not overwritten")
        ready = True
    return {"directory": str(directory), "files": files, "ready": ready,
            "module": (directory / "dsh_desktop_tool.mjs").as_uri()}


def _materialize_plugin_cache(repository: Path, identity: dict, plan: dict) -> None:
    """Publish a verified two-module directory before changing DSH configuration.

    Old addresses are immutable and retained for rollback. A staging directory
    becomes visible at its final address only after both original byte streams
    have been verified; no source rewriting or URL-query loader assumptions.
    """
    directory = _below(Path(plan["directory"]), repository)
    expected = plan["files"]
    if directory.exists():
        if _inventory(directory) != expected:
            raise ValueError("The existing content-addressed plugin cache differs; it was not overwritten")
        return
    if _source_identity(repository)["sha256"] != identity["sha256"]:
        raise ValueError("Repository implementation changed during installation; rerun setup")
    data = {}
    for name, digest in expected.items():
        value = (repository / "tools" / name).read_bytes()
        if digest is None or hashlib.sha256(value).hexdigest() != digest:
            raise ValueError("Plugin source changed while preparing its content-addressed cache")
        data[name] = value
    parent = _below(directory.parent, repository)
    parent.mkdir(parents=True, exist_ok=True)
    staging = _below(parent / (".stage-" + uuid.uuid4().hex), repository)
    staging.mkdir()
    try:
        for name, value in data.items():
            _atomic_write(staging / name, value, expected=None)
        if _inventory(staging) != expected:
            raise ValueError("The staged desktop plugin does not match its source bytes")
        if directory.exists():
            if _inventory(directory) != expected:
                raise ValueError("A different plugin cache appeared while preparing setup")
        else:
            staging.rename(directory)
    finally:
        # Remove only our known staging files, never a user-selected directory.
        if staging.exists():
            _below(staging, parent)
            for name in data:
                staged = staging / name
                if staged.is_file() and not staged.is_symlink():
                    staged.unlink()
            staging.rmdir()


def install_desktop(*, repository: Path = REPOSITORY, dsh_home: Path | None = None,
                    dsh_executable: Path | None = None, dry_run: bool = False,
                    uninstall: bool = False) -> dict:
    repository = repository.expanduser().resolve(strict=True)
    home = (dsh_home or Path.home() / ".dsh").expanduser().resolve()
    profile = _below(home / "profiles" / "desktop" / "cordis.patch.yml", home)
    managed = _below(home / ".fish-proteus817", home)
    manifest_path = _below(managed / "install.json", home)
    skill = _below(home / "skills" / "fish-proteus817", home)
    before = _read(profile)
    content = before or b""
    bounds = _bounds(content)
    prior = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else None
    if prior and (prior.get("schema") != SCHEMA or prior.get("profile") != str(profile)):
        raise ValueError("The desktop installation manifest does not match this selected profile")
    if bounds:
        if not prior:
            raise ValueError("A managed desktop block exists without its installation manifest")
        actual_block = content[bounds[0]:bounds[1]]
        if hashlib.sha256(actual_block).hexdigest() != prior.get("block_sha256"):
            raise ValueError("The installed desktop block was edited; preserve and reconcile it before updating")
    outside = content if not bounds else content[:bounds[0]] + content[bounds[1]:]
    if PLUGIN_ID.encode() in outside:
        raise ValueError("A separate desktop registration already uses this plugin ID")
    if uninstall:
        return _uninstall(home, profile, managed, manifest_path, skill, before, bounds, prior, dry_run)
    runtime = _runtime_diagnostics(repository)
    missing = [str(path.relative_to(repository)) for path in
               (repository / "tools" / "dsh_desktop_tool.mjs", repository / "tools" / "dsh_design_tool.mjs",
                repository / "tools" / "dsh_desktop_bootstrap.mjs", repository / "tools" / "desktop_gate.py")
               if not path.is_file()]
    executable = find_dsh(dsh_executable)
    archive = executable.parent / "resources" / "app.asar"
    identity = _source_identity(repository)
    # The stable bootstrap is a versioned loading protocol. Config updates reuse
    # its callback, which dynamically imports the new immutable implementation
    # URI. Keeping the same Entry avoids parallel old/new disposal races.
    plugin_id = BOOTSTRAP_ID
    bootstrap = repository / "tools" / "dsh_desktop_bootstrap.mjs"
    bootstrap_sha = hashlib.sha256(bootstrap.read_bytes()).hexdigest() if bootstrap.is_file() else None
    bootstrap_migration = bool(bounds and prior and prior.get("plugin_id") != BOOTSTRAP_ID)
    bootstrap_protocol_update = bool(bounds and prior and prior.get("plugin_id") == BOOTSTRAP_ID
                                     and prior.get("bootstrap_sha256") != bootstrap_sha)
    plugin_cache = _plugin_cache_plan(repository, identity)
    config = {"plugin": bootstrap.as_uri(), "implementationModule": plugin_cache["module"],
              "workspace": str(repository), "python": str(Path(sys.executable).resolve()),
              "gate": str(repository / "tools" / "desktop_gate.py"),
              "stateRoot": str(repository / ".work" / "desktop"),
              "sourceIdentity": identity["sha256"],
              "toolsModule": (archive / "dsh" / "node_modules" / "@deepseek-ai" / "dsh-tools" / "lib" / "index.js").as_uri()}
    source = repository / "skills" / "fish-proteus817"
    wanted = _inventory(source)
    if "SKILL.md" not in wanted:
        raise ValueError("The repository skill is incomplete")
    project_skill = _project_skill_diagnostics(repository, wanted)
    present = _inventory(skill) if skill.exists() else {}
    if set(present) - set(wanted):
        raise ValueError("The existing global skill has extra files; refusing to overwrite them")
    newline = b"\r\n" if b"\r\n" in content else b"\n"
    block = _block(config.copy(), newline, plugin_id=plugin_id)
    empty_flow_converted = _convert_empty_flow_profile(content) if not bounds else None
    append_content = content if empty_flow_converted is None else empty_flow_converted
    separator = b"" if not append_content or append_content.endswith(b"\n") else newline
    after = (content[:bounds[0]] + block + content[bounds[1]:]) if bounds else append_content + separator + block
    errors = runtime["errors"] + [f"Repository file missing: {name}" for name in missing]
    if bootstrap_migration:
        errors.append("Existing direct-plugin entry requires migration: uninstall it, wait for DSH to unload "
                      "that tool, then install the stable bootstrap")
    if bootstrap_protocol_update:
        errors.append("The installed bootstrap protocol source changed; a protocol upgrade with DSH reload "
                      "is required instead of an ordinary implementation update")
    if not profile.parent.is_dir() or not (profile.parent / "package.json").is_file():
        errors.append("Existing DSH desktop profile not found; open the installed desktop once before setup")
    report = {"schema": SCHEMA, "status": "ready" if not errors else "not_ready", "profile": str(profile),
              "skill": str(skill), "plugin_id": plugin_id, "plugin": config, "runtime": runtime, "errors": errors,
              "source_identity": identity, "plugin_cache": plugin_cache, "project_skill": project_skill,
              "bootstrap_sha256": bootstrap_sha,
              "bootstrap_migration_required": bootstrap_migration,
              "bootstrap_protocol_update_required": bootstrap_protocol_update,
              "empty_flow_profile_converted": empty_flow_converted is not None,
              "project_skill_update_required": project_skill["project_skill_update_required"],
              "warnings": (["An existing project-level skill differs and can shadow this global installation; "
                            "update that project skill before testing in this repository."]
                           if project_skill["project_skill_update_required"] else []),
              "profile_change": before != after, "skill_change": present != wanted,
              "reload": "DSH profile patch hot reload; confirm the tool appears in the existing desktop session"}
    if dry_run:
        report["dry_run"] = True
        return report
    if errors:
        raise ValueError("; ".join(errors))
    if before == after and present == wanted and prior and plugin_cache["ready"]:
        return {**report, "status": "unchanged", "manifest": str(manifest_path)}
    managed.mkdir(parents=True, exist_ok=True)
    lock = managed / "install.lock"
    with lock.open("x", encoding="ascii") as stream:
        stream.write(str(os.getpid()))
    backup = None
    old_skill = None
    new_skill = None
    profile_written = False
    try:
        # The lock serializes our installers; compare-and-replace also detects user edits.
        if _read(profile) != before or (_inventory(skill) if skill.exists() else {}) != present:
            raise ValueError("Installation targets changed after preflight")
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        backup = _below(managed / "backups" / stamp, home)
        backup.mkdir(parents=True)
        if before is not None:
            (backup / "cordis.patch.yml").write_bytes(before)
        if prior:
            (backup / "install.json").write_bytes(_read(manifest_path))
        _materialize_plugin_cache(repository, identity, plugin_cache)
        plugin_cache["ready"] = True
        if present != wanted:
            new_skill = _below(managed / f"skill-stage-{uuid.uuid4().hex}", home)
            shutil.copytree(source, new_skill)
            if _inventory(new_skill) != wanted:
                raise ValueError("The staged skill did not match the source")
            skill.parent.mkdir(parents=True, exist_ok=True)
            if skill.exists():
                old_skill = backup / "skill-before"
                skill.rename(old_skill)
            new_skill.rename(skill)
        elif present and prior is None:
            # An identical pre-existing skill is still user-owned at first setup.
            shutil.copytree(skill, backup / "skill-original")
        if before != after:
            _atomic_write(profile, after, expected=before)
            profile_written = True
        original_skill = prior.get("original_skill") if prior else (
            str(old_skill or backup / "skill-original") if present else None)
        empty_flow = prior.get("empty_flow_profile") if prior else None
        if empty_flow_converted is not None:
            empty_flow = {"original_profile": str(backup / "cordis.patch.yml"),
                          "original_sha256": hashlib.sha256(before).hexdigest(),
                          "converted_sha256": hashlib.sha256(empty_flow_converted).hexdigest()}
        manifest = {"schema": SCHEMA, "profile": str(profile), "repository": str(repository),
                    "block_sha256": hashlib.sha256(block).hexdigest(), "plugin_id": plugin_id, "skill_files": wanted,
                    "bootstrap_sha256": bootstrap_sha,
                    "original_skill": original_skill,
                    "initial_profile_existed": prior.get("initial_profile_existed", True) if prior else before is not None,
                    "initial_separator": prior.get("initial_separator", "") if prior else separator.decode(),
                    "empty_flow_profile": empty_flow,
                    "backup": str(backup), "config": config}
        _atomic_write(manifest_path, _json_bytes(manifest), expected=_read(manifest_path))
        return {**report, "status": "updated" if prior else "installed", "backup": str(backup),
                "manifest": str(manifest_path), "profile_sha256": hashlib.sha256(after).hexdigest()}
    except BaseException:
        if profile_written and _read(profile) == after:
            if before is not None:
                _atomic_write(profile, before, expected=after)
            elif profile.exists():
                profile.rename(backup / "rolled-back-profile.yml")
        if present != wanted and skill.exists() and _inventory(skill) == wanted:
            skill.rename(backup / "rolled-back-new-skill")
        if old_skill and old_skill.exists() and not skill.exists():
            old_skill.rename(skill)
        raise
    finally:
        lock.unlink()


def _uninstall(home, profile, managed, manifest_path, skill, before, bounds, prior, dry_run):
    if prior is None:
        return {"schema": SCHEMA, "status": "not_installed", "profile": str(profile), "dry_run": dry_run}
    present = _inventory(skill) if skill.exists() else {}
    if present and present != prior.get("skill_files"):
        raise ValueError("The installed global skill was edited; preserve and reconcile it before uninstalling")
    original = prior.get("original_skill")
    original_path = _below(Path(original), managed) if original else None
    if original_path and not original_path.is_dir():
        raise ValueError("The original skill backup is missing; refusing partial uninstall")
    content = before or b""
    after = content if not bounds else content[:bounds[0]] + content[bounds[1]:]
    # Undo only the newline added before our appended block, if still adjacent at EOF.
    separator = prior.get("initial_separator", "").encode()
    if bounds and bounds[1] == len(content) and separator and after.endswith(separator):
        after = after[:-len(separator)]
    empty_flow = prior.get("empty_flow_profile")
    if empty_flow and hashlib.sha256(after).hexdigest() == empty_flow.get("converted_sha256"):
        original_profile = _below(Path(empty_flow["original_profile"]), managed)
        if not original_profile.is_file():
            raise ValueError("The original empty-flow profile backup is missing; refusing partial uninstall")
        after = original_profile.read_bytes()
        if hashlib.sha256(after).hexdigest() != empty_flow.get("original_sha256"):
            raise ValueError("The original empty-flow profile backup changed; refusing partial uninstall")
    if dry_run:
        return {"schema": SCHEMA, "status": "ready_to_uninstall", "profile": str(profile), "dry_run": True}
    lock = managed / "install.lock"
    with lock.open("x", encoding="ascii") as stream:
        stream.write(str(os.getpid()))
    backup = None
    moved_skill = None
    restored_skill = False
    profile_written = False
    try:
        if _read(profile) != before or (_inventory(skill) if skill.exists() else {}) != present:
            raise ValueError("Uninstall targets changed after preflight")
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        backup = _below(managed / "backups" / (stamp + "-uninstall"), home)
        backup.mkdir(parents=True)
        if before is not None:
            (backup / "cordis.patch.yml").write_bytes(before)
        (backup / "install.json").write_bytes(manifest_path.read_bytes())
        # Keep removed assets as a backup instead of recursively deleting them.
        if skill.exists():
            moved_skill = backup / "removed-skill"
            skill.rename(moved_skill)
        if original_path:
            shutil.copytree(original_path, skill)
            restored_skill = True
        if before != after:
            _atomic_write(profile, after, expected=before)
            profile_written = True
        manifest_path.rename(backup / "removed-install.json")
        return {"schema": SCHEMA, "status": "uninstalled", "profile": str(profile), "backup": str(backup),
                "profile_sha256": hashlib.sha256(after).hexdigest(), "original_skill_restored": bool(original_path)}
    except BaseException:
        if profile_written and _read(profile) == after:
            _atomic_write(profile, before, expected=after)
        if restored_skill and skill.exists():
            skill.rename(backup / "rolled-back-restored-skill")
        if moved_skill and moved_skill.exists() and not skill.exists():
            moved_skill.rename(skill)
        raise
    finally:
        lock.unlink()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dsh-home", type=Path, help="Existing DSH home (default: ~/.dsh)")
    parser.add_argument("--dsh-executable", type=Path, help="Existing desktop executable, selected once at installation")
    parser.add_argument("--dry-run", action="store_true", help="Report installation readiness without changing files")
    parser.add_argument("--uninstall", action="store_true", help="Remove this registration and restore its original skill")
    args = parser.parse_args()
    try:
        result = install_desktop(dsh_home=args.dsh_home, dsh_executable=args.dsh_executable,
                                 dry_run=args.dry_run, uninstall=args.uninstall)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["status"] != "not_ready" else 1
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
        print(json.dumps({"schema": SCHEMA, "status": "error", "message": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    raise SystemExit(main())
