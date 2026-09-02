"""
app.py - Centralized Telemetry Collector & FEFO Logistics Server
Exposes REST APIs for edge ESP32 microcontrollers and serves the Mission-Control Web Dashboard.
"""

import os
import time
import threading
from datetime import datetime, timezone
from flask import Flask, jsonify, request, render_template, send_from_directory
from flask_cors import CORS
from risk_engine import SpoilageRiskEngine

app = Flask(__name__, static_folder="static", template_folder="templates")
CORS(app)

# Thread-safe in-memory storage for container states & historical time-series buffers
lock = threading.Lock()

# Initial pre-seeded demo containers across godown and bag stack deployments
INITIAL_CONTAINERS = {
    "SILO-A01": {
        "container_id": "SILO-A01",
        "storage_type": "Vertical Central Rod Array",
        "grain_type": "Hard Red Winter Wheat",
        "capacity_tons": 120.0,
        "temperature": 22.4,
        "ambient_temp": 23.0,
        "humidity": 56.2,
        "core_moisture": 12.8,
        "headspace_co2": 440.0,
        "history": []
    },
    "SILO-A02": {
        "container_id": "SILO-A02",
        "storage_type": "Vertical Central Rod Array",
        "grain_type": "Premium Basmati Rice",
        "capacity_tons": 85.0,
        "temperature": 24.1,
        "ambient_temp": 24.8,
        "humidity": 61.5,
        "core_moisture": 13.6,
        "headspace_co2": 720.0,
        "history": []
    },
    "STACK-B01": {
        "container_id": "STACK-B01",
        "storage_type": "Handheld Spear Probe Stack",
        "grain_type": "Yellow Dent Corn",
        "capacity_tons": 40.0,
        "temperature": 26.8,
        "ambient_temp": 25.2,
        "humidity": 68.4,
        "core_moisture": 15.2,
        "headspace_co2": 1420.0,
        "history": []
    },
    "STACK-B02": {
        "container_id": "STACK-B02",
        "storage_type": "Handheld Spear Probe Stack",
        "grain_type": "Soybean Seed Stacks",
        "capacity_tons": 35.0,
        "temperature": 21.9,
        "ambient_temp": 22.5,
        "humidity": 52.0,
        "core_moisture": 11.9,
        "headspace_co2": 415.0,
        "history": []
    },
    "CONT-C01": {
        "container_id": "CONT-C01",
        "storage_type": "Containerized Godown Array",
        "grain_type": "Malt Barley",
        "capacity_tons": 60.0,
        "temperature": 23.0,
        "ambient_temp": 32.5, # Solar heat wave scenario baseline
        "humidity": 58.0,
        "core_moisture": 13.0,
        "headspace_co2": 460.0,
        "history": []
    },
    "SPEAR-D01": {
        "container_id": "SPEAR-D01",
        "storage_type": "Live ESP32 Spear Probe",
        "grain_type": "Paddy Grain Bags",
        "capacity_tons": 15.0,
        "temperature": 23.5,
        "ambient_temp": 24.0,
        "humidity": 57.0,
        "core_moisture": 13.2,
        "headspace_co2": 450.0,
        "history": []
    }
}

# Container telemetry state map
CONTAINER_STORE = {}

# In-memory notifications & logistics alert dispatch log
NOTIFICATION_LOG = []

def log_notification(level: str, container_id: str, title: str, message: str, dts: float = None):
    """Logs an automated logistics alert event with simulated dispatch notification recipients"""
    now_str = datetime.now(timezone.utc).strftime("%H:%M:%S")
    entry = {
        "id": len(NOTIFICATION_LOG) + 1,
        "timestamp": now_str,
        "level": level, # CRITICAL, WARNING, INFO, SUCCESS
        "container_id": container_id,
        "title": title,
        "message": message,
        "days_to_spoilage": dts,
        "recipient": "Milling Logistics Dispatcher & Warehouse Floor Manager (Push/SMS)"
    }
    NOTIFICATION_LOG.insert(0, entry) # Most recent first
    if len(NOTIFICATION_LOG) > 50:
        NOTIFICATION_LOG.pop()
    return entry

