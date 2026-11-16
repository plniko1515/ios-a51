#!/usr/bin/env python3
"""Build the a51 (SM-A515F, Exynos 9611) ADT for the A51 XNU config.

Derived from mkadt_herolte.py. Facts: stock BOOT DTB (GIC 0x12301000/0x12302000,
UFSHCI 0x13520000, timer 26 MHz, INTID 27), mainline exynos9611 dtsi (A73
MPIDR 0x0..0x3, A53 MPIDR 0x100..0x103) and the verified-live UEFI chain facts
(Exynos9611Pkg/Platform: framebuffer 0xCA000000 1080x2400 BGRA, bootshim FD at
0x90000000). Storage is the Exynos 9611 UFS (/a51-ufs); iOS rootfs lives on the
GPT "userdata" partition. No touch/GPU nodes yet: the Sweet drivers target the
donors' hardware; the A51 bring-up (melfas mms_ts@48 on i2c@13870000) follows.
"""
import argparse
import os
from pathlib import Path

import adt
import mkadt

# XNU RAM window in bank 1 (0x80000000..0xbfffffff). Stock reservations here:
# sec_debug_magic 0x80000000+0x1000 and the bootshim FD loaded by S-Boot at
# 0x90000000 (verified chain); seclog sits at 0xc0000000. The window starts
# after the magic page and ends below the FD.
DRAM_BASE = 0x82000000
DRAM_SIZE = 0x0e000000     # 224 MiB, ends at 0x90000000
# --bank2: the second DRAM bank (stock DTB banks 0x80000000+1GiB and
# 0x880000000+2GiB; 6GiB variants add 0x900000000). Clean bank, no fixed
# reservations; needs the bank-aware loader like herolte's.
BANK2_BASE, BANK2_SIZE = 0x880000000, 0x80000000
SOC_BASE = 0x10000000       # arm-io ranges base; child regs are relative
# Framebuffer VERIFIED LIVE on this device (UEFI bring-up painter + DECON SW
# trigger): S-Boot lights the panel and scans out from 0xCA000000.
FB_BASE, FB_WIDTH, FB_HEIGHT = 0xCA000000, 1080, 2400

# Exynos 9611 GIC-400: distributor 0x12301000, CPU interface 0x12302000
# (stock DTB interrupt-controller@12300000, reg 0x12301000/0x12302000/...).
GICD, GICC = 0x12301000, 0x12302000
# Exynos 9611 UFSHCI (stock DTB 13520000.ufs): standard HCI at +0, vendor
# HCI +0x100, UNIPRO +0x1000, UFS protector +0x2000. Absolute address for the
# kernel-side driver (a51_ufs, patch 0402+; root = GPT "userdata").
UFS_BASE = 0x13520000


def set_prop(node, name, value):
    for i, (key, flags, _) in enumerate(node.props):
        if key == name:
            node.props[i] = (key, flags, value)
            return
    node.props.append((name, 0, value))


def add_haptics(root):
    """/product/haptics as the iPhone X's DeviceTree.d22ap has it (16.7.16): with
    closed-loop, MobileGestalt's DeviceSupportsClosedLoopHaptics, Darwin plays its
    vibrations and feedbacks as waveforms on the audio plug-in's "Actuator"
    (gpu/hakios-audio), whose samples go to the motor (/dev/hakios-haptic).
    Without it Darwin looks for an IOKit vibrator the iPhone X has not and stays
    still. Idempotent."""
    product = child(root, 'product')
    if any(c.prop('name') == mkadt.cstr('haptics') for c in product.children):
        return
    def phandles(n):
        yield int.from_bytes(n.prop('AAPL,phandle') or b'\0\0\0\0', 'little')
        for c in n.children:
            yield from phandles(c)
    handle = max(phandles(root)) + 1
    product.children.append(mkadt.node('haptics', [
        ('AAPL,phandle', mkadt.u32(handle)),
        ('closed-loop', mkadt.u32(1)),
        ('supports-3rd-party-haptics', mkadt.u32(1)),
    ]))


def add_bluetooth_isp(root):
    """From the Note FE port (its mkadt_gracerlte.py, 0435/0458): the iPhone X's Bluetooth node
    (D22AP /arm-io/uart1/bluetooth's properties, bluetooth,n88), directly under /arm-io so the platform
    expert makes it a nub (bluetoothd: "no bluetooth service in device tree" without it; boot-0344bt:
    bluetoothd exited 0 again and again), and the S9 ports' camera node /arm-io/isp, where MobileGestalt
    looks for cameras (no compatible, no device_type: no driver matches it). Idempotent."""
    arm_io = child(root, 'arm-io')
    names = {c.prop('name') for c in arm_io.children}
    if mkadt.cstr('bluetooth') not in names:
        arm_io.children.append(mkadt.node('bluetooth', [
            ('device_type', mkadt.cstr('bluetooth')),
            ('compatible', mkadt.cstr('bluetooth,n88')),
            ('transport-speed', mkadt.u32(3000000)),
            ('transport-encoding', mkadt.u32(3)),
            ('vendor-id', mkadt.u32(0x05ac)),
            ('product-id', mkadt.u32(0x12a0)),
            ('coex', mkadt.u32(2)),
            ('local-mac-address', bytes((0x02, 0x41, 0x35, 0x31, 0x35, 0x02))),
        ]))
    if mkadt.cstr('isp') not in names:
        arm_io.children.append(mkadt.node('isp', [
            ('camera-rear', mkadt.u32(1)),
            ('camera-front', mkadt.u32(1)),
        ]))


