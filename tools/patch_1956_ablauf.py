#!/usr/bin/env python3
"""1.9.56 — Geführter Ablauf + ein Hauptknopf pro Seite (Pakete 1 und 2).

Paket 1  Seitenleiste als Schritte ① Einrichten ② Anlernen ③ Prüfen mit Häkchen,
         "Nächster Schritt"-Karte oben in der rechten Spalte (leere Zustände führen
         weiter), Erststart-Assistent "Erste Schritte" (6 Punkte, live abgehakt).
Paket 2  Rechts oben genau eine Primäraktion je Seite (Prüfen / Foto aufnehmen /
         Leerbild merken), Nebenaktion daneben, Rest im "⋯"-Menü. Linie und Arm
         nur im Linienbetrieb (laufende Linie bleibt überall stoppbar).
         Kopfzeile in Klartext ("2 Objekte gelernt" statt "Verbund + M3 · 128 NPs").
         Bildleiste: "90° drehen" wandert ins Rechtsklick-Menü.
Motor-/Arm-/Bandeinstellungen werden nicht berührt.
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


h = H.read_text(encoding="utf-8")
if "ABLAUF (1.9.56)" in h:
    print("index.html: schon gepatcht")
else:
    # ---------- Seitenleiste: Schritte ----------
    h = ers(h, '''  <div class="ops-nav-caption">Betrieb</div>
  <button class="snav modus" data-tat="modus" data-modus="betreiben" title="Erkennung">
    <svg viewBox="0 0 16 16" aria-hidden="true"><circle cx="8" cy="8" r="5"/><path d="M8 0v4M8 12v4M0 8h4M12 8h4"/></svg><span>Erkennung</span></button>
  <button class="snav" id="navLinie" data-tat="ansicht_linie" title="Linienbetrieb">
    <svg viewBox="0 0 16 16" aria-hidden="true"><rect x="1" y="8" width="14" height="6" rx="3"/><path d="M3 4h10M10 1l3 3-3 3"/><circle cx="4" cy="11" r="1"/><circle cx="12" cy="11" r="1"/></svg><span>Linienbetrieb</span></button>
  <button class="snav" data-tat="rezepte" title="Rezepte und Aufträge">
    <svg viewBox="0 0 16 16" aria-hidden="true"><rect x="3" y="2" width="10" height="13" rx="1"/><path d="M6 1h4v3H6zM6 7h4M6 10h4"/></svg><span>Rezepte</span></button>
  <div class="ops-nav-caption ops-expert">Einrichten</div>
  <button class="snav modus ops-expert" data-tat="modus" data-modus="einrichten" title="Kamera und Zonen einrichten">
    <svg viewBox="0 0 16 16" aria-hidden="true"><path d="M3 1v14M8 1v14M13 1v14M1 5h4M6 10h4M11 6h4"/></svg><span>Kamera &amp; Zonen</span></button>
  <button class="snav modus ops-expert" data-tat="modus" data-modus="anlernen" title="Objekte anlegen, Fotos aufnehmen, trainieren">
    <svg viewBox="0 0 16 16" aria-hidden="true"><path d="M2 12l1-3 8-8 3 3-8 8zM2 15h12"/></svg><span>Objekte &amp; Lernen</span></button>
''', '''  <!-- ABLAUF (1.9.56): die drei Schritte in der Reihenfolge, in der man sie braucht -->
  <button class="snav ops-expert" id="navStart" data-tat="erststart" hidden title="Erste Schritte: geführte Einrichtung">
    <svg viewBox="0 0 16 16" aria-hidden="true"><path d="M3 15V2M3 2h9l-2 3 2 3H3"/></svg><span>Erste Schritte</span><em id="navStartStand">0/6</em></button>
  <div class="ops-nav-caption ops-expert">Ablauf</div>
  <button class="snav modus schritt ops-expert" data-tat="modus" data-modus="einrichten" title="Schritt 1: Kamera, Aufnahmefenster und Leerbild einrichten">
    <i class="snr" aria-hidden="true">1</i><span>Einrichten</span></button>
  <button class="snav modus schritt ops-expert" data-tat="modus" data-modus="anlernen" title="Schritt 2: Objekte anlegen, fotografieren, lernen">
    <i class="snr" aria-hidden="true">2</i><span>Anlernen</span></button>
  <button class="snav modus schritt" data-tat="modus" data-modus="betreiben" title="Schritt 3: Teile prüfen">
    <i class="snr" aria-hidden="true">3</i><span>Prüfen</span></button>
  <div class="ops-nav-caption">Betrieb</div>
  <button class="snav" id="navLinie" data-tat="ansicht_linie" title="Linienbetrieb">
    <svg viewBox="0 0 16 16" aria-hidden="true"><rect x="1" y="8" width="14" height="6" rx="3"/><path d="M3 4h10M10 1l3 3-3 3"/><circle cx="4" cy="11" r="1"/><circle cx="12" cy="11" r="1"/></svg><span>Linienbetrieb</span></button>
  <button class="snav" data-tat="rezepte" title="Rezepte und Aufträge">
    <svg viewBox="0 0 16 16" aria-hidden="true"><rect x="3" y="2" width="10" height="13" rx="1"/><path d="M6 1h4v3H6zM6 7h4M6 10h4"/></svg><span>Rezepte</span></button>
''')
    # Beschriftung des Einrichten-Schritts nicht mehr umschreiben
    h = ers(h, '''      const kz = document.querySelector('#seitenNav .snav[data-modus="einrichten"] span');
      if (kz) kz.textContent = STATIONAER() ? "Kamera" : "Kamera & Zonen";
''', '')

    # ---------- Kopfaktionen: Haupt + Neben + ⋯ ----------
    h = ers(h, '''  <div class="ops-actions">
    <button class="ops-btn" id="opsAnalysisButton" data-ops-action="analyse" aria-haspopup="dialog">Analyse öffnen</button>
    <span id="liniePhase" hidden></span>
    <button class="kopftaste" data-tat="betrieb" id="betriebKnopf" title="Nur die Ansicht ändern; der Maschinenmodus bleibt unverändert">Bedienansicht</button>
    <button id="armKnopf" class="ops-btn" data-tat="arm_dialog" hidden title="Arduino-Arm steuern und anlernen">Roboterarm</button>
    <button id="linieKnopf" data-tat="linie">Linie aktivieren</button>
  </div>''', '''  <div class="ops-actions">
    <span id="liniePhase" hidden></span>
    <button class="ops-btn" id="opsNeben" hidden></button>
    <button class="ops-haupt" id="opsHaupt" hidden></button>
    <button id="armKnopf" class="ops-btn" data-tat="arm_dialog" hidden title="Arduino-Arm steuern und anlernen">Roboterarm</button>
    <button id="linieKnopf" data-tat="linie">Linie aktivieren</button>
    <span class="ops-mehr-wrap">
      <button class="ops-btn ops-mehr" id="opsMehrKnopf" data-tat="ops_mehr" aria-haspopup="menu" aria-expanded="false" title="Weitere Aktionen" aria-label="Weitere Aktionen">
        <svg viewBox="0 0 16 16" aria-hidden="true"><circle cx="3" cy="8" r="1.4"/><circle cx="8" cy="8" r="1.4"/><circle cx="13" cy="8" r="1.4"/></svg></button>
      <span id="opsMehr" role="menu" hidden>
        <button class="ops-btn" id="opsAnalysisButton" data-ops-action="analyse" role="menuitem" aria-haspopup="dialog">Analyse öffnen</button>
        <button class="kopftaste" data-tat="betrieb" id="betriebKnopf" role="menuitem" title="Nur die Ansicht ändern; der Maschinenmodus bleibt unverändert">Bedienansicht</button>
        <button class="ops-btn" data-tat="erststart" role="menuitem">Erste Schritte</button>
      </span>
    </span>
  </div>''')

    # ---------- Bildleiste: Drehen raus (ins Rechtsklick-Menü) ----------
    h = ers(h, '''        <button class="vknopf" data-tat="drehen" title="Kamerabild 90° drehen">
          <svg viewBox="0 0 16 16"><path d="M13.2 8.6a5.3 5.3 0 1 1-1.5-4.4
            M13.5 1.6v3.1h-3.1"/></svg></button>
''', '')
    h = ers(h, '''      <button class="mini" data-tat="leerbild" data-art="haupt">${L ? "Leerbild neu" : "Leerbild merken"}</button>
      ${MODUS === "betreiben" && STATIONAER() ? `<button class="mini an" data-tat="pruefen">Prüfen</button>` : ""}''',
            '''      <button class="mini" data-tat="leerbild" data-art="haupt">${L ? "Leerbild neu" : "Leerbild merken"}</button>
      ${MODUS !== "betreiben" ? `<button class="mini" data-tat="drehen">Bild 90° drehen</button>` : ""}
      ${MODUS === "betreiben" && STATIONAER() ? `<button class="mini an" data-tat="pruefen">Prüfen</button>` : ""}''')

    # ---------- Kopfzeile Klartext ----------
    h = ers(h, '''    <span class="chipfeld"><small>Modell</small><b id="cModell">–</b></span>''',
            '''    <button class="chipfeld" data-tat="modus" data-modus="anlernen" title="Anlernen öffnen"><small>Gelernt</small><b id="cModell">–</b></button>''')
    h = ers(h, '''  const cM = $("cModell");
  if (cM && h.nps) cM.innerHTML = `Verbund + M3 · ${h.nps} NPs
    <em class="aktivChip">AKTIV</em>`;''', '''  const cM = $("cModell");
  if (cM) {
    // Klartext (1.9.56): was der Nutzer wissen will, ist "was kann die Anlage
    // gerade erkennen" - die Technik steht im Tooltip.
    const LB = (Z.lernen || {}).bericht;
    const n = LB && LB.ok ? (LB.klassen || []).filter(x => !/nichts|stör|hintergrund/i.test(String(x))).length : 0;
    const t = trAb(n ? (n === 1 ? "1 Objekt" : n + " Objekte") : "noch nichts");
    if (cM.textContent !== t) cM.textContent = t;
    cM.className = n ? "" : "leise";
    cM.parentElement.title = (h.nps ? `Verbund + M3 · ${h.nps} NPs` + (h.karten > 1 ? ` · ${h.karten} Karten` : "") : "kein Chip")
      + " — Klick: Anlernen";
  }''')
    h = ers(h, '''  const ak = $("armKnopf");
  if (ak) ak.hidden = !Z.arm_uno;''', '''  const ak = $("armKnopf");
  // Arm nur im Linienbetrieb (1.9.56) - dort wird er gebraucht.
  if (ak) ak.hidden = !Z.arm_uno || !(ANSICHT_LINIE && MODUS === "betreiben");''')

    # ---------- opsSync: Titel, Hauptknopf, Häkchen ----------
    h = ers(h, '''  const names = { betreiben:"Erkennung", anlernen:"Objekte & Lernen",
                  einrichten: STATIONAER() ? "Kamera" : "Kamera & Zonen" };''',
            '''  const names = { betreiben:"Prüfung", anlernen:"Anlernen", einrichten:"Einrichten" };''')
    h = ers(h, '''  $("opsAnalysisButton").hidden = !production;''', '''  $("opsAnalysisButton").hidden = !production;
  try { hauptAktionSetzen(); ablaufMalen(); } catch (e) {}''')

    # ---------- Prüfen-Knopf in der Spalte -> Kopf (Hand/Auto bleibt) ----------
    h = ers(h, '''      <button class="pu-pruefen" data-tat="pruefen" ${(!teil || PRUEF_LAEUFT || MODUS !== "betreiben") ? "disabled" : ""}
        title="Alle Teile im Bild jetzt prüfen und buchen (Leertaste)">PRÜFEN</button>
''', '''      <span class="pu-hinweis">Auslöser</span>
''')

    # ---------- Spalte: Nächster-Schritt-Karte ----------
    h = ers(h, '''  let neu = MODUS === "einrichten" ? spalteEinrichten()
            : MODUS === "anlernen"   ? spalteAnlernen()
            :                          spalteBetreiben();''', '''  let neu = blockNaechsterSchritt() + (MODUS === "einrichten" ? spalteEinrichten()
            : MODUS === "anlernen"   ? spalteAnlernen()
            :                          spalteBetreiben());''')

    # ---------- Klick-Handler ----------
    h = ers(h, '''  if (tat === "modus") return setzeModus(el.dataset.modus);
''', '''  if (tat === "modus") { ablaufMenueZu(); return setzeModus(el.dataset.modus); }
  if (tat === "ops_mehr") {
    const m = $("opsMehr"), an = m.hidden;
    m.hidden = !an; el.setAttribute("aria-expanded", String(an));
    return;
  }
  if (tat === "erststart") { ablaufMenueZu(); erstStartZeigen(true); return; }
  if (tat === "erststart_zu") {
    erstStartZeigen(false);
    try { localStorage.setItem("nbes_erststart", "zu"); } catch (e) {}
    return;
  }
  if (tat === "erst_schritt") { return erstSchrittTun(el.dataset.nr); }
''')

    # ---------- JS-Bausteine ----------
    h = ers(h, '''/* ---------- OPS 2 presentation and accessibility (no API calls) ---------- */
function opsSync() {''', '''/* ---------- ABLAUF (1.9.56): Schritte, Hauptknopf, Erste Schritte ----------
   Ein Stand, aus dem alles abgeleitet wird: Häkchen in der Seitenleiste,
   Nächster-Schritt-Karte, Hauptknopf rechts oben und der Assistent.     */
// Text gleich in der aktiven Sprache setzen - sonst schreibt jeder Takt Deutsch
// hinein und der Übersetzer muss es wieder umschreiben.
const trAb = (x) => (typeof SPRACHE !== "undefined" && SPRACHE === "en" && uebersetzeText(x)) || x;
function ablaufStand() {
  const b = (Z && Z.bereich) || {}, f = (Z && Z.fortschritt) || {};
  const LB = ((Z && Z.lernen) || {}).bericht;
  const objekteVoll = echt().filter(k => k.prototypen >= ZIEL).length;
  const P = b.pruef || {};
  const zaehler = Object.values((Z && Z.zaehler) || {}).reduce((s, v) => s + (+v || 0), 0);
  const s = {
    scharf: (b.schaerfe || 0) >= 25,
    leerbild: !!((b.leerbild || {})[quelleVon("haupt")]),
    fenster: !!f.eingerichtet,
    objekte: objekteVoll >= 2, objekteVoll,
    gelernt: !!(LB && LB.ok),
    // Stationaer: gebuchte Pruefungen; Linie: gezaehlte Teile der Linie.
    geprueft: STATIONAER() ? (P.gesamt || 0) > 0 : zaehler > 0,
  };
  s.schritt1 = s.leerbild || s.fenster;
  s.schritt2 = s.objekte && s.gelernt;
  s.schritt3 = s.geprueft;
  s.erledigt = ["scharf", "leerbild", "fenster", "objekte", "gelernt", "geprueft"].filter(k => s[k]).length;
  return s;
}
function ablaufMenueZu() {
  const m = $("opsMehr"); if (m && !m.hidden) { m.hidden = true; $("opsMehrKnopf").setAttribute("aria-expanded", "false"); }
}
document.addEventListener("pointerdown", ev => {
  if (!ev.target.closest || ev.target.closest(".ops-mehr-wrap")) return;
  ablaufMenueZu();
}, true);
function ablaufMalen() {
  if (!Z) return;
  const s = ablaufStand();
  const fertig = { einrichten: s.schritt1, anlernen: s.schritt2, betreiben: s.schritt3 };
  const nr = { einrichten: "1", anlernen: "2", betreiben: "3" };
  document.querySelectorAll("#seitenNav .snav.schritt").forEach(b => {
    const ok = !!fertig[b.dataset.modus];
    b.classList.toggle("erledigt", ok);
    const i = b.querySelector(".snr"), t = ok ? "✓" : nr[b.dataset.modus];
    if (i && i.textContent !== t) i.textContent = t;
  });
  const ns = $("navStart");
  if (ns) {
    ns.hidden = s.erledigt >= 6;
    const t = s.erledigt + "/6";
    if ($("navStartStand").textContent !== t) $("navStartStand").textContent = t;
  }
  // Erststart: einmal von selbst, solange noch nichts fotografiert ist.
  if (!ERST_GEZEIGT && Z.klassen) {
    ERST_GEZEIGT = true;
    let zu = false; try { zu = localStorage.getItem("nbes_erststart") === "zu"; } catch (e) {}
    const leer = !(Z.klassen || []).some(k => k.prototypen > 0) && !s.gelernt;
    if (!zu && leer) erstStartZeigen(true);
  }
  if (!$("erstStart").hidden) erstStartMalen();
}
let ERST_GEZEIGT = false;
function hauptAktionSetzen() {
  const hk = $("opsHaupt"), nk = $("opsNeben"), lk = $("linieKnopf");
  if (!hk || !Z) return;
  const LI = ((Z.bereich || {}).linie) || {};
  // Linie: Knopf nur im Linienbetrieb - laeuft sie, bleibt STOPP ueberall sichtbar.
  if (lk) lk.hidden = STATIONAER() || !(LI.aktiv || (ANSICHT_LINIE && MODUS === "betreiben"));
  const s = ablaufStand();
  let haupt = null, neben = null;
  if (MODUS === "betreiben" && STATIONAER()) {
    const teil = (Z.erkannt && (Z.erkannt.je_objekt || []).length) || 0;
    haupt = { t: PRUEF_LAEUFT ? "Prüft …" : "PRÜFEN", tat: "pruefen", aus: PRUEF_LAEUFT || !teil,
              title: teil ? "Alle Teile im Bild prüfen und buchen (Leertaste)" : "Kein Teil im Bild" };
  } else if (MODUS === "anlernen") {
    const k = objekt(AKTIV);
    haupt = { t: "Foto aufnehmen", tat: "aufnehmen", aus: !k,
              title: k ? `Foto von „${k.name}“ aufnehmen (Leertaste)` : "Erst ein Objekt wählen oder anlegen" };
    const plan = Z.trainingsplan || {};
    neben = { t: s.gelernt ? "Neu lernen …" : "Lernen …", tat: "training_dialog", aus: !plan.bereit,
              title: plan.bereit ? "Gelerntes auf den Chip bringen" : "Mindestens zwei Objekte mit Fotos nötig" };
  } else if (MODUS === "einrichten") {
    haupt = { t: s.leerbild ? "Leerbild neu merken" : "Leerbild merken", tat: "leerbild", art: "haupt",
              title: "Ohne Teil im Bild: merkt sich den leeren Hintergrund" };
    neben = { t: "Weiter: Anlernen →", tat: "modus", modus: "anlernen", title: "Schritt 2" };
  }
  const setze = (el, a, cls) => {
    el.hidden = !a;
    if (!a) return;
    const tt = trAb(a.t);
    if (el.textContent !== tt) el.textContent = tt;
    el.dataset.tat = a.tat; el.disabled = !!a.aus; el.title = a.title || "";
    if (a.art) el.dataset.art = a.art; else delete el.dataset.art;
    if (a.modus) el.dataset.modus = a.modus; else delete el.dataset.modus;
  };
  setze(hk, haupt); setze(nk, neben);
}
function blockNaechsterSchritt() {
  if (!Z || document.body.classList.contains("betrieb")) return "";
  const s = ablaufStand();
  const karte = (art, titel, text, knopf) => `<div class="block naechst ${art}">
    <div class="ns-titel">${titel}</div><div class="ns-text">${text}</div>${knopf || ""}</div>`;
  const geh = (m, t) => `<button class="mini an" data-tat="modus" data-modus="${m}">${t}</button>`;
  if (MODUS === "betreiben") {
    if (!s.gelernt) return karte("warn", "Noch nichts gelernt",
      "Ohne gelernte Objekte findet SE Inspect Umrisse, kann sie aber nicht benennen.",
      geh("anlernen", "Zu Schritt 2: Anlernen →"));
    return "";
  }
  if (MODUS === "anlernen") {
    if (s.schritt2) return karte("gut", "Gelernt ✓", "Die Anlage kennt deine Objekte. Weiter mit dem Prüfen.",
      geh("betreiben", "Zu Schritt 3: Prüfen →"));
    if (s.objekte) return karte("", "Bereit zum Lernen",
      "Zwei oder mehr Objekte haben genug Fotos. Rechts oben „Lernen …“ drücken.", "");
    return karte("", `Schritt 2 · ${s.objekteVoll}/2 Objekte fertig`,
      `Lege mindestens zwei Objekte an und mache je ${ZIEL} Fotos — Teil in den Rahmen legen, Leertaste.` +
      (s.schritt1 ? "" : " <i>Tipp: Erst in Schritt 1 das Leerbild merken.</i>"), "");
  }
  if (MODUS === "einrichten" && s.schritt1) return karte("gut", "Eingerichtet ✓",
    "Kamera und Hintergrund passen. Weiter mit dem Anlernen.", geh("anlernen", "Zu Schritt 2: Anlernen →"));
  return "";
}
/* Erste Schritte: sechs Punkte, live abgehakt, jeder mit einem Knopf. */
const ERST_SCHRITTE = [
  ["scharf", "Kamera scharf stellen", "Teil unter die Kamera legen, „Scharf stellen“ drücken.", "Scharf stellen"],
  ["leerbild", "Leerbild merken", "Teil wegnehmen — die Anlage merkt sich den leeren Hintergrund.", "Leerbild merken"],
  ["fenster", "Aufnahmefenster anpassen", "Den Rahmen so groß ziehen, dass ein Teil gut hineinpasst (Ecke ziehen oder Mausrad).", "Zum Einrichten"],
  ["objekte", "Zwei Objekte fotografieren", `Je Objekt ${ZIEL} Fotos — in verschiedenen Lagen.`, "Zum Anlernen"],
  ["gelernt", "Lernen", "Die Fotos auf den Chip bringen — dauert Sekunden.", "Lernen …"],
  ["geprueft", "Erste Prüfung", "Teil auflegen und PRÜFEN drücken (oder Leertaste).", "Zum Prüfen"],
];
function erstStartZeigen(an) {
  const d = $("erstStart"); if (!d) return;
  d.hidden = !an;
  if (an) erstStartMalen();
}
function erstStartMalen() {
  const box = $("erstStartListe"); if (!box || !Z) return;
  const s = ablaufStand();
  const naechst = ERST_SCHRITTE.findIndex(x => !s[x[0]]);
  const neu = ERST_SCHRITTE.map(([k, titel, text, knopf], i) => `
    <li class="${s[k] ? "ok" : i === naechst ? "jetzt" : ""}">
      <i>${s[k] ? "✓" : i + 1}</i>
      <div><b>${titel}</b><span>${text}</span></div>
      ${s[k] ? "" : `<button class="mini ${i === naechst ? "an" : ""}" data-tat="erst_schritt" data-nr="${i}">${knopf}</button>`}
    </li>`).join("");
  if (box.dataset.sig !== neu) { box.innerHTML = neu; box.dataset.sig = neu; }
  const st = $("erstStartStand"); if (st) st.textContent = `${s.erledigt} von 6 erledigt`;
}
async function erstSchrittTun(nr) {
  const k = ERST_SCHRITTE[+nr]; if (!k) return;
  const ziel = { scharf: "einrichten", leerbild: "einrichten", fenster: "einrichten",
                 objekte: "anlernen", gelernt: "anlernen", geprueft: "betreiben" }[k[0]];
  if (MODUS !== ziel) await setzeModus(ziel);
  if (k[0] === "scharf") { try { await hole("/api/feed_kamera", { quelle: "haupt", aktion: "af_einmal" }); } catch (e) {} kamDockSetzen(true); }
  else if (k[0] === "leerbild") { const b = document.querySelector('#opsHaupt[data-tat="leerbild"]'); if (b) b.click(); }
  else if (k[0] === "gelernt") { const plan = Z.trainingsplan || {}; if (plan.bereit) { erstStartZeigen(false); $("dTraining").hidden = false; return; } }
  if (k[0] !== "leerbild" && k[0] !== "scharf") erstStartZeigen(false);
  erstStartMalen();
}

/* ---------- OPS 2 presentation and accessibility (no API calls) ---------- */
function opsSync() {''')

    # ---------- Erststart-Dialog im DOM ----------
    h = ers(h, '''<section id="opsCommand" aria-label="Arbeitsbereich und Linienbefehle" tabindex="-1">''', '''<div id="erstStart" role="dialog" aria-modal="false" aria-labelledby="erstStartTitel" hidden>
  <div class="es-kopf"><div><div class="es-eyebrow">SE INSPECT</div><h2 id="erstStartTitel">Erste Schritte</h2>
    <small id="erstStartStand"></small></div>
    <button class="es-zu" data-tat="erststart_zu" aria-label="Schließen" title="Schließen — jederzeit wieder über „Erste Schritte“">×</button></div>
  <ol id="erstStartListe"></ol>
  <div class="es-fuss">Alles hakt sich von selbst ab. Du kannst jeden Punkt auch später machen.</div>
</div>

<section id="opsCommand" aria-label="Arbeitsbereich und Linienbefehle" tabindex="-1">''')

    # ---------- CSS ----------
    h = ers(h, '''/* Kamera-Dock (1.9.52) */''', '''/* ABLAUF (1.9.56) ---------------------------------------------------------- */
body#opsApp .snav.schritt .snr { flex:0 0 22px; width:22px; height:22px; border-radius:50%; border:1.5px solid currentColor;
  display:inline-flex; align-items:center; justify-content:center; font:700 11.5px/1 Inter,system-ui,sans-serif; font-style:normal; opacity:.85; }
body#opsApp .snav.schritt.an .snr { opacity:1; }
body#opsApp .snav.schritt.erledigt .snr { background:var(--gut,#22c55e); border-color:var(--gut,#22c55e); color:#06231a; opacity:1; }
body#opsApp #navStart { border:1px dashed var(--akzent,#49e7ff) !important; color:var(--akzent,#49e7ff) !important; margin-bottom:6px; }
body#opsApp #navStart em { margin-left:auto; font-style:normal; font-size:11px; opacity:.85; }
body#opsApp #navStart[hidden] { display:none !important; }
body#opsApp.schmal #navStart em { display:none; }
body#opsApp .ops-haupt { min-height:42px; padding:10px 22px; min-width:150px; border-radius:6px; cursor:pointer;
  background:var(--akzent); border:1px solid var(--akzent); color:var(--aufAkzent,#041014); font-size:13.5px; font-weight:750; letter-spacing:.02em; }
body#opsApp .ops-haupt:disabled { opacity:.45; cursor:default; }
body#opsApp .ops-haupt:not(:disabled):hover { filter:brightness(1.1); }
body#opsApp #opsNeben { min-height:42px; padding:9px 16px; }
body#opsApp #opsNeben[hidden], body#opsApp .ops-haupt[hidden], body#opsApp #linieKnopf[hidden] { display:none !important; }
body#opsApp .ops-mehr-wrap { position:relative; display:inline-flex; }
body#opsApp .ops-mehr { min-width:42px; min-height:42px; padding:0 10px; display:inline-flex; align-items:center; justify-content:center; }
body#opsApp .ops-mehr svg { width:18px; height:18px; fill:currentColor; stroke:none; }
body#opsApp #opsMehr { position:absolute; right:0; top:calc(100% + 6px); z-index:40; display:flex; flex-direction:column; gap:4px;
  min-width:220px; padding:6px; background:var(--panel); border:1px solid var(--rand); border-radius:8px; box-shadow:0 12px 30px #0006; }
body#opsApp #opsMehr[hidden] { display:none; }
body#opsApp #opsMehr > button { width:100%; justify-content:flex-start; text-align:left; min-height:38px; margin:0; }
body#opsApp #opsMehr > button[hidden] { display:none !important; }
body#opsApp #kopfChips button.chipfeld { cursor:pointer; text-align:left; background:transparent; border:0; color:inherit; font:inherit; padding:0; }
body#opsApp #cModell.leise { color:var(--leise) !important; }
.pu-hinweis { font-size:11px; color:var(--leise,#8a94a0); margin-right:6px; }
.block.naechst { border-left:3px solid var(--akzent,#49e7ff); background:rgba(73,231,255,.06); }
.block.naechst.gut { border-left-color:var(--gut,#22c55e); background:rgba(34,197,94,.07); }
.block.naechst.warn { border-left-color:var(--warn,#f5b041); background:rgba(245,176,65,.07); }
.naechst .ns-titel { font-weight:700; font-size:14px; color:var(--text); margin-bottom:4px; }
.naechst .ns-text { font-size:12.5px; color:var(--leise,#8a94a0); line-height:1.45; }
.naechst .mini { margin-top:10px; }
#erstStart { position:fixed; right:24px; bottom:56px; z-index:60; width:min(420px,calc(100vw - 32px)); max-height:calc(100vh - 120px); overflow:auto;
  background:var(--panel,#0b1b22); border:1px solid var(--akzent,#49e7ff); border-radius:12px; box-shadow:0 20px 60px #000a; padding:18px 18px 14px; }
#erstStart[hidden] { display:none; }
#erstStart .es-kopf { display:flex; justify-content:space-between; align-items:flex-start; gap:12px; }
#erstStart .es-eyebrow { font-size:10px; letter-spacing:.14em; color:var(--akzent,#49e7ff); font-weight:700; }
#erstStart h2 { margin:2px 0 2px; font-size:19px; color:var(--text); }
#erstStart small { color:var(--leise,#8a94a0); font-size:12px; }
#erstStart .es-zu { background:transparent; border:0; color:var(--leise,#8a94a0); font-size:22px; cursor:pointer; line-height:1; padding:2px 6px; }
#erstStart ol { list-style:none; margin:14px 0 8px; padding:0; display:grid; gap:8px; }
#erstStart li { display:grid; grid-template-columns:26px 1fr auto; gap:10px; align-items:center; padding:9px 10px; border:1px solid var(--rand,#333b43); border-radius:8px; }
#erstStart li > i { width:24px; height:24px; border-radius:50%; border:1.5px solid var(--rand,#556); display:flex; align-items:center; justify-content:center; font-style:normal; font-weight:700; font-size:12px; color:var(--leise,#8a94a0); }
#erstStart li.ok { opacity:.6; } #erstStart li.ok > i { background:var(--gut,#22c55e); border-color:var(--gut,#22c55e); color:#06231a; }
#erstStart li.jetzt { border-color:var(--akzent,#49e7ff); background:rgba(73,231,255,.06); } #erstStart li.jetzt > i { border-color:var(--akzent,#49e7ff); color:var(--akzent,#49e7ff); }
#erstStart li b { display:block; font-size:13.5px; color:var(--text); } #erstStart li span { display:block; font-size:12px; color:var(--leise,#8a94a0); line-height:1.4; margin-top:2px; }
#erstStart .es-fuss { font-size:11.5px; color:var(--leise,#8a94a0); }
/* Kamera-Dock (1.9.52) */''')
    H.write_text(h, encoding="utf-8")
    print("index.html gepatcht")

s = S.read_text(encoding="utf-8")
if "1.9.56-ablauf" not in s:
    s = ers(s, 'BUILD = "1.0.0-alpha.1"', 'BUILD = "1.9.56-ablauf"')
    S.write_text(s, encoding="utf-8")
    print("server.py: BUILD 1.9.56-ablauf")

d = D.read_text(encoding="utf-8")
if "Nachtrag 11" not in d:
    d = ers(d, '\nif (window.spracheNachladen) window.spracheNachladen();\n', '''
/* ---- Nachtrag 11 (1.9.56 Ablauf) ---- */
Object.assign(window.SPRACHEN.en, {
  "Ablauf": "Workflow", "Anlernen": "Teach", "Lernen": "Learn", "kein Chip — Klick: Anlernen": "no chip — click: Teach", "{} — Klick: Anlernen": "{} — click: Teach", "Erste Schritte": "First steps", "Gelernt": "Learned",
  "noch nichts": "nothing yet", "1 Objekt": "1 object", "{} Objekte": "{} objects",
  "Weitere Aktionen": "More actions", "Auslöser": "Trigger", "Prüft …": "Inspecting …",
  "Leerbild neu merken": "Record empty image again", "Weiter: Anlernen →": "Next: Teach →",
  "Lernen …": "Learn …", "Neu lernen …": "Learn again …", "Bild 90° drehen": "Rotate image 90°",
  "Schritt 1: Kamera, Aufnahmefenster und Leerbild einrichten": "Step 1: set up camera, capture window and empty image",
  "Schritt 2: Objekte anlegen, fotografieren, lernen": "Step 2: create objects, take photos, learn",
  "Schritt 3: Teile prüfen": "Step 3: inspect parts", "Schritt 2": "Step 2",
  "Erste Schritte: geführte Einrichtung": "First steps: guided setup", "Anlernen öffnen": "Open Teach",
  "Alle Teile im Bild prüfen und buchen (Leertaste)": "Inspect and log all parts in the image (space bar)",
  "Kein Teil im Bild": "No part in the image", "Erst ein Objekt wählen oder anlegen": "Select or create an object first",
  "Gelerntes auf den Chip bringen": "Put what was learned onto the chip",
  "Mindestens zwei Objekte mit Fotos nötig": "At least two objects with photos needed",
  "Ohne Teil im Bild: merkt sich den leeren Hintergrund": "With no part in view: records the empty background",
  "Noch nichts gelernt": "Nothing learned yet",
  "Ohne gelernte Objekte findet SE Inspect Umrisse, kann sie aber nicht benennen.": "Without learned objects SE Inspect finds outlines but cannot name them.",
  "Zu Schritt 2: Anlernen →": "To step 2: Teach →", "Zu Schritt 3: Prüfen →": "To step 3: Inspect →",
  "Gelernt ✓": "Learned ✓", "Die Anlage kennt deine Objekte. Weiter mit dem Prüfen.": "The cell knows your objects. Continue with inspecting.",
  "Bereit zum Lernen": "Ready to learn",
  "Zwei oder mehr Objekte haben genug Fotos. Rechts oben „Lernen …“ drücken.": "Two or more objects have enough photos. Press “Learn …” at the top right.",
  "Schritt 2 · {}/2 Objekte fertig": "Step 2 · {}/2 objects done",
  "Lege mindestens zwei Objekte an und mache je {} Fotos — Teil in den Rahmen legen, Leertaste.": "Create at least two objects and take {} photos of each — place the part in the frame, press space.",
  "Tipp: Erst in Schritt 1 das Leerbild merken.": "Tip: record the empty image in step 1 first.",
  "Eingerichtet ✓": "Set up ✓", "Kamera und Hintergrund passen. Weiter mit dem Anlernen.": "Camera and background are fine. Continue with teaching.",
  "Kamera scharf stellen": "Focus the camera", "Teil unter die Kamera legen, „Scharf stellen“ drücken.": "Place a part under the camera, press “Focus”.",
  "Scharf stellen": "Focus", "Teil wegnehmen — die Anlage merkt sich den leeren Hintergrund.": "Remove the part — the cell records the empty background.",
  "Aufnahmefenster anpassen": "Adjust the capture window",
  "Den Rahmen so groß ziehen, dass ein Teil gut hineinpasst (Ecke ziehen oder Mausrad).": "Size the frame so a part fits comfortably (drag a corner or use the mouse wheel).",
  "Zum Einrichten": "To setup", "Zwei Objekte fotografieren": "Photograph two objects",
  "Je Objekt {} Fotos — in verschiedenen Lagen.": "{} photos per object — in different positions.", "Zum Anlernen": "To teaching",
  "Die Fotos auf den Chip bringen — dauert Sekunden.": "Put the photos onto the chip — takes seconds.",
  "Erste Prüfung": "First inspection", "Teil auflegen und PRÜFEN drücken (oder Leertaste).": "Place a part and press INSPECT (or the space bar).",
  "Zum Prüfen": "To inspecting", "{} von 6 erledigt": "{} of 6 done",
  "Alles hakt sich von selbst ab. Du kannst jeden Punkt auch später machen.": "Everything ticks itself off. You can do any step later.",
  "Schließen — jederzeit wieder über „Erste Schritte“": "Close — reopen any time via “First steps”"
});

if (window.spracheNachladen) window.spracheNachladen();
''')
    D.write_text(d, encoding="utf-8")
    print("sprache_en.js: Nachtrag 11")
