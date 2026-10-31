# Changelog

## 2026-10-31

Changes from the original checkout at `96e1df8`:

- Move the external SCD41 I2C wiring from SDA GPIO4 / SCL GPIO5 to
  **SDA GPIO5 / SCL GPIO6**. Update the README wiring table and the LCD
  sensor-fault wiring hint to match. Power remains 3V3(OUT) and GND.
- Support Arduino-ESP32 3.x backlight PWM using `ledcAttach()` and
  pin-based `ledcWrite()`, including day/night brightness changes and an
  initialization failure check. Retain the Arduino-ESP32 2.x API branch.
- Upgrade GFX Library for Arduino from 1.5.9 to 1.6.9 because the old
  library failed to compile against the installed Arduino-ESP32 3.3.12
  SPI API.
- Use `rgbLedWrite()` on Arduino-ESP32 3.x to replace deprecated
  `neopixelWrite()`, retaining the existing red/green correction and the
  older-framework branch.
- Increase the LCD and web API clock-string buffers from 6 to 12 bytes
  to eliminate the compiler's format-truncation warnings.

### Validation

- `pio run`: passed with PlatformIO Espressif32 8.0.0,
  Arduino-ESP32 3.3.12, GFX Library for Arduino 1.6.9, and
  Sensirion I2C SCD4x 1.1.0. Arduino-ESP32 2.x was not rebuilt.
- `pio run -t upload`: passed on the connected ESP32-S3 through
  `/dev/cu.usbmodem101`; flash data hash verified and the board reset.
- Sensor readings, LCD output, and day/night brightness still require
  observation on the physical device after rewiring.

The GFX download from the PlatformIO mirror was interrupted. The same
1.6.9 release was downloaded from the upstream GitHub release tag and
installed locally; `platformio.ini` keeps the registry dependency so
other checkouts do not depend on a local archive path.
