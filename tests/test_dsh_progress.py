"""Launcher progress contracts using local synthetic children, never a model."""
from contextlib import ExitStack, redirect_stderr, redirect_stdout
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from tools import dsh_headless


class DshProgressTests(unittest.TestCase):
    def setUp(self):
        work = Path(__file__).resolve().parents[1] / ".work" / "dsh-progress-tests"
        work.mkdir(parents=True, exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(dir=work)
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.assertTrue(self.root.is_relative_to(work.resolve()))

    def child(self, source, *arguments):
        process = subprocess.Popen(
            [sys.executable, "-I", "-B", "-c", source, *map(str, arguments)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", errors="replace",
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        self.addCleanup(self.finish, process)
        return process

    @staticmethod
    def finish(process):
        if process.poll() is None:
            dsh_headless.stop_owned_process(process)
        process.communicate(timeout=5)

    def test_complete_known_audit_rows_expose_only_action_status_and_counts(self):
        path = self.root / "audit.jsonl"
        rows = [
            {"action": "inspect", "payload_status": "file_verified",
             "input": {"password": "SYNTHETIC_PRIVATE_TEXT"}},
            {"operation": "doctor", "payload_status": "blocked"},
            {"action": "SYNTHETIC_PRIVATE_TEXT", "payload_status": "passed"},
            {"action": {"secret": "SYNTHETIC_PRIVATE_TEXT"}},
            {"action": "edit", "payload_status": "SYNTHETIC_PRIVATE_TEXT"},
        ]
        path.write_bytes(b"".join(json.dumps(row).encode()+b"\n" for row in rows)
                         + b'not json\n{"action":"edit","payload_status":"blocked",'
                         + b'"partial_utf8":"\xe6\xb5')
        snapshot = dsh_headless.progress_snapshot(path, {"inspect", "doctor", "edit"})
        self.assertEqual(snapshot, {"tool_calls": 3, "blocked_calls": 1,
                                    "last_action": "edit", "last_status": "unknown"})
        self.assertNotIn("SYNTHETIC_PRIVATE_TEXT", json.dumps(snapshot))
        self.assertEqual(dsh_headless.progress_snapshot(self.root/"absent", {"inspect"})["tool_calls"], 0)

    def test_repeated_communication_preserves_single_input_and_large_utf8_streams(self):
        path = self.root / "audit.jsonl"
        path.write_text(json.dumps({"action": "inspect", "payload_status": "file_verified",
                                   "input": {"secret": "AUDIT_PRIVATE_SENTINEL"}})+"\n", encoding="utf-8")
        process = self.child(
            "import sys,json,time\nsys.stdin.reconfigure(encoding='utf-8')\n"
            "task=sys.stdin.read()\n"
            "out=json.dumps({'received':task,'body':'\\u6d4b\\u91cf\\U0001f30a'*40000},ensure_ascii=False).encode('utf-8')\n"
            "err=('RAW_PRIVATE_SENTINEL'+'\\u79d8\\u5bc6'*30000).encode('utf-8')\n"
            "for i in range(0,max(len(out),len(err)),40000):\n"
            " sys.stdout.buffer.write(out[i:i+40000]);sys.stdout.buffer.flush()\n"
            " sys.stderr.buffer.write(err[i:i+40000]);sys.stderr.buffer.flush();time.sleep(.02)\n"
        )
        progress = io.StringIO()
        stdout, stderr = dsh_headless.communicate_with_progress(
            process, "one task \u4e2d\u6587", timeout=10, interval=.03,
            audit_path=path, allowed_actions={"inspect"}, stream=progress)
        payload = json.loads(stdout)
        self.assertEqual(payload["received"], "one task \u4e2d\u6587")
        self.assertEqual(payload["body"], "\u6d4b\u91cf\U0001f30a"*40000)
        self.assertEqual(stderr, "RAW_PRIVATE_SENTINEL"+"\u79d8\u5bc6"*30000)
        self.assertEqual(process.returncode, 0)
        self.assertGreater(len(progress.getvalue().splitlines()), 1)
        for private in ("RAW_PRIVATE_SENTINEL", "AUDIT_PRIVATE_SENTINEL", "one task", "\u79d8\u5bc6", str(path)):
            self.assertNotIn(private, progress.getvalue())

    def test_timeout_uses_one_deadline_and_collected_output_remains_recoverable(self):
        ready = self.root / "ready"
        process = self.child(
            "import sys,time\nfrom pathlib import Path\n"
            "Path(sys.argv[1]).write_text('ready')\n"
            "sys.stdin.read();print('BEFORE_TIMEOUT',flush=True);time.sleep(20)\n", ready)
        deadline = time.monotonic()+5
        while not ready.exists() and process.poll() is None and time.monotonic() < deadline:
            time.sleep(.01)
        self.assertTrue(ready.exists(), "Synthetic child did not start")
        started = time.monotonic()
        with self.assertRaises(subprocess.TimeoutExpired) as caught:
            dsh_headless.communicate_with_progress(
                process, "once", timeout=.25, interval=.04, audit_path=self.root/"absent",
                allowed_actions={"inspect"}, stream=io.StringIO())
        self.assertEqual(caught.exception.timeout, .25)
        self.assertLess(time.monotonic()-started, 5)
        self.assertIsNone(process.poll())
        dsh_headless.stop_owned_process(process)
        stdout, _ = process.communicate(timeout=5)
        self.assertIn("BEFORE_TIMEOUT", stdout)
        self.assertIsNotNone(process.returncode)

    def test_unavailable_progress_display_does_not_interrupt_child_or_lose_output(self):
        class BrokenProgress:
            def write(self, text):
                raise BrokenPipeError("synthetic closed pipe")
            def flush(self):
                raise BrokenPipeError("synthetic closed pipe")

        closed = io.StringIO()
        closed.close()
        for stream in (BrokenProgress(), closed):
            with self.subTest(stream=type(stream).__name__):
                process = self.child("import sys,time\ntext=sys.stdin.read();time.sleep(.12);print(text)")
                stdout, stderr = dsh_headless.communicate_with_progress(
                    process, "one input", timeout=5, interval=.03, stream=stream,
                    audit_path=self.root/"absent", allowed_actions={"inspect"})
                self.assertEqual(stdout, "one input\n")
                self.assertEqual(stderr, "")
                self.assertEqual(process.returncode, 0)

    def cli_fixture(self, workflow, *, interrupt=False):
        script = self.root / (workflow+"-child.py")
        script.write_text(
            "import sys,json,time\nfrom pathlib import Path\n"
            "sys.stdin.read()\n"
            "overlay=json.loads(Path(sys.argv[sys.argv.index('--patch')+1]).read_text('utf-8'))\n"
            "plugin=next(row['insert'][0] for row in overlay if 'insert' in row)\n"
            "design=plugin['id']=='fish-proteus-design-tool'\n"
            "audit=Path(plugin['config']['auditPath'])\n"
            "audit.write_text(json.dumps({'action' if design else 'operation':'capabilities' if design else 'doctor',"
            "'payload_status':'prepared','input':{'secret':'AUDIT_PRIVATE_SENTINEL'}})+'\\n',encoding='utf-8')\n"
            "print(json.dumps({'type':'message','text':'MODEL_PRIVATE_SENTINEL'}),flush=True)\n"
            "time.sleep(.12)\n"
            "print(json.dumps({'type':'final','reason':{'kind':'completed'}}),flush=True)\n",
            encoding="utf-8")
        output = self.root/".work"/workflow
        argv = ["dsh_headless.py", "--workflow", workflow, "--output", str(output),
                "--tools-module", str(script), "--task", "synthetic request",
                "--allowed-operations", "capabilities" if workflow == "design" else "doctor"]
        original = dsh_headless.communicate_with_progress
        children = []
        original_popen = subprocess.Popen

        def launch(*args, **kwargs):
            process = original_popen(*args, **kwargs)
            if str(script) in args[0]:
                children.append(process)
                self.addCleanup(self.finish, process)
            return process

        def fast_progress(*args, **kwargs):
            if interrupt:
                raise KeyboardInterrupt
            return original(*args, **kwargs, interval=.02)

        stdout, stderr = io.StringIO(), io.StringIO()
        with ExitStack() as stack:
            stack.enter_context(patch.object(dsh_headless, "REPOSITORY", self.root))
            stack.enter_context(patch.object(dsh_headless, "install_skill", return_value={"skill": "synthetic-skill"}))
            stack.enter_context(patch.object(dsh_headless, "find_command", return_value=([sys.executable, str(script)], {}, "synthetic-local-child")))
            stack.enter_context(patch.object(dsh_headless, "design_input_manifest", return_value={"projects": {}, "firmware": {}, "config": {}}))
            stack.enter_context(patch.object(dsh_headless, "communicate_with_progress", side_effect=fast_progress))
            stack.enter_context(patch.object(dsh_headless.subprocess, "Popen", side_effect=launch))
            stack.enter_context(patch.object(sys, "argv", argv))
            stack.enter_context(patch.dict(os.environ, {key: "" for key in ("DEEPSEEK_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY")}))
            stack.enter_context(redirect_stdout(stdout))
            stack.enter_context(redirect_stderr(stderr))
            code = dsh_headless.main()
        return code, json.loads(stdout.getvalue()), stderr.getvalue(), output, children

    def test_both_cli_workflows_keep_stdout_one_json_and_progress_metadata_only(self):
        for workflow in ("course", "design"):
            with self.subTest(workflow=workflow):
                code, result, progress, output, children = self.cli_fixture(workflow)
                self.assertEqual(code, 0)
                self.assertEqual(result["status"], "finished")
                self.assertTrue(result["agent_turn_completed"])
                self.assertEqual(result, json.loads((output/"result.json").read_text("utf-8")))
                self.assertIn("MODEL_PRIVATE_SENTINEL", (output/"events.jsonl").read_text("utf-8"))
                for private in ("MODEL_PRIVATE_SENTINEL", "AUDIT_PRIVATE_SENTINEL", str(output)):
                    self.assertNotIn(private, progress)
                self.assertGreater(len(progress.splitlines()), 1)
                self.assertEqual(len(children), 1)

    def test_keyboard_interrupt_stops_owned_child_and_records_cancellation(self):
        code, result, _, output, children = self.cli_fixture("course", interrupt=True)
        self.assertEqual(code, 130)
        self.assertEqual(result["status"], "cancelled")
        self.assertTrue(result["cancelled"])
        self.assertFalse(result["timed_out"])
        self.assertFalse(result["agent_turn_completed"])
        self.assertEqual(len(children), 1)
        self.assertIsNotNone(children[0].poll())
        self.assertEqual(result, json.loads((output/"result.json").read_text("utf-8")))


if __name__ == "__main__":
    unittest.main()
