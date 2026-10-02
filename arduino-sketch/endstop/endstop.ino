// ======================================================
// RAMPS 1.4 Endstop Test – X_MIN, Y_MIN, Z_MIN
// Board: Arduino Mega 2560
// Open Serial Monitor: 115200 baud
// Press each endstop (mechanical switch) and observe output
// ======================================================

// Standard RAMPS 1.4 pin mapping:
#define X_MIN_PIN 3
#define Y_MIN_PIN 14
#define Z_MIN_PIN 18

// true = aktiv LOW (normal bei Schalter S/GND + Pullup)
bool INVERT = true;

void setup() {
  Serial.begin(115200);
  Serial.println(F("=== RAMPS 1.4 Endstop Test ==="));
  Serial.println(F("Schließe Endstops an S & - an, nicht an +"));
  Serial.println(F("Drücke Schalter oder kurz Signal-GND => Anzeige wechselt"));
  Serial.println(F("-------------------------------------------"));

  pinMode(X_MIN_PIN, INPUT_PULLUP);
  pinMode(Y_MIN_PIN, INPUT_PULLUP);
  pinMode(Z_MIN_PIN, INPUT_PULLUP);
}

void loop() {
  int x = digitalRead(X_MIN_PIN);
  int y = digitalRead(Y_MIN_PIN);
  int z = digitalRead(Z_MIN_PIN);

  // Falls invertiert (aktive LOW Schalter)
  if (INVERT) {
    x = !x; y = !y; z = !z;
  }

  Serial.print("X=");
  Serial.print(x);
  Serial.print("  Y=");
  Serial.print(y);
  Serial.print("  Z=");
  Serial.println(z);

  delay(500);  // alle 0,5 Sekunden aktualisieren
}
