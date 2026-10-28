"""Read-only firmware identity and model-event parsing, independent of Windows.

CM3 event syntax follows the MIT Proteus_automatic_package simulation adapter;
see fish_proteus/_vendor/proteus_auto/NOTICE.md and LICENSE.upstream.
"""
from __future__ import annotations

import hashlib
import math
from pathlib import Path
import re
import struct
import zipfile

MAX_FIRMWARE_BYTES = 64 * 1024 * 1024


def _hex_info(data: bytes) -> dict:
    try:
        lines = data.decode("ascii").splitlines()
    except UnicodeDecodeError as error:
        raise ValueError("Intel HEX must be ASCII") from error
    ended, upper, count, ranges = False, 0, 0, []
    for line in lines:
        if not line.strip():
            continue
        if ended or not re.fullmatch(r":[0-9a-fA-F]+", line):
            raise ValueError("Invalid Intel HEX record or data after EOF")
        try:
            record = bytes.fromhex(line[1:])
        except ValueError as error:
            raise ValueError("Invalid Intel HEX hex digits") from error
        if len(record) < 5 or len(record) != record[0] + 5 or sum(record) % 256:
            raise ValueError("Invalid Intel HEX length/checksum")
        size, address, kind = record[0], int.from_bytes(record[1:3], "big"), record[3]
        if kind not in range(6):
            raise ValueError("Unsupported Intel HEX record type")
        if kind and (address != 0 or size != {1: 0, 2: 2, 3: 4, 4: 2, 5: 4}[kind]):
            raise ValueError("Invalid Intel HEX control record")
        if kind == 0:
            start = upper + address
            if start + size > 2**32:
                raise ValueError("Out-of-range Intel HEX data")
            if size:
                ranges.append((start, start + size))
            count += size
        elif kind == 1:
            ended = True
        elif kind in (2, 4):
            upper = int.from_bytes(record[4:-1], "big") << (4 if kind == 2 else 16)
    if not ended:
        raise ValueError("Intel HEX is missing EOF")
    ranges.sort()
    if any(left[1] > right[0] for left, right in zip(ranges, ranges[1:])):
        raise ValueError("Overlapping Intel HEX data")
    if not ranges:
        raise ValueError("Intel HEX contains no firmware data")
    return {"data_bytes": count, "address_range": [ranges[0][0], max(end for _, end in ranges)],
            "checksum_verified": True}


def _elf_info(data: bytes) -> dict:
    if len(data) < 16 or data[:4] != b"\x7fELF" or data[4] not in (1, 2) or data[5] not in (1, 2) or data[6] != 1:
        raise ValueError("Invalid ELF identification")
    bits, endian = (32 if data[4] == 1 else 64), ("<" if data[5] == 1 else ">")
    layout = "HHIIIIIHHHHHH" if bits == 32 else "HHIQQQIHHHHHH"
    size = 52 if bits == 32 else 64
    if len(data) < size:
        raise ValueError("Truncated ELF header")
    values = struct.unpack_from(endian + layout, data, 16)
    kind, machine, version, entry, phoff, shoff, flags, ehsize, phentsize, phnum, shentsize, shnum, shstrndx = values
    if version != 1 or ehsize != size or kind not in (1, 2, 3):
        raise ValueError("Invalid ELF header fields")
    if phnum == 65535 or shnum == 0 and shoff or shstrndx == 65535:
        raise ValueError("Extended ELF table numbering is unsupported")
    if phnum and (phentsize != (32 if bits == 32 else 56) or phoff < size or phoff + phnum * phentsize > len(data)):
        raise ValueError("ELF program table outside file")
    if shnum and (shentsize != (40 if bits == 32 else 64) or shoff < size or shoff + shnum * shentsize > len(data)):
        raise ValueError("ELF section table outside file")
    if shnum and shstrndx >= shnum:
        raise ValueError("ELF section name table index outside table")
    for index in range(shnum):
        fields = struct.unpack_from(endian + ("IIIIIIIIII" if bits == 32 else "IIQQQQIIQQ"),
                                    data, shoff + index * shentsize)
        section_type, offset, section_size = fields[1], fields[4], fields[5]
        if section_type != 8 and offset + section_size > len(data):
            raise ValueError("ELF section outside file")
    for index in range(phnum):
        fields = struct.unpack_from(endian + ("IIIIIIII" if bits == 32 else "IIQQQQQQ"), data, phoff + index * phentsize)
        if bits == 32:
            segment_type, offset, _, _, filesz, memsz, _, _ = fields
        else:
            segment_type, _, offset, _, _, filesz, memsz, _ = fields
        if offset + filesz > len(data) or segment_type == 1 and filesz > memsz:
            raise ValueError("ELF segment outside file or invalid memory size")
    return {"machine": machine, "bits": bits, "entry": entry,
            "program_segments": phnum, "container_bounds_verified": True}


