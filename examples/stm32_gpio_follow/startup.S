/* Original Cortex-M3 vector/start fixture. SPDX-License-Identifier: MIT */
.syntax unified
.cpu cortex-m3
.thumb
.section .isr_vector,"a",%progbits
.word _stack_top
.word Reset_Handler
.rept 14
.word Default_Handler
.endr

.section .text.Reset_Handler,"ax",%progbits
.global Reset_Handler
.type Reset_Handler,%function
.thumb_func
Reset_Handler:
    bl main
1:  b 1b
.size Reset_Handler, .-Reset_Handler

.section .text.Default_Handler,"ax",%progbits
.type Default_Handler,%function
.thumb_func
Default_Handler:
    b Default_Handler
.size Default_Handler, .-Default_Handler
