// KUMA Guard T-Deck - on-device battle implementation.
#include "kuma_battle.h"
#include "input.h"
#include "kuma_audio.h"
#include "bear_sprites_data.h"     // BearSprite, BEAR_SPRITES[] (shared KUMA states)
#include "battle_sprites_data.h"   // ENEMY_SPRITES[], KB_*_S, SKULL_S
#include "kuma_logo_data.h"        // クマ wordmark
#include "kuma_bg_data.h"          // night-watch backgrounds

namespace {
LGFX_TDeck* D = nullptr;
lgfx::LGFX_Sprite FB;
lgfx::LGFX_Sprite bgBattle;        // night-watch arena bg, decoded once + blitted
bool fbReady = false;
bool bgReady = false;

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
const char* AB_TYPE[4] = {"DISRUPT","LURE","RF","CONTAIN"};   // move types
const char* CMD_OPT[4] = {"FIGHT","BAG","RUN","AUTO"};        // top-level command menu
enum { MENU_NONE = 0, MENU_CMD = 1, MENU_ABIL = 2 };

// Sustained-attack gate: high threat must persist this many polls (~2s each)
// before the "DEPLOY COUNTERMEASURES?" prompt appears. Low on purpose.
constexpr int SUSTAIN_POLLS = 1;   // ~2nd consecutive high poll (~4s)

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
// night-watch arena background; falls back to black if the decode failed
void drawBg() {
  if (bgReady && fbReady) { bgBattle.pushSprite(&FB, 0, 0); return; }
  lgfx::LovyanGFX* g = G();
  if (!(bgReady && g->drawPng(KUMA_BG_BATTLE, KUMA_BG_BATTLE_LEN, 0, 0)))
    g->fillScreen(BG);
}
void spr(const BearSprite& s, int x, int y) { G()->drawPng(s.data, s.len, x, y); }

void hpbar(int x, int y, int w, int cur, int mx) {
  float p = mx ? (float)cur / mx : 0; if (p<0) p=0;
  uint16_t c = p>0.5f?GREEN : p>0.22f?AMBER : RED;
  G()->drawRect(x, y, w, 6, GREY);
  G()->fillRect(x+1, y+1, (int)((w-2)*p), 4, c);
}

// full battle scene. menuMode: 0 none, 1 command (Fight/Bag/Run/Auto), 2 abilities
void scene(const char* msg, int menuMode, int sel, const BearSprite& kuma,
           int kHp, int kMax, int eHp, int eMax, int en, uint16_t lvl) {
  lgfx::LovyanGFX* g = G();
  drawBg();
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
  // menu (2x2, bottom-right)
  if (menuMode) {
    const int cx[4]={150,234,150,234}, cy[4]={146,146,192,192};
    for (int i=0;i<4;i++){
      bool s = (i==sel);
      uint16_t bgc = s ? 0x13E6 : BOX;
      g->fillRect(cx[i], cy[i], 82, 44, bgc);
      g->drawRect(cx[i], cy[i], 82, 44, s?CYAN:DIM);
      if (menuMode == MENU_CMD) {
        g->setTextSize(2); g->setTextColor(s?CYAN:FG, bgc);
        g->setCursor(cx[i]+8, cy[i]+14); g->print(CMD_OPT[i]); g->setTextSize(1);
      } else {
        bool weak = EN_WEAK[en] & (1<<i);          // super-effective -> amber
        g->setTextColor(s ? CYAN : (weak ? AMBER : FG), bgc);
        g->setCursor(cx[i]+4, cy[i]+6); g->print(AB_NAME[i]);
        g->setTextColor(GREY, bgc); g->setCursor(cx[i]+4, cy[i]+24); g->print(AB_TYPE[i]);
      }
    }
  }
  push();
}

void flashScreen(uint16_t c) { G()->fillScreen(c); push(); delay(70); }

int autoPick(int en) {
  for (int i=0;i<4;i++) if (EN_WEAK[en] & (1<<i)) return i;
  return 0;
}

// YES/NO over the battlefield; returns true on YES
bool confirmDialog(const char* prompt, int kHp, int kMax, int eHp, int eMax, int en, uint16_t lvl) {
  int sel = 0; bool dirty = true; unsigned long t0 = millis();
  for (;;) {
    if (dirty) {
      scene(prompt, MENU_NONE, 0, KB_DEFEND_S, kHp, kMax, eHp, eMax, en, lvl);
      lgfx::LovyanGFX* g = G();
      const char* yn[2] = {"YES", "NO"};
      for (int i=0;i<2;i++){ bool s=(i==sel); int x=158+i*78, y=150;
        g->fillRect(x,y,72,40,s?0x13E6:BOX); g->drawRect(x,y,72,40,s?CYAN:DIM);
        g->setTextSize(2); g->setTextColor(s?CYAN:FG,s?0x13E6:BOX); g->setCursor(x+16,y+12);
        g->print(yn[i]); g->setTextSize(1); }
      push(); dirty = false;
    }
    InputEvent e = input::poll();
    if (e==InputEvent::Left||e==InputEvent::Up)        { sel=0; dirty=true; }
    else if (e==InputEvent::Right||e==InputEvent::Down){ sel=1; dirty=true; }
    else if (e==InputEvent::Select)                    return sel==0;
    else if (e==InputEvent::Back)                      return false;
    if (millis()-t0 >= 20000) return false;
    delay(20);
  }
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
  scene(introMsg.c_str(), MENU_NONE, 0, KB_DEFEND_S, kHp, kMax, eHp, eMax, en, lvl);
  delay(1500);

  // --- turn loop: Fight / Bag / Run / Auto ---
  bool autoMode = false;
  while (true) {
    int act = 0;                                    // default: Fight
    if (!autoMode) {
      int sel = 0; bool dirty = true; unsigned long t0 = millis(); act = -1;
      while (act < 0 && millis() - t0 < 30000) {
        if (dirty) { scene("WHAT WILL KUMA DO?", MENU_CMD, sel, KB_DEFEND_S, kHp,kMax,eHp,eMax,en,lvl); dirty=false; }
        InputEvent e = input::poll();
        if (e==InputEvent::Up||e==InputEvent::Left){sel=(sel+3)&3;dirty=true;}
        else if(e==InputEvent::Down||e==InputEvent::Right){sel=(sel+1)&3;dirty=true;}
        else if(e==InputEvent::Select){act=sel;}
        delay(20);
      }
      if (act < 0) act = 0;                          // timeout -> Fight
    }
    if (act == 1) {                                  // BAG (future)
      scene("Bag empty -- no items yet.", MENU_NONE, 0, KB_DEFEND_S, kHp,kMax,eHp,eMax,en,lvl);
      delay(1400); continue;
    }
    if (act == 2) {                                  // RUN
      if (confirmDialog("Attempt to flee?", kHp,kMax,eHp,eMax,en,lvl)) {
        audio::stopMusic();
        scene("KUMA broke contact.", MENU_NONE, 0, KB_DEFEND_S, kHp,kMax,eHp,eMax,en,lvl);
        delay(1500); return;
      }
      continue;
    }
    if (act == 3) {                                  // AUTO
      if (confirmDialog("Engage auto-protocol?", kHp,kMax,eHp,eMax,en,lvl)) autoMode = true;
      continue;
    }

    // --- FIGHT: pick an attack ---
    int sel = autoPick(en);
    if (!autoMode) {
      bool dirty = true; unsigned long t0 = millis(); int ab = -1;
      while (ab == -1 && millis() - t0 < 30000) {
        if (dirty) { scene("CHOOSE AN ATTACK", MENU_ABIL, sel, KB_DEFEND_S, kHp,kMax,eHp,eMax,en,lvl); dirty=false; }
        InputEvent e = input::poll();
        if (e==InputEvent::Up||e==InputEvent::Left){sel=(sel+3)&3;dirty=true;}
        else if(e==InputEvent::Down||e==InputEvent::Right){sel=(sel+1)&3;dirty=true;}
        else if(e==InputEvent::Select){ab=sel;}
        else if(e==InputEvent::Back){ab=-2;}          // back to command menu
        delay(20);
      }
      if (ab == -2) continue;                         // backed out
      if (ab >= 0) sel = ab;                          // else timeout keeps autoPick
    }

    // --- resolve the move ---
    const BearSprite& clip = (sel==3) ? BEAR_SPRITES[4] : KB_ATTACK_S;
    audio::sfx(AB_SFX[sel]);
    String m1 = String("KUMA used ") + AB_NAME[sel] + "!";
    scene(m1.c_str(), MENU_NONE, 0, clip, kHp,kMax,eHp,eMax,en,lvl); delay(500);
    bool weak = EN_WEAK[en] & (1<<sel);
    if (sel == 1) {
      marked = true; int dmg = random(AB_MIN[1], AB_MAX[1]+1); eHp = max(0, eHp-dmg);
      scene("Threat took the bait. MARKED.", MENU_NONE, 0, KB_DEFEND_S, kHp,kMax,eHp,eMax,en,lvl);
    } else {
      int dmg = random(AB_MIN[sel], AB_MAX[sel]+1);
      if (weak) dmg = (int)(dmg*1.7f);
      if (marked) { dmg = (int)(dmg*1.5f); marked = false; }
      eHp = max(0, eHp-dmg);
      scene(weak ? "Super effective!" : "Hit.", MENU_NONE, 0, KB_DEFEND_S, kHp,kMax,eHp,eMax,en,lvl);
    }
    delay(900);
    if (eHp <= 0) break;

    // --- enemy turn ---
    int edmg = random(8, 17); kHp = max(0, kHp-edmg);
    String em = String(EN_NAME[en]) + " strikes back!";
    scene(em.c_str(), MENU_NONE, 0, BEAR_SPRITES[5], kHp,kMax,eHp,eMax,en,lvl);
    delay(900);
    if (kHp <= 0) break;
    if (autoMode) delay(400);
  }

  // --- resolve ---
  audio::stopMusic();
  if (eHp <= 0) {
    audio::playTrack(audio::TRK_VICTORY, false);
    kuma_api::postBattleWin();
    String w = String("KUMA decrypted the ") + EN_NAME[en] + ".";
    scene(w.c_str(), MENU_NONE, 0, KB_VICTORY_S, kHp, kMax, 0, eMax, en, lvl);
    delay(1500);
    lgfx::LovyanGFX* g2 = G(); drawBg();
    g2->setTextSize(3); g2->setTextColor(GREEN); g2->setCursor(70, 40); g2->print("VICTORY!");
    g2->setTextSize(1); g2->setTextColor(CYAN); g2->setCursor(96, 76); g2->print("DATA SECURED");
    spr(KB_VICTORY_S, 110, 96); push();
    delay(13000);                          // hold through the victory track
  } else {
    lgfx::LovyanGFX* g2 = G(); drawBg();
    g2->setTextSize(1); g2->setTextColor(AMBER); g2->setCursor(20, 110);
    g2->print("Link dropped... KUMA regroups."); push();
    delay(2500);
  }
  audio::stopMusic();
}

// "DEPLOY COUNTERMEASURES?" gate, shown on a sustained attack. YES -> battle,
// NO -> stay in ALERT (the detection is already logged). Default on timeout = NO.
bool deployPrompt(int en, uint16_t lvl) {
  audio::sfx(audio::SFX_CLAW_ID);
  int sel = 0; bool dirty = true; unsigned long t0 = millis();
  for (;;) {
    if (dirty) {
      lgfx::LovyanGFX* g = G();
      drawBg();
      g->setFont(&fonts::Font0);
      g->setTextSize(2); g->setTextColor(RED, BG);
      g->setCursor(14, 8); g->print("! SUSTAINED ATTACK");
      g->setTextSize(1); g->setTextColor(AMBER, BG);
      g->setCursor(14, 34); g->printf("Hostile %s locked on", EN_NAME[en]);
      const BearSprite& es = ENEMY_SPRITES[en]; spr(es, 318 - es.w, 44);
      spr(BEAR_SPRITES[5], 6, 238 - BEAR_SPRITES[5].h);   // alert KUMA
      g->setTextSize(2); g->setTextColor(CYAN, BG);
      g->setCursor(120, 92);  g->print("DEPLOY");
      g->setCursor(120, 116); g->print("COUNTER-");
      g->setCursor(120, 140); g->print("MEASURES?");
      const char* yn[2] = {"YES", "NO"};
      for (int i = 0; i < 2; ++i) {
        bool s = (i == sel); int x = 124 + i * 100, y = 176;
        g->fillRect(x, y, 90, 48, s ? 0x13E6 : BOX);
        g->drawRect(x, y, 90, 48, s ? CYAN : DIM);
        g->setTextSize(3); g->setTextColor(s ? CYAN : FG, s ? 0x13E6 : BOX);
        g->setCursor(x + (i ? 26 : 14), y + 12); g->print(yn[i]);
      }
      g->setTextSize(1);
      push(); dirty = false;
    }
    InputEvent e = input::poll();
    if (e == InputEvent::Left || e == InputEvent::Up)         { sel = 0; dirty = true; }
    else if (e == InputEvent::Right || e == InputEvent::Down) { sel = 1; dirty = true; }
    else if (e == InputEvent::Select)                          return sel == 0;
    else if (e == InputEvent::Back)                            return false;
    if (millis() - t0 >= 20000) return false;    // timeout -> NO (stay in alert)
    delay(20);
  }
}
}  // namespace

