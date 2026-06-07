// KUMA Guard T-Deck - UI implementation (LovyanGFX).
#include "kuma_ui.h"
#include "bear_sprites_data.h"
#include "kuma_logo_data.h"

namespace {
LGFX_TDeck* D = nullptr;
lgfx::LGFX_Sprite fb;       // off-screen framebuffer (PSRAM) -> push once = no flicker
bool fbReady = false;

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
  g->fillScreen(BG);

  // --- top bar: クマ wordmark + level, online dot ------------------------
  g->drawPng(KUMA_LOGO, sizeof KUMA_LOGO, 8, 3);   // katakana wordmark
  g->setTextSize(1); g->setTextColor(GREEN, BG);
  g->setCursor(8 + KUMA_LOGO_W + 8, 11);
  g->printf("Lv %u", s.level);
  g->fillCircle(244, 12, 4, s.online ? GREEN : RED);
  g->setTextColor(s.online ? GREEN : GREY, BG); g->setCursor(254, 9);
  g->print(s.online ? "ONLINE" : "OFFLINE");
  g->drawFastHLine(0, 26, 320, 0x2945);

  // --- bear, centered (real sprite, algorithmic fallback) ----------------
  BearState bs = s.online ? s.bearState : BearState::Error;
  int si = bearSpriteIndex(bs);
  if (si >= 0) {
    const BearSprite& sp = BEAR_SPRITES[si];
    if (!g->drawPng(sp.data, sp.len, 160 - sp.w / 2, 112 - sp.h / 2))
      drawBear(g, bs, 160, 112, 58);   // decode hiccup -> algorithmic fallback
  } else {
    drawBear(g, bs, 160, 112, 58);
  }

  // --- status / say line (centered) --------------------------------------
  String say = !s.online ? "backend offline"
             : (s.eventsLast10m > 0 ? s.threatLevel : String("all quiet"));
  say.toUpperCase();
  g->setTextSize(2);
  g->setTextColor(s.online ? threatColor(s.threatLevel) : GREY, BG);
  g->setCursor(160 - (int)say.length() * 6, 178); g->print(say.c_str());

  // --- stat bar ----------------------------------------------------------
  g->drawFastHLine(0, 206, 320, 0x2945);
  const int   cxs[5]    = {32, 96, 160, 224, 288};
  const char* labels[5] = {"THREAT", "UPTIME", "EVENTS", "NETWRK", "SENSOR"};
  char up[16]; hms(s.uptimeSeconds, up);
  char ev[8]; snprintf(ev, sizeof ev, "%u", s.eventsLast10m);
  char nw[8]; snprintf(nw, sizeof nw, "%u", s.networkCount);
  String thr = s.online ? s.threatLevel : String("--"); thr.toUpperCase();
  const char* vals[5] = {thr.c_str(), up, ev, nw,
                         s.online ? s.wifiInterface.c_str() : "--"};
  uint16_t vcol[5] = {threatColor(s.threatLevel), FG, FG, CYAN, FG};
  g->setTextSize(1);
  for (int i = 0; i < 5; ++i) {
    g->setTextColor(GREY, BG);
    g->setCursor(cxs[i] - (int)strlen(labels[i]) * 3, 212); g->print(labels[i]);
    g->setTextColor(vcol[i], BG);
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

void drawSettings(int volPct, int brightPct, int sel) {
  lgfx::LovyanGFX* g = fbReady ? static_cast<lgfx::LovyanGFX*>(&fb)
                               : static_cast<lgfx::LovyanGFX*>(D);
  g->fillScreen(BG);
  g->setFont(&fonts::Font0);
  g->setTextSize(2); g->setTextColor(CYAN, BG); g->setCursor(10, 10); g->print("SETTINGS");

  const char* labels[2] = {"Volume", "Brightness"};
  const int   vals[2]   = {volPct, brightPct};
  for (int i = 0; i < 2; ++i) {
    int y = 70 + i * 60;
    bool s = (i == sel);
    if (s) { g->fillRect(6, y - 8, 308, 46, 0x10A2); g->drawRect(6, y - 8, 308, 46, CYAN); }
    g->setTextSize(2); g->setTextColor(s ? CYAN : FG, s ? 0x10A2 : BG);
    g->setCursor(16, y - 2); g->print(labels[i]);
    // bar
    int bx = 16, by = y + 22, bw = 240;
    g->drawRect(bx, by, bw, 12, GREY);
    g->fillRect(bx + 1, by + 1, (bw - 2) * vals[i] / 100, 10, s ? CYAN : GREEN);
    g->setTextSize(1); g->setTextColor(FG, s ? 0x10A2 : BG);
    g->setCursor(bx + bw + 12, by + 2); g->printf("%d%%", vals[i]);
  }
  g->setTextSize(1); g->setTextColor(GREY, BG); g->setCursor(10, 224);
  g->print("up/down: row   left/right: adjust   back: save");
  if (fbReady) fb.pushSprite(D, 0, 0);
}

}  // namespace kuma_ui
