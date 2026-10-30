# CLI and Python

[Docs](README.md) · [Python API](GENERIC_API.md) · [Configuration](configuration.md)

A normal DeepSeek Harness chat does not use this page. The desktop tool calls the same backend. Use the commands when you want a job you can rerun, or when you are not in a chat.

The console script is `fish-proteus`. `python -m fish_proteus` is the same program. Both print JSON.

## Course commands

| Command | What it does |
| :-- | :-- |
| `doctor` | Read-only report of Proteus and NASM. `--proteus` overrides the executable |
| `import-course --source --destination` | Copy and hash the original course tree into a private library |
| `prepare --library --case --output` | Make one job from `divider`, `cascade`, or `switch` |
| `build --manifest` | Assemble a new 8086 MZ executable for that job |
| `run --manifest` | Load it into Proteus and observe. `--seconds` asks for a native interval, greater than 0 and at most 60 |
| `verify --manifest` | Compare the recorded observations with an expectation computed again |

`prepare` accepts `--divisor` for `divider`, `--divisor0` and `--divisor1` for `cascade`, and `--on-value`, `--off-value`, and `--invert` for `switch`. Values can be decimal or prefixed, as in `0x33`.

One divider, from the repository root, after [import](getting-started.md):

```powershell
python -m fish_proteus prepare --library .local/course --case divider --divisor 10 --output .work/manual-100khz
python -m fish_proteus build --manifest .work/manual-100khz/job.json
python -m fish_proteus run --manifest .work/manual-100khz/job.json --seconds 0.05
python -m fish_proteus verify --manifest .work/manual-100khz/job.json
```

Use a new output directory for the next variant. Read each command's JSON before the next one. A built executable is not a `passed` verify.

The MZ file is firmware for the simulated 8086. Do not run it as a Windows program.

## Python

`ProteusConfig`, `Library`, and `Circuit` are the file API. `Session` and `Simulation` are created only when you ask for a native run, and only on Windows.

```python
from fish_proteus.automation import Circuit, Library, ProteusConfig

config = ProteusConfig.discover()
library = Library(config=config)
print(library.search("RESISTOR", limit=10))

circuit = Circuit(config=config)
circuit.add("RESISTOR", "R1", "10k", 0, 0)
circuit.add("CAPACITOR", "C1", "100n", 5_080_000, 0)
circuit.connect("R1.2", "C1.1")
circuit.save(".work/new-filter.pdsprj")
```

That save does not mean the filter was simulated. Pick an unused destination. The rest of the calls, including firmware and graphs, are in the [Python API](GENERIC_API.md).

## Launchers you can ignore

`tools/dsh_headless.py` is for a reproducible experiment with an explicit allowlist of operations. A desktop chat does not need it. `--probe` checks that Harness can be started. The account provider uses `--credential-store`. The API-key provider is `--provider deepseek-official` plus `DEEPSEEK_API_KEY`.

`tools/build_stm32_demo.py --toolchain <root> --output <new-directory>` builds the GPIO follower from [`examples/stm32_gpio_follow/`](../examples/stm32_gpio_follow/) with your Arm GNU toolchain. The helper defaults to DWARF-2. An ELF container is not, by itself, proof the Proteus loader accepts it.

`tools/generic_structure_acceptance.py` and `tools/generic_native_acceptance.py` are local acceptance runs. The second one starts Proteus. `tools/acceptance.py` repeats the course jobs. Their records belong in [Validation](release/VALIDATION.md), not in a claim that every future run will match.

## 中文

平常在 Harness 里说话即可，不必敲这些命令。`fish-proteus` 面向可重复的课程任务：导入、准备、汇编、运行、独立验证。Python 的 `Circuit.save` 只说明文件写出去了。headless 启动器是专门做对照实验用的。
