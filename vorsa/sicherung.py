"""Komplettsicherung einer Anlage (Industrie-Paket I4, 1.9.63).

Eine ZIP-Datei mit dem ganzen Datenordner (vorsa_daten/): Objekte und Fotos,
Gelerntes (chip_modell*.fbz + Begleitdatei), Pruefprogramme, Leerbilder,
Einstellungen (pruef/eaio/sps/rollen), Testsatz, Pruef- und Aenderungsprotokoll.
Dazu manifest.json (Build, Zeit, Rechner, Anzahl, Pruefsummen).

Einspielen ersetzt den Datenordner. Vorher wird der aktuelle Stand als ZIP
neben den Datenordner gelegt (vorsa_sicherungen/vor-einspielen-<Zeit>.zip), damit
nichts verloren geht. Danach muss der Dienst neu starten - der Server haelt den
Zustand im Speicher und wuerde ihn sonst beim naechsten Speichern ueberschreiben.

Nicht enthalten: der trainierte M3-Detektor (vorsa_m3.fbz im Projektordner, gross,
eigene Datei) und Programmcode.
"""
from __future__ import annotations

import hashlib
import io
import json
import shutil
import socket
import time
import zipfile
from pathlib import Path

MAX_BYTES = 1024 * 1024 * 1024          # 1 GB entpackt
AUSLASSEN = (".vor-", ".tmp")


def _dateien(ordner: Path):
    for p in sorted(ordner.rglob("*")):
        if p.is_file() and not any(a in p.name for a in AUSLASSEN):
            yield p


def erstellen(ordner, build: str, profil: str = "") -> tuple:
    """-> (zip_bytes, dateiname)"""
    ordner = Path(ordner)
    buf = io.BytesIO()
    pruef = {}
    n = 0
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for p in _dateien(ordner):
            rel = p.relative_to(ordner).as_posix()
            daten = p.read_bytes()
            pruef[rel] = hashlib.sha256(daten).hexdigest()[:16]
            z.writestr("vorsa_daten/" + rel, daten)
            n += 1
        z.writestr("manifest.json", json.dumps({
            "art": "se-inspect-sicherung", "version": 1, "build": build, "profil": profil,
            "zeit": time.strftime("%Y-%m-%d %H:%M:%S"), "rechner": socket.gethostname(),
            "dateien": n, "pruefsummen": pruef}, indent=1, ensure_ascii=False))
    name = f"se-inspect-sicherung-{socket.gethostname()}-{time.strftime('%Y%m%d-%H%M')}.zip"
    return buf.getvalue(), name


def pruefen(daten: bytes) -> dict:
    """Ohne zu schreiben: ist das eine gueltige Sicherung? -> Manifest + Befund."""
    try:
        z = zipfile.ZipFile(io.BytesIO(daten))
    except zipfile.BadZipFile:
        return {"ok": False, "grund": "keine ZIP-Datei"}
    namen = z.namelist()
    if "manifest.json" not in namen:
        return {"ok": False, "grund": "keine SE-Inspect-Sicherung (manifest.json fehlt)"}
    try:
        m = json.loads(z.read("manifest.json"))
    except Exception:
        return {"ok": False, "grund": "manifest.json unlesbar"}
    if m.get("art") != "se-inspect-sicherung":
        return {"ok": False, "grund": "falsche Art im Manifest"}
    summe = 0
    for info in z.infolist():
        n = info.filename
        if n == "manifest.json" or n.endswith("/"):
            continue
        if not n.startswith("vorsa_daten/") or ".." in Path(n).parts or n.startswith("/") or "\\" in n:
            return {"ok": False, "grund": f"unzulaessiger Pfad in der Sicherung: {n[:60]}"}
        summe += info.file_size
        if summe > MAX_BYTES:
            return {"ok": False, "grund": "Sicherung zu gross (> 1 GB entpackt)"}
    fehler = []
    for rel, h in (m.get("pruefsummen") or {}).items():
        try:
            if hashlib.sha256(z.read("vorsa_daten/" + rel)).hexdigest()[:16] != h:
                fehler.append(rel)
        except KeyError:
            fehler.append(rel)
    if fehler:
        return {"ok": False, "grund": f"{len(fehler)} Datei(en) beschaedigt, z. B. {fehler[0]}"}
    return {"ok": True, "manifest": {k: m.get(k) for k in ("build", "profil", "zeit", "rechner", "dateien")}}


def einspielen(ordner, daten: bytes, build: str) -> dict:
    befund = pruefen(daten)
    if not befund.get("ok"):
        return befund
    ordner = Path(ordner)
    ablage = ordner.parent / "vorsa_sicherungen"
    ablage.mkdir(parents=True, exist_ok=True)
    vorher, _ = erstellen(ordner, build) if ordner.exists() else (b"", "")
    vor_name = ""
    if vorher:
        vor_name = f"vor-einspielen-{time.strftime('%Y%m%d-%H%M%S')}.zip"
        (ablage / vor_name).write_bytes(vorher)
    neu = ordner.with_name(ordner.name + ".neu")
    if neu.exists():
        shutil.rmtree(neu)
    neu.mkdir(parents=True)
    with zipfile.ZipFile(io.BytesIO(daten)) as z:
        for info in z.infolist():
            if info.filename == "manifest.json" or info.filename.endswith("/"):
                continue
            ziel = neu / info.filename[len("vorsa_daten/"):]
            ziel.parent.mkdir(parents=True, exist_ok=True)
            ziel.write_bytes(z.read(info))
    alt = ordner.with_name(ordner.name + ".alt")
    if alt.exists():
        shutil.rmtree(alt)
    if ordner.exists():
        ordner.rename(alt)
    neu.rename(ordner)
    if alt.exists():
        shutil.rmtree(alt, ignore_errors=True)
    return {"ok": True, "manifest": befund["manifest"], "vorher": str(Path("vorsa_sicherungen") / vor_name) if vor_name else "",
            "neustart": True}
