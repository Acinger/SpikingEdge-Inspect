# SE Inspect

**A neuromorphic inspection cell you can build: Raspberry Pi 5 + BrainChip AKD1500 + one camera.**
Learns a new part on the chip in seconds, classifies by aligned silhouettes, measures geometry on the Pi, and says "unknown" instead of guessing. Every published number carries its date, build, firmware and method — see [spikingedge.com/evidence](https://spikingedge.com/evidence/).

*Project name history: the lab prototype is called VORSA INSPECT, its detector VORSA-M3. The code still uses `vorsa/` as package name; the product name is SE Inspect.*

| | |
|---|---|
| Licence | PolyForm Noncommercial 1.0.0 — free for non-commercial use, see `LICENSE`; commercial use: `COMMERCIAL.md` |
| Status | **alpha** — build `1.0.0-alpha.3` (the UI footer shows the running build). Release notes: `RELEASE_NOTES.md` |
| Hardware | Pi 5 (Bookworm 64-bit, kernel 6.12), 1–4 × AKD1500 M.2 on a Geekworm X1011 carrier (ASM1184e PCIe switch), Camera Module 3; belt and arm optional |
| Without hardware | the full UI with synthetic scenes and a CPU stand-in for the chip |
| Docs | [Guide (12 chapters)](https://spikingedge.com/guide/) · [Docs](https://spikingedge.com/docs/) · [Demos](https://spikingedge.com/demos/) · [Evidence](https://spikingedge.com/evidence/) |
| German README | `README.md` (original project notes, VORSA-M3 architecture) |

## Three ways in

**A. Five minutes, no hardware (laptop).**
```
git clone https://github.com/Acinger/SpikingEdge-Inspect.git && cd SpikingEdge-Inspect
bash install.sh --laptop
source ~/akida-env/bin/activate
python3 tools/run_web.py --synthetisch --port 8080
```
Open `http://localhost:8080`. The footer shows the build string; the hint line says *Chip-Lernen bereit: CPU-Ersatz* — learning and recognition run in software with the same numbers the chip would give, only slower and without any hardware claim. Create two objects, take six photos each (the synthetic table changes every few seconds), run on-chip learning, switch to Inspection and press **INSPECT** (or the space bar).

**B. Thirty minutes, one card (Pi 5).**
```
git clone https://github.com/Acinger/SpikingEdge-Inspect.git ~/vorsa-m3 && cd ~/vorsa-m3
bash install.sh
```
Packages, the patched Akida PCIe driver for kernel 6.12, the runtime environment, benches, and the systemd service. Then guide chapter 08.

**C. The full cell** — belt and arm (a second camera returns with `VORSA_ZWEITKAMERA=1`): guide chapters 01–12 and a `start.local.sh` next to `start.sh` with `export VORSA_PROFIL=linie`, `export VORSA_BAND=relais`, `export VORSA_ARM=uno` (machine-specific, not versioned). Read `SAFETY.md` first.

## What is in the box

| Path | What |
|---|---|
| `vorsa/web/server.py` | the server: camera, recognition loop, inspection log, alarms, line state machine, card watchdog, API |
| `vorsa/web/static/index.html` | the operator UI (German/English, three looks) |
| `vorsa/edge_learn.py` | on-chip learning: silhouettes → prototypes on the AKD1500, card ensemble (replicated or distributed), watchdog |
| `vorsa/segmentation.py`, `fitting.py`, `tracking.py`, `calibration.py` | the geometric reference pipeline on the Pi |
| `vorsa/hypothesen.py`, `vorsa/verteiler.py` | SE Inspect 1.0: hypotheses for touching/overlapping parts, card scheduler |
| `vorsa/mehrbild.py`, `vorsa/testsatz.py`, `vorsa/akida_cpu.py` | multi-frame capture, test set, CPU stand-in |
| `vorsa/model_m3.py`, `train_job.py`, `detektor.py` | VORSA-M3 detector (experimental, needs the training environment) |
| `vorsa/linie.py`, `arm_uno.py`, `arduino-sketch/` | belt, arm, firmware (line profile) |
| `tools/test_*.py`, `tools/run_selftest.py` | benches — all run without a card |
| `tools/eval_testsatz.py` | evaluates a recorded test set: hit rate, unknown rate, false-confident rate |
| `tools/patch_19xx_*.py` | every change since 1.9.37 as a reproducible patch script |
| `SE_INSPECT_1_0_SPEC.md` | the 1.0 specification: scope, quality targets, benches, work packages |
| `CHANGELOG.md` | what changed per build |

## Digital I/O (PLC, light barrier)

Settings › **I/O** maps five signals: input **Trigger** (rising edge starts an inspection when the inspection trigger is set to *External*), outputs **Ready**, **OK**, **NOK** (unknown, reject or no part) and **Fault** — pulse or hold. Three drivers, one configuration (`vorsa_daten/eaio.json`):

| Driver | Hardware | Notes |
|---|---|---|
| Simulation (default) | none | lamps and a test button per signal in the UI |
| GPIO | optocoupler/relay modules or GPIO relay HATs | `gpiozero` (lgpio on Pi 5); default pins BCM 17 in, 22/23/24/25 out; GPIO 18 (belt relay), 0–3 blocked |
| Modbus TCP | network I/O module | coils = outputs, discrete inputs = inputs; built-in client, no extra library |

Pi GPIO is 3.3 V only — 24 V signals go through optocouplers. None of this is a safety function (`SAFETY.md`). Bench: `python3 tools/test_eaio.py` (simulation, a mocked gpiozero and an in-process Modbus server). Without the hardware the driver falls back to simulation and shows why.

## PLC interface (Modbus TCP)

Off by default. Settings › **PLC / Modbus** (admin) starts a Modbus TCP server on port 1502 (optionally read-only). Input registers 0–12 (mirrored at holding registers 100+): status bits (ready, inspecting, fault, last OK, last NOK, simulated), verdict (1 good, 2 unknown, 3 reject, 4 empty), object ID + 1, confidence ‰, parts, 32-bit counter, good/unknown/reject, job no., heartbeat, **result sequence** (+1 per inspection). Commands: holding register 0 ← 1 inspect / 2 reset counters, holding register 1 ← job no., coil 0 ← inspect. Modbus has no authentication — enable it only on an isolated machine network. Bench: `python3 tools/test_sps.py`.

## User roles

Off by default (everything open). Setting an **admin PIN** under Settings › Users turns the UI into an operator station: without sign-in it can inspect, acknowledge, load jobs and start/stop the line. **Setter** (optional PIN) may set up and teach; **admin** also manages users and I/O. Enforced in the server, not only in the UI; every change is written to `vorsa_daten/aenderungen.jsonl` (time, role, action — never PINs). Forgot the admin PIN: delete `vorsa_daten/rollen.json` on the Pi.

## Benches

```
pip install "numpy<2" opencv-python-headless
for t in farbmaske glanz linie_fluss karten_waechter m3_head mehrbild hypothesen verteiler stationaer; do python3 tools/test_$t.py | tail -1; done
python3 tools/run_selftest.py --use-background --out /tmp/selftest | tail -3
```
Expected last lines: `FEHLER: 0`, `FLUSS_OK`, `WAECHTER_OK`, `GESAMT: OK`, `MEHRBILD_OK`, `HYPOTHESEN_OK`, `VERTEILER_OK`, `STATIONAER_OK`.

## Honest limits

Silhouette learning separates shapes, not colours or surface defects. Figures on the website are measured under our bench lighting; the test-set tool exists so that you can measure yours. The belt/arm profile is experimental. See `SAFETY.md` and the [Limitations](https://spikingedge.com/evidence/limitations/) page.

## Contributing and citing

`CONTRIBUTING.md` (DCO + a one-line CLA), `CITATION.cff`. Questions: hello@spikingedge.com.
