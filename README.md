# GrainGuard IoT: Ultra-Low-Cost Multi-Spectral Grain Spoilage & FEFO Decision Engine

> **Multi-Spectral Early Spoilage Detection via Headspace Metabolic Respiration ($CO_2$), Differential Microclimate Rate-of-Change ($\Delta T, \Delta RH$), and Automated First-Expired, First-Out (FEFO) Warehouse Prioritization.**

---

## 1. Executive Summary & Value Proposition

Traditional grain warehouse monitoring relies on manual spear sampling or basic ambient room temperature sensors. Because grain bulk is a natural thermal insulator with high thermal inertia, **internal mold rot and pest hotspots remain hidden for 3 to 5 days** until thermal conduction or wetness diffusion reaches the outer boundaries—by which point irreversible grain caking, mycotoxin contamination, and financial loss have occurred.

**GrainGuard IoT** overcomes thermal lag through **Metabolic Respiration Early Detection**:
1. **Biological Respiration Gas Diffusion**: Fungal spores and weevils consume oxygen and exhale $CO_2$ rapidly in interstitial headspace voids. Gas diffuses through grain air pockets within minutes, providing an advance warning window **3 to 5 days before core temperatures rise**.
2. **Differential Matrix Logic ($\Delta T = T_{\text{Core}} - T_{\text{Outer Wall}}$)**: Solar diurnal warming heats godowns *outside-in* ($\Delta T < 0$, flat $CO_2$). Biological spoilage heats *inside-out* ($\Delta T > 0$, surging $CO_2$). Cross-referencing core heat with $CO_2$ eliminates costly false weather alarms.
3. **FEFO (First-Expired, First-Out) Logistics Decision Engine**: Ingests real-time multi-spectral sensor data, computes **Days-to-Spoilage (DTS)**, and automatically promotes at-risk grain lots to **Rank #1 FEFO Dispatch**, enabling warehouse managers to prioritize them for immediate milling or flour processing before quality degrades.

---

## 2. System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Grain Storage Physical Nodes             │
│  [Spear Probe / Rod Array: DHT22 + Capacitive Moisture]     │
│  [Headspace Mount: MQ-135 CO2/Air Quality Proxy]            │
│  [Ambient Sensor: Outer Wall Temperature]                   │
└──────────────────────────────┬──────────────────────────────┘
                               │ (I2C / 1-Wire / ADC / GPIO)
                               ▼
┌─────────────────────────────────────────────────────────────┐
│              ESP32 Edge Microcontroller Node                │
│  - Polls sensors every 5s                                   │
│  - Formats JSON payload with container metadata             │
│  - Transmits via Wi-Fi HTTP POST                            │
└──────────────────────────────┬──────────────────────────────┘
                               │ HTTP POST /api/telemetry (JSON)
                               ▼
