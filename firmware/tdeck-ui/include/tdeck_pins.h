// KUMA Guard - LilyGo T-Deck pin map.
// Source: Xinyuan-LilyGO/T-Deck examples/UnitTest/utilities.h
#pragma once

// Master power-enable: MUST be driven HIGH at boot or the display, keyboard,
// radio and SD stay unpowered.
#define TDECK_POWERON       10

// Shared SPI bus (display + SD + LoRa)
#define TDECK_SPI_MOSI      41
#define TDECK_SPI_MISO      38
#define TDECK_SPI_SCK       40

// ST7789 display (320x240 landscape)
#define TDECK_TFT_CS        12
#define TDECK_TFT_DC        11
#define TDECK_TFT_BL        42

// I2C bus (keyboard + touch)
#define TDECK_I2C_SDA       18
#define TDECK_I2C_SCL       8
#define TDECK_KEYBOARD_INT  46
#define TDECK_KEYBOARD_ADDR 0x55   // ESP32-C3 keyboard co-processor

// Trackball (active-low pulses)
#define TDECK_TB_UP         3
#define TDECK_TB_DOWN       15
#define TDECK_TB_LEFT       1
#define TDECK_TB_RIGHT      2
#define TDECK_TB_CLICK      0      // shared with BOOT

// I2S audio (MAX98357A amp -> speaker). LilyGo T-Deck reference pins.
#define TDECK_I2S_BCK       7
#define TDECK_I2S_WS        5
#define TDECK_I2S_DOUT      6

// Misc
#define TDECK_SDCARD_CS     39
#define TDECK_BAT_ADC       4
#define TDECK_BL_PIN        42
