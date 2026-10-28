# Development and maintenance

## 0.2.2 split-edit regression

Importing a definition, saving, reopening and only then placing an instance is
a required workflow. Same-batch import-and-add tests do not cover it. The patch
recovers only a selected embedded definition's template without overwriting
definitions or parsing every unused device. Check empty and populated sheets,
repeated reopening, duplicate-import refusal and unchanged source inputs.

The DSH launcher must show bounded metadata-only progress while keeping its
final stdout JSON and complete local evidence. Repeated communicate waits must
not resend the task, duplicate model execution or reset the overall timeout.

## 0.2.0 development scope

The 0.2.0 baseline has completed its supported local acceptance, including the
final installed wheel and real DSH task. Version 0.2.1 updates public
documentation and release metadata for
[fish-proteus817-skill](https://github.com/Lorentz-Caldfilis/fish-proteus817-skill);
the simulation implementation is unchanged. [Release status](RELEASE_STATUS.md)
separates the completed baseline from checks of each new distribution.

The 2026-10-27 development target is a composable Proteus 8.17 SP2 Skill:
library discovery, circuit construction/editing, owned native sessions, firmware,
interactive inputs, CM3 GPIO and existing graph measurements. The three 8086
course workflows remain recipes and regression coverage. Adding more fixed
cases does not satisfy the generic-design target.

Read the approved [architecture](design/ARCHITECTURE.md),
[design standard](design/DESIGN_STANDARD.md) and [roadmap](design/ROADMAP.md)
before implementation. The roadmap's G01–G14 requirements determine completion;
the 0.2.0 version number is not an acceptance result. The development evidence
includes 13 native structural candidates and six observed GPIO sequences on
the documented input paths. The final 0.2.0 wheel, after an earlier candidate,
passed representative native checks in an isolated installation, completing its
G12 acceptance. Each rebuilt
distribution requires its own artifact hashes and installed check.
G13 now has an actual authorized DSH runtime continuation with independently
checked SDF, firmware, clocks, GPIO and cleanup. File and runtime phases share
the managed project but use separate DSH sessions. Keep these measured results
and each distribution's identity distinct from general compatibility claims.

## Architecture

| Path | Responsibility |
| --- | --- |
| `skills/fish-proteus817/` | Generic task routing, precise tool references, evidence rules and optional course recipes. |
| `fish_proteus/config.py`, `automation.py` | Immutable installed-resource configuration and public `Library`/`Circuit`/lazy `Session`/`Simulation` API. |
| `fish_proteus/_vendor/proteus_auto/` | Reviewed MIT format/library/runtime modules with pinned original and adapted identities. |
| `fish_proteus/design_cli.py` | Task-scoped typed actions, atomic edit batches, revisions, native sequences and declarative verification. |
| `fish_proteus/firmware.py`, `netlist.py` | Firmware identity/format checks, CM3 event parsing and native SDF parsing without desktop imports. |
| Other `fish_proteus/` modules | Protected course import, fresh 8086 builds, independent waveform/LED readers and course verification. |
| `runtime_adaptation/` | Exact-build Windows session/profile, native numeric time, controls, property read-back, graphs, capture and OCR. |
| `examples/stm32_gpio_follow/` | Original PA0-to-PA5 acceptance firmware source; no compiler or prebuilt firmware is bundled. |
| `tools/` | Generic and course DSH gates, firmware/toolchain helpers, separate file/native acceptance and clean-source export. |
| `tests/` | Original synthetic fixtures, error cases and explicitly optional licensed-local checks. |
| `public-release.json` | Exact reviewed source/document allowlist for the public distribution. |

Before implementation, record the requested scope and acceptance criteria in the relevant issue/design note. Keep calculations, generated artifacts, actual observations and model claims distinct. Update user-facing documentation and the changelog when behavior or compatibility changes.

## Local workflow

1. Install the editable project with its `dsh` extra into one Python 3.10+ environment.
2. Check the precise [Python API](GENERIC_API.md) and [typed tool contract](../skills/fish-proteus817/references/generic-api.md); update their contract when an operation changes.
   Keep the tool's read-only `help` responses aligned with the bundled contract:
   the bounded DSH workflow disables general filesystem access.
3. Run `python -B -m unittest discover -s tests -v` for offline behavior. Licensed-local tests are explicit; public tests must not depend on installed proprietary definitions.
4. Use `tools/generic_structure_acceptance.py` to generate new local projects and authored expectations. Its `file_verified` status does not establish native SDF acceptance. `tools/generic_native_acceptance.py` launches serial owned sessions for a separate check.
5. For runtime changes, create new work copies and test the affected scenarios on an interactive Windows desktop. Serialize native edits, file edits and GUI access. Preserve failed runs; do not relabel them as passes.
6. Retain the course recipes as regression coverage. Widen testing when a change or unresolved risk warrants it, and preserve source/import identities.
7. Update `public-release.json` when adding reviewed public files; refresh adapted vendor hashes only for intentional changes, then verify them with `tools/vendor_provenance.py`.
8. Export a fresh source tree, build Python distributions there, inspect their contents, and retain checksums. Verify the final installed package separately from the development checkout.

An ignored scratch `.py` file inside a Python package can still be picked up by a packaging backend. `.gitignore` alone is not a package allowlist. A fresh export avoids ignored probes and stale `build/` contents from a private development checkout.

## Evidence invariants

Use fresh outputs and bind source, firmware, project revision, native run and raw
evidence identities. Calculate expectations independently of observations.
Separate `prepared`, `file_verified`, `native_verified`, `runtime_observed` and
`runtime_verified`; an agent final, parsed file or opened window establishes
none of the later levels by itself.

Generic `run_for` records the initialized native start/end clock, elapsed time,
tolerance, overshoot and completion reason. A startup interval before that start
is not part of the request. GPIO event timestamps and CSV axes do not substitute
for the current interactive clock. The older course runner has optional clock
OCR: unreadable timing stays false/null while a sufficient independently
measured waveform can still establish frequency behavior.

Control commands, mechanical positions and downstream GPIO/voltage/LED response
are different evidence. Bind controls in the file layer, then save/reopen before
interaction. Keep an input/output transition sequence in one Session/PID. Graph
evidence requires clearing and recalculating existing analyses; duplicate CSV
trace names retain their occurrence, and interpolation cannot extrapolate.

For the tested STM32 model, direct LOGICSTATE/LOGICTOGGLE inputs and passive
controls are separate compatibility paths. The four passive controls require
the exercised 3.3 V ADC interface plus ideal digital BUFFER; their direct-to-PA0
candidates failed. Preserve that limitation when changing fixtures or reports.
This simulation interface does not validate a physical logic IC.

Generic log/GPIO evidence finalizes after normal owned-process exit. Match the
complete raw-log hash and native step-clock prefix, with one engine epoch per
trace sequence. The later installed candidate-wheel check observed reset
returning stopped, with no restart witness. Five controls were bound together;
SW1 supplied GPIO evidence and SW2–5 supplied state/idempotence checks, not five
simultaneous GPIO outputs. LOGFILE
restoration is distinct from native Save normalizing indexed TRACE_* options.
Retain TLS and other diagnostics; functional GPIO success does not establish
an error-free log.

Both the historical candidate and final 0.2.0 wheel used Python `-I`, loaded three public modules from
site-packages with hashes matching the clean source, and exercised native
structure/save/reopen, MCU/log behavior and fresh repeated-name CSV. The
earlier clean source copy ran 161 tests with 16 explicit skips; final 0.2.0 clean
source recorded 166 tests, with 150 passed and 16 explicit skips. The development checkout's
166/13-skip result and 11 local checks remain separate. Each release binds its
actual wheel hashes and isolated native report outside the archive. Do not
inherit a previous archive's identity or claim CI execution from local results.

For time assertions, use full native-sequence step indices, not the ordinal
number of a run_for call. The real DSH task retained an initial failed time
verification, corrected indices without changing the requested durations or
tolerances, then passed its runtime checks. Mixed-basis verification retains
its weakest basis; do not rename a native_verified aggregate as runtime_verified.
Audit complete local tool-result copies and hashed job artifacts when CLI
projections are incomplete; CLI projection length does not establish what
entered the model context.

8255 observations require independently read PA0 and LED states, native wiring checks and stable transitions in one simulation. Grey loaded pin markers remain unknown. Cleanup may close only the process owned by the current session and remove only its exact temporary staging directory.

## Source and compatibility boundaries

The vendor modules come from the pinned MIT reference recorded in
[`PROVENANCE.json`](../fish_proteus/_vendor/proteus_auto/PROVENANCE.json).
Preserve the original Git blob identities, adapted SHA256 values and notices.
The upstream's historical 8.16 records and earlier wheels do not establish
acceptance of this source or its 8.17 package. Do not replace an exact-build
profile with a version-name check or bypass an unknown layout.

Installed libraries, official project containers/donors and user firmware are
local read-only inputs. Public code can describe how to use them; do not export
their definitions, compiled firmware, diagrams, native graphs or raw sessions.
The pure file/firmware modules must remain importable without loading Windows
desktop APIs. See [Validation](VALIDATION.md) for the current evidence boundary.

## Version and publication

Keep the package version, `fish_proteus.__version__`, skill metadata and publication configuration aligned. This project has no automatic PyPI upload, official-catalog submission or visibility-changing workflow. See [Publication](../PUBLICATION.md), [Contributing](../CONTRIBUTING.md) and [Third-party notices](../THIRD_PARTY_NOTICES.md).

For a documentation/metadata revision, record the changed files and verify new
links, source/package members and the actual installed distribution. Compare
the affected implementation identities to the accepted baseline when reusing
behavioral evidence. Report any new native or DSH execution explicitly; unchanged
code and an installation check do not establish that a new simulation ran.
Keep new package hashes and CI results tied to the actual version/commit, and
retain the earlier baseline separately in [release status](RELEASE_STATUS.md).

## 中文维护约定

构建前先记录用户需求、授权范围与验收条件。实现后按受影响范围检查，保留失败记录，再更新文档与版本记录。公开文件采用显式白名单；未提交 Git 的探测脚本也可能被 Python 打包工具发现，因此必须从全新导出目录构建发行包，不能把 `.gitignore` 当作分发边界。

私有课程材料和会话留在本地或私有开发历史中。复制、打包、提交源码和改变仓库可见性是不同操作，不能互相替代。

0.2.0 以通用元件/引脚/拓扑组合、受管会话、固件、交互和测量为主；三个课程例程保留为 recipes。设计来源、规范与 G01–G14 门槛以 `docs/design/` 为准。文件重开、原生 SDF、实际时间/输出、DSH 和最终安装包分别验收，进行中项目不得提前写成通过。

已记录结构、六类 GPIO 与隔离安装验证；ADC+BUFFER/直连限制、reset 仅 stopped、restart 与五路同时 GPIO 未测继续保留。G13 在具体外发授权后完成真实运行续段：文件阶段 17 次请求/四断言，运行阶段 19 次请求，复用项目但不是同一 DSH 会话。计时索引失败与纠正记录保留，七项混合验证总状态仍按最弱依据记 native_verified；每次发行另绑定实际包哈希与安装报告。

0.2.0 最终 wheel 已实际重新安装并完成单独原生验收；0.2.1 只修订公开文档和发行元数据，仿真实现沿用该基线。本轮新包的安装/成员/来源身份检查与 CI 必须按实际结果登记，既不把旧包哈希移给新包，也不把未重跑的原生/DSH 场景写成新实验。
