"""Persistent desktop session tasks around the existing typed design service.

The desktop host supplies session identity, working directory and storage. Model
requests describe domain actions or register explicitly selected local files;
they do not select another session, an executable or a Python module.
"""
from __future__ import annotations

from collections import deque
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
from itertools import islice
import json
import os
from pathlib import Path
import shutil
import tempfile
import uuid

from .config import ProteusConfig
from .design_cli import ACTIONS, DesignTask, execute_request, validate_request, _identifier


SCHEMA = "fish-proteus.desktop.v1"
DESKTOP_FIELDS = {
    "task_create": (set(), {"label"}),
    "task_list": (set(), set()),
    "task_current": (set(), set()),
    "task_select": ({"task_id"}, set()),
    "resources": (set(), set()),
    "resource_find": (set(), {"query", "kind", "scope", "limit"}),
    "resource_register": ({"kind"}, {"path", "candidate_id", "name"}),
    "project_export": ({"destination"}, set()),
}
DESKTOP_ACTIONS = frozenset(DESKTOP_FIELDS)
ALL_ACTIONS = ACTIONS | DESKTOP_ACTIONS
REVISION_ACTIONS = frozenset({"edit", "generator_update", "run_sequence", "verify"})
CONFIG_FIELDS = ("executable", "library_root", "samples_root", "template_project")
EXTENSIONS = {"project": {".pdsprj"}, "firmware": {".elf", ".hex"}}


def _need(condition, message):
    if not condition:
        raise ValueError(message)


def _now():
    return datetime.now(timezone.utc).isoformat()


def _sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _write(path, value):
    """Replace one complete manifest on its own filesystem."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=".desktop-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf8", newline="\n") as stream:
            json.dump(value, stream, ensure_ascii=False, allow_nan=False, sort_keys=True, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if Path(temporary).exists():
            Path(temporary).unlink()


@contextmanager
def file_lock(path):
    """An OS-owned nonblocking lock; a dead process cannot leave a stale lock."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as stream:
        if stream.seek(0, os.SEEK_END) == 0:
            stream.write(b"\0")
            stream.flush()
        stream.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise RuntimeError("Another Proteus request is using this session or native engine; retry after it finishes") from exc
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == "nt":
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def _local_path(value, working_directory):
    _need(isinstance(value, str) and 0 < len(value) <= 32768 and "\0" not in value,
          "A local file/directory path is required")
    _need(not value.startswith(("\\\\", "//")), "Network and device paths are not local resources")
    path = Path(value).expanduser()
    return (path if path.is_absolute() else working_directory / path).resolve()


def _process_is_running(pid):
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.WaitForSingleObject.argtypes = (wintypes.HANDLE, wintypes.DWORD)
        kernel.WaitForSingleObject.restype = wintypes.DWORD
        kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
        kernel.CloseHandle.restype = wintypes.BOOL
        process = kernel.OpenProcess(0x00100000 | 0x1000, False, pid)
        if not process:
            # Only ERROR_INVALID_PARAMETER conclusively means no such PID.
            return ctypes.get_last_error() != 87
        try:
            return kernel.WaitForSingleObject(process, 0) != 0
        finally:
            kernel.CloseHandle(process)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _recover_dead_design_lock(root):
    """Recover only this task's core lock after its writer has exited.

    The session OS lock is already held. A live or unidentifiable owner remains
    blocked; no process is terminated and no other task file is removed.
    """
    lock = root / ".design.lock"
    if not lock.exists():
        return
    text = lock.read_text(encoding="ascii").strip()
    _need(text.isdecimal() and 0 < int(text) <= 2**32 - 1,
          "The interrupted task lock has an unidentifiable owner")
    _need(not _process_is_running(int(text)), "Another process still owns this design task")
    lock.unlink()


class GPIOTraceConfigurationError(ValueError):
    """A known model lacks the trace setting required by the requested reader."""


