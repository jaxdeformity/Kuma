// KUMA Guard T-Deck - backend HTTP client implementation.
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
  WiFi.setAutoReconnect(true);          // recover automatically after a drop
  WiFi.persistent(true);
  WiFi.begin(KUMA_WIFI_SSID, KUMA_WIFI_PASSWORD);
}

bool wifiConnected() { return WiFi.status() == WL_CONNECTED; }

// Call every loop tick. If the link is down (e.g. a deauth kicked us off the
// protected AP), force a fresh association attempt, throttled so we don't spam
// WiFi.begin(). Without this the face stays OFFLINE until a reboot.
void reconnectIfDown() {
  if (WiFi.status() == WL_CONNECTED) return;
  static uint32_t lastTry = 0;
  uint32_t now = millis();
  if (now - lastTry < 3000) return;     // retry at most every 3s
  lastTry = now;
  WiFi.disconnect();
  WiFi.begin(KUMA_WIFI_SSID, KUMA_WIFI_PASSWORD);
}

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
  out.level         = doc["level"]          | 1;
  out.networkCount  = doc["network_count"]  | 0;
  out.spriteSet     = doc["sprite_set"]     | "states";
  out.background    = doc["background"]      | "backg1";
  out.creator       = doc["creator"]         | false;
  out.wifiInterface = doc["wifi_interface"] | "wlan1mon";
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

int fetchNetworks(KumaNetwork* out, int maxN) {
  if (!wifiConnected()) return 0;
  HTTPClient http;
  http.setTimeout(5000);
  if (!http.begin(baseUrl() + "/api/networks?limit=" + String(maxN))) return 0;
  if (http.GET() != 200) { http.end(); return 0; }
  JsonDocument doc;
  DeserializationError err = deserializeJson(doc, http.getStream());
  http.end();
  if (err) return 0;
  int n = 0;
  for (JsonObject e : doc["networks"].as<JsonArray>()) {
    if (n >= maxN) break;
    out[n].bssid = e["bssid"] | "??";
    const char* ss = e["ssid"] | "";
    out[n].ssid = (ss && ss[0]) ? String(ss) : String("<hidden>");
    out[n].security = e["security"] | "?";
    out[n].channel = e["channel"] | 0;
    out[n].rssi = e["best_rssi"] | 0;
    out[n].timesSeen = e["times_seen"] | 0;
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

bool postBattleWin() {
  if (!wifiConnected()) return false;
  HTTPClient http;
  http.setTimeout(2000);
  if (!http.begin(baseUrl() + "/api/progress/battle-win")) return false;
  int code = http.POST("");
  http.end();
  return code == 200;
}

String get(const String& path) {
  if (!wifiConnected()) return "(offline)";
  HTTPClient http;
  http.setTimeout(3000);
  if (!http.begin(baseUrl() + path)) return "(begin failed)";
  int code = http.GET();
  String body = (code == 200) ? http.getString() : (String("HTTP ") + code);
  http.end();
  return body;
}

String shell(const String& cmd, String& cwdOut) {
  if (!wifiConnected()) return "(offline)";
  HTTPClient http;
  http.setTimeout(25000);                         // server caps commands at 20s
  if (!http.begin(baseUrl() + "/api/shell")) return "(begin failed)";
  http.addHeader("Content-Type", "application/json");
  http.addHeader("X-KUMA-Shell-Token", KUMA_SHELL_TOKEN);
  JsonDocument body; body["cmd"] = cmd;
  String payload; serializeJson(body, payload);
  int code = http.POST(payload);
  String resp = http.getString();
  http.end();
  if (code != 200) return String("! HTTP ") + code + "  " + resp;
  JsonDocument rd;
  if (deserializeJson(rd, resp)) return resp;     // not JSON, show raw
  cwdOut = rd["cwd"] | cwdOut;
  return rd["out"] | "";
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
