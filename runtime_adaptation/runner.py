"""Run a prepared 8086 course job in the installed Proteus desktop application."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib, json, math, os, re, shutil, tempfile, uuid, zipfile
from pathlib import Path
import xml.etree.ElementTree as ET


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _write(path,value):
    Path(path).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


def _finish(output,job_root,result):
    _write(output/'runtime.json',result)
    _write(job_root/'runtime.json',result)
    manifest_path=Path(result['manifest_path'])
    manifest=json.loads(manifest_path.read_text(encoding='utf-8-sig'))
    manifest['runtime']={'status':result['status'],'file':result['runtime_file']}
    _write(manifest_path,manifest)
    return result


def _cleanup_stage(stage):
    stage=Path(stage)
    temporary_root=Path(tempfile.gettempdir()).resolve()
    if stage.is_symlink() or stage.resolve().parent!=temporary_root or not stage.name.startswith('fish-pds-'):
        raise RuntimeError('Refusing cleanup outside the exact temporary staging directory')
    shutil.rmtree(stage)


def _stage(job):
    """Copy only this job's files into an ASCII-friendly private temporary tree."""
    root=Path(job['job_root']).resolve()
    stage=Path(tempfile.mkdtemp(prefix='fish-pds-')).resolve()
    paths={}
    for key in ('project','source','executable'):
        original=Path(job[key]).resolve(strict=True)
        if not original.is_relative_to(root):raise ValueError(f'{key} is outside the prepared job directory')
        target=stage/original.relative_to(root);target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(original,target);paths[key]=target
    # Rebase the existing source-project XML, preserving all binary design data.
    project=paths['project']
    with zipfile.ZipFile(project) as archive:
        records=[(info,archive.read(info.filename)) for info in archive.infolist()]
    with zipfile.ZipFile(project,'w') as archive:
        for info,data in records:
            if info.filename=='FIRMWARE/8086.XML':
                element=ET.fromstring(data);element.set('BUILDPATH',str(stage/'8086'))
                data=ET.tostring(element,encoding='utf-8',xml_declaration=True)
            elif info.filename=='ROOT.DSN' and job['case_id'] in ('divider','cascade'):
                # Existing 8.13 course DSN: edit only the numeric timebase in
                # the instantiated DSO property block, never device defaults.
                candidates=[]
                for match in re.finditer(rb'\{HORIZVAL=([^}\r\n]+)\}',data):
                    context=data[max(0,match.start()-300):match.start()]
                    if b'PROPERTIES\0' in context and b'{MODDLL=DSO.DLL}' in context:
                        candidates.append(match)
                if len(candidates)!=1:raise ValueError('Expected one instantiated DSO HORIZVAL property')
                match=candidates[0]
                seconds=.1 if job['case_id']=='cascade' else 1e-6
                mantissa,exponent=format(seconds,'.16e').split('e')
                value=(mantissa+'e'+('-' if int(exponent)<0 else '+')+f'{abs(int(exponent)):03d}').encode('ascii')
                if len(value)!=len(match.group(1)):raise ValueError('Refusing unknown DSO property length change')
                data=data[:match.start(1)]+value+data[match.end(1):]
            archive.writestr(info,data)
    return stage,paths


def _switch_binding_slots(netlist):
    """Choose two unused documented actuator slots from actual SDF bindings."""
    parts=netlist['parts']
    if parts.get('K0',{}).get('device')!='SWITCH':
        raise ValueError('Expected the supplied K0 SWITCH component')
    occupied=set()
    for reference,part in parts.items():
        for key in ('INC','DEC','KEY'):
            value=part['properties'].get(key)
            if value in (None,''):continue
            if not re.fullmatch(r'[0-9]',value):
                raise ValueError(f'Unrecognized actuator binding {reference}.{key}={value!r}')
            if reference!='K0' or key=='KEY':occupied.add(value)
    # Slots 1 and 2 were exercised on the actual 8.17 installation. Other free
    # digits use the same native key-slot mechanism, never process offsets.
    free=[slot for slot in '1234567890' if slot not in occupied]
    if len(free)<2:raise ValueError('Two unused actuator key slots are required')
    return free[:2]


