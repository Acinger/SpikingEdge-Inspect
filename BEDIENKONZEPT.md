# VORSA-M3 — Bedienkonzept

Stand 2026-08-26. Vorschlag zur Abstimmung, noch nicht gebaut.

---

## 1. Leitsatz

Die Anlage hat drei Tätigkeiten, und sie gehören nie gemischt:

    EINRICHTEN     ein Bild herstellen, das gleich bleibt
    ANLERNEN       dem System beibringen, was deine Teile sind
    BETREIBEN      laufen lassen und zählen

Eine vierte prüft die anderen drei:

    MESSEN         was kostet es an Zeit und Strom, und hält das Kernziel

Die heutige Oberfläche macht alles gleichzeitig. Deshalb sagt kein Element,
was gerade passiert — das ist die Ursache, nicht die Anordnung der Kästen.

---

## 2. Aufteilung des Bildschirms

    ┌─────────────────────────────────────────────────────────────┐
    │ VORSA-M3   Einrichten │ Anlernen │ Betreiben │ Messen   ⚙ ● │
    ├──────────────────────────────────────────┬──────────────────┤
    │                                          │                  │
    │            Kamerabild, formatfüllend     │   Spalte des     │
    │                                          │   Modus          │
    │   ┌────────────┐                         │                  │
    │   │ ein Griff  │  Inhalt hängt vom       │   Nur EIN Thema  │
    │   │ links      │  Modus ab               │   gleichzeitig   │
    │   └────────────┘                         │                  │
    │                                          │                  │
    │   grosse Ergebniszeile                   │                  │
    ├──────────────────────────────────────────┴──────────────────┤
    │ BILDRATE  LATENZ  AUSSCHNITT  OBJEKTE  FOTOS  CHIP          │
    └─────────────────────────────────────────────────────────────┘

**Regel:** Kein Panel zeigt etwas, das der aktuelle Modus nicht braucht.
Alles Seltene liegt hinter dem Zahnrad, nicht im Bild.

Der Fuß bleibt in allen Modi gleich. Er ist der Ort, an dem man ohne
Hinsehen merkt, dass etwas nicht stimmt.

---

## 3. Die vier Modi

### 3.1 Einrichten

Ziel: ein Bild, das sich nicht mehr ändert.

- Fenstergröße und Lage des Ausschnitts
- Kameraregler: Fokus, Weißabgleich, Belichtung, Helligkeit, Kontrast,
  Sättigung, Verstärkung — je Regler sichtbar, ob die Kamera ihn annimmt
- Automatik an / Werte festhalten
- Einstellungen als Preset sichern und laden
- **Schärfeanzeige** (Laplace-Varianz als Balken): Autofokus wird beurteilbar
  statt geraten
- **Übersteuerung sichtbar machen**: ausgebrannte Flächen rot einfärben. Ein
  überstrahltes Teil verliert genau die Kanten, aus denen die Kontur entsteht
- **Kalibrierung im Browser**: vier Ecken auf ein bekanntes Rechteck klicken,
  Restfehler in mm wird angezeigt. Der Rechenteil dafür liegt fertig in
  `calibration.residual_check` und ist heute nicht erreichbar

**Neue Funktion, die ich für die wichtigste halte — Einstellungsdrift:**
Beim Trainieren wird die Kameraeinstellung mitgespeichert. Weicht sie später
ab, meldet die Oberfläche das im Klartext:

    Einstellung seit dem Anlernen verändert:
    Weißabgleich 4200 → 5100, Belichtung -6 → -4

Ohne diese Meldung sucht man den Fehler im Modell, während er in der Kamera
sitzt. Das ist der häufigste Weg, ein funktionierendes System für kaputt zu
halten.

### 3.2 Anlernen

Erkennung pausiert, das Bild zeigt nur den Aufnahmerahmen.

- Objektliste. Klick auf ein Objekt öffnet dessen **Lernfenster**
- Lernfenster: Name, alle Fotos als Raster, jedes löschbar, jedes anklickbar
  für die Variantenvorschau, Fortschritt, großer Aufnahmeknopf
- Varianten je Objekt (spiegeln, 90°-Schritte, frei drehen, händig) —
  gehören zum Objekt, nicht zur Kamera. Ein händiges Teil darf nicht
  gespiegelt werden, ein symmetrisches schon
