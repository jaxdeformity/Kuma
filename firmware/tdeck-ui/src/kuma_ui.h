// KUMA Guard T-Deck - screen rendering + the bear mascot.
#pragma once
#include "display.h"
#include "kuma_api_client.h"

enum class Screen { Home, ModeSelect, EventList, Settings, Networks };

// Firmware version shown on the Settings -> Firmware row (committed, unlike the
// gitignored config.h). Bump on flashes.
#define KUMA_FW_VERSION "0.2.0"

// Settings rows, in display order. SET_COUNT bounds row navigation.
enum SettingsRow {
  SET_VOLUME, SET_BRIGHT, SET_WIFI, SET_ABOUT, SET_CREDITS,
  SET_REBOOT, SET_POWEROFF, SET_COUNT
};

// Everything drawSettings needs, assembled by the caller each redraw.
struct SettingsView {
  int  vol;             // 0..100
  int  bright;          // 0..100
  int  sel;             // highlighted row (SettingsRow)
  int  confirm;         // row index awaiting click-to-confirm, or -1
  const char* wifiSsid; // associated SSID ("" if none)
  const char* ip;       // local IP string, or "offline"
  bool backendOnline;   // Pi backend reachable
  const char* fwVersion;
  const char* backendVersion;
};

namespace kuma_ui {
  void begin(LGFX_TDeck* d);
  void splash();
  void drawHome(const KumaStatus& s);
  void drawModeSelect(int selectedIndex, KumaMode current);
  void drawEventList(const KumaEvent* ev, int n);
  void drawSettings(const SettingsView& v);
  void drawNetworks(const KumaNetwork* nets, int n, int total, int scroll);
  void drawBear(lgfx::LovyanGFX* g, BearState st, int cx, int cy, int r);
}
