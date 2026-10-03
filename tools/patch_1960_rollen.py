#!/usr/bin/env python3
"""1.9.60 — Industrie-Paket I3: Benutzerrollen mit PIN + Änderungsprotokoll.

Server: Rollenprüfung für JEDEN POST vor der Route (403 mit Grund), Token im
Kopf X-SE-Token, /api/anmelden, /api/abmelden, /api/rollen (GET Übersicht +
Protokoll, POST pin/aus/zeit). Ohne Admin-PIN bleibt alles offen wie bisher.
Oberfläche: Schloss unten links (Anmelden/Abmelden, PIN-Eingabe), Bediener
sieht nur Prüfen/Linie/Prüfprogramme/Meldungen, Einstellungen › Benutzer
(PINs, Abmeldezeit, Rollen aus, Änderungsprotokoll). 403 öffnet die Anmeldung.
"""
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
H = ROOT / "vorsa" / "web" / "static" / "index.html"
S = ROOT / "vorsa" / "web" / "server.py"
D = ROOT / "vorsa" / "web" / "static" / "sprache_en.js"


def ers(t, a, n, k=1):
    if t.count(a) != k:
        raise SystemExit(f"FEHLER: {t.count(a)}x statt {k}x: {a[:140]}")
    return t.replace(a, n)


s = S.read_text(encoding="utf-8")
if "from ..rollen import Rollen" in s:
    print("server.py: schon gepatcht")
else:
    s = ers(s, 'BUILD = "1.9.59-eaio"', 'BUILD = "1.9.60-rollen"')
    s = ers(s, '''        # DIGITALE EIN-/AUSGAENGE (I1, 1.9.59): Trigger rein, OK/NOK/Bereit/''', '''        # BENUTZERROLLEN (I3, 1.9.60): ohne Admin-PIN alles offen.
        try:
            from ..rollen import Rollen
            self.rollen = Rollen(zustand.ordner)
        except Exception as exc:
            print(f"  Rollen nicht verfuegbar: {exc}", flush=True)
            self.rollen = None
        # DIGITALE EIN-/AUSGAENGE (I1, 1.9.59): Trigger rein, OK/NOK/Bereit/''')
    s = ers(s, '''        def _koerper(self) -> dict:
            try:
                laenge = int(self.headers.get("Content-Length", 0))''', '''        def _koerper(self) -> dict:
            # 1.9.60: einmal lesen, danach aus dem Zwischenspeicher - die
            # Rollenpruefung braucht den Koerper vor der Route.
            if "_koerper_d" in self.__dict__:
                return self._koerper_d
            self._koerper_d = self._koerper_lesen()
            return self._koerper_d

        def _koerper_lesen(self) -> dict:
            try:
                laenge = int(self.headers.get("Content-Length", 0))''')
    s = ers(s, '''        def do_POST(self):
            try:
                return self._post_roh()
            except Exception as exc:
                self._routenfehler("POST", exc)''', '''        def do_POST(self):
            try:
                # Keep-Alive: dieselbe Handler-Instanz bedient mehrere
                # Anfragen - den Koerper der vorigen nie wiederverwenden.
                self.__dict__.pop("_koerper_d", None)
                weg = urlparse(self.path).path
                koerper = self._koerper()
                r = getattr(verarbeitung, "rollen", None)
                rolle = r.rolle(self.headers.get("X-SE-Token", "")) if r else "admin"
                if r is not None:
                    noetig = r.noetig(weg, koerper)
                    if not r.darf(rolle, noetig):
                        return self._json({
                            "ok": False, "verboten": True, "rolle": rolle, "rolle_noetig": noetig,
                            "grund": {"einrichter": "Anmeldung als Einrichter nötig",
                                      "admin": "Anmeldung als Admin nötig"}.get(noetig, "nicht erlaubt")}, 403)
                antwort = self._post_roh()
                if r is not None:
                    r.protokoll(rolle, weg, koerper)
                return antwort
            except Exception as exc:
                self._routenfehler("POST", exc)''')
    s = ers(s, '''            if weg == "/api/eaio":
                e = getattr(verarbeitung, "eaio", None)
                return self._json(e.status() if e else {"fehler": "nicht verfuegbar"})''', '''            if weg == "/api/eaio":
                e = getattr(verarbeitung, "eaio", None)
                return self._json(e.status() if e else {"fehler": "nicht verfuegbar"})

            if weg == "/api/rollen":
                r = getattr(verarbeitung, "rollen", None)
                if r is None:
                    return self._json({"aktiv": False, "rolle": "admin", "pins": {}, "protokoll": []})
                return self._json(r.uebersicht(r.rolle(self.headers.get("X-SE-Token", ""))))''')
    s = ers(s, '''            if weg == "/api/eaio":
                # I1: {aktion: "einstellen", ...cfg} | {aktion: "test", signal}''', '''            if weg in ("/api/anmelden", "/api/abmelden", "/api/rollen"):
                r = getattr(verarbeitung, "rollen", None)
                if r is None:
                    return self._json({"ok": False, "grund": "Rollen nicht verfuegbar"}, 409)
                if weg == "/api/anmelden":
                    return self._json(r.anmelden(str(koerper.get("pin", ""))))
                if weg == "/api/abmelden":
                    return self._json(r.abmelden(self.headers.get("X-SE-Token", "")))
                rolle = r.rolle(self.headers.get("X-SE-Token", ""))
                return self._json(r.verwalten(rolle, koerper))

            if weg == "/api/eaio":
                # I1: {aktion: "einstellen", ...cfg} | {aktion: "test", signal}''')
    S.write_text(s, encoding="utf-8")
    print("server.py gepatcht")

