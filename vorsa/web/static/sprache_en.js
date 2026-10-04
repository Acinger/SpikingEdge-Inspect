/* SE Inspect — English dictionary for the operator UI (A13, 1.9.39).
   Keys are German text nodes / attributes exactly as rendered (whitespace
   collapsed). "{}" matches a number. Fragments that the markup splits into
   several text nodes are translated as fragments, so they read on in sequence.
   Unknown strings stay German and are collected in window.I18N_FEHLEND. */
window.SPRACHEN = window.SPRACHEN || {};
window.SPRACHEN.en = {
  /* ---- navigation, modes, page names ---- */
  "Betrieb": "Operation", "Erkennung": "Inspection", "Linienbetrieb": "Line mode", "Rezepte": "Recipes",
  "Einrichten": "Setup", "Kamera & Zonen": "Camera & zones", "Kamera": "Camera", "Objekte & Lernen": "Objects & learning",
  "System": "System", "Zustand": "Status", "Meldungen": "Messages", "Hauptnavigation": "Main navigation",
  "Zustand: Hardware, Diagnose, Wartung": "Status: hardware, diagnostics, maintenance",
  "Kamera und Zonen einrichten": "Set up camera and zones", "Objekte anlegen, Fotos aufnehmen, trainieren": "Create objects, take photos, train",
  "Rezepte und Aufträge": "Recipes and jobs", "Rezepte und Aufträge öffnen": "Open recipes and jobs", "Rezepte & Aufträge": "Recipes & jobs",
  "Alarme und Meldungen": "Alarms and messages", "Alarme und Meldungen öffnen": "Open alarms and messages", "Alarme & Meldungen": "Alarms & messages",
  "Helle oder dunkle Darstellung": "Light or dark theme", "Dunkel": "Dark", "Hell": "Light",
  "Navigation ein- oder ausklappen": "Expand or collapse navigation", "Einklappen": "Collapse",
  "BILDERKENNUNG": "IMAGE INSPECTION", "Arbeitsbereich und Linienbefehle": "Work area and line commands",
  "Analyse öffnen": "Open analysis", "Analyse schließen": "Close analysis", "Analyse": "Analysis",
  "Bedienansicht": "Operator view", "Expertenansicht": "Expert view",
  "Nur Ansicht umschalten; Maschinenmodus bleibt unverändert": "Switches the view only; the machine mode is unchanged",
  "Nur die Ansicht ändern; der Maschinenmodus bleibt unverändert": "Changes the view only; the machine mode is unchanged",
  "Bedienansicht ist in der Betriebsart Erkennung verfügbar": "The operator view is available in Inspection mode",
  "Zum Arbeitsbereich": "To the work area", "Lernzonen A / B": "Learning zones A / B", "Einrichtung": "Setup",
  "Objekte & Training": "Objects & training", "Prüfung": "Inspection", "Prüfung und Details": "Inspection and details",
  "Prüfbereich auswählen": "Choose inspection pane", "Prüfdetails": "Inspection details", "Teildetails": "Part details",
  "Erkennungsdetails": "Recognition details", "Vorgang & Hinweise": "Activity & notes", "Zusatzinfos": "Extra info",
  "Betriebsart": "Operating mode", "Warte auf Zustandsdaten": "Waiting for status data",
  "Zustandsdaten werden geladen": "Loading status data", "Zustandsdaten aktuell": "Status data current",
  "Zustandsdaten veraltet · {} s": "Status data stale · {} s",
  "Keine aktuellen Zustandsdaten. Angezeigte Werte können veraltet sein.": "No current status data. Displayed values may be stale.",
  "Kein aktuelles Kamerabild. Die letzte Aufnahme kann veraltet sein.": "No current camera image. The last frame may be stale.",
  "DATEN VERALTET": "DATA STALE", "KEINE VERBINDUNG": "NO CONNECTION", "BILD VERALTET": "IMAGE STALE", "BILD AKTUELL": "IMAGE LIVE",
  "VERBINDE …": "CONNECTING …", "Bildstream aktuell": "Image stream live", "Bildverbindung unterbrochen": "Image connection lost",
  "Bildverbindung wird aufgebaut": "Connecting image stream", "Warte auf Kamerabild …": "Waiting for camera image …",
  "Warte auf Kamera": "Waiting for camera", "Warte auf Kamera ": "Waiting for camera ",

  /* ---- stationary inspection ---- */
  "PRÜFEN": "INSPECT", "Prüfen": "Inspect", "Hand": "Manual", "Auto": "Auto",
  "Alle Teile im Bild jetzt prüfen und buchen (Leertaste)": "Inspect and record all parts in the image now (space bar)",
  "Hand: Knopf oder Leertaste. Auto: jede neue, still liegende Szene wird von selbst geprüft.": "Manual: button or space bar. Auto: every new scene that lies still is inspected by itself.",
  "Prüfung läuft …": "Inspecting …", "Kein Teil im Bild": "No part in the image",
  "Szene geprüft — nächstes Teil auflegen": "Scene inspected — place the next part",
  "Szene steht — Automatik prüft": "Scene is still — auto will inspect", "Szene steht — bereit": "Scene is still — ready",
  "Szene bewegt sich": "Scene is moving", "Livebild": "Live image", "Aktuelles Prüfurteil": "Current verdict",
  "Aktuelles Prüfurteil und Sitzungszähler": "Current verdict and session counters",
  "{} Teil · {} · Hand": "{} part · {} · manual", "{} Teile · {} · Hand": "{} parts · {} · manual",
  "{} Teil · {} · Automatik": "{} part · {} · auto", "{} Teile · {} · Automatik": "{} parts · {} · auto",
  "Kein Teil im Fenster": "No part in the window", "Nicht zugeordnet": "Not assigned", "kein Teil im Fenster": "no part in the window",
  "kein Teil im Fenster · {} %": "no part in the window · {} %",
  "sicher benannt": "confidently named", "nicht sicher zugeordnet": "not confidently assigned", "Negativklasse": "negative class",
  "nie gelernt - unbekanntes Teil": "never learned - unknown part", "unter Schwelle {} %": "below threshold {} %",
  "Gleichstand - Merkmale trennen nicht": "tie - features do not separate", "· Automatik": "· auto",
  "GUT": "GOOD", "UNBEKANNT": "UNKNOWN", "AUSSCHUSS": "REJECT", "Unbekannt": "Unknown", "Geprüft": "Inspected", "GEPRÜFT": "INSPECTED",
  "Gut-Quote": "Good rate", "Teile / min": "Parts / min", "UNBEKANNT-QUOTE": "UNKNOWN RATE", "LAUFZEIT": "RUNTIME",
  "Zähler erfassen abgeschlossene Prüfungen.": "Counters record completed inspections.",
  "Sitzungsdetails": "Session details", "Letzte Prüfungen · {}": "Recent inspections · {}",
  "Noch kein Teil geprüft — Teil auflegen und PRÜFEN drücken (oder Auslöser Auto).": "No part inspected yet — place a part and press INSPECT (or set trigger to Auto).",
  "Noch kein Teil geprüft — Urteile entstehen im Linienbetrieb je abgeräumtem Teil.": "No part inspected yet — verdicts arise in line mode per removed part.",
  "unbekanntes Teil": "unknown part", "Unbekanntes Teil": "Unknown part", "unbekannt": "unknown", "gut": "good", "ausschuss": "reject",
  "Prüfparameter": "Inspection parameters", "Konfidenzschwelle": "Confidence threshold", "Ziel Unbek.-Quote": "Target unknown rate",
  "Darunter gilt ein benanntes Teil als UNBEKANNT (0 = aus)": "Below this a named part counts as UNKNOWN (0 = off)",
  "Ab dieser Unbekannt-Quote wird Nachlernen empfohlen": "Above this unknown rate re-learning is recommended",
  "aus": "off", "Nachlernen empfohlen": "Re-learning recommended",
  "— Unbekannt-Quote {} % liegt über dem Ziel von {} %.": "— unknown rate {} % is above the target of {} %.",
  "Klasse wählen": "Choose class", "Klasse …": "Class …",
  "→ Bild wird Lernfoto. Danach Chip-Lernen ausführen.": "→ image becomes a learning photo. Then run on-chip learning.",
  "CSV-Export": "CSV export", "Protokoll als CSV herunterladen": "Download the log as CSV", "Zähler zurücksetzen": "Reset counters",
  "Sitzungszähler auf null": "Session counters to zero", "Ton an": "Sound on", "Ton aus": "Sound off",
  "Alarmton bei Unbekannt/Ausschuss": "Alarm sound on unknown/reject",
  "Sitzungszähler des Prüfbuchs auf null setzen? Das Bildarchiv": "Reset the session counters of the inspection log? The image archive",
  "und die Alarm-Historie bleiben erhalten.": "and the alarm history are kept.", "Zurücksetzen": "Reset",
  "Prüfung nicht möglich": "Inspection not possible", "nur im Profil stationaer": "only in the stationary profile",
  "Betriebsart Erkennung waehlen": "Select the Inspection mode", "kein Teil im Bild": "no part in the image",
  "kein Bild innerhalb von 3 s": "no image within 3 s",

  /* ---- live result line, objects ---- */
  "{} Objekt im Bild": "{} object in the image", "{} Objekte im Bild": "{} objects in the image", "{} IM BILD ▾": "{} IN IMAGE ▾",
  "Objekte je Bild": "Objects per image", "Teil im Fenster.": "part in the window.", "nichts im Rahmen": "nothing in the frame",
  "nur Hintergrund oder Störteile im Rahmen": "only background or stray parts in the frame",
  "Antwort — ein Teil im Fenster.": "answer — one part in the window.", "beurteilt den ganzen": "judges the whole",
  "Ausschnitt und gibt": "crop and gives", "wartet auf Teil": "waiting for part", "Teil freigestellt": "part isolated",
  "Warum?": "Why?", "Warum erkannt?": "Why recognised?", "Live-Teil ↔ gelerntes Beispiel": "Live part ↔ learned example",
  "Live-Teil": "Live part", "Lernbeispiel": "Learned example", "Aufschlüsselung": "Breakdown",
  "alle Objekte gleichauf — die Merkmale trennen sie nicht": "all objects tie — the features do not separate them",
  "Erkennungsprotokoll": "Recognition log", "LETZTE WECHSEL ▾": "RECENT CHANGES ▾",
  "Noch keine Ergebnisse — sobald die Erkennung wechselt, steht hier das Protokoll.": "No results yet — as soon as the recognition changes, the log appears here.",
  "Noch keine Ergebnisse — sobald die": "No results yet — as soon as the", "Erkennung wechselt, steht hier das Protokoll.": "recognition changes, the log appears here.",
  "Konfidenzverlauf": "Confidence trend",
  "Sobald genug Messungen da sind, steht hier der Verlauf der Treffersicherheit.": "Once enough measurements exist, the trend of the match confidence appears here.",
  "Sobald genug Messungen da sind, steht": "Once enough measurements exist, the", "hier der Verlauf der Treffersicherheit.": "trend of the match confidence appears here.",
  "Was der Chip sieht": "What the chip sees", "Genau dieser Ausschnitt geht an die Karte.": "Exactly this crop goes to the card.",
  "Genau dieser Ausschnitt": "Exactly this crop", "geht an die Karte.": "goes to the card.",
  "Geometrische Umrisse, keine Klassifikation — auf der Karte liegt noch nichts.": "Geometric outlines, no classification — nothing is on the card yet.",
  "Geometrische Umrisse, keine": "Geometric outlines, no", "Klassifikation — auf der Karte liegt noch nichts.": "classification — nothing is on the card yet.",
  "noch nichts auf dem Chip gelernt": "nothing learned on the chip yet", "Treffer auf den Lernbildern": "Hits on the learning images",
  "Verwechslung beim Lernen": "Confusion during learning", "Auf dem Chip": "On the chip", "Chip antwortet nicht:": "Chip does not answer:",
  "Karte antwortet nicht": "Card does not answer", "kein Akida": "no Akida", "keine Karte": "no card",
  "{} Rahmen nach Fusion -> keiner benannt": "{} frames after fusion -> none named",
  "Wasserscheiden-Stuecke / Rahmen aus dem Fit / nachgereicht": "watershed pieces / frames from the fit / added later",
  "Pi, geometrisch": "Pi, geometric", "Teile mit Kasten und Winkel.": "Parts with box and angle.",
  "Teile je Bild, mit Kasten, Winkel und Verdeckungsgrad.": "Parts per image, with box, angle and occlusion.",
  "M{}-Detektor stolpert": "M{} detector stumbles", "M{}-Detektor: nicht geladen: vorsa_m{}.fbz nicht gefunden - im Startverzeichnis des Servers ablegen": "M{} detector: not loaded: vorsa_m{}.fbz not found - place it in the server's start directory",
  "nicht geladen: vorsa_m{}.fbz nicht gefunden - im Startverzeichnis des Servers ablegen — die Erkennung läuft ohne Detektor weiter.": "not loaded: vorsa_m{}.fbz not found - place it in the server's start directory — recognition continues without the detector.",
  "— die Erkennung läuft ohne Detektor weiter.": "— recognition continues without the detector.",
  "— es wird bei jedem Bild neu versucht; Einzelheiten im Serverlog.": "— retried on every image; details in the server log.",
  "Erkennung laeuft geometrisch (OpenCV), VORSA-M{} ist noch nicht trainiert": "Recognition runs geometrically (OpenCV), VORSA-M{} is not trained yet",
  "Erkennung laeuft geometrisch (OpenCV), SE-M{} ist noch nicht trainiert": "Recognition runs geometrically (OpenCV), SE-M{} is not trained yet",
  "Synthetische Bildquelle - keine echte Kamera": "Synthetic image source - no real camera",
  "Chip-Lernen nicht moeglich: MetaTF nicht importierbar - Umgebung aktivieren: source ~/akida-env/bin/activate": "On-chip learning not possible: MetaTF cannot be imported - activate the environment: source ~/akida-env/bin/activate",
  "No module named 'akida'": "No module named 'akida'",

  /* ---- camera, view, zoom ---- */
  "Kamera: Fokus, Belichtung, Zoom": "Camera: focus, exposure, zoom", "Kamera: Fokus, Belichtung, Leerbild": "Camera: focus, exposure, empty image",
  "Kamerabild": "Camera image", "Kamerabild {}° drehen": "Rotate camera image {}°", "Kamera neu öffnen": "Reopen camera",
  "Kamera schließen und neu öffnen? Das Bild setzt kurz aus.": "Close and reopen the camera? The image pauses briefly.",
  "Kamera ausgefallen": "Camera failed", "Kamera weicht ab": "Camera deviates", "Neu öffnen": "Reopen",
  "KAMERA · {}×{} · {} FPS": "CAMERA · {}×{} · {} FPS", "KAMERA · –": "CAMERA · –", "Kamera:": "Camera:", "Kamera: ": "Camera: ",
  "Keine Kamera aktiv —": "No camera active —", "es laufen synthetische Bilder.": "synthetic images are running.",
  "es laufen synthetische Bilder. Regler hätten keine Wirkung.": "synthetic images are running. Controls would have no effect.",
  "Keine Kamera aktiv — es laufen synthetische Bilder. Regler hätten keine Wirkung.": "No camera active — synthetic images are running. Controls would have no effect.",
  "Vollständige Kamerasteuerung": "Full camera control", "Fokus": "Focus", "Licht": "Light", "Schärfe": "Sharpness", "Scharf": "Sharp",
  "Sauber": "Clean", "Festhalten": "Hold", "Werte festhalten": "Hold values", "Auto alle": "Auto all", "Alle Automatiken an": "All automatics on",
  "Alle Automatiken dieser Kamera zurück": "Reset all automatics of this camera", "Automatik": "Automatic",
  "Ein bewegter Regler schaltet die": "A moved slider switches off the", "zugehörige Automatik dieser Kamera ab (Belichtung / Weißabgleich / Fokus).": "corresponding automatic of this camera (exposure / white balance / focus).",
  "„Auto alle\" in der Leiste gibt sie zurück.": "\"Auto all\" in the bar restores it.",
  "Für die Erkennung ist „festhalten\" der wichtigere Zustand:": "For recognition, \"hold\" is the more important state:",
  "ein nachregelnder Weißabgleich lässt dasselbe Objekt von Bild zu Bild anders": "a re-adjusting white balance makes the same object look different from image to image",
  "aussehen, und das Modell kann das nicht von einer echten Änderung": "and the model cannot tell that from a real change",
  "unterscheiden.": "apart.", "Auf Startwerte zurück": "Back to start values", "Aktuelle Einstellung sichern": "Save current setting",
  "Name der Einstellung": "Name of the setting", "Gesichert wird die Kameraeinstellung zusammen mit dem Ausschnitt. Getrennt wären sie wertlos.": "The camera setting is saved together with the crop. Apart they would be worthless.",
  "Gesichert wird die Kameraeinstellung zusammen mit": "The camera setting is saved together with", "dem Ausschnitt. Getrennt wären sie wertlos.": "the crop. Apart they would be worthless.",
  "noch keine gesichert": "none saved yet", "Laden": "Load", "laden": "load", "Leeren": "Clear",
  "Ansicht": "View", "Anzeige": "Display", "Anzeige: Rahmen, Konturen, Beschriftung": "Display: frames, contours, labels",
  "Objektrahmen": "Object frames", "Konturen": "Contours", "Beschriftung": "Labels", "Legende": "Legend", "Vollbild": "Full screen",
  "Heranzoomen": "Zoom in", "Herauszoomen": "Zoom out", "Herauszoomen bis zur Übersicht": "Zoom out to the overview",
  "Zoom zurücksetzen (auch Doppelklick aufs Bild)": "Reset zoom (double-click on the image works too)",
  "Außen abdunkeln": "Darken outside", "Aufnahmerahmen": "Capture frame", "Aufnahmefenster": "Capture window", "Fenster": "Window",
  "Rahmen im Bild anfassen und verschieben; Kamera-Regler über „Kamera\" am Bild.": "Grab and move the frame in the image; camera controls via \"Camera\" on the image.",
  "Rahmen im Bild anfassen und verschieben; Kamera-Regler": "Grab and move the frame in the image; camera controls", "über „Kamera\" am Bild.": "via \"Camera\" on the image.",
  "Fenster hat keine Größe — bitte melden.": "Window has no size — please report.", "Ausschnitt": "Crop", "AUSSCHNITT": "CROP",
  "Ausschnitt {} px": "Crop {} px", "{} % · {} → {} px": "{} % · {} → {} px", "{} → {} px": "{} → {} px", "{} × {} px": "{} × {} px", "{} px": "{} px",
  "Kleiner als die Modellgröße — wird hochskaliert, ohne Detail zu gewinnen.": "Smaller than the model size — upscaled without gaining detail.",
  "Kleiner als die Modellgröße — wird": "Smaller than the model size — will be", "hochskaliert, ohne Detail zu gewinnen.": "upscaled without gaining detail.",
  "Kleiner als die Modellgröße — wird hochskaliert, ohne Detail zu": "Smaller than the model size — upscaled without gaining", "gewinnen.": "detail.",
  "AUFLÖSUNG": "RESOLUTION", "Größe": "Size", "Leerbild": "Empty image", "Leeres Band merken": "Record empty belt", "Leerbild verwerfen": "Discard empty image",
  "Leeres Band merken: danach zählt alles als Teil, was sich vom leeren Band unterscheidet": "Record the empty belt: afterwards everything that differs from the empty belt counts as a part",
  "Leeres Band merken: danach zählt alles als Teil, was sich": "Record the empty belt: afterwards everything counts as a part that", "vom leeren Band unterscheidet": "differs from the empty belt",
  "Jetzt liegt NICHTS auf dem Band in dieser Zone? Etwa zwei Sekunden": "Is there NOTHING on the belt in this zone now? For about two seconds",
  "lang werden {} Bilder aufgenommen: das leere Band samt seinem": "{} images are recorded: the empty belt including its",
  "Flackern (Blendflecken, Lampen). TIPP: Band dabei LAUFEN lassen —": "flicker (glare spots, lamps). TIP: let the belt RUN meanwhile —",
  "dann lernt das Leerbild auch die Struktur des Bands in allen": "then the empty image also learns the belt texture in all",
  "Lagen, und nur echte Teile bleiben übrig. Bei geänderter": "positions, and only real parts remain. If the",
  "Kamera, Arm-Sequenz) und speichere die Einrichtung unter einem Namen —": "camera, arm sequence) and save the setup under a name —",
  ") — Erkennung läuft jetzt über die Differenz zum leeren Band": ") — recognition now runs on the difference to the empty belt",
  "Pi-Kamera {}": "Pi camera {}", "Zone nutzt USB-Kamera": "Zone uses USB camera", "Bildquelle dieser Zone": "Image source of this zone",
  "Kamera wählen … — zweite Perspektive fürs Lernen": "Choose camera … — second perspective for learning",

  /* ---- learning ---- */
  "Lernmodus": "Learning mode", "Objekt": "Object", "Objekte": "Objects", "Objekt A": "Object A", "Object B": "Object B", "Objekt B": "Object B",
  "Neues Objekt": "New object", "Objekt löschen": "Delete object", "Umbenennen": "Rename", "Name": "Name", "Name, z. B. Karabiner M{}": "Name, e.g. carabiner M{}",
  "Name, z. B. Abholung": "Name, e.g. pickup", "Namen rechts eintragen": "Enter the name on the right", "Foto": "Photo", "Fotos": "Photos",
  "Foto aufnehmen": "Take photo", "Kein Foto:": "No photo:", "Kein Foto: ": "No photo: ", "Foto gespeichert (": "Photo saved (",
  "{} Fotos · {} Beispiele": "{} photos · {} examples", "{} Beispiele": "{} examples", "Beispiele": "Examples", "je Beispiel": "per example",
  "Noch {} Fotos von „Objekt A“": "{} more photos of \"Object A\"", "„Objekt A“ hat noch keine Fotos.": "\"Object A\" has no photos yet.",
  "„Objekt B“ hat noch keine Fotos.": "\"Object B\" has no photos yet.", "Aufnahmeserie": "Capture series", "Serie starten": "Start series",
  "Teil langsam drehen, während die Serie läuft.": "Rotate the part slowly while the series runs.", "Objekt jedes Mal etwas anders drehen": "Rotate the object a little differently each time",
  "Objekt formatfüllend in den Rahmen bringen": "Fill the frame with the object", "Erst ein Objekt wählen": "Choose an object first",
  "Erst ein Objekt anlegen (Lernmodus).": "Create an object first (learning mode).", "Erst zwei Objekte mit Fotos anlegen.": "Create two objects with photos first.",
  "Mindestens zwei echte Objekte mit Fotos nötig.": "At least two real objects with photos are needed.",
  "Mindestens zwei echte Objekte mit Fotos": "At least two real objects with photos", "nötig.": "are needed.",
  "Mindestens zwei echte Objekte mit Fotos noetig - mit einem gibt es nichts zu unterscheiden.": "At least two real objects with photos are needed - with one there is nothing to tell apart.",
  "Chip-Lernen": "On-chip learning", "Chip-Lernen · Sekunden": "On-chip learning · seconds", "— Sekunden, erkennt": "— seconds, recognises",
  "Trainieren": "Train", "Training": "Training", "Training starten …": "Start training …", "M{}-Training": "M{} training", "M{}-Training · Stunden": "M{} training · hours",
  "— Stunden, findet": "— hours, finds", "M{}-Training: Minuten bis Stunden, erzeugt den eigentlichen Detektor.": "M{} training: minutes to hours, produces the actual detector.",
  "erzeugt den Detektor:": "produces the detector:", "M{}-Schritte": "M{} steps", "Der Dialog zeigt vorher, was hingeht,": "The dialog shows beforehand what is sent,",
  "und lässt die Wahl zwischen den beiden Wegen:": "and lets you choose between the two paths:",
  "Das bisher Gelernte wird ersetzt.": "What was learned so far is replaced.", "Gelerntes verwerfen": "Discard learned data",
  "Das Gedächtnis auf der Karte wird gelöscht — alle angelernten": "The memory on the card is erased — all learned",
  "Teile müssen danach neu gezeigt werden. Das lässt sich nicht": "parts must be shown again afterwards. This cannot be",
  "beenden und neu starten.": "quit and restart.", "Neuronen je Objekt und Karte": "Neurons per object and card", "Merkmalsdichte": "Feature density",
  "Punkte je Schablone": "Points per template", "mit Varianten": "with variants", "×Varianten": "×variants", "beim Training": "during training",
  "Lernzonen": "Learning zones", "Lernzonen: je Kamera eine Zone — ein Foto nimmt beide Perspektiven auf": "Learning zones: one zone per camera — one photo captures both perspectives",
  "LERNZONE · KAMERA A": "LEARNING ZONE · CAMERA A", "LERNZONE · KAMERA B": "LEARNING ZONE · CAMERA B", "LERNFENSTER · Objekt A": "LEARNING WINDOW · Object A",
  "Erst eine Kamera für diese Lernzone wählen": "Choose a camera for this learning zone first", "Lernzone war ein Teil freistellbar": "learning zone: a part could be isolated",
  "aufziehen — dieser Ausschnitt wird bei jedem Foto gelernt": "drag — this crop is learned with every photo",
  "— jedes Foto nimmt diesen Ausschnitt auf": "— every photo captures this crop", "-Bild, Rechteck mit der Maus aufziehen": " image, drag a rectangle with the mouse",
  "→ echtes Objekt": "→ real object", "→ Negativklasse": "→ negative class", "negativ": "negative", "„nichts / Störteil\" anlegen": "create \"nothing / stray part\"",
  "Keine Negativklasse. Ohne sie meldet der Chip auch bei leerem Band ein Objekt.": "No negative class. Without it the chip reports an object even on an empty belt.",
  "Negativklasse: leeres Band, Unterlage, Störteile — ohne sie muss der Chip immer eines der echten Objekte wählen": "Negative class: empty belt, base, stray parts — without it the chip always has to pick one of the real objects",
  "Eine Negativklasse enthält leeres": "A negative class contains the empty", "Band, Unterlage und Störteile. Ohne sie muss der Chip sich immer für eines": "belt, base and stray parts. Without it the chip always has to decide for one",
  "der echten Objekte entscheiden — auch wenn gar nichts da ist.": "of the real objects — even when nothing is there.",
  "Unklare Fälle": "Unclear cases", "unklare Fälle": "unclear cases", "Unklare Fälle löschen": "Delete unclear cases",
  "Jeder nicht auflösbare Fall wird mit Bild abgelegt —": "Every unresolvable case is stored with its image —", "das Material für die nächste Trainingsrunde.": "the material for the next training round.",
  "Das ist Nachlern-Material — sicher?": "This is re-learning material — sure?", "Korrigieren: richtigen Rahmen um ein Teil ziehen → Lernbeispiel": "Correct: draw the right frame around a part → learning example",
  "Trainingsreferenz": "Training reference", "Seit dem Anlernen verändert. Das Modell hat etwas": "Changed since learning. The model has seen something",
  "anderes gesehen, als die Kamera jetzt liefert.": "different from what the camera delivers now.",
  "gelernt hat — das allein kann die Erkennung unbrauchbar machen.": "has learned — that alone can make recognition useless.",
  "Der Trefferwert ist kein Gütemaß für unbekannte": "The match value is not a quality measure for unknown", "Der letzte Wert ist kein Gütemaß für unbekannte": "The last value is not a quality measure for unknown",
  "Bilder. Er zeigt nur, dass überhaupt etwas gelernt wurde.": "images. It only shows that something was learned at all.",
  "Gesichert — nach einem Neustart wird der Stand": "Saved — after a restart the state", "zurückgespielt.": "is restored.",
  "NICHT gesichert. Nach einem Neustart muss": "NOT saved. After a restart it must", "neu gelernt werden.": "be learned again.",
  "Stand der Dateien auf dem Pi": "State of the files on the Pi", "Geladen:": "Loaded:", "Modell": "Model", "Daten": "Data", "Stand": "State",
  "Beschriftungen mehr, als sie erklären. Wer die Trennung zweier berührender": "labels more than they explain. Whoever wants to judge the separation of two touching",
  "Teile beurteilen will, braucht die Konturen ohne alles andere.": "parts needs the contours without anything else.",
  "Teile beurteilen will": "parts needs",

  /* ---- status / hardware / diagnostics ---- */
  "Hardware": "Hardware", "Diagnose": "Diagnostics", "Wartung": "Maintenance", "Software": "Software", "Systemstatus": "System status", "Systemwerte": "System values",
  "Karte": "Card", "Karte ": "Card ", "{}er Karte": "{} card", "Karten im Verbund": "Cards in the ensemble", "Karten im Detail …": "Cards in detail …",
  "Zustand der Karte": "Card status", "Karte zurücksetzen": "Reset card", "Karte zurücksetzen (PCIe)": "Reset card (PCIe)",
  "Die Karte wird vom PCIe-Bus genommen und neu eingebunden, ihr": "The card is removed from the PCIe bus and re-attached, its",
  "solange steht die Erkennung.": "recognition pauses meanwhile.", "Karte ist leer": "Card is empty", "Karte gemessen": "Card measured",
  "Karte + Pi in Ruhe": "Card + Pi idle", "Pi allein": "Pi alone", "Pi unter Last": "Pi under load", "Leistung": "Power", "Leistung Pi": "Power Pi", "Leistung Karte": "Power card",
  "Pi gegen AKD{} messen": "Measure Pi against AKD{}", "KARTE GEGEN PI": "CARD VS PI", "Messen": "Measure", "MESSREIHE": "MEASUREMENT SERIES", "Messung": "Measurement",
  "Zeit je Bild · gemessen": "Time per image · measured", "{} ms": "{} ms", "ms/Bild": "ms/image", "Bilder/s": "images/s", "BILDRATE": "FRAME RATE", "INFERENZ": "INFERENCE",
  "Reine Rechenzeit auf den AKD{}-Karten je Bild": "Pure compute time on the AKD{} cards per image",
  "Reine Rechenzeit auf den AKD{}-Karten je Bild —": "Pure compute time on the AKD{} cards per image —", "Gesamtlatenz der Pipeline:": "total pipeline latency:",
  "Reine Rechenzeit auf den AKD{}-Karten je Bild — Gesamtlatenz der Pipeline: {} ms": "Pure compute time on the AKD{} cards per image — total pipeline latency: {} ms",
  "Der Ring zeigt, wie viel die Karte vom Pi-Wert": "The ring shows how much of the Pi value the card", "braucht — ein Viertel Ring heißt ein Viertel der Zeit.": "needs — a quarter ring means a quarter of the time.",
  "Leistung vorbelegt aus veröffentlichten Tests: Pi {} {} W unter Last (Tom's Hardware), AKD{} unter {} mW im PCIe-Betrieb (BrainChip). Meldet die Karte einen eigenen Messwert, gilt dieser.": "Power preset from published tests: Pi {} {} W under load (Tom's Hardware), AKD{} under {} mW in PCIe operation (BrainChip). If the card reports its own reading, that applies.",
  "Leistung vorbelegt aus veröffentlichten Tests: Pi {}": "Power preset from published tests: Pi {}", "{} W unter Last (Tom's Hardware), AKD{} unter {} mW im PCIe-Betrieb": "{} W under load (Tom's Hardware), AKD{} under {} mW in PCIe operation",
  "(BrainChip). Meldet die Karte einen eigenen Messwert, gilt dieser.": "(BrainChip). If the card reports its own reading, that applies.",
  "Kernziel prüfen": "Check core goal", "Kernziel jetzt prüfen": "Check core goal now", "KERNZIEL": "CORE GOAL", "DURCHLÄUFE": "PASSES",
  "Es ist nichts durchgefallen.": "Nothing has failed.", "Ein PASS bedeutet nur etwas, wenn auch etwas scheitern kann.": "A PASS only means something if something can also fail.",
  "Leistungsübersicht": "Performance overview", "BENENNUNGSQUOTE": "NAMING RATE", "noch nichts gezählt": "nothing counted yet", "keine Aufrufe bisher": "no calls so far",
  "Zählwerk": "Counter", "gesamt": "total", "Hinweise": "Notes", "Achtung": "Attention", "Fehler": "Error", "Jetzt": "Now", "jetzt": "now",
  "im Einsatz": "in use", "· aktiv": "· active", "Gerät": "Device", "Wert": "Value", "Art": "Type", "Weg": "Path", "Faktor": "Factor", "Anzahl": "Count", "Bilder": "Images",
  "Eingang": "Input", "Abstand": "Distance", "Aufnahme": "Capture", "Arbeiten": "Working", "Mehr": "More", "Über": "About", "Zurück": "Back", "Schließen": "Close",
  "Abbrechen": "Cancel", "Aktualisieren": "Refresh", "Ansehen": "View", "Noch keine": "None yet", "Schritte.": "steps.", "ein": "one", "eine": "one", "mehrere": "several",
  "Schließen — läuft weiter": "Close — keeps running", "Noch keine Prüfdaten verfügbar.": "No inspection data available yet.",
  "Server liefert keine Zonendaten — aktiver": "Server delivers no zone data — active", "sonst server.py und linie.py kopieren und neu starten.": "otherwise copy server.py and linie.py and restart.",
  ", benötigt {}.{}+. Server mit Strg+C": ", requires {}.{}+. Server with Ctrl+C", "nicht möglich": "not possible", "Sie wird automatisch neu verbunden — das Bild": "It is reconnected automatically — the image",
  "Zustand: Hardware": "Status: hardware", "Stand der Dateien": "File state",

  /* ---- alarms ---- */
  "Quittieren": "Acknowledge", "Alle quittieren": "Acknowledge all", "{} unquittiert · {} aktiv": "{} unacknowledged · {} active", "noch keine Ereignisse": "no events yet",
  "Keine Alarme. Läuft die Anlage, erscheinen hier": "No alarms. While the cell runs, this shows", "Störungen, Hinweise und Prüf-Ereignisse mit Zeitstempel — bis sie": "faults, notes and inspection events with time stamp — until they",
  "quittiert sind, zählt die Glocke sie mit.": "are acknowledged, the bell counts them.",
  "UNBEKANNT: Teil nicht zuordenbar": "UNKNOWN: part cannot be assigned", "AUSSCHUSS erkannt": "REJECT detected",
  "UNBEKANNT: Teil in der Anlieferung nicht zuordenbar": "UNKNOWN: part in delivery cannot be assigned", "UNBEKANNT: Teil in der Abholzone nicht zuordenbar": "UNKNOWN: part in pickup zone cannot be assigned",

  /* ---- recipes ---- */
  "Rezept": "Recipe", "Aktuelle Einrichtung speichern": "Save current setup", "Mit aktueller Einrichtung überschreiben": "Overwrite with current setup",
  "Noch kein Rezept. Richte ein Produkt ein (Zonen, Kamera, Arm-Sequenz) und speichere die Einrichtung unter einem Namen — beim nächsten Umrüsten genügt „Laden\".": "No recipe yet. Set up a product (zones, camera, arm sequence) and save the setup under a name — at the next changeover \"Load\" is enough.",
  "Noch kein Rezept. Richte ein Produkt ein (Zonen,": "No recipe yet. Set up a product (zones,", "beim nächsten Umrüsten genügt „Laden\".": "at the next changeover \"Load\" is enough.",
  "Ein Rezept bündelt die Einrichtung für ein Produkt: Kameraeinstellungen, Erkennungsfenster, Zonen + Kameraquellen und die Arm-Sequenz. Das Gelernte bleibt davon unberührt.": "A recipe bundles the setup for a product: camera settings, recognition window, zones + camera sources and the arm sequence. What was learned is not affected.",
  "Ein Rezept bündelt die Einrichtung für ein Produkt: Kameraeinstellungen,": "A recipe bundles the setup for a product: camera settings,",
  "Erkennungsfenster, Zonen + Kameraquellen und die Arm-Sequenz. Das": "recognition window, zones + camera sources and the arm sequence. What was",
  "Gelernte bleibt davon unberührt.": "learned is not affected.", "und die Arm-Sequenz werden auf den gespeicherten Stand gesetzt.": "and the arm sequence are set to the saved state.",

  /* ---- line, belt, arm (profile linie) ---- */
  "Linie": "Line", "Linie aktivieren": "Activate line", "Linie aus": "Line off", "keine Linie": "no line", "Band läuft": "Belt running", "Band steht": "Belt stopped",
  "BAND LÄUFT ▶": "BELT RUNNING ▶", "BAND LÄUFT": "BELT RUNNING", "PRÜFT · BAND HÄLT": "INSPECTING · BELT HOLDS", "FÖRDERBAND (SIM)": "CONVEYOR (SIM)", "ARM (SIM)": "ARM (SIM)",
  "Fluss": "Flow", "Einzel": "Single", "Fluss: Band läuft von sich aus, hält zum Prüfen in der Anlieferung und für den Arm in der Abholung. Einzel: Band startet erst, wenn die Anlieferung ein benanntes Teil zeigt.": "Flow: the belt runs by itself, stops for inspection in delivery and for the arm in pickup. Single: the belt only starts when delivery shows a named part.",
  "ANLIEFERUNG": "DELIVERY", "ABHOLUNG": "PICKUP", "ANLIEFERUNG · FEED {}": "DELIVERY · FEED {}", "ABHOLUNG · FEED {}": "PICKUP · FEED {}",
  "Warte auf Anlieferung": "Waiting for delivery", "Teil in Abholung": "Part in pickup", "Zone leer": "Zone empty", "Teile in den Zonen": "Parts in the zones",
  "nicht benannt — Band stoppt hier": "not named — belt stops here", "Störung — Teil entfernen": "Fault — remove the part",
  "PROTOKOLL · {} ABGERÄUMT · {} GEPRÜFT": "LOG · {} REMOVED · {} INSPECTED", "· {} GEPRÜFT": "· {} INSPECTED", "PROTOKOLL": "LOG",
  "Anlieferungszone zurücksetzen": "Reset delivery zone", "Abholzone zurücksetzen": "Reset pickup zone", "Anlieferungszone neu": "Redefine delivery zone",
  "festlegen (Kamerabild erscheint zum Ziehen)": "(camera image appears for dragging)", "Abholzone neu festlegen (Kamerabild erscheint": "Redefine pickup zone (camera image appears", "zum Ziehen)": "for dragging)",
  "Linien-Zone im Bild aufziehen": "Drag a line zone in the image", "ANLIEFERUNGSZONE aufziehen — dort erkennt die Kamera neue Teile": "Drag the DELIVERY ZONE — the camera detects new parts there",
  "ABHOLZONE aufziehen — dort stoppt das Band und der Arm greift": "Drag the PICKUP ZONE — the belt stops there and the arm picks",
  "+ BLICK {}": "+ VIEW {}", "BLICK {} — Anlieferzone im zweiten Kamerabild aufziehen": "VIEW {} — drag the delivery zone in the second camera image",
  "Blick {}: zweite Kamera auf dieselbe Anlieferzone — zwei Winkel, ein Urteil": "View {}: second camera on the same delivery zone — two angles, one verdict",
  "Zone von Blick {} im zweiten Kamerabild ziehen": "Drag the zone of view {} in the second camera image",
  "Roboterarm": "Robot arm", "Roboterarm (Arduino)": "Robot arm (Arduino)", "Arduino-Arm steuern und anlernen": "Control and teach the Arduino arm", "→ HOLEN": "→ FETCH",
  "▶ START": "▶ START", "■ STOP": "■ STOP", "● LIVE": "● LIVE", "LIVE ▾": "LIVE ▾", "AUS ▾": "OFF ▾", "MOTOREN AN": "MOTORS ON", "MOTOREN AUS": "MOTORS OFF",
  "+ PUMPE AN": "+ PUMP ON", "+ PUMPE AUS": "+ PUMP OFF", "PUMPE AN": "PUMP ON", "PUMPE AUS": "PUMP OFF", "+ PAUSE {} s": "+ PAUSE {} s", "PUNKT MERKEN": "STORE POINT",
  "HOME (ENDSCHALTER)": "HOME (LIMIT SWITCHES)", "ACHSEN (SCHRITTE) — Schrittweite:": "AXES (STEPS) — step size:", "{}°-Schritte": "{}° steps", "frei drehen": "rotate freely", "Längsachse": "long axis",
  "senkrecht spiegeln": "mirror vertically", "waagerecht spiegeln": "mirror horizontally", "händig (Spiegeln sperren)": "handed (lock mirroring)",
  "Noch keine Punkte —": "No points yet —", "Achsen in Stellung fahren und PUNKT MERKEN.": "move the axes into position and STORE POINT.",
  "SEQUENZ „HOLEN\" — spielt bei jedem": "SEQUENCE \"FETCH\" — plays at every", "Linien-Auftrag automatisch": "line job automatically",
  "Der Arm wird stromlos und verliert seine Referenz. Vor": "The arm loses power and its reference. Before", "dem nächsten Lauf ist ein Homing nötig.": "the next run a homing is required.",
  "Band und Arm werden angehalten, ein laufender Zyklus bricht": "Belt and arm are stopped, a running cycle is aborted",
  "Kartenleiste auf-/zuklappen": "Expand/collapse the card bar", "Teil": "Part", "Band": "Belt", "Zone": "Zone",

  /* ---- misc ---- */
  "VORSA": "VORSA", "INSPECT / OPS {}": "INSPECT / OPS {}", "{}. Okt. {}": "{} Oct {}", "Sprache": "Language",
  "Vorgang": "Activity", "Schritt {} von {}": "step {} of {}", "· Schritt {} von {}": "· step {} of {}",
  "Erst ein Objekt anlegen": "Create an object first", "Verwerfen": "Discard", "Speichern": "Save", "Löschen": "Delete", "Übernehmen": "Apply", "OK": "OK", "Ja": "Yes", "Nein": "No",
  "Einstellungen": "Settings", "Kameraeinstellungen": "Camera settings", "Belichtung": "Exposure", "Weißabgleich": "White balance", "Kontrast": "Contrast", "Helligkeit": "Brightness",
  "Sättigung": "Saturation", "Zoom": "Zoom", "Drehen": "Rotate", "Spiegeln": "Mirror", "Lernfoto": "Learning photo", "Negativ": "Negative",
  "Linienbefehle": "Line commands", "Band starten": "Start belt", "Band stoppen": "Stop belt", "Arm": "Arm", "Störung": "Fault", "Hinweis": "Note", "Warnung": "Warning",
  "Keine": "None", "keine": "none", "ja": "yes", "nein": "no", "an": "on", "Kamera {}": "Camera {}", "1. Cam (links)": "1st cam (left)", "2. Cam (rechts)": "2nd cam (right)",
  "{}. CAM (LINKS)": "{}. CAM (LEFT)", "{}. CAM (RECHTS)": "{}. CAM (RIGHT)"
};
/* ---- Nachtrag 1 (aus I18N_FEHLEND) ---- */
Object.assign(window.SPRACHEN.en, {
  "LEER": "EMPTY", "FOKUS": "FOCUS", "LICHT": "LIGHT", "ZOOM": "ZOOM", "OBJEKTE": "OBJECTS", "SEGMENTE": "SEGMENTS", "FOTOS": "PHOTOS", "BEISPIELE": "EXAMPLES",
  "AKD1500-Karten": "AKD1500 cards", "AUSSCHNITT {} PX": "CROP {} PX", "LINIE AKTIVIEREN": "ACTIVATE LINE", "BEREIT": "READY", "KLASSE": "CLASS", "KONFIDENZ": "CONFIDENCE",
  "MASSE": "DIMENSIONS", "WINKEL": "ANGLE", "LAGE": "POSITION", "frei": "free", "QUELLE": "SOURCE", "geometry": "geometry", "betreiben": "operate",
  "Anlieferungszone neu festlegen (Kamerabild erscheint zum Ziehen)": "Redefine the delivery zone (camera image appears for dragging)",
  "Abholzone neu festlegen (Kamerabild erscheint zum Ziehen)": "Redefine the pickup zone (camera image appears for dragging)",
  "MetaTF nicht importierbar - Umgebung aktivieren: source ~/akida-env/bin/activate": "MetaTF cannot be imported - activate the environment: source ~/akida-env/bin/activate",
  "MetaTF nicht importierbar": "MetaTF cannot be imported", "Kein Akida-Gerät gefunden.": "No Akida device found.", "keins": "none", "fehlt": "missing",
  "VORSA-M3 — Visual Overlap-Resilient Sparse Architecture. Ein AKD1500, eine Sequenz, ein Durchgang. Die Erkennung im Livebild läuft derzeit geometrisch über OpenCV; der trainierte Detektor ersetzt sie, sobald das M3-Training durchgelaufen ist.": "VORSA-M3 — Visual Overlap-Resilient Sparse Architecture. One AKD1500, one sequence, one pass. Live recognition currently runs geometrically via OpenCV; the trained detector replaces it once the M3 training has finished.",
  "Sprache: Deutsch / English": "Language: Deutsch / English", "VORSA INSPECT · UI {}": "VORSA INSPECT · UI {}",
  "Formfüllung": "Fill ratio", "unbekannt?": "unknown?", "→ Objekt": "→ object", "▸ auf": "▸ open",
  "Bei sechs Teilen verdecken": "With six parts,", "Chip-Lernen: {} Beispiele × {} ms ≈ {} s.": "On-chip learning: {} examples × {} ms ≈ {} s.",
  "{} Objekte": "{} objects", "{} Objekt": "{} object", "KEINE KAMERA": "NO CAMERA", "LINIE AUS": "LINE OFF", "EINRICHTEN": "SETUP", "EINSTELLUNGEN SICHERN": "SAVE SETTINGS",
  "WAS DER CHIP SIEHT": "WHAT THE CHIP SEES", "VARIANTEN DIESES OBJEKTS": "VARIANTS OF THIS OBJECT", "Auf den Chip trainieren": "Train onto the chip",
  "AKTIV": "ACTIVE", "AUS": "OFF", "aktiv": "active"
});

