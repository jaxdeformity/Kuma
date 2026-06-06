// KUMA Guard M5Core — screen rendering (SKELETON).
//
// Uses M5Unified's M5.Display (M5GFX). Sprint 1 draws text-only screens that
// match docs/api.md layouts; the pixel bear is a crude placeholder. Sprint 2
// swaps drawBear() for real sprite frames (see bear_sprites.cpp) and adds the
// event list/detail screens fed by /api/events.
#include "kuma_ui.h"
#include <M5Unified.h>

namespace {
constexpr int COLOR_BG     = 0x0000;  // black
constexpr int COLOR_SAFE   = 0x07E0;  // green
constexpr int COLOR_SENT   = 0x07FF;  // cyan
constexpr int COLOR_HONEY  = 0xFD20;  // orange
constexpr int COLOR_ALERT  = 0xF800;  // red

const char* MODE_LABELS[5] = {"Hibernate", "Foraging", "Honey",
                              "Sentinel", "Apex"};

uint16_t threatColor(const String& level) {
  if (level == "high" || level == "critical") return COLOR_ALERT;
  if (level == "medium") return COLOR_HONEY;
  return COLOR_SAFE;
}
}  // namespace

namespace kuma_ui {

void begin() {
  M5.Display.setRotation(1);
  M5.Display.fillScreen(COLOR_BG);
  M5.Display.setTextSize(2);
}

void drawHome(const KumaStatus& s) {
  auto& d = M5.Display;
  d.fillScreen(COLOR_BG);
  d.setTextColor(COLOR_SENT, COLOR_BG);
  d.setCursor(8, 8);
  d.print("KUMA GUARD");

  d.setTextColor(COLOR_SAFE, COLOR_BG);
  d.setCursor(8, 36);
  d.print("SENTINEL MODE");

  d.setCursor(8, 72);
  d.setTextColor(threatColor(s.threatLevel), COLOR_BG);
  d.printf("Threat: %s", s.online ? s.threatLevel.c_str() : "--");

  d.setTextColor(COLOR_SENT, COLOR_BG);
  d.setCursor(8, 100); d.printf("Events: %u", s.eventsLast10m);
  d.setCursor(8, 128); d.printf("Backend: %s", s.online ? "ONLINE" : "OFFLINE");

  drawBear(s.bearState, 230, 70);
}

void drawModeSelect(int selectedIndex) {
  auto& d = M5.Display;
  d.fillScreen(COLOR_BG);
  d.setTextColor(COLOR_SENT, COLOR_BG);
  d.setCursor(8, 8); d.print("Select Mode");
  for (int i = 0; i < 5; ++i) {
    d.setCursor(8, 40 + i * 28);
    d.setTextColor(i == selectedIndex ? COLOR_ALERT : COLOR_SAFE, COLOR_BG);
    d.printf("%s %s", i == selectedIndex ? ">" : " ", MODE_LABELS[i]);
  }
}

void drawEventList() {
  // Sprint 2: GET /api/events and render "[SEV] event_type" rows.
}

void drawActionConfirm(const char* action) {
  auto& d = M5.Display;
  d.fillScreen(COLOR_BG);
  d.setTextColor(COLOR_HONEY, COLOR_BG);
  d.setCursor(8, 8);  d.print("Confirm Action?");
  d.setTextColor(COLOR_SENT, COLOR_BG);
  d.setCursor(8, 50); d.print(action);
  d.setCursor(8, 110); d.print("A:Cancel  B:Confirm  C:Back");
}

void drawBear(BearState state, int x, int y) {
  // Placeholder mascot: a colored square whose color encodes the mood.
  // Sprint 2: replace with pushImage() sprite frames from bear_sprites.cpp.
  uint16_t c = COLOR_SAFE;
  switch (state) {
    case BearState::Alert:      c = COLOR_ALERT; break;
    case BearState::Suspicious: c = COLOR_SENT;  break;
    case BearState::HoneyTrap:  c = COLOR_HONEY; break;
    case BearState::Error:      c = 0x7BEF;      break;  // grey
    default: break;
  }
  M5.Display.fillRoundRect(x, y, 70, 70, 8, c);
}

}  // namespace kuma_ui