def initialize_database():
    """Generates synthetic 24-hour historical curves for initial containers"""
    global CONTAINER_STORE
    with lock:
        CONTAINER_STORE.clear()
        now = time.time()
        
        for cid, info in INITIAL_CONTAINERS.items():
            base_temp = info["temperature"]
            base_amb = info["ambient_temp"]
            base_rh = info["humidity"]
            base_moist = info["core_moisture"]
            base_co2 = info["headspace_co2"]
            
            # Generate 20 historical points representing 24 hours of trend
            history = []
            for i in range(20, 0, -1):
                timestamp = datetime.fromtimestamp(now - (i * 3600), timezone.utc).strftime("%H:%M")
                
                # Gradual rise for STACK-B01 to show respiration lead curve
                if cid == "STACK-B01":
                    hist_co2 = max(420.0, base_co2 - (i * 48.0))
                    hist_temp = max(22.0, base_temp - (i * 0.2)) # Temp lags far behind CO2!
                    hist_rh = max(55.0, base_rh - (i * 0.6))
                    hist_moist = max(13.0, base_moist - (i * 0.1))
                elif cid == "CONT-C01": # Solar diurnal curve
                    hist_co2 = 450.0 + (i % 3) * 5.0
                    hist_temp = 22.5 + (i % 2) * 0.3
                    hist_amb = 24.0 + (20 - i) * 0.4
                    hist_rh = base_rh
                    hist_moist = base_moist
                    base_amb = hist_amb
                else:
                    hist_co2 = base_co2 + (i % 4 - 2) * 8.0
                    hist_temp = base_temp + (i % 3 - 1) * 0.2
                    hist_rh = base_rh + (i % 2 - 0.5) * 0.5
                    hist_moist = base_moist + (i % 2 - 0.5) * 0.1
                
                history.append({
                    "timestamp": timestamp,
                    "temperature": round(hist_temp, 1),
                    "ambient_temp": round(base_amb, 1),
                    "humidity": round(hist_rh, 1),
                    "core_moisture": round(hist_moist, 1),
                    "headspace_co2": round(hist_co2, 1)
                })

            container_data = dict(info)
            container_data["history"] = history
            CONTAINER_STORE[cid] = container_data

# Run initial seeding
initialize_database()


@app.route("/")
def index():
    """Serves the FEFO Warehouse Mission-Control Web Dashboard"""
    return render_template("index.html")


