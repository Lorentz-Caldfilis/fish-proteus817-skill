# Fish for Proteus 8.17 SP2

[English](README.md) | [简体中文](README.zh-CN.md)

An Agent Skill and Python toolkit for composing supported Proteus schematics,
editing existing circuits, assigning firmware, running owned native sessions,
and checking actual simulation results. **DeepSeek Harness (DSH)** uses a typed
design tool; the three 8086 course workflows remain optional recipes.

**Version 0.3.0 · Alpha · MIT · Target: Proteus 8.17 SP2 (8.17.37159)**

This is an experimental open-source Skill for the supported scope below.
Version 0.3.0 adds one-time DSH desktop integration, automatic session tasks and
on-demand local project/firmware registration. Split-edit import fixes and the
specialized headless launcher remain available. See
[release status](docs/RELEASE_STATUS.md) for version-specific evidence and the
completed 0.2.0 baseline; supported formats and simulation scope remain bounded.

## Scope

| Area | Composable operations | Boundary |
| --- | --- | --- |
| `Library` | Search installed devices; inspect actual pins, defaults, models and definition identity. | Lookup, successful import and simulation support are separate facts. |
| `Circuit` | Import selected definitions; create a blank topology or open a recognized layout; add/edit/copy/move/rotate/mirror/delete parts; connect/disconnect pins, branches and buses. | Supported single-user-sheet CDB v7 layouts and conservative orthogonal routing. |
| Nets and power | Six terminal kinds, real wire labels, same-name logical nets and power-rail bindings. | Unknown objects or unsafe reconstruction are rejected. |
| `Session` / `Simulation` | Own one process; read native SDF/properties; save; start/pause/stop/reset and request native timed intervals. | Interactive Windows and an exact supported native build/profile. |
| Firmware and inputs | Check ELF/Intel HEX identity; assign and read back PROGRAM; bind BUTTON, SW-SPST, SW-SPST-MOM, SWITCH, LOGICSTATE and LOGICTOGGLE. | Two actuator slots per binary input, ten slots total; binding changes require save/reopen. |
| Measurements | CM3 GPIO events with timestamps; existing graph CSV, duplicate trace occurrences and in-range interpolation. | GPIO events are digital states; existing analyses must be recalculated for fresh graph evidence. |
| DSH desktop | Persistent tool registration, automatic session tasks, local resource discovery/registration, editable project export, native sequences and assertions. | One-time companion installation; actual device/model support remains task-specific. |

Recorded local evidence includes 13 native structural candidates and six actual
CM3 GPIO 0→1→0 sequences. The final 0.2.0 wheel passed representative native checks
in an isolated installation, completing its G12 package acceptance. Every rebuilt
distribution requires its own artifact hashes and installed check. A real DSH design/runtime
task also completed in two phases sharing one managed project: file construction
and a separately authorized native continuation. This establishes the documented
reference-aligned supported scope on the tested local installation. Follow
[Validation](docs/VALIDATION.md) and the G01–G14
[roadmap](docs/design/ROADMAP.md) for the current evidence and completion gates.
Arbitrary PCB layout, arbitrary Proteus formats and new graph/probe creation
are outside this implementation.

In the tested STM32F103R6 setup, LOGICSTATE and LOGICTOGGLE drive PA0 directly.
BUTTON, SW-SPST, SW-SPST-MOM and SWITCH achieved downstream GPIO transitions
through an explicit 3.3 V ADC interface plus digital BUFFER. Their direct
passive-to-PA0 candidates did not produce the required response. This is a
verified simulation input-conditioning path, with no physical-interface claim.

Request → inspect real definitions/pins → compose or edit → save/reopen → native
SDF → firmware/simulation → actual measurements → independent assertions.

The skill lives at [`skills/fish-proteus817/SKILL.md`](skills/fish-proteus817/SKILL.md).
Use the **complete repository**: the skill depends on the Python backend, Windows
runtime adapter and tools. Copying the skill directory alone does not supply
these components or install Proteus.

## Requirements

- Python **3.10 or newer** and Git; file-level code imports without a Windows desktop.
- For native work: Windows, PowerShell, an **interactive desktop**, and your own
  Proteus **8.17 SP2** installation with the required models, library and template/donor resources.
- For DSH: an installed DeepSeek Harness, configured authentication and network
  access to its selected model provider.
- For the optional 8086 recipes: the separately obtained course originals and NASM.
  The original STM32 GPIO example uses a separately supplied Arm GNU toolchain.

