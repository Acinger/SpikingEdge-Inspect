# SE Inspect 1.0.0-alpha.1 — release notes

*2026-10-02 · first public alpha · licence PolyForm Noncommercial 1.0.0 (`LICENSE`, commercial use: `COMMERCIAL.md`)*

## What this is

A neuromorphic inspection cell for one camera: Raspberry Pi 5, one to four BrainChip AKD1500 cards, Camera Module 3. It learns a part on the chip from a handful of photos, recognises it by aligned silhouettes, measures geometry on the Pi and says **unknown** instead of guessing. The web UI is bilingual (German/English) and runs without any hardware in synthetic mode.

## What works in this alpha

- **Stationary profile** (default, `VORSA_PROFIL=stationaer`): inspection cell without belt or arm. Trigger by hand (button / space bar) or automatically when the scene settles; per-part inspection log; multi-frame averaging before segmentation.
- **Line profile** (`VORSA_PROFIL=linie`): belt via relay or L298N, Arduino stepper arm, delivery and pickup zones **from one camera**. A second camera, "view 2" fusion and per-camera learning zones are switched off in this release (`VORSA_ZWEITKAMERA=1` brings them back, untested here).
- **Recognition chain**: empty-image difference → geometry → hypotheses for overlapping parts (two rounds) → card distributor across 1–4 AKD1500 → verdict with confidence bars. CPU stand-in (`VORSA_CPU_LERNEN=1`, automatic in synthetic mode) gives the same numbers in software, slower, with no hardware claim.
- **Camera dock** under the image (image, colour, window, background), right-click menu for overlays, capture-window resize in the learning view, three looks (SpikingEdge, industrial, Magna).
- **Test-set tool**: record scenes with expected results, `tools/eval_testsatz.py` scores a build against them.
- **Benches without hardware** (`tools/test_*.py`, `tools/run_selftest.py`) and UI smokes (`tools/smoke_*.js`, jsdom) — run in CI on every push.
- **Installer** `install.sh` (Pi 5, Bookworm 64-bit, kernel 6.12, patched Akida PCIe driver) and `install.sh --laptop`.

## Known limitations (read before relying on it)

- Alpha: interfaces, file layouts and the `vorsa_daten/` format may change between alphas without migration.
- The published quality numbers (Q1–Q10 in `SE_INSPECT_1_0_SPEC.md`) are **not yet measured on a real bench test set**; what exists are synthetic benches and lab observations. Evidence pages on spikingedge.com label every figure with its provenance.
- Hypotheses for ring-shaped fragments reach ~80 % on the synthetic bench (target 75 %); real overlapping parts are untested at scale.
- The trained SE-M3 detector is not included; live recognition runs geometrically (OpenCV) plus on-chip silhouette matching.
- One Pi, one camera, tested on Pi 5 8 GB with 1 and 4 cards. Pi 4 and other cameras are untested.
- Safety: a belt and an arm are machinery. `SAFETY.md` is mandatory reading; nothing in this software is a safety function.
- `bereich_info` can show a partially updated state for one frame at low frame rates (B9 in `AUDIT_FREIGABE.md`), cosmetic.

## How to try it

See `README.md` — five minutes on a laptop without hardware, thirty minutes on a Pi 5 with one card.

## Reporting

Bugs and bench results: GitHub issues. Attach `install.log` and the build string from the UI footer. Contributions: `CONTRIBUTING.md` (DCO + one-line CLA).

## Changes since the lab prototype (VORSA INSPECT 1.9.37)

`CHANGELOG.md` lists every build 1.9.38 → 1.0.0-alpha.1; each one has a reproducible patch script in `tools/patch_19xx_*.py`.
