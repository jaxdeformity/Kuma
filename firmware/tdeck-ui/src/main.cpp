// KUMA Guard - LilyGo T-Deck UI client (flagship face).
//
// Boot: power-enable -> I2C -> display -> Wi-Fi -> poll the Pi backend and
// render the bear. Trackball/keyboard drive a small screen state machine.
//
//   Home        : status + bear. Click/Enter -> Mode select. Right -> Events.
//   ModeSelect  : Up/Down choose, Click/Enter applies (POST /api/mode), Back.
//   EventList   : recent events from /api/events. Back -> Home.
#include <Arduino.h>
#include <Wire.h>
#include <Preferences.h>

#include "tdeck_pins.h"
#include "config.h"
#include "display.h"
#include "input.h"
#include "kuma_api_client.h"
#include "kuma_ui.h"
#include "kuma_battle.h"
#include "kuma_audio.h"

static LGFX_TDeck display;
static KumaStatus g_status;
static KumaEvent  g_events[8];
static int        g_eventCount = 0;

static Screen g_screen = Screen::Home;
static int    g_modeIndex = 3;             // default highlight: Sentinel
static uint32_t g_lastStatusPoll = 0;
static uint8_t  g_statusFails = 0;         // tolerate transient poll failures

static Preferences g_prefs;
static int g_setVol = 22;                  // %
static int g_setBright = 80;               // %
static int g_setSel = 0;                   // selected settings row

static uint8_t brightRaw(int pct) { return (uint8_t)(30 + pct * 225 / 100); }  // never fully dark

void setup() {
  Serial.begin(115200);

  // T-Deck master power-enable - without this the panel/keyboard stay dark.
  pinMode(TDECK_POWERON, OUTPUT);
  digitalWrite(TDECK_POWERON, HIGH);
  delay(100);

  Wire.begin(TDECK_I2C_SDA, TDECK_I2C_SCL);

  display.init();
  // load saved settings (volume + brightness)
  g_prefs.begin("kuma", false);
  g_setVol = g_prefs.getUChar("vol", 22);
  g_setBright = g_prefs.getUChar("bright", 80);
  display.setBrightness(brightRaw(g_setBright));
  kuma_ui::begin(&display);
  battle::begin(&display);
  audio::begin();
  audio::setVolume(g_setVol);
  kuma_ui::splash();

  input::begin();
  kuma_api::begin();             // start Wi-Fi association (non-blocking)
  delay(1200);
  kuma_ui::drawHome(g_status);
}

static void enterScreen(Screen s) {
  g_screen = s;
  switch (s) {
    case Screen::Home:       kuma_ui::drawHome(g_status); break;
    case Screen::ModeSelect: kuma_ui::drawModeSelect(g_modeIndex, g_status.mode); break;
    case Screen::EventList:
      g_eventCount = kuma_api::fetchEvents(g_events, 8);
      kuma_ui::drawEventList(g_events, g_eventCount);
      break;
    case Screen::Settings:
      kuma_ui::drawSettings(g_setVol, g_setBright, g_setSel);
      break;
  }
}

void loop() {
  const uint32_t now = millis();

  // --- poll backend (Home screen refresh) --------------------------------
  if (now - g_lastStatusPoll >= KUMA_STATUS_POLL_MS) {
    g_lastStatusPoll = now;
    KumaStatus tmp;
    if (kuma_api::fetchStatus(tmp)) {
      g_status = tmp; g_statusFails = 0;          // good poll -> update
    } else if (++g_statusFails >= 3) {
      g_status.online = false;                    // only after 3 fails (~6s)
      g_status.bearState = BearState::Error;
    }                                             // else: keep last-good bear
    if (g_screen == Screen::Home) {
      battle::maybeStart(g_status);                // runs the on-device battle if threatened
      kuma_ui::drawHome(g_status);                 // (re)draw the monitoring face
    }
  }

  // --- input -------------------------------------------------------------
  InputEvent ev = input::poll();
  if (ev == InputEvent::None) { delay(15); return; }

  switch (g_screen) {
    case Screen::Home:
      if (ev == InputEvent::Select) enterScreen(Screen::ModeSelect);
      else if (ev == InputEvent::Right) enterScreen(Screen::EventList);
      else if (ev == InputEvent::Left) { g_setSel = 0; enterScreen(Screen::Settings); }
      break;

    case Screen::ModeSelect:
      if (ev == InputEvent::Up) {
        g_modeIndex = (g_modeIndex + 4) % 5;
        kuma_ui::drawModeSelect(g_modeIndex, g_status.mode);
      } else if (ev == InputEvent::Down) {
        g_modeIndex = (g_modeIndex + 1) % 5;
        kuma_ui::drawModeSelect(g_modeIndex, g_status.mode);
      } else if (ev == InputEvent::Select) {
        kuma_api::setMode(static_cast<KumaMode>(g_modeIndex));
        kuma_api::fetchStatus(g_status);
        enterScreen(Screen::Home);
      } else if (ev == InputEvent::Back || ev == InputEvent::Left) {
        enterScreen(Screen::Home);
      }
      break;

    case Screen::EventList:
      if (ev == InputEvent::Back || ev == InputEvent::Left)
        enterScreen(Screen::Home);
      break;

    case Screen::Settings: {
      int* val = (g_setSel == 0) ? &g_setVol : &g_setBright;
      if (ev == InputEvent::Up)        { g_setSel = (g_setSel + 1) % 2; }
      else if (ev == InputEvent::Down) { g_setSel = (g_setSel + 1) % 2; }
      else if (ev == InputEvent::Right){ *val = min(100, *val + 5); }
      else if (ev == InputEvent::Left) { *val = max(0,   *val - 5); }
      else if (ev == InputEvent::Back || ev == InputEvent::Select) {
        g_prefs.putUChar("vol", g_setVol);
        g_prefs.putUChar("bright", g_setBright);
        enterScreen(Screen::Home);
        break;
      }
      audio::setVolume(g_setVol);                 // apply live
      display.setBrightness(brightRaw(g_setBright));
      kuma_ui::drawSettings(g_setVol, g_setBright, g_setSel);
      break;
    }
  }
}
