"""Conservative project-level simulation options; no application/global settings.

Recognizes the complete counted ASCII property list at ROOT.DSN EOF. Its shape
was independently checked against installed official examples; original bytes
before the list and every other archive member are preserved.
"""
from __future__ import annotations

import copy
import hashlib
import math
import os
from pathlib import Path, PureWindowsPath
import re
import struct
import tempfile
from zipfile import ZipFile

from .config import ProteusConfig
from ._vendor.proteus_auto.proteus_project import Project, UnsupportedFormat


def decode_options(data: bytes) -> tuple[int, dict[str, str]]:
    records = {}
    for offset in range(max(0, len(data) - 30000), max(0, len(data) - 7)):
        length = struct.unpack_from('<I', data, offset)[0]
        if not 3 <= length <= 2048 or offset + 4 + length > len(data):
            continue
        fields = data[offset + 4:offset + 4 + length].split(b'\0')
        if len(fields) != 3 or fields[-1]:
            continue
        key, value = fields[:2]
        if not re.fullmatch(rb'[A-Z_][A-Z0-9_]*', key) or not all(32 <= char < 127 for char in value):
            continue
        end = offset + 4 + length
        if end in records:
            raise UnsupportedFormat('Ambiguous simulation option boundary')
        records[end] = (offset, key.decode('ascii'), value.decode('ascii'))
    end, rows = len(data), []
    while end in records:
        offset, key, value = records[end]
        rows.append((key, value))
        end = offset
    rows.reverse()
    keys = [key for key, _ in rows]
    if (end < 4 or not rows or len(rows) > 256 or len(set(keys)) != len(keys) or keys != sorted(keys)
            or not {'ABSTOL', 'LOGSTART', 'LOGTIME'} <= set(keys)
            or struct.unpack_from('<I', data, end - 4)[0] != len(rows)):
        raise UnsupportedFormat('Recognized complete simulation options at EOF are required')
    return end - 4, dict(rows)


def rewrite_options(data: bytes, properties: dict) -> bytes:
    offset, original = decode_options(data)
    if not isinstance(properties, dict) or not properties or not properties.keys() <= original.keys() | {'LOGFILE'}:
        raise ValueError('Choose existing simulation keys or LOGFILE')
    values = dict(original)
    for key, value in properties.items():
        if value is None:
            if key in {'ABSTOL', 'LOGSTART', 'LOGTIME'}:
                raise ValueError('Required simulation options cannot be removed')
            values.pop(key, None)
            continue
        if type(value) is bool:
            value = 'Yes' if value else 'No'
        elif type(value) in (int, float):
            if not math.isfinite(value):
                raise ValueError('Simulation numeric values must be finite')
            value = str(value)
        if not isinstance(value, str) or len(key) + len(value) + 2 > 2048 or not all(32 <= ord(c) < 127 for c in value):
            raise ValueError('Simulation options require bounded printable ASCII')
        if key == 'LOGFILE' and (not value or not (Path(value).is_absolute() or PureWindowsPath(value).is_absolute())):
            raise ValueError('LOGFILE requires an absolute ASCII path')
        values[key] = value
    if values == original:
        return bytes(data)
    body = struct.pack('<I', len(values))
    for key, value in sorted(values.items()):
        record = key.encode('ascii') + b'\0' + value.encode('ascii') + b'\0'
        body += struct.pack('<I', len(record)) + record
    changed = bytes(data[:offset]) + body
    if decode_options(changed) != (offset, values):
        raise UnsupportedFormat('Simulation option roundtrip mismatch')
    return changed


def read_simulation_options(project) -> dict[str, str]:
    return decode_options(bytes(Project(project)._dsn))[1]


def set_simulation_options(source, destination, properties, *, config=None, overwrite=False):
    """Atomically copy/update one known option list, preserving unknown geometry.

    LOGFILE is a trusted local caller's output path. The DSH tool chooses it on
    the host; model requests cannot supply arbitrary log destinations.
    """
    source = Path(source).resolve(strict=True)
    config = config or ProteusConfig.discover()
    destination = config.check_destination(destination)
    if destination.suffix.lower() != '.pdsprj' or type(overwrite) is not bool:
        raise ValueError('A .pdsprj destination and boolean overwrite are required')
    if destination.exists() and not overwrite:
        raise FileExistsError(destination)
    source_hash = hashlib.sha256(source.read_bytes()).digest()
    project = Project(source)
    changed = rewrite_options(bytes(project._dsn), properties)
    if destination == source and changed == bytes(project._dsn):
        return destination
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix='.fish-options-', suffix='.pdsprj', dir=destination.parent)
    os.close(descriptor)
    temporary = Path(name)
    try:
        with ZipFile(temporary, 'w') as archive:
            archive.comment = project._comment
            for info in project._infos:
                archive.writestr(copy.copy(info), changed if info.filename == 'ROOT.DSN' else project._members[info.filename])
        if Project(temporary).components() != project.components() or read_simulation_options(temporary) != decode_options(changed)[1]:
            raise UnsupportedFormat('Option update changed project structure')
        if hashlib.sha256(source.read_bytes()).digest() != source_hash:
            raise UnsupportedFormat('Source changed while updating simulation options')
        if overwrite:
            os.replace(temporary, destination)
        elif os.name == 'nt':
            os.rename(temporary, destination)
        else:
            os.link(temporary, destination)
            temporary.unlink()
    finally:
        temporary.unlink(missing_ok=True)
    return destination
