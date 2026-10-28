"""Exercise timing completion with an owned-desktop fake, without Windows UI."""
import ctypes
import importlib.util
from pathlib import Path
import types
import unittest
from unittest.mock import Mock, patch

import runtime_adaptation


class DesktopFake:
    def __init__(self, native_pause=True, readback=None):
        self.native_pause=native_pause
        self.readback=readback
        self.typed=''
        self.now=0.0
        self.state='paused'
        self.pause_calls=0
        self.timer_accepted=False
        self.window_available=True

    def message(self, hwnd, message, wp=0, lp=0):
        if message==0xB1:self.typed=''
        elif message==0x102:self.typed+=chr(wp)
        elif message==0xD:
            buffer=ctypes.create_unicode_buffer(self.typed if self.readback is None else self.readback)
            ctypes.memmove(lp,buffer,ctypes.sizeof(buffer))
        elif message==0x111:
            self.timer_accepted=True
            self.state='paused' if self.native_pause else 'running'

    def pause(self):
        self.pause_calls+=1
        self.state='paused'
        return {'state':self.state,'simulation_seconds':None}

    def wait(self, condition, timeout=15):
        result=condition()
        if not result:raise TimeoutError('Owned PID/window unavailable')
        return result

    def sleep(self, seconds):
        self.now+=seconds


def controller_for(desktop):
    # Only the UI dependency boundary is replaced. Load the actual controller
    # source and run its real run_timed method on every supported CI platform.
    native=types.ModuleType('runtime_adaptation.native')
    native.message=desktop.message
    session=types.ModuleType('runtime_adaptation.session')
    session.Session=object
    path=Path(__file__).resolve().parents[1]/'runtime_adaptation'/'controller.py'
    spec=importlib.util.spec_from_file_location('runtime_adaptation._timing_unit_controller',path)
    module=importlib.util.module_from_spec(spec)
    with patch.dict('sys.modules',{'runtime_adaptation.native':native,'runtime_adaptation.session':session}), \
         patch.object(runtime_adaptation,'native',native,create=True):
        spec.loader.exec_module(module)
    controller=object.__new__(module.Controller)
    controller.pause=desktop.pause
    controller.menu=Mock()
    controller._dialog=Mock(return_value={'hwnd':9,'children':[{'cls':'Edit','control_id':257,'hwnd':7}]})
    controller._click=Mock()
    controller._wait=desktop.wait
    controller._ready=lambda: {'hwnd':1} if desktop.window_available else None
    controller.state=lambda: {'state':desktop.state,'simulation_seconds':None,'method':'fake-owned-native-menu'}
    return module,controller


class RuntimeTimingTests(unittest.TestCase):
    def run_timer(self, desktop, clocks, seconds=.1):
        module,controller=controller_for(desktop)
        controller.clock=Mock(side_effect=clocks)
        with patch.object(module.time,'monotonic',lambda: desktop.now), \
             patch.object(module.time,'sleep',desktop.sleep):
            result=controller.run_timed(seconds)
        return result,controller

    def test_unreadable_start_and_end_clocks_do_not_block_native_pause(self):
        result,controller=self.run_timer(DesktopFake(),[ValueError('decimal missing'),RuntimeError('OCR failed')])
        self.assertEqual(result['state'],'paused')
        self.assertFalse(result['actual_time_verified'])
        self.assertIsNone(result['simulation_seconds'])
        self.assertEqual([d['phase'] for d in result['timing_diagnostics']],['timer-start','timer-end'])
        self.assertEqual([call.args[0] for call in controller.clock.call_args_list],['timer-start','timer-end'])

    def test_zero_ocr_elapsed_is_diagnostic_instead_of_fatal(self):
        result,_=self.run_timer(DesktopFake(),[{'simulation_seconds':0.0},{'simulation_seconds':0.0}])
        self.assertFalse(result['actual_time_verified'])
        self.assertIsNone(result['simulation_seconds'])
        self.assertEqual(result['clock_elapsed_seconds'],0.0)
        self.assertEqual(result['timing_diagnostics'][0]['phase'],'timer-end')

    def test_matching_optional_clock_readings_can_verify_native_completion(self):
        result,_=self.run_timer(DesktopFake(),[{'simulation_seconds':1.0},{'simulation_seconds':1.1}])
        self.assertTrue(result['actual_time_verified'])
        self.assertEqual(result['simulation_seconds'],1.1)

    def test_hanging_native_timer_gets_bounded_pause_without_inventing_time(self):
        desktop=DesktopFake(native_pause=False)
        result,_=self.run_timer(desktop,[ValueError('unreadable'),ValueError('unreadable')],seconds=2.2)
        self.assertEqual(result['completion'],'bounded-capture-pause-unverified-duration')
        self.assertEqual(desktop.pause_calls,2)
        self.assertLessEqual(desktop.now,result['capture_wait_wall_seconds']+.26)
        self.assertFalse(result['actual_time_verified'])
        self.assertIsNone(result['simulation_seconds'])

    def test_native_input_readback_mismatch_remains_fatal(self):
        desktop=DesktopFake(readback='incorrect')
        with self.assertRaisesRegex(RuntimeError,'Timer input read-back mismatch'):
            self.run_timer(desktop,[ValueError('unreadable')])
        self.assertFalse(desktop.timer_accepted)

    def test_optional_clock_failure_does_not_hide_lost_owned_window(self):
        desktop=DesktopFake()
        def clock(label):
            if label=='timer-end':
                desktop.window_available=False
                raise RuntimeError('OCR could not capture the window')
            return {'simulation_seconds':0.0}
        with self.assertRaisesRegex(TimeoutError,'Owned PID/window unavailable'):
            self.run_timer(desktop,clock)


if __name__=='__main__':
    unittest.main()
