// ============================================================================
// RAMPS 1.4/1.5 – XYZ mit Endstops an X+/Y+/Z+ (MAX)
// Pumpe an D10 (2s Druckaufbau, danach automatisch AUS)
// 5V-Pressure-Valve an D11 (digital, manuell steuerbar & automatisch durch Pumpen-Logik)
// ----------------------------------------------------------------------------
// Verhalten (Pumpe/Ventil):
//  • pump 1: Ventil schließt (halten), Pumpe läuft 2000 ms, danach AUS; Ventil bleibt zu = hält Druck.
//  • pump 0: Pumpe AUS, Ventil öffnet (Druck ablassen).
//  • valve 0|1: manuell Ventil schließen(0)/öffnen(1) – überschreibt die automatische Ventilstellung.
//  • pumppwm <0..255>: PWM der Pumpe (wirkt während der 2s-Aufbauphase).
//  • pumpkick: kurzer 100%-Kick (optional).
// ----------------------------------------------------------------------------
// Standard-Endstop-Logik: NO→GND, INPUT_PULLUP, PRESSED=LOW.
// ============================================================================

#include <Arduino.h>

// ---- STEP/DIR/EN Pins (RAMPS) ----
#define X_STEP_PIN 54
#define X_DIR_PIN  55
#define X_EN_PIN   38
#define Y_STEP_PIN 60
#define Y_DIR_PIN  61
#define Y_EN_PIN   56
#define Z_STEP_PIN 46
#define Z_DIR_PIN  48
#define Z_EN_PIN   62

// ---- MAX Endstops (X+/Y+/Z+) ----
#define X_MAX_PIN  2
#define Y_MAX_PIN  15
#define Z_MAX_PIN  19

// ---- Optional: X-MIN vorhanden (hier ungenutzt) ----
#define X_MIN_PIN  3

// ---- Aktoren ----
#define PUMP_PIN   10     // RAMPS D10 (MOSFET) – Pumpe (12/24 V)
#define VALVE_PIN  11     // 5V-Ventil (Servo 0) – digital (LOW/zu, HIGH/auf) => bei Bedarf invertieren

// ---- Timings / Polaritäten ----
volatile unsigned int STEP_DELAY_US = 1000;
volatile unsigned int PULSE_US      = 6;
// 0 = Enable LOW-aktiv (A4988/DRV8825 Standard), 1 = HIGH-aktiv
volatile uint8_t ENABLE_ACTIVE_HIGH = 0;

// Endstop-Logik
const bool ENDSTOP_ACTIVE_LOW = true;

// ---- Achsen/Lock ----
struct Axis {
  const char* name;
  uint8_t step, dir, en, maxEnd;
  bool lockActive;
  bool lockDirPlus;
};
Axis AX_X = {"x", X_STEP_PIN, X_DIR_PIN, X_EN_PIN, X_MAX_PIN, false, false};
Axis AX_Y = {"y", Y_STEP_PIN, Y_DIR_PIN, Y_EN_PIN, Y_MAX_PIN, false, false};
Axis AX_Z = {"z", Z_STEP_PIN, Z_DIR_PIN, Z_EN_PIN, Z_MAX_PIN, false, false};

inline void dWrite(uint8_t pin, bool hi){ digitalWrite(pin, hi?HIGH:LOW); }
void setupAxisPins(const Axis& a){
  pinMode(a.step, OUTPUT); dWrite(a.step, false);
  pinMode(a.dir , OUTPUT); dWrite(a.dir , false);
  pinMode(a.en  , OUTPUT);
  const bool disabled = (ENABLE_ACTIVE_HIGH==0) ? true : false;
  dWrite(a.en, disabled);
}
void enableAxis(const Axis& a, bool on){
  const bool level = (ENABLE_ACTIVE_HIGH==0) ? !on : on;
  dWrite(a.en, level);
}
void enableAll(bool on){ enableAxis(AX_X,on); enableAxis(AX_Y,on); enableAxis(AX_Z,on); }

inline bool endstopMaxPressed(uint8_t pin){
  int v = digitalRead(pin);
  return ENDSTOP_ACTIVE_LOW ? (v==LOW) : (v==HIGH);
}

inline void stepPulse(const Axis& a){
  dWrite(a.step, true);
  delayMicroseconds(PULSE_US);
  dWrite(a.step, false);
}
inline void setDir(const Axis& a, bool plus){
  dWrite(a.dir, plus ? HIGH : LOW);
  delayMicroseconds(5);
}