def _trace_setting_missing_or_zero(value):
    if value is None or (isinstance(value, str) and not value.strip()):
        return True
    text = str(value).strip()
    try:
        return int(text, 0) == 0
    except ValueError:
        try:
            return float(text) == 0
        except ValueError:
            # Do not guess an unfamiliar model-property expression. The
            # native reader and subsequent evidence checks still decide it.
            return False


def _preflight_gpio_capture(payload, root, inputs, api, runtime):
    """Check only the exercised STM32 model, without changing its circuit."""
    requests = [step for step in payload["steps"] if step["op"] == "gpio_events"]
    if not requests:
        return
    task = DesignTask(root, inputs, api=api, runtime=runtime)
    if payload.get("request_id") in task.state.get("requests", {}):
        # The core validates request/payload/report identity on replay and
        # never starts a Session. Do not replace that historical response
        # with a preflight assessment of a newer circuit revision.
        return
    current = task.state.get("current")
    if current is None or current.get("mode") != "structural":
        return  # Opaque staged projects and other models are not inferred.
    from ._vendor.proteus_auto.proteus_project import UnsupportedFormat
    try:
        components = task._circuit(payload["expected_revision"]).components()
    except UnsupportedFormat:
        return
    targets = {part["ref"]: part for part in components
               if str(part.get("device", "")).upper() == "STM32F103R6"}
    selected = set()
    for request in requests:
        if request.get("ref") is None:
            selected.update(targets)
        elif request["ref"] in targets:
            selected.add(request["ref"])
    missing = [ref for ref in sorted(selected)
               if _trace_setting_missing_or_zero(targets[ref].get("properties", {}).get("TRACE_GPIO"))]
    if missing:
        raise GPIOTraceConfigurationError(
            "GPIO capture for STM32F103R6 " + ", ".join(missing)
            + " requires a saved nonzero TRACE_GPIO property before opening Proteus. "
              "TRACE_GPIO is missing or zero. Use edit/set_properties on those refs with "
              'properties={"TRACE_GPIO":"3"}, save the managed circuit, then run again '
              "(the tested port-A trace path; other nonzero masks are also accepted). "
              "No native session was started and the circuit was not changed.")


def _validate_desktop(payload):
    _need(isinstance(payload, dict), "The desktop request must be a JSON object")
    action = payload.get("action")
    _need(isinstance(action, str) and action in ALL_ACTIONS, "Unknown desktop/design action")
    if action in DESKTOP_FIELDS:
        required, optional = DESKTOP_FIELDS[action]
        _need(required <= payload.keys(), f"Missing fields for {action}")
        _need(not (payload.keys() - required - optional - {"action", "request_id"}),
              f"Unexpected fields for {action}")
    return action


