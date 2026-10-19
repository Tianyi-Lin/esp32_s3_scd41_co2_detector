#pragma once

#include <Arduino.h>

enum class AirQualityLevel : uint8_t {
    Good,
    Ventilate,
    Poor,
};

struct AirQualityRgb {
    uint8_t r;
    uint8_t g;
    uint8_t b;
};

// Logical RGB colors for the physical status LED. The LCD uses a brighter
// orange for the warning band because the two light sources render the same
// RGB value differently.
// Good air should be unmistakably green on both the LCD and the status LED.
// Keeping the red and blue channels at zero avoids the previous cyan tint.
constexpr AirQualityRgb kAirGoodColor{0, 255, 0};
// RGB LED warning orange: #FF8C00. The stronger green component keeps the
// warning band visibly orange instead of looking like a dimmer version of red.
constexpr AirQualityRgb kAirVentilateColor{255, 140, 0};
constexpr AirQualityRgb kAirPoorColor{255, 0, 0};
// Physical RGB LED during the startup sensor warm-up: pure blue #0000FF.
constexpr AirQualityRgb kSensorWarmupLedColor{0, 0, 255};
// A lighter blue remains more legible on the LCD's dark background.
constexpr AirQualityRgb kSensorWarmupColor{75, 157, 255};
constexpr AirQualityRgb kSensorFaultColor{187, 104, 255};

inline AirQualityLevel airQualityLevel(uint16_t co2Ppm) {
    if (co2Ppm < 800) return AirQualityLevel::Good;
    if (co2Ppm < 1500) return AirQualityLevel::Ventilate;
    return AirQualityLevel::Poor;
}

inline AirQualityRgb airQualityColor(AirQualityLevel level) {
    switch (level) {
        case AirQualityLevel::Good:
            return kAirGoodColor;
        case AirQualityLevel::Ventilate:
            return kAirVentilateColor;
        case AirQualityLevel::Poor:
            return kAirPoorColor;
    }
    return {0, 0, 0};
}

inline const char* airQualityLabel(AirQualityLevel level) {
    switch (level) {
        case AirQualityLevel::Good:
            return "FRESH";
        case AirQualityLevel::Ventilate:
            return "VENTILATE";
        case AirQualityLevel::Poor:
            return "HIGH CO2";
    }
    return "--";
}
