"""Install pinned portable NASM locally; never alters PATH or system installs."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import urllib.request
import zipfile

VERSION = "3.02"
URL = f"https://www.nasm.us/pub/nasm/releasebuilds/{VERSION}/win64/nasm-{VERSION}-win64.zip"
ARCHIVE_SHA256 = "161d0bfaff53c2f9e9f3e69fd0672323ebabafd1268976a5cec11be92a19aee7"


def install(directory: str | Path, archive: str | Path | None = None) -> dict:
    target = Path(directory).resolve()
    target.mkdir(parents=True, exist_ok=True)
    if archive:
        archive_path = Path(archive).resolve()
    else:
        archive_path = target / f"nasm-{VERSION}-win64.zip"
        if not archive_path.is_file():
            request = urllib.request.Request(URL, headers={"User-Agent": "FishForProteus8.17sp2-bootstrap/1"})
            with urllib.request.urlopen(request, timeout=30) as response:
                payload = response.read(32 * 1024 * 1024 + 1)
                if len(payload) > 32 * 1024 * 1024:
                    raise ValueError("NASM archive exceeds the expected maximum size")
            archive_path.write_bytes(payload)
    payload = archive_path.read_bytes()
    digest = hashlib.sha256(payload).hexdigest()
    if digest != ARCHIVE_SHA256:
        raise ValueError("NASM archive SHA-256 mismatch; no files were installed")
    installed = []
    with zipfile.ZipFile(archive_path) as zipped:
        for name in ("nasm.exe", "ndisasm.exe", "LICENSE"):
            candidates = [info for info in zipped.infolist() if Path(info.filename).name.lower() == name.lower()]
            if len(candidates) != 1:
                raise ValueError(f"Expected one {name} in official NASM archive")
            data = zipped.read(candidates[0])
            destination = target / name
            if destination.exists() and destination.read_bytes() != data:
                raise ValueError(f"Refusing to replace a different local file: {destination}")
            destination.write_bytes(data)
            installed.append({"name": name, "sha256": hashlib.sha256(data).hexdigest()})
    version = subprocess.run([str(target / "nasm.exe"), "-v"], shell=False, capture_output=True,
                             text=True, errors="replace", timeout=15, check=True).stdout.strip()
    result = {"status": "installed", "version": version, "url": URL,
              "archive_sha256": digest, "directory": str(target), "files": installed,
              "nasm": str(target / "nasm.exe"), "global_changes": False}
    (target / "provenance.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", default=str(Path(__file__).resolve().parents[1] / ".tools/nasm"))
    parser.add_argument("--archive", help="Use an already downloaded official ZIP, checked against the pinned hash")
    arguments = parser.parse_args()
    try:
        result = install(arguments.directory, arguments.archive)
    except (OSError, ValueError, subprocess.SubprocessError, zipfile.BadZipFile) as error:
        print(json.dumps({"status": "error", "error": str(error)}, ensure_ascii=False))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
