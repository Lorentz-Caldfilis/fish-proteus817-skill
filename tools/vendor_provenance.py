"""Record or verify adapted source hashes; upstream identities remain pinned."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def check(root: Path, *, refresh=False) -> dict:
    vendor = root / "fish_proteus" / "_vendor" / "proteus_auto"
    manifest = vendor / "PROVENANCE.json"
    data = json.loads(manifest.read_text(encoding="utf-8"))
    if data.get("schema") != "fish-proteus.vendor.v1" or len(data.get("commit", "")) != 40:
        raise ValueError("Invalid vendor provenance schema or source commit")
    for row in data["files"]:
        name = row["path"]
        if Path(name).name != name or not name.endswith(".py") or len(row["original_git_blob_sha1"]) != 40:
            raise ValueError("Invalid vendor source identity")
        digest = hashlib.sha256((vendor / name).read_bytes()).hexdigest()
        if refresh:
            row["adapted_sha256"] = digest
        elif row["adapted_sha256"] != digest:
            raise ValueError("Vendor adapted identity changed: " + name)
    if refresh:
        manifest.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"status": "refreshed" if refresh else "passed", "files": len(data["files"]),
            "upstream_commit": data["commit"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true", help="Record intentional local changes")
    args = parser.parse_args()
    print(json.dumps(check(Path(__file__).resolve().parents[1], refresh=args.refresh)))


if __name__ == "__main__":
    main()
