/** Host path preflight, before mkdir/probes or starting Python. */
import { realpathSync, existsSync, mkdirSync, openSync, writeSync, closeSync, unlinkSync } from 'node:fs';
import { dirname, resolve, join, win32, isAbsolute } from 'node:path';
import { randomUUID } from 'node:crypto';

export function checkWritablePath(value, { ascii = false, platform = process.platform, env = process.env } = {}) {
  if (typeof value !== 'string' || !value || value.includes('\0')) throw new Error('Writable path is required');
  const strict = env.FISH_PROTEUS_STRICT_NON_SYSTEM_DRIVE ?? '1';
  if (!['0', '1'].includes(strict)) throw new Error('FISH_PROTEUS_STRICT_NON_SYSTEM_DRIVE must be 0 or 1');
  const check = path => {
    if (ascii && !/^[\x20-\x7e]+$/.test(path)) throw new Error('Temporary paths must be ASCII');
    if (platform === 'win32' && strict === '1') {
      const drive = win32.parse(path).root.slice(0, 2).toLowerCase();
      const system = (env.SystemDrive || env.SYSTEMDRIVE || 'C:').replace(/[\\/]+$/, '').toLowerCase();
      if (!/^[a-z]:$/.test(system)) throw new Error('Invalid SystemDrive; cannot establish a non-system destination');
      if (!/^[a-z]:$/.test(drive) || drive === system) throw new Error('Writable paths require a local non-system drive');
    }
  };
  let path = resolve(value);
  check(path);
  // Resolve the closest existing ancestor so junctions cannot redirect a probe.
  const suffix = [];
  let parent = path;
  while (!existsSync(parent)) {
    const next = dirname(parent);
    if (next === parent) throw new Error('No existing writable ancestor');
    suffix.unshift(parent.slice(next.length + (next.endsWith('/') || next.endsWith('\\') ? 0 : 1)));
    parent = next;
  }
  path = join(realpathSync(parent), ...suffix);
  check(path);
  return path;
}

export function writableDirectory(value, options = {}) {
  let root = checkWritablePath(value, options);
  mkdirSync(root, { recursive: true });
  root = checkWritablePath(root, options);
  const probe = join(root, `.fish-write-probe-${randomUUID()}`);
  const fd = openSync(probe, 'wx');
  try { writeSync(fd, 'fish'); } finally { closeSync(fd); unlinkSync(probe); }
  return root;
}

export function timeoutScale() {
  const scale = Number(process.env.FISH_PROTEUS_TIMEOUT_SCALE ?? '1');
  if (!Number.isFinite(scale) || scale < 1 || scale > 20) throw new Error('FISH_PROTEUS_TIMEOUT_SCALE must be between 1 and 20');
  return scale;
}

export function childEnvironment(workspace, configuredTemp) {
  const env = {};
  const names = ['PATH', 'Path', 'SYSTEMROOT', 'SystemRoot', 'SystemDrive', 'SYSTEMDRIVE', 'WINDIR', 'COMSPEC',
    'PATHEXT', 'PROGRAMFILES', 'ProgramFiles', 'ProgramFiles(x86)', 'PROGRAMFILES(X86)',
    'PROGRAMDATA', 'ProgramData', 'USERPROFILE', 'LOCALAPPDATA', 'APPDATA',
    'FISH_PROTEUS_EXE', 'FISH_PROTEUS_LIBRARY', 'FISH_PROTEUS_SAMPLES', 'FISH_PROTEUS_TEMPLATE',
    'FISH_PROTEUS_NASM', 'FISH_PROTEUS_STRICT_NON_SYSTEM_DRIVE', 'FISH_PROTEUS_TIMEOUT_SCALE'];
  for (const key of names) if (process.env[key] !== undefined) env[key] = process.env[key];
  const selected = process.env.FISH_PROTEUS_TEMP_DIR || configuredTemp || join(workspace, '.work', 'fish-proteus-temp');
  if (!isAbsolute(selected)) throw new Error('FISH_PROTEUS_TEMP_DIR must be absolute');
  const temp = writableDirectory(selected, { ascii: true });
  timeoutScale();
  return { ...env, TEMP: temp, TMP: temp, FISH_PROTEUS_TEMP_DIR: temp,
    PYTHONDONTWRITEBYTECODE: '1', PYTHONIOENCODING: 'utf-8' };
}
