// KUMA Guard - M5Core UI client entrypoint.
//
// The M5Core is the face/controller only. It:
//   1. joins Wi-Fi,
//   2. polls the Pi backend /api/status,
//   3. renders the bear + mode + threat level,
//   4. lets the user switch modes / confirm safe actions.
//
// Button mapping (M5Core BASIC, 3 buttons):
//   A = previous / menu     B = select / confirm     C = next / back
//
// SKELETON: drawing + nav are stubbed in kuma_ui.cpp. Wi-Fi + HTTP are stubbed
// in kuma_api_client.cpp. The control loop and structure are real so the
// firmware compiles and the screens wire up cleanly in Sprint 2.
#include <M5Unified.h>

#include "config.h"
#include "kuma_api_client.h"
#include "kuma_ui.h"

static KumaStatus g_status;
static Screen g_screen = Screen::Home;
static int g_modeIndex = 3;            // default highlight: Sentinel
static uint32_t g_lastStatusPoll = 0;

void setup() {
  auto cfg = M5.config();
  M5.begin(cfg);
  kuma_ui::begin();
  kuma_api::begin();                   // connect Wi-Fi (stub in Sprint 1)
  kuma_ui::drawHome(g_status);
}

void loop() {
  M5.update();                         // refresh button state

  // --- poll backend ---------------------------------------------------
  const uint32_t now = millis();
  if (now - g_lastStatusPoll >= KUMA_STATUS_POLL_MS) {
    g_lastStatusPoll = now;
    kuma_api::fetchStatus(g_status);   // sets g_status.online
    if (g_screen == Screen::Home) kuma_ui::drawHome(g_status);
  }

  // --- buttons: A=prev/menu  B=select/confirm  C=next/back ------------
  if (M5.BtnB.wasPressed()) {
    switch (g_screen) {
      case Screen::Home:        g_screen = Screen::ModeSelect;
                                kuma_ui::drawModeSelect(g_modeIndex); break;
      case Screen::ModeSelect:  kuma_api::setMode(
                                    static_cast<KumaMode>(g_modeIndex));
                                g_screen = Screen::Home;
                                kuma_ui::drawHome(g_status); break;
      default:                  g_screen = Screen::Home;
                                kuma_ui::drawHome(g_status); break;
    }
  }
  if (M5.BtnC.wasPressed() && g_screen == Screen::ModeSelect) {
    g_modeIndex = (g_modeIndex + 1) % 5;
    kuma_ui::drawModeSelect(g_modeIndex);
  }
  if (M5.BtnA.wasPressed() && g_screen == Screen::ModeSelect) {
    g_modeIndex = (g_modeIndex + 4) % 5;
    kuma_ui::drawModeSelect(g_modeIndex);
  }

  delay(20);
}
