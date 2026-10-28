"""Small, deterministic artifact helpers. No Proteus process is started here."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import struct
import tempfile
from typing import Any


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: str | Path, value: Any) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    encoded = (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    descriptor, temporary = tempfile.mkstemp(prefix=".fish-json-", dir=target.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(encoded)
        os.replace(temporary, target)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def read_json(path: str | Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError("Expected a JSON object")
    return value


def mz_image(code: bytes, entry_offset: int = 0) -> bytes:
    """Wrap one relocation-free 8086 code segment in a DOS MZ image.

    The 512-byte header and CS:IP/SS:SP conventions match the supplied course
    executables. This is for the Proteus 8086 loader, not host Windows execution.
    It deliberately does not claim MASM CodeView debug-symbol compatibility.
    """
    if not code or len(code) > 65536:
        raise ValueError("MZ requires one nonempty code segment of at most 65536 bytes")
    if not isinstance(entry_offset, int) or not 0 <= entry_offset < len(code):
        raise ValueError("Entry offset must point inside the code segment")
    total = 512 + len(code)
    header = struct.pack(
        "<14H", 0x5A4D, total % 512, (total + 511) // 512,
        0, 32, 0, 0xFFFF, 0, 0, 0, entry_offset, 0, 0x1E, 0,
    )
    return header.ljust(512, b"\0") + code


def describe_mz(path: str | Path) -> dict[str, Any]:
    target = Path(path)
    data = target.read_bytes()
    if len(data) < 28 or data[:2] != b"MZ":
        raise ValueError("Not a DOS MZ executable")
    h = struct.unpack_from("<14H", data)
    image_bytes = (h[2] - 1) * 512 + (h[1] or 512)
    header_bytes = h[4] * 16
    if h[2] == 0 or header_bytes < 28 or image_bytes > len(data) or header_bytes >= image_bytes:
        raise ValueError("Invalid MZ header or truncated load image")
    entry = h[11] * 16 + h[10]
    load = data[header_bytes:image_bytes]
    if entry >= len(load):
        raise ValueError("MZ entry point lies outside its load image")
    return {
        "path": str(target.resolve()), "format": "dos-mz", "architecture": "8086",
        "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(),
        "header_bytes": header_bytes, "load_image_bytes": len(load),
        "load_image_sha256": hashlib.sha256(load).hexdigest(),
        "relocation_count": h[3], "cs": h[11], "ip": h[10],
        "ss": h[7], "sp": h[8], "entry_offset": entry,
        "trailing_bytes": len(data) - image_bytes,
    }


def mz_code(path: str | Path) -> bytes:
    information = describe_mz(path)
    data = Path(path).read_bytes()
    start = information["header_bytes"]
    return data[start:start + information["load_image_bytes"]]
