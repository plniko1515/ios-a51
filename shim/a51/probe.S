/* SPDX-License-Identifier: GPL-2.0-only
 * Samsung a51 (SM-A515F, Exynos 9611) stage-0 handoff probe.
 * Diagnostic only: no storage, EFS, PMIC or MMU changes. It records the
 * S-Boot handoff on the firmware framebuffer, then requests TWRP through
 * the proven UEFI-chain PMU path: INFORM3 (0x1186080C) = SEC recovery
 * reason 0x12345674, then PMU SWRESET (+0x400) = 1 (exynos-reboot.c).
 *
 * The arm64 Image header fields text_offset/image_size/flags are rewritten
 * by tools/herolte-pack-boot.py from the stock kernel's header.
 */
.section .text.head, "ax"
.global _start
_start:
    b entry
    .long 0
    .quad 0x80000            /* text_offset: replaced by the packer */
    .quad 0                  /* image_size: replaced by the packer */
    .quad 0                  /* flags: replaced by the packer */
    .quad 0, 0, 0
    .byte 0x41, 0x52, 0x4d, 0x64
    .long 0

entry:
    msr daifset, #15
    mov x19, x0              /* FDT from S-Boot */
    mrs x20, CurrentEL
    mrs x21, sctlr_el1
    adr x22, _start
    adr x14, a51_probe_stack_top
    mov sp, x14
    mov x0, x19
    mov x1, x20
    mov x2, x21
    mov x3, x22
    bl a51_probe_main       /* returns only to request recovery */
    /* Exynos 9611 PMU 0x11860000: INFORM3 (recovery), SWRESET. */
    ldr x0, =0x11860000
    ldr w14, =0x12345674
    str w14, [x0, #0x80c]
    dsb sy
    mov w14, #1
    str w14, [x0, #0x400]
    dsb sy
halt:
    wfe
    b halt
    .ltorg

.section .data, "aw"
.balign 16
a51_probe_stack:
    .space 8192
a51_probe_stack_top:
