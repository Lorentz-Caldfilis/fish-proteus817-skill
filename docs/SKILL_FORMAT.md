# Skill format and upstream references

[English README](../README.md) · [中文说明](../README.zh-CN.md)

## Normative format

This project follows the [Agent Skills specification](https://agentskills.io/specification), checked on 2026-10-26. A skill is a directory with a `SKILL.md` entrypoint containing YAML frontmatter and Markdown instructions. The name matches the directory; references are loaded only when relevant.

```text
skills/
└── fish-proteus817/
    ├── SKILL.md
    ├── LICENSE.txt
    └── references/
        └── cases-and-evidence.md
```

The entrypoint declares `name`, `description`, `license`, `compatibility`, and string-valued `metadata`. This skill has specific requirements: Windows desktop access, the companion repository/Python backend, a compatible local Proteus installation, separately supplied course projects, and DeepSeek Harness for agent execution.

The format does not require duplicating the Python backend inside the skill directory. This distribution supplies the backend in the same repository; copying only the skill directory is insufficient. `tools/dsh_install_skill.py` installs it into the repository-local `.dsh/skills/` directory. The optional frontmatter fields describe the package; execution permissions are enforced by the host and typed tool, not granted by a YAML declaration.

Release 0.1.1 passed the specification's [skills-ref reference validator](https://github.com/agentskills/agentskills/tree/69ef37e9424c0a7ea9dd2293b559e43ec8176379/skills-ref), version 0.1.0, with no reported problems. That development tool requires Python 3.11+, separately from this project's Python 3.10+ runtime. Its pinned check is also included in CI; a successful format check does not certify the simulation behavior.

## Reference repositories

| Source | What was used |
| --- | --- |
| [Agent Skills specification](https://agentskills.io/specification) | File structure, frontmatter, naming and progressive disclosure. |
| [Anthropic Skills](https://github.com/anthropics/skills) | Independent skill folders, license attribution and a repository-level user guide. Individual skills have different licenses; none are assumed to share one repository-wide license. |
| [OpenAI Plugins](https://github.com/openai/plugins) | Current official examples of separating repository documentation, skill instructions and supporting resources. Its Codex plugin manifest is specific to that host and is not added to this DSH skill. |
| [OpenAI Skills](https://github.com/openai/skills) | Historical examples, including per-skill `LICENSE.txt`. As checked on the date above, that repository directs current examples to OpenAI Plugins. |
| [DeepSeek Harness](https://github.com/deepseek-ai/deepseek-harness) | The target harness and its host/plugin boundary. This project was locally tested with DSH 0.2.1-rc.3. |
| [Teacher-referenced proteus-skills](https://github.com/kudoumakoto6523-design/proteus-skills) | Original workflow context. Upstream 8.16 observations are not treated as tests of this 8.17 adapter. |

Using these conventions is not certification, endorsement, acceptance into an official catalog, or tested compatibility with every Agent Skills host. Only the DSH/local-runtime combinations described in [Validation](VALIDATION.md) have recorded desktop results.

## License structure

The original implementation and public documentation use the [MIT license](../LICENSE). The skill contains the same text in `LICENSE.txt`, so its notice travels with the folder. Included upstream MIT code retains its own copyright notice. External course projects, proprietary programs and their derivatives are outside that grant; see [Third-party notices](../THIRD_PARTY_NOTICES.md).

## 中文说明

规范依据为 Agent Skills 官方格式：独立目录、YAML 元数据、`SKILL.md` 主入口及按需读取的参考文件。README 面向安装和使用者，Skill 正文面向执行任务的模型，两者不重复承载全部内容。

本项目是 DSH Skill 和配套后端，不因遵循共同文件格式而自动成为 Codex/Claude 插件，也不声称已经被官方市场收录。`LICENSE.txt` 随 Skill 目录携带；课程原件和电路衍生材料的权利不由 MIT 许可覆盖。