No Proteus installation, device definitions, official samples, teacher projects,
compiler or compiled firmware is bundled.

## Set up the repository

Run these commands in Windows PowerShell:

```powershell
git clone https://github.com/Lorentz-Caldfilis/fish-proteus817-skill.git
Set-Location fish-proteus817-skill
py -3 -m venv .venv
$FishPython = (Resolve-Path .\.venv\Scripts\python.exe).Path
& $FishPython -m pip install -e ".[dsh]"
```

A virtual environment is optional. To use an existing Python 3.10+ interpreter,
set `$FishPython = (Get-Command python.exe).Source` and use that interpreter for
installation and subsequent commands. The `dsh` extra installs PyYAML for
credential-store handling and log redaction.

Install the desktop integration once:

```powershell
& $FishPython tools/dsh_install_desktop.py
```

The installer adds the global Skill and one local-plugin entry to your existing
DSH desktop profile, preserving backups and other settings. It stores the actual
Python and repository paths. If desktop discovery needs help, supply
`--dsh-executable 'C:\path\to\DeepSeek Harness.exe'` once. Keep the companion
repository at that location. `--dry-run` checks readiness without writing;
`--uninstall` removes this registration and restores a previous global Skill.

Then use an ordinary DSH desktop conversation, for example:

> Use the Proteus skill to create an RC low-pass schematic with R=2.2k and
> C=100n. Add input/output labels, check the saved wiring and component values,
> and give me the editable project location. Distinguish file checks from simulation.

No per-task launch arguments, donor manifest or job directory is needed. The
adapter discovers installed resources and manages separate tasks per conversation.
Provide a local project or firmware path in your request when the task needs it.
For multiple designs in one conversation, ask to create another task or resume
an earlier one. See [desktop workflow](skills/fish-proteus817/references/desktop-workflow.md)
for the tool contract and [release status](docs/RELEASE_STATUS.md) for actual
desktop loading and acceptance results.

`tools/dsh_install_skill.py` remains a project-only Skill installer for specialized
deployments; by itself it does not register the desktop execution tool.

## Compose a circuit with Python

```python
from fish_proteus.automation import Circuit, Library, ProteusConfig

config = ProteusConfig.discover()
library = Library(config=config)
print(library.search("RESISTOR", limit=10))
print(library.get("RESISTOR", library="ASIMMDLS"))

circuit = Circuit(config=config)
circuit.add("RESISTOR", "R1", "10k", 0, 0)
circuit.add("CAPACITOR", "C1", "100n", 5_080_000, 0)
print(circuit.pins("R1"))
circuit.connect("R1.2", "C1.1")
circuit.add_wire_label("R1.2", "C1.1", "FILTER_OUT")
circuit.add_terminal("input", "VIN", "R1.1")
circuit.add_terminal("ground", "", "C1.2")
circuit.save(".work/new-filter.pdsprj")
```

This creates an editable file; it does not establish simulated filter behavior.
Use an unused destination. Coordinates are native integers: **100000 = 1 mm**.
`Circuit()` uses an installed format container with a blank topology;
`Circuit.open(path, config=config)` preserves a recognized existing layout.
Import additional devices with an explicit library selector or a local donor,
then use enumerated logical pin names or unambiguous physical numbers.

`ProteusConfig.discover()` accepts explicit resource paths and the process
environment variables `FISH_PROTEUS_EXE`, `FISH_PROTEUS_LIBRARY`,
`FISH_PROTEUS_SAMPLES`, `FISH_PROTEUS_TEMPLATE`. Installed resources stay read-only.
Saves validate source identity and refuse stale edits or implicit overwrites.
The [Python API](docs/GENERIC_API.md) documents firmware, owned `Session` and
`Simulation` calls, six input types, CM3 logs and existing graph CSV operations.

## Optional: specialized headless acceptance

The following launch arguments are for isolated reproducible experiments,
not ordinary desktop setup. In this specialized deployment, mutations carry
`expected_revision`, inputs are host-registered, and `run_sequence` must be
explicitly enabled. The desktop adapter manages these internals automatically.
The read-only `help` action supplies the exact actions, edits, steps, assertions
and workflow contract through the tool when filesystem access is disabled.

An explicit `stage` action prepares an opaque working copy for supported native
or generator operations. It does not turn an unrecognized project into an
editable reconstructed topology; a failed `open` is not a blank-design fallback.

