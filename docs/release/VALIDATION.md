# Validation and reproducibility

[English README](../../README.md) · [中文说明](../../README.zh-CN.md)

The completed final 0.2.0 package baseline is recorded in
[release status](RELEASE_STATUS.md). Version 0.2.1 changes public documentation
and release metadata while retaining that simulation implementation. New
distribution identities, installation checks and remote CI results are recorded
for their actual artifacts; the historical results below do not predeclare them.

## 0.2.0 recorded generic acceptance

The 2026-10-27 target extends the public interface from three course recipes to
composable `Library`, `Circuit`, `Session` and `Simulation` operations. The
[architecture](../design/ARCHITECTURE.md), [standard](../design/DESIGN_STANDARD.md) and
[G01–G14 roadmap](../design/ROADMAP.md) define the required evidence. This section
records the 0.2.0 development and final acceptance. The **13-case native structural matrix has
passed**. Six native GPIO sequences passed their functional/source/ownership
checks on the documented topologies, with diagnostics retained. The final
0.2.0 wheel passed representative isolated-installation native checks,
completing its G12 acceptance; rebuilt distributions require their own identity
and installed check. Earlier candidate results are labeled separately below.
G13 completed a real, specifically authorized DSH runtime continuation. These
records establish the documented reference-aligned supported scope on this
local 8.17 build, within the limits below.

| Gates | Completed 0.2.0 evidence | Limits and later-release requirements |
| --- | --- | --- |
| G01–G02: devices | Actual local library lookup and native generation/save/reopen with R/C, DEVICE:RES, diode, NPN, relay, LED, ULN2003A and ATMEGA328P; the catalogue SDF matched all nine parts. STM32 definitions can come from a local donor. | U1/U2 title placement passed a later native/visual check; no claim that every imported device was simulated. |
| G03–G06: editing and nets | All 13 candidates passed native checks and file reopening after native save, including terminal types, 50/51/53-byte properties and ADI→file→native editing. The corrected reversed-wire native follow-up also passed. | Each release binds its own identities; support remains bounded to recognized layouts. |
| G07: firmware | The same hash-identified original DWARF-2 ELF loaded and produced PA5 responses in all six recorded sequences; the final installed wheel separately passed its original-firmware GPIO check. | ELF container validity alone is insufficient; later releases bind their own installation evidence. |
| G08: native time | Actual clock readings cover 0.01/1.25 s and real `timer_roundoff_pause`. The later installed candidate also observed reset returning stopped. | Restart was not exercised; do not infer a cleared clock or restarted engine from stopped state. |
| G09–G10: controls and GPIO | Six downstream PA5 010 sequences passed on the documented paths. An installed candidate bound five LOGICSTATE controls together: SW1 supplied GPIO 010; SW2–5 supplied press/repeat/release and unchanged-clock checks. | Preserve the direct/passive distinction. This does not establish five simultaneous GPIO responses. |
| G11: existing graph CSV | Fresh amplitude-1/2 voltage/current/waveform samples approximately doubled; an independent RC comparison and same-name frequency columns are recorded. The final installed wheel separately produced a fresh 41-row repeated-name CSV. | Report measured numerical discrepancies without inventing a post-hoc acceptance tolerance; representative installed checks do not repeat every source scenario. |
| G12: package | The final 0.2.0 wheel built from the 115-file clean export returned `installed_wheel_native_verified` under Python `-I`; installed module hashes and representative structure/MCU/CSV behavior were checked. Final artifact identities are in [release status](RELEASE_STATUS.md). | Rebuilt distributions must retain separate artifact hashes and actual installed checks; a previous archive identity cannot be inherited. |
| G13: agent | File phase: 17 requests/four assertions. A separately authorized runtime continuation: 19 requests, verified SDF/firmware/clocks/GPIO and cleanup. All final seven assertions passed. | Preserve each assertion's basis: mixed aggregate native_verified; time-only verification runtime_verified. Separate DSH sessions shared one managed project. |
| G14: protection and provenance | Exercised installed inputs retained hashes; the private course integrity check matched all 22 imported files and the teacher originals. Negative file/revision/path checks are present. Final vendor provenance, owned-process cleanup and 47 package-audit checks passed for 0.2.0. | Repeat affected provenance, public allowlist and package checks for each new distribution; retain private originals and raw evidence separately. |