// Bewegung mit Lock-Logik
bool moveSteps(Axis& a, bool plus, long n){
  if(endstopMaxPressed(a.maxEnd)){
    if(!a.lockActive){ a.lockActive = true; a.lockDirPlus = plus; }
    if(plus == a.lockDirPlus){
      Serial.print(F("LOCK ")); Serial.println(a.name);
      Serial.println(F("ERR endstop pressed; move opposite only"));
      return false;
    }
  } else {
    a.lockActive = false;
  }
  setDir(a, plus);
  for(long i=0;i<n;i++){
    if(endstopMaxPressed(a.maxEnd)){
      a.lockActive  = true;
      a.lockDirPlus = plus;
      Serial.print(F("HIT "));  Serial.println(a.name);
      Serial.print(F("LOCK ")); Serial.println(a.name);
      return false;
    }
    stepPulse(a);
    delayMicroseconds(STEP_DELAY_US);
  }
  if(!endstopMaxPressed(a.maxEnd)) a.lockActive = false;
  return true;
}
void testAxis(Axis& a){
  enableAxis(a,true); delay(10);
  moveSteps(a,true,800);
  delay(120);
  moveSteps(a,false,800);
}
Axis* axisByName(const String& s){
  if(s=="x") return &AX_X;
  if(s=="y") return &AX_Y;
  if(s=="z") return &AX_Z;
  return nullptr;
}

// ---- Pumpe D10 ----
int pump_pwm_val = 255;
void pump_set_pwm(int v){ if(v<0)v=0; if(v>255)v=255; pump_pwm_val=v; pinMode(PUMP_PIN,OUTPUT); analogWrite(PUMP_PIN, v); }
void pump_on(){ pump_set_pwm(pump_pwm_val); }
void pump_off(){ pump_set_pwm(0); }
void pump_kickstart(unsigned long ms=250){ int keep=pump_pwm_val; analogWrite(PUMP_PIN,255); delay(ms); analogWrite(PUMP_PIN,keep); }

// ---- 5V-Ventil D11 ----
// Annahme: LOW = geschlossen (hält), HIGH = offen (entlüftet)
// Falls invertiert: einfach HIGH/LOW in open()/close() tauschen.
bool valve_state = true;        // true=OFFEN, false=ZU
bool valve_manual_override = false; // true = "valve"-Befehl hält den Zustand fest

void valve_open(){ pinMode(VALVE_PIN, OUTPUT); digitalWrite(VALVE_PIN, HIGH); valve_state = true; }
void valve_close(){ pinMode(VALVE_PIN, OUTPUT); digitalWrite(VALVE_PIN, LOW ); valve_state = false; }

// ---- Pumpen-State ----
enum PumpState : uint8_t { PUMP_IDLE=0, PUMP_BUILDING=1, PUMP_HOLDING=2 };
PumpState pump_state = PUMP_IDLE;
unsigned long pump_build_until_ms = 0;
const unsigned long PUMP_BUILD_MS = 2000; // 2 s

// ---- Serial Helfer ----
String readLine(){
  static String buf;
  while(Serial.available()){
    char c=Serial.read();
    if(c=='\r') continue;
    if(c=='\n'){ String s=buf; buf=""; return s; }
    buf += c;
  }
  return String();
}

// ---- Print ----
void printHelp(){
  Serial.println(F("Befehle:"));
  Serial.println(F("  help | ping | list | endstat"));
  Serial.println(F("  spd <us> | pulse <us> | enpol <0|1>"));
  Serial.println(F("  enall <0|1> | en <x|y|z> <0|1>"));
  Serial.println(F("  mv <x|y|z> <+|-> <steps> | test <x|y|z|all> | home <x|y|z|all>"));
  Serial.println(F("  pump <0|1> | pumppwm <0..255> | pumpkick"));
  Serial.println(F("  valve <0|1>   // 1=open (entlueften), 0=close (halten); setzt manuellen Override"));
}
void printAxisCfg(const Axis& a){
  Serial.print(a.name); Serial.print(F(": STEP=")); Serial.print(a.step);
  Serial.print(F(" DIR="));  Serial.print(a.dir);
  Serial.print(F(" EN="));   Serial.print(a.en);
  Serial.print(F(" MAX="));  Serial.print(a.maxEnd);
  Serial.print(F(" lock=")); Serial.print(a.lockActive?F("ON"):F("off"));
  if(a.lockActive){ Serial.print(F(" dir=")); Serial.print(a.lockDirPlus?'+':'-'); }
  Serial.println();
}
void printList(){
  Serial.println(F("RAMPS XYZ + MAX-Endstops + D10 Pumpe + D11 Ventil (2s-Build & Hold)"));
  printAxisCfg(AX_X); printAxisCfg(AX_Y); printAxisCfg(AX_Z);
  Serial.print(F("Enable aktiv: ")); Serial.println(ENABLE_ACTIVE_HIGH?F("HIGH"):F("LOW"));
  Serial.print(F("spd(us)=")); Serial.print(STEP_DELAY_US);
  Serial.print(F(" pulse(us)=")); Serial.println(PULSE_US);
  Serial.print(F("PUMP D10 PWM=")); Serial.println(pump_pwm_val);
  Serial.print(F("VALVE D11=")); Serial.print(valve_state?F("OPEN"):F("CLOSED"));
  Serial.print(F(" manual=")); Serial.println(valve_manual_override?F("ON"):F("off"));
  Serial.print(F("Pump-Mode="));
  if(pump_state==PUMP_IDLE) Serial.println(F("IDLE"));
  else if(pump_state==PUMP_BUILDING) Serial.println(F("BUILDING"));
  else Serial.println(F("HOLDING"));
}
void printEndstops(){
  Serial.print(F("X+ MAX=")); Serial.print(endstopMaxPressed(X_MAX_PIN)?"PRESSED":"open"); Serial.print(F("  "));
  Serial.print(F("Y+ MAX=")); Serial.print(endstopMaxPressed(Y_MAX_PIN)?"PRESSED":"open"); Serial.print(F("  "));
  Serial.print(F("Z+ MAX=")); Serial.print(endstopMaxPressed(Z_MAX_PIN)?"PRESSED":"open");
  Serial.println();
}

