#pragma once

// Waveshare ESP32-S3-LCD-1.47B built-in ST7789 display.
constexpr int LCD_MOSI_PIN = 45;
constexpr int LCD_SCLK_PIN = 40;
constexpr int LCD_CS_PIN = 42;
constexpr int LCD_DC_PIN = 41;
constexpr int LCD_RST_PIN = 39;
constexpr int LCD_BACKLIGHT_PIN = 46;
constexpr int LCD_WIDTH = 172;
constexpr int LCD_HEIGHT = 320;
constexpr int LCD_COLUMN_OFFSET = 34;
// Landscape, rotated 180 degrees from the original orientation (1).
constexpr uint8_t LCD_ROTATION = 3;
constexpr uint8_t LCD_BACKLIGHT_PWM_CHANNEL = 0;
constexpr uint32_t LCD_BACKLIGHT_PWM_HZ = 5000;
constexpr uint8_t LCD_DAY_BRIGHTNESS = 255;
// Lowest reliably visible duty cycle on the MOSFET-driven LCD backlight.
constexpr uint8_t LCD_NIGHT_BRIGHTNESS = 8;

// One addressable WS2812-compatible RGB LED is mounted behind the acrylic
// light guide. Waveshare documents its data input on GPIO38.
constexpr int RGB_LED_PIN = 38;
constexpr uint8_t RGB_LED_BRIGHTNESS = 96;
// This board's fitted pixel/driver combination presents red and green in the
// opposite order to neopixelWrite().  Swap them at the hardware boundary so
// the rest of the application can keep using ordinary logical RGB values.
// The startup self-test must be seen as RED -> GREEN -> BLUE.
constexpr bool RGB_LED_SWAP_RED_GREEN = true;

// The on-board BOOT key is active-low on GPIO0. It is only a boot strap while
// resetting; after startup it is safe to use as the page button.
constexpr int PAGE_BUTTON_PIN = 0;

// The board routes the Li-ion battery node through a 200K/100K divider to
// GPIO1. The ADC therefore sees one third of the actual battery voltage.
constexpr int BATTERY_ADC_PIN = 1;
constexpr float BATTERY_ADC_DIVIDER = 3.0f;

// External SCD41 bus on the exposed left-side header.
constexpr int SCD41_SDA_PIN = 5;
constexpr int SCD41_SCL_PIN = 6;
constexpr uint32_t SCD41_I2C_FREQUENCY_HZ = 100000;