h = H.read_text(encoding="utf-8")
if "ROLLEN (1.9.60)" in h:
    print("index.html: schon gepatcht")
else:
    # hole(): Token mitschicken, 403 -> Anmeldung
    h = ers(h, '''async function hole(pfad, daten) {
  const o = daten ? { method:"POST", headers:{"Content-Type":"application/json"},
                      body:JSON.stringify(daten) } : {};
  const a = await fetch(pfad, o);
  return a.json();
}''', '''/* ROLLEN (1.9.60): Token je Browser; eine verweigerte Aktion oeffnet die Anmeldung. */
let SE_TOKEN = "";
try { SE_TOKEN = localStorage.getItem("nbes_token") || ""; } catch (e) {}
let ROLLE = { aktiv: false, rolle: "admin", pins: {} };
async function hole(pfad, daten) {
  const kopf = SE_TOKEN ? { "X-SE-Token": SE_TOKEN } : {};
  const o = daten ? { method:"POST", headers:Object.assign({"Content-Type":"application/json"}, kopf),
                      body:JSON.stringify(daten) } : { headers: kopf };
  const a = await fetch(pfad, o);
  const j = await a.json();
  if (a.status === 403 && j && j.verboten) {
    MELDUNG = j.grund || "nicht erlaubt"; setTimeout(() => { MELDUNG = ""; }, 4000);
    try { anmeldenZeigen(j.grund, j.rolle_noetig); } catch (e) {}
  }
  return j;
}
async function rolleLaden() {
  try { ROLLE = await hole("/api/rollen"); } catch (e) {}
  rolleAnwenden();
}
function rolleAnwenden() {
  const bed = !!ROLLE.aktiv && ROLLE.rolle === "bediener";
  document.body.classList.toggle("rolle-bediener", bed);
  const k = $("navRolle");
  if (k) {
    const n = { admin: "Admin", einrichter: "Einrichter", bediener: "Bediener" }[ROLLE.rolle] || "";
    k.hidden = !ROLLE.aktiv;
    k.classList.toggle("offen", ROLLE.rolle !== "bediener");
    k.title = ROLLE.aktiv ? `Angemeldet: ${n} — Klick: ${ROLLE.rolle === "bediener" ? "anmelden" : "abmelden"}` : "";
    const l = $("navRolleLabel"); if (l) l.textContent = ROLLE.rolle === "bediener" ? "" : n.slice(0, 1);
  }
  if (bed && typeof MODUS !== "undefined" && MODUS !== "betreiben") { try { setzeModus("betreiben"); } catch (e) {} }
}
function anmeldenZeigen(grund, noetig) {
  const d = $("dAnmelden"); if (!d) return;
  $("anmGrund").textContent = grund || (noetig === "admin" ? "PIN für Admin eingeben" : "PIN eingeben");
  $("anmFehler").textContent = "";
  d.hidden = false;
  const f = $("anmPin"); f.value = ""; setTimeout(() => f.focus(), 30);
}
async function anmelden() {
  const r = await hole("/api/anmelden", { pin: $("anmPin").value });
  if (r && r.ok) {
    SE_TOKEN = r.token; try { localStorage.setItem("nbes_token", SE_TOKEN); } catch (e) {}
    $("dAnmelden").hidden = true; await rolleLaden(); LETZTE_SPALTE = ""; aktualisieren();
  } else { $("anmFehler").textContent = (r && r.grund) || "PIN falsch"; $("anmPin").value = ""; }
}''')
    # Schloss in der Fussleiste
    h = ers(h, '''      <button class="snav klein" data-tat="seite_schmal" title="Navigation ein- oder ausklappen">''',
            '''      <button class="snav klein" id="navRolle" data-tat="rolle" hidden title="Anmelden">
        <svg viewBox="0 0 16 16" aria-hidden="true"><rect x="3" y="7" width="10" height="8" rx="1.5"/><path d="M5 7V5a3 3 0 016 0v2"/></svg><span id="navRolleLabel"></span></button>
      <button class="snav klein" data-tat="seite_schmal" title="Navigation ein- oder ausklappen">''')
    # Anmelde-Dialog
    h = ers(h, '''<div id="rueckToast" role="status" hidden>''', '''<div class="schleier" id="dAnmelden" hidden>
  <div class="fenster anm-fenster" role="dialog" aria-labelledby="anmTitel">
    <div class="fkopf"><h2 id="anmTitel">Anmelden</h2><button class="zu" data-tat="dialog_zu" data-ziel="dAnmelden">×</button></div>
    <div class="anm-koerper">
      <p id="anmGrund">PIN eingeben</p>
      <input id="anmPin" class="eingabe" type="password" inputmode="numeric" autocomplete="off" maxlength="8" placeholder="PIN">
      <div id="anmFehler" class="anm-fehler"></div>
      <button class="ops-haupt" data-tat="anmelden" style="width:100%">Anmelden</button>
      <small>Einrichter: einrichten und anlernen · Admin: zusätzlich Benutzer und Ein-/Ausgänge</small>
    </div>
  </div>
</div>
<div id="rueckToast" role="status" hidden>''')
    # Handler
    h = ers(h, '''  if (tat === "eaio_treiber") {''', '''  if (tat === "anmelden") { return anmelden(); }
  if (tat === "rolle") {
    if (ROLLE.aktiv && ROLLE.rolle !== "bediener") {
      await hole("/api/abmelden", {}); SE_TOKEN = ""; try { localStorage.removeItem("nbes_token"); } catch (e) {}
      $("dEinstellungen").hidden = true; await rolleLaden(); return;
    }
    anmeldenZeigen(); return;
  }
  if (tat === "rolle_pin") {
    const f = $("eInhalt").querySelector(`[data-pin="${el.dataset.rolle}"]`);
    const r = await hole("/api/rollen", { aktion: "pin", rolle: el.dataset.rolle, pin: f ? f.value : "" });
    if (r && r.ok === false) { MELDUNG = r.grund; setTimeout(() => { MELDUNG = ""; }, 4000); }
    if (r && r.ok && el.dataset.rolle === "admin" && !ROLLE.aktiv) {
      // erster Admin-PIN: gleich als Admin anmelden, sonst sperrt man sich aus
      const a = await hole("/api/anmelden", { pin: f.value });
      if (a && a.ok) { SE_TOKEN = a.token; try { localStorage.setItem("nbes_token", SE_TOKEN); } catch (e) {} }
    }
    await rolleLaden(); zeichneEinstellungen(); return;
  }
  if (tat === "rollen_aus") {
    if (!await bestaetigen({ titel: "Rollen ausschalten", text: "Alle PINs löschen? Danach ist die Oberfläche wieder für alle offen.", ok: "Ausschalten" })) return;
    await hole("/api/rollen", { aktion: "aus" }); await rolleLaden(); zeichneEinstellungen(); return;
  }
  if (tat === "rolle_zeit") {
    const f = $("eInhalt").querySelector('[data-rolle-zeit]');
    await hole("/api/rollen", { aktion: "zeit", minuten: f ? +f.value : 15 }); await rolleLaden(); zeichneEinstellungen(); return;
  }
  if (tat === "eaio_treiber") {''')
    h = ers(h, '''  if (ev.key === "Escape") {
    $("dEinstellungen").hidden = true;''', '''  if (ev.key === "Escape") {
    $("dAnmelden").hidden = true;
    $("dEinstellungen").hidden = true;''')
    # Enter im PIN-Feld (vor dem Tastenfilter, der Eingabefelder ausschliesst)
    h = ers(h, '''document.addEventListener("keydown", ev => {
  if (ev.target.closest("input,textarea,select,button,summary,[contenteditable],[role='button'],[role='switch']")) return;''', '''document.addEventListener("keydown", ev => {
  if (ev.target.id === "anmPin" && ev.key === "Enter") { ev.preventDefault(); anmelden(); return; }
  if (ev.target.closest("input,textarea,select,button,summary,[contenteditable],[role='button'],[role='switch']")) return;''')
    # Reiter Benutzer
    h = ers(h, '''["eaio", "Ein-/Ausgänge"],''', '''["eaio", "Ein-/Ausgänge"], ["benutzer", "Benutzer"],''')
    h = ers(h, '''  if (ABSCHNITT === "eaio") return abschnittEaio();''', '''  if (ABSCHNITT === "eaio") return abschnittEaio();
  if (ABSCHNITT === "benutzer") return abschnittBenutzer();''')
    h = ers(h, '''function inhaltAbschnitt() {''', '''let ROLLE_GELADEN = 0;
function abschnittBenutzer() {
  if (Date.now() - ROLLE_GELADEN > 3000) { ROLLE_GELADEN = Date.now(); rolleLaden().then(() => { if (ABSCHNITT === "benutzer") zeichneEinstellungen(); }); }
  const R = ROLLE, p = R.pins || {};
  const pinZeile = (rolle, titel, text) => `<div class="e-zeile"><div><b>${titel}</b><span>${text}</span><span>${p[rolle] ? "PIN gesetzt" : "kein PIN"}</span></div>
      <div class="e-wahl"><input class="eingabe" data-pin="${rolle}" type="password" inputmode="numeric" maxlength="8" placeholder="neuer PIN" style="width:110px">
        <button class="mini" data-tat="rolle_pin" data-rolle="${rolle}">${p[rolle] ? "Ändern" : "Setzen"}</button></div></div>`;
  return `<h3>Benutzer</h3>
    <div class="e-hinweis">${R.aktiv ? "Rollen sind aktiv. Ohne Anmeldung ist die Anlage eine Bedienstation: prüfen, quittieren, Prüfprogramm laden."
      : "Rollen sind aus — die Oberfläche ist für alle offen. Mit einem Admin-PIN wird sie ohne Anmeldung zur Bedienstation."}</div>
    ${pinZeile("admin", "Admin", "alles, auch Benutzer und Ein-/Ausgänge")}
    ${R.aktiv ? pinZeile("einrichter", "Einrichter", "einrichten, anlernen, Einstellungen (leer lassen = keiner)") : ""}
    ${R.aktiv ? `<div class="e-zeile"><div><b>Automatisch abmelden</b><span>nach Minuten ohne Aktion</span></div>
      <div class="e-wahl"><input class="eingabe" data-rolle-zeit type="number" min="1" max="480" value="${R.abmelden_min || 15}" style="width:70px">
        <button class="mini" data-tat="rolle_zeit">Übernehmen</button></div></div>
    <div class="e-zeile"><div><b>Rollen ausschalten</b><span>löscht alle PINs</span></div>
      <div class="e-wahl"><button class="mini gefahr" data-tat="rollen_aus">Ausschalten</button></div></div>` : ""}
    <h4>Änderungsprotokoll</h4>
    <div class="eio-log">${(R.protokoll || []).length ? R.protokoll.map(e => `<div><span>${txt(e.zeit.slice(5))}</span><span>${txt(e.rolle)}</span>${txt(e.weg.replace("/api/", ""))} ${txt(e.inhalt === "{}" ? "" : e.inhalt)}</div>`).join("")
      : '<div class="leise">noch keine Einträge</div>'}</div>`;
}
function inhaltAbschnitt() {''')
    # Start: Rolle laden, alle 10 s nachfuehren
    h = ers(h, '''  setInterval(opsSync, 1000);''', '''  setInterval(opsSync, 1000);
  rolleLaden(); setInterval(rolleLaden, 10000);''')
    h = ers(h, '''/* Kamera-Dock (1.9.52) */''', '''/* ROLLEN (1.9.60) */
body#opsApp.rolle-bediener .ops-expert, body#opsApp.rolle-bediener #betriebKnopf { display:none !important; }
body#opsApp #navRolle[hidden] { display:none !important; }
body#opsApp #navRolle.offen { color:var(--akzent,#49e7ff) !important; }
.anm-fenster { max-width:360px; }
.anm-koerper { padding:16px 18px 18px; display:grid; gap:10px; }
.anm-koerper p { margin:0; color:var(--text); font-size:14px; }
.anm-koerper input { font-size:22px; letter-spacing:.4em; text-align:center; padding:10px; }
.anm-koerper small { color:var(--leise,#8a94a0); font-size:11.5px; line-height:1.4; }
.anm-fehler { color:var(--rot,#ff2d7a); font-size:12.5px; min-height:16px; }
/* Kamera-Dock (1.9.52) */''')
    H.write_text(h, encoding="utf-8")
    print("index.html gepatcht")

