#include "display_ui.h"

#include "air_quality.h"
#include "app_state.h"
#include "board_config.h"

#include <Arduino.h>

namespace {
constexpr uint16_t rgb565(uint8_t r, uint8_t g, uint8_t b) {
    return static_cast<uint16_t>(((r & 0xF8) << 8) |
                                 ((g & 0xFC) << 3) | (b >> 3));
}

constexpr uint16_t kBackground = rgb565(2, 7, 15);
constexpr uint16_t kTopBar = rgb565(5, 16, 29);
constexpr uint16_t kPanel = rgb565(7, 20, 35);
constexpr uint16_t kPanelEdge = rgb565(24, 65, 85);
constexpr uint16_t kGrid = rgb565(6, 27, 42);
constexpr uint16_t kNeonCyan = rgb565(0, 222, 255);
constexpr uint16_t kNeonPink = rgb565(255, 43, 166);
constexpr uint16_t kDimCyan = rgb565(8, 72, 88);
constexpr uint16_t kWhite = rgb565(238, 246, 255);
constexpr uint16_t kMuted = rgb565(126, 165, 184);
constexpr uint16_t kBlue = rgb565(kSensorWarmupColor.r,
                                  kSensorWarmupColor.g,
                                  kSensorWarmupColor.b);
constexpr uint16_t kGreen = rgb565(kAirGoodColor.r, kAirGoodColor.g,
                                   kAirGoodColor.b);
// The LCD needs a lighter warning orange than the physical RGB LED so the
// perceived colors remain clear on their different light sources: #FF991C.
constexpr uint16_t kOrange = rgb565(255, 153, 28);
constexpr uint16_t kRed = rgb565(kAirPoorColor.r, kAirPoorColor.g,
                                 kAirPoorColor.b);
constexpr uint16_t kPurple = rgb565(kSensorFaultColor.r,
                                    kSensorFaultColor.g,
                                    kSensorFaultColor.b);
constexpr uint32_t kRefreshMs = 1000;
constexpr uint32_t kButtonDebounceMs = 35;
constexpr uint32_t kDoubleClickGapMs = 350;
constexpr uint32_t kNetworkResetHoldMs = 4000;
constexpr uint32_t kHistoryMaxIntervalMs = 60000;
}  // namespace

bool DisplayUi::begin() {
    bus_ = new Arduino_HWSPI(LCD_DC_PIN, LCD_CS_PIN, LCD_SCLK_PIN,
                             LCD_MOSI_PIN);
    panel_ = new Arduino_ST7789(bus_, LCD_RST_PIN, LCD_ROTATION, true, LCD_WIDTH,
                               LCD_HEIGHT, LCD_COLUMN_OFFSET, 0,
                               LCD_COLUMN_OFFSET, 0);
    if (bus_ == nullptr || panel_ == nullptr || !panel_->begin(80000000)) {
        Serial.println("[LCD] Initialization failed.");
        return false;
    }

    // Draw into PSRAM first, then transfer one finished frame. The LCD never
    // sees the clear-and-redraw steps, so changing values does not flash.
    canvas_ = new Arduino_Canvas(panel_->width(), panel_->height(), panel_);
    if (canvas_ == nullptr || !canvas_->begin(GFX_SKIP_OUTPUT_BEGIN)) {
        Serial.println("[LCD] Frame buffer allocation failed.");
        return false;
    }
    gfx_ = canvas_;

    // Small scratch canvas used to render the temperature and humidity at
    // 90% of the built-in 3x bitmap font without dropping all the way to 2x.
    metricCanvas_ = new Arduino_Canvas(90, 24, panel_);
    if (metricCanvas_ == nullptr ||
        !metricCanvas_->begin(GFX_SKIP_OUTPUT_BEGIN)) {
        Serial.println("[LCD] Metric buffer allocation failed.");
        return false;
    }

    pinMode(LCD_BACKLIGHT_PIN, OUTPUT);
    ledcSetup(LCD_BACKLIGHT_PWM_CHANNEL, LCD_BACKLIGHT_PWM_HZ, 8);
    ledcAttachPin(LCD_BACKLIGHT_PIN, LCD_BACKLIGHT_PWM_CHANNEL);
    ledcWrite(LCD_BACKLIGHT_PWM_CHANNEL, LCD_DAY_BRIGHTNESS);
    backlightInitialized_ = true;
    pinMode(PAGE_BUTTON_PIN, INPUT_PULLUP);
    pinMode(BATTERY_ADC_PIN, INPUT);
    analogReadResolution(12);
    analogSetPinAttenuation(BATTERY_ADC_PIN, ADC_11db);
    lastButtonReading_ = digitalRead(PAGE_BUTTON_PIN) == LOW;
    stableButtonPressed_ = lastButtonReading_;
    if (stableButtonPressed_) buttonPressedMs_ = millis();
    gfx_->fillScreen(kBackground);
    draw();
    Serial.printf("[LCD] Ready: %d x %d, buffered. BOOT key changes page.\n",
                  gfx_->width(), gfx_->height());
    return true;
}

