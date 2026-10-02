#include <Servo.h>

// Pins für die 6 Servos (Servo 2 jetzt auf D9 statt D4)
static const uint8_t SERVO_PINS[6] = {2, 3, 9, 5, 6, 7};
Servo servos[6];

// Maximale Winkel (können durch LIMITS von der App geändert werden)
static int MAX_ANGLES[6] = {80, 80, 80, 80, 80, 80};
// Startposition
int currentAngles[6] = {40, 40, 40, 40, 40, 40};

void setup() {
  Serial.begin(115200);
  for (int i = 0; i < 6; i++) {
    servos[i].attach(SERVO_PINS[i]);
    servos[i].write(currentAngles[i]);
  }
  Serial.println("ROBOMAUS Arm bereit");
}

void loop() {
  if (Serial.available()) {
    String line = Serial.readStringUntil('\n');
    line.trim();
    if (line.length() == 0) return;
    parseCommand(line);
  }
}

void parseCommand(String cmd) {
  if (cmd.startsWith("S,")) {
    // Einzelnen Servo ansteuern: S,<index>,<winkel>
    int comma1 = cmd.indexOf(',', 2);
    if (comma1 == -1) return;
    int idx = cmd.substring(2, comma1).toInt();
    int angle = cmd.substring(comma1 + 1).toInt();
    setServo(idx, angle);

  } else if (cmd.startsWith("ALL,")) {
    // Alle Servos auf denselben Winkel
    int angle = cmd.substring(4).toInt();
    for (int i = 0; i < 6; i++) setServo(i, angle);

  } else if (cmd.startsWith("POSE,")) {
    // Komplettpose mit Dauer: POSE,a0,a1,a2,a3,a4,a5,duration
    int vals[6];
    int lastPos = 5; // Startindex nach "POSE,"
    for (int i = 0; i < 6; i++) {
      int next = cmd.indexOf(',', lastPos + 1);
      if (next == -1 && i < 5) return;
      vals[i] = (i < 5) ? cmd.substring(lastPos + 1, next).toInt() : cmd.substring(lastPos + 1).toInt();
      lastPos = next;
    }
    // Letzter Wert = Dauer
    int duration = vals[5];
    vals[5] = cmd.substring(cmd.lastIndexOf(',') + 1).toInt();
    movePose(vals, duration);

  } else if (cmd.startsWith("LIMITS,")) {
    // Neue Maximalwinkel setzen
    int si = 7;
    for (int i = 0; i < 6; i++) {
      int ni = cmd.indexOf(',', si);
      int val;
      if (ni == -1 && i < 5) return;
      val = (i < 5) ? cmd.substring(si, ni).toInt() : cmd.substring(si).toInt();
      MAX_ANGLES[i] = constrain(val, 0, 180);
      si = ni + 1;
    }
    Serial.println("Neue Limits gesetzt");
  }
}

void setServo(int idx, int angle) {
  if (idx < 0 || idx >= 6) return;
  angle = constrain(angle, 0, MAX_ANGLES[idx]);
  servos[idx].write(angle);
  currentAngles[idx] = angle;
}

void movePose(int vals[6], int duration) {
  int start[6];
  for (int i = 0; i < 6; i++) start[i] = currentAngles[i];
  int steps = max(1, duration / 20); // 20ms Schritte
  for (int s = 1; s <= steps; s++) {
    for (int i = 0; i < 6; i++) {
      int target = constrain(vals[i], 0, MAX_ANGLES[i]);
      int val = map(s, 0, steps, start[i], target);
      servos[i].write(val);
      currentAngles[i] = val;
    }
    delay(20);
  }
}
