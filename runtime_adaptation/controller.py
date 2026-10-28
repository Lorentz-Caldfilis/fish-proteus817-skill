"""Standard Windows messages for a single owned Proteus process.

No process memory offsets, DLL patching, global keyboard/mouse input or host
execution of the 16-bit program are used. Scope display settings are prepared
in the disposable project and read back independently with Windows OCR.
"""
from pathlib import Path
import ctypes as c
from ctypes import wintypes as w
import json, math, re, subprocess, time, unicodedata, uuid
from . import native
from .capture import capture_window
from .session import Session


class Controller(Session):
    def __init__(self,*args,**kwargs):
        self.dpi_context_set=native.enable_dpi_awareness()
        self.clock_evidence=[]
        self.evidence_directory=None
        super().__init__(*args,**kwargs)

    def command_rows(self):
        main=self._wait(self._ready)
        return native.refreshed_menus(main['hwnd'])

    def state(self):
        if self.process.poll() is not None:return {'state':'exited','simulation_seconds':None}
        rows={r['path']:r['enabled'] for r in self.command_rows()}
        pause=rows.get('Debug/Pause VSM Debugging')
        stop=rows.get('Debug/Stop VSM Debugging')
        state='unknown' if pause is None or stop is None else 'running' if pause else 'paused' if stop else 'stopped'
        return {'state':state,'simulation_seconds':None,'method':'refreshed-native-menu-state'}

    def until_state(self, states, timeout=30):
        return self._wait(lambda: (v if (v:=self.state())['state'] in states else None),timeout=timeout)

    @staticmethod
    def click_local(hwnd,x,y,double=False):
        point=(int(y)<<16)|(int(x)&0xffff)
        native.message(hwnd,0x201,1,point)
        native.message(hwnd,0x202,0,point)
        if double:
            native.message(hwnd,0x203,1,point)
            native.message(hwnd,0x202,0,point)

    def show_schematic(self):
        main=self._wait(self._ready)
        native.u.ShowWindow.argtypes=(w.HWND,c.c_int)
        native.u.ShowWindow(main['hwnd'],4) # SW_SHOWNOACTIVATE
        time.sleep(.2)
        main=self._wait(self._ready)
        if main['title'].endswith('Schematic Capture'):
            # Pausing can enqueue a later source-module activation. Require the
            # selected view to stay visible before sampling its schematic.
            time.sleep(.3)
            main=self._wait(self._ready)
        if main['title'].endswith('Schematic Capture'):
            return main
        # The native module strip owns the schematic as its first tab. It must
        # be selected after a pause auto-opens the source/disassembly module.
        tabs=[r for r in main['children'] if r['control_id']==2 and r['cls']=='LX_APPLN_DClkNoDC']
        if len(tabs)==1:
            for attempt in range(3):
                self.click_local(tabs[0]['hwnd'],70,12)
                time.sleep(.25)
                main=self._ready()
                if main and main['title'].endswith('Schematic Capture'):return main
            raise RuntimeError('The owned module strip did not select Schematic Capture')
        elif not main['title'].endswith('Schematic Capture'):
            raise RuntimeError('Unrecognized module strip; schematic view is unavailable')
        return self._ready()

    def start(self):
        if self.state()['state']!='running':self.menu('Debug/Run Simulation')
        return self.until_state({'running'})

    def pause(self):
        if self.state()['state']=='running':self.menu('Debug/Pause VSM Debugging')
        return self.until_state({'paused','stopped'})

    def stop(self):
        if self.state()['state'] in ('running','paused'):self.menu('Debug/Stop VSM Debugging')
        return self.until_state({'stopped'})

    def click_schematic_pixel(self,x,y):
        main=self.show_schematic()
        canvases=[row for row in main['children'] if row['cls']=='LX_APPLN_OwnDC' and row['control_id']==5 and row['visible']]
        if len(canvases)!=1:raise RuntimeError('Expected one owned visible schematic canvas')
        canvas=canvases[0];owner=w.DWORD()
        native.u.GetWindowThreadProcessId(canvas['hwnd'],c.byref(owner))
        if owner.value!=self.pid:raise RuntimeError('Schematic canvas PID mismatch')
        native.u.GetWindowRect.argtypes=(w.HWND,c.POINTER(w.RECT))
        native.u.GetClientRect.argtypes=(w.HWND,c.POINTER(w.RECT))
        native.u.ScreenToClient.argtypes=(w.HWND,c.POINTER(w.POINT))
        rect=w.RECT();bounds=w.RECT()
        native.u.GetWindowRect(main['hwnd'],c.byref(rect));native.u.GetClientRect(canvas['hwnd'],c.byref(bounds))
        point=w.POINT(rect.left+round(x),rect.top+round(y));native.u.ScreenToClient(canvas['hwnd'],c.byref(point))
        # Match the receiving application's DPI context for WM_MOUSE lParam.
        if hasattr(native.u,'GetWindowDpiAwarenessContext'):
            native.u.GetWindowDpiAwarenessContext.argtypes=(w.HWND,);native.u.GetWindowDpiAwarenessContext.restype=c.c_void_p
            native.u.PhysicalToLogicalPointForPerMonitorDPI.argtypes=(w.HWND,c.POINTER(w.POINT))
            point=w.POINT(rect.left+round(x),rect.top+round(y))
            if not native.u.PhysicalToLogicalPointForPerMonitorDPI(canvas['hwnd'],c.byref(point)):
                raise RuntimeError('Could not transform physical actuator coordinates')
            target_context=native.u.GetWindowDpiAwarenessContext(canvas['hwnd'])
            previous=native.u.SetThreadDpiAwarenessContext(target_context)
            try:
                native.u.ScreenToClient(canvas['hwnd'],c.byref(point))
                native.u.GetClientRect(canvas['hwnd'],c.byref(bounds))
            finally:native.u.SetThreadDpiAwarenessContext(previous)
        if not bounds.left<=point.x<bounds.right or not bounds.top<=point.y<bounds.bottom:
            raise RuntimeError('Rendered actuator point is outside the owned canvas')
        native.message(canvas['hwnd'],0x200,0,(point.y<<16)|(point.x&0xffff))
        self.click_local(canvas['hwnd'],point.x,point.y)
        return {'method':'PID-scoped-native-canvas-mouse-messages','pid':self.pid,
                'canvas_hwnd':canvas['hwnd'],'screenshot_pixel':[x,y],'canvas_client':[point.x,point.y]}

    def run_timed(self,seconds,timeout=120):
        seconds=float(seconds)
        if not math.isfinite(seconds) or not 1e-6<=seconds<=60:
            raise ValueError('Requested simulation duration must be between 1 microsecond and 60 seconds')
        timeout=float(timeout)
        if not math.isfinite(timeout) or timeout<=0:
            raise ValueError('Capture timeout must be finite and positive')
        # This wall-time budget only bounds waiting for a capture. It is never
        # substituted for the simulator's clock or for measured waveform data.
        wait_budget=min(timeout,max(2.0,min(8.0,seconds*2+1.0)))
        diagnostics=[];clock_readings={}
        self.pause()
        try:
            start_clock=self.clock('timer-start');clock_readings['start']=start_clock
        except Exception as exc:
            start_clock=None
            diagnostics.append({'phase':'timer-start','detail':f'{type(exc).__name__}: {exc}'})
        self.menu('Debug/Run Simulation (timed breakpoint)')
        dialog=self._dialog('Execute for specified time')
        edits=[r for r in dialog['children'] if r['cls']=='Edit' and r['control_id']==257]
        if len(edits)!=1:raise RuntimeError('Unrecognized timed-breakpoint input')
        hwnd=edits[0]['hwnd'];typed=f'{seconds:.6f}'.rstrip('0').rstrip('.')
        native.message(hwnd,0xB1,0,-1)
        for character in typed:native.message(hwnd,0x102,ord(character))
        buffer=c.create_unicode_buffer(128)
        native.message(hwnd,0xD,len(buffer),c.addressof(buffer))
        if buffer.value!=typed:
            self._click(dialog,'Cancel')
            raise RuntimeError(f'Timer input read-back mismatch: {buffer.value!r}')
        native.message(dialog['hwnd'],0x111,1,0)
        # Wait until the dialog has gone, and don't accept a stale initial menu.
        self._wait(lambda: self._ready(),timeout=10)
        time.sleep(.15)
        started=time.monotonic()
        completion='native-timer-command-acknowledged'
        while True:
            result=self.state()
            if result['state'] in ('paused','stopped'):break
            if result['state']!='running':
                raise RuntimeError(f'Unexpected native state while awaiting capture: {result["state"]}')
            if time.monotonic()-started>=wait_budget:
                result=self.pause()
                completion='bounded-capture-pause-unverified-duration'
                diagnostics.append({'phase':'capture-wait','detail':'Native timer did not pause within the bounded capture wait; requested simulation duration is unverified'})
                break
            time.sleep(.1)
        verified=False;extra={}
        try:
            end_clock=self.clock('timer-end');clock_readings['end']=end_clock
            if start_clock:
                elapsed=end_clock['simulation_seconds']-start_clock['simulation_seconds']
                verified=(completion=='native-timer-command-acknowledged' and abs(elapsed-seconds)<=1e-6)
                extra={'clock_elapsed_seconds':elapsed,'clock_tolerance_seconds':1e-6}
                if not verified:
                    diagnostics.append({'phase':'timer-end','detail':f'OCR clock duration does not verify the requested interval: {elapsed} versus {seconds}'})
            if verified:result['simulation_seconds']=end_clock['simulation_seconds']
        except Exception as exc:
            diagnostics.append({'phase':'timer-end','detail':f'{type(exc).__name__}: {exc}'})
        if not verified:result['simulation_seconds']=None
        # Optional OCR failures must not hide a lost PID, disabled/modal main
        # window, or failed native pause. These remain required observations.
        self._wait(self._ready,timeout=10)
        if result['state'] not in ('paused','stopped'):
            raise RuntimeError('Native simulation did not pause for waveform capture')
        return dict(result,requested_seconds=seconds,completion=completion,actual_time_verified=verified,
                    timing_diagnostics=diagnostics,clock_readings=clock_readings,
                    capture_wait_wall_seconds=wait_budget,**extra)

    def clock(self,label):
        from .image_evidence import crop_scaled_png
        from fish_proteus.waveform import _png_rgb
        directory=Path(self.evidence_directory or self.project.parent/'clock-evidence')
        directory.mkdir(parents=True,exist_ok=True)
        token=label+'-'+uuid.uuid4().hex[:8]
        full=directory/(token+'-window.png');capture_window(self._ready()['hwnd'],full)
        width,height,_=_png_rgb(full.read_bytes())
        crop=directory/(token+'-statusbar.png')
        crop_scaled_png(full,crop,(min(350,width//4),max(0,height-55),min(width,1100),height),scale=3)
        ocr_path=directory/(token+'-ocr.json');ocr=read_ocr(crop,ocr_path)
        self.clock_evidence.extend((full,crop,ocr_path))
        text=unicodedata.normalize('NFKC',ocr['Text']).replace('·','.')
        match=re.search(r'(PAUSED|ANIMATING)\s*:\s*([0-9][0-9\s:.]*?)\s*s\b',text,re.I)
        if not match:raise ValueError(f'Native status clock was not recognized: {text!r}')
        value=re.sub(r'\s+','',match[2])
        if '.' not in value and ':' not in value:
            raise ValueError('OCR did not resolve the native clock decimal separator')
        if ':' in value:
            fields=value.split(':')
            if len(fields)!=3:raise ValueError('Unrecognized native clock format')
            seconds=float(fields[0])*3600+float(fields[1])*60+float(fields[2])
        else:seconds=float(value)
        if not math.isfinite(seconds) or not 0<=seconds<=86400:raise ValueError('Invalid native status clock')
        return {'state':'paused' if match[1].upper()=='PAUSED' else 'running',
                'simulation_seconds':seconds,'method':'Windows-OCR-native-statusbar','raw_text':ocr['Text'],
                'ocr_file':str(ocr_path),'resolution_seconds':1e-9}

    def open_scope(self):
        def command():
            matches=[r for r in self.command_rows() if r['path'].endswith('Digital Oscilloscope') and r['enabled']]
            return matches[0] if len(matches)==1 else None
        entry=self._wait(command)
        # Device-popup numbering may change while models finish registering.
        # Invoke the ID from this freshly observed owned menu, without a second
        # text-path lookup that could race a newly inserted debug entry.
        native.message(self._ready()['hwnd'],0x111,entry['command_id'])
        def find():
            rows=[r for r in native.windows(self.pid) if r['title']=='Digital Oscilloscope']
            return rows[0] if len(rows)==1 else None
        row=self._wait(find)
        native.u.ShowWindow.argtypes=(w.HWND,c.c_int);native.u.ShowWindow(row['hwnd'],4)
        native.u.SetWindowPos.argtypes=(w.HWND,w.HWND,c.c_int,c.c_int,c.c_int,c.c_int,w.UINT)
        if not native.u.SetWindowPos(row['hwnd'],None,0,0,1380,900,0x14):raise c.WinError(c.get_last_error())
        time.sleep(.25)
        return row

    @staticmethod
    def screenshot_point(hwnd,x,y):
        # Convert a PrintWindow pixel point to that HWND's client coordinates.
        native.u.GetWindowRect.argtypes=(w.HWND,c.POINTER(w.RECT))
        native.u.ClientToScreen.argtypes=(w.HWND,c.POINTER(w.POINT))
        rect=w.RECT();origin=w.POINT(0,0)
        native.u.GetWindowRect(hwnd,c.byref(rect));native.u.ClientToScreen(hwnd,c.byref(origin))
        return int(x-(origin.x-rect.left)),int(y-(origin.y-rect.top))



def read_ocr(image_path, output_path):
    script=Path(__file__).with_name('ocr.ps1')
    command=['powershell.exe','-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',str(script),'-ImagePath',str(Path(image_path).resolve())]
    result=subprocess.run(command,capture_output=True,timeout=40)
    stdout=result.stdout.decode('utf-8-sig',errors='replace')
    stderr=result.stderr.decode('utf-8-sig',errors='replace')
    if result.returncode:raise RuntimeError(f'Windows OCR failed: {stderr[:1200]}')
    data=json.loads(stdout)
    Path(output_path).write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    return data


def scope_timebase(ocr):
    words=[word for line in ocr.get('Lines',[]) for word in line.get('Words',[])]
    selected=sorted((word for word in words if 866<=word['X']<=947 and 850<=word['Y']<=880),key=lambda w:w['X'])
    text=unicodedata.normalize('NFKC',''.join(word['Text'] for word in selected)).replace(' ','').replace(',','.')
    if not re.fullmatch(r'(?:\d+(?:\.\d*)?|\.\d+)(?:[munpµμ]?s?)?',text):
        raise RuntimeError(f'Oscilloscope timebase could not be read reliably: {text!r}')
    return text


def read_8255_ocr(image_path,output_directory):
    """Read the pin labels in a lossless crop, mapping boxes to original pixels."""
    from .image_evidence import crop_scaled_png
    import copy,hashlib
    output=Path(output_directory)
    full_path=output/'full-ocr.json';full=read_ocr(image_path,full_path)
    words=[word for line in full.get('Lines',[]) for word in line.get('Words',[])]
    anchors=[word for word in words if unicodedata.normalize('NFKC',word['Text']).upper().replace('O','0')=='PA0']
    if len(anchors)!=1:raise RuntimeError('Expected one actual PA0 label for the 8255 OCR crop')
    anchor=anchors[0];unit=anchor['Height']/11.0
    from fish_proteus.waveform import _png_rgb
    width,height,_=_png_rgb(Path(image_path).read_bytes())
    box=(max(0,int(anchor['X']-190*unit)),max(0,int(anchor['Y']-60*unit)),
         min(width,int(anchor['X']+100*unit)),min(height,int(anchor['Y']+530*unit)))
    crop=output/'pin-labels-crop.png';transform=crop_scaled_png(image_path,crop,box,scale=3)
    crop_ocr_path=output/'pin-labels-crop-ocr.json';raw=read_ocr(crop,crop_ocr_path)
    normalized=copy.deepcopy(raw)
    for line in normalized.get('Lines',[]):
        for word in line.get('Words',[]):
            word['X']=box[0]+word['X']/3;word['Y']=box[1]+word['Y']/3
            word['Width']/=3;word['Height']/=3
    normalized['SourceImage']=str(Path(image_path).resolve())
    normalized['SourceImageSHA256']=hashlib.sha256(Path(image_path).read_bytes()).hexdigest()
    normalized['Transformation']=transform
    normalized_path=output/'pin-labels-original-coordinates.json'
    normalized_path.write_text(json.dumps(normalized,ensure_ascii=False,indent=2),encoding='utf-8')
    return normalized,[full_path,crop,crop_ocr_path,normalized_path]


def read_led_ocr(image_path,output_directory,pin_ocr):
    """OCR the actual D0..D7 labels next to the upright course LED bank."""
    from .image_evidence import crop_scaled_png
    from fish_proteus.waveform import _png_rgb
    import copy,hashlib
    output=Path(output_directory)
    words=[word for line in pin_ocr.get('Lines',[]) for word in line.get('Words',[])]
    anchors=[word for word in words if unicodedata.normalize('NFKC',word['Text']).upper().replace('O','0')=='PA0']
    if len(anchors)!=1:raise RuntimeError('Expected one actual PA0 label for the LED OCR crop')
    anchor=anchors[0];unit=anchor['Height']/11.0
    width,height,_=_png_rgb(Path(image_path).read_bytes())
    box=(max(0,int(anchor['X']+110*unit)),max(0,int(anchor['Y']+80*unit)),
         min(width,int(anchor['X']+430*unit)),min(height,int(anchor['Y']+590*unit)))
    crop=output/'led-labels-crop.png';transform=crop_scaled_png(image_path,crop,box,scale=3)
    raw_path=output/'led-labels-crop-ocr.json';raw=read_ocr(crop,raw_path)
    normalized=copy.deepcopy(raw)
    for line in normalized.get('Lines',[]):
        for word in line.get('Words',[]):
            word['X']=box[0]+word['X']/3;word['Y']=box[1]+word['Y']/3
            word['Width']/=3;word['Height']/=3
    normalized['SourceImage']=str(Path(image_path).resolve())
    normalized['SourceImageSHA256']=hashlib.sha256(Path(image_path).read_bytes()).hexdigest()
    normalized['Transformation']=transform
    path=output/'led-labels-original-coordinates.json'
    path.write_text(json.dumps(normalized,ensure_ascii=False,indent=2),encoding='utf-8')
    return normalized,[crop,raw_path,path]