def child(node, name):
    for candidate in node.children:
        if candidate.prop('name') == mkadt.cstr(name):
            return candidate
    raise ValueError(f'missing donor ADT node {name}')


def build(canvas=(FB_WIDTH, FB_HEIGHT), dram=(DRAM_BASE, DRAM_SIZE), scale=3):
    root = mkadt.build(seed=os.urandom(64), qemu=True)
    if scale == 2:
        # --scale2: a whole iPhone XR screen, 414x896 points at @2x (828x1792).
        # UIKit picks the status bar layout by native pixel width and notch; any
        # other @2x size gets the red rdar:45025538 bar. The kernel scales it to
        # the panel (sweetfb_scale=1 sweetfb_lw=828 sweetfb_lh=1792 sweetfb_gpu=1).
        set_prop(child(root, 'chosen'), 'display-scale', mkadt.u32(2))
        product = child(root, 'product')
        set_prop(product, 'artwork-device-subtype', mkadt.u32(1792))
        set_prop(product, 'artwork-scale-factor', mkadt.u32(2))
        canvas = (828, 1792)
    # The userland is the iPhone X IPSW (iPhone10,3 / D22AP), like the donor.
    # 'samsung,a5xelte' keeps the shared SweetPlatformExpert IONameMatch.
    set_prop(root, 'compatible', mkadt.cstr('D22AP') + mkadt.cstr('iPhone10,3') +
             mkadt.cstr('samsung,a5xelte') + mkadt.cstr('samsung,a51') +
             mkadt.cstr('samsung,exynos9611') + mkadt.cstr('AppleARM'))
    chosen = child(root, 'chosen')
    set_prop(chosen, 'dram-base', mkadt.u64(dram[0]))
    set_prop(chosen, 'dram-size', mkadt.u64(dram[1]))
    set_prop(chosen, 'firmware-version', mkadt.cstr('a51-entry'))
    set_prop(chosen, 'system-firmware-version', mkadt.cstr('a51-entry'))
    # MobileGestalt derives the UDID from these; without them it waits for a
    # Bluetooth/Wi-Fi driver forever, and LaunchServices never finishes seeding
    # the app database (SpringBoard stays on the boot logo). Synthetic,
    # locally administered addresses, not the phone's.
    for name, last in (('wifi0', 1), ('bluetooth0', 2), ('ethernet0', 3)):
        set_prop(chosen, f'mac-address-{name}', bytes((0x02, 0x41, 0x35, 0x31, 0x35, last)))
    # An sRGB screen, not the iPhone X's P3: with "P3" WebKit and PosterBoard
    # draw into 10-bit surfaces, which CoreAnimation over our renderer never
    # shows (see herolte boot-0317).
    set_prop(child(root, 'product'), 'artwork-display-gamut', mkadt.cstr('sRGB'))
    add_haptics(root)
    add_bluetooth_isp(root)
    cpus = child(root, 'cpus')
    cpu0 = child(cpus, 'cpu0')
    # Stock A51 DTB (DEVICE-VERIFIED): /cpus/cpu@100..103 are Cortex-A53 with
    # reg <0x0 0x0..0x3>, /cpus/cpu@0..3 are Cortex-A73 with reg <0x0 0x100..0x103>.
    # The stock kernel logs "Booting Linux on physical CPU 0x0" with
    # cpu0 mips=230 (A53 1.7 GHz) and cpu4 mips=480 (A73 2.3 GHz): S-Boot hands
    # off on an A53 at MPIDR 0x0. Getting this backwards makes XNU's
    # ml_get_cpu_number(MPIDR) return -1 -> assertion at machine_routines.c:1244.
    set_prop(cpu0, 'compatible', mkadt.cstr('arm,cortex-a53') + mkadt.cstr('ARM,v8'))
    set_prop(cpu0, 'reg', mkadt.u32(0x0))
    set_prop(cpu0, 'timebase-frequency', mkadt.u32(26000000))
    for logical in range(1, 8):
        big = logical >= 4
        core = logical - 4 if big else logical
        cpus.children.append(mkadt.node(f'cpu{logical}', [
            ('device_type', mkadt.cstr('cpu')),
            # SweetCPU matches IONameMatch 'arm,cortex-a53' (KernelConfigTables);
            # the A73s keep their own compatible (no driver matches them).
            ('compatible', (mkadt.cstr('arm,cortex-a73') if big else b'') +
                           mkadt.cstr('arm,cortex-a53') + mkadt.cstr('ARM,v8')),
            # device-verified MPIDRs: A53 cluster at Aff1=0 (0x0..0x3),
            # A73 cluster at Aff1=1 (0x100..0x103). cpu0 is 'running' above.
            ('reg', mkadt.u32(0x100 | core if big else core)),
            ('cpu-id', mkadt.u32(logical)),
            ('cluster-id', mkadt.u32(0)),
            ('cluster-type', mkadt.u32(0)),
            ('die-cluster-id', mkadt.u32(0)),
            ('cluster-core-id', mkadt.u32(logical)),
            ('l2-cache-id', mkadt.u32(1 if big else 0)),
            ('l3-cache-id', mkadt.u32(0)),
            ('state', mkadt.cstr('stopped')),
            ('timebase-frequency', mkadt.u32(26000000)),
            ('clock-frequency', mkadt.u32(2300000000 if big else 1700000000)),
            ('bus-frequency', mkadt.u32(100000000)),
            ('memory-frequency', mkadt.u32(1794000000)),
            ('peripheral-frequency', mkadt.u32(26000000)),
            ('fixed-frequency', mkadt.u32(26000000)),
        ]))
    arm_io = child(root, 'arm-io')
    set_prop(arm_io, 'device_type', mkadt.cstr('a51-io'))
    set_prop(arm_io, 'compatible', mkadt.cstr('samsung,exynos9611-io') +
             mkadt.cstr('arm-io'))
    set_prop(arm_io, 'ranges', mkadt.u64(0, SOC_BASE, 0xf0000000))
    arm_io.children = [n for n in arm_io.children if n.prop('name') == mkadt.cstr('wdt')]
    # GIC-400: distributor 0x12301000, CPU interface 0x12302000 (stock DTB).
    arm_io.children.append(mkadt.node('gic', [
        ('compatible', mkadt.cstr('arm,cortex-a15-gic')),
        ('interrupt-controller', mkadt.cstr('master')),
        ('virtual-timer-intid', mkadt.u32(27)),
        ('reg', mkadt.u64(GICD - SOC_BASE, 0x1000, GICC - SOC_BASE, 0x1000)),
    ]))
    arm_io.children.append(mkadt.node('disp0', [
        ('device_type', mkadt.cstr('display-subsystem')),
        # AppleCLCD (SweetFramebuffer.cpp) matches 'samsung,a5xelte-display'
        # in KernelConfigTables.cpp; without it SpringBoard sees no main display.
        ('compatible', mkadt.cstr('samsung,a5xelte-display') +
         mkadt.cstr('samsung,a51-display')),
        ('canvas-width', mkadt.u32(canvas[0])),
        ('canvas-height', mkadt.u32(canvas[1])),
    ]))
    # launchd starts com.apple.wifid only if the device tree has a node named
    # "wlan"; without wifid there is no Wi-Fi in Settings or the status bar.
    # A51's radio is a Broadcom core behind Samsung's SCSC block (stock DTB
    # scsc_wifibt@119c0000); the kernel-side driver is bring-up work.
    arm_io.children.append(mkadt.node('wlan', [
        ('device_type', mkadt.cstr('wlan')),
        ('compatible', mkadt.cstr('samsung,a51-wifi')),
    ]))
    root.children = [n for n in root.children if n.prop('name') not in
                     (mkadt.cstr('sweet-fbcon'), mkadt.cstr('sweet-ufs'))]
    # Exynos 9611 UFSHCI. Absolute address; the A51 UFS driver (a51_ufs,
    # patch 0402+) reads it and exposes the GPT "userdata" partition as root.
    root.children.append(mkadt.node('a51-ufs', [
        ('reg', mkadt.u64(UFS_BASE, 0x3000)),
    ]))
    # pe_serial.c looks this node up by name for the kprintf console
    # (A5XELTE builds search "a5xelte-fbcon"; keep the donor's node name).
    root.children.append(mkadt.node('a5xelte-fbcon', [
        ('reg', mkadt.u64(FB_BASE, FB_WIDTH * FB_HEIGHT * 4)),
        ('width', mkadt.u32(FB_WIDTH)),
        ('height', mkadt.u32(FB_HEIGHT)),
        ('stride', mkadt.u32(FB_WIDTH * 4)),
    ]))
    return root


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    parser.add_argument('--canvas', default=f'{FB_WIDTH}x{FB_HEIGHT}',
                        help='presented display WxH (default: full panel)')
    parser.add_argument('--scale2', action='store_true',
                        help='iPhone XR screen, 828x1792 @2x')
    parser.add_argument('--bank2', action='store_true',
                        help='XNU RAM = the second bank instead of the 224 MiB bank-1 window')
    parser.add_argument('--bank2-mb', type=int, default=BANK2_SIZE >> 20,
                        help='MiB of the second bank to use')
    args = parser.parse_args()
    canvas = tuple(int(v) for v in args.canvas.lower().split('x'))
    dram = (BANK2_BASE, min(args.bank2_mb << 20, BANK2_SIZE)) if args.bank2 else (DRAM_BASE, DRAM_SIZE)
    blob = adt.serialize(build(canvas, dram, 2 if args.scale2 else 3))
    args.output.write_bytes(blob)
    print(f'{args.output}: {len(blob)} bytes')
