# Troubleshooting

[Docs](README.md) · [Getting started](getting-started.md) · [Configuration](configuration.md)

## The chat says the Proteus tool is missing

The skill file is not enough. Run `python tools/dsh_install_desktop.py` from this clone, with the same interpreter you installed the package into. If Harness was not found, pass `--dsh-executable`. Then start a new conversation.

`tools/dsh_install_skill.py` does not register the desktop tool.

## Proteus was not found

Set `FISH_PROTEUS_EXE` to the full path of `PDS.EXE`, or pass `--proteus` to `doctor` and `run`. The usual install is under `Labcenter Electronics\Proteus 8 Professional\BIN`. Discovery does not search the whole disk.

`python -m fish_proteus doctor` is the read-only check.

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

## Credentials and course files

Do not paste an API key into a chat, a commit, or an issue. Desktop use goes through Harness's own sign-in. The headless API-key route uses `DEEPSEEK_API_KEY` in the environment.

Course projects, their screenshots, and raw session logs stay private. The public tree is an allowlist, described in [Publication](../PUBLICATION.md).

## 中文

最常见的三件事：桌面工具没注册、`PDS.EXE` 不在默认路径、文件检查被说成仿真通过。第一种重新跑安装器；第二种设置 `FISH_PROTEUS_EXE`；第三种看返回状态是 `file_verified` 还是 `runtime_verified`。打不开的工程不会被悄悄换成一张空白图。
