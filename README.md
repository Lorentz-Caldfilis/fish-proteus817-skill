# Fish for Proteus

### Your Proteus lab, from a sentence in the chat.

**An RC filter. An 8086 divider. A pin on an STM32 that follows another pin.**
DeepSeek Harness draws the schematic in Proteus 8.17 SP2, wires it, loads the program, and runs the simulation. A saved file and a measurement stay two different answers.

I built this as a course extension. The lab was still the clicking: drop a part, connect a pin, load firmware, then decide whether the simulation actually did what I asked.

[![License](https://img.shields.io/badge/license-MIT-111111)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-111111)](https://www.python.org/downloads/)
[![CI](https://github.com/Lorentz-Caldfilis/fish-proteus817-skill/actions/workflows/ci.yml/badge.svg)](https://github.com/Lorentz-Caldfilis/fish-proteus817-skill/actions/workflows/ci.yml)
[![Version](https://img.shields.io/badge/version-0.3.0--alpha-111111)](CHANGELOG.md)
![Windows](https://img.shields.io/badge/Windows-0078D4?logo=windows&logoColor=white)
![Proteus](https://img.shields.io/badge/Proteus-8.17%20SP2-111111)

**[Docs](docs/README.md)** · **[Get started](docs/getting-started.md)** · **[Skill](skills/fish-proteus817/SKILL.md)** · **English** · [简体中文](README.zh-CN.md)

## Is this for you?

Proteus keeps the circuit in its own project, on a Windows desktop, with a licensed install you already have. This repository teaches an agent how to use that install. It does not ship Proteus, device libraries, or your course files.

- **Say the circuit in chat.** The skill places parts, wires pins, and saves an editable `.pdsprj`.
- **Use the parts on this machine.** It looks up the libraries you installed. A name in a catalogue is not a promise that the part simulates.
- **Separate the file from the run.** Saving a schematic, opening the window, and measuring a pin are three results. The agent is told to keep them apart.

You want it if you have Proteus 8.17 SP2 on an interactive Windows desktop and you use DeepSeek Harness. If you are happy clicking through Proteus yourself, you do not need it.

Alpha, version 0.3.0. It is not an MCP server, and it is not a Labcenter or DeepSeek product.

## Quick start

You need Python 3.10 or newer, Git, your own Proteus **8.17 SP2**, and DeepSeek Harness on that same Windows desktop.

**1 · Install.** In PowerShell, from the folder where you want the repo:

```powershell
git clone https://github.com/Lorentz-Caldfilis/fish-proteus817-skill.git
Set-Location fish-proteus817-skill
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dsh]"
```

**2 · Register the skill once.**

```powershell
.\.venv\Scripts\python.exe tools/dsh_install_desktop.py
```

If Proteus or Harness is not in the usual place, set the path before you install. Details are in [Configuration](docs/configuration.md).

```powershell
$env:FISH_PROTEUS_EXE = 'C:\path\to\BIN\PDS.EXE'
.\.venv\Scripts\python.exe tools/dsh_install_desktop.py --dsh-executable 'C:\path\to\DeepSeek Harness.exe'
```

`--dry-run` only checks. `--uninstall` removes this skill and restores the previous one. Leave the clone where the installer found it.

**3 · Ask in a normal chat.** Open DeepSeek Harness. No launch flags, no job folder:

> Use the Proteus skill. Make an RC low-pass with R = 2.2k and C = 100n. Label the input and the output, check the saved wiring and the part values, and tell me where the editable project is. Say whether you only checked the file, or whether you simulated it.

## Try asking

These are requests, not recorded replies. A real answer depends on your libraries and on whether you asked for a simulation.

> Build a 100 kHz output from a 1 MHz clock with one 8253. Use divisor 10. Tell me what you measured, not what the divisor implies.

> PA0 is an input. Make PA5 follow it on an STM32F103R6, load my ELF, and show the GPIO edges you actually recorded.

> Open this project, change the resistor to 4.7k, save a copy, and do not start the simulator.

The 8086 and STM32 pieces need materials you supply yourself: the course originals, NASM, or an Arm GNU toolchain. See [Getting started](docs/getting-started.md).

## What it can do

| | |
| :-- | :-- |
| **Library** | Search devices installed on this machine and read their real pins |
| **Schematic** | Start a sheet, or edit a copy: parts, wires, labels, power rails |
| **Firmware** | Check an ELF or Intel HEX file and assign it to the CPU |
| **Simulation** | Own one Proteus process, run a timed interval, read CM3 GPIO or an existing graph |
| **Course recipes** | Optional 8086 divider, cascaded counters, and the 8255 LED switch |

Coordinates inside a project are Proteus integers: **100000 = 1 mm**.

Wiring is conservative and orthogonal. Interactive controls are the six kinds already supported: `BUTTON`, `SW-SPST`, `SW-SPST-MOM`, `SWITCH`, `LOGICSTATE`, and `LOGICTOGGLE`. On the STM32F103R6 setup that was tried, the first four needed an ADC plus a digital buffer before PA0 responded. Direct wiring of those four to PA0 did not.

## A picture of a real run

> **TODO for the owner.** Put a screenshot or a short GIF here: a DeepSeek Harness conversation beside the Proteus schematic it saved. Use a circuit you are allowed to publish. This slot is empty on purpose. Nothing in this section is a result.

## How it fits together

The chat loads the skill at `skills/fish-proteus817/SKILL.md`. That skill calls one desktop tool, `fish_proteus_design`. The tool talks to the Python package in this repo, which talks to your Proteus installation. Copying the skill folder by itself does not register the tool.

```text
chat → skill fish-proteus817 → fish_proteus_design → fish_proteus → Proteus 8.17 SP2
```

The map of files, and what each directory is for, is in [Architecture](docs/architecture.md).

## Configuration

| Variable | When you need it |
| :-- | :-- |
| `FISH_PROTEUS_EXE` | `PDS.EXE` is not in the usual Labcenter folder |
| `FISH_PROTEUS_LIBRARY` | Device libraries live somewhere else |
| `FISH_PROTEUS_SAMPLES` | Samples live somewhere else |
| `FISH_PROTEUS_TEMPLATE` | You want a different blank-project template |
| `DSH_DESKTOP_EXE` | The installer cannot find DeepSeek Harness |
| `DEEPSEEK_API_KEY` | Only for the optional headless API-key route |

Installed Proteus files stay read-only. The full list, including the course and test variables, is in [Configuration](docs/configuration.md).

## Limits

- Native simulation needs an interactive Windows desktop and Proteus **8.17 SP2** (build 8.17.37159 is the one this was written against). CI runs the offline tests on Linux and Windows. It does not launch Proteus.
- PCB layout, unfamiliar project formats, and creating new graphs or probes are outside what this does.
- A successful command is not a working circuit. If a measurement was not taken, the behavior is unverified.
- This Alpha build has no support promise and no fix-time promise.

What was actually tried, including the runs that failed, is kept in [Validation](docs/release/VALIDATION.md) and [Release status](docs/release/RELEASE_STATUS.md). Those notes are the evidence. This page does not repeat them.

## Documentation

| | |
| :-- | :-- |
| **[Get started](docs/getting-started.md)** | Install, first chat, and the course extras |
| **[Configuration](docs/configuration.md)** | Environment variables |
| **[Using the skill](docs/skill-usage.md)** | What the agent is supposed to do |
| **[CLI and Python](docs/cli.md)** | `fish-proteus`, the library API, the optional launchers |
| **[Architecture](docs/architecture.md)** | Where the code and the skill sit |
| **[Troubleshooting](docs/troubleshooting.md)** | Missing tool, missing Proteus, file versus simulation |
| **[Release notes](docs/release/README.md)** | Recorded checks, and what they do not prove |

## Contributing

Issues and pull requests are welcome. Describe the circuit, the Proteus build, and what you observed. Do not attach course projects, screenshots of them, credentials, or raw session logs.

Offline tests need no Proteus:

```powershell
python -m pip install -e ".[dsh,dev]"
python -B -m unittest discover -s tests -v
python -m ruff check .
```

The rest is in [Contributing](CONTRIBUTING.md). Security reports go through [Security](SECURITY.md).

## License

[MIT](LICENSE). The [Chinese text](LICENSE.zh-CN.md) is an unofficial translation.

Fish for Proteus is not affiliated with [Labcenter Electronics](https://www.labcenter.com/) or DeepSeek. Proteus, its libraries, and your course materials stay under their own terms. Upstream code kept in this repo is listed in [Third-party notices](THIRD_PARTY_NOTICES.md).
