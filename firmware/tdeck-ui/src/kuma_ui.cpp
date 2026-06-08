// KUMA Guard T-Deck - UI implementation (LovyanGFX).
#include "kuma_ui.h"
#include "bear_sprites_data.h"
#include "kuma_logo_data.h"
#include "kuma_bg_data.h"

namespace {
LGFX_TDeck* D = nullptr;
lgfx::LGFX_Sprite fb;       // off-screen framebuffer (PSRAM) -> push once = no flicker
lgfx::LGFX_Sprite bgDash;   // night-watch background, decoded once + blitted each frame
bool fbReady = false;
bool bgReady = false;

// RGB565 palette
constexpr uint16_t BG     = 0x0000;  // black
constexpr uint16_t FG     = 0xFFFF;  // white
constexpr uint16_t CYAN   = 0x07FF;  // sentinel
constexpr uint16_t GREEN  = 0x07E0;  // safe / low
constexpr uint16_t AMBER  = 0xFD20;  // honey / medium
constexpr uint16_t RED    = 0xF800;  // high / critical
constexpr uint16_t GREY   = 0x7BEF;  // offline
constexpr uint16_t FUR    = 0x8C51;  // bear brown
constexpr uint16_t FURDK  = 0x5AC9;  // darker brown
constexpr uint16_t SNOUT  = 0xC618;  // light grey

const char* MODE_LABELS[5] = {"Hibernate", "Foraging", "Honey",
                              "Sentinel", "Apex"};

uint16_t threatColor(const String& t) {
  if (t == "high" || t == "critical") return RED;
  if (t == "medium") return AMBER;
  return GREEN;
}

void hms(uint32_t s, char* buf) {
  sprintf(buf, "%02u:%02u:%02u", s / 3600, (s % 3600) / 60, s % 60);
}

// bear_state -> embedded sprite index (-1 = use algorithmic fallback)
int bearSpriteIndex(BearState st) {
  switch (st) {
    case BearState::Sleeping:   return 0;  // hibernating
    case BearState::Foraging:   return 1;
    case BearState::Suspicious: return 2;  // sentinel
    case BearState::HoneyTrap:  return 3;  // honey
    case BearState::ApexReady:  return 4;  // apex
    case BearState::Alert:      return 5;
    case BearState::Logging:    return 6;  // investigating
    default:                    return -1; // Error / offline -> fallback
  }
}
}  // namespace