@app.route("/api/telemetry", methods=["POST"])
def ingest_telemetry():
    """
    Ingests live multi-sensor telemetry from physical ESP32 or simulation harness.
    Payload format:
    {
        "container_id": "SPEAR-D01",
        "grain_type": "Wheat",
        "capacity_tons": 25.0,
        "temperature": 24.2,
        "ambient_temp": 23.5,
        "humidity": 58.0,
        "core_moisture": 13.5,
        "headspace_co2": 480.0
    }
    """
    try:
        data = request.get_json(force=True)
        if not data or "container_id" not in data:
            return jsonify({"status": "error", "message": "Missing 'container_id' in payload"}), 400

        cid = str(data["container_id"]).strip().upper()
        now_ts = datetime.now(timezone.utc).strftime("%H:%M:%S")

        with lock:
            if cid not in CONTAINER_STORE:
                CONTAINER_STORE[cid] = {
                    "container_id": cid,
                    "storage_type": data.get("storage_type", "ESP32 IoT Node"),
                    "grain_type": data.get("grain_type", "Stored Grains"),
                    "capacity_tons": float(data.get("capacity_tons", 25.0)),
                    "temperature": float(data.get("temperature", 22.0)),
                    "ambient_temp": float(data.get("ambient_temp", 22.0)),
                    "humidity": float(data.get("humidity", 55.0)),
                    "core_moisture": float(data.get("core_moisture", 12.0)),
                    "headspace_co2": float(data.get("headspace_co2", 420.0)),
                    "history": []
                }
            
            c = CONTAINER_STORE[cid]
            c["temperature"] = float(data.get("temperature", c["temperature"]))
            c["ambient_temp"] = float(data.get("ambient_temp", c.get("ambient_temp", c["temperature"])))
            c["humidity"] = float(data.get("humidity", c["humidity"]))
            c["core_moisture"] = float(data.get("core_moisture", c["core_moisture"]))
            c["headspace_co2"] = float(data.get("headspace_co2", c["headspace_co2"]))
            if "grain_type" in data:
                c["grain_type"] = data["grain_type"]
            if "capacity_tons" in data:
                c["capacity_tons"] = float(data["capacity_tons"])

            # Append to rolling history buffer (keep last 30 readings)
            c["history"].append({
                "timestamp": now_ts,
                "temperature": round(c["temperature"], 1),
                "ambient_temp": round(c["ambient_temp"], 1),
                "humidity": round(c["humidity"], 1),
                "core_moisture": round(c["core_moisture"], 1),
                "headspace_co2": round(c["headspace_co2"], 1)
            })
            if len(c["history"]) > 30:
                c["history"].pop(0)

            # Evaluate through Spoilage Risk Engine
            eval_result = SpoilageRiskEngine.evaluate_telemetry(c, c["history"][:-1] if len(c["history"]) > 1 else None)
            c.update(eval_result)

        return jsonify({
            "status": "success",
            "message": f"Telemetry ingested for {cid}",
            "evaluation": eval_result
        }), 200

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/containers", methods=["GET"])
def get_containers():
    """
    Returns all monitored storage containers evaluated and sorted by FEFO Dispatch Priority.
    Rank #1 corresponds to the container with the shortest Days-To-Spoilage (DTS).
    """
    with lock:
        evaluated_list = []
        for cid, data in CONTAINER_STORE.items():
            eval_res = SpoilageRiskEngine.evaluate_telemetry(data, data.get("history", []))
            combined = dict(data)
            combined.update(eval_res)
            # Remove bulky history from list view for lightweight fast polling
            if "history" in combined:
                combined["history_length"] = len(combined["history"])
                del combined["history"]
            evaluated_list.append(combined)

        ranked = SpoilageRiskEngine.rank_fefo_priority(evaluated_list)

    return jsonify({
        "status": "success",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_containers": len(ranked),
        "containers": ranked
    })


@app.route("/api/containers/<cid>", methods=["GET"])
def get_container_detail(cid):
    """Returns granular telemetry and full time-series history for chart rendering"""
    cid = cid.strip().upper()
    with lock:
        if cid not in CONTAINER_STORE:
            return jsonify({"status": "error", "message": f"Container {cid} not found"}), 404
        
        data = CONTAINER_STORE[cid]
        eval_res = SpoilageRiskEngine.evaluate_telemetry(data, data.get("history", []))
        full_detail = dict(data)
        full_detail.update(eval_res)
        
    return jsonify({
        "status": "success",
        "container": full_detail
    })


@app.route("/api/dispatch/<cid>", methods=["POST"])
def dispatch_container(cid):
    """
    Executes FEFO Dispatch action for a given container (e.g. sent to milling plant).
    Resets container telemetry to fresh safe baseline batch.
    """
    cid = cid.strip().upper()
    with lock:
        if cid not in CONTAINER_STORE:
            return jsonify({"status": "error", "message": f"Container {cid} not found"}), 404
        
        c = CONTAINER_STORE[cid]
        c["temperature"] = 21.5
        c["ambient_temp"] = 22.0
        c["humidity"] = 54.0
        c["core_moisture"] = 12.0
        c["headspace_co2"] = 410.0
        c["history"] = [{
            "timestamp": datetime.now(timezone.utc).strftime("%H:%M:%S"),
            "temperature": 21.5,
            "ambient_temp": 22.0,
            "humidity": 54.0,
            "core_moisture": 12.0,
            "headspace_co2": 410.0
        }]
        
    return jsonify({
        "status": "success",
        "message": f"Container {cid} successfully dispatched to milling plant! Stock replenished with fresh certified batch."
    })


