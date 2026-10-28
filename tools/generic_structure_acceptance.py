"""Independent offline structural acceptance, with a queue for native SDF checks.

This tool never launches Proteus. Its successful status is ``file_verified``;
only a separately captured native netlist can establish native acceptance.
Installed definitions and generated proprietary project files stay local.
"""
from __future__ import annotations

import argparse
import ast
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
from zipfile import ZipFile
import xml.etree.ElementTree as ET
from unittest.mock import patch

REPOSITORY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY))


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def jsonable(value):
    if isinstance(value, dict):
        return {str(key) if isinstance(key, str) else json.dumps(key): jsonable(item)
                for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [jsonable(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    return value


def write_json(path, value):
    Path(path).write_text(json.dumps(jsonable(value), ensure_ascii=False, indent=2) + "\n",
                          encoding="utf-8")


def canonical_groups(groups):
    """Canonicalize a partition and reject duplicated membership, not just missing pins."""
    result, seen = [], set()
    for group in groups:
        normalized = [item if isinstance(item, str) else ".".join(item) for item in group]
        if not normalized or len(set(normalized)) != len(normalized):
            raise AssertionError("Empty net or repeated endpoint in one net")
        if set(normalized) & seen:
            raise AssertionError("One endpoint occurs in several nets")
        seen.update(normalized)
        result.append(tuple(sorted(normalized)))
    return sorted(result)


def assert_partition(actual, expected):
    """Compare all specified pins, including expected isolated pins and forbidden bridges."""
    intended = canonical_groups(expected)
    universe = {pin for group in intended for pin in group}
    actual = canonical_groups(actual)
    projected = [tuple(pin for pin in group if pin in universe) for group in actual]
    projected = sorted(group for group in projected if group)
    if projected != intended:
        raise AssertionError(f"Net partition differs: expected {intended!r}, got {projected!r}")
    return len(universe)


def compare_native_graph(graph, expected):
    """Compare parsed SDF to an authored intent; this does not attest capture provenance.

    ``expected`` contains parts and optional net_groups expressed as REF.PIN.
    Exact net names are immaterial. Physical pin numbers must be specified by
    the caller; logical names are never guessed into physical numbers.
    """
    actual_parts = graph["parts"]
    intended = expected.get("parts", {})
    if expected.get("exact_parts", True) and set(actual_parts) != set(intended):
        raise AssertionError("Native part references differ from intent")
    for ref, fields in intended.items():
        if ref not in actual_parts:
            raise AssertionError("Missing native part: " + ref)
        for field in ("device", "value"):
            if field in fields and actual_parts[ref].get(field) != fields[field]:
                raise AssertionError(f"Native {ref}.{field} differs")
        for key, value in fields.get("properties", {}).items():
            if actual_parts[ref].get("properties", {}).get(key) != value:
                raise AssertionError(f"Native {ref}.{key} differs")
    checked = 0
    if "net_groups" in expected:
        groups = [[f"{pin['ref']}.{pin['pin']}" for pin in net["pins"]]
                  for net in graph["nets"] if net.get("pins")]
        checked = assert_partition(groups, expected["net_groups"])
    return {"status": "matched", "parts_checked": len(intended), "pins_checked": checked,
            "provenance_verified": False, "runtime_status": "not_run"}


def semantic_snapshot(circuit):
    components = sorted(circuit.components(), key=lambda row: row["ref"])
    pins = {row["ref"]: circuit.pins(row["ref"]) for row in components}
    # A decoded terminal belongs to its physical net. Its arbitrary representative
    # pin can change after serialization even when every wire and glyph survives.
    representatives = {tuple(pin): sorted(group)[0]
                       for group in circuit.nets(physical=True) for pin in group}
    terminals = []
    for row in circuit.terminals():
        item = {key: row.get(key) for key in ("kind", "name", "pin")}
        if row.get("pin") is not None:
            item["pin"] = representatives[tuple(row["pin"])]
        if row.get("pin") is None:
            item["position"] = row.get("position")
            item["rotation"] = row.get("rotation")
        terminals.append(item)
    return jsonable({"components": components, "pins": pins,
                     "nets": canonical_groups(circuit.nets()),
                     "terminals": sorted(terminals, key=lambda row: json.dumps(jsonable(row), sort_keys=True)),
                     "wire_labels": sorted([(row["text"], representatives.get(tuple(row["owner"]), row["owner"]))
                                            for row in circuit.wire_labels()]),
                     "power": circuit.power_rails()})


def geometry_snapshot(project):
    """Compare actual decoded geometry while ignoring archive/object byte offsets."""
    from fish_proteus.automation import Project, decode_net_objects
    graph = decode_net_objects(Project(project))
    if not graph["complete"] or not graph["rebuild_complete"]:
        raise AssertionError("Generated geometry was not fully recognized")
    wires = [{"points": row["points"],
              "labels": [{key: label[key] for key in ("text", "position", "tail_hex")}
                         for label in row["labels"]]} for row in graph["wires"]]
    terminals = [{key: row[key] for key in ("kind", "name", "position", "rotation", "contact")}
                 for row in graph["terminals"]]
    return jsonable({"wires": sorted(wires, key=lambda row: json.dumps(jsonable(row), sort_keys=True)),
                     "terminals": sorted(terminals, key=lambda row: json.dumps(jsonable(row), sort_keys=True))})


def vendor_dependency_audit(root=REPOSITORY):
    """Resolve relative imports with AST only, so Windows DLL code is never imported."""
    package = Path(root) / "fish_proteus" / "_vendor" / "proteus_auto"
    unresolved, external = [], set()
    for path in sorted(package.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        module = "fish_proteus._vendor.proteus_auto"
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.level:
                target = importlib.util.resolve_name("." * node.level + (node.module or ""), module)
                candidate = Path(root).joinpath(*target.split("."))
                if not candidate.with_suffix(".py").is_file() and not (candidate / "__init__.py").is_file():
                    unresolved.append({"source": path.name, "line": node.lineno, "target": target})
            elif isinstance(node, ast.Import):
                external.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                external.add(node.module.split(".")[0])
    manifest = json.loads((package / "PROVENANCE.json").read_text(encoding="utf-8"))
    expected_modules = {row["path"] for row in manifest["files"]} | {"__init__.py"}
    actual_modules = {path.name for path in package.glob("*.py")}
    if expected_modules != actual_modules:
        raise AssertionError("Vendor module set differs from its provenance manifest")
    if manifest["commit"] != "7439819a7ea4cff47fb9b321d8b0e97ac74fafb2":
        raise AssertionError("Vendor source does not match the reviewed pinned commit")
    if not (package / "LICENSE.upstream").is_file() or not (package / "NOTICE.md").is_file():
        raise AssertionError("Vendor license or scope/modification notice is missing")
    mismatches = [row["path"] for row in manifest["files"]
                  if sha256(package / row["path"]) != row["adapted_sha256"]]
    local_dependencies = sorted(name for name in external if
                                (Path(root) / name / "__init__.py").is_file() or
                                (Path(root) / name).with_suffix(".py").is_file())
    third_party = sorted(name for name in external if
                         name not in sys.stdlib_module_names and name not in local_dependencies)
    if unresolved or mismatches or third_party:
        raise AssertionError(json.dumps({"unresolved_imports": unresolved,
                                         "provenance_hash_mismatches": mismatches,
                                         "non_stdlib_imports": third_party}))
    return {"status": "passed", "modules": len(list(package.glob("*.py"))),
            "upstream_commit": manifest["commit"], "license_present": (package / "LICENSE.upstream").is_file(),
            "scope_notice_present": (package / "NOTICE.md").is_file(),
            "relative_imports_resolved": True, "local_dependencies": local_dependencies,
            "non_stdlib_imports": third_party}


def run_acceptance(output, config=None):
    from fish_proteus.automation import Circuit, Library, ProteusConfig
    from fish_proteus._vendor.proteus_auto.proteus_project import UnsupportedFormat

    config = config or ProteusConfig.discover()
    config.require("library_root", "template_project")
    output = config.check_destination(output)
    if output.exists():
        raise ValueError("Choose an unused output directory; acceptance evidence is immutable")
    output.mkdir(parents=True)
    sources = {str(config.template_project): sha256(config.template_project)}
    results, native_queue = [], []

    def check(condition, message):
        if not condition:
            raise AssertionError(message)

    def reject(circuit, operation):
        before = circuit.revision
        try:
            operation()
        except (ValueError, KeyError, UnsupportedFormat):
            check(circuit.revision == before, "Rejected operation partially mutated the circuit")
        else:
            raise AssertionError("Invalid operation was accepted")

    def case(name, function):
        folder = output / name
        folder.mkdir()
        row = {"name": name, "native_status": "not_run", "runtime_status": "not_run"}
        try:
            row.update(function(folder) or {})
            row["status"] = "file_verified"
        except Exception as error:
            row.update(status="failed", error_type=type(error).__name__, error=str(error))
        results.append(row)
        write_json(folder / "result.json", row)
        return row

    def save_roundtrip(circuit, folder, expected, filename="circuit.pdsprj", *, open_config=None):
        before = semantic_snapshot(circuit)
        path = circuit.save(folder / filename)
        reopened = Circuit.open(path, config=open_config or config)
        after = semantic_snapshot(reopened)
        write_json(folder / (path.stem + "-before.json"), before)
        write_json(folder / (path.stem + "-after.json"), after)
        write_json(folder / (path.stem + "-expected.json"), expected)
        check(before == after, "Save/reopen changed semantic state; compare before/after evidence")
        if "net_groups" in expected:
            assert_partition(reopened.nets(), expected["net_groups"])
        native_queue.append({"project": str(path), "sha256": sha256(path),
                             "expected": str(folder / (path.stem + "-expected.json")),
                             "native_status": "not_run"})
        return reopened, path

    def catalogue(folder):
        library = Library(config=config)
        devices = [("RESISTOR", "ASIMMDLS", "R1", "4k7"),
                   ("RES", "DEVICE", "R2", "22k"),
                   ("CAPACITOR", "ASIMMDLS", "C1", "47n"),
                   ("1N4007", "DIODE", "D1", "1N4007"),
                   ("2N2222", "BIPOLAR", "Q1", "2N2222"),
                   ("RELAY", "ACTIVE", "RL1", "RELAY"),
                   ("LED-YELLOW", "ACTIVE", "D2", "LED-YELLOW"),
                   ("ULN2003A", "ANALOG", "U1", "ULN2003A"),
                   ("ATMEGA328P", "AVR2", "U2", "ATMEGA328P")]
        c, metadata, intended = Circuit(config=config), [], {}
        for index, (device, lib, ref, value) in enumerate(devices):
            item = library.get(device, library=lib)
            sources.setdefault(item["path"], sha256(item["path"]))
            check(item["simulation_verified"] is False, "Lookup cannot certify simulation")
            check(item["pin_parse_status"] == "parsed" and item["pins"], "Missing actual pin definition")
            metadata.append(item)
            if device not in c.templates:
                c.import_device(device, library=lib)
            # Center the catalogue on one page. The taller ATmega symbol on
            # the last row needs extra clearance above it (its top pin is
            # 4572000 native units above its instance origin).
            x = (-5080000, 0, 5080000)[index % 3]
            y = (-5080000, 0, 7620000)[index // 3]
            c.add(device, ref, value, x, y)
            if device == "RES":
                c.update(ref, label_offsets={"reference": (-508000, -762000)})
            elif ref in {"U1", "U2"}:
                # Native Y increases upward: keep the two tall symbols' text
                # above their bodies, clear of the COM and PD0 pin labels.
                c.update(ref, label_offsets={"reference": (254000, 762000),
                                             "value": (254000, 406400)})
            intended[ref] = {"device": device, "value": value}
        for name in ("CAPACITOR", "1N4007"):
            try:
                library.get(name)
            except UnsupportedFormat:
                pass
            else:
                raise AssertionError("Ambiguous library choice was guessed: " + name)
        reject(c, lambda: c.import_device("FISH_NONEXISTENT_PART_2026"))
        save_roundtrip(c, folder, {"parts": intended, "exact_parts": True})
        write_json(folder / "metadata.json", metadata)
        return {"gates": ["G01", "G02"], "lookups": len(metadata),
                "simulation_status": "not_run", "ambiguous_lookup_rejected": True,
                "catalogue_layout": "centered three columns by three rows",
                "native_visual_status": "not_run"}

    def buses(folder):
        c = Circuit(config=config)
        for index in range(1, 7):
            c.add("CAPACITOR", f"C{index}", "100n", (index - 1) * 5080000, 0)
        for pin in ("1", "2"):
            for index in range(2, 7):
                c.connect(f"C1.{pin}", f"C{index}.{pin}")
        c.add_wire_label("C3.1", "C1.1", "WIRE_KEEP")
        top = [f"C{i}.1" for i in range(1, 7)]
        bottom = [f"C{i}.2" for i in range(1, 7)]
        c.add_terminal("power", "VTEST", "C1.1")
        c.add_terminal("ground", "", "C1.2")
        for kind, ref in (("label", "C2.1"), ("input", "C3.1"),
                          ("output", "C4.1"), ("bidir", "C5.1")):
            c.add_terminal(kind, "BUS_TOP", ref)
        c.add_terminal("input", "ENABLE", position=(-5080000, 5080000), rotation=90)
        c.configure_power({"GND": 0, "VTEST": 3.3}, {"VDD": "VTEST", "VSS": "GND"})
        expected = {"parts": {f"C{i}": {"device": "CAPACITOR", "value": "100n"}
                              for i in range(1, 7)}, "net_groups": [top, bottom],
                    "terminal_kinds": ["ground", "power", "label", "input", "output", "bidir"]}
        assert_partition(c.nets(), expected["net_groups"])
        reopened, path = save_roundtrip(c, folder, expected, "six-way.pdsprj")
        revision = reopened.revision
        check(reopened.revision == revision, "Opened multiway revision is unstable")
        json.dumps(reopened.inspect())  # Must work without a custom encoder.
        detached_snapshot = reopened.connections()
        detached_snapshot.clear()
        check(reopened.revision == revision, "Public connection snapshot mutated the circuit")
        moved = Circuit.open(path, config=config)
        moved.move("C6", 25_908_000, 0)
        check(moved.revision != revision, "Moving a routed multiway component kept its old revision")
        write_json(folder / "multiway-revisions.json", {"opened": revision, "moved": moved.revision,
                                                        "inspect_json_serializable": True})
        check({row["kind"] for row in reopened.terminals()} == set(expected["terminal_kinds"]),
              "A terminal kind disappeared")
        unchanged_hash = sha256(path)
        preserved_geometry = geometry_snapshot(path)
        preserved = reopened.save(folder / "existing-preserved.pdsprj")
        check(geometry_snapshot(preserved) == preserved_geometry,
              "Existing project rewrite changed wire, terminal, or label geometry")
        native_queue.append({"project": str(preserved), "sha256": sha256(preserved),
                             "expected": str(folder / "six-way-expected.json"), "native_status": "not_run"})
        # Anchor removal must keep five surviving branches connected, not discard the bus.
        reopened.rename("C6", "C_SIX6")
        reopened.update("C_SIX6", value="220n", properties={"API_NOTE": "variable length text"})
        reopened.delete_component("C1")
        names = ["C2", "C3", "C4", "C5", "C_SIX6"]
        edited = {"parts": {ref: {"device": "CAPACITOR", "value": "220n" if ref == "C_SIX6" else "100n"}
                            for ref in names}, "net_groups": [[f"{ref}.{pin}" for ref in names] for pin in (1, 2)]}
        assert_partition(reopened.nets(), edited["net_groups"])
        five, _ = save_roundtrip(reopened, folder, edited, "surviving-five.pdsprj")
        check([row["text"] for row in five.wire_labels()] == ["WIRE_KEEP"],
              "Deleting a bus anchor lost or duplicated the surviving branch label")
        five.disconnect("C5.1")
        four = copy.deepcopy(edited)
        four["net_groups"] = [[f"{ref}.1" for ref in names if ref != "C5"], ["C5.1"],
                              [f"{ref}.2" for ref in names]]
        four_saved, _ = save_roundtrip(five, folder, four, "detached-four.pdsprj")
        four_saved.disconnect("C4.1")
        three = copy.deepcopy(four)
        three["net_groups"] = [[f"{ref}.1" for ref in names if ref not in ("C4", "C5")],
                               ["C4.1"], ["C5.1"], [f"{ref}.2" for ref in names]]
        three_saved, _ = save_roundtrip(four_saved, folder, three, "detached-three.pdsprj")
        check([row["text"] for row in three_saved.wire_labels()] == ["WIRE_KEEP"],
              "Branch detach lost or duplicated the label on C3.1")
        check(sha256(path) == unchanged_hash, "Editing a loaded project changed the source file")
        return {"gates": ["G03", "G04", "G05", "G06"], "six_way_and_surviving_five": True,
                "all_six_terminal_kinds": True, "native_sdf_pending": True}

    def label_merging(folder):
        c = Circuit(config=config)
        for index, (x, y) in enumerate(((0, 0), (5080000, 0), (0, 5080000), (5080000, 5080000)), 1):
            c.add("RESISTOR", f"R{index}", "10k", x, y)
        first_pin = {row["name"]: row["position"] for row in c.pins("R1")}
        second_pin = {row["name"]: row["position"] for row in c.pins("R2")}
        c.connect("R1.2", "R2.1", points=[first_pin["2"], second_pin["1"]])
        c.connect("R3.2", "R4.1")
        c.add_wire_label("R1.2", "R2.1", "REMOTE_JOIN", position=(2540000, -254000))
        c.add_wire_label("R3.2", "R4.1", "REMOTE_JOIN")
        parts = {f"R{i}": {"device": "RESISTOR", "value": "10k"} for i in range(1, 5)}
        merged = {"parts": parts, "net_groups": [["R1.2", "R2.1", "R3.2", "R4.1"],
                                                  ["R1.1"], ["R2.2"], ["R3.1"], ["R4.2"]]}
        assert_partition(c.nets(physical=True), [["R1.2", "R2.1"], ["R3.2", "R4.1"]])
        reopened, path = save_roundtrip(c, folder, merged, "same-name-merged.pdsprj")
        before_geometry = geometry_snapshot(path)
        preserved = reopened.save(folder / "preserved.pdsprj")
        check(geometry_snapshot(preserved) == before_geometry, "Rewriting changed manual route/explicit label geometry")
        reopened.remove_wire_label("R1.2", "R2.1", "REMOTE_JOIN")
        separated = {"parts": parts,
                     "net_groups": [["R1.2", "R2.1"], ["R3.2", "R4.1"],
                                    ["R1.1"], ["R2.2"], ["R3.1"], ["R4.2"]]}
        save_roundtrip(reopened, folder, separated, "label-removed.pdsprj")
        check(len(reopened.wire_labels()) == 1, "Removal touched the other physical net")
        return {"gates": ["G04", "G05", "G06"], "wire_label_merges_disjoint_geometry": True,
                "remove_preserves_physical_connections": True, "manual_geometry_preserved": True}

    def component_edits(folder):
        c = Circuit(config=config)
        c.add("RESISTOR", "R1", "1k", 0, 0)
        c.copy_component("R1", "R22", 5080000, 5080000)
        c.rename("R22", "R_VARIABLE22")
        c.update("R_VARIABLE22", value="123.456k", properties={"API_NOTE": "long original property"},
                 label_offsets={"value": (762000, -508000)})
        c.move("R_VARIABLE22", 7620000, 2540000)
        c.rotate("R_VARIABLE22", 90)
        c.mirror("R_VARIABLE22", "x")
        expected = {"parts": {"R1": {"device": "RESISTOR", "value": "1k"},
                               "R_VARIABLE22": {"device": "RESISTOR", "value": "123.456k",
                                                 "properties": {"API_NOTE": "long original property"}}}}
        for operation in (lambda: c.update("R1", x=True), lambda: c.rotate("R1", 17),
                          lambda: c.rename("R1", "R_VARIABLE22"), lambda: c.update("R1", properties={"bad": "x"}),
                          lambda: c.connect("R1.unknown", "R_VARIABLE22.1"),
                          lambda: c.connect("R1.1", "R1.1")):
            reject(c, operation)
        saved, path = save_roundtrip(c, folder, expected)
        check(next(row for row in saved.components() if row["ref"] == "R_VARIABLE22")["position"]
              == {"x": 7620000, "y": 2540000}, "Move was not absolute")
        before = sha256(path)
        try:
            c.save(path)
        except UnsupportedFormat:
            pass
        else:
            raise AssertionError("Existing destination was silently overwritten")
        check(sha256(path) == before, "Rejected overwrite altered destination")
        return {"gates": ["G03", "G14"], "invalid_edits_atomic": True, "no_clobber": True}

    def empty_fallback(folder):
        template = folder / "configured-template.pdsprj"
        template.write_bytes(config.template_project.read_bytes())
        isolated = ProteusConfig(config.executable, config.library_root, config.samples_root, template)
        # Deliberately incompatible process-local discovery demonstrates that the
        # explicitly passed configuration, including empty-file fallback, is used.
        with patch.dict(os.environ, {"FISH_PROTEUS_TEMPLATE": str(folder / "missing-environment-template.pdsprj")}):
            c = Circuit(config=isolated)
            reopened, _ = save_roundtrip(c, folder, {"parts": {}, "net_groups": []}, "empty.pdsprj",
                                         open_config=isolated)
            reopened.add("RESISTOR", "R1", "10k", 0, 0)
            save_roundtrip(reopened, folder, {"parts": {"R1": {"device": "RESISTOR", "value": "10k"}}},
                           "from-empty.pdsprj", open_config=isolated)
        return {"gates": ["G05", "G06"], "configured_empty_fallback": True}

    def stale_and_unknown(folder):
        c = Circuit(config=config)
        source = c.save(folder / "source.pdsprj")
        opened = Circuit.open(source, config=config)
        with ZipFile(source, "a") as archive:
            archive.comment = b"external edit in an owned work copy"
        external_hash = sha256(source)
        target = folder / "stale-save-as.pdsprj"
        reject(opened, lambda: opened.save(target))
        check(not target.exists(), "Stale save-as created a destination")
        sentinel = folder / "existing-destination.pdsprj"
        sentinel.write_bytes(b"Owned destination must survive stale overwrite refusal")
        sentinel_hash = sha256(sentinel)
        reject(opened, lambda: opened.save(sentinel, overwrite=True))
        check(sha256(sentinel) == sentinel_hash, "Stale save-as clobbered an existing destination")
        check(sha256(source) == external_hash, "Stale save erased external source changes")
        fresh = Circuit.open(source, config=config)
        commented = fresh.save(folder / "comment-preserved.pdsprj")
        with ZipFile(commented) as archive:
            check(archive.comment == b"external edit in an owned work copy", "Archive comment was lost")
        unknown = folder / "unknown-version.pdsprj"
        with ZipFile(source) as old, ZipFile(unknown, "w") as new:
            for info in old.infolist():
                data = old.read(info.filename)
                if info.filename == "PROJECT.XML":
                    metadata = ET.fromstring(data)
                    metadata.find("TIMESTAMP").set("FILEVER", "999")
                    data = ET.tostring(metadata)
                new.writestr(info, data)
        unknown_hash = sha256(unknown)
        try:
            Circuit.open(unknown, config=config)
        except UnsupportedFormat:
            pass
        else:
            raise AssertionError("Unknown FILEVER was accepted")
        check(sha256(unknown) == unknown_hash, "Unknown input was changed")
        return {"gates": ["G06", "G14"], "stale_save_as_rejected": True,
                "stale_overwrite_preserves_destination": True, "archive_comment_preserved": True,
                "unknown_version_rejected": True}

    def revision_and_protection(folder):
        c = Circuit(config=config)
        rails = {"GND": 0, "TEST_RAIL": 3.3}
        bindings = {"VDD": "TEST_RAIL", "VSS": "GND"}
        c.configure_power(rails, bindings)
        original = c.revision
        c.configure_power(dict(rails, TEST_RAIL=5.0), bindings)
        changed = c.revision
        c.configure_power(rails, bindings)
        check(changed != original and c.revision == original, "Power revisions do not track exact state")
        for protected in (config.library_root / "rejected.pdsprj", config.template_project):
            reject(c, lambda target=protected: c.save(target, overwrite=True))
        write_json(folder / "revisions.json", {"baseline": original, "changed": changed, "restored": c.revision})
        return {"gates": ["G14"], "power_revision_change_and_restore": True,
                "installed_targets_rejected": True}

    for name, function in (("catalogue-imports", catalogue), ("six-way-buses", buses),
                           ("wire-labels", label_merging),
                           ("component-edits", component_edits), ("empty-fallback", empty_fallback),
                           ("stale-and-unknown", stale_and_unknown),
                           ("revision-protection", revision_and_protection),
                           ("vendor-dependencies", lambda _: vendor_dependency_audit())):
        case(name, function)
    unchanged = all(sha256(path) == digest for path, digest in sources.items())
    summary = {"schema": "fish-proteus.generic-structure-acceptance.v1",
               "status": "file_verified" if unchanged and all(row["status"] == "file_verified" for row in results) else "incomplete",
               "native_status": "not_run", "runtime_status": "not_run", "sources_unchanged": unchanged,
               "source_hashes": sources, "results": results, "native_queue": native_queue,
               "limits": ["Offline serialization and independent intent checks only",
                          "No native SDF was captured and no simulation was run",
                          "Definitions imported from the licensed local installation are not release artifacts"]}
    write_json(output / "acceptance.json", summary)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        summary = run_acceptance(args.output)
    except (OSError, ValueError) as error:
        print(json.dumps({"status": "blocked", "error": str(error)}))
        return 2
    print(json.dumps({key: value for key, value in summary.items()
                      if key not in ("native_queue", "source_hashes")}, ensure_ascii=False, indent=2))
    return 0 if summary["status"] == "file_verified" else 1


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
