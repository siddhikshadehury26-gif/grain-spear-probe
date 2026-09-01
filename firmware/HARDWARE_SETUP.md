# GrainGuard-IoT Hardware Architecture & Wiring Guide

This document specifies the complete physical wiring, component specifications, pinout mapping, and calibration procedures for the ultra-low-cost multi-spectral grain spoilage monitoring node.

---

## 1. Bill of Materials (BOM) & Component Map

| Component | Function | Operating Voltage | Pin Type | Connection to ESP32 |
| :--- | :--- | :--- | :--- | :--- |
| **ESP32 Dev Module** (30-pin / 38-pin) | Edge Microcontroller & Wi-Fi Node | 5V (MicroUSB) / 3.3V Logic | MCU | Master Controller |
| **MQ-135 Gas Sensor** | Headspace Metabolic Respiration ($CO_2$, Ammonia, VOCs) | 5V (Heater), 3.3V Analog Out | Analog | `AOUT` $\rightarrow$ `GPIO 35` (ADC1_CH7) |
| **DHT22 (AM2302) or DHT11** | Grain Core Temperature & Equilibrium RH (%) | 3.3V - 5V | Digital (1-Wire) | `DATA` $\rightarrow$ `GPIO 4` (with 10k pullup) |
| **Capacitive Soil Moisture Sensor v1.2** | Grain Core Contact Moisture / Dampness | 3.3V | Analog | `AOUT` $\rightarrow$ `GPIO 34` (ADC1_CH6) |
| **Status LED & 220Ω Resistor** (Optional) | Telemetry TX Indicator | 3.3V | Digital Out | `Anode` $\rightarrow$ `GPIO 2` |
| **Perforated Spear Probe Sheath** | Mechanical dust barrier & micro-climate filter | N/A | Enclosure | Shielding core sensors |

---

## 2. Wiring & Pinout Blueprint

```
                     ┌────────────────────────┐
                     │     ESP32 Dev Board    │
                     │                        │
       [ 5V Power ] ─┤ VIN                GND ├─ [ Common Ground ]
     [ 3.3V Power ] ─┤ 3V3             GPIO 2 ├─ [ Status LED ]
                     │                        │
  MQ-135 Analog Out ─┤ GPIO 35        GPIO 4  ├─ DHT22 Data (Core Temp & RH)
Capacitive Moisture ─┤ GPIO 34                │
                     │                        │
                     └────────────────────────┘
```

### Detailed Wire Connections:
1. **MQ-135 Gas Sensor**:
   - `VCC` $\rightarrow$ ESP32 `VIN` (5V recommended for sensor heater filament)
   - `GND` $\rightarrow$ ESP32 `GND`
   - `AOUT` $\rightarrow$ ESP32 `GPIO 35`
2. **DHT22 / DHT11 Sensor**:
   - `VCC` $\rightarrow$ ESP32 `3V3` (or `5V`)
   - `GND` $\rightarrow$ ESP32 `GND`
   - `DATA` $\rightarrow$ ESP32 `GPIO 4` (Place a $4.7\text{k}\Omega - 10\text{k}\Omega$ pull-up resistor between `VCC` and `DATA` if using bare sensor module).
3. **Capacitive Soil Moisture Probe**:
   - `VCC` $\rightarrow$ ESP32 `3V3`
   - `GND` $\rightarrow$ ESP32 `GND`
   - `AOUT` $\rightarrow$ ESP32 `GPIO 34`

---

## 3. Physical Risk Mitigations & Enclosure Design

1. **Dust & Hot Filament Isolation**:
   - The MQ-135 contains a heated micro-filament. In grain godowns where fine grain dust is explosive, the MQ-135 must be housed inside a **flame-arrestor mesh enclosure** (fine stainless steel 316 wire mesh, 100+ mesh count) placed in the container headspace.
2. **Perforated Spear Insertion Rod**:
   - Core sensors (DHT22 and Capacitive Probe) are housed inside a 1-meter slotted PVC/FRP spear with drilled 2mm air diffusion holes, preventing physical abrasion from grain kernels during insertion and extraction.
3. **Thermal Lag Compensation**:
   - Headspace $CO_2$ gas diffuses quickly through the air interstitial pockets (minutes to hours), while temperature conduction through grain bulk takes 3–5 days. The firmware prioritizes $CO_2$ rate-of-change ($\Delta CO_2 / \Delta t$) for instant hazard classification.

---

## 4. Calibration & Quick-Start Verification (Phase B)

1. Open `firmware/esp32_firmware.ino` in **Arduino IDE**.
2. Install required Arduino libraries via Library Manager:
   - `DHT sensor library` by Adafruit
   - `Adafruit Unified Sensor`
3. Update `WIFI_SSID`, `WIFI_PASSWORD`, and `SERVER_URL` (with your computer's local IP address, e.g. `http://192.168.1.50:5000/api/telemetry`).
4. Select board **ESP32 Dev Module**, select the appropriate COM Port, and click **Upload**.
5. Open the **Serial Monitor** at **115200 baud**.
6. **Live Sensor Verification**:
   - **MQ-135 Breath Test**: Exhale gently onto the MQ-135 sensor. Observe $CO_2$ readings surging from ~420 ppm to 2,000+ ppm.
   - **Capacitive Moisture Test**: Touch the probe tip with a damp paper towel. Observe moisture percentage jumping from ~12% to ~22%.
   - **DHT Sensor**: Touch the sensor body with fingers to observe temperature rising above ambient.
