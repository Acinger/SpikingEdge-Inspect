#!/usr/bin/env python3
"""1.9.59 — Industrie-Paket I1: digitale Ein-/Ausgänge (vorsa/eaio.py).

Server: Trigger-Eingang -> Prüfung (Auslöser "Extern", stationär), OK/NOK nach
jeder Prüfung (stationär je Szene, Linie je gebuchtem Teil), Bereit/Fehler aus
Betriebsart und Alarmbuch. /api/eaio (GET Zustand, POST einstellen/test).
Oberfläche: Einstellungen › Ein-/Ausgänge mit Treiberwahl (Simulation, GPIO,
Modbus TCP), Pin-/Adresstabelle, Live-Lampen, Test je Signal, Puls/Halten.
Prüf-Auslöser bekommt "Extern". Ohne Hardware läuft alles in der Simulation.
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
if "EinAusgaenge" in s:
    print("server.py: schon gepatcht")
else:
    s = ers(s, 'BUILD = "1.9.58-anlernen"', 'BUILD = "1.9.59-eaio"')
    s = ers(s, '''        # Alarmbuch (Stufe 2): flankengesteuerte Alarme mit Quittieren.
        self.alarmbuch = Alarmbuch()
''', '''        # Alarmbuch (Stufe 2): flankengesteuerte Alarme mit Quittieren.
        self.alarmbuch = Alarmbuch()
        # DIGITALE EIN-/AUSGAENGE (I1, 1.9.59): Trigger rein, OK/NOK/Bereit/
        # Fehler raus. Ohne Hardware: Simulation. Bandrelais (GPIO 18) tabu.
        self._pruef_anfrage_grund = "hand"
        try:
            from ..eaio import EinAusgaenge
            self.eaio = EinAusgaenge(zustand.ordner, ausloesen=self._eaio_trigger)
            if self.eaio.fehler:
                print(f"  Ein-/Ausgaenge: {self.eaio.fehler} -> Simulation", flush=True)
        except Exception as exc:
            print(f"  Ein-/Ausgaenge nicht verfuegbar: {exc}", flush=True)
            self.eaio = None
        if self.profil == "linie" and self.eaio is not None:
            # Linie: jedes gebuchte Teil meldet OK/NOK - eine Stelle, linie.py
            # bleibt unangetastet.
            _buche = self.pruefbuch.buche

            def _buche_mit_ausgang(urteil, *a, **k):
                e = _buche(urteil, *a, **k)
                try:
                    self.eaio.ergebnis(str(urteil))
                except Exception:
                    pass
                return e
            self.pruefbuch.buche = _buche_mit_ausgang
''')
    s = ers(s, '''    def pruefen_jetzt(self) -> dict:''', '''    def _eaio_trigger(self) -> None:
        """Trigger-Eingang (Flanke): eine Pruefung anfordern. Wirft mit Grund,
        wenn nicht zulaessig - der Grund steht dann im I/O-Protokoll."""
        if self.profil != "stationaer":
            raise RuntimeError("nur im Profil stationaer (Linie hat eigene Sensorik)")
        if self.pruef_ausloeser != "extern":
            raise RuntimeError("Pruef-Ausloeser steht nicht auf Extern")
        if str(self.zustand.betriebsart) != "betreiben":
            raise RuntimeError("nicht im Pruefen")
        self._pruef_anfrage_grund = "extern"
        self._pruef_anfrage = True

    def pruefen_jetzt(self) -> dict:''')
    s = ers(s, '''        if self._pruef_anfrage:
            self._pruef_anfrage = False
            self._pruef_antwort = self._pruef_stationaer_buchen("hand")
            return''', '''        if self._pruef_anfrage:
            self._pruef_anfrage = False
            grund, self._pruef_anfrage_grund = self._pruef_anfrage_grund, "hand"
            self._pruef_antwort = self._pruef_stationaer_buchen(grund)
            if grund == "extern" and not self._pruef_antwort.get("ok"):
                # Trigger ohne Teil: die SPS wartet auf eine Antwort -> NOK.
                try:
                    self.eaio.ergebnis("leer")
                except Exception:
                    pass
            return''')
    s = ers(s, '''        self._pruef_gebucht_sig = self._pruef_szene_sig or self._pruef_szene_kennung()
        self._pruef_gebucht_zeit = time.time()
        return {"ok": True, "urteil": gesamt, "teile": teile}''', '''        self._pruef_gebucht_sig = self._pruef_szene_sig or self._pruef_szene_kennung()
        self._pruef_gebucht_zeit = time.time()
        try:
            if self.eaio is not None:
                self.eaio.ergebnis(gesamt)
        except Exception:
            pass
        return {"ok": True, "urteil": gesamt, "teile": teile}''')
    s = ers(s, '''    def pruef_ausloeser_setzen(self, art: str) -> dict:
        art = "auto" if str(art).lower() == "auto" else "hand"''', '''    def pruef_ausloeser_setzen(self, art: str) -> dict:
        art = str(art).lower()
        art = art if art in ("auto", "extern") else "hand"''')
    s = ers(s, '''                if d.get("ausloeser") in ("hand", "auto"):
                    self.pruef_ausloeser = d["ausloeser"]''', '''                if d.get("ausloeser") in ("hand", "auto", "extern"):
                    self.pruef_ausloeser = d["ausloeser"]''')
    s = ers(s, '''                if koerper.get("ausloeser") in ("hand", "auto"):''', '''                if koerper.get("ausloeser") in ("hand", "auto", "extern"):''')
    s = ers(s, '''                self.zustand.bereich_info["alarme"] = self._alarm_stand
                self.zustand.bereich_info["system"] = self._system_stand
''', '''                self.zustand.bereich_info["alarme"] = self._alarm_stand
                self.zustand.bereich_info["system"] = self._system_stand
                if self.eaio is not None:
                    self.eaio.anlage(
                        bereit=(art == "betreiben"),
                        stoerung=bool((self._alarm_stand or {}).get("aktiv_alarm")))
                    self.zustand.bereich_info["eaio"] = {
                        "zustand": dict(self.eaio.zustand),
                        "simuliert": self.eaio.status()["simuliert"],
                        "treiber": self.eaio.cfg.get("treiber")}
''')
    s = ers(s, '''            if weg == "/api/rezepte":
                rb = getattr(verarbeitung, "rezeptbuch", None)''', '''            if weg == "/api/eaio":
                e = getattr(verarbeitung, "eaio", None)
                return self._json(e.status() if e else {"fehler": "nicht verfuegbar"})

            if weg == "/api/rezepte":
                rb = getattr(verarbeitung, "rezeptbuch", None)''')
    s = ers(s, '''            if weg == "/api/pruef_einst":''', '''            if weg == "/api/eaio":
                # I1: {aktion: "einstellen", ...cfg} | {aktion: "test", signal}
                e = getattr(verarbeitung, "eaio", None)
                if e is None:
                    return self._json({"ok": False, "grund": "nicht verfuegbar"}, 409)
                if koerper.get("aktion") == "test":
                    return self._json(e.test(str(koerper.get("signal", ""))))
                if koerper.get("aktion") == "einstellen":
                    return self._json(e.einstellen(koerper))
                return self._json({"ok": False, "grund": "aktion=einstellen|test"}, 400)

            if weg == "/api/pruef_einst":''')
    S.write_text(s, encoding="utf-8")
    print("server.py gepatcht")

h = H.read_text(encoding="utf-8")
if "EAIO (1.9.59)" in h:
    print("index.html: schon gepatcht")
else:
    h = ers(h, '''  ["allgemein", "Allgemein"], ["kamera", "Kamera"], ["erkennung", "Erkennung"], ["programme", "Prüfprogramme"],''',
            '''  ["allgemein", "Allgemein"], ["kamera", "Kamera"], ["erkennung", "Erkennung"], ["programme", "Prüfprogramme"], ["eaio", "Ein-/Ausgänge"],''')
    h = ers(h, '''  if (ABSCHNITT === "programme") return abschnittProgramme();''', '''  if (ABSCHNITT === "programme") return abschnittProgramme();
  if (ABSCHNITT === "eaio") return abschnittEaio();''')
    h = ers(h, '''function inhaltAbschnitt() {''', '''/* EAIO (1.9.59): digitale Ein-/Ausgaenge - Treiber, Belegung, Lampen, Test. */
let EAIO = null, EAIO_GELADEN = 0;
async function eaioLaden() { try { EAIO = await hole("/api/eaio"); } catch (e) {} if (ABSCHNITT === "eaio") zeichneEinstellungen(); }
function abschnittEaio() {
  if (Date.now() - EAIO_GELADEN > 1000) { EAIO_GELADEN = Date.now(); eaioLaden(); }
  const E = EAIO;
  if (!E || !E.cfg) return `<h3>Ein-/Ausgänge</h3><div class="e-hinweis">Wird geladen …</div>`;
  const c = E.cfg, tr = c.treiber, mb = c.modbus || {};
  const NAME = { trigger: "Trigger", bereit: "Bereit", ok: "OK", nok: "NOK", fehler: "Fehler" };
  const WAS = { trigger: "steigende Flanke löst eine Prüfung aus", bereit: "Anlage bereit, keine Störung",
                ok: "nach der Prüfung: alles gut", nok: "nach der Prüfung: unbekannt, Ausschuss oder kein Teil", fehler: "aktive Störung" };
  const zeile = (s, ein) => `<tr>
      <td><i class="eio-lampe ${E.zustand[s] ? "an" : ""} ${ein ? "ein" : ""}"></i></td>
      <td><b>${NAME[s]}</b><small><span>${ein ? "Eingang" : "Ausgang"}</span> · <span>${WAS[s]}</span></small></td>
      <td>${tr === "modbus"
        ? `<input class="eingabe eio-feld" data-eio="adr" data-signal="${s}" type="number" min="0" value="${(mb.adressen || {})[s] ?? ""}" title="${ein ? "Discrete Input" : "Coil"}">`
        : `<input class="eingabe eio-feld" data-eio="pin" data-signal="${s}" type="number" min="0" max="27" value="${(c.pins || {})[s] ?? ""}" title="GPIO (BCM)">`}</td>
      <td><label class="eio-inv"><input type="checkbox" data-eio="inv" data-signal="${s}" ${(c.invertiert || {})[s] ? "checked" : ""}> invertiert</label></td>
      <td><button class="mini" data-tat="eaio_test" data-signal="${s}">${ein ? "Auslösen" : "Test 1 s"}</button></td></tr>`;
  const P = ((Z.bereich || {}).pruef) || {};
  return `<h3>Ein-/Ausgänge</h3>
    <div class="e-zeile"><div><b>Treiber</b><span>${E.simuliert
        ? (E.fehler ? `Simulation — ${txt(E.fehler)}` : "Simulation: keine Hardware angesprochen, alles hier sichtbar")
        : (tr === "gpio" ? "GPIO aktiv (gpiozero)" : `Modbus TCP aktiv · ${txt(mb.host || "")}:${mb.port}`)}</span></div>
      <div class="e-wahl">${eWahl("eaio_treiber", "sim", tr === "sim", "Simulation")}${eWahl("eaio_treiber", "gpio", tr === "gpio", "GPIO")}${eWahl("eaio_treiber", "modbus", tr === "modbus", "Modbus TCP")}</div></div>
    ${tr === "modbus" ? `<div class="e-zeile eio-mb"><div><b>Modbus-Gerät</b><span>I/O-Modul im Netz: Coils = Ausgänge, Discrete Inputs = Eingänge</span></div>
      <div class="e-wahl"><input class="eingabe" data-eio="host" value="${txt(mb.host || "")}" placeholder="IP-Adresse" style="width:140px">
        <input class="eingabe" data-eio="port" type="number" value="${mb.port || 502}" style="width:72px" title="Port">
        <input class="eingabe" data-eio="einheit" type="number" value="${mb.einheit || 1}" style="width:56px" title="Unit-ID"></div></div>` : ""}
    <table class="eio-tab"><thead><tr><th></th><th>Signal</th><th>${tr === "modbus" ? "Adresse" : "GPIO"}</th><th></th><th></th></tr></thead>
      <tbody>${E.eingaenge.map(s => zeile(s, true)).join("")}${E.ausgaenge.map(s => zeile(s, false)).join("")}</tbody></table>
    <div class="e-zeile"><div><b>OK / NOK</b><span>Puls: kurz an · Halten: bis zur nächsten Prüfung</span></div>
      <div class="e-wahl">${eWahl("eaio_modus", "puls", c.modus === "puls", "Puls")}${eWahl("eaio_modus", "halten", c.modus === "halten", "Halten")}
        <input class="eingabe" data-eio="puls_ms" type="number" min="20" max="5000" value="${c.puls_ms}" style="width:76px" title="Pulslänge in ms"> ms</div></div>
    <div class="knopfreihe" style="margin:10px 0"><button class="mini an" data-tat="eaio_uebernehmen">Belegung übernehmen</button></div>
    ${STATIONAER() ? `<div class="e-hinweis">Der Trigger löst nur aus, wenn der Prüf-Auslöser auf Extern steht.
      ${P.ausloeser !== "extern" ? `<button class="lu-link" data-tat="pruef_ausloeser" data-wert="extern">Auf Extern stellen</button>` : ""}</div>`
      : `<div class="e-hinweis">Linienbetrieb: OK/NOK je gebuchtem Teil; der Trigger-Eingang wird hier nicht gebraucht (die Linie hat eigene Sensorik).</div>`}
    <div class="e-erkl"><b>Anschluss:</b> Pi-GPIO verträgt nur 3,3 V — 24-V-Signale immer über Optokoppler, Lasten über Relais oder Transistor.
      GPIO 18 (Bandrelais), I²C (2/3) und 0/1 sind gesperrt. Nichts hiervon ist eine Sicherheitsfunktion (SAFETY.md).</div>
    <h4>Zuletzt</h4><div class="eio-log">${(E.ereignisse || []).length ? E.ereignisse.map(e => `<div><span>${txt(e.zeit)}</span>${txt(e.text)}</div>`).join("") : '<div class="leise">noch nichts</div>'}</div>`;
}
function eaioFormular() {
  const box = $("eInhalt"), c = {}; if (!box) return c;
  const q = sel => [...box.querySelectorAll(sel)];
  const pins = {}, adr = {}, inv = {};
  q('[data-eio="pin"]').forEach(i => { pins[i.dataset.signal] = i.value === "" ? null : +i.value; });
  q('[data-eio="adr"]').forEach(i => { adr[i.dataset.signal] = +i.value || 0; });
  q('[data-eio="inv"]').forEach(i => { inv[i.dataset.signal] = i.checked; });
  if (Object.keys(pins).length) c.pins = pins;
  c.invertiert = inv;
  const m = {}; const v = k => { const e = box.querySelector(`[data-eio="${k}"]`); return e ? e.value : null; };
  if (v("host") != null) { m.host = v("host"); m.port = +v("port") || 502; m.einheit = +v("einheit") || 1; }
  if (Object.keys(adr).length) m.adressen = adr;
  if (Object.keys(m).length) c.modbus = m;
  if (v("puls_ms") != null) c.puls_ms = +v("puls_ms") || 200;
  return c;
}
async function eaioSenden(extra) {
  try { EAIO = await hole("/api/eaio", Object.assign({ aktion: "einstellen" }, eaioFormular(), extra || {})); } catch (e) {}
  if (EAIO && EAIO.ok === false) { MELDUNG = EAIO.grund; setTimeout(() => { MELDUNG = ""; }, 4000); }
  zeichneEinstellungen();
}
function inhaltAbschnitt() {''')
    h = ers(h, '''  if (tat === "sprache_setzen") {''', '''  if (tat === "eaio_treiber") { return eaioSenden({ treiber: el.dataset.wert }); }
  if (tat === "eaio_modus") { return eaioSenden({ modus: el.dataset.wert }); }
  if (tat === "eaio_uebernehmen") { return eaioSenden({}); }
  if (tat === "eaio_test") {
    try { EAIO = await hole("/api/eaio", { aktion: "test", signal: el.dataset.signal }); } catch (e) {}
    zeichneEinstellungen(); setTimeout(eaioLaden, 1100); return;
  }
  if (tat === "sprache_setzen") {''')
    # Ausloeser Extern: Kachel + Allgemein
    h = ers(h, '''        <button data-tat="pruef_ausloeser" data-wert="auto" class="${auto ? "an" : ""}">Auto</button>''',
            '''        <button data-tat="pruef_ausloeser" data-wert="auto" class="${auto ? "an" : ""}">Auto</button>
        <button data-tat="pruef_ausloeser" data-wert="extern" class="${P.ausloeser === "extern" ? "an" : ""}" title="Extern: Trigger-Eingang (Lichtschranke/SPS) löst aus — siehe Einstellungen › Ein-/Ausgänge">Extern</button>''')
    h = ers(h, '''        <button data-tat="pruef_ausloeser" data-wert="hand" class="${auto ? "" : "an"}">Hand</button>''',
            '''        <button data-tat="pruef_ausloeser" data-wert="hand" class="${!auto && P.ausloeser !== "extern" ? "an" : ""}">Hand</button>''')
    h = ers(h, '''      <div class="e-wahl">${eWahl("pruef_ausloeser", "hand", P.ausloeser !== "auto", "Hand")}${eWahl("pruef_ausloeser", "auto", P.ausloeser === "auto", "Auto")}</div></div>` : ""}''',
            '''      <div class="e-wahl">${eWahl("pruef_ausloeser", "hand", !P.ausloeser || P.ausloeser === "hand", "Hand")}${eWahl("pruef_ausloeser", "auto", P.ausloeser === "auto", "Auto")}${eWahl("pruef_ausloeser", "extern", P.ausloeser === "extern", "Extern")}</div></div>` : ""}''')
    h = ers(h, '''/* Kamera-Dock (1.9.52) */''', '''/* EAIO (1.9.59) */
.eio-tab { width:100%; border-collapse:collapse; margin:8px 0 4px; font-size:12.5px; }
.eio-tab th { text-align:left; font-size:10.5px; letter-spacing:.1em; text-transform:uppercase; color:var(--leise,#8a94a0); font-weight:700; padding:4px 6px; }
.eio-tab td { padding:7px 6px; border-top:1px solid var(--rand,#333b43); vertical-align:middle; }
.eio-tab td b { display:block; color:var(--text); } .eio-tab td small { display:block; color:var(--leise,#8a94a0); font-size:11px; }
.eio-tab .eio-feld { width:70px; }
.eio-lampe { display:inline-block; width:14px; height:14px; border-radius:50%; background:#2a343d; border:1px solid #445; }
.eio-lampe.an { background:var(--gut,#22c55e); box-shadow:0 0 8px var(--gut,#22c55e); border-color:var(--gut,#22c55e); }
.eio-lampe.ein.an { background:var(--akzent,#49e7ff); box-shadow:0 0 8px var(--akzent,#49e7ff); border-color:var(--akzent,#49e7ff); }
.eio-inv { font-size:11.5px; color:var(--leise,#8a94a0); white-space:nowrap; }
.eio-log { font:12px ui-monospace,Consolas,monospace; color:var(--leise,#8a94a0); display:grid; gap:2px; max-height:150px; overflow:auto; }
.eio-log span { color:var(--text); margin-right:10px; }
/* Kamera-Dock (1.9.52) */''')
    H.write_text(h, encoding="utf-8")
    print("index.html gepatcht")

d = D.read_text(encoding="utf-8")
if "Nachtrag 14" not in d:
    d = ers(d, '\nif (window.spracheNachladen) window.spracheNachladen();\n', '''
/* ---- Nachtrag 14 (1.9.59 Ein-/Ausgaenge) ---- */
Object.assign(window.SPRACHEN.en, {
  "Ein-/Ausgänge": "I/O", "Wird geladen …": "Loading …", "Treiber": "Driver", "Simulation": "Simulation", "GPIO": "GPIO", "Modbus TCP": "Modbus TCP",
  "Simulation: keine Hardware angesprochen, alles hier sichtbar": "Simulation: no hardware addressed, everything visible here",
  "Simulation — {}": "Simulation — {}", "GPIO aktiv (gpiozero)": "GPIO active (gpiozero)",
  "Modbus-Gerät": "Modbus device", "I/O-Modul im Netz: Coils = Ausgänge, Discrete Inputs = Eingänge": "Network I/O module: coils = outputs, discrete inputs = inputs",
  "IP-Adresse": "IP address", "Signal": "Signal", "Adresse": "Address", "Eingang": "Input", "Ausgang": "Output",
  "Trigger": "Trigger", "Bereit": "Ready", "OK": "OK", "NOK": "NOK", "Fehler": "Fault",
  "steigende Flanke löst eine Prüfung aus": "rising edge triggers an inspection", "Anlage bereit, keine Störung": "cell ready, no fault",
  "nach der Prüfung: alles gut": "after inspection: all good", "nach der Prüfung: unbekannt, Ausschuss oder kein Teil": "after inspection: unknown, reject or no part",
  "aktive Störung": "active fault", "invertiert": "inverted", "Auslösen": "Fire", "Test 1 s": "Test 1 s",
  "Eingang · {}": "Input · {}", "Ausgang · {}": "Output · {}",
  "OK / NOK": "OK / NOK", "Puls: kurz an · Halten: bis zur nächsten Prüfung": "Pulse: briefly on · Hold: until the next inspection",
  "Puls": "Pulse", "Halten": "Hold", "Pulslänge in ms": "Pulse length in ms", "Belegung übernehmen": "Apply mapping",
  "Der Trigger löst nur aus, wenn der Prüf-Auslöser auf Extern steht.": "The trigger only fires when the inspection trigger is set to External.", "Extern": "External",
  "Auf Extern stellen": "Set to external",
  "Linienbetrieb: OK/NOK je gebuchtem Teil; der Trigger-Eingang wird hier nicht gebraucht (die Linie hat eigene Sensorik).": "Line mode: OK/NOK per logged part; the trigger input is not needed here (the line has its own sensing).",
  "Anschluss:": "Wiring:",
  "Pi-GPIO verträgt nur 3,3 V — 24-V-Signale immer über Optokoppler, Lasten über Relais oder Transistor. GPIO 18 (Bandrelais), I²C (2/3) und 0/1 sind gesperrt. Nichts hiervon ist eine Sicherheitsfunktion (SAFETY.md).": "Pi GPIO tolerates only 3.3 V — always route 24 V signals through optocouplers, loads through relays or transistors. GPIO 18 (belt relay), I²C (2/3) and 0/1 are blocked. None of this is a safety function (SAFETY.md).",
  "Zuletzt": "Recent", "noch nichts": "nothing yet",
  "Extern: Trigger-Eingang (Lichtschranke/SPS) löst aus — siehe Einstellungen › Ein-/Ausgänge": "External: trigger input (light barrier/PLC) fires — see Settings › I/O"
});

if (window.spracheNachladen) window.spracheNachladen();
''')
    D.write_text(d, encoding="utf-8")
    print("sprache_en.js: Nachtrag 14")