namespace kuma_ui {

void begin(LGFX_TDeck* d) {
  D = d;
  D->setRotation(1);            // landscape 320x240
  D->fillScreen(BG);
  D->setTextWrap(false);
  // off-screen framebuffer in PSRAM: render the whole screen, blit once (no flicker)
  fb.setColorDepth(16);
  fb.setPsram(true);
  fbReady = fb.createSprite(320, 240);
  if (fbReady) fb.setTextWrap(false);
  // Decode the dashboard background once; blitting the sprite each bob tick is
  // far cheaper than re-decoding the PNG ~4x/second.
  bgDash.setColorDepth(16);
  bgDash.setPsram(true);
  if (bgDash.createSprite(320, 240)) {
    bgReady = bgDash.drawPng(KUMA_BG_DASH, KUMA_BG_DASH_LEN, 0, 0);
    if (!bgReady) bgDash.deleteSprite();
  }
}

void splash() {
  D->fillScreen(BG);
  D->setTextColor(CYAN, BG);
  D->setTextSize(3);
  D->setCursor(70, 80);
  D->print("KUMA");
  D->setTextSize(2);
  D->setTextColor(GREY, BG);
  D->setCursor(70, 120);
  D->print("Guard");
  drawBear(D, BearState::Sleeping, 250, 110, 40);
}

// --- the bear -----------------------------------------------------------
void drawBear(lgfx::LovyanGFX* g, BearState st, int cx, int cy, int r) {
  uint16_t tint = FUR;
  switch (st) {
    case BearState::Alert:      tint = RED;   break;
    case BearState::Suspicious: tint = CYAN;  break;
    case BearState::HoneyTrap:  tint = AMBER; break;
    case BearState::Foraging:   tint = GREEN; break;
    case BearState::Error:      tint = GREY;  break;
    default:                    tint = FUR;   break;
  }
  // ears
  int er = r / 3;
  g->fillCircle(cx - r + er, cy - r + er, er, FURDK);
  g->fillCircle(cx + r - er, cy - r + er, er, FURDK);
  // head
  g->fillCircle(cx, cy, r, tint);
  // snout
  g->fillCircle(cx, cy + r / 4, r / 2, SNOUT);
  // nose
  g->fillCircle(cx, cy + r / 6, r / 8, BG);

  // eyes by mood
  int ex = r / 2, ey = cy - r / 4, eye = r / 8;
  switch (st) {
    case BearState::Sleeping:                 // closed (lines)
      g->drawFastHLine(cx - ex - eye, ey, 2 * eye, BG);
      g->drawFastHLine(cx + ex - eye, ey, 2 * eye, BG);
      break;
    case BearState::Alert:                     // wide
      g->fillCircle(cx - ex, ey, eye + 1, BG);
      g->fillCircle(cx + ex, ey, eye + 1, BG);
      g->fillCircle(cx - ex, ey, 2, RED);
      g->fillCircle(cx + ex, ey, 2, RED);
      break;
    case BearState::Suspicious:                // half-lidded
      g->fillCircle(cx - ex, ey, eye, BG);
      g->fillCircle(cx + ex, ey, eye, BG);
      g->fillRect(cx - ex - eye, ey - eye, 2 * eye, eye, tint);
      g->fillRect(cx + ex - eye, ey - eye, 2 * eye, eye, tint);
      break;
    default:                                   // normal dots
      g->fillCircle(cx - ex, ey, eye, BG);
      g->fillCircle(cx + ex, ey, eye, BG);
      break;
  }
}

// --- screens ------------------------------------------------------------
void drawHome(const KumaStatus& s) {
  // Draw the whole dashboard into the off-screen framebuffer, then blit once.
  lgfx::LovyanGFX* g = fbReady ? static_cast<lgfx::LovyanGFX*>(&fb)
                               : static_cast<lgfx::LovyanGFX*>(D);
  // night-watch background (text drawn transparent so the scene shows through)
  if (fbReady && bgReady)      bgDash.pushSprite(&fb, 0, 0);
  else if (!fbReady && bgReady) g->drawPng(KUMA_BG_DASH, KUMA_BG_DASH_LEN, 0, 0);
  else                          g->fillScreen(BG);

  // --- top bar: クマ wordmark + level, online dot ------------------------
  g->drawPng(KUMA_LOGO, sizeof KUMA_LOGO, 8, 3);   // katakana wordmark
  g->setTextSize(1); g->setTextColor(GREEN);
  g->setCursor(8 + KUMA_LOGO_W + 8, 11);
  g->printf("Lv %u", s.level);
  g->fillCircle(244, 12, 4, s.online ? GREEN : RED);
  g->setTextColor(s.online ? GREEN : GREY); g->setCursor(254, 9);
  g->print(s.online ? "ONLINE" : "OFFLINE");
  g->drawFastHLine(0, 26, 320, 0x2945);

  // --- bear, centered (real sprite, algorithmic fallback) ----------------
  BearState bs = s.online ? s.bearState : BearState::Error;
  static const int BOB[4] = {0, -3, -4, -3};
  int bob = BOB[(millis() / 240) % 4];           // gentle idle bob, like the web
  int si = bearSpriteIndex(bs);
  if (si >= 0) {
    const BearSprite& sp = BEAR_SPRITES[si];
    if (!g->drawPng(sp.data, sp.len, 160 - sp.w / 2, 112 - sp.h / 2 + bob))
      drawBear(g, bs, 160, 112 + bob, 58);   // decode hiccup -> algorithmic fallback
  } else {
    drawBear(g, bs, 160, 112 + bob, 58);
  }

  // (no mood/threat text - the bear's state conveys what's going on)

  // --- stat bar (no threat readout) --------------------------------------
  g->drawFastHLine(0, 206, 320, 0x2945);
  const int   cxs[4]    = {40, 120, 200, 280};
  const char* labels[4] = {"UPTIME", "EVENTS", "NETWORKS", "SENSOR"};
  char up[16]; hms(s.uptimeSeconds, up);
  char ev[8]; snprintf(ev, sizeof ev, "%u", s.eventsLast10m);
  char nw[8]; snprintf(nw, sizeof nw, "%u", s.networkCount);
  const char* vals[4] = {up, ev, nw, s.online ? s.wifiInterface.c_str() : "--"};
  uint16_t vcol[4] = {FG, FG, CYAN, FG};
  g->setTextSize(1);
  for (int i = 0; i < 4; ++i) {
    g->setTextColor(GREY);
    g->setCursor(cxs[i] - (int)strlen(labels[i]) * 3, 212); g->print(labels[i]);
    g->setTextColor(vcol[i]);
    g->setCursor(cxs[i] - (int)strlen(vals[i]) * 3, 226); g->print(vals[i]);
  }

  if (fbReady) fb.pushSprite(D, 0, 0);
}

void drawModeSelect(int selectedIndex, KumaMode current) {
  D->fillScreen(BG);
  D->setTextSize(2);
  D->setTextColor(CYAN, BG);
  D->setCursor(10, 10);
  D->print("Select Mode");
  for (int i = 0; i < 5; ++i) {
    int yy = 50 + i * 34;
    bool sel = (i == selectedIndex);
    if (sel) D->fillRoundRect(6, yy - 4, 308, 30, 4, 0x18E3);
    D->setTextColor(sel ? RED : GREEN, sel ? 0x18E3 : BG);
    D->setCursor(16, yy);
    bool isCur = ((int)current == i);
    D->printf("%s %s%s", sel ? ">" : " ", MODE_LABELS[i], isCur ? "  *" : "");
  }
}

void drawEventList(const KumaEvent* ev, int n) {
  D->fillScreen(BG);
  D->setTextSize(2);
  D->setTextColor(CYAN, BG);
  D->setCursor(10, 10);
  D->print("Recent Events");
  if (n == 0) {
    D->setTextColor(GREY, BG);
    D->setCursor(10, 50);
    D->print("(none)");
    return;
  }
  for (int i = 0; i < n && i < 6; ++i) {
    int yy = 48 + i * 30;
    uint16_t c = ev[i].severity == "high" || ev[i].severity == "critical" ? RED
               : ev[i].severity == "medium" ? AMBER : GREEN;
    D->setTextColor(c, BG);
    D->setCursor(10, yy);
    String sev = ev[i].severity; sev.toUpperCase();
    D->printf("[%s] %s", sev.substring(0, 3).c_str(), ev[i].eventType.c_str());
  }
}

void drawSettings(const SettingsView& v) {
  lgfx::LovyanGFX* g = fbReady ? static_cast<lgfx::LovyanGFX*>(&fb)
                               : static_cast<lgfx::LovyanGFX*>(D);
  g->fillScreen(BG);
  g->setFont(&fonts::Font0);
  g->setTextSize(2); g->setTextColor(CYAN, BG); g->setCursor(10, 8); g->print("SETTINGS");
  g->drawFastHLine(0, 32, 320, 0x2945);

  const char* labels[SET_COUNT] = {
    "Volume", "Brightness", "Wi-Fi / IP", "Firmware", "Reboot", "Power Off"};
  const int top = 42, rowH = 28;

  for (int i = 0; i < SET_COUNT; ++i) {
    int y = top + i * rowH;
    bool s = (i == v.sel);
    uint16_t rowBg = s ? 0x10A2 : BG;
    if (s) { g->fillRect(6, y, 308, rowH - 4, rowBg); g->drawRect(6, y, 308, rowH - 4, CYAN); }
    g->setTextSize(1); g->setTextColor(s ? CYAN : FG, rowBg);
    g->setCursor(14, y + 7); g->print(labels[i]);

    const int cx = 140;   // where the right-hand value/control starts
    switch (i) {
      case SET_VOLUME:
      case SET_BRIGHT: {
        int val = (i == SET_VOLUME) ? v.vol : v.bright;
        int bx = cx, by = y + 6, bw = 120, bh = 11;
        g->drawRect(bx, by, bw, bh, GREY);
        g->fillRect(bx + 1, by + 1, (bw - 2) * val / 100, bh - 2, s ? CYAN : GREEN);
        g->setTextColor(FG, rowBg); g->setCursor(bx + bw + 8, y + 7); g->printf("%d%%", val);
        break;
      }
      case SET_WIFI: {
        g->setTextColor(v.backendOnline ? GREEN : AMBER, rowBg);
        g->setCursor(cx, y + 7);
        if (v.wifiSsid && v.wifiSsid[0]) g->printf("%.12s %s", v.wifiSsid, v.ip);
        else                             g->print(v.ip);
        break;
      }
      case SET_ABOUT: {
        g->setTextColor(GREY, rowBg); g->setCursor(cx, y + 7);
        if (v.backendVersion && v.backendVersion[0])
          g->printf("v%s  api %s", v.fwVersion, v.backendVersion);
        else
          g->printf("v%s", v.fwVersion);
        break;
      }
      case SET_REBOOT:
      case SET_POWEROFF: {
        if (v.confirm == i) {
          g->setTextColor(RED, rowBg); g->setCursor(cx, y + 7); g->print("click to confirm");
        } else {
          g->setTextColor(GREY, rowBg); g->setCursor(cx, y + 7); g->print("click");
        }
        break;
      }
    }
  }

  g->setTextColor(GREY, BG); g->setCursor(10, 224);
  g->print("up/dn row  L/R adjust  click action  back save");
  if (fbReady) fb.pushSprite(D, 0, 0);
}

void drawNetworks(const KumaNetwork* nv, int n, int total, int scroll) {
  lgfx::LovyanGFX* g = fbReady ? static_cast<lgfx::LovyanGFX*>(&fb)
                               : static_cast<lgfx::LovyanGFX*>(D);
  g->fillScreen(BG);
  g->setFont(&fonts::Font0); g->setTextSize(1);
  g->setTextColor(CYAN, BG); g->setCursor(8, 6); g->printf("NETWORKS  %d observed", total);
  g->drawFastHLine(0, 18, 320, 0x2945);
  const int rowH = 22, top = 22, visible = 9;
  if (n == 0) { g->setTextColor(GREY, BG); g->setCursor(8, 40); g->print("(none mapped yet)"); }
  for (int i = 0; i < visible; ++i) {
    int idx = scroll + i; if (idx >= n) break;
    const KumaNetwork& w = nv[idx];
    int y = top + i * rowH;
    String ss = w.ssid; if (ss.length() > 30) ss = ss.substring(0, 30);
    g->setTextColor(FG, BG); g->setCursor(6, y); g->print(ss);
    uint16_t rc = w.rssi > -60 ? GREEN : (w.rssi > -75 ? AMBER : RED);
    g->setTextColor(rc, BG); g->setCursor(264, y); g->printf("%ddBm", w.rssi);
    g->setTextColor(GREY, BG); g->setCursor(6, y + 9);
    g->printf("%s  ch%d %s  x%d", w.bssid.c_str(), w.channel, w.security.c_str(), w.timesSeen);
  }
  g->setTextColor(GREY, BG); g->setCursor(6, 230);
  int lo = n ? scroll + 1 : 0, hi = min(scroll + visible, n);
  g->printf("up/down scroll  back home   [%d-%d/%d]", lo, hi, n);
  if (fbReady) fb.pushSprite(D, 0, 0);
}

}  // namespace kuma_ui