These file checks use authored topology expectations, including required
connections and required isolation. The structural helper emits a native queue;
its `file_verified` status does not attest native capture provenance or electrical
behavior. Saved/parsed files, native SDF, measured outputs and independent
runtime assertions remain separate levels.

On 2026-10-27, the maintainer refreshed the intentional adapted-source identities
and executed all **16 tests** in `test_generic_acceptance.py` with the licensed
local checks enabled; all passed. This is a development-source result. Subsequent
changes require relevant checks and a final provenance refresh; it is not a
record of the final installed 0.2.0 package.

The final structural batch verified **13 candidates**, including the catalogue,
six-way and surviving networks, wire-label merge/removal, edited components,
empty/repopulated files, independent terminal types and the 50/51/53-byte
property boundary. Every candidate was reopened by the file API after its
native save. The separate ADI continuation set native VALUE/API_NOTE, saved,
reopened in the codec, changed the value, and confirmed that change through
another native SDF. Queue originals retained their hashes and all owned
processes closed. This establishes the recorded structural scope; the catalogue
devices were not all simulated.

The revised 3×3 catalogue screenshot contains all nine parts inside the page
frame. A later change moved only U1/U2 title coordinates above their bodies. Native
SDF, save/reopen, ADI continuation and a new screenshot confirmed COM/PD0 were
clear of those titles; this is not a general label-placement algorithm. A later VSOURCE fixture prompted an independent native A/B test of
two-pin endpoint ordering. The corrected reverse-order candidate passed native
save and file reopening, with strict new-route validation retained.

The final development-source suite recorded 166 discovered tests: 153 executed
successfully and 13 skipped. The two enabled local classes added 11 successful
checks. The official Skill validator accepted the Skill, and all 12 adapted
vendor entries matched provenance. These checks precede G12 and do not establish
the identity or native behavior of the final installed wheel.

### Historical candidate-wheel acceptance

A wheel built from the 115-file clean source export was installed into a
separate virtual environment and exercised with Python `-I`. The result was
`installed_wheel_native_verified`. The loaded fish_proteus package, automation
module and runtime adapter came from site-packages; their SHA256 values matched
the clean source. The earlier clean candidate separately ran 161 tests, with 145
executed successfully and 16 explicit skips for unavailable tools/private
resources and other declared local conditions.

The installed-wheel run created a three-resistor junction, checked actual
native SDF, saved and reopened it. In one MCU process, five LOGICSTATE controls
were bound together. SW1 produced actual PA5 0→1→0 at 0.002507375,
0.100003 and 0.200002375 seconds; SW2–5 each exercised press, a repeated command
with changed=false, and release without advancing the paused clock. The
DWARF-2 ELF identity matched the earlier runs. The complete native log had no
reported diagnostics in this candidate; the earlier TLS-bearing runs remain
unchanged. Inputs retained hashes and the process closed normally.

The same candidate observed reset returning stopped; restart was not tested,
and the reset result is not a claim of a zero clock. A fresh FREQUENCY RESPONSE
export contained 41 rows and two separately addressable C1(2) columns, then
closed normally. These are representative installed-candidate results, not a
claim that every source scenario or five GPIO outputs ran simultaneously.

Documentation updates change distribution identities. Each release keeps its
archive hashes and actual installed-wheel report outside the archive; a
previous candidate's hash cannot establish a rebuilt distribution's identity.

### Final 0.2.0 wheel acceptance

The final wheel was rebuilt, installed again in an isolated environment and
checked using Python `-I`; this was an actual package acceptance after the
candidate described above. Its SHA256 is
`9d7b80684d8d8b6cd90d182a9544917e86adbdfd74e81ec15aa9140c499c7f99`.
The result was `installed_wheel_native_verified`, with module identities checked
against final clean source. Native structure/save/reopen, five bound controls
with one GPIO 0→1→0 chain, spare-control idempotence, reset returning stopped and
a fresh 41-row graph CSV passed. Protected inputs retained their hashes and
owned processes closed normally. Restart and five simultaneous GPIO responses
remain untested. The complete final report's SHA256 is
`88c7330c430bdc23b0c53c163cf31be3aec409d61b07d17926dffc17c2227358`;
raw machine paths and logs remain private.

