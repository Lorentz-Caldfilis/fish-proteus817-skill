# Fish for Proteus 8.17 SP2

[English](README.md) | [简体中文](README.zh-CN.md)

面向 Proteus 的 Agent Skill 与 Python 工具库：组合受支持的原理图、编辑既有电路、配置固件、运行自有原生会话，并检查实际仿真结果。**DeepSeek Harness（DSH）** 通过类型化设计工具执行任务；三个 8086 课程流程保留为可选 recipes。

**版本 0.3.0 · Alpha · MIT 许可证 · 目标：Proteus 8.17 SP2（8.17.37159）**

本项目以实验性开源 Skill 发布，支持范围如下。0.3.0 增加一次性 DSH 桌面接入、自动会话任务和任务中途工程/固件登记；保留分次导入修复及专用 headless 启动器。[发行状态](docs/RELEASE_STATUS.md)区分桌面验收、各版本实际检查与历史基线。

## 支持范围

| 领域 | 可组合操作 | 边界 |
| --- | --- | --- |
| `Library` | 查询本机器件，读取实际引脚、默认属性、模型及定义身份。 | 查得到、导入成功和支持仿真分别确认。 |
| `Circuit` | 导入所选定义，空白组图或打开已识别布局；添加、编辑、复制、移动、旋转、镜像、删除元件；连接和断开引脚、支路、总线。 | 受支持的单用户页 CDB v7 布局与保守正交布线。 |
| 网络与电源 | 六类端子、真实导线标签、同名逻辑合网、电源轨及绑定。 | 未知对象或无法安全重建的结构拒绝重写。 |
| `Session` / `Simulation` | 管理自有进程，读取原生 SDF/属性，保存，启停/暂停/复位及原生计时。 | 需要可交互 Windows 桌面和精确支持的原生构建配置。 |
| 固件与输入 | ELF/Intel HEX 身份检查、PROGRAM 配置与回读；绑定 BUTTON、SW-SPST、SW-SPST-MOM、SWITCH、LOGICSTATE、LOGICTOGGLE。 | 每个二态输入占两个执行器槽，总共十槽；改绑定后须保存重开。 |
| 测量 | 带时间戳的 CM3 GPIO 事件；已有图表 CSV、同名轨迹 occurrence 和范围内插值。 | GPIO 事件是数字状态；新图表证据必须重新计算已有分析。 |
| DSH 桌面 | 持久工具注册、自动会话任务、本地资源发现/登记、可编辑工程导出、原生序列及断言。 | 首次安装配套接入；实际器件/模型兼容性按任务确认。 |

本机已记录 13 个原生结构候选及六类真实 CM3 GPIO 0→1→0。0.2.0 最终 wheel 已完成实际隔离安装和代表性原生验证，完成该版 G12 验收；每次发行仍须保留该包哈希和安装复核。真实 DSH 在同一受管项目上分文件设计与另行授权的运行续段完成闭环，本机已完成所述参考能力的受支持范围对齐验证。证据与 G01–G14 门槛见[验证说明](docs/VALIDATION.md)和[路线](docs/design/ROADMAP.md)。任意 Proteus 格式、PCB 布局和新建图表/探针不在本实现范围内。

在已测试的 STM32F103R6 配置中，LOGICSTATE/LOGICTOGGLE 直接驱动 PA0；BUTTON、SW-SPST、SW-SPST-MOM、SWITCH 经显式 3.3 V ADC 接口和数字 BUFFER 得到下游 GPIO 响应。这四类被动控件直接接 PA0 的候选未产生所需响应。这里验证的是仿真输入调理路径，不代表实体硬件接口验证。

自然语言要求 → 查询实际定义/引脚 → 组合或编辑 → 保存重开 → 原生 SDF → 固件/仿真 → 实际测量 → 独立断言。

Skill 入口为 [`skills/fish-proteus817/SKILL.md`](skills/fish-proteus817/SKILL.md)。请使用**完整仓库**：Skill 需要配套 Python 后端、Windows 运行适配和工具。单独复制 Skill 目录不会同时安装这些组件或 Proteus。

