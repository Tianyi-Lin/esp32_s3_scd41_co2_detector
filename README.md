# ESP32-S3 SCD41 CO₂ Detector

An ESP32-S3 adaptation inspired by the architecture of
[AuraNode](https://github.com/gtxzsxxk/auranode), rewritten for the Waveshare
ESP32-S3-LCD-1.47B and its built-in 172 x 320 ST7789 color display.

This project is a new Arduino/PlatformIO implementation. It does not copy the
reference repository's ESP32-C3 pin map, SH1106 display driver, build files, or
source code.

## Current features

- Reads CO2, temperature, and humidity from a Sensirion SCD41.
- Retries automatically after sensor wiring or communication errors.
- Shows card-based AQI, Network, System, and History pages on the built-in LCD,
  with NTP-synchronized Beijing time in every page's top bar.
- Uses an off-screen frame buffer to eliminate full-screen redraw flicker.
- Changes pages with a short press of the on-board **BOOT** key (GPIO0).
- Supports an automatic night mode, scheduled for 22:00–09:00 Beijing time by
  default. Night mode turns the RGB LED off and lowers the LCD backlight to its
  minimum setting. Double-press **BOOT** to switch it manually until the next
  scheduled start/end boundary.
- Clears the saved home Wi-Fi after BOOT is held for 4 seconds, immediately
  reopening the setup hotspot while leaving the sensor running.
- Drives the on-board RGB LED on GPIO38 from the live CO2 level, using the
  same three-band scale as the LCD number: green below 800 ppm, orange from
  800 to 1499 ppm, and red at 1500 ppm or higher. All three physical LED
  colors and all three LCD colors are configured independently from the web
  dashboard. Startup sensor warm-up lasts at least 10 seconds and holds the
  physical RGB LED at pure blue (`#0000FF`); purple indicates a sensor fault.
- Runs a red → green → blue RGB self-test at every startup so the on-board
  light can be checked independently of the current CO2 level.
- Adds a fourth LCD page with a 60-point rolling CO2 waveform. Sampling starts
  at one second per point, compacts adjacent samples as the buffer fills, and
  grows to one minute per point for approximately one hour of history.
- Starts a local Wi-Fi setup hotspot, disables it after home Wi-Fi connects,
  and restores it if the home connection is unavailable for 30 seconds.
- Serves a responsive live dashboard at `http://192.168.4.1`.
- Saves an optional 2.4 GHz Wi-Fi network in the ESP32's preferences storage.
- Provides JSON sensor data at `/api/data`.
- Provides R/G/B web sliders with live hardware preview and persistent storage
  for separate physical-LED and LCD palettes across all three CO2 bands.

MQTT and HTTPS are intentionally left for a later step. Home Assistant can
read the current measurements from the local HTTP JSON endpoint at `/api/data`
without requiring an MQTT broker.

## Display orientation

The LCD uses landscape rotation `3`, which is 180 degrees from the original
rotation `1`. The value is defined by `LCD_ROTATION` in
[`src/board_config.h`](src/board_config.h) and used when the display is initialized.

## 3D enclosure models and source

[`3d_models/`](3d_models/) contains the saved FreeCAD projects, editable sketch
and feature models, STEP/STL exports, assembly checks, and exploded views.
[`3d_models/scripts/`](3d_models/scripts/) contains the Python modeling source,
geometry helpers, historical repair/check scripts, and a FreeCAD macro.

See the [model version guide](3d_models/README.md) before editing or printing.
The [latest enclosure candidate](3d_models/盖板2.5mm_中壳加深_20261028/) uses
2.5 mm front and rear cover plates, without a deep rear skirt; additional depth
is carried by the middle shell while retaining the 20 mm PCB-to-PCB gap.
The outward-facing SCD41 rear cover is an **unfinished preview**: enclosure
thickness and actual cable/connector clearance still need review. Modeling
scripts retain their original local paths and may overwrite models; read the
[script notes](3d_models/scripts/README.md) and work on copies before running them.

## SCD41 wiring

Disconnect USB power before changing wires. Hold the Waveshare board with its
USB-C connector at the top and use the labeled pins on the left header:

| SCD41 pin | ESP32-S3-LCD-1.47B pin |
|---|---|
| VCC / VIN | 3V3(OUT) |
| GND | GND |
| SDA | GP4 |
| SCL | GP5 |

Use **3V3(OUT)**, not 5V and not VBAT. The SCD41 I2C address is `0x62`.

## Build and upload in VS Code

1. Open this folder in VS Code.
2. Wait until PlatformIO has finished preparing the project.
3. With USB disconnected, finish the four sensor wires shown above.
4. Reconnect the board using a USB data cable.
5. Use PlatformIO **Upload**, then open **Serial Monitor** at 115200 baud.

At startup the display shows a hotspot similar to `AuraNode-S3-1A2B` and an
eight-character password similar to `AURA1A2B`. Connect a phone or computer to
that hotspot and open `http://192.168.4.1`.

The dashboard includes a **three-band color configuration** card. Each CO2
band has separate R/G/B sliders for the physical RGB LED and for the LCD.
Moving an LED slider previews that color on the on-board LED; moving an LCD
slider previews it on the Air Quality screen. Select **Save all colors** to
keep the complete palette across restarts, or **Cancel all previews** to
restore the last saved palette. When the board is connected to home Wi-Fi,
the same page is available at the LAN address shown on the Network/System
screen.

The dashboard also includes a **Night Mode** card. It can enable or disable
the automatic schedule and set separate start/end times. The default is
22:00–09:00 Beijing time, including schedules that cross midnight. The saved
schedule persists across restarts. Internet access is needed initially to
synchronize the clock; the manual BOOT-key toggle continues to work even when
the clock has not synchronized.

The hotspot turns off after the device connects to the saved home Wi-Fi. If
that connection is unavailable for 30 seconds, the hotspot returns
automatically. Holding BOOT for 4 seconds also restores it immediately.

## Page button

After the board has started, briefly press and release the on-board **BOOT** key
to move to the next page. The sequence is AQI → Network → System → History →
AQI. A single press is applied after a short delay so the
firmware can distinguish it from a double press. Double-press BOOT to turn night
mode on or off manually. The manual choice lasts until the next configured
automatic start/end boundary. Hold BOOT for 4 seconds to forget the saved home
Wi-Fi and return to setup mode. This does not reboot the board; the setup hotspot
remains active.

Do not keep BOOT held while resetting or reconnecting USB: GPIO0 is also the
ESP32-S3 boot strap pin and holding it during reset selects download mode.

## 致谢 / Acknowledgements

本项目的早期设计思路与功能规划参考了
[AuraNode](https://github.com/gtxzsxxk/auranode#%E5%8C%85%E8%A3%85%E6%B8%85%E5%8D%95--whats-in-the-box)。
感谢 [@gtxzsxxk](https://github.com/gtxzsxxk) 开源 AuraNode 项目及其详细文档，
为 SCD41 空气质量监测、Wi-Fi 配网、网页控制台和多页面显示等功能提供了重要启发。

This project was inspired by the ideas and feature design of
[AuraNode](https://github.com/gtxzsxxk/auranode). Special thanks to
[@gtxzsxxk](https://github.com/gtxzsxxk) for publishing the project and its
detailed documentation. This firmware is an independent implementation for the
Waveshare ESP32-S3-LCD-1.47B hardware.
