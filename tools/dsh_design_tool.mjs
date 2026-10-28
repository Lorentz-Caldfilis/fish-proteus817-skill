/** Composable Proteus tool: closed domain schemas and a host-fixed task root. */
import { spawn } from 'node:child_process';
import { appendFile, mkdir, realpath, readFile, writeFile } from 'node:fs/promises';
import { createHash, randomUUID } from 'node:crypto';
import { dirname, isAbsolute, join, relative } from 'node:path';
import { StringDecoder } from 'node:string_decoder';

export const name = 'fish-proteus-design-tool';
export const inject = ['tools'];
const actions = ['capabilities', 'help', 'library_search', 'library_get', 'create', 'open', 'stage', 'inspect', 'edit', 'generators', 'generator_update', 'firmware_info', 'extract_firmware', 'graph_sample', 'run_sequence', 'verify'];
const edits = ['import_device', 'import_from_project', 'add', 'update', 'move', 'rotate', 'mirror', 'set_properties', 'assign_firmware', 'bind_controls', 'rename', 'copy_component', 'delete_component', 'connect', 'disconnect', 'set_route', 'add_wire_label', 'remove_wire_label', 'add_terminal', 'update_terminal', 'delete_terminal', 'configure_power'];
const steps = ['status', 'start', 'pause', 'stop', 'reset', 'controls', 'control_state', 'press', 'release', 'set_switch', 'run_for', 'set_firmware', 'log', 'gpio_events', 'errors', 'netlist', 'set_properties', 'save', 'graphs', 'export_graph'];
const string = description => ({ type: 'string', description });
const number = description => ({ type: 'number', description });
const integer = description => ({ type: 'integer', description });
const boolean = description => ({ type: 'boolean', description });
const json = description => ({ type: 'json', description });
const point = { type: 'array', items: { type: 'integer' }, description: '[x,y] in native integers; 100000 = 1 mm.' };

function childOf(path, root) {
  const suffix = relative(root, path);
  return suffix !== '' && !suffix.startsWith('..') && !isAbsolute(suffix);
}

/** Preserve integer literals before JSON.parse can round a 64-bit identity. */
export function parseCliJSON(text) {
  if (typeof text !== 'string') throw new TypeError('CLI JSON must be text.');
  let encoded = '', syntax = '', quoted = false, escaped = false;
  for (let index = 0; index < text.length;) {
    const character = text[index];
    if (quoted) {
      encoded += character; syntax += character; index++;
      if (escaped) escaped = false;
      else if (character === '\\') escaped = true;
      else if (character === '"') quoted = false;
      continue;
    }
    if (character === '"') {
      quoted = true; encoded += character; syntax += character; index++;
      continue;
    }
    const token = /[-0-9]/.test(character)
      ? /^-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?/.exec(text.slice(index))?.[0]
      : undefined;
    if (token) {
      const digits = token.startsWith('-') ? token.slice(1) : token;
      const unsafe = /^-?\d+$/.test(token)
        && (digits.length > 16 || (digits.length === 16 && digits > '9007199254740991'));
      encoded += unsafe ? JSON.stringify(token) : token;
      // Validate original JSON grammar with a numeric stand-in. Quoting alone
      // could accidentally turn an invalid bare numeric object key into JSON.
      syntax += unsafe ? '0' : token;
      index += token.length;
    } else {
      encoded += character; syntax += character; index++;
    }
  }
  if (syntax !== encoded) JSON.parse(syntax);
  return JSON.parse(encoded);
}

/** Retain canonical bytes locally, including when JSON/UTF-8 is invalid. */
export function decodeCliStdout(raw) {
  const bytes = Buffer.isBuffer(raw) ? raw : Buffer.from(raw, 'utf8');
  const stdout = bytes.toString('utf8');
  let payload, validUtf8 = true;
  try {
    new TextDecoder('utf-8', { fatal: true }).decode(bytes);
    payload = parseCliJSON(stdout);
  } catch (error) {
    validUtf8 = !(error instanceof TypeError);
    payload = { status: 'blocked', error: 'Invalid or interrupted design output', diagnostic_tail: stdout.slice(-8000) };
  }
  return { payload, stdout, stdout_base64: bytes.toString('base64'),
    stdout_sha256: createHash('sha256').update(bytes).digest('hex'), stdout_bytes: bytes.length,
    stdout_encoding: 'utf-8', stdout_utf8_valid: validUtf8 };
}

