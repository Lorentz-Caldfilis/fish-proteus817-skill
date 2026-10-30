# Public-source publication

This repository separates the reviewed public source distribution from private course material and historical desktop evidence. The exporter is a local packaging tool; it does not alter repository visibility, rewrite history, create GitHub releases or upload to a registry.

## Current distribution and completed 0.2.0 baseline

The current source version is 0.3.0. Desktop integration for that version is
recorded in [release status](docs/release/RELEASE_STATUS.md). Version 0.2.1 was the
previous documentation and release-metadata revision for the clean public
repository
[fish-proteus817-skill](https://github.com/Lorentz-Caldfilis/fish-proteus817-skill).
The 0.2.1 simulation implementation is unchanged from 0.2.0. Release status
keeps that completed 0.2.0 acceptance separate from later distributions.

The 0.2.0 development evidence includes 13 native structural cases and six GPIO
sequences on the documented input paths. Its **final wheel**, separately from
the earlier candidate, passed representative native checks in an isolated
installation (`installed_wheel_native_verified`), completing its G12 acceptance.
Each rebuilt distribution requires its own artifact hashes and actual
installed check. G13 completed a real runtime continuation after specific user
authorization, with independently checked native SDF, firmware, clocks, GPIO and
cleanup. Its 19 requests followed a separate 17-request file phase on the same
managed task. Archive checksums and the corresponding installed-native reports
are stored alongside the artifacts; this document does not embed its own
archive's checksum or claim universal compatibility.
The completed 0.2.0 supported scope and its limits are recorded against the
G01–G14 gates in the
[roadmap](docs/design/ROADMAP.md) and [validation record](docs/release/VALIDATION.md)
and bound to the final artifact identities in [release status](docs/release/RELEASE_STATUS.md).
Earlier 0.1.x source/package identities and runtime records remain historical evidence.

Review the generic backend, adapted vendor source, Skill references and original
firmware **source** in the public allowlist. Installed device/model definitions,
official format containers and donors, compiled firmware, native projects,
SDF/graph exports, screenshots, machine paths and raw DSH sessions remain local.
The MIT notice does not relicense those external inputs or their raw artifacts.

Keep the six-control scope with the release: LOGICSTATE/LOGICTOGGLE were
direct; four passive controls required ADC+BUFFER simulation conditioning.
Retain the direct-input failures, diagnostics and LOGFILE/native-option
distinction in private provenance. Observed functional success is not a blanket
error-free or physical-interface claim. The real DSH file phase completed 17
requests/four file assertions; its authorized runtime continuation independently
established the response closure. Preserve per-assertion evidence levels and
the retained failed attempts.

The earlier clean candidate source ran 161 tests with 16 explicit skips. Its installed
smoke used Python `-I`, matched three site-packages module hashes to clean
source, and verified native structure, a single GPIO sequence with five controls
bound, spare-control idempotence, reset returning stopped and fresh duplicate-name
CSV. Restart and five simultaneous GPIO outputs were not tested. Preserve this
candidate's identity separately from each rebuilt archive; the results do not
predeclare a future wheel hash or a CI result.

## Build a new distribution

From a trusted checkout with `.[dsh]` installed, choose a new output directory:

```powershell
python tools/public_release.py --output .work/public-release
python tools/public_release.py --check .work/public-release/repository
```

The output contains:

| Item | Purpose |
| --- | --- |
| `repository/` | Clean source tree containing only `public-release.json` entries and a generated `PUBLIC_MANIFEST.json`. The manifest is created here; it is not a source file in Git. |
| `fish-proteus817-<version>-source.zip` | Portable copy of that tree, with deterministic member ordering and timestamps. |
| `SHA256SUMS` | SHA-256 of the source ZIP. |
| `release.json` | Local export result and file/manifest identity. |

Owned source text is normalized to UTF-8/LF for reproducible packaging. Original evidence bytes are never normalized or copied into the public tree. The audit checks the exact file set, hashes, bundled license identity, skill frontmatter, Python syntax and local documentation links. It is an integrity check of the reviewed allowlist, not legal certification or a universal secret detector.

## Python distributions

Build from the exported `repository/` in a separate environment with current build tools, never from a private checkout containing untracked runtime probes or stale build output:

```powershell
python -m pip install build
python -m build .work/public-release/repository --outdir .work/public-release/python-dist
```

Inspect wheel and sdist members against the public allowlist. The Python package carries the project license and included upstream notices; the full repository is still required for the Skill and DSH project tools. Creating these files does not publish them to PyPI.

Verify the adapted-source manifest after intentional implementation changes and
before export. Keep the pinned upstream Git blob identities distinct from the
adapted SHA256 values; include the bundled MIT license and modification/scope
notices. The reference project's historical native report or earlier wheel is
not evidence for the current package.

Install the final wheel into an isolated environment outside the development
import path. Check actual loaded module identities, resource files, CLI and
representative file/native operations from that installation. Record the exact
source ZIP, wheel and sdist hashes, their member audits and relevant test skips.
An ignored probe can be packaged despite being absent from Git; neither a clean
status nor `.gitignore` replaces export and archive-member inspection.

## Git history and visibility

For an existing private repository that previously stored course screenshots, native netlists or session records, deleting them from a new commit does not remove older revisions. Preserve that history privately. Publish the exported tree to a new clean repository, or use a separately reviewed history-remediation process. An orphan `public-release` branch can carry the clean tree inside the private development repository for review, but it does **not** make other branches or earlier commits safe to expose.

Do not turn the original mixed-history repository public as a shortcut. GitHub also exposes Actions history/logs when a repository becomes public; see [GitHub's visibility documentation](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/managing-repository-settings/setting-repository-visibility). Review destination, history, notices and release contents before that separate publishing action.

The source allowlist excludes original course projects, generated binaries, native SDF/graph artifacts, screenshots, credentials, private sessions and development journals. MIT applies to the original implementation and public documentation only; external materials retain their own rights.

The public destination is the separate clean repository linked above. Its
history and other exposed records must be reviewed independently; do not push
private development branches or merge their history into that repository.

## 中文说明

使用显式白名单生成干净源码目录、可复现 ZIP 和哈希清单；打包工具不改变 GitHub 可见性、不上传包、不改写 Git 历史。Python 发行包应从该全新目录构建，避免私有工作区中的探测脚本或旧构建缓存混入。

若旧私有仓库存过课程电路和会话，只删除当前文件不足以安全公开整个仓库。可以将干净目录推到新的公开仓库，同时保留原私有开发历史；也可先在私有库内用无父提交的 `public-release` 分支评审。该分支不会自动清除其他分支和旧提交，不能直接把原库一键设为公开。

当前仓库源码版本为 0.3.0，桌面接入记录见发行状态。下文 0.2.0 / 0.2.1 仍是历史证据，不改写成 0.3.0 的验收结论。

0.2.0 已有本机结构、六类 GPIO、隔离安装和真实 DSH 闭环证据，ADC+BUFFER、直连失败及诊断限制保留。G13 在具体外发授权后完成独立运行续段，17 次文件请求与 19 次运行阶段请求共享任务但不是同一 DSH 会话。每次发行按实际包哈希和安装报告记录，不继承旧包身份、不制造自包含 checksum 循环，也不预写未来包哈希或 CI。白名单只含原创源码与合法 MIT 改编，不含模型/器件定义、官方 donor、原生工程、编译固件、图像、原始导出、个人路径或会话。

0.2.0 最终 wheel 已完成实际隔离安装原生验收，不再处于“仅候选包通过、最终包待验”的状态。0.2.1 修订公开入口、说明和发行元数据，仿真实现不变；公开目标为独立干净仓库 `fish-proteus817-skill`。本轮新包的实际检查、哈希及远端 CI 只在结果产生后登记，不能将 0.2.0 的包身份改名沿用，详见[发行状态](docs/release/RELEASE_STATUS.md)。
