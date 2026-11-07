"""Offline policy evidence; no claim about a school's Windows I/O trace."""
import json
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import types
from unittest.mock import patch, Mock

from fish_proteus import host_paths as paths
from fish_proteus.design_cli import _make_log_directory, _remove_log_directory
from runtime_adaptation.scope_layout import validate_scope_layout


class HostPathTests(unittest.TestCase):
    def test_proteus_discovery_does_not_apply_write_policy_to_read_only_resources(self):
        from fish_proteus.config import ProteusConfig
        with patch.object(paths, 'validate_location', side_effect=AssertionError('write check on read resource')):
            config = ProteusConfig.discover(executable=r'C:\Proteus\BIN\PDS.EXE',
                                           library_root=r'C:\Proteus\DATA\LIBRARY')
        self.assertIn('PDS.EXE', str(config.executable))

    def test_pds_launch_has_explicit_temp_and_project_cwd(self):
        import runtime_adaptation
        native = types.ModuleType('runtime_adaptation.native')
        native.u = Mock()
        source = Path(__file__).resolve().parents[1] / 'runtime_adaptation/session.py'
        spec = importlib.util.spec_from_file_location('runtime_adaptation._path_test_session', source)
        module = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {'runtime_adaptation.native': native}), \
                patch.object(runtime_adaptation, 'native', native, create=True):
            spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve(); project = root / 'job.pdsprj'; project.touch()
            install = root / 'installation'; install.mkdir(); exe = install / 'PDS.EXE'; exe.touch()
            selected = root / 'selected-temp'
            with patch.dict(os.environ, {'FISH_PROTEUS_TEMP_DIR': str(selected)}), \
                    patch.object(module.subprocess, 'STARTUPINFO', return_value=types.SimpleNamespace(dwFlags=0), create=True), \
                    patch.object(module.subprocess, 'STARTF_USESHOWWINDOW', 1, create=True), \
                    patch.object(module.subprocess, 'Popen') as popen, \
                    patch.object(module.Session, '_wait'), patch.object(module.time, 'sleep'):
                module.Session(project, exe)
            self.assertEqual(popen.call_args.kwargs['cwd'], root)
            env = popen.call_args.kwargs['env']
            self.assertEqual(env['TEMP'], str(selected))
            self.assertEqual(env['TMP'], env['TEMP'])
            self.assertEqual(list(install.iterdir()), [exe])

    def test_ocr_launch_has_explicit_temp_and_scaled_timeout(self):
        from test_runtime_timing import controller_for, DesktopFake
        module,_ = controller_for(DesktopFake())
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve(); selected = root / 'selected-temp'
            result = types.SimpleNamespace(returncode=0, stdout=b'{"Text":"fixture"}', stderr=b'')
            with patch.dict(os.environ, {'FISH_PROTEUS_TEMP_DIR': str(selected), 'FISH_PROTEUS_TIMEOUT_SCALE': '2'}), \
                    patch.object(module.subprocess, 'run', Mock(return_value=result)) as run:
                module.read_ocr(root / 'image.png', root / 'ocr.json')
            self.assertEqual(run.call_args.kwargs['env']['TEMP'], str(selected))
            self.assertEqual(run.call_args.kwargs['timeout'], 80)

    @unittest.skipUnless(shutil.which('node'), 'Node unavailable')
    def test_legacy_bridge_reaches_real_child_without_creating_job_early(self):
        module = (Path(__file__).resolve().parents[1] / 'tools/dsh_project_tool.mjs').as_uri()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve(); gate = root / 'gate.py'; sdk = root / 'sdk.mjs'
            gate.write_text('import json,os,sys\njson.load(sys.stdin)\nprint(json.dumps(dict(os.environ)))\n')
            sdk.write_text('export const defineTool = value => value;')
            config = dict(workspace=str(root), python=sys.executable, gate=str(gate), library=str(root/'library'),
                          jobDirectory=str(root/'.work/job'), auditPath=str(root/'.work/audit.jsonl'),
                          toolsModule=sdk.as_uri(), allowedOperations=['doctor'])
            code = ('import {apply} from ' + json.dumps(module) + ';'
                    'let tool; await apply({tools:{register:t=>tool=t,guard:()=>{}}},' + json.dumps(config) + ');'
                    'console.log(JSON.stringify(await tool.execute({operation:"doctor"},{})));')
            env = {**os.environ, 'FISH_PROTEUS_TEMP_DIR':str(root/'temp'),
                   'FISH_PROTEUS_EXE':r'C:\Proteus\PDS.EXE', 'FISH_PROTEUS_NASM':r'D:\nasm.exe',
                   'DEEPSEEK_API_KEY':'synthetic-private'}
            result = subprocess.run([shutil.which('node'), '--input-type=module', '-e', code],
                                    capture_output=True, text=True, env=env, check=True)
            observed = json.loads(result.stdout)['payload']
            for key in ('FISH_PROTEUS_EXE', 'FISH_PROTEUS_NASM', 'FISH_PROTEUS_TEMP_DIR'):
                self.assertEqual(observed[key], env[key])
            self.assertEqual(observed['TEMP'], env['FISH_PROTEUS_TEMP_DIR'])
            self.assertEqual(observed['TMP'], observed['TEMP'])
            self.assertNotIn('DEEPSEEK_API_KEY', observed)
            self.assertFalse((root/'.work/job').exists())

    def test_windows_drive_policy_is_case_insensitive_and_uses_systemdrive(self):
        env = {"SystemDrive": "C:", "FISH_PROTEUS_STRICT_NON_SYSTEM_DRIVE": "1"}
        for value in (r"C:\temp", r"c:\temp", r"\\server\share", r"D:relative"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                paths.validate_location(value, windows=True, environ=env)
        paths.validate_location(r"D:\temp", windows=True, environ=env)
        for system in ('', 'invalid'):
            with self.assertRaises(ValueError):
                paths.validate_location(r'C:\temp', windows=True, environ={**env, 'SystemDrive': system})
        with self.assertRaises(ValueError):
            paths.validate_location(r"D:\temp", windows=True, environ={**env, "SystemDrive": "D:"})
        paths.validate_location(r"D:\中文仓库", windows=True, environ=env)
        with self.assertRaises(ValueError):
            paths.validate_location(r"D:\中文临时", ascii_only=True, windows=True, environ=env)

    def test_no_default_temp_or_home_fallback(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(tempfile, 'gettempdir', side_effect=AssertionError), \
                patch.object(Path, 'home', side_effect=AssertionError):
            with self.assertRaisesRegex(ValueError, 'No temporary root'):
                paths.temp_root()

    def test_rejection_precedes_mkdir_and_probe(self):
        with patch.object(paths, 'check_path', side_effect=ValueError('system drive')), \
                patch.object(Path, 'mkdir') as mkdir, patch.object(tempfile, 'mkstemp') as probe:
            with self.assertRaises(ValueError):
                paths.writable_directory(r'C:\forbidden')
            mkdir.assert_not_called(); probe.assert_not_called()

    def test_explicit_temp_probe_and_staging_stay_beneath_selected_root(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            selected = root / 'ascii-temp'
            with patch.dict(os.environ, {'FISH_PROTEUS_TEMP_DIR': str(selected)}), \
                    patch.object(tempfile, 'gettempdir', side_effect=AssertionError):
                env = paths.child_environment(root, base={'marker': 'kept'})
                self.assertEqual(env['TEMP'], str(selected))
                self.assertEqual(env['TMP'], env['TEMP'])
                self.assertEqual(list(selected.iterdir()), [])
                stage = _make_log_directory(root / '中文任务')
                self.assertEqual(stage.parent, selected)
                _remove_log_directory(stage)
                self.assertEqual(list(selected.iterdir()), [])

    def test_bad_explicit_temp_does_not_fall_back_to_valid_anchor(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for selected in ('relative', str(root / '中文')):
                with patch.dict(os.environ, {'FISH_PROTEUS_TEMP_DIR': selected}), \
                        patch.object(Path, 'mkdir') as mkdir:
                    with self.assertRaises(ValueError): paths.temp_root(root)
                    mkdir.assert_not_called()
            with patch.dict(os.environ, {'FISH_PROTEUS_TEMP_DIR': str(root / 'unwritable')}), \
                    patch.object(tempfile, 'mkstemp', side_effect=PermissionError('denied')) as probe:
                with self.assertRaises(PermissionError): paths.temp_root(root)
                self.assertEqual(probe.call_count, 1)
                self.assertEqual(probe.call_args.kwargs['dir'], root / 'unwritable')
                self.assertFalse((root / '.work').exists())

    def test_symlink_destination_is_resolved_before_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve(); actual = root / 'actual'; actual.mkdir()
            try: (root / 'link').symlink_to(actual, target_is_directory=True)
            except OSError: self.skipTest('Symlink privilege unavailable')
            with patch.object(paths, 'validate_location') as validate:
                paths.check_path(root / 'link' / 'new')
                self.assertEqual(validate.call_args.args[0], actual / 'new')

    def test_scope_layout_rejects_offscreen_size_dpi_and_hidden(self):
        validate_scope_layout((0, 0, 1380, 900), (0, 0, 1920, 1040), 96, True)
        for rect, area, dpi, visible in [
            ((0, 0, 1380, 900), (0, 0, 1366, 728), 96, True),
            ((0, 0, 1380, 900), (0, 0, 1920, 1040), 120, True),
            ((-50, 0, 1330, 900), (0, 0, 1920, 1040), 96, True),
            ((0, 0, 1200, 800), (0, 0, 1920, 1040), 96, True),
            ((0, 0, 1380, 900), (0, 0, 1920, 1040), 96, False),
        ]:
            with self.assertRaisesRegex(ValueError, 'Unsupported oscilloscope layout'):
                validate_scope_layout(rect, area, dpi, visible)

    def test_timeout_scale_rejects_invalid_values(self):
        for value in ('0', '-1', 'nan', 'inf', '21', 'oops'):
            with patch.dict(os.environ, {'FISH_PROTEUS_TIMEOUT_SCALE': value}), self.assertRaises(ValueError):
                paths.timeout_scale()

    @unittest.skipUnless(shutil.which('node'), 'Node unavailable')
    def test_js_child_environment_uses_validated_temp_and_keeps_only_allowed_values(self):
        module = (Path(__file__).resolve().parents[1] / 'tools/host_paths.mjs').as_uri()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            code = 'import {childEnvironment} from ' + json.dumps(module) + '; console.log(JSON.stringify(childEnvironment(process.argv[1])));'
            env = {**os.environ, 'FISH_PROTEUS_TEMP_DIR': str(root / 'temp'),
                   'FISH_PROTEUS_EXE': r'C:\Proteus\BIN\PDS.EXE', 'FISH_PROTEUS_NASM': r'D:\nasm.exe',
                   'DEEPSEEK_API_KEY': 'synthetic-do-not-forward', 'TEMP': str(root / 'wrong')}
            result = subprocess.run([shutil.which('node'), '--input-type=module', '-e', code, str(root)],
                                    capture_output=True, text=True, env=env, check=True)
            observed = json.loads(result.stdout)
            self.assertEqual(observed['TEMP'], str(root / 'temp'))
            self.assertEqual(observed['TMP'], observed['TEMP'])
            self.assertEqual(observed['FISH_PROTEUS_EXE'], env['FISH_PROTEUS_EXE'])
            self.assertEqual(observed['FISH_PROTEUS_NASM'], env['FISH_PROTEUS_NASM'])
            self.assertNotIn('DEEPSEEK_API_KEY', observed)
            env['FISH_PROTEUS_TEMP_DIR'] = str(root / '中文')
            result = subprocess.run([shutil.which('node'), '--input-type=module', '-e', code, str(root)],
                                    capture_output=True, text=True, env=env)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse((root / '中文').exists())
