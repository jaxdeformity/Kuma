// KUMA Guard T-Deck — input: BlackBerry-style I2C keyboard + trackball.
#pragma once

enum class InputEvent { None, Up, Down, Left, Right, Select, Back };

namespace input {
  void begin();           // call after Wire.begin()
  InputEvent poll();      // non-blocking; returns the next pending event
  char lastKey();         // last ASCII key from the keyboard (0 if none)
}
