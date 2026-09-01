"""
mock_esp32.py - Multi-Node IoT Telemetry Simulation Engine
Simulates ESP32 edge probes streaming multi-spectral sensor data over HTTP POST to the Flask backend.
"""

import time
import random
import argparse
import requests
import sys

SERVER_URL = "http://127.0.0.1:5000"

SIMULATED_NODES = [
    {
        "container_id": "SILO-A01",
        "storage_type": "Vertical Central Rod Array",
        "grain_type": "Hard Red Winter Wheat",
        "capacity_tons": 120.0,
        "temperature": 22.2,
        "ambient_temp": 22.8,
        "humidity": 55.5,
        "core_moisture": 12.5,
        "headspace_co2": 430.0,
        "state": "normal"
    },
    {
        "container_id": "SILO-A02",
        "storage_type": "Vertical Central Rod Array",
        "grain_type": "Premium Basmati Rice",
        "capacity_tons": 85.0,
        "temperature": 23.8,
        "ambient_temp": 24.2,
        "humidity": 60.5,
        "core_moisture": 13.4,
        "headspace_co2": 680.0,
        "state": "elevated"
    },
    {
        "container_id": "STACK-B01",
        "storage_type": "Handheld Spear Probe Stack",
        "grain_type": "Yellow Dent Corn",
        "capacity_tons": 40.0,
        "temperature": 26.5,
        "ambient_temp": 24.9,
        "humidity": 67.8,
        "core_moisture": 15.0,
        "headspace_co2": 1380.0,
        "state": "warning"
    },
    {
        "container_id": "STACK-B02",
        "storage_type": "Handheld Spear Probe Stack",
        "grain_type": "Soybean Seed Stacks",
        "capacity_tons": 35.0,
        "temperature": 21.8,
        "ambient_temp": 22.1,
        "humidity": 51.5,
        "core_moisture": 11.8,
        "headspace_co2": 410.0,
        "state": "normal"
    },
    {
        "container_id": "CONT-C01",
        "storage_type": "Containerized Godown Array",
        "grain_type": "Malt Barley",
        "capacity_tons": 60.0,
        "temperature": 22.8,
        "ambient_temp": 34.0, # Solar heating demonstration
        "humidity": 57.5,
        "core_moisture": 12.9,
        "headspace_co2": 450.0,
        "state": "solar"
    },
    {
        "container_id": "SPEAR-D01",
        "storage_type": "Live ESP32 Spear Probe",
        "grain_type": "Paddy Grain Bags",
        "capacity_tons": 15.0,
        "temperature": 23.0,
        "ambient_temp": 23.5,
        "humidity": 56.0,
        "core_moisture": 13.0,
        "headspace_co2": 445.0,
        "state": "live_demo"
    }
]

