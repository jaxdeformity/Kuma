// KUMA Guard T-Deck - backend HTTP client (real).
#pragma once
#include <Arduino.h>
#include "kuma_types.h"

struct KumaStatus {
  String    device;
  String    version;
  KumaMode  mode = KumaMode::Unknown;
  String    threatLevel;          // low|medium|high|critical
  BearState bearState = BearState::Error;
  uint32_t  uptimeSeconds = 0;
  uint16_t  eventsLast10m = 0;
  uint16_t  level = 1;
  uint16_t  networkCount = 0;
  String    spriteSet = "states"; // active form's sprite pack
  String    wifiInterface;        // sensor iface
  bool      online = false;       // false => backend unreachable
};

struct KumaEvent {
  String severity;
  String eventType;
  int    confidence = 0;
  String ssid;
};

namespace kuma_api {
  void begin();                                   // Wi-Fi STA connect
  bool wifiConnected();
  bool fetchStatus(KumaStatus& out);              // GET /api/status
  int  fetchEvents(KumaEvent* out, int maxN);     // GET /api/events -> count
  bool setMode(KumaMode mode);                    // POST /api/mode
  bool postBattleWin();                           // POST /api/progress/battle-win
  String get(const String& path);                 // raw GET (for the terminal)
  String shell(const String& cmd, String& cwdOut);// POST /api/shell -> combined output
  bool sendAction(const char* action, bool confirm);  // POST /api/action
}
