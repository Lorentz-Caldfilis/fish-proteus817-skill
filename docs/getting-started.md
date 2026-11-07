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

On Windows, first follow [School computers / no system-drive writes](configuration.md#school-computers-no-system-drive-writes). Use a non-system-drive repository and virtual environment, a verified ASCII temporary directory, and the actual initialized Harness home. Set TEMP/TMP, `FISH_PROTEUS_TEMP_DIR` and pip cache policy **before starting Harness**. `--dsh-home` selects an existing home; it never migrates one. Repository placement on D alone is insufficient. For ordinary machines only, the documented strict-mode opt-out is available.

学校机先读[写入配置与边界](configuration.md#学校机禁止向系统盘写数据)：在启动 Harness 前设置 TEMP/TMP、`FISH_PROTEUS_TEMP_DIR`、pip 缓存；仓库和虚拟环境放非系统盘。`--dsh-home` 不是搬家工具。外部 Proteus/Harness/Windows 的全部写入无法由本 skill 保证。

From PowerShell:

```powershell
git clone https://github.com/Lorentz-Caldfilis/fish-proteus817-skill.git
Set-Location fish-proteus817-skill
py -3 -B -m venv .venv
.\.venv\Scripts\python.exe -B -m pip install --no-cache-dir -e ".[dsh]"
.\.venv\Scripts\python.exe -B tools/dsh_install_desktop.py --dsh-home $ActualInitializedHarnessHome
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

All three directories must each contain exactly one `.pdsprj` and `main.asm`, even if only divider is requested. GitHub source alone cannot reproduce the course five-divider case. No teacher files are bundled. A partial import is not supported.

三套固定材料目录都必须各有一个 `.pdsprj` 和 `main.asm`，只跑 divider 也一样。仅有 GitHub 源码无法复现课程五分频，仓库不分发教师原件，不支持隐式的单套材料导入。

```powershell
.\.venv\Scripts\python.exe -B tools/bootstrap_nasm.py
.\.venv\Scripts\python.exe -B -m fish_proteus doctor
.\.venv\Scripts\python.exe -B -m fish_proteus import-course --source $CourseReference --destination .local/course
```

`bootstrap_nasm.py` downloads a pinned NASM archive, checks its SHA-256, and puts it in `.tools/nasm`. It does not change the system `PATH`. Pass `--archive` if you already have that archive.

Commands for one divider job are in [CLI and Python](cli.md).

## What to read next

- [Using the skill](skill-usage.md) if you want to know what the agent was told.
- [Troubleshooting](troubleshooting.md) if the tool is missing or Proteus does not start.
- [Release notes](release/README.md) if you want the record of what was actually run.
