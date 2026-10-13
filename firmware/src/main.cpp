// E-Ink Frame 2.0 — LOLIN D32 Pro + Waveshare 7.3" ACeP 7 colores (HAT F)
//
// Un ciclo:
//   despertar → medir batería (WiFi apagado) → WiFi rápido → 1 petición al servidor
//   → 304: dormir   |   200: 192 KB a PSRAM → WiFi OFF → volcar al panel → refresco (light sleep)
//   → pines en estado fijo → deep sleep el tiempo que diga el servidor.
//
// El servidor decide qué imagen mostrar y cuánto dormir; aquí no hay lógica de rotación.

#include <Arduino.h>
#include <HTTPClient.h>
#include <SPI.h>
#include <WiFi.h>
#include <driver/gpio.h>
#include <driver/rtc_io.h>
#include <esp_sleep.h>
#include <esp_wifi.h>
#include <rom/crc.h>

#include <GxEPD2_7C.h>
#include <Fonts/FreeSansBold18pt7b.h>
#include <Fonts/FreeSans12pt7b.h>

#if __has_include("config.h")
#include "config.h"
#else
#error "Falta include/config.h: copia include/config.example.h a include/config.h y rellénalo"
#endif

#ifndef FW_VERSION
#define FW_VERSION "dev"
#endif

#ifdef EINK_DEBUG
#define LOG(...) Serial.printf(__VA_ARGS__)
#else
#define LOG(...) \
  do {           \
  } while (0)
#endif

// ---------------------------------------------------------------------------
// Constantes
// ---------------------------------------------------------------------------
static constexpr uint32_t NATIVE_BYTES = 800UL * 480UL / 2UL;  // 4 bits por píxel
static constexpr uint32_t WIFI_TIMEOUT_MS = 8000;
static constexpr uint32_t HTTP_TIMEOUT_MS = 10000;
static constexpr uint32_t MIN_SLEEP_S = 60;
static constexpr uint32_t MAX_SLEEP_S = 24UL * 3600UL;
static constexpr uint32_t DEFAULT_SLEEP_S = 30UL * 60UL;
static constexpr uint32_t LOW_BATTERY_RECHECK_S = 6UL * 3600UL;
static constexpr uint32_t BROWNOUT_COOLDOWN_S = 30UL * 60UL;
static constexpr uint32_t STATE_MAGIC = 0xE1A2C0DE;

// ---------------------------------------------------------------------------
// Estado que sobrevive al deep sleep (RTC RAM). Se valida con CRC: tras un
// power-on o un brownout el contenido no es fiable.
// ---------------------------------------------------------------------------
struct RtcState {
  uint32_t magic;
  char etag[48];            // imagen que está en pantalla
  uint8_t bssid[6];         // AP y canal de la última conexión (conexión rápida)
  int32_t channel;
  uint16_t failCount;       // fallos seguidos (backoff)
  uint32_t lastAwakeMs;     // duración del ciclo anterior (se informa al servidor)
  uint8_t rotation;         // para dibujar la pantalla de batería baja
  uint16_t factorMilli;     // corrección del ADC (×1000) que manda el servidor
  uint16_t lowMv;
  uint16_t criticalMv;
  bool lowBatteryShown;
  char pendingReason[16];   // reinicio anómalo pendiente de informar (brownout, panic…)
  uint32_t crc;
};

RTC_DATA_ATTR RtcState st;

static uint32_t stateCrc() {
  return crc32_le(0, reinterpret_cast<const uint8_t*>(&st), offsetof(RtcState, crc));
}

static void saveState() { st.crc = stateCrc(); }

static void loadState() {
  if (st.magic == STATE_MAGIC && st.crc == stateCrc()) return;
  memset(&st, 0, sizeof(st));
  st.magic = STATE_MAGIC;
  st.rotation = DEFAULT_ROTATION;
  st.factorMilli = 1000;
  st.lowMv = 3500;
  st.criticalMv = 3300;
}

// ---------------------------------------------------------------------------
// Pantalla
// ---------------------------------------------------------------------------
#define EPD_PAGE_ROWS 40  // solo para la pantalla de batería baja (16 KB)
GxEPD2_7C<GxEPD2_730c_ACeP_730, EPD_PAGE_ROWS> display(
    GxEPD2_730c_ACeP_730(PIN_EPD_CS, PIN_EPD_DC, PIN_EPD_RST, PIN_EPD_BUSY));

