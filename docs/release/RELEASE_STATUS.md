# Release status and evidence identity

[English README](../../README.md) · [中文说明](../../README.zh-CN.md)

## Current desktop integration: 0.3.0

Version 0.3.0 adds a persistent ordinary-desktop plugin and session/task/resource
management. The one-time installer preserves other profile settings and installs
the global Skill. The specialized headless launcher remains optional.

Actual normal-desktop acceptance: in the existing desktop conversation,
the real selected model loaded Skill 0.3.0 and called `fish_proteus_design` with
`capabilities`, returning `prepared` and the matching 8.17.37159 profile. No shell
or headless invocation substituted for that call.

In a separate ordinary desktop conversation, a natural-language RC design
completed 41 backend calls, native SDF inspection, five passing structural
assertions and editable-project export. The same conversation created an
independent STM32 task and registered the supplied firmware during work. Its
initial attempts omitted analog supply bindings and then GPIO trace setup;
those failed/unobserved runs remain retained. After the trace prerequisite was
added to the workflow reference and a steer message requested rereading it,
the existing project passed GPIO 010, three actual native intervals of
0.1/0.1/0.1025 seconds (each within 0.003 seconds) and no-errors assertions.
This is a documented continuation, not an unassisted first-attempt claim.
The previous RC task remained intact; an unsupported sample-open scratch task
also remains recorded without a success claim.

The persistent entry uses a stable bootstrap and content-addressed JS
implementations. Actual subsequent tool audits recorded the new implementation
URI after hot updates; ordinary profile settings and tool mode were preserved.
Cold restart was checked without debugging flags: both existing desktop agents
still exposed the tool and the task catalogue restored the previous designs.
This startup check inspected the real registry; model-driven invocation is the
separate desktop evidence above. The temporary verifier was removed, repeated
installation returned `unchanged`, and all profile bytes outside the managed
plugin block matched the original user configuration.

The final clean source passed 245 offline tests (221 passed, 24 explicit optional
environment skips). Official Skill validation, 12 vendor provenance checks and
48 archive/source checks passed. The exact 0.3.0 wheel was installed in an
isolated interpreter: six loaded module identities matched clean source, native
structure/save/reopen, GPIO 010, timing, reset-stopped and fresh 41-row CSV
passed. Installed desktop task creation, automatic revisions and a pure
netlist-only native assertion also passed. An initial private harness attempt
selected a non-ASCII LOGFILE path and was rejected; it remains recorded. The
retry used the backend's owned ASCII staging and passed without a source change.
Final artifact hashes and remote CI/publication identity belong to the release
validation record, not to older 0.2.x assets.

Pure native structural sequences no longer require a simulation LOGFILE when
no log, GPIO or errors observation is requested. Full runtime logging and
hash-based verification remain required for the corresponding assertions.

## Retained 0.2.2 repairs and incomplete acceptance

This patch addresses a user-observed split-edit failure: an imported device
definition survived saving, but its placement template was unavailable after
reopening unless an instance had already been placed. Recovery must use the
selected definition already embedded in the project, preserve collision
rejection and leave unrelated unsupported definitions alone.

The bounded launcher also reports terminal progress without exposing model
text, credentials or raw native logs. Its final stdout JSON and local evidence
retain their existing roles. A terminal heartbeat is not a simulation pass.

The original failed task is retained privately. This document does not predeclare
new test, native, DSH, artifact or CI outcomes: results are bound to the actual
0.2.2 source, packages and external validation summary after execution.

A generated-circuit follow-up isolated a separate power setup error: VCC/GND
rail definitions lacked their same-name net bindings. With the same topology
and firmware, adding only those bindings produced GPIO 010; the unchanged
control case failed native compilation. The Skill reference and demo task now
state the tested requirement. The initial whole-agent retry timed out; any
guided continuation is recorded separately, not relabeled as a single-run pass.

## 0.2.1 publication revision

