#!/usr/bin/env python3
"""1.9.72: Testlauf laesst sich nicht mehr durch einen Moduswechsel entwerten.

Pi 2026-10-04: ab Szene 20 lieferte der Testlauf nur noch "-" - waehrend des
Laufs wurde auf Anlernen umgeschaltet (dann setzt die Schleife erkannt=None).
Jetzt: /api/betriebsart antwortet 409 "Testlauf laeuft" solange der Lauf
geht; bricht der Modus trotzdem weg, bricht der Lauf mit klarem Grund ab,
statt leere Szenen zu zaehlen. Idempotent."""
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
S = ROOT / "vorsa/web/server.py"; E = ROOT / "vorsa/web/static/sprache_en.js"; H = ROOT / "vorsa/web/static/index.html"
s, e, h = S.read_text(encoding="utf-8"), E.read_text(encoding="utf-8"), H.read_text(encoding="utf-8")
if "Testlauf läuft – erst abwarten" in s:
    print("schon angewendet"); raise SystemExit(0)
def ers(t, a, b):
    assert t.count(a) == 1, (a[:60], t.count(a)); return t.replace(a, b)
s = ers(s, 'BUILD = "1.9.71-m3fortschritt"', 'BUILD = "1.9.72-testlauf"')
s = ers(s, '''                if art not in ("einrichten", "anlernen", "betreiben", "messen"):
                    return self._json({"fehler": f"Betriebsart {art!r} unbekannt"}, 400)
                zustand.betriebsart = art''', '''                if art not in ("einrichten", "anlernen", "betreiben", "messen"):
                    return self._json({"fehler": f"Betriebsart {art!r} unbekannt"}, 400)
                if getattr(verarbeitung, "_testlauf", {}).get("laeuft") and art != "betreiben":
                    return self._json({"ok": False, "fehler": "Testlauf läuft – erst abwarten (Einstellungen › Erkennung)",
                                       "grund": "Testlauf läuft – erst abwarten (Einstellungen › Erkennung)"}, 409)
                zustand.betriebsart = art''')
s = ers(s, '''                self._testbild = b
                start = getattr(self, "_takt", 0)
                bis = time.time() + 8.0
                while time.time() < bis and getattr(self, "_takt", 0) < start + 6:
                    time.sleep(0.03)
                erk = self.zustand.erkannt or {}''', '''                if str(self.zustand.betriebsart) != "betreiben":
                    raise RuntimeError("Betriebsart wurde während des Testlaufs gewechselt – Lauf abgebrochen, bitte wiederholen")
                self._testbild = b
                start = getattr(self, "_takt", 0)
                bis = time.time() + 8.0
                while time.time() < bis and getattr(self, "_takt", 0) < start + 6:
                    time.sleep(0.03)
                erk = self.zustand.erkannt or {}''')
e = ers(e, "if (window.spracheNachladen) window.spracheNachladen();", '''/* ---- Nachtrag 26 (1.9.72 Testlauf) ---- */
Object.assign(window.SPRACHEN.en, {
  "Testlauf läuft – erst abwarten (Einstellungen › Erkennung)": "Test run in progress – wait for it to finish (Settings › Recognition)",
  "RuntimeError: Betriebsart wurde während des Testlaufs gewechselt – Lauf abgebrochen, bitte wiederholen": "RuntimeError: Mode was changed during the test run – run aborted, please repeat"
});

if (window.spracheNachladen) window.spracheNachladen();''')
h = ers(h, '''  await hole("/api/betriebsart", { art: m });
  if (m === "anlernen" && !AKTIV && echt().length) AKTIV = echt()[0].id;
  await aktualisieren();
}''', '''  const r = await hole("/api/betriebsart", { art: m });
  if (r && r.ok === false && r.grund) {
    // 1.9.72: Server lehnt ab (z. B. Testlauf laeuft) - Oberflaeche folgt dem Server.
    MELDUNG = r.grund; setTimeout(() => { MELDUNG = ""; }, 4000);
    MODUS = (Z && Z.betriebsart) || "betreiben";
    document.querySelectorAll(".modus").forEach(b => b.classList.toggle("an", b.dataset.modus === MODUS));
  }
  if (m === "anlernen" && !AKTIV && echt().length) AKTIV = echt()[0].id;
  await aktualisieren();
}''')
S.write_text(s, encoding="utf-8"); E.write_text(e, encoding="utf-8"); H.write_text(h, encoding="utf-8")
print("ok 1.9.72")
