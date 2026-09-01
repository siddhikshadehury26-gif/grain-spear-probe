/*
 * ============================================================================================
 * GrainGuard-IoT: Multi-Spectral Grain Spoilage & FEFO Telemetry Node
 * Target Microcontroller: ESP32 Dev Module / NodeMCU-32S
 * Sensors:
 *   1. MQ-135 Gas Sensor (Headspace Respiration / CO2 proxy) -> GPIO 35 (ADC1_CH7)
 *   2. Capacitive Soil Moisture Sensor v1.2 (Core dampness) -> GPIO 34 (ADC1_CH6)
 *   3. DHT11 / DHT22 (Core Microclimate Temp & RH) -> GPIO 4 (Digital)
 *   4. Onboard Status LED -> GPIO 2 (Blinks on telemetry transmission)
 * ============================================================================================
 */

#include <WiFi.h>
#include <HTTPClient.h>
#include <DHT.h>

// ==========================================
// 1. NETWORK & SERVER CONFIGURATION
// ==========================================
const char* WIFI_SSID     = "YOUR_WIFI_SSID";       // Set your Wi-Fi SSID / Mobile Hotspot
const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";   // Set your Wi-Fi Password

// Backend Flask server URL (Replace with your computer's local IP address e.g. 192.168.1.100)
const char* SERVER_URL    = "http://192.168.1.100:5000/api/telemetry";

// Container Identification Metadata
const char* CONTAINER_ID  = "SPEAR-D01";
const char* STORAGE_TYPE  = "Live ESP32 Spear Probe";
const char* GRAIN_TYPE    = "Paddy Grain Bags";
const float CAPACITY_TONS = 15.0;

// Telemetry Transmission Interval (milliseconds)
const unsigned long POLL_INTERVAL_MS = 5000; 

// ==========================================
// 2. HARDWARE PIN DEFINITIONS
// ==========================================
#define DHTPIN        4       // Digital pin connected to DHT sensor
#define DHTTYPE       DHT22   // DHT11 or DHT22 (AM2302)
#define PIN_MOISTURE  34      // ADC1 channel for Capacitive Moisture Probe
#define PIN_MQ135     35      // ADC1 channel for MQ-135 Gas Sensor
#define PIN_LED       2       // Built-in status LED

DHT dht(DHTPIN, DHTTYPE);

// ==========================================
// 3. CALIBRATION CONSTANTS
// ==========================================
// Capacitive Moisture Sensor Calibration (Air vs Pure Water ADC values)
const int MOISTURE_AIR_VAL   = 3150; // Dry air ADC reading (~10% moisture)
const int MOISTURE_WATER_VAL = 1350; // Saturated water ADC reading (~25% moisture)

// MQ-135 Sensor Load Resistor & Clean Air Baseline
const float RL_VALUE         = 10.0; // Load resistance in kilo-ohms
const float RO_CLEAN_AIR     = 76.6; // Baseline clean air resistance (calibrated at ~400ppm)

unsigned long lastTransmissionTime = 0;

// ==========================================
// 4. HELPER FUNCTIONS
// ==========================================

// Smooth analog readings with 10-sample rolling average
int readSmoothedADC(int pin, int samples = 10) {
  long sum = 0;
  for (int i = 0; i < samples; i++) {
    sum += analogRead(pin);
    delay(5);
  }
  return sum / samples;
}

// Convert MQ-135 ADC reading into approximate CO2 / Air Quality ppm
float calculateCO2_PPM(int rawADC) {
  float sensorVolt = ((float)rawADC / 4095.0) * 3.3;
  if (sensorVolt <= 0.1) return 400.0;
  
  // Calculate sensor resistance RS
  float RS = ((3.3 - sensorVolt) / sensorVolt) * RL_VALUE;
  float ratio = RS / RO_CLEAN_AIR;
  
  // Power-law approximation for MQ-135 CO2 curve: ppm = a * (RS/RO)^b
  // Parameters typical for CO2 curve: a ≈ 116.6, b ≈ -2.76
  float ppm = 116.6 * pow(ratio, -2.76);
  
  // Clamp within realistic agricultural atmospheric ranges (350 to 5000 ppm)
  if (ppm < 380.0) ppm = 380.0;
  if (ppm > 5000.0) ppm = 5000.0;
  return ppm;
}

// Convert Capacitive ADC to calibrated Grain Moisture Content %
float calculateMoisturePercent(int rawADC) {
  // Linear interpolation between calibrated dry and wet limits
  float percent = 10.0 + ((float)(MOISTURE_AIR_VAL - rawADC) / (float)(MOISTURE_AIR_VAL - MOISTURE_WATER_VAL)) * 15.0;
  if (percent < 9.0) percent = 9.0;
  if (percent > 28.0) percent = 28.0;
  return percent;
}

