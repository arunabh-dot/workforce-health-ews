"""Acceptance tests for Privacy Policy module (Step 6)."""

import pytest
import pandas as pd
from ews.privacy.policy import (
    suppress_small_cell,
    apply_small_cell_and_complementary_suppression,
    filter_by_role,
    PrivacyViolationError,
    PURPOSE_LIMITATION_BANNER,
    log_audit_event,
)
from ews.db import get_engine, AuditLog
from sqlalchemy.orm import Session


def test_small_cell_suppression_single():
    assert suppress_small_cell(0) == "<5"
    assert suppress_small_cell(3) == "<5"
    assert suppress_small_cell(4) == "<5"
    assert suppress_small_cell(5) == "5"
    assert suppress_small_cell(12) == "12"
    assert suppress_small_cell(None) == "N/A"


def test_complementary_suppression_blocks_differencing():
    """Verify that if a single cell is <5, complementary suppression suppresses a 2nd cell."""
    # Group of 4 sites in district with counts: [3, 10, 15, 20]
    # Sum is 48. If only 3 is suppressed, 48 - (10+15+20) = 3 reveals it!
    # With complementary suppression, 10 must also be suppressed!
    df = pd.DataFrame({
        "site_id": ["S01", "S02", "S03", "S04"],
        "district": ["D1", "D1", "D1", "D1"],
        "clinic_heat_visits": [3, 10, 15, 20],
    })

    suppressed = apply_small_cell_and_complementary_suppression(
        df, count_columns=["clinic_heat_visits"], group_col="district"
    )

    vals = suppressed["clinic_heat_visits"].tolist()
    # Exactly two cells should now be '<5' (3 and 10)
    assert vals.count("<5") == 2
    assert "<5" in vals[0] # Original < 5
    assert "<5" in vals[1] # Complementary suppressed 10
    assert vals[2] == "15"
    assert vals[3] == "20"


def test_role_based_access_scopes():
    df_sites = pd.DataFrame({
        "site_id": ["S01", "S02", "S03"],
        "district": ["D1", "D1", "D2"],
        "clinic_heat_visits": [12, 14, 18],
        "level": ["Watch", "Warning", "Critical"],
    })

    # 1. Site safety officer: own site only
    sso = filter_by_role(df_sites, "Site safety officer", user_site_id="S01")
    assert len(sso) == 1
    assert sso["site_id"].iloc[0] == "S01"

    # 2. Occupational health lead: assigned district
    ohl = filter_by_role(df_sites, "Occupational health lead", user_district="D1")
    assert len(ohl) == 2
    assert set(ohl["site_id"]) == {"S01", "S02"}

    # 3. District regulator: Critical only and clinic counts redacted
    reg = filter_by_role(df_sites, "District regulator")
    assert len(reg) == 1
    assert reg["level"].iloc[0] == "Critical"
    assert "[REDACTED - REGULATOR SCOPE]" in reg["clinic_heat_visits"].iloc[0]


def test_refuse_individual_identifier_queries():
    df_with_worker = pd.DataFrame({
        "worker_id": ["W123"],
        "site_id": ["S01"],
        "count": [2],
    })
    with pytest.raises(PrivacyViolationError):
        filter_by_role(df_with_worker, "Site safety officer")


def test_audit_log_entry():
    engine = get_engine()
    log_audit_event("District regulator", "Alerts Overview", "Inspected critical alerts", engine=engine)
    with Session(engine) as session:
        recent = session.query(AuditLog).order_by(AuditLog.id.desc()).first()
        assert recent is not None
        assert recent.user_role == "District regulator"
        assert recent.view == "Alerts Overview"
