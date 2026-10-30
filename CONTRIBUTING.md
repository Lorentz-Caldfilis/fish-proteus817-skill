# Contributing

[English README](README.md) · [简体中文](README.zh-CN.md)

## Development

Describe the problem, supported template and desired behavior in an issue or pull request. For implementation work, update the relevant development note before coding. Keep changes focused and report which commands were actually run.

Use Python 3.10+ and a virtual environment:

```powershell
python -m pip install -e ".[dsh,dev]"
python -B -m unittest discover -s tests -v
python -m ruff check .
```

Offline tests use synthetic fixtures and require neither Proteus nor DSH authentication. Runtime changes need a fresh job and an interactive Windows desktop; report the exact tested versions and keep private course inputs and raw sessions outside the contribution.

New behavior should have an observable check or a meaningful negative test. Documentation-only edits need link/command review rather than tests that match wording. Do not turn expected calculations, a successful build or a model summary into a claimed simulation result.

## Public files and releases

Add intentionally public files to `public-release.json`. Export to a new directory with `tools/public_release.py`, then audit and build from the exported tree as described in [Publication](PUBLICATION.md). Never submit credentials, software binaries, teacher projects, course-derived diagrams/screenshots/netlists or personal session records. Synthetic fixtures must be original and clearly identified.

Keep source versions, skill metadata and the changelog consistent. A pull request should explain the concrete change, relevant validation and material limits. See [Development](docs/DEVELOPMENT.md) for architecture and [Security](SECURITY.md) for sensitive reports.

## Licensing and conduct

By contributing original material, you agree to distribute that contribution under this project's [MIT license](LICENSE). Preserve upstream copyright and license notices for reused material and identify its source; do not submit code whose terms conflict with distribution here. This project does not require a separate contributor license agreement.

Communicate respectfully, explain evidence and uncertainty, and review technical claims rather than making personal judgments.

## 中文说明

提出修改时先说明具体问题、模板与预期行为；开始实现前先更新相应开发说明。离线测试使用原创合成数据，不需要 Proteus 或私有课程文件；`python -m ruff check .` 检查离线源码，不改写已审阅的 vendor 目录。运行适配改动需使用新任务副本在交互桌面验证，并如实写出版本、实测与限制。

新增公开文件需要进入 `public-release.json`，发行包从全新导出目录构建。不要提交课程原件、衍生电路图/截图/接线图、软件文件、凭据或个人会话。原创贡献使用 MIT，复用上游材料保留其归属与许可。文档修改检查链接和命令，不为匹配措辞而新增测试。
