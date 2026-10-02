// ============================================================================
// RAMPS 1.4.2 – Minimal 3-Axis (X,Y,Z) + Air Pump on D10 (always ON at startup)
// Board: Arduino Mega 2560
// Baudrate: 115200
// No endstops/fan logic; focus on reliable motion and D10 pump control.
// ----------------------------------------------------------------------------
// Serial commands (optional; for later fine control):
//   help | ping | list
//   spd <us>            ; default 1000, min 50
//   pulse <us>          ; default 6, min 2
//   enall <0|1>
//   en <x|y|z> <0|1>
//   enpol <0|1>         ; 0=ENABLE active LOW (default), 1=active HIGH
//   mv <x|y|z> <+|-> <steps>
//   test <x|y|z|all>
//   pump <0|1>          ; D10 OFF/ON (hard switch)
//   pumppwm <0..255>    ; D10 PWM (255=full on)
// ============================================================================

#include <Arduino.h>

// ---- RAMPS 1.4.2 axis pins ----
#define X_STEP_PIN 54
#define X_DIR_PIN  55
#define X_EN_PIN   38

#define Y_STEP_PIN 60
#define Y_DIR_PIN  61
#define Y_EN_PIN   56

#define Z_STEP_PIN 46
#define Z_DIR_PIN  48
#define Z_EN_PIN   62

// ---- Air pump (RAMPS D10 -> Arduino pin 10) ----
#define PUMP_D10   10

// ---- timings (µs) ----
volatile unsigned int STEP_DELAY_US = 1000;
volatile unsigned int PULSE_US      = 6;

// ---- enable polarity: 0 = LOW active (A4988/DRV8825 default), 1 = HIGH active ----
volatile uint8_t ENABLE_ACTIVE_HIGH = 0;

struct Axis { const char* n; uint8_t step, dir, en; };
Axis AX_X = {"x", X_STEP_PIN, X_DIR_PIN, X_EN_PIN};
Axis AX_Y = {"y", Y_STEP_PIN, Y_DIR_PIN, Y_EN_PIN};
Axis AX_Z = {"z", Z_STEP_PIN, Z_DIR_PIN, Z_EN_PIN};

Axis* axisByName(const String& s){
  if(s=="x") return &AX_X;
  if(s=="y") return &AX_Y;
  if(s=="z") return &AX_Z;
  return nullptr;
}

// ---- utils ----
inline void pinWrite(uint8_t pin, bool hi){ digitalWrite(pin, hi?HIGH:LOW); }

void setupAxisPins(const Axis& a){
  pinMode(a.step, OUTPUT); pinWrite(a.step, false);
  pinMode(a.dir , OUTPUT); pinWrite(a.dir , false);
  pinMode(a.en  , OUTPUT);
  bool disabled_level = (ENABLE_ACTIVE_HIGH==0) ? true : false; // HIGH if LOW-active logic
  pinWrite(a.en, disabled_level);
}
void enableAxis(const Axis& a, bool on){
  bool level = (ENABLE_ACTIVE_HIGH==0) ? !on : on; // translate logical ON to physical level
  pinWrite(a.en, level);
}
void enableAll(bool on){ enableAxis(AX_X,on); enableAxis(AX_Y,on); enableAxis(AX_Z,on); }

void stepPulse(const Axis& a){
  pinWrite(a.step, true);
  delayMicroseconds(PULSE_US);
  pinWrite(a.step, false);
}
void moveSteps(const Axis& a, bool plus, long n){
  pinWrite(a.dir, plus?true:false);
  delayMicroseconds(5);
  for(long i=0;i<n;i++){
    stepPulse(a);
    delayMicroseconds(STEP_DELAY_US);
  }
}
void testAxis(Axis& a){
  enableAxis(a,true); delay(10);
  moveSteps(a,true,800); delay(200);
  moveSteps(a,false,800);
}

// ---- pump helpers (D10) ----
void pump_on(){ pinMode(PUMP_D10, OUTPUT); analogWrite(PUMP_D10, 255); }    // full on
void pump_off(){ pinMode(PUMP_D10, OUTPUT); analogWrite(PUMP_D10, 0); }     // off
void pump_pwm(int v){
  if(v<0) v=0; if(v>255) v=255;
  pinMode(PUMP_D10, OUTPUT); analogWrite(PUMP_D10, v);
}

// ---- serial helpers ----
String readLine(){
  static String buf;
  while(Serial.available()){
    char c = Serial.read();
    if(c=='\r') continue;
    if(c=='\n'){ String s=buf; buf=""; return s; }
    buf += c;
  }
  return String();
}
void printHelp(){
  Serial.println(F("help | ping | list"));
  Serial.println(F("spd <us> | pulse <us>"));
  Serial.println(F("enall <0|1> | en <x|y|z> <0|1> | enpol <0|1>"));
  Serial.println(F("mv <x|y|z> <+|-> <steps> | test <x|y|z|all>"));
  Serial.println(F("pump <0|1> | pumppwm <0..255>  (D10)"));
}
void printList(){
  auto p=[&](Axis& a){
    Serial.print(a.n); Serial.print(F(": STEP=")); Serial.print(a.step);
    Serial.print(F(" DIR=")); Serial.print(a.dir);
    Serial.print(F(" EN="));  Serial.println(a.en);
  };
  Serial.println(F("RAMPS 1.4.2 pins:")); p(AX_X); p(AX_Y); p(AX_Z);
  Serial.print(F("Enable active ")); Serial.println(ENABLE_ACTIVE_HIGH?F("HIGH"):F("LOW"));
  Serial.print(F("spd(us)=")); Serial.print(STEP_DELAY_US);
  Serial.print(F(" pulse(us)=")); Serial.println(PULSE_US);
  Serial.print(F("Pump D10=")); Serial.println(PUMP_D10);
}

