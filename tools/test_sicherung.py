#!/usr/bin/env python3
"""Bench I4 (1.9.63): Komplettsicherung.

  python3 tools/test_sicherung.py            # Modul (Temp-Ordner)
  python3 tools/test_sicherung.py --server   # zusaetzlich: eigener synthetischer Server,
                                              # herunterladen, pruefen, einspielen, Neustart-Code
"""
import io, json, os, subprocess, sys, tempfile, time, urllib.request, zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from vorsa.sicherung import einspielen, erstellen, pruefen  # noqa: E402

FEHLER = []


def ok(b, t):
    print(("ok   " if b else "FEHL ") + t)
    if not b:
        FEHLER.append(t)


# ---------------------------------------------------------------- Modul
basis = Path(tempfile.mkdtemp())
a = basis / "vorsa_daten"
(a / "prototypen" / "0").mkdir(parents=True)
(a / "klassen.json").write_text('{"klassen":[1]}')
(a / "prototypen" / "0" / "f.png").write_bytes(b"\x89PNG" + bytes(range(256)) * 10)
(a / "eaio.json").write_text('{"treiber":"sim"}')
(a / "alt.json.vor-20260101").write_text("weg")
roh, name = erstellen(a, "TEST", "stationaer")
z = zipfile.ZipFile(io.BytesIO(roh))
ok("manifest.json" in z.namelist() and "vorsa_daten/klassen.json" in z.namelist(), "ZIP mit Manifest und Daten: " + name)
ok(not any(".vor-" in n for n in z.namelist()), "*.vor-* Sicherungsreste nicht enthalten")
p = pruefen(roh)
ok(p["ok"] and p["manifest"]["dateien"] == 3 and p["manifest"]["build"] == "TEST", "pruefen: gueltig, 3 Dateien")
ok(not pruefen(b"kein zip")["ok"], "keine ZIP -> abgelehnt")
buf = io.BytesIO()
with zipfile.ZipFile(buf, "w") as zz:
    zz.writestr("manifest.json", json.dumps({"art": "se-inspect-sicherung", "pruefsummen": {}}))
    zz.writestr("vorsa_daten/../../etc/x", "boese")
ok("unzulaessiger Pfad" in pruefen(buf.getvalue()).get("grund", ""), "Pfad mit .. abgelehnt")
kaputt = bytearray(roh)
buf = io.BytesIO()
with zipfile.ZipFile(io.BytesIO(roh)) as q, zipfile.ZipFile(buf, "w") as zz:
    for n in q.namelist():
        zz.writestr(n, q.read(n) if n != "vorsa_daten/klassen.json" else b'{"klassen":[2]}')
ok("beschaedigt" in pruefen(buf.getvalue()).get("grund", ""), "veraenderte Datei -> Pruefsumme schlaegt an")
# Einspielen in einen anderen Stand
b = basis / "zweite" / "vorsa_daten"
b.mkdir(parents=True)
(b / "klassen.json").write_text('{"klassen":["anders"]}')
(b / "nur_hier.txt").write_text("x")
e = einspielen(b, roh, "TEST")
ok(e["ok"] and e["neustart"], "einspielen ok")
ok(json.loads((b / "klassen.json").read_text()) == {"klassen": [1]} and (b / "prototypen" / "0" / "f.png").exists(), "Inhalt ersetzt")
ok(not (b / "nur_hier.txt").exists(), "alte Dateien weg (ersetzt, nicht gemischt)")
vor = basis / "zweite" / "vorsa_sicherungen"
ok(any(x.name.startswith("vor-einspielen-") for x in vor.iterdir()), "alter Stand vorher gesichert")
alt = next(vor.iterdir()).read_bytes()
ok("vorsa_daten/nur_hier.txt" in zipfile.ZipFile(io.BytesIO(alt)).namelist(), "Vorher-Sicherung enthaelt den alten Stand")

# ---------------------------------------------------------------- Server
if "--server" in sys.argv:
    d = Path(tempfile.mkdtemp()) / "vorsa_daten"
    env = dict(os.environ, VORSA_SYNTH_HALTEN_S="30")
    srv = subprocess.Popen([sys.executable, "tools/run_web.py", "--port", "8791", "--synthetisch", "--daten", str(d)],
                           cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    B = "http://127.0.0.1:8791"
    try:
        for _ in range(40):
            try:
                urllib.request.urlopen(B + "/api/state", timeout=1); break
            except Exception:
                time.sleep(0.5)
        q = urllib.request.Request(B + "/api/klasse_neu", data=json.dumps({"name": "Sicherungstest"}).encode(), headers={"content-type": "application/json"})
        urllib.request.urlopen(q, timeout=5)
        q = urllib.request.Request(B + "/api/sicherung", data=b"{}", headers={"content-type": "application/json"})
        r = urllib.request.urlopen(q, timeout=20)
        zroh = r.read()
        ok(r.headers.get("Content-Type") == "application/zip" and "attachment" in r.headers.get("Content-Disposition", ""), "Server: ZIP-Download")
        ok("Sicherungstest" in zipfile.ZipFile(io.BytesIO(zroh)).read("vorsa_daten/klassen.json").decode(), "Server: neues Objekt in der Sicherung")
        q = urllib.request.Request(B + "/api/sicherung_pruefen", data=zroh, headers={"content-type": "application/zip"})
        ok(json.loads(urllib.request.urlopen(q, timeout=20).read())["ok"], "Server: pruefen ok")
        q = urllib.request.Request(B + "/api/sicherung_einspielen", data=b"Unsinn", headers={"content-type": "application/zip"})
        ok(not json.loads(urllib.request.urlopen(q, timeout=20).read())["ok"] and srv.poll() is None, "Server: Unsinn abgewiesen, laeuft weiter")
        q = urllib.request.Request(B + "/api/sicherung_einspielen", data=zroh, headers={"content-type": "application/zip"})
        ok(json.loads(urllib.request.urlopen(q, timeout=20).read())["ok"], "Server: einspielen ok")
        code = srv.wait(timeout=10)
        ok(code == 1, f"Server beendet sich mit Code 1 (systemd startet neu): {code}")
    finally:
        if srv.poll() is None:
            srv.kill()

print("FEHLER: " + " | ".join(FEHLER) if FEHLER else "SICHERUNG_OK")
sys.exit(1 if FEHLER else 0)