d = D.read_text(encoding="utf-8")
if "Nachtrag 15" not in d:
    d = ers(d, '\nif (window.spracheNachladen) window.spracheNachladen();\n', '''
/* ---- Nachtrag 15 (1.9.60 Rollen) ---- */
Object.assign(window.SPRACHEN.en, {
  "Benutzer": "Users", "Anmelden": "Sign in", "PIN eingeben": "Enter PIN", "PIN für Admin eingeben": "Enter admin PIN", "PIN": "PIN",
  "PIN falsch": "Wrong PIN", "Anmeldung als Einrichter nötig": "Sign in as setter needed", "Anmeldung als Admin nötig": "Sign in as admin needed",
  "Einrichter: einrichten und anlernen · Admin: zusätzlich Benutzer und Ein-/Ausgänge": "Setter: setup and teaching · Admin: also users and I/O",
  "Rollen sind aktiv. Ohne Anmeldung ist die Anlage eine Bedienstation: prüfen, quittieren, Prüfprogramm laden.": "Roles are active. Without sign-in the cell is an operator station: inspect, acknowledge, load jobs.",
  "Rollen sind aus — die Oberfläche ist für alle offen. Mit einem Admin-PIN wird sie ohne Anmeldung zur Bedienstation.": "Roles are off — the interface is open to everyone. With an admin PIN it becomes an operator station without sign-in.",
  "Admin": "Admin", "Einrichter": "Setter", "Bediener": "Operator", "alles, auch Benutzer und Ein-/Ausgänge": "everything, including users and I/O",
  "einrichten, anlernen, Einstellungen (leer lassen = keiner)": "setup, teaching, settings (leave empty = none)",
  "{} · PIN gesetzt": "{} · PIN set", "{} · kein PIN": "{} · no PIN", "PIN gesetzt": "PIN set", "kein PIN": "no PIN", "neuer PIN": "new PIN", "Ändern": "Change", "Setzen": "Set",
  "Automatisch abmelden": "Automatic sign-out", "nach Minuten ohne Aktion": "after minutes without activity",
  "Rollen ausschalten": "Turn roles off", "löscht alle PINs": "deletes all PINs", "Ausschalten": "Turn off",
  "Alle PINs löschen? Danach ist die Oberfläche wieder für alle offen.": "Delete all PINs? Afterwards the interface is open to everyone again.",
  "Änderungsprotokoll": "Change log", "noch keine Einträge": "no entries yet",
  "PIN: 4 bis 8 Ziffern": "PIN: 4 to 8 digits", "Admin- und Einrichter-PIN müssen verschieden sein": "Admin and setter PIN must differ"
});

if (window.spracheNachladen) window.spracheNachladen();
''')
    D.write_text(d, encoding="utf-8")
    print("sprache_en.js: Nachtrag 15")
