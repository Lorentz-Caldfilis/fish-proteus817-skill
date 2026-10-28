/** DSH plugin exposing only the fixed fish_proteus workflow, without a shell. */
import { spawn } from 'node:child_process';
import { realpath, appendFile, mkdir } from 'node:fs/promises';
import { dirname, relative, isAbsolute, join, resolve } from 'node:path';

export const name = 'fish-proteus-project-tool';
export const inject = ['tools'];

const operations = new Set(['doctor', 'prepare', 'build', 'run', 'verify']);

function isChild(path, root) {
  const suffix = relative(root, path);
  return suffix !== '' && !suffix.startsWith('..') && !isAbsolute(suffix);
}

export async function apply(ctx, config) {
  const workspace = await realpath(config.workspace);
  const python = await realpath(config.python);
  const gate = await realpath(config.gate);
  const library = await realpath(config.library).catch(() => resolve(config.library));
  if (!isChild(gate, workspace) || !isChild(library, workspace)) {
    throw new Error('The fixed gate and input library must belong to this workspace.');
  }
  const allowed = config.allowedOperations;
  if (!Array.isArray(allowed) || allowed.length === 0 || allowed.some(value => !operations.has(value))) {
    throw new Error('A nonempty explicit operation allowlist is required.');
  }
  if (!isChild(config.jobDirectory, join(workspace, '.work'))) {
    throw new Error('The fixed job directory must be beneath this workspace/.work.');
  }
  if (!isChild(config.auditPath, join(workspace, '.work'))) {
    throw new Error('The audit path must be beneath this workspace/.work.');
  }
  const { defineTool } = await import(config.toolsModule);
  const tool = defineTool({
    name: 'fish_proteus',
    description: `Run the fixed local 8086 Proteus workflow. Enabled operations: ${allowed.join(', ')}. The course library and one job directory are fixed by the supervisor; no arbitrary commands or paths are accepted.`,
    parameters: {
      operation: { type: 'string', required: true, enum: allowed, description: 'One enabled workflow stage.' },
      case: { type: 'string', enum: ['divider', 'cascade', 'switch'], description: 'Required when preparing a job.' },
      divisor: { type: 'integer', description: 'Single-counter divisor, 2 to 65536; 65536 uses hardware count encoding zero.' },
      divisor0: { type: 'integer', description: 'First cascade-counter divisor, 2 to 65536.' },
      divisor1: { type: 'integer', description: 'Second cascade-counter divisor, 2 to 65536.' },
      on_value: { type: 'integer', description: 'Switch-case selected output byte, 0 to 255.' },
      off_value: { type: 'integer', description: 'Switch-case other output byte, 0 to 255.' },
      invert: { type: 'boolean', description: 'Reverse the switch condition only when requested.' },
      seconds: { type: 'number', description: 'Runtime observation duration, above zero and at most 20 seconds.' },
    },
    output: {
      schema: { type: 'json' },
      render: (_args, value) => [{ type: 'text', text: JSON.stringify(value, null, 2) }],
    },
    async execute(args, exec) {
      if (!allowed.includes(args.operation)) throw new Error('Operation not enabled for this task.');
      // The child does not inherit the harness's model credentials or arbitrary
      // Python import settings. No shell parses this argv or the JSON input.
      const environment = {};
      for (const key of ['SystemRoot', 'WINDIR', 'PATH', 'PATHEXT', 'TEMP', 'TMP', 'USERPROFILE', 'APPDATA', 'LOCALAPPDATA', 'ProgramData', 'PROGRAMFILES', 'PROGRAMFILES(X86)']) {
        if (process.env[key] !== undefined) environment[key] = process.env[key];
      }
      const argv = ['-I', '-B', gate, '--workspace', workspace, '--library', library, '--job-directory', config.jobDirectory, '--allowed', ...allowed];
      const result = await new Promise((resolve, reject) => {
        const child = spawn(python, argv, { cwd: workspace, env: environment, windowsHide: true, stdio: ['pipe', 'pipe', 'pipe'] });
        let stdout = '', stderr = '', ended = false;
        const stop = () => { if (!ended) child.kill(); };
        const timer = setTimeout(stop, 120000);
        exec.signal?.addEventListener('abort', stop, { once: true });
        child.stdout.setEncoding('utf8');
        child.stderr.setEncoding('utf8');
        child.stdout.on('data', chunk => { stdout += chunk; if (stdout.length > 1000000) stop(); });
        child.stderr.on('data', chunk => { stderr += chunk; if (stderr.length > 1000000) stop(); });
        child.on('error', error => {
          ended = true;
          clearTimeout(timer);
          exec.signal?.removeEventListener('abort', stop);
          reject(error);
        });
        child.on('close', (code, signal) => {
          ended = true;
          clearTimeout(timer);
          exec.signal?.removeEventListener('abort', stop);
          let payload;
          try { payload = JSON.parse(stdout); } catch { payload = { status: 'invalid_output', output: stdout.slice(-16000) }; }
          resolve({ exit_code: code, signal, payload, stderr: stderr.slice(-16000) });
        });
        child.stdin.on('error', () => {});
        child.stdin.end(JSON.stringify(args));
      });
      await mkdir(dirname(config.auditPath), { recursive: true });
      await appendFile(config.auditPath, JSON.stringify({ operation: args.operation, input: args, exit_code: result.exit_code, payload_status: result.payload?.status ?? null }) + '\n', 'utf8');
      return result;
    },
  });
  ctx.tools.register(tool);
  // A monotonic runtime guard enforces the model's capability allowlist even
  // if a future DSH bundle accidentally contributes an additional tool.
  ctx.tools.guard(exec => ['skill', 'fish_proteus'].includes(exec.name)
    ? undefined : 'This bounded workflow permits only skill and fish_proteus.');
}
