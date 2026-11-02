# Configuration

[Docs](README.md) · [Getting started](getting-started.md)

Paths point at software you installed. None of these variables are required when discovery finds Proteus and DeepSeek Harness on their own.

Discovery order for Proteus is: the argument you passed, then the environment variable, then `PDS.EXE` on `PATH`, then `Program Files` and `Program Files (x86)` under `Labcenter Electronics\Proteus 8 Professional\BIN\PDS.EXE`. Libraries, samples, and the blank template then come from that install's `DATA` directory unless you override them.

Installed files are read-only. A save into the Proteus install, the library tree, or the samples tree is refused.

## Proteus

| Variable | Meaning |
| :-- | :-- |
| `FISH_PROTEUS_EXE` | Full path to `PDS.EXE` |
| `FISH_PROTEUS_LIBRARY` | Device library root |
| `FISH_PROTEUS_SAMPLES` | Samples root |
| `FISH_PROTEUS_TEMPLATE` | Project used as an empty format container. The usual default is the installed `Rescap.pdsprj` under Graph Based Simulation |
| `FISH_PROTEUS_NASM` | `nasm.exe` for the 8086 recipes, if it is not on `PATH` and you did not run `tools/bootstrap_nasm.py` |
| `FISH_PROTEUS_TIMEOUT_SCALE` | Multiplier for launch, menu, timed-run, OCR, and NASM waits. Unset or `1` keeps the built-in deadlines (45s, 15s, 60–120s, 40s, 30s). It does not change simulated seconds. At most 30 |
| `FISH_PROTEUS_WORKDIR` | Folder for skill-owned writes: staging, native logs, the desktop task store, the plugin cache, and portable NASM. Unset keeps the system temp directory and `<repo>/.work/desktop` |

`fish-proteus doctor` and `fish-proteus run` also take `--proteus`. `build` takes `--nasm`. Those flags set the same variables for that process.

For desktop setup, the installer saves the four verified Proteus resource paths in its managed profile entry. They take precedence over the desktop process environment. To change them, set the relevant `FISH_PROTEUS_*` overrides in the installer shell and rerun setup; reinstall without overrides retains the saved paths. This also works when the model installs from an already-running Harness session.

## Slow PCs and a frozen C:

Set `FISH_PROTEUS_TIMEOUT_SCALE` and `FISH_PROTEUS_WORKDIR` in the environment that starts DeepSeek Harness, not only in a shell you have already closed. If the installer wrote the task store under the workdir, Harness still needs that variable or the tool will not load. `doctor` prints `timeouts.effective_seconds`. A clone that sits on a frozen drive should be imported with `python -B` or `PYTHONDONTWRITEBYTECODE=1`, so Python does not try to write `.pyc` files beside the source. The desktop tool already passes `-B`.

`FISH_PROTEUS_WORKDIR` does not move a path you typed: a saved project, a course `--output`, or an export stays there, so choose D: yourself. It also does not move the Harness profile. That profile defaults to `~/.dsh`. Pass `--dsh-home` only when Harness is already using that home.

Python, pip, and many Windows APIs still use `TEMP` and `TMP`. Point those at the same writable drive. Create the virtualenv there too. A Chinese username often makes the profile path unusable for a native log or a firmware `PROGRAM` path. Use an ASCII workdir, such as `D:\fish-proteus`. The log staging falls back to an ASCII ancestor or to temp when the workdir is unset; if none of those can be written, the error names each path it tried.

## DeepSeek Harness

| Variable | Meaning |
| :-- | :-- |
| `DSH_DESKTOP_EXE` | Full path to `DeepSeek Harness.exe` when the installer or the headless probe cannot find it |
| `DEEPSEEK_API_KEY` | API key for the optional headless route `--provider deepseek-official` only |

The desktop installer can take `--dsh-executable` once instead of `DSH_DESKTOP_EXE`.

A normal desktop chat uses Harness's own sign-in. It does not read `DEEPSEEK_API_KEY`. The headless account route uses `--credential-store` and Harness's own credential file. Point that flag at a store you already have. Do not commit it.

`DSH_HOME` in the headless launcher is a directory the launcher creates for that run. You do not set it.

## Tests

These are for the offline suite and local acceptance. Leaving them unset is the normal case.

| Variable | Meaning |
| :-- | :-- |
| `FISH_GENERIC_TEST_LOCAL` | Set to `1` to run tests that need a licensed local Proteus install |
| `FISH_SCOPE_TEST_PNG` | Optional scope-capture PNG for a waveform test |
| `FISH_SCOPE_TEST_TIMEBASE` | Timebase text for that PNG. Default used by the test is `1u` |
| `FISH_SCOPE_TEST_CHANNEL` | Scope channel for that PNG. Default used by the test is `A` |

## 中文

日常只用在发现失败时设 `FISH_PROTEUS_EXE` 和 `DSH_DESKTOP_EXE`。机器慢设 `FISH_PROTEUS_TIMEOUT_SCALE`。C: 不能写时设 `FISH_PROTEUS_WORKDIR`，并把 `TEMP` 和 `TMP` 指到同一块盘。`DEEPSEEK_API_KEY` 只给可选的 headless API-key 路线。安装目录里的 Proteus 文件保持只读。
