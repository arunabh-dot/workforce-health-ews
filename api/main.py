"""FastAPI application for Workforce Health Early Warning System.

Enforces role-based views, small-cell suppression, audit logging,
and provides endpoints for alerts, timeseries, health status, validation, and what-if simulation.
"""

from datetime import date, datetime
from typing import List, Dict, Any, Optional
import json
from pathlib import Path
from fastapi import FastAPI, Query, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import pandas as pd
import numpy as np
from sqlalchemy.orm import Session

from ews.config import load_settings, load_playbook
from ews.db import get_engine, SiteDay, Alert, AuditLog
from ews.privacy.policy import (
    filter_by_role,
    apply_small_cell_and_complementary_suppression,
    log_audit_event,
    PURPOSE_LIMITATION_BANNER,
    PrivacyViolationError,
    VALID_ROLES,
)
from ews.models.fuse import FusionRiskModel, extract_fusion_features
from ews.models.alerting import calculate_confidence, match_playbook_rule

app = FastAPI(
    title="Workforce Health Early Warning System API",
    description="Multi-signal surveillance API fusing weather, air quality, clinic visits, and incidents.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Pydantic Request / Response Models
class AlertItem(BaseModel):
    id: int
    site_id: str
    date: str
    level: str
    score: float
    confidence: float
    role: str
    action_id: str
    action: Optional[str] = None
    evidence: Optional[str] = None
    dominant_signal: Optional[str] = None
    contributions: Dict[str, Any]


class WhatIfRequest(BaseModel):
    site_id: str
    date: str
    dropped_signals: List[str] = Field(default_factory=list, description="e.g. ['clinic', 'pm25']")


class WhatIfResponse(BaseModel):
    site_id: str
    date: str
    original_score: float
    recomputed_score: float
    original_confidence: float
    recomputed_confidence: float
    original_level: str
    recomputed_level: str
    active_dominant_signal: str
    confidence_badge: str
    action_recommended: str
    evidence_shown: str


@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "system": "Workforce Health Early Warning System",
        "purpose_limitation": PURPOSE_LIMITATION_BANNER,
    }


@app.get("/alerts", response_model=List[Dict[str, Any]])
def get_alerts(
    role: str = Query("Site safety officer", description="User role"),
    date_str: Optional[str] = Query(None, alias="date", description="Date YYYY-MM-DD"),
    site_id: Optional[str] = Query(None, description="Optional site filter"),
    district: Optional[str] = Query(None, description="Optional district filter"),
):
    """Retrieve open alerts visible to the requesting role with privacy suppression applied."""
    role_val = role if isinstance(role, str) else "Site safety officer"
    date_val = date_str if isinstance(date_str, str) else None
    site_val = site_id if isinstance(site_id, str) else None
    dist_val = district if isinstance(district, str) else None

    if role_val not in VALID_ROLES:
        raise HTTPException(status_code=403, detail=f"Unauthorized role '{role_val}'")

    engine = get_engine()
    log_audit_event(role_val, "GET /alerts", f"Query date={date_val}, site={site_val}", engine=engine)

    with Session(engine) as session:
        query = session.query(Alert)
        if date_val:
            query = query.filter(Alert.date == pd.to_datetime(date_val).date())
        if site_val and role_val == "Site safety officer":
            query = query.filter(Alert.site_id == site_val)

        rows = query.order_by(Alert.date.desc(), Alert.score.desc()).all()

    if not rows:
        return []

    # Map to list of dicts
    alerts_data = []
    playbook_rules = load_playbook()

    for r in rows:
        contrib = r.get_contributions()
        action_match = match_playbook_rule(
            r.level,
            contrib.get("dominant_signal", "environment"),
            r.confidence,
            playbook_rules,
        )
        alerts_data.append({
            "id": r.id,
            "site_id": r.site_id,
            "date": str(r.date),
            "level": r.level,
            "score": r.score,
            "confidence": r.confidence,
            "action_id": r.action_id,
            "role": r.role,
            "action": action_match.get("action", ""),
            "evidence": action_match.get("evidence_shown", ""),
            "dominant_signal": contrib.get("dominant_signal", "environment"),
            "contributions": contrib,
        })

    alerts_df = pd.DataFrame(alerts_data)
    # Role-based filter
    try:
        filtered_df = filter_by_role(alerts_df, role_val, user_site_id=site_val, user_district=dist_val)
    except PrivacyViolationError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return filtered_df.to_dict(orient="records")


