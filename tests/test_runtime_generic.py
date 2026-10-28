"""Native timing and ownership policy without a Proteus or Windows desktop."""
import ctypes
import hashlib
import os
from pathlib import Path
import tempfile
import threading
import types
import unittest
from unittest.mock import Mock,patch

from runtime_adaptation import generic
from runtime_adaptation.profile817 import CompatibilityError,profile_for,PROFILE817


class TimerFake:
    def __init__(self,states):
        self.states=iter(states);self.last=states[-1];self.typed=''
        self.session=object.__new__(generic.Session)
        self.session._lock=threading.RLock();self.session.operations=[]
        self.session._dialog=Mock(return_value={'hwnd':9,'children':[{'cls':'Edit','control_id':257,'hwnd':7}]})
        self.session._wait=self.wait
        self.simulation=generic.Simulation(self.session)
        self.simulation.status=self.status
        self.simulation._menu=Mock();self.simulation._message=self.message
        self.simulation.pause=Mock()
    def status(self):return dict(next(self.states,self.last))
    def wait(self,condition,timeout=15):
        for _ in range(4):
            value=condition()
            if value:return value
        raise TimeoutError('Native target was not observed')
    def message(self,hwnd,message,wp=0,lp=0):
        if message==0xB1:self.typed=''
        elif message==0x102:self.typed+=chr(wp)
        elif message==0xD:
            buffer=ctypes.create_unicode_buffer(self.typed)
            ctypes.memmove(lp,buffer,ctypes.sizeof(buffer))


def state(seconds,kind='paused',remaining=0):
    return {'state':kind,'simulation_seconds':seconds,'timer_remaining_seconds':remaining,
            'native_state':3 if kind=='paused' else 0,'actual_time_verified':seconds is not None}


