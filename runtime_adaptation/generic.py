"""Owned Proteus 8.17 sessions with native numeric time and generic measurements.

The course runner remains independent. This facade fails closed when its exact
native ABI cannot be established; it never substitutes OCR or wall time for the
engine's current time. Offline imports work without Windows; desktop interaction
requires an owned Windows session.
"""
from __future__ import annotations

from datetime import datetime,timezone
import hashlib
import math
import os
from pathlib import Path
import threading
import time

from .profile817 import profile_for
from fish_proteus._vendor.proteus_auto.simulation import Simulation as _ReferenceSimulation


def _sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class Session:
    """One explicitly owned project/PID; save is explicit and close does not save."""
    def __init__(self,project,executable=None,config=None,logfile=None):
        if os.name!='nt':raise OSError('Proteus desktop sessions require interactive Windows')
        from fish_proteus.config import ProteusConfig
        from .controller import Controller
        self.config=config or ProteusConfig.discover(executable=executable)
        self.config.require('executable')
        selected=Path(executable or self.config.executable).resolve(strict=True)
        self.project=Path(project).resolve(strict=True)
        self.config.check_destination(self.project)
        self.native_profile=profile_for(selected)
        self._lock=threading.RLock()
        self._revision=_sha(self.project)
        input_project_sha256=self._revision
        self.operations=[]
        self.logfile=None
        self.final_logfile_sha256=None
        self.normal_closed=False
        self.last_active_status=None
        self.log_metadata={'complete':False,'finalized_after_process_close':False,
                           'through_clock_seconds':None}
        self._final_log_text=None
        self._log_option_changed=False
        if logfile is not None:self._configure_logfile(logfile)
        # Retain the partial controller so a constructor failure cannot orphan
        # its newly created process before assignment returns to this facade.
        self._desktop=Controller.__new__(Controller)
        try:
            Controller.__init__(self._desktop,self.project,executable=selected)
            self.process=self._desktop.process;self.pid=self._desktop.pid
            self._created=self._creation_time()
        except BaseException as error:
            process=getattr(self._desktop,'process',None)
            if process is not None:
                if process.poll() is None:process.terminate();process.wait(timeout=10)
                error.owned_pid=process.pid
                error.owned_process_closed=process.poll() is not None
            if self._log_option_changed:
                try:self._finish_logfile(False)
                except Exception as cleanup_error:error.log_cleanup_error=str(cleanup_error)
            raise
        self.identity={'pid':self.pid,'created_filetime_100ns':self._created,
                       'opened_at':datetime.now(timezone.utc).isoformat(),
                       'project':str(self.project),'project_sha256':self._revision,
                       'input_project_sha256':input_project_sha256,
                       'executable':str(selected),'profile':self.native_profile.describe()}
        if self.logfile is not None:
            self.identity['native_logfile']=str(self.logfile)

    def _configure_logfile(self,logfile):
        from fish_proteus.simulation_options import read_simulation_options,set_simulation_options
        path=self.config.check_destination(Path(logfile).expanduser().resolve())
        if not str(path).isascii() or any(ord(char)<32 for char in str(path)):
            raise ValueError('Native LOGFILE requires a fresh ASCII path; use an owned ASCII temporary directory')
        if path.exists():raise FileExistsError(path)
        if path==self.project:raise ValueError('LOGFILE cannot be the project itself')
        values=read_simulation_options(self.project)
        self._previous_logfile=values.get('LOGFILE')
        path.parent.mkdir(parents=True,exist_ok=True)
        set_simulation_options(self.project,self.project,{'LOGFILE':str(path)},
                               config=self.config,overwrite=True)
        self._revision=_sha(self.project)
        self._log_option_changed=True
        self.logfile=path
        try:
            if read_simulation_options(self.project).get('LOGFILE')!=str(path):
                raise RuntimeError('The project LOGFILE option did not match its requested owned path')
        except Exception:
            self._restore_logfile()
            raise
        self.log_metadata.update(path=str(path),source='native-project-LOGFILE')

    def _restore_logfile(self):
        if not self._log_option_changed:return
        from fish_proteus.simulation_options import read_simulation_options,set_simulation_options
        if _sha(self.project)!=self._revision:
            raise RuntimeError('The project changed externally; refusing to overwrite it while restoring LOGFILE')
        if read_simulation_options(self.project).get('LOGFILE')!=str(self.logfile):
            raise RuntimeError('The project LOGFILE option changed unexpectedly')
        set_simulation_options(self.project,self.project,{'LOGFILE':self._previous_logfile},
                               config=self.config,overwrite=True)
        self._revision=_sha(self.project);self._log_option_changed=False
        self.operations.append({'operation':'restore_logfile_option','project_sha256':self._revision})

    def _finish_logfile(self,normal):
        if self.logfile is None:return
        try:
            if self.logfile.is_file():
                if self.logfile.stat().st_size>16*1024*1024:
                    raise RuntimeError('Native LOGFILE exceeds its 16 MiB read bound')
                raw=self.logfile.read_bytes()
                self.final_logfile_sha256=hashlib.sha256(raw).hexdigest()
                try:text=raw.decode('utf-8-sig');encoding='utf-8'
                except UnicodeDecodeError:
                    encoding='mbcs' if os.name=='nt' else 'cp1252'
                    text=raw.decode(encoding,errors='replace')
                self._final_log_text=text
                self.log_metadata.update(complete=bool(normal),finalized_after_process_close=True,
                                         bytes=len(raw),sha256=self.final_logfile_sha256,encoding=encoding,
                                         last_active_status=self.last_active_status,
                                         through_clock_seconds=(self.last_active_status or {}).get('simulation_seconds'),
                                         through_clock_basis='last verified active native clock before final process close')
            elif normal:
                raise RuntimeError('The owned Proteus process did not create its configured LOGFILE')
        finally:
            self._restore_logfile()

    def _creation_time(self):
        import ctypes as c
        from ctypes import wintypes as w
        from . import native
        native.k.GetProcessTimes.argtypes=(w.HANDLE,c.POINTER(w.FILETIME),c.POINTER(w.FILETIME),c.POINTER(w.FILETIME),c.POINTER(w.FILETIME))
        native.k.GetProcessTimes.restype=w.BOOL
        fields=[w.FILETIME() for _ in range(4)]
        if not native.k.GetProcessTimes(int(self.process._handle),*[c.byref(value) for value in fields]):
            raise c.WinError(c.get_last_error())
        return (fields[0].dwHighDateTime<<32)|fields[0].dwLowDateTime

    def assert_identity(self):
        if self.process.poll() is not None:raise RuntimeError('The owned Proteus process has exited')
        if self.process.pid!=self.pid or self._creation_time()!=self._created:
            raise RuntimeError('Proteus PID creation identity changed')
        if _sha(self.project)!=self._revision:
            raise RuntimeError('The open project changed on disk; close and reopen before continuing')

    def _ready(self):
        self.assert_identity()
        return self._desktop._ready()

    def _wait(self,condition,timeout=15):return self._desktop._wait(condition,timeout=timeout)
    def _dialog(self,title):return self._desktop._dialog(title)
    def _click(self,dialog,label):return self._desktop._click(dialog,label)
    def _file_dialog(self,title,path):return self._desktop._file_dialog(title,path)

    def menu(self,path):
        with self._lock:
            self.assert_identity();return self._desktop.menu(path)

    def show_schematic(self):
        with self._lock:
            self.assert_identity();return self._desktop.show_schematic()

    def export_netlist(self,destination):
        with self._lock:
            self.assert_identity();return self._desktop.export_netlist(destination)

    def netlist(self):
        with self._lock:
            self.assert_identity();return self._desktop.netlist()

    def set_properties(self,ref,**properties):
        with self._lock:
            self.assert_identity();return self._desktop.set_properties(ref,**properties)

    def save(self):
        with self._lock:
            self.assert_identity();saved=self._desktop.save()
            self._revision=_sha(self.project)
            self.operations.append({'operation':'save','project_sha256':self._revision})
            return saved

    def close(self,*,save=False):
        with self._lock:
            if self.process.poll() is not None:
                if self._log_option_changed:self._finish_logfile(self.normal_closed)
                return self.process.returncode
            self.assert_identity()
            self._desktop.show_schematic()
            self._desktop.stop()
            if save:self.save()
            result=self._desktop.close()
            self.normal_closed=result==0
            self._finish_logfile(self.normal_closed)
            return result

    def __enter__(self):return self
    def __exit__(self,kind,value,traceback):
        try:self.close()
        except Exception:
            if self.process.poll() is None:self.process.terminate();self.process.wait(timeout=10)
            if self._log_option_changed:self._finish_logfile(False)
            if kind is None:raise