void DisplayUi::loop() {
    if (gfx_ == nullptr) return;

    const uint32_t now = millis();
    applyBacklightMode();
    recordCo2History(now);
    handleButton(now);
    if (now - lastDrawMs_ >= kRefreshMs) {
        lastDrawMs_ = now;
        draw();
    }
}

void DisplayUi::handleButton(uint32_t now) {
    const bool reading = digitalRead(PAGE_BUTTON_PIN) == LOW;
    if (reading != lastButtonReading_) {
        lastButtonReading_ = reading;
        buttonChangedMs_ = now;
    }

    if (now - buttonChangedMs_ >= kButtonDebounceMs &&
        reading != stableButtonPressed_) {
        stableButtonPressed_ = reading;
        if (stableButtonPressed_) {
            buttonPressedMs_ = now;
            longPressHandled_ = false;
        } else if (!longPressHandled_) {
            if (pendingSingleClick_ &&
                now - lastShortClickMs_ <= kDoubleClickGapMs) {
                pendingSingleClick_ = false;
                nightModeToggleRequested_ = true;
                Serial.println("[KEY] BOOT double-click: toggle night mode.");
            } else {
                if (pendingSingleClick_) nextPage();
                pendingSingleClick_ = true;
                lastShortClickMs_ = now;
            }
        }
    }

    if (stableButtonPressed_ && !longPressHandled_ &&
        now - buttonPressedMs_ >= kNetworkResetHoldMs) {
        longPressHandled_ = true;
        pendingSingleClick_ = false;
        networkResetRequested_ = true;
        page_ = 1;
        lastDrawMs_ = now;
        draw();
        Serial.println("[KEY] BOOT held for 4 seconds: clear saved Wi-Fi.");
    }

    if (pendingSingleClick_ && !stableButtonPressed_ &&
        now - lastShortClickMs_ > kDoubleClickGapMs) {
        pendingSingleClick_ = false;
        nextPage();
    }
}

void DisplayUi::applyBacklightMode() {
    if (!backlightInitialized_ ||
        backlightNightActive_ == gNightMode.active) {
        return;
    }
    backlightNightActive_ = gNightMode.active;
    ledcWrite(LCD_BACKLIGHT_PWM_CHANNEL,
              backlightNightActive_ ? LCD_NIGHT_BRIGHTNESS
                                    : LCD_DAY_BRIGHTNESS);
    Serial.printf("[LCD] Backlight %s.\n",
                  backlightNightActive_ ? "night minimum" : "day full");
}

bool DisplayUi::consumeNetworkResetRequest() {
    if (!networkResetRequested_) return false;
    networkResetRequested_ = false;
    return true;
}

bool DisplayUi::consumeNightModeToggleRequest() {
    if (!nightModeToggleRequested_) return false;
    nightModeToggleRequested_ = false;
    return true;
}

void DisplayUi::nextPage() {
    page_ = (page_ + 1) % 4;
    lastDrawMs_ = millis();
    draw();
    Serial.printf("[KEY] Page %u/4\n", page_ + 1);
}

void DisplayUi::compactCo2History() {
    uint8_t compactedCount = 0;
    for (uint8_t i = 0; i + 1 < co2HistoryCount_; i += 2) {
        co2History_[compactedCount] =
            (static_cast<uint32_t>(co2History_[i]) +
             co2History_[i + 1] + 1) /
            2;
        co2HistoryTimeMs_[compactedCount] =
            co2HistoryTimeMs_[i] +
            (co2HistoryTimeMs_[i + 1] - co2HistoryTimeMs_[i]) / 2;
        ++compactedCount;
    }
    co2HistoryCount_ = compactedCount;
    co2HistoryIntervalMs_ =
        min<uint32_t>(co2HistoryIntervalMs_ * 2,
                      kHistoryMaxIntervalMs);
    Serial.printf("[HISTORY] Compacted to %u points, %lus/point.\n",
                  co2HistoryCount_, co2HistoryIntervalMs_ / 1000UL);
}

