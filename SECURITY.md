# Security and private-data handling

## Supported scope

Security fixes currently target the 0.2.x source line and the documented Windows/Proteus/DSH combination. The 0.1.x line is historical and is not an actively maintained security branch. Other runtime versions require separate compatibility testing. This Alpha project assumes a trusted local checkout, local manifests and an operator-authorized desktop session; no response-time or fix-delivery SLA is offered.

The model-facing tool restricts operation names, numerical parameters and job paths. This reduces what the agent can request; it is not an operating-system sandbox against a malicious host or repository. Review a skill and its companion code before granting it desktop or account access.

## Reporting

If this repository's GitHub Security page offers private vulnerability reporting, use it. Otherwise open a minimal issue requesting a private reporting channel. Do not include exploit details, credentials, private course files or raw logs in that initial public issue. The maintainer can then arrange an appropriate channel. No guaranteed response-time service is offered.

For ordinary compatibility bugs, use the bug-report template and include sanitized version information and the failing stage. A Proteus launch failure and an incorrect observed waveform are different reports.

## Data boundaries

- Keep DSH credential stores, tokens and account files outside Git. The account route may refresh its existing managed sign-in store.
- Runtime outputs can contain full local paths, screenshots of course designs and native circuit graphs. Treat them as private until reviewed for contents and rights.
- Preserve teacher originals; use separate imports/jobs. Do not run the generated 16-bit firmware as a Windows application.
- The runtime should operate only on its owned Proteus PID. A blocked run must not be resolved by replacing software DLLs, disabling checks or changing global ACLs.

The public exporter only copies an explicitly reviewed text-file allowlist and verifies file identities. It does not determine copyright ownership, detect every possible secret or erase earlier Git history. See [Publication](PUBLICATION.md).

## 中文说明

当前安全维护范围为 0.2.x 和文档列明的 Windows/Proteus/DSH 组合；0.1.x 仅保留历史记录，不作为持续安全维护分支。本项目处于 Alpha 阶段，不承诺响应或修复时限。

安全问题优先使用仓库提供的私密报告入口；若没有该入口，先提交不含细节的 issue 请求安排私下沟通，不公开 token、漏洞利用细节、课程文件或原始日志。常规兼容问题请提供脱敏后的软件版本、失败阶段和可复现步骤。

专用工具的参数/目录限制不是操作系统沙箱。课程截图、接线图、会话及本机路径默认私有；公开白名单和哈希检查不能代替权利核验、完整秘密扫描或 Git 历史处理。
