# Sources and third-party notices

The project's [MIT license](LICENSE) covers its original implementation, skill instructions and public documentation. It does not relicense externally supplied software, course files or their circuit-derived artifacts.

| Resource | Use and distribution |
| --- | --- |
| Teacher-provided 8086/8253/8255 course projects | Supplied separately by the operator. Original project/source files, circuit diagrams, screenshots, generated circuit graphs/netlists and supplied binaries are excluded from the public distribution. The importer records hashes and uses copies. No public-redistribution license is asserted. |
| [proteus-skills](https://github.com/kudoumakoto6523-design/proteus-skills) | Teacher-provided reference for skill workflow and evidence separation; upstream identifies its original skill/example work as MIT. |
| [proteus-automatic-api](https://github.com/kudoumakoto6523-design/Proteus_automatic_package), commit `7439819a7ea4cff47fb9b321d8b0e97ac74fafb2` | PID-scoped Win32/session helpers adapted in `runtime_adaptation/native.py` and `session.py`. Upstream MIT notice is preserved in [LICENSE.upstream](runtime_adaptation/LICENSE.upstream), with modifications described in [NOTICE.md](runtime_adaptation/NOTICE.md). Its license applies to its original code, not proprietary or course samples. |
| Same pinned MIT source, generic adapter | Twelve format/library/runtime modules are adapted under `fish_proteus/_vendor/proteus_auto`. [Original license](fish_proteus/_vendor/proteus_auto/LICENSE.upstream), [modification notice](fish_proteus/_vendor/proteus_auto/NOTICE.md) and [per-file identities](fish_proteus/_vendor/proteus_auto/PROVENANCE.json) accompany the source and wheel. The pure CM3 event parser in `fish_proteus/firmware.py` follows that adapter's log syntax. Original Git blob identities and modified SHA256 identities are distinct; 8.16 historical reports do not verify this 8.17 adaptation. No upstream firmware binaries, device libraries, official samples or native artifacts are redistributed. |
| [EasyEDA API skill](https://github.com/easyeda/easyeda-api-skill), [KiCad IPC design](https://dev-docs.kicad.org/en/apis-and-binding/ipc-api/) | Architectural references for typed API discovery, units, session identity and transactions. No software API, source code, device content or internal file format is copied from these projects. |
| [NASM](https://www.nasm.us/) | Optional portable assembler, downloaded from the official release site with a pinned archive hash. The bootstrap preserves its bundled LICENSE. NASM binaries are not committed here. |
| [DeepSeek Harness](https://github.com/deepseek-ai/deepseek-harness) | Host framework. The project supplies a local skill and launcher, not a copy of the framework or user credentials. |
| [PyYAML](https://github.com/yaml/pyyaml) | Optional MIT-licensed Python dependency for the `dsh` extra. Installed separately; no vendored copy. |
| Proteus 8 Professional | User's installed software, models and libraries; no executable, DLL, license or device-library redistribution. |

Software compatibility observations in this project are measurements on the
reported local installation, not a statement of official Labcenter endorsement.

The pure SDF parser in `fish_proteus/netlist.py` reuses the MIT session helper's
parser without importing desktop code. The STM32 GPIO fixture sources are
original MIT implementation following ST's published register semantics; no
vendor firmware or library is included. The operator supplies a compiler.

Synthetic test fixtures and parameterized assembly-generation code are original project implementation. They encode the supported hardware protocol; they are not a license grant for the external course circuit or any imported source file.

The reviewed public source allowlist is `public-release.json`. Earlier private development history can contain materials excluded from that distribution; changing repository visibility does not make them MIT-licensed. See [Publication](PUBLICATION.md).

## 中文说明

MIT 许可适用于本项目原创实现、Skill 指令和公开文档；纳入的上游 MIT 代码保留其原有声明。第三方程序、课程工程、课程电路衍生图像/接线图及账号数据不在本项目许可范围内，也不随公开源码包分发。

运行者自行取得合法课程资料、Proteus、模型及 DSH。NASM 从官方归档单独准备，PyYAML 通过可选依赖安装；它们保留各自条款。源码生成器和合成测试是本项目实现，不代表外部电路或导入源码获得了重新许可。

格式参考来源见 [Skill 格式说明](docs/SKILL_FORMAT.md)；遵循格式不代表获得相应机构认证或官方市场收录。