/* ---- Nachtrag 2 (A2 Mehrbild) ---- */
Object.assign(window.SPRACHEN.en, {
  "Bilder mitteln": "Average frames", "{} Bilder": "{} frames",
  "Stehende Szene über N Bilder mitteln: weniger Rauschen, kein Flackern (1 = aus)": "Average a still scene over N frames: less noise, no flicker (1 = off)",
  "Kein Teil im Bild · {} von {} Bildern gemittelt": "No part in the image · {} of {} frames averaged",
  "Szene geprüft — nächstes Teil auflegen · {} von {} Bildern gemittelt": "Scene inspected — place the next part · {} of {} frames averaged",
  "Szene steht — Automatik prüft · {} von {} Bildern gemittelt": "Scene is still — auto will inspect · {} of {} frames averaged",
  "Szene steht — bereit · {} von {} Bildern gemittelt": "Scene is still — ready · {} of {} frames averaged",
  "Szene bewegt sich · {} von {} Bildern gemittelt": "Scene is moving · {} of {} frames averaged",
  "Prüfung läuft … · {} von {} Bildern gemittelt": "Inspecting … · {} of {} frames averaged"
});

/* ---- Nachtrag 3 (A6 Testsatz) ---- */
Object.assign(window.SPRACHEN.en, {
  "Testsatz · {} Szenen": "Test set · {} scenes", "Szene aufnehmen": "Capture scene", "leer": "empty", "Einzeln": "Single", "Mehrere": "Multiple", "Leer": "Empty", "Gesamt": "Total",
  "Szene mit Soll-Wert ablegen; der Testsatz misst später Trefferquote, Unbekannt- und Falsch-sicher-Rate. Er wird nicht zum Lernen benutzt.": "Store the scene with its expected value; the test set later measures hit rate, unknown rate and false-confident rate. It is never used for learning.",
  "Klick: einmal dazu · Rechtsklick / Umschalt-Klick: eins weniger": "Click: add one · Shift-click: remove one", "Nichts liegt im Bild": "Nothing is in the image",
  "Aktuelles Bild mit diesem Soll in den Testsatz": "Add the current image with this expected value to the test set", "Erst Objekte anlegen.": "Create objects first.",
  "Szene entfernen": "Remove scene", "Aufnahme nicht möglich": "Capture not possible", "kein Testsatz-Ordner": "no test set folder"
});

