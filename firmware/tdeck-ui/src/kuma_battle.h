// KUMA Guard T-Deck - on-device Pokemon-style battle.
//
// When the backend reports a high/critical threat with a mappable rogue event,
// the T-Deck drops monitoring and runs the full encounter -> battle on-screen:
// enemy reveal, 4 abilities with type-effectiveness, 30s auto-turn, chiptune +
// SFX, win posts XP and plays victory, then returns to the monitoring face.
#pragma once
#include "display.h"
#include "kuma_api_client.h"

namespace battle {
  void begin(LGFX_TDeck* d);
  bool maybeStart(const KumaStatus& s);   // true if a battle ran (caller redraws home after)
}
