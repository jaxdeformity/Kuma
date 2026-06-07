// KUMA Guard T-Deck - I2S audio implementation.
//
// A single mixer task fills the I2S DMA continuously: it synthesizes the active
// chiptune notes (square/triangle) for the current track and adds a one-shot SFX
// channel on top. All public calls just flip volatile state the task reads; if
// I2S won't init, every call is a safe no-op so the battle still runs silent.
#include "kuma_audio.h"
#include "tdeck_pins.h"
#include "music_data.h"
#include "sfx_data.h"
#include <driver/i2s.h>
#include <math.h>

namespace {
constexpr int RATE = SFX_RATE;          // 22050, shared by music synth + sfx
constexpr int BUF  = 256;
bool g_ok = false;

// --- music bed state (written by API, read by task) ---
volatile const ChipNote* g_score = nullptr;
volatile uint16_t g_scoreLen = 0;
volatile uint32_t g_loopMs   = 0;
volatile bool     g_loop     = false;
volatile uint32_t g_startSample = 0;    // global sample index when the track started
volatile bool     g_musicOn  = false;

// --- sfx one-shot channel ---
volatile const int16_t* g_sfx = nullptr;
volatile uint32_t g_sfxLen = 0;
volatile uint32_t g_sfxPos = 0;
volatile bool     g_sfxOn  = false;

uint32_t g_global = 0;                   // free-running sample counter (phase clock)
volatile float g_volF = 0.22f;           // master volume (0..1), default low
volatile uint8_t g_volPct = 22;

const float WVOL[4] = {0.20f, 0.24f, 0.15f, 0.16f};

inline float noteFreq(uint8_t n) { return 440.0f * powf(2.0f, (n - 69) / 12.0f); }

void mixerTask(void*) {
  static int16_t out[BUF];
  // small cache of notes active this buffer
  struct V { float freq; uint8_t k; };
  V act[8];
  for (;;) {
    int nAct = 0;
    if (g_musicOn && g_score && g_scoreLen) {
      uint32_t elapsed = g_global - g_startSample;
      uint32_t ms = (uint32_t)((uint64_t)elapsed * 1000 / RATE);
      if (g_loop && g_loopMs) ms %= g_loopMs;
      else if (!g_loop && g_loopMs && ms > g_loopMs + 400) g_musicOn = false;  // one-shot done
      for (uint16_t i = 0; i < g_scoreLen && nAct < 8; ++i) {
        uint16_t t = g_score[i].t, d = g_score[i].d;
        if (ms >= t && ms < (uint32_t)t + d) {
          act[nAct].freq = noteFreq(g_score[i].n);
          act[nAct].k = g_score[i].k & 3;
          nAct++;
        }
      }
    }
    for (int i = 0; i < BUF; ++i) {
      float s = 0.0f;
      float ts = (float)(g_global + i) / RATE;
      for (int v = 0; v < nAct; ++v) {
        float ph = act[v].freq * ts; ph -= (long)ph;            // frac
        float w = (act[v].k == 1) ? (4.0f * fabsf(ph - 0.5f) - 1.0f)  // triangle
                                  : (ph < 0.5f ? 1.0f : -1.0f);        // square
        s += w * WVOL[act[v].k] * 9000.0f;
      }
      if (g_sfxOn && g_sfx && g_sfxPos < g_sfxLen) {
        s += (float)g_sfx[g_sfxPos++] * 0.9f;
        if (g_sfxPos >= g_sfxLen) g_sfxOn = false;
      }
      s *= g_volF;                                   // master volume
      if (s > 32767) s = 32767; else if (s < -32768) s = -32768;
      out[i] = (int16_t)s;
    }
    g_global += BUF;
    size_t wrote = 0;
    i2s_write(I2S_NUM_0, out, sizeof out, &wrote, portMAX_DELAY);
  }
}
}  // namespace

namespace audio {

void begin() {
  i2s_config_t cfg = {};
  cfg.mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_TX);
  cfg.sample_rate = RATE;
  cfg.bits_per_sample = I2S_BITS_PER_SAMPLE_16BIT;
  cfg.channel_format = I2S_CHANNEL_FMT_ONLY_LEFT;
  cfg.communication_format = I2S_COMM_FORMAT_STAND_I2S;
  cfg.intr_alloc_flags = 0;
  cfg.dma_buf_count = 6;
  cfg.dma_buf_len = BUF;
  cfg.use_apll = false;
  cfg.tx_desc_auto_clear = true;
  if (i2s_driver_install(I2S_NUM_0, &cfg, 0, nullptr) != ESP_OK) return;
  i2s_pin_config_t pins = {};
  pins.mck_io_num = I2S_PIN_NO_CHANGE;
  pins.bck_io_num = TDECK_I2S_BCK;
  pins.ws_io_num  = TDECK_I2S_WS;
  pins.data_out_num = TDECK_I2S_DOUT;
  pins.data_in_num = I2S_PIN_NO_CHANGE;
  if (i2s_set_pin(I2S_NUM_0, &pins) != ESP_OK) return;
  i2s_zero_dma_buffer(I2S_NUM_0);
  g_ok = true;
  xTaskCreatePinnedToCore(mixerTask, "kuma_mix", 4096, nullptr, 4, nullptr, 0);
}

bool ok() { return g_ok; }

void playTrack(Track t, bool loop) {
  if (!g_ok) return;
  const ChipNote* sc; uint16_t len; uint32_t lp;
  switch (t) {
    case TRK_ENCOUNTER: sc = MUS_ENCOUNTER; len = MUS_ENCOUNTER_LEN; lp = MUS_ENCOUNTER_LOOP; break;
    case TRK_BATTLE:    sc = MUS_BATTLE;    len = MUS_BATTLE_LEN;    lp = MUS_BATTLE_LOOP;    break;
    default:            sc = MUS_VICTORY;   len = MUS_VICTORY_LEN;   lp = MUS_VICTORY_LOOP;   break;
  }
  g_musicOn = false;
  g_score = sc; g_scoreLen = len; g_loopMs = lp; g_loop = loop;
  g_startSample = g_global;
  g_musicOn = true;
}

void stopMusic() { g_musicOn = false; }

void setVolume(uint8_t pct) { if (pct > 100) pct = 100; g_volPct = pct; g_volF = pct / 100.0f; }
uint8_t volume() { return g_volPct; }

void sfx(SfxId s) {
  if (!g_ok) return;
  const int16_t* p; uint32_t n;
  switch (s) {
    case SFX_CLAW_ID:    p = SFX_CLAW;    n = SFX_CLAW_LEN;    break;
    case SFX_CHARGED_ID: p = SFX_CHARGED; n = SFX_CHARGED_LEN; break;
    default:             p = SFX_FULL;    n = SFX_FULL_LEN;    break;
  }
  g_sfxOn = false;
  g_sfx = p; g_sfxLen = n; g_sfxPos = 0;
  g_sfxOn = true;
}

}  // namespace audio
