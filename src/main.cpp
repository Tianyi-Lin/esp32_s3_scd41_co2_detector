#include "app_state.h"
#include "display_ui.h"
#include "night_mode.h"
#include "sensor_service.h"
#include "status_led.h"
#include "web_portal.h"

#include <Arduino.h>

SensorSnapshot gSensor;
NetworkSnapshot gNetwork;
AirQualityColorSettings gAirQualityColors;
NightModeState gNightMode;

SensorService sensorService;
DisplayUi displayUi;
WebPortal webPortal;
StatusLed statusLed;
NightModeService nightModeService;

void setup() {
    Serial.begin(115200);
    delay(1200);
    Serial.println();
    Serial.println("AuraNode S3 prototype starting");

    displayUi.begin();
    statusLed.begin();
    webPortal.begin();
    nightModeService.begin();
    sensorService.begin();
}

void loop() {
    sensorService.loop();
    webPortal.loop();
    nightModeService.loop();
    statusLed.loop();
    displayUi.loop();
    if (displayUi.consumeNightModeToggleRequest()) {
        nightModeService.toggleManual();
    }
    if (displayUi.consumeNetworkResetRequest()) {
        webPortal.clearSavedWifi();
    }
    delay(2);
}
