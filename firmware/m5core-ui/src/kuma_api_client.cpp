// KUMA Guard M5Core - backend HTTP client (SKELETON).
//
// Sprint 2 fills these in with WiFi.begin() + HTTPClient + ArduinoJson.
// The function bodies below are safe no-ops/stubs so the firmware links and
// the UI can be exercised against a stubbed status.
#include "kuma_api_client.h"

#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>

#include "config.h"
#include "modes.h"

namespace kuma_api {

void begin() {
  // Sprint 2: WiFi.mode(WIFI_STA); WiFi.begin(KUMA_WIFI_SSID, KUMA_WIFI_PASSWORD);
  // then block (with timeout) until WL_CONNECTED.
}

bool fetchStatus(KumaStatus& out) {
  // Sprint 2:
  //   HTTPClient http;
  //   http.begin("http://" KUMA_BACKEND_HOST ":" + String(KUMA_BACKEND_PORT) + "/api/status");
  //   if (http.GET() == 200) { JsonDocument doc; deserializeJson(doc, http.getString());
  //                            out.mode = modeFromString(doc["mode"]); ... out.online = true; }
  out.online = false;            // stub: pretend backend is unreachable
  out.bearState = BearState::Error;
  return false;
}

bool setMode(KumaMode mode) {
  // Sprint 2: POST /api/mode {"mode": modeName(mode)}
  (void)mode;
  return false;
}

bool sendAction(const char* action, bool confirm) {
  // Sprint 2: POST /api/action {"action": action, "confirm": confirm}
  (void)action; (void)confirm;
  return false;
}

}  // namespace kuma_api