class GenericRuntimeTests(unittest.TestCase):
    def test_requested_duration_uses_actual_relative_start(self):
        fake=TimerFake([state(.05),state(.060000000000000005)])
        result=fake.simulation.run_for(.01)
        self.assertEqual(result['start_seconds'],.05)
        self.assertAlmostEqual(result['actual_elapsed_seconds'],.01)
        self.assertTrue(result['actual_time_verified'])

    def test_missing_native_clock_does_not_fall_back_to_request_or_wall_time(self):
        fake=TimerFake([state(None)])
        with self.assertRaisesRegex(RuntimeError,'initialized native clock'):
            fake.simulation.run_for(.01)
        fake.simulation._menu.assert_not_called()

    def test_native_pause_before_target_is_not_success(self):
        fake=TimerFake([state(.05),state(.055)])
        with self.assertRaisesRegex(TimeoutError,'not observed'):
            fake.simulation.run_for(.01)

    def test_engine_clock_lost_after_timer_submission_is_explicit_failure(self):
        fake=TimerFake([state(.05),state(None,'stopped')])
        with self.assertRaisesRegex(RuntimeError,'clock became unavailable'):
            fake.simulation.run_for(.01)

    def test_overshoot_tolerance_is_enforced(self):
        fake=TimerFake([state(.05),state(.064)])
        with self.assertRaisesRegex(RuntimeError,'overshot'):
            fake.simulation.run_for(.01,tolerance_seconds=.003)

    def test_roundoff_pause_requires_positive_nonadvancing_remainder(self):
        fake=TimerFake([state(.05),state(.06,'running',1e-300),state(.06)])
        result=fake.simulation.run_for(.01)
        self.assertEqual(result['completion'],'timer_roundoff_pause')
        self.assertEqual(result['roundoff_remaining_seconds'],1e-300)
        fake.simulation.pause.assert_called_once()

    def test_unknown_binary_is_refused_before_any_desktop_launch(self):
        root=Path(__file__).resolve().parents[1]/'.work'
        with tempfile.TemporaryDirectory(prefix='generic-runtime-test-',dir=root) as directory:
            executable=Path(directory)/'PDS.EXE';executable.write_bytes(b'MZ-unrecognized-build')
            with self.assertRaisesRegex(CompatibilityError,'Unsupported PDS'):
                profile_for(executable)

    def test_final_log_cache_preserves_raw_identity_and_reads_after_close(self):
        root=Path(__file__).resolve().parents[1]/'.work'
        with tempfile.TemporaryDirectory(prefix='generic-runtime-test-',dir=root) as directory:
            path=Path(directory)/'native.log'
            raw=b'#T:[GPIO] drive PIO0.5 = 1\r\n%T=0.125\r\n%S=U1_SYSINTERFACE\r\n%E=0001\r\n'
            path.write_bytes(raw)
            session=object.__new__(generic.Session)
            session.logfile=path;session.normal_closed=True;session._log_option_changed=False
            session.last_active_status=state(.2);session.log_metadata={};session._final_log_text=None
            session._finish_logfile(True)
            simulation=generic.Simulation(session)
            self.assertEqual(session.final_logfile_sha256,hashlib.sha256(raw).hexdigest())
            self.assertTrue(session.log_metadata['complete'])
            self.assertEqual(session.log_metadata['through_clock_seconds'],.2)
            path.write_bytes(b'external later modification')
            self.assertEqual(simulation.log(),raw.decode())
            self.assertEqual(simulation.gpio_events(ref='U1',port=0,pin=5),
                             [{'ref':'U1','port':0,'pin':5,'value':1,'seconds':.125}])

    def test_live_buffer_is_not_a_final_log_even_if_it_contains_text(self):
        session=object.__new__(generic.Session)
        session.logfile=Path('native.log');session.normal_closed=False;session._final_log_text='partial'
        with self.assertRaisesRegex(RuntimeError,'normal Session.close'):
            generic.Simulation(session).log()

    def test_log_capture_requires_explicit_opt_in_without_clipboard_fallback(self):
        session=object.__new__(generic.Session)
        session.logfile=None
        with self.assertRaisesRegex(RuntimeError,'requires Session'):
            generic.Simulation(session).log()

    def test_log_restore_never_overwrites_an_external_project_edit(self):
        root=Path(__file__).resolve().parents[1]/'.work'
        with tempfile.TemporaryDirectory(prefix='generic-runtime-test-',dir=root) as directory:
            path=Path(directory)/'task.pdsprj';path.write_bytes(b'owned earlier revision')
            session=object.__new__(generic.Session)
            session.project=path;session._revision=hashlib.sha256(path.read_bytes()).hexdigest()
            session._log_option_changed=True
            path.write_bytes(b'external subsequent revision')
            with patch('fish_proteus.simulation_options.set_simulation_options') as setter:
                with self.assertRaisesRegex(RuntimeError,'changed externally'):
                    session._restore_logfile()
            setter.assert_not_called()
            self.assertEqual(path.read_bytes(),b'external subsequent revision')

    def test_creation_time_failure_cleans_up_the_partial_owned_controller(self):
        root=Path(__file__).resolve().parents[1]/'.work'
        with tempfile.TemporaryDirectory(prefix='generic-runtime-test-',dir=root) as directory:
            project=Path(directory)/'task.pdsprj';project.write_bytes(b'private test project')
            executable=Path(directory)/'PDS.EXE';executable.write_bytes(b'not executed')
            process=Mock(pid=56789);process.poll.side_effect=[None,0]
            class Controller:
                def __init__(self,*args,**kwargs):self.process=process;self.pid=process.pid
            module=types.ModuleType('runtime_adaptation.controller');module.Controller=Controller
            config=types.SimpleNamespace(executable=executable,require=Mock(),check_destination=Mock())
            with patch.dict('sys.modules',{'runtime_adaptation.controller':module}), \
                 patch.object(generic,'os',types.SimpleNamespace(name='nt',path=os.path)), \
                 patch.object(generic,'profile_for',return_value=PROFILE817), \
                 patch.object(generic.Session,'_creation_time',side_effect=OSError('creation read failed')):
                with self.assertRaisesRegex(OSError,'creation read failed') as failure:
                    generic.Session(project,config=config)
            process.terminate.assert_called_once();process.wait.assert_called_once_with(timeout=10)
            self.assertTrue(failure.exception.owned_process_closed)
            self.assertEqual(failure.exception.owned_pid,56789)


if __name__=='__main__':unittest.main()
