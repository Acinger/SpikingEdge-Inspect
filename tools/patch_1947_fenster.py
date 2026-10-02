#!/usr/bin/env python3
"""UI 1.9.47 — Aufnahmefenster direkt am Bild (Anmerkung Ace, 2026-10-02):

- Groesse des Aufnahmefensters im Videokopf: [−] Fenster 60 % [+], sichtbar
  im Lernen und Einrichten (nicht im Betrieb).
- Rahmenecke anfassen und ziehen = Groesse aendern; Mausrad ueber dem Rahmen
  = Groesse aendern (statt Zoom) in Lernen/Einrichten.
- Knopf "Lernzonen" im Profil stationaer ausgeblendet.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
H = ROOT / "vorsa" / "web" / "static" / "index.html"
S = ROOT / "vorsa" / "web" / "server.py"


def ers(t, a, n, k=1):
    if t.count(a) != k:
        raise SystemExit(f"FEHLER: {t.count(a)}x statt {k}x: {a[:160]}")
    return t.replace(a, n)


h = H.read_text(encoding="utf-8")
if 'id="fensterLeiste"' in h:
    print("index.html: schon gepatcht")
else:
    # 1) Leiste im Videokopf
    h = ers(h, '''      <button class="vknopf" id="lernzonenKnopf" data-tat="lernzonen" hidden''',
            '''      <span id="fensterLeiste" class="vfenster" hidden title="Größe des Aufnahmefensters — auch: Rahmenecke ziehen oder Mausrad über dem Rahmen">
        <button class="vknopf" data-tat="fenster_schritt" data-schritt="-5" aria-label="Fenster kleiner">−</button>
        <span id="fensterLeisteWert">Fenster 100 %</span>
        <button class="vknopf" data-tat="fenster_schritt" data-schritt="5" aria-label="Fenster größer">+</button>
      </span>
      <button class="vknopf" id="lernzonenKnopf" data-tat="lernzonen" hidden''')
    # 2) Sichtbarkeit je Modus + Lernzonen stationaer aus
    h = ers(h, '''  const lk = $("lernzonenKnopf");
  if (lk) lk.hidden = m !== "anlernen";''', '''  const lk = $("lernzonenKnopf");
  if (lk) lk.hidden = m !== "anlernen" || STATIONAER();
  const fl = $("fensterLeiste");
  if (fl) fl.hidden = m === "betreiben";''')
    # Wert aktuell halten (opsSync laeuft bei jedem Zustand)
    h = ers(h, '''  const zk = $("zoneKnopf");
  if (zk) zk.hidden = STATIONAER() || !(MODUS === "einrichten" || (ANSICHT_LINIE && !lern));''',
            '''  const zk = $("zoneKnopf");
  if (zk) zk.hidden = STATIONAER() || !(MODUS === "einrichten" || (ANSICHT_LINIE && !lern));
  const fl = $("fensterLeiste");
  if (fl) {
    fl.hidden = MODUS === "betreiben" || lern;
    const fw = $("fensterLeisteWert"), bf = Math.round(((Z && Z.bereich) || {}).fenster || 100);
    if (fw && fw.dataset.wert !== String(bf)) { fw.dataset.wert = String(bf); fw.textContent = `Fenster ${bf} %`; }
  }
  const lk2 = $("lernzonenKnopf");
  if (lk2 && STATIONAER()) lk2.hidden = true;''')
    # 3) Aktion [−]/[+]
    h = ers(h, '''  if (tat === "pruefen") { await pruefenJetzt(); return; }''', '''  if (tat === "pruefen") { await pruefenJetzt(); return; }
  if (tat === "fenster_schritt") {
    const f = Math.round(((Z && Z.bereich) || {}).fenster || 100) + parseInt(el.dataset.schritt, 10);
    await fensterSetzen(f); return;
  }''')
    # 4) Groesse setzen (gemeinsam fuer Leiste, Ecke, Rad)
    h = ers(h, '''function rahmenSenden(cx, cy) {''', '''let fensterTimer = null, fensterZiel = null;
async function fensterSetzen(f) {
  f = Math.max(10, Math.min(100, Math.round(f)));
  const fw = $("fensterLeisteWert");
  if (fw) { fw.dataset.wert = String(f); fw.textContent = `Fenster ${f} %`; }
  if (Z && Z.bereich) Z.bereich.fenster = f;
  fensterZiel = f;
  if (fensterTimer) return;
  fensterTimer = setTimeout(async () => {
    fensterTimer = null;
    const z = fensterZiel; fensterZiel = null;
    try {
      const r = await hole("/api/bereich", { fenster: z });
      if (Z) Z.bereich = Object.assign({}, Z.bereich, r);
      LETZTE_SPALTE = ""; zeichneRechts();
    } catch (e) {}
  }, 120);
}
// Ecke des Rahmens? -> Groesse aendern statt verschieben.
function anRahmenEcke(rx, ry) {
  const b = (Z && Z.bereich) || {};
  const w = b.bild_breite, h = b.bild_hoehe;
  if (!w || !h || b.seite == null) return null;
  const fx0 = b.x / w, fy0 = b.y / h, fx1 = (b.x + b.seite) / w, fy1 = (b.y + b.seite) / h;
  const tol = Math.max(0.02, 0.12 * (fx1 - fx0));
  const nahX = Math.abs(rx - fx0) < tol || Math.abs(rx - fx1) < tol;
  const nahY = Math.abs(ry - fy0) < tol || Math.abs(ry - fy1) < tol;
  if (nahX && nahY && rx > fx0 - tol && rx < fx1 + tol && ry > fy0 - tol && ry < fy1 + tol)
    return { cx: (fx0 + fx1) / 2, cy: (fy0 + fy1) / 2, gross: Math.min(w, h), w, h };
  return null;
}
function rahmenSenden(cx, cy) {''')
    # 5) pointerdown: Ecke -> Groesse; pointermove: Cursor
    h = ers(h, '''  const [rx, ry] = bildZuAusschnitt(e.clientX, e.clientY);
  const mitte = imRahmen(rx, ry);
  if (!mitte) return;
  e.preventDefault();
  const dx = mitte.cx - rx, dy = mitte.cy - ry;
  const move = (ev) => {
    const [mx, my] = bildZuAusschnitt(ev.clientX, ev.clientY);
    rahmenSenden(Math.max(0, Math.min(1, mx + dx)),
                 Math.max(0, Math.min(1, my + dy)));
  };''', '''  const [rx, ry] = bildZuAusschnitt(e.clientX, e.clientY);
  const ecke = anRahmenEcke(rx, ry);
  if (ecke) {
    // Groesse aendern: Seite = 2 * groesster Abstand zur Mitte (in Bild-px)
    e.preventDefault();
    const moveE = (ev) => {
      const [mx, my] = bildZuAusschnitt(ev.clientX, ev.clientY);
      const seite = 2 * Math.max(Math.abs(mx - ecke.cx) * ecke.w, Math.abs(my - ecke.cy) * ecke.h);
      fensterSetzen(seite / ecke.gross * 100);
    };
    const upE = () => { window.removeEventListener("pointermove", moveE); window.removeEventListener("pointerup", upE); };
    window.addEventListener("pointermove", moveE);
    window.addEventListener("pointerup", upE);
    return;
  }
  const mitte = imRahmen(rx, ry);
  if (!mitte) return;
  e.preventDefault();
  const dx = mitte.cx - rx, dy = mitte.cy - ry;
  const move = (ev) => {
    const [mx, my] = bildZuAusschnitt(ev.clientX, ev.clientY);
    rahmenSenden(Math.max(0, Math.min(1, mx + dx)),
                 Math.max(0, Math.min(1, my + dy)));
  };''')
    h = ers(h, '''  const [rx, ry] = bildZuAusschnitt(e.clientX, e.clientY);
  BILD.style.cursor = imRahmen(rx, ry) ? "move" : "";''', '''  const [rx, ry] = bildZuAusschnitt(e.clientX, e.clientY);
  BILD.style.cursor = anRahmenEcke(rx, ry) ? "nwse-resize" : imRahmen(rx, ry) ? "move" : "";''')
    # 6) Mausrad ueber dem Rahmen (Lernen/Einrichten, nicht gezoomt) -> Groesse
    h = ers(h, '''  e.preventDefault();
  const r = $("videoteil").getBoundingClientRect();
  zoomUm(e.deltaY < 0 ? 1.18 : 1 / 1.18,''', '''  e.preventDefault();
  if (MODUS !== "betreiben" && ZOOM <= 1.001 && !ZONE_ZIEHEN && e.target === BILD) {
    const [rx, ry] = bildZuAusschnitt(e.clientX, e.clientY);
    if (imRahmen(rx, ry)) {
      fensterSetzen((((Z && Z.bereich) || {}).fenster || 100) + (e.deltaY < 0 ? 4 : -4));
      return;
    }
  }
  const r = $("videoteil").getBoundingClientRect();
  zoomUm(e.deltaY < 0 ? 1.18 : 1 / 1.18,''')
    # 7) CSS
    h = ers(h, '''.ts-chips { display:flex; flex-wrap:wrap; gap:5px; margin:6px 0; }''', '''.vfenster { display:inline-flex; align-items:center; gap:4px; margin-right:6px; }
.vfenster[hidden] { display:none !important; }
.vfenster #fensterLeisteWert { font-size:11px; min-width:84px; text-align:center; color:var(--text); font-variant-numeric:tabular-nums; }
.vfenster .vknopf { min-width:28px; padding:0 8px; font-weight:800; }
body.stationaer #lernzonenKnopf { display:none !important; }
.ts-chips { display:flex; flex-wrap:wrap; gap:5px; margin:6px 0; }''')
    H.write_text(h, encoding="utf-8")
    print("index.html gepatcht")

s = S.read_text(encoding="utf-8")
if "1.9.47-fenster" not in s:
    s = ers(s, 'BUILD = "1.9.46-se-design"', 'BUILD = "1.9.47-fenster"')
    S.write_text(s, encoding="utf-8")
    print("server.py gepatcht")