void DisplayUi::recordCo2History(uint32_t now) {
    if (!gSensor.ready || gSensor.fault) return;

    if (co2HistoryCount_ == 0) {
        co2History_[0] = gSensor.co2Ppm;
        co2HistoryTimeMs_[0] = now;
        co2HistoryCount_ = 1;
        lastCo2HistorySampleMs_ = now;
        return;
    }

    if (now - lastCo2HistorySampleMs_ < co2HistoryIntervalMs_) return;

    if (co2HistoryCount_ >= kHistoryCapacity &&
        co2HistoryIntervalMs_ < kHistoryMaxIntervalMs) {
        compactCo2History();
        // After changing cadence, wait until a full new interval has elapsed
        // from the most recent raw sample before appending another point.
        if (now - lastCo2HistorySampleMs_ < co2HistoryIntervalMs_) return;
    }

    if (co2HistoryCount_ >= kHistoryCapacity) {
        for (uint8_t i = 1; i < kHistoryCapacity; ++i) {
            co2History_[i - 1] = co2History_[i];
            co2HistoryTimeMs_[i - 1] = co2HistoryTimeMs_[i];
        }
        co2HistoryCount_ = kHistoryCapacity - 1;
    }

    co2History_[co2HistoryCount_] = gSensor.co2Ppm;
    co2HistoryTimeMs_[co2HistoryCount_] = now;
    ++co2HistoryCount_;
    lastCo2HistorySampleMs_ = now;
}

void DisplayUi::drawCenteredIn(const String& text, int16_t x, int16_t y,
                               int16_t w, uint8_t size, uint16_t color) {
    gfx_->setTextSize(size);
    gfx_->setTextColor(color);
    const int16_t width = text.length() * 6 * size;
    gfx_->setCursor(x + max<int16_t>(0, (w - width) / 2), y);
    gfx_->print(text);
}

String DisplayUi::fitText(const String& text, uint8_t maxChars) const {
    if (text.length() <= maxChars) return text;
    if (maxChars < 4) return text.substring(0, maxChars);
    return text.substring(0, maxChars - 3) + "...";
}

float DisplayUi::readBatteryVoltage() {
    // The 100 nF capacitor on BAT_ADC is allowed to settle before averaging.
    // analogReadMilliVolts() applies the ESP32 calibration, then the schematic
    // divider ratio restores the actual battery-node voltage.
    analogReadMilliVolts(BATTERY_ADC_PIN);
    delayMicroseconds(150);
    uint32_t totalMillivolts = 0;
    constexpr uint8_t kSamples = 16;
    for (uint8_t i = 0; i < kSamples; ++i) {
        totalMillivolts += analogReadMilliVolts(BATTERY_ADC_PIN);
        delayMicroseconds(80);
    }
    const float measured =
        (totalMillivolts / static_cast<float>(kSamples)) *
        BATTERY_ADC_DIVIDER / 1000.0f;
    batteryVoltage_ = batteryVoltage_ <= 0.0f
                          ? measured
                          : batteryVoltage_ * 0.7f + measured * 0.3f;
    return batteryVoltage_;
}

void DisplayUi::drawPanel(int16_t x, int16_t y, int16_t w, int16_t h,
                          uint16_t accent) {
    // Slightly clipped-looking corners and segmented neon marks retain the
    // existing card geometry while giving it a restrained cyberpunk skin.
    gfx_->fillRoundRect(x, y, w, h, 5, kPanel);
    gfx_->drawRoundRect(x, y, w, h, 5, kPanelEdge);
    gfx_->drawRoundRect(x + 2, y + 2, w - 4, h - 4, 3, kDimCyan);
    gfx_->fillRect(x, y + 11, 3, h - 22, accent);
    gfx_->drawFastHLine(x + 6, y, 18, accent);
    gfx_->drawFastVLine(x, y + 6, 12, accent);
    gfx_->drawFastHLine(x + w - 24, y + h - 1, 18, kNeonCyan);
    gfx_->drawFastVLine(x + w - 1, y + h - 18, 12, kNeonCyan);
}

void DisplayUi::drawPill(const String& text, int16_t x, int16_t y, int16_t w,
                         uint16_t background, uint16_t foreground) {
    gfx_->fillRoundRect(x, y, w, 17, 3, background);
    gfx_->drawRoundRect(x, y, w, 17, 3, foreground);
    gfx_->drawFastHLine(x + 5, y, min<int16_t>(16, w - 10), foreground);
    drawCenteredIn(text, x, y + 5, w, 1, foreground);
}

