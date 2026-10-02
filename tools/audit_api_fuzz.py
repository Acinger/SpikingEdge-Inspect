#!/usr/bin/env python3
"""Audit: jede /api/*-Route mit leeren, falsch typisierten und kaputten
Koerpern aufrufen. Erwartung: Antwort (JSON oder Bytes), nie 500 durch eine
unbehandelte Ausnahme, Server lebt danach noch.

  python3 tools/audit_api_fuzz.py http://127.0.0.1:8765
"""
import json, re, sys, urllib.request, urllib.error
from pathlib import Path

BASIS = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8765"
SRC = (Path(__file__).resolve().parent.parent / "vorsa" / "web" / "server.py").read_text(encoding="utf-8")
ROUTEN = sorted(set(re.findall(r'weg == "(/api/[a-z_0-9]+)"', SRC)))
# gefaehrliche oder blockierende Routen auslassen
AUS = {"/api/lernen", "/api/lernen_sofort", "/api/kernziel_start", "/api/messung_start", "/api/m3_start",
       "/api/vergessen", "/api/karte_reset", "/api/kamera_neu", "/api/klasse_loeschen", "/api/leerbild",
       "/api/ereignisse_leeren", "/api/pruef_reset", "/api/preset_loeschen", "/api/rezept_loeschen",
       "/api/prototyp_loeschen", "/api/zaehler_zuruecksetzen", "/api/lauf_abbrechen", "/api/arm"}
KOERPER = [None, b"", b"{}", b"[]", b"null", b'{"x": 1}', b'{"art": 123, "klasse": "a", "id": -1, "name": 5, "fenster": "x", "takt": 9, "aktiv": "ja", "soll": 1, "tat": "nix", "nr": "q", "datei": "../../etc/passwd", "ausloeser": 1, "mehrbild": "viele", "schwelle": "hoch"}',
           b"{bad json", b'"string"', b"\xff\xfe\x00"]


def ruf(weg, body, methode):
    req = urllib.request.Request(BASIS + weg, data=body, method=methode,
                                 headers={"Content-Type": "application/json"} if body is not None else {})
    try:
        with urllib.request.urlopen(req, timeout=15) as a:
            return a.status, a.read()[:120]
    except urllib.error.HTTPError as e:
        return e.code, e.read()[:120]
    except Exception as e:
        return -1, str(e).encode()


def main():
    print(f"{len(ROUTEN)} Routen im Server, {len(ROUTEN - AUS) if isinstance(ROUTEN, set) else len([r for r in ROUTEN if r not in AUS])} werden gefuzzt")
    schlecht = []
    n = 0
    for weg in ROUTEN:
        if weg in AUS:
            continue
        for methode in ("POST", "GET"):
            for body in (KOERPER if methode == "POST" else [None]):
                code, text = ruf(weg, body, methode)
                n += 1
                if code == -1 or code >= 500:
                    schlecht.append((weg, methode, body, code, text[:80]))
    # unbekannte Pfade / Traversal
    for weg in ["/api/gibtsnicht", "/static/../server.py", "/static/x.js", "/karte.png", "/api/pruef_bild?datei=../../etc/passwd",
                "/api/testsatz_bild?datei=..%2F..%2Fetc%2Fpasswd", "/api/prototyp?datei=../../etc/passwd"]:
        code, text = ruf(weg, None, "GET")
        n += 1
        if code == -1 or code >= 500 or (b"root:" in text):
            schlecht.append((weg, "GET", None, code, text[:80]))
    # lebt der Server noch?
    req = urllib.request.Request(BASIS + "/api/state")
    with urllib.request.urlopen(req, timeout=15) as a:
        lebt = a.status == 200 and b'"profil"' in a.read()
    print(f"{n} Aufrufe, {len(schlecht)} Befunde, Server lebt: {lebt}")
    for s in schlecht:
        print("  ", s)
    print("API_FUZZ_OK" if not schlecht and lebt else "API_FUZZ_FEHLER")
    return 0 if (not schlecht and lebt) else 1


if __name__ == "__main__":
    sys.exit(main())