/* ---- Nachtrag 4 (A9 Look) ---- */
Object.assign(window.SPRACHEN.en, {
  "Darstellung wechseln: SpikingEdge · Hell · Magna": "Switch look: SpikingEdge · Light · Magna", "SpikingEdge": "SpikingEdge", "Magna": "Magna"
});

/* ---- Nachtrag 5 (1.9.47 Fenster am Bild) ---- */
Object.assign(window.SPRACHEN.en, {
  "Fenster {} %": "Window {} %", "Fenster kleiner": "Smaller window", "Fenster größer": "Larger window",
  "Größe des Aufnahmefensters — auch: Rahmenecke ziehen oder Mausrad über dem Rahmen": "Size of the capture window — also: drag a frame corner or use the mouse wheel over the frame"
});

/* ---- Nachtrag 6 (1.9.48 Live-Urteil) ---- */
Object.assign(window.SPRACHEN.en, { "1 Teil": "1 part", "{} Teile": "{} parts",
  "Übereinstimmung mit dem gelernten Muster": "Match with the learned pattern", "Übereinstimmung mit dem gelernten Muster · Schwelle {} %": "Match with the learned pattern · threshold {} %" });

/* ---- Nachtrag 7 (1.9.50 Einrichten, Kontextmenue) ---- */
Object.assign(window.SPRACHEN.en, {
  "Bild scharf": "Image sharp", "Schärfe {}": "Sharpness {}", "Schärfe –": "Sharpness –", "Fenster groß genug": "Window large enough",
  "Leerbild gemerkt": "Empty image recorded", "vom {}": "from {}", "noch nicht": "not yet", "Kamera festgehalten": "Camera held",
  "keine Automatik regelt nach": "no automatic re-adjusts", "Automatik aktiv": "automatic active",
  "Reihenfolge: Teil in den Rahmen, scharf stellen, Automatik festhalten, Leerbild ohne Teil merken, Einstellung sichern.": "Order: part into the frame, focus, hold the automatics, record the empty image without a part, save the setting.",
  "Scharf stellen": "Focus", "Einmal scharf stellen und festhalten": "Focus once and hold", "Licht −": "Light −", "Licht +": "Light +",
  "Belichtung, Weißabgleich und Fokus einfrieren": "Freeze exposure, white balance and focus",
  "Ein bewegter Regler schaltet die zugehörige Automatik ab. „Festhalten“ friert alle ein — das ist für die Erkennung der wichtigere Zustand.": "A moved slider switches off its automatic. \"Hold\" freezes all of them — the more important state for recognition.",
  "nicht gemerkt": "not recorded", "Neu merken": "Record again", "Verwerfen": "Discard",
  "Referenz des leeren Tischs: 16 Bilder über ~2 s, danach zählt als Teil, was sich davon unterscheidet. Bei neuer Beleuchtung oder Kameraeinstellung neu merken.": "Reference of the empty table: 16 frames over ~2 s; afterwards anything that differs counts as a part. Record again after changing light or camera settings.",
  "Belichtungszeit": "Exposure time", "Verstärkung": "Gain", "Fokus (Linse)": "Focus (lens)", "Aktionen": "Actions", "Zoom zurücksetzen": "Reset zoom",
  "Kamera-Leiste": "Camera bar", "Fenster −": "Window −", "Fenster +": "Window +", "Leerbild neu": "Empty image again", "Leerbild merken": "Record empty image"
});

