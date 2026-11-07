# Configuration

[Docs](README.md) · [Getting started](getting-started.md)

These settings describe the optional `codex/school-non-system-paths` branch for users who cannot write to the system drive. For ordinary use, choose [main](https://github.com/Lorentz-Caldfilis/fish-proteus817-skill/tree/main) and its configuration documentation. Main prioritizes the skill's core circuit workflow; the school-specific restrictions here are not requirements for main.

本文针对可选的 `codex/school-non-system-paths` 分支。普通使用选择 main 并阅读 main 的配置文档；main 优先实现 skill 的核心用途，不承担这里禁止写系统盘的特殊要求。

Resource paths point at software you installed. Discovery can find those read-only resources; writable paths have a separate policy below.

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

`fish-proteus doctor` and `fish-proteus run` also take `--proteus`. `build` takes `--nasm`. Those flags set the same variables for that process.

For desktop setup, the installer saves the four verified Proteus resource paths in its managed profile entry. They take precedence over the desktop process environment. To change them, set the relevant `FISH_PROTEUS_*` overrides in the installer shell and rerun setup; reinstall without overrides retains the saved paths. This also works when the model installs from an already-running Harness session.

## DeepSeek Harness

| Variable | Meaning |
| :-- | :-- |
| `DSH_DESKTOP_EXE` | Full path to `DeepSeek Harness.exe` when the installer or the headless probe cannot find it |
| `DEEPSEEK_API_KEY` | API key for the optional headless route `--provider deepseek-official` only |

The desktop installer can take `--dsh-executable` once instead of `DSH_DESKTOP_EXE`.

A normal desktop chat uses Harness's own sign-in. It does not read `DEEPSEEK_API_KEY`. The headless account route uses `--credential-store` and Harness's own credential file. Point that flag at a store you already have. Do not commit it.

Desktop setup requires `--dsh-home`, or `DSH_HOME` if that argument is absent. It must be the actual Harness home with an existing `profiles/desktop/package.json`. It is not a migration/copy command. There is no `Path.home()/.dsh` fallback. The headless launcher separately overrides `DSH_HOME` with its isolated `output/home`; that does not relocate an ordinary desktop profile.

## School computers: no system-drive writes

This branch defaults to `FISH_PROTEUS_STRICT_NON_SYSTEM_DRIVE=1` on Windows. Before creating a writable root or probing it, the tool resolves existing links/junctions and compares its drive with `%SystemDrive%` (default `C:`). UNC/device paths are not writable roots. Allowed roots are created if needed and tested with a private file **inside that root**, then the probe is removed. Invalid or unwritable roots cause `blocked`/a nonzero exit; the tool never falls back to system TEMP or the user home. Read-only Proteus resources on C remain allowed.

| Variable | Meaning and priority |
| :-- | :-- |
| `FISH_PROTEUS_TEMP_DIR` | Absolute writable ASCII non-system directory for course staging, LOGFILE staging, probes and child TEMP/TMP. Environment > validated installed `tempRoot` > the caller's owned repository/task `.work/fish-proteus-temp`. A bad explicit choice blocks instead of falling back. |
| `FISH_PROTEUS_STRICT_NON_SYSTEM_DRIVE` | `1` by default. `0` is an explicit ordinary-machine/hosted-CI opt-out and **does not provide school-machine protection**. No drive restriction on POSIX; ASCII/temp/probe rules still apply. |
| `FISH_PROTEUS_TIMEOUT_SCALE` | Finite multiplier 1..20, default 1. Applies to native UI waits, OCR, capture waits, JS bridge limits and headless total timeout. |
| `DSH_HOME` | Actual initialized desktop home, used only when installer `--dsh-home` is absent. Must pass writable-path checks. |

CLI destinations still win for their own outputs and must pass the same writable-path checks. Desktop tasks and plugin caches stay in `repository/.work/desktop`; NASM stays in `.tools/nasm`. There is no second work-root setting. Repository names may contain Chinese characters; configure a separate ASCII temporary root in that case. Putting the repository on D alone does not redirect every writable path. The installer saves only a temp root that passed an actual probe; dry-run checks location without creating or probing and cannot establish writability. Reinstallation revalidates saved paths. Explicit Proteus resource overrides still follow their existing precedence and can be on C.

Set the following **before starting Harness**, using already verified writable ASCII non-system directories and actual installed executable paths:

```powershell
$env:FISH_PROTEUS_STRICT_NON_SYSTEM_DRIVE = '1'
$env:TEMP = $VerifiedWritableAsciiTemp
$env:TMP = $VerifiedWritableAsciiTemp
$env:FISH_PROTEUS_TEMP_DIR = $VerifiedWritableAsciiTemp
$env:PIP_CACHE_DIR = $VerifiedWritablePipCache
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:FISH_PROTEUS_EXE = $ActualPdsExe
$env:DSH_DESKTOP_EXE = $ActualHarnessExe
# Set DSH_HOME only if this is already the home Harness really uses.
$env:DSH_HOME = $ActualInitializedHarnessHome
# Start the actual Harness from this environment after setup.
```

An already-running Harness does not inherit changes made in the installer's shell. The bridge enforces validated TEMP/TMP for its Python children, and Python explicitly passes them to PDS, OCR and compiler children; this does not change the host Harness process. JS keeps `-I -B` and filters out model credentials and arbitrary environment values, while forwarding the documented Proteus/NASM/path/timeout settings. PDS starts in the disposable project's directory, not its installation BIN. This cwd change still needs native acceptance on the target installation.

For installation, use `python -B -m pip install --no-cache-dir -e ".[dsh]"` in the same configured session, with a non-system-drive virtual environment. `--no-cache-dir` disables pip's cache, **not temporary files**; TEMP/TMP are still necessary. `PIP_CACHE_DIR` is a pip setting, not an automatic skill feature. Use `python -B` for manual Python commands; a Python startup may create bytecode before application validation otherwise.

Responsibility has three layers:

1. Repository-controlled output: installers, CLI, bridges, runner and design tool validate their file/directory, log, screenshot, staging, plugin-cache and task-state destinations.
2. Child processes: the tool sets validated TEMP/TMP and disables Python bytecode where launch controls permit. This controls those settings, not every behavior of the child.
3. External programs: Proteus, Harness and Windows can still write user preferences, AppData/Documents, licensing data, crash reports, registry values or autosaves. **This skill alone cannot guarantee that those programs never touch C.** No school-machine I/O tracing was performed by the offline suite. This remains version 0.3.0, Alpha, with bounded support.

Timeout baselines: short capture waits now allow at least 15 wall-clock seconds (bounded by the caller's timeout), OCR 40 seconds, ordinary UI waits 15 seconds, bridge calls 600 seconds, and headless total 900 seconds. Multiply all by the same scale; explicit `--timeout` is the headless base before scaling. A sequence with many UI/OCR actions can still exhaust its outer budget; raise the headless total as needed. A timeout is a blocked/unverified observation, never proof of a faulty circuit or measured simulation time.

## 学校机：禁止向系统盘写数据

Windows 默认严格模式 `FISH_PROTEUS_STRICT_NON_SYSTEM_DRIVE=1`，按 `%SystemDrive%` 比较盘符；写入前解析链接/联接并拒绝系统盘。临时根 `FISH_PROTEUS_TEMP_DIR` 必须是绝对、ASCII、可写的非系统盘目录。优先级是环境变量、安装时持久化且重新验证的 `tempRoot`、调用方仓库/任务的 `.work/fish-proteus-temp`；显式设置错误不会换一个目录继续，缺少合法根就 blocked，绝不回退系统 TEMP 或用户主目录。输出参数仍优先用于自己的目标，且须通过同样校验；C 盘的只读 Proteus 安装资源仍可读取。中文仓库名不受限，但须另配 ASCII 临时目录。

在启动 Harness **之前**设置上面的 TEMP/TMP、新变量和必要的 pip 缓存目录；已经运行的 Harness 不会继承另一个 shell 的变化。安装器 `--dsh-home` 优先于 `DSH_HOME`，只能选择 Harness 真正使用且已有 desktop profile/package.json 的 home，不会搬家。headless 的 `output/home` 是另一种隔离运行方式。dry-run 不创建目录、不做写探测，因此不能证明目录可写；正式安装才验证并保存。手工命令使用 `python -B`，安装时 `--no-cache-dir` 不能代替 TEMP/TMP 设置。仓库放 D 盘不等于所有路径已解决。

`FISH_PROTEUS_TIMEOUT_SCALE=1..20` 同时放大 UI/OCR、捕获、桌面桥及 headless 等待预算；短捕获默认至少 15 秒，桥默认 600 秒，headless 默认 900 秒（`--timeout` 是倍率之前的总预算）。多步序列仍可能耗尽总预算，不能据此判定电路错误。`STRICT_NON_SYSTEM_DRIVE=0` 只供普通机器/单系统盘 CI 显式退出限制，不能用于学校机保证。

本仓库负责自己的输出路径校验；尽量控制子进程 TEMP/TMP 与 Python 字节码；**无法单独保证 Proteus、Harness、Windows 的 AppData、Documents、授权、崩溃报告、注册表和自动保存都不写 C**。仍是 0.3.0 Alpha，不承诺任意学校机零写入或免调试；离线测试不等于目标学校机实测。

## Tests

These are for the offline suite and local acceptance. Leaving them unset is the normal case.

| Variable | Meaning |
| :-- | :-- |
| `FISH_GENERIC_TEST_LOCAL` | Set to `1` to run tests that need a licensed local Proteus install |
| `FISH_SCOPE_TEST_PNG` | Optional scope-capture PNG for a waveform test |
| `FISH_SCOPE_TEST_TIMEBASE` | Timebase text for that PNG. Default used by the test is `1u` |
| `FISH_SCOPE_TEST_CHANNEL` | Scope channel for that PNG. Default used by the test is `A` |

## 中文

发现失败时设 `FISH_PROTEUS_EXE` 和 `DSH_DESKTOP_EXE`；写入策略按上方学校机章节配置。`DEEPSEEK_API_KEY` 只给可选的 headless API-key 路线。安装目录里的 Proteus 文件保持只读。
