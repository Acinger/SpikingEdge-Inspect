// ============================================================================
// VORSA-ARM Firmware 1.0  -  RAMPS 1.4 auf Arduino Mega 2560, 115200 Baud
//
// 3-Achs-Stepperarm (X=Basis, Y=Schulter, Z=Ellbogen) + Saugpumpe an D10.
// Ersatz fuer den verlorenen "5th-S-curve"-Sketch: gleiches Protokoll,
// gleiche Pins (von der alten Firmware selbst gemeldet), plus sauber
// einstellbare RICHTUNGS-SCHALTER pro Achse.
//
// ---------------------------------------------------------------------------
// RICHTUNGEN EINSTELLEN (die einzigen Zeilen, die man je anfassen muss):
//   DIR_INV[..]  dreht die Laufrichtung der Achse komplett um
//                (wenn "+" in die falsche Richtung faehrt).
//   HOME_PLUS[..] sagt, ob die Referenzfahrt in "+"-Richtung zum
//                Endschalter faehrt (false = in "-"-Richtung).
//                Basis X steht hier auf false, weil die alte Firmware
//                vom Endschalter WEG drehte (2026-09-05).
// ---------------------------------------------------------------------------
// Befehle (alle enden mit OK/DONE/ERR; Bewegungen melden DONE):
//   help | ping | list | endstat | pos
//   spd <us> | pulse <us> | smooth <pct 0..30>
//   enall <0|1> | en <x|y|z> <0|1>
//   mv <x|y|z> <+|-> <steps>
//   g1 x <abs> y <abs> z <abs>     (beliebige Teilmenge, faehrt gemeinsam)
//   home <x|y|z|all>               (MAX-Endschalter, setzt POS=0)
//   pump <0|1> | pumppwm <0..255> | pumpkick
//   test <x|y|z>
// ============================================================================

#include <Arduino.h>

// ---- RAMPS-Pins (identisch zur alten Firmware) ----
#define X_STEP 54
#define X_DIR  55
#define X_EN   38
#define X_MAX   2
#define Y_STEP 60
#define Y_DIR  61
#define Y_EN   56
#define Y_MAX  15
#define Z_STEP 46
#define Z_DIR  48
#define Z_EN   62
#define Z_MAX  19
#define PUMP_D10 10

// ---- RICHTUNGS-SCHALTER (siehe Kopfkommentar) ----
bool DIR_INV[3]   = { false, true,  false };  // x, y (Y-inv wie gehabt), z
bool HOME_PLUS[3] = { false, true,  true  };  // x: umgedreht (2026-09-05)

// ---- Timing ----
unsigned int STEP_DELAY_US = 1000;   // Grundtakt zwischen Schritten
unsigned int PULSE_US      = 6;      // Laenge des Schrittpulses
unsigned int RAMP_PCT      = 12;     // Anteil der Strecke fuer Anfahrrampe
const unsigned long HOME_TIMEOUT_MS = 20000UL;

struct Achse {
  const char* n;
  uint8_t step, dir, en, endst;
  long pos;
};
Achse AX[3] = {
  {"x", X_STEP, X_DIR, X_EN, X_MAX, 0},
  {"y", Y_STEP, Y_DIR, Y_EN, Y_MAX, 0},
  {"z", Z_STEP, Z_DIR, Z_EN, Z_MAX, 0},
};
int pumpPwm = 0;

int axIndex(const String& s) {
  if (s == "x") return 0;
  if (s == "y") return 1;
  if (s == "z") return 2;
  return -1;
}

// ---- Grundfunktionen ----
inline bool endPressed(uint8_t pin) { return digitalRead(pin) == LOW; }

void setDir(int i, bool plus) {
  bool pegel = plus;
  if (DIR_INV[i]) pegel = !pegel;
  digitalWrite(AX[i].dir, pegel ? HIGH : LOW);
}

void enableAxis(int i, bool on) {           // Enable ist aktiv LOW
  digitalWrite(AX[i].en, on ? LOW : HIGH);
}

void enableAll(bool on) { for (int i = 0; i < 3; i++) enableAxis(i, on); }

inline void stepPulse(int i) {
  digitalWrite(AX[i].step, HIGH);
  delayMicroseconds(PULSE_US);
  digitalWrite(AX[i].step, LOW);
}