/* ---- Nachtrag 8 (1.9.52 Kamera-Dock) ---- */
Object.assign(window.SPRACHEN.en, {
  "Kameraeinstellungen": "Camera settings", "Kameraeinstellungen schließen": "Close camera settings", "Schließen": "Close", "synthetisch": "synthetic",
  "Bild": "Image", "Farbe": "Colour", "Fenster": "Window", "Hintergrund & Sichern": "Background & save", "Mitteln": "Average", "Größe": "Size",
  "Keine Kamera aktiv — synthetische Bilder, Regler ohne Wirkung.": "No camera active — synthetic images, sliders have no effect.",
  "Auf Startwerte": "Start values", "Rahmen im Bild: Ecke ziehen oder Mausrad.": "Frame in the image: drag a corner or use the mouse wheel.",
  "Leerbild:": "Empty image:", "Sichern": "Save", "Einstellung laden": "Load setting", "Kamera + Fenster zusammen sichern — nach dem Einrichten.": "Save camera + window together — after setup.",
  "{} → {} px · zu klein, wird hochskaliert": "{} → {} px · too small, will be upscaled", "Schärfe": "Sharpness", "— fokussieren": "— focus",
  "Urteil vom Gesamtbild — die Geometrie fand keinen Umriss, darum auch keine Objektrahmen.": "Verdict from the whole image — the geometry found no outline, hence no object frames either."
});

