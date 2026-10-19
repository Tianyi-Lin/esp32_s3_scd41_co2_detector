#pragma once

#include <Arduino.h>

struct SensorSnapshot {
    uint16_t co2Ppm = 0;
    float temperatureC = 0.0F;
    float humidityRh = 0.0F;
    uint32_t updatedAtMs = 0;
    bool detected = false;
    bool ready = false;
    bool fault = false;
};

struct NetworkSnapshot {
    String apSsid;
    String apPassword;
    String apIp;
    String staSsid;
    String staIp;
    int32_t rssi = 0;
    bool apActive = false;
    bool staConnected = false;
};

struct RgbColor {
    uint8_t r;
    uint8_t g;
    uint8_t b;
};

struct AirQualityColorSettings {
    RgbColor ledSaved[3] = {
        {0, 255, 0}, {255, 140, 0}, {255, 0, 0}};
    RgbColor ledEdit[3] = {
        {0, 255, 0}, {255, 140, 0}, {255, 0, 0}};
    RgbColor displaySaved[3] = {
        {0, 255, 0}, {255, 153, 28}, {255, 0, 0}};
    RgbColor displayEdit[3] = {
        {0, 255, 0}, {255, 153, 28}, {255, 0, 0}};
    uint8_t previewBand = 0;
    bool previewLed = false;
    bool previewDisplay = false;
};

struct NightModeState {
    bool scheduleEnabled = true;
    uint16_t startMinute = 22 * 60;
    uint16_t endMinute = 9 * 60;
    bool timeValid = false;
    uint16_t localMinute = 0;
    bool scheduledActive = false;
    bool manualOverride = false;
    bool manualTarget = false;
    bool active = false;
};

extern SensorSnapshot gSensor;
extern NetworkSnapshot gNetwork;
extern AirQualityColorSettings gAirQualityColors;
extern NightModeState gNightMode;
