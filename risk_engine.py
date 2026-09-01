"""
risk_engine.py - Algorithmic Risk Processor & FEFO Decision Matrix
Calculates Days-to-Spoilage (DTS), Spoilage Risk Index, Differential Temperature Matrix,
and dynamic First-Expired, First-Out (FEFO) Dispatch Prioritization.
"""

from datetime import datetime, timezone
from typing import Dict, List, Any, Optional

class SpoilageRiskEngine:
    # Baseline Safe Thresholds for Stored Grains (Wheat, Rice, Corn, Pulses)
    SAFE_CO2_PPM = 600.0         # Normal ambient / clean respiration < 600 ppm
    ELEVATED_CO2_PPM = 1000.0    # Incipient mold / early insect metabolic activity
    WARNING_CO2_PPM = 1800.0     # Active fungal colony respiration
    CRITICAL_CO2_PPM = 2500.0    # High-density mold rot / severe hotspot

    SAFE_RH_PERCENT = 65.0       # Grain equilibrium moisture threshold
    CRITICAL_RH_PERCENT = 75.0   # Fast fungal proliferation zone

    SAFE_TEMP_C = 25.0           # Optimal storage temp
    CRITICAL_TEMP_C = 35.0       # Thermal runaway / bio-heating peak

    # Capacitive moisture raw sensor calibration (0-100% moisture index proxy)
    SAFE_CORE_MOISTURE = 14.5    # Safe grain moisture content (%)
    CRITICAL_CORE_MOISTURE = 18.5# Wet spot / condensation hazard (%)

    @staticmethod
    def calculate_differential_matrix(core_temp: float, ambient_temp: float, co2_ppm: float, d_co2_dt: float) -> Dict[str, Any]:
        """
        Differential Matrix Logic:
        ΔT = T_Core - T_Ambient
        
        Physics & Biology Principles:
        - Solar / Diurnal Heat Swing: Outer wall warms faster than dense grain core (T_Ambient > T_Core => ΔT < 0)
          AND CO2 is stable/flat. Result: FALSE-ALARM REJECTED (Environment thermal wave, not biological spoilage).
        - Internal Biological Mold/Pest Hotspot: Grain core generates metabolic heat from inside-out (T_Core > T_Ambient => ΔT > 0)
          AND CO2 rate-of-change (d_co2_dt) is sharply positive. Result: TRUE SPOILAGE HOTSPOT DETECTED!
        """
        delta_t = round(core_temp - ambient_temp, 2)
        
        is_solar_heating = (ambient_temp > core_temp + 2.0) and (d_co2_dt < 30.0)
        is_internal_hotspot = (delta_t > 1.5) or (d_co2_dt > 50.0 and core_temp > 27.0)
        
        if is_solar_heating:
            thermal_classification = "DIURNAL_SOLAR_SWING"
            explanation = "External heat flux detected (Ambient > Core). Respiration stable. False alarm rejected."
        elif is_internal_hotspot:
            thermal_classification = "INTERNAL_METABOLIC_HOTSPOT"
            explanation = "Internal bio-heating detected (Core > Ambient) with active respiration flux."
        else:
            thermal_classification = "ISOTHERMAL_EQUILIBRIUM"
            explanation = "Storage temperature is in stable thermal equilibrium with surroundings."
            
        return {
            "delta_temp": delta_t,
            "classification": thermal_classification,
            "is_solar_heating": is_solar_heating,
            "is_internal_hotspot": is_internal_hotspot,
            "explanation": explanation
        }

    @classmethod
    def evaluate_telemetry(cls, 
                           current_reading: Dict[str, Any], 
                           previous_history: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """
        Multi-Factor Evaluation producing Risk Score (0-100), Status Level, Days-To-Spoilage (DTS),
        and actionable recommendations.
        """
        co2 = float(current_reading.get("headspace_co2", 420.0))
        temp = float(current_reading.get("temperature", 22.0))
        ambient = float(current_reading.get("ambient_temp", temp - 1.0))
        rh = float(current_reading.get("humidity", 55.0))
        moisture = float(current_reading.get("core_moisture", 12.5))
        grain_type = current_reading.get("grain_type", "Standard Grain")
        capacity_tons = float(current_reading.get("capacity_tons", 50.0))

        # Calculate Rate-of-Change (Δ) over recent readings if history available
        d_co2_dt = 0.0
        d_temp_dt = 0.0
        d_rh_dt = 0.0
        
        if previous_history and len(previous_history) > 0:
            last = previous_history[-1]
            last_co2 = float(last.get("headspace_co2", co2))
            last_temp = float(last.get("temperature", temp))
            last_rh = float(last.get("humidity", rh))
            # Assume 1 delta step (or approximate per-hour derivative)
            d_co2_dt = round(co2 - last_co2, 2)
            d_temp_dt = round(temp - last_temp, 2)
            d_rh_dt = round(rh - last_rh, 2)

        # Differential Temperature Matrix
        diff_matrix = cls.calculate_differential_matrix(temp, ambient, co2, d_co2_dt)

        # 1. Respiration Risk Score (Weight: 45% - Most sensitive early warning)
        # CO2 tracks mold respiration 3-5 days before thermal spikes
        if co2 <= cls.SAFE_CO2_PPM:
            co2_risk = max(0.0, (co2 - 350.0) / (cls.SAFE_CO2_PPM - 350.0) * 15.0)
        elif co2 <= cls.ELEVATED_CO2_PPM:
            co2_risk = 15.0 + ((co2 - cls.SAFE_CO2_PPM) / (cls.ELEVATED_CO2_PPM - cls.SAFE_CO2_PPM)) * 25.0
        elif co2 <= cls.WARNING_CO2_PPM:
            co2_risk = 40.0 + ((co2 - cls.ELEVATED_CO2_PPM) / (cls.WARNING_CO2_PPM - cls.ELEVATED_CO2_PPM)) * 30.0
        else:
            co2_risk = min(100.0, 70.0 + ((co2 - cls.WARNING_CO2_PPM) / (cls.CRITICAL_CO2_PPM - cls.WARNING_CO2_PPM)) * 30.0)

        # Velocity multiplier for rapidly accelerating CO2
        if d_co2_dt > 50.0:
            co2_risk = min(100.0, co2_risk + min(25.0, d_co2_dt * 0.2))

        # 2. Moisture & Humidity Risk Score (Weight: 30%)
        rh_excess = max(0.0, rh - cls.SAFE_RH_PERCENT)
        moisture_excess = max(0.0, moisture - cls.SAFE_CORE_MOISTURE)
        rh_risk = min(100.0, (rh_excess / (cls.CRITICAL_RH_PERCENT - cls.SAFE_RH_PERCENT)) * 50.0 + 
                             (moisture_excess / (cls.CRITICAL_CORE_MOISTURE - cls.SAFE_CORE_MOISTURE)) * 50.0)

        # 3. Thermal Risk Score (Weight: 25%)
        if diff_matrix["is_solar_heating"]:
            # Dampen thermal risk if heat is coming from outside solar exposure
            temp_risk = max(5.0, (temp - 20.0) * 1.5)
        else:
            temp_risk = max(0.0, min(100.0, ((temp - cls.SAFE_TEMP_C) / (cls.CRITICAL_TEMP_C - cls.SAFE_TEMP_C)) * 80.0 + 
                                           max(0.0, diff_matrix["delta_temp"] * 10.0)))

        # Composite Multi-Spectral Risk Index (0 - 100)
        composite_risk = (0.45 * co2_risk) + (0.30 * rh_risk) + (0.25 * temp_risk)
        if co2 >= cls.CRITICAL_CO2_PPM:
            composite_risk = max(composite_risk, 80.0 + min(20.0, (co2 - cls.CRITICAL_CO2_PPM) / 100.0))
        composite_risk = round(max(0.0, min(100.0, composite_risk)), 1)

        # Determine Status Category
        if co2 >= cls.CRITICAL_CO2_PPM or composite_risk >= 75.0:
            status = "CRITICAL"
            status_color = "#ef4444" # Crimson Red
            badge_class = "badge-critical"
            action_code = "IMMEDIATE_DISPATCH"
            action_label = "EMERGENCY DISPATCH: Immediate Milling / Deep Fumigation"
            action_urgency = "Immediate"
        elif composite_risk >= 50.0 or co2 >= cls.WARNING_CO2_PPM:
            status = "WARNING"
            status_color = "#f59e0b" # Amber
            badge_class = "badge-warning"
            action_code = "PRIORITIZE_MILLING"
            action_label = "Prioritize for Secondary Processing / Milling"
            action_urgency = "High"
        elif composite_risk >= 25.0 or co2 >= cls.ELEVATED_CO2_PPM:
            status = "ELEVATED"
            status_color = "#06b6d4" # Cyan Blue
            badge_class = "badge-elevated"
            action_code = "MONITOR_HEADSPACE"
            action_label = "Schedule Headspace Aeration / Venting"
            action_urgency = "Medium-Low"
        else:
            status = "OPTIMAL"
            status_color = "#10b981" # Emerald Green
            badge_class = "badge-optimal"
            action_code = "SAFE_STORAGE"
            action_label = "Safe for Long-Term Buffer Stock"
            action_urgency = "Low"

        # Calculate Estimated Days to Spoilage (DTS)
        # Inverted exponential decay based on composite risk and moisture-respiration coupling
        if composite_risk <= 5.0:
            dts = 180.0
        elif composite_risk < 25.0:
            # 60 to 180 days
            dts = round(180.0 - ((composite_risk - 5.0) / 20.0) * 120.0, 1)
        elif composite_risk < 50.0:
            # 15 to 60 days
            dts = round(60.0 - ((composite_risk - 25.0) / 25.0) * 45.0, 1)
        elif composite_risk < 75.0:
            # 4 to 14 days (Early Respiration Warning Window)
            dts = round(14.0 - ((composite_risk - 50.0) / 25.0) * 10.0, 1)
        else:
            # 0.5 to 3 days (Active Spoilage / Thermal Runaway)
            dts = round(max(0.5, 3.5 - ((composite_risk - 75.0) / 25.0) * 3.0), 1)

        # Early Detection Lead Time Advantage (Days gained over traditional thermal probes)
        # Mold respiration detected via CO2 gives a 3 to 5 day advance warning
        early_lead_days = 0.0
        if status in ["ELEVATED", "WARNING"] and temp < 30.0:
            early_lead_days = round(min(5.0, max(2.5, (co2 / 400.0) * 1.2)), 1)
        elif status == "CRITICAL":
            early_lead_days = 4.2

        # Detailed Diagnostic Drivers
        root_causes = []
        if co2 > cls.ELEVATED_CO2_PPM:
            root_causes.append(f"Metabolic Respiration Spike: Headspace CO2 reached {int(co2)} ppm (+{d_co2_dt} ppm/interval)")
        if rh > cls.SAFE_RH_PERCENT:
            root_causes.append(f"Micro-climate Humidity Excess: Equilibrium RH at {rh}% (Threshold: {cls.SAFE_RH_PERCENT}%)")
        if moisture > cls.SAFE_CORE_MOISTURE:
            root_causes.append(f"Capacitive Core Dampness: Grain moisture at {moisture}% (Threshold: {cls.SAFE_CORE_MOISTURE}%)")
        if diff_matrix["is_internal_hotspot"]:
            root_causes.append(f"Inside-Out Bio-Heating: Core leads ambient by +{diff_matrix['delta_temp']}°C")
        if not root_causes:
            root_causes.append("All multi-spectral telemetry channels within certified safe operating envelopes.")

        return {
            "container_id": current_reading.get("container_id", "UNKNOWN"),
            "grain_type": grain_type,
            "capacity_tons": capacity_tons,
            "temperature": temp,
            "ambient_temp": ambient,
            "humidity": rh,
            "core_moisture": moisture,
            "headspace_co2": co2,
            "delta_co2_rate": d_co2_dt,
            "delta_temp_rate": d_temp_dt,
            "delta_rh_rate": d_rh_dt,
            "differential_matrix": diff_matrix,
            "risk_score": composite_risk,
            "status": status,
            "status_color": status_color,
            "badge_class": badge_class,
            "days_to_spoilage": dts,
            "early_lead_days": early_lead_days,
            "action_code": action_code,
            "action_label": action_label,
            "action_urgency": action_urgency,
            "root_causes": root_causes,
            "last_updated": datetime.now(timezone.utc).isoformat()
        }

    @classmethod
    def rank_fefo_priority(cls, evaluated_containers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Sorts container records by FEFO (First-Expired, First-Out) Dispatch Priority.
        Rank #1 is assigned to the container with the shortest Days-to-Spoilage (DTS).
        Ties are broken by highest tonnage and highest composite risk score.
        """
        sorted_list = sorted(
            evaluated_containers, 
            key=lambda c: (c.get("days_to_spoilage", 999.0), -c.get("risk_score", 0.0), -c.get("capacity_tons", 0.0))
        )

        for index, item in enumerate(sorted_list, start=1):
            item["fefo_rank"] = index
            if index == 1 and item.get("status") in ["WARNING", "CRITICAL"]:
                item["dispatch_tag"] = "URGENT DISPATCH #1"
            elif item.get("status") == "CRITICAL":
                item["dispatch_tag"] = f"CRITICAL QUEUE #{index}"
            elif item.get("status") == "WARNING":
                item["dispatch_tag"] = f"WARNING QUEUE #{index}"
            elif item.get("status") == "ELEVATED":
                item["dispatch_tag"] = f"ELEVATED QUEUE #{index}"
            else:
                item["dispatch_tag"] = f"SAFE QUEUE #{index}"

        return sorted_list
