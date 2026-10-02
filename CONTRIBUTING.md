# Contributing

Thank you for looking at this. The project is small, concrete and measured; contributions should keep it that way.

## What helps most

1. **Reproductions.** Run a demo or bench on your hardware and report the exact output (command, output, Pi/OS/kernel/MetaTF versions, card firmware). A reproduction that *fails* is as valuable as one that passes.
2. **Test scenes.** Scenes with known truth for the test set (see Inspection → Test set in the UI, and `tools/eval_testsatz.py`).
3. **Bug reports with a bench.** If you can turn a failure into a small script under `tools/test_*.py` that goes red, it will be fixed.
4. **Translations and documentation.** The UI dictionary lives in `vorsa/web/static/sprache_en.js`; untranslated strings appear in `window.I18N_FEHLEND` in the browser console.

## Ground rules

- Every claim in a pull request about accuracy, speed or stability comes with the command that shows it. "Works for me" is a report, not a result.
- One topic per pull request. Keep patches to the operator UI (`vorsa/web/static/index.html`) small and describe what the user sees differently.
- No vendor code, no model weights, no customer images in the repository.
- German or English are both fine in commit messages and issues; code comments are German today and will stay consistent per file.

## Licence of contributions — DCO + CLA

The project is published under the PolyForm Noncommercial License 1.0.0 and is licensed commercially by the maintainer (see `COMMERCIAL.md`). So that both remain possible, every contribution needs two things:

**1. Developer Certificate of Origin (DCO).** Sign every commit with `git commit -s`, which adds `Signed-off-by: Name <email>`. By doing so you certify the [DCO 1.1](https://developercertificate.org/): the contribution is your own work (or you have the right to submit it) and you submit it under the project's licence.

**2. Contributor Licence Agreement (CLA), once.** With your first pull request, add a line to `CONTRIBUTORS.md`:

```
<Name> <email> — I grant Andreas Thurmayr a perpetual, worldwide, non-exclusive, royalty-free licence to use, modify, sublicense and distribute my contributions to this project under any licence, including commercial licences, and I confirm that I have the right to grant this.
```

That sentence is the whole CLA. It lets the project stay free for everyone non-commercial *and* be licensed to companies without asking every contributor again. You keep the copyright on your contribution.

Pull requests without DCO sign-off or without the CLA line cannot be merged — not out of formality, but because otherwise the project could not keep its licence promise.

## How to run the benches

```
pip install "numpy<2" opencv-python-headless
python3 tools/test_farbmaske.py && python3 tools/test_glanz.py && python3 tools/test_linie_fluss.py \
 && python3 tools/test_karten_waechter.py && python3 tools/test_m3_head.py && python3 tools/test_mehrbild.py \
 && python3 tools/test_hypothesen.py && python3 tools/test_verteiler.py && python3 tools/test_stationaer.py \
 && python3 tools/run_selftest.py --use-background --out /tmp/selftest
```

All of them run without a card. The UI smokes need Node ≥ 18 and `npm install jsdom@24`, then `python3 tools/run_web.py --port 8765 --synthetisch --daten /tmp/vd &` and `node tools/smoke_stationaer.js http://127.0.0.1:8765`.
