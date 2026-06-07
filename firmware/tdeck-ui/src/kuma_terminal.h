// KUMA Guard T-Deck - keyboard terminal/console.
//
// The whole point of the BlackBerry keyboard: type commands and talk to KUMA.
// A blocking console screen (like the battle) - reads the keyboard + trackball,
// runs commands against the Pi API, prints to a scrollback. Back/exit returns home.
#pragma once
#include "display.h"

namespace terminal {
  void begin(LGFX_TDeck* d);
  void run();   // blocking until the user exits
}