/* ---- Nachtrag 9 (1.9.53 SE Inspect) ---- */
Object.assign(window.SPRACHEN.en, {
  "SE INSPECT": "SE INSPECT", "SpikingEdge · UI {}": "SpikingEdge · UI {}", "SE Inspect · UI {} · früher VORSA INSPECT": "SE Inspect · UI {} · formerly VORSA INSPECT",
  "SE-M3 (VORSA-M3) — Visual Overlap-Resilient Sparse Architecture. Ein AKD1500, eine Sequenz, ein Durchgang. Die Erkennung im Livebild läuft derzeit geometrisch über OpenCV; der trainierte Detektor ersetzt sie, sobald das M3-Training durchgelaufen ist.": "SE-M3 (VORSA-M3) — Visual Overlap-Resilient Sparse Architecture. One AKD1500, one sequence, one pass. Live recognition currently runs geometrically via OpenCV; the trained detector replaces it once the M3 training has finished."
});

/* ---- Nachtrag 10 (1.9.54) ---- */
Object.assign(window.SPRACHEN.en, {
  "Kamera-Einstellungen": "Camera settings",
  "Einkamera-Betrieb: Zonen kommen aus der Hauptkamera (Zweitkamera: VORSA_ZWEITKAMERA=1)": "Single-camera mode: zones come from the main camera (second camera: VORSA_ZWEITKAMERA=1)",
  "Leerbild ✓ {}": "Empty image ✓ {}", "Leerbild vom {} aktiv — Klick: neu merken": "Empty image from {} active — click to record again",
  "Leerbild verworfen": "Empty image discarded", "Leerbild gemerkt ({}, {} Bilder, Flackern bis {}) — Erkennung läuft jetzt über die Differenz zum leeren Band": "Empty image recorded ({}, {} images, flicker up to {}) — recognition now uses the difference to the empty belt",
  "Leerbild: nicht möglich": "Empty image: not possible", "Leeres Band merken: danach zählt alles als Teil, was sich vom leeren Band unterscheidet": "Record the empty belt: afterwards anything that differs from the empty belt counts as a part", "Kamera: Bild, Farbe, Fenster, Leerbild": "Camera: image, colour, window, empty image"
});

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

