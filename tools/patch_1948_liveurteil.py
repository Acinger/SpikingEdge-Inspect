#!/usr/bin/env python3
"""UI 1.9.48 — Live-Urteil als Kopf der Pruef-Kachel (Anmerkung Ace):

Ganz oben, gross, mit Konfidenzbalken (Schwelle als Markierung) und
Aufschluesselung je Klasse als Balken; Zahlen springen beim Wechsel kurz
auf (sanfte Animation). Danach PRUEFEN-Knopf, dann die Zaehler.
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
if "function liveUrteilHtml" in h:
    print("index.html: schon gepatcht")
else:
    h = ers(h, '''  const stat = STATIONAER() ? pruefStationaerKopf(P, zeit) : "";
  return `<div class="block"><section class="ops-pruef-summary">${stat}<div class="btitel">
      <span>${STATIONAER() ? "Livebild" : "Aktuelles Prüfurteil"}</span></div>
    <div class="pu-urteil ${L.urteil}">
      <b>${U[L.urteil] || "—"}</b>
      <div><div class="pu-name">${txt(L.name || (L.urteil === "leer"
          ? "Kein Teil im Fenster" : "Nicht zugeordnet"))}</div>
        <small>${txt(L.grund || "")}${konf ? " · " + konf : ""}</small></div>
    </div>
    <div class="pu-stat">''', '''  const stat = STATIONAER() ? pruefStationaerKopf(P, zeit) : "";
  return `<div class="block"><section class="ops-pruef-summary">
    ${liveUrteilHtml(L, P, U)}
    ${stat}
    <div class="pu-stat">''')
    h = ers(h, '''/* TESTSATZ (A6, 1.9.45): Pruefszenen mit Soll-Werten sammeln. */''', '''/* LIVE-URTEIL (1.9.48): grosser Kopf mit Balken. */
function liveUrteilHtml(L, P, U) {
  const erk = (Z && Z.erkannt) || {};
  const leer = L.urteil === "leer";
  const k = L.konfidenz != null ? Math.max(0, Math.min(1, L.konfidenz)) : 0;
  const pct = Math.round(k * 100);
  const schw = P.schwelle != null ? Math.round(P.schwelle * 100) : null;
  const alle = (erk.alle || []).slice().sort((a, b) => b.anteil - a.anteil).slice(0, 4);
  const teile = (erk.je_objekt || []).length;
  const name = L.name || (leer ? "Kein Teil im Fenster" : "Nicht zugeordnet");
  const balken = leer ? "" : `
    <div class="lu-balken" title="Übereinstimmung mit dem gelernten Muster${schw != null ? ` · Schwelle ${schw} %` : ""}">
      <div class="lu-fuell" style="width:${pct}%"></div>
      ${schw != null ? `<i class="lu-schwelle" style="left:${schw}%"></i>` : ""}
      <span class="lu-pct">${pct} %</span>
    </div>`;
  const klassen = (!leer && alle.length > 1) ? `<div class="lu-klassen">${alle.map(a => `
      <div class="lu-k ${a.name === L.name ? "sieger" : ""}"><span class="lu-kn">${txt(a.name)}</span>
        <div class="lu-kb"><div style="width:${Math.round(Math.max(0, Math.min(1, a.anteil)) * 100)}%"></div></div>
        <span class="lu-kv">${Math.round(a.anteil * 100)}</span></div>`).join("")}</div>` : "";
  return `<div class="lu ${L.urteil}" data-lu="${txt(L.urteil + ":" + name + ":" + pct)}">
    <div class="lu-kopf"><span class="lu-urteil">${U[L.urteil] || "—"}</span>
      <span class="lu-teile">${teile ? (teile === 1 ? "1 Teil" : teile + " Teile") : ""}</span></div>
    <div class="lu-name">${txt(name)}</div>
    ${balken}
    <div class="lu-grund">${txt(L.grund || "")}</div>
    ${klassen}
  </div>`;
}
/* TESTSATZ (A6, 1.9.45): Pruefszenen mit Soll-Werten sammeln. */''')
    # CSS
    h = ers(h, '''.vfenster { display:inline-flex; align-items:center; gap:4px; margin-right:6px; }''', '''/* Live-Urteil (1.9.48) */
.lu { --luc:var(--leise,#8a94a0); --lub:rgba(128,128,128,.08); position:relative; border:1px solid var(--rand,#333b43); border-left:6px solid var(--luc);
  border-radius:8px; padding:14px 16px 12px; margin-bottom:12px; background:var(--lub); transition:background .35s,border-color .35s; }
.lu.gut { --luc:var(--gut,#22c55e); --lub:var(--ops-good-bg,rgba(34,197,94,.10)); }
.lu.unbekannt { --luc:var(--warn,#ffc62e); --lub:var(--ops-warn-bg,rgba(255,198,46,.10)); }
.lu.ausschuss { --luc:var(--rot,#ff2d7a); --lub:var(--ops-bad-bg,rgba(255,45,122,.12)); }
.lu-kopf { display:flex; align-items:baseline; justify-content:space-between; gap:10px; }
.lu-urteil { font-size:40px; line-height:1; font-weight:800; letter-spacing:-1.5px; color:var(--luc); animation:luPop .35s ease-out; }
.lu-teile { font-size:11px; font-weight:700; letter-spacing:.08em; text-transform:uppercase; color:var(--leise,#8a94a0); }
.lu-name { margin-top:8px; font-size:22px; font-weight:700; letter-spacing:-.3px; color:var(--text); overflow-wrap:anywhere; }
.lu-balken { position:relative; height:14px; margin:10px 0 4px; border-radius:7px; background:rgba(127,127,127,.18); overflow:visible; }
.lu-fuell { height:100%; border-radius:7px; background:linear-gradient(90deg,var(--luc),var(--luc) 70%,rgba(255,255,255,.35)); transition:width .4s ease; }
.lu-schwelle { position:absolute; top:-4px; bottom:-4px; width:2px; background:var(--text); opacity:.6; }
.lu-pct { position:absolute; right:8px; top:-1px; font-size:11px; font-weight:800; color:var(--text); line-height:16px; }
.lu-grund { font-size:12px; color:var(--leise,#8a94a0); margin-top:4px; }
.lu-klassen { margin-top:10px; display:grid; gap:4px; }
.lu-k { display:grid; grid-template-columns:minmax(60px,1fr) 2fr 34px; align-items:center; gap:8px; font-size:11px; color:var(--leise,#8a94a0); }
.lu-k.sieger { color:var(--text); font-weight:700; }
.lu-kb { height:6px; border-radius:3px; background:rgba(127,127,127,.18); overflow:hidden; }
.lu-kb div { height:100%; background:var(--luc); opacity:.55; transition:width .4s ease; }
.lu-k.sieger .lu-kb div { opacity:1; }
.lu-kv { text-align:right; font-variant-numeric:tabular-nums; }
@keyframes luPop { from { transform:scale(.92); opacity:.4; } to { transform:none; opacity:1; } }
body#opsApp[data-ui="ops2"].se .lu-urteil { font-family:"Inter",system-ui,sans-serif; }
.vfenster { display:inline-flex; align-items:center; gap:4px; margin-right:6px; }''')
    H.write_text(h, encoding="utf-8")
    print("index.html gepatcht")

s = S.read_text(encoding="utf-8")
if "1.9.48-liveurteil" not in s:
    s = ers(s, 'BUILD = "1.9.47-fenster"', 'BUILD = "1.9.48-liveurteil"')
    S.write_text(s, encoding="utf-8"); print("server.py gepatcht")
