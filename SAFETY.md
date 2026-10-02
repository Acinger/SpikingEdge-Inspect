# Safety

SE Inspect controls real things: a 12 V conveyor through a relay, a stepper arm through an Arduino, and it sits next to a camera and a bench light. The software has **no safety function**. Read this before anything moves.

## Non-negotiable

1. **The software is not a safety device.** Stops, interlocks and emergency-off are hardware. A crashed Pi, a stuck relay or a browser tab in the wrong state must not be able to hurt anyone. Use a normally-open motor contact so that loss of control stops the belt (the code assumes relay jumper **H**, high-trigger, see guide chapter 03).
2. **Unpowered wiring.** Everything is wired with the 12 V supply and the Pi switched off. Common ground between Pi, relay module and motor supply is mandatory; the Pi runs from its own USB-C supply, never from the 12 V.
3. **Arm:** motors are off until "Motors on"; after power loss the arm has lost its reference and needs a homing run. Keep hands out of the working envelope while a line job runs. The "Fetch" sequence plays automatically in line mode.
4. **PCIe reset** (card watchdog) removes the card from the bus for ~6 s; recognition pauses, the belt is stopped by the state machine, but nothing physical is guaranteed by that.
5. **Light:** use a diffuse, flicker-free lamp; do not look into point-like LEDs at close range.

## The stationary profile (SE Inspect 1.0)

In the profile `stationaer` (default) the belt stays in simulation, the arm is not loaded and the line cannot be activated. That is the profile for the first setup and for everyone without a belt. The line profile is opt-in via `VORSA_PROFIL=linie`.

## Reporting

Found something that could hurt someone? Write to hello@spikingedge.com with "SAFETY" in the subject before posting it publicly.