static const gpio_num_t kOutPins[] = {
    (gpio_num_t)PIN_EPD_CS, (gpio_num_t)PIN_EPD_DC, (gpio_num_t)PIN_EPD_RST,
    (gpio_num_t)PIN_EPD_SCK, (gpio_num_t)PIN_EPD_MOSI};
static bool pinsReleased = false;

// Libera los pines retenidos durante el deep sleep para poder usar el SPI
static void releasePins() {
  if (pinsReleased) return;
  gpio_deep_sleep_hold_dis();
  for (gpio_num_t p : kOutPins) gpio_hold_dis(p);
  pinsReleased = true;
}

// Deja las entradas del HAT (con su adaptador de niveles) a niveles fijos durante el
// deep sleep: una entrada CMOS flotando puede consumir corriente de forma continua.
static void parkPins() {
  SPI.end();
  struct { int pin; int level; } levels[] = {
      {PIN_EPD_CS, HIGH},   // panel deseleccionado (y LED integrado apagado)
      {PIN_EPD_RST, HIGH},  // un pulso bajo despertaría al controlador
      {PIN_EPD_DC, LOW},
      {PIN_EPD_SCK, LOW},
      {PIN_EPD_MOSI, LOW},
  };
  for (auto& l : levels) {
    gpio_hold_dis((gpio_num_t)l.pin);
    pinMode(l.pin, OUTPUT);
    digitalWrite(l.pin, l.level);
    gpio_hold_en((gpio_num_t)l.pin);
  }
  pinMode(PIN_EPD_BUSY, INPUT);
  gpio_deep_sleep_hold_en();
}

// Mientras el panel refresca (~35 s) el ESP32 no tiene nada que hacer: light sleep
// hasta que BUSY suba (o 1 s como red de seguridad). Ahorra ~20 mA durante el refresco.
static void busyCallback(const void*) {
#if LIGHT_SLEEP_WHILE_BUSY
  gpio_wakeup_enable((gpio_num_t)PIN_EPD_BUSY, GPIO_INTR_HIGH_LEVEL);
  esp_sleep_enable_gpio_wakeup();
  esp_sleep_enable_timer_wakeup(1000000ULL);
  esp_light_sleep_start();
  gpio_wakeup_disable((gpio_num_t)PIN_EPD_BUSY);
  esp_sleep_disable_wakeup_source(ESP_SLEEP_WAKEUP_GPIO);
  esp_sleep_disable_wakeup_source(ESP_SLEEP_WAKEUP_TIMER);
#else
  delay(10);
#endif
}

static void displayBegin() {
  releasePins();
  SPI.begin(PIN_EPD_SCK, -1, PIN_EPD_MOSI, -1);
#ifdef EINK_DEBUG
  display.init(115200, true, 2, false);
#else
  display.init(0, true, 2, false);
#endif
  display.epd2.setBusyCallback(busyCallback);
}

static void showNative(const uint8_t* data) {
  displayBegin();
  uint32_t t0 = millis();
  display.epd2.writeNative(data, nullptr, 0, 0, 800, 480, false, false, false);
  display.epd2.refresh(false);
  display.hibernate();
  LOG("Refresco completo en %lu ms\n", millis() - t0);
}

static void centeredText(const char* text, const GFXfont* font, int16_t y, uint16_t color) {
  int16_t x1, y1;
  uint16_t w, h;
  display.setFont(font);
  display.setTextColor(color);
  display.getTextBounds(text, 0, 0, &x1, &y1, &w, &h);
  display.setCursor((display.width() - w) / 2 - x1, y);
  display.print(text);
}

static void showLowBattery(uint32_t mv) {
  displayBegin();
  display.setRotation(st.rotation & 3);
  display.setFullWindow();
  char volts[24];
  snprintf(volts, sizeof(volts), "%.2f V", mv / 1000.0f);
  display.firstPage();
  do {
    display.fillScreen(GxEPD_WHITE);
    const int16_t w = display.width(), h = display.height();
    const int16_t bw = w / 3, bh = bw / 2, bx = (w - bw) / 2, by = h / 2 - bh;
    for (int i = 0; i < 6; i++) display.drawRoundRect(bx + i, by + i, bw - 2 * i, bh - 2 * i, 10, GxEPD_BLACK);
    display.fillRect(bx + bw, by + bh / 3, bw / 12, bh / 3, GxEPD_BLACK);
    display.fillRect(bx + 14, by + 14, bw / 7, bh - 28, GxEPD_RED);
    centeredText("BATERIA BAJA", &FreeSansBold18pt7b, by + bh + 70, GxEPD_BLACK);
    centeredText("Carga el marco por USB", &FreeSans12pt7b, by + bh + 115, GxEPD_BLACK);
    centeredText(volts, &FreeSans12pt7b, by + bh + 155, GxEPD_RED);
  } while (display.nextPage());
  display.hibernate();
}