void DisplayUi::drawCyberBackground() {
    // A very dark technical grid only appears in the gutters around cards,
    // keeping the data areas clean and high contrast.
    for (int16_t x = 0; x < gfx_->width(); x += 20) {
        gfx_->drawFastVLine(x, 0, gfx_->height(), kGrid);
    }
    for (int16_t y = 0; y < gfx_->height(); y += 16) {
        gfx_->drawFastHLine(0, y, gfx_->width(), kGrid);
    }
    gfx_->drawFastHLine(8, 168, 34, kNeonPink);
    gfx_->drawFastHLine(46, 168, 16, kDimCyan);
    gfx_->drawFastHLine(gfx_->width() - 62, 168, 54, kNeonCyan);
}

int16_t DisplayUi::drawScaledMetric(const String& text, int16_t x, int16_t y,
                                    uint16_t color, bool smallDecimal) {
    constexpr int16_t kSourceHeight = 24;
    constexpr int16_t kTargetHeight = 22;
    constexpr int16_t kScratchWidth = 90;

    const int16_t sourceWidth =
        min<int16_t>(kScratchWidth, text.length() * 18);
    const int16_t targetWidth = (sourceWidth * 9 + 5) / 10;

    metricCanvas_->fillScreen(kPanel);
    metricCanvas_->setTextSize(3);
    metricCanvas_->setTextColor(color);
    metricCanvas_->setCursor(0, 0);
    metricCanvas_->print(text);

    const uint16_t* source = metricCanvas_->getFramebuffer();
    const int16_t decimalIndex = smallDecimal ? text.indexOf('.') : -1;
    if (decimalIndex < 0) {
        for (int16_t targetY = 0; targetY < kTargetHeight; ++targetY) {
            const int16_t sourceY = targetY * kSourceHeight / kTargetHeight;
            for (int16_t targetX = 0; targetX < targetWidth; ++targetX) {
                const int16_t sourceX = targetX * sourceWidth / targetWidth;
                gfx_->drawPixel(x + targetX, y + targetY,
                                source[sourceY * kScratchWidth + sourceX]);
            }
        }
        return targetWidth;
    }

    // Compact the decimal from a full 16-pixel character cell to 7 pixels.
    // The 3x3 dot remains clear while sitting much closer to both digits.
    constexpr int16_t kDecimalWidth = 7;
    const int16_t leftSourceWidth = decimalIndex * 18;
    const int16_t rightSourceStart = (decimalIndex + 1) * 18;
    const int16_t rightSourceWidth = sourceWidth - rightSourceStart;
    const int16_t leftTargetWidth = (leftSourceWidth * 9 + 5) / 10;
    const int16_t rightTargetWidth = (rightSourceWidth * 9 + 5) / 10;

    for (int16_t targetY = 0; targetY < kTargetHeight; ++targetY) {
        const int16_t sourceY = targetY * kSourceHeight / kTargetHeight;
        for (int16_t targetX = 0; targetX < leftTargetWidth; ++targetX) {
            const int16_t sourceX =
                targetX * leftSourceWidth / leftTargetWidth;
            gfx_->drawPixel(x + targetX, y + targetY,
                            source[sourceY * kScratchWidth + sourceX]);
        }
        for (int16_t targetX = 0; targetX < rightTargetWidth; ++targetX) {
            const int16_t sourceX =
                rightSourceStart + targetX * rightSourceWidth /
                                       rightTargetWidth;
            gfx_->drawPixel(x + leftTargetWidth + kDecimalWidth + targetX,
                            y + targetY,
                            source[sourceY * kScratchWidth + sourceX]);
        }
    }
    gfx_->fillRect(x + leftTargetWidth, y, kDecimalWidth, kTargetHeight,
                   kPanel);
    gfx_->fillRect(x + leftTargetWidth + 2, y + 16, 3, 3, color);
    return leftTargetWidth + kDecimalWidth + rightTargetWidth;
}

