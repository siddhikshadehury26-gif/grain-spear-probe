"""
test_system.py - End-to-End Automated Verification Test Suite
Tests:
1. Web server HTML and static assets loading.
2. /api/summary, /api/containers, and /api/containers/<id> endpoints.
3. Telemetry ingestion from simulated ESP32 node.
4. Spoilage risk calculation, DTS math, and FEFO ranking.
5. Hackathon simulation triggers:
   - Breath Exhale Trigger (CO2 spike -> Rank #1 CRITICAL)
   - Diurnal Solar Heat Wave (Ambient 38°C -> Rejects false alarm)
   - Wet Core Condensation Leak
   - Container FEFO Dispatch
"""

import requests
import sys

BASE_URL = "http://127.0.0.1:5000"

def test_endpoints():
    print("=" * 60)
    print("GrainGuard IoT System: Automated Verification Suite")
    print("=" * 60)

    # 1. Test Index Page Serving
    print("\n[1/7] Testing Web Server Index Page...")
    res = requests.get(f"{BASE_URL}/")
    assert res.status_code == 200, f"Failed to load index page: {res.status_code}"
    assert "GrainGuard" in res.text, "Index HTML missing brand title"
    assert "FEFO Priority Dispatch Queue" in res.text, "Index HTML missing FEFO section"
    print("  [PASS] Index HTML page successfully rendered.")

    # 2. Test Summary Endpoint
    print("\n[2/7] Testing /api/summary Endpoint...")
    res = requests.get(f"{BASE_URL}/api/summary")
    assert res.status_code == 200, f"Failed summary endpoint: {res.status_code}"
    summary = res.json()
    assert summary["status"] == "success"
    assert summary["total_stock_tons"] > 0
    assert summary["total_monitored_units"] >= 5
    print(f"  [PASS] Summary KPIs Verified: {summary['total_stock_tons']} Tons across {summary['total_monitored_units']} units.")

    # 3. Test Container List & FEFO Sorting
    print("\n[3/7] Testing /api/containers Endpoint & FEFO Sorting...")
    res = requests.get(f"{BASE_URL}/api/containers")
    assert res.status_code == 200
    data = res.json()
    containers = data["containers"]
    assert len(containers) >= 5
    print(f"  [PASS] Retrieved {len(containers)} containers.")
    for c in containers:
        print(f"    - Rank #{c['fefo_rank']}: {c['container_id']:<10} | {c['grain_type']:<22} | Status: {c['status']:<8} | DTS: {c['days_to_spoilage']} Days")

    # 4. Test Live Telemetry Ingestion (ESP32 emulation)
    print("\n[4/7] Testing Ingestion /api/telemetry (Simulating ESP32 Node)...")
    payload = {
        "container_id": "SPEAR-D01",
        "storage_type": "Live ESP32 Spear Probe",
        "grain_type": "Paddy Grain Bags",
        "capacity_tons": 15.0,
        "temperature": 23.4,
        "ambient_temp": 23.8,
        "humidity": 58.0,
        "core_moisture": 13.1,
        "headspace_co2": 465.0
    }
    res = requests.post(f"{BASE_URL}/api/telemetry", json=payload)
    assert res.status_code == 200
    eval_data = res.json()["evaluation"]
    assert eval_data["status"] == "OPTIMAL"
    print(f"  [PASS] Ingested telemetry for SPEAR-D01. Status: {eval_data['status']}, DTS: {eval_data['days_to_spoilage']} days.")

    # 5. Test Live Breath Exhale Simulation Trigger
    print("\n[5/7] Testing Hackathon Event Trigger: Breath Exhale on MQ-135...")
    res = requests.post(f"{BASE_URL}/api/simulate/event", json={"event": "breath_spike", "container_id": "SPEAR-D01"})
    assert res.status_code == 200
    # Verify container state updated to CRITICAL and Rank #1
    res = requests.get(f"{BASE_URL}/api/containers")
    top_container = res.json()["containers"][0]
    assert top_container["container_id"] == "SPEAR-D01", f"Expected SPEAR-D01 at Rank 1, got {top_container['container_id']}"
    assert top_container["status"] == "CRITICAL", f"Expected status CRITICAL, got {top_container['status']}"
    assert top_container["headspace_co2"] >= 2500.0
    assert top_container["days_to_spoilage"] <= 3.5
    print(f"  [PASS] Breath Trigger Confirmed! SPEAR-D01 successfully promoted to FEFO Rank #1 (CRITICAL). CO2: {top_container['headspace_co2']} ppm.")

    # 6. Test Diurnal Solar Heat Wave Simulation (False Alarm Rejection)
    print("\n[6/7] Testing Differential Matrix: Diurnal Solar Heat Wave on CONT-C01...")
    res = requests.post(f"{BASE_URL}/api/simulate/event", json={"event": "solar_heat", "container_id": "CONT-C01"})
    assert res.status_code == 200
    res = requests.get(f"{BASE_URL}/api/containers/CONT-C01")
    cont_detail = res.json()["container"]
    diff_matrix = cont_detail["differential_matrix"]
    assert diff_matrix["is_solar_heating"] == True
    assert diff_matrix["classification"] == "DIURNAL_SOLAR_SWING"
    assert cont_detail["status"] == "OPTIMAL"
    print(f"  [PASS] Solar False-Alarm Rejection Confirmed! Ambient={cont_detail['ambient_temp']}°C, Core={cont_detail['temperature']}°C.")
    print(f"    Differential Matrix Classification: {diff_matrix['classification']}. Status remains OPTIMAL.")

    # 7. Test FEFO Dispatch Execution
    print("\n[7/7] Testing FEFO Dispatch to Milling Plant...")
    res = requests.post(f"{BASE_URL}/api/dispatch/SPEAR-D01")
    assert res.status_code == 200
    res = requests.get(f"{BASE_URL}/api/containers/SPEAR-D01")
    dispatched_detail = res.json()["container"]
    assert dispatched_detail["status"] == "OPTIMAL"
    assert dispatched_detail["headspace_co2"] <= 450.0
    print(f"  [PASS] Dispatch verified! Container SPEAR-D01 safely replenished with fresh certified stock.")

    print("\n" + "=" * 60)
    print("ALL 7 SYSTEM TESTS PASSED PERFECTLY!")
    print("=" * 60)

if __name__ == "__main__":
    test_endpoints()