// ---------------------------------------------------------------------------
// Batería
// ---------------------------------------------------------------------------
static uint32_t readBatteryRawMv() {
  analogSetPinAttenuation(PIN_BATTERY, ADC_11db);
  analogReadMilliVolts(PIN_BATTERY);  // descartar la primera
  uint32_t sum = 0;
  constexpr int N = 64;
  for (int i = 0; i < N; i++) sum += analogReadMilliVolts(PIN_BATTERY);
  return (uint32_t)((sum / (float)N) * BATTERY_DIVIDER + 0.5f);
}

// ---------------------------------------------------------------------------
// Sueño
// ---------------------------------------------------------------------------
[[noreturn]] static void deepSleep(uint32_t seconds) {
  seconds = constrain(seconds, MIN_SLEEP_S, MAX_SLEEP_S);
  WiFi.mode(WIFI_OFF);
  st.lastAwakeMs = millis();
  saveState();
  LOG("Deep sleep %u s (despierto %u ms)\n", (unsigned)seconds, (unsigned)st.lastAwakeMs);
#ifdef EINK_DEBUG
  Serial.flush();
#endif
  parkPins();
#if PIN_BUTTON >= 0
  // Esperar a que se suelte el botón para no despertar al instante
  pinMode(PIN_BUTTON, INPUT_PULLUP);
  for (int i = 0; i < 500 && digitalRead(PIN_BUTTON) == LOW; i++) delay(10);
  rtc_gpio_pullup_en((gpio_num_t)PIN_BUTTON);
  rtc_gpio_pulldown_dis((gpio_num_t)PIN_BUTTON);
  esp_sleep_enable_ext0_wakeup((gpio_num_t)PIN_BUTTON, 0);
#endif
  esp_sleep_enable_timer_wakeup((uint64_t)seconds * 1000000ULL);
  esp_deep_sleep_start();
}

[[noreturn]] static void failAndSleep(const char* why) {
  st.failCount = min<uint16_t>(st.failCount + 1, 10);
  // 5, 10, 20, 40, 60, 60… minutos
  uint32_t s = min<uint32_t>(300UL << min<uint16_t>(st.failCount - 1, 4), 3600UL);
  LOG("ERROR: %s → reintento en %u s\n", why, (unsigned)s);
  deepSleep(s);
}

// ---------------------------------------------------------------------------
// Motivo del despertar
// ---------------------------------------------------------------------------
static const char* resetReasonName(esp_reset_reason_t r) {
  switch (r) {
    case ESP_RST_POWERON: return "poweron";
    case ESP_RST_BROWNOUT: return "brownout";
    case ESP_RST_PANIC: return "panic";
    case ESP_RST_INT_WDT:
    case ESP_RST_TASK_WDT:
    case ESP_RST_WDT: return "watchdog";
    case ESP_RST_SW: return "software";
    case ESP_RST_EXT: return "reset";
    default: return "unknown";
  }
}

static const char* wakeReason(bool& abnormal) {
  abnormal = false;
  esp_reset_reason_t rr = esp_reset_reason();
  if (rr == ESP_RST_DEEPSLEEP) {
    switch (esp_sleep_get_wakeup_cause()) {
      case ESP_SLEEP_WAKEUP_TIMER: return "timer";
      case ESP_SLEEP_WAKEUP_EXT0: return "button";
      default: return "other";
    }
  }
  abnormal = rr != ESP_RST_POWERON && rr != ESP_RST_EXT && rr != ESP_RST_SW;
  return resetReasonName(rr);
}

// ---------------------------------------------------------------------------
// WiFi
// ---------------------------------------------------------------------------
static bool waitWifi(uint32_t timeoutMs) {
  uint32_t t0 = millis();
  while (WiFi.status() != WL_CONNECTED) {
    if (millis() - t0 > timeoutMs) return false;
    delay(10);
  }
  return true;
}