// ---- Homing ----
bool homeAxis(Axis& a, unsigned long timeout_ms = 15000UL){
  enableAxis(a,true); delay(10);
  if(endstopMaxPressed(a.maxEnd)){
    setDir(a, false);
    for(int i=0;i<400;i++){ stepPulse(a); delayMicroseconds(STEP_DELAY_US); }
  }
  setDir(a, true);
  unsigned long t0 = millis();
  while(!endstopMaxPressed(a.maxEnd)){
    stepPulse(a); delayMicroseconds(STEP_DELAY_US);
    if(millis()-t0 > timeout_ms){
      Serial.print(F("ERR home ")); Serial.print(a.name); Serial.println(F(": Timeout"));
      return false;
    }
  }
  a.lockActive = true; a.lockDirPlus = true;
  Serial.print(F("OK home ")); Serial.println(a.name);
  return true;
}

// ---- Setup/Loop ----
unsigned long lastBlink=0;

void setup(){
  pinMode(LED_BUILTIN, OUTPUT); dWrite(LED_BUILTIN, LOW);
  Serial.begin(115200);

  setupAxisPins(AX_X); setupAxisPins(AX_Y); setupAxisPins(AX_Z);

  pinMode(X_MAX_PIN, INPUT_PULLUP);
  pinMode(Y_MAX_PIN, INPUT_PULLUP);
  pinMode(Z_MAX_PIN, INPUT_PULLUP);
  pinMode(X_MIN_PIN, INPUT_PULLUP);

  // Aktoren initial
  pump_set_pwm(0);
  pinMode(VALVE_PIN, OUTPUT);
  valve_open();                 // Start: offen/entlüftet
  valve_manual_override = false;
  pump_state = PUMP_IDLE;

  enableAll(true);

  Serial.println(F("RAMPS XYZ + MAX-Endstops + Pumpe D10 + Ventil D11 bereit (2s-Build/Hold)"));
  printList();
}

