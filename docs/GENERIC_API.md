# Generic file and runtime API

For ordinary DSH desktop use, run the one-time desktop installer and use the
[desktop task/resource contract](../skills/fish-proteus817/references/desktop-workflow.md).
It manages session tasks, resource IDs and current revisions around this API;
the Python examples and specialized CLI below remain available independently.

The generic workflow composes real devices, pins and operations. The three 8086
course cases remain separate recipes. Runtime support requires a licensed local
Windows installation and a validated native build; a catalogue match alone
does not establish device import or simulation compatibility.

## Configuration and identity

`fish_proteus.config.ProteusConfig` is immutable. `discover()` checks explicit
arguments, `FISH_PROTEUS_EXE`, `FISH_PROTEUS_LIBRARY`, `FISH_PROTEUS_SAMPLES`,
`FISH_PROTEUS_TEMPLATE`, and the installed executable's `DATA` directory.
Resource discovery never launches an application or changes its configuration.
Pass separate configurations to use separate installations. Installed resources
are read-only inputs; saves beneath the installation or resource roots fail.

All `Circuit` positions and route points are **native integer coordinates**:
100000 units = 1 mm. Component rotations are multiples of 90 degrees, and
`mirror(axis)` accepts `x` or `y`. Enumerated pin positions use the same units.
Use logical pin names or unambiguous physical numbers obtained from `pins()`.

## Library and circuit

```python
from fish_proteus.automation import Circuit, Library, ProteusConfig

config = ProteusConfig.discover()
library = Library(config=config)
candidates = library.search("RESISTOR", limit=10)
definition = library.get("RESISTOR", library="ASIMMDLS")

circuit = Circuit(config=config)  # New blank sheet, not an existing-file edit.
circuit.add("RESISTOR", "R1", "10k", 0, 0)
circuit.add("CAPACITOR", "C1", "100n", 5080000, 0)
pins = circuit.pins("R1")
circuit.connect("R1.2", "C1.1")
circuit.save("output/new-filter.pdsprj")
```

`Circuit()` uses the user's installed RC sample as a format container, removes
its topology and graph cache, and strips its firmware project members. It does
not copy a complete predefined solution. Imported device definitions remain
local inputs and are not part of the open-source package.

| Operation | Signature and result |
| --- | --- |
| Open existing layout | `Circuit.open(path, config=config)`; refuses unrecognized objects, unsupported sheets or unsafe rebuilds |
| Import device | `import_device(name, library=None, donor_project=None)`; choose a library when duplicate device names exist |
| Inspect | `inspect()` includes components, pins, logical nets, connections, terminals, power rails, source SHA256 and revision |
| Add | `add(device, ref, value, x, y, rotation=0, mirror_x=False, mirror_y=False, properties=None)` |
| Edit | `update(ref, **changes)`, `set_properties(ref, **properties)`, `rename(ref, new_ref)` |
| Geometry | `move(ref, x, y)`, `rotate(ref, degrees=90)`, `mirror(ref, axis="x")` |
| Duplicate/delete | `copy_component(ref, new_ref, x, y)`, `delete_component(ref)` |
| Wires | `connect(first, second, points=None)`, `disconnect(first, second=None)`, `set_route(first, second, points)` |
| Wire labels | `add_wire_label(first, second, text, position=None)`, `remove_wire_label(first, second, text)`, `wire_labels()`; first endpoint owns new labels on branches; removal is scoped to that physical net |
| Terminals | `add_terminal(kind, name, pin=None, position=None, rotation=None)`, `update_terminal(id, **changes)`, `delete_terminal(id)` |
| Power | `configure_power(rails, bindings=None)`, `power_rails()` |
| Interactive bindings | `bind_controls(*refs)`; two of ten global key slots per binary input; validates all existing INC/DEC/KEY reservations |
| Save | `save(destination, title=None, overwrite=False)`; complete temporary archive validation before atomic publication |

Terminals support `label`, `input`, `output`, `bidir`, `power`, `ground`. Named
terminals and real wire labels participate in logical connectivity. Wiring is
conservative orthogonal routing with supported junction structures; this is
not an arbitrary obstacle router. Layout recognition is limited to single user
sheet CDB v7 projects with the explicitly supported metadata versions.

A power rail group and an actual net name are distinct. The official STM32
sample uses the group `VCC/VDD` with bindings from `VCC` and `VDD`; its terminals
must use a bound net such as `VCC`. A literal terminal named `VCC/VDD` creates
a separate net rather than selecting that group. Verify native aliases and
electrical behavior after editing power configuration.

The read-only `revision` changes with the source identity, topology, properties,
embedded definitions and persistent members, including power rails. DSH edits
must provide `expected_revision`. Every save checks the original source digest,
even when saving to another file. A source modified by native Proteus must be
reopened before further file editing. New outputs do not overwrite existing
files without an explicit flag.

## Native runtime and numerical evidence

`Session(project, executable=None, config=None)` and `Simulation(session)` are
lazy Windows factories exported by `fish_proteus.automation`. The runtime uses
only its owned process and exact build profile. File edits and an open native
session must be serialized. Changed control bindings require save and reopen.

The simulation API covers `status/start/pause/stop/reset/run_for`, `controls`,
`control_state`, `press/release/set_switch`, firmware assignment, native logs
and supported CM3 GPIO events. Precise time requests require the actual native
clock. Request duration, actual elapsed time, tolerance, overshoot and completion
reason remain separate fields. GPIO timestamps and graph axes are not the
current interactive clock.

`graphs(session)` and `export_graph(session, graph, destination, simulate=True)`
operate on existing graph/probe objects. Fresh evidence must clear old data and
run the analysis. `parse_graph_csv(text)` preserves duplicate trace names;
`sample_graph(data, trace, x, occurrence=0)` interpolates inside the exported
range and rejects extrapolation. Generator edits preserve unknown layout and
currently require values with the original byte width.

`firmware_info(path)` binds actual bytes to SHA256 and validates supported ELF
container bounds or Intel HEX record types/checksums. Other permitted firmware
containers report `format_verified=False`. Format validity does not prove CPU
compatibility or execution. `extract_firmware(project, destination, member)`
extracts only a chosen firmware image, never project build scripts.

Capability reporting separates implementation and test evidence. The acceptance
requirements and current progress are maintained in the
[roadmap](design/ROADMAP.md). See the skill's generic reference for the bounded
DSH task protocol; the Python API is intended for trusted local callers.

## 中文要点

通用接口按实际库、元件、引脚、连线、端子、电源、固件、仿真与测量组合；三个课程
例程只是配方。坐标明确为原生整数，100000单位为1毫米。新建和打开既有工程使用不同
入口，未知结构拒绝重写。保存原子提交并核对源文件身份，安装资料保持只读。

接口存在、文件校验、原生SDF、实际仿真和行为验证分别记录。精确计时读取原生时钟；
按钮机械状态不代表下游响应；图表必须重新计算，同名CSV列按occurrence区分。
最终能力以本机证据和[能力矩阵](design/ROADMAP.md)为准。