The final clean source separately recorded 166 discovered tests: 150 passed
and 16 explicitly skipped. The final package-member audit passed 47 checks.
The DSH acceptance and final-adapter recheck below are separate actual runs;
neither is inferred from a package installation. [Release status](RELEASE_STATUS.md)
binds those completed 0.2.0 records and explains the 0.2.1 publication revision.

An initial native batch exposed a property-serialization defect above 50 bytes
that both the writer and offline parser had accepted. Both were corrected and
the failed records retained. A separate six-terminal test also distinguished
default generic terminals (`GT`) from actual wire labels (`LBL`); the original
expectation had confused those objects. The corrected expectation is supported
by the installed help and a pre-existing paired official DSN/SDF example, not
solely by changing the target to match this run. The corrected independent
terminal test passed in the final structural batch. Shared-name terminals can
collapse to one native name/type, so a same-name bus alone cannot establish
glyph-type coverage.

### Preliminary numeric time observations

The current native adapter reads the engine clock rather than using the course
runner's optional OCR. A stopped engine must initialize before an actual start
can be defined. In the recorded preliminary session, the first requested interval
started at 0.05 s; the initialization interval is excluded from elapsed time.

| Requested interval | Actual start | Actual end | Actual elapsed | Preselected tolerance |
| --- | --- | --- | --- | --- |
| 0.01 s | 0.05 s | 0.060000000000000005 s | 0.010000000000000002 s | 0.003 s |
| 1.25 s | 0.060000000000000005 s | 1.3099999999999996 s | 1.2499999999999996 s | 0.003 s |

Both records reported an initialized clock, a paused native timer completion and
zero positive overshoot. They demonstrate those captured intervals only, not
completion of G08 or the other 0.2.0 gates. A GPIO event's last timestamp, a CSV
axis, wall time and a requested duration cannot fill a missing current clock.

Another real run started at 0.02 s and reached 0.03 s for a 0.01 s request,
with an actual elapsed value of 0.009999999999999998 s and a remaining timer
value of 1.734723475976807e-18 s. The adapter paused the verified engine through
`timer_roundoff_pause`; this completion path was observed natively, not only in
a mock. That run did not establish the full downstream GPIO scenario.

### Firmware, logs and agent progress

The original firmware built as a DWARF-2 ELF loaded and executed in the tested
8.17 build. A DWARF-5 ELF from the same machine-code payload failed to load,
while the matching HEX succeeded. The helper now defaults to
`--dwarf-version 2`, with 4 and 5 available for explicit compatibility testing.
Container validation and machine-code identity therefore do not by themselves
establish native debug-loader compatibility.

Generic GPIO/log evidence is finalized after a normal owned-session close,
using the complete hashed raw log and actual step-clock prefixes. All six
recorded controls and PA5 output sequences were independently read as 0→1→0.
Each sequence kept one PID, verified actual clocks, normal close, unchanged
source identity and a restored temporary LOGFILE field.

| Control | Tested path to STM32 PA0 | Observed PA5 |
| --- | --- | --- |
| LOGICSTATE | Direct digital input | 0→1→0 |
| LOGICTOGGLE | Direct digital input | 0→1→0 |
| BUTTON | 3.3 V source → ADC interface → ideal digital BUFFER | 0→1→0 |
| SW-SPST | Same explicit conditioned path | 0→1→0 |
| SW-SPST-MOM | Same explicit conditioned path | 0→1→0 |
| SWITCH | Same explicit conditioned path | 0→1→0 |

The conditioned ADC uses low/high thresholds 0.8/2.5 V with 0.2 V hysteresis.
Direct passive-to-PA0 candidates at 3.3/5 V, a static closed state and a floating
input firmware variant did not yield the required transitions. Those failures
remain separate. This validates the stated simulation interface, not a repaired
direct analogue-to-MCU bridge or a physical IC.

The frozen aggregate is `native_gpio_observed_with_diagnostics`: all six
functional/ownership checks passed, while BUTTON and LOGICSTATE retain TLS
host-name diagnostics. No-error assertions are separate. Native Save normalized
TRACE_* options; only LOGFILE restoration is claimed. Actual parsed native SDF
snapshots and hashes were retained; temporary raw SDF bytes were not retained,
and their raw hash is explicitly unavailable. That six-control matrix did not
exercise independent reset/restart or five simultaneous GPIO outputs. The
later installed candidate's limited reset and five-binding checks are described
separately above.