For a desktop DSH installation, set `DSH_DESKTOP_EXE` to its installed executable.
A `dsh` CLI already on `PATH` can be used without that setting:

```powershell
$env:DSH_DESKTOP_EXE = Read-Host 'Full path to DeepSeek Harness.exe (desktop only)'
& $FishPython tools/dsh_headless.py --probe
```

The supplied natural-language task asks the model to compose an STM32 input
follower from actual definitions, then verify its SDF and PA0→PA5 response.
Provide a lawful local STM32F103R6 donor and the original example's compiled ELF:

```powershell
$DonorProject = Read-Host 'Full path to your STM32F103R6 donor project'
$FollowFirmware = Read-Host 'Full path to the compiled gpio-follow.elf'
& $FishPython tools/dsh_headless.py `
  --workflow design `
  --provider deepseek-account `
  --credential-store "$env:USERPROFILE\.dsh\.credentials.yaml" `
  --input-project "donor=$DonorProject" `
  --input-firmware "follow=$FollowFirmware" `
  --output .work/dsh-design-session `
  --job-directory .work/dsh-design-job `
  --allowed-operations capabilities help library_search library_get create open inspect edit firmware_info run_sequence verify `
  --task-file tools/demo_task_generic.txt `
  --timeout 600
```

To build that original firmware with your own Arm GNU installation, use
`tools/build_stm32_demo.py --toolchain <toolchain-root> --output <new-directory>`.
Its source is in [`examples/stm32_gpio_follow/`](examples/stm32_gpio_follow/).
The helper defaults to DWARF-2 for the tested Proteus loader; a valid ELF
container alone does not establish debug-format compatibility.
The task description supplies behavior, not a complete prebuilt circuit.
The real file phase completed 17 typed requests and four file assertions. After
specific user authorization for the provider payload, a separate runtime phase
completed 19 requests and verified native SDF, firmware identity, actual time
and GPIO 0→1→0. Both phases used the same managed project, not one DSH session.
The final seven mixed assertions passed with aggregate `native_verified`;
the runtime assertions and a separate time-only verification established their
runtime basis. Details and retained failures are in [Validation](docs/VALIDATION.md).

Keep each session and task directory fresh. The host controls the task root,
input IDs, configuration and operation allowlist. The model cannot submit shell
commands, arbitrary executable paths or arbitrary code through the design tool.
Read the [tool contract](skills/fish-proteus817/references/generic-api.md) and
[workflow rules](skills/fish-proteus817/references/workflows-and-evidence.md).

Point `--credential-store` to your own existing store. The account provider uses
DSH's normal sign-in lifecycle and may refresh it. For API-key authentication,
select `--provider deepseek-official` and configure `DEEPSEEK_API_KEY` in the
process environment. These are separate provider routes. Keep credentials and
raw sessions private. For an undiscovered launcher use `--dsh-executable`;
an unrecognized layout may also need `--tools-module`. The launcher uses a
project-local DSH home and temporary profile configuration.

## Optional 8086 course recipes

The legacy `fish_proteus` CLI/tool supports these supplied course templates and
their parameter variants. They are not required for the generic file API:

| Case | Circuit | Example request |
| --- | --- | --- |
| `divider` | One 8253 counter with a 1 MHz input | Produce a 100 kHz output using divisor 10. |
| `cascade` | Two cascaded 8253 counters | Produce a 1 Hz or 2 Hz output. |
| `switch` | 8255, K0/PA0 input, and eight LEDs | Select 33h for PA0=0 and CCh for PA0=1. |

The expected course reference directory contains:

```text
参考/
├── T8253_v1信号1MHz五分频/
├── T8253_v2两个CNT级联/
└── T8255_v1用K0控制LED全亮或全灭/
```

Each directory must contain its original `.pdsprj` project and `main.asm`.
Importing creates a private, hash-checked copy; subsequent jobs use separate
working copies. Keep the original reference directory available for provenance checks.

Prepare the project-local NASM toolchain and inspect the environment:

```powershell
& $FishPython tools/bootstrap_nasm.py
& $FishPython -m fish_proteus doctor
```

The bootstrap downloads a pinned official NASM archive, verifies its SHA-256, and
installs it under `.tools/nasm`. It does not change the system `PATH`.
An existing matching archive can be supplied with `--archive`.

Import your course files by entering the reference directory's actual path:

