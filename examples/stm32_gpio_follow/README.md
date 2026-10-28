# STM32 GPIO follower acceptance fixture

Original MIT source for STM32F103R6: PA0 is a digital input with pull-down;
PA5 is a 2 MHz push-pull output that follows PA0. It uses the reset HSI clock,
no interrupts, no HAL, and no external C library. The firmware writes outputs
only when their state changes, keeping native GPIO traces bounded.

The startup defines a Cortex-M3 vector table and 10 KiB RAM stack top. The
linker rejects globals requiring initialization. See ST's
[RM0008 reference manual](https://www.st.com/resource/en/reference_manual/cd00171190-stm32f101-103-105-107-stm32f100-series-armbased-32bit-mcus-stmicroelectronics.pdf)
for RCC/GPIO register semantics.

Build with a separately obtained Arm GNU toolchain using
`python tools/build_stm32_demo.py --toolchain <directory> --output <new-directory>`
from the repository root. The tool records source/compiler/output hashes. It
does not download a compiler, launch Proteus or prove runtime correctness.
Generated ELF/HEX files, installed models and native project copies remain local.

The builder defaults to DWARF 2 debug information; `--dwarf-version` can select
2, 4 or 5 for explicit compatibility comparisons. Debug format changes the ELF
identity even when the generated HEX code image is identical. Check actual
loader behavior on the target Proteus build before claiming ELF support.
