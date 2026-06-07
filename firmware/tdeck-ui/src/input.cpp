// KUMA Guard T-Deck - input implementation.
//
// Keyboard: the T-Deck has an ESP32-C3 keyboard co-processor on I2C @ 0x55.
// Reading one byte returns the ASCII of the last pressed key (0 = none).
// Trackball: four active-low GPIOs pulse as the ball rolls; the center is a
// shared BOOT button. We debounce on falling edges.
#include "input.h"
#include <Arduino.h>
#include <Wire.h>
#include "tdeck_pins.h"

namespace {
char     g_lastKey = 0;
uint8_t  g_tbState[4];                                   // up,down,left,right
const uint8_t TB_PINS[4] = {TDECK_TB_UP, TDECK_TB_DOWN,
                            TDECK_TB_LEFT, TDECK_TB_RIGHT};
const InputEvent TB_EVENTS[4] = {InputEvent::Up, InputEvent::Down,
                                 InputEvent::Left, InputEvent::Right};
uint32_t g_lastClickMs = 0;

char readKeyboard() {
  Wire.requestFrom((uint8_t)TDECK_KEYBOARD_ADDR, (uint8_t)1);
  if (Wire.available()) {
    char c = Wire.read();
    return c;
  }
  return 0;
}
}  // namespace

namespace input {

void begin() {
  for (int i = 0; i < 4; ++i) {
    pinMode(TB_PINS[i], INPUT_PULLUP);
    g_tbState[i] = digitalRead(TB_PINS[i]);
  }
  pinMode(TDECK_TB_CLICK, INPUT_PULLUP);
}

InputEvent poll() {
  // --- trackball: detect HIGH->LOW edges (one per detent) ----------------
  for (int i = 0; i < 4; ++i) {
    uint8_t s = digitalRead(TB_PINS[i]);
    if (g_tbState[i] == HIGH && s == LOW) {
      g_tbState[i] = s;
      return TB_EVENTS[i];
    }
    g_tbState[i] = s;
  }
  // --- trackball click = Select (debounced) ------------------------------
  if (digitalRead(TDECK_TB_CLICK) == LOW && millis() - g_lastClickMs > 250) {
    g_lastClickMs = millis();
    return InputEvent::Select;
  }
  // --- keyboard ----------------------------------------------------------
  char c = readKeyboard();
  if (c) {
    g_lastKey = c;
    switch (c) {
      case 0x0D: return InputEvent::Select;   // enter
      case 0x08: return InputEvent::Back;     // backspace
      case 'w':  return InputEvent::Up;
      case 's':  return InputEvent::Down;
      case 'a':  return InputEvent::Left;
      case 'd':  return InputEvent::Right;
      default:   break;
    }
  }
  return InputEvent::None;
}

// Read a fresh key from the keyboard FIFO and consume it (0 = none). Do NOT
// return a cached value or it repeats forever.
char lastKey() { return readKeyboard(); }

}  // namespace input