- **Aufnahmeserie**: „10 Fotos, alle 0,8 s". Man dreht das Teil, statt
  zehnmal zu klicken
- **Sofortprüfung je Foto**: lässt sich das Teil vom Hintergrund trennen?
  Wie groß ist sein Flächenanteil? Ist es scharf? Ein unbrauchbares Foto
  wird beim Speichern markiert, nicht erst beim Training
- **Ähnlichkeitswarnung vor dem Training**: zwei Objekte mit zu nah
  beieinanderliegenden Merkmalen werden verwechselt. Das ist genau der
  Fehler, den wir am 26.08. gemessen haben — ähnliche Fläche, ähnliche
  Helligkeit. Er lässt sich vorher ansagen
- **Negativklasse „nichts / Störteil"**: ohne sie meldet der Chip immer
  eines der gelernten Objekte, auch bei leerem Band. Fehlt heute

**Trainingsdialog** (zeigt vorher, was wirklich hingeht):

    Objekt      Fotos   gesamt
    Winkel        3       24
    Mutter        5       40
    ─────────────────────────
    2 Objekte     8       64

    ⚠ „Winkel" hat nur 3 Fotos — gemessen waren 5 nötig
    64 Beispiele × 2 ms ≈ 0,1 s

    [Auf dem Chip lernen]   [M3 voll trainieren]   [Abbrechen]

Die beiden Knöpfe sind zwei verschiedene Dinge und werden im Dialog auch so
benannt: der erste braucht Sekunden und erkennt ein Teil im Ausschnitt, der
zweite braucht Minuten bis Stunden und findet mehrere Teile mit Kasten und
Winkel.

### 3.3 Betreiben

Wenig Bedienung, große Zahlen.

- Zählwerk je Objekt, Schichtzähler, Rücksetzen
- **Ereignisprotokoll**: jeder „unklar"-Fall wird mit Bild abgelegt. Das ist
  das Material für die nächste Trainingsrunde — die Anlage sammelt ihre
  eigenen schweren Fälle
- **Grenzwerte**: steigt der Anteil „verdeckt" oder „unklar" über einen Wert,
  wird gemeldet. Meist ist dann etwas Mechanisches passiert, nicht etwas
  Rechnerisches
- **Ausgabe nach außen**: CSV oder JSONL mitschreiben. Später Feldbus, MQTT
  oder ein einfacher HTTP-Abruf für die Anlagensteuerung

### 3.4 Messen

- **Kernziel-Prüfung**: Variantentabelle mit PASS/FAIL, Sequenzen, Passes,
  belegte NPs. Läuft heute nur auf der Kommandozeile
- **Pi gegen AKD1500**: Zeit je Bild, Median und 95er, Bilder je Sekunde
- **Energie je 1000 erkannte Objekte** — das Kernmaß des Projekts.
  Ausdrücklich gekennzeichnet: Zeiten gemessen, Energie gerechnet. Der Pi hat
  keinen Stromsensor. Die angenommene Leistung steht bei jedem Ergebnis
  dabei und ist durch einen Messwert vom Steckdosenmessgerät ersetzbar
- **Dauerlauf** über zehn Minuten mit Temperatur: die Drosselung des Pi
  fällt in einer Zehn-Bilder-Messung nie auf
- **Wiedererkennungsprobe**: ein Teil neu fotografieren und gegen das
  Gelernte prüfen, ohne es zu lernen. Das ist die einzige ehrliche Gütezahl.
  Die Gegenprobe auf den Lernbildern ist keine, und sie wird auch heute
  schon so beschriftet

---

## 4. Anzeige

Einzeln schaltbar, weil dieselben Daten unterschiedlich dicht gebraucht
werden:

| Schalter | wirkt |
|---|---|
| Aufnahmerahmen | blauer Rahmen um den Ausschnitt |
| Außen abdunkeln | alles außerhalb des Rahmens |
| Objektrahmen | gedrehte Kästen |
| Konturen | sichtbare Außenlinie |
| Längsachse | Richtung des Teils |
| Beschriftung | ID, Klasse, Winkel, Maße |
| Legende | Zählung oben links |