static bool connectWifi() {
  WiFi.persistent(false);
  WiFi.mode(WIFI_STA);
  WiFi.setSleep(true);
  WiFi.setTxPower(WIFI_TX_POWER);
#if USE_STATIC_IP
  WiFi.config(IPAddress(STATIC_IP), IPAddress(GATEWAY_IP), IPAddress(SUBNET_MASK), IPAddress(DNS_IP));
#endif
  uint32_t t0 = millis();
  bool ok = false;
  if (st.channel > 0) {
    // Conexión rápida: sin escaneo, directo al AP y canal de la última vez
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD, st.channel, st.bssid, true);
    ok = waitWifi(WIFI_TIMEOUT_MS / 2);
    if (!ok) {
      LOG("Conexión rápida fallida, escaneando\n");
      WiFi.disconnect();
      st.channel = 0;
    }
  }
  if (!ok) {
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
    ok = waitWifi(WIFI_TIMEOUT_MS);
  }
  if (ok) {
    st.channel = WiFi.channel();
    memcpy(st.bssid, WiFi.BSSID(), 6);
    LOG("WiFi en %lu ms, IP %s, RSSI %d, canal %d\n", millis() - t0, WiFi.localIP().toString().c_str(),
        WiFi.RSSI(), st.channel);
  }
  return ok;
}

// ---------------------------------------------------------------------------
// Petición al servidor
// ---------------------------------------------------------------------------
struct FrameResponse {
  int code = -1;
  uint32_t sleepS = DEFAULT_SLEEP_S;
  String etag;
  uint8_t* data = nullptr;
};

static void applyServerHeaders(HTTPClient& http, FrameResponse& r) {
  long s = http.header("X-Sleep-Seconds").toInt();
  if (s > 0) r.sleepS = (uint32_t)s;
  r.etag = http.header("ETag");
  String rot = http.header("X-Rotation");
  if (rot.length()) st.rotation = (uint8_t)(rot.toInt() & 3);
  long f = http.header("X-Battery-Factor").toInt();
  if (f >= 500 && f <= 1500) st.factorMilli = (uint16_t)f;
  long low = http.header("X-Battery-Low-Mv").toInt();
  if (low >= 3000 && low <= 4200) st.lowMv = (uint16_t)low;
  long crit = http.header("X-Battery-Critical-Mv").toInt();
  if (crit >= 3000 && crit <= 4200) st.criticalMv = (uint16_t)crit;
}

static bool readBody(HTTPClient& http, uint8_t* buf, uint32_t expected) {
  WiFiClient* s = http.getStreamPtr();
  uint32_t got = 0, last = millis();
  while (got < expected) {
    int avail = s->available();
    if (avail > 0) {
      int n = s->read(buf + got, min<uint32_t>((uint32_t)avail, expected - got));
      if (n > 0) {
        got += n;
        last = millis();
      }
    } else {
      if (!s->connected()) break;
      if (millis() - last > HTTP_TIMEOUT_MS) break;
      delay(2);
    }
  }
  LOG("Recibidos %u/%u bytes\n", (unsigned)got, (unsigned)expected);
  return got == expected;
}

static FrameResponse requestFrame(uint32_t batteryRawMv, const char* wake) {
  FrameResponse r;
  String url = String(SERVER_URL) + "/api/device/frame?fw=" FW_VERSION "&bat=" + String(batteryRawMv) +
               "&rssi=" + String(WiFi.RSSI()) + "&wake=" + wake;
  if (st.lastAwakeMs > 0) url += "&awake=" + String(st.lastAwakeMs);

  HTTPClient http;
  http.setReuse(false);
  http.setConnectTimeout(5000);
  http.setTimeout(HTTP_TIMEOUT_MS);
  http.setUserAgent("eink-frame/" FW_VERSION);
  if (!http.begin(url)) return r;
  http.addHeader("Authorization", "Bearer " DEVICE_TOKEN);
  if (st.etag[0]) http.addHeader("If-None-Match", st.etag);
  static const char* keys[] = {"X-Sleep-Seconds", "ETag", "X-Rotation", "X-Battery-Factor",
                               "X-Battery-Low-Mv", "X-Battery-Critical-Mv"};
  http.collectHeaders(keys, sizeof(keys) / sizeof(keys[0]));

  r.code = http.GET();
  LOG("GET %s → %d\n", url.c_str(), r.code);
  if (r.code > 0) applyServerHeaders(http, r);

  if (r.code == HTTP_CODE_OK) {
    int len = http.getSize();
    if (len != (int)NATIVE_BYTES) {
      LOG("Tamaño inesperado: %d\n", len);
      r.code = -2;
    } else {
      r.data = (uint8_t*)(psramFound() ? ps_malloc(NATIVE_BYTES) : malloc(NATIVE_BYTES));
      if (!r.data) {
        LOG("Sin memoria para la imagen\n");
        r.code = -3;
      } else if (!readBody(http, r.data, NATIVE_BYTES)) {
        free(r.data);
        r.data = nullptr;
        r.code = -4;
      }
    }
  }
  http.end();
  return r;
}