Fresh graph samples at four recorded times cover INPUT and R1(2) voltage plus
ICAP current for amplitudes 1 and 2. Their ratios are approximately two. The
report also retains an independent RC response calculation and its numerical
discrepancies. No acceptance tolerance was invented after observing those
values. Frequency CSV retains repeated trace names with occurrence selection.

### Real DSH design and runtime continuation

The file phase made 17 typed requests, generated a new CPU/LOGICSTATE design and
satisfied four file assertions. After the user explicitly authorized the
particular provider payload, a separate headless runtime continuation finished
with exit code zero, 100 recorded events and 19 typed requests. The credential
store was unchanged. Both phases used the same managed task/project; they were
not one DSH session. Earlier approval rejections occurred before launch and are
retained as history, not a current authorization block.

The final native sequence used one process. Independently parsed PA5 events
were 0 at 0.002559 s, 1 at 0.352524 s and 0 at 0.502519 s. Its three time requests
were each 0.15 s with a preselected 0.003 s tolerance:

| Request | Native start | Native end | Actual elapsed |
| --- | --- | --- | --- |
| 0.15 s | 0.2 s | 0.3525 s | 0.1525 s |
| 0.15 s | 0.3525 s | 0.5025 s | 0.15 s |
| 0.15 s | 0.5025 s | 0.6525 s | 0.15 s |

The final active native clock was 0.6525 s. Native SDF, PROGRAM/HEX identity,
current project hash/revision and registered power script were independently
checked; the project remained editable through Circuit.open. The raw-log hash
matched, the log was complete, final error messages were empty and the owned
process closed normally.

The first eight-step exploratory sequence was not the response closure. An
initial seven-check verification failed its three time checks because it used
run_for ordinals 0/1/2 instead of full-sequence indices 5/9/13. Correcting those
indices preserved the original 0.15 s requests and 0.003 s tolerances. A separate
three-time verification returned runtime_verified; the final seven mixed
assertions all passed with aggregate native_verified, reflecting the weakest
evidence basis. Runtime checks retain their individual runtime basis. Failed
attempts were preserved and the mixed aggregate was not relabeled.

Five CLI tool-result projections were incomplete at an 8192-character display
limit. Review used the complete local tool-result copies and hashed job
artifacts. That projection behavior does not establish model-context truncation.
Raw sessions, provider data and machine paths remain private. Each distribution
separately records actual archive identities and installed-native evidence;
successful G13 execution does not transfer an older wheel's identity to a rebuild.

### Final adapter recheck

The audit found a display precision issue in the earlier JavaScript wrapper:
64-bit process creation identities exceeded the safe-integer range. Python's
original records and native identity guards were exact. The final adapter now
parses out-of-range integer literals as their original decimal strings and
keeps stdout bytes, base64 and SHA256 locally, outside the model projection.
Five additional regression tests cover this boundary and invalid JSON without
changing native time, process ownership or verification rules.

A fresh real DSH continuation using those exact adapter bytes finished with
9 requests and 44 events. In PID 57812, requests of 0.1 s with preselected
0.003 s tolerance produced native intervals 0→0.1, 0.1→0.2 and 0.2→0.3025 s.
PA5 was 0 at 0.002559 s, 1 at 0.100024 s and 0 at 0.200019 s. All seven mixed
assertions passed on the first attempt; the aggregate remained native_verified
under the same weakest-basis rule. It used the same existing task, with no
circuit or firmware changes and save_project=false. The temporary LOGFILE
was restored and the owned process exited normally; final errors were empty.

An independent audit passed 19 checks, including 23 run artifacts, 9 request
reports, all 9 original stdout byte hashes and the exact integer-to-decimal-string
mapping. The raw log SHA256 was
`29e5d62b5850bc56cc06d52b004161be498f69dad35d2eb5c45e8c8b0210ed71`.
Three CLI mirrors still hit the 8192-character rendering limit; complete local
reports remain the audit basis, with no claim about model-context truncation.
The earlier attempts and precision finding remain separate historical records.

### Reproduce the generic checks

The public offline suite needs neither Proteus nor private course files:

```powershell
python -B -m unittest discover -s tests -v
python tools/vendor_provenance.py
```

With your own licensed local installation, generate a fresh structural queue:

```powershell
python tools/generic_structure_acceptance.py --output .work/my-structure
```

Then, separately on the interactive Windows desktop, launch serial native checks:

