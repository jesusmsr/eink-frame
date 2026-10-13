// Copia este fichero como config.h (está en .gitignore) y rellena tus datos.
#pragma once

// ---------- WiFi ----------
#define WIFI_SSID      "TuWiFi"
#define WIFI_PASSWORD  "TuContraseña"

// IP fija: ahorra ~1 s de DHCP en cada despertar. 0 = usar DHCP.
#define USE_STATIC_IP  1
#define STATIC_IP      192, 168, 1, 60
#define GATEWAY_IP     192, 168, 1, 1
#define SUBNET_MASK    255, 255, 255, 0
#define DNS_IP         192, 168, 1, 1

// Potencia de emisión WiFi. Bajarla reduce los picos de corriente (menos riesgo de
// brownout con la batería baja) a cambio de menos alcance. Opciones de WiFiGeneric.h:
// WIFI_POWER_19_5dBm, WIFI_POWER_17dBm, WIFI_POWER_15dBm, WIFI_POWER_13dBm...
#define WIFI_TX_POWER  WIFI_POWER_17dBm

// ---------- Servidor ----------
// IP LAN del NAS + puerto publicado en compose.yaml. HTTP plano (sin TLS) a propósito:
// es más rápido y gasta menos que pasar por Cloudflare.
#define SERVER_URL     "http://192.168.1.10:8080"
// Mismo valor que DEVICE_TOKEN en el .env del contenedor
#define DEVICE_TOKEN   "pon-aqui-el-token"

// ---------- Pines (LOLIN D32 Pro + Waveshare 7.3" HAT (F)) ----------
#define PIN_EPD_CS     5    // ojo: es también el LED integrado de la D32 Pro
#define PIN_EPD_DC     27
#define PIN_EPD_RST    26
#define PIN_EPD_BUSY   25
#define PIN_EPD_SCK    18   // VSPI por defecto
#define PIN_EPD_MOSI   23   // VSPI por defecto

#define PIN_BATTERY    35   // _VBAT en la D32 Pro (divisor 100k/100k)
#define BATTERY_DIVIDER 2.0f

// Botón opcional "siguiente foto" entre el pin y GND. Debe ser un pin RTC
// (p. ej. 32 o 33, libres si no usas pantalla TFT). -1 = sin botón.
#define PIN_BUTTON     -1

// Rotación por defecto para la pantalla de "batería baja" (el servidor la actualiza)
#define DEFAULT_ROTATION 3

// Esperar el refresco (~35 s) en light sleep en vez de con la CPU activa.
#define LIGHT_SLEEP_WHILE_BUSY 1
