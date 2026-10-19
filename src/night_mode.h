#pragma once

#include <Arduino.h>

class NightModeService {
  public:
    void begin();
    void loop();
    void toggleManual();

  private:
    uint32_t lastRefreshMs_ = 0;
    uint16_t cachedStartMinute_ = 0;
    uint16_t cachedEndMinute_ = 0;
    bool cachedScheduleEnabled_ = false;
    bool hadValidSchedule_ = false;
    bool lastScheduledActive_ = false;
    bool lastReportedActive_ = false;
    bool reportInitialized_ = false;

    void refresh(bool force = false);
    bool isScheduledNight(uint16_t minute) const;
};
