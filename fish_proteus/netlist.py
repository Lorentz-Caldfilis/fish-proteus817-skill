"""Pure parser for native logical SDF exports. No desktop is imported.

Adapted from the pinned MIT session helper; provenance and license are in
fish_proteus/_vendor/proteus_auto/NOTICE.md and LICENSE.upstream.
"""

def parse_sdf(text):
    """Parse the part/pin tables exported by the native logical SDF compiler."""
    if not text.startswith("ISIS SCHEMATIC DESCRIPTION FORMAT"):
        raise ValueError("Not an ISIS SDF netlist")
    # ponytail: exported one-line part records; reject malformed tables instead of guessing.
    def fields(line):
        result, current, quoted, pos = [], [], False, 0
        while pos < len(line):
            char = line[pos]
            if char == '"':
                if quoted and line[pos:pos + 2] == '""':
                    current.append('"')
                    pos += 1
                else:
                    quoted = not quoted
            elif char == ',' and not quoted:
                result.append(''.join(current))
                current = []
            else:
                current.append(char)
            pos += 1
        if quoted:
            raise ValueError("Unterminated SDF string")
        return result + [''.join(current)]

    def count(value):
        value = int(value)
        if not 0 <= value <= 100000:
            raise ValueError("Invalid SDF table count")
        return value

    lines = [line for line in text.splitlines() if line.strip()]
    parts, nets = {}, []
    have_parts = False
    for index, line in enumerate(lines):
        if line.startswith("*PARTLIST,"):
            size = count(line.split(",")[1])
            if have_parts or index + 1 + size > len(lines):
                raise ValueError("Duplicate or truncated SDF part table")
            have_parts = True
            for entry in lines[index + 1:index + 1 + size]:
                row = fields(entry)
                if len(row) < 3 or row[0] in parts:
                    raise ValueError("Malformed or duplicate SDF part")
                parts[row[0]] = dict(device=row[1], value=row[2], properties=dict(
                    item.split("=", 1) for item in row[3:] if "=" in item))
        if line.startswith("*NETLIST,"):
            if not have_parts:
                raise ValueError("Missing SDF part table")
            pos = index + 1
            for _ in range(count(line.split(",")[1])):
                if pos >= len(lines):
                    raise ValueError("Truncated SDF net table")
                header = fields(lines[pos])
                if len(header) < 2 or any("=" not in item for item in header[2:]):
                    raise ValueError("Malformed SDF net header")
                name, pin_count = header[:2]
                properties = dict(item.split("=", 1) for item in header[2:])
                pin_count = count(pin_count)
                pos += 1
                if pos + pin_count > len(lines):
                    raise ValueError("Truncated SDF pin table")
                pins, terminals = [], []
                for _ in range(pin_count):
                    endpoint = fields(lines[pos])
                    pos += 1
                    if len(endpoint) == 2 and endpoint[1] in {"LBL", "PT", "PR", "IT", "OT", "BT", "GT"}:
                        ref, kind = endpoint
                        terminals.append(dict(name=ref, kind=kind))
                        continue
                    elif len(endpoint) == 3:
                        ref, kind, pin = endpoint
                    else:
                        raise ValueError(f"Unsupported SDF endpoint: {endpoint}")
                    if pin is not None and ref not in parts:
                        raise ValueError(f"Unknown SDF part {ref}")
                    pins.append(dict(ref=ref, kind=kind, pin=pin))
                nets.append(dict(name=name, pins=pins, terminals=terminals, properties=properties))
            if pos != len(lines):
                raise ValueError("Unexpected records after SDF net table")
            return dict(parts=parts, nets=nets)
    raise ValueError("Missing SDF net table")

