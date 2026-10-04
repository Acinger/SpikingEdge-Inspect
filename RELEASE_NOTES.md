# SE Inspect 1.0.0-alpha.3 — release notes

*2026-10-04 · third public alpha · licence PolyForm Noncommercial 1.0.0 (`LICENSE`, commercial use: `COMMERCIAL.md`)*

This alpha is about the cell learning from its own operation and about measuring instead of guessing. Everything below was exercised on a Pi 5 with four AKD1500 M.2 modules against a real 48-scene test set (SD card, Allen key, foreign parts, empty table) — which is also where most of the fixes in this release come from.

## New: the cell learns from operation (1.1-A)

- Parts that were **unknown** during inspection land in the inspection archive. **Teach › Suggestions from operation** groups them by shape and colour and shows each group with thumbnails: *As new object*, *To object …*, *Background* or *Discard* — then **Train …**. A slider sets the grouping finer or coarser.
- Also reachable from the "Re-teach recommended" card in Inspect.

## New: threshold from the test set (1.1-B)

- **Settings › Recognition › Threshold from the test set** runs every test-set scene through recognition and shows, for thresholds 30–95 %, hits, foreign parts detected, known parts reported as unknown and the false-confident rate. The suggestion is the threshold with the most hits at ≤ 1 % false-confident; if no threshold achieves that, it is marked as a **compromise** with a note on what actually helps.
- **Calibration per object**: each object reaches a different confidence when recognised correctly (on the bench: SD card ~0.6, Allen key ~0.9). The test run measures this and rescales so that a typical hit sits at 90 % for every object — one threshold then fits all. Shown in the settings, discardable, marked as outdated after a new training.
- The test set now has a **Foreign part** chip (expected: unknown) and is visible in both profiles under Inspect › Details; "Open test set" jumps there.

## New: statistics and trend (1.1-C)

- A persistent inspection journal (`pruefjournal.jsonl`) survives restarts. **Inspect › Trend**: today's numbers, stacked bars for the last 24 hours, a 14-day table, and a **drift warning** ("confidence dropping") when the mean confidence of the last 50 named parts falls ≥ 8 points below the first 50 after training.

## Fixed

- **M3 training looked stuck at "Isolating photos 0 %"**: it was isolating every photo in all 32 augmentation variants (3 872 passes on 687-px images, no progress). Rotation variants were useless for M3 (scene synthesis rotates anyway). Now original + mirror only, images capped at 384 px, progress per photo, and an **overall progress bar** across all phases with percent and colour (blue running, green done, red failed).
- **Test run measured a different chain than live**: test scenes were 687-px crops, so the empty image was rejected by a shape check and empty scenes produced phantom parts. The empty image is now cropped to the capture window and scaled to the scene. The test run also measures strictly raw (calibration locked) and refuses mode switches while it runs.
- **Empty image vs. rotation**: the empty image remembers the rotation it was taken at; if the image has been rotated since, it is not used and Setup/Inspect say so.
- **Image rotation** survives a restart (`drehung.json`); rotate button in the zoom bar (locked during Inspect).
- Two UI elements that jumped on every state refresh (Teach-zones button, First steps) are quiet now.

## Known limitations

- Alpha: interfaces, file layouts and the `vorsa_daten/` format may change between alphas without migration.
- Silhouette matching cannot separate foreign parts with the same outline as a taught object (bench: a dark plastic chip vs. an SD card). Teaching such parts as *Background* is the only remedy in this release.
- Digital I/O, the Modbus I/O-module driver and the PLC interface remain **untested on real I/O hardware**. Modbus has no authentication: isolated machine networks only.
- The M3 training chain (TensorFlow → cnn2snn → AKD1500) has not yet been run end-to-end on the bench since the speed-up; report what you see.
- Nothing in this software is a safety function (`SAFETY.md`).

## Upgrading from alpha.2

Pull, then `sudo systemctl restart vorsa`. Learned objects and settings in `vorsa_daten/` stay. New files: `pruefjournal.jsonl`, `kalibrierung.json`, `drehung.json`, `vorschlaege_erledigt.json` — all optional. `install.sh --config "<link from spikingedge.com/configure>"` writes the configuration files for a fresh cell.

## Changes

`CHANGELOG.md` lists every build 1.9.63 → 1.0.0-alpha.3; each has a reproducible patch script in `tools/patch_19xx_*.py`. New benches: `test_selbstlernen`, `test_trend`, `test_kalibrierung`, `test_m3_fortschritt`, `test_1_1_server`; new UI smokes: `smoke_elf`, `smoke_drehen`, `smoke_ruhig`, `smoke_laufbalken`.

---

# SE Inspect 1.0.0-alpha.2 — release notes (previous)

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
