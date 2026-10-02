#!/usr/bin/env python3
"""A6 — Testsatz-Werkzeug (Build 1.9.45).

server.py: Testsatz-Ablage, /api/testsatz (aufnehmen/liste/loeschen/soll),
/api/testsatz_bild, Stand in bereich.pruef.testsatz, letzter roher
Ausschnitt fuer die Aufnahme. index.html: Block "Testsatz" in der
Pruef-Kachel (stationaer). Exakte Ersetzungen, idempotent.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
S = ROOT / "vorsa" / "web" / "server.py"
H = ROOT / "vorsa" / "web" / "static" / "index.html"


def ers(t, a, n, k=1):
    if t.count(a) != k:
        raise SystemExit(f"FEHLER: {t.count(a)}x statt {k}x: {a[:160]}")
    return t.replace(a, n)


E = ROOT / "vorsa" / "edge_learn.py"
el = E.read_text(encoding="utf-8")
if '"verbund_modus": self.verbund_modus' not in el:
    el = ers(el, '''            "klassen": self.klassen,
            "groesse": self.groesse,
            "faktor": self._faktor,
            "formbild": self.formbild,
            "modus": self.modus,
''', '''            "klassen": self.klassen,
            "groesse": self.groesse,
            "faktor": self._faktor,
            "formbild": self.formbild,
            "modus": self.modus,
            "verbund_modus": self.verbund_modus,
''')
    el = ers(el, '''            self.neuron_karte = dict(begleit.get("neuron_karte") or {})''', '''            self.neuron_karte = dict(begleit.get("neuron_karte") or {})
            if begleit.get("verbund_modus") in ("repliziert", "verteilt"):
                self.verbund_modus = begleit["verbund_modus"]''')
    E.write_text(el, encoding="utf-8"); print("edge_learn.py gepatcht (verbund_modus sichern)")

srv = S.read_text(encoding="utf-8")
if "1.9.45-testsatz" in srv:
    print("server.py: schon gepatcht")
else:
    srv = ers(srv, 'BUILD = "1.9.44-cpu-ersatz"', 'BUILD = "1.9.45-testsatz"')
    srv = ers(srv, '''        self._pruef_anfrage = False       # /api/pruefen wartet auf den Takt
''', '''        self._pruef_anfrage = False       # /api/pruefen wartet auf den Takt
        # TESTSATZ (A6, 1.9.45): Pruefszenen mit Soll-Werten fuer die
        # Qualitaetsziele; Aufnahme nimmt den ROHEN Ausschnitt (vor dem
        # Mehrbild-Mittel), damit die Auswertung dieselbe Kette durchlaeuft.
        from ..testsatz import Testsatz
        try:
            self.testsatz = Testsatz(zustand.ordner)
        except Exception:
            self.testsatz = None
        self._roh_ausschnitt = None
''')
    srv = ers(srv, '''            ausschnitt = frame[y:y + seite, x:x + seite].copy()
            n = 0
            # MEHRBILD (A2): nur stationaer und nur beim Betreiben - die''', '''            ausschnitt = frame[y:y + seite, x:x + seite].copy()
            n = 0
            self._roh_ausschnitt = ausschnitt
            # MEHRBILD (A2): nur stationaer und nur beim Betreiben - die''')
    srv = ers(srv, '''                ps["letzte_pruefung"] = self._pruef_letzte''', '''                ps["letzte_pruefung"] = self._pruef_letzte
                if self.testsatz is not None:
                    ps["testsatz"] = self.testsatz.uebersicht()''')
    srv = ers(srv, '''    def pruefen_jetzt(self) -> dict:''', '''    def testsatz_aufnehmen(self, soll, notiz: str = "") -> dict:
        """Aktuelle Szene in den Testsatz: rohes Bild + Soll + Ist."""
        if self.testsatz is None:
            return {"ok": False, "grund": "kein Testsatz-Ordner"}
        bild = self._roh_ausschnitt
        if bild is None:
            return {"ok": False, "grund": "kein Bild"}
        erk = self.zustand.erkannt or {}
        return self.testsatz.aufnehmen(bild.copy(), list(soll or []), notiz,
                                       ist=list(erk.get("je_objekt") or []))

    def pruefen_jetzt(self) -> dict:''')
    srv = ers(srv, '''            if weg == "/api/pruefen":
                # STATIONAER (1.9.38): Szene jetzt pruefen und buchen.
                return self._json(verarbeitung.pruefen_jetzt())
''', '''            if weg == "/api/pruefen":
                # STATIONAER (1.9.38): Szene jetzt pruefen und buchen.
                return self._json(verarbeitung.pruefen_jetzt())

            if weg == "/api/testsatz":
                # TESTSATZ (A6): {tat: aufnehmen|liste|loeschen|soll, ...}
                ts = verarbeitung.testsatz
                if ts is None:
                    return self._json({"ok": False, "grund": "kein Testsatz"}, 503)
                tat = str(koerper.get("tat", "liste"))
                if tat == "aufnehmen":
                    return self._json(verarbeitung.testsatz_aufnehmen(
                        koerper.get("soll") or [], str(koerper.get("notiz", ""))))
                if tat == "loeschen":
                    return self._json(ts.loeschen(int(koerper.get("id", -1))))
                if tat == "soll":
                    return self._json(ts.soll_aendern(int(koerper.get("id", -1)),
                                                      koerper.get("soll") or [],
                                                      koerper.get("notiz")))
                return self._json({"ok": True, "szenen": ts.szenen,
                                   "uebersicht": ts.uebersicht()})
''')
    srv = ers(srv, '''            if weg == "/api/pruef_bild":''', '''            if weg == "/api/testsatz_bild":
                datei = (frage.get("datei") or [""])[0]
                ts = verarbeitung.testsatz
                b = ts.bild(datei) if (ts is not None and datei) else None
                return self._bytes(b or b"", "image/jpeg", 200 if b else 404)

            if weg == "/api/pruef_bild":''')
    S.write_text(srv, encoding="utf-8")
    print("server.py gepatcht")

h = H.read_text(encoding="utf-8")
if 'data-tat="testsatz_aufnehmen"' in h:
    print("index.html: schon gepatcht")
else:
    # Block nach den Pruefparametern (nur stationaer)
    h = ers(h, '''    </div></details>
    ${P.nachlernen ? `<div class="pu-nachlernen">''', '''    </div></details>
    ${P.nachlernen ? `<div class="pu-nachlernen">''')
    h = ers(h, '''/* STATIONAERE PRUEFUNG (1.9.38): Knopf / Leertaste -> /api/pruefen. */''', '''/* TESTSATZ (A6, 1.9.45): Pruefszenen mit Soll-Werten sammeln. */
let TS_SOLL = [];                 // gewaehlte Soll-Klassen fuer die naechste Szene
function testsatzBlock(P) {
  const T = P.testsatz || { anzahl: 0, leer: 0, einzeln: 0, mehrere: 0, klassen: {}, letzte: [] };
  const ks = (Z.klassen || []).filter(k => !k.negativ);
  const chips = ks.map(k => {
    const n = TS_SOLL.filter(x => x === k.name).length;
    return `<button class="mini ts-chip ${n ? "an" : ""}" data-tat="ts_soll" data-name="${txt(k.name)}"
      title="Klick: einmal dazu · Rechtsklick / Umschalt-Klick: eins weniger">${txt(k.name)}${n > 1 ? ` ×${n}` : ""}</button>`;
  }).join("");
  const zeit = t => new Date(t * 1000).toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" });
  return `<details class="ops-details" data-ops-disclosure="testsatz" ${OPS_OPEN.has("testsatz") ? "open" : ""}>
    <summary>Testsatz · ${T.anzahl} Szenen</summary><div class="ops-detail-content">
    <p class="ops-count-note">Szene mit Soll-Wert ablegen; der Testsatz misst später Trefferquote, Unbekannt- und Falsch-sicher-Rate. Er wird nicht zum Lernen benutzt.</p>
    <div class="ts-chips">${chips || '<span class="leise">Erst Objekte anlegen.</span>'}
      <button class="mini ts-chip ${TS_SOLL.length ? "" : "an"}" data-tat="ts_leer" title="Nichts liegt im Bild">leer</button></div>
    <div class="pu-knoepfe">
      <button data-tat="testsatz_aufnehmen" class="an" title="Aktuelles Bild mit diesem Soll in den Testsatz">Szene aufnehmen</button>
      <span class="leise" style="font-size:10px;align-self:center">Soll: ${TS_SOLL.length ? TS_SOLL.map(txt).join(" + ") : "leer"}</span>
    </div>
    <div class="pu-stat" style="margin-top:8px">
      <div><span>Einzeln</span><b>${T.einzeln}</b></div><div><span>Mehrere</span><b>${T.mehrere}</b></div>
      <div><span>Leer</span><b>${T.leer}</b></div><div><span>Gesamt</span><b>${T.anzahl}</b></div>
    </div>
    ${(T.letzte || []).length ? `<div class="ts-liste">${T.letzte.map(s => `<div class="pu-zeile">
      <img src="/api/testsatz_bild?datei=${encodeURIComponent(s.datei)}" alt="">
      <span class="t">#${s.id} · ${zeit(s.zeit)}</span>
      <span class="n">${s.leer ? "leer" : s.soll.map(txt).join(" + ")}</span>
      <span class="k">${(s.ist || []).map(o => txt(o.name)).join(", ")}</span>
      <button class="mini gefahr" data-tat="ts_loeschen" data-id="${s.id}" title="Szene entfernen">×</button></div>`).join("")}</div>` : ""}
    </div></details>`;
}
/* STATIONAERE PRUEFUNG (1.9.38): Knopf / Leertaste -> /api/pruefen. */''')
    h = ers(h, '''  if (tat === "pruefen") { await pruefenJetzt(); return; }''', '''  if (tat === "pruefen") { await pruefenJetzt(); return; }
  if (tat === "ts_soll") {
    const n = el.dataset.name;
    if (ev.shiftKey) { const i = TS_SOLL.indexOf(n); if (i >= 0) TS_SOLL.splice(i, 1); }
    else TS_SOLL.push(n);
    LETZTE_SPALTE = ""; zeichneRechts(); return;
  }
  if (tat === "ts_leer") { TS_SOLL = []; LETZTE_SPALTE = ""; zeichneRechts(); return; }
  if (tat === "testsatz_aufnehmen") {
    try {
      const r = await hole("/api/testsatz", { tat: "aufnehmen", soll: TS_SOLL });
      if (r && !r.ok) { MELDUNG = r.grund || "Aufnahme nicht möglich"; setTimeout(() => { MELDUNG = ""; }, 2500); }
    } catch (e) {}
    LETZTE_SPALTE = ""; await aktualisieren(); return;
  }
  if (tat === "ts_loeschen") {
    try { await hole("/api/testsatz", { tat: "loeschen", id: parseInt(el.dataset.id, 10) }); } catch (e) {}
    LETZTE_SPALTE = ""; await aktualisieren(); return;
  }''')
    h = ers(h, '''body.stationaer #navLinie, body.stationaer #linieAnsicht, body.stationaer .ltakt-linie { display:none !important; }''',
            '''body.stationaer #navLinie, body.stationaer #linieAnsicht, body.stationaer .ltakt-linie { display:none !important; }
.ts-chips { display:flex; flex-wrap:wrap; gap:5px; margin:6px 0; }
.ts-chip.an { color:var(--aufAkzent,#fff); background:var(--akzent,#3a7bd5); border-color:var(--akzent,#3a7bd5); }
.ts-liste { margin-top:8px; display:grid; gap:4px; }
.ts-liste .pu-zeile img { width:34px; height:34px; object-fit:cover; border-radius:3px; }
.ts-liste .pu-zeile button { margin-left:auto; }''')
    H.write_text(h, encoding="utf-8")
    print("index.html gepatcht")
