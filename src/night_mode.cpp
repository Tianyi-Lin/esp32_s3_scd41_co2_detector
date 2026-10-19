#include "night_mode.h"

#include "app_state.h"

#include <time.h>

namespace {
constexpr long kUtcOffsetSeconds = 8L * 60L * 60L;
constexpr uint32_t kRefreshMs = 1000;
}  // namespace

void NightModeService::begin() {
    cachedScheduleEnabled_ = gNightMode.scheduleEnabled;
    cachedStartMinute_ = gNightMode.startMinute;
    cachedEndMinute_ = gNightMode.endMinute;
    configTime(kUtcOffsetSeconds, 0, "pool.ntp.org", "time.nist.gov",
               "time.google.com");
    refresh(true);
    Serial.println("[NIGHT] Beijing time sync started (UTC+8).");
}

bool NightModeService::isScheduledNight(uint16_t minute) const {
    if (!gNightMode.scheduleEnabled ||
        gNightMode.startMinute == gNightMode.endMinute) {
        return false;
    }
    if (gNightMode.startMinute < gNightMode.endMinute) {
        return minute >= gNightMode.startMinute &&
               minute < gNightMode.endMinute;
    }
    return minute >= gNightMode.startMinute ||
           minute < gNightMode.endMinute;
}

void NightModeService::refresh(bool force) {
    const uint32_t now = millis();
    if (!force && now - lastRefreshMs_ < kRefreshMs) return;
    lastRefreshMs_ = now;

    const bool configChanged =
        cachedScheduleEnabled_ != gNightMode.scheduleEnabled ||
        cachedStartMinute_ != gNightMode.startMinute ||
        cachedEndMinute_ != gNightMode.endMinute;
    if (configChanged) {
        cachedScheduleEnabled_ = gNightMode.scheduleEnabled;
        cachedStartMinute_ = gNightMode.startMinute;
        cachedEndMinute_ = gNightMode.endMinute;
        gNightMode.manualOverride = false;
        hadValidSchedule_ = false;
    }

    struct tm timeInfo;
    gNightMode.timeValid = getLocalTime(&timeInfo, 10);
    bool scheduled = false;
    if (gNightMode.timeValid) {
        gNightMode.localMinute =
            static_cast<uint16_t>(timeInfo.tm_hour * 60 + timeInfo.tm_min);
        scheduled = isScheduledNight(gNightMode.localMinute);
        if (hadValidSchedule_ && scheduled != lastScheduledActive_) {
            // A manual choice lasts only until the next automatic boundary.
            gNightMode.manualOverride = false;
        }
        lastScheduledActive_ = scheduled;
        hadValidSchedule_ = true;
    } else {
        gNightMode.localMinute = 0;
        hadValidSchedule_ = false;
    }

    gNightMode.scheduledActive = scheduled;
    gNightMode.active = gNightMode.manualOverride
                            ? gNightMode.manualTarget
                            : gNightMode.scheduledActive;

    if (!reportInitialized_ || lastReportedActive_ != gNightMode.active) {
        reportInitialized_ = true;
        lastReportedActive_ = gNightMode.active;
        Serial.printf("[NIGHT] %s (%s).\n",
                      gNightMode.active ? "ACTIVE" : "INACTIVE",
                      gNightMode.manualOverride
                          ? "manual override"
                          : (gNightMode.timeValid ? "automatic schedule"
                                                  : "waiting for time"));
    }
}

void NightModeService::loop() { refresh(false); }

void NightModeService::toggleManual() {
    refresh(true);
    gNightMode.manualOverride = true;
    gNightMode.manualTarget = !gNightMode.active;
    gNightMode.active = gNightMode.manualTarget;
    lastReportedActive_ = gNightMode.active;
    reportInitialized_ = true;
    Serial.printf("[NIGHT] Manual override: %s until next schedule boundary.\n",
                  gNightMode.active ? "ACTIVE" : "INACTIVE");
}
