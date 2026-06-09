// KUMA Guard T-Deck - terminal implementation.
#include "kuma_terminal.h"
#include "input.h"
#include "kuma_api_client.h"
#include "kuma_rf.h"
#include "kuma_types.h"
#include "kuma_logo_data.h"
#include "kuma_bg_data.h"
#include "config.h"
#include "tdeck_pins.h"
#include <Arduino.h>

namespace {
LGFX_TDeck* D = nullptr;
lgfx::LGFX_Sprite FB;
lgfx::LGFX_Sprite bgTerm;     // heavily-dimmed night-watch bg (shows behind text)
bool fbReady = false;
bool bgReady = false;

constexpr uint16_t BG=0x0000, FG=0xC67A, GREEN=0x07E0, CYAN=0x07FF,
                   AMBER=0xFD20, RED=0xF800, GREY=0x5ACB, DIM=0x2945;
constexpr int VIEW_ROWS = 21, COLW = 52;   // visible text rows / wrap width
constexpr int SCROLLBACK = 300;            // retained history lines (real scrollback)

String  g_lines[SCROLLBACK];               // ring buffer of output lines
int     g_start  = 0;                      // ring index of the oldest retained line
int     g_count  = 0;                      // number of valid lines (<= SCROLLBACK)
int     g_scroll = 0;                      // lines scrolled up from bottom (0 = live)
String  g_cwd = "~";                       // tracked from the Pi shell responses
int     g_kuroPending = 0;                 // 0 none, 1 arm-kuroshuna, 2 arm-broadcast

lgfx::LovyanGFX* G() { return fbReady ? (lgfx::LovyanGFX*)&FB : (lgfx::LovyanGFX*)D; }

int     maxScroll()   { return g_count > VIEW_ROWS ? g_count - VIEW_ROWS : 0; }
String& lineAt(int k) { return g_lines[(g_start + k) % SCROLLBACK]; }

void putLine(const String& s) {
  // wrap to COLW chars per row, append into the scrollback ring
  int i = 0, n = s.length();
  do {
    String chunk = s.substring(i, min(n, i + COLW));
    if (g_count < SCROLLBACK) {
      g_lines[(g_start + g_count) % SCROLLBACK] = chunk;
      ++g_count;
    } else {                                  // full: overwrite + drop the oldest
      g_lines[g_start] = chunk;
      g_start = (g_start + 1) % SCROLLBACK;
    }
    // if the user is reading history, keep their view anchored to the same text
    if (g_scroll > 0) g_scroll = min(g_scroll + 1, maxScroll());
    i += COLW;
  } while (i < n);
}

void render(const String& input) {
  lgfx::LovyanGFX* g = G();
  // semi-opaque night-watch backdrop; text drawn transparent over it
  if (bgReady && fbReady)       bgTerm.pushSprite(&FB, 0, 0);
  else if (bgReady)             g->drawPng(KUMA_BG_TERM, KUMA_BG_TERM_LEN, 0, 0);
  else                          g->fillScreen(BG);
  g->drawPng(KUMA_LOGO, sizeof KUMA_LOGO, 6, 2);
  g->setFont(&fonts::Font0); g->setTextSize(1);
  g->setTextColor(CYAN); g->setCursor(64, 8); g->print("// TERMINAL");
  g->drawFastHLine(0, 24, 320, DIM);

  // viewport: VIEW_ROWS lines ending g_scroll lines above the newest
  int first = g_count - g_scroll - VIEW_ROWS;
  if (first < 0) first = 0;
  int row = 0;
  for (int k = first; k < g_count && row < VIEW_ROWS; ++k, ++row) {
    const String& ln = lineAt(k);
    uint16_t c = FG;
    if (ln.startsWith("kuma>")) c = GREY;
    else if (ln.startsWith("!")) c = RED;
    else if (ln.startsWith("*")) c = AMBER;
    g->setTextColor(c); g->setCursor(4, 28 + row * 9); g->print(ln);
  }

  // scrollbar: only when history exceeds the viewport
  if (g_count > VIEW_ROWS) {
    const int X = 317, Y0 = 28, H = 198;            // track spans the text area
    g->drawFastVLine(X, Y0, H, DIM);
    int thumb  = max(8, H * VIEW_ROWS / g_count);
    int travel = H - thumb;
    int top = Y0 + travel - (maxScroll() ? travel * g_scroll / maxScroll() : 0);
    g->fillRect(X - 1, top, 3, thumb, g_scroll ? AMBER : GREY);
  }

  if (g_scroll > 0) {                                // reading history, not live
    g->setTextColor(AMBER); g->setCursor(4, 230);
    g->printf("-- history -%d  (roll down to live) --", g_scroll);
  } else {
    String pr = g_cwd; if (pr.length() > 16) pr = "~" + pr.substring(pr.length() - 13);
    g->setTextColor(GREEN); g->setCursor(4, 230);
    g->printf("%s$ %s_", pr.c_str(), input.c_str());
  }
  if (fbReady) FB.pushSprite(D, 0, 0);
}

const char* HELP[] = {
  "this is a REAL shell on the Pi (kuma1).",
  "any command runs on the Pi: ls, cd, cat,",
  "ps, ip a, systemctl status kuma-backend...",
  "built-ins:",
  " status / events / net   KUMA summaries",
  " mode <name>             switch KUMA mode",
  " kuroshuna [arm|broadcast|off|deauth]  gloves off",
  "   deauth <bssid> <ch> [client]   own-radio (gated)",
  " clear / exit",
};

void exec(const String& raw) {
  String line = raw; line.trim();
  if (line.length() == 0) return;
  putLine("kuma> " + line);
  int sp = line.indexOf(' ');
  String cmd = (sp < 0) ? line : line.substring(0, sp);
  String arg = (sp < 0) ? "" : line.substring(sp + 1); arg.trim();
  cmd.toLowerCase();

  if (g_kuroPending && (cmd == "confirm" || cmd == "y" || cmd == "yes")) {
    bool ok = (g_kuroPending == 1) ? kuma_api::armKuroshuna(true)
                                   : kuma_api::armBroadcast(true);
    putLine(ok ? "* KUROSHUNA armed - gloves off"
               : "! arm refused (lab_mode/allow_broadcast off on the Pi?)");
    g_kuroPending = 0;
    return;
  }
  if (g_kuroPending) { g_kuroPending = 0; putLine("(kuroshuna confirm cancelled)"); }

  if (cmd == "help") { for (auto h : HELP) putLine(h); }
  else if (cmd == "clear") { g_count = 0; g_start = 0; g_scroll = 0; }
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
  else if (cmd == "kuroshuna" || cmd == "kuro") {
    // split arg into up to 4 space-separated tokens (preserve case for MACs)
    String t[4]; int nt = 0; { String w = arg; w.trim();
      while (w.length() && nt < 4) { int sp = w.indexOf(' ');
        t[nt++] = (sp < 0) ? w : w.substring(0, sp);
        w = (sp < 0) ? "" : w.substring(sp + 1); w.trim(); } }
    String sub = t[0]; sub.toLowerCase();

    if (sub == "deauth") {
      KumaStatus s;
      if (!kuma_api::fetchStatus(s) || !s.kuroshunaArmed) {
        putLine("! kuroshuna not armed (arm first)"); return; }
      if (nt < 3) { putLine("! usage: kuroshuna deauth <bssid> <channel> [client]"); return; }
      uint8_t bssid[6], client[6];
      if (!kuma_rf::parseMac(t[1], bssid)) { putLine("! bad bssid"); return; }
      int ch = t[2].toInt();
      if (ch < 1 || ch > 14) { putLine("! channel 1-14"); return; }
      if (nt >= 4) { if (!kuma_rf::parseMac(t[3], client)) { putLine("! bad client"); return; } }
      else { for (int i = 0; i < 6; i++) client[i] = 0xFF; }   // broadcast
      // AUTHORIZE FIRST (while still connected to the Pi)
      if (!kuma_api::authorizeAction(t[1], "deauth")) {
        putLine("! refused by Pi gate (not approved / disarmed)"); return; }
      putLine(String("* authorized; injecting on ch") + ch + " (link will drop, self-heals)");
      int sent = kuma_rf::deauth(bssid, client, (uint8_t)ch, 64);
      putLine(String("* deauth sent ") + sent + " frames -> " + t[1]);
      // the main loop's reconnectIfDown() restores the Pi link
    } else if (sub == "status" || sub == "") {
      KumaStatus s;
      if (!kuma_api::fetchStatus(s)) { putLine("! backend offline"); return; }
      putLine(String("kuroshuna: ") + (s.kuroshunaArmed ? "ARMED" : "disarmed")
              + "  broadcast: " + (s.broadcastArmed ? "ARMED" : "off"));
    } else if (sub == "arm" || sub == "on") {
      putLine("! KUROSHUNA = gloves off (active offense vs approved targets).");
      putLine("! type 'kuroshuna confirm' to arm.");
      g_kuroPending = 1;
    } else if (sub == "broadcast") {
      putLine("! BROADCAST tier = INDISCRIMINATE: transmits to EVERYTHING in range.");
      putLine("! only with physical RF isolation. type 'kuroshuna confirm' to arm.");
      g_kuroPending = 2;
    } else if (sub == "off" || sub == "disarm") {
      bool ok = kuma_api::armKuroshuna(false);   // disarm also clears broadcast on the Pi
      putLine(ok ? "* KUROSHUNA disarmed" : "! disarm failed");
    } else {
      putLine("! usage: kuroshuna [status|arm|broadcast|off|deauth]");
    }
  }
  else if (cmd == "get") {
    if (arg.length() == 0) { putLine("! usage: get <path>"); return; }
    if (!arg.startsWith("/")) arg = "/" + arg;
    String body = kuma_api::get(arg);
    if (body.length() > 360) body = body.substring(0, 360) + "...";
    putLine(body);
  }
  else {
    // anything else: run it as a real shell command on the Pi
    String out = kuma_api::shell(line, g_cwd);
    int start = 0, n = out.length();
    while (start < n) {
      int nl = out.indexOf('\n', start);
      String ln = (nl < 0) ? out.substring(start) : out.substring(start, nl);
      ln.replace("\t", "  ");
      if (ln.length() || nl >= 0) putLine(ln);
      if (nl < 0) break;
      start = nl + 1;
    }
  }
}
}  // namespace