void DisplayUi::drawTopBar(const char* title, uint16_t accent) {
    // Keep important content away from the physically rounded glass corners.
    gfx_->fillRoundRect(7, 3, gfx_->width() - 14, 25, 4, kTopBar);
    gfx_->drawRoundRect(7, 3, gfx_->width() - 14, 25, 4, kPanelEdge);
    gfx_->drawFastHLine(12, 27, 90, kNeonCyan);
    gfx_->drawFastHLine(105, 27, 24, kNeonPink);
    gfx_->fillRect(9, 8, 3, 15, accent);
    gfx_->fillTriangle(16, 15, 21, 10, 21, 20, accent);
    gfx_->fillTriangle(21, 10, 26, 15, 21, 20, accent);
    gfx_->setTextSize(2);
    gfx_->setTextColor(kWhite);
    gfx_->setCursor(33, 7);
    gfx_->print(title);

    char clockText[6] = "--:--";
    if (gNightMode.timeValid) {
        snprintf(clockText, sizeof(clockText), "%02u:%02u",
                 gNightMode.localMinute / 60,
                 gNightMode.localMinute % 60);
    }
    drawPill(clockText, 153, 7, 66, rgb565(8, 39, 53), kNeonCyan);

    const bool online = gNetwork.staConnected;
    const char* status = gNightMode.active ? "NIGHT"
                                           : (online ? "ONLINE" : "SETUP");
    const uint16_t statusBackground =
        gNightMode.active ? rgb565(8, 39, 53)
                          : (online ? rgb565(16, 66, 51)
                                    : rgb565(72, 57, 22));
    const uint16_t statusColor =
        gNightMode.active ? kNeonCyan : (online ? kGreen : kOrange);
    drawPill(status, 235, 7, 69, statusBackground, statusColor);
}

void DisplayUi::drawPageDots(uint16_t accent) {
    for (uint8_t i = 0; i < 4; ++i) {
        const int16_t x = 130 + i * 17;
        if (i == page_) {
            gfx_->fillRect(x, 157, 12, 4, accent);
            gfx_->drawFastHLine(x, 156, 12, kNeonCyan);
        } else {
            gfx_->drawRect(x + 2, 157, 5, 4, kPanelEdge);
        }
    }
    gfx_->setTextSize(1);
    gfx_->setTextColor(kNeonCyan);
    gfx_->setCursor(271, 154);
    gfx_->print("NEXT");
    gfx_->drawLine(301, 156, 305, 159, kNeonCyan);
    gfx_->drawLine(305, 159, 301, 162, kNeonCyan);
}

uint16_t DisplayUi::co2Color(uint16_t ppm) const {
    const RgbColor& color = gAirQualityColors.displaySaved[
        static_cast<uint8_t>(airQualityLevel(ppm))];
    return rgb565(color.r, color.g, color.b);
}

