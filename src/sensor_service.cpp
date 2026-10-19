#include "sensor_service.h"

#include "app_state.h"
#include "board_config.h"

#include <Arduino.h>
#include <SensirionCore.h>
#include <Wire.h>

namespace {
constexpr uint8_t kMaxFailures = 5;
constexpr uint32_t kPollIntervalMs = 1000;
constexpr uint32_t kRestartIntervalMs = 10000;
constexpr uint32_t kWarmupDurationMs = 10000;
char errorMessage[64];
}  // namespace

void SensorService::begin() {
    Wire.begin(SCD41_SDA_PIN, SCD41_SCL_PIN, SCD41_I2C_FREQUENCY_HZ);
    delay(1000);
    active_ = startSensor();
}

bool SensorService::isPresent() {
    Wire.beginTransmission(SCD41_I2C_ADDR_62);
    return Wire.endTransmission() == 0;
}

bool SensorService::startSensor() {
    lastStartAttemptMs_ = millis();
    gSensor.detected = isPresent();
    gSensor.ready = false;

    if (!gSensor.detected) {
        gSensor.fault = true;
        Serial.println("[SCD41] Not found at address 0x62. Check the four wires.");
        return false;
    }

    sensor_.begin(Wire, SCD41_I2C_ADDR_62);
    sensor_.wakeUp();
    sensor_.stopPeriodicMeasurement();

    int16_t error = sensor_.reinit();
    if (error != 0) {
        recordFailure("reinit", error);
        return false;
    }

    uint64_t serialNumber = 0;
    error = sensor_.getSerialNumber(serialNumber);
    if (error != 0) {
        recordFailure("getSerialNumber", error);
        return false;
    }

    error = sensor_.startPeriodicMeasurement();
    if (error != 0) {
        recordFailure("startPeriodicMeasurement", error);
        return false;
    }
    measurementStartedMs_ = millis();

    Serial.printf("[SCD41] Ready. Serial: %08lX%08lX\n",
                  static_cast<unsigned long>(serialNumber >> 32),
                  static_cast<unsigned long>(serialNumber & 0xFFFFFFFF));
    consecutiveFailures_ = 0;
    gSensor.fault = false;
    return true;
}

void SensorService::recordFailure(const char* operation, int16_t error) {
    errorToString(error, errorMessage, sizeof(errorMessage));
    Serial.printf("[SCD41] %s failed: %s (%d)\n", operation, errorMessage,
                  error);

    if (consecutiveFailures_ < 255) ++consecutiveFailures_;
    if (consecutiveFailures_ >= kMaxFailures) {
        gSensor.fault = true;
        gSensor.ready = false;
        active_ = false;
        lastStartAttemptMs_ = millis();
        Serial.println("[SCD41] Paused after repeated errors; retrying in 10 seconds.");
    }
}

void SensorService::loop() {
    const uint32_t now = millis();
    if (!active_) {
        if (now - lastStartAttemptMs_ >= kRestartIntervalMs) {
            consecutiveFailures_ = 0;
            active_ = startSensor();
        }
        return;
    }

    if (now - lastPollMs_ < kPollIntervalMs) return;
    lastPollMs_ = now;

    bool dataReady = false;
    int16_t error = sensor_.getDataReadyStatus(dataReady);
    if (error != 0) {
        recordFailure("getDataReadyStatus", error);
        return;
    }
    if (!dataReady) return;

    uint16_t co2Ppm = 0;
    float temperatureC = 0.0F;
    float humidityRh = 0.0F;
    error = sensor_.readMeasurement(co2Ppm, temperatureC, humidityRh);
    if (error != 0) {
        recordFailure("readMeasurement", error);
        return;
    }

    consecutiveFailures_ = 0;
    gSensor.co2Ppm = co2Ppm;
    gSensor.temperatureC = temperatureC;
    gSensor.humidityRh = humidityRh;
    gSensor.updatedAtMs = now;
    // Keep the public sensor state in WARMING UP for at least 10 seconds,
    // even if the SCD41 reports its first sample earlier.
    gSensor.ready = co2Ppm > 0 &&
                    now - measurementStartedMs_ >= kWarmupDurationMs;
    gSensor.fault = false;

    Serial.printf("[SCD41] CO2 %u ppm | %.2f C | %.1f %%RH\n", co2Ppm,
                  temperatureC, humidityRh);
}
