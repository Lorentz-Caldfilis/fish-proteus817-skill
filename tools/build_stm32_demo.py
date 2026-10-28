"""Build the original fixed STM32 acceptance fixture with a supplied compiler."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from fish_proteus.firmware import firmware_info


def build(toolchain: Path, output: Path, *, dwarf_version=2) -> dict:
    if dwarf_version not in (2, 4, 5):
        raise ValueError("Supported debug formats: DWARF 2, 4 or 5")
    toolchain, output = toolchain.resolve(strict=True), output.resolve()
    if output.exists():
        raise FileExistsError(output)
    suffix = ".exe" if os.name == "nt" else ""
    compiler = toolchain / "bin" / ("arm-none-eabi-gcc" + suffix)
    objcopy = toolchain / "bin" / ("arm-none-eabi-objcopy" + suffix)
    if not compiler.is_file() or not objcopy.is_file():
        raise FileNotFoundError("Arm GNU compiler and objcopy are required")
    source = ROOT / "examples" / "stm32_gpio_follow"
    sources = [source / "main.c", source / "startup.S", source / "stm32f103r6.ld"]
    source_hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
    output.mkdir(parents=True)
    elf, hexfile = output / "gpio-follow.elf", output / "gpio-follow.hex"
    command = [str(compiler), "-mcpu=cortex-m3", "-mthumb", "-ffreestanding", "-fno-builtin",
               "-nostdlib", "-Os", "-g3", f"-gdwarf-{dwarf_version}", "-Wall", "-Wextra", "-Werror", "-Wl,--build-id=none",
               "-Wl,-Map=" + str(output / "gpio-follow.map"), "-T", str(sources[2]),
               str(sources[1]), str(sources[0]), "-o", str(elf)]
    completed = subprocess.run(command, capture_output=True, text=True, timeout=60)
    if completed.returncode:
        raise RuntimeError("Firmware build failed: " + completed.stdout + completed.stderr)
    subprocess.run([str(objcopy), "-O", "ihex", str(elf), str(hexfile)], check=True,
                   capture_output=True, text=True, timeout=30)
    result = {"status": "built", "runtime_verified": False, "debug_format": f"DWARF-{dwarf_version}", "source_sha256": source_hashes,
              "compiler": {"path": str(compiler), "sha256": hashlib.sha256(compiler.read_bytes()).hexdigest(),
                           "version": subprocess.run([str(compiler), "--version"], capture_output=True,
                                                     text=True, check=True, timeout=10).stdout.splitlines()[0]},
              "command": command, "elf": firmware_info(elf), "hex": firmware_info(hexfile),
              "input": "PA0", "output": "PA5"}
    (output / "build.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--toolchain", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--dwarf-version", type=int, choices=(2, 4, 5), default=2)
    args = parser.parse_args()
    print(json.dumps(build(args.toolchain, args.output, dwarf_version=args.dwarf_version), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    main()