@app.get("/alerts/{alert_id}")
def get_alert_detail(alert_id: int, role: str = Query("Site safety officer")):
    """Get full explanatory details, contributions, evidence, and assumptions for one alert."""
    engine = get_engine()
    log_audit_event(role, f"GET /alerts/{alert_id}", engine=engine)

    with Session(engine) as session:
        alert = session.query(Alert).filter(Alert.id == alert_id).first()
        if not alert:
            raise HTTPException(status_code=404, detail="Alert not found")

        contrib = alert.get_contributions()
        playbook_rules = load_playbook()
        action_match = match_playbook_rule(
            alert.level,
            contrib.get("dominant_signal", "environment"),
            alert.confidence,
            playbook_rules,
        )

        # Assumptions metadata
        settings = load_settings()
        assumptions = {
            "data_disclosure": "Real weather and air quality; simulated workforce signals",
            "detection_threshold": {
                "watch": settings.alerting.watch_threshold,
                "warning": settings.alerting.warning_threshold,
                "critical": settings.alerting.critical_threshold,
            },
            "baseline_window": f"{settings.baseline.rolling_window_days} days rolling (excluding preceding {settings.baseline.exclusion_buffer_days} days)",
            "persistence_rule": "At least 2 consecutive days above threshold to trigger Warning or Critical",
            "purpose_limitation": PURPOSE_LIMITATION_BANNER,
        }

        return {
            "id": alert.id,
            "site_id": alert.site_id,
            "date": str(alert.date),
            "level": alert.level,
            "score": alert.score,
            "confidence": alert.confidence,
            "action_id": alert.action_id,
            "role": alert.role,
            "recommended_action": action_match.get("action", ""),
            "evidence_shown": action_match.get("evidence_shown", ""),
            "contributions": contrib,
            "assumptions": assumptions,
        }


@app.get("/sites/{site_id}/series")
def get_site_series(
    site_id: str,
    signal: Optional[str] = Query("clinic_heat_visits"),
    start_date: Optional[str] = Query(None, alias="start"),
    end_date: Optional[str] = Query(None, alias="end"),
    role: str = Query("Site safety officer"),
):
    """Retrieve observed series, baseline expected values, and CUSUM/EWMA state for charts."""
    engine = get_engine()
    log_audit_event(role, f"GET /sites/{site_id}/series", f"Signal {signal}", engine=engine)

    query = f"SELECT * FROM site_day WHERE site_id = '{site_id}'"
    if start_date:
        query += f" AND date >= '{start_date}'"
    if end_date:
        query += f" AND date <= '{end_date}'"
    query += " ORDER BY date ASC"

    df = pd.read_sql_query(query, con=engine)
    if df.empty:
        raise HTTPException(status_code=404, detail="Site or date range not found")

    df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")

    # If regulator, redact site-level clinic counts
    if role == "District regulator" and signal in ["clinic_heat_visits", "clinic_resp_visits"]:
        raise HTTPException(status_code=403, detail="Site-level clinical counts redacted for District regulator role.")

    # Small cell suppression for count returns
    if signal in ["clinic_heat_visits", "clinic_resp_visits", "incident_count"]:
        df = apply_small_cell_and_complementary_suppression(df, count_columns=[signal])

    return df.to_dict(orient="records")


@app.get("/health/data")
def get_data_health_grid(
    date_str: Optional[str] = Query(None, alias="date"),
    role: str = Query("Data steward"),
):
    """Return signal availability matrix by site for the requested date."""
    engine = get_engine()
    log_audit_event(role, "GET /health/data", f"Date {date_str}", engine=engine)

    query = "SELECT site_id, date, district, signal_available_weather, signal_available_pm25, signal_available_clinic_heat, signal_available_clinic_resp, signal_available_incidents, signal_available_absence FROM site_day"
    if date_str:
        query += f" WHERE date = '{date_str}'"
    query += " ORDER BY site_id ASC"

    df = pd.read_sql_query(query, con=engine)
    if df.empty:
        return []

    df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
    return df.to_dict(orient="records")


