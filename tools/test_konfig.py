#!/usr/bin/env python3
"""Bench: tools/konfig_anwenden.py (Link aus dem Website-Konfigurator -> Dateien).
  python3 tools/test_konfig.py
Laeuft in einem Temp-Ordner; der Projektordner bleibt unberuehrt."""
import json, os, subprocess, sys, tempfile
from pathlib import Path
HIER = Path(__file__).resolve().parent
FEHLER = []
def ok(b, t):
    print(("ok   " if b else "FEHL ") + t)
    if not b: FEHLER.append(t)
def lauf(link, ziel, *extra):
    env = dict(os.environ, VORSA_KONFIG_ZIEL=str(ziel))
    return subprocess.run([sys.executable, str(HIER / "konfig_anwenden.py"), link, *extra], env=env, capture_output=True, text=True)
z = Path(tempfile.mkdtemp())
r = lauf("https://spikingedge.com/configure/", z)
ok(r.returncode == 0 and "VORSA_PROFIL=stationaer" in (z / "start.local.sh").read_text(), "ohne Antworten: stationaer")
ok(not (z / "vorsa_daten" / "eaio.json").exists(), "ohne I/O: keine eaio.json")
r = lauf("https://spikingedge.com/configure/#aufbau=arm&io=opto&anzahl=viele", z)
sh = (z / "start.local.sh").read_text()
ok("VORSA_PROFIL=linie" in sh and "VORSA_BAND=relais" in sh and "VORSA_ARM=uno" in sh and "VORSA_EAIO=gpio" in sh, "Linie + Arm + GPIO")
e = json.loads((z / "vorsa_daten" / "eaio.json").read_text())
ok(e["treiber"] == "gpio" and e["pins"]["trigger"] == 17 and 18 not in e["pins"].values(), "eaio.json GPIO, Pin 18 frei")
ok(any(p.name.startswith("start.local.sh.vor-") for p in z.iterdir()), "alte start.local.sh gesichert")
ok(not (z / "vorsa_daten" / "pruef.json").exists(), "Linie: keine pruef.json")
(z / "vorsa_daten" / "pruef.json").write_text(json.dumps({"schwelle": 0.6, "ausloeser": "hand"}))
r = lauf("aufbau=stationaer&io=taster", z)
p = json.loads((z / "vorsa_daten" / "pruef.json").read_text())
ok(p == {"schwelle": 0.6, "ausloeser": "extern"}, "pruef.json zusammengefuehrt (Schwelle bleibt): " + str(p))
ok(json.loads((z / "vorsa_daten" / "eaio.json").read_text())["invertiert"]["trigger"] is True, "Taster: Trigger invertiert")
r = lauf("#io=modbus", z)
ok(json.loads((z / "vorsa_daten" / "sps.json").read_text())["an"] is True and "keine Anmeldung" in r.stdout, "Modbus-SPS: sps.json + Warnung")
z2 = Path(tempfile.mkdtemp())
r = lauf("aufbau=linie&io=modul", z2, "--zeigen")
ok(r.returncode == 0 and not (z2 / "start.local.sh").exists() and "192.0.2.10" in r.stdout, "--zeigen schreibt nichts")
r = lauf("aufbau=rakete", z2)
ok(r.returncode != 0 and "nicht gueltig" in (r.stdout + r.stderr), "ungueltiger Wert abgelehnt")
r = lauf("foo=1", z2)
ok(r.returncode != 0 and "Unbekannter Schluessel" in (r.stdout + r.stderr), "unbekannter Schluessel abgelehnt")
print("FEHLER: " + " | ".join(FEHLER) if FEHLER else "KONFIG_OK"); sys.exit(1 if FEHLER else 0)
