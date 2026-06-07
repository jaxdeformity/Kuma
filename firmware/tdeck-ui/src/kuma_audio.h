// KUMA Guard T-Deck - I2S audio: looping chiptune + attack SFX (MAX98357A).
#pragma once
#include <Arduino.h>

namespace audio {
  enum Track { TRK_ENCOUNTER, TRK_BATTLE, TRK_VICTORY };
  enum SfxId { SFX_CLAW_ID, SFX_CHARGED_ID, SFX_FULL_ID };

  void begin();                         // init I2S + mixer task (no-op on failure)
  void playTrack(Track t, bool loop);   // start/replace the music bed
  void stopMusic();                     // silence the music bed
  void sfx(SfxId s);                    // fire a one-shot attack sound over the music
  bool ok();                            // true if I2S came up
}
