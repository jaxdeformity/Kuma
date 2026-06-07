// KUMA Guard T-Deck — backend HTTP client implementation.
#include "kuma_api_client.h"
#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include "config.h"

namespace {
String baseUrl() {
  return String("http://") + KUMA_BACKEND_HOST + ":" + KUMA_BACKEND_PORT;
}
}  // namespace

namespace kuma_api {

void begin() {
  WiFi.mode(WIFI_STA);
  WiFi.setSleep(false);
  WiFi.begin(KUMA_WIFI_SSID, KUMA_WIFI_PASSWORD);
}

bool wifiConnected() { return WiFi.status() == WL_CONNECTED; }

bool fetchStatus(KumaStatus& out) {
  out.online = false;
  if (!wifiConnected()) { out.bearState = BearState::Error; return false; }

  HTTPClient http;
  http.setConnectTimeout(1500);
  http.setTimeout(2000);
  if (!http.begin(baseUrl() + "/api/status")) return false;
  int code = http.GET();
  if (code != 200) { http.end(); out.bearState = BearState::Error; return false; }

  JsonDocument doc;
  DeserializationError err = deserializeJson(doc, http.getStream());
  http.end();
  if (err) { out.bearState = BearState::Error; return false; }

  out.device        = doc["device"]       | "KUMA Guard";
  out.version       = doc["version"]      | "?";
  out.mode          = modeFromString(doc["mode"] | "");
  out.threatLevel   = doc["threat_level"] | "low";
  out.bearState     = bearStateFromString(doc["bear_state"] | "");
  out.uptimeSeconds = doc["uptime_seconds"] | 0;
  out.eventsLast10m = doc["events_last_10m"] | 0;
  out.online        = true;
  return true;
}

int fetchEvents(KumaEvent* out, int maxN) {
  if (!wifiConnected()) return 0;
  HTTPClient http;
  http.setConnectTimeout(1500);
  http.setTimeout(2500);
  if (!http.begin(baseUrl() + "/api/events?limit=" + String(maxN))) return 0;
  int code = http.GET();
  if (code != 200) { http.end(); return 0; }

  JsonDocument doc;
  DeserializationError err = deserializeJson(doc, http.getStream());
  http.end();
  if (err || !doc.is<JsonArray>()) return 0;

  int n = 0;
  for (JsonObject e : doc.as<JsonArray>()) {
    if (n >= maxN) break;
    out[n].severity   = e["severity"]   | "low";
    out[n].eventType  = e["event_type"] | "?";
    out[n].confidence = e["confidence"] | 0;
    out[n].ssid       = e["ssid"]       | "";
    ++n;
  }
  return n;
}

bool setMode(KumaMode mode) {
  if (!wifiConnected()) return false;
  HTTPClient http;
  http.setTimeout(2000);
  if (!http.begin(baseUrl() + "/api/mode")) return false;
  http.addHeader("Content-Type", "application/json");
  String body = String("{\"mode\":\"") + modeName(mode) + "\"}";
  int code = http.POST(body);
  http.end();
  return code == 200;
}

bool sendAction(const char* action, bool confirm) {
  if (!wifiConnected()) return false;
  HTTPClient http;
  http.setTimeout(2000);
  if (!http.begin(baseUrl() + "/api/action")) return false;
  http.addHeader("Content-Type", "application/json");
  String body = String("{\"action\":\"") + action +
                "\",\"confirm\":" + (confirm ? "true" : "false") + "}";
  int code = http.POST(body);
  http.end();
  return code == 200;
}

}  // namespace kuma_api