unsigned long lastBlink=0;

void setup(){
  pinMode(LED_BUILTIN, OUTPUT); digitalWrite(LED_BUILTIN, LOW);
  Serial.begin(115200);

  // axes
  setupAxisPins(AX_X); setupAxisPins(AX_Y); setupAxisPins(AX_Z);
  enableAll(true); // give torque immediately

  // Air pump ON by default (as requested)
  pump_on();

  Serial.println(F("RAMPS 1.4.2 XYZ + PUMP D10 (ON) READY"));
  printList();
}
void loop(){
  // small heartbeat
  unsigned long t=millis();
  if(t - lastBlink > 500){ lastBlink=t; digitalWrite(LED_BUILTIN, !digitalRead(LED_BUILTIN)); }

  String line = readLine(); if(line.length()==0) return;
  line.trim(); line.toLowerCase();

  if(line=="help"){ printHelp(); return; }
  if(line=="ping"){ Serial.println(F("pong")); return; }
  if(line=="list"){ printList(); return; }

  if(line.startsWith("spd ")){
    long v=line.substring(4).toInt(); if(v<50)v=50; if(v>1000000)v=1000000;
    STEP_DELAY_US=(unsigned int)v; Serial.print(F("OK spd=")); Serial.println(STEP_DELAY_US); return;
  }
  if(line.startsWith("pulse ")){
    long v=line.substring(6).toInt(); if(v<2)v=2; if(v>100000)v=100000;
    PULSE_US=(unsigned int)v; Serial.print(F("OK pulse=")); Serial.println(PULSE_US); return;
  }

  if(line.startsWith("enall ")){
    bool on=(line.endsWith("1")||line.endsWith(" on"));
    enableAll(on); Serial.print(F("OK enall ")); Serial.println(on?F("ON"):F("OFF")); return;
  }
  if(line.startsWith("en ")){
    int s1=line.indexOf(' '), s2=line.indexOf(' ',s1+1);
    if(s2<0){ Serial.println(F("ERR usage: en <x|y|z> <0|1>")); return; }
    String a1=line.substring(s1+1,s2), a2=line.substring(s2+1);
    Axis* A=axisByName(a1); if(!A){ Serial.println(F("ERR axis")); return; }
    bool on=(a2=="1"||a2=="on"); enableAxis(*A,on);
    Serial.print(F("OK en ")); Serial.print(A->n); Serial.print(F("=")); Serial.println(on?F("ON"):F("OFF")); return;
  }
  if(line.startsWith("enpol ")){
    int v=line.substring(6).toInt(); ENABLE_ACTIVE_HIGH=(v?1:0);
    // put outputs into disabled default of new logic; then user can enall 1
    bool disabled_level = (ENABLE_ACTIVE_HIGH==0) ? true : false;
    pinWrite(AX_X.en, disabled_level); pinWrite(AX_Y.en, disabled_level); pinWrite(AX_Z.en, disabled_level);
    Serial.print(F("OK enpol=")); Serial.println(ENABLE_ACTIVE_HIGH); return;
  }

  if(line.startsWith("mv ")){
    int s1=line.indexOf(' '), s2=line.indexOf(' ',s1+1), s3=line.indexOf(' ',s2+1);
    if(s1<0||s2<0||s3<0){ Serial.println(F("ERR usage: mv <x|y|z> <+|-> <steps>")); return; }
    String ax=line.substring(s1+1,s2), di=line.substring(s2+1,s3);
    long steps=line.substring(s3+1).toInt(); if(steps<=0){ Serial.println(F("ERR steps")); return; }
    Axis* A=axisByName(ax); if(!A){ Serial.println(F("ERR axis")); return; }
    enableAxis(*A,true);
    bool plus=(di=="+"); moveSteps(*A, plus, steps);
    Serial.print(F("OK mv ")); Serial.print(ax); Serial.print(F(" ")); Serial.print(plus?'+':'-'); Serial.print(' '); Serial.println(steps); return;
  }

  if(line=="test all"){ testAxis(AX_X); testAxis(AX_Y); testAxis(AX_Z); Serial.println(F("OK test all")); return; }
  if(line=="test x"){ testAxis(AX_X); Serial.println(F("OK test x")); return; }
  if(line=="test y"){ testAxis(AX_Y); Serial.println(F("OK test y")); return; }
  if(line=="test z"){ testAxis(AX_Z); Serial.println(F("OK test z")); return; }
  if(line=="test"){ testAxis(AX_X); testAxis(AX_Y); testAxis(AX_Z); Serial.println(F("OK test all")); return; }

  // pump control (optional)
  if(line.startsWith("pump ")){ int on=line.substring(5).toInt(); if(on>0) pump_on(); else pump_off();
    Serial.print(F("OK pump=")); Serial.println(on>0?1:0); return; }
  if(line.startsWith("pumppwm ")){ int v=line.substring(8).toInt(); pump_pwm(v);
    Serial.print(F("OK pumppwm=")); Serial.println(v); return; }

  Serial.println(F("ERR unknown"));
}
