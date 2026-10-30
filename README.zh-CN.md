# Fish for Proteus

### 在聊天里把 Proteus 实验做完。

**一个 RC 滤波。一块 8086 分频。STM32 上一个跟着另一个走的引脚。**
你在 DeepSeek Harness 里把电路说出来。它在 Proteus 8.17 SP2 里画原理图、连线、加载程序、跑仿真。文件存上了，和仿真里量到了，是两件事。

这是我的课程扩展作业。实验本身还是那些点击：放器件、接线、加载程序，然后判断仿真到底有没有按要求走。

[![License](https://img.shields.io/badge/license-MIT-111111)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-111111)](https://www.python.org/downloads/)
[![CI](https://github.com/Lorentz-Caldfilis/fish-proteus817-skill/actions/workflows/ci.yml/badge.svg)](https://github.com/Lorentz-Caldfilis/fish-proteus817-skill/actions/workflows/ci.yml)
[![Version](https://img.shields.io/badge/version-0.3.0--alpha-111111)](CHANGELOG.md)
![Windows](https://img.shields.io/badge/Windows-0078D4?logo=windows&logoColor=white)
![Proteus](https://img.shields.io/badge/Proteus-8.17%20SP2-111111)

**[文档](docs/README.md)** · **[开始使用](docs/getting-started.md)** · **[Skill](skills/fish-proteus817/SKILL.md)** · [English](README.md) · **简体中文**

## 这东西适合你吗？

Proteus 的工程在你自己的 Windows 桌面上，软件也得你自己有授权。这个仓库教 Agent 怎么用那套安装，它不附带 Proteus、器件库，也不附带你的课程文件。

- **在对话里把电路说清楚。** Skill 会放器件、连引脚，并存成还能继续改的 `.pdsprj`。
- **用这台电脑上真正有的器件。** 它查的是你安装的库。库里搜得到，不代表这个器件能仿真。
- **把存盘和实测分开。** 原理图存好、窗口打开、引脚上量到变化，是三个结果。Agent 被要求分开报告。

你已经装了 Proteus 8.17 SP2，平时用 DeepSeek Harness，就可以用。如果你更想自己在 Proteus 里点，那就不需要它。

当前是 Alpha，版本 0.3.0。它不是 MCP 服务器，也不是 Labcenter 或 DeepSeek 的产品。

## 快速开始

需要 Python 3.10 或更高版本、Git、你自己的 Proteus **8.17 SP2**，以及同一台 Windows 电脑上的 DeepSeek Harness。

**1 · 安装。** 在 PowerShell 里，进到你想放仓库的目录：

```powershell
git clone https://github.com/Lorentz-Caldfilis/fish-proteus817-skill.git
Set-Location fish-proteus817-skill
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dsh]"
```

**2 · 注册一次 Skill。**

```powershell
.\.venv\Scripts\python.exe tools/dsh_install_desktop.py
```

Proteus 或 Harness 不在默认位置时，先把路径设上。说明在[配置](docs/configuration.md)。

```powershell
$env:FISH_PROTEUS_EXE = 'C:\path\to\BIN\PDS.EXE'
.\.venv\Scripts\python.exe tools/dsh_install_desktop.py --dsh-executable 'C:\path\to\DeepSeek Harness.exe'
```

`--dry-run` 只检查，不写入。`--uninstall` 卸掉这个 Skill，并恢复上一次的全局 Skill。仓库留在安装器记下的那个位置。

**3 · 在普通对话里说。** 打开 DeepSeek Harness。不用启动参数，也不用先建任务目录：

> 用 Proteus skill 做一个 RC 低通，R = 2.2k，C = 100n。标上输入和输出，检查存盘后的连线和器件值，告诉我可编辑工程在哪。请说明你只检查了文件，还是已经仿真过。

## 可以这样问

下面是提问，不是某次真实回复。答成什么样，取决于你机器上的器件库，以及你有没有要求仿真。

> 用一块 8253，把 1 MHz 时钟分成 100 kHz，分频比 10。告诉我你量到了什么，不要只根据分频比推断。

> PA0 是输入。在 STM32F103R6 上让 PA5 跟着 PA0 走，加载我的 ELF，把实际记到的 GPIO 边沿给我。

> 打开这个工程，把电阻改成 4.7k，另存一份，不要启动仿真器。

8086 和 STM32 还要你自己准备材料：课程原件、NASM，或者 Arm GNU 工具链。见[开始使用](docs/getting-started.md)。

## 它能做的事

| | |
| :-- | :-- |
| **器件库** | 搜索这台电脑上安装的器件，读取真实引脚 |
| **原理图** | 新建图纸，或在副本上改：器件、连线、标签、电源 |
| **固件** | 检查 ELF 或 Intel HEX，再装到 CPU 上 |
| **仿真** | 管住一个 Proteus 进程，跑一段计时，读 CM3 GPIO 或已有图表 |
| **课程例子** | 可选的 8086 分频、级联计数，以及 8255 控制 LED |

工程里的坐标是 Proteus 整数：**100000 = 1 mm**。

走线是保守的正交线。交互控件目前就是这六种：`BUTTON`、`SW-SPST`、`SW-SPST-MOM`、`SWITCH`、`LOGICSTATE`、`LOGICTOGGLE`。在试过的 STM32F103R6 上，前四种要经过 ADC 再加数字缓冲，PA0 才有反应。这四种直接接到 PA0 时没有得到需要的结果。

## 一次真实运行的画面

> **留给维护者的 TODO。** 这里应放一张截图或一段短 GIF：一边是 DeepSeek Harness 的对话，一边是它存下来的 Proteus 原理图。请用你有权公开的电路。这个位置故意空着，本节里没有任何实测结果。

## 它是怎么串起来的

对话加载的是 `skills/fish-proteus817/SKILL.md`。Skill 调用桌面上的一个工具 `fish_proteus_design`。工具再调用本仓库里的 Python 包，由它去操作你安装的 Proteus。只复制 Skill 目录，工具不会注册上去。

```text
对话 → skill fish-proteus817 → fish_proteus_design → fish_proteus → Proteus 8.17 SP2
```

目录各自干什么，写在[结构](docs/architecture.md)里。

## 配置

| 变量 | 什么时候要设 |
| :-- | :-- |
| `FISH_PROTEUS_EXE` | `PDS.EXE` 不在 Labcenter 的默认目录 |
| `FISH_PROTEUS_LIBRARY` | 器件库在别处 |
| `FISH_PROTEUS_SAMPLES` | 示例工程在别处 |
| `FISH_PROTEUS_TEMPLATE` | 你想换一张空白工程模板 |
| `DSH_DESKTOP_EXE` | 安装器找不到 DeepSeek Harness |
| `DEEPSEEK_API_KEY` | 只用在可选的 headless API-key 路线 |

安装好的 Proteus 文件保持只读。课程和测试用到的其余变量在[配置](docs/configuration.md)。

## 做不到的事

- 原生仿真需要可交互的 Windows 桌面，以及 Proteus **8.17 SP2**（这份代码对着的构建是 8.17.37159）。CI 在 Linux 和 Windows 上跑离线测试，不会启动 Proteus。
- PCB 布局、不认识的工程格式、新建图表或探针，都不在范围内。
- 命令成功不等于电路是对的。没做测量，行为就还没被验证。
- Alpha 版本不承诺支持和修复时限。

实际试过什么、哪些次没过，记在[验证记录](docs/release/VALIDATION.md)和[发行状态](docs/release/RELEASE_STATUS.md)。那两份是证据。这一页不再把它们抄一遍。

## 文档

| | |
| :-- | :-- |
| **[开始使用](docs/getting-started.md)** | 安装、第一次对话、课程附加步骤 |
| **[配置](docs/configuration.md)** | 环境变量 |
| **[Skill 怎么用](docs/skill-usage.md)** | Agent 应该做什么 |
| **[命令行和 Python](docs/cli.md)** | `fish-proteus`、库 API、可选启动器 |
| **[结构](docs/architecture.md)** | 代码和 Skill 各在哪 |
| **[排查](docs/troubleshooting.md)** | 找不到工具、找不到 Proteus、文件和仿真搞混 |
| **[发行记录](docs/release/README.md)** | 已记录的检查，以及它们证明不了什么 |

## 参与

欢迎提 issue 和 pull request。写清电路、Proteus 构建号，以及你实际看到的现象。不要附上课程工程、它们的截图、凭据或原始会话日志。

离线测试不需要 Proteus：

```powershell
python -m pip install -e ".[dsh,dev]"
python -B -m unittest discover -s tests -v
python -m ruff check .
```

其余约定在[贡献说明](CONTRIBUTING.md)。安全问题走[安全说明](SECURITY.md)。

## 许可证

[MIT](LICENSE)。[中文文本](LICENSE.zh-CN.md)是非正式译文。

Fish for Proteus 与 [Labcenter Electronics](https://www.labcenter.com/) 和 DeepSeek 没有隶属关系。Proteus、它的库，以及你的课程材料，权利仍归原处。本仓库保留的上游代码见[第三方说明](THIRD_PARTY_NOTICES.md)。