def _prepare_switch(session,staged,output,artifact):
    session.show_schematic()
    before_path=output/'switch-before.sdf'
    before=session.export_netlist(before_path);artifact(before_path)
    inc,dec=_switch_binding_slots(before)
    session.set_properties('K0',INC=inc,DEC=dec)
    bound_path=output/'switch-bound.sdf'
    bound=session.export_netlist(bound_path);artifact(bound_path)
    netlist_path=output/'switch-native-netlist.json';_write(netlist_path,bound);artifact(netlist_path)
    if bound['parts']['K0']['properties'].get('INC')!=inc or bound['parts']['K0']['properties'].get('DEC')!=dec:
        raise RuntimeError('Native K0 actuator bindings did not read back')
    cpus=[part for part in bound['parts'].values() if part['device']=='8086']
    if len(cpus)!=1:raise RuntimeError('Expected one native 8086 firmware property')
    firmware=cpus[0]['properties'].get('PROGRAM','')
    resolved=(staged['project'].parent/firmware.replace('\\',os.sep)).resolve()
    if resolved!=staged['executable'].resolve() or _sha(resolved)!=_sha(staged['executable']):
        raise RuntimeError('Native 8086 PROGRAM does not reference this staged build')
    mapping=[]
    for bit in range(8):
        reference=f'D{bit}';led=bound['parts'].get(reference,{})
        if led.get('device')!='LED-GREEN' or led.get('properties',{}).get('DRIVE')!='1':
            raise RuntimeError(f'{reference} is not the reviewed directly driven green LED')
        pair={(reference,'A'),('U8',f'PB{bit}')}
        matches=[net for net in bound['nets'] if {(pin['ref'],pin['pin']) for pin in net['pins']}==pair]
        if len(matches)!=1:raise RuntimeError(f'Native SDF does not prove PB{bit} drives {reference}.A')
        mapping.append({'bit':bit,'led':reference,'native_net':matches[0],
                        'native_led':led,'native_port_pin':f'PB{bit}'})
    mapping_path=output/'switch-native-LED-mapping.json';_write(mapping_path,mapping);artifact(mapping_path)
    session.save()
    return {'method':'native-ADI-SDF-unused-key-slots','component':'K0',
            'inc_slot':inc,'dec_slot':dec,'inc_command':(int(inc)<<12)|3,
            'dec_command':(int(dec)<<12)|3,'native_program':firmware,
            'setup_pid':session.pid,'bindings_checked_against_all_parts':True,
            'led_mapping_file':str(mapping_path),'led_mapping_checked_from_native_sdf':True,
            'native_netlist':{'path':str(netlist_path),'sha256':_sha(netlist_path)}}


def _observe_switch(session,output,bindings,artifact):
    """Observe same-simulation input transitions and stable visible LED bytes."""
    import time
    from .controller import read_8255_ocr,read_led_ocr
    from .capture import capture_window
    from . import native
    from fish_proteus.led_observation import observe_leds,observe_pa0
    samples=[];attempts=[]
    # These are desired physical inputs, never expected output values. Output
    # bytes are collected solely from the independent image reader.
    for phase,(target,command) in enumerate(((1,None),(0,bindings['inc_command']),(1,bindings['dec_command']))):
        session.pause()
        if command is not None:
            native.message(session._ready()['hwnd'],0x111,command)
        previous=None
        for attempt in range(6):
            session.start();time.sleep(.35);session.pause();session.show_schematic()
            session.menu('View/Zoom To View Entire Sheet');time.sleep(.35)
            session.show_schematic()
            directory=output/f'switch-{phase}-attempt-{attempt}';directory.mkdir()
            image=directory/'schematic.png';capture_window(session._ready()['hwnd'],image);artifact(image)
            pin_ocr,pin_artifacts=read_8255_ocr(image,directory)
            for path in pin_artifacts:artifact(path)
            led_ocr,led_artifacts=read_led_ocr(image,directory,pin_ocr)
            for path in led_artifacts:artifact(path)
            input_reading=observe_pa0(image,pin_ocr)
            led_reading=observe_leds(image,led_ocr)
            observation={'input_bit':input_reading['input_bit'],'led_mask':led_reading['led_mask'],
                         'pid':session.pid,'phase':phase,'attempt':attempt,
                         'input_observation':input_reading,'led_observation':led_reading,
                         'simulation_seconds':None,'actual_time_verified':False}
            evidence=directory/'observation.json';_write(evidence,observation);artifact(evidence)
            attempts.append(observation)
            state=(observation['input_bit'],observation['led_mask'])
            if state==previous and state[0]==target:
                samples.append(dict(observation,stable_observations=2,command_id=command))
                break
            previous=state
        else:raise RuntimeError(f'Input phase {phase} did not yield two stable real observations')
    return {'samples':samples,'observation_attempts':attempts,'method':'same-PID-native-actuator-commands-and-independent-LED-image-observation',
            'observation_kind':'rendered-LED-display','simulation_seconds':None,'actual_time_verified':False}


