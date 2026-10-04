#!/usr/bin/env python3
"""1.9.63 — Industrie-Paket I4: Komplettsicherung + install.sh --config.

Server: POST /api/sicherung (ZIP herunterladen), /api/sicherung_pruefen und
/api/sicherung_einspielen (ZIP als Rohkoerper; nur Admin bzw. offen ohne Rollen).
Nach dem Einspielen beendet sich der Server mit Code 1 - systemd (Restart=on-failure)
startet ihn mit dem eingespielten Stand neu.
Oberflaeche: Einstellungen › Wartung › Komplettsicherung.
"""
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
H = ROOT / "vorsa" / "web" / "static" / "index.html"
S = ROOT / "vorsa" / "web" / "server.py"
D = ROOT / "vorsa" / "web" / "static" / "sprache_en.js"
R = ROOT / "vorsa" / "rollen.py"


def ers(t, a, n, k=1):
    if t.count(a) != k:
        raise SystemExit(f"FEHLER: {t.count(a)}x statt {k}x: {a[:140]}")
    return t.replace(a, n)


r = R.read_text(encoding="utf-8")
if "/api/sicherung" not in r:
    r = ers(r, '''    "/api/rollen", "/api/eaio", "/api/sps",''', '''    "/api/rollen", "/api/eaio", "/api/sps", "/api/sicherung", "/api/sicherung_pruefen", "/api/sicherung_einspielen",''')
    R.write_text(r, encoding="utf-8")
    print("rollen.py: Sicherung nur Admin")

s = S.read_text(encoding="utf-8")
if "/api/sicherung_einspielen" in s:
    print("server.py: schon gepatcht")
else:
    s = ers(s, 'BUILD = "1.0.0-alpha.2"', 'BUILD = "1.9.63-sicherung"')
    s = ers(s, '''                self.__dict__.pop("_koerper_d", None)
                weg = urlparse(self.path).path
                koerper = self._koerper()''', '''                self.__dict__.pop("_koerper_d", None)
                self.__dict__.pop("_roh_d", None)
                weg = urlparse(self.path).path
                if weg in ("/api/sicherung_pruefen", "/api/sicherung_einspielen"):
                    # ZIP als Rohkoerper (kein JSON); hoechstens 1 GB.
                    n = int(self.headers.get("Content-Length", 0) or 0)
                    if n <= 0 or n > 1024 * 1024 * 1024:
                        return self._json({"ok": False, "grund": "leere oder zu grosse Datei"}, 400)
                    self._roh_d = self.rfile.read(n)
                    self._koerper_d = {}
                koerper = self._koerper()''')
    s = ers(s, '''            if weg == "/api/sps":
                return self._json(verarbeitung.sps_einstellen(koerper))''', '''            if weg == "/api/sps":
                return self._json(verarbeitung.sps_einstellen(koerper))

            if weg == "/api/sicherung":
                # I4: Komplettsicherung des Datenordners als ZIP.
                from ..sicherung import erstellen
                roh, name = erstellen(zustand.ordner, BUILD, getattr(verarbeitung, "profil", ""))
                self.send_response(200)
                self.send_header("Content-Type", "application/zip")
                self.send_header("Content-Length", str(len(roh)))
                self.send_header("Content-Disposition", f'attachment; filename="{name}"')
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(roh)
                return None

            if weg in ("/api/sicherung_pruefen", "/api/sicherung_einspielen"):
                from ..sicherung import einspielen, pruefen
                roh = self.__dict__.get("_roh_d", b"")
                if weg.endswith("pruefen"):
                    return self._json(pruefen(roh))
                erg = einspielen(zustand.ordner, roh, BUILD)
                if erg.get("ok"):
                    print(f"  Sicherung eingespielt ({erg['manifest']}) - Neustart", flush=True)
                    # Antwort zuerst ausliefern, dann beenden: systemd startet neu,
                    # der Server liest den eingespielten Stand frisch ein.
                    threading.Timer(0.8, lambda: __import__("os")._exit(1)).start()
                return self._json(erg)''')
    if "\nimport os\n" not in s and "import os," not in s and "\nimport os " not in s:
        s = s.replace("\nimport json\n", "\nimport json\nimport os\n", 1)
    S.write_text(s, encoding="utf-8")
    print("server.py gepatcht")