class DesktopTasks:
    """One trusted desktop session, opened and locked for each request."""

    def __init__(self, store_root, session_id, working_directory, config=None):
        _need(isinstance(session_id, str) and 0 < len(session_id) <= 4096,
              "The desktop host must supply a real session identity")
        self.store = Path(store_root).expanduser().resolve()
        self.working_directory = Path(working_directory).expanduser().resolve(strict=True)
        _need(self.working_directory.is_dir(), "The session working directory must be a directory")
        self.session_id = session_id
        self.session_key = hashlib.sha256(session_id.encode("utf8")).hexdigest()
        self.root = self.store / "sessions" / self.session_key
        self.manifest = self.root / "session.json"
        self.config_values = dict(config or {})
        _need(self.config_values.keys() <= set(CONFIG_FIELDS), "Unknown desktop resource configuration")
        self.state = None
        self.deferred_save = False

    def load(self):
        self.state = json.loads(self.manifest.read_text(encoding="utf8")) if self.manifest.is_file() else {
            "schema": SCHEMA, "session_id": self.session_id, "current_task": None,
            "tasks": {}, "candidates": {}}
        _need(self.state.get("schema") == SCHEMA and self.state.get("session_id") == self.session_id,
              "Desktop session identity or schema mismatch")

    def config(self):
        return ProteusConfig.discover(**self.config_values)

    def save(self):
        if not self.deferred_save:
            _write(self.manifest, self.state)

    def replay_management(self, payload):
        """Session-level management IDs never depend on the selected task."""
        request_id = _identifier(payload["request_id"])
        digest = hashlib.sha256(json.dumps(payload, sort_keys=True, allow_nan=False).encode()).hexdigest()
        cached = self.state.get("desktop_requests", {}).get(request_id)
        if cached is None:
            return digest, None
        _need(cached["sha256"] == digest, "request_id was already used for a different desktop management request")
        report = self.root / "desktop-requests" / (hashlib.sha256(request_id.encode("utf8")).hexdigest() + ".json")
        _need(report.is_file() and _sha(report) == cached["report_sha256"],
              "Recorded desktop management response identity mismatch")
        return digest, dict(json.loads(report.read_text(encoding="utf8")), replayed=True)

    def record_management(self, payload, digest, result):
        request_id = payload["request_id"]
        report = self.root / "desktop-requests" / (hashlib.sha256(request_id.encode("utf8")).hexdigest() + ".json")
        _write(report, result)
        self.state.setdefault("desktop_requests", {})[request_id] = {
            "sha256": digest, "report_sha256": _sha(report)}
        # Commit task selection and its response index together. A crash before
        # this replace can leave an unreferenced task directory, never a second
        # visible task or a committed task selection without its replay record.
        self.deferred_save = False
        self.save()

    def task_root(self, task_id):
        _need(task_id in self.state["tasks"] and isinstance(task_id, str)
              and len(task_id) == 32 and all(c in "0123456789abcdef" for c in task_id),
              "Unknown task in this desktop session")
        path = (self.root / "tasks" / task_id).resolve()
        _need(self.root in path.parents, "Task path escapes its desktop session")
        return path

    def create_task(self, label=None):
        label = label if label is not None else "Proteus design"
        _need(isinstance(label, str) and 0 < len(label) <= 256 and "\0" not in label,
              "Task label must be a short nonempty string")
        task_id = uuid.uuid4().hex
        item = {"task_id": task_id, "label": label, "created_utc": _now()}
        path = self.root / "tasks" / task_id
        _write(path / "desktop-task.json", {**item, "schema": SCHEMA,
               "inputs": {"projects": {}, "firmware": {}}, "resources": {}})
        self.state["tasks"][task_id] = item
        self.state["current_task"] = task_id
        self.save()
        return task_id

    def current_task(self):
        return self.state["current_task"] or self.create_task()

    def task(self):
        task_id = self.current_task()
        path = self.task_root(task_id)
        item = json.loads((path / "desktop-task.json").read_text(encoding="utf8"))
        _need(item.get("schema") == SCHEMA and item.get("task_id") == task_id,
              "Desktop task identity mismatch")
        return path, item

    def context(self):
        task_id = self.state.get("current_task") if self.state else None
        result = {"session_id": self.session_id, "task_id": task_id,
                "task_root": str(self.task_root(task_id)) if task_id else None,
                "working_directory": str(self.working_directory)}
        if task_id:
            root = self.task_root(task_id)
            manifest = root / "design-task.json"
            if manifest.is_file():
                current = json.loads(manifest.read_text(encoding="utf8")).get("current")
                if current:
                    project = (root / current["path"]).resolve()
                    _need(root in project.parents, "Managed project path escapes task storage")
                    result["project_path"] = str(project)
        return result

    def _check_resources(self, item):
        for record in item["resources"].values():
            source = Path(record["path"])
            _need(source.is_file() and _sha(source) == record["sha256"],
                  "A registered original changed; register the changed file in a new task")

    def _inputs(self, item):
        return {"config": self.config_values, **item["inputs"]}

    def _sync_inputs(self, root, item):
        """Append host-authorized inputs without relaxing DesignTask's fixed-input API.

        Registration is persistent in desktop-task.json. Every call verifies all
        original hashes; only newly registered entries can enter the backend
        manifest. Retrying after a crash is safe, and no old ID is rebound.
        """
        self._check_resources(item)
        manifest = root / "design-task.json"
        if not manifest.is_file():
            return
        state = json.loads(manifest.read_text(encoding="utf8"))
        expected = {f"{kind}:{key}": {"path": path, "sha256": item["resources"][key]["sha256"]}
                    for kind, values in item["inputs"].items() for key, path in values.items()}
        observed = state.get("inputs", {})
        _need(all(key in expected and expected[key] == value for key, value in observed.items()),
              "Existing backend original-input identity changed")
        if observed != expected:
            state["inputs"] = expected
            _write(manifest, state)

    def register(self, payload):
        kind = payload["kind"]
        _need(kind in EXTENSIONS, "Resource kind must be project or firmware")
        _need(("path" in payload) != ("candidate_id" in payload),
              "Choose exactly one local path or discovered candidate_id")
        if "candidate_id" in payload:
            candidate = self.state["candidates"].get(payload["candidate_id"])
            _need(candidate is not None and candidate["kind"] == kind,
                  "Unknown discovered candidate for this resource kind/session")
            source = Path(candidate["path"]).resolve(strict=True)
        else:
            source = _local_path(payload["path"], self.working_directory)
        _need(source.is_file() and source.suffix.lower() in EXTENSIONS[kind],
              "Select an existing .pdsprj project or .elf/.hex firmware of the requested kind")
        _need(source != self.store and self.store not in source.parents,
              "Managed task artifacts are not original inputs; use a separate external source")
        root, item = self.task()
        self._check_resources(item)
        digest = _sha(source)
        for key, value in item["resources"].items():
            if value["path"] == str(source) and value["kind"] == kind:
                return {"input_id": key, **value, "reused": True}
        _need(len(item["inputs"]["projects" if kind == "project" else "firmware"]) < 128,
              "This task has reached the backend's 128-input limit for this resource kind")
        name = payload.get("name", source.name)
        _need(isinstance(name, str) and 0 < len(name) <= 256 and "\0" not in name,
              "Resource name must be a short string")
        key = ("project-" if kind == "project" else "firmware-") + uuid.uuid4().hex[:20]
        record = {"kind": kind, "name": name, "path": str(source), "sha256": digest}
        item["inputs"]["projects" if kind == "project" else "firmware"][key] = str(source)
        item["resources"][key] = record
        _write(root / "desktop-task.json", item)
        return {"input_id": key, **record, "reused": False}

    def find(self, payload):
        kind, scope = payload.get("kind"), payload.get("scope", "workspace")
        _need(kind is None or kind in EXTENSIONS, "Unknown resource kind")
        _need(scope in {"workspace", "samples"}, "Resource scope must be workspace or samples")
        limit = payload.get("limit", 30)
        _need(type(limit) is int and 1 <= limit <= 100, "Resource limit must be between 1 and 100")
        query = payload.get("query", "")
        _need(isinstance(query, str) and len(query) <= 512, "Resource query must be a short string")
        base = self.working_directory if scope == "workspace" else self.config().samples_root
        _need(base.is_dir(), "The selected resource search directory does not exist")
        extensions = EXTENSIONS[kind] if kind else set().union(*EXTENSIONS.values())
        pending, matches, scanned, truncated = deque([(base, 0)]), [], 0, False
        while pending and scanned < 5000 and len(matches) < limit:
            directory, depth = pending.popleft()
            try:
                with os.scandir(directory) as stream:
                    budget = 5000 - scanned
                    entries = list(islice(stream, budget + 1))
                    if len(entries) > budget:
                        truncated = True
                        entries = entries[:budget]
                    entries.sort(key=lambda entry: entry.name.casefold())
            except OSError:
                continue
            for entry in entries:
                scanned += 1
                if scanned > 5000:
                    truncated = True
                    break
                path = Path(entry.path)
                if entry.is_dir(follow_symlinks=False):
                    if (depth < 6 and entry.name not in {".git", "node_modules", ".venv", "__pycache__", ".dsh"}
                            and path.resolve() != self.store and self.store not in path.resolve().parents):
                        pending.append((path, depth + 1))
                    elif depth >= 6:
                        truncated = True
                    continue
                if (not entry.is_file(follow_symlinks=False) or path.suffix.lower() not in extensions
                        or query.casefold() not in str(path.relative_to(base)).casefold()):
                    continue
                actual_kind = "project" if path.suffix.lower() == ".pdsprj" else "firmware"
                candidate_id = "candidate-" + hashlib.sha256(str(path.resolve()).encode("utf8")).hexdigest()[:32]
                self.state["candidates"][candidate_id] = {"path": str(path.resolve()), "kind": actual_kind}
                matches.append({"candidate_id": candidate_id, "name": path.name, "kind": actual_kind,
                                "relative_name": path.relative_to(base).as_posix()})
                if len(matches) >= limit:
                    truncated = True
                    break
        truncated = truncated or bool(pending) or scanned >= 5000
        self.save()
        return {"matches": matches, "scope": scope, "scanned_entries": min(scanned, 5000),
                "truncated": truncated, "maximum_depth": 6,
                "note": "Candidates are file locations, not compatibility or simulation proof."}

    def export(self, payload):
        root, item = self.task()
        self._check_resources(item)
        task = DesignTask(root, self._inputs(item))
        source = task.current()
        destination = _local_path(payload["destination"], self.working_directory)
        _need(not destination.exists(), "Export destination must be a new directory; existing files are never overwritten")
        _need(destination != self.store and self.store not in destination.parents,
              "Export must be outside desktop task storage")
        config = self.config()
        config.check_destination(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = Path(tempfile.mkdtemp(prefix=".fish-export-", dir=destination.parent))
        try:
            relative = source.relative_to(root)
            target = temporary / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
            for name in ("inputs", "firmware"):
                dependency = root / name
                if dependency.is_dir():
                    shutil.copytree(dependency, temporary / name)
            _write(temporary / "export.json", {"schema": SCHEMA, "project": relative.as_posix(),
                   "sha256": _sha(target), "revision": task.state["current"]["revision"]})
            _need(not destination.exists(), "Export destination appeared during export")
            temporary.rename(destination)
        finally:
            if temporary.exists():
                # This exact directory is the temporary created above, never user input.
                shutil.rmtree(temporary)
        return {"directory": str(destination), "project": str(destination / relative),
                "sha256": _sha(source), "revision": task.state["current"]["revision"]}


def _dispatch_desktop_request(desktop, payload, allowed, api, runtime):
    action = payload["action"]
    if action == "task_create":
        desktop.create_task(payload.get("label"))
        data = dict(desktop.state["tasks"][desktop.state["current_task"]])
    elif action == "task_list":
        data = {"tasks": list(desktop.state["tasks"].values()), "current_task": desktop.state["current_task"]}
    elif action == "task_select":
        desktop.task_root(payload["task_id"])
        desktop.state["current_task"] = payload["task_id"]
        desktop.save()
        data = dict(desktop.state["tasks"][payload["task_id"]])
    elif action == "resource_find":
        data = desktop.find(payload)
    elif action == "resource_register":
        data = desktop.register(payload)
    elif action in {"task_current", "resources"}:
        root, item = desktop.task()
        data = {**desktop.state["tasks"][item["task_id"]], "resources": item["resources"]}
        manifest = root / "design-task.json"
        if manifest.is_file():
            data["current"] = json.loads(manifest.read_text(encoding="utf8")).get("current")
        if action == "resources":
            data["installation"] = desktop.config().describe()
            data["working_directory"] = str(desktop.working_directory)
    elif action == "project_export":
        root, item = desktop.task()
        _recover_dead_design_lock(root)
        desktop._sync_inputs(root, item)
        data = desktop.export(payload)
    elif action == "help" and payload.get("topic") == "desktop":
        _need(not (payload.keys() - {"action", "topic", "request_id"}), "Unexpected fields for help")
        source = Path(__file__).resolve().parents[1] / "skills" / "fish-proteus817" / "references" / "desktop-workflow.md"
        data = {"topic": "desktop", "source": "bundled-reference",
                "content": source.read_text(encoding="utf8")}
    else:
        _need(action in allowed, "The installed desktop tool has not enabled this action")
        root, item = desktop.task()
        _recover_dead_design_lock(root)
        desktop._sync_inputs(root, item)
        forwarded = dict(payload)
        if action in REVISION_ACTIONS and "expected_revision" not in forwarded:
            manifest = root / "design-task.json"
            state = json.loads(manifest.read_text(encoding="utf8")) if manifest.is_file() else {}
            _need(state.get("current") is not None, "Create, open or stage a project first")
            forwarded["expected_revision"] = state["current"]["revision"]
            if "request_id" in payload:
                # A replay must use the revision from its first dispatch,
                # not the newer current revision produced by that request.
                requests = item.setdefault("requests", {})
                digest = hashlib.sha256(json.dumps(payload, sort_keys=True, allow_nan=False).encode()).hexdigest()
                cached = requests.get(payload["request_id"])
                if cached:
                    _need(cached["sha256"] == digest, "request_id was already used for a different desktop request")
                    forwarded["expected_revision"] = cached["expected_revision"]
                else:
                    requests[payload["request_id"]] = {"sha256": digest,
                        "expected_revision": forwarded["expected_revision"]}
                    _write(root / "desktop-task.json", item)
        if action == "run_sequence":
            validate_request(forwarded, allowed)
            _preflight_gpio_capture(forwarded, root, desktop._inputs(item), api, runtime)
            with file_lock(desktop.store / ".native.lock"):
                result = execute_request(forwarded, root, desktop._inputs(item), allowed, api=api, runtime=runtime)
        else:
            result = execute_request(forwarded, root, desktop._inputs(item), allowed, api=api, runtime=runtime)
        result["desktop"] = desktop.context()
        return result
    context = desktop.context()
    if action == "project_export":
        context["export_path"] = data["project"]
    return {"schema": SCHEMA, "action": action,
            "status": "file_verified" if action == "project_export" else "prepared", "data": data,
            "desktop": context, "evidence_refs": [], "ended_utc": _now()}


def _blocked_result(payload, desktop, exc):
    try:
        context = desktop.context() if desktop and desktop.state else None
    except (OSError, ValueError, KeyError, TypeError):
        context = None
    return {"schema": SCHEMA, "action": payload.get("action") if isinstance(payload, dict) else None,
            "status": "blocked", "error": {"type": type(exc).__name__, "message": str(exc)},
            "desktop": context, "ended_utc": _now()}


def execute_desktop_request(payload, *, store_root, session_id, working_directory,
                            config=None, allowed=ACTIONS, api=None, runtime=None):
    """Execute one request with host-derived context, returning actual backend evidence."""
    desktop = None
    errors = (OSError, ValueError, KeyError, RuntimeError, TypeError, ImportError, AttributeError)
    try:
        action = _validate_desktop(payload)
        desktop = DesktopTasks(store_root, session_id, working_directory, config)
        with file_lock(desktop.root / ".session.lock"):
            desktop.load()
            management = action in DESKTOP_ACTIONS or (action == "help" and payload.get("topic") == "desktop")
            cached_request = management and "request_id" in payload
            digest = None
            if cached_request:
                digest, replayed = desktop.replay_management(payload)
                if replayed is not None:
                    return replayed
                desktop.deferred_save = True
            try:
                result = _dispatch_desktop_request(desktop, payload, allowed, api, runtime)
            except errors as exc:
                result = _blocked_result(payload, desktop, exc)
            if cached_request:
                desktop.record_management(payload, digest, result)
            return result
    except errors as exc:
        return _blocked_result(payload, desktop, exc)