```powershell
$CourseReference = Read-Host 'Path to the course reference directory'
& $FishPython -m fish_proteus import-course `
  --source $CourseReference `
  --destination .local/course
```

### Run a manual 100 kHz example

From the repository root, create a new job and run each stage:

```powershell
& $FishPython -m fish_proteus prepare --library .local/course --case divider --divisor 10 --output .work/manual-100khz
& $FishPython -m fish_proteus build --manifest .work/manual-100khz/job.json
& $FishPython -m fish_proteus run --manifest .work/manual-100khz/job.json --seconds 0.05
& $FishPython -m fish_proteus verify --manifest .work/manual-100khz/job.json
```

Use a fresh job directory for each variant. Read each command's JSON and exit code
before continuing. A successful build and an opened simulator are separate stages
from a `passed` verification result.

The generated 16-bit MZ executable is firmware for Proteus; `run` loads it into the
simulated 8086. For a nondefault installation, `doctor` and `run` accept
`--proteus 'C:\path\to\BIN\PDS.EXE'`. Other preparation options include
`--divisor0`/`--divisor1` for `cascade` and `--on-value 0x33 --off-value 0xCC`
for `switch`. Use `& $FishPython -m fish_proteus prepare --help` for all options.

### Use the course DSH workflow

The course launcher exposes a `fish_proteus` tool with five possible operations:
`doctor`, `prepare`, `build`, `run`, and `verify`. The supervisor fixes the course
library, one job directory, and an operation allowlist. Tool arguments contain
case parameters; they do not accept shell commands or arbitrary paths.

The legacy launcher default is `--workflow course`. For an existing DSH account
sign-in, explicitly enable all five operations:

```powershell
& $FishPython tools/dsh_headless.py `
  --provider deepseek-account `
  --credential-store "$env:USERPROFILE\.dsh\.credentials.yaml" `
  --library .local/course `
  --output .work/dsh-100khz-session `
  --job-directory .work/dsh-100khz-job `
  --allowed-operations doctor prepare build run verify `
  --task-file tools/demo_task_100khz.txt `
  --timeout 300
```

The example task asks DSH to calculate the divisor, load the skill, build a fresh
8086 program, run it in Proteus, and report the measured output and verification.
Choose fresh session and job directories for subsequent tasks. The launcher uses
the same Python interpreter selected above for its backend calls.

## Results and observations

Generic tasks retain current revision and hashed evidence references. File,
native and runtime assertions produce different evidence levels:

| Generic result | Meaning |
| --- | --- |
| `prepared` | A task/project input has been staged. |
| `file_verified` | File-level checks accepted the declared structure. |
| `native_verified` | Assertions accepted actual native structural evidence. |
| `runtime_observed` | A native sequence collected actual output. |
| `runtime_verified` | Runtime assertions accepted fresh matching evidence. |
| `blocked` / `unsupported` / `failed` | A required condition is unavailable, unsupported or did not match. |

Requested time, initialized native start/end time, elapsed time, tolerance and
overshoot remain separate. Input position is not downstream output. CM3 log
events are digital observations with native timestamps, not analog voltage or
the current simulation clock. Generic raw-log evidence is finalized after the
owned session closes normally and is matched to the actual step clock.
CSV measurements use existing graph objects;
`simulate=true` clears/recalculates analysis, duplicate trace names use
`occurrence`, and sampling rejects extrapolation.

Each course job keeps its source, build record, `job.json`, runtime reports, screenshots,
OCR output, and hashes. Individual runs live under `runtime/<run-id>/`; the
job-level `runtime.json` points to the latest report. `verify` writes
`verification.json` and recomputes expectations separately from observations.

| Course result | Meaning |
| --- | --- |
| `built` | A fresh 8086 artifact was assembled and checked. |
| `runtime_observed` | The runtime adapter collected actual simulation output. |
| `passed` | Independent verification accepted the recorded observations. |
| `blocked` | A required tool, observation, or condition was unavailable. |
| `failed` | A verification check did not match its required result. |

Counter frequencies come from actual oscilloscope traces, their visible grid,
and the displayed timebase. The switch workflow observes PA0 and the D0–D7 **LED
display**, with its wiring checked from the native netlist; this is **not a direct
PB register read**. It tests input transition and recovery within one simulation.

The course `--seconds` requests a native simulation interval. Optional clock OCR does not
establish an exact elapsed time when it is unreadable or inconsistent: reports
then retain `actual_time_verified: false` and `simulation_seconds: null`.
Behavior verification still requires sufficient real waveform or LED observations.

