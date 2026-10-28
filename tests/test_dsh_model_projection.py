"""Synthetic outbound projection tests; no account, network, GUI or real inputs."""
import copy
import base64
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import unittest


@unittest.skipUnless(shutil.which("node"), "Node is required for the actual model projection")
class ModelProjectionTests(unittest.TestCase):
    def node_from_raw(self, raw, body):
        """Keep original integer tokens until the production decoder sees them."""
        script = ("import {parseCliJSON,decodeCliStdout,projectModelResponse} from './tools/dsh_design_tool.mjs';"
                  "const chunks=[];for await(const chunk of process.stdin)chunks.push(chunk);"
                  "const raw=Buffer.concat(chunks);" + body)
        process = subprocess.run([shutil.which("node"), "--input-type=module", "-e", script],
                                 cwd=Path(__file__).resolve().parents[1], capture_output=True,
                                 input=raw.encode("utf8") if isinstance(raw, str) else raw,
                                 timeout=15, check=True)
        return json.loads(process.stdout)

    def project(self, result, context=None):
        original = copy.deepcopy(result)
        script = ("import {projectModelResponse} from './tools/dsh_design_tool.mjs';"
                  "let s='';for await(const c of process.stdin)s+=c;"
                  "const v=JSON.parse(s);console.log(JSON.stringify(projectModelResponse(v.result,v.context))); ")
        process = subprocess.run([shutil.which("node"), "--input-type=module", "-e", script],
                                 cwd=Path(__file__).resolve().parents[1], capture_output=True,
                                 input=json.dumps({"result": result, "context": context or {}}),
                                 text=True, encoding="utf8", timeout=15, check=True)
        self.assertEqual(result, original)  # local canonical payload remains intact
        return json.loads(process.stdout)

    def test_native_bytes_raw_logs_secrets_and_absolute_paths_stay_local(self):
        digest = "a" * 64
        result = {"exit_code": 0, "stderr": "RAW_NATIVE_LOG_SENTINEL C:\\Users\\Alice\\secret.txt",
                  "payload": {"action": "run_sequence", "status": "runtime_observed", "circuit_id": "circuit-7",
                    "current": {"path": "projects/generated.pdsprj", "revision": digest, "sha256": digest},
                    "data": {"units_per_mm": 100000, "simulation_seconds": .3025,
                      "identity": {"project": "C:\\Users\\Alice\\Private\\task\\projects\\generated.pdsprj",
                                   "executable": "/opt/private tools/PDS.EXE"},
                      "secret": "SYNTHETIC_SECRET", "api_key": "SYNTHETIC_KEY",
                      "binary": {"type": "Buffer", "data": list(range(256))},
                      "opaque_buffer": {"type": "Buffer", "data": list(range(128))},
                      "raw_native_log": "RAW_NATIVE_LOG_SENTINEL",
                      "unc_location": "\\\\private-host\\private-share\\native.log",
                      "blob": "TEACHER_CONTENT_SENTINEL",
                      "steps": [
                        {"op": "log", "data": {"text": "RAW_NATIVE_LOG_SENTINEL", "log_complete": True,
                            "raw_log_sha256": digest, "raw_log_artifact_id": "raw-7"}},
                        {"op": "gpio_events", "data": {"events": [{"ref": "U7", "pin": 5, "value": 1, "seconds": .1}],
                            "log_complete": True, "collected_after_close": True, "through_simulation_seconds": .3025}},
                        {"op": "errors", "data": {"messages": ["Missing '/home/alice/private source.hex'",
                            "Denied C:\\Users\\Alice\\Private\\other.dat", "Bearer SYNTHETIC_BEARER password=SYNTHETIC_PASSWORD"],
                            "log": "RAW_NATIVE_LOG_SENTINEL"}}]},
                    "evidence_refs": [{"artifact_id": "raw-7", "path": "runs/r7/simulation-log-raw.log", "sha256": digest}]}}
        output = self.project(result, {"workspace": "C:\\Users\\Alice\\Private",
            "taskRoot": "C:\\Users\\Alice\\Private\\task", "localReportId": "local-7", "localReportSha256": digest})
        text = json.dumps(output)
        for private in ("RAW_NATIVE_LOG_SENTINEL", "TEACHER_CONTENT_SENTINEL", "SYNTHETIC_SECRET", "SYNTHETIC_KEY",
                        "SYNTHETIC_BEARER", "SYNTHETIC_PASSWORD", "C:\\\\Users", "/home/alice", "/opt/private", "private-host"):
            self.assertNotIn(private, text)
        data = output["payload"]["data"]
        self.assertEqual(data["units_per_mm"], 100000)
        self.assertEqual(data["simulation_seconds"], .3025)
        self.assertEqual(data["steps"][1]["data"]["events"][0]["value"], 1)
        self.assertEqual(data["steps"][0]["data"]["raw_log_artifact_id"], "raw-7")
        self.assertEqual(output["payload"]["evidence_refs"][0]["sha256"], digest)
        self.assertEqual(output["model_projection"]["local_report_ref"], "local-report:local-7")
        self.assertEqual(data["opaque_buffer"], "[binary omitted]")

    def test_library_definition_raw_fields_are_omitted_but_semantic_pins_and_hash_survive(self):
        result = {"payload": {"action": "library_get", "status": "prepared", "data": {
            "name": "SYNTHETIC", "device_id": "TEST:SYNTHETIC", "path": "C:\\PrivateLib\\TEST.LIB",
            "definition_sha256": "b" * 64, "properties_raw": "PRIVATE_LIBRARY_TEXT",
            "sections": {"COMPONENT": ["PRIVATE_LIBRARY_TEXT"]}, "pinouts": {"PKG": ["PRIVATE_LIBRARY_TEXT"]},
            "pins": [{"name": "PA0", "number": "1", "anchor": [100000, 0], "record_offset": 42}],
            "defaults": {"CLOCK": "8M"}, "models": {"MODDLL": "SYNTH.DLL"}}}}
        output = self.project(result)
        self.assertNotIn("PRIVATE_LIBRARY_TEXT", json.dumps(output))
        data = output["payload"]["data"]
        self.assertEqual(data["pins"][0]["name"], "PA0")
        self.assertEqual(data["pins"][0]["anchor"], [100000, 0])
        self.assertEqual(data["definition_sha256"], "b" * 64)
        self.assertTrue(data["path"].startswith("resource:"))

    def test_registered_inputs_get_virtual_ids_and_public_help_links_remain_usable(self):
        result = {"payload": {"action": "help", "data": {"content":
            "Read https://github.com/Lorentz-Caldfilis/fish-proteus817-skill/blob/main/README.md; "
            "native coordinates 100000 = 1 mm.", "path": "C:\\Inputs\\follow.hex"}}}
        output = self.project(result, {"inputs": {"firmware": {"follow": "C:\\Inputs\\follow.hex"}}})
        self.assertEqual(output["payload"]["data"]["path"], "input:follow")
        self.assertIn("https://github.com/", output["payload"]["data"]["content"])
        self.assertIn("100000 = 1 mm", output["payload"]["data"]["content"])
        for url in (
            "https://github.com/Lorentz-Caldfilis/another-project/README.md",
            "https://github.com/Lorentz-Caldfilis/fish-proteus817-skill-extra/README.md",
            "https://github.com/Lorentz-Caldfilis/fish-proteus817-skill/README.md?token=private",
            "https://github.com@private.example/fish-proteus817-skill/README.md",
        ):
            with self.subTest(url=url):
                hidden = self.project({"payload": {"action": "help", "data": {"content": "Read " + url}}})
                self.assertNotIn("https://", hidden["payload"]["data"]["content"])

    def test_failed_native_diagnostic_remains_a_failure_without_raw_stderr(self):
        result = {"exit_code": 2, "stderr": "RAW_STDERR_SENTINEL", "payload": {
            "action": "run_sequence", "status": "blocked", "diagnostic_tail": "RAW_TAIL_SENTINEL",
            "error": {"type": "TLSFailure", "message": "TLS host-name certificate mismatch; debug '/var/private/native.log'"},
            "data": {"checks": [{"type": "no_errors", "passed": False,
                                   "actual": ["TLS host-name certificate mismatch"]}]}}}
        output = self.project(result)
        self.assertEqual(output["exit_code"], 2)
        self.assertEqual(output["payload"]["status"], "blocked")
        self.assertEqual(output["payload"]["error"]["type"], "TLSFailure")
        self.assertIn("TLS host-name certificate mismatch", output["payload"]["error"]["message"])
        self.assertFalse(output["payload"]["data"]["checks"][0]["passed"])
        for private in ("RAW_STDERR_SENTINEL", "RAW_TAIL_SENTINEL", "/var/private"):
            self.assertNotIn(private, json.dumps(output))

    def test_real_json_decoder_preserves_positive_negative_nested_large_integer_tokens(self):
        raw = ('{"positive":9007199254740993,"negative":-9007199254740993,'
               '"filetime":134375348473988092,"nested":[{"value":18446744073709551615},'
               '-18446744073709551616],"positive_boundary":9007199254740992,'
               '"negative_boundary":-9007199254740992,"safe_positive":9007199254740991,'
               '"safe_negative":-9007199254740991,"small":42}')
        output = self.node_from_raw(raw, "console.log(JSON.stringify(parseCliJSON(raw.toString('utf8'))));")
        self.assertEqual(output["positive"], "9007199254740993")
        self.assertEqual(output["negative"], "-9007199254740993")
        self.assertEqual(output["filetime"], "134375348473988092")
        self.assertEqual(output["nested"], [{"value": "18446744073709551615"}, "-18446744073709551616"])
        self.assertEqual(output["positive_boundary"], "9007199254740992")
        self.assertEqual(output["negative_boundary"], "-9007199254740992")
        self.assertEqual(output["safe_positive"], 9007199254740991)
        self.assertEqual(output["safe_negative"], -9007199254740991)
        self.assertEqual(output["small"], 42)

    def test_normal_numbers_floats_exponents_and_quoted_numeric_strings_keep_types(self):
        raw = ('{"safe":42,"fraction":0.6525,"negative":-1.25,"exponent":1.5e3,'
               '"large_float":9007199254740993.0,"large_exponent":9007199254740993e0,'
               '"negative_zero":-0,"quoted":"9007199254740993",'
               '"escaped":"escaped \\" quote and \\\\ slash 9007199254740993"}')
        output = self.node_from_raw(raw,
            "const value=parseCliJSON(raw.toString('utf8'));console.log(JSON.stringify({value,"
            "types:Object.fromEntries(Object.entries(value).map(([k,v])=>[k,typeof v])),"
            "negative_zero_preserved:Object.is(value.negative_zero,-0)}));")
        expected = json.loads(raw)
        for key in ("safe", "fraction", "negative", "exponent", "large_float", "large_exponent"):
            self.assertEqual(output["types"][key], "number")
            self.assertEqual(output["value"][key], float(expected[key]))
        self.assertTrue(output["negative_zero_preserved"])
        for key in ("quoted", "escaped"):
            self.assertEqual(output["types"][key], "string")
            self.assertEqual(output["value"][key], expected[key])

    def test_invalid_json_is_not_repaired_by_quoting_large_integers(self):
        invalid = [
            '{9007199254740993:0}', '{"x":9007199254740993 "y":0}',
            '{"x":09007199254740993}', '{"x":+9007199254740993}',
            '{"x":9007199254740993,}', '[9007199254740993,]',
            '{"x":9007199254740993.}', '{"x":9007199254740993e}',
            '{"x":"unterminated 9007199254740993}', '{"x":"\\q9007199254740993"}',
            '[9007199254740993] trailing', '',
        ]
        for raw in invalid:
            with self.subTest(raw=raw):
                output = self.node_from_raw(raw,
                    "try {parseCliJSON(raw.toString('utf8'));console.log(JSON.stringify({accepted:true}));}"
                    "catch(error){console.log(JSON.stringify({accepted:false,type:error.name}));}")
                self.assertFalse(output["accepted"])
                self.assertEqual(output["type"], "SyntaxError")

    def test_original_stdout_bytes_hash_stay_local_while_exact_identity_reaches_projection(self):
        raw = ('{"action":"run_sequence","status":"runtime_observed","data":{'
               '"identity":{"created_filetime_100ns":134375348473988092,"pid":2468},'
               '"units_per_mm":100000,"simulation_seconds":0.6525,'
               '"secret":"SYNTHETIC_SECRET_STDOUT","raw_native_log":"RAW_STDOUT_SENTINEL",'
               '"stdout_base64":"SMALL_BINARY_SENTINEL","stdout_sha256":"PRIVATE_STDOUT_HASH",'
               '"events":[{"ref":"U1","port":0,"pin":5,"value":1,"seconds":0.352524}]}}')
        output = self.node_from_raw(raw,
            "const local={exit_code:0,...decodeCliStdout(raw)};"
            "console.log(JSON.stringify({local,model:projectModelResponse(local)}));")
        local, model = output["local"], output["model"]
        self.assertEqual(local["stdout"], raw)
        self.assertEqual(base64.b64decode(local["stdout_base64"]), raw.encode())
        self.assertEqual(local["stdout_bytes"], len(raw.encode()))
        self.assertEqual(local["stdout_sha256"], hashlib.sha256(raw.encode()).hexdigest())
        self.assertTrue(local["stdout_utf8_valid"])
        self.assertEqual(local["payload"]["data"]["identity"]["created_filetime_100ns"], "134375348473988092")
        self.assertEqual(model["payload"]["data"]["identity"]["created_filetime_100ns"], "134375348473988092")
        self.assertEqual(model["payload"]["data"]["simulation_seconds"], .6525)
        self.assertEqual(model["payload"]["data"]["events"][0]["value"], 1)
        self.assertIn("decimal strings", model["model_projection"]["integer_encoding"])
        text = json.dumps(model)
        for private in ("SYNTHETIC_SECRET_STDOUT", "RAW_STDOUT_SENTINEL", "SMALL_BINARY_SENTINEL",
                        "PRIVATE_STDOUT_HASH", local["stdout_base64"], local["stdout_sha256"]):
            self.assertNotIn(private, text)
        self.assertNotIn("stdout", model)

    def test_invalid_stdout_is_retained_locally_and_error_projection_stays_closed(self):
        for raw in (b'{"secret":"SYNTHETIC_INVALID_SECRET",', b'{"invalid":"\xff"}'):
            with self.subTest(raw=raw):
                output = self.node_from_raw(raw,
                    "const local={exit_code:2,...decodeCliStdout(raw)};"
                    "console.log(JSON.stringify({local,model:projectModelResponse(local)}));")
                local, model = output["local"], output["model"]
                self.assertEqual(base64.b64decode(local["stdout_base64"]), raw)
                self.assertEqual(local["stdout_sha256"], hashlib.sha256(raw).hexdigest())
                self.assertEqual(local["payload"]["status"], "blocked")
                self.assertEqual(model["payload"]["status"], "blocked")
                self.assertNotIn("diagnostic_tail", model["payload"])
                self.assertNotIn("SYNTHETIC_INVALID_SECRET", json.dumps(model))
                self.assertNotIn(local["stdout_base64"], json.dumps(model))
                self.assertEqual(local["stdout_utf8_valid"], b'\xff' not in raw)


if __name__ == "__main__":
    unittest.main()
