/* SPDX-License-Identifier: GPL-2.0-only */
#pragma once
#include <stdint.h>

/* S-Boot scanout buffer (VERIFIED LIVE on this device: the UEFI bring-up
 * painter wrote 0xCA000000 and the DECON SW trigger showed it; 1080x2400
 * BGRA8888, stride 4320). */
#define A51_FB_BASE 0xca000000UL
#define A51_FB_WIDTH 1080U
#define A51_FB_HEIGHT 2400U

/* Let CPU writes reach the panel (DECON SW trigger, command-mode panel),
 * returns the previous trigger state. */
uint32_t a51_fb_enable(void);
void a51_fb_text(unsigned row, const char *s);
void a51_fb_hex(unsigned row, const char *label, uint64_t value);