## 环境要求

- Python **3.10 或更高版本**及 Git；文件层模块可在没有 Windows 桌面的环境导入。
- 原生操作需要 Windows、PowerShell、**可交互桌面**，以及自行合法取得的 Proteus **8.17 SP2**、所需模型、器件库和模板/donor 资源。
- 使用 DSH 时，需要已安装的 DeepSeek Harness、配置好的登录或 API 凭据，以及对应模型服务的网络连接。
- 可选 8086 recipes 需要另行取得的课程原件和 NASM；原创 STM32 GPIO 示例使用另行提供的 Arm GNU 工具链。

公开包不附带 Proteus、器件定义、官方样例、教师工程、编译器或编译后的固件。

## 安装与准备

在 Windows PowerShell 中执行：

```powershell
git clone https://github.com/Lorentz-Caldfilis/fish-proteus817-skill.git
Set-Location fish-proteus817-skill
py -3 -m venv .venv
$FishPython = (Resolve-Path .\.venv\Scripts\python.exe).Path
& $FishPython -m pip install -e ".[dsh]"
```

虚拟环境是可选项。使用现有 Python 3.10+ 时，可设置 `$FishPython = (Get-Command python.exe).Source`，安装和运行均使用同一解释器。`dsh` 可选依赖安装 PyYAML，用于凭据存储处理和日志脱敏。

一次性安装桌面接入：

```powershell
& $FishPython tools/dsh_install_desktop.py
```

安装器会安装全局 Skill，并仅向已有 DSH 桌面 profile 增加本插件，保留备份和其他设置。Python 与仓库绝对位置会持久保存，不依赖临时环境变量。自动发现 DSH 失败时，仅在首次安装补充 `--dsh-executable 'C:\你的路径\DeepSeek Harness.exe'`。请保留该仓库位置；`--dry-run` 只检查，`--uninstall` 撤销本插件并恢复此前全局 Skill。

随后直接在普通 DSH 桌面会话中提出要求，例如：

> 使用 Proteus skill 新建一个 R=2.2k、C=100n 的 RC 低通原理图，添加输入输出标签，检查保存后的连接和器件值，给出可编辑工程位置。请区分文件检查与仿真结果。

不需要逐次准备启动参数、donor 清单或任务目录。工具自动发现安装资源，按对话隔离并管理任务；需要既有工程或固件时，在要求中给出本地路径即可。同一对话要设计另一个电路或继续旧设计，可以直接要求新建或切换任务。详见[桌面工作流](skills/fish-proteus817/references/desktop-workflow.md)；本机实际加载和验收结果见[发行状态](docs/RELEASE_STATUS.md)。

`tools/dsh_install_skill.py` 保留用于专用部署的项目级 Skill 安装，单独执行它不会注册桌面工具。

## 使用 Python 组合电路

```python
from fish_proteus.automation import Circuit, Library, ProteusConfig

config = ProteusConfig.discover()
library = Library(config=config)
print(library.search("RESISTOR", limit=10))
print(library.get("RESISTOR", library="ASIMMDLS"))

circuit = Circuit(config=config)
circuit.add("RESISTOR", "R1", "10k", 0, 0)
circuit.add("CAPACITOR", "C1", "100n", 5_080_000, 0)
print(circuit.pins("R1"))
circuit.connect("R1.2", "C1.1")
circuit.add_wire_label("R1.2", "C1.1", "FILTER_OUT")
circuit.add_terminal("input", "VIN", "R1.1")
circuit.add_terminal("ground", "", "C1.2")
circuit.save(".work/new-filter.pdsprj")
```

这个示例生成可编辑文件，尚未证明滤波器的仿真行为。目标路径应未被使用。坐标为原生整数：**100000 = 1 mm**。`Circuit()` 使用安装中的格式容器创建空白拓扑；`Circuit.open(path, config=config)` 保留已识别的既有布局。额外器件通过明确的器件库选择或本地 donor 导入，再使用实际枚举出的逻辑引脚名或无歧义物理引脚号。

`ProteusConfig.discover()` 支持显式资源路径和当前进程的 `FISH_PROTEUS_EXE`、`FISH_PROTEUS_LIBRARY`、`FISH_PROTEUS_SAMPLES`、`FISH_PROTEUS_TEMPLATE`。安装资源保持只读。保存校验来源身份，拒绝陈旧修改和隐式覆盖。[Python API](docs/GENERIC_API.md) 说明固件、自有 `Session` / `Simulation`、六类输入、CM3 日志及已有图表 CSV 接口。

## 可选：专用 headless 验收

以下启动参数只用于独立可复现实验，不是普通桌面使用的准备步骤。该专用部署中修改携带 `expected_revision`，输入由宿主登记，原生运行须明确启用 `run_sequence`；桌面工具自动管理这些内部参数。
禁用文件系统工具时，模型可通过只读 `help` 动作取得 actions、edits、steps、assertions 与 workflow 的精确合约。

显式 `stage` 可准备未经结构重建的工作副本，供受支持的原生或生成器操作使用；它不会让未知项目变成可重建的可编辑拓扑，`open` 失败也不能静默改走空白新建。

使用桌面版时，将 `DSH_DESKTOP_EXE` 设为已安装的可执行文件。若 `dsh` CLI 已在 `PATH` 中，可省略该设置：

```powershell
$env:DSH_DESKTOP_EXE = Read-Host 'DeepSeek Harness.exe 的完整路径（仅桌面版需要）'
& $FishPython tools/dsh_headless.py --probe
```

附带的自然语言任务要求模型从实际定义组合 STM32 输入跟随电路，再验证 SDF 和 PA0→PA5 响应。需要提供合法取得的本地 STM32F103R6 donor，以及编译后的原创示例 ELF：

```powershell
$DonorProject = Read-Host 'STM32F103R6 donor 工程的完整路径'
$FollowFirmware = Read-Host '编译后的 gpio-follow.elf 完整路径'
& $FishPython tools/dsh_headless.py `
  --workflow design `
  --provider deepseek-account `
  --credential-store "$env:USERPROFILE\.dsh\.credentials.yaml" `
  --input-project "donor=$DonorProject" `
  --input-firmware "follow=$FollowFirmware" `
  --output .work/dsh-design-session `
  --job-directory .work/dsh-design-job `
  --allowed-operations capabilities help library_search library_get create open inspect edit firmware_info run_sequence verify `
  --task-file tools/demo_task_generic.txt `
  --timeout 600
```

使用自有 Arm GNU 安装构建原创固件，可执行 `tools/build_stm32_demo.py --toolchain <toolchain-root> --output <new-directory>`，源码见 [`examples/stm32_gpio_follow/`](examples/stm32_gpio_follow/)。任务给出行为要求，没有直接交付完整成品电路。文件阶段完成 17 次请求/四项断言；取得该次具体外发授权后，运行续段完成 19 次请求并核验原生 SDF、固件、实际时间和 GPIO 010。两阶段复用受管项目，并非同一 DSH 会话。最终七项混合断言全过，总状态为 `native_verified`；运行各项及单独计时验证保留其运行证据层级，失败记录见[验证说明](docs/VALIDATION.md)。
构建器默认使用本机构建已实测的 DWARF-2；ELF 容器有效不代表调试格式受 Proteus 装载器支持。

每次会话和任务使用新目录。宿主控制任务根目录、输入 ID、配置与操作白名单。模型不能通过设计工具提交 shell 命令、任意可执行文件路径或任意代码。精确参数见[工具合约](skills/fish-proteus817/references/generic-api.md)与[工作流规则](skills/fish-proteus817/references/workflows-and-evidence.md)。

凭据路径应指向你自己的已有存储。账号提供器使用 DSH 的正常登录流程，可能刷新该存储。API-key 路线使用 `--provider deepseek-official` 和进程环境中的 `DEEPSEEK_API_KEY`，两条提供器路线分别配置。凭据和原始会话保持私有。不识别启动器时使用 `--dsh-executable`，特殊布局可能还需要 `--tools-module`。启动器使用项目级 DSH home 和临时 profile 配置。

