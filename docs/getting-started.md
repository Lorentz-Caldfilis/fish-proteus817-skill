# Getting started

[Docs](README.md) · [Configuration](configuration.md) · [简体中文 README](../README.zh-CN.md)

The short path is also on the [README](../README.md). This page is what each step is doing, and what to do when the circuit is one of the course examples.

## What you need

- Windows, an interactive desktop, and your own Proteus **8.17 SP2**. The build this code was written against is 8.17.37159.
- Python 3.10 or newer, and Git.
- DeepSeek Harness, already able to sign in or call its model.
- For the optional 8086 recipes: the course's original projects and `main.asm`, plus NASM.
- For the STM32 GPIO example: an Arm GNU toolchain you supply. The source is in [`examples/stm32_gpio_follow/`](../examples/stm32_gpio_follow/). No compiler and no ELF are in this repo.

File-level Python imports work without Windows. Simulation does not.

## Install and register

From PowerShell:

```powershell
git clone https://github.com/Lorentz-Caldfilis/fish-proteus817-skill.git
Set-Location fish-proteus817-skill
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dsh]"
.\.venv\Scripts\python.exe tools/dsh_install_desktop.py
```

The installer adds this skill to your existing Harness profile and remembers the Python and the repo path. Other settings are left in place. A backup is kept. `--dry-run` writes nothing. `--uninstall` removes this registration.

`tools/dsh_install_skill.py` only copies the skill into a project-local folder. It does not register the desktop tool. Use `dsh_install_desktop.py` for a normal chat.

If `PDS.EXE` or `DeepSeek Harness.exe` is not discovered, set the paths in [Configuration](configuration.md) and run the installer again.

## First chat

Open DeepSeek Harness and talk. You do not pass a job directory or an input id.

> Use the Proteus skill. Make an RC low-pass with R = 2.2k and C = 100n. Label the input and the output, check the saved wiring and the part values, and tell me where the editable project is. Say whether you only checked the file, or whether you simulated it.

The tool keeps a working copy per conversation. Ask for another task when you want a second circuit in the same chat. Ask it to export when you want a project outside that working area.

## Course materials

The 8086 recipes expect a reference tree you already have, with each case's original `.pdsprj` and `main.asm`:

```text
参考/
├── T8253_v1信号1MHz五分频/
├── T8253_v2两个CNT级联/
└── T8255_v1用K0控制LED全亮或全灭/
```

Import makes a private, hashed copy. Later jobs use fresh working copies.

```powershell
.\.venv\Scripts\python.exe tools/bootstrap_nasm.py
.\.venv\Scripts\python.exe -m fish_proteus doctor
.\.venv\Scripts\python.exe -m fish_proteus import-course --source $CourseReference --destination .local/course
```

`bootstrap_nasm.py` downloads a pinned NASM archive, checks its SHA-256, and puts it in `.tools/nasm`. It does not change the system `PATH`. Pass `--archive` if you already have that archive.

Commands for one divider job are in [CLI and Python](cli.md).

## What to read next

- [Using the skill](skill-usage.md) if you want to know what the agent was told.
- [Troubleshooting](troubleshooting.md) if the tool is missing or Proteus does not start.
- [Release notes](release/README.md) if you want the record of what was actually run.
