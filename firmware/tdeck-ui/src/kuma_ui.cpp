// KUMA Guard T-Deck - UI implementation (LovyanGFX).
#include "kuma_ui.h"
#include "bear_sprites_data.h"
#include "evo_sprites_data.h"       // evo1..evo5 packs; reuses BearSprite, include AFTER base
#include "shuna_sprites_data.h"     // SHUNA character pack + シュナ wordmark; AFTER base
#include "offline_sprites_data.h"   // reuses BearSprite; include AFTER bear sprites
#include "kuma_logo_data.h"
#include "kuma_bg_data.h"
#include "kuroshuna_sprites_data.h"

namespace {
LGFX_TDeck* D = nullptr;
lgfx::LGFX_Sprite fb;       // off-screen framebuffer (PSRAM) -> push once = no flicker
lgfx::LGFX_Sprite bgDash;   // home background, decoded on change + blitted each frame
bool fbReady = false;
bool bgReady = false;
String loadedBg = "";       // which home background bgDash currently holds

// Map a backend background name to its baked PNG. backg1/backg2 are the two
// selectable home backgrounds; backgFLAG is the creator/showcase background.
static void bgDataFor(const String& name, const uint8_t*& data, size_t& len) {
  if (name == "backg2")        { data = KUMA_BG_DASH2; len = KUMA_BG_DASH2_LEN; }
  else if (name == "backgFLAG"){ data = KUMA_BG_FLAG;  len = KUMA_BG_FLAG_LEN;  }
  else                         { data = KUMA_BG_DASH1; len = KUMA_BG_DASH1_LEN; }
}

// (Re)decode the home background into bgDash only when the requested one
// changes - decoding a PNG every frame would be far too slow.
static void ensureHomeBg(const String& name) {
  if (name == loadedBg && bgReady) return;
  const uint8_t* data; size_t len;
  bgDataFor(name, data, len);
  if (!bgDash.width() && !bgDash.createSprite(320, 240)) { bgReady = false; return; }
  bgReady = bgDash.drawPng(data, len, 0, 0);
  loadedBg = bgReady ? name : "";
}

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

// Calm face by operator-chosen mode. Sentinel/Apex are never chosen manually -
// they only surface as threat faces (bearSpriteIndex) when an attack hits.
int modeSpriteIndex(KumaMode m) {
  switch (m) {
    case KumaMode::Hibernate: return 0;  // sleeping
    case KumaMode::Foraging:  return 1;  // foraging
    case KumaMode::Honey:     return 3;  // honey
    case KumaMode::Sentinel:  return 2;  // (auto) sentinel
    case KumaMode::Apex:      return 4;  // (auto) apex
    default:                  return 1;  // foraging
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
  ensureHomeBg("backg1");   // default home background until /status says otherwise
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
  // Pick the home background the backend selected (creator unit -> backgFLAG).
  // Only re-decodes when it actually changes.
  ensureHomeBg(s.online ? s.background : String("backg1"));
  // home background (text drawn transparent so the scene shows through)
  if (fbReady && bgReady) {
    bgDash.pushSprite(&fb, 0, 0);
  } else if (!fbReady && bgReady) {
    const uint8_t* data; size_t len; bgDataFor(loadedBg, data, len);
    g->drawPng(data, len, 0, 0);
  } else {
    g->fillScreen(BG);
  }

  // HUD legibility: semi-opaque dark bands behind the top status bar and the
  // bottom stat strip so the text stays readable over the bright cyber-space
  // background. Alpha-blend on the framebuffer; opaque fallback if no PSRAM fb.
  if (fbReady) {
    g->fillRectAlpha(0,   0, 320, 27, 0xCC, 0x000000);
    g->fillRectAlpha(0, 205, 320, 35, 0xCC, 0x000000);
  } else {
    g->fillRect(0,   0, 320, 27, BG);
    g->fillRect(0, 205, 320, 35, BG);
  }

  // --- top bar: クロシュナ/シュナ/クマ wordmark + level, online dot ------
  bool kuro  = s.kuroshunaArmed;
  bool shuna = (s.character == "shuna");
  const uint16_t KURO_ACCENT = 0x901F;   // purple-magenta (RGB565)
  uint16_t accent = kuro ? KURO_ACCENT : 0x2945;
  uint16_t logoW = kuro ? KUROSHUNA_LOGO_W : (shuna ? SHUNA_LOGO_W : KUMA_LOGO_W);
  if (kuro)        g->drawPng(KUROSHUNA_LOGO, sizeof KUROSHUNA_LOGO, 8, 3);
  else if (shuna)  g->drawPng(SHUNA_LOGO, sizeof SHUNA_LOGO, 8, 3);
  else             g->drawPng(KUMA_LOGO, sizeof KUMA_LOGO, 8, 3);
  g->setTextSize(1); g->setTextColor(kuro ? KURO_ACCENT : GREEN);
  g->setCursor(8 + logoW + 8, 11);
  g->printf("Lv %u", s.level);
  g->fillCircle(244, 12, 4, s.online ? (kuro ? RED : GREEN) : RED);
  g->setTextColor(s.online ? (kuro ? RED : GREEN) : RED); g->setCursor(254, 9);
  g->print(s.online ? "ONLINE" : "OFFLINE");
  g->drawFastHLine(0, 26, 320, accent);

  // --- bear, centered + scaled up to fill the face -----------------------
  static const int BOB[4] = {0, -3, -4, -3};
  int bob = BOB[(millis() / 240) % 4];           // gentle idle bob, like the web
  const int   DISP_H = 172;                        // target on-screen sprite height
  const int   CY = 118;                           // vertical center between the HUD bands
  // SC is per-sprite: 128px bear packs -> ~1.34x (unchanged look), 192px Shuna
  // -> ~0.90x clean downscale, so the detailed art stays crisp (no double resample).
  if (!s.online) {
    // OFFLINE: Kuma paces around hunting for a signal - a 6-frame loop
    // (idle/check/no-link/retry/frustrated) plus a slow horizontal walk.
    int f = (millis() / 5000) % OFFLINE_SPRITE_COUNT;  // hold each state 5s
    uint32_t t = millis() % 6000;                       // slow 6s walk cycle
    int pace = (t < 3000) ? (int)t : 6000 - (int)t;     // 0..3000..0
    int cx = 115 + pace * 90 / 3000;                    // drift x=115..205 gently
    const BearSprite& sp = OFFLINE_SPRITES[f];
    float SC = (float)DISP_H / sp.h;
    int dw = (int)(sp.w * SC), dh = (int)(sp.h * SC);
    if (!g->drawPng(sp.data, sp.len, cx - dw / 2, CY - dh / 2 + bob, 0, 0, 0, 0, SC, SC))
      drawBear(g, BearState::Error, cx, CY + bob, 72);   // decode hiccup fallback
  } else {
    BearState bs = s.bearState;
    // Calm states reflect the chosen mode; threat states use the attack face.
    bool calm = (bs == BearState::Sleeping || bs == BearState::Foraging
                 || bs == BearState::HoneyTrap);
    int si = calm ? modeSpriteIndex(s.mode) : bearSpriteIndex(bs);
    // Kuroshuna armed: one pose for all states. Shuna overrides form packs otherwise.
    const BearSprite* pack = shuna ? SHUNA_SPRITES : evoPackFor(s.spriteSet.c_str());
    if (!pack) pack = BEAR_SPRITES;
    if (kuro) {
      const BearSprite& sp = KUROSHUNA_APEX;
      float SC = (float)DISP_H / sp.h;
      int dw = (int)(sp.w * SC), dh = (int)(sp.h * SC);
      if (!g->drawPng(sp.data, sp.len, 160 - dw / 2, CY - dh / 2 + bob, 0, 0, 0, 0, SC, SC))
        drawBear(g, bs, 160, CY + bob, 78);
    } else if (si >= 0) {
      const BearSprite& sp = pack[si];
      float SC = (float)DISP_H / sp.h;
      int dw = (int)(sp.w * SC), dh = (int)(sp.h * SC);
      if (!g->drawPng(sp.data, sp.len, 160 - dw / 2, CY - dh / 2 + bob, 0, 0, 0, 0, SC, SC))
        drawBear(g, bs, 160, CY + bob, 78);   // decode hiccup -> algorithmic fallback
    } else {
      drawBear(g, bs, 160, CY + bob, 78);
    }
  }

  // (no mood/threat text - the bear's state conveys what's going on)

  // --- stat bar (no threat readout) --------------------------------------
  g->drawFastHLine(0, 206, 320, accent);
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
  // Only the operator-chosen modes are selectable. Sentinel + Apex are
  // automatic - they engage on their own when an attack is detected.
  for (int i = 0; i < 3; ++i) {
    int yy = 56 + i * 40;
    bool sel = (i == selectedIndex);
    if (sel) D->fillRoundRect(6, yy - 6, 308, 34, 4, 0x18E3);
    D->setTextColor(sel ? RED : GREEN, sel ? 0x18E3 : BG);
    D->setCursor(16, yy);
    bool isCur = ((int)current == i);
    D->printf("%s %s%s", sel ? ">" : " ", MODE_LABELS[i], isCur ? "  *" : "");
  }
  D->setTextSize(1); D->setTextColor(GREY, BG);
  D->setCursor(10, 196); D->print("Sentinel + Apex auto-engage on attack.");
  D->setCursor(10, 210); D->print("Select applies + resets KUMA to calm.");
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
    "Volume", "Brightness", "Wi-Fi / IP", "Firmware", "Credits",
    "Reboot", "Power Off"};
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
      case SET_CREDITS: {
        // KUMA was designed & built by Jax. Tip of the hat on his own hardware.
        g->setTextColor(CYAN, rowBg); g->setCursor(cx, y + 7);
        g->print("jaxdeformity");
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