@app.get("/validation/report")
def get_validation_report_json():
    """Return the latest validation report metrics as JSON."""
    report_file = Path(__file__).resolve().parent.parent / "validation" / "report.md"
    if not report_file.exists():
        return {"status": "pending", "message": "Validation report has not been generated yet."}

    with open(report_file, "r", encoding="utf-8") as f:
        content = f.read()

    return {
        "status": "ready",
        "markdown_report": content,
    }


@app.post("/whatif/drop-signal", response_model=WhatIfResponse)
def simulate_whatif_drop_signal(req: WhatIfRequest):
    """Simulate dropping one or more signals and recompute risk score, confidence, and alert level.
    
    Demonstrates graceful degradation when inputs are missing.
    """
    engine = get_engine()
    fusion_model = FusionRiskModel.load()
    playbook_rules = load_playbook()
    settings = load_settings()

    # Load recent 10 days for site to simulate rolling CUSUM effect
    target_dt = pd.to_datetime(req.date).date()
    start_dt = target_dt - pd.Timedelta(days=10)

    query = f"SELECT * FROM site_day WHERE site_id = '{req.site_id}' AND date >= '{start_dt}' AND date <= '{target_dt}' ORDER BY date ASC"
    df = pd.read_sql_query(query, con=engine)
    if df.empty:
        raise HTTPException(status_code=404, detail="Site or date not found")

    # Original evaluation
    from ews.models.baseline import compute_site_day_baselines
    from ews.models.detect import apply_anomaly_detection

    base_orig = compute_site_day_baselines(df)
    det_orig = apply_anomaly_detection(base_orig)
    _, X_orig = extract_fusion_features(det_orig)
    probs_orig, _, contribs_orig = fusion_model.predict(X_orig)

    orig_score = float(probs_orig[-1])
    orig_contrib = contribs_orig[-1]
    orig_conf = 1.0
    orig_level = "Warning" if orig_score >= 0.55 else ("Watch" if orig_score >= 0.30 else "Clear")

    # Modified evaluation: Zero out or drop the requested signals
    mod_df = df.copy()
    dropped_lower = [s.lower() for s in req.dropped_signals]
    
    missing_count = len(dropped_lower)
    if "clinic" in dropped_lower or "clinic_heat" in dropped_lower:
        mod_df["clinic_heat_visits"] = np.nan
        mod_df["signal_available_clinic_heat"] = False
    if "pm25" in dropped_lower or "air_quality" in dropped_lower:
        mod_df["pm25"] = np.nan
        mod_df["signal_available_pm25"] = False
    if "incidents" in dropped_lower:
        mod_df["incident_count"] = np.nan
        mod_df["signal_available_incidents"] = False

    base_mod = compute_site_day_baselines(mod_df)
    det_mod = apply_anomaly_detection(base_mod)
    _, X_mod = extract_fusion_features(det_mod)
    probs_mod, _, contribs_mod = fusion_model.predict(X_mod)

    recomputed_score = float(probs_mod[-1])
    recomputed_contrib = contribs_mod[-1]
    recomputed_conf = calculate_confidence(missing_signal_count=missing_count, is_district_fallback=False)

    recomputed_level = "Warning" if recomputed_score >= 0.55 else ("Watch" if recomputed_score >= 0.30 else "Clear")
    dominant_sig = recomputed_contrib.get("dominant_signal", "environment")

    action_match = match_playbook_rule(
        recomputed_level,
        dominant_sig,
        recomputed_conf,
        playbook_rules,
    )

    conf_badge = "High (1.0)" if recomputed_conf >= 0.8 else ("Moderate (0.7)" if recomputed_conf >= 0.5 else "Low (<0.5)")

    return WhatIfResponse(
        site_id=req.site_id,
        date=str(req.date),
        original_score=round(orig_score, 3),
        recomputed_score=round(recomputed_score, 3),
        original_confidence=round(orig_conf, 2),
        recomputed_confidence=round(recomputed_conf, 2),
        original_level=orig_level,
        recomputed_level=recomputed_level,
        active_dominant_signal=dominant_sig,
        confidence_badge=conf_badge,
        action_recommended=action_match.get("action", ""),
        evidence_shown=action_match.get("evidence_shown", ""),
    )