/* ---- Nachtrag 12 (1.9.57 Einstellungen, Prüfprogramme) ---- */
Object.assign(window.SPRACHEN.en, {
  "Einstellungen": "Settings", "Allgemein": "General", "Erkennung": "Recognition", "Prüfprogramme": "Jobs", "Programm": "Job",
  "Einstellungen: Allgemein, Kamera, Erkennung, Prüfprogramme": "Settings: general, camera, recognition, jobs",
  "Prüfprogramme: Einrichtung je Produkt, Umrüsten per Auswahl": "Jobs: setup per product, changeover by selection",
  "Prüfprogramme öffnen": "Open jobs", "Sprache": "Language", "Oberfläche und Meldungen": "Interface and messages",
  "Darstellung": "Appearance", "Farbschema der Oberfläche": "Colour scheme", "Hell": "Light",
  "Ton bei Unbekannt / Ausschuss": "Sound on unknown / reject", "Kurzer Hinweiston nach der Prüfung": "Short tone after inspection",
  "An": "On", "Aus": "Off", "Prüf-Auslöser": "Inspection trigger",
  "Hand: Knopf oder Leertaste · Auto: jede neue, still liegende Szene": "Manual: button or space bar · Auto: every new, settled scene",
  "Die geführte Einrichtung erneut öffnen": "Open the guided setup again", "Öffnen": "Open",
  "Schnell nachstellen geht direkt am Bild: Knopf „Kamera“ über dem Kamerabild.": "For quick adjustments use the “Camera” button above the image.",
  "Dieselben Werte wie unter Prüfung › Prüfdetails › Prüfparameter.": "Same values as Inspection › Inspection details › Parameters.",
  "Konfidenzschwelle": "Confidence threshold", "Ziel Unbek.-Quote": "Target unknown rate", "Bilder mitteln": "Average frames",
  "— wie sicher sich die Anlage sein muss, bevor sie einen Namen nennt. Höher = öfter „unbekannt“, dafür seltener falsch.": "— how sure the cell must be before it names a part. Higher = more often “unknown”, but less often wrong.",
  "Ziel Unbekannt-Quote": "Target unknown rate",
  "— liegt der Anteil unbekannter Teile darüber, schlägt die Anlage Nachlernen vor.": "— if the share of unknown parts exceeds it, the cell suggests re-teaching.",
  "Ältere Kamera-Einstellungen": "Older camera settings",
  "Aus früheren Versionen (nur Kamera + Fenster). Neu sichern geht als Prüfprogramm.": "From earlier versions (camera + window only). Save new ones as a job.",
  "ALS PRÜFPROGRAMM SICHERN": "SAVE AS JOB", "Name, z. B. Gehäuse A": "Name, e.g. Housing A", "Sichern": "Save",
  "Alle Prüfprogramme …": "All jobs …", "Prüfprogramme …": "Jobs …", "Prüfprogramm, z. B. Gehäuse A": "Job, e.g. Housing A",
  "Kamera + Fenster als Prüfprogramm sichern": "Save camera + window as a job",
  "Prüfprogramm aktualisieren": "Update job",
  "Ein Prüfprogramm bündelt die Einrichtung für ein Produkt: Kameraeinstellungen, Aufnahmefenster, Zonen und die Arm-Sequenz. Umrüsten = Programm laden. Das Gelernte bleibt davon unberührt.": "A job bundles the setup for one product: camera settings, capture window, zones and the arm sequence. Changeover = load the job. What was learned is not affected.",
  "Noch kein Prüfprogramm. Richte ein Produkt ein (Kamera, Fenster, Zonen, Arm-Sequenz) und speichere die Einrichtung unter einem Namen — beim nächsten Umrüsten genügt „Laden\".": "No job yet. Set up a product (camera, window, zones, arm sequence) and save the setup under a name — next changeover, just “Load”."
});

