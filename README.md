# SE Inspect

**A neuromorphic inspection cell you can build: Raspberry Pi 5 + BrainChip AKD1500 + one camera.**
Learns a new part on the chip in seconds, classifies by aligned silhouettes, measures geometry on the Pi, and says "unknown" instead of guessing. Every published number carries its date, build, firmware and method — see [spikingedge.com/evidence](https://spikingedge.com/evidence/).

*Project name history: the lab prototype is called VORSA INSPECT, its detector VORSA-M3. The code still uses `vorsa/` as package name; the product name is SE Inspect.*

| | |
|---|---|
| Licence | PolyForm Noncommercial 1.0.0 — free for non-commercial use, see `LICENSE`; commercial use: `COMMERCIAL.md` |
| Status | **alpha** — build `1.0.0-alpha.1` (the UI footer shows the running build). Release notes: `RELEASE_NOTES.md` |
| Hardware | Pi 5 (Bookworm 64-bit, kernel 6.12), 1–4 × AKD1500 on PCIe, Camera Module 3; belt and arm optional |
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
