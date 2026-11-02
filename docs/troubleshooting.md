# Troubleshooting

[Docs](README.md) · [Getting started](getting-started.md) · [Configuration](configuration.md)

## The chat says the Proteus tool is missing

The skill file is not enough. Run `python tools/dsh_install_desktop.py` from this clone, with the same interpreter you installed the package into. If Harness was not found, pass `--dsh-executable`. Then start a new conversation.

`tools/dsh_install_skill.py` does not register the desktop tool.

## Proteus was not found

Set `FISH_PROTEUS_EXE` to the full path of `PDS.EXE`, or pass `--proteus` to `doctor` and `run`. The usual install is under `Labcenter Electronics\Proteus 8 Professional\BIN`. Discovery does not search the whole disk.

`python -m fish_proteus doctor` is the read-only check. It uses the same discovery as a real run: the `--proteus` argument, then `FISH_PROTEUS_EXE`, then `PDS.EXE` on `PATH`, then Labcenter under Program Files. `native_profile.ok` is the exact 8.17 SP2 build 37159 hash check. `work` says whether the temporary directory and the desktop task store can take a file, and it names the path.

## The agent saved a file and called it done

Ask whether it simulated. `file_verified` means the saved project matched a file check. A measurement needs a native run and a result such as `runtime_observed` or `runtime_verified`. An open window is neither.

If you only wanted the schematic, say so. The agent is allowed to stop before the simulator.

## Open failed, or the sheet came back blank

An unrecognized project is not turned into a new empty design. The agent should explain the limit. `create` is how a new sheet starts. `open` is for a layout this code already understands. `stage` is for a native run on a project it will not reconstruct.

## A part will not simulate

Search and import are separate from simulation. Duplicate names exist in more than one library. The agent should read the pins from the definition it actually imported.

For the STM32F103R6 setup that was tried, `BUTTON`, `SW-SPST`, `SW-SPST-MOM`, and `SWITCH` did not drive PA0 directly. They were observed to work through a 3.3 V ADC interface and a digital buffer. `LOGICSTATE` and `LOGICTOGGLE` drove PA0 directly in that same setup. That is a simulation path, not a claim about a physical board.

## GPIO stayed flat

CM3 GPIO logging needs the processor's trace property saved before the native session opens. The tested STM32 setting is in the [workflow reference](../skills/fish-proteus817/references/workflows-and-evidence.md). Other microcontroller models are not assumed to use the same property.

Keep one stimulus and its response in a single `run_sequence`. A second call starts another session.

## Proteus starts, then the tool times out

The process is hidden. `doctor` does not open it. If the main window titled `<project> - ...` never appears, the error lists the window titles that were still open. Open Proteus by hand first and dismiss every license, update, and first-run dialog. A box you cannot see is enough to use up the 45 second launch wait.

Menus, dialogs, and buttons are the English strings from 8.17 SP2, including the netlist dialog's own spelling. A Chinese installation will not match them. This copy does not translate the UI.

## The hash check failed

`native_profile.ok` is false when `PDS.EXE` or `ISIS.DLL`, `NETLIST.DLL`, `PRIMS.DLL`, or `VSMDEBUG.DLL` is not the 8.17 SP2 build 37159 this code was written against. That refusal is intentional. A simulation that reads the native clock will not run. `doctor` is the check. Do not delete the hashes to make a different build pass.

## A slow lab PC

Leave `FISH_PROTEUS_TIMEOUT_SCALE` unset on a machine that already keeps up. On an old PC set it to `2` or `3` in the environment Harness inherits, then run `doctor` and read `timeouts.effective_seconds`. The scale stretches launch (45s), menu waits (15s), timed runs (60–120s), the short capture wait inside a course timed run (2–8s), OCR (40s), and NASM (30s). It does not change how many simulated seconds you asked for.

## C: does not accept files

School images often freeze the system drive. `FISH_PROTEUS_WORKDIR` is the folder for staging, native logs, the desktop task store, the plugin cache, and portable NASM. `doctor` reports those paths. If a write fails, the error names the directory instead of a bare access-denied. Harness has to be started with that variable set. If the installer put the task store there, starting Harness without it will refuse the tool and name the configured path.

Set `TEMP` and `TMP` as well. Python and Windows still use them for anything this variable does not wrap. Create the venv on the same drive. A course `--output` or a project you asked to save stays on the path you gave, so point that at D: too.

The Harness profile is still `~/.dsh` unless Harness itself uses another home. `--dsh-home` only helps when that is the home Harness reads.

A Chinese username can make the profile and the default temp path unusable for a native log or a firmware path. Native `LOGFILE` and `PROGRAM` values need an ASCII path. Staging looks for an ASCII ancestor, then temp. Set `FISH_PROTEUS_WORKDIR` to an ASCII folder such as `D:\fish-proteus` when that fallback has nowhere to go. A volume without 8.3 short names cannot invent an ASCII path for a Chinese one.

## OCR or the oscilloscope dial

OCR runs `powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass`. A lab policy that ignores `Bypass` blocks it. The message says so when PowerShell reports the policy.

The time-base dial is a box on the 1380×900 scope window `open_scope` requests. A capture that is a uniform scale of that window, such as 200% DPI, uses the same box scaled up. A different shape is not guessed. The status clock crop already follows the window height.

## Linux, or CI

Importing the Python package and running the unit tests does not need Proteus. Starting a simulation does. The GitHub workflow runs the offline tests and the skill-format check. It does not sign in to Harness.

## Credentials and course files

Do not paste an API key into a chat, a commit, or an issue. Desktop use goes through Harness's own sign-in. The headless API-key route uses `DEEPSEEK_API_KEY` in the environment.

Course projects, their screenshots, and raw session logs stay private. The public tree is an allowlist, described in [Publication](../PUBLICATION.md).

## 中文

最常见的几件事：桌面工具没注册、`PDS.EXE` 不在默认路径、文件检查被说成仿真通过、启动对话框把隐藏的 Proteus 挡住、C: 不能写。第一种重新跑安装器；第二种设置 `FISH_PROTEUS_EXE`；第三种看返回状态是 `file_verified` 还是 `runtime_verified`。打不开的工程不会被悄悄换成一张空白图。换机器先跑 `doctor`：`native_profile.ok` 才是 8.17 SP2 构建 37159 的哈希检查，界面必须是英文。机器慢设 `FISH_PROTEUS_TIMEOUT_SCALE`。C: 冻结时设 `FISH_PROTEUS_WORKDIR`，并把 `TEMP` 和 `TMP` 指到同一块可写的盘。中文用户名路径不能当 native 日志或固件路径，工作目录请用 ASCII，例如 `D:\fish-proteus`。
