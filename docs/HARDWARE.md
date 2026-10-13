# Hardware y diagnóstico

## Conexiones (LOLIN D32 Pro → Waveshare 7.3" e-Paper HAT (F))

| HAT | D32 Pro | Notas |
|---|---|---|
| VCC | 3V3 | |
| GND | GND | |
| DIN | GPIO 23 | MOSI (VSPI) |
| CLK | GPIO 18 | SCK (VSPI) |
| CS | GPIO 5 | También es el LED integrado |
| DC | GPIO 27 | |
| RST | GPIO 26 | |
| BUSY | GPIO 25 | |

La batería se mide en **GPIO 35** (divisor 100k/100k de la placa, `_VBAT` en el core de Arduino). El cargador integrado es un TP4054 (máx. 500 mA) que carga por hardware cuando hay USB: el firmware no interviene.

## Prueba 1 · ¿La placa duerme de verdad?

Con 5000 mAh durando 1–2 días, el consumo medio era de ~100–200 mA: el ESP32 prácticamente no dormía.

1. Multímetro en **corriente**, en serie entre el + de la batería y la placa. Sin USB.
2. Con el **firmware antiguo**: observa 2–3 minutos después de que termine el refresco.
   - Por debajo de 1 mA → dormía; el problema es la batería (prueba 2).
   - Decenas de mA de forma constante o con picos cada pocos segundos → no dormía, o se reiniciaba en bucle (brownout).
3. Con `pio run -e sleeptest -t upload` (firmware que solo hiberna el panel y duerme): esta es la **línea base** de placa + HAT.
   - Esperable: del orden de 0,1–0,5 mA (ESP32 en deep sleep, regulador, divisor de 21 µA, adaptador de niveles del HAT).
   - Si sale bastante más, comprueba si hay una microSD puesta o si el LED de GPIO 5 queda encendido.

## Prueba 2 · ¿Carga la batería?

1. Sin USB, mide la tensión en bornes de la batería (V₀).
2. Conecta un **cargador de pared** de 5 V (no un puerto de PC) con un cable de datos/carga fiable. Comprueba si se enciende el LED de carga de la placa.
3. Pasados 15 minutos, vuelve a medir: tiene que subir hacia 4,2 V.
   - Si no sube y el LED de carga está apagado → la protección de la batería ha cortado (descarga profunda), o hay un problema de conector/polaridad.
   - Si el LED está encendido pero la tensión apenas sube → batería degradada o de menos capacidad de la indicada. Cámbiala.
4. **Antes de conectar una batería nueva**, comprueba la polaridad del JST PH 2.0: muchas baterías vienen con los cables al revés respecto a las placas LOLIN.

## Prueba 3 · Calibrar la lectura de batería

Con el firmware nuevo funcionando:
1. Espera a que el marco se conecte (en *Marco* verás la nueva lectura).
2. Mide la batería con el multímetro.
3. En *Marco → Calibrar batería*, introduce el valor. El servidor calcula el factor de corrección y lo envía al marco en la siguiente conexión.

## Calibrar la paleta de colores

1. *Ajustes → Paleta → Enviar carta de calibración*. Saldrá en la próxima conexión.
2. Fotografía el marco con luz natural, sin flash, de frente.
3. Con un cuentagotas (cualquier editor de fotos), toma el color de cada franja y ponlo en *Ajustes → Paleta*.
4. Guarda: todas las imágenes se regeneran con la paleta nueva, y la vista previa del panel web pasa a coincidir con lo que ves en el marco.

## Consumo esperado del firmware 2.0

Son estimaciones; la gráfica «Tiempo despierto por conexión» de la página *Marco* te da los datos reales.

| Ciclo | Despierto | Carga aprox. |
|---|---|---|
| Sin cambios (304) | 1–2 s con WiFi | ~0,05 mAh |
| Foto nueva | ~2–3 s con WiFi + ~35 s de refresco en light sleep | ~0,3 mAh |

Con una foto cada 30 min y silencio de 00:00 a 07:00 son 34 refrescos al día, unos 10–15 mAh/día más el consumo en reposo. Con 5000 mAh reales eso son **meses**, no días, siempre que la línea base de la prueba 1 salga baja.
