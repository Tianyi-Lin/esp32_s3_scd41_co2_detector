#include "status_led.h"

#include "air_quality.h"
#include "app_state.h"
#include "board_config.h"
#include <esp_arduino_version.h>

#include <Arduino.h>
#include <esp32-hal-rgb-led.h>

namespace {
void writePixel(uint8_t pin, uint8_t red, uint8_t green, uint8_t blue) {
#if ESP_ARDUINO_VERSION_MAJOR >= 3
    rgbLedWrite(pin, red, green, blue);
#else
    neopixelWrite(pin, red, green, blue);
#endif
}
}  // namespace

void StatusLed::begin() {
    // A visible power-on test makes wiring/driver faults unambiguous. After
    // red, green, and blue, the normal CO2 status color takes over.
    constexpr Rgb kSelfTestRed{255, 0, 0};
    constexpr Rgb kSelfTestGreen{0, 255, 0};
    constexpr Rgb kSelfTestPureBlue{0, 0, 255};

    writeColor(kSelfTestRed);
    delay(350);
    writeColor(kSelfTestGreen);
    delay(350);
    writeColor(kSelfTestPureBlue);
    delay(350);
    writeColor({0, 0, 0});
    Serial.println("[RGB] Self-test complete: RED > GREEN > BLUE.");
}

StatusLed::Rgb StatusLed::targetColor() const {
    if (gNightMode.active) return {0, 0, 0};
    if (gSensor.fault) {
        return {kSensorFaultColor.r, kSensorFaultColor.g,
                kSensorFaultColor.b};
    }
    if (!gSensor.ready) {
        return {kSensorWarmupLedColor.r, kSensorWarmupLedColor.g,
                kSensorWarmupLedColor.b};
    }
    if (gAirQualityColors.previewLed) {
        const RgbColor& preview =
            gAirQualityColors.ledEdit[gAirQualityColors.previewBand];
        return {preview.r, preview.g, preview.b};
    }

    const AirQualityLevel level = airQualityLevel(gSensor.co2Ppm);
    const RgbColor& color =
        gAirQualityColors.ledSaved[static_cast<uint8_t>(level)];
    return {color.r, color.g, color.b};
}

int8_t StatusLed::currentMode() const {
    if (gNightMode.active) return 6;
    if (gSensor.fault) return 5;
    if (!gSensor.ready) return 4;
    return static_cast<int8_t>(airQualityLevel(gSensor.co2Ppm));
}

const char* StatusLed::modeLabel(int8_t mode) const {
    switch (mode) {
        case 0:
            return "GREEN / FRESH";
        case 1:
            return "ORANGE / VENTILATE";
        case 2:
            return "RED / HIGH CO2";
        case 4:
            return "BLUE / WARMING UP";
        case 5:
            return "PURPLE / SENSOR FAULT";
        case 6:
            return "OFF / NIGHT MODE";
        default:
            return "UNKNOWN";
    }
}

void StatusLed::writeColor(const Rgb& color) const {
    const uint8_t red = static_cast<uint16_t>(color.r) *
                        RGB_LED_BRIGHTNESS / 255;
    const uint8_t green = static_cast<uint16_t>(color.g) *
                          RGB_LED_BRIGHTNESS / 255;
    const uint8_t blue = static_cast<uint16_t>(color.b) *
                         RGB_LED_BRIGHTNESS / 255;
    // neopixelWrite() takes logical RGB values.  The optional swap exists only
    // for board variants whose fitted pixel has a non-standard channel order.
    if (RGB_LED_SWAP_RED_GREEN) {
        writePixel(RGB_LED_PIN, green, red, blue);
    } else {
        writePixel(RGB_LED_PIN, red, green, blue);
    }
}

void StatusLed::loop() {
    const int8_t mode = currentMode();
    if (mode != lastMode_) {
        Serial.printf("[RGB] %s | CO2 %u ppm\n", modeLabel(mode),
                      gSensor.co2Ppm);
        lastMode_ = mode;
    }

    const Rgb target = targetColor();
    if (target.r == current_.r && target.g == current_.g &&
        target.b == current_.b) {
        return;
    }

    // The LCD uses this same discrete palette.  Apply it immediately so the
    // status LED never passes through an intermediate mixed color (for
    // example cyan while changing from warm-up blue to healthy green).
    current_ = target;
    writeColor(current_);
}
