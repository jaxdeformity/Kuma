// KUMA Guard T-Deck - on-device battle implementation.
#include "kuma_battle.h"
#include "input.h"
#include "kuma_audio.h"
#include "bear_sprites_data.h"     // BearSprite, BEAR_SPRITES[] (shared KUMA states)
#include "battle_sprites_data.h"   // ENEMY_SPRITES[], KB_*_S, SKULL_S
#include "kuma_logo_data.h"        // クマ wordmark

namespace {
LGFX_TDeck* D = nullptr;
lgfx::LGFX_Sprite FB;
bool fbReady = false;

constexpr uint16_t BG=0x0000, FG=0xFFFF, RED=0xF800, GREEN=0x07E0,
                   AMBER=0xFD20, CYAN=0x07FF, GREY=0x7BEF, DIM=0x2945, BOX=0x10A2;

// --- enemies (index matches ENEMY_SPRITES order) ---
const char* EN_NAME[10] = {"ROGUE AP","EVIL TWIN","DEAUTHER","WIFI PINEAPPLE",
  "BEACON FLOOD","KARMA LURE","HANDSHAKE HARV","SNIFFER","RF JAMMER","BOTNET WORM"};
const uint16_t EN_HP[10] = {120,125,135,150,115,130,145,110,140,160};
// weak-ability bitmask: bit0 SIGNAL MAUL, bit1 HONEY SNARE, bit2 CHANNEL ROAR, bit3 PAWLOCK
const uint8_t EN_WEAK[10] = {0b1001,0b0011,0b0100,0b0011,0b0101,0b0010,0b1010,0b1000,0b0100,0b1100};

// --- abilities ---
const char* AB_NAME[4] = {"SIGNAL MAUL","HONEY SNARE","CHANNEL ROAR","PAWLOCK"};
const char* AB_SUB[4]  = {"disrupt","bait+mark","break flood","contain"};
const uint8_t AB_MIN[4]={20,8,20,22}, AB_MAX[4]={26,12,26,30};
const audio::SfxId AB_SFX[4]={audio::SFX_CLAW_ID,audio::SFX_FULL_ID,audio::SFX_CHARGED_ID,audio::SFX_FULL_ID};

int eventToEnemy(const String& etRaw) {
  String e = etRaw; e.toLowerCase();
  if (e.indexOf("deauth")>=0 || e.indexOf("disassoc")>=0) return 2;
  if (e.indexOf("twin")>=0) return 1;
  if (e.indexOf("rogue")>=0 || e.indexOf("bssid")>=0) return 0;
  if (e.indexOf("beacon")>=0 || e.indexOf("ssid")>=0) return 4;
  if (e.indexOf("pineap")>=0) return 3;
  if (e.indexOf("karma")>=0) return 5;
  if (e.indexOf("handshake")>=0 || e.indexOf("eapol")>=0) return 6;
  if (e.indexOf("sniff")>=0) return 7;
  if (e.indexOf("jam")>=0) return 8;
  if (e.indexOf("botnet")>=0 || e.indexOf("worm")>=0) return 9;
  return -1;   // apex_response, mock, etc. -> no battle
}

lgfx::LovyanGFX* G() { return fbReady ? (lgfx::LovyanGFX*)&FB : (lgfx::LovyanGFX*)D; }
void push() { if (fbReady) FB.pushSprite(D, 0, 0); }
void spr(const BearSprite& s, int x, int y) { G()->drawPng(s.data, s.len, x, y); }

void hpbar(int x, int y, int w, int cur, int mx) {
  float p = mx ? (float)cur / mx : 0; if (p<0) p=0;
  uint16_t c = p>0.5f?GREEN : p>0.22f?AMBER : RED;
  G()->drawRect(x, y, w, 6, GREY);
  G()->fillRect(x+1, y+1, (int)((w-2)*p), 4, c);
}

// full battle scene
void scene(const char* msg, bool menu, int sel, const BearSprite& kuma,
           int kHp, int kMax, int eHp, int eMax, int en, uint16_t lvl) {
  lgfx::LovyanGFX* g = G();
  g->fillScreen(BG);
  // message strip
  g->setFont(&fonts::Font0); g->setTextSize(1); g->setTextColor(FG, BG);
  g->setCursor(6, 3); g->print(msg);
  // enemy sprite (top-right) + info (top-left)
  const BearSprite& es = ENEMY_SPRITES[en];
  spr(es, 318 - es.w, 14);
  g->fillRect(6, 14, 178, 50, BOX); g->drawRect(6, 14, 178, 50, DIM);
  g->setTextColor(FG, BOX); g->setCursor(10, 20); g->print(EN_NAME[en]);
  spr(SKULL_S, 120, 18);                            // unknown rank (big skull)
  hpbar(10, 44, 162, eHp, eMax);
  // KUMA sprite (bottom-left)
  spr(kuma, 6, 238 - kuma.h);
  // KUMA info (right of sprite)
  g->drawPng(KUMA_LOGO, sizeof KUMA_LOGO, 150, 116);
  g->setTextColor(GREEN, BG); g->setCursor(150 + KUMA_LOGO_W + 8, 122);
  g->printf("Lv %u", lvl);
  hpbar(152, 134, 160, kHp, kMax);
  // ability menu (2x2, bottom-right)
  if (menu) {
    const int cx[4]={150,234,150,234}, cy[4]={146,146,192,192};
    for (int i=0;i<4;i++){
      bool s = (i==sel);
      bool weak = EN_WEAK[en] & (1<<i);
      uint16_t bgc = s ? 0x13E6 : BOX;
      g->fillRect(cx[i], cy[i], 82, 44, bgc);
      g->drawRect(cx[i], cy[i], 82, 44, s?CYAN:DIM);
      // super-effective abilities tinted amber (no separate marker glyph)
      g->setTextColor(s ? CYAN : (weak ? AMBER : FG), bgc);
      g->setCursor(cx[i]+4, cy[i]+6); g->print(AB_NAME[i]);
      g->setTextColor(GREY, bgc); g->setCursor(cx[i]+4, cy[i]+24); g->print(AB_SUB[i]);
    }
  }
  push();
}

void flashScreen(uint16_t c) { G()->fillScreen(c); push(); delay(70); }

int autoPick(int en) {
  for (int i=0;i<4;i++) if (EN_WEAK[en] & (1<<i)) return i;
  return 0;
}

void run(int en, uint16_t lvl) {
  int eMax = EN_HP[en], eHp = eMax, kMax = 120, kHp = kMax;
  bool marked = false;

  // --- encounter ---
  audio::playTrack(audio::TRK_ENCOUNTER, false);
  for (int i=0;i<2;i++){ flashScreen(RED); G()->fillScreen(BG); push(); delay(120); }
  lgfx::LovyanGFX* g = G();
  g->fillScreen(BG);
  g->setTextSize(2); g->setTextColor(RED, BG); g->setCursor(40, 60); g->print("THREAT DETECTED");
  push(); delay(1400);
  // enemy approaches
  g->fillScreen(BG); g->setTextSize(1); g->setTextColor(CYAN, BG);
  g->setCursor(40, 30); g->print("HOSTILE SIGNAL LOCKED");
  spr(ENEMY_SPRITES[en], 320-ENEMY_SPRITES[en].w-30, 60); push(); delay(1500);
  audio::playTrack(audio::TRK_BATTLE, true);

  String introMsg = String("HOSTILE ") + EN_NAME[en] + " DETECTED";
  scene(introMsg.c_str(), false, 0, KB_DEFEND_S, kHp, kMax, eHp, eMax, en, lvl);
  delay(1500);

  // --- turn loop ---
  while (true) {
    // player turn: menu + input, 30s auto
    int sel = autoPick(en);
    scene("WHAT WILL KUMA DO?", true, sel, KB_DEFEND_S, kHp, kMax, eHp, eMax, en, lvl);
    unsigned long t0 = millis(); unsigned long lastDraw = t0; bool chosen = false;
    while (millis() - t0 < 30000) {
      InputEvent e = input::poll();
      if (e == InputEvent::Up || e == InputEvent::Left)  { sel=(sel+3)&3; scene("WHAT WILL KUMA DO?", true, sel, KB_DEFEND_S, kHp, kMax, eHp, eMax, en, lvl); }
      else if (e == InputEvent::Down || e == InputEvent::Right) { sel=(sel+1)&3; scene("WHAT WILL KUMA DO?", true, sel, KB_DEFEND_S, kHp, kMax, eHp, eMax, en, lvl); }
      else if (e == InputEvent::Select) { chosen = true; break; }
      delay(20);
    }
    (void)chosen;  // timeout uses the pre-selected weak ability

    // --- do move ---
    const BearSprite& clip = (sel==3) ? BEAR_SPRITES[4] /*apex*/ : KB_ATTACK_S;
    audio::sfx(AB_SFX[sel]);
    String m1 = String("KUMA used ") + AB_NAME[sel] + "!";
    scene(m1.c_str(), false, 0, clip, kHp, kMax, eHp, eMax, en, lvl);
    delay(500);
    bool weak = EN_WEAK[en] & (1<<sel);
    if (sel == 1) {                       // HONEY SNARE -> mark, little damage
      marked = true;
      int dmg = random(AB_MIN[1], AB_MAX[1]+1);
      eHp = max(0, eHp - dmg);
      scene("Threat took the bait. MARKED.", false, 0, KB_DEFEND_S, kHp, kMax, eHp, eMax, en, lvl);
    } else {
      int dmg = random(AB_MIN[sel], AB_MAX[sel]+1);
      if (weak) dmg = (int)(dmg * 1.7f);
      if (marked) { dmg = (int)(dmg * 1.5f); marked = false; }
      eHp = max(0, eHp - dmg);
      const char* line = weak ? "Super effective!" : "Hit.";
      scene(line, false, 0, KB_DEFEND_S, kHp, kMax, eHp, eMax, en, lvl);
    }
    delay(900);
    if (eHp <= 0) break;

    // --- enemy turn ---
    int edmg = random(8, 17);
    kHp = max(0, kHp - edmg);
    String em = String(EN_NAME[en]) + " strikes back!";
    scene(em.c_str(), false, 0, BEAR_SPRITES[5] /*alert*/, kHp, kMax, eHp, eMax, en, lvl);
    delay(900);
    if (kHp <= 0) break;
  }

  // --- resolve ---
  audio::stopMusic();
  if (eHp <= 0) {
    audio::playTrack(audio::TRK_VICTORY, false);
    kuma_api::postBattleWin();
    String w = String(EN_NAME[en]) + " contained.";
    scene(w.c_str(), false, 0, KB_VICTORY_S, kHp, kMax, 0, eMax, en, lvl);
    delay(1500);
    lgfx::LovyanGFX* g2 = G(); g2->fillScreen(BG);
    g2->setTextSize(2); g2->setTextColor(GREEN, BG); g2->setCursor(34, 50); g2->print("THREAT CONTAINED");
    spr(KB_VICTORY_S, 110, 100); push();
    delay(13000);                          // hold through the victory track
  } else {
    lgfx::LovyanGFX* g2 = G(); g2->fillScreen(BG);
    g2->setTextSize(1); g2->setTextColor(AMBER, BG); g2->setCursor(20, 110);
    g2->print("Link dropped... KUMA regroups."); push();
    delay(2500);
  }
  audio::stopMusic();
}
}  // namespace

namespace battle {

void begin(LGFX_TDeck* d) {
  D = d;
  FB.setColorDepth(16);
  FB.setPsram(true);
  fbReady = FB.createSprite(320, 240);
}

bool maybeStart(const KumaStatus& s) {
  // Fire once per threat episode: re-arm only after the threat drops back down,
  // so a sustained/repeated same-type attack rolls into a single encounter.
  static bool armed = true;
  if (!s.online) return false;
  bool high = (s.threatLevel == "high" || s.threatLevel == "critical");
  if (!high) { armed = true; return false; }   // threat cleared -> ready for the next
  if (!armed) return false;                     // already battled this episode
  KumaEvent ev[8];
  int n = kuma_api::fetchEvents(ev, 8);
  int en = -1;
  for (int i=0;i<n;i++) { en = eventToEnemy(ev[i].eventType); if (en>=0) break; }
  if (en < 0) return false;
  armed = false;                                // consume this episode
  run(en, s.level);
  return true;
}

}  // namespace battle
