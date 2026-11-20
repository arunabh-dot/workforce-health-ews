"""FastAPI application for the Workforce Health Early Warning System.

Endpoints
---------
GET  /                      – health check
GET  /sites                 – list all site IDs and districts
GET  /alerts                – latest alerts (optional ?level= filter)
GET  /alerts/{site_id}      – alerts for a specific site
GET  /scores/{site_id}      – latest calibrated risk score for a site
GET  /events                – ground-truth events (admin view)
GET  /validation/summary    – backtest metrics summary (from report.md)
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from ews.db import get_engine

app = FastAPI(
    title="Workforce Health Early Warning System API",
    description=(
        "Multi-signal early warning system for outdoor / industrial workforce health. "
        "Fuses real meteorological data, air-quality telemetry, and simulated clinical "
        "surveillance into calibrated probabilistic alerts."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Allow Streamlit dashboard and local testing to call the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


def _engine():
    return get_engine()


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.get("/", tags=["Health"])
def root():
    return {"status": "ok", "system": "Workforce Health EWS", "version": "1.0.0"}


# ---------------------------------------------------------------------------
# Sites
# ---------------------------------------------------------------------------

@app.get("/sites", tags=["Sites"])
def list_sites() -> List[Dict[str, Any]]:
    """Return all site IDs and their district assignments."""
    engine = _engine()
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT DISTINCT site_id, district FROM site_day ORDER BY site_id")
        ).fetchall()
    return [{"site_id": r[0], "district": r[1]} for r in rows]


# ---------------------------------------------------------------------------
# Alerts
# ---------------------------------------------------------------------------

@app.get("/alerts", tags=["Alerts"])
def get_alerts(
    level: Optional[str] = Query(None, description="Filter by level: Watch, Warning, Critical"),
    limit: int = Query(200, ge=1, le=5000),
) -> List[Dict[str, Any]]:
    """Return the most recent alerts, optionally filtered by severity level."""
    engine = _engine()
    with engine.connect() as conn:
        if level:
            rows = conn.execute(
                text(
                    "SELECT site_id, date, level, score, contributions, action_id, role, confidence "
                    "FROM alerts WHERE level = :lvl ORDER BY date DESC, score DESC LIMIT :lim"
                ),
                {"lvl": level, "lim": limit},
            ).fetchall()
        else:
            rows = conn.execute(
                text(
                    "SELECT site_id, date, level, score, contributions, action_id, role, confidence "
                    "FROM alerts ORDER BY date DESC, score DESC LIMIT :lim"
                ),
                {"lim": limit},
            ).fetchall()

    result = []
    for r in rows:
        try:
            contribs = json.loads(r[4]) if isinstance(r[4], str) else r[4]
        except Exception:
            contribs = {}
        result.append({
            "site_id":      r[0],
            "date":         str(r[1]),
            "level":        r[2],
            "score":        r[3],
            "contributions": contribs,
            "action_id":    r[5],
            "role":         r[6],
            "confidence":   r[7],
        })
    return result


@app.get("/alerts/{site_id}", tags=["Alerts"])
def get_site_alerts(site_id: str, limit: int = Query(90, ge=1, le=1000)) -> List[Dict[str, Any]]:
    """Return the most recent alerts for a specific site."""
    engine = _engine()
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT date, level, score, contributions, action_id, role, confidence "
                "FROM alerts WHERE site_id = :sid ORDER BY date DESC LIMIT :lim"
            ),
            {"sid": site_id, "lim": limit},
        ).fetchall()
    if not rows:
        raise HTTPException(status_code=404, detail=f"No alerts found for site '{site_id}'")
    result = []
    for r in rows:
        try:
            contribs = json.loads(r[3]) if isinstance(r[3], str) else r[3]
        except Exception:
            contribs = {}
        result.append({
            "site_id":       site_id,
            "date":          str(r[0]),
            "level":         r[1],
            "score":         r[2],
            "contributions": contribs,
            "action_id":     r[4],
            "role":          r[5],
            "confidence":    r[6],
        })
    return result


# ---------------------------------------------------------------------------
# Risk scores
# ---------------------------------------------------------------------------

@app.get("/scores/{site_id}", tags=["Scores"])
def get_site_latest_score(site_id: str) -> Dict[str, Any]:
    """Return the latest calibrated risk score for a site."""
    engine = _engine()
    with engine.connect() as conn:
        row = conn.execute(
            text(
                "SELECT date, score, level, confidence FROM alerts "
                "WHERE site_id = :sid ORDER BY date DESC LIMIT 1"
            ),
            {"sid": site_id},
        ).fetchone()
    if row is None:
        return {"site_id": site_id, "score": None, "level": "Clear", "date": None}
    return {
        "site_id":    site_id,
        "date":       str(row[0]),
        "score":      row[1],
        "level":      row[2],
        "confidence": row[3],
    }


# ---------------------------------------------------------------------------
# Ground-truth events (admin)
# ---------------------------------------------------------------------------

@app.get("/events", tags=["Validation"])
def get_truth_events() -> List[Dict[str, Any]]:
    """Return ground-truth event records (for validation and demo purposes)."""
    engine = _engine()
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT event_id, event_type, start_date, end_date, affected_sites, severity, description FROM events_truth")
        ).fetchall()
    result = []
    for r in rows:
        try:
            sites = json.loads(r[4]) if isinstance(r[4], str) else r[4]
        except Exception:
            sites = []
        result.append({
            "event_id":       r[0],
            "event_type":     r[1],
            "start_date":     str(r[2]),
            "end_date":       str(r[3]),
            "affected_sites": sites,
            "severity":       r[5],
            "description":    r[6],
        })
    return result


# ---------------------------------------------------------------------------
# Validation summary
# ---------------------------------------------------------------------------

@app.get("/validation/summary", tags=["Validation"])
def validation_summary() -> Dict[str, Any]:
    """Return the most recent backtest metric summary."""
    report_path = Path(__file__).resolve().parent.parent.parent / "validation" / "report.md"
    if not report_path.exists():
        raise HTTPException(status_code=404, detail="Validation report not found. Run python -m ews.validation.backtest first.")
    # Return the raw markdown; the Streamlit page renders it
    return {
        "report_path": str(report_path),
        "report_md":   report_path.read_text(encoding="utf-8"),
    }
