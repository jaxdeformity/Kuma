// firmware/tdeck-ui/src/kuma_rf.h - T-Deck own-radio RF (gated by the caller).
#pragma once
#include <Arduino.h>

namespace kuma_rf {
// Parse "AA:BB:CC:DD:EE:FF" or dash form into out[6]. Returns false if malformed.
bool parseMac(const String& s, uint8_t out[6]);

// Inject a targeted deauth (both directions) `bursts` times on `channel`.
// Returns frames sent. CAUTION: switching channel + injecting drops the STA
// link; the caller must authorize FIRST and trigger a reconnect afterwards.
int deauth(const uint8_t bssid[6], const uint8_t client[6], uint8_t channel, int bursts);
}  // namespace kuma_rf