// Rampen-Verzoegerung: am Anfang und Ende der Strecke langsamer.
unsigned int rampDelay(long k, long n) {
  long rampe = (n * (long)RAMP_PCT) / 100;
  if (rampe < 1) return STEP_DELAY_US;
  long rest = n - 1 - k;
  long m = (k < rest) ? k : rest;           // Abstand zum naeheren Ende
  if (m >= rampe) return STEP_DELAY_US;
  // linear von 3x Grundtakt auf 1x
  return STEP_DELAY_US + (unsigned int)((STEP_DELAY_US * 2L
                                         * (rampe - m)) / rampe);
}

// Eine Achse relativ bewegen. Stoppt, wenn der Endschalter in
// Fahrtrichtung-zum-Schalter gedrueckt wird. Liefert gefahrene Schritte.
long moveRel(int i, bool plus, long n) {
  enableAxis(i, true);
  setDir(i, plus);
  delayMicroseconds(10);
  bool zumSchalter = (plus == HOME_PLUS[i]);
  long k = 0;
  for (; k < n; k++) {
    if (zumSchalter && endPressed(AX[i].endst)) break;
    stepPulse(i);
    delayMicroseconds(rampDelay(k, n));
    AX[i].pos += plus ? 1 : -1;
  }
  return k;
}

// Mehrere Achsen GEMEINSAM zum Absolutziel (DDA ueber die laengste Achse).
void moveAbs(long zx, long zy, long zz, bool hatX, bool hatY, bool hatZ) {
  long ziel[3] = { zx, zy, zz };
  bool hat[3] = { hatX, hatY, hatZ };
  long delta[3];
  bool plus[3];
  long maxN = 0;
  for (int i = 0; i < 3; i++) {
    delta[i] = hat[i] ? (ziel[i] - AX[i].pos) : 0;
    plus[i] = delta[i] >= 0;
    if (delta[i] < 0) delta[i] = -delta[i];
    if (delta[i] > maxN) maxN = delta[i];
    if (hat[i]) { enableAxis(i, true); setDir(i, plus[i]); }
  }
  if (maxN == 0) return;
  delayMicroseconds(10);
  long akku[3] = { 0, 0, 0 };
  for (long k = 0; k < maxN; k++) {
    for (int i = 0; i < 3; i++) {
      if (delta[i] == 0) continue;
      akku[i] += delta[i];
      if (akku[i] >= maxN) {
        akku[i] -= maxN;
        bool zumSchalter = (plus[i] == HOME_PLUS[i]);
        if (zumSchalter && endPressed(AX[i].endst)) { delta[i] = 0;
                                                      continue; }
        stepPulse(i);
        AX[i].pos += plus[i] ? 1 : -1;
      }
    }
    delayMicroseconds(rampDelay(k, maxN));
  }
}

bool homeAxis(int i) {
  enableAxis(i, true);
  delay(10);
  bool plus = HOME_PLUS[i];
  // Steht der Schalter schon gedrueckt: erst ein Stueck freifahren.
  if (endPressed(AX[i].endst)) {
    setDir(i, !plus);
    delayMicroseconds(10);
    for (int k = 0; k < 400; k++) { stepPulse(i);
                                    delayMicroseconds(STEP_DELAY_US); }
  }
  setDir(i, plus);
  delayMicroseconds(10);
  unsigned long t0 = millis();
  while (!endPressed(AX[i].endst)) {
    stepPulse(i);
    delayMicroseconds(STEP_DELAY_US);
    if (millis() - t0 > HOME_TIMEOUT_MS) {
      Serial.print(F("ERR home Timeout "));
      Serial.println(AX[i].n);
      return false;
    }
  }
  AX[i].pos = 0;
  Serial.print(F("OKH home "));
  Serial.println(AX[i].n);
  return true;
}

// ---- Pumpe ----
void pumpSet(int v) {
  if (v < 0) v = 0;
  if (v > 255) v = 255;
  pumpPwm = v;
  analogWrite(PUMP_D10, v);
}

// ---- Ausgaben ----
void printPos() {
  Serial.print(F("POS x="));
  Serial.print(AX[0].pos);
  Serial.print(F(" y="));
  Serial.print(AX[1].pos);
  Serial.print(F(" z="));
  Serial.print(AX[2].pos);
  Serial.print(F(" pump="));
  Serial.println(pumpPwm > 0 ? 1 : 0);
}