/* ---- Nachtrag 13 (1.9.58 Anlernen & Pruefen) ---- */
Object.assign(window.SPRACHEN.en, {
  "OBJEKTE": "OBJECTS", "{} + Hintergrund": "{} + background", "Hintergrund": "Background", "Hintergrund · {} Fotos": "Background · {} photos",
  "{} Fotos · bereit": "{} photos · ready", "noch {} Fotos": "{} more photos", "noch keine Fotos": "no photos yet", "Objekt wählen": "Select object",
  "Hintergrund: leere Fläche, Unterlage, Störteile — damit die Anlage auch „nichts“ sagen kann": "Background: empty surface, base, foreign parts — so the cell can also say “nothing”",
  "Neues Objekt, z. B. Schraube M6": "New object, e.g. screw M6", "+ Anlegen": "+ Add", "Objekt anlegen": "Add object",
  "Noch kein Hintergrund. Ohne ihn meldet die Anlage auch bei leerer Fläche ein Objekt.": "No background yet. Without it the cell reports an object even on an empty surface.",
  "Hintergrund anlegen": "Add background", "FOTOS · {}": "PHOTOS · {}",
  "Teil in den Rahmen legen, dann Leertaste oder oben „Foto aufnehmen“. Lage zwischen den Fotos ändern.": "Place the part in the frame, then press space or “Take photo” at the top. Change its position between photos.",
  "{} Lernbeispiele mit Varianten": "{} learning examples with variants",
  "Foto löschen (rückgängig machbar)": "Delete photo (can be undone)", "Foto gelöscht": "Photo deleted", "Rückgängig": "Undo",
  "Live-Vorschau": "Live preview", "Was die Kamera gerade sieht — gezählt wird erst beim Prüfen": "What the camera sees right now — counted only when inspecting",
  "Gebuchte Prüfungen": "Logged inspections", "ⓘ Kein Umriss gefunden · Urteil aus dem ganzen Fenster": "ⓘ No outline found · verdict from the whole window",
  "Die Geometrie fand keinen Umriss — das Urteil stammt vom ganzen Fenster, darum keine Objektrahmen.": "Geometry found no outline — the verdict comes from the whole window, hence no object frames.",
  "Objekt löschen": "Delete object", "Löschen": "Delete",
  "„{}“ mit {} Fotos endgültig löschen? Das lässt sich nicht rückgängig machen.": "Permanently delete “{}” with {} photos? This cannot be undone.",
  "Tastenkürzel": "Keyboard shortcuts", "Tastenkürzel  ?": "Shortcuts  ?", "Leertaste": "Space",
  "Prüfen (Schritt 3) · Foto aufnehmen (Schritt 2)": "Inspect (step 3) · take photo (step 2)", "Objekt wählen (Schritt 2)": "Select object (step 2)",
  "Mausrad": "Mouse wheel", "über dem Rahmen: Aufnahmefenster größer/kleiner": "over the frame: capture window larger/smaller",
  "Rechtsklick": "Right-click", "im Bild: Anzeige und Aktionen": "in the image: display and actions", "Fenster schließen": "Close window", "Esc": "Esc", "diese Hilfe": "this help",
  "Oben rechts „Lernen …“ öffnet den Dialog. Er zeigt vorher, was hingeht, und lässt die Wahl zwischen den beiden Wegen:": "“Learn …” at the top right opens the dialog. It shows beforehand what goes in and lets you choose between the two paths:"
});

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

/* ---- Nachtrag 15 (1.9.60 Rollen) ---- */
Object.assign(window.SPRACHEN.en, {
  "Benutzer": "Users", "Anmelden": "Sign in", "PIN eingeben": "Enter PIN", "PIN für Admin eingeben": "Enter admin PIN", "PIN": "PIN",
  "PIN falsch": "Wrong PIN", "Anmeldung als Einrichter nötig": "Sign in as setter needed", "Anmeldung als Admin nötig": "Sign in as admin needed",
  "Einrichter: einrichten und anlernen · Admin: zusätzlich Benutzer und Ein-/Ausgänge": "Setter: setup and teaching · Admin: also users and I/O",
  "Rollen sind aktiv. Ohne Anmeldung ist die Anlage eine Bedienstation: prüfen, quittieren, Prüfprogramm laden.": "Roles are active. Without sign-in the cell is an operator station: inspect, acknowledge, load jobs.",
  "Rollen sind aus — die Oberfläche ist für alle offen. Mit einem Admin-PIN wird sie ohne Anmeldung zur Bedienstation.": "Roles are off — the interface is open to everyone. With an admin PIN it becomes an operator station without sign-in.",
  "Admin": "Admin", "Einrichter": "Setter", "Bediener": "Operator", "alles, auch Benutzer und Ein-/Ausgänge": "everything, including users and I/O",
  "einrichten, anlernen, Einstellungen (leer lassen = keiner)": "setup, teaching, settings (leave empty = none)",
  "{} · PIN gesetzt": "{} · PIN set", "{} · kein PIN": "{} · no PIN", "PIN gesetzt": "PIN set", "kein PIN": "no PIN", "neuer PIN": "new PIN", "Ändern": "Change", "Setzen": "Set",
  "Automatisch abmelden": "Automatic sign-out", "nach Minuten ohne Aktion": "after minutes without activity",
  "Rollen ausschalten": "Turn roles off", "löscht alle PINs": "deletes all PINs", "Ausschalten": "Turn off",
  "Alle PINs löschen? Danach ist die Oberfläche wieder für alle offen.": "Delete all PINs? Afterwards the interface is open to everyone again.",
  "Änderungsprotokoll": "Change log", "noch keine Einträge": "no entries yet",
  "PIN: 4 bis 8 Ziffern": "PIN: 4 to 8 digits", "Admin- und Einrichter-PIN müssen verschieden sein": "Admin and setter PIN must differ"
});

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

/* ---- Nachtrag 17 (1.9.62 Training) ---- */
Object.assign(window.SPRACHEN.en, {
  "Training …": "Train …", "Neu trainieren …": "Retrain …", "Training": "Training",
  "Zwei oder mehr Objekte haben genug Fotos. Rechts oben „Training …“ drücken.": "Two or more objects have enough photos. Press “Train …” at the top right.",
  "Oben rechts „Training …“ öffnet den Dialog. Er zeigt vorher, was hingeht, und lässt die Wahl zwischen den beiden Wegen:": "“Train …” at the top right opens the dialog. It shows beforehand what goes in and lets you choose between the two paths:"
});

/* ---- Nachtrag 18 (1.9.63 Sicherung) ---- */
Object.assign(window.SPRACHEN.en, {
  "Komplettsicherung": "Full backup", "Sicherung herunterladen": "Download backup", "Sicherung einspielen …": "Restore backup …",
  "Eine Datei mit allem, was diese Anlage kann: Objekte und Fotos, Gelerntes, Prüfprogramme, Leerbilder, Einstellungen, Ein-/Ausgänge, Benutzer, Testsatz und Protokolle. Zum Aufbewahren oder um einen zweiten Pi gleich einzurichten.": "One file with everything this cell knows: objects and photos, what was learned, jobs, empty images, settings, I/O, users, test set and logs. To keep, or to set up a second Pi the same way.",
  "Sicherung wird erstellt …": "Creating backup …", "Sicherung wird geprüft …": "Checking backup …", "Sicherung einspielen": "Restore backup", "Einspielen": "Restore",
  "Eingespielt — SE Inspect startet neu, die Seite lädt gleich neu …": "Restored — SE Inspect is restarting, the page will reload …",
  "Kein Neustart erkannt — läuft SE Inspect ohne Dienst? Dann von Hand neu starten.": "No restart detected — is SE Inspect running without the service? Then restart it by hand."
});

