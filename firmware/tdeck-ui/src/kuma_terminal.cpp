// KUMA Guard T-Deck - terminal implementation.
#include "kuma_terminal.h"
#include "input.h"
#include "kuma_api_client.h"
#include "kuma_types.h"
#include "kuma_logo_data.h"
#include "config.h"
#include "tdeck_pins.h"
#include <Arduino.h>

namespace {
LGFX_TDeck* D = nullptr;
lgfx::LGFX_Sprite FB;
bool fbReady = false;

constexpr uint16_t BG=0x0000, FG=0xC67A, GREEN=0x07E0, CYAN=0x07FF,
                   AMBER=0xFD20, RED=0xF800, GREY=0x5ACB, DIM=0x2945;
constexpr int ROWS = 21, COLW = 52;

String g_buf[ROWS];
int g_count = 0;

lgfx::LovyanGFX* G() { return fbReady ? (lgfx::LovyanGFX*)&FB : (lgfx::LovyanGFX*)D; }

void putLine(const String& s) {
  // wrap to COLW chars per row
  int i = 0, n = s.length();
  do {
    String chunk = s.substring(i, min(n, i + COLW));
    if (g_count < ROWS) g_buf[g_count++] = chunk;
    else { for (int r = 1; r < ROWS; ++r) g_buf[r-1] = g_buf[r]; g_buf[ROWS-1] = chunk; }
    i += COLW;
  } while (i < n);
}

void render(const String& input) {
  lgfx::LovyanGFX* g = G();
  g->fillScreen(BG);
  g->drawPng(KUMA_LOGO, sizeof KUMA_LOGO, 6, 2);
  g->setFont(&fonts::Font0); g->setTextSize(1);
  g->setTextColor(CYAN, BG); g->setCursor(64, 8); g->print("// TERMINAL");
  g->drawFastHLine(0, 24, 320, DIM);
  for (int r = 0; r < g_count; ++r) {
    uint16_t c = FG;
    if (g_buf[r].startsWith("kuma>")) c = GREY;
    else if (g_buf[r].startsWith("!")) c = RED;
    else if (g_buf[r].startsWith("*")) c = AMBER;
    g->setTextColor(c, BG); g->setCursor(4, 28 + r * 9); g->print(g_buf[r]);
  }
  g->setTextColor(GREEN, BG); g->setCursor(4, 230);
  g->printf("kuma> %s_", input.c_str());
  if (fbReady) FB.pushSprite(D, 0, 0);
}

const char* HELP[] = {
  "commands:",
  " status        device/mode/threat/level",
  " events        recent detections",
  " net           mapped network count",
  " mode <name>   hibernate|foraging|honey|sentinel|apex",
  " get <path>    raw GET (e.g. get /api/progress)",
  " clear         wipe the screen",
  " exit          back to dashboard",
};

void exec(const String& raw) {
  String line = raw; line.trim();
  if (line.length() == 0) return;
  putLine("kuma> " + line);
  int sp = line.indexOf(' ');
  String cmd = (sp < 0) ? line : line.substring(0, sp);
  String arg = (sp < 0) ? "" : line.substring(sp + 1); arg.trim();
  cmd.toLowerCase();

  if (cmd == "help") { for (auto h : HELP) putLine(h); }
  else if (cmd == "clear") { g_count = 0; }
  else if (cmd == "status") {
    KumaStatus s;
    if (!kuma_api::fetchStatus(s)) { putLine("! backend offline"); return; }
    putLine(String("device  ") + s.device + " v" + s.version);
    putLine(String("mode    ") + modeName(s.mode) + "   threat " + s.threatLevel);
    putLine(String("level   ") + s.level + "   networks " + s.networkCount);
    putLine(String("events(10m) ") + s.eventsLast10m + "   form " + s.spriteSet);
    char up[16]; sprintf(up, "%lu", (unsigned long)s.uptimeSeconds);
    putLine(String("uptime  ") + up + "s");
  }
  else if (cmd == "events") {
    KumaEvent ev[6]; int n = kuma_api::fetchEvents(ev, 6);
    if (n == 0) { putLine("(no events)"); return; }
    for (int i = 0; i < n; ++i)
      putLine(String(i+1) + ". [" + ev[i].severity + "] " + ev[i].eventType);
  }
  else if (cmd == "net" || cmd == "networks") {
    KumaStatus s; kuma_api::fetchStatus(s);
    putLine(String("mapped networks: ") + s.networkCount);
    putLine("export: " + String("http://") + KUMA_BACKEND_HOST + ":8080/api/networks/export");
  }
  else if (cmd == "mode") {
    KumaMode m = modeFromString(arg);
    if (arg.length() == 0) { putLine("! usage: mode <name>"); return; }
    bool ok = kuma_api::setMode(m);
    putLine(ok ? (String("* mode -> ") + arg) : "! mode change failed");
  }
  else if (cmd == "get") {
    if (arg.length() == 0) { putLine("! usage: get <path>"); return; }
    if (!arg.startsWith("/")) arg = "/" + arg;
    String body = kuma_api::get(arg);
    if (body.length() > 360) body = body.substring(0, 360) + "...";
    putLine(body);
  }
  else { putLine(String("! unknown: ") + cmd + " (try help)"); }
}
}  // namespace

namespace terminal {

void begin(LGFX_TDeck* d) {
  D = d;
  FB.setColorDepth(16); FB.setPsram(true);
  fbReady = FB.createSprite(320, 240);
}

void run() {
  g_count = 0;
  putLine("KUMA terminal ready. type 'help'.");
  putLine("(ESC or trackball-click to exit)");
  String input = "";
  bool dirty = true;
  unsigned long tEnter = millis();
  for (;;) {
    if (dirty) { render(input); dirty = false; }
    char c = input::lastKey();            // single fresh read per loop, consumed
    if (c) {
      if (c == 27) return;                              // ESC exits
      else if (c == '\r' || c == '\n') {
        String cmd = input; input = "";
        if (cmd == "exit" || cmd == "quit") return;
        exec(cmd); dirty = true;
      } else if (c == 8 || c == 127) {                  // backspace
        if (input.length()) input.remove(input.length()-1);
        dirty = true;
      } else if (c >= 32 && c < 127) {
        if (input.length() < 48) input += c;
        dirty = true;
      }
    }
    // physical exit: trackball click (after a short guard so entry doesn't bounce)
    if (millis() - tEnter > 500 && digitalRead(TDECK_TB_CLICK) == LOW) return;
    delay(20);
  }
}

}  // namespace terminal
