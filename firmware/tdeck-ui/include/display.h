// KUMA Guard T-Deck - LovyanGFX display driver for the ST7789 panel.
// Config matches the T-Deck's shared-SPI wiring (see tdeck_pins.h).
#pragma once

#define LGFX_USE_V1
#include <LovyanGFX.hpp>
#include "tdeck_pins.h"

class LGFX_TDeck : public lgfx::LGFX_Device {
  lgfx::Panel_ST7789 _panel;
  lgfx::Bus_SPI      _bus;
  lgfx::Light_PWM    _light;

public:
  LGFX_TDeck() {
    {
      auto c = _bus.config();
      c.spi_host    = SPI3_HOST;     // T-Deck shares the VSPI/SPI3 bus
      c.spi_mode    = 0;
      c.freq_write  = 40000000;
      c.freq_read   = 16000000;
      c.pin_sclk    = TDECK_SPI_SCK;
      c.pin_mosi    = TDECK_SPI_MOSI;
      c.pin_miso    = TDECK_SPI_MISO;
      c.pin_dc      = TDECK_TFT_DC;
      _bus.config(c);
      _panel.setBus(&_bus);
    }
    {
      auto c = _panel.config();
      c.pin_cs        = TDECK_TFT_CS;
      c.pin_rst       = -1;
      c.pin_busy      = -1;
      c.panel_width   = 240;
      c.panel_height  = 320;
      c.offset_x      = 0;
      c.offset_y      = 0;
      c.readable      = false;
      c.invert        = true;     // ST7789 on the T-Deck wants inversion on
      c.rgb_order     = false;
      c.dlen_16bit    = false;
      c.bus_shared    = true;     // SD + LoRa share this SPI bus
      _panel.config(c);
    }
    {
      auto c = _light.config();
      c.pin_bl      = TDECK_TFT_BL;
      c.freq        = 12000;
      c.pwm_channel = 7;
      _light.config(c);
      _panel.setLight(&_light);
    }
    setPanel(&_panel);
  }
};
