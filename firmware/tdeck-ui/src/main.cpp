// KUMA Guard - LilyGo T-Deck UI client (flagship face).
//
// Boot: power-enable -> I2C -> display -> Wi-Fi -> poll the Pi backend and
// render the bear. Trackball/keyboard drive a small screen state machine.
//
//   Home        : status + bear. Click/Enter -> Mode select. Right -> Events,
//                 Left -> Settings, Up -> Networks, Down -> Terminal.
//   ModeSelect  : Up/Down choose, Click/Enter applies (POST /api/mode), Back.
//   EventList   : recent events from /api/events. Back -> Home.
//   Settings    : Up/Down row; L/R adjust sliders; click fires actions
//                 (Reboot/Power Off, click-to-confirm); Back saves -> Home.
#include <Arduino.h>
#include <Wire.h>
#include <WiFi.h>
#include <Preferences.h>
#include <esp_sleep.h>

#include "tdeck_pins.h"
#include "config.h"
#include "display.h"
#include "input.h"
#include "kuma_api_client.h"
#include "kuma_ui.h"
#include "kuma_battle.h"
#include "kuma_audio.h"
#include "kuma_terminal.h"
#include "kuma_rf.h"

static LGFX_TDeck display;
static KumaStatus g_status;
static KumaEvent  g_events[8];
static int        g_eventCount = 0;
static KumaNetwork g_nets[40];
static int        g_netCount = 0;
static int        g_netScroll = 0;

static Screen g_screen = Screen::Home;
static int    g_modeIndex = 1;             // default highlight: Foraging (manual modes 0..2)

// --- Attack menu state ---
static int     g_attackSel   = 0;   // 0=BROADCAST, 1=TARGETED in AttackMode
static int     g_broadcastSel = 0;  // 0..4 in BroadcastMenu
static String  g_targetBssid;       // BSSID string being entered in TargetEntry
static int     g_targetCh    = 6;   // channel being entered
static int     g_targetField = 0;   // 0=bssid, 1=channel
static uint32_t g_lastStatusPoll = 0;
static uint8_t  g_statusFails = 0;         // tolerate transient poll failures

static Preferences g_prefs;
static int g_setVol = 22;                  // %
static int g_setBright = 80;               // %
static int g_setSel = 0;                   // selected settings row (SettingsRow)
static int g_setConfirm = -1;              // action row awaiting click-to-confirm

static uint8_t brightRaw(int pct) { return (uint8_t)(30 + pct * 225 / 100); }  // never fully dark

// Assemble the live Settings view (Wi-Fi/IP, version) and render it. Strings are
// locals kept alive across the synchronous draw call.
static void drawSettingsScreen() {
  String ip   = (WiFi.status() == WL_CONNECTED) ? WiFi.localIP().toString()
                                                : String("offline");
  String ssid = WiFi.SSID();
  SettingsView v;
  v.vol = g_setVol; v.bright = g_setBright; v.sel = g_setSel; v.confirm = g_setConfirm;
  v.wifiSsid = ssid.c_str(); v.ip = ip.c_str();
  v.backendOnline = g_status.online;
  v.fwVersion = KUMA_FW_VERSION; v.backendVersion = g_status.version.c_str();
  kuma_ui::drawSettings(v);
}

static void saveSettings() {
  g_prefs.putUChar("vol", g_setVol);
  g_prefs.putUChar("bright", g_setBright);
}

// Real power-off on the T-Deck: cut the board power-enable rail and deep-sleep
// (no wake source -> stays off until reset / power button). Save first.
static void powerOff() {
  saveSettings();
  display.fillScreen(0x0000);
  display.setTextColor(0x07FF); display.setTextSize(2);
  display.setCursor(48, 108); display.print("Powering off...");
  delay(800);
  display.setBrightness(0);
  digitalWrite(TDECK_POWERON, LOW);   // drop the peripheral power rail
  esp_deep_sleep_start();             // minimal draw; wake on reset/power
}

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
  terminal::begin(&display);
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
    case Screen::Networks:
      g_netScroll = 0;
      g_netCount = kuma_api::fetchNetworks(g_nets, 40);
      kuma_ui::drawNetworks(g_nets, g_netCount, g_netCount, g_netScroll);
      break;
    case Screen::Settings:
      drawSettingsScreen();
      break;
    case Screen::AttackMode:
      kuma_ui::drawAttackMode(g_attackSel);
      break;
    case Screen::BroadcastMenu:
      kuma_ui::drawBroadcastMenu(g_broadcastSel);
      break;
    case Screen::TargetEntry:
      kuma_ui::drawTargetEntry(g_targetBssid, g_targetCh, g_targetField);
      break;
  }
}

