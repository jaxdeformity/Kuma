// KUMA Guard M5Core - backend HTTP client.
#pragma once

#include <Arduino.h>
#include "modes.h"

struct KumaStatus {
  String device;
  String version;
  KumaMode mode = KumaMode::Unknown;
  String threatLevel;       // low|medium|high|critical
  BearState bearState = BearState::Error;
  uint32_t uptimeSeconds = 0;
  uint16_t eventsLast10m = 0;
  bool online = false;      // false => backend unreachable
};

namespace kuma_api {
  void begin();                                  // connect Wi-Fi
  bool fetchStatus(KumaStatus& out);             // GET /api/status
  bool setMode(KumaMode mode);                   // POST /api/mode
  bool sendAction(const char* action, bool confirm);  // POST /api/action
}