namespace battle {

void begin(LGFX_TDeck* d) {
  D = d;
  FB.setColorDepth(16);
  FB.setPsram(true);
  fbReady = FB.createSprite(320, 240);
  bgBattle.setColorDepth(16);
  bgBattle.setPsram(true);
  if (bgBattle.createSprite(320, 240)) {
    bgReady = bgBattle.drawPng(KUMA_BG_BATTLE, KUMA_BG_BATTLE_LEN, 0, 0);
    if (!bgReady) bgBattle.deleteSprite();
  }
}

bool maybeStart(const KumaStatus& s) {
  // Flow: attack -> ALERT (the bear face, driven by bear_state). If the attack
  // is SUSTAINED (high threat across a few polls), prompt "DEPLOY
  // COUNTERMEASURES?". YES -> battle, then reset to calm (drop alert). NO ->
  // stay in ALERT (detection already logged). One prompt per episode; re-arms
  // when the threat clears (e.g. after a battle's reset, or a mode pick).
  static int  sustain = 0;
  static bool decided = false;
  if (!s.online) { sustain = 0; decided = false; return false; }
  bool high = (s.threatLevel == "high" || s.threatLevel == "critical");
  if (!high) { sustain = 0; decided = false; return false; }   // calm -> re-arm
  if (decided) return false;                    // already decided this episode
  if (sustain < SUSTAIN_POLLS) { sustain++; return false; }    // not sustained yet
  KumaEvent ev[8];
  int n = kuma_api::fetchEvents(ev, 8);
  int en = -1;
  for (int i=0;i<n;i++) { en = eventToEnemy(ev[i].eventType); if (en>=0) break; }
  if (en < 0) return false;
  decided = true;                               // consume the decision for this episode
  if (deployPrompt(en, s.level)) {              // YES -> engage
    run(en, s.level);
    kuma_api::sendAction("clear_mock_events", true);   // battle over -> reset to calm
  }
  // NO -> remain in ALERT; the detection event is already logged. No reset.
  return true;
}

}  // namespace battle
