# iOS dla Galaxy A51 (SM-A515F, Exynos 9611)

Port jądra XNU (generacja iOS 16, `xnu-8796.141.3` = macOS 13.5) na Samsunga
Galaxy A51. Baza: sprawdzone porty [wardevsa/ios-a5xelte](https://github.com/wardevsa/ios-a5xelte)
(Galaxy A5 2016 / Exynos 7580) i jego linia `herolte` (Galaxy S7 / Exynos 8890 —
tam iOS 16.7.16 userland iPhone X wchodzi na home screen z GPU, WiFi, BT,
dźwiękiem, dotykiem i przyciskami).

**Jądro buduje GitHub Actions na runnerze `macos-15-intel` (Xcode 15) — bez
Hackintosha.** KDK 13.5 pobierane z publicznego CDN
[dortania/KdkSupportPkg](https://github.com/dortania/KdkSupportPkg) (bez Apple ID).

## Status

| Etap | Stan |
|---|---|
| UEFI boot chain (edk2, S-Boot → UEFI → XnuLoaderA51) | gotowe (repo `edk2-a51`, `boot-a51-ios-v1.img`) |
| Konfiguracja maszyny A51 w XNU (`MACHINE_CONFIG=A51`) | patch `xnu/patches/0400-a51-machine-config.patch` |
| Pierwszy build kernela w CI | **w toku** |
| Sterowniki podstawy (dotyk, power/volume, WiFi, dźwięk) | planowane (wzorce Sweet* + facty ze stock DTB) |
| iOS rootfs (partycja `userdata`) | planowane (repo `ios-root-build`) |

## Jak działa CI

Workflow [`.github/workflows/xnu.yml`](.github/workflows/xnu.yml):

1. Klonuje [blacktop/darwin-xnu-build](https://github.com/blacktop/darwin-xnu-build) (pinned commit),
   który sam pobiera xnu `xnu-8796.141.3` z apple-oss-distributions i KDK 13.5 z dortania.
2. Kopiuje `xnu/patches/*` do `dxb/patches/` — najpierw uruchamiane są skrypty
   `*.sh` (staging libpthread/BearSSL/HFS), potem `*.patch` wg numeracji
   (`0001…0345` = seria a5xelte/herolte, `0400…` = patche A51); niestosowalne
   patche są pomijane z ostrzeżeniem (np. `0030-sweet-ufs-writes`).
3. Buduje `TARGET_CONFIGS=DEVELOPMENT ARM64 A51` — wynik:
   `dxb/fakeroot/System/Library/Kernels/kernel.development.a51`.
4. Skanuje kernel pod kątem instrukcji LSE (A51 to ARMv8.0 — Cortex-A53/A73,
   bez ARMv8.1 atomics) i pakuję drzewo builda do artifactów.

Ręczne uruchomienie: **Actions → xnu → Run workflow** (opcje: `kernel_config`,
`machine_config`, `keep_going` = `make -k`, żeby jedno uruchomienie zebrało
wszystkie błędy kompilacji).

## ⚠️ Prywatne repo = płatne minuty

Na **prywatnym** repo runner macOS liczy się z mnożnikiem **10×** (rachunek
minut quota). Na **publicznym** repo minuty macOS są **darmowe**.
`Settings → Danger Zone → Change visibility`. Workflow ma limit `timeout-minutes: 120`.

## Struktura

- `xnu/patches/` — seria patchy na xnu-8796.141.3 (`0001–0345` upstream
  a5xelte/herolte, `0400+` = A51),
- `shim/`, `gpu/`, `apps/`, `tools/`, `docs/` — boot shim, sterowniki GPU,
  aplikacje iOS, narzędzia, dokumentacja upstream (README a5xelte:
  `docs/upstream-readme-a5xelte-herolte.md`),
- `AGENTS.md`, `NOTES.md` — notatki i konwencje.

## Uruchamianie na urządzeniu

iOS startuje z partycji **userdata** (label GPT `userdata` w stock GPT A51).
Boot chain: S-Boot (BOOT partitions) → UEFI (`boot-a51-ios-v1.img` z osadzonym
XnuLoaderA51) → XNU z ADT wygenerowanym ze stock DTB (`tools/mkadt_a51.py`, TODO).
