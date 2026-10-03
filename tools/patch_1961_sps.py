#!/usr/bin/env python3
"""1.9.61 — Industrie-Paket I2: SPS-Anbindung per Modbus TCP (vorsa/sps.py).

SE Inspect als Modbus-Server: Ergebnis, Zähler, Status in Registern; Befehle
Prüfen / Zähler zurücksetzen / Prüfprogramm Nr. laden. Standard AUS, Port 1502,
"nur lesen" möglich. Einstellungen › SPS (Admin): Ein/Aus, Port, Live-Register,
Programmnummern. /api/sps (GET Zustand, POST einstellen).
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
if '"/api/sps"' not in r:
    r = ers(r, '''    "/api/rollen", "/api/eaio",''', '''    "/api/rollen", "/api/eaio", "/api/sps",''')
    R.write_text(r, encoding="utf-8")
    print("rollen.py: /api/sps nur Admin")

s = S.read_text(encoding="utf-8")
if "SpsServer" in s:
    print("server.py: schon gepatcht")
else:
    s = ers(s, 'BUILD = "1.9.60-rollen"', 'BUILD = "1.9.61-sps"')
    # Linie: Wrapper unabhaengig von eaio, meldet an E/A UND SPS
    s = ers(s, '''        if self.profil == "linie" and self.eaio is not None:
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
''', '''        # SPS-ANBINDUNG (I2, 1.9.61): Modbus-TCP-Server, Standard aus.
        self._sps_letzt = {"urteil": "", "objekt_id": -1, "konfidenz": 0.0, "teile": 0}
        self._sps_seq = 0
        try:
            from ..sps import SpsServer
            self.sps = SpsServer(self._sps_stand, self._sps_befehl)
            c = self._sps_cfg()
            if c.get("an"):
                f = self.sps.starten(int(c.get("port", 1502)), bool(c.get("nur_lesen")))
                print(f"  SPS/Modbus: {'Port ' + str(self.sps.port) if not f else f}", flush=True)
        except Exception as exc:
            print(f"  SPS nicht verfuegbar: {exc}", flush=True)
            self.sps = None
        if self.profil == "linie":
            # Linie: jedes gebuchte Teil meldet OK/NOK an Ein-/Ausgaenge und
            # SPS - eine Stelle, linie.py bleibt unangetastet.
            _buche = self.pruefbuch.buche

            def _buche_mit_ausgang(urteil, name="", konf=0.0, *a, **k):
                e = _buche(urteil, name, konf, *a, **k)
                try:
                    if self.eaio is not None:
                        self.eaio.ergebnis(str(urteil))
                    self._sps_merken(str(urteil), str(name or ""), float(konf or 0), 1)
                except Exception:
                    pass
                return e
            self.pruefbuch.buche = _buche_mit_ausgang
''')
    s = ers(s, '''    def _eaio_trigger(self) -> None:''', '''    # ---- SPS (I2) -------------------------------------------------------
    def _sps_cfg_pfad(self):
        try:
            return Path(self.zustand.ordner) / "sps.json"
        except Exception:
            return None

    def _sps_cfg(self) -> dict:
        p = self._sps_cfg_pfad()
        try:
            if p and p.exists():
                return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
        return {"an": False, "port": 1502, "nur_lesen": False}

    def sps_einstellen(self, k: dict) -> dict:
        c = self._sps_cfg()
        if "an" in k:
            c["an"] = bool(k["an"])
        if "port" in k:
            c["port"] = max(1, min(65535, int(k["port"])))
        if "nur_lesen" in k:
            c["nur_lesen"] = bool(k["nur_lesen"])
        p = self._sps_cfg_pfad()
        try:
            if p:
                p.write_text(json.dumps(c), encoding="utf-8")
        except Exception:
            pass
        f = ""
        if self.sps is not None:
            if c["an"]:
                f = self.sps.starten(c["port"], c["nur_lesen"])
            else:
                self.sps.stoppen()
        return {"ok": not f, "grund": f, **self.sps_status()}

    def _sps_programme(self) -> list:
        rb = getattr(self, "rezeptbuch", None)
        if rb is None:
            return []
        try:
            return sorted((rb.uebersicht().get("rezepte") or {}).keys(), key=str.casefold)
        except Exception:
            return []

    def _sps_merken(self, urteil: str, name: str, konf: float, teile: int) -> None:
        oid = -1
        try:
            for k in self.zustand.klassen.values():
                if k.name == name:
                    oid = int(k.id)
                    break
        except Exception:
            pass
        self._sps_seq = (self._sps_seq + 1) & 0xFFFF
        self._sps_letzt = {"urteil": urteil, "objekt_id": oid, "konfidenz": konf, "teile": teile, "name": name}

    def _sps_stand(self) -> dict:
        st = {}
        try:
            st = self.pruefbuch.statistik()
        except Exception:
            pass
        al = getattr(self, "_alarm_stand", None) or {}
        rb = getattr(self, "rezeptbuch", None)
        aktiv = rb.aktiv_name() if rb else ""
        prog = self._sps_programme()
        return {**self._sps_letzt,
                "bereit": str(self.zustand.betriebsart) == "betreiben" and not al.get("aktiv_alarm"),
                "laeuft": bool(getattr(self, "_pruef_anfrage", False)),
                "stoerung": bool(al.get("aktiv_alarm")),
                "simuliert": not bool((getattr(self.zustand, "hardware", {}) or {}).get("geraet")),
                "gesamt": st.get("gesamt", 0), "gut": st.get("gut", 0),
                "unbekannt": st.get("unbekannt", 0), "ausschuss": st.get("ausschuss", 0),
                "programm": (prog.index(aktiv) + 1) if aktiv in prog else 0,
                "sequenz": self._sps_seq}

    def _sps_befehl(self, art: str, wert: int) -> str:
        if art == "pruefen":
            if self.profil != "stationaer":
                return "abgewiesen: Pruefen per SPS nur stationaer"
            if str(self.zustand.betriebsart) != "betreiben":
                return "abgewiesen: nicht im Pruefen"
            self._pruef_anfrage_grund = "sps"
            self._pruef_anfrage = True
            return "Pruefung ausgeloest"
        if art == "zaehler_reset":
            self.pruefbuch.reset()
            return "Zaehler zurueckgesetzt"
        if art == "programm":
            prog = self._sps_programme()
            if not 1 <= int(wert) <= len(prog):
                return f"abgewiesen: Programm {wert} gibt es nicht (1-{len(prog)})"
            name = prog[int(wert) - 1]
            threading.Thread(target=lambda: self.rezeptbuch.anwenden(name, self, self.zustand),
                             daemon=True).start()
            try:
                self.rollen and self.rollen.protokoll("sps", "/sps/programm", {"name": name})
            except Exception:
                pass
            return f"Programm {wert} ({name}) wird geladen"
        return "unbekannt"

    def sps_status(self) -> dict:
        c = self._sps_cfg()
        st = self.sps.status() if self.sps is not None else {"aktiv": False, "fehler": "nicht verfuegbar"}
        reg = []
        try:
            reg = self.sps.register() if self.sps is not None else []
        except Exception:
            pass
        return {"cfg": c, **st, "register": reg, "programme": self._sps_programme(),
                "letzt": dict(self._sps_letzt)}

    def _eaio_trigger(self) -> None:''')
    # stationaer: Ergebnis merken
    s = ers(s, '''        try:
            if self.eaio is not None:
                self.eaio.ergebnis(gesamt)
        except Exception:
            pass
        return {"ok": True, "urteil": gesamt, "teile": teile}''', '''        try:
            if self.eaio is not None:
                self.eaio.ergebnis(gesamt)
            t0 = teile[0] if teile else {}
            self._sps_merken(gesamt, str(t0.get("name") or ""), float(t0.get("konfidenz") or 0), len(teile))
        except Exception:
            pass
        return {"ok": True, "urteil": gesamt, "teile": teile}''')
    s = ers(s, '''            if grund == "extern" and not self._pruef_antwort.get("ok"):
                # Trigger ohne Teil: die SPS wartet auf eine Antwort -> NOK.
                try:
                    self.eaio.ergebnis("leer")
                except Exception:
                    pass''', '''            if grund in ("extern", "sps") and not self._pruef_antwort.get("ok"):
                # Trigger ohne Teil: die SPS wartet auf eine Antwort -> NOK.
                try:
                    if self.eaio is not None:
                        self.eaio.ergebnis("leer")
                    self._sps_merken("leer", "", 0.0, 0)
                except Exception:
                    pass''')
    s = ers(s, '''            if weg == "/api/rollen":
                r = getattr(verarbeitung, "rollen", None)
                if r is None:''', '''            if weg == "/api/sps":
                return self._json(verarbeitung.sps_status())

            if weg == "/api/rollen":
                r = getattr(verarbeitung, "rollen", None)
                if r is None:''')
    s = ers(s, '''            if weg in ("/api/anmelden", "/api/abmelden", "/api/rollen"):''', '''            if weg == "/api/sps":
                return self._json(verarbeitung.sps_einstellen(koerper))

            if weg in ("/api/anmelden", "/api/abmelden", "/api/rollen"):''')
    S.write_text(s, encoding="utf-8")
    print("server.py gepatcht")

h = H.read_text(encoding="utf-8")
if "SPS (1.9.61)" in h:
    print("index.html: schon gepatcht")
else:
    h = ers(h, '''["eaio", "Ein-/Ausgänge"], ["benutzer", "Benutzer"],''', '''["eaio", "Ein-/Ausgänge"], ["sps", "SPS / Modbus"], ["benutzer", "Benutzer"],''')
    h = ers(h, '''  if (ABSCHNITT === "benutzer") return abschnittBenutzer();''', '''  if (ABSCHNITT === "benutzer") return abschnittBenutzer();
  if (ABSCHNITT === "sps") return abschnittSps();''')
    h = ers(h, '''let ROLLE_GELADEN = 0;''', '''/* SPS (1.9.61): Modbus-TCP-Server - Schalter, Live-Register, Programmnummern. */
let SPS = null, SPS_GELADEN = 0;
async function spsLaden() { try { SPS = await hole("/api/sps"); } catch (e) {} if (ABSCHNITT === "sps") zeichneEinstellungen(); }
function abschnittSps() {
  if (Date.now() - SPS_GELADEN > 1000) { SPS_GELADEN = Date.now(); spsLaden(); }
  const S = SPS;
  if (!S || !S.cfg) return `<h3>SPS / Modbus</h3><div class="e-hinweis">Wird geladen …</div>`;
  const c = S.cfg, reg = S.register || [];
  const NAMEN = ["Status-Bits", "Urteil (1 gut · 2 unbek. · 3 Aussch. · 4 leer)", "Objekt-ID + 1", "Konfidenz ‰", "Teile", "Zähler gesamt (low)",
    "Zähler gesamt (high)", "gut", "unbekannt", "Ausschuss", "Programm-Nr.", "Lebenszähler", "Ergebnis-Sequenz"];
  return `<h3>SPS / Modbus</h3>
    <div class="e-hinweis">SE Inspect als Modbus-TCP-Server: die SPS liest Ergebnis und Zähler und schreibt Befehle. Modbus hat keine Anmeldung — nur im abgeschotteten Maschinennetz einschalten.</div>
    <div class="e-zeile"><div><b>Modbus-Server</b><span>${S.aktiv ? `läuft auf Port ${S.port} · ${S.verbindungen} Verbindungen · ${S.anfragen} Anfragen` : (S.fehler ? txt(S.fehler) : "aus")}</span></div>
      <div class="e-wahl">${eWahl("sps_an", "1", c.an, "An")}${eWahl("sps_an", "0", !c.an, "Aus")}</div></div>
    <div class="e-zeile"><div><b>Port und Schreibrecht</b><span>1502 braucht keine Root-Rechte · „nur lesen“ sperrt Befehle der SPS</span></div>
      <div class="e-wahl"><input class="eingabe" data-sps="port" type="number" min="1" max="65535" value="${c.port || 1502}" style="width:84px">
        ${eWahl("sps_lesen", "0", !c.nur_lesen, "lesen + schreiben")}${eWahl("sps_lesen", "1", !!c.nur_lesen, "nur lesen")}
        <button class="mini" data-tat="sps_port">Übernehmen</button></div></div>
    ${S.letzter_befehl ? `<div class="e-hinweis">Letzter Befehl der SPS: ${txt(S.letzter_befehl)}</div>` : ""}
    <h4>Eingangsregister (FC 4 · gespiegelt ab Halteregister 100)</h4>
    <table class="eio-tab"><thead><tr><th>Adr.</th><th>Inhalt</th><th>Wert</th></tr></thead><tbody>
      ${NAMEN.map((n, i) => `<tr><td>${i}</td><td>${n}</td><td><b>${reg[i] != null ? (i === 0 ? reg[i].toString(2).padStart(6, "0") : reg[i]) : "–"}</b></td></tr>`).join("")}
    </tbody></table>
    <div class="e-erkl"><b>Befehle:</b> Halteregister 0 ← 1 = Prüfung auslösen, 2 = Zähler zurücksetzen · Halteregister 1 ← Programm-Nr. laden · Coil 0 ← 1 = Prüfung auslösen.
      Status-Bits: b0 bereit · b1 Prüfung läuft · b2 Störung · b3 letzte OK · b4 letzte NOK · b5 ohne Chip (simuliert). Neue Ergebnisse erkennt die SPS an der Ergebnis-Sequenz.</div>
    <h4>Programmnummern</h4>
    <div class="eio-log">${(S.programme || []).length ? S.programme.map((n, i) => `<div><span>${i + 1}</span>${txt(n)}</div>`).join("") : '<div class="leise">noch keine Prüfprogramme</div>'}</div>`;
}
let ROLLE_GELADEN = 0;''')
    h = ers(h, '''  if (tat === "anmelden") { return anmelden(); }''', '''  if (tat === "anmelden") { return anmelden(); }
  if (tat === "sps_an" || tat === "sps_lesen" || tat === "sps_port") {
    const k = {};
    if (tat === "sps_an") k.an = el.dataset.wert === "1";
    if (tat === "sps_lesen") k.nur_lesen = el.dataset.wert === "1";
    const p = $("eInhalt").querySelector('[data-sps="port"]'); if (p) k.port = +p.value || 1502;
    const r = await hole("/api/sps", k);
    if (r && r.ok === false && r.grund) { MELDUNG = r.grund; setTimeout(() => { MELDUNG = ""; }, 4000); }
    SPS = r; zeichneEinstellungen(); return;
  }''')
    H.write_text(h, encoding="utf-8")
    print("index.html gepatcht")

d = D.read_text(encoding="utf-8")
if "Nachtrag 16" not in d:
    d = ers(d, '\nif (window.spracheNachladen) window.spracheNachladen();\n', '''
/* ---- Nachtrag 16 (1.9.61 SPS) ---- */
Object.assign(window.SPRACHEN.en, {
  "SPS / Modbus": "PLC / Modbus", "Modbus-Server": "Modbus server",
  "SE Inspect als Modbus-TCP-Server: die SPS liest Ergebnis und Zähler und schreibt Befehle. Modbus hat keine Anmeldung — nur im abgeschotteten Maschinennetz einschalten.": "SE Inspect as a Modbus TCP server: the PLC reads results and counters and writes commands. Modbus has no authentication — only enable it on an isolated machine network.",
  "läuft auf Port {} · {} Verbindungen · {} Anfragen": "running on port {} · {} connections · {} requests", "aus": "off",
  "Port und Schreibrecht": "Port and write access", "1502 braucht keine Root-Rechte · „nur lesen“ sperrt Befehle der SPS": "1502 needs no root rights · “read only” blocks PLC commands",
  "lesen + schreiben": "read + write", "nur lesen": "read only", "Übernehmen": "Apply", "Letzter Befehl der SPS: {}": "Last PLC command: {}",
  "Eingangsregister (FC 4 · gespiegelt ab Halteregister 100)": "Input registers (FC 4 · mirrored from holding register 100)",
  "Adr.": "Addr.", "Inhalt": "Content", "Wert": "Value", "Status-Bits": "Status bits", "Urteil (1 gut · 2 unbek. · 3 Aussch. · 4 leer)": "Verdict (1 good · 2 unknown · 3 reject · 4 empty)",
  "Objekt-ID + 1": "Object ID + 1", "Konfidenz ‰": "Confidence ‰", "Teile": "Parts", "Zähler gesamt (low)": "Total counter (low)", "Zähler gesamt (high)": "Total counter (high)",
  "gut": "good", "unbekannt": "unknown", "Ausschuss": "Reject", "Programm-Nr.": "Job no.", "Lebenszähler": "Heartbeat", "Ergebnis-Sequenz": "Result sequence",
  "Befehle:": "Commands:",
  "Halteregister 0 ← 1 = Prüfung auslösen, 2 = Zähler zurücksetzen · Halteregister 1 ← Programm-Nr. laden · Coil 0 ← 1 = Prüfung auslösen. Status-Bits: b0 bereit · b1 Prüfung läuft · b2 Störung · b3 letzte OK · b4 letzte NOK · b5 ohne Chip (simuliert). Neue Ergebnisse erkennt die SPS an der Ergebnis-Sequenz.": "Holding register 0 ← 1 = trigger inspection, 2 = reset counters · holding register 1 ← load job no. · coil 0 ← 1 = trigger inspection. Status bits: b0 ready · b1 inspecting · b2 fault · b3 last OK · b4 last NOK · b5 no chip (simulated). The PLC detects new results by the result sequence.",
  "Programmnummern": "Job numbers", "noch keine Prüfprogramme": "no jobs yet"
});

if (window.spracheNachladen) window.spracheNachladen();
''')
    D.write_text(d, encoding="utf-8")
    print("sprache_en.js: Nachtrag 16")
