#!/usr/bin/env python3
"""1.9.54 Teil 2 — Einkamera-Version, Reste raus (Anmerkung Ace, Screenshot):
* alter Kamera-Streifen (#kamHaupt mit "Mehr"-Reglern) entfernt — er kam ueber
  localStorage (nbes_kamleiste_haupt) wieder hoch und lag unter dem Dock
* JEDER Kamera-Knopf (Hauptbild, Zonen Anlieferung/Abholung, Rechtsklick)
  oeffnet das Kamera-Dock: eine Kamera, eine Einstellung
* Rechtsklick-Menue wird nie mehr abgeschnitten (im Bild gehalten, scrollt)
"""
import re
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
H = ROOT / "vorsa" / "web" / "static" / "index.html"
D = ROOT / "vorsa" / "web" / "static" / "sprache_en.js"
def ers(t, a, n, k=1):
    if t.count(a) != k: raise SystemExit(f"FEHLER: {t.count(a)}x statt {k}x: {a[:120]}")
    return t.replace(a, n)
h = H.read_text(encoding="utf-8")
if 'id="kamHaupt"' not in h:
    print("index.html: schon gepatcht")
else:
    h, n = re.subn(r'    <div class="lfkam" id="kamHaupt" data-art="haupt" hidden>.*?\n    </div>\n', '', h, count=1, flags=re.S)
    assert n == 1
    h = ers(h, 'title="Kamera: Fokus, Belichtung, Leerbild" aria-controls="kamHaupt" aria-expanded="false">',
            'title="Kamera: Bild, Farbe, Fenster, Leerbild" aria-controls="kamDock" aria-expanded="false">')
    h = ers(h, '''try { if ($("kamHaupt") && !$("kamHaupt").hidden) $("videoteil").classList.add("kamoffen"); } catch (e) {}\n''', '')
    h = ers(h, '''try {
  for (const a of ["anliefer", "abhol", "haupt"]) {
    const b = $(feedId(a, "kam"));
    if (b) b.hidden = localStorage.getItem("nbes_kamleiste_" + a) !== "1";
  }
} catch (e) {}''', '''// 1.9.54: eine Kamera, eine Einstellung - die Zonen-Streifen bleiben zu,
// jeder Kamera-Knopf oeffnet das Dock. Alte Merker loeschen.
try { for (const a of ["anliefer", "abhol", "haupt"]) localStorage.removeItem("nbes_kamleiste_" + a); } catch (e) {}''')
    h = ers(h, '''  if (tat === "kamdock" || (tat === "feed_kam" && el.dataset.art === "haupt")) {
    kamDockSetzen(!KAMDOCK_OFFEN);
    if (MENUE_KONTEXT) ansichtMenueZeigen(false);
    return;
  }
  if (tat === "feed_kam") {
    // Kamera-Leiste dieser Kachel (oder des Hauptbilds) ein-/ausblenden;
    // je Feed gemerkt. UI 2.2: Standard zu.
    const art = el.dataset.art;
    const bar = $(feedId(art, "kam"));
    if (bar) {
      bar.hidden = !bar.hidden;
      try { localStorage.setItem("nbes_kamleiste_" + art,
                                 bar.hidden ? "0" : "1"); } catch (e) {}
      if (bar.hidden) { const mb = $(feedId(art, "mehr")); if (mb) mb.hidden = true; }
      if (art === "haupt") $("videoteil").classList.toggle("kamoffen", !bar.hidden);
      try { leerbildKnoepfe(); } catch (e) {}
    }
    opsSync();
    return;
  }''', '''  if (tat === "kamdock" || tat === "feed_kam") {
    // 1.9.54: Einkamera-Version - jeder Kamera-Knopf (Hauptbild, Zone,
    // Rechtsklick) oeffnet dasselbe Dock.
    kamDockSetzen(!KAMDOCK_OFFEN);
    if (MENUE_KONTEXT) ansichtMenueZeigen(false);
    opsSync();
    return;
  }''')
    h = ers(h, '''  document.querySelectorAll('[data-tat="feed_kam"]').forEach(b => {
    const id = feedId(b.dataset.art, "kam");
    const bar = $(id);
    b.setAttribute("aria-controls", id);
    b.setAttribute("aria-expanded", String(!!bar && !bar.hidden));
    b.classList.toggle("an", !!bar && !bar.hidden);
  });''', '''  document.querySelectorAll('[data-tat="feed_kam"]').forEach(b => {
    b.setAttribute("aria-controls", "kamDock");
    b.setAttribute("aria-expanded", String(KAMDOCK_OFFEN));
    b.classList.toggle("an", KAMDOCK_OFFEN);
  });''')
    # Rechtsklick-Menue: im Bild halten, bei wenig Platz scrollen
    h = ers(h, '''  if (kontext) {
    const vt = $("videoteil"); const vr = vt.getBoundingClientRect();
    const x = Math.min(kontext.x, Math.max(0, vr.width - 250)), y = Math.min(kontext.y, Math.max(0, vr.height - 330));
    m.style.left = x + "px"; m.style.top = y + "px"; m.style.right = "auto";
  } else { m.style.left = ""; m.style.top = ""; m.style.right = ""; }
  if (an) ansichtMenueMalen();''', '''  if (an) ansichtMenueMalen();
  if (kontext) {
    const vt = $("videoteil"); const vr = vt.getBoundingClientRect();
    const mh = Math.min(m.offsetHeight || 330, vr.height - 16);
    const x = Math.min(kontext.x, Math.max(0, vr.width - (m.offsetWidth || 250) - 8));
    const y = Math.min(kontext.y, Math.max(8, vr.height - mh - 8));
    m.style.left = x + "px"; m.style.top = y + "px"; m.style.right = "auto"; m.style.maxHeight = mh + "px";
  } else { m.style.left = ""; m.style.top = ""; m.style.right = ""; m.style.maxHeight = ""; }''')
    h = ers(h, '''      <button class="mini" data-tat="feed_kam" data-art="haupt">Kamera-Leiste</button>''',
            '''      <button class="mini" data-tat="feed_kam" data-art="haupt">Kamera-Einstellungen</button>''')
    h = ers(h, '''body#opsApp #ansichtMenue .am-kopf {''', '''body#opsApp #ansichtMenue { max-height:calc(100% - 60px); overflow:auto; }
body#opsApp #ansichtMenue .am-kopf {''')
    h = ers(h, '''/* Kamera-Dock (1.9.52) */''', '''/* 1.9.54: Zonen-Kamerastreifen nie mehr - eine Kamera, ein Dock */
#linieAnsicht .lfkam, #linieAnsicht .lfmehr { display:none !important; }
/* Kamera-Dock (1.9.52) */''')
    H.write_text(h, encoding="utf-8"); print("index.html gepatcht")
