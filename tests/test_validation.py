"""Tests for Validation and Metric Calculation functions."""

import pytest
import numpy as np
import pandas as pd
from datetime import date, timedelta
from ews.validation.backtest import calculate_metrics, deduplicate_alert_episodes


def test_deduplicate_alert_episodes():
    """Verify consecutive alert days collapse into a single episode."""
    d0 = date(2025, 7, 1)
    d1 = date(2025, 7, 2)
    d2 = date(2025, 7, 3)
    d5 = date(2025, 7, 6) # Separated by 3 days

    alerts = [
        {"site_id": "S01", "date": d0, "level": "Warning", "score": 0.60, "confidence": 1.0, "contributions": {}},
        {"site_id": "S01", "date": d1, "level": "Critical", "score": 0.80, "confidence": 0.9, "contributions": {}},
        {"site_id": "S01", "date": d2, "level": "Critical", "score": 0.85, "confidence": 0.9, "contributions": {}},
        {"site_id": "S01", "date": d5, "level": "Warning", "score": 0.62, "confidence": 1.0, "contributions": {}},
    ]

    episodes = deduplicate_alert_episodes(alerts)
    assert len(episodes) == 2, f"Expected 2 episodes (d0-d2 and d5), got {len(episodes)}"
    assert episodes[0]["start_date"] == d0
    assert episodes[0]["last_date"] == d2
    assert episodes[0]["max_level"] == "Critical"
    assert episodes[0]["max_score"] == 0.85

    assert episodes[1]["start_date"] == d5
    assert episodes[1]["max_level"] == "Warning"


def test_calculate_metrics_synthetic():
    """Verify sensitivity, lead time, and PPV calculation on known synthetic scenario."""
    ev_start = date(2025, 6, 10)
    ev_end = date(2025, 6, 14)
    test_events = [{
        "event_id": "EVT_TEST",
        "event_type": "heat_wave",
        "start_date": ev_start,
        "end_date": ev_end,
        "affected_sites": ["S01"],
        "severity": 2.0,
    }]

    # Alert fired on June 9 (1 day before start, 2 days before harm threshold June 11)
    alerts = [
        {"site_id": "S01", "date": date(2025, 6, 9), "level": "Warning", "score": 0.65, "confidence": 1.0, "contributions": {}},
        {"site_id": "S01", "date": date(2025, 6, 10), "level": "Critical", "score": 0.80, "confidence": 1.0, "contributions": {}},
    ]

    dummy_df = pd.DataFrame([{"date": date(2025, 6, 9), "site_id": "S01"}])
    m = calculate_metrics(alerts, test_events, dummy_df, total_days=30)

    assert m["detected_events"] == 1
    assert m["sensitivity_pct"] == 100.0
    assert m["lead_time_days"] == 2.0  # June 11 (harm) - June 9 (alert) = 2 days
    assert m["ppv_pct"] == 100.0
    assert m["false_alarms_per_month"] == 0.0