void printList() {
  Serial.println(F("VORSA-ARM 1.0  RAMPS XYZ + D10 Pumpe"));
  for (int i = 0; i < 3; i++) {
    Serial.print(AX[i].n);
    Serial.print(F(": STEP="));
    Serial.print(AX[i].step);
    Serial.print(F(" DIR="));
    Serial.print(AX[i].dir);
    Serial.print(F(" EN="));
    Serial.print(AX[i].en);
    Serial.print(F(" MAX="));
    Serial.print(AX[i].endst);
    Serial.print(F(" POS="));
    Serial.print(AX[i].pos);
    Serial.print(F(" dirinv="));
    Serial.print(DIR_INV[i] ? 1 : 0);
    Serial.print(F(" homeplus="));
    Serial.println(HOME_PLUS[i] ? 1 : 0);
  }
  Serial.print(F("spd(us)="));
  Serial.print(STEP_DELAY_US);
  Serial.print(F(" pulse(us)="));
  Serial.print(PULSE_US);
  Serial.print(F(" ramp="));
  Serial.print(RAMP_PCT);
  Serial.println(F("%"));
}

void printHelp() {
  Serial.println(F("Befehle:"));
  Serial.println(F("  help | ping | list | endstat | pos"));
  Serial.println(F("  spd <us> | pulse <us> | smooth <pct>"));
  Serial.println(F("  enall <0|1> | en <x|y|z> <0|1>"));
  Serial.println(F("  mv <x|y|z> <+|-> <steps>"));
  Serial.println(F("  g1 x <abs> y <abs> z <abs>"));
  Serial.println(F("  home <x|y|z|all>"));
  Serial.println(F("  pump <0|1> | pumppwm <0..255> | pumpkick"));
  Serial.println(F("  test <x|y|z>"));
}

String readLine() {
  static String buf;
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\r') continue;
    if (c == '\n') { String s = buf; buf = ""; return s; }
    buf += c;
  }
  return String();
}

void setup() {
  Serial.begin(115200);
  for (int i = 0; i < 3; i++) {
    pinMode(AX[i].step, OUTPUT);
    digitalWrite(AX[i].step, LOW);
    pinMode(AX[i].dir, OUTPUT);
    pinMode(AX[i].en, OUTPUT);
    digitalWrite(AX[i].en, HIGH);          // aus (aktiv LOW)
    pinMode(AX[i].endst, INPUT_PULLUP);
  }
  pinMode(PUMP_D10, OUTPUT);
  pumpSet(0);                              // Pumpe AUS beim Start
  Serial.println(F("VORSA-ARM 1.0 bereit"));
  printList();
}

