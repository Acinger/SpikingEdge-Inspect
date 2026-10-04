#!/usr/bin/env python3
"""Konfiguration aus dem Website-Konfigurator auf diesen Rechner anwenden.

  python3 tools/konfig_anwenden.py "https://spikingedge.com/configure/#aufbau=linie&io=opto"
  python3 tools/konfig_anwenden.py "aufbau=linie&io=opto"          # nur der Teil hinter #
  python3 tools/konfig_anwenden.py "<link>" --zeigen              # nur anzeigen, nichts schreiben
  bash install.sh --config "<link>"                                # dasselbe im Installer

Schreibt dieselben Dateien wie spikingedge.com/configure/ (Abschnitt "Configuration
for the Pi"): start.local.sh im Projektordner, eaio.json / sps.json / pruef.json in
vorsa_daten/. Vorhandene Dateien werden vorher als *.vor-<Zeit> gesichert; pruef.json
wird zusammengefuehrt (nur der Ausloeser wird gesetzt), nicht ersetzt.
Fragen ohne Einfluss auf die Dateien (Teilegroesse, Oberflaeche, Takt, Karten) werden
akzeptiert und nur angezeigt.
"""
import argparse, json, os, shutil, sys, time
from pathlib import Path
from urllib.parse import parse_qsl, urlparse

# VORSA_KONFIG_ZIEL: anderer Projektordner (Tests)
ROOT = Path(os.environ.get("VORSA_KONFIG_ZIEL") or Path(__file__).resolve().parent.parent)
GUELTIG = {
    "aufbau": {"stationaer", "linie", "arm"},
    "groesse": {"klein", "mittel", "gross"},
    "oberflaeche": {"matt", "glanz"},
    "anzahl": {"eins", "wenige", "viele"},
    "takt": {"ruhig", "sekunde", "schnell"},
    "io": {"keine", "taster", "opto", "modul", "modbus"},
    "karten": {"auto", "1", "2", "3", "4"},
    "form": {"auto", "pcie", "m2"},
}
STD = {"aufbau": "stationaer", "groesse": "mittel", "oberflaeche": "matt", "anzahl": "eins",
       "takt": "ruhig", "io": "keine", "karten": "auto", "form": "auto"}


def lesen(text: str) -> dict:
    text = text.strip()
    if "#" in text:
        text = text.split("#", 1)[1]
    elif text.startswith("http"):
        text = urlparse(text).fragment
    s = dict(STD)
    for k, v in parse_qsl(text, keep_blank_values=False):
        if k not in GUELTIG:
            raise SystemExit(f"Unbekannter Schluessel {k!r} - Link aus spikingedge.com/configure/ kopieren.")
        if v not in GUELTIG[k]:
            raise SystemExit(f"{k}={v!r} ist nicht gueltig (erlaubt: {', '.join(sorted(GUELTIG[k]))}).")
        s[k] = v
    return s


def dateien(s: dict, link: str) -> list:
    """Muss zu dateien() in site/assets/konfigurator-*.js passen."""
    profil = "stationaer" if s["aufbau"] == "stationaer" else "linie"
    sh = ["# SE Inspect — configuration from spikingedge.com/configure/", "# " + link, f"export VORSA_PROFIL={profil}"]
    if s["aufbau"] != "stationaer":
        sh.append("export VORSA_BAND=relais")
    if s["aufbau"] == "arm":
        sh.append("export VORSA_ARM=uno")
    if s["io"] in ("taster", "opto"):
        sh.append("export VORSA_EAIO=gpio")
    if s["io"] == "modul":
        sh.append("export VORSA_EAIO=modbus")
    out = [("start.local.sh", ROOT / "start.local.sh", "\n".join(sh) + "\n", "ersetzen")]
    if s["io"] in ("taster", "opto", "modul"):
        e = {"treiber": "modbus" if s["io"] == "modul" else "gpio", "modus": "puls", "puls_ms": 200, "entprell_ms": 20,
             "pins": {"trigger": 17, "bereit": 22, "ok": 23, "nok": 24, "fehler": 25},
             "invertiert": {"trigger": s["io"] == "taster", "bereit": False, "ok": False, "nok": False, "fehler": False}}
        if s["io"] == "modul":
            e["modbus"] = {"host": "192.0.2.10", "port": 502, "einheit": 1,
                           "adressen": {"trigger": 0, "bereit": 0, "ok": 1, "nok": 2, "fehler": 3}, "zyklus_ms": 20}
        out.append(("eaio.json", ROOT / "vorsa_daten" / "eaio.json", json.dumps(e, indent=1) + "\n", "ersetzen"))
    if s["io"] == "modbus":
        out.append(("sps.json", ROOT / "vorsa_daten" / "sps.json", json.dumps({"an": True, "port": 1502, "nur_lesen": False}, separators=(",", ":")) + "\n", "ersetzen"))
    if s["aufbau"] == "stationaer" and s["io"] not in ("keine", "modbus"):
        out.append(("pruef.json", ROOT / "vorsa_daten" / "pruef.json", json.dumps({"ausloeser": "extern"}, separators=(",", ":")) + "\n", "zusammenfuehren"))
    return out


def anwenden(s: dict, link: str, zeigen: bool) -> int:
    print("Konfiguration:", ", ".join(f"{k}={v}" for k, v in s.items()))
    stempel = time.strftime("%Y%m%d-%H%M%S")
    for name, ziel, text, art in dateien(s, link):
        if art == "zusammenfuehren" and ziel.exists():
            try:
                alt = json.loads(ziel.read_text(encoding="utf-8"))
            except Exception:
                alt = {}
            alt.update(json.loads(text))
            text = json.dumps(alt) + "\n"
        print(f"\n--- {ziel.relative_to(ROOT)} ({'wird zusammengefuehrt' if art == 'zusammenfuehren' else 'neu'})")
        print(text.rstrip())
        if zeigen:
            continue
        ziel.parent.mkdir(parents=True, exist_ok=True)
        if ziel.exists():
            sicher = ziel.with_name(ziel.name + ".vor-" + stempel)
            shutil.copy2(ziel, sicher)
            print(f"    (alte Datei gesichert: {sicher.name})")
        ziel.write_text(text, encoding="utf-8")
        if name == "start.local.sh":
            ziel.chmod(0o755)
    if s["io"] == "modul":
        print("\n!  Modbus-I/O-Modul: IP-Adresse in vorsa_daten/eaio.json eintragen (192.0.2.10 ist ein Platzhalter)"
              " oder in der Oberflaeche unter Einstellungen > Ein-/Ausgaenge.")
    if s["io"] == "modbus":
        print("\n!  Modbus hat keine Anmeldung - nur im abgeschotteten Maschinennetz betreiben.")
    if not zeigen:
        print("\nFertig. Jetzt: sudo systemctl restart vorsa   (oder start.sh neu starten)")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("link", help="Link aus spikingedge.com/configure/ oder der Teil hinter #")
    ap.add_argument("--zeigen", action="store_true", help="nur anzeigen, nichts schreiben")
    a = ap.parse_args()
    link = a.link if a.link.startswith("http") else "https://spikingedge.com/configure/#" + a.link.lstrip("#")
    return anwenden(lesen(a.link), link, a.zeigen)


if __name__ == "__main__":
    sys.exit(main())
