# SE Inspect 1.0.0-alpha.2 — release notes

*2026-10-03 · second public alpha · licence PolyForm Noncommercial 1.0.0 (`LICENSE`, commercial use: `COMMERCIAL.md`)*

Two things in this alpha: the operator interface was reorganised around the way people actually work, and SE Inspect can now be wired into a machine. Everything below runs in simulation without hardware and is benched in CI; the hardware paths for digital I/O and Modbus are **untested on real I/O** — reports welcome.

## New: guided workflow

- The sidebar is the workflow: **① Setup → ② Teach → ③ Inspect**, each step ticks itself off. A "next step" card leads on; **First steps** is a six-point assistant that opens once on a fresh cell.
- **One primary button per page** (INSPECT / Take photo / Record empty image), everything else in the "⋯" menu. Line and arm buttons only appear in line mode; a running line stays stoppable everywhere.
- **One settings window** (gear): General · Camera · Recognition · Jobs · I/O · PLC/Modbus · Users | Hardware · Diagnostics · Maintenance.
- **Jobs** (formerly "recipes") bundle the setup per product; the old "save setting" is part of it.
- **Teach**: objects as cards with photo progress and status light, "Background" instead of "nothing / foreign part", **Train …** opens the training dialog. Photo delete with **Undo**.
- **Inspect**: verdict card marked **Live preview**, counters below as **Logged inspections**. Keyboard help with "?".

## New: fits into a machine

- **Digital I/O** (`vorsa/eaio.py`): input *trigger*, outputs *ready / OK / NOK / fault*, pulse or hold. Drivers: **simulation** (default), **GPIO** via gpiozero (optocoupler/relay modules), **Modbus TCP I/O module**. Without the hardware a driver falls back to simulation and says why. GPIO 18 (belt relay) and 0–3 are blocked. New inspection trigger **External**.
- **PLC interface** (`vorsa/sps.py`): SE Inspect as a **Modbus TCP server** — status bits, verdict, object, confidence, counters, job number, heartbeat, result sequence; commands inspect / reset counters / load job. Off by default, port 1502, optional read-only.
- **User roles** (`vorsa/rollen.py`): operator / setter / admin with PIN (hashed), enforced in the server, automatic sign-out, change log. Off until an admin PIN is set.

## Configure your cell

[spikingedge.com/configure](https://spikingedge.com/configure/) turns six answers into a parts list with test status, rules of thumb for camera and light, a wiring sketch, guide chapters and the configuration files (`start.local.sh`, `eaio.json`, `sps.json`, `pruef.json`) for this release.

## Known limitations

- Alpha: interfaces, file layouts and the `vorsa_daten/` format may change between alphas without migration.
- Digital I/O, the Modbus I/O-module driver and the PLC interface are benched against a mocked gpiozero and an in-process Modbus peer — **not yet on real I/O hardware**. Modbus has no authentication: isolated machine networks only.
- Recognition rates on a real test set are **not yet published** (Q1–Q10 in `SE_INSPECT_1_0_SPEC.md`); the test-set tool is in the software.
- The trained SE-M3 detector is not included; live recognition runs geometrically (OpenCV) plus on-chip silhouette matching.
- Tested on Pi 5 8 GB with 1 and 4 cards and Camera Module 3. Nothing in this software is a safety function (`SAFETY.md`).

## Upgrading from alpha.1

Pull, then `sudo systemctl restart vorsa`. Learned objects and settings in `vorsa_daten/` stay. Roles, I/O and Modbus are off until you switch them on.

## Changes

`CHANGELOG.md` lists every build 1.9.56 → 1.0.0-alpha.2; each has a reproducible patch script in `tools/patch_19xx_*.py`.

---

# SE Inspect 1.0.0-alpha.1 — release notes (previous)

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