/** Model-only projection. Complete native reports and bytes remain local. */
export function projectModelResponse(result, context = {}) {
  const mappings = new Map();
  let omitted = 0, resource = 0;
  const add = (path, id) => {
    if (typeof path !== 'string' || path.length === 0) return;
    mappings.set(path, id);
    if (/^[A-Za-z]:[\\/]/.test(path)) {
      mappings.set(path.replaceAll('\\', '/'), id);
      mappings.set(path.replaceAll('/', '\\'), id);
    }
  };
  add(context.workspace, 'resource:workspace');
  add(context.taskRoot, 'resource:task');
  for (const [key, path] of Object.entries(context.inputs?.config ?? {})) add(path, `resource:${key}`);
  for (const kind of ['projects', 'firmware']) {
    for (const [key, path] of Object.entries(context.inputs?.[kind] ?? {})) add(path, `input:${key}`);
  }
  const payload = result?.payload ?? {};
  for (const entry of payload.evidence_refs ?? []) {
    if (entry.path && entry.artifact_id) {
      add(entry.path, `artifact:${entry.artifact_id}`);
      if (context.taskRoot) add(join(context.taskRoot, entry.path), `artifact:${entry.artifact_id}`);
    }
  }
  if (payload.current?.path) {
    const id = `artifact:project-${payload.circuit_id ?? 'current'}`;
    add(payload.current.path, id);
    if (context.taskRoot) add(join(context.taskRoot, payload.current.path), id);
  }
  const virtual = value => {
    if (!mappings.has(value)) mappings.set(value, `resource:local-${++resource}`);
    return mappings.get(value);
  };
  const escape = value => value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const sanitize = value => {
    let text = value;
    if (/^(?:[A-Za-z]:[\\/]|\\\\|\/)/.test(text)) return virtual(text);
    // Preserve only public documentation URLs, shielding them from path rules.
    const urls = [];
    text = text.replace(/https?:\/\/[^\s"'<>\)]+/g, url => {
      if (/^https:\/\/(?:github\.com\/Lorentz-Caldfilis\/fish-proteus817-skill(?:\/|$)|agentskills\.io\/)/i.test(url) && !/[?@]/.test(url)) {
        const token = `__FISH_PUBLIC_URL_${urls.length}__`; urls.push([token, url]); return token;
      }
      return virtual(url);
    });
    for (const [path, id] of [...mappings].sort((a, b) => b[0].length - a[0].length)) {
      text = text.replace(new RegExp(escape(path), /^[A-Za-z]:/.test(path) ? 'gi' : 'g'), () => id);
    }
    text = text.replace(/\b(?:Bearer\s+)[A-Za-z0-9._~+\/=\-]+/gi, '[credential omitted]');
    text = text.replace(/\b(?:api[_-]?key|password|passwd|secret|access[_-]?token|refresh[_-]?token)\s*[:=]\s*["']?[^\s,"';]+/gi, '[credential omitted]');
    text = text.replace(/\bsk-[A-Za-z0-9_-]{12,}\b/g, '[credential omitted]');
    text = text.replace(/[A-Za-z]:[\\/][^\r\n"'<>|]*/g, value => virtual(value));
    text = text.replace(/\\\\[^\r\n"'<>|]*/g, value => virtual(value));
    text = text.replace(/(?<![A-Za-z0-9:/])\/[^\s\r\n"'<>|][^\r\n"'<>|]*/gu, value => virtual(value));
    for (const [token, url] of urls) text = text.replaceAll(token, url);
    return text;
  };
  const secretKey = /password|passwd|secret|credential|authorization|api[_-]?key|access[_-]?token|refresh[_-]?token|private[_-]?key|(^|_)token$/i;
  const rawKey = /^(?:log|raw_log|raw_text|native_log|raw_native_log|log_text|stderr|stdout(?:_.*)?|diagnostic_tail|properties_raw|sections|pinouts|binary|blob|body|buffer|dsn|cdb|hex|base64|source_text|source_code|script_text|file_contents|content_bytes|raw_bytes|body_bytes|encoded_bytes|layout|tail_hex|record_offset|xy_offset|span)$/i;
  const walk = (value, key = '', path = []) => {
    if (secretKey.test(key) || rawKey.test(key) || (key === 'content' && payload.action !== 'help')) { omitted++; return undefined; }
    if (value === null || typeof value === 'boolean' || typeof value === 'number') return value;
    if (typeof value === 'string') {
      if (key === 'text' && (path.includes('simulation_log') || path.includes('log') || path.includes('final_errors'))) { omitted++; return undefined; }
      if (value.length >= 256 && /^[A-Za-z0-9+/=\r\n]+$/.test(value)) { omitted++; return '[binary encoding omitted]'; }
      return sanitize(value);
    }
    if (ArrayBuffer.isView(value) || value instanceof ArrayBuffer || (value?.type === 'Buffer' && Array.isArray(value.data))) { omitted++; return '[binary omitted]'; }
    if (Array.isArray(value)) return value.map(item => walk(item, '', path)).filter(item => item !== undefined);
    if (typeof value === 'object') {
      const output = {};
      const operation = value.op;
      for (const [childKey, child] of Object.entries(value)) {
        if (operation === 'log' && childKey === 'data' && child && typeof child === 'object') {
          const { text, ...metadata } = child;
          if (text !== undefined) omitted++;
          output.data = walk({ ...metadata, text_available_locally: text !== undefined }, childKey, [...path, 'log']);
          continue;
        }
        const projected = walk(child, childKey, [...path, key || operation || 'payload']);
        if (projected !== undefined) output[sanitize(childKey)] = projected;
      }
      return output;
    }
    omitted++;
    return undefined;
  };
  const envelope = {};
  for (const key of ['schema', 'request_id', 'task_id', 'action', 'status', 'data', 'side_effects', 'evidence_refs',
    'circuit_id', 'session_id', 'current', 'ended_utc', 'error', 'stage', 'original_status']) {
    if (Object.hasOwn(payload, key)) envelope[key] = payload[key];
  }
  const projected = walk({ exit_code: result?.exit_code ?? null, signal: result?.signal ?? null,
    termination: result?.termination ?? null, payload: envelope });
  projected.model_projection = {
    schema: 'fish-proteus.model-projection.v1', omitted_fields: omitted,
    raw_native_log: 'local artifact only', local_paths: 'virtual resource/input/artifact identifiers',
    integer_encoding: 'Pure JSON integers outside +/-9007199254740991 are original decimal strings; other numbers retain their numeric type.',
    local_report_ref: context.localReportId ? `local-report:${context.localReportId}` : null,
    local_report_sha256: context.localReportSha256 ?? null,
  };
  return projected;
}

function closedModelResponse(result, context) {
  try { return projectModelResponse(result, context); }
  catch {
    // A projection failure must never fall back to the complete native value
    // or an exception containing a host filename.
    return { exit_code: result?.exit_code ?? null, payload: { status: 'blocked',
      error: { type: 'ModelProjectionError', message: 'A minimized model response could not be produced; inspect the local evidence.' } },
      model_projection: { schema: 'fish-proteus.model-projection.v1', failed_closed: true } };
  }
}

export function parameters(allowed) {
  return {
    action: { type: 'string', enum: allowed, required: true, description: 'One enabled composable design action. Read the generic-api skill reference for its exact required fields.' },
    request_id: string('Optional unique request ID. Replaying an identical ID/payload returns the recorded result; changing its payload is rejected.'),
    topic: { type: 'string', enum: ['actions', 'edits', 'steps', 'assertions', 'workflow'], description: 'Fixed help section; use this to read the skill references without a general filesystem tool.' },
    expected_revision: string('Required by edit, generator_update, run_sequence and verify; copy the current returned revision exactly.'),
    query: string('Installed library search text.'), limit: integer('Search limit, 1..1000.'),
    name: string('Exact enumerated device or generator name.'), library: string('Enumerated library name, never a file path.'),
    input_id: string('Project input ID registered by the host.'),
    template_input: string('Registered template project ID for create; omitted uses the host configured template.'),
    title: string('ASCII project title.'), ref: string('Existing component reference for inspect filtering.'),
    sections: { type: 'array', items: { type: 'string', enum: ['components', 'pins', 'connections', 'nets', 'terminals', 'wire_labels', 'power_rails'] }, description: 'Optional inspect sections.' },
    properties: json('Native uppercase property names and printable scalar values. PROGRAM/file/script and LOGFILE/LOGFILENAME paths are host-controlled; use firmware_id.'),
    firmware_id: string('Host-registered firmware ID or a firmware artifact ID.'),
    artifact_id: string('Returned artifact ID, never a host file path.'),
    member: string('Optional exact relative ELF/HEX archive member for extract_firmware.'),
    trace: string('Exact observed CSV column name.'), x: number('CSV-axis sample position; no extrapolation.'),
    occurrence: integer('Zero-based occurrence for repeated CSV column names.'),
    save_project: boolean('run_sequence saves its owned task copy after stopping by default. Set false only when no native changes require saving.'),
    operations: {
      type: 'array', description: '1..2000 edit operations; the whole batch succeeds before a new project revision is saved.',
      items: { type: 'object', additionalProperties: false, properties: {
        op: { type: 'string', enum: edits, required: true },
        library: string('Installed library selector.'),
        donor_input: string('Registered donor project ID; only definitions are imported.'), input_id: string('Registered project ID for import_from_project.'),
        device: string('Imported device name.'), ref: string('Component reference.'), new_ref: string('New unique component reference.'), value: string('Printable ASCII component value.'),
        x: integer('Absolute native X; 100000 = 1 mm.'), y: integer('Absolute native Y; 100000 = 1 mm.'),
        rotation: integer('Degrees, supported orthogonal rotations.'), degrees: integer('Relative rotation in degrees.'),
        mirror_x: boolean('Mirror across X.'), mirror_y: boolean('Mirror across Y.'), axis: { type: 'string', enum: ['x', 'y'] },
        properties: json('Uppercase native property map; path-bearing properties are restricted.'),
        changes: json('Typed update keys documented in references/generic-api.md; unknown keys are rejected by the gate.'),
        refs: { type: 'array', items: { type: 'string' }, description: '1..5 existing binary controls to bind before save/reopen.' },
        first: string('REF.PIN logical endpoint from inspect.'), second: string('REF.PIN logical endpoint from inspect.'),
        points: { type: 'json', description: 'Explicit orthogonal route [[x,y],...] including both pin locations, or null to restore automatic routing.' },
        kind: { type: 'string', enum: ['label', 'input', 'output', 'bidir', 'power', 'ground'] },
        name: string('Native device or terminal/net name.'), pin: string('Optional REF.PIN attachment.'),
        text: string('Native wire-label text.'),
        position: point, terminal_id: string('Terminal ID returned by add_terminal/inspect.'),
        rails: json('Power rails: {name:voltage} or {name:{voltage:number,flags:"POWER"}}.'), bindings: json('Power pin/net name -> rail name.'),
        firmware_id: string('Registered or extracted firmware ID for assign_firmware.'), clock: string('Optional CPU CLOCK property value.'),
      } },
    },
    steps: {
      type: 'array', description: '1..128 native steps in one Session/PID; at most 120 requested simulation seconds. Request log/gpio_events/errors at actual active clocks; collection is deferred until normal close, GPIO replays only its clock prefix. No reset or stop/restart in a traced sequence. Host stop/save/close cleanup always runs.',
      items: { type: 'object', additionalProperties: false, properties: {
        op: { type: 'string', enum: steps, required: true }, ref: string('Enumerated component/control reference.'),
        closed: boolean('Desired binary switch position.'), seconds: number('Native run_for request, >0..60 seconds.'),
        tolerance_seconds: number('Allowed native overshoot, 0..1 seconds; default .003.'), timeout: number('Wall-clock wait budget only, 1..120 seconds.'),
        firmware_id: string('Registered/extracted firmware ID.'), clock: string('Optional CPU CLOCK property.'),
        properties: json('Native property map. Simulation must be stopped first.'), port: integer('GPIO port filter.'), pin: integer('GPIO pin filter.'),
        graph: json('Exact enumerated existing graph name or numeric index.'), simulate: boolean('export_graph defaults true and clears/recalculates stale graph data. false cannot verify a fresh simulation.'),
      } },
    },
    assertions: {
      type: 'array', description: '1..128 independent declarative checks; missing or stale evidence blocks verification.',
      items: { type: 'object', additionalProperties: false, properties: {
        type: { type: 'string', enum: ['connected', 'isolated', 'component', 'csv_range', 'gpio_sequence', 'simulation_time', 'no_errors'], required: true },
        artifact_id: string('Actual native-netlist/CSV/GPIO/run/error artifact ID. Omit only for file-level structural assertions.'),
        pins: { type: 'array', items: { type: 'string' }, description: 'REF.PIN endpoints that must share one net.' },
        first: string('First REF.PIN that must remain isolated from second.'), second: string('Second REF.PIN.'),
        ref: string('Component or GPIO event reference.'), fields: json('Expected component device/value/properties subset.'),
        trace: string('CSV trace column name.'), occurrence: integer('Repeated-column occurrence, default 0.'),
        x: number('Sample position on actual CSV axis.'), minimum: number('Independent minimum sample value.'), maximum: number('Independent maximum sample value.'),
        port: integer('GPIO port.'), pin: integer('GPIO pin.'), values: { type: 'array', items: { type: 'integer' }, description: 'Expected ordered binary state sequence, e.g. [0,1,0].' },
        step: integer('Zero-based index in the complete native_run.steps array; the selected entry must have op=run_for. This is not the ordinal among run_for entries.'), seconds: number('Independent elapsed-time target.'), tolerance_seconds: number('Independent absolute time tolerance.'),
      } },
    },
  };
}

export async function apply(ctx, config) {
  const workspace = await realpath(config.workspace);
  const python = await realpath(config.python);
  const gate = await realpath(config.gate);
  const inputsFile = await realpath(config.inputsFile);
  const hostInputs = JSON.parse(await readFile(inputsFile, 'utf8'));
  if (!childOf(gate, workspace) || !childOf(inputsFile, join(workspace, '.work')) ||
      !childOf(config.taskRoot, join(workspace, '.work')) || !childOf(config.auditPath, join(workspace, '.work'))) {
    throw new Error('The design gate, task and host input manifest must belong to the fixed workspace.');
  }
  const allowed = config.allowedActions;
  if (!Array.isArray(allowed) || allowed.length === 0 || allowed.some(value => !actions.includes(value))) {
    throw new Error('A nonempty domain-action allowlist is required.');
  }
  const { defineTool } = await import(config.toolsModule);
  ctx.tools.register(defineTool({
    name: 'fish_proteus_design',
    description: `Compose Proteus 8.17 SP2 circuits and native runs in one fixed task workspace. Enabled actions: ${allowed.join(', ')}. The host registers inputs/configuration; no code, shell, executable or arbitrary host path is accepted. Read the fish-proteus817 skill's generic-api reference.`,
    parameters: parameters(allowed),
    output: { schema: { type: 'json' }, render: (_args, value) => [{ type: 'text', text: JSON.stringify(value, null, 2) }] },
    async execute(args, exec) {
      if (!allowed.includes(args.action)) throw new Error('Design action is not enabled for this task.');
      const environment = {};
      for (const key of ['SystemRoot', 'WINDIR', 'PATH', 'PATHEXT', 'TEMP', 'TMP', 'USERPROFILE', 'APPDATA', 'LOCALAPPDATA', 'ProgramData', 'PROGRAMFILES', 'PROGRAMFILES(X86)']) {
        if (process.env[key] !== undefined) environment[key] = process.env[key];
      }
      const argv = ['-I', '-B', gate, '--workspace', workspace, '--task-root', config.taskRoot, '--inputs-file', inputsFile, '--allow', ...allowed];
      let result;
      try { result = await new Promise((resolve, reject) => {
        const child = spawn(python, argv, { cwd: workspace, env: environment, windowsHide: true, stdio: ['pipe', 'pipe', 'pipe'] });
        const stdoutChunks = [];
        const stdoutDecoder = new StringDecoder('utf8');
        let stdoutCharacters = 0, stderr = '', ended = false, termination = null;
        const stop = reason => {
          if (ended || termination) return;
          termination = reason;
          if (process.platform === 'win32' && process.env.SystemRoot) {
            // This exact child owns any Proteus descendants; never kill by image name.
            const killer = spawn(join(process.env.SystemRoot, 'System32', 'taskkill.exe'), ['/PID', String(child.pid), '/T', '/F'], { windowsHide: true, stdio: 'ignore' });
            killer.on('error', () => child.kill());
          } else child.kill();
        };
        const cancel = () => stop('aborted');
        const timer = setTimeout(() => stop('timeout'), 360000);
        exec.signal?.addEventListener('abort', cancel, { once: true });
        child.stderr.setEncoding('utf8');
        child.stdout.on('data', chunk => { stdoutChunks.push(chunk); stdoutCharacters += stdoutDecoder.write(chunk).length; if (stdoutCharacters > 2000000) stop('output_limit'); });
        child.stdout.on('end', () => { stdoutCharacters += stdoutDecoder.end().length; if (stdoutCharacters > 2000000) stop('output_limit'); });
        child.stderr.on('data', chunk => { stderr += chunk; if (stderr.length > 1000000) stop('output_limit'); });
        child.on('error', error => { ended = true; clearTimeout(timer); exec.signal?.removeEventListener('abort', cancel); reject(error); });
        child.on('close', (code, signal) => {
          ended = true; clearTimeout(timer); exec.signal?.removeEventListener('abort', cancel);
          const decoded = decodeCliStdout(Buffer.concat(stdoutChunks));
          resolve({ exit_code: code, signal, termination, ...decoded, stderr: stderr.slice(-16000) });
        });
        child.stdin.on('error', () => {});
        child.stdin.end(JSON.stringify(args));
      }); } catch (error) {
        result = { exit_code: null, signal: null, termination: 'launcher_error',
          payload: { status: 'blocked', error: { type: error.name, message: error.message } } };
      }
      // The full wrapper is retained locally before any outbound projection.
      const reportId = randomUUID();
      const reportDirectory = join(dirname(config.auditPath), 'local-tool-results');
      const full = JSON.stringify(result, null, 2) + '\n';
      try {
        await mkdir(dirname(config.auditPath), { recursive: true });
        await appendFile(config.auditPath, JSON.stringify({ action: args.action, input: args, exit_code: result.exit_code, payload_status: result.payload?.status ?? null, termination: result.termination }) + '\n', 'utf8');
        await mkdir(reportDirectory, { recursive: true });
        await writeFile(join(reportDirectory, `${reportId}.json`), full, { encoding: 'utf8', flag: 'wx' });
      } catch (error) {
        return closedModelResponse({ exit_code: result.exit_code, payload: { status: 'blocked',
          error: { type: 'LocalEvidenceWriteError', message: 'The complete local tool report could not be persisted.' },
          original_status: result.payload?.status ?? null, side_effects: result.payload?.side_effects ?? {} } },
        { workspace, taskRoot: config.taskRoot, inputs: hostInputs });
      }
      return closedModelResponse(result, { workspace, taskRoot: config.taskRoot, inputs: hostInputs,
        localReportId: reportId, localReportSha256: createHash('sha256').update(full).digest('hex') });
    },
  }));
  ctx.tools.guard(exec => ['skill', 'fish_proteus_design'].includes(exec.name) ? undefined : 'This task permits only skill and fish_proteus_design.');
}
