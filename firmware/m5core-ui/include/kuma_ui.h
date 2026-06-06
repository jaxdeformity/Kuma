// KUMA Guard M5Core — screen rendering + navigation.
#pragma once

#include "kuma_api_client.h"

enum class Screen { Home, ModeSelect, EventList, EventDetail, ActionConfirm };

namespace kuma_ui {
  void begin();
  void drawHome(const KumaStatus& s);
  void drawModeSelect(int selectedIndex);
  void drawEventList();      // Sprint 2: populate from /api/events
  void drawActionConfirm(const char* action);
  void drawBear(BearState state, int x, int y);  // pixel mascot
}