Drei Voreinstellungen, damit man nicht sieben Schalter bedient:

- **Sauber** — nur das Bild
- **Arbeiten** — Aufnahmerahmen, Objektrahmen, Konturen
- **Prüfen** — alles, mit Winkel und Millimetern

Bei sechs Teilen verdecken Beschriftungen mehr, als sie erklären. Wer die
Trennung zweier berührender Teile beurteilen will, braucht die Konturen ohne
alles andere.

---

## 5. Einstellungsfenster (Zahnrad)

Ein Dialog, links die Abschnitte:

    Aufnahme    Kameraregler in voller Breite, Presets verwalten
    Anzeige     alle Schalter aus Abschnitt 4
    Objekte     Klassen anlegen, umbenennen, löschen, Varianten je Objekt
    Modell      aktive Variante, Eingangsgröße, Raster, NPs, Passes
    Messen      Leistungsannahmen, Umfang der Messreihen
    Daten       Datenordner, belegter Platz, alles löschen, Sicherung
    Über        Versionen von MetaTF, TensorFlow, cnn2snn, Gerät

Die schwebenden Panels im Bild behalten nur die Griffe, die man **während**
der Arbeit braucht. Alles, was man einmal einstellt, zieht hierher um.

---

## 6. Bedienregeln

1. **Jede zerstörende Aktion fragt und sagt vorher, was verloren geht.**
   Vergessen, Objekt löschen, neu trainieren.
2. **Jede Zahl sagt, woher sie kommt.** Gemessen oder gerechnet. Wo eine
   Annahme drinsteckt, steht sie daneben.
3. **Keine stille Ersatzhandlung.** Fällt die Kamera aus, sagt die
   Oberfläche das. Sie schaltet nicht heimlich auf Testbilder um — genau das
   hat uns einen halben Tag gekostet.
4. **Tastatur:** Leertaste Foto, 1–8 Objekt wählen, Tab Modus wechseln.
5. **Ein Weg vorwärts.** Wer nichts angelegt hat, sieht genau einen Knopf.

---

## 7. Erster Start

Über der Bühne eine Leiste mit drei Schritten, die abhakt, was erledigt ist:

    ① Bild einrichten  ──  ② Objekte anlernen  ──  ③ Betrieb

Sie verschwindet, sobald alle drei erledigt sind, und kommt zurück, wenn
etwas wegfällt — etwa wenn das Gelernte verworfen wurde.

---

## 8. Reihenfolge des Baus

| # | Was | Warum zuerst |
|---|---|---|
| 1 | Modi, Lernfenster, Trainingsdialog | ohne sie ist nichts bedienbar |
| 2 | Anzeigeschalter | klein, sofort spürbar |
| 3 | Einstellungsfenster | nimmt den Panels die Last ab |
| 4 | Messen: Kernziel, Pi gegen AKD1500 | prüft, was wir behaupten |
| 5 | Negativklasse, Sofortprüfung, Serie | macht das Anlernen belastbar |
| 6 | Einstellungsdrift, Ereignisprotokoll | macht den Betrieb belastbar |
| 7 | Kalibrierung im Browser, Ausgabe nach außen | Anschluss an die Anlage |

---

## 9. Was ich bewusst NICHT vorschlage

- **Benutzerverwaltung und Rechte.** Eine Maschine an einem Band, ein
  Bediener. Rechte kosten Bedienschritte und verhindern hier nichts.
- **Mehrere Modelle gleichzeitig verwalten.** Ein AKD1500, ein Modell. Eine
  Verwaltungsebene für etwas, das es nur einmal gibt, ist Ballast.
- **Bearbeiten der Fotos in der Oberfläche.** Zuschneiden, Drehen, Retusche
  — wer das braucht, hat den Ausschnitt falsch eingerichtet. Der richtige
  Ort ist Schritt 1, nicht eine Nachbearbeitung.
- **Beschriften von Hand.** Für M3 werden die Szenen aus den freigestellten
  Fotos zusammengesetzt, dadurch ist die Beschriftung exakt bekannt. Wer
  Überlappungsbilder von Hand beschriftet, rät bei genau der Größe, auf die
  es ankommt: wo das verdeckte Teil endet.
