# Contributing

[English](README.md) · [简体中文](README.zh-CN.md) · [Docs](docs/README.md)

Issues and pull requests are welcome. Say what the circuit was supposed to do, which Proteus build you have, and what you actually saw.

## Before you open a pull request

Use Python 3.10 or newer:

```powershell
python -m pip install -e ".[dsh,dev]"
python -B -m unittest discover -s tests -v
python -m ruff check .
```

The offline tests use synthetic fixtures. They do not need Proteus, and they do not sign in to DeepSeek Harness. A change to the Windows session needs a fresh job on an interactive desktop. Write down the versions you ran. Keep course files and raw sessions out of the commit.

New behavior needs a check someone else can run, or a test that shows the failure. A documentation change needs a look at the links and the commands. Do not add a test whose only job is to match a sentence. Do not turn a calculation, a successful build, or a model's summary into a claim that the simulation passed.

Ruff does not reformat `fish_proteus/_vendor`. Those files have pinned provenance hashes.

## What stays out of Git

Add a new public file to `public-release.json`, then export with `tools/public_release.py` as described in [Publication](PUBLICATION.md).

Do not commit credentials, Proteus binaries, teacher projects, screenshots or netlists taken from them, or personal session logs. A synthetic fixture should be obviously synthetic.

## License

Original contributions are under this project's [MIT license](LICENSE). Keep upstream copyright and license notices, and name the source. Do not submit code whose terms conflict with that.

There is no separate contributor license agreement.

Be direct about evidence, including what you could not check.

## 中文

先写清问题、电路和你看到的现象。离线测试不需要 Proteus，也不登录 DSH。改 Windows 会话时用新的任务副本，在交互桌面上验证，并写出版本。

新的公开文件要写进 `public-release.json`。不要提交课程原件、截图、凭据或原始会话。`ruff` 不改写 `fish_proteus/_vendor`。原创贡献使用 MIT；复用上游代码时保留它的许可和出处。