void DisplayUi::drawHome() {
    uint16_t accent = gSensor.fault
                          ? kPurple
                          : (gSensor.ready ? co2Color(gSensor.co2Ppm)
                                           : kBlue);
    if (gAirQualityColors.previewDisplay) {
        const RgbColor& preview = gAirQualityColors.displayEdit[
            gAirQualityColors.previewBand];
        accent = rgb565(preview.r, preview.g, preview.b);
    }
    drawTopBar("AQI", accent);
    drawPanel(10, 36, 194, 117, accent);
    drawPanel(212, 36, 98, 55, kBlue);
    drawPanel(212, 98, 98, 55, kPurple);

    gfx_->setTextSize(1);
    gfx_->setTextColor(kMuted);
    gfx_->setCursor(22, 47);
    gfx_->print("CARBON DIOXIDE (CO2)");

    if (gSensor.fault) {
        gfx_->setTextSize(3);
        gfx_->setTextColor(kPurple);
        gfx_->setCursor(22, 70);
        gfx_->print("SENSOR");
        gfx_->setCursor(22, 98);
        gfx_->print("OFFLINE");
        gfx_->setTextSize(1);
        gfx_->setTextColor(kMuted);
        gfx_->setCursor(22, 135);
        gfx_->print("CHECK GP4 / GP5");
    } else if (!gSensor.ready) {
        gfx_->setTextSize(3);
        gfx_->setTextColor(kBlue);
        gfx_->setCursor(22, 75);
        gfx_->print("WARMING UP");
        gfx_->setTextSize(1);
        gfx_->setTextColor(kMuted);
        gfx_->setCursor(22, 113);
        gfx_->print("FIRST READING IN A MOMENT");
    } else {
        const String value(gSensor.co2Ppm);
        // The built-in bitmap font grows in 8-pixel steps. Moving from 5x to
        // 6x makes the normal 3/4-digit CO2 reading about 10 pixels taller.
        const uint8_t valueSize = value.length() > 4 ? 5 : 6;
        gfx_->setTextSize(valueSize);
        gfx_->setTextColor(accent);
        gfx_->setCursor(32, 73);
        gfx_->print(value);
        gfx_->setTextSize(2);
        gfx_->setTextColor(kMuted);
        gfx_->setCursor(158, 120);
        gfx_->print("ppm");
        drawPill(airQualityLabel(airQualityLevel(gSensor.co2Ppm)), 22, 136,
                 93, rgb565(20, 42, 55), accent);
    }

    gfx_->setTextSize(1);
    gfx_->setTextColor(kMuted);
    gfx_->setCursor(224, 46);
    gfx_->print("TEMPERATURE");
    const String temperatureText =
        gSensor.ready ? String(gSensor.temperatureC, 1) : "--.-";
    const int16_t temperatureDecimal = temperatureText.indexOf('.');
    const int16_t temperatureLeftWidth =
        (temperatureDecimal * 18 * 9 + 5) / 10;
    const int16_t temperatureRightWidth =
        ((temperatureText.length() - temperatureDecimal - 1) * 18 * 9 + 5) /
        10;
    const int16_t temperatureWidth =
        temperatureLeftWidth + 7 + temperatureRightWidth;
    const int16_t temperatureX =
        212 + max<int16_t>(5, (98 - temperatureWidth - 14) / 2);
    drawScaledMetric(temperatureText, temperatureX, 61, kWhite, true);
    gfx_->setTextSize(1);
    gfx_->setTextColor(kWhite);
    const int16_t temperatureUnitY = 75;
    gfx_->drawCircle(temperatureX + temperatureWidth + 3,
                     temperatureUnitY + 2, 2, kWhite);
    gfx_->setCursor(temperatureX + temperatureWidth + 8, temperatureUnitY);
    gfx_->print("C");

    gfx_->setTextSize(1);
    gfx_->setTextColor(kMuted);
    gfx_->setCursor(224, 108);
    gfx_->print("HUMIDITY");
    const String humidityText =
        gSensor.ready ? String(gSensor.humidityRh, 0) : "--";
    const int16_t humidityWidth =
        (humidityText.length() * 18 * 9 + 5) / 10;
    const int16_t humidityX =
        212 + max<int16_t>(5, (98 - humidityWidth - 10) / 2);
    drawScaledMetric(humidityText, humidityX, 122, kWhite);
    gfx_->setTextSize(1);
    gfx_->setTextColor(kWhite);
    gfx_->setCursor(humidityX + humidityWidth + 4, 136);
    gfx_->print("%");

    drawPageDots(accent);
}

void DisplayUi::drawNetwork() {
    const uint16_t accent = gNetwork.staConnected ? kGreen : kOrange;
    drawTopBar("NETWORK", accent);
    drawPanel(10, 36, 145, 117, accent);
    drawPanel(165, 36, 145, 117, kBlue);

    gfx_->setTextSize(1);
    gfx_->setTextColor(kMuted);
    gfx_->setCursor(22, 48);
    gfx_->print("HOME WIFI");
    drawPill(gNetwork.staConnected ? "CONNECTED" : "NOT CONNECTED", 22, 63,
             116, rgb565(20, 42, 55), accent);

    gfx_->setTextColor(kWhite);
    gfx_->setCursor(22, 91);
    gfx_->print(gNetwork.staConnected ? fitText(gNetwork.staSsid, 19)
                                      : "Use setup hotspot");
    gfx_->setTextColor(kMuted);
    gfx_->setCursor(22, 109);
    gfx_->print(gNetwork.staConnected ? gNetwork.staIp : "No LAN address");
    drawCenteredIn("HOLD BOOT 4S", 15, 122, 135, 1, kOrange);
    drawCenteredIn("TO RESET WI-FI", 15, 138, 135, 1, kOrange);

    gfx_->setTextColor(kMuted);
    gfx_->setCursor(177, 48);
    gfx_->print("SETUP HOTSPOT");
    if (gNetwork.apActive) {
        gfx_->setTextColor(kWhite);
        gfx_->setCursor(177, 67);
        gfx_->print(fitText(gNetwork.apSsid, 19));
        gfx_->setTextColor(kMuted);
        gfx_->setCursor(177, 88);
        gfx_->print("PASSWORD");
        gfx_->setTextColor(kWhite);
        gfx_->setCursor(177, 102);
        gfx_->print(gNetwork.apPassword);
        gfx_->setTextColor(kBlue);
        gfx_->setCursor(177, 132);
        gfx_->print("192.168.4.1");
    } else {
        drawPill("OFF WHILE ONLINE", 177, 63, 116,
                 rgb565(16, 66, 51), kGreen);
        drawCenteredIn("AUTO DISABLED", 170, 91, 135, 1, kWhite);
        drawCenteredIn("REOPENS IF OFFLINE", 170, 109, 135, 1, kMuted);
        drawCenteredIn("LAN ACCESS ACTIVE", 170, 132, 135, 1, kBlue);
    }

    drawPageDots(accent);
}

