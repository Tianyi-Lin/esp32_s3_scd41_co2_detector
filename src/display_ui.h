#pragma once

#include <Arduino_GFX_Library.h>

class DisplayUi {
  public:
    bool begin();
    void loop();
    bool consumeNetworkResetRequest();
    bool consumeNightModeToggleRequest();

  private:
    Arduino_DataBus* bus_ = nullptr;
    Arduino_GFX* panel_ = nullptr;
    Arduino_Canvas* canvas_ = nullptr;
    Arduino_Canvas* metricCanvas_ = nullptr;
    Arduino_GFX* gfx_ = nullptr;
    uint32_t lastDrawMs_ = 0;
    uint32_t buttonChangedMs_ = 0;
    uint32_t buttonPressedMs_ = 0;
    uint32_t lastShortClickMs_ = 0;
    uint8_t page_ = 0;
    bool lastButtonReading_ = false;
    bool stableButtonPressed_ = false;
    bool longPressHandled_ = false;
    bool networkResetRequested_ = false;
    bool pendingSingleClick_ = false;
    bool nightModeToggleRequested_ = false;
    bool backlightInitialized_ = false;
    bool backlightNightActive_ = false;
    float batteryVoltage_ = 0.0f;
    static constexpr uint8_t kHistoryCapacity = 60;
    uint16_t co2History_[kHistoryCapacity] = {};
    uint32_t co2HistoryTimeMs_[kHistoryCapacity] = {};
    uint8_t co2HistoryCount_ = 0;
    uint32_t co2HistoryIntervalMs_ = 1000;
    uint32_t lastCo2HistorySampleMs_ = 0;

    void draw();
    void drawCyberBackground();
    void handleButton(uint32_t now);
    void applyBacklightMode();
    void recordCo2History(uint32_t now);
    void compactCo2History();
    void nextPage();
    void drawTopBar(const char* title, uint16_t accent);
    void drawPageDots(uint16_t accent);
    void drawPanel(int16_t x, int16_t y, int16_t w, int16_t h,
                   uint16_t accent);
    void drawPill(const String& text, int16_t x, int16_t y, int16_t w,
                  uint16_t background, uint16_t foreground);
    int16_t drawScaledMetric(const String& text, int16_t x, int16_t y,
                             uint16_t color, bool smallDecimal = false);
    void drawCenteredIn(const String& text, int16_t x, int16_t y, int16_t w,
                        uint8_t size, uint16_t color);
    String fitText(const String& text, uint8_t maxChars) const;
    float readBatteryVoltage();
    void drawHome();
    void drawNetwork();
    void drawHelp();
    void drawHistory();
    uint16_t co2Color(uint16_t ppm) const;
};
