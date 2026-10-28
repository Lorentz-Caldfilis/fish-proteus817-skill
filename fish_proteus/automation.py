"""Public, composable Proteus file API and lazy Windows runtime factories.

Coordinates use native integers: 100000 units = 1 mm. File editing accepts
only the independently recognized single-sheet layouts in the bundled codec.
An API method's existence is not a claim of device simulation support.
"""
from __future__ import annotations

import hashlib
import json
import copy
from pathlib import Path

from .config import ProteusConfig
from ._vendor.proteus_auto.component_codec import Circuit as _Circuit
from ._vendor.proteus_auto.device_library import Library as _Library, describe_definition
from ._vendor.proteus_auto.proteus_project import Project, UnsupportedFormat
from ._vendor.proteus_auto.net_objects import decode_net_objects
from ._vendor.proteus_auto.net_edit import invalidate_routes
from ._vendor.proteus_auto.measurements import (graphs, export_graph, parse_graph_csv,
                                                sample as sample_graph, generators,
                                                set_generator_properties)
from .firmware import firmware_info, extract_firmware, gpio_events
from .netlist import parse_sdf
from .simulation_options import (decode_options, rewrite_options, read_simulation_options,
                                 set_simulation_options)

UNITS_PER_MM = 100000


def _canonical(value):
    """Encode internal maps with tuple keys without dropping layout identity."""
    if isinstance(value, dict):
        items = [[_canonical(key), _canonical(item)] for key, item in value.items()]
        return {"map": sorted(items, key=lambda pair: json.dumps(pair[0], sort_keys=True))}
    if isinstance(value, (tuple, list)):
        return {"tuple" if isinstance(value, tuple) else "list": [_canonical(item) for item in value]}
    if isinstance(value, (bytes, bytearray)):
        return {"bytes_hex": value.hex()}
    if isinstance(value, Path):
        return {"path": str(value)}
    return value


def _public(value):
    if isinstance(value, dict):
        if all(isinstance(key, str) for key in value):
            return {key: _public(item) for key, item in value.items()}
        return {"native_mapping": [{"key": _public(key), "value": _public(item)}
                                   for key, item in value.items()]}
    if isinstance(value, (tuple, list)):
        return [_public(item) for item in value]
    return value


class Library(_Library):
    def __init__(self, directory=None, *, config: ProteusConfig | None = None):
        if directory is None:
            config = config or ProteusConfig.discover()
            directory = config.library_root
        self.config = config
        super().__init__(directory)

    def search(self, query="", limit=30):
        return [dict(entry, device_id=f"{entry['library']}:{entry['name']}")
                for entry in super().search(query, limit)]

    def get(self, name, library=None):
        entry, body = self.definition(name, library)
        result = describe_definition(entry, body)
        return dict(result, device_id=f"{result['library']}:{result['name']}",
                    definition_sha256=hashlib.sha256(body).hexdigest(),
                    simulation_verified=False)