┌─────────────────────────────────────────────────────────────┐
│         Flask Backend & FEFO Risk Calculation Engine        │
│  - Differential Matrix Logic (ΔT = T_Core - T_Outer)        │
│  - Metabolic Respiration Velocity (d[CO2]/dt)               │
│  - Days-to-Spoilage (DTS) Multi-Factor Polynomial Model      │
│  - Dynamic FEFO Priority Sorter (Rank #1 = Urgent Dispatch)  │
│  - REST API Endpoints & In-Memory / SQLite Telemetry Store  │
└──────────────────────────────┬──────────────────────────────┘
                               │ Real-Time Polling / REST API
                               ▼
┌─────────────────────────────────────────────────────────────┐
│          Modern FEFO Logistics Mission-Control Web UI       │
│  - Live Warehouse Overview KPIs (At-Risk Tons, Risk Index)  │
│  - FEFO Priority Dispatch Queue Table (Direct Mill routing) │
│  - Visual Container Health Cards with Glow Indicators       │
│  - Interactive Multi-Spectral Time-Series Lead Charts        │
│  - Hackathon Demo Controls (Breath Test, Solar Wave, Reset) │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. Quick Start & Execution

### Prerequisites
- Python 3.10+ (Flask, Flask-CORS, Requests)
- Optional: ESP32 Dev Board + Arduino IDE (for physical hardware)

### 1. Launch the Backend Server
```bash
python app.py
```
*Access the Web Dashboard at: `http://127.0.0.1:5000`*

### 2. Launch Multi-Node Telemetry Simulator (Optional / Parallel Terminal)
```bash
python mock_esp32.py
```
*Simulates 6 storage units streaming continuous telemetry.*

---

## 4. Live Hackathon Demonstration Sequence

Use the **Interactive Live Demo Bar** directly in the Web UI (or execute via API):

| Step | Action / Scenario | Demonstrated Value | Observed System Response |
| :--- | :--- | :--- | :--- |
| **1** | **Normal Storage Baseline** | Safe certified storage operation | All units `OPTIMAL` (Green), $CO_2 < 500$ ppm, DTS > 100 days. |
| **2** | **Breath Exhale Trigger ($CO_2$ Surge)** | Metabolic respiration of active mold | Unit instantly leaps to **CRITICAL** (Red), jumps to **Rank #1 FEFO Dispatch**, audio-visual banner triggers. |
| **3** | **Diurnal Solar Heat Wave** | Outside-in diurnal weather heating | Ambient rises to 38.5°C, but Differential Matrix recognizes $\Delta T < 0$ and flat $CO_2$, rejecting false alarm! |
| **4** | **Core Water Infiltration** | Roof rain leak / condensation | Capacitive moisture jumps to 19.8%, RH to 84%, triggering early preventative warning. |
| **5** | **1-Click FEFO Milling Dispatch** | Automated warehouse logistics action | Unit dispatched to milling plant, telemetry reset with certified fresh stock batch. |

---

## 5. Hardware Specifications & Pin Mapping

| Component | Function | Operating Voltage | Connection to ESP32 |
| :--- | :--- | :--- | :--- |
| **ESP32 Dev Module** | Edge Microcontroller & Wi-Fi Node | 5V / 3.3V Logic | Master Controller |
| **MQ-135 Gas Sensor** | Headspace Respiration Proxy ($CO_2$) | 5V (Heater), 3.3V Out | `AOUT` $\rightarrow$ `GPIO 35` (ADC1_CH7) |
| **DHT22 / DHT11** | Grain Core Temp & Equilibrium RH | 3.3V - 5V | `DATA` $\rightarrow$ `GPIO 4` |
| **Capacitive Soil Moisture Sensor** | Direct Grain Contact Dampness | 3.3V | `AOUT` $\rightarrow$ `GPIO 34` (ADC1_CH6) |
| **Status Indicator LED** | Telemetry Transmission Blink | 3.3V | `Anode` $\rightarrow$ `GPIO 2` |

*Refer to `firmware/HARDWARE_SETUP.md` for complete schematics and sensor calibration details.*

---

## 6. Software & Algorithmic Design

### Mathematical Days-to-Spoilage (DTS) Model
The composite risk score $R \in [0, 100]$ is computed as:
$$R = 0.45 \cdot R_{\text{CO}_2} + 0.30 \cdot R_{\text{RH \& Moisture}} + 0.25 \cdot R_{\text{Thermal}}$$

Where:
- $R_{\text{CO}_2}$ is the non-linear respiration function tracking absolute $CO_2$ ppm and the velocity derivative $\frac{d[CO_2]}{dt}$.
- $R_{\text{RH \& Moisture}}$ evaluates equilibrium relative humidity relative to the critical 65% fungal equilibrium boundary and core dampness.
- $R_{\text{Thermal}}$ is modulated by the differential thermal gradient $\Delta T = T_{\text{Core}} - T_{\text{Ambient}}$.

Estimated Days to Spoilage (DTS) is determined via piece-wise decay:
$$\text{DTS} = \begin{cases} 
180.0 & R \le 5 \\
180 - \left(\frac{R - 5}{20}\right) \times 120 & 5 < R \le 25 \\
60 - \left(\frac{R - 25}{25}\right) \times 45 & 25 < R \le 50 \\
14 - \left(\frac{R - 50}{25}\right) \times 10 & 50 < R \le 75 \quad \text{(3-5 Day Respiration Early Window)} \\
\max\left(0.5, 3.5 - \left(\frac{R - 75}{25}\right) \times 3.0\right) & R > 75 \quad \text{(Thermal Bio-Heating Runaway)}
\end{cases}$$
