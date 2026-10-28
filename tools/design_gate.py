"""Fixed-workspace gate for the composable DSH design tool; no shell/eval."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


def descendant(path: Path, root: Path) -> Path:
    path, root = path.expanduser().resolve(), root.resolve()
    if path == root or root not in path.parents:
        raise ValueError("The selected path must remain below its fixed task/workspace root")
    return path


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--task-root", required=True, type=Path)
    parser.add_argument("--inputs-file", required=True, type=Path)
    parser.add_argument("--allow", required=True, nargs="+")
    args = parser.parse_args(argv)
    try:
        workspace = args.workspace.resolve(strict=True)
        if workspace != Path(__file__).resolve().parents[1]:
            raise ValueError("The design gate may only import its own trusted repository")
        task_root = descendant(args.task_root, workspace / ".work")
        inputs_file = descendant(args.inputs_file, workspace / ".work")
        raw = sys.stdin.read(2_000_001)
        if len(raw) > 2_000_000:
            raise ValueError("The structured request exceeds the gate input limit")
        def reject_constant(_value):
            raise ValueError("Non-finite JSON values are disabled")
        payload = json.loads(raw, parse_constant=reject_constant)
        inputs = json.loads(inputs_file.read_text(encoding="utf8"))
        sys.path.insert(0, str(workspace))
        from fish_proteus.design_cli import ACTIONS, execute_request
        if not args.allow or not set(args.allow) <= ACTIONS:
            raise ValueError("The host action allowlist contains an unknown action")
        result = execute_request(payload, task_root, inputs, frozenset(args.allow))
    except (OSError, ValueError, KeyError, RuntimeError, TypeError, ImportError) as exc:
        result = {"schema": "fish-proteus.design.v1", "status": "blocked", "stage": "design_gate",
                  "error": {"type": type(exc).__name__, "message": str(exc)}}
    print(json.dumps(result, ensure_ascii=False, default=str, allow_nan=False))
    return 0 if result["status"] not in {"blocked", "unsupported", "failed"} else 2


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf8")
    sys.stderr.reconfigure(encoding="utf8")
    raise SystemExit(main())