## 可选 8086 课程 recipes

旧 `fish_proteus` CLI/工具保留以下模板及参数变体；通用文件 API 无需这些课程材料：

| 场景 | 电路 | 要求示例 |
| --- | --- | --- |
| `divider` | 1 MHz 输入的单个 8253 计数器 | 使用除数 10，得到 100 kHz 输出。 |
| `cascade` | 两个 8253 计数器级联 | 产生 1 Hz 或 2 Hz 输出。 |
| `switch` | 8255、K0/PA0 输入和八个 LED | PA0=0 时输出 33h，PA0=1 时输出 CCh。 |

参考目录应包含：

```text
参考/
├── T8253_v1信号1MHz五分频/
├── T8253_v2两个CNT级联/
└── T8255_v1用K0控制LED全亮或全灭/
```

每组目录需要原始 `.pdsprj` 工程和 `main.asm`。导入器创建私有副本并记录哈希，后续任务另建工作副本。导入后仍需保留原始参考目录，供来源一致性检查使用。

准备项目内 NASM，并检查本机环境：

```powershell
& $FishPython tools/bootstrap_nasm.py
& $FishPython -m fish_proteus doctor
```

安装器下载固定版本的官方 NASM ZIP，校验 SHA-256 后放入 `.tools/nasm`，不更改系统 `PATH`。已有匹配 ZIP 时可使用 `--archive`。

输入你实际使用的课程参考目录：

```powershell
$CourseReference = Read-Host '课程参考目录的完整路径'
& $FishPython -m fish_proteus import-course `
  --source $CourseReference `
  --destination .local/course
```

### 手动复现 100 kHz 示例

在仓库根目录新建任务，逐步执行：

```powershell
& $FishPython -m fish_proteus prepare --library .local/course --case divider --divisor 10 --output .work/manual-100khz
& $FishPython -m fish_proteus build --manifest .work/manual-100khz/job.json
& $FishPython -m fish_proteus run --manifest .work/manual-100khz/job.json --seconds 0.05
& $FishPython -m fish_proteus verify --manifest .work/manual-100khz/job.json
```

每个变体使用新的任务目录；读取每步 JSON 和退出码后再继续。构建成功、软件打开、采到观测和验证为 `passed` 是分别记录的事实。

生成的 16 位 MZ 是由 Proteus 装载的 8086 固件。`doctor` 和 `run` 支持 `--proteus 'C:\path\to\BIN\PDS.EXE'` 指定其他安装位置。级联任务使用 `--divisor0`、`--divisor1`，8255 任务使用 `--on-value 0x33 --off-value 0xCC`；更多参数见 `& $FishPython -m fish_proteus prepare --help`。

### 在 DSH 中使用课程工具

课程启动器提供 `fish_proteus` 工具，支持 `doctor`、`prepare`、`build`、`run` 和 `verify` 五个操作。操作者固定课程库、一个任务目录及本次操作白名单；模型提交场景参数，工具不接受 shell 命令或任意路径。

旧启动器默认 `--workflow course`。使用已有 DSH account 登录，并为本次任务明确启用五个操作：

```powershell
& $FishPython tools/dsh_headless.py `
  --provider deepseek-account `
  --credential-store "$env:USERPROFILE\.dsh\.credentials.yaml" `
  --library .local/course `
  --output .work/dsh-100khz-session `
  --job-directory .work/dsh-100khz-job `
  --allowed-operations doctor prepare build run verify `
  --task-file tools/demo_task_100khz.txt `
  --timeout 300
```

示例任务要求 DSH 自行计算除数、加载 Skill、构建新程序、在 Proteus 中运行并报告实测及验证结果。后续任务使用新的会话和工程目录；后端调用沿用 `$FishPython` 所选解释器。

## 结果与观测

通用任务记录当前 revision 和带哈希的证据引用。文件、原生和运行断言属于不同证据层级：