def update_node_telemetry(node):
    """Applies physics/biology variations based on container state"""
    state = node.get("state", "normal")
    
    if state == "normal":
        # Slight natural jitter around baseline
        node["temperature"] = round(node["temperature"] + random.uniform(-0.1, 0.1), 1)
        node["ambient_temp"] = round(node["ambient_temp"] + random.uniform(-0.15, 0.15), 1)
        node["humidity"] = round(max(45.0, min(62.0, node["humidity"] + random.uniform(-0.3, 0.3))), 1)
        node["core_moisture"] = round(max(11.0, min(14.0, node["core_moisture"] + random.uniform(-0.05, 0.05))), 1)
        node["headspace_co2"] = round(max(380.0, min(550.0, node["headspace_co2"] + random.uniform(-6.0, 6.0))), 1)

    elif state == "elevated":
        # Slow incipient respiration
        node["headspace_co2"] = round(min(980.0, node["headspace_co2"] + random.uniform(1.0, 8.0)), 1)
        node["humidity"] = round(min(66.0, node["humidity"] + random.uniform(0.0, 0.2)), 1)
        node["temperature"] = round(node["temperature"] + random.uniform(-0.05, 0.1), 1)

    elif state == "warning":
        # Active mold respiration with slow thermal creep
        node["headspace_co2"] = round(min(2200.0, node["headspace_co2"] + random.uniform(5.0, 25.0)), 1)
        node["humidity"] = round(min(74.0, node["humidity"] + random.uniform(0.1, 0.4)), 1)
        node["temperature"] = round(min(32.0, node["temperature"] + random.uniform(0.05, 0.15)), 1)

    elif state == "critical":
        # Bio-heating peak and extreme CO2
        node["headspace_co2"] = round(min(3600.0, node["headspace_co2"] + random.uniform(15.0, 40.0)), 1)
        node["humidity"] = round(min(88.0, node["humidity"] + random.uniform(0.2, 0.6)), 1)
        node["temperature"] = round(min(38.5, node["temperature"] + random.uniform(0.1, 0.3)), 1)
        node["core_moisture"] = round(min(21.0, node["core_moisture"] + 0.1), 1)

    elif state == "solar":
        # Scorching exterior with cool inner core and flat CO2
        node["ambient_temp"] = round(35.0 + random.uniform(-0.5, 2.0), 1)
        node["temperature"] = round(23.0 + random.uniform(-0.1, 0.2), 1)
        node["headspace_co2"] = round(440.0 + random.uniform(-5.0, 5.0), 1)

    elif state == "live_demo":
        node["temperature"] = round(node["temperature"] + random.uniform(-0.05, 0.05), 1)
        node["ambient_temp"] = round(node["ambient_temp"] + random.uniform(-0.1, 0.1), 1)
        node["humidity"] = round(node["humidity"] + random.uniform(-0.2, 0.2), 1)
        node["core_moisture"] = round(node["core_moisture"] + random.uniform(-0.02, 0.02), 1)
        node["headspace_co2"] = round(max(400.0, min(500.0, node["headspace_co2"] + random.uniform(-4.0, 4.0))), 1)

    return {
        "container_id": node["container_id"],
        "storage_type": node["storage_type"],
        "grain_type": node["grain_type"],
        "capacity_tons": node["capacity_tons"],
        "temperature": node["temperature"],
        "ambient_temp": node["ambient_temp"],
        "humidity": node["humidity"],
        "core_moisture": node["core_moisture"],
        "headspace_co2": node["headspace_co2"]
    }

def send_payload(payload):
    """Transmits JSON telemetry to the Flask backend"""
    try:
        res = requests.post(f"{SERVER_URL}/api/telemetry", json=payload, timeout=3)
        if res.status_code == 200:
            data = res.json()
            eval_data = data.get("evaluation", {})
            status = eval_data.get("status", "UNKNOWN")
            dts = eval_data.get("days_to_spoilage", "N/A")
            co2 = payload.get("headspace_co2")
            temp = payload.get("temperature")
            cid = payload.get("container_id")
            print(f"[{time.strftime('%H:%M:%S')}] {cid:<10} | CO2: {co2:>6.1f} ppm | Temp: {temp:>4.1f}°C | Status: {status:<8} | DTS: {dts} days")
            return True
        else:
            print(f"Server returned status {res.status_code}: {res.text}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"Error connecting to {SERVER_URL}: {e}")
        return False

def run_simulation(interval=3, iterations=None):
    """Loops through simulated nodes and sends telemetry"""
    print(f"=== Starting Multi-Spectral Grain IoT Simulator (Target: {SERVER_URL}) ===")
    print("Press Ctrl+C to stop.\n")
    
    count = 0
    while True:
        try:
            for node in SIMULATED_NODES:
                payload = update_node_telemetry(node)
                send_payload(payload)
                time.sleep(0.3)
            
            count += 1
            if iterations and count >= iterations:
                break
                
            time.sleep(max(0.5, interval - (len(SIMULATED_NODES) * 0.3)))
        except KeyboardInterrupt:
            print("\nSimulation stopped by user.")
            break

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Multi-Spectral Grain IoT Telemetry Simulator")
    parser.add_argument("--interval", type=float, default=3.0, help="Polling interval between rounds in seconds")
    parser.add_argument("--once", action="store_true", help="Send one complete round of telemetry and exit")
    parser.add_argument("--server", type=str, default="http://127.0.0.1:5000", help="Flask backend server URL")
    
    args = parser.parse_args()
    SERVER_URL = args.server
    
    if args.once:
        run_simulation(iterations=1)
    else:
        run_simulation(interval=args.interval)