class Simulation(_ReferenceSimulation):
    """Native 8.17 state/time with reference actuator, firmware and log operations."""
    def __init__(self,session):
        if not isinstance(session,Session):raise TypeError('Use the owned 8.17 Session facade')
        self.session=session
        self._known_status_layout=False

    def status(self):
        from fish_proteus._vendor.proteus_auto.interactive_native import snapshot
        with self.session._lock:
            self.session.assert_identity()
            for attempt in range(3):
                try:
                    values=snapshot(self.session,timer=True);break
                except RuntimeError as error:
                    # Loading a CPU/debugger can unload an unrelated module
                    # between EnumProcessModules and its filename query. Retry
                    # the entire checked snapshot, never accept a partial list.
                    if str(error)!='Proteus module path could not be read' or attempt==2:raise
                    time.sleep(.05)
            result={'state':values['state'],'simulation_seconds':values['current_seconds'],
                    'timer_remaining_seconds':values['remaining_seconds'],
                    'clock_initialized':values['clock_initialized'],
                    'actual_time_verified':bool(values['clock_initialized'] and values['current_seconds'] is not None and math.isfinite(values['current_seconds'])),
                    'native_state':values['native_state'],'native_clock':'VSMDEBUG-double-seconds',
                    'pid':self.session.pid,'profile':self.session.native_profile.identifier}
            if result['actual_time_verified'] and result['state'] in ('running','paused'):
                self.session.last_active_status=dict(result)
            return result

    def log(self):
        """Return final project LOGFILE text after the owned process closes.

        Capture requires explicit Session(logfile=...) opt-in before startup.
        Live project-file logs are buffered and are deliberately rejected as
        final observations. This supported path does not use the clipboard.
        """
        if getattr(self.session,'logfile',None) is None:
            raise RuntimeError('Native log capture requires Session(logfile=fresh_ASCII_path) before startup')
        if not self.session.normal_closed or self.session._final_log_text is None:
            raise RuntimeError('Final native LOGFILE requires a normal Session.close(); live file bytes may be buffered')
        return self.session._final_log_text

    def gpio_events(self,**filters):
        from fish_proteus.firmware import gpio_events
        return gpio_events(self.log(),**filters)

    def _menu(self,path):
        from fish_proteus._vendor.proteus_auto import proteus_native as native
        with self.session._lock:
            self.session.assert_identity()
            window=self.session._wait(self.session._ready)
            rows=[item for item in native.refreshed_menus(window['hwnd']) if item['path']==path and item['enabled']]
            if len(rows)!=1:raise RuntimeError(f'Missing or disabled native simulation command: {path}')
            self._message(window['hwnd'],0x111,rows[0]['command_id'])

    def run_for(self,seconds,timeout=60,tolerance_seconds=.003):
        """Return actual numeric elapsed/overshoot; never wall-time completion."""
        import ctypes as c
        seconds=float(seconds);tolerance=float(tolerance_seconds)
        if not math.isfinite(seconds) or seconds<1e-6 or abs(seconds*1e6-round(seconds*1e6))>1e-6:
            raise ValueError('Duration must be a finite integer number of microseconds')
        if not math.isfinite(tolerance) or tolerance<0:raise ValueError('Tolerance must be finite and nonnegative')
        with self.session._lock:
            before=self.status()
            if before['state']=='stopped':
                # A stopped 8.17 module has no initialized clock. Establish an
                # actual active engine and pause it before defining the target.
                self.start();self.pause();before=self.status()
            if before['state']=='running':self.pause();before=self.status()
            if before['state']!='paused' or before['simulation_seconds'] is None:
                raise RuntimeError('A paused initialized native clock is required')
            start=before['simulation_seconds']
            target=start+seconds
            self._menu('Debug/Run Simulation (timed breakpoint)')
            dialog=self.session._dialog('Execute for specified time')
            edits=[row for row in dialog['children'] if row['cls']=='Edit' and row['control_id']==257 and row.get('visible',True)]
            if len(edits)!=1:raise RuntimeError('Unrecognized native timed-breakpoint input')
            hwnd=edits[0]['hwnd'];typed=format(seconds,'.6f').rstrip('0').rstrip('.')
            self._message(hwnd,0xB1,0,-1)
            for char in typed:self._message(hwnd,0x102,ord(char))
            buffer=c.create_unicode_buffer(128);self._message(hwnd,0xD,len(buffer),c.addressof(buffer))
            if buffer.value!=typed:raise RuntimeError('Native timer input read-back mismatch')
            self._message(dialog['hwnd'],0x111,1,0)
            def reached():
                state=self.status();actual=state['simulation_seconds'];remaining=state['timer_remaining_seconds']
                if actual is None or not state.get('actual_time_verified'):
                    raise RuntimeError(f'Native simulation clock became unavailable during the timed request: {state}')
                if actual<target-1e-9:return None
                if state['state']=='paused':return dict(state,completion='native-timer-paused')
                if (state['state']=='running' and remaining>0 and actual+remaining==actual
                        and actual<=target+tolerance+1e-9):
                    self.pause();confirmed=self.status()
                    if confirmed['state']!='paused':raise RuntimeError('Native roundoff pause not acknowledged')
                    return dict(confirmed,completion='timer_roundoff_pause',roundoff_remaining_seconds=remaining)
                return None
            state=self.session._wait(reached,timeout=timeout)
            overshoot=max(0.0,state['simulation_seconds']-target)
            if overshoot>tolerance+1e-9:raise RuntimeError(f'Native timer overshot the permitted target: {state}')
            result=dict(state,requested_seconds=seconds,start_seconds=start,end_seconds=state['simulation_seconds'],
                        actual_elapsed_seconds=state['simulation_seconds']-start,overshoot_seconds=overshoot,
                        tolerance_seconds=tolerance,actual_time_verified=True)
            self.session.operations.append({'operation':'run_for',**result})
            return result

    def set_firmware(self,ref,path,clock=None):
        from fish_proteus.firmware import firmware_info
        info=firmware_info(path)
        if self.status()['state']!='stopped':raise RuntimeError('Stop before configuring firmware')
        actual_path=Path(path).resolve(strict=True)
        native_path=str(actual_path)
        if not native_path.isascii():
            try:relative=os.path.relpath(actual_path,self.session.project.parent)
            except ValueError:relative=''
            if relative and relative.isascii():native_path=relative
        if not native_path.isascii():
            import ctypes as c
            from ctypes import wintypes as w
            from . import native
            native.k.GetShortPathNameW.argtypes=(w.LPCWSTR,w.LPWSTR,w.DWORD)
            buffer=c.create_unicode_buffer(32768)
            length=native.k.GetShortPathNameW(native_path,buffer,len(buffer))
            if not 0<length<len(buffer) or not buffer.value.isascii() or not Path(buffer.value).samefile(actual_path):
                raise ValueError('This native ADI route requires an existing ASCII firmware path or verified Windows short path')
            native_path=buffer.value
        values={'PROGRAM':native_path}
        if clock is not None:values['CLOCK']=str(clock)
        actual=self.session.set_properties(ref,**values)
        loaded=actual['properties'].get('PROGRAM','')
        loaded_path=Path(loaded)
        if not loaded_path.is_absolute():loaded_path=self.session.project.parent/loaded_path
        if not loaded_path.samefile(actual_path) or _sha(loaded_path)!=_sha(actual_path):
            raise RuntimeError('Native PROGRAM read-back does not identify the selected firmware')
        result={'firmware':info,'part':actual,'loaded_program':loaded,
                'loaded_program_sha256':_sha(loaded_path)}
        self.session.operations.append({'operation':'set_firmware',**result})
        return result