| 通用状态 | 含义 |
| --- | --- |
| `prepared` | 已准备任务或工程输入。 |
| `file_verified` | 文件级检查接受了声明的结构。 |
| `native_verified` | 断言接受了实际原生结构证据。 |
| `runtime_observed` | 原生序列已取得实际输出。 |
| `runtime_verified` | 运行断言接受了新鲜且身份匹配的证据。 |
| `blocked` / `unsupported` / `failed` | 所需条件不可用、不支持或检查未匹配。 |

请求时长、初始化后的原生起止时间、经过时长、容差和超出量分别记录。输入位置不等于下游输出。CM3 日志事件是带原生时间戳的数字观测，不是模拟电压或当前仿真时钟；通用原始日志在自有会话正常关闭后完成收集，再与实际步骤时钟匹配。CSV 使用已有图表对象；`simulate=true` 清理并重算分析，同名轨迹使用 `occurrence`，采样拒绝越界外推。

每个课程任务保存源码、构建记录、`job.json`、运行报告、截图、OCR 与哈希。各次运行位于 `runtime/<run-id>/`；任务根目录 `runtime.json` 保存最新报告内容。`verify` 写出 `verification.json`，分别计算预期并检查实际观测。

| 课程状态 | 含义 |
| --- | --- |
| `built` | 已实际构建并检查新的 8086 程序。 |
| `runtime_observed` | 运行适配器已取得实际仿真输出。 |
| `passed` | 独立验证接受了记录的观测。 |
| `blocked` | 所需工具、观测或环境条件不可用。 |
| `failed` | 验证检查未满足判据。 |

计数器频率来自实际示波器轨迹、可见网格和界面时基。8255 分别观测 PA0 和 D0–D7 **LED 显示**，核对实际原生接线图，并在同一次仿真中检查切换与恢复；这**不是 PB 寄存器直接读数**。

课程 `--seconds` 是原生计时请求。可选时钟 OCR 无法可靠读出或验证时，保留 `actual_time_verified: false`、`simulation_seconds: null`。功能验证仍须有足够的真实波形或 LED 观测。

## 测试与验证

离线测试无需 Proteus 或私有课程文件：

```powershell
& $FishPython -B -m unittest discover -s tests -v
```

可选的静态检查会跳过已审阅的 Proteus 上游源码：

```powershell
& $FishPython -m pip install -e ".[dev]"
& $FishPython -m ruff check .
```

使用自己的导入模板执行串行桌面验收：

```powershell
& $FishPython tools/acceptance.py --library .local/course --output .work/acceptance --runtime --repeat 3
```

使用本机安装执行通用文件层验收：

```powershell
& $FishPython tools/generic_structure_acceptance.py --output .work/structure-check
```

随后可在交互桌面上单独核对原生队列：

```powershell
& $FishPython tools/generic_native_acceptance.py --queue .work/structure-check/acceptance.json --output .work/native-structure-check
```

第二条命令会启动 Proteus。`file_verified` 本身不代表原生或仿真通过。实际证据与未测扩展见[验证说明](docs/VALIDATION.md)；[发行状态](docs/RELEASE_STATUS.md)区分已完成的 0.2.0 验收与新发行包。
开发期间，本机 16 项结构检查已通过；0.2.0 最终 wheel 随后完成了单独的隔离安装原生验收。
13 个结构候选、ADI 续编、反向导线和六类 GPIO 检查通过，U1/U2 标题遮挡已修正并原生/目视复核，原始诊断保留。源码套件 166 项（跳过 13），另有 11 项本地检查；早期干净候选 161 项（显式跳过 16），官方 Skill 与 12 项 vendor 校验通过。早期候选与 0.2.0 最终 wheel 分别完成隔离安装验证；最终包已验证原生结构、五绑定下 SW1 GPIO/备用控件幂等、reset 停止及新 CSV，restart 与五路同时 GPIO 未测。真实 DSH 续段的时间/GPIO与清理已独立核验，软件退出或模型总结本身不作通过依据；每次发行仍绑定实际包身份。