h = H.read_text(encoding="utf-8")
if "SICHERUNG (1.9.63)" in h:
    print("index.html: schon gepatcht")
else:
    h = ers(h, '''    <div class="knopfreihe" style="margin-top:12px">
      <button class="mini gefahr" data-tat="ereignisse_leeren">Unklare Fälle löschen</button>
      <button class="mini gefahr" data-tat="vergessen">Gelerntes verwerfen</button></div>`;
}''', '''    <div class="knopfreihe" style="margin-top:12px">
      <button class="mini gefahr" data-tat="ereignisse_leeren">Unklare Fälle löschen</button>
      <button class="mini gefahr" data-tat="vergessen">Gelerntes verwerfen</button></div>
    <h4>Komplettsicherung</h4>
    <div class="e-hinweis">Eine Datei mit allem, was diese Anlage kann: Objekte und Fotos, Gelerntes, Prüfprogramme, Leerbilder, Einstellungen, Ein-/Ausgänge, Benutzer, Testsatz und Protokolle. Zum Aufbewahren oder um einen zweiten Pi gleich einzurichten.</div>
    <div class="knopfreihe"><button class="mini an" data-tat="sicherung_laden">Sicherung herunterladen</button>
      <label class="mini sich-datei">Sicherung einspielen …<input type="file" accept=".zip,application/zip" data-sicherung-datei hidden></label></div>
    <div class="e-hinweis" id="sichStand">${txt(SICH_STAND)}</div>`;
}
/* SICHERUNG (1.9.63) */
let SICH_STAND = "";
async function sicherungLaden() {
  SICH_STAND = "Sicherung wird erstellt …"; zeichneEinstellungen();
  try {
    const a = await fetch("/api/sicherung", { method: "POST", headers: Object.assign({ "Content-Type": "application/json" }, SE_TOKEN ? { "X-SE-Token": SE_TOKEN } : {}), body: "{}" });
    if (a.status === 403) { const j = await a.json(); anmeldenZeigen(j.grund, j.rolle_noetig); SICH_STAND = ""; zeichneEinstellungen(); return; }
    const blob = await a.blob();
    const name = ((a.headers.get("Content-Disposition") || "").match(/filename="([^"]+)"/) || [])[1] || "se-inspect-sicherung.zip";
    const l = document.createElement("a"); l.href = URL.createObjectURL(blob); l.download = name; document.body.appendChild(l); l.click();
    setTimeout(() => { URL.revokeObjectURL(l.href); l.remove(); }, 1000);
    SICH_STAND = `Heruntergeladen: ${name} (${(blob.size / 1048576).toFixed(1)} MB)`;
  } catch (e) { SICH_STAND = "Sicherung fehlgeschlagen: " + e; }
  zeichneEinstellungen();
}
async function sicherungEinspielen(datei) {
  const kopf = Object.assign({ "Content-Type": "application/zip" }, SE_TOKEN ? { "X-SE-Token": SE_TOKEN } : {});
  SICH_STAND = "Sicherung wird geprüft …"; zeichneEinstellungen();
  const roh = await datei.arrayBuffer();
  let p = await (await fetch("/api/sicherung_pruefen", { method: "POST", headers: kopf, body: roh })).json();
  if (p.verboten) { anmeldenZeigen(p.grund, p.rolle_noetig); SICH_STAND = ""; zeichneEinstellungen(); return; }
  if (!p.ok) { SICH_STAND = "Nicht eingespielt: " + (p.grund || "ungültig"); zeichneEinstellungen(); return; }
  const m = p.manifest || {};
  if (!await bestaetigen({ titel: "Sicherung einspielen",
      text: `Sicherung von „${m.rechner || "?"}“ vom ${m.zeit || "?"} (Build ${m.build || "?"}, ${m.dateien || "?"} Dateien) einspielen? Der jetzige Stand wird vorher gesichert, danach startet SE Inspect neu.`,
      ok: "Einspielen" })) { SICH_STAND = ""; zeichneEinstellungen(); return; }
  const e = await (await fetch("/api/sicherung_einspielen", { method: "POST", headers: kopf, body: roh })).json();
  if (!e.ok) { SICH_STAND = "Nicht eingespielt: " + (e.grund || "Fehler"); zeichneEinstellungen(); return; }
  SICH_STAND = "Eingespielt — SE Inspect startet neu, die Seite lädt gleich neu …"; zeichneEinstellungen();
  const bis = Date.now() + 90000;
  await new Promise(r => setTimeout(r, 4000));
  while (Date.now() < bis) {
    try { const a = await fetch("/api/state", { cache: "no-store" }); if (a.ok) { location.reload(); return; } } catch (x) {}
    await new Promise(r => setTimeout(r, 2000));
  }
  SICH_STAND = "Kein Neustart erkannt — läuft SE Inspect ohne Dienst? Dann von Hand neu starten.";
  zeichneEinstellungen();
}
document.addEventListener("change", ev => {
  const f = ev.target.closest && ev.target.closest("[data-sicherung-datei]");
  if (f && f.files && f.files[0]) { sicherungEinspielen(f.files[0]); f.value = ""; }
});''')
    h = ers(h, '''  if (tat === "anmelden") { return anmelden(); }''', '''  if (tat === "anmelden") { return anmelden(); }
  if (tat === "sicherung_laden") { return sicherungLaden(); }''')
    h = ers(h, '''/* Kamera-Dock (1.9.52) */''', '''/* SICHERUNG (1.9.63) */
#eInhalt .sich-datei { cursor:pointer; display:inline-flex; align-items:center; }
/* Kamera-Dock (1.9.52) */''')
    H.write_text(h, encoding="utf-8")
    print("index.html gepatcht")