// Connect or reconnect to Wi-Fi
void connectToWiFi() {
  if (WiFi.status() == WL_CONNECTED) return;
  
  Serial.print("[WiFi] Connecting to: ");
  Serial.println(WIFI_SSID);
  
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  
  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 20) {
    delay(500);
    Serial.print(".");
    digitalWrite(PIN_LED, !digitalRead(PIN_LED));
    attempts++;
  }
  
  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\n[WiFi] Connected successfully!");
    Serial.print("[WiFi] IP Address: ");
    Serial.println(WiFi.localIP());
    digitalWrite(PIN_LED, HIGH);
  } else {
    Serial.println("\n[WiFi] Connection failed. Will retry in loop.");
    digitalWrite(PIN_LED, LOW);
  }
}

// ==========================================
// 5. SETUP
// ==========================================
void setup() {
  Serial.begin(115200);
  delay(1000);
  
  Serial.println("=================================================");
  Serial.println(" GrainGuard-IoT: Multi-Spectral Telemetry Node   ");
  Serial.println(" Early Spoilage & FEFO Decision Dispatch System  ");
  Serial.println("=================================================");
  
  pinMode(PIN_LED, OUTPUT);
  pinMode(PIN_MOISTURE, INPUT);
  pinMode(PIN_MQ135, INPUT);
  
  // Set ADC attenuation to 11dB for full 0-3.3V range
  analogSetAttenuation(ADC_11db);
  
  dht.begin();
  Serial.println("[Sensors] DHT Initialized.");
  
  connectToWiFi();
}

// ==========================================
// 6. MAIN POLLING LOOP
// ==========================================
void loop() {
  // Ensure Wi-Fi remains connected
  if (WiFi.status() != WL_CONNECTED) {
    connectToWiFi();
  }

  unsigned long currentMillis = millis();
  if (currentMillis - lastTransmissionTime >= POLL_INTERVAL_MS) {
    lastTransmissionTime = currentMillis;

    // 1. Read DHT Sensor (Core Temp & RH)
    float humidity = dht.readHumidity();
    float temperature = dht.readTemperature();
    
    // Fallback if DHT fails to read
    if (isnan(humidity) || isnan(temperature)) {
      Serial.println("[WARN] Failed to read from DHT sensor! Using fallback default.");
      humidity = 55.0;
      temperature = 22.5;
    }

    // 2. Read Capacitive Moisture Probe
    int rawMoistureADC = readSmoothedADC(PIN_MOISTURE);
    float coreMoisture = calculateMoisturePercent(rawMoistureADC);

    // 3. Read MQ-135 Gas Sensor (Headspace Respiration)
    int rawGasADC = readSmoothedADC(PIN_MQ135);
    float co2_ppm = calculateCO2_PPM(rawGasADC);

    // Estimate outer wall ambient temperature (ambient proxy)
    float ambientTemp = temperature + 0.5;

    // Print Diagnostics to Serial Monitor
    Serial.println("\n--- [TELEMETRY SNAPSHOT] ---");
    Serial.printf("Node ID       : %s (%s)\n", CONTAINER_ID, GRAIN_TYPE);
    Serial.printf("Core Temp     : %.1f °C\n", temperature);
    Serial.printf("Equilibrium RH: %.1f %%\n", humidity);
    Serial.printf("Core Moisture : %.1f %% (Raw ADC: %d)\n", coreMoisture, rawMoistureADC);
    Serial.printf("Headspace CO2 : %.1f ppm (Raw ADC: %d)\n", co2_ppm, rawGasADC);
    Serial.println("----------------------------");

    // 4. Send HTTP POST to Flask Backend
    if (WiFi.status() == WL_CONNECTED) {
      HTTPClient http;
      http.begin(SERVER_URL);
      http.addHeader("Content-Type", "application/json");

      // Construct JSON payload
      char payload[350];
      snprintf(payload, sizeof(payload),
        "{\"container_id\":\"%s\",\"storage_type\":\"%s\",\"grain_type\":\"%s\",\"capacity_tons\":%.1f,\"temperature\":%.1f,\"ambient_temp\":%.1f,\"humidity\":%.1f,\"core_moisture\":%.1f,\"headspace_co2\":%.1f}",
        CONTAINER_ID, STORAGE_TYPE, GRAIN_TYPE, CAPACITY_TONS, temperature, ambientTemp, humidity, coreMoisture, co2_ppm
      );

      digitalWrite(PIN_LED, HIGH); // Flash LED during POST
      int httpResponseCode = http.POST(payload);

      if (httpResponseCode > 0) {
        String response = http.getString();
        Serial.printf("[HTTP] POST Success (Code %d): %s\n", httpResponseCode, response.c_str());
      } else {
        Serial.printf("[HTTP] POST Failed! Error: %s\n", http.errorToString(httpResponseCode).c_str());
      }
      
      http.end();
      digitalWrite(PIN_LED, LOW);
    } else {
      Serial.println("[HTTP] Cannot send payload: WiFi not connected.");
    }
  }
}