## Testing and validation

Offline tests require neither Proteus nor private course files:

```powershell
& $FishPython -B -m unittest discover -s tests -v
```

For serial desktop acceptance with your imported templates:

```powershell
& $FishPython tools/acceptance.py --library .local/course --output .work/acceptance --runtime --repeat 3
```

For generic file-level acceptance with your local installation:

```powershell
& $FishPython tools/generic_structure_acceptance.py --output .work/structure-check
```

Its queue can then be checked separately on the interactive desktop:

```powershell
& $FishPython tools/generic_native_acceptance.py --queue .work/structure-check/acceptance.json --output .work/native-structure-check
```

The second command launches Proteus. A `file_verified` result alone is not native
or simulation acceptance. [Validation](docs/VALIDATION.md) records the actual
scope and untested extensions. The [release status](docs/RELEASE_STATUS.md)
separates the completed 0.2.0 package acceptance from each new distribution.
The 16-check local structural suite passed during development; the final 0.2.0
wheel subsequently passed its separate isolated-installation native check.
The final native structural batch matched 13 candidates, including independent
terminal types, property-length boundaries and native-save/file-reopen checks;
the ADI-to-file-to-native property continuation also passed. The two tall catalogue symbols now keep their titles clear of COM/PD0; a
new native save/reopen and screenshot check passed, as did the reversed-wire follow-up. All six GPIO sequences passed their functional/source/ownership checks
on the input paths described above, with raw diagnostics retained. The source
suite recorded 166 tests (13 skipped), plus 11 enabled local checks; the earlier clean
candidate copy recorded 161 tests with 16 explicit skips. Official Skill validation
and 12 vendor-provenance entries passed. Both the earlier candidate and final
0.2.0 wheel were checked in isolated installations. The final wheel verified
native structure, SW1 GPIO 010 with five controls bound, spare-control idempotence,
reset returning stopped and fresh repeated-name CSV. Restart and five simultaneous
GPIO outputs were not tested. Rebuilt distributions must retain their own
installed verification and hashes. The real DSH continuation's time/GPIO
evidence and cleanup were independently checked; a launcher final or model
narrative alone is not the acceptance criterion.

The final DSH adapter was rechecked in a fresh nine-request continuation:
all seven checks passed on the first attempt and its native clock reached
0.3025 s. Large integer identities are exact decimal strings across the
JavaScript boundary; original stdout bytes and hashes stay local.

The historical 0.1.0 baseline recorded **70 local offline tests, eight course
simulation scenarios and a real course DSH workflow**. Version 0.1.1 improved
public distribution. These records do not establish 0.2.0 generic acceptance or
compatibility across machines/builds. CI runs offline tests on Windows and
Linux; it does not launch Proteus or authenticate to DSH.

## Documentation and license

| Document | Purpose |
| --- | --- |
| [Release status](docs/RELEASE_STATUS.md) | Completed 0.2.0 baseline, 0.2.1 change scope and artifact-specific evidence. |
| [Python API](docs/GENERIC_API.md) | Configuration, circuits, native sessions, firmware and measurements. |
| [Typed tool API](skills/fish-proteus817/references/generic-api.md) | Domain actions, revisions, native steps and assertions. |
| [Architecture](docs/design/ARCHITECTURE.md) / [standard](docs/design/DESIGN_STANDARD.md) / [roadmap](docs/design/ROADMAP.md) | Design sources, rules and G01–G14 acceptance gates. |
| [Skill format](docs/SKILL_FORMAT.md) | Skill structure, discovery, and backend requirements. |
| [Development](docs/DEVELOPMENT.md) | Source boundaries, evidence rules and maintenance workflow. |
| [Validation](docs/VALIDATION.md) | Recorded local validation and its limits. |
| [Contributing](CONTRIBUTING.md) | Development and contribution workflow. |
| [Security](SECURITY.md) | Reporting security issues and handling private data. |
| [Third-party notices](THIRD_PARTY_NOTICES.md) | Upstream attribution and distribution terms. |
| [Changelog](CHANGELOG.md) | Release history. |
| [Publication](PUBLICATION.md) | Clean source export, checksums and history boundaries. |

Project code and documentation are licensed under [MIT](LICENSE), with an
[unofficial Chinese translation](LICENSE.zh-CN.md). Proteus, its
models, teacher-provided projects, DSH credentials, and private session records
are supplied separately and are not included in the public distribution.
