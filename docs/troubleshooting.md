# Troubleshooting

[Docs](README.md) · [Getting started](getting-started.md) · [Configuration](configuration.md)

## The chat says the Proteus tool is missing

The skill file is not enough. Run `python -B tools/dsh_install_desktop.py` from this clone, with the same interpreter you installed the package into. If Harness was not found, pass `--dsh-executable`. Then start a new conversation.

`tools/dsh_install_skill.py` does not register the desktop tool.

## Proteus was not found

Set `FISH_PROTEUS_EXE` to the full path of `PDS.EXE`, or pass `--proteus` to `doctor` and `run`. The usual install is under `Labcenter Electronics\Proteus 8 Professional\BIN`. Discovery does not search the whole disk.

`python -B -m fish_proteus doctor` is the read-only check.

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

## Linux, or CI

Importing the Python package and running the unit tests does not need Proteus. Starting a simulation does. The GitHub workflow runs the offline tests and the skill-format check. It does not sign in to Harness.

## Writable path blocked

Read [school-machine configuration](configuration.md#school-computers-no-system-drive-writes). Set TEMP/TMP and `FISH_PROTEUS_TEMP_DIR` before starting Harness. Select the actual initialized non-system-drive home with `--dsh-home`; it is not a migration tool. A D-drive checkout does not fix C-drive TEMP or home. A dry-run cannot probe writability without writing, so `ready` is a location/prerequisite preview; actual installation probes before saving configuration. Read-only PDS paths can remain on C. Third-party Windows/Proteus/Harness writes are outside the skill's complete control.

## Runtime compatibility and measurement limits

- `FISH_PROTEUS_TIMEOUT_SCALE=1..20` increases waits together. Timeouts leave results blocked/unverified, not evidence of circuit failure. Headless `--timeout` defaults to 900 seconds before scaling; bridge calls have 600 seconds before scaling. Long multi-action sequences may need a larger outer budget.
- Scope OCR uses one reviewed pixel layout: fully visible 1380×900 at 96 DPI inside a monitor's usable work area. The preflight refuses other sizes, clipping and DPI. Per-monitor DPI awareness is not arbitrary-resolution support. Target-machine acceptance is still needed for window-manager behavior and PDS's project-directory working directory.
- The course convention is **channel A = output (yellow), channel B = input (cyan)**. Divider/cascade verification now requires the measured input near 1 MHz, measured output within 1% of the expected frequency, and a measured division ratio within 2%. Missing B blocks verification even when A matches; `runtime_observed` alone is not `passed`.
- Course import always checks all three named directories, each with exactly one `.pdsprj` and `main.asm`. Source-only users cannot reproduce the course five-divider baseline without their own teacher materials. Nothing is bundled or silently omitted.
- Menus/dialogs are matched in English, including the native spelling `Complile Netlist`, `Schematic Capture` and `Digital Oscilloscope`. Chinese Windows does not imply compatibility with Chinese Proteus UI. Windows OCR tries en-US then the user's language and fails if no usable language exists. Working PowerShell and Windows OCR language packs are prerequisites. Do not change school AppLocker/group policy to bypass restrictions; blocked execution remains blocked.
- Generic native reads require the exact SHA-256 fingerprints of PDS and the reviewed DLLs in `runtime_adaptation/profile817.py`. Not every distribution labelled 8.17 SP2 matches. Keep rejection, layout guards and resource protection enabled.
- Valid counter values are 2..65536, but the course scope timebase is fixed at 1 µs/div for divider and 0.1 s/div for cascade. Legal inputs do not guarantee two same-direction edges are observable. Five-divider is the existing baseline, not proof for every parameter.

### 中文：运行边界

学校机先配非系统盘的 TEMP/TMP、`FISH_PROTEUS_TEMP_DIR` 和真实 `--dsh-home`，且必须在启动 Harness 前设置；仓库放 D 盘不足以解决全部路径。无法保证外部程序全部不写 C。慢机调 `FISH_PROTEUS_TIMEOUT_SCALE`，不能把等待超时解释为电路错误。示波器固定像素 OCR 仅支持完整可见的 1380×900、96 DPI；其他布局 blocked，不承诺任意缩放/分辨率。

课程 **A=黄色输出，B=青色输入**；分频验证必须有接近 1 MHz 的输入、在目标 1% 误差内的输出和 2% 误差内的实测比值。输入缺失即 blocked，不再仅凭输出 passed。导入仍需三套固定中文目录各一个工程和 `main.asm`，仅源码不能复现五分频。计数 2..65536 合法不等于固定 1µs/0.1s 时基下总能看到两个同向边沿。

匹配英文菜单/对话框（含 `Complile Netlist` 原生拼写），中文 Windows 不代表中文 Proteus UI 兼容。OCR 先 en-US 再用户语言，需要可用语言包及可运行的 PowerShell；不通过修改 AppLocker/组策略绕过学校限制。通用原生读数要求 PDS/DLL 的精确 SHA-256，不是所有标着 8.17 SP2 的安装包都支持。保留哈希、布局和资源校验；仍需目标机验证，离线测试不能证明真实 Windows I/O 行为。

## Credentials and course files

Do not paste an API key into a chat, a commit, or an issue. Desktop use goes through Harness's own sign-in. The headless API-key route uses `DEEPSEEK_API_KEY` in the environment.

Course projects, their screenshots, and raw session logs stay private. The public tree is an allowlist, described in [Publication](../PUBLICATION.md).

## 中文

最常见的三件事：桌面工具没注册、`PDS.EXE` 不在默认路径、文件检查被说成仿真通过。第一种重新跑安装器；第二种设置 `FISH_PROTEUS_EXE`；第三种看返回状态是 `file_verified` 还是 `runtime_verified`。打不开的工程不会被悄悄换成一张空白图。