void loop(){
  unsigned long t=millis();
  if(t-lastBlink>500){ lastBlink=t; dWrite(LED_BUILTIN, !digitalRead(LED_BUILTIN)); }

  // State-Machine Pumpe
  if(pump_state == PUMP_BUILDING){
    if((long)(millis() - pump_build_until_ms) >= 0){
      pump_off();
      pump_state = PUMP_HOLDING;
      // Ventil bleibt zu (halten)
      Serial.println(F("OK pump build done -> HOLDING"));
    }
  }

  // Parser
  String line = readLine(); if(line.length()==0) return;
  line.trim(); line.toLowerCase();

  if(line=="help"){ printHelp(); return; }
  if(line=="ping"){ Serial.println(F("pong")); return; }
  if(line=="list"){ printList(); return; }
  if(line=="endstat"){ printEndstops(); return; }

  if(line.startsWith("spd ")){ long v=line.substring(4).toInt(); if(v<50)v=50; if(v>1000000)v=1000000; STEP_DELAY_US=(unsigned int)v; Serial.print(F("OK spd=")); Serial.println(STEP_DELAY_US); return; }
  if(line.startsWith("pulse ")){ long v=line.substring(6).toInt(); if(v<2)v=2; if(v>100000)v=100000; PULSE_US=(unsigned int)v; Serial.print(F("OK pulse=")); Serial.println(PULSE_US); return; }
  if(line.startsWith("enpol ")){ int v=line.substring(6).toInt(); ENABLE_ACTIVE_HIGH=(v?1:0);
    const bool dis=(ENABLE_ACTIVE_HIGH==0)?true:false;
    dWrite(AX_X.en,dis); dWrite(AX_Y.en,dis); dWrite(AX_Z.en,dis);
    Serial.print(F("OK enpol=")); Serial.println(ENABLE_ACTIVE_HIGH);
    Serial.println(F("Hinweis: danach ggf. 'enall 1' senden.")); return; }

  if(line.startsWith("enall ")){ bool on=(line.endsWith("1")||line.endsWith(" on")); enableAll(on);
    Serial.print(F("OK enall ")); Serial.println(on?F("ON"):F("OFF")); return; }

  if(line.startsWith("en ")){
    int s1=line.indexOf(' '), s2=line.indexOf(' ', s1+1);
    if(s2<0){ Serial.println(F("ERR usage: en <x|y|z> <0|1>")); return; }
    String a1=line.substring(s1+1, s2), a2=line.substring(s2+1);
    Axis* A=axisByName(a1); if(!A){ Serial.println(F("ERR axis")); return; }
    bool on=(a2=="1"||a2=="on"); enableAxis(*A,on);
    Serial.print(F("OK en ")); Serial.print(A->name); Serial.print(F("=")); Serial.println(on?F("ON"):F("OFF")); return;
  }

  if(line.startsWith("mv ")){
    int s1=line.indexOf(' '), s2=line.indexOf(' ', s1+1), s3=line.indexOf(' ', s2+1);
    if(s1<0||s2<0||s3<0){ Serial.println(F("ERR usage: mv <x|y|z> <+|-> <steps>")); return; }
    String ax=line.substring(s1+1, s2), di=line.substring(s2+1, s3);
    long steps=line.substring(s3+1).toInt(); if(steps<=0){ Serial.println(F("ERR steps")); return; }
    Axis* A=axisByName(ax); if(!A){ Serial.println(F("ERR axis")); return; }
    bool plus=(di=="+");
    enableAxis(*A,true);
    bool ok=moveSteps(*A,plus,steps);
    Serial.print(F("OK mv ")); Serial.print(ax); Serial.print(F(" ")); Serial.print(plus?'+':'-'); Serial.print(' '); Serial.println(steps);
    return;
  }

  if(line=="test x"){ testAxis(AX_X); Serial.println(F("OK test x")); return; }
  if(line=="test y"){ testAxis(AX_Y); Serial.println(F("OK test y")); return; }
  if(line=="test z"){ testAxis(AX_Z); Serial.println(F("OK test z")); return; }
  if(line=="test all"){ testAxis(AX_X); testAxis(AX_Y); testAxis(AX_Z); Serial.println(F("OK test all")); return; }

  if(line.startsWith("home ")){
    String targ=line.substring(5); targ.trim(); bool any=false, ok=true;
    if(targ=="x"||targ=="all"){ any=true; ok&=homeAxis(AX_X); }
    if(targ=="y"||targ=="all"){ any=true; ok&=homeAxis(AX_Y); }
    if(targ=="z"||targ=="all"){ any=true; ok&=homeAxis(AX_Z); }
    if(!any){ Serial.println(F("ERR usage: home <x|y|z|all>")); return; }
    Serial.println(ok?F("OK home"):F("ERR home")); return;
  }

  // ---- Pumpe/Valve ----
  if(line.startsWith("pump ")){
    int on=line.substring(5).toInt();
    if(on>0){
      valve_manual_override = false; // Automatik übernehmen lassen
      valve_close();                // halten
      pump_on();
      pump_state = PUMP_BUILDING;
      pump_build_until_ms = millis() + PUMP_BUILD_MS;
      Serial.println(F("OK pump=1 (BUILD 2s, valve CLOSED)"));
    } else {
      pump_off();
      valve_manual_override = false; // zurücksetzen
      valve_open();                 // entlüften
      pump_state = PUMP_IDLE;
      Serial.println(F("OK pump=0 (IDLE, valve OPEN)"));
    }
    return;
  }

  if(line.startsWith("pumppwm ")){
    int v=line.substring(8).toInt(); if(v<0)v=0; if(v>255)v=255;
    pump_pwm_val = v;
    if(pump_state==PUMP_BUILDING) pump_set_pwm(pump_pwm_val);
    Serial.print(F("OK pumppwm=")); Serial.println(v); return;
  }

  if(line=="pumpkick"){ pump_kickstart(250); Serial.println(F("OK pumpkick")); return; }

  if(line.startsWith("valve ")){
    // Manuelle Ventilsteuerung (Override aktiv)
    int on=line.substring(6).toInt();
    valve_manual_override = true;
    if(on>0){ valve_open();  Serial.println(F("OK valve=1 (OPEN/manual)")); }
    else    { valve_close(); Serial.println(F("OK valve=0 (CLOSED/manual)")); }
    return;
  }

  Serial.println(F("ERR unknown"));
}