```powershell
python tools/generic_native_acceptance.py --queue .work/my-structure/acceptance.json --output .work/my-native-structure
```

Local integration tests in `test_generic_acceptance.py` can also be enabled with
the process environment variable `FISH_GENERIC_TEST_LOCAL=1`; they do not launch
Proteus. Full runtime testing uses appropriate runnable projects, local models,
firmware and fresh raw evidence. The [typed tool contract](../../skills/fish-proteus817/references/generic-api.md)
defines exact actions, one-session sequences and assertions. New work directories
are required; generated project/model data and raw sessions remain private.

## Recorded desktop baseline

The following are maintainer-recorded results from the 0.1.0 development baseline on 2026-10-26. Raw course diagrams, screenshots, native netlists, local paths and DSH sessions remain private; they are not part of the open-source grant. These aggregate results are not a substitute for reproducing the task with your own legitimately obtained course files.

| Component | Recorded environment |
| --- | --- |
| Proteus | 8.17 SP2, `PDS.EXE` 8.17.37159.0 |
| Python | 3.14 for the desktop runs |
| DeepSeek Harness | 0.2.1-rc.3, desktop-bundled CLI, account provider |
| Model | `deepseek-v4-pro` |
| Assembler | Official portable NASM 3.02 |
| Input | Three supplied 8086 course templates, 22 protected original files |

## Observed scenarios

| Scenario | Independently calculated target | Observed result |
| --- | --- | --- |
| 8253 divider, count 5 | 200 kHz | Approximately 200000 Hz |
| 8253 divider, count 10 | 100 kHz | Approximately 100125.156 Hz |
| Cascaded counts 1000 × 1000 | 1 Hz | 1.0 Hz |
| Cascaded counts 1000 × 500 | 2 Hz | 2.0 Hz |
| 8255 default | PA0 1→0→1; LED masks 00h→FFh→00h | Matched in one simulation |
| 8255 alternate pattern | PA0 1→0→1; LED masks CCh→33h→CCh | Matched in one simulation |
| Fresh count-10 job, repeat 2 | 100 kHz | Approximately 100125.156 Hz |
| Fresh count-10 job, repeat 3 | 100 kHz | Approximately 100125.156 Hz |

All eight scenarios met the documented checks. Frequency is calculated from visible waveform edges, grid spacing and a read-back scope timebase; the measurement function receives no expected frequency. The count-10 pixel measurement differs from the target by about 0.1252%, within the preselected 1% limit. The single-counter captures also resolved a 1 MHz input; the slower cascade captures did not independently resolve that input.

Each switch phase required two stable frames of PA0 and LED readings within the same simulation process. The native graph verified the positive-drive LED connections and resistor return to ground. Loaded PB pin markers could be grey, so the result is an LED display observation, not a PB register read. Owned simulator processes were closed, and the originals and import copies retained their hashes.

An early batch stopped at an optional clock OCR check. The correction retained clock errors as diagnostics and reran all six affected counter jobs. Exact elapsed simulation time was still unverified (`actual_time_verified=false`, `simulation_seconds=null`); passing frequency checks do not prove an exact requested duration.

A fresh real DSH session loaded the skill, selected divisor 10 from the requested 1 MHz-to-100 kHz conversion, then executed `doctor`, `prepare`, `build`, `run` and `verify`. All five operations returned zero; 26 recorded verification checks passed. Its final narrative overstated the requested 0.01 seconds as actual elapsed time in one sentence. That statement was rejected during review; neither exact duration nor total cycle count is established by the record.

## Public checks

The baseline suite recorded 70 tests. The public source contains synthetic waveform/LED fixtures, an independent 8086 I/O interpreter and negative tests. One additional real-image regression is optional and skips when the maintainer's private screenshot is not provided. Public CI uses Windows/Linux and Python 3.10/3.14; it does not run Proteus or authenticate to DSH.

Version 0.1.1 improves publication metadata, licensing, documentation and reproducible allowlist-based source export. Simulator control, assembly generation and observation algorithms retain the baseline behavior. Desktop DSH discovery now requires `PATH`, `DSH_DESKTOP_EXE` or an explicit executable, rather than a developer-specific drive path.

