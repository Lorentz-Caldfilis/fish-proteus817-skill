# Security

[English](README.md) · [简体中文](README.zh-CN.md)

Security fixes target the 0.3.x line on the documented Windows, Proteus 8.17 SP2, and DeepSeek Harness combination. Older lines are history, not maintained security branches. This is an Alpha project: a trusted local checkout, local job files, and a desktop session you chose to run. There is no response-time promise.

The desktop tool checks its own operations and works on copies. It can register a project or a firmware file you point at, and it can export to a new directory. It does not try to be a sandbox against a hostile machine or a hostile checkout. Read the skill and this repo before you give them a desktop session or an account.

## Reporting

If this repository's GitHub Security page offers private vulnerability reporting, use it. Otherwise open a short issue that asks for a private channel. Leave out exploit detail, credentials, course files, and raw logs. The maintainer can arrange the channel.

Ordinary bugs use the bug-report template: versions, the stage that failed, and a sanitized reproduction. A Proteus window that never opened is a different report from a waveform that is wrong.

## What to keep private

- Credential stores, tokens, and account files stay outside Git. The Harness account route may refresh its own sign-in store.
- Runtime output can contain full paths, screenshots of course designs, and native graphs. Treat it as private until you have looked at what is in it.
- Keep teacher originals unchanged. Import and jobs use other directories. Do not run the generated 16-bit firmware as a Windows program.
- The runtime should stay on the Proteus process it owns. A blocked run is not a reason to replace DLLs, turn checks off, or change global ACLs.

`tools/public_release.py` copies an allowlist of text files and checks their hashes. It does not decide copyright, find every secret, or erase old Git history. See [Publication](PUBLICATION.md).

## 中文

安全维护范围是 0.3.x，以及文档里写明的 Windows、Proteus 8.17 SP2 和 DeepSeek Harness。更早的版本只留作记录。本项目是 Alpha，不承诺回复或修复时限。

优先走 GitHub 的私密漏洞入口。没有这个入口时，先开一个不含细节的 issue，请维护者安排私下沟通。不要在公开 issue 里贴 token、利用细节、课程文件或原始日志。

这个工具会限制自己的参数，但它不是操作系统沙箱。课程截图、接线图、会话和本机路径默认都是私有的。
