"""Host-context entry point for the persistent DSH desktop design plugin."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--store-root", required=True, type=Path)
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--working-directory", required=True, type=Path)
    parser.add_argument("--config-file", type=Path)
    args = parser.parse_args(argv)
    try:
        workspace = args.workspace.resolve(strict=True)
        if workspace != Path(__file__).resolve().parents[1]:
            raise ValueError("The desktop gate may import only its own trusted repository")
        raw = sys.stdin.read(2_000_001)
        if len(raw) > 2_000_000:
            raise ValueError("Desktop request exceeds the input size limit")
        def reject_constant(_value):
            raise ValueError("Non-finite JSON number")
        payload = json.loads(raw, parse_constant=reject_constant)
        config = json.loads(args.config_file.read_text(encoding="utf8")) if args.config_file else None
        sys.path.insert(0, str(workspace))
        from fish_proteus.desktop import execute_desktop_request
        result = execute_desktop_request(payload, store_root=args.store_root,
            session_id=args.session_id, working_directory=args.working_directory, config=config)
    except (OSError, ValueError, KeyError, TypeError, ImportError) as exc:
        result = {"schema": "fish-proteus.desktop.v1", "status": "blocked",
                  "error": {"type": type(exc).__name__, "message": str(exc)}}
    print(json.dumps(result, ensure_ascii=False, allow_nan=False))
    return 0 if result["status"] not in {"blocked", "unsupported", "failed"} else 2


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf8")
    sys.stderr.reconfigure(encoding="utf8")
    raise SystemExit(main())
