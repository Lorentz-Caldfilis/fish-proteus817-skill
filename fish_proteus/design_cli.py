"""Composable, task-scoped design requests for the DSH typed tool.

Requests contain domain operations, never Python, shell commands or host paths.
The host supplies resource configuration and named read-only inputs separately.
Native sequences keep one Session in this process and always stop/close it.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path, PureWindowsPath
import re
import shutil
import sys
import tempfile
import uuid
import zipfile


SCHEMA = "fish-proteus.design.v1"
REFERENCE_ROOT = Path(__file__).resolve().parents[1] / "skills" / "fish-proteus817" / "references"
READ_ACTIONS = frozenset({"capabilities", "help", "library_search", "library_get", "inspect", "generators", "firmware_info", "graph_sample", "verify"})
FILE_ACTIONS = READ_ACTIONS | {"create", "open", "stage", "edit", "generator_update", "extract_firmware"}
ACTIONS = FILE_ACTIONS | {"run_sequence"}
ACTION_FIELDS = {
    "capabilities": (set(), set()),
    "help": (set(), {"topic"}),
    "library_search": (set(), {"query", "limit"}),
    "library_get": ({"name"}, {"library"}),
    "create": (set(), {"template_input", "title"}),
    "open": ({"input_id"}, set()),
    "stage": ({"input_id"}, set()),
    "inspect": (set(), {"ref", "sections"}),
    "edit": ({"expected_revision", "operations"}, {"title"}),
    "generators": (set(), set()),
    "generator_update": ({"expected_revision", "name", "properties"}, set()),
    "firmware_info": ({"firmware_id"}, set()),
    "extract_firmware": (set(), {"member"}),
    "graph_sample": ({"artifact_id", "trace", "x"}, {"occurrence"}),
    "run_sequence": ({"expected_revision", "steps"}, {"save_project"}),
    "verify": ({"expected_revision", "assertions"}, set()),
}
EDIT_FIELDS = {
    "import_device": ({"name"}, {"library", "donor_input"}),
    "import_from_project": ({"input_id", "device"}, set()),
    "add": ({"device", "ref", "value", "x", "y"}, {"rotation", "mirror_x", "mirror_y", "properties"}),
    "update": ({"ref", "changes"}, set()),
    "move": ({"ref", "x", "y"}, set()),
    "rotate": ({"ref"}, {"degrees"}),
    "mirror": ({"ref"}, {"axis"}),
    "set_properties": ({"ref", "properties"}, set()),
    "assign_firmware": ({"ref", "firmware_id"}, {"clock"}),
    "bind_controls": ({"refs"}, set()),
    "rename": ({"ref", "new_ref"}, set()),
    "copy_component": ({"ref", "new_ref", "x", "y"}, set()),
    "delete_component": ({"ref"}, set()),
    "connect": ({"first", "second"}, {"points"}),
    "disconnect": ({"first"}, {"second"}),
    "set_route": ({"first", "second", "points"}, set()),
    "add_wire_label": ({"first", "second", "text"}, {"position"}),
    "remove_wire_label": ({"first", "second", "text"}, set()),
    "add_terminal": ({"kind", "name"}, {"pin", "position", "rotation"}),
    "update_terminal": ({"terminal_id", "changes"}, set()),
    "delete_terminal": ({"terminal_id"}, set()),
    "configure_power": ({"rails"}, {"bindings"}),
}
STEP_FIELDS = {
    "status": (set(), set()), "start": (set(), set()), "pause": (set(), set()),
    "stop": (set(), set()), "reset": (set(), set()), "controls": (set(), set()),
    "control_state": ({"ref"}, set()), "press": ({"ref"}, set()), "release": ({"ref"}, set()),
    "set_switch": ({"ref", "closed"}, set()),
    "run_for": ({"seconds"}, {"timeout", "tolerance_seconds"}),
    "set_firmware": ({"ref", "firmware_id"}, {"clock"}),
    "log": (set(), set()), "gpio_events": (set(), {"ref", "port", "pin"}),
    "errors": (set(), set()), "netlist": (set(), set()),
    "set_properties": ({"ref", "properties"}, set()), "save": (set(), set()),
    "graphs": (set(), set()), "export_graph": ({"graph"}, {"simulate", "timeout"}),
}
ASSERT_FIELDS = {
    "connected": ({"pins"}, {"artifact_id"}),
    "isolated": ({"first", "second"}, {"artifact_id"}),
    "component": ({"ref", "fields"}, {"artifact_id"}),
    "csv_range": ({"artifact_id", "trace", "x", "minimum", "maximum"}, {"occurrence"}),
    "gpio_sequence": ({"artifact_id", "ref", "port", "pin", "values"}, set()),
    "simulation_time": ({"artifact_id", "step", "seconds", "tolerance_seconds"}, set()),
    "no_errors": ({"artifact_id"}, set()),
}
ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,95}\Z")
PATH_PROPERTIES = {"PROGRAM", "FIRMWARE", "FILE", "FILENAME", "DATAFILE", "IMAGEFILE", "SCRIPT", "PYTHON", "COMMAND", "LOGFILE", "LOGFILENAME"}


def _need(condition, message):
    if not condition:
        raise ValueError(message)


def _fields(value, kind, table, common=()):
    _need(isinstance(value, dict), "An operation must be a JSON object")
    name = value.get(kind)
    _need(isinstance(name, str) and name in table, f"Unknown {kind}")
    required, optional = table[name]
    _need(required <= value.keys(), f"Missing fields for {name}: {sorted(required - value.keys())}")
    _need(not (value.keys() - required - optional - {kind} - set(common)), f"Unexpected fields for {name}")
    return name


def _text(value, name="text", maximum=4096, empty=False):
    _need(isinstance(value, str) and (empty or bool(value)) and len(value) <= maximum,
          f"Invalid {name}")
    _need(all(32 <= ord(ch) < 127 for ch in value), f"{name} must be printable ASCII")
    return value


def _identifier(value):
    _need(isinstance(value, str) and ID_PATTERN.fullmatch(value) is not None, "Invalid registered input/artifact ID")
    reserved = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}
    _need(value.split(".", 1)[0].upper() not in reserved and not value.endswith("."), "Reserved Windows identifier")
    return value


def _number(value, name, lower=-1e100, upper=1e100, integer=False):
    _need(type(value) in ((int,) if integer else (int, float)) and math.isfinite(value)
          and lower <= value <= upper, f"Invalid {name}")


def _point(value):
    _need(isinstance(value, (list, tuple)) and len(value) == 2, "A point needs two native integers")
    for item in value:
        _number(item, "native coordinate", -2**31, 2**31-1, True)


def _endpoint(value):
    if isinstance(value, str):
        value = value.rsplit(".", 1)
    _need(isinstance(value, (list, tuple)) and len(value) == 2, "Use REF.PIN or [ref,pin]")
    for item in value:
        _text(item, "pin endpoint", 96)


def _properties(value):
    _need(isinstance(value, dict) and 0 < len(value) <= 128, "Properties must be a nonempty bounded object")
    for key, item in value.items():
        _need(isinstance(key, str) and re.fullmatch(r"[A-Z_][A-Z0-9_]*", key) is not None,
              "Property keys must be native uppercase names")
        _need(key not in PATH_PROPERTIES, "Use a registered firmware ID; arbitrary file/script properties are disabled")
        _need(type(item) in (str, int, float), "Property values must be strings or finite numbers")
        if type(item) in (int, float):
            _number(item, "property value")
        _text(str(item), "property value")
        if key in {"MODFILE", "MODDLL", "ITFMOD"}:
            _need(not any(ch in str(item) for ch in "\\/:") and ".." not in str(item),
                  "Model file properties may only name installed resources")


def _changes(changes, terminal=False):
    allowed = {"kind", "name", "pin", "position", "rotation"} if terminal else {
        "value", "x", "y", "rotation", "mirror_x", "mirror_y", "properties", "label_offsets"}
    _need(isinstance(changes, dict) and changes and changes.keys() <= allowed, "Invalid edit changes")
    if "properties" in changes:
        _properties(changes["properties"])
    for key in ("x", "y", "rotation"):
        if key in changes and changes[key] is not None:
            _number(changes[key], key, -2**31, 2**31-1, True)
    for key in ("mirror_x", "mirror_y"):
        if key in changes:
            _need(type(changes[key]) is bool, f"{key} must be boolean")
    if "position" in changes and changes["position"] is not None:
        _point(changes["position"])
    if "pin" in changes and changes["pin"] is not None:
        _endpoint(changes["pin"])
    if "label_offsets" in changes:
        offsets = changes["label_offsets"]
        _need(isinstance(offsets, dict) and offsets.keys() <= {"reference", "value", "device", "properties"}, "Invalid label offsets")
        for point in offsets.values():
            _point(point)
    for key in ("kind", "name", "value"):
        if key in changes:
            _text(changes[key], key, 1024, empty=key == "name")


def validate_request(payload, allowed=ACTIONS):
    """Validate all nested operations before any native process or disk edit."""
    action = _fields(payload, "action", ACTION_FIELDS, {"request_id"})
    _need(action in allowed, "This action is not enabled by the task host")
    if "request_id" in payload:
        _identifier(payload["request_id"])
    if "expected_revision" in payload:
        _need(isinstance(payload["expected_revision"], str) and re.fullmatch(r"[0-9a-f]{64}", payload["expected_revision"]) is not None,
              "expected_revision must be the current returned SHA256 revision")
    if "topic" in payload:
        _need(payload["topic"] in {"actions", "edits", "steps", "assertions", "workflow"}, "Unknown fixed help topic")
    for key in ("input_id", "template_input", "artifact_id", "firmware_id"):
        if key in payload:
            _identifier(payload[key])
    for key in ("name", "trace", "ref", "title", "query"):
        if key in payload:
            _text(payload[key], key, 256, empty=key == "query")
    if "library" in payload:
        _library_selector(payload["library"])
    if "limit" in payload:
        _number(payload["limit"], "limit", 1, 1000, True)
    if "properties" in payload:
        _properties(payload["properties"])
    if "x" in payload:
        _number(payload["x"], "sample x")
    if "occurrence" in payload:
        _number(payload["occurrence"], "occurrence", 0, 65535, True)
    if "member" in payload:
        _relative(payload["member"])
    if "sections" in payload:
        _need(isinstance(payload["sections"], list) and payload["sections"] and set(payload["sections"]) <= {
            "components", "pins", "connections", "nets", "terminals", "wire_labels", "power_rails"}, "Invalid inspect sections")
    if action == "edit":
        operations = payload["operations"]
        _need(isinstance(operations, list) and 1 <= len(operations) <= 2000, "Use 1..2000 structured edit operations")
        for operation in operations:
            _validate_edit(operation)
    if action == "run_sequence":
        steps = payload["steps"]
        _need(isinstance(steps, list) and 1 <= len(steps) <= 128, "Use 1..128 native sequence steps")
        if "save_project" in payload:
            _need(type(payload["save_project"]) is bool, "save_project must be boolean")
        for step in steps:
            _validate_step(step)
        if any(step["op"] in {"log", "gpio_events", "errors"} for step in steps):
            _need(_single_log_epoch(steps), "Log/GPIO/error observations require one engine epoch; run reset or stop/restart in a separate sequence")
        _need(sum(float(step.get("seconds", 0)) for step in steps) <= 120, "A sequence may request at most 120 simulation seconds")
        if payload.get("save_project", True) is False:
            mutations = [i for i, step in enumerate(steps) if step["op"] in {"set_properties", "set_firmware"}]
            _need(not mutations or any(step["op"] == "save" for step in steps[max(mutations)+1:]),
                  "Native property changes must be explicitly saved before closing")
    if action == "verify":
        assertions = payload["assertions"]
        _need(isinstance(assertions, list) and 1 <= len(assertions) <= 128, "Use 1..128 declarative assertions")
        for assertion in assertions:
            kind = _fields(assertion, "type", ASSERT_FIELDS)
            if "artifact_id" in assertion:
                _identifier(assertion["artifact_id"])
            if kind == "connected":
                _need(isinstance(assertion["pins"], list) and 2 <= len(assertion["pins"]) <= 256, "connected needs at least two pins")
                for pin in assertion["pins"]:
                    _endpoint(pin)
            if kind == "isolated":
                _endpoint(assertion["first"]); _endpoint(assertion["second"])
            if kind == "component":
                _text(assertion["ref"], "ref", 96)
                _need(isinstance(assertion["fields"], dict) and assertion["fields"] and assertion["fields"].keys() <= {
                    "device", "value", "properties"}, "Unsupported component assertion fields")
            if kind == "csv_range":
                _text(assertion["trace"], "trace", 256)
                for key in ("x", "minimum", "maximum"):
                    _number(assertion[key], key)
                _need(assertion["minimum"] <= assertion["maximum"], "Invalid sample interval")
                _number(assertion.get("occurrence", 0), "occurrence", 0, 65535, True)
            if kind == "gpio_sequence":
                _text(assertion["ref"], "ref", 96)
                for key in ("port", "pin"):
                    _number(assertion[key], key, 0, 255, True)
                _need(isinstance(assertion["values"], list) and 2 <= len(assertion["values"]) <= 256
                      and all(type(x) is int and x in (0, 1) for x in assertion["values"]), "Invalid GPIO sequence")
            if kind == "simulation_time":
                _number(assertion["step"], "step", 0, 127, True)
                _number(assertion["seconds"], "seconds", 0, 120)
                _number(assertion["tolerance_seconds"], "tolerance", 0, 1)
    return payload


def _single_log_epoch(steps):
    started = stopped = False
    for step in steps:
        if step["op"] == "reset":
            return False
        if step["op"] in {"start", "run_for"}:
            if stopped:
                return False
            started = True
        elif step["op"] == "stop" and started:
            stopped = True
    return True


def _library_selector(value):
    _text(value, "library selector", 128)
    _need(not any(ch in value for ch in "\\/:") and ".." not in value, "Use an enumerated library name, not a path")


def _validate_edit(item):
    op = _fields(item, "op", EDIT_FIELDS)
    for key in ("name", "device", "ref", "new_ref", "value", "terminal_id", "kind", "axis", "text"):
        if key in item:
            _text(item[key], key, 1024, empty=op == "add_terminal" and key == "name")
    for key in ("donor_input", "input_id", "firmware_id"):
        if key in item:
            _identifier(item[key])
    if "library" in item:
        _library_selector(item["library"])
    if "properties" in item:
        _properties(item["properties"])
    if "changes" in item:
        _changes(item["changes"], op == "update_terminal")
    for key in ("x", "y", "rotation", "degrees"):
        if key in item and item[key] is not None:
            _number(item[key], key, -2**31, 2**31-1, True)
    for key in ("mirror_x", "mirror_y"):
        if key in item:
            _need(type(item[key]) is bool, f"{key} must be boolean")
    for key in ("first", "second", "pin"):
        if key in item and item[key] is not None:
            _endpoint(item[key])
    if "points" in item and item["points"] is not None:
        _need(isinstance(item["points"], list) and 2 <= len(item["points"]) <= 1024, "Invalid route points")
        for point in item["points"]:
            _point(point)
    if "position" in item and item["position"] is not None:
        _point(item["position"])
    if op == "bind_controls":
        _need(isinstance(item["refs"], list) and 1 <= len(item["refs"]) <= 5, "Bind 1..5 binary controls")
        for ref in item["refs"]:
            _text(ref, "ref", 96)
    if op == "configure_power":
        _need(isinstance(item["rails"], dict) and len(item["rails"]) <= 128, "Invalid power rails")
        _need(isinstance(item.get("bindings", {}), dict), "Invalid power bindings")
        for name, voltage in item["rails"].items():
            _text(name, "rail name", 128)
            if isinstance(voltage, dict):
                _need(voltage.keys() <= {"voltage", "flags"} and "voltage" in voltage, "Invalid rail definition")
                _need(voltage.get("flags", "POWER") in ("", "POWER"), "Unknown rail flags")
                voltage = voltage["voltage"]
            _number(voltage, "rail voltage")
        for name, rail in item.get("bindings", {}).items():
            _text(name, "binding", 128)
            _need(rail in item["rails"], "Unknown binding rail")
    if "clock" in item:
        _text(str(item["clock"]), "clock", 128)


def _validate_step(item):
    op = _fields(item, "op", STEP_FIELDS)
    if "ref" in item:
        _text(item["ref"], "ref", 96)
    if "firmware_id" in item:
        _identifier(item["firmware_id"])
    if "properties" in item:
        _properties(item["properties"])
    if "closed" in item:
        _need(type(item["closed"]) is bool, "closed must be boolean")
    if "seconds" in item:
        _number(item["seconds"], "seconds", 1e-9, 60)
    if "timeout" in item:
        _number(item["timeout"], "timeout", 1, 120)
    if "tolerance_seconds" in item:
        _number(item["tolerance_seconds"], "tolerance_seconds", 0, 1)
    for key in ("port", "pin"):
        if key in item:
            _number(item[key], key, 0, 255, True)
    if "simulate" in item:
        _need(type(item["simulate"]) is bool, "simulate must be boolean")
    if "graph" in item:
        if type(item["graph"]) is int:
            _number(item["graph"], "graph index", 0, 65535, True)
        else:
            _text(item["graph"], "graph name", 256)
    if "clock" in item:
        _text(str(item["clock"]), "clock", 128)


def _relative(value):
    _need(isinstance(value, str) and value and len(value) <= 512, "Invalid relative artifact path")
    win = PureWindowsPath(value)
    _need(not win.is_absolute() and not win.drive and not value.startswith(("/", "\\"))
          and ":" not in value and ".." not in win.parts, "Artifact paths must remain relative to the fixed task")
    return value


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _json_default(value):
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (set, tuple)):
        return list(value)
    raise TypeError(f"Not a public JSON value: {type(value).__name__}")


def _write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp-" + uuid.uuid4().hex)
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=_json_default, allow_nan=False) + "\n", encoding="utf8")
    temporary.replace(path)


def _make_log_directory(task_root):
    """Host-owned ASCII staging, preferably within an ancestor of this task.

    Windows sandbox TEMP may permit directory creation but deny child-file I/O.
    Use a fixed staging name under a writable ASCII task ancestor, then try the
    OS temp directory. No model-supplied field selects either base or filename.
    """
    task_root = Path(task_root).resolve()
    bases = [parent / ".work" / "fish-proteus-log-staging"
             for parent in (task_root, *task_root.parents)
             if str(parent).isascii() and parent != Path(parent.anchor)]
    bases.append(Path(tempfile.gettempdir()))
    for base in bases:
        if not str(base).isascii():
            continue
        directory = None
        try:
            base.mkdir(parents=True, exist_ok=True)
            directory = Path(tempfile.mkdtemp(prefix="fish-proteus-log-", dir=base)).resolve()
            probe = directory / "write-probe"
            probe.write_bytes(b"")
            probe.unlink()
            return directory
        except OSError:
            if directory is not None:
                try:
                    _remove_log_directory(directory)
                except OSError:
                    pass
    raise ValueError("No writable ASCII native-log staging directory is available")


def _remove_log_directory(directory):
    """Delete only the exact temporary directory created by this host call."""
    directory = Path(directory)
    _need(directory.is_absolute() and directory.resolve() == directory
          and directory.name.startswith("fish-proteus-log-"), "Refusing cleanup outside the owned log directory")
    shutil.rmtree(directory)


class DesignTask:
    """One fixed workspace. Original inputs are registered by the host only."""

    def __init__(self, root, inputs=None, *, api=None, runtime=None):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.inputs = inputs or {}
        _need(isinstance(self.inputs, dict) and self.inputs.keys() <= {"schema", "config", "projects", "firmware"}, "Invalid host input manifest")
        self.api = api
        self.runtime = runtime
        self.manifest = self.root / "design-task.json"
        self.state = json.loads(self.manifest.read_text(encoding="utf8")) if self.manifest.is_file() else {
            "schema": SCHEMA, "task_id": uuid.uuid4().hex, "circuit_id": None,
            "current": None, "artifacts": {}, "requests": {}, "inputs": {}}
        _need(self.state.get("schema") == SCHEMA, "Unknown design task format")
        self._bind_inputs()

    def path(self, relative):
        candidate = (self.root / _relative(relative)).resolve()
        _need(candidate != self.root and self.root in candidate.parents, "Artifact path escapes task root")
        return candidate

    def _bind_inputs(self):
        observed = {}
        for kind in ("projects", "firmware"):
            entries = self.inputs.get(kind, {})
            _need(isinstance(entries, dict) and len(entries) <= 128, "Host inputs must be bounded ID mappings")
            for key, path in entries.items():
                _identifier(key)
                source = Path(path).expanduser().resolve(strict=True)
                _need(source.is_file() and self.root not in source.parents and source != self.root,
                      "Original inputs must be files outside the mutable task directory")
                if kind == "projects":
                    _need(source.suffix.lower() == ".pdsprj", "Registered projects must be .pdsprj files")
                observed[f"{kind}:{key}"] = {"path": str(source), "sha256": _sha(source)}
        if self.state["inputs"]:
            _need(self.state["inputs"] == observed, "A registered original changed or the host input mapping was replaced")
        self.state["inputs"] = observed

    def _api(self):
        if self.api is None:
            from . import automation
            self.api = automation
        return self.api

    def _runtime(self):
        if self.runtime is None:
            from runtime_adaptation import generic
            self.runtime = generic
        return self.runtime

    def config(self):
        from .config import ProteusConfig
        values = self.inputs.get("config", {})
        _need(isinstance(values, dict) and values.keys() <= {"executable", "library_root", "samples_root", "template_project"}, "Unknown host configuration key")
        return ProteusConfig.discover(**values)

    def input(self, kind, key):
        _identifier(key)
        record = self.state["inputs"].get(f"{kind}:{key}")
        _need(record is not None, f"The host did not register {kind} input {key}")
        path = Path(record["path"])
        _need(_sha(path) == record["sha256"], "Original input changed")
        return path

    def firmware(self, key):
        if f"firmware:{key}" in self.state["inputs"]:
            source = self.input("firmware", key)
            target = self.path(f"inputs/firmware-{key}{source.suffix.lower()}")
            target.parent.mkdir(parents=True, exist_ok=True)
            if not target.exists():
                shutil.copyfile(source, target)
            _need(_sha(target) == _sha(source), "Staged firmware identity mismatch")
            return target
        record, path = self.artifact(key)
        _need(record["kind"] == "firmware", "This artifact is not firmware")
        return path

    def program_reference(self, firmware):
        """Persistent ASCII PROGRAM relative to managed projects, not a host path."""
        project = self.current()
        firmware = Path(firmware).resolve(strict=True)
        _need(self.root in firmware.parents, "PROGRAM must resolve to staged task firmware")
        reference = os.path.relpath(firmware, project.parent)
        _text(reference, "relative PROGRAM", 512)
        _need((project.parent / reference).resolve() == firmware, "Relative PROGRAM identity mismatch")
        return reference

    def current(self, expected=None):
        current = self.state.get("current")
        _need(current is not None, "Create, open or stage a project first")
        path = self.path(current["path"])
        _need(path.is_file() and _sha(path) == current["sha256"], "Managed project changed outside this task; reopen a registered input")
        if expected is not None:
            _need(expected == current["revision"], "Stale expected_revision; inspect the current project before editing or running")
        return path

    def artifact(self, key, *, fresh=False):
        _identifier(key)
        record = self.state["artifacts"].get(key)
        _need(record is not None, "Unknown artifact ID")
        path = self.path(record["path"])
        _need(path.is_file() and _sha(path) == record["sha256"], "Artifact identity mismatch")
        if fresh:
            _need(record.get("revision") == self.state["current"]["revision"], "Evidence belongs to an earlier project revision")
        return record, path

    def record(self, path, kind, *, artifact_id=None, **metadata):
        path = Path(path).resolve()
        _need(self.root in path.parents, "Evidence must belong to this task")
        key = _identifier(artifact_id) if artifact_id else uuid.uuid4().hex
        _need(key not in self.state["artifacts"], "Artifact ID is already registered")
        record = {"artifact_id": key, "path": path.relative_to(self.root).as_posix(), "sha256": _sha(path),
                  "kind": kind, "revision": (self.state.get("current") or {}).get("revision"), **metadata}
        self.state["artifacts"][key] = record
        return record

    def _set_current(self, path, *, mode="structural"):
        digest = _sha(path)
        revision = self._api().Circuit.open(path, config=self.config()).revision if mode == "structural" else digest
        self.state["current"] = {"path": Path(path).relative_to(self.root).as_posix(), "sha256": digest,
                                 "revision": revision, "mode": mode}
        self.state["circuit_id"] = self.state["circuit_id"] or uuid.uuid4().hex
        return self.state["current"]

    def _destination(self):
        return self.path("projects/" + uuid.uuid4().hex + ".pdsprj")

    def _circuit(self, expected=None):
        path = self.current(expected)
        _need(self.state["current"]["mode"] == "structural", "Staged opaque projects support native/property operations, not whole-sheet reconstruction")
        return self._api().Circuit.open(path, config=self.config())

    @contextmanager
    def locked(self):
        lock = self.root / ".design.lock"
        descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        try:
            os.write(descriptor, str(os.getpid()).encode("ascii"))
            yield
        finally:
            os.close(descriptor)
            lock.unlink()

    def handle(self, payload, allowed=ACTIONS):
        validate_request(payload, allowed)
        with self.locked():
            # Reload after acquiring the lock: concurrent callers never share stale state.
            if self.manifest.is_file():
                self.state = json.loads(self.manifest.read_text(encoding="utf8"))
            self._bind_inputs()
            request_id = payload.get("request_id", uuid.uuid4().hex)
            request_hash = hashlib.sha256(json.dumps(payload, sort_keys=True, allow_nan=False).encode()).hexdigest()
            cached = self.state["requests"].get(request_id)
            if cached:
                _need(cached["sha256"] == request_hash, "request_id was already used for a different request")
                cached_path = self.path(cached["report"])
                _need(cached.get("report_sha256") == _sha(cached_path), "Recorded response identity mismatch")
                return dict(json.loads(cached_path.read_text(encoding="utf8")), replayed=True)
            report = {"schema": SCHEMA, "request_id": request_id, "task_id": self.state["task_id"],
                      "action": payload["action"], "status": "blocked", "data": None,
                      "side_effects": {}, "evidence_refs": []}
            before = set(self.state["artifacts"])
            try:
                status, data, effects = self._dispatch(payload, request_id, allowed)
                report.update(status=status, data=data, side_effects=effects)
            except (OSError, ValueError, KeyError, RuntimeError, NotImplementedError, ImportError, TypeError, AttributeError) as exc:
                report.update(error={"type": type(exc).__name__, "message": str(exc)},
                              status="unsupported" if isinstance(exc, NotImplementedError) else "blocked")
            self._bind_inputs()
            report.update(circuit_id=self.state["circuit_id"], current=self.state["current"],
                          session_id=(report.get("data") or {}).get("session_id") if isinstance(report.get("data"), dict) else None,
                          evidence_refs=[self.state["artifacts"][key] for key in self.state["artifacts"] if key not in before],
                          ended_utc=datetime.now(timezone.utc).isoformat())
            relative = f"requests/{request_id}.json"
            _write(self.path(relative), report)
            self.state["requests"][request_id] = {"sha256": request_hash, "report": relative, "report_sha256": _sha(self.path(relative))}
            _write(self.manifest, self.state)
            return report

    def _dispatch(self, p, request_id, allowed):
        action, api = p["action"], self._api()
        if action == "help":
            topic = p.get("topic", "actions")
            documents = REFERENCE_ROOT
            source = documents / ("workflows-and-evidence.md" if topic == "workflow" else "generic-api.md")
            companion = Path(__file__).resolve().parents[1] / "tools" / "dsh_design_tool.mjs"
            if companion.is_file() and source.is_file():
                text = source.read_text(encoding="utf8")
                headings = {"actions": "## Actions", "edits": "## Edit operations", "steps": "## Native steps", "assertions": "## Assertions"}
                if topic != "workflow":
                    text = text.split(headings[topic], 1)[1]
                    text = headings[topic] + text.split("\n## ", 1)[0]
                return "prepared", {"topic": topic, "source": "bundled-reference", "content": text}, {}
            table = {"actions": ACTION_FIELDS, "edits": EDIT_FIELDS, "steps": STEP_FIELDS, "assertions": ASSERT_FIELDS}.get(topic, ACTION_FIELDS)
            result = {"topic": topic, "source": "embedded-contract", "units_per_mm": 100000,
                                "fields": {name: {"required": sorted(fields[0]), "optional": sorted(fields[1])} for name, fields in table.items()},
                                "note": "Use fresh expected_revision and registered IDs. Unknown fields, paths and code are rejected. See the full companion skill references for workflow details."}
            if topic == "workflow":
                result["workflow"] = ["Read capabilities and actual library/pins before choosing devices.",
                                      "Create a new topology, open a recognized input, or explicitly stage an opaque project.",
                                      "Apply an edit batch against current.revision; inspect and verify its saved file structure.",
                                      "Run enabled native steps in one owned Session, collect SDF/CSV/GPIO/time artifacts, then stop/save/close.",
                                      "Verify independent assertions against fresh matching artifacts; unverified time remains false/null."]
            return "prepared", result, {}
        if action == "capabilities":
            config = self.config()
            profile = {"probe_state": "not_probed", "runtime_verified": False}
            if hasattr(config, "executable"):
                from runtime_adaptation.profile817 import profile_for, CompatibilityError
                try:
                    profile = {"probe_state": "fingerprint_matched", "profile": profile_for(config.executable).describe(), "runtime_verified": False}
                except (OSError, CompatibilityError) as exc:
                    profile = {"probe_state": "unavailable", "reason": str(exc), "runtime_verified": False}
            return "prepared", {**api.capability_report(config), "service": "fish-proteus-design", "protocol_version": 1,
                                "allowed_actions": sorted(allowed), "native_profile": profile,
                                "task_id": self.state["task_id"], "registered_inputs": sorted(self.state["inputs"])}, {}
        if action == "library_search":
            rows = api.Library(config=self.config()).search(p.get("query", ""), p.get("limit", 30))
            return "prepared", {"matches": rows, "lookup_is_simulation_proof": False}, {}
        if action == "library_get":
            return "prepared", api.Library(config=self.config()).get(p["name"], p.get("library")), {}
        if action in {"create", "open", "stage"}:
            _need(self.state["current"] is None, "This task already has a project; create a new task for a different input")
            destination = self._destination()
            if action == "create":
                template = self.input("projects", p["template_input"]) if p.get("template_input") else None
                circuit = api.Circuit(template_project=template, config=self.config())
                circuit.save(destination, title=p.get("title"))
                self._set_current(destination)
            else:
                source = self.input("projects", p["input_id"])
                if action == "open":
                    api.Circuit.open(source, config=self.config())  # do not replace unknown objects with a blank sheet
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, destination)
                self._set_current(destination, mode="structural" if action == "open" else "native")
            record = self.record(destination, "project")
            return ("prepared" if action == "stage" else "file_verified"), self.state["current"], {"created_project": record["artifact_id"], "originals_modified": False}
        if action == "inspect":
            circuit = self._circuit()
            data = circuit.inspect()
            data["wire_labels"] = circuit.wire_labels()
            if p.get("ref"):
                ref = p["ref"]
                data["components"] = [x for x in data["components"] if x["ref"] == ref]
                _need(data["components"], "Unknown component reference")
                data["pins"] = {ref: data["pins"][ref]}
            if p.get("sections"):
                data = {key: value for key, value in data.items() if key in {*p["sections"], "revision", "source_sha256", "coordinate_unit", "units_per_mm"}}
            return "file_verified", data, {}
        if action == "edit":
            circuit = self._circuit(p["expected_revision"])
            outputs = [self._edit(circuit, op) for op in p["operations"]]
            destination = self._destination()
            circuit.save(destination, title=p.get("title"))
            self._set_current(destination)
            self.record(destination, "project")
            return "file_verified", {"operations": outputs, "revision": self.state["current"]["revision"]}, {"saved_new_revision": True, "originals_modified": False}
        if action == "generators":
            return "file_verified", api.generators(self.current()), {}
        if action == "generator_update":
            source = self.current(p["expected_revision"])
            destination = self._destination()
            destination.parent.mkdir(parents=True, exist_ok=True)
            api.set_generator_properties(source, destination, p["name"], **p["properties"])
            self._set_current(destination, mode=self.state["current"]["mode"])
            self.record(destination, "project")
            return "file_verified", api.generators(destination), {"saved_new_revision": True}
        if action == "firmware_info":
            return "file_verified", api.firmware_info(self.firmware(p["firmware_id"])), {}
        if action == "extract_firmware":
            project = self.current()
            member = p.get("member")
            if member is None:
                with zipfile.ZipFile(project) as archive:
                    candidates = [x.filename for x in archive.infolist() if x.filename.startswith("FIRMWARE/") and Path(x.filename).suffix.lower() in {".elf", ".hex", ".cof", ".coff", ".cdb", ".bin"}]
                _need(len(candidates) == 1, "Choose an exact firmware archive member")
                member = candidates[0]
            suffix = Path(member).suffix.lower()
            _need(suffix in {".elf", ".hex"}, "Only ELF/HEX extraction is enabled")
            destination = self.path(f"firmware/{uuid.uuid4().hex}{suffix}")
            destination.parent.mkdir(parents=True, exist_ok=True)
            data = api.extract_firmware(project, destination, member=member)
            record = self.record(destination, "firmware")
            return "file_verified", {"firmware": data, "firmware_id": record["artifact_id"]}, {"extracted_firmware": True}
        if action == "graph_sample":
            record, path = self.artifact(p["artifact_id"], fresh=True)
            _need(record["kind"] == "graph_csv", "Select an exported CSV artifact")
            data = api.parse_graph_csv(path.read_text(encoding="cp1252"))
            value = api.sample_graph(data, p["trace"], p["x"], occurrence=p.get("occurrence", 0))
            fresh = record.get("simulated") is True and record.get("run_status") == "runtime_observed"
            return "runtime_observed" if fresh else "file_verified", {"value": value, "trace": p["trace"], "x": p["x"], "occurrence": p.get("occurrence", 0), "source": record, "fresh_simulation": fresh}, {}
        if action == "run_sequence":
            return self._run_sequence(p, request_id)
        if action == "verify":
            return self._verify(p)
        raise ValueError("Unknown design action")

    def _edit(self, circuit, op):
        method = op["op"]
        args = {key: value for key, value in op.items() if key != "op"}
        if method == "import_device":
            donor = args.pop("donor_input", None)
            result = circuit.import_device(**args, donor_project=self.input("projects", donor) if donor else None)
        elif method == "import_from_project":
            result = circuit.import_from_project(self.input("projects", args["input_id"]), args["device"])
        elif method in {"update", "update_terminal"}:
            key = "terminal_id" if method == "update_terminal" else "ref"
            result = getattr(circuit, method)(args[key], **args["changes"])
        elif method == "set_properties":
            result = circuit.set_properties(args["ref"], **args["properties"])
        elif method == "assign_firmware":
            path = self.firmware(args["firmware_id"])
            info = self._api().firmware_info(path)
            program = self.program_reference(path)
            values = {"PROGRAM": program}
            if "clock" in args:
                values["CLOCK"] = str(args["clock"])
            circuit.set_properties(args["ref"], **values)
            result = {"firmware": info, "ref": args["ref"], "program": program,
                      "program_resolved_sha256": _sha(path)}
        elif method == "bind_controls":
            result = circuit.bind_controls(*args["refs"])
        else:
            # method is from the closed EDIT_FIELDS registry, never model code.
            result = getattr(circuit, method)(**args)
        return {"op": method, "result": None if result is circuit else result}

    def _run_sequence(self, p, request_id):
        project = self.current(p["expected_revision"])
        rt = self._runtime()
        run_root = self.path(f"runs/{request_id}/run.json").parent
        run_root.mkdir(parents=True, exist_ok=False)
        snapshot = run_root / "project-input.pdsprj"
        shutil.copyfile(project, snapshot)
        capture_log = any(step["op"] in {"log", "gpio_events", "errors"} for step in p["steps"])
        result = {"schema": "fish-proteus.design-run.v1", "request_id": request_id,
                  "project_before_sha256": _sha(project), "steps": [], "cleanup": {},
                  "status": "blocked", "actual_time_verified": False, "simulation_seconds": None,
                  "log_complete": False, "log_capture_requested": capture_log, "final_active_clock": None,
                  "single_log_epoch": _single_log_epoch(p["steps"])}
        pending, deferred = [], []
        session = simulation = log_directory = None
        error = None
        native_saved = False
        raw_id, raw_sha = None, None

        def clock(status):
            value = status.get("simulation_seconds") if isinstance(status, dict) else None
            if (isinstance(status, dict) and status.get("actual_time_verified") is True
                    and type(value) in (int, float) and math.isfinite(value) and value >= 0):
                return value
            return None

        def remember_active(status, source="native_step_result"):
            value = clock(status)
            if value is not None and status.get("state") in {"running", "paused"}:
                result["final_active_clock"] = value
                result["last_active_status"] = status
                result["final_active_clock_capture"] = {"source": source, "captured_before_stop": True,
                                                        "actual_time_verified": True, "simulation_seconds": value}

        def attach(path, kind, **metadata):
            key = uuid.uuid4().hex
            pending.append({"path": Path(path), "kind": kind, "artifact_id": key, **metadata})
            return key

        try:
            session_options = {"config": self.config()}
            if capture_log:
                log_directory = _make_log_directory(self.root)
                session_options["logfile"] = log_directory / "native.log"
            session = rt.Session(project, **session_options)
            simulation = rt.Simulation(session)
            result["session_id"] = str(getattr(session, "identity", {}).get("session_id", uuid.uuid4().hex))
            result["identity"] = getattr(session, "identity", {"pid": session.pid})
            profile = getattr(session, "native_profile", None)
            result["native_profile"] = profile.describe() if profile is not None and callable(getattr(profile, "describe", None)) else result["identity"].get("profile")
            for index, step in enumerate(p["steps"]):
                operation = step["op"]
                args = {key: value for key, value in step.items() if key != "op"}
                entry = {"index": index, "op": operation, "input": args, "status": "blocked"}
                result["steps"].append(entry)
                if operation in {"log", "gpio_events", "errors", "stop", "reset"}:
                    observed = simulation.status()
                    remember_active(observed, "native_status_before_stop" if operation in {"stop", "reset"} else "native_status_at_log_request")
                    if operation in {"log", "gpio_events", "errors"}:
                        entry.update(status="deferred", clock_at_request=observed,
                                     requested_at_simulation_seconds=clock(observed))
                        deferred.append(entry)
                        continue
                if operation in {"set_properties", "save"}:
                    _need(simulation.status()["state"] == "stopped", "Stop the simulation before native property changes or saving")
                if operation == "set_properties":
                    data = session.set_properties(args["ref"], **args["properties"])
                elif operation == "save":
                    data = session.save(); native_saved = True
                elif operation == "netlist":
                    native_sdf = run_root / f"{index:03d}-netlist.sdf"
                    data = session.export_netlist(native_sdf)
                    if native_sdf.is_file():
                        attach(native_sdf, "native_sdf", step=index)
                elif operation == "graphs":
                    data = rt.graphs(session)
                elif operation == "export_graph":
                    csv = run_root / f"{index:03d}-graph.csv"
                    data = rt.export_graph(session, args["graph"], csv, simulate=args.get("simulate", True), timeout=args.get("timeout", 60))
                    csv_id = attach(csv, "graph_csv", step=index, simulated=args.get("simulate", True))
                    data = dict(data, artifact_id=csv_id)
                elif operation == "set_firmware":
                    data = simulation.set_firmware(args["ref"], self.firmware(args["firmware_id"]), clock=args.get("clock"))
                else:
                    data = getattr(simulation, operation)(**args)
                entry.update(status="executed", data=data)
                if isinstance(data, dict):
                    remember_active(data)
            result["status"] = "runtime_observed"
        except (OSError, ValueError, KeyError, RuntimeError, ImportError, TypeError, AttributeError) as exc:
            error = exc
            result["error"] = {"type": type(exc).__name__, "message": str(exc)}
        finally:
            if simulation is not None:
                try:
                    observed = simulation.status()
                    result["final_observed_status"] = observed
                    remember_active(observed, "native_status_before_cleanup_stop")
                    result["cleanup"]["stop"] = simulation.stop()
                    if p.get("save_project", True):
                        session.save(); native_saved = True
                        result["cleanup"]["saved_project"] = True
                except (OSError, ValueError, RuntimeError, NotImplementedError) as exc:
                    result["cleanup"]["stop_or_save_error"] = str(exc)
                    error = error or exc
            if session is not None:
                try:
                    code = session.close()
                    result["cleanup"]["close_exit_code"] = code
                    result["cleanup"]["owned_process_closed"] = True
                    _need(code in (0, None), "Owned Proteus process exited unsuccessfully")
                except (OSError, ValueError, RuntimeError) as exc:
                    result["cleanup"]["close_error"] = str(exc)
                    error = error or exc
                    process = getattr(session, "process", None)
                    if process is not None:
                        try:
                            if process.poll() is None:
                                process.terminate(); process.wait(timeout=10)
                                result["cleanup"]["forced_owned_process_termination"] = True
                            result["cleanup"]["owned_process_closed"] = process.poll() is not None
                        except (OSError, RuntimeError, TimeoutError) as cleanup_error:
                            result["cleanup"]["forced_cleanup_error"] = str(cleanup_error)
            try:
                if session is not None and capture_log:
                    metadata = dict(getattr(session, "log_metadata", {}) or {})
                    result["log_metadata"] = metadata
                    finalized = bool(getattr(session, "normal_closed", False)) and metadata.get("complete") is True and metadata.get("finalized_after_process_close") is True
                    actual_path = Path(session.logfile).resolve() if getattr(session, "logfile", None) else None
                    _need(actual_path is None or actual_path == (log_directory / "native.log").resolve(), "Runtime changed the host-selected log output")
                    if actual_path is not None and actual_path.is_file():
                        raw = run_root / "simulation-log-raw.log"
                        shutil.copyfile(actual_path, raw)
                        raw_sha = _sha(raw)
                        hash_matches = raw_sha == getattr(session, "final_logfile_sha256", None)
                        result["log_complete"] = finalized and hash_matches
                        raw_id = attach(raw, "simulation_log_raw", log_complete=finalized and hash_matches,
                                        collected_after_close=True, encoding=metadata.get("encoding", "utf-8"))
                        result["raw_log_artifact_id"] = raw_id
                        result["raw_log_sha256"] = raw_sha
                        if finalized:
                            _need(hash_matches, "Final native logfile hash does not match the closed-session cache")
                    if deferred:
                        _need(finalized and raw_id is not None, "A complete logfile finalized by normal process close is required")
                    if finalized and raw_id is not None:
                        common = {"log_complete": True, "collected_after_close": True,
                                  "raw_log_artifact_id": raw_id, "raw_log_sha256": raw_sha,
                                  "single_log_epoch": result["single_log_epoch"]}
                        # Always retain final diagnostics, even if a deferred
                        # GPIO request later fails its independent-clock check.
                        observed = simulation.errors()
                        final_errors = {key: value for key, value in observed.items() if key != "log"}
                        final_errors.update(scope="complete_final_run", through_simulation_seconds=result["final_active_clock"], **common)
                        final_path = run_root / "final-errors.json"
                        final_id = uuid.uuid4().hex
                        _write(final_path, {"op": "errors", "status": "executed", "data": final_errors, "artifact_id": final_id})
                        pending.append({"path": final_path, "kind": "simulation_errors", "artifact_id": final_id,
                                        "log_complete": True, "collected_after_close": True, "raw_log_artifact_id": raw_id})
                        result["final_errors_artifact_id"] = final_id
                        result["final_errors"] = final_errors
                        for entry in deferred:
                            operation, args = entry["op"], entry["input"]
                            cutoff = entry["requested_at_simulation_seconds"]
                            if operation == "gpio_events":
                                _need(cutoff is not None, "Deferred GPIO requires an independently verified native clock at its request step")
                                events = simulation.gpio_events(**args)
                                for event in events:
                                    _need(type(event.get("seconds")) in (int, float) and math.isfinite(event["seconds"]) and event["seconds"] >= 0, "Invalid native GPIO event time")
                                data = {"events": [event for event in events if event["seconds"] <= cutoff],
                                        "filters": args, "scope": "event_timestamp_prefix", "through_simulation_seconds": cutoff,
                                        "requested_at_simulation_seconds": cutoff, **common}
                            elif operation == "errors":
                                observed = simulation.errors()
                                data = {key: value for key, value in observed.items() if key != "log"}
                                data.update(scope="complete_final_run", through_simulation_seconds=result["final_active_clock"],
                                            requested_at_simulation_seconds=cutoff, **common)
                            else:
                                text = simulation.log()
                                data = {"text": text[:16000], "text_truncated": len(text) > 16000,
                                        "scope": "complete_final_run", "through_simulation_seconds": result["final_active_clock"],
                                        "requested_at_simulation_seconds": cutoff, **common}
                            entry.update(status="executed", data=data)
            except (OSError, ValueError, KeyError, RuntimeError, ImportError, TypeError, AttributeError) as exc:
                error = error or exc
                result["log_collection_error"] = {"type": type(exc).__name__, "message": str(exc)}
                for entry in deferred:
                    if entry["status"] == "deferred":
                        entry.update(status="blocked", error={"type": type(exc).__name__, "message": str(exc)})
            finally:
                if log_directory is not None:
                    try:
                        _remove_log_directory(log_directory)
                        result["cleanup"]["owned_log_directory_removed"] = True
                    except (OSError, ValueError) as exc:
                        error = error or exc
                        result["cleanup"]["log_directory_error"] = str(exc)
        result["actual_time_verified"] = result["final_active_clock"] is not None
        result["simulation_seconds"] = result["final_active_clock"]
        # Session.close restores the original LOGFILE option after native saving.
        # Hash/revision must be computed after that restoration, even without save.
        if session is not None and project.is_file():
            mode = self.state["current"]["mode"]
            try:
                self._set_current(project, mode=mode)
            except (ValueError, KeyError, TypeError):
                self._set_current(project, mode="native")
                result["structural_reopen_available"] = False
        result["project_after_sha256"] = _sha(project)
        if error is not None:
            result["status"] = "unsupported" if isinstance(error, NotImplementedError) else "blocked"
        # Only now write final step JSON and register immutable hashes. No
        # previously registered artifact is rewritten with deferred results.
        for entry in result["steps"]:
            path = run_root / f"{entry['index']:03d}-{entry['op']}.json"
            key = uuid.uuid4().hex
            entry["artifact_id"] = key
            _write(path, entry)
            kind = {"netlist": "native_netlist", "gpio_events": "gpio_events", "log": "simulation_log", "errors": "simulation_errors"}.get(entry["op"], "native_step")
            data = entry.get("data") or {}
            pending.append({"path": path, "kind": kind, "artifact_id": key,
                            "log_complete": data.get("log_complete") if isinstance(data, dict) else None,
                            "collected_after_close": data.get("collected_after_close") if isinstance(data, dict) else None,
                            "raw_log_artifact_id": data.get("raw_log_artifact_id") if isinstance(data, dict) else None})
        for item in pending:
            metadata = {key: value for key, value in item.items() if key not in {"path", "kind", "artifact_id"}}
            self.record(item["path"], item["kind"], artifact_id=item["artifact_id"],
                        session_id=result.get("session_id"), run_status=result["status"],
                        project_before_sha256=result["project_before_sha256"],
                        project_after_sha256=result["project_after_sha256"], **metadata)
        _write(run_root / "run.json", result)
        run_record = self.record(run_root / "run.json", "native_run", session_id=result.get("session_id"))
        self.record(snapshot, "project_snapshot", session_id=result.get("session_id"))
        result["run_artifact_id"] = run_record["artifact_id"]
        return result["status"], result, {"native_session_started": session is not None, "saved_project": native_saved,
                                        "only_owned_process": True, "native_logfile_host_selected": log_directory is not None}

    def _complete_log(self, record, data):
        _need(isinstance(data, dict) and data.get("log_complete") is True
              and data.get("collected_after_close") is True
              and data.get("single_log_epoch") is True
              and record.get("log_complete") is True and record.get("collected_after_close") is True,
              "Verification requires a complete native log collected after normal process close")
        raw_record, path = self.artifact(data.get("raw_log_artifact_id"), fresh=True)
        _need(raw_record["kind"] == "simulation_log_raw" and raw_record.get("log_complete") is True
              and raw_record.get("collected_after_close") is True and raw_record.get("run_status") == "runtime_observed"
              and raw_record.get("session_id") == record.get("session_id")
              and raw_record["sha256"] == data.get("raw_log_sha256"), "Final logfile provenance/identity mismatch")
        return raw_record, path

    def _verify(self, p):
        self.current(p["expected_revision"])
        checks = []
        levels = []
        for assertion in p["assertions"]:
            kind = assertion["type"]
            record = data = None
            if "artifact_id" in assertion:
                record, path = self.artifact(assertion["artifact_id"], fresh=True)
                if record["kind"] == "graph_csv":
                    data = self._api().parse_graph_csv(path.read_text(encoding="cp1252"))
                else:
                    data = json.loads(path.read_text(encoding="utf8"))
                if record["kind"] in {"native_netlist", "gpio_events", "simulation_log", "simulation_errors", "native_step"}:
                    data = data["data"]
            if kind in {"connected", "isolated", "component"}:
                if record:
                    _need(record["kind"] == "native_netlist", "Structural native assertions need an actual SDF/netlist artifact")
                    nets = [[(pin["ref"], pin["pin"]) for pin in net["pins"]] for net in data["nets"]]
                    parts = data["parts"]
                    levels.append("native_verified")
                else:
                    circuit = self._circuit()
                    nets, parts = circuit.nets(), {x["ref"]: x for x in circuit.components()}
                    levels.append("file_verified")
                if kind == "connected":
                    pins = [tuple(x.rsplit(".", 1)) if isinstance(x, str) else tuple(x) for x in assertion["pins"]]
                    passed = any(set(pins) <= {tuple(pin) for pin in net} for net in nets)
                    actual = nets
                elif kind == "isolated":
                    first = tuple(assertion["first"].rsplit(".", 1)) if isinstance(assertion["first"], str) else tuple(assertion["first"])
                    second = tuple(assertion["second"].rsplit(".", 1)) if isinstance(assertion["second"], str) else tuple(assertion["second"])
                    known = {tuple(pin) for net in nets for pin in net}
                    passed = first in known and second in known and not any({first, second} <= {tuple(pin) for pin in net} for net in nets)
                    actual = nets
                else:
                    part = parts.get(assertion["ref"])
                    def matches(actual, expected):
                        return isinstance(actual, dict) and all(matches(actual.get(k), v) if isinstance(v, dict) else actual.get(k) == v for k, v in expected.items())
                    passed = part is not None and matches(part, assertion["fields"])
                    actual = part
            elif kind == "csv_range":
                _need(record["kind"] == "graph_csv" and record.get("simulated") is True and record.get("run_status") == "runtime_observed", "Fresh re-simulated graph CSV from a completed sequence is required")
                actual = self._api().sample_graph(data, assertion["trace"], assertion["x"], occurrence=assertion.get("occurrence", 0))
                passed = assertion["minimum"] <= actual <= assertion["maximum"]
                levels.append("runtime_verified")
            elif kind == "gpio_sequence":
                _need(record["kind"] == "gpio_events" and record.get("run_status") == "runtime_observed", "GPIO verification requires actual native event data from a completed sequence")
                raw_record, raw_path = self._complete_log(record, data)
                cutoff = data.get("through_simulation_seconds")
                _need(type(cutoff) in (int, float) and math.isfinite(cutoff) and cutoff >= 0
                      and data.get("scope") == "event_timestamp_prefix", "Missing independently observed GPIO cutoff")
                # Reparse actual raw bytes, rather than trusting a derived event
                # list or an expected value written into a step result.
                encoding = raw_record.get("encoding", "utf-8")
                _need(encoding in {"utf-8", "utf-8-sig", "ascii", "cp1252", "mbcs"}, "Unknown native log encoding")
                decode_encoding = "utf-8-sig" if encoding == "utf-8" else encoding
                parsed = self._api().gpio_events(raw_path.read_bytes().decode(decode_encoding, errors="replace"), **data.get("filters", {}))
                prefix = [event for event in parsed if event["seconds"] <= cutoff]
                _need(prefix == data.get("events"), "Derived GPIO events differ from their raw-log prefix")
                events = [x for x in prefix if x["ref"] == assertion["ref"] and x["port"] == assertion["port"] and x["pin"] == assertion["pin"]]
                actual = []
                previous_seconds = -1.0
                for event in events:
                    _need(type(event.get("seconds")) in (int, float) and math.isfinite(event["seconds"])
                          and event["seconds"] >= previous_seconds, "Native GPIO timestamps must be finite and monotonic")
                    previous_seconds = event["seconds"]
                    if not actual or actual[-1] != event["value"]:
                        actual.append(event["value"])
                wanted = assertion["values"]
                passed = any(actual[i:i+len(wanted)] == wanted for i in range(len(actual)-len(wanted)+1))
                levels.append("runtime_verified")
            elif kind == "simulation_time":
                _need(record["kind"] == "native_run", "Time verification requires a native run artifact")
                _need(data["status"] == "runtime_observed", "Native sequence did not complete successfully")
                step = data["steps"][assertion["step"]]
                observed = step.get("data", {})
                actual = observed.get("actual_elapsed_seconds")
                passed = step["op"] == "run_for" and observed.get("actual_time_verified") is True and type(actual) in (int, float) and abs(actual-assertion["seconds"]) <= assertion["tolerance_seconds"]
                levels.append("runtime_verified")
            elif kind == "no_errors":
                _need(record["kind"] == "simulation_errors" and record.get("run_status") == "runtime_observed", "Select an actual errors observation from a completed sequence")
                self._complete_log(record, data)
                actual, passed = data.get("messages"), data.get("messages") == []
                levels.append("native_verified")
            checks.append({"type": kind, "passed": passed, "actual": actual, "expected": assertion})
        passed = all(check["passed"] for check in checks)
        rank = {"file_verified": 0, "native_verified": 1, "runtime_verified": 2}
        # A mixed claim is only as strong as its weakest basis; checks retain per-assertion evidence.
        status = min(levels, key=rank.get) if passed else "failed"
        report = {"passed": passed, "checks": checks, "levels": levels, "revision": self.state["current"]["revision"]}
        path = self.path("verification/" + uuid.uuid4().hex + ".json")
        _write(path, report)
        self.record(path, "verification")
        return status, report, {}


def execute_request(payload, task_root, inputs=None, allowed=ACTIONS, **dependencies):
    return DesignTask(task_root, inputs, **dependencies).handle(payload, allowed)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task-root", required=True, type=Path)
    parser.add_argument("--inputs-file", type=Path)
    parser.add_argument("--allow", nargs="+", choices=sorted(ACTIONS), default=sorted(FILE_ACTIONS))
    args = parser.parse_args(argv)
    try:
        raw = sys.stdin.read(2_000_001)
        _need(len(raw) <= 2_000_000, "Design request exceeds the input size limit")
        payload = json.loads(raw, parse_constant=lambda value: (_ for _ in ()).throw(ValueError("Non-finite JSON number")))
        inputs = json.loads(args.inputs_file.read_text(encoding="utf8")) if args.inputs_file else {}
        result = execute_request(payload, args.task_root, inputs, frozenset(args.allow))
    except (OSError, ValueError, KeyError, TypeError, ImportError) as exc:
        result = {"schema": SCHEMA, "status": "blocked", "error": {"type": type(exc).__name__, "message": str(exc)}}
    print(json.dumps(result, ensure_ascii=False, default=_json_default, allow_nan=False))
    return 0 if result["status"] not in {"blocked", "unsupported", "failed"} else 2


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf8")
    raise SystemExit(main())
