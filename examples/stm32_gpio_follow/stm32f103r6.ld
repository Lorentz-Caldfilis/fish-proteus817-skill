/* Original fixture, no initialized C data. SPDX-License-Identifier: MIT */
ENTRY(Reset_Handler)
MEMORY {
    FLASH (rx) : ORIGIN = 0x08000000, LENGTH = 32K
    RAM (rwx) : ORIGIN = 0x20000000, LENGTH = 10K
}
_stack_top = ORIGIN(RAM) + LENGTH(RAM);
SECTIONS {
    .text : { KEEP(*(.isr_vector)) *(.text*) *(.rodata*) } > FLASH
    .data : { *(.data*) } > RAM AT> FLASH
    .bss (NOLOAD) : { *(.bss*) *(COMMON) } > RAM
    ASSERT(SIZEOF(.data) == 0 && SIZEOF(.bss) == 0,
           "Fixture startup requires no initialized or zeroed globals")
    /DISCARD/ : { *(.comment) *(.note*) }
}