void loop() {
  const uint32_t now = millis();

  kuma_api::reconnectIfDown();   // self-heal Wi-Fi if a deauth kicked us off

  // --- poll backend (Home screen refresh) --------------------------------
  if (now - g_lastStatusPoll >= KUMA_STATUS_POLL_MS) {
    g_lastStatusPoll = now;
    KumaStatus tmp;
    if (kuma_api::fetchStatus(tmp)) {
      // Toast when a new network appears between polls; guard s_lastNetCount
      // nonzero so the very first poll doesn't toast the whole backlog.
      static uint32_t s_lastNetCount = 0;
      if (s_lastNetCount && tmp.networkCount > s_lastNetCount)
        kuma_ui::toast(String("+1 EXP  new network (") + tmp.networkCount + ")");
      s_lastNetCount = tmp.networkCount;
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

  // --- idle/anim redraw: ~10fps so the idle bob and the offline walk cycle
  //     animate smoothly (drawHome is a cheap PSRAM-framebuffer blit) ---------
  static uint32_t g_lastBob = 0;
  if (g_screen == Screen::Home && now - g_lastBob >= 100) {
    g_lastBob = now;
    kuma_ui::drawHome(g_status);
  }

  // --- input -------------------------------------------------------------
  InputEvent ev = input::poll();
  // TargetEntry types via the keyboard (poll() returns None for plain keys, so
  // drain input::lastKey() here before the None early-return). Field 0 = BSSID
  // (hex + ':'), field 1 = channel (digits). Backspace edits the BSSID.
  if (g_screen == Screen::TargetEntry) {
    char c = input::lastKey();
    if (c) {
      if (g_targetField == 0) {
        if ((c == 8 || c == 127) && g_targetBssid.length())
          g_targetBssid.remove(g_targetBssid.length() - 1);
        else if (((c >= '0' && c <= '9') || (c >= 'a' && c <= 'f') ||
                  (c >= 'A' && c <= 'F') || c == ':') && g_targetBssid.length() < 17)
          g_targetBssid += c;
      } else {                                   // channel field: digits
        if (c >= '0' && c <= '9') {
          int v = g_targetCh * 10 + (c - '0');
          g_targetCh = (v >= 1 && v <= 14) ? v : (c - '0');   // clamp/restart at 1-14
        } else if (c == 8 || c == 127) {
          g_targetCh = 0;
        }
      }
      kuma_ui::drawTargetEntry(g_targetBssid, g_targetCh, g_targetField);
    }
  }
  if (ev == InputEvent::None) { delay(15); return; }

  switch (g_screen) {
    case Screen::Home:
      if (ev == InputEvent::Select) {
        if (g_status.kuroshunaArmed) {
          g_attackSel = 0;
          enterScreen(Screen::AttackMode);
        } else {
          enterScreen(Screen::ModeSelect);
        }
      }
      else if (ev == InputEvent::Right) enterScreen(Screen::EventList);
      else if (ev == InputEvent::Left) { g_setSel = 0; g_setConfirm = -1; enterScreen(Screen::Settings); }
      else if (ev == InputEvent::Down) { terminal::run(); enterScreen(Screen::Home); }
      else if (ev == InputEvent::Up) enterScreen(Screen::Networks);
      break;

    case Screen::ModeSelect:
      // Only the 3 manual modes (Hibernate/Foraging/Honey = enum 0..2) are here.
      if (ev == InputEvent::Up) {
        g_modeIndex = (g_modeIndex + 2) % 3;
        kuma_ui::drawModeSelect(g_modeIndex, g_status.mode);
      } else if (ev == InputEvent::Down) {
        g_modeIndex = (g_modeIndex + 1) % 3;
        kuma_ui::drawModeSelect(g_modeIndex, g_status.mode);
      } else if (ev == InputEvent::Select) {
        kuma_api::setMode(static_cast<KumaMode>(g_modeIndex));   // switch mode
        kuma_api::sendAction("clear_mock_events", true);         // reset KUMA to calm
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

    case Screen::Networks:
      if (ev == InputEvent::Down && g_netScroll + 9 < g_netCount) {
        g_netScroll++; kuma_ui::drawNetworks(g_nets, g_netCount, g_netCount, g_netScroll);
      } else if (ev == InputEvent::Up && g_netScroll > 0) {
        g_netScroll--; kuma_ui::drawNetworks(g_nets, g_netCount, g_netCount, g_netScroll);
      } else if (ev == InputEvent::Back || ev == InputEvent::Left) {
        enterScreen(Screen::Home);
      }
      break;

    case Screen::AttackMode:
      if (ev == InputEvent::Up || ev == InputEvent::Down) {
        g_attackSel = 1 - g_attackSel;   // toggle 0<->1
        kuma_ui::drawAttackMode(g_attackSel);
      } else if (ev == InputEvent::Select) {
        if (g_attackSel == 0) {
          g_broadcastSel = 0;
          enterScreen(Screen::BroadcastMenu);
        } else {
          g_targetBssid = "";
          g_targetCh = 6;
          g_targetField = 0;
          enterScreen(Screen::TargetEntry);
        }
      } else if (ev == InputEvent::Back || ev == InputEvent::Left) {
        enterScreen(Screen::Home);
      }
      break;

    case Screen::BroadcastMenu: {
      static const char* ATTACK_NAMES[5] = {"gemini","deauth","aoi","rengoku","bankai"};
      static const char* ATTACK_LABELS[5]= {"GEMINI","DEAUTH","AOI","RENGOKU","BANKAI"};
      if (ev == InputEvent::Up) {
        g_broadcastSel = (g_broadcastSel + 4) % 5;
        kuma_ui::drawBroadcastMenu(g_broadcastSel);
      } else if (ev == InputEvent::Down) {
        g_broadcastSel = (g_broadcastSel + 1) % 5;
        kuma_ui::drawBroadcastMenu(g_broadcastSel);
      } else if (ev == InputEvent::Select) {
        const char* nm = ATTACK_NAMES[g_broadcastSel];
        const char* lb = ATTACK_LABELS[g_broadcastSel];
        bool ok = kuma_api::broadcastAttack(String(nm));
        if (ok) {
          kuma_ui::toast(String("blasting ") + lb + "...", 3000);
        } else {
          kuma_ui::toast("refused - broadcast not armed", 3000);
        }
        enterScreen(Screen::Home);
      } else if (ev == InputEvent::Back || ev == InputEvent::Left) {
        g_attackSel = 0;
        enterScreen(Screen::AttackMode);
      }
      break;
    }

    case Screen::TargetEntry: {
      // Keyboard input: characters accumulate into bssid or channel field.
      // Select on field 0 -> move to field 1; Select on field 1 -> fire.
      // Back/Left -> cancel back to AttackMode.
      if (ev == InputEvent::Back || ev == InputEvent::Left) {
        enterScreen(Screen::AttackMode);
        break;
      }
      if (ev == InputEvent::Up || ev == InputEvent::Down) {
        g_targetField = 1 - g_targetField;
        kuma_ui::drawTargetEntry(g_targetBssid, g_targetCh, g_targetField);
        break;
      }
      if (ev == InputEvent::Select) {
        if (g_targetField == 0) {
          // advance to channel field
          g_targetField = 1;
          kuma_ui::drawTargetEntry(g_targetBssid, g_targetCh, g_targetField);
        } else {
          // fire: authorize then deauth
          if (g_targetBssid.length() < 17) {
            kuma_ui::toast("bad BSSID", 2000);
            break;
          }
          uint8_t bssid[6], client[6];
          if (!kuma_rf::parseMac(g_targetBssid, bssid)) {
            kuma_ui::toast("bad BSSID format", 2000);
            break;
          }
          for (int i = 0; i < 6; i++) client[i] = 0xFF;  // broadcast deauth
          bool auth = kuma_api::authorizeAction(g_targetBssid, "deauth");
          if (!auth) {
            kuma_ui::toast("refused by gate", 2500);
            enterScreen(Screen::AttackMode);
            break;
          }
          int sent = kuma_rf::deauth(bssid, client, (uint8_t)g_targetCh, 64);
          kuma_ui::toast(String("deauth ") + sent + " frames -> " + g_targetBssid, 3000);
          enterScreen(Screen::Home);
        }
        break;
      }
      // (typed characters are accumulated at the top of loop() via input::lastKey())
      break;
    }

    case Screen::Settings: {
      bool slider = (g_setSel == SET_VOLUME || g_setSel == SET_BRIGHT);
      bool action = (g_setSel == SET_REBOOT || g_setSel == SET_POWEROFF);

      if (ev == InputEvent::Up)   { g_setSel = (g_setSel + SET_COUNT - 1) % SET_COUNT; g_setConfirm = -1; }
      else if (ev == InputEvent::Down) { g_setSel = (g_setSel + 1) % SET_COUNT; g_setConfirm = -1; }
      else if ((ev == InputEvent::Left || ev == InputEvent::Right) && slider) {
        int* val = (g_setSel == SET_VOLUME) ? &g_setVol : &g_setBright;
        *val = (ev == InputEvent::Right) ? min(100, *val + 5) : max(0, *val - 5);
        audio::setVolume(g_setVol);                 // apply live
        display.setBrightness(brightRaw(g_setBright));
        g_setConfirm = -1;
      }
      else if (ev == InputEvent::Left) {            // non-slider row: leave + save
        saveSettings(); enterScreen(Screen::Home); break;
      }
      else if (ev == InputEvent::Select && action) {
        if (g_setConfirm == g_setSel) {             // second click = do it
          if (g_setSel == SET_REBOOT) { saveSettings(); ESP.restart(); }
          else                        { powerOff(); }   // never returns
        } else {
          g_setConfirm = g_setSel;                  // arm confirm
        }
      }
      else if (ev == InputEvent::Back) {            // save + home from anywhere
        saveSettings(); enterScreen(Screen::Home); break;
      }
      drawSettingsScreen();
      break;
    }
  }
}
