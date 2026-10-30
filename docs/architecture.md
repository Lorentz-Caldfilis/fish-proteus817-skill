# Architecture

[Docs](README.md) · [Using the skill](skill-usage.md) · [Design notes](design/ARCHITECTURE.md)

```text
chat in DeepSeek Harness
        │
        ▼
skills/fish-proteus817/SKILL.md     what the agent is told
        │
        ▼
fish_proteus_design                 one desktop tool, registered once
        │
        ▼
fish_proteus/                       schematics, firmware checks, course jobs
runtime_adaptation/                 the Windows session around Proteus 8.17
        │
        ▼
your Proteus 8.17 SP2 install       not in this repository
```

The packages stay at the repository root so an editable install and the desktop tool can import `fish_proteus` and `runtime_adaptation` directly. Moving `skills/fish-proteus817/`, `tools/`, or those two packages means updating the installer and the tests together.

## Directories

| Path | Role |
| :-- | :-- |
| `skills/fish-proteus817/` | Skill entry and the references the agent loads when it needs them |
| `fish_proteus/` | Public Python API, course jobs, and the JSON CLI |
| `fish_proteus/_vendor/proteus_auto/` | MIT format and runtime code, reviewed and pinned. Do not reformat it to chase a linter |
| `runtime_adaptation/` | Windows-only session, capture, and the 8.17 profile |
| `tools/` | Desktop installer, optional headless launcher, acceptance scripts |
| `examples/stm32_gpio_follow/` | Original firmware source for the PA0-to-PA5 example |
| `tests/` | Offline tests. They use synthetic fixtures |
| `docs/design/` | Design record for the 8.17 work. Several of those notes are in Chinese |
| `docs/release/` | What was run, on which artifact, and what failed |

`tools/public_release.py` writes `PUBLIC_MANIFEST.json` into an export directory. That file is generated. It is not source.

## Design record

[Architecture](design/ARCHITECTURE.md), the [design standard](design/DESIGN_STANDARD.md), the [roadmap](design/ROADMAP.md), and the [desktop integration note](design/DESKTOP_INTEGRATION.md) are the notes that were kept while the tool was built. They are more specific than this page, and they are not a warranty that a new Proteus build will behave the same way.

[Development](DEVELOPMENT.md) is the maintainer workflow: what to run, what not to claim, and how a public export is cut.

## 中文

对话读 Skill，Skill 调 `fish_proteus_design`，工具再进 Python，最后才碰到你本机的 Proteus。`docs/design/` 里是实现时留下的设计笔记，有几篇是中文。它们比本页细，但不是对其他构建的保证。