def firmware_info(path) -> dict:
    """Inspect actual bytes; header validity does not prove CPU compatibility."""
    path = Path(path).resolve(strict=True)
    size = path.stat().st_size
    if not path.is_file() or not 0 < size <= MAX_FIRMWARE_BYTES:
        raise ValueError("Firmware must be a nonempty file of at most 64 MiB")
    data, suffix = path.read_bytes(), path.suffix.lower()
    result = {"path": str(path), "size": len(data), "format": suffix[1:],
              "sha256": hashlib.sha256(data).hexdigest(), "format_verified": False}
    if suffix == ".elf":
        result.update(_elf_info(data), format_verified=True)
    elif suffix == ".hex":
        result.update(_hex_info(data), format_verified=True)
    elif suffix not in (".bin", ".cof", ".coff", ".cdb"):
        raise ValueError(f"Unsupported firmware extension: {suffix}")
    return result


def extract_firmware(project, destination, member=None) -> dict:
    """Extract a single explicitly selected image, never project build scripts."""
    destination = Path(destination).resolve()
    if destination.exists():
        raise FileExistsError(destination)
    with zipfile.ZipFile(project) as archive:
        candidates = [entry for entry in archive.infolist() if entry.filename.startswith("FIRMWARE/")
                      and Path(entry.filename).suffix.lower() in (".elf", ".hex", ".cof", ".coff", ".cdb", ".bin")]
        if member is None:
            if len(candidates) != 1:
                raise ValueError("Choose an exact firmware member")
            member = candidates[0].filename
        matches = [entry for entry in candidates if entry.filename == member]
        if len(matches) != 1 or not 0 < matches[0].file_size <= MAX_FIRMWARE_BYTES:
            raise ValueError("Missing, ambiguous or oversized embedded firmware")
        if destination.suffix.lower() != Path(member).suffix.lower():
            raise ValueError("Destination must preserve the firmware extension")
        data = archive.read(matches[0])
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("xb") as output:
        output.write(data)
    try:
        result = firmware_info(destination)
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    return dict(result, member=member)


def gpio_events(log, ref=None, port=None, pin=None) -> list[dict]:
    """Decode Copy All and native LOGFILE CM3 events without inventing time.

    Native #T messages carry following %T/%S/%E metadata. A final event without
    its complete metadata is ignored. Collection completeness is a separate
    session property; last event time is never the current simulation clock.
    """
    pattern = r"\[GPIO\] drive PIO(\d+)\.(\d+) = ([01]) \[([^\]]+)_SYSINTERFACE\] @(\S+)"
    events = []
    def seconds_from(clock):
        if not re.fullmatch(r"\d+:\d{2}:\d{2}(?:\.\d+)?|\d+(?:\.\d+)?(?:[eE][+-]?\d+)?s?", clock):
            raise ValueError("Invalid native GPIO event time")
        if ":" in clock:
            hours, minutes, seconds = map(float, clock.split(":"))
            if minutes >= 60 or seconds >= 60:
                raise ValueError("Invalid native GPIO event time")
            seconds += hours * 3600 + minutes * 60
        else:
            seconds = float(clock.removesuffix("s"))
        if not math.isfinite(seconds) or seconds < 0:
            raise ValueError("Invalid native GPIO event time")
        return seconds
    def append(position, component, p, n, value, clock):
        event = {"ref": component, "port": int(p), "pin": int(n), "value": int(value),
                 "seconds": seconds_from(clock)}
        if all(wanted is None or wanted == event[key] for wanted, key in ((ref, "ref"), (port, "port"), (pin, "pin"))):
            events.append((position, event))
    for match in re.finditer(pattern, log):
        p, n, value, component, clock = match.groups()
        append(match.start(), component, p, n, value, clock)
    pending, metadata, position = None, {}, 0
    def finish():
        if pending is None or not {"T", "S", "E"} <= metadata.keys():
            return
        match = re.fullmatch(r"\[GPIO\] drive PIO(\d+)\.(\d+) = ([01])", pending[1])
        source = re.fullmatch(r"(.+)_SYSINTERFACE", metadata["S"])
        if match and source and re.fullmatch(r"[0-9A-Fa-f]+", metadata["E"]):
            append(pending[0], source[1], *match.groups(), metadata["T"])
    for raw in log.splitlines(keepends=True):
        line = raw.rstrip('\r\n')
        header = re.fullmatch(r"#([A-Z]):(.*)", line)
        if header:
            finish()
            pending, metadata = ((position, header[2]) if header[1] == 'T' else None), {}
        elif re.fullmatch(r"%[TSE]=.*", line) and pending is not None:
            key, value = line[1:].split('=', 1)
            if key in metadata and metadata[key] != value:
                raise ValueError("Conflicting native GPIO metadata")
            metadata[key] = value
        elif line and not line.startswith('%'):
            finish()
            pending, metadata = None, {}
        position += len(raw)
    if log.endswith(('\n', '\r')):
        finish()
    return [event for _, event in sorted(events, key=lambda item: item[0])]
