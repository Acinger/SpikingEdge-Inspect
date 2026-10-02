#!/usr/bin/env python3
"""A8 — CPU-Ersatz fuer das Chip-Lernen ohne Karte (Build 1.9.44).

edge_learn.py laedt vorsa.akida_cpu, wenn MetaTF fehlt UND VORSA_CPU_LERNEN=1;
run_web.py setzt das beim synthetischen Start automatisch. Die Oberflaeche
sagt "CPU-Ersatz". server.py: Build.
"""
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
E = ROOT / "vorsa" / "edge_learn.py"; R = ROOT / "tools" / "run_web.py"; S = ROOT / "vorsa" / "web" / "server.py"
def ers(t, a, n, k=1):
    if t.count(a) != k: raise SystemExit(f"FEHLER: {t.count(a)}x statt {k}x: {a[:120]}")
    return t.replace(a, n)
el = E.read_text(encoding="utf-8")
if "CPU_ERSATZ" in el:
    print("edge_learn.py: schon gepatcht")
else:
    el = ers(el, '''try:
    import akida
    AKIDA_DA = True
except Exception:                      # pragma: no cover
    akida = None
    AKIDA_DA = False
''', '''try:
    import akida
    AKIDA_DA = True
except Exception:                      # pragma: no cover
    akida = None
    AKIDA_DA = False
# CPU-ERSATZ (SE Inspect A8, 1.9.44): ohne MetaTF und nur auf Wunsch
# (VORSA_CPU_LERNEN=1, beim synthetischen Start automatisch) rechnet der
# Silhouetten-Abgleich in numpy. Gleiche Zahlen wie auf dem Chip, keine
# Aussage ueber Hardware - die Oberflaeche sagt "CPU-Ersatz".
CPU_ERSATZ = False
if not AKIDA_DA:
    import os as _os
    if _os.environ.get("VORSA_CPU_LERNEN", "") == "1":
        try:
            from . import akida_cpu as akida      # type: ignore
            AKIDA_DA = True
            CPU_ERSATZ = True
        except Exception:                  # pragma: no cover
            akida = None
''')
    el = ers(el, '''        if not AKIDA_DA:
            return False, ("MetaTF nicht importierbar - Umgebung aktivieren: "
                           "source ~/akida-env/bin/activate")
        try:
            g = akida.devices()''', '''        if not AKIDA_DA:
            return False, ("MetaTF nicht importierbar - Umgebung aktivieren: "
                           "source ~/akida-env/bin/activate")
        if CPU_ERSATZ:
            return True, (f"CPU-Ersatz ({len(akida.devices())} simulierte Karten) - "
                          "Silhouetten-Abgleich in Software, nur zum Ausprobieren")
        try:
            g = akida.devices()''')
    E.write_text(el, encoding="utf-8"); print("edge_learn.py gepatcht")
rw = R.read_text(encoding="utf-8")
if "VORSA_CPU_LERNEN" in rw:
    print("run_web.py: schon gepatcht")
else:
    rw = ers(rw, '''from vorsa.web.server import starte      # noqa: E402
''', '''# CPU-Ersatz fuers Chip-Lernen beim synthetischen Start (A8): muss VOR dem
# Import des Servers feststehen, weil edge_learn beim Import entscheidet.
import os as _os
if "--synthetisch" in sys.argv and "VORSA_CPU_LERNEN" not in _os.environ:
    try:
        import akida  # noqa: F401  (echte Karte vorhanden? dann kein Ersatz)
    except Exception:
        _os.environ["VORSA_CPU_LERNEN"] = "1"
from vorsa.web.server import starte      # noqa: E402
''')
    R.write_text(rw, encoding="utf-8"); print("run_web.py gepatcht")
s = S.read_text(encoding="utf-8")
if "1.9.44-cpu" not in s:
    s = ers(s, 'BUILD = "1.9.43-lernfenster"', 'BUILD = "1.9.44-cpu-ersatz"'); S.write_text(s, encoding="utf-8"); print("server.py gepatcht")