// ---------------------------------------------------------------------------
void setup() {
  setCpuFrequencyMhz(80);  // suficiente para WiFi y SPI; consume bastante menos que 240 MHz
#ifdef EINK_DEBUG
  Serial.begin(115200);
  delay(50);
#endif
  loadState();

#ifdef SLEEP_TEST
  // Prueba de consumo en reposo: panel a deep sleep, pines aparcados y a dormir para
  // siempre. Mide la corriente con el multímetro en serie con la batería (rango µA/mA).
  LOG("SLEEP_TEST: batería %u mV. Durmiendo sin temporizador.\n", (unsigned)readBatteryRawMv());
  displayBegin();
  display.hibernate();
  parkPins();
  esp_deep_sleep_start();
#endif

  bool abnormal = false;
  const char* wake = wakeReason(abnormal);
  LOG("\n== E-Ink Frame " FW_VERSION " · despertar: %s ==\n", wake);

  if (abnormal) {
    // Reinicio por brownout/panic/watchdog: apuntarlo para informar y no reintentar
    // enseguida (un bucle de reinicios es lo que vaciaba la batería).
    strlcpy(st.pendingReason, wake, sizeof(st.pendingReason));
    st.channel = 0;  // por si el AP cambió
    deepSleep(strcmp(wake, "brownout") == 0 ? BROWNOUT_COOLDOWN_S : MIN_SLEEP_S * 5);
  }

  // 1) Batería, antes de encender el WiFi (con 120 mA de carga la lectura cae)
  const uint32_t rawMv = readBatteryRawMv();
  const uint32_t mv = rawMv * st.factorMilli / 1000;
  LOG("Batería: %u mV (bruto %u)\n", (unsigned)mv, (unsigned)rawMv);
  const bool batteryValid = rawMv > 2500;  // sin batería (solo USB) la lectura no tiene sentido
  if (batteryValid && mv < st.criticalMv) {
    if (!st.lowBatteryShown) {
      showLowBattery(mv);
      st.lowBatteryShown = true;
      st.etag[0] = '\0';  // al recuperarse, volver a pedir la foto
    }
    deepSleep(LOW_BATTERY_RECHECK_S);
  }
  if (st.lowBatteryShown && mv > st.criticalMv + 100) st.lowBatteryShown = false;

  // 2) WiFi
  if (!connectWifi()) failAndSleep("WiFi");

  // 3) Una petición: el servidor dice si hay imagen nueva y cuánto dormir
  const char* reported = st.pendingReason[0] ? st.pendingReason : wake;
  FrameResponse r = requestFrame(rawMv, reported);

  // 4) Apagar el WiFi antes de tocar la pantalla
  WiFi.disconnect(true);
  WiFi.mode(WIFI_OFF);

  if (r.code == HTTP_CODE_OK && r.data) {
    st.pendingReason[0] = '\0';
    st.failCount = 0;
    showNative(r.data);
    free(r.data);
    strlcpy(st.etag, r.etag.c_str(), sizeof(st.etag));
    deepSleep(r.sleepS);
  }
  if (r.code == HTTP_CODE_NOT_MODIFIED || r.code == HTTP_CODE_NO_CONTENT) {
    st.pendingReason[0] = '\0';
    st.failCount = 0;
    deepSleep(r.sleepS);
  }
  if (r.code == HTTP_CODE_UNAUTHORIZED) failAndSleep("token rechazado (revisa DEVICE_TOKEN)");
  failAndSleep("servidor");
}

void loop() {
  // No se llega nunca: setup() siempre termina en deep sleep
  deepSleep(DEFAULT_SLEEP_S);
}
