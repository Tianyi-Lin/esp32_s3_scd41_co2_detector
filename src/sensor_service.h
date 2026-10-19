#pragma once

#include <SensirionI2cScd4x.h>

class SensorService {
  public:
    void begin();
    void loop();

  private:
    SensirionI2cScd4x sensor_;
    uint32_t lastPollMs_ = 0;
    uint32_t lastStartAttemptMs_ = 0;
    uint32_t measurementStartedMs_ = 0;
    uint8_t consecutiveFailures_ = 0;
    bool active_ = false;

    bool startSensor();
    bool isPresent();
    void recordFailure(const char* operation, int16_t error);
};