/* ---- Nachtrag 19 (1.9.65 Version 1.1: Vorschlaege, Trend, Schwelle aus dem Testsatz) ---- */
Object.assign(window.SPRACHEN.en, {
  "Vorschläge aus dem Betrieb": "Suggestions from operation", "Vorschläge ansehen": "View suggestions",
  "Teile, die beim Prüfen": "Parts that were", "unbekannt": "unknown",
  "waren, nach Form und Farbe gruppiert. Du entscheidest je Gruppe – danach „Training …“.": "during inspection, grouped by shape and colour. You decide per group – then “Train …”.",
  "feiner": "finer", "gröber": "coarser", "Gruppierung feiner oder gröber": "Grouping finer or coarser",
  "{} Fotos →": "{} photos →", "Erst nach dem Training erkennt die Anlage das Objekt.": "The cell recognises the object only after training.",
  "{}× unbekannt": "{}× unknown", "· ähnelt": "· resembles",
  "Name, z. B. Mutter M8": "Name, e.g. nut M8", "Als neues Objekt": "As new object", "Zu vorhandenem Objekt": "To existing object", "Zu Objekt …": "To object …",
  "Hintergrund": "Background", "Verwerfen": "Discard", "Nicht mehr vorschlagen": "Don't suggest again",
  "Unterlage, Störteile – damit die Anlage dazu „nichts“ sagt": "Base, stray parts – so the cell says “nothing” for them",
  "{} unbekannt": "{} unknown",
  "{} Gruppe ähnlicher Teile, die beim Prüfen unbekannt waren.": "{} group of similar parts that were unknown during inspection.",
  "{} Gruppen ähnlicher Teile, die beim Prüfen unbekannt waren.": "{} groups of similar parts that were unknown during inspection.",
  "Unbekannte Teile liegen vor, aber noch keine Gruppe ähnlicher Teile.": "There are unknown parts, but no group of similar parts yet.",
  "Bilder werden verglichen …": "Comparing images …",
  "{} unbekannte Bilder, aber keine Gruppe mit mindestens zwei ähnlichen Teilen.": "{} unknown images, but no group with at least two similar parts.",
  "Regler Richtung „gröber“ schieben – oder weiter prüfen, bis sich Teile wiederholen.": "Move the slider towards “coarser” – or keep inspecting until parts repeat.",
  "Noch keine unbekannten Teile aus dem Betrieb.": "No unknown parts from operation yet.",
  "Was beim Prüfen unbekannt ist, landet hier – gruppiert, zum Übernehmen.": "Whatever is unknown during inspection ends up here – grouped, ready to adopt.",
  "{} Bilder verworfen.": "{} images discarded.", "Nicht möglich": "Not possible",
  "Konfidenzschwelle {} % übernommen": "Confidence threshold {} % applied",
  "Trend": "Trend", "Trend wird geladen …": "Loading trend …", "Sicherheit sinkt": "Confidence dropping",
  "— {} % nach dem letzten Training, jetzt {} % (je {} Teile). Meist Licht, Kamera oder neue Teilevarianten – erst dort nachsehen, dann ggf. nachtrainieren.": "— {} % after the last training, now {} % ({} parts each). Usually light, camera or new part variants – check there first, then retrain if needed.",
  "Sicherheit stabil · {} % → {} %": "Confidence stable · {} % → {} %",
  "Drift-Prüfung ab {} benannten Teilen nach dem Training · bisher {}": "Drift check from {} named parts after training · so far {}",
  "Heute": "Today", "{} Teile im Journal": "{} parts in the log", "Teile": "Parts", "Gut": "Good", "Unbekannt": "Unknown", "Ausschuss": "Reject",
  "Letzte 24 Stunden": "Last 24 hours", "max. {} / h": "max. {} / h", "jetzt": "now", "gut": "good",
  "Letzte 14 Tage": "Last 14 days", "Tag": "Day", "Unbek.": "Unkn.", "Aussch.": "Rej.", "Sicherheit": "Confidence",
  "{}:00 · {} Teile": "{}:00 · {} parts", "{}:00 · {} Teile · {} % gut · {} % unbekannt": "{}:00 · {} parts · {} % good · {} % unknown",
  "— {} % → {} % seit dem letzten Training.": "— {} % → {} % since the last training.", "Trend ansehen": "View trend",
  "Schwelle aus dem Testsatz": "Threshold from the test set",
  "Spielt jede Testsatz-Szene durch das Gelernte und misst für jede Schwelle von 30 bis 95 %, wie oft richtig, unbekannt oder falsch-sicher benannt wird. Gut sind etwa 50 Szenen, darunter Fremdteile („unbekannt“). Prüfen pausiert so lange.": "Runs every test-set scene through what was learned and measures, for each threshold from 30 to 95 %, how often parts are named correctly, as unknown or falsely confident. About 50 scenes work well, including foreign parts (“unknown”). Inspection pauses meanwhile.",
  "Szene {} von {} …": "Scene {} of {} …", "Vorschlag:": "Suggestion:",
  "— die kleinste Schwelle, bei der höchstens {} % der Teile falsch-sicher benannt werden.": "— the lowest threshold at which at most {} % of parts are named with false confidence.",
  "Keine Schwelle erreicht das Ziel – erst mehr und bessere Lernfotos, dann neu messen.": "No threshold reaches the target – first more and better training photos, then measure again.",
  "· {} Szenen · {}": "· {} scenes · {}", "· {} Szenen ·": "· {} scenes ·",
  "Schwelle": "Threshold", "Treffer": "Hits", "Fremdteil erkannt": "Foreign part detected", "Bekanntes unbekannt": "Known as unknown", "Falsch-sicher": "False-confident",
  "{} % übernehmen": "Apply {} %", "Neu messen": "Measure again", "Testlauf starten": "Start test run", "{} Szenen im Testsatz": "{} scenes in the test set",
  "Testsatz leer – Szenen unter Prüfung › Testsatz aufnehmen": "Test set empty – capture scenes under Inspection › Test set",
  "Nur {} Szenen – der Vorschlag ist grob. Ab etwa 50 Szenen (mit Fremdteilen) wird er belastbar.": "Only {} scenes – the suggestion is rough. From about 50 scenes (with foreign parts) it becomes reliable.",
  "Keine Fremdteil-Szenen im Testsatz – ob die Anlage Unbekanntes erkennt, ist so nicht geprüft.": "No foreign-part scenes in the test set – whether the cell detects unknown parts is not checked this way.",
  "Jetzt „Training …“ – erst danach erkennt die Anlage das Objekt.": "Now “Train …” – only then does the cell recognise the object.",
  "Name fehlt": "Name missing", "keine Bilder": "no images", "Objekt unbekannt": "Object unknown", "läuft schon": "already running",
  "Testsatz leer – erst Szenen aufnehmen (Prüfung › Testsatz)": "Test set empty – capture scenes first (Inspection › Test set)",
  "Linie läuft – erst stoppen": "Line running – stop it first", "nichts gelernt – erst trainieren": "nothing learned – train first",
  "Testlauf nicht möglich": "Test run not possible",
  "Stehende Szene über N Bilder mitteln: weniger Rauschen (1 = aus)": "Average a still scene over N frames: less noise (1 = off)"
});

/* ---- Nachtrag 20 (1.9.66 Drehknopf) ---- */
Object.assign(window.SPRACHEN.en, {
  "Bild 90° drehen": "Rotate image 90°", "Bild 90° drehen (jetzt {}°)": "Rotate image 90° (now {}°)",
  "Drehen nur in Einrichten oder Anlernen – die Lage gilt für Lernen und Prüfen": "Rotate only in Set up or Teach – the orientation applies to teaching and inspection"
});

/* ---- Nachtrag 21 (1.9.67 Fremdteil) ---- */
Object.assign(window.SPRACHEN.en, {
  "Fremdteil": "Foreign part", "Fremdteil ×{}": "Foreign part ×{}",
  "Teil, das die Anlage NICHT benennen soll (Störteil, fremdes Teil) – Soll: unbekannt. Rechtsklick / Umschalt-Klick: eins weniger": "Part the cell must NOT name (stray or foreign part) – expected: unknown. Right-click / Shift-click: one less"
});

/* ---- Nachtrag 22 (1.9.68 Testsatz) ---- */
Object.assign(window.SPRACHEN.en, { "Testsatz öffnen": "Open test set" });

/* ---- Nachtrag 23 (1.9.70 Kalibrierung) ---- */
Object.assign(window.SPRACHEN.en, {
  "Kompromiss:": "Compromise:", "— beste Abwägung zwischen Treffern und Falschbenennungen.": "— best balance between hits and false names.",
  "— die meisten Treffer bei höchstens {} % falsch-sicher.": "— the most hits with at most {} % falsely confident.",
  "Kalibrierung je Objekt": "Calibration per object", "vom letzten Training – Testlauf wiederholen": "from the last training – repeat the test run",
  "typisch {} % → 90 %": "typically {} % → 90 %",
  "Jedes Objekt erreicht richtig erkannt eine andere Sicherheit. Die Anlage rechnet sie so um, dass ein typischer Treffer überall bei 90 % liegt – dann passt eine Schwelle für alle.": "Each object reaches a different confidence when recognised correctly. The cell rescales it so a typical hit sits at 90 % for every object – then one threshold fits all.",
  "Kalibrierung verwerfen": "Discard calibration",
  "Nach dem Testlauf wird die Sicherheit je Objekt kalibriert (ab 3 richtig erkannten Einzelszenen je Objekt).": "After the test run, confidence is calibrated per object (from 3 correctly recognised single scenes per object).",
  "Keine Schwelle erreicht beides – viele Treffer UND kaum Falschbenennungen. Der Vorschlag ist ein Kompromiss ({} % Treffer, {} % falsch-sicher). Besser wird es nur durch bessere Trennung: Leerbild neu, mehr Lernfotos in verschiedenen Lagen, Störteile als Hintergrund lernen.": "No threshold achieves both – many hits AND hardly any false names. The suggestion is a compromise ({} % hits, {} % falsely confident). Only better separation helps: new empty image, more training photos in different positions, teach stray parts as background.",
  "Das Leerbild passt nicht mehr – das Bild wurde seit der Aufnahme gedreht. Es wird nicht benutzt. Teil wegnehmen und neu merken.": "The empty image no longer fits – the image was rotated since it was captured. It is not used. Remove the part and capture it again.",
  "Leerbild veraltet": "Empty image outdated",
  "— seit der Aufnahme wurde das Bild gedreht. Ohne passendes Leerbild meldet die Anlage leicht Teile, wo keine sind.": "— the image was rotated since it was captured. Without a matching empty image the cell easily reports parts where there are none.",
  "Zum Einrichten": "Go to Set up"
});

/* ---- Nachtrag 24 (Pruefspalte, Reste) ---- */
Object.assign(window.SPRACHEN.en, {
  "Soll: leer": "Expected: empty", "Soll: Fremdteil": "Expected: foreign part",
  "Klasse wählen → Bild wird Lernfoto. Danach Chip-Lernen ausführen.": "Choose a class → the image becomes a training photo. Then run chip learning."
});

/* ---- Nachtrag 25 (1.9.71 M3-Fortschritt) ---- */
Object.assign(window.SPRACHEN.en, {
  "Fotos freistellen": "Isolating photos", "TensorFlow laden": "Loading TensorFlow", "Modell bauen": "Building model",
  "Quantisieren": "Quantising", "Nach Akida umwandeln": "Converting to Akida", "Auf den AKD1500 legen": "Mapping onto the AKD1500",
  "Training (getrennte Umgebung)": "Training (separate environment)"
});

/* ---- Nachtrag 26 (1.9.72 Testlauf) ---- */
Object.assign(window.SPRACHEN.en, {
  "Testlauf läuft – erst abwarten (Einstellungen › Erkennung)": "Test run in progress – wait for it to finish (Settings › Recognition)",
  "RuntimeError: Betriebsart wurde während des Testlaufs gewechselt – Lauf abgebrochen, bitte wiederholen": "RuntimeError: Mode was changed during the test run – run aborted, please repeat"
});

if (window.spracheNachladen) window.spracheNachladen();