Version 0.2.1 is an Alpha documentation and release-metadata revision for
[fish-proteus817-skill](https://github.com/Lorentz-Caldfilis/fish-proteus817-skill).
It updates public installation/source links, security-maintenance scope and the
distinction between completed acceptance and historical candidate records.
The DSH model projection's exact documentation-URL allowlist also moves to the
new repository; unrelated, lookalike and credential-bearing URLs remain hidden.
The circuit-design and simulation implementation is unchanged from 0.2.0.
The earlier private development repository and its mixed history remain separate.

This document fixes the completed 0.2.0 baseline below. It does not declare a
0.2.1 archive hash, successful installation, remote commit, CI result or native
run in advance. Those outcomes must be registered against the actual new
artifacts and commits after their checks complete.

## Completed 0.2.0 baseline

The final 0.2.0 release completed the documented supported scope on Proteus
8.17 SP2, build 8.17.37159. It is no longer awaiting final-wheel or real-DSH
acceptance. Public source commit:
`a97a1d7b491562ebba851280533d3ecaa276eb1c`.

| Record | Completed result |
| --- | --- |
| Structural acceptance | 13 actual native cases, including native save/file reopening, terminals, property-length boundaries, branches, wire labels and an ADI continuation. |
| Inputs and measurements | Six actual GPIO 0→1→0 sequences on the documented paths, actual native clocks and fresh existing-graph CSV observations. |
| Final wheel | Actual isolated installation with Python `-I`; installed module identities matched final clean source. Native structure/save/reopen, five bound controls with one GPIO chain, spare-control idempotence, reset returning stopped and a fresh 41-row CSV passed. Result: `installed_wheel_native_verified`. |
| Real DSH | A 17-request file phase and a separately authorized 19-request native continuation shared one managed project. A final 9-request adapter recheck passed all seven mixed assertions on its first attempt, with actual GPIO 010 and a 0.3025 s native clock. The mixed result is `native_verified`; runtime checks keep their individual runtime basis. |
| Independent audit | The final DSH adapter audit passed 19 checks; its byte/integer transport checks did not change native identity or verification rules. |
| Offline and package checks | Development source: 166 discovered, 153 passed, 13 skipped, plus 11 enabled local checks. Final clean source: 166 discovered, 150 passed, 16 skipped. Official Skill validation, 12 vendor-provenance entries and 47 package-audit checks passed. |

These hashes identify **0.2.0 only**:

| Artifact | SHA256 |
| --- | --- |
| `fish-proteus817-0.2.0-source.zip` | `ebb0d7ab9b5677464a2042b66428d82da2f2a6a3ef184b00854ddab1e0dadc70` |
| `fish_for_proteus817-0.2.0-py3-none-any.whl` | `9d7b80684d8d8b6cd90d182a9544917e86adbdfd74e81ec15aa9140c499c7f99` |
| `fish_for_proteus817-0.2.0.tar.gz` | `c1a48486b1caf2a919cf47da11c582ceaa1a3bbb8b68da991ec27f32f0c47f1c` |
| Final installed-native report, retained privately | `88c7330c430bdc23b0c53c163cf31be3aec409d61b07d17926dffc17c2227358` |
| Final DSH independent audit, retained privately | `5c9309010b3b8c2345a99463c2fe8840e9f3afcdf592b2cfdf5e402955945bc5` |

Full reports remain private because they contain local paths and raw runtime
material. [Validation](VALIDATION.md) gives methods, measurements and retained
failures; the hashes above identify those records without disclosing them.

## Registering 0.2.1 and later distributions

1. Export the reviewed allowlist into a fresh tree; record its actual manifest,
   source archive and source identities. Build wheels and sdists from that tree.
2. Audit archive members and third-party notices; install the actual wheel in an
   isolated environment and record loaded module identities and performed checks.
   Reusing the 0.2.0 behavioral baseline requires an explicit comparison of the
   relevant implementation bytes and its unchanged supported environment.
3. Put generated archive hashes in that version's external `SHA256SUMS` and
   sanitized validation record. Record exact commands, results, skips and which
   native/DSH scenarios actually ran. If none ran for a documentation revision,
   state that the native/DSH evidence remains the 0.2.0 baseline.
4. Record a remote commit, CI run and uploaded asset identity only after reading
   their actual results. CI performs offline checks; it does not establish
   Proteus simulation or account-based DSH acceptance.

Metadata changes produce new package identities even when simulation code stays
the same. A previous package hash or successful installation cannot be relabeled
as a new package's result. An earlier candidate record remains historical after
final acceptance; neither kind of record grants additional software capabilities.

## Supported scope and retained limits

This remains an experimental Skill for recognized single-user-sheet CDB v7
layouts and the documented exact native build. Device lookup, import and
simulation are distinct. There is no arbitrary PCB layout or new graph/probe
creation. LOGICSTATE/LOGICTOGGLE were direct inputs; BUTTON, SW-SPST,
SW-SPST-MOM and SWITCH required explicit ADC+BUFFER simulation conditioning.
Their failed direct-to-MCU candidates, earlier TLS diagnostics, time-index
mistakes and corrected wire/property defects remain part of the history.
Reset/restart and five simultaneous GPIO responses were not validated.

## 中文说明

0.2.0 的本机受支持范围已完成验收：最终 wheel 在早期候选之后实际重新安装并执行原生检查，真实 DSH 设计/运行及最终适配器复核也已完成。它不再处于“最终包待验”或“等待真实 DSH”的状态；上表固定该版包、最终安装报告和独立 DSH 审计的身份。

0.2.1 为公开文档、入口和发行元数据修订，并同步 DSH 投影的帮助链接精确白名单；仿真实现不变，公开目标为独立干净仓库 `fish-proteus817-skill`。新包应登记自己的白名单/成员检查、实际安装、模块身份、哈希和实际远端 CI；这些结果不能提前写成通过，也不能用 0.2.0 的哈希代替。若本轮没有重跑原生或 DSH，则明确沿用经过实现身份核对的 0.2.0 行为基线，不宣称新增实验。

Alpha 阶段与开源许可分别描述成熟度和使用条件。本项目继续保留 ADC+BUFFER 输入调理、早期诊断、未知格式拒绝、reset/restart 与五路同时 GPIO 未验证等边界，不因更换公开入口或版本号而扩展能力声明。