void loop() {
  String line = readLine();
  if (line.length() == 0) return;
  line.trim();
  line.toLowerCase();

  if (line == "help") { printHelp(); return; }
  if (line == "ping") { Serial.println(F("PONG")); return; }
  if (line == "list") { printList(); return; }
  if (line == "pos") { printPos(); return; }
  if (line == "endstat") {
    for (int i = 0; i < 3; i++) {
      Serial.print(AX[i].n);
      Serial.print(F("="));
      Serial.print(endPressed(AX[i].endst) ? F("PRESSED") : F("open"));
      Serial.print(F(" "));
    }
    Serial.println(F("OK"));
    return;
  }
  if (line.startsWith("spd ")) {
    long v = line.substring(4).toInt();
    if (v < 200) v = 200;
    if (v > 100000) v = 100000;
    STEP_DELAY_US = (unsigned int)v;
    Serial.print(F("OK spd="));
    Serial.println(STEP_DELAY_US);
    return;
  }
  if (line.startsWith("pulse ")) {
    long v = line.substring(6).toInt();
    if (v < 2) v = 2;
    if (v > 1000) v = 1000;
    PULSE_US = (unsigned int)v;
    Serial.print(F("OK pulse="));
    Serial.println(PULSE_US);
    return;
  }
  if (line.startsWith("smooth ")) {
    long v = line.substring(7).toInt();
    if (v < 0) v = 0;
    if (v > 30) v = 30;
    RAMP_PCT = (unsigned int)v;
    Serial.print(F("OK smooth="));
    Serial.println(RAMP_PCT);
    return;
  }
  if (line.startsWith("enall ")) {
    bool on = line.endsWith("1");
    enableAll(on);
    Serial.print(F("OK enall "));
    Serial.println(on ? F("ON") : F("OFF"));
    return;
  }
  if (line.startsWith("en ")) {
    int s1 = line.indexOf(' '), s2 = line.indexOf(' ', s1 + 1);
    if (s2 < 0) { Serial.println(F("ERR en <x|y|z> <0|1>")); return; }
    int i = axIndex(line.substring(s1 + 1, s2));
    if (i < 0) { Serial.println(F("ERR axis")); return; }
    bool on = line.substring(s2 + 1).toInt() > 0;
    enableAxis(i, on);
    Serial.println(F("OK en"));
    return;
  }
  if (line.startsWith("mv ")) {
    int s1 = line.indexOf(' '), s2 = line.indexOf(' ', s1 + 1),
        s3 = line.indexOf(' ', s2 + 1);
    if (s1 < 0 || s2 < 0 || s3 < 0) {
      Serial.println(F("ERR mv <x|y|z> <+|-> <steps>"));
      return;
    }
    int i = axIndex(line.substring(s1 + 1, s2));
    if (i < 0) { Serial.println(F("ERR axis")); return; }
    bool plus = line.substring(s2 + 1, s3) == "+";
    long n = line.substring(s3 + 1).toInt();
    if (n <= 0) { Serial.println(F("ERR steps")); return; }
    Serial.println(F("BUSY"));
    long k = moveRel(i, plus, n);
    Serial.print(F("DONE mv "));
    Serial.println(k);
    return;
  }
  if (line.startsWith("g1")) {
    long zi[3] = { 0, 0, 0 };
    bool hat[3] = { false, false, false };
    int p = 2;
    while (p < (int)line.length()) {
      while (p < (int)line.length() && line[p] == ' ') p++;
      if (p >= (int)line.length()) break;
      int i = axIndex(line.substring(p, p + 1));
      if (i < 0) { Serial.println(F("ERR g1 achse")); return; }
      p += 1;
      while (p < (int)line.length() && line[p] == ' ') p++;
      int e = line.indexOf(' ', p);
      if (e < 0) e = line.length();
      zi[i] = line.substring(p, e).toInt();
      hat[i] = true;
      p = e;
    }
    if (!hat[0] && !hat[1] && !hat[2]) {
      Serial.println(F("ERR g1 x <abs> y <abs> z <abs>"));
      return;
    }
    Serial.println(F("BUSY"));
    moveAbs(zi[0], zi[1], zi[2], hat[0], hat[1], hat[2]);
    Serial.println(F("DONE g1"));
    return;
  }
  if (line.startsWith("home")) {
    String t = line.length() > 5 ? line.substring(5) : String("all");
    t.trim();
    Serial.println(F("BUSY"));
    bool ok = true;
    if (t == "all") {
      for (int i = 0; i < 3; i++) ok &= homeAxis(i);
    } else {
      int i = axIndex(t);
      if (i < 0) { Serial.println(F("ERR axis")); return; }
      ok = homeAxis(i);
    }
    Serial.println(ok ? F("DONE home") : F("ERR home"));
    return;
  }
  if (line.startsWith("pump ")) {
    pumpSet(line.substring(5).toInt() > 0 ? 255 : 0);
    Serial.print(F("OK pump="));
    Serial.println(pumpPwm > 0 ? 1 : 0);
    return;
  }
  if (line.startsWith("pumppwm ")) {
    pumpSet(line.substring(8).toInt());
    Serial.print(F("OK pumppwm="));
    Serial.println(pumpPwm);
    return;
  }
  if (line == "pumpkick") {
    int alt = pumpPwm;
    pumpSet(255);
    delay(300);
    pumpSet(alt > 0 ? alt : 0);
    Serial.println(F("OK pumpkick"));
    return;
  }
  if (line.startsWith("test ")) {
    int i = axIndex(line.substring(5));
    if (i < 0) { Serial.println(F("ERR axis")); return; }
    Serial.println(F("BUSY"));
    moveRel(i, true, 400);
    delay(150);
    moveRel(i, false, 400);
    Serial.println(F("DONE test"));
    return;
  }
  Serial.println(F("ERR unknown"));
}
