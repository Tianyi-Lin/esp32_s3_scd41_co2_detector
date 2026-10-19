#include "web_portal.h"

#include "app_state.h"

#include <Arduino.h>
#include <WiFi.h>

namespace {
constexpr uint32_t kApRecoveryDelayMs = 30000;
constexpr uint32_t kColorPreviewTimeoutMs = 120000;

const char kDashboardHtml[] PROGMEM = R"HTML(
<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>AuraNode S3</title><style>
:root{color-scheme:dark;font-family:system-ui,sans-serif;background:#07111d;color:#eaf2ff}
body{margin:0;padding:24px;max-width:880px;margin:auto}.top{display:flex;justify-content:space-between;align-items:center}
.pill{padding:7px 12px;border-radius:99px;background:#17263a}.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin:24px 0}
.card{background:#101e30;border:1px solid #203651;border-radius:18px;padding:22px}.value{font-size:42px;font-weight:750}.label{color:#9db0c8}
.wide{grid-column:1/-1}input,button{box-sizing:border-box;width:100%;padding:12px;margin-top:9px;border-radius:10px;border:1px solid #36506c;background:#0b1726;color:#fff}
button{background:#1d7eea;border:0;font-weight:700;cursor:pointer}.danger{background:#6b2630}.secondary{background:#24364d}.ok{color:#51df8a}.warn{color:#ffd166}
.palette-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}.band{background:#0b1726;border:1px solid #29425f;border-radius:14px;padding:15px}.band h3{margin:0 0 4px}.target{margin-top:14px;padding-top:12px;border-top:1px solid #203651}.target-head{display:flex;justify-content:space-between;align-items:center}.swatch{width:42px;height:24px;border-radius:7px;border:1px solid #6b7f96}.slider-row{display:grid;grid-template-columns:18px 1fr 34px;gap:8px;align-items:center;color:#9db0c8}.slider-row input{padding:0;margin:8px 0;accent-color:#4b9dff}.slider-row output{text-align:right;color:#eaf2ff;font-variant-numeric:tabular-nums}.actions{display:grid;grid-template-columns:1fr 1fr;gap:10px}
.night-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}.night-toggle{display:flex;align-items:center;gap:10px;margin:12px 0}.night-toggle input{width:auto;margin:0;accent-color:#00deff}.night-state{padding:10px 12px;border-left:3px solid #00deff;background:#0b1726}
@media(max-width:750px){.grid,.palette-grid{grid-template-columns:1fr}.value{font-size:36px}}
</style></head><body><div class="top"><div><h1>AuraNode S3</h1><div class="label">ESP32-S3 + SCD41</div></div><div id="status" class="pill">连接中</div></div>
<div class="grid"><div class="card"><div id="co2" class="value">--</div><div class="label">CO₂ ppm</div></div>
<div class="card"><div id="temp" class="value">--</div><div class="label">温度 °C</div></div>
<div class="card"><div id="rh" class="value">--</div><div class="label">湿度 %RH</div></div>
<div class="card wide"><h2>三档颜色配置</h2><p class="label">实体 RGB 灯与屏幕颜色互相独立。拖动 R/G/B 滑杆会在对应硬件上实时预览。</p>
<div id="paletteGrid" class="palette-grid"></div><div class="actions"><button id="saveColors">保存全部颜色</button><button id="cancelColors" class="secondary">取消全部预览</button></div><p id="colorMessage" class="label"></p></div>
<div class="card wide"><h2>夜间模式</h2><p class="label">夜间自动关闭实体 RGB 灯，并把屏幕背光降到最低。时间采用北京时间；双击 BOOT 可临时手动切换，下一计划边界恢复自动。</p>
<div id="nightStatus" class="night-state">读取中…</div><form id="nightForm"><label class="night-toggle"><input id="nightEnabled" type="checkbox">启用自动夜间模式</label><div class="night-grid"><label>开始时间<input id="nightStart" type="time" required></label><label>结束时间<input id="nightEnd" type="time" required></label></div><button>保存夜间模式</button></form><p id="nightMessage" class="label"></p></div>
<div class="card wide"><h2>网络</h2><div id="network" class="label">读取中…</div>
<form id="wifi"><label>2.4 GHz Wi-Fi 名称</label><input name="ssid" required autocomplete="off"><label>Wi-Fi 密码</label><input name="password" type="password"><button>保存并连接</button></form>
<button id="forget" class="danger">忘记已保存的 Wi-Fi</button><p id="message" class="label"></p></div></div>
<script>
const q=s=>document.querySelector(s);async function update(){try{const d=await fetch('/api/data').then(r=>r.json());q('#co2').textContent=d.ready?d.co2_ppm:'--';q('#temp').textContent=d.ready?d.temperature_c.toFixed(1):'--';q('#rh').textContent=d.ready?d.humidity_rh.toFixed(0):'--';q('#status').textContent=d.sensor_fault?'传感器异常':(d.sta_connected?'已联网':'配置模式');q('#status').className='pill '+(d.sensor_fault?'warn':'ok');q('#network').textContent=d.sta_connected?`${d.sta_ssid} · ${d.sta_ip} · ${d.rssi} dBm`:`请连接 2.4 GHz Wi-Fi；设备热点 ${d.ap_ssid}`;q('#nightStatus').textContent=d.night_active?`夜间模式运行中 · ${d.night_manual?'手动覆盖':'自动计划'}`:(d.time_valid?`日间模式 · 当前 ${d.local_time}`:'等待联网校时；双击 BOOT 仍可手动启用');}catch(e){q('#status').textContent='连接中断';}}setInterval(update,2500);update();
q('#wifi').onsubmit=async e=>{e.preventDefault();q('#message').textContent='正在保存…';const r=await fetch('/api/wifi',{method:'POST',body:new FormData(e.target)});q('#message').textContent=await r.text();};
q('#forget').onclick=async()=>{if(!confirm('确定清除已保存的 Wi-Fi？'))return;const r=await fetch('/api/forget',{method:'POST'});q('#message').textContent=await r.text();};
const bands=[['绿色档','< 800 ppm'],['橙色档','800–1499 ppm'],['红色档','≥ 1500 ppm']];const targets=[['led','实体 RGB 灯'],['display','屏幕配色']];let previewTimer,pendingGroup;
const clamp=v=>Math.max(0,Math.min(255,Number(v)||0));const hex=v=>clamp(v).toString(16).padStart(2,'0');
function updateGroup(group){const values={};group.querySelectorAll('input').forEach(input=>{values[input.dataset.channel]=clamp(input.value);input.nextElementSibling.value=values[input.dataset.channel];});group.querySelector('.swatch').style.background='#'+hex(values.r)+hex(values.g)+hex(values.b);return values;}
function renderPalettes(data){q('#paletteGrid').innerHTML=bands.map((band,bi)=>`<section class='band'><h3>${band[0]}</h3><div class='label'>${band[1]}</div>${targets.map(target=>{const c=data.bands[bi][target[0]];return `<div class='target color-group' data-band='${bi}' data-target='${target[0]}'><div class='target-head'><strong>${target[1]}</strong><span class='swatch'></span></div>${['r','g','b'].map(ch=>`<label class='slider-row'><span>${ch.toUpperCase()}</span><input type='range' min='0' max='255' value='${c[ch]}' data-channel='${ch}'><output>${c[ch]}</output></label>`).join('')}</div>`;}).join('')}</section>`).join('');document.querySelectorAll('.color-group').forEach(group=>{updateGroup(group);group.querySelectorAll('input').forEach(input=>input.oninput=()=>{updateGroup(group);pendingGroup=group;clearTimeout(previewTimer);previewTimer=setTimeout(()=>previewGroup(group),100);});});}
async function previewGroup(group){const c=updateGroup(group);const body=new URLSearchParams({band:group.dataset.band,target:group.dataset.target,r:c.r,g:c.g,b:c.b});const response=await fetch('/api/colors/preview',{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body});const text=await response.text();if(!response.ok)throw new Error(text);q('#colorMessage').textContent=text;}
async function loadColors(){try{const data=await fetch('/api/colors').then(r=>r.json());renderPalettes(data);}catch(e){q('#colorMessage').textContent='读取颜色配置失败';}}
q('#saveColors').onclick=async()=>{clearTimeout(previewTimer);try{for(const group of document.querySelectorAll('.color-group'))await previewGroup(group);const response=await fetch('/api/colors/save',{method:'POST'});q('#colorMessage').textContent=await response.text();}catch(e){q('#colorMessage').textContent=e.message;}};
q('#cancelColors').onclick=async()=>{clearTimeout(previewTimer);const response=await fetch('/api/colors/cancel',{method:'POST'});q('#colorMessage').textContent=await response.text();await loadColors();};loadColors();
const clock=m=>`${String(Math.floor(m/60)).padStart(2,'0')}:${String(m%60).padStart(2,'0')}`;async function loadNight(){try{const d=await fetch('/api/night').then(r=>r.json());q('#nightEnabled').checked=d.enabled;q('#nightStart').value=clock(d.start_minute);q('#nightEnd').value=clock(d.end_minute);}catch(e){q('#nightMessage').textContent='读取夜间模式配置失败';}}q('#nightForm').onsubmit=async e=>{e.preventDefault();const body=new URLSearchParams({enabled:q('#nightEnabled').checked?'1':'0',start:q('#nightStart').value,end:q('#nightEnd').value});const response=await fetch('/api/night',{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body});q('#nightMessage').textContent=await response.text();if(response.ok)await loadNight();};loadNight();
</script></body></html>
)HTML";
}  // namespace

WebPortal::WebPortal() : server_(80) {}

void WebPortal::begin() {
    preferences_.begin("auranode", false);
    loadColorSettings();
    loadNightSettings();

    const uint16_t suffix = static_cast<uint16_t>(ESP.getEfuseMac() & 0xFFFF);
    char apName[24];
    char apPassword[12];
    snprintf(apName, sizeof(apName), "AuraNode-S3-%04X", suffix);
    snprintf(apPassword, sizeof(apPassword), "AURA%04X", suffix);
    apSsid_ = apName;
    apPassword_ = apPassword;

    WiFi.mode(WIFI_AP_STA);
    WiFi.setSleep(false);
    gNetwork.apSsid = apSsid_;
    gNetwork.apPassword = apPassword_;
    startSetupAp();

    startSavedNetwork();

    server_.on("/", HTTP_GET, [this]() { handleRoot(); });
    server_.on("/api/data", HTTP_GET, [this]() { handleData(); });
    server_.on("/api/scan", HTTP_GET, [this]() { handleScan(); });
    server_.on("/api/wifi", HTTP_POST, [this]() { handleSaveWifi(); });
    server_.on("/api/forget", HTTP_POST, [this]() { handleForgetWifi(); });
    server_.on("/api/colors", HTTP_GET, [this]() { handleColors(); });
    server_.on("/api/colors/preview", HTTP_POST,
               [this]() { handlePreviewColor(); });
    server_.on("/api/colors/save", HTTP_POST,
               [this]() { handleSaveColors(); });
    server_.on("/api/colors/cancel", HTTP_POST,
               [this]() { handleCancelColorPreview(); });
    server_.on("/api/night", HTTP_GET,
               [this]() { handleNightSettings(); });
    server_.on("/api/night", HTTP_POST,
               [this]() { handleSaveNightSettings(); });
    server_.onNotFound([this]() { server_.send(404, "text/plain", "Not found"); });
    server_.begin();

}

void WebPortal::startSetupAp() {
    if (gNetwork.apActive) return;

    WiFi.mode(WIFI_AP_STA);
    gNetwork.apActive = WiFi.softAP(apSsid_.c_str(), apPassword_.c_str());
    gNetwork.apIp = gNetwork.apActive ? WiFi.softAPIP().toString() : "";
    if (gNetwork.apActive) {
        Serial.printf("[WEB] Setup AP %s | password %s | http://%s\n",
                      apSsid_.c_str(), apPassword_.c_str(),
                      gNetwork.apIp.c_str());
    } else {
        Serial.println("[WEB] Failed to start setup hotspot.");
    }
}

void WebPortal::stopSetupAp() {
    if (!gNetwork.apActive) return;

    // Switching explicitly to station-only mode is more reliable than
    // softAPdisconnect(true) on this Arduino-ESP32 release, whose return value
    // can report failure even after disabling the AP interface.
    if (WiFi.mode(WIFI_STA)) {
        gNetwork.apActive = false;
        gNetwork.apIp = "";
        Serial.println("[WEB] Setup hotspot disabled while home Wi-Fi is online.");
    } else {
        Serial.println("[WEB] Failed to disable setup hotspot.");
    }
}

void WebPortal::startSavedNetwork() {
    if (!preferences_.isKey("wifi_ssid")) return;

    const String ssid = preferences_.getString("wifi_ssid", "");
    const String password = preferences_.isKey("wifi_pass")
                                ? preferences_.getString("wifi_pass", "")
                                : String();
    if (ssid.isEmpty()) return;

    Serial.printf("[WIFI] Connecting to saved network: %s\n", ssid.c_str());
    WiFi.begin(ssid.c_str(), password.c_str());
}

void WebPortal::loop() {
    server_.handleClient();
    if ((gAirQualityColors.previewLed || gAirQualityColors.previewDisplay) &&
        millis() - lastColorPreviewMs_ >= kColorPreviewTimeoutMs) {
        restoreColorEdits();
        Serial.println("[COLOR] Web preview timed out; restored saved colors.");
    }
    if (millis() - lastNetworkRefreshMs_ >= 1000) {
        lastNetworkRefreshMs_ = millis();
        refreshNetworkState();
    }
}

void WebPortal::refreshNetworkState() {
    gNetwork.staConnected = WiFi.status() == WL_CONNECTED;
    if (gNetwork.staConnected) {
        disconnectedSinceMs_ = 0;
        gNetwork.staSsid = WiFi.SSID();
        gNetwork.staIp = WiFi.localIP().toString();
        gNetwork.rssi = WiFi.RSSI();
        stopSetupAp();
    } else {
        gNetwork.staIp = "";
        gNetwork.rssi = 0;
        if (disconnectedSinceMs_ == 0) disconnectedSinceMs_ = millis();
        if (!gNetwork.apActive &&
            millis() - disconnectedSinceMs_ >= kApRecoveryDelayMs) {
            startSetupAp();
        }
    }
}

String WebPortal::jsonEscape(const String& value) const {
    String result;
    result.reserve(value.length() + 8);
    for (size_t i = 0; i < value.length(); ++i) {
        const char c = value.charAt(i);
        if (c == '\\' || c == '"') result += '\\';
        if (c == '\n' || c == '\r') result += ' ';
        else result += c;
    }
    return result;
}

void WebPortal::handleRoot() {
    server_.send_P(200, "text/html; charset=utf-8", kDashboardHtml);
}

void WebPortal::handleData() {
    String json;
    json.reserve(480);
    json += "{\"ready\":" + String(gSensor.ready ? "true" : "false");
    json += ",\"sensor_fault\":" + String(gSensor.fault ? "true" : "false");
    json += ",\"co2_ppm\":" + String(gSensor.co2Ppm);
    json += ",\"temperature_c\":" + String(gSensor.temperatureC, 2);
    json += ",\"humidity_rh\":" + String(gSensor.humidityRh, 1);
    json += ",\"sta_connected\":" + String(gNetwork.staConnected ? "true" : "false");
    json += ",\"sta_ssid\":\"" + jsonEscape(gNetwork.staSsid) + "\"";
    json += ",\"sta_ip\":\"" + gNetwork.staIp + "\"";
    json += ",\"rssi\":" + String(gNetwork.rssi);
    json += ",\"ap_active\":" + String(gNetwork.apActive ? "true" : "false");
    json += ",\"ap_ssid\":\"" + jsonEscape(gNetwork.apSsid) + "\"";
    json += ",\"uptime_s\":" + String(millis() / 1000UL);
    json += ",\"night_active\":" + String(gNightMode.active ? "true" : "false");
    json += ",\"night_manual\":" + String(gNightMode.manualOverride ? "true" : "false");
    json += ",\"time_valid\":" + String(gNightMode.timeValid ? "true" : "false");
    char localTime[6];
    snprintf(localTime, sizeof(localTime), "%02u:%02u",
             gNightMode.localMinute / 60, gNightMode.localMinute % 60);
    json += ",\"local_time\":\"" + String(localTime) + "\"}";
    server_.send(200, "application/json", json);
}

void WebPortal::handleScan() {
    const int count = WiFi.scanNetworks(false, true);
    String json = "[";
    for (int i = 0; i < count; ++i) {
        if (i > 0) json += ',';
        json += "{\"ssid\":\"" + jsonEscape(WiFi.SSID(i)) + "\",\"rssi\":";
        json += String(WiFi.RSSI(i));
        json += "}";
    }
    json += "]";
    WiFi.scanDelete();
    server_.send(200, "application/json", json);
}

void WebPortal::handleSaveWifi() {
    String ssid = server_.arg("ssid");
    const String password = server_.arg("password");
    ssid.trim();
    if (ssid.isEmpty() || ssid.length() > 32 || password.length() > 64) {
        server_.send(400, "text/plain; charset=utf-8", "Wi-Fi 名称或密码格式不正确。");
        return;
    }

    preferences_.putString("wifi_ssid", ssid);
    preferences_.putString("wifi_pass", password);
    WiFi.disconnect(false, false);
    WiFi.begin(ssid.c_str(), password.c_str());
    server_.send(202, "text/plain; charset=utf-8", "已保存，正在连接。成功后设置热点会自动关闭。");
}

void WebPortal::handleForgetWifi() {
    clearSavedWifi();
    server_.send(200, "text/plain; charset=utf-8", "已清除 Wi-Fi 配置，设备热点仍可使用。");
}

void WebPortal::loadColorSettings() {
    const RgbColor ledDefaults[3] = {
        {0, 255, 0}, {255, 140, 0}, {255, 0, 0}};
    const RgbColor displayDefaults[3] = {
        {0, 255, 0}, {255, 153, 28}, {255, 0, 0}};

    for (uint8_t band = 0; band < 3; ++band) {
        char key[5];
        snprintf(key, sizeof(key), "l%ur", band);
        gAirQualityColors.ledSaved[band].r =
            preferences_.getUChar(key, ledDefaults[band].r);
        snprintf(key, sizeof(key), "l%ug", band);
        gAirQualityColors.ledSaved[band].g =
            preferences_.getUChar(key, ledDefaults[band].g);
        snprintf(key, sizeof(key), "l%ub", band);
        gAirQualityColors.ledSaved[band].b =
            preferences_.getUChar(key, ledDefaults[band].b);

        snprintf(key, sizeof(key), "d%ur", band);
        gAirQualityColors.displaySaved[band].r =
            preferences_.getUChar(key, displayDefaults[band].r);
        snprintf(key, sizeof(key), "d%ug", band);
        gAirQualityColors.displaySaved[band].g =
            preferences_.getUChar(key, displayDefaults[band].g);
        snprintf(key, sizeof(key), "d%ub", band);
        gAirQualityColors.displaySaved[band].b =
            preferences_.getUChar(key, displayDefaults[band].b);
    }

    // Migrate the previous single warning-color setting if it exists.
    if (!preferences_.isKey("l1r") && preferences_.isKey("rgb_r")) {
        gAirQualityColors.ledSaved[1].r =
            preferences_.getUChar("rgb_r", ledDefaults[1].r);
        gAirQualityColors.ledSaved[1].g =
            preferences_.getUChar("rgb_g", ledDefaults[1].g);
        gAirQualityColors.ledSaved[1].b =
            preferences_.getUChar("rgb_b", ledDefaults[1].b);
    }
    restoreColorEdits();
}

void WebPortal::loadNightSettings() {
    gNightMode.scheduleEnabled = preferences_.getBool("night_on", true);
    gNightMode.startMinute =
        min<uint16_t>(1439, preferences_.getUShort("night_start", 22 * 60));
    gNightMode.endMinute =
        min<uint16_t>(1439, preferences_.getUShort("night_end", 9 * 60));
    if (gNightMode.startMinute == gNightMode.endMinute) {
        gNightMode.startMinute = 22 * 60;
        gNightMode.endMinute = 9 * 60;
    }
}

void WebPortal::persistNightSettings() {
    preferences_.putBool("night_on", gNightMode.scheduleEnabled);
    preferences_.putUShort("night_start", gNightMode.startMinute);
    preferences_.putUShort("night_end", gNightMode.endMinute);
}

void WebPortal::restoreColorEdits() {
    for (uint8_t band = 0; band < 3; ++band) {
        gAirQualityColors.ledEdit[band] =
            gAirQualityColors.ledSaved[band];
        gAirQualityColors.displayEdit[band] =
            gAirQualityColors.displaySaved[band];
    }
    gAirQualityColors.previewLed = false;
    gAirQualityColors.previewDisplay = false;
}

void WebPortal::persistColorSettings() {
    for (uint8_t band = 0; band < 3; ++band) {
        char key[5];
        snprintf(key, sizeof(key), "l%ur", band);
        preferences_.putUChar(key, gAirQualityColors.ledSaved[band].r);
        snprintf(key, sizeof(key), "l%ug", band);
        preferences_.putUChar(key, gAirQualityColors.ledSaved[band].g);
        snprintf(key, sizeof(key), "l%ub", band);
        preferences_.putUChar(key, gAirQualityColors.ledSaved[band].b);
        snprintf(key, sizeof(key), "d%ur", band);
        preferences_.putUChar(key, gAirQualityColors.displaySaved[band].r);
        snprintf(key, sizeof(key), "d%ug", band);
        preferences_.putUChar(key, gAirQualityColors.displaySaved[band].g);
        snprintf(key, sizeof(key), "d%ub", band);
        preferences_.putUChar(key, gAirQualityColors.displaySaved[band].b);
    }
}

void WebPortal::handleColors() {
    String json = "{\"bands\":[";
    json.reserve(420);
    for (uint8_t band = 0; band < 3; ++band) {
        if (band > 0) json += ',';
        const RgbColor& led = gAirQualityColors.ledSaved[band];
        const RgbColor& display = gAirQualityColors.displaySaved[band];
        json += "{\"led\":{\"r\":" + String(led.r);
        json += ",\"g\":" + String(led.g);
        json += ",\"b\":" + String(led.b) + "},\"display\":{\"r\":";
        json += String(display.r) + ",\"g\":" + String(display.g);
        json += ",\"b\":" + String(display.b) + "}}";
    }
    json += "]}";
    server_.send(200, "application/json", json);
}

bool WebPortal::readColorArguments(uint8_t& band, bool& led, uint8_t& red,
                                   uint8_t& green, uint8_t& blue) {
    if (!server_.hasArg("band") || !server_.hasArg("target") ||
        !server_.hasArg("r") || !server_.hasArg("g") ||
        !server_.hasArg("b")) {
        server_.send(400, "text/plain; charset=utf-8", "缺少颜色参数。");
        return false;
    }

    const long requestedBand = server_.arg("band").toInt();
    const String target = server_.arg("target");
    const long r = server_.arg("r").toInt();
    const long g = server_.arg("g").toInt();
    const long b = server_.arg("b").toInt();
    if (requestedBand < 0 || requestedBand > 2 ||
        (target != "led" && target != "display") || r < 0 || r > 255 ||
        g < 0 || g > 255 || b < 0 || b > 255) {
        server_.send(400, "text/plain; charset=utf-8", "颜色参数不正确。");
        return false;
    }

    band = static_cast<uint8_t>(requestedBand);
    led = target == "led";
    red = static_cast<uint8_t>(r);
    green = static_cast<uint8_t>(g);
    blue = static_cast<uint8_t>(b);
    return true;
}

void WebPortal::handlePreviewColor() {
    uint8_t band;
    uint8_t red;
    uint8_t green;
    uint8_t blue;
    bool led;
    if (!readColorArguments(band, led, red, green, blue)) return;

    RgbColor& color = led ? gAirQualityColors.ledEdit[band]
                          : gAirQualityColors.displayEdit[band];
    color = {red, green, blue};
    gAirQualityColors.previewBand = band;
    gAirQualityColors.previewLed = led;
    gAirQualityColors.previewDisplay = !led;
    lastColorPreviewMs_ = millis();
    server_.send(200, "text/plain; charset=utf-8",
                 led ? "正在实体 RGB 灯上预览，尚未保存。"
                     : "正在检测仪屏幕上预览，尚未保存。");
}

void WebPortal::handleSaveColors() {
    for (uint8_t band = 0; band < 3; ++band) {
        gAirQualityColors.ledSaved[band] =
            gAirQualityColors.ledEdit[band];
        gAirQualityColors.displaySaved[band] =
            gAirQualityColors.displayEdit[band];
    }
    gAirQualityColors.previewLed = false;
    gAirQualityColors.previewDisplay = false;
    persistColorSettings();
    Serial.println("[COLOR] Saved all LED and display palette colors.");
    server_.send(200, "text/plain; charset=utf-8",
                 "三档灯光与屏幕颜色均已保存，重启后仍会保留。");
}

void WebPortal::handleCancelColorPreview() {
    restoreColorEdits();
    server_.send(200, "text/plain; charset=utf-8",
                 "已取消预览并恢复全部已保存颜色。");
}

bool WebPortal::parseClockMinute(const String& value,
                                 uint16_t& minute) const {
    if (value.length() != 5 || value.charAt(2) != ':') return false;
    for (uint8_t i : {0, 1, 3, 4}) {
        if (!isDigit(value.charAt(i))) return false;
    }
    const int hour = value.substring(0, 2).toInt();
    const int minutePart = value.substring(3, 5).toInt();
    if (hour < 0 || hour > 23 || minutePart < 0 || minutePart > 59) {
        return false;
    }
    minute = static_cast<uint16_t>(hour * 60 + minutePart);
    return true;
}

void WebPortal::handleNightSettings() {
    String json;
    json.reserve(180);
    json += "{\"enabled\":" +
            String(gNightMode.scheduleEnabled ? "true" : "false");
    json += ",\"start_minute\":" + String(gNightMode.startMinute);
    json += ",\"end_minute\":" + String(gNightMode.endMinute);
    json += ",\"active\":" + String(gNightMode.active ? "true" : "false");
    json += ",\"scheduled\":" +
            String(gNightMode.scheduledActive ? "true" : "false");
    json += ",\"manual_override\":" +
            String(gNightMode.manualOverride ? "true" : "false");
    json += ",\"time_valid\":" +
            String(gNightMode.timeValid ? "true" : "false") + "}";
    server_.send(200, "application/json", json);
}

void WebPortal::handleSaveNightSettings() {
    if (!server_.hasArg("enabled") || !server_.hasArg("start") ||
        !server_.hasArg("end")) {
        server_.send(400, "text/plain; charset=utf-8",
                     "缺少夜间模式参数。");
        return;
    }

    uint16_t startMinute;
    uint16_t endMinute;
    if (!parseClockMinute(server_.arg("start"), startMinute) ||
        !parseClockMinute(server_.arg("end"), endMinute) ||
        startMinute == endMinute) {
        server_.send(400, "text/plain; charset=utf-8",
                     "时间格式不正确，开始和结束时间也不能相同。");
        return;
    }

    const String enabled = server_.arg("enabled");
    if (enabled != "0" && enabled != "1") {
        server_.send(400, "text/plain; charset=utf-8",
                     "启用状态参数不正确。");
        return;
    }

    gNightMode.scheduleEnabled = enabled == "1";
    gNightMode.startMinute = startMinute;
    gNightMode.endMinute = endMinute;
    persistNightSettings();
    Serial.printf("[NIGHT] Saved schedule: %s %02u:%02u-%02u:%02u.\n",
                  gNightMode.scheduleEnabled ? "enabled" : "disabled",
                  startMinute / 60, startMinute % 60, endMinute / 60,
                  endMinute % 60);
    server_.send(200, "text/plain; charset=utf-8",
                 "夜间模式计划已保存，设备会自动应用。");
}

void WebPortal::clearSavedWifi() {
    preferences_.remove("wifi_ssid");
    preferences_.remove("wifi_pass");
    WiFi.disconnect(false, true);
    gNetwork.staConnected = false;
    gNetwork.staSsid = "";
    gNetwork.staIp = "";
    gNetwork.rssi = 0;
    disconnectedSinceMs_ = 0;
    startSetupAp();
    Serial.println("[WIFI] Saved network cleared. Setup hotspot is active.");
}
