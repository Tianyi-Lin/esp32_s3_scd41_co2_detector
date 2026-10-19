#pragma once

#include <Arduino.h>

class StatusLed {
  public:
    void begin();
    void loop();

  private:
    struct Rgb {
        uint8_t r;
        uint8_t g;
        uint8_t b;
    };

    Rgb current_{0, 0, 0};
    int8_t lastMode_ = -1;

    Rgb targetColor() const;
    int8_t currentMode() const;
    const char* modeLabel(int8_t mode) const;
    void writeColor(const Rgb& color) const;
};