d = D.read_text(encoding="utf-8")
if "Nachtrag 18" not in d:
    d = ers(d, '\nif (window.spracheNachladen) window.spracheNachladen();\n', '''
/* ---- Nachtrag 18 (1.9.63 Sicherung) ---- */
Object.assign(window.SPRACHEN.en, {
  "Komplettsicherung": "Full backup", "Sicherung herunterladen": "Download backup", "Sicherung einspielen …": "Restore backup …",
  "Eine Datei mit allem, was diese Anlage kann: Objekte und Fotos, Gelerntes, Prüfprogramme, Leerbilder, Einstellungen, Ein-/Ausgänge, Benutzer, Testsatz und Protokolle. Zum Aufbewahren oder um einen zweiten Pi gleich einzurichten.": "One file with everything this cell knows: objects and photos, what was learned, jobs, empty images, settings, I/O, users, test set and logs. To keep, or to set up a second Pi the same way.",
  "Sicherung wird erstellt …": "Creating backup …", "Sicherung wird geprüft …": "Checking backup …", "Sicherung einspielen": "Restore backup", "Einspielen": "Restore",
  "Eingespielt — SE Inspect startet neu, die Seite lädt gleich neu …": "Restored — SE Inspect is restarting, the page will reload …",
  "Kein Neustart erkannt — läuft SE Inspect ohne Dienst? Dann von Hand neu starten.": "No restart detected — is SE Inspect running without the service? Then restart it by hand."
});

if (window.spracheNachladen) window.spracheNachladen();
''')
    D.write_text(d, encoding="utf-8")
    print("sprache_en.js: Nachtrag 18")
