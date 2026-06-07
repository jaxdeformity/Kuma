// KUMA Guard T-Deck — screen rendering + the bear mascot.
#pragma once
#include "display.h"
#include "kuma_api_client.h"

enum class Screen { Home, ModeSelect, EventList };

namespace kuma_ui {
  void begin(LGFX_TDeck* d);
  void splash();
  void drawHome(const KumaStatus& s);
  void drawModeSelect(int selectedIndex, KumaMode current);
  void drawEventList(const KumaEvent* ev, int n);
  void drawBear(BearState st, int cx, int cy, int r);
}
