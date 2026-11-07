# Documentation

This documentation belongs to the optional `codex/school-non-system-paths` branch for users who cannot write to the system drive. For ordinary use, start with [main's documentation](https://github.com/Lorentz-Caldfilis/fish-proteus817-skill/blob/main/docs/README.md). Main prioritizes the skill's circuit-design, editing and verification workflow; it does not require this branch's school-specific write policy.

这是可选学校分支的文档。日常使用选择 main，优先完成 skill 的核心用途；禁止写系统盘的特殊要求只针对本分支。

Start with [Getting started](getting-started.md) if you want the install to work. The pages below are the rest of the map. Recorded lab results live under [release/](release/README.md), not in the README.

| | |
| :-- | :-- |
| **[Getting started](getting-started.md)** | Requirements, the three setup steps, and the optional course materials |
| **[Configuration](configuration.md)** | Environment variables and where a default install is found |
| **[Using the skill](skill-usage.md)** | How DeepSeek Harness is supposed to use `fish_proteus_design` |
| **[CLI and Python](cli.md)** | `fish-proteus`, the library, and the launchers you do not need for a normal chat |
| **[Architecture](architecture.md)** | Directories, and which design notes are the lab record |
| **[Troubleshooting](troubleshooting.md)** | The failures that look like a broken circuit and are not |
| **[Release notes](release/README.md)** | What was checked, on which build, and what is still open |

The skill the agent reads is [`skills/fish-proteus817/SKILL.md`](../skills/fish-proteus817/SKILL.md). Its longer contracts are in that folder's `references/`.

## 中文

面向人的入口是仓库根目录的[简体中文 README](../README.zh-CN.md)。上面这几页是英文说明，结构与中文 README 的文档表一致。实测和发行身份在 [release/](release/README.md)，设计笔记在 [design/](design/ARCHITECTURE.md)，其中几篇原文是中文。