@app.route("/api/simulate/event", methods=["POST"])
def simulate_event():
    """
    Interactive Hackathon Demo Event Trigger:
    Supported Events:
    - 'breath_spike': Simulates breath exhaled onto MQ-135 sensor (rapid CO2 spike to 2850 ppm, triggers Rank #1 FEFO CRITICAL alert).
    - 'solar_heat': Simulates diurnal solar heat wave on godown wall (Ambient 36°C, Core 23°C, CO2 flat => Rejects False Alarm).
    - 'wet_core_leak': Simulates bottom rain infiltration (Moisture 19.5%, RH 82%, incipient mold respiration).
    - 'normal_reset': Resets all containers to certified pristine baseline.
    - 'step_spoilage': Simulates +12 hours of progressive fungal respiration curve.
    """
    data = request.get_json(force=True) or {}
    event_type = data.get("event", "breath_spike")
    target_id = data.get("container_id", "SPEAR-D01").strip().upper()

    with lock:
        if target_id not in CONTAINER_STORE and event_type not in ["normal_reset", "all_healthy"]:
            # Fallback to first available container
            target_id = list(CONTAINER_STORE.keys())[0]

        now_ts = datetime.now(timezone.utc).strftime("%H:%M:%S")

        if event_type == "breath_spike":
            # Real-time MQ-135 Gas Exhale Test
            c = CONTAINER_STORE[target_id]
            c["headspace_co2"] = 2950.0   # Severe metabolic respiration surge
            c["humidity"] = min(92.0, c["humidity"] + 12.0)
            c["temperature"] = c["temperature"] + 0.8 # Mild temp rise (thermal lag!)
            c["history"].append({
                "timestamp": now_ts,
                "temperature": round(c["temperature"], 1),
                "ambient_temp": round(c["ambient_temp"], 1),
                "humidity": round(c["humidity"], 1),
                "core_moisture": round(c["core_moisture"], 1),
                "headspace_co2": round(c["headspace_co2"], 1)
            })
            msg = f"Breath Exhale Trigger Activated on {target_id}! CO2 surged to 2950 ppm. Metabolic lead alert triggered."
            log_notification("CRITICAL", target_id, "🚨 CRITICAL METABOLIC RESPIRATION ALERT", f"{target_id} Headspace CO2 reached 2950 ppm (+2500 ppm surge). Estimated Spoilage: 1.5 Days. Immediate milling dispatch required!", 1.5)

        elif event_type == "solar_heat":
            # Solar Heat Wave (Differential Matrix Demo)
            c = CONTAINER_STORE[target_id]
            c["ambient_temp"] = 38.5      # Scorching exterior wall
            c["temperature"] = 23.2       # Grain core remains cool due to insulation
            c["headspace_co2"] = 430.0    # No biological activity!
            c["history"].append({
                "timestamp": now_ts,
                "temperature": round(c["temperature"], 1),
                "ambient_temp": round(c["ambient_temp"], 1),
                "humidity": round(c["humidity"], 1),
                "core_moisture": round(c["core_moisture"], 1),
                "headspace_co2": round(c["headspace_co2"], 1)
            })
            msg = f"Solar Heat Wave Simulated on {target_id}. Ambient={c['ambient_temp']}°C, Core={c['temperature']}°C. Differential matrix rejects false alarm."
            log_notification("INFO", target_id, "☀️ Diurnal Solar Heat Filtered", f"{target_id} Exterior wall warmed to 38.5°C. Differential matrix confirmed ΔT < 0 and flat CO2. False alarm rejected.", 180.0)

        elif event_type == "wet_core_leak":
            c = CONTAINER_STORE[target_id]
            c["core_moisture"] = 19.8     # Critical dampness
            c["humidity"] = 84.0          # High interstitial RH
            c["headspace_co2"] = 1650.0   # Incipient mold growth
            c["history"].append({
                "timestamp": now_ts,
                "temperature": round(c["temperature"], 1),
                "ambient_temp": round(c["ambient_temp"], 1),
                "humidity": round(c["humidity"], 1),
                "core_moisture": round(c["core_moisture"], 1),
                "headspace_co2": round(c["headspace_co2"], 1)
            })
            msg = f"Wet Core Infiltration Injected on {target_id}! Moisture: 19.8%, RH: 84%."
            log_notification("WARNING", target_id, "💧 Water Infiltration & Condensation Warning", f"{target_id} Capacitive moisture jumped to 19.8%, RH 84%. Spoilage danger in 4.5 Days. Aeration/Milling prioritized.", 4.5)

        elif event_type in ["normal_reset", "all_healthy"]:
            initialize_database()
            msg = "All grain storage silos and stack probes reset to optimal baseline parameters."
            log_notification("SUCCESS", "ALL_NODES", "✓ Baseline Stock Restored", "All warehouse containers recalibrated to pristine certified storage baseline.", 180.0)

        elif event_type == "step_spoilage":
            c = CONTAINER_STORE[target_id]
            c["headspace_co2"] = min(3500.0, c["headspace_co2"] + 350.0)
            c["humidity"] = min(90.0, c["humidity"] + 2.5)
            c["temperature"] = min(38.0, c["temperature"] + 0.4)
            c["history"].append({
                "timestamp": now_ts,
                "temperature": round(c["temperature"], 1),
                "ambient_temp": round(c["ambient_temp"], 1),
                "humidity": round(c["humidity"], 1),
                "core_moisture": round(c["core_moisture"], 1),
                "headspace_co2": round(c["headspace_co2"], 1)
            })
            msg = f"Advanced 12h mold growth cycle on {target_id}. CO2 now {c['headspace_co2']} ppm."
            log_notification("WARNING", target_id, "📈 Mold Respiration Accelerated", f"{target_id} Advanced fungal respiration cycle (+350 ppm). Days to Spoilage declining.", 3.8)

        else:
            return jsonify({"status": "error", "message": f"Unknown event '{event_type}'"}), 400

    return jsonify({
        "status": "success",
        "message": msg,
        "target_container": target_id
    })


