# Release notes

[Docs](../README.md) · [简体中文 README](../../README.zh-CN.md)

This folder is the lab record. The README only says what the tool is for. It does not repeat the counts, the hashes, or the runs that failed.

| | |
| :-- | :-- |
| **[Release status](RELEASE_STATUS.md)** | Which version a result belongs to, and which artifact was installed |
| **[Validation](VALIDATION.md)** | How those checks were made, what passed, and what is still open |
| **[Roadmap](../design/ROADMAP.md)** | The G01–G14 gates those notes refer to |
| **[Changelog](../../CHANGELOG.md)** | What changed in the source, in plain language |

Read a result against the version named in it. A 0.2.0 wheel check is not a check of a later tree. A file check is not a native check. A native structural read is not a GPIO measurement. The notes keep those apart on purpose.

How a new source export is built is in [Publication](../../PUBLICATION.md). The exporter writes `PUBLIC_MANIFEST.json` into the export directory. That manifest is not stored in Git.

## 中文

这里是实验记录，不是 README 的另一份缩写。看结论时对着那一版的包。0.2.0 的安装检查不能拿来充当后来版本的结果。文件通过、原生结构通过、GPIO 量到，是三件不同的事。
