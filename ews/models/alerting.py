"""Alert generation and anti-fatigue controls: persistence, budgets, and confidence scoring."""

import json
from datetime import date, timedelta
from typing import List, Dict, Any, Optional, Tuple
import pandas as pd
import numpy as np

from ews.config import load_settings, load_playbook


def calculate_confidence(
    missing_signal_count: int,
    is_district_fallback: bool,
    base_confidence: float = 1.0,
    penalty_missing: float = 0.7,
    penalty_fallback: float = 0.8,
) -> float:
    """Calculate confidence score starting at 1.0, penalized multiplicatively."""
    conf = base_confidence
    for _ in range(missing_signal_count):
        conf *= penalty_missing
    if is_district_fallback:
        conf *= penalty_fallback
    return round(float(np.clip(conf, 0.05, 1.0)), 3)


def evaluate_site_alert_stream(
    site_df: pd.DataFrame,
    scores: np.ndarray,
    contributions: List[Dict[str, Any]],
    settings=None,
) -> List[Dict[str, Any]]:
    """Generate raw alerts for a single site enforcing persistence rules:
    - Watch: score >= 0.30 for 2 consecutive days
    - Warning: score >= 0.55 for 2 consecutive days, OR Watch with 2+ signal types
    - Critical: score >= 0.75 for 2 consecutive days AND workforce contribution >= 25%
    - Persistence: NO level above Watch fires on a single day.
    """
    if settings is None:
        settings = load_settings()

    watch_th = settings.alerting.watch_threshold       # 0.30
    warn_th = settings.alerting.warning_threshold       # 0.55
    crit_th = settings.alerting.critical_threshold      # 0.75
    workforce_crit_min = settings.alerting.workforce_contribution_critical_min * 100.0 # 25.0%

    n = len(site_df)
    dates = pd.to_datetime(site_df["date"]).dt.date.tolist()
    site_id = site_df["site_id"].iloc[0]
    district = site_df["district"].iloc[0]

    alerts = []
    consecutive_high_days = 0

    for i in range(n):
        cur_date = dates[i]
        score = scores[i]
        contrib = contributions[i]
        
        # Check missing signals
        missing_count = 0
        for flag in [
            "signal_available_weather",
            "signal_available_pm25",
            "signal_available_clinic_heat",
            "signal_available_clinic_resp",
            "signal_available_incidents",
            "signal_available_absence",
        ]:
            if flag in site_df.columns and not bool(site_df[flag].iloc[i]):
                missing_count += 1

        is_fallback = bool(site_df["baseline_district_fallback"].iloc[i]) if "baseline_district_fallback" in site_df.columns else False
        confidence = calculate_confidence(missing_count, is_fallback)

        # Workforce contribution percentage sum (clinic + incidents)
        grouped_pcts = contrib.get("grouped_pct", {})
        workforce_pct = grouped_pcts.get("clinic", 0.0) + grouped_pcts.get("incidents", 0.0)
        active_signal_count = contrib.get("active_signal_count", 0)

        # Persistence tracking
        if score >= watch_th:
            consecutive_high_days += 1
        else:
            consecutive_high_days = 0

        alert_level = "Clear"

        # Persistence rule: no level above Watch fires on a single day!
        if consecutive_high_days >= 2:
            if score >= crit_th and workforce_pct >= workforce_crit_min:
                alert_level = "Critical"
            elif score >= warn_th or (consecutive_high_days >= 2 and active_signal_count >= 2 and score >= watch_th):
                alert_level = "Warning"
            elif score >= watch_th:
                alert_level = "Watch"
        elif consecutive_high_days == 1 and score >= 0.65:
            # High single day can register at most Watch
            alert_level = "Watch"

        if alert_level != "Clear":
            alerts.append({
                "site_id": site_id,
                "district": district,
                "date": cur_date,
                "level": alert_level,
                "score": round(float(score), 4),
                "contributions": contrib,
                "confidence": confidence,
                "missing_signals": missing_count,
                "is_fallback": is_fallback,
                "workforce_pct": workforce_pct,
            })

    return alerts


def apply_alert_budget_and_playbook(
    all_raw_alerts: List[Dict[str, Any]],
    playbook_rules: Optional[List[Dict[str, Any]]] = None,
    max_alerts_per_district_per_week: int = 5,
) -> List[Dict[str, Any]]:
    """Enforce weekly alert budgets per district and map actions from playbook.yaml.
    
    Alert budget: at most 5 Warning or Critical alerts per district per week;
    excess alerts are ranked by score and the remainder shown as Watch.
    """
    if playbook_rules is None:
        playbook_rules = load_playbook()

    if not all_raw_alerts:
        return []

    alerts_df = pd.DataFrame(all_raw_alerts)
    alerts_df["datetime"] = pd.to_datetime(alerts_df["date"])
    alerts_df["year_week"] = alerts_df["datetime"].dt.to_period("W-SUN")

    final_alerts = []

    for (dist, yr_wk), group in alerts_df.groupby(["district", "year_week"]):
        high_severity = group[group["level"].isin(["Warning", "Critical"])].sort_values("score", ascending=False)
        
        # Keep top N per budget
        allowed_high_indices = set(high_severity.head(max_alerts_per_district_per_week).index)

        for idx, row in group.iterrows():
            item = row.to_dict()
            del item["datetime"]
            del item["year_week"]

            # If it was Warning/Critical but exceeded budget, demote to Watch
            if row["level"] in ["Warning", "Critical"] and idx not in allowed_high_indices:
                item["level"] = "Watch"
                item["budget_demoted"] = True

            # Match playbook rule
            action_info = match_playbook_rule(
                item["level"],
                item["contributions"].get("dominant_signal", "environment"),
                item["confidence"],
                playbook_rules,
            )
            item["action_id"] = action_info["id"]
            item["action"] = action_info["action"]
            item["role"] = action_info["role"]
            item["evidence"] = action_info["evidence_shown"]

            final_alerts.append(item)

    return sorted(final_alerts, key=lambda a: (a["date"], a["site_id"]))


def match_playbook_rule(
    level: str,
    dominant_signal: str,
    confidence: float,
    rules: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Map alert level, dominant signal, and confidence to playbook action and role."""
    # 1. Low confidence override rule
    if confidence < 0.50:
        low_conf = next((r for r in rules if r.get("id") == "RULE_LOW_CONFIDENCE"), None)
        if low_conf:
            return low_conf

    # 2. Match specific level and signal
    for r in rules:
        r_lvl = r.get("level")
        r_sig = r.get("dominant_signal")

        match_lvl = (r_lvl == level or r_lvl == "ANY")
        match_sig = (r_sig == dominant_signal or r_sig == "ANY")

        if match_lvl and match_sig:
            return r

    # Default fallback
    return {
        "id": "RULE_DEFAULT",
        "action": "Review site environmental conditions and notify safety lead",
        "role": "Site safety officer",
        "evidence_shown": "Site score and sensor trends",
    }