def graphs(*args,**kwargs):
    from fish_proteus._vendor.proteus_auto.measurements import graphs as function
    return function(*args,**kwargs)

def export_graph(*args,**kwargs):
    from fish_proteus._vendor.proteus_auto.measurements import export_graph as function
    return function(*args,**kwargs)

def generators(*args,**kwargs):
    from fish_proteus._vendor.proteus_auto.measurements import generators as function
    return function(*args,**kwargs)

def set_generator_properties(*args,**kwargs):
    from fish_proteus._vendor.proteus_auto.measurements import set_generator_properties as function
    return function(*args,**kwargs)

def parse_graph_csv(*args,**kwargs):
    from fish_proteus._vendor.proteus_auto.measurements import parse_graph_csv as function
    return function(*args,**kwargs)

def sample(*args,**kwargs):
    from fish_proteus._vendor.proteus_auto.measurements import sample as function
    return function(*args,**kwargs)

def firmware_info(*args,**kwargs):
    from fish_proteus.firmware import firmware_info as function
    return function(*args,**kwargs)

def extract_firmware(*args,**kwargs):
    from fish_proteus.firmware import extract_firmware as function
    return function(*args,**kwargs)

def gpio_events(*args,**kwargs):
    from fish_proteus.firmware import gpio_events as function
    return function(*args,**kwargs)
