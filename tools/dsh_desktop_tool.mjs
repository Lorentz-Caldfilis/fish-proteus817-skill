/** Persistent desktop adapter. Session/task plumbing is owned by the host. */
import { spawn } from 'node:child_process';
import { appendFile, mkdir, realpath, writeFile } from 'node:fs/promises';
import { createHash, randomUUID } from 'node:crypto';
import { dirname, isAbsolute, join, relative } from 'node:path';
import { parameters, decodeCliStdout, projectModelResponse } from './dsh_design_tool.mjs';

export const name = 'fish-proteus-desktop-tool';
export const inject = ['tools', 'workingDirectory'];
export const desktopActions = [
  'task_create', 'task_list', 'task_current', 'task_select', 'resources',
  'resource_find', 'resource_register', 'project_export',
  'capabilities', 'help', 'library_search', 'library_get', 'create', 'open', 'stage',
  'inspect', 'edit', 'generators', 'generator_update', 'firmware_info',
  'extract_firmware', 'graph_sample', 'run_sequence', 'verify',
];

const text = description => ({ type: 'string', description });
const inside = (path, root) => {
  const suffix = relative(root, path);
  return suffix !== '' && !suffix.startsWith('..') && !isAbsolute(suffix);
};

export function desktopParameters() {
  const schema = parameters(desktopActions);
  schema.action.description = 'Proteus design or desktop task/resource action. Task directories and input manifests are automatic. Read help topic desktop for task/resource operations.';
  schema.expected_revision.description = 'Optional optimistic revision. Omitted uses the current managed project; an explicitly stale revision is still rejected.';
  schema.topic.enum = [...schema.topic.enum, 'desktop'];
  return { ...schema,
    label: text('Optional human-readable label for task_create.'),
    task_id: text('An actual task ID from task_list, for task_select; belongs to this DSH session.'),
    kind: { type: 'string', enum: ['project', 'firmware'], description: 'Input resource kind for resource_find/resource_register.' },
    path: text('User-selected local project or ELF/HEX path, absolute or relative to this DSH session working directory. For resource_register; never a command.'),
    candidate_id: text('Actual candidate ID from resource_find. Use instead of path to register a discovered file.'),
    scope: { type: 'string', enum: ['workspace', 'samples'], description: 'Bounded resource_find scope: current session directory or installed Proteus samples.' },
    destination: text('User-selected NEW directory for project_export. Existing destinations are never overwritten.'),
  };
}

function blocked(type, message) {
  return { exit_code: 2, payload: { schema: 'fish-proteus.desktop.v1', status: 'blocked',
    error: { type, message } } };
}

function childEnvironment() {
  const environment = {};
  for (const key of ['PATH', 'Path', 'SYSTEMROOT', 'SystemRoot', 'WINDIR', 'COMSPEC',
    'PATHEXT', 'TEMP', 'TMP', 'PROGRAMFILES', 'ProgramFiles', 'ProgramFiles(x86)',
    'PROGRAMDATA', 'ProgramData', 'USERPROFILE', 'LOCALAPPDATA', 'APPDATA',
    'FISH_PROTEUS_EXE', 'FISH_PROTEUS_LIBRARY', 'FISH_PROTEUS_SAMPLES', 'FISH_PROTEUS_TEMPLATE']) {
    if (process.env[key] !== undefined) environment[key] = process.env[key];
  }
  environment.PYTHONIOENCODING = 'utf-8';
  return environment;
}

/** One owned process tree per call; no shell, no global tool restrictions. */
export function runDesktopGate(config, args, { sessionId, workingDirectory, signal }) {
  return new Promise((resolve, reject) => {
    const child = spawn(config.python, ['-I', '-B', config.gate,
      '--workspace', config.workspace, '--store-root', config.stateRoot,
      '--session-id', sessionId, '--working-directory', workingDirectory],
    { cwd: config.workspace, env: childEnvironment(), shell: false, windowsHide: true,
      stdio: ['pipe', 'pipe', 'pipe'] });
    let ended = false, termination = null, byteCount = 0, stderr = '';
    const chunks = [];
    const stop = reason => {
      if (ended || termination) return;
      termination = reason;
      if (process.platform === 'win32' && child.pid) {
        const killer = spawn('taskkill', ['/PID', String(child.pid), '/T', '/F'],
          { windowsHide: true, stdio: 'ignore', shell: false });
        killer.on('error', () => child.kill());
      } else child.kill('SIGTERM');
    };
    const cancel = () => stop('aborted');
    const timer = setTimeout(() => stop('timeout'), 360000);
    signal?.addEventListener('abort', cancel, { once: true });
    if (signal?.aborted) cancel();
    child.stdout.on('data', chunk => {
      byteCount += chunk.length;
      if (byteCount <= 4_000_000) chunks.push(chunk);
      else stop('output_limit');
    });
    child.stderr.setEncoding('utf8');
    child.stderr.on('data', chunk => {
      stderr = (stderr + chunk).slice(-16000);
    });
    const cleanup = () => {
      ended = true;
      clearTimeout(timer);
      signal?.removeEventListener('abort', cancel);
    };
    child.on('error', error => { cleanup(); reject(error); });
    child.on('close', (code, childSignal) => {
      cleanup();
      const decoded = decodeCliStdout(Buffer.concat(chunks));
      // A killed process cannot establish successful work even with an old JSON tail.
      if (termination) decoded.payload = { status: 'blocked', error: {
        type: 'InterruptedDesktopCall', message: `The owned backend call ended: ${termination}. Inspect its local report before retrying.` } };
      resolve({ exit_code: code, signal: childSignal, termination, ...decoded, stderr });
    });
    child.stdin.on('error', () => {});
    child.stdin.end(JSON.stringify(args));
  });
}