d = D.read_text(encoding="utf-8")
if "Nachtrag 10" not in d:
    d = ers(d, '\nif (window.spracheNachladen) window.spracheNachladen();\n', '''
/* ---- Nachtrag 10 (1.9.54) ---- */
Object.assign(window.SPRACHEN.en, {
  "Kamera-Einstellungen": "Camera settings", "Kamera: Bild, Farbe, Fenster, Leerbild": "Camera: image, colour, window, empty image"
});

if (window.spracheNachladen) window.spracheNachladen();
''')
    D.write_text(d, encoding="utf-8"); print("sprache_en.js gepatcht")

# ---- Teil 3: "Leerbild" in Englisch ueberall (Anmerkung Ace) ----
h = H.read_text(encoding="utf-8")
if 'const re = new RegExp("^" + kk.replace(/[.*+?^$()|[\\]\\\\]/g, "\\\\$&").replace(/\\{\\}/g, "(\\\\d+(?:[.,]\\\\d+)?)") + "$");' in h:
    # Zahlenmuster {} erfasst jetzt auch Uhrzeit/Datum (12:49, 02.10. 12:49)
    h = h.replace('.replace(/\\{\\}/g, "(\\\\d+(?:[.,]\\\\d+)?)")', '.replace(/\\{\\}/g, "(\\\\d+(?:[ .,:\\\\-]+\\\\d+)*)")')
    H.write_text(h, encoding="utf-8"); print("index.html: Zahlenmuster erweitert")
d = D.read_text(encoding="utf-8")
if '"Leerbild ✓ {}"' not in d:
    d = ers(d, '''  "Kamera-Einstellungen": "Camera settings",''', '''  "Kamera-Einstellungen": "Camera settings",
  "Leerbild ✓ {}": "Empty image ✓ {}", "Leerbild vom {} aktiv — Klick: neu merken": "Empty image from {} active — click to record again",
  "Leerbild verworfen": "Empty image discarded", "Leerbild gemerkt ({}, {} Bilder, Flackern bis {}) — Erkennung läuft jetzt über die Differenz zum leeren Band": "Empty image recorded ({}, {} images, flicker up to {}) — recognition now uses the difference to the empty belt",
  "Leerbild: nicht möglich": "Empty image: not possible", "Leeres Band merken: danach zählt alles als Teil, was sich vom leeren Band unterscheidet": "Record the empty belt: afterwards anything that differs from the empty belt counts as a part",''')
    D.write_text(d, encoding="utf-8"); print("sprache_en.js: Leerbild-Muster")
