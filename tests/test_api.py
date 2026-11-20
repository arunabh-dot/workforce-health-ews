"""Acceptance tests for FastAPI endpoints (Step 9)."""

import pytest
from api.main import (
    app,
    health_check,
    get_alerts,
    get_alert_detail,
    simulate_whatif_drop_signal,
    WhatIfRequest,
)
from ews.privacy.policy import PURPOSE_LIMITATION_BANNER
from fastapi import HTTPException


def test_openapi_docs_load():
    """Verify OpenAPI documentation schema loads cleanly."""
    schema = app.openapi()
    assert schema["info"]["title"] == "Workforce Health Early Warning System API"
    assert "/alerts" in schema["paths"]
    assert "/whatif/drop-signal" in schema["paths"]
    assert "/health" in schema["paths"]


def test_health_endpoint():
    res = health_check()
    assert res["status"] == "healthy"
    assert PURPOSE_LIMITATION_BANNER in res["purpose_limitation"]


def test_get_alerts_role_filtering():
    """Verify alerts are filtered according to the requester's role."""
    # 1. Site safety officer
    alerts_sso = get_alerts(role="Site safety officer", site_id="S01")
    for a in alerts_sso:
        assert a["site_id"] == "S01"

    # 2. District regulator: only sees Critical alerts
    alerts_reg = get_alerts(role="District regulator")
    for a in alerts_reg:
        assert a["level"] == "Critical"

    # 3. Invalid role raises HTTPException 403
    with pytest.raises(HTTPException) as excinfo:
        get_alerts(role="Unauthorized Auditor")
    assert excinfo.value.status_code == 403


def test_whatif_drop_signal_endpoint():
    """Verify the what-if endpoint gracefully recomputes score and downscales confidence."""
    req = WhatIfRequest(
        site_id="S01",
        date="2025-07-18",
        dropped_signals=["clinic", "pm25"],
    )
    res = simulate_whatif_drop_signal(req)
    assert res.site_id == "S01"
    assert res.recomputed_confidence < res.original_confidence
    assert res.recomputed_confidence <= 0.50
    assert len(res.action_recommended) > 0
    assert len(res.evidence_shown) > 0
