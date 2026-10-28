import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from runtime_adaptation.runner import _cleanup_stage, _stage, _switch_binding_slots, run_job


class RuntimeIntegrityTests(unittest.TestCase):
    def setUp(self):
        work=Path(__file__).resolve().parents[1]/'.work'
        work.mkdir(exist_ok=True)
        self.workspace=tempfile.TemporaryDirectory(prefix='test-runtime-',dir=work)
        if not Path(self.workspace.name).resolve().is_relative_to(work.resolve()):
            raise RuntimeError('Test directory escaped the workspace')
        self.addCleanup(self.workspace.cleanup)
        previous=tempfile.tempdir
        tempfile.tempdir=self.workspace.name
        self.addCleanup(setattr,tempfile,'tempdir',previous)

    def make_job(self, root):
        root=Path(root)
        source=root/'8086/main.asm';source.parent.mkdir(parents=True)
        source.write_text('CODE SEGMENT\nN: JMP N\nCODE ENDS\nEND N\n',encoding='utf-8')
        executable=root/'8086/Debug/Debug.exe';executable.parent.mkdir()
        executable.write_bytes(b'MZ'+bytes(30))
        project=root/'T8253.pdsprj'
        dsn=(b'binary-prefix\0PROPERTIES\0\0\0\0{MODDLL=DSO.DLL}\n'
             b'{HORIZSRC=0}\n{HORIZVAL=9.9999999999999995e-007}\n{HORIZPOS=200}\n\0tail')
        with zipfile.ZipFile(project,'w') as archive:
            archive.writestr('ROOT.DSN',dsn)
            archive.writestr('ROOT.CDB',b'untouched-netlist-data')
            archive.writestr('FIRMWARE/8086.XML',b'<PROJECT BUILDPATH="old"><FILES /></PROJECT>')
        sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
        job={'case_id':'cascade','job_root':str(root),'job_file':str(root/'job.json'),
             'source':str(source),'executable':str(executable),'project':str(project),
             'build':{'status':'built','source_sha256':sha(source),'artifact':{'sha256':sha(executable)}},
             'runtime':{'status':'not_run'}}
        (root/'job.json').write_text(json.dumps(job),encoding='utf-8')
        return job,dsn

    def test_staging_preserves_originals_and_binary_record_lengths(self):
        with tempfile.TemporaryDirectory() as directory:
            job,dsn=self.make_job(directory)
            before=Path(job['project']).read_bytes()
            stage,paths=_stage(job)
            try:
                self.assertEqual(Path(job['project']).read_bytes(),before)
                self.assertEqual(paths['executable'].read_bytes(),Path(job['executable']).read_bytes())
                with zipfile.ZipFile(paths['project']) as archive:
                    staged_dsn=archive.read('ROOT.DSN')
                    self.assertEqual(len(staged_dsn),len(dsn))
                    self.assertEqual(staged_dsn,dsn.replace(b'9.9999999999999995e-007',b'1.0000000000000001e-001'))
                    self.assertEqual(archive.read('ROOT.CDB'),b'untouched-netlist-data')
            finally:_cleanup_stage(stage)

    def test_stale_source_is_blocked_before_any_desktop_import(self):
        with tempfile.TemporaryDirectory() as directory:
            job,_=self.make_job(directory)
            Path(job['source']).write_text('changed after build',encoding='utf-8')
            result=run_job(job['job_file'])
            self.assertEqual(result['status'],'blocked')
            self.assertNotIn('pid',result)
            latest=json.loads((Path(directory)/'runtime.json').read_text(encoding='utf-8'))
            manifest=json.loads(Path(job['job_file']).read_text(encoding='utf-8'))
            self.assertEqual(latest['runtime_file'],result['runtime_file'])
            self.assertEqual(manifest['runtime']['file'],result['runtime_file'])

    def test_changed_binary_is_blocked_before_desktop_import(self):
        with tempfile.TemporaryDirectory() as directory:
            job,_=self.make_job(directory)
            Path(job['executable']).write_bytes(b'different artifact')
            result=run_job(job['job_file'])
            self.assertEqual(result['status'],'blocked')
            self.assertNotIn('pid',result)

    def test_manifest_root_mismatch_cannot_redirect_output(self):
        with tempfile.TemporaryDirectory() as directory:
            job,_=self.make_job(directory)
            job['job_root']=str(Path(directory)/'8086')
            Path(job['job_file']).write_text(json.dumps(job),encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'Manifest parent'):
                run_job(job['job_file'])
            self.assertFalse((Path(directory)/'8086/runtime').exists())

    def test_invalid_duration_has_no_runtime_side_effect(self):
        with tempfile.TemporaryDirectory() as directory:
            job,_=self.make_job(directory)
            for duration in (float('nan'),float('inf'),-1,0):
                with self.assertRaises(ValueError):run_job(job['job_file'],seconds=duration)
            self.assertFalse((Path(directory)/'runtime').exists())

    def test_actuator_bindings_reserve_other_components_and_k0_key(self):
        netlist={'parts':{'K0':{'device':'SWITCH','properties':{'KEY':'1'}},
                          'OTHER':{'device':'BUTTON','properties':{'INC':'2','DEC':'3'}}}}
        self.assertEqual(_switch_binding_slots(netlist),['4','5'])
        netlist['parts']['OTHER']['properties']['INC']='16'
        with self.assertRaisesRegex(ValueError,'Unrecognized actuator binding'):
            _switch_binding_slots(netlist)


if __name__=='__main__':
    unittest.main()