def run_job(manifest_path: str | Path, seconds: float=0.05,
            proteus_executable: str | Path | None=None) -> dict:
    """Collect observations, never derive observed values from job.expected.

    The application is a Windows desktop process, so standard user desktop access
    is required. A sandbox denial is a blocked result, not a reason to alter
    Proteus, component libraries or globally configured paths.
    """
    job_file=Path(manifest_path).resolve(strict=True)
    job=json.loads(job_file.read_text(encoding='utf-8-sig'))
    duration=float(seconds)
    if not math.isfinite(duration) or not 1e-6<=duration<=60:
        raise ValueError('seconds must be finite and between 1 microsecond and 60 seconds')
    job_root=Path(job['job_root']).resolve(strict=True)
    if job_file.parent!=job_root:
        raise ValueError('Manifest parent must match the prepared job_root')
    output=job_root/'runtime'/uuid.uuid4().hex[:12];output.mkdir(parents=True)
    result={'schema':'fish-proteus.runtime.v1','status':'blocked','case_id':job['case_id'],
            'recorded_at':datetime.now(timezone.utc).isoformat(),'observed':{},'diagnostics':[],
            'raw_artifacts':[],'requested_seconds':duration,'states':[],'errors':[],
            'limitations':[],'runtime_file':str(output/'runtime.json')}
    result['manifest_path']=str(job_file)
    for key in ('source','executable','project'):
        result[key+'_sha256']=_sha(job[key])
    expected_artifact=job.get('build',{}).get('artifact',{}).get('sha256')
    if (job.get('build',{}).get('status')!='built' or expected_artifact!=result['executable_sha256']
            or job.get('build',{}).get('source_sha256')!=result['source_sha256']):
        result['diagnostics'].append('A matching, newly built 8086 artifact is required before runtime execution')
        return _finish(output,job_root,result)
    if os.name!='nt':
        result['diagnostics'].append('Proteus desktop runtime is available only on Windows')
        return _finish(output,job_root,result)
    exe=Path(proteus_executable or os.environ.get('FISH_PROTEUS_EXE') or
             r'C:\Program Files (x86)\Labcenter Electronics\Proteus 8 Professional\BIN\PDS.EXE')
    if not exe.is_file() or exe.name.upper()!='PDS.EXE':
        result['diagnostics'].append('Configured Proteus PDS.EXE does not exist')
        return _finish(output,job_root,result)
    result['proteus_executable']=str(exe.resolve());result['proteus_executable_sha256']=_sha(exe)
    session=None;stage=None
    def artifact(path):
        path=Path(path)
        result['raw_artifacts'].append({'path':str(path),'sha256':_sha(path),'bytes':path.stat().st_size})
    try:
        from .controller import Controller, read_ocr, scope_timebase
        from .capture import capture_window
        from . import native
        stage,staged=_stage(job)
        result['staged_executable_sha256']=_sha(staged['executable'])
        result['phase']='launch'
        session=Controller(staged['project'],executable=exe)
        session.evidence_directory=output/'clock'
        if job['case_id']=='switch':
            result['phase']='bind_switch'
            result['switch_bindings']=_prepare_switch(session,staged,output,artifact)
            session.close();result['switch_bindings']['setup_process_closed']=True
            session=None
            # Native save can update the design container; record its final
            # identity before launching the process that supplies all samples.
            if _sha(staged['executable'])!=result['executable_sha256']:
                raise RuntimeError('Native preparation changed the staged 8086 executable')
            result['phase']='reopen_bound_switch'
            session=Controller(staged['project'],executable=exe)
            session.evidence_directory=output/'clock'
        result['staged_project_sha256']=_sha(staged['project'])
        result['pid']=session.pid
        result['phase']='show_schematic'
        session.show_schematic();result['states'].append(session.state())
        result['phase']='start'
        session.start();result['states'].append(session.state())
        if job['case_id'] in ('divider','cascade'):
            result['phase']='open_scope'
            scope=session.open_scope()
            # These are capture settings; every value is read back from actual UI.
            result['phase']='run_timed'
            timer=session.run_timed(duration);result['states'].append(timer)
            scope=session.open_scope()
            from fish_proteus.waveform import measure_scope
            result['phase']='capture';result['acquisition_attempts']=[]
            for attempt in range(4):
                image=output/f'oscilloscope-{attempt}.png';capture_window(scope['hwnd'],image);artifact(image)
                ocr_path=output/f'oscilloscope-{attempt}-ocr.json';ocr=read_ocr(image,ocr_path);artifact(ocr_path)
                raw_timebase=scope_timebase(ocr)
                timebase=raw_timebase if re.search(r'[a-zA-Zµμ]',raw_timebase) else raw_timebase+'s'
                try:
                    measured=measure_scope(image,timebase,channel='A')
                    result['acquisition_attempts'].append({'attempt':attempt,'image':str(image),'status':'measured'})
                    break
                except ValueError as exc:
                    result['acquisition_attempts'].append({'attempt':attempt,'image':str(image),'status':'incomplete','reason':str(exc)})
                    if attempt==3:raise
                    # Auto-triggered scopes can be paused halfway through a
                    # sweep. Acquire additional native simulation time, retain
                    # every rejected image, and retry rather than invent data.
                    extra=.6 if job['case_id']=='cascade' else .00005
                    result['states'].append(session.run_timed(extra))
                    scope=session.open_scope()
            result['observed']={'output_hz':measured['frequency_hz'],'timebase_text':timebase,'method':measured['method'],
                                'timebase_raw_ui_text':raw_timebase,
                                'timebase_unit_basis':'DSO HORIZVAL is expressed in seconds; unitless SI dial values use base seconds',
                                'waveform':measured,'observation_kind':'rendered-oscilloscope-waveform'}
            try:
                incoming=measure_scope(image,timebase,channel='B')
                result['observed']['input_hz']=incoming['frequency_hz']
                result['observed']['input_waveform']=incoming
            except ValueError:
                result['limitations'].append('Input-channel frequency could not be measured from this capture')
            result['status']='runtime_observed'
        elif job['case_id']=='switch':
            result['phase']='observe_switch'
            result['observed']=_observe_switch(session,output,result['switch_bindings'],artifact)
            result['observed']['output_observation']='led-display'
            result['observed']['mapping_basis']='reviewed-teacher-template'
            result['observed']['led_wiring']=result['switch_bindings']['native_netlist']
            result['observed']['original_project_sha256']=job.get('source_provenance',{}).get('project_sha256')
            result['limitations'].append('Loaded PB pin markers can be grey; output samples read the D0..D7 LED display, not the PB register')
            result['limitations'].append('Switch samples prove stable same-simulation responses; the requested --seconds is not an exact-duration claim for this event-driven branch')
            result['status']='runtime_observed'
        else:
            raise ValueError('Unknown course case')
        session.pause();session.show_schematic()
        main_image=output/'schematic.png';capture_window(session._ready()['hwnd'],main_image);artifact(main_image)
        snapshot=output/'native-state.json'
        _write(snapshot,{'windows':native.windows(session.pid),'menus':session.command_rows()});artifact(snapshot)
        session.stop();result['states'].append(session.state())
        result['limitations'].append('Native menu state acknowledges the timed command; numeric simulator time is not read from private memory')
    except Exception as exc:
        result['status']='blocked'
        result['diagnostics'].append(f'{type(exc).__name__}: {exc}')
        result['errors'].append(f'{type(exc).__name__}: {exc}')
        if session is not None:
            try:
                from . import native
                snapshot=output/'blocked-native-state.json'
                _write(snapshot,{'windows':native.windows(session.pid),'menus':session.command_rows()});artifact(snapshot)
            except Exception as detail:result['diagnostics'].append(f'Diagnostic capture: {detail}')
    finally:
        if session is not None:
            for evidence in session.clock_evidence:
                if Path(evidence).is_file():artifact(evidence)
            try:
                session.stop();session.close();result['process_closed']=True
            except Exception as exc:
                result['status']='blocked'
                result['errors'].append(f'Close: {exc}')
                result['diagnostics'].append(f'Close: {exc}')
                if session.process.poll() is None:
                    session.process.terminate();session.process.wait(timeout=10)
                    result['process_closed']=True;result['own_process_terminated_after_close_failure']=True
        if stage is not None:
            # The directory was created by mkdtemp in this call; never a user path.
            try:_cleanup_stage(stage)
            except OSError as exc:result['diagnostics'].append(f'Temporary staging cleanup: {exc}')
        _finish(output,job_root,result)
    return result
