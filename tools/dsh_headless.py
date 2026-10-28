"""Run real DSH headless in an isolated project-local home and retain its events.

This is a launcher for DSH, not an emulation of DSH or a substitute model.
Selected credentials are never copied. The account route uses DSH's native
credential provider, which may normally refresh the existing sign-in.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

# Bootstrap only paths derived from this trusted script, never the task input.
# -I also omits the script directory, so register tools before its local import.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from dsh_install_skill import REPOSITORY, install_skill
sys.path.insert(0, str(REPOSITORY))


def find_command(explicit: Path | None = None) -> tuple[list[str], dict[str, str], str]:
    """Prefer an explicit launcher; otherwise use PATH or an installed desktop CLI."""
    if explicit is None:
        found = shutil.which("dsh.cmd") or shutil.which("dsh")
        if found:
            launcher = Path(found)
            if launcher.suffix.lower() == ".cmd":
                script = launcher.parent / "node_modules" / "@deepseek-ai" / "dsh" / "lib" / "bin.js"
                node = shutil.which("node")
                if script.is_file() and node:
                    return [node, str(script)], {}, "npm-node-cli"
                raise ValueError("The dsh.cmd layout is not recognized; pass an explicit DSH executable.")
            return [found], {}, "path-cli"
        configured = os.environ.get("DSH_DESKTOP_EXE")
        candidates = [Path(configured)] if configured else []
        explicit = next((p for p in candidates if p.is_file()), None)
        if explicit is None:
            raise ValueError("DSH was not found. Pass --dsh-executable or set DSH_DESKTOP_EXE.")
    executable = explicit.expanduser().resolve(strict=True)
    if executable.name.lower() == "deepseek harness.exe":
        archive = executable.parent / "resources" / "app.asar"
        if not archive.is_file():
            raise ValueError("The desktop installation has no resources/app.asar.")
        entry = archive / "dsh" / "node_modules" / "@deepseek-ai" / "dsh" / "lib" / "bin.js"
        return [str(executable), str(entry)], {"ELECTRON_RUN_AS_NODE": "1"}, "desktop-bundled-cli"
    return [str(executable)], {}, "explicit-cli"


def probe(explicit: Path | None = None) -> dict:
    command, extra, route = find_command(explicit)
    process = subprocess.run(
        command + ["--version"], capture_output=True, text=True, encoding="utf-8",
        errors="replace", timeout=30, env={**os.environ, **extra},
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    return {
        "status": "available" if process.returncode == 0 else "error",
        "route": route,
        "command": command,
        "exit_code": process.returncode,
        "version": process.stdout.strip(),
        "stderr": process.stderr.strip(),
    }


def credential_environment(path: Path | None) -> dict[str, str]:
    """Read only a specifically selected DEEPSEEK_API_KEY reference, never grants."""
    if path is None:
        return {}
    try:
        import yaml
    except ImportError as exc:
        raise ValueError("Reading a YAML credential store requires PyYAML; alternatively set DEEPSEEK_API_KEY.") from exc
    try:
        document = yaml.safe_load(path.expanduser().resolve(strict=True).read_text(encoding="utf-8"))
    except Exception as exc:
        # YAML parser diagnostics can quote secret source lines.
        raise ValueError("The selected credential store could not be read safely.") from None
    if not isinstance(document, dict) or document.get("version") != 1:
        raise ValueError("The selected credential store is not a supported version-1 mapping.")
    refs = document.get("refs")
    value = refs.get("DEEPSEEK_API_KEY") if isinstance(refs, dict) else None
    if not isinstance(value, str) or not value.strip():
        raise ValueError("The selected store has no nonempty DEEPSEEK_API_KEY reference.")
    return {"DEEPSEEK_API_KEY": value}


def credential_fingerprint(path: Path | None) -> str | None:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path is not None and path.is_file() else None


def credential_redactions(path: Path | None) -> set[str]:
    """Collect only sensitive scalar fields in memory for defensive log scrubbing."""
    if path is None:
        return set()
    try:
        import yaml
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception:
        return set()
    values: set[str] = set()
    def visit(value: object) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                if key in {"DEEPSEEK_API_KEY", "token", "secret", "apiKey", "key"} and isinstance(child, str) and len(child) > 8:
                    values.add(child)
                else:
                    visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)
    visit(data)
    return values


def summarize_events(text: str, return_code: int) -> dict:
    events = []
    malformed_lines = 0
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            malformed_lines += 1
            continue
        if isinstance(event, dict):
            events.append(event)
    final = next((event for event in reversed(events) if event.get("type") == "final"), None)
    reason = final.get("reason") if final else None
    reason_source = "final" if reason is not None else None
    if final is not None and reason is None:
        # Desktop-bundled 0.2.1-rc.3 projects the terminal reason on the
        # turn_end status rather than the final event. Never inherit a reason
        # from an earlier turn if the last turn remained unfinished.
        last_start = max((i for i, event in enumerate(events) if event.get("type") == "status" and event.get("phase") == "turn_start"), default=-1)
        terminal = next((event for event in reversed(events[last_start + 1:]) if event.get("type") == "status" and event.get("phase") == "turn_end"), None)
        if terminal is not None:
            reason = terminal.get("reason")
            reason_source = "terminal_status"
    completed = final is not None and return_code == 0 and isinstance(reason, dict) and reason.get("kind") == "completed"
    return {
        "agent_turn_completed": completed,
        "note": "An agent-turn completion is not a Proteus verification result.",
        "event_count": len(events),
        "event_types": sorted({str(event.get("type")) for event in events}),
        "non_json_lines": malformed_lines,
        "session_id": next((event.get("sessionId") for event in events if event.get("type") == "session"), None),
        "final_reason": reason,
        "reason_source": reason_source,
    }


def design_input_manifest(args: argparse.Namespace) -> dict:
    """Resolve host-selected paths before model execution; never accepts model paths."""
    from fish_proteus.config import ProteusConfig
    overrides = json.loads(args.design_config.read_text(encoding="utf8")) if args.design_config else {}
    if not isinstance(overrides, dict) or not overrides.keys() <= {"executable", "library_root", "samples_root", "template_project"}:
        raise ValueError("--design-config must contain only Proteus resource-path configuration.")
    config = ProteusConfig.discover(**overrides)
    result = {"schema": "fish-proteus.design-inputs.v1", "config": {
        key: str(getattr(config, key)) for key in ("executable", "library_root", "samples_root", "template_project")},
        "projects": {}, "firmware": {}}
    for kind, values in (("projects", args.input_project), ("firmware", args.input_firmware)):
        from fish_proteus.design_cli import _identifier
        for item in values:
            key, separator, path = item.partition("=")
            if not separator:
                raise ValueError("Register design inputs as ID=PATH.")
            _identifier(key)
            if key in result[kind]:
                raise ValueError("Design input IDs must be unique within their kind.")
            source = Path(path).expanduser().resolve(strict=True)
            if not source.is_file() or (kind == "projects" and source.suffix.lower() != ".pdsprj"):
                raise ValueError("Registered inputs must be files; projects must use .pdsprj.")
            result[kind][key] = str(source)
    return result


def run(args: argparse.Namespace) -> dict:
    workspace = args.workspace.expanduser().resolve(strict=True)
    if workspace != REPOSITORY:
        raise ValueError("Run the bounded headless workflow from this repository's own workspace.")
    output = args.output.expanduser().resolve()
    if workspace / ".work" not in output.parents:
        raise ValueError("--output must be an evidence directory inside this workspace/.work.")
    if output.exists() and any(output.iterdir()):
        raise ValueError("Use a new or empty output directory to preserve previous evidence.")
    output.mkdir(parents=True, exist_ok=True)
    installation = install_skill(workspace, update=args.update_skill)
    task = args.task_file.read_text(encoding="utf-8-sig") if args.task_file else args.task
    if not task or not task.strip():
        raise ValueError("The task must not be empty.")
    workflow = getattr(args, "workflow", "course")
    if workflow == "design":
        from fish_proteus.design_cli import ACTIONS, FILE_ACTIONS, READ_ACTIONS
        enabled = args.allowed_operations or sorted(FILE_ACTIONS)
        if not enabled or not set(enabled) <= ACTIONS:
            raise ValueError("The design workflow received an unknown --allowed-operations action.")
        read_actions = READ_ACTIONS
    else:
        enabled = args.allowed_operations or ["doctor", "prepare", "build"]
        if not enabled or not set(enabled) <= {"doctor", "prepare", "build", "run", "verify"}:
            raise ValueError("The course workflow received an unknown --allowed-operations stage.")
        read_actions = {"doctor"}
    command, extra_env, route = find_command(args.dsh_executable)
    credential_store = args.credential_store.expanduser().resolve(strict=True) if args.credential_store else None
    if args.provider == "deepseek-account" and credential_store is None:
        raise ValueError("The isolated account route needs --credential-store pointing to the existing DSH store.")
    original_fingerprint = credential_fingerprint(credential_store)
    redactions = credential_redactions(credential_store)
    secret_env = credential_environment(credential_store) if args.provider == "deepseek-official" else {}
    launch_env = {**os.environ, **extra_env, **secret_env, "DSH_HOME": str(output / "home")}
    # The shipped headless profile ignores the user's credential store. The
    # optional account route restores its native provider and normal token
    # lifecycle through a temporary overlay, never editing saved profiles.
    overlay = [
        {"id": "agent-default-model", "config": {"provider": args.provider, "model": args.model, "reasoningEffort": "high"}},
        {"id": "sandbox-policy", "config": {"mode": args.permission_mode, "workspaceRoot": str(workspace)}},
        {"id": "approval", "config": {"policy": "never"}},
        {"id": "permission", "config": {"defaultPreset": "fish-proteus", "presets": {"fish-proteus": {"sandbox": args.permission_mode, "approval": "never"}}}},
    ]
    if args.permission_mode == "read-only" and not set(enabled) <= read_actions:
        raise ValueError("The read-only task mode cannot enable project mutation or native execution.")
    job_directory = (args.job_directory or (output / "job")).expanduser().resolve()
    if workspace / ".work" not in job_directory.parents:
        raise ValueError("--job-directory must be inside the selected workspace/.work.")
    library = (args.library or (workspace / ".local" / "course")).expanduser().resolve()
    if workspace not in library.parents:
        raise ValueError("--library must belong to the selected workspace.")
    module = args.tools_module
    if module is None:
        script = Path(command[-1]).resolve()
        if script.suffix.lower() == ".js":
            module = script.parents[2] / "dsh-tools" / "lib" / "index.js"
        else:
            raise ValueError("Pass --tools-module for this DSH launcher layout.")
    # Expose the purpose-built capability instead of an unrestricted shell.
    # The DSH filesystem policy stays workspace-write; only the CLI's bounded
    # project operations execute in the native host process.
    disabled_tools = [
        "tool-pwsh", "tool-bash", "tool-fs", "tool-fs-search", "tool-jobs",
        "tool-working-directory", "tool-subagent-control", "tool-subagent-list-agents",
        "tool-subagent", "tool-subagent-fork", "tool-workflow", "tool-web",
        "tool-todo", "tool-goal", "tool-plugin-manager",
    ]
    overlay += [{"id": identifier, "disabled": True} for identifier in disabled_tools]
    plugin = {
        "id": "fish-proteus-project-tool",
        "name": (REPOSITORY / "tools" / "dsh_project_tool.mjs").as_uri(),
        "config": {
            "workspace": str(workspace), "python": sys.executable,
            "gate": str(REPOSITORY / "tools" / "dsh_cli_gate.py"),
            "library": str(library), "jobDirectory": str(job_directory),
            "allowedOperations": enabled,
            "toolsModule": module.expanduser().resolve().as_uri(),
            "auditPath": str(output / "project-tool-audit.jsonl"),
        },
    }
    if workflow == "design":
        inputs_path = output / "design-inputs.json"
        inputs_path.write_text(json.dumps(design_input_manifest(args), ensure_ascii=False, indent=2) + "\n", encoding="utf8")
        plugin = {
            "id": "fish-proteus-design-tool",
            "name": (REPOSITORY / "tools" / "dsh_design_tool.mjs").as_uri(),
            "config": {
                "workspace": str(workspace), "python": sys.executable,
                "gate": str(REPOSITORY / "tools" / "design_gate.py"),
                "taskRoot": str(job_directory), "inputsFile": str(inputs_path),
                "allowedActions": enabled,
                "toolsModule": module.expanduser().resolve().as_uri(),
                "auditPath": str(output / "design-tool-audit.jsonl"),
            },
        }
    overlay += [
        {"id": "tools", "config": {"mode": "native"}},
        {"insert": [plugin]},
    ]
    if args.provider == "deepseek-account":
        overlay += [
            {"id": "credentials", "disabled": False, "config": {"path": str(credential_store), "watch": False}},
            {"id": "authorization", "disabled": False},
            {"id": "deepseek-account", "disabled": False},
        ]
    overlay_path = output / "profile-overlay.json"
    overlay_path.write_text(json.dumps(overlay, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output / "task.txt").write_text(task, encoding="utf-8")
    # Installed desktop 0.2.1-rc.3 has no permission CLI flags even though
    # newer upstream documentation does. Profile overlays configure the actual
    # installed services, without pretending unsupported flags exist.
    argv = command + ["--profile", "headless", "--patch", str(overlay_path), "--json", "-"]
    started = datetime.now(timezone.utc).isoformat()
    process = subprocess.Popen(
        argv, cwd=workspace, env=launch_env, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace",
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    timed_out = False
    try:
        stdout, stderr = process.communicate(task, timeout=args.timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True, timeout=30)
        else:
            process.kill()
        stdout, stderr = process.communicate(timeout=30)
    # Redact the launch credential even if an upstream error unexpectedly echoes it.
    secrets = {value for key, value in launch_env.items() if key in {"DEEPSEEK_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY"} and value}
    secrets |= redactions | credential_redactions(credential_store)
    for secret in sorted(secrets, key=len, reverse=True):
        stdout, stderr = stdout.replace(secret, "[REDACTED]"), stderr.replace(secret, "[REDACTED]")
    (output / "events.jsonl").write_text(stdout, encoding="utf-8")
    (output / "stderr.log").write_text(stderr, encoding="utf-8")
    summary = summarize_events(stdout, process.returncode)
    result = {
        "status": "timeout" if timed_out else ("finished" if summary["agent_turn_completed"] else "error"),
        "started_utc": started,
        "ended_utc": datetime.now(timezone.utc).isoformat(),
        "workspace": str(workspace),
        "route": route,
        "model_provider": args.provider,
        "model": args.model,
        "permission_mode": args.permission_mode,
        "workflow": workflow,
        "execution_capability": "bounded-fish-proteus-design-tool" if workflow == "design" else "bounded-fish-proteus-tool",
        "allowed_operations": enabled,
        "fixed_job_directory": str(job_directory),
        "credential_from_selected_store": credential_store is not None,
        "credential_access": "native-managed-store" if args.provider == "deepseek-account" else "api-key-process-environment",
        "original_credential_store_modified": original_fingerprint != credential_fingerprint(credential_store),
        "exit_code": process.returncode,
        "timed_out": timed_out,
        "skill": installation["skill"],
        "events": str(output / "events.jsonl"),
        "diagnostics": str(output / "stderr.log"),
        **summary,
    }
    (output / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--probe", action="store_true", help="Only read the installed DSH CLI version.")
    parser.add_argument("--list-actions", action="store_true", help="Load and list the selected local action registry without starting DSH or installing a skill.")
    parser.add_argument("--dsh-executable", type=Path)
    parser.add_argument("--workspace", type=Path, default=REPOSITORY)
    parser.add_argument("--output", type=Path)
    prompt = parser.add_mutually_exclusive_group()
    prompt.add_argument("--task")
    prompt.add_argument("--task-file", type=Path)
    parser.add_argument("--credential-store", type=Path, help="Use the existing store without copying it; account sign-in may normally refresh.")
    parser.add_argument("--provider", choices=("deepseek-official", "deepseek-account"), default="deepseek-official", help="Authentication route (default: deepseek-official); use deepseek-account with --credential-store for an existing DSH sign-in.")
    parser.add_argument("--model", default="deepseek-v4-pro")
    parser.add_argument("--permission-mode", choices=("read-only", "workspace-write"), default="workspace-write")
    parser.add_argument("--workflow", choices=("course", "design"), default="course", help="Select the legacy course stages or composable design API.")
    parser.add_argument("--library", type=Path, help="Fixed imported library inside the selected workspace.")
    parser.add_argument("--job-directory", type=Path, help="Fixed new job below workspace/.work; the model cannot select other paths.")
    parser.add_argument("--allowed-operations", nargs="+", help="Explicit enabled stages/actions; design defaults to file actions and excludes native run_sequence.")
    parser.add_argument("--input-project", action="append", default=[], metavar="ID=PATH", help="Host-register a read-only .pdsprj input for design workflows; repeat for donors/templates.")
    parser.add_argument("--input-firmware", action="append", default=[], metavar="ID=PATH", help="Host-register a read-only ELF/HEX firmware input for design workflows.")
    parser.add_argument("--design-config", type=Path, help="Host configuration JSON containing executable/library_root/samples_root/template_project paths.")
    parser.add_argument("--tools-module", type=Path, help="Installed @deepseek-ai/dsh-tools/lib/index.js when not discoverable from the launcher.")
    parser.add_argument("--timeout", type=float, default=300)
    parser.add_argument("--update-skill", action="store_true")
    args = parser.parse_args()
    if args.list_actions:
        if args.workflow == "design":
            from fish_proteus.design_cli import ACTIONS, FILE_ACTIONS
            actions, defaults = sorted(ACTIONS), sorted(FILE_ACTIONS)
        else:
            actions, defaults = ["doctor", "prepare", "build", "run", "verify"], ["doctor", "prepare", "build"]
        print(json.dumps({"status": "available", "workflow": args.workflow, "actions": actions, "default_actions": defaults}, indent=2))
        return 0
    if not args.probe and (args.output is None or not (args.task or args.task_file)):
        parser.error("A run needs --output and either --task or --task-file.")
    if args.timeout <= 0:
        parser.error("--timeout must be positive.")
    try:
        result = probe(args.dsh_executable) if args.probe else run(args)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result.get("status") in {"available", "finished"} else 1
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        print(json.dumps({"status": "error", "message": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    raise SystemExit(main())