void DisplayUi::drawHelp() {
    const uint16_t sensorAccent = gSensor.detected ? kGreen : kPurple;
    const uint16_t networkAccent = gNetwork.staConnected ? kGreen : kOrange;
    drawTopBar("SYSTEM", kBlue);
    drawPanel(10, 36, 94, 117, sensorAccent);
    drawPanel(113, 36, 94, 117, networkAccent);
    drawPanel(216, 36, 94, 117, kBlue);

    gfx_->setTextSize(1);
    gfx_->setTextColor(kMuted);
    gfx_->setCursor(22, 49);
    gfx_->print("SENSOR");
    gfx_->fillCircle(57, 83, 17, sensorAccent);
    gfx_->fillCircle(57, 83, 9, kPanel);
    drawCenteredIn("SCD41", 15, 108, 84, 2, kWhite);
    drawCenteredIn(gSensor.detected ? "0x62 ONLINE" : "NOT FOUND", 15, 136,
                    84, 1, sensorAccent);

    gfx_->setTextColor(kMuted);
    gfx_->setCursor(125, 49);
    gfx_->print("WIFI");
    for (uint8_t i = 0; i < 4; ++i) {
        const int16_t h = 5 + i * 5;
        const bool active = gNetwork.staConnected &&
                            gNetwork.rssi > (-90 + static_cast<int>(i) * 12);
        gfx_->fillRoundRect(135 + i * 13, 101 - h, 8, h, 2,
                            active ? networkAccent : kPanelEdge);
    }
    if (gNetwork.staConnected) {
        drawCenteredIn("LINKED", 118, 110, 84, 1, networkAccent);
        drawCenteredIn(fitText(gNetwork.staSsid, 12), 118, 125, 84, 1,
                       kWhite);
        drawCenteredIn(String(gNetwork.rssi) + " dBm", 118, 140, 84, 1,
                       kBlue);
    } else {
        drawCenteredIn("SETUP MODE", 118, 117, 84, 1, networkAccent);
        drawCenteredIn(gNetwork.apActive ? "AP ACTIVE" : "AP WAITING", 118,
                       136, 84, 1, kWhite);
    }

    gfx_->setTextColor(kMuted);
    gfx_->setCursor(228, 49);
    gfx_->print("UPTIME");
    const uint32_t totalMinutes = millis() / 60000UL;
    const String uptime = totalMinutes >= 60
                              ? String(totalMinutes / 60) + "h"
                              : String(totalMinutes) + "m";
    drawCenteredIn(uptime, 221, 65, 84, 2, kBlue);

    gfx_->drawFastHLine(228, 91, 70, kPanelEdge);
    gfx_->drawFastHLine(228, 91, 18, kNeonPink);
    drawCenteredIn("BATTERY", 221, 100, 84, 1, kMuted);
    const String voltage = String(readBatteryVoltage(), 2) + " V";
    drawCenteredIn(voltage, 221, 117, 84, 2, kWhite);
    drawCenteredIn("ADC LIVE", 221, 140, 84, 1, kNeonCyan);

    drawPageDots(kBlue);
}

