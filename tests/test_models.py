"""Acceptance tests for Steps 4 and 5: Baselines, CUSUM, Fusion, and Alerting."""

import pytest
import numpy as np
import pandas as pd
from datetime import date
from ews.models.baseline import compute_site_day_baselines
from ews.models.detect import compute_cusum_series, apply_anomaly_detection
from ews.models.fuse import FusionRiskModel, extract_fusion_features
from ews.models.alerting import evaluate_site_alert_stream, apply_alert_budget_and_playbook, calculate_confidence
from ews.config import load_settings, load_playbook


def test_step4_cusum_breach_and_calm():
    """Step 4 acceptance check:
    - On a no-event stretch, fewer than 2% of site-days breach CUSUM threshold.
    - On a simulated heat wave/event, CUSUM breaches.
    """
    rng = np.random.default_rng(42)
    # 1. Calm stretch: N(0, 1) standard normal residuals
    n_days = 200
    calm_residuals = rng.normal(0, 1.0, size=n_days)
    s_calm = compute_cusum_series(calm_residuals, k=0.5)
    breaches_calm = np.sum(s_calm >= 4.0)
    pct_calm = (breaches_calm / n_days) * 100.0
    assert pct_calm < 2.0, f"Calm stretch CUSUM breaches should be < 2%, got {pct_calm:.2f}%"

    # 2. Event stretch: sustained shift z = +2.5 for 5 days
    event_residuals = np.concatenate([
        rng.normal(0, 1.0, size=20),
        np.full(6, 2.5), # Sustained event
        rng.normal(0, 1.0, size=20),
    ])
    s_event = compute_cusum_series(event_residuals, k=0.5)
    assert np.any(s_event >= 4.0), "CUSUM must breach during sustained event"


def test_step5_contributions_faithfulness():
    """Step 5 acceptance check: Contributions sum to the score in log-odds."""
    fusion = FusionRiskModel.load()
    assert fusion.is_fitted

    # Synthetic sample row
    sample_features = pd.DataFrame([{
        "clinic_heat_cusum": 3.5,
        "clinic_resp_cusum": 0.5,
        "incident_cusum": 1.2,
        "heat_index_exceed": 4.0,
        "pm25_exceed": 10.0,
        "district_peer_heat_cusum": 2.0,
        "district_peer_resp_cusum": 0.2,
        "district_peer_incident_cusum": 0.8,
        "district_peer_hi_exceed": 3.0,
        "district_peer_pm25_exceed": 8.0,
    }])

    cal_prob, raw_log_odds, contribs = fusion.predict(sample_features)
    c0 = contribs[0]

    # Sum of feature contributions + intercept must equal raw log-odds exactly
    feat_sum = sum(c0["feature_contributions"].values()) + c0["intercept"]
    assert abs(feat_sum - raw_log_odds[0]) < 1e-4, f"Sum {feat_sum} != raw log odds {raw_log_odds[0]}"
    assert abs(feat_sum - c0["total_log_odds"]) < 1e-4


def test_step5_persistence_blocks_single_day_warnings():
    """Step 5 acceptance check: Persistence rule blocks single-day Warnings."""
    settings = load_settings()
    dates = [date(2025, 6, 1) + pd.Timedelta(days=i) for i in range(5)]
    site_df = pd.DataFrame({
        "site_id": ["S01"] * 5,
        "district": ["District-1"] * 5,
        "date": dates,
        "signal_available_weather": [True] * 5,
        "signal_available_pm25": [True] * 5,
        "signal_available_clinic_heat": [True] * 5,
        "signal_available_clinic_resp": [True] * 5,
        "signal_available_incidents": [True] * 5,
        "signal_available_absence": [True] * 5,
        "baseline_district_fallback": [False] * 5,
    })

    # Single spike to 0.85 on day 2 preceded and followed by 0.10
    scores = np.array([0.10, 0.85, 0.10, 0.10, 0.10])
    contribs = [
        {"grouped_pct": {"clinic": 50.0, "environment": 50.0}, "active_signal_count": 2, "dominant_signal": "clinic"}
        for _ in range(5)
    ]

    alerts = evaluate_site_alert_stream(site_df, scores, contribs, settings=settings)
    
    # Day 2 can register at most Watch; Warning or Critical must NOT fire on a single isolated day
    day2_alert = next((a for a in alerts if a["date"] == dates[1]), None)
    if day2_alert:
        assert day2_alert["level"] == "Watch", f"Single day spike must not exceed Watch, got {day2_alert['level']}"


def test_step5_district_weekly_alert_budget():
    """Step 5 acceptance check: Alert budget of at most 5 Warning/Critical per district per week."""
    playbook = load_playbook()
    # Create 8 high alerts in the same district on the same week
    test_alerts = []
    mon = date(2025, 7, 7) # Monday
    for i in range(8):
        test_alerts.append({
            "site_id": f"S{i+1:02d}",
            "district": "District-1",
            "date": mon,
            "level": "Warning",
            "score": 0.60 + (i * 0.02), # varying scores
            "confidence": 1.0,
            "contributions": {"dominant_signal": "environment", "grouped_pct": {"environment": 100.0}},
        })

    budgeted = apply_alert_budget_and_playbook(test_alerts, playbook_rules=playbook, max_alerts_per_district_per_week=5)
    warning_or_critical = [a for a in budgeted if a["level"] in ["Warning", "Critical"]]
    watch_alerts = [a for a in budgeted if a["level"] == "Watch"]

    assert len(warning_or_critical) == 5, f"Expected exactly 5 high alerts, got {len(warning_or_critical)}"
    assert len(watch_alerts) == 3, f"Expected 3 demoted to Watch, got {len(watch_alerts)}"