class Circuit(_Circuit):
    def __init__(self, template_project=None, *, config: ProteusConfig | None = None):
        self.config = config or ProteusConfig.discover()
        super().__init__(template_project or self.config.template_project,
                         library_root=self.config.library_root,
                         fallback_template=self.config.template_project)

    @classmethod
    def open(cls, path, *, config: ProteusConfig | None = None):
        return super().open(path, config=config)

    @property
    def revision(self) -> str:
        state = {"parts": self._parts, "connections": self._connections,
                 "terminals": self._terminals, "title": self._title,
                 "dsn_sha256": hashlib.sha256(self._dsn).hexdigest(),
                 "members": {name: hashlib.sha256(data).hexdigest()
                             for name, data in self._members.items()}}
        data = json.dumps(_canonical(state), sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(self._source_digest + data).hexdigest()

    def inspect(self) -> dict:
        try:
            options = self.simulation_options()
        except UnsupportedFormat as error:
            options = {"status": "unsupported", "reason": str(error)}
        return _public({"revision": self.revision, "source_sha256": self._source_digest.hex(),
                "coordinate_unit": "proteus_native_integer", "units_per_mm": UNITS_PER_MM,
                "components": self.components(),
                "pins": {part["ref"]: self.pins(part["ref"]) for part in self.components()},
                "connections": self.connections(), "nets": self.nets(),
                "terminals": self.terminals(), "power_rails": self.power_rails(),
                "wire_labels": self.wire_labels(), "simulation_options": options})

    def simulation_options(self):
        return decode_options(self._dsn)[1]

    def configure_simulation_options(self, **properties):
        updated = rewrite_options(self._dsn, properties)
        self._dsn = updated
        self._members['ROOT.DSN'] = updated
        return self

    def _wire_edge(self, first, second):
        endpoints = (self._endpoint(first), self._endpoint(second))
        for index, edge in enumerate(self._connections):
            if {edge["first"], edge["second"]} == set(endpoints):
                return index, endpoints
        raise ValueError("Wire label requires an existing connection; inspect connections first")

    def add_wire_label(self, first, second, text, *, position=None):
        """Attach a real WIRE LABEL; auto-place on a segment unless positioned.

        The first endpoint owns the label on branched nets. This operation
        preserves the existing wire geometry and validates before committing.
        """
        if not isinstance(text, str) or not text or len(text) >= 255 or not all(32 <= ord(c) < 127 for c in text):
            raise ValueError("Wire label must be 1..254 printable ASCII characters")
        if position is not None and (not isinstance(position, (list, tuple)) or len(position) != 2 or
                                     not all(type(x) is int and -2**31 <= x < 2**31 for x in position)):
            raise ValueError("Wire label position requires two native signed integers")
        index, endpoints = self._wire_edge(first, second)
        connections = copy.deepcopy(self._connections)
        label = {"text": text, "_pin": endpoints[0], "auto_position": position is None,
                 "position": tuple(position) if position is not None else (0, 0)}
        connections[index].setdefault("labels", []).append(label)
        self._validate(self._parts, connections, self._terminals)
        self._connections = connections
        return self

    def remove_wire_label(self, first, second, text):
        """Remove a named wire label from this physical net; keep its topology."""
        _, endpoints = self._wire_edge(first, second)
        physical = next(set(net) for net in self.nets(physical=True) if endpoints[0] in net)
        connections, terminals = invalidate_routes(self._connections, self._terminals, physical)
        removed = 0
        for item in connections + terminals:
            touched = item.get("first", item.get("pin")) in physical
            if touched:
                before = item.get("labels", [])
                after = [label for label in before if label.get("text") != text]
                removed += len(before) - len(after)
                item["labels"] = after
        if not removed:
            raise ValueError("No matching wire label on the physical net")
        self._validate(self._parts, connections, terminals)
        self._connections, self._terminals = connections, terminals
        return self

    def wire_labels(self) -> list[dict]:
        result, seen = [], set()
        for item in self._connections + self._terminals:
            layout = item.get("layout") or {}
            groups = [(item.get("first", item.get("pin")), item.get("labels", []))]
            groups += list(layout.get("labels", {}).items())
            groups += [(tuple(link["first"]), link.get("labels", [])) for link in layout.get("links", [])]
            for owner, labels in groups:
                for label in labels:
                    record = dict(label, owner=label.get("_pin", owner))
                    key = json.dumps(record, sort_keys=True, separators=(",", ":"))
                    if key not in seen:
                        seen.add(key)
                        result.append(record)
        return copy.deepcopy(result)

    def save(self, destination, title=None, *, overwrite=False):
        destination = self.config.check_destination(destination)
        if hashlib.sha256(self.source.read_bytes()).digest() != self._source_digest:
            raise UnsupportedFormat("Source changed outside this Circuit; reopen it before saving")
        return super().save(destination, title, overwrite=overwrite)


def capability_report(config: ProteusConfig | None = None) -> dict:
    """Report implementation boundaries, not runtime acceptance results."""
    config = config or ProteusConfig.discover()
    return {"schema": "fish-proteus.capabilities.v1", "resources": config.describe(),
            "coordinate_unit": "proteus_native_integer", "units_per_mm": UNITS_PER_MM,
            "file_formats": {"cdb": 7, "filever": [840, 847], "user_sheets": 1},
            "domains": {"library": {"implemented": True, "runtime_verified": False},
                        "circuit": {"implemented": True, "runtime_verified": False},
                        "session": {"implemented": True, "requires": "Windows and supported build"},
                        "simulation": {"implemented": True, "requires": "validated native clock/control profile"}},
            "limits": ["No arbitrary PCB layout or new graph/probe creation",
                       "Device lookup does not establish import or simulation compatibility",
                       "Native runtime capabilities require per-build validation"]}


def Session(project, executable=None, *, config=None, logfile=None):
    from runtime_adaptation.generic import Session as RuntimeSession
    return RuntimeSession(project, executable=executable, config=config, logfile=logfile)


def Simulation(session):
    from runtime_adaptation.generic import Simulation as RuntimeSimulation
    return RuntimeSimulation(session)


__all__ = ["ProteusConfig", "Library", "Circuit", "Project", "Session", "Simulation",
           "UnsupportedFormat", "decode_net_objects", "capability_report", "UNITS_PER_MM",
           "graphs", "export_graph", "parse_graph_csv", "sample_graph", "generators",
           "set_generator_properties", "firmware_info", "extract_firmware", "gpio_events", "parse_sdf",
           "read_simulation_options", "set_simulation_options"]
