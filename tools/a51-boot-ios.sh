#!/bin/sh
# Flash a ready XNU BOOT image to the A51, install the GPU/audio driver
# package into the drop zone, and reboot. Run from the repo root with the
# phone in TWRP, /data UNMOUNTED (Mount menu). Host side only, no auto-root.
#
#   sh tools/a51-boot-ios.sh /path/to/a51-xnu-boot.img
#
# Needs: /tmp/opencode/a51-kernel-dl/a51.payload (kernel + ADT) and the
# drop-zone sources under /home/niko/Pobrane/M (the public mesa-ios
# artifact from the ios-a5xelte project). The iOS rootfs is the 20 GiB
# HFSX image already written to userdata by tools/a51-flash-ios.py.
set -eu
BOOT_IMG=${1:?usage: a51-boot-ios.sh BOOT.img}
[ "$(adb devices | awk 'NR>1 && $2=="recovery"{n++} END{print n+0}')" -ge 1 ] || {
    echo "phone must be in TWRP (recovery) via adb" >&2; exit 1;
}

# 1. BOOT: shim + SWEETXNU payload (kernel + ADT with rd=ufsroot0 cmdline).
python3 tools/a51-flash-ios.py adb "$BOOT_IMG" --boot

# 2. Drop zone: Mesa/EAGL GPU, audio, helper, settings.
#    Kept off the repo: the dylibs are build artifacts (public mesa-ios
#    workflow), never commit them. Adapt the source paths if yours differ.
M=/home/niko/Pobrane/M
D=/home/niko/Dokumenty/ios-a5xelte/drop
python3 tools/a51-drop.py adb \
  autorun="$M/hero-run" \
  gl.env="$D/gl.env" test.env="$D/test.env" \
  disabled.list="$D/disabled.list" wallpaper.off="$D/wallpaper.off" \
  gestures.off="$D/gestures.off" \
  lib/libdrm.2.dylib="$M/lib/libdrm.2.dylib" \
  lib/libOSMesa.8.dylib="$M/lib/libOSMesa.8.dylib" \
  lib/libheroeagl.dylib="$M/lib/libhakiosgl.dylib" \
  lib/libherosb.dylib="$M/lib/libherosb.dylib" \
  lib/libheroapp.dylib="$M/lib/libheroapp.dylib" \
  audio/HakiosAudio="$M/audio/HakiosAudio" \
  audio/Info.plist="$M/audio/Info.plist"

echo "BOOT + drop zone installed; rebooting into iOS"
adb reboot
