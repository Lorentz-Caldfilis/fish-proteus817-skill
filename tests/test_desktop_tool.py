"""Exercise the real JS adapter with an original local Python child, not Proteus."""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
NODE = shutil.which("node")


@unittest.skipUnless(NODE, "Node is optional; desktop DSH supplies its own runtime")
class DesktopToolTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        (self.root / "tools").mkdir()
        self.gate = self.root / "tools" / "desktop_gate.py"
        self.gate.write_text("""import argparse,json,sys,time
from pathlib import Path
p=argparse.ArgumentParser()
for k in ['workspace','store-root','session-id','working-directory']:p.add_argument('--'+k)
a=p.parse_args();v=json.load(sys.stdin)
if v.get('query')=='wait':time.sleep(30)
print(json.dumps({'schema':'fish-proteus.design.v1','action':v['action'],'status':'prepared',
 'data':{'session_observed':a.session_id,'cwd_observed':a.working_directory,
 'unexpected_key_present':bool(__import__('os').environ.get('DEEPSEEK_API_KEY')),
 'native_identity':9223372036854775807},
 'desktop':{'session_id':a.session_id,'task_id':'test-task','task_root':str(Path(a.store_root)/'tasks'/'one'),
 'project_path':str(Path(a.store_root)/'tasks'/'one'/'new.pdsprj')}}))
""", encoding="utf8")
        self.sdk = self.root / "sdk.mjs"
        self.sdk.write_text("export const defineTool = value => value;\n", encoding="utf8")

    def node(self, code, value=None):
        result = subprocess.run([NODE, "--input-type=module", "-e", code],
            input=json.dumps(value or {}), text=True, encoding="utf8",
            capture_output=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def execute(self, *, missing=False, abort=False, action="capabilities"):
        module = (ROOT / "tools/dsh_desktop_tool.mjs").as_uri()
        config = {"workspace": str(self.root), "python": sys.executable,
            "gate": str(self.gate), "stateRoot": str(self.root / ".work/desktop"),
            "sourceIdentity": "synthetic-tested-source",
            "toolsModule": self.sdk.as_uri()}
        code = f"""
import {{apply}} from {json.dumps(module)};
const config=JSON.parse(await new Promise(resolve=>{{let s='';process.stdin.on('data',x=>s+=x);process.stdin.on('end',()=>resolve(s));}}));
let tool;const ctx={{tools:{{register:t=>tool=t,guard:()=>{{throw Error('global guard called')}}}},
 workingDirectory:{{get:s=>config.workspace}}}};
process.env.DEEPSEEK_API_KEY='synthetic-value-must-not-be-inherited';
await apply(ctx,config);
const control=new AbortController();
if ({str(abort).lower()}) setTimeout(()=>control.abort(),150);
const exec={{signal:control.signal,...({str(missing).lower()}?{{}}:{{agent:{{session:{{id:'real-desktop-session'}}}}}})}};
const result=await tool.execute({{action:{json.dumps(action)},query:{json.dumps('wait' if abort else 'normal')}}},exec);
console.log(JSON.stringify({{name:tool.name,result}}));
"""
        return self.node(code, config)

    def test_registration_uses_normal_registry_and_real_agent_context(self):
        value = self.execute()
        self.assertEqual(value["name"], "fish_proteus_design")
        result = value["result"]
        self.assertEqual(result["payload"]["data"]["session_observed"], "real-desktop-session")
        self.assertEqual(result["payload"]["data"]["native_identity"], "9223372036854775807")
        self.assertFalse(result["payload"]["data"]["unexpected_key_present"])
        self.assertEqual(result["delivery"]["project_path"], str(self.root / ".work/desktop/tasks/one/new.pdsprj"))
        self.assertEqual(result["desktop"]["task_id"], "test-task")
        records = list((self.root / ".work/desktop/observations").rglob("audit.jsonl"))
        self.assertEqual(len(records), 1)
        audit = json.loads(records[0].read_text())
        self.assertEqual(audit["action"], "capabilities")
        self.assertEqual(audit["source_identity"], "synthetic-tested-source")
        self.assertEqual(audit["implementation_module"], (ROOT / "tools/dsh_desktop_tool.mjs").as_uri())

    def test_missing_agent_does_not_create_shared_fallback_task(self):
        result = self.execute(missing=True)["result"]
        self.assertEqual(result["payload"]["error"]["type"], "MissingDesktopSession")
        self.assertFalse((self.root / ".work/desktop/observations").exists())

    def test_abort_terminates_owned_child_and_cannot_claim_success(self):
        result = self.execute(abort=True)["result"]
        self.assertEqual(result["payload"]["status"], "blocked")
        self.assertEqual(result["termination"], "aborted")
        self.assertNotIn("delivery", result)

    def test_projection_keeps_output_delivery_but_omits_raw_inputs(self):
        module = (ROOT / "tools/dsh_desktop_tool.mjs").as_uri()
        value = self.node(f"""
import {{desktopProjection}} from {json.dumps(module)};
const result={{exit_code:0,payload:{{action:'inspect',status:'file_verified',
 data:{{raw_log:'private raw data',password:'synthetic-secret',path:'C:/private/donor.pdsprj',pins:['R1.1','R2.1']}},
 desktop:{{task_id:'one',task_root:'C:/repo/.work/desktop/one',project_path:'C:/outside/source.pdsprj'}}}}}};
console.log(JSON.stringify(desktopProjection(result,{{workspace:'C:/repo',stateRoot:'C:/repo/.work/desktop'}})));
""")
        self.assertNotIn("delivery", value)
        data = value["payload"]["data"]
        self.assertNotIn("raw_log", data)
        self.assertNotIn("password", data)
        self.assertNotEqual(data["path"], "C:/private/donor.pdsprj")
        self.assertEqual(data["pins"], ["R1.1", "R2.1"])

    def test_schema_exposes_generic_and_desktop_operations_without_host_arguments(self):
        module = (ROOT / "tools/dsh_desktop_tool.mjs").as_uri()
        value = self.node(f"import {{desktopParameters}} from {json.dumps(module)};console.log(JSON.stringify(desktopParameters()));")
        self.assertIn("resource_register", value["action"]["enum"])
        self.assertIn("run_sequence", value["action"]["enum"])
        self.assertIn("candidate_id", value)
        self.assertIn("desktop", value["topic"]["enum"])
        self.assertNotIn("session_id", value)
        self.assertNotIn("task_root", value)
        self.assertNotIn("allow", value)

    def test_same_bootstrap_callback_loads_new_implementation_on_upgrade(self):
        old = self.root / "old.mjs"
        new = self.root / "new.mjs"
        old.write_text("export function apply(ctx){ctx.loaded.push('old')}\n", encoding="utf8")
        new.write_text("export function apply(ctx){ctx.loaded.push('new')}\n", encoding="utf8")
        module = (ROOT / "tools/dsh_desktop_bootstrap.mjs").as_uri()
        value = self.node(f"""
import {{apply}} from {json.dumps(module)};
const ctx={{loaded:[]}};
await apply(ctx,{{implementationModule:{json.dumps(old.as_uri())}}});
await apply(ctx,{{implementationModule:{json.dumps(new.as_uri())}}});
console.log(JSON.stringify(ctx.loaded));
""")
        self.assertEqual(value, ["old", "new"])


if __name__ == "__main__":
    unittest.main()
