# VORSA-M3 — Plan für vier Karten

Stand 2026-08-27. Vorschlag zur Abstimmung.

Vier AKD1500 sind kein „viermal dasselbe schneller" — richtig eingesetzt
sind sie vier verschiedene Rollen. Der Plan hat zwei Stufen: was **heute**
geht (ohne M3-Training), und was das **Endprodukt** wird (mit).

---

## Stufe 1 — sofort umsetzbar

### 1a. Viermal mehr Gedächtnis (größter Sofortgewinn)

Die härteste Grenze des Silhouetten-Abgleichs ist die Neuronenzahl: eine
Karte fasst ~128 Ansichten je Objekt, dann teilen sich Ansichten einen
Platz. Vier Karten lernen **denselben Bestand, aber verschiedene Anteile**
der Ansichten — zusammen 4× so viele gespeicherte Silhouetten je Objekt.
Bei der Erkennung fragt der Pi alle vier und nimmt die beste
Übereinstimmung.

Warum das trifft: unsere Fehler sind fast immer „diese eine Drehlage war
nicht im Gedächtnis". Mehr Schablonen decken mehr Lagen ab.

### 1b. Der Neuheitswächter

Karte 1 bekommt eine eigene Aufgabe: sie lernt NUR die Frage „kenne ich
das überhaupt?" — alle Objekte zusammen gegen die Negativklasse. Fällt
ihre Übereinstimmung unter die Schwelle, meldet die Anlage **unbekanntes
Teil** statt der besten Fehlzuordnung. Das ist der Unterschied zwischen
einem Demo und einem Produkt: ein Produkt sagt „weiß ich nicht", statt
selbstbewusst falsch zu liegen.

### 1c. Schattenlernen (das Produktmerkmal)

Neue Objekte werden auf einer **Reserve-Karte** angelernt, während Karte 0
ununterbrochen weiter erkennt. Erst wenn die Gegenprobe auf der
Reserve-Karte sitzt, tauschen die beiden ihre Rollen — ein Handgriff, null
Stillstand. Anlernen im laufenden Betrieb, ohne die Linie anzuhalten:
das kann kein Kamerasystem von der Stange.

### 1d. Durchsatz nebenbei

Liegen mehrere Teile im Bild, verteilt der Pi die Ausschnitte
reihum auf die Karten statt alle nacheinander über Karte 0. Der
`akida_pool` aus der ersten Projektwoche macht genau das. Gewinn:
Latenz, nicht Genauigkeit — deshalb Beifang, kein Hauptgericht.

---

## Stufe 2 — das Endprodukt (nach dem M3-Training)

### 2a. Finden und Bestätigen: die zweistufige Erkennung

    Karten 0-2   M3-Detektor      FINDET: mehrere Teile, Kasten, Winkel,
                                  Verdeckungsgrad - auch bei Überlappung
    Karte 3      Silhouetten-     BESTÄTIGT: jeder gefundene Ausschnitt
                 Abgleich         wird gegen die gelernten Muster geprüft

Der Detektor liefert Kandidaten, der Verifizierer drückt die Fehlalarme.
Zwei unabhängige Verfahren müssen sich einig sein — die Kombination ist
genauer als jedes allein, und beide laufen auf Neuromorphik; der Pi
orchestriert nur.

### 2b. Drei Karten, drei Blickweisen auf dasselbe Bild

Die Detektor-Karten 0-2 arbeiten nicht dasselbe ab, sondern:

    Karte 0   volles Bild, 256 px    Übersicht: wo liegt überhaupt etwas
    Karte 1   linke Bildhälfte       Detail in voller Schärfe
    Karte 2   rechte Bildhälfte      Detail in voller Schärfe

Damit steigt die effektive Auflösung des Detektors, ohne das
Ein-Durchgangs-Kernziel je Karte anzutasten. Kleine Teile, die im
256-px-Gesamtbild vier Pixel groß wären, bekommen echte Kontur.

### 2c. Die Energiegeschichte wird erst damit rund

Vier Karten × gemessene ~300 mW plus Pi ≈ unter 4 W für ein System, das
findet, klassifiziert, verifiziert und zählt. Der Messen-Abschnitt
rechnet das heute schon ehrlich — mit vier aktiven Karten wird daraus
das Verkaufsargument: Wh je 1000 geprüfte Teile, gemessen, nicht
behauptet.

---

## Ehrlichkeit zuerst

Was die vier Karten NICHT können: eine schwache Erkennung in eine starke
verwandeln. Wenn die Silhouette zweier Teile gleich aussieht, sehen vier
Karten viermal dieselbe Silhouette. Der größte einzelne Sprung bleibt das
M3-Training — die Karten machen aus einem guten Verfahren ein
belastbares System, nicht aus einem schwachen ein gutes.

## Vorgeschlagene Reihenfolge

    1   1a Gedächtnis ×4 + 1d Pool     ERLEDIGT (Verbund, jetzt Karten 0-2)
    2   1b Neuheitswächter             ERLEDIGT (55-%-Schwelle, Torsomass)
    3   M3-Training über Nacht         ERLEDIGT (vorsa_m3.fbz, Karte 3)
    4   2a Detektor + Verifizierer     ERLEDIGT als NOTNAGEL-Kaskade:
                                       Geometrie+Chip zuerst, Detektor nur
                                       fuer unbenannte Reste (2026-08-28)
    5   1c Schattenlernen              offen
    6   M3-Nachtraining                offen: Kaesten bei satter
                                       Ueberlappung sitzen noch schief

## Stufe 3 — Zweitkamera als Zweitmeinung (2026-08-28)

Die USB-Webcam schaut seitlich mit. Sie ist KEIN permanenter zweiter
Feed, sondern eine Zweitmeinung: nur wenn der Hauptfeed "unbekannt"
oder eine knappe Entscheidung meldet, geht ein Webcam-Schnappschuss
durch denselben Verbund (mit eigens angelernten Seitenansichten) und
darf das Urteil kippen. Kein Kalibrier- und kein Fusionsproblem - und
genau in den Faellen wirksam, die von oben prinzipiell unloesbar sind.
Voraussetzung: kontrastreicher Hintergrund fuer die Seitenansicht.
