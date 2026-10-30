# Using the skill

[Docs](README.md) · [Skill file](../skills/fish-proteus817/SKILL.md) · [Troubleshooting](troubleshooting.md)

DeepSeek Harness loads [`skills/fish-proteus817/SKILL.md`](../skills/fish-proteus817/SKILL.md) when a request is about Proteus, a schematic, firmware on a Proteus CPU, or one of the course circuits. The skill's only desktop tool is `fish_proteus_design`.

If that tool is missing, the agent is told to say the desktop integration is not installed. It is not told to invent a schematic or a measurement. Register it with `tools/dsh_install_desktop.py`, described in [Getting started](getting-started.md).

## What the agent is for

You describe the circuit. The agent is supposed to:

1. Check `capabilities` when it is unsure the machine is ready.
2. Look up devices and pins that are actually installed.
3. Create a sheet, open a recognized project, or stage a copy for a native run.
4. Edit in one batch, then read back the saved file.
5. Simulate only when the request needs a measurement, and say which result is which.

You do not prepare task ids, job folders, or launch arguments. A new chat gets a task. `task_create` starts another circuit. `task_list` and `task_select` return to an earlier one. Hand the agent a path when you already have a project or a firmware file. It registers that file and keeps the original.

## What to ask

> Use the Proteus skill. Make an RC low-pass with R = 2.2k and C = 100n. Label the input and the output, check the saved wiring and the part values, and tell me where the editable project is. Say whether you only checked the file, or whether you simulated it.

> Build a 100 kHz output from a 1 MHz clock with one 8253. Use divisor 10. Tell me what you measured, not what the divisor implies.

> PA0 is an input. Make PA5 follow it on an STM32F103R6, load my ELF, and show the GPIO edges you actually recorded.

> Open this project, change the resistor to 4.7k, save a copy, and do not start the simulator.

Say which file is the donor or the firmware when the task needs one. Say if you want a simulation. Otherwise a careful agent should stop at the file.

## How a result is worded

| Word the tool uses | What it means |
| :-- | :-- |
| `prepared` | A task or a project input is staged |
| `file_verified` | The saved file matched the checks that were declared |
| `native_verified` | Checks accepted a native structural read |
| `runtime_observed` | A native run collected output |
| `runtime_verified` | Runtime checks accepted that fresh output |
| `blocked`, `unsupported`, `failed` | Something required was missing, not supported, or did not match |

For the course jobs, `built` means a new 8086 program was assembled, `passed` means a separate check accepted the recorded observations, and `blocked` means a tool or an observation was missing.

An opened Proteus window is none of those.

## Where the longer rules are

The agent reads these when it needs them. They are the contract, not a second copy of this page.

| | |
| :-- | :-- |
| [Desktop workflow](../skills/fish-proteus817/references/desktop-workflow.md) | Tasks, resource registration, export |
| [Tool contract](../skills/fish-proteus817/references/generic-api.md) | Actions, edits, steps, assertions |
| [Workflow and evidence](../skills/fish-proteus817/references/workflows-and-evidence.md) | Power, timing, GPIO, existing graphs |
| [Course recipes](../skills/fish-proteus817/references/cases-and-evidence.md) | Divider, cascade, and the 8255 switch |

## 中文

Agent 只应通过 `fish_proteus_design` 干活。工具没注册时，它应当说明桌面接入没装好，而不是编一份原理图或一份测量。你用自然语言描述电路；任务号和目录由工具自己管。文件检查、原生读回和仿真测量是不同结论。