The 0.1.1 clean-source candidate passed 82 discovered tests on the maintainer's Windows host: 77 executed successfully and five were explicitly skipped (three optional NASM cross-checks, one private real-image regression, and one symlink test unavailable to that Windows account). No private course files or local toolchain were copied into that test tree. The original development checkout separately executed the NASM checks. The official pinned `skills-ref` format validator reported no errors, and all nine PowerShell examples in each README parsed without syntax errors.

From a checkout with dependencies installed:

```powershell
python -B -m unittest discover -s tests -v
python tools/public_release.py --output .work/release-check
python tools/public_release.py --check .work/release-check/repository
```

For a fresh desktop run after importing your originals:

```powershell
python tools/acceptance.py --library .local/course --output .work/my-acceptance --runtime --repeat 3
```

An unused output directory is required. Omitting `--runtime` produces `build_only`, not a simulation pass. Keep generated files and raw evidence private until their rights and contents have been reviewed.

## Limits

The historical 0.1.x measurements following the 0.2.0 acceptance section cover three existing
circuits and selected variants. They cannot establish the new generic gates.
The generic file editor accepts supported single-user-sheet CDB v7 projects,
conservative orthogonal routes and recognized objects; it does not reconstruct
unknown layouts. Device lookup is not universal import/simulation support.
Graph APIs operate on existing graph/probe objects and bounded generator edits.

No result here establishes arbitrary PCB routing, direct register debugging,
headless Windows service operation, other display/build configurations, other
Proteus versions or future DSH compatibility. Missing or ambiguous actual output
must remain unavailable, even when a file or command was accepted.

## 中文说明

以上为维护者在 0.1.0 本机环境记录的结果，公开版只给出经过筛选的数值、方法和复现步骤，不分发课程电路图、仿真截图、原生接线图或私有会话。0.1.1 的公开发行检查与此前桌面实验分开看待，不能把打包通过或 CI 通过称为重新执行了全部 Proteus 仿真。

0.2.0 在本机受支持范围内完成所述参考能力对齐验证。13 个结构候选、六端子、属性边界、ADI 续编、反向导线与原件保护有记录；目录图九件在 frame 内，U1/U2 标题已移离 COM/PD0 并完成原生及截图复核。默认端子 GT 与导线标签 LBL 有厂商独立资料依据。受支持格式、输入调理、诊断、未测扩展与每次发行包身份的边界继续保留，不扩写为任意 Proteus/PCB 支持。

六类控件与 PA5 均已实际记录 010：两类数字输入直连，四类被动输入经 ADC+BUFFER；直连失败限制、早期 TLS 诊断及 TRACE_* 规范化保留。后续隔离安装候选验证了五控件同时绑定，其中仅 SW1 提供 GPIO 010，SW2–5 验证状态/幂等/时钟不变；reset 返回 stopped，restart 与五路同时 GPIO 未测试。该候选日志完整且 diagnostics 为空，不能据此抹去其他实验的诊断。

开发源码 166 项（153 通过、13 跳过）及额外 11 项本地检查、官方 Skill/12 项 vendor 通过；早期干净候选 161 项（145 通过、16 显式跳过），隔离安装有结构/MCU/CSV 证据。具体外发授权后，真实 DSH 运行续段以 19 次请求、100 事件、exit0 完成；文件阶段 17 次请求/四断言独立保留。最终同 PID 的 GPIO010、三次 .15 秒请求、实际 .6525 时钟、SDF/固件/工程身份和关闭已复核。索引错误的失败记录保留，纠正后七项混合全过但总状态仍为 native_verified，单独计时为 runtime_verified。完整本地结果用于主审计，不从 CLI 投影不完整推断模型上下文截断；每次发行另验该包身份。

旧课程基线的精确经过时长未确认；8255 观察的是 PA0 与 LED 显示，不是 PB 寄存器直读。模型总结中的过度表述已明确拒绝，实际文件与测量结果优先。上游 8.16 历史记录、旧 wheel、本次源码和最终 8.17 安装包的身份与证据也分别保留。

0.2.0 最终发行 wheel 已在候选之后重新安装，并通过实际原生结构、单路 GPIO、五控件绑定/幂等、reset 停止和新 CSV 检查；其报告及包哈希见[发行状态](RELEASE_STATUS.md)。0.2.1 为公开文档和元数据修订，仿真实现不变；本轮打包、安装或远端 CI 的结果必须对应新包和实际提交，本文的 0.2.0 记录不预告其通过。