namespace terminal {

void begin(LGFX_TDeck* d) {
  D = d;
  FB.setColorDepth(16); FB.setPsram(true);
  fbReady = FB.createSprite(320, 240);
  bgTerm.setColorDepth(16); bgTerm.setPsram(true);
  if (bgTerm.createSprite(320, 240)) {
    bgReady = bgTerm.drawPng(KUMA_BG_TERM, KUMA_BG_TERM_LEN, 0, 0);
    if (!bgReady) bgTerm.deleteSprite();
  }
}

void run() {
  g_start = 0; g_count = 0; g_scroll = 0;
  putLine("KUMA terminal ready. type 'help'.");
  putLine("(roll trackball to scroll | ESC or click to exit)");
  String input = "";
  bool dirty = true;
  unsigned long tEnter = millis();
  uint8_t tbUp = digitalRead(TDECK_TB_UP), tbDn = digitalRead(TDECK_TB_DOWN);
  for (;;) {
    if (dirty) { render(input); dirty = false; }
    char c = input::lastKey();            // single fresh read per loop, consumed
    if (c) {
      if (c == 27) return;                              // ESC exits
      else if (c == '\r' || c == '\n') {
        String cmd = input; input = "";
        if (cmd == "exit" || cmd == "quit") return;
        g_scroll = 0;                                   // jump to live on a new command
        exec(cmd); dirty = true;
      } else if (c == 8 || c == 127) {                  // backspace
        if (input.length()) input.remove(input.length()-1);
        dirty = true;
      } else if (c >= 32 && c < 127) {
        if (input.length() < 48) input += c;
        dirty = true;
      }
    }
    // trackball roll = scroll through scrollback (HIGH->LOW edge per detent)
    uint8_t u = digitalRead(TDECK_TB_UP), d = digitalRead(TDECK_TB_DOWN);
    if (tbUp == HIGH && u == LOW) { g_scroll = min(g_scroll + 3, maxScroll()); dirty = true; }
    if (tbDn == HIGH && d == LOW) { g_scroll = max(g_scroll - 3, 0);           dirty = true; }
    tbUp = u; tbDn = d;
    // physical exit: trackball click (after a short guard so entry doesn't bounce)
    if (millis() - tEnter > 500 && digitalRead(TDECK_TB_CLICK) == LOW) return;
    delay(20);
  }
}

}  // namespace terminal
