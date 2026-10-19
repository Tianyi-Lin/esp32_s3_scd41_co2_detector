#pragma once

#include <Preferences.h>
#include <WebServer.h>

class WebPortal {
  public:
    WebPortal();
    void begin();
    void loop();
    void clearSavedWifi();

  private:
    WebServer server_;
    Preferences preferences_;
    String apSsid_;
    String apPassword_;
    uint32_t lastNetworkRefreshMs_ = 0;
    uint32_t disconnectedSinceMs_ = 0;
    uint32_t lastColorPreviewMs_ = 0;

    void startSavedNetwork();
    void startSetupAp();
    void stopSetupAp();
    void refreshNetworkState();
    void handleRoot();
    void handleData();
    void handleScan();
    void handleSaveWifi();
    void handleForgetWifi();
    void handleColors();
    void handlePreviewColor();
    void handleSaveColors();
    void handleCancelColorPreview();
    void handleNightSettings();
    void handleSaveNightSettings();
    bool readColorArguments(uint8_t& band, bool& led, uint8_t& red,
                            uint8_t& green, uint8_t& blue);
    void loadColorSettings();
    void loadNightSettings();
    void persistColorSettings();
    void persistNightSettings();
    void restoreColorEdits();
    bool parseClockMinute(const String& value, uint16_t& minute) const;
    String jsonEscape(const String& value) const;
};