历史 0.1.0 基线记录了 **70 项本机离线测试、8 个课程仿真场景和真实课程 DSH 全流程**；0.1.1 完善公开发行。这些记录不代表 0.2.0 通用能力验收或跨机器/构建兼容。CI 在 Windows 和 Linux 上执行离线检查，不启动 Proteus，也不登录 DSH。

最终适配器另经九次请求的真实 DSH 续段复核，七项断言首试通过，原生时钟为 0.3025 秒。超 JavaScript 安全范围的身份整数以原十进制字符串传输；完整 stdout 字节与哈希仅留本地，精度修复没有改变原生PID校验或验证判据。

## 项目结构

Python 包放在仓库根目录，便于可编辑安装、JSON 命令行和 DeepSeek Harness 直接导入 `fish_proteus` 与 `runtime_adaptation`。Agent Skill 路径固定为 [`skills/fish-proteus817/SKILL.md`](skills/fish-proteus817/SKILL.md)。移动这些目录前，必须同时更新桌面安装器、公开白名单和测试。

```text
.
├── fish_proteus/                 # Python 包与 fish-proteus 命令行
│   └── _vendor/proteus_auto/     # 已审阅的 MIT 格式/运行适配
├── runtime_adaptation/           # Windows 上的 Proteus 8.17 会话适配
├── skills/fish-proteus817/       # Agent Skill 入口与参考
├── tools/                        # DSH 安装器、headless 启动器和验收脚本
├── examples/stm32_gpio_follow/   # 原创 PA0 到 PA5 固件源码
├── tests/                        # 离线 unittest（不需要 Proteus）
└── docs/                         # API、验证、设计说明与发行状态
```

`tools/public_release.py` 把 `PUBLIC_MANIFEST.json` 写到导出目录。该清单是生成物，不是源码。

## 限制与声明

本项目是非官方的实验性 Alpha 工具，与 Labcenter Electronics 和 DeepSeek 没有隶属关系，也不是 Proteus 产品。

- 原生会话需要你自行取得的 Proteus **8.17 SP2**，以及可交互的 Windows 桌面。Linux 与 CI 只运行离线测试。
- 保存文件、打开窗口和通过行为断言是不同结果。不支持的格式、PCB 布局，以及新建图表或探针，都不在本实现范围内。
- 发行内容不包含 Proteus、器件库、官方样例、课程工程、编译器或编译后的固件。MIT 许可覆盖本项目原创代码和文档；上游说明见[第三方说明](THIRD_PARTY_NOTICES.md)。

## 文档与许可

| 文档 | 内容 |
| --- | --- |
| [发行状态](docs/RELEASE_STATUS.md) | 当前 0.3.0 桌面证据、此前基线与逐包检查。 |
| [Python API](docs/GENERIC_API.md) | 配置、电路、原生会话、固件与测量。 |
| [类型化工具 API](skills/fish-proteus817/references/generic-api.md) | 领域操作、revision、原生步骤与断言。 |
| [架构](docs/design/ARCHITECTURE.md) / [规范](docs/design/DESIGN_STANDARD.md) / [路线](docs/design/ROADMAP.md) | 设计来源、规则与 G01–G14 完成门槛。 |
| [Skill 格式](docs/SKILL_FORMAT.md) | 规范依据、目录结构和后端依赖。 |
| [开发维护](docs/DEVELOPMENT.md) | 源码边界、证据规则与维护流程。 |
| [验证说明](docs/VALIDATION.md) | 已记录本机验证及其边界。 |
| [贡献指南](CONTRIBUTING.md) | 开发、检查与贡献流程。 |
| [安全说明](SECURITY.md) | 问题反馈与私有材料处理。 |
| [第三方说明](THIRD_PARTY_NOTICES.md) | 上游归属及分发边界。 |
| [版本记录](CHANGELOG.md) | 版本变化。 |
| [发行说明](PUBLICATION.md) | 干净源码导出、哈希及历史边界。 |

项目原创代码和公开文档使用 [MIT 许可证](LICENSE)，另附[中文参考译文](LICENSE.zh-CN.md)。Proteus、模型、课程工程、账号凭据和私有会话记录需另行取得，不包含在公开发行中。
