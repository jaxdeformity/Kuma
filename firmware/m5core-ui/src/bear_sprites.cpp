// KUMA Guard M5Core — pixel bear sprite data (SKELETON / placeholder).
//
// Sprint 2: define small RGB565 bitmaps per BearState and blit them with
// M5.Display.pushImage(x, y, w, h, data). For flicker-free animation use an
// off-screen M5Canvas (LovyanGFX sprite) and push the whole frame at once.
//
// Keeping the art crude is intentional (see the brief): the pipeline matters
// more than the bear. One frame per mood is enough for v0.0.
#include <Arduino.h>

// Example placeholder: a 2x2 RGB565 swatch. Real frames replace this.
const uint16_t BEAR_PLACEHOLDER_16x16[] = {
    // TODO(sprint2): 16x16 (or 32x32) RGB565 frames for sleeping / foraging /
    // suspicious / alert / honey_trap / apex_ready / logging / error.
    0x07FF, 0x07FF,
    0x07FF, 0x07FF,
};