void DisplayUi::drawHistory() {
    const uint16_t accent =
        gSensor.ready && !gSensor.fault ? co2Color(gSensor.co2Ppm) : kBlue;
    drawTopBar("HISTORY", accent);
    drawPanel(10, 36, 300, 117, accent);

    gfx_->setTextSize(2);
    gfx_->setTextColor(accent);
    gfx_->setCursor(22, 47);
    if (gSensor.ready && !gSensor.fault) gfx_->print(gSensor.co2Ppm);
    else gfx_->print("---");
    gfx_->setTextSize(1);
    gfx_->setTextColor(kMuted);
    gfx_->setCursor(80, 54);
    gfx_->print("ppm");

    gfx_->setTextColor(kNeonCyan);
    gfx_->setCursor(249, 48);
    gfx_->printf("%lus/PT", co2HistoryIntervalMs_ / 1000UL);

    constexpr int16_t plotX = 22;
    constexpr int16_t plotY = 68;
    constexpr int16_t plotW = 276;
    constexpr int16_t plotH = 69;
    constexpr int16_t plotBottom = plotY + plotH - 1;
    gfx_->drawRect(plotX, plotY, plotW, plotH, kPanelEdge);

    for (uint8_t i = 1; i < 4; ++i) {
        const int16_t y = plotY + i * plotH / 4;
        gfx_->drawFastHLine(plotX + 1, y, plotW - 2, kGrid);
    }
    for (uint8_t i = 1; i < 6; ++i) {
        const int16_t x = plotX + i * plotW / 6;
        gfx_->drawFastVLine(x, plotY + 1, plotH - 2, kGrid);
    }

    uint16_t observedMax = 1600;
    for (uint8_t i = 0; i < co2HistoryCount_; ++i) {
        observedMax = max<uint16_t>(observedMax, co2History_[i]);
    }
    const uint16_t yMin = 400;
    const uint16_t yMax =
        max<uint16_t>(1600, ((observedMax + 199) / 200) * 200);
    const auto valueToY = [&](uint16_t value) -> int16_t {
        const int32_t clamped =
            max<int32_t>(yMin, min<int32_t>(yMax, value));
        return plotBottom -
               (clamped - yMin) * (plotH - 1) / (yMax - yMin);
    };

    const int16_t y800 = valueToY(800);
    const int16_t y1500 = valueToY(1500);
    for (int16_t x = plotX + 1; x < plotX + plotW - 1; x += 6) {
        gfx_->drawFastHLine(x, y800, 3, kOrange);
        gfx_->drawFastHLine(x, y1500, 3, kRed);
    }
    gfx_->setTextSize(1);
    gfx_->setTextColor(kOrange);
    gfx_->setCursor(plotX + 3, max<int16_t>(plotY + 2, y800 - 9));
    gfx_->print("800");
    gfx_->setTextColor(kRed);
    gfx_->setCursor(plotX + 3, max<int16_t>(plotY + 2, y1500 - 9));
    gfx_->print("1500");

    if (co2HistoryCount_ > 0) {
        const uint32_t newestTime =
            co2HistoryTimeMs_[co2HistoryCount_ - 1];
        const uint32_t windowMs =
            co2HistoryIntervalMs_ * kHistoryCapacity;
        int16_t previousX = plotX + plotW - 1;
        int16_t previousY = valueToY(co2History_[0]);
        bool havePrevious = false;
        for (uint8_t i = 0; i < co2HistoryCount_; ++i) {
            const uint32_t ageMs = newestTime - co2HistoryTimeMs_[i];
            const int16_t x = max<int16_t>(
                plotX + 1,
                plotX + plotW - 1 -
                    static_cast<uint64_t>(ageMs) * (plotW - 2) / windowMs);
            const int16_t y = valueToY(co2History_[i]);
            const uint16_t pointColor = co2Color(co2History_[i]);
            if (havePrevious) {
                gfx_->drawLine(previousX, previousY, x, y, pointColor);
            }
            gfx_->fillCircle(x, y, 1, pointColor);
            previousX = x;
            previousY = y;
            havePrevious = true;
        }
    } else {
        drawCenteredIn("WAITING FOR CO2 DATA", plotX, 98, plotW, 1,
                       kMuted);
    }

    String spanLabel = "SPAN ";
    if (co2HistoryCount_ > 1) {
        const uint32_t spanSeconds =
            (co2HistoryTimeMs_[co2HistoryCount_ - 1] -
             co2HistoryTimeMs_[0]) /
            1000UL;
        if (spanSeconds >= 3600) spanLabel += "1h";
        else if (spanSeconds >= 60) spanLabel += String(spanSeconds / 60) + "m";
        else spanLabel += String(spanSeconds) + "s";
    } else {
        spanLabel += "0s";
    }
    gfx_->setTextColor(kMuted);
    gfx_->setCursor(22, 141);
    gfx_->print(spanLabel);
    gfx_->setCursor(243, 141);
    gfx_->printf("%u/60", co2HistoryCount_);

    drawPageDots(accent);
}

void DisplayUi::draw() {
    gfx_->fillScreen(kBackground);
    drawCyberBackground();
    // A web display-color preview always shows the Air Quality page so the
    // selected band color is visible even if the user was on another page.
    if (gAirQualityColors.previewDisplay) drawHome();
    else if (page_ == 0) drawHome();
    else if (page_ == 1) drawNetwork();
    else if (page_ == 2) drawHelp();
    else drawHistory();
    canvas_->flush();
}