export function desktopProjection(result, context) {
  const desktop = result.payload?.desktop ?? {};
  const taskRoot = typeof desktop.task_root === 'string' && inside(desktop.task_root, context.stateRoot)
    ? desktop.task_root : undefined;
  const projected = projectModelResponse(result, { ...context, taskRoot });
  projected.desktop = {
    session_scoped: true,
    task_id: desktop.task_id ?? null,
    automatic_revision: true,
  };
  // Generated output locations are needed for normal desktop delivery. Raw
  // input paths, credentials, binary bodies and native logs remain minimized.
  const projectPath = desktop.project_path;
  if (taskRoot && typeof projectPath === 'string' && inside(projectPath, taskRoot)) {
    projected.delivery = { project_path: projectPath };
  }
  if (desktop.export_path && result.payload?.action === 'project_export'
      && result.payload?.status === 'file_verified') {
    projected.delivery = { ...projected.delivery, export_path: desktop.export_path };
  }
  return projected;
}

export async function apply(ctx, config) {
  const workspace = await realpath(config.workspace);
  const python = await realpath(config.python);
  const gate = await realpath(config.gate);
  const stateRoot = config.stateRoot;
  if (!isAbsolute(stateRoot) || !inside(stateRoot, join(workspace, '.work'))
      || !inside(gate, join(workspace, 'tools'))) {
    throw new Error('Desktop plugin paths must belong to its installed companion repository.');
  }
  await mkdir(stateRoot, { recursive: true });
  const checkedStateRoot = await realpath(stateRoot);
  if (!inside(checkedStateRoot, join(workspace, '.work'))) {
    throw new Error('Desktop task storage cannot escape through a link.');
  }
  const fixed = { workspace, python, gate, stateRoot: checkedStateRoot };
  const { defineTool } = await import(config.toolsModule);
  ctx.tools.register(defineTool({
    name: 'fish_proteus_design',
    description: 'Design and simulate circuits with the installed Proteus. Tasks are automatically isolated by this DSH session; no launch parameters are needed. Discover installed libraries/samples, register user-selected projects or firmware during work, create/edit/inspect, run native sequences, verify actual results and export an editable project. Course examples are optional. Use help topic desktop for task/resource operations and other help topics for exact design fields.',
    parameters: desktopParameters(),
    output: { schema: { type: 'json' }, render: (_args, value) => [{ type: 'text', text: JSON.stringify(value, null, 2) }] },
    async execute(args, exec) {
      const session = exec.agent?.session;
      if (!session || typeof session.id !== 'string' || !session.id) {
        return blocked('MissingDesktopSession', 'A real DSH agent session is required; no shared fallback task was created.');
      }
      const workingDirectory = ctx.workingDirectory.get(session);
      if (typeof workingDirectory !== 'string' || !isAbsolute(workingDirectory)) {
        return blocked('MissingWorkingDirectory', 'The current DSH session has no absolute working directory.');
      }
      let result;
      try {
        result = await runDesktopGate(fixed, args, { sessionId: session.id, workingDirectory, signal: exec.signal });
      } catch (error) {
        result = blocked(error.name, error.message);
      }
      const sessionKey = createHash('sha256').update(session.id).digest('hex');
      const reportDirectory = join(checkedStateRoot, 'observations', sessionKey);
      const reportId = randomUUID();
      const full = JSON.stringify(result, null, 2) + '\n';
      try {
        await mkdir(reportDirectory, { recursive: true });
        await writeFile(join(reportDirectory, `${reportId}.json`), full, { encoding: 'utf8', flag: 'wx' });
        await appendFile(join(reportDirectory, 'audit.jsonl'), JSON.stringify({
          report_id: reportId, action: args.action, payload_status: result.payload?.status ?? null,
          exit_code: result.exit_code, termination: result.termination ?? null,
          implementation_module: import.meta.url,
          source_identity: config.sourceIdentity ?? null,
          ended_utc: new Date().toISOString(),
        }) + '\n', 'utf8');
      } catch {
        return blocked('LocalEvidenceWriteError', 'The complete local tool result could not be preserved; no success is claimed.');
      }
      try {
        return desktopProjection(result, { workspace, stateRoot: checkedStateRoot,
          localReportId: reportId, localReportSha256: createHash('sha256').update(full).digest('hex') });
      } catch {
        return blocked('ModelProjectionError', 'The minimized desktop result is unavailable; inspect its local evidence.');
      }
    },
  }));
}