@app.route("/api/notifications", methods=["GET"])
def get_notifications():
    """Returns the list of automated spoilage alerts and logistics dispatch notifications"""
    with lock:
        return jsonify({
            "status": "success",
            "total": len(NOTIFICATION_LOG),
            "notifications": NOTIFICATION_LOG[:25]
        })


@app.route("/api/summary", methods=["GET"])
def get_warehouse_summary():
    """Returns aggregated high-level KPIs for executive warehouse operations"""
    with lock:
        total_tons = sum(c["capacity_tons"] for c in CONTAINER_STORE.values())
        total_units = len(CONTAINER_STORE)
        
        evaluated = []
        for c in CONTAINER_STORE.values():
            eval_res = SpoilageRiskEngine.evaluate_telemetry(c, c.get("history", []))
            evaluated.append(eval_res)
            
        at_risk_tons = sum(e["capacity_tons"] for e in evaluated if e["status"] in ["WARNING", "CRITICAL"])
        critical_count = sum(1 for e in evaluated if e["status"] == "CRITICAL")
        warning_count = sum(1 for e in evaluated if e["status"] == "WARNING")
        elevated_count = sum(1 for e in evaluated if e["status"] == "ELEVATED")
        optimal_count = sum(1 for e in evaluated if e["status"] == "OPTIMAL")

        avg_co2 = round(sum(e["headspace_co2"] for e in evaluated) / max(1, total_units), 1)
        mean_risk = round(sum(e["risk_score"] for e in evaluated) / max(1, total_units), 1)

        # Top FEFO candidate
        ranked = SpoilageRiskEngine.rank_fefo_priority(evaluated)
        top_dispatch = ranked[0] if ranked else None

    return jsonify({
        "status": "success",
        "total_stock_tons": round(total_tons, 1),
        "at_risk_tons": round(at_risk_tons, 1),
        "total_monitored_units": total_units,
        "critical_units": critical_count,
        "warning_units": warning_count,
        "elevated_units": elevated_count,
        "optimal_units": optimal_count,
        "mean_headspace_co2": avg_co2,
        "mean_risk_index": mean_risk,
        "top_fefo_priority": top_dispatch
    })


if __name__ == "__main__":
    print("Starting Grain Spoilage & FEFO Telemetry Server on http://127.0.0.1:5000")
    app.run(host="0.0.0.0", port=5000, debug=True)
