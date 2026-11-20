"""Test simulation generator reproducibility and event properties."""

from pathlib import Path
import pandas as pd
import pytest
from ews.sim.generate import generate_simulation_dataset
from ews.db import get_engine, EventTruth, SiteDay
from sqlalchemy import func, select
from sqlalchemy.orm import Session


def test_seed_reproducibility():
    """Verify that same seed gives identical output."""
    df1, ev1 = generate_simulation_dataset(seed=42)
    df2, ev2 = generate_simulation_dataset(seed=42)

    pd.testing.assert_frame_equal(df1, df2)
    assert len(ev1) == len(ev2)
    for e1, e2 in zip(ev1, ev2):
        assert e1["event_id"] == e2["event_id"]
        assert e1["start_date"] == e2["start_date"]
        assert e1["affected_sites"] == e2["affected_sites"]


def test_events_truth_count():
    """Verify events_truth has between 12 and 15 events."""
    engine = get_engine()
    with Session(engine) as session:
        count = session.query(func.count(EventTruth.id)).scalar()
        assert 12 <= count <= 15, f"Expected 12 to 15 events, found {count}"


def test_lag_structure_figure_exists():
    """Verify that the diagnostic plot showing lagged rises was generated."""
    fig1 = Path("ews/validation/figures/lag_structure.png")
    fig2 = Path("validation/figures/lag_structure.png")
    assert fig1.exists() or fig2.exists(), "Lag structure plot must exist"


def test_site_day_coverage_and_bad_site():
    """Verify 30 sites across 1096 days = 32880 records, and persistent bad data site."""
    engine = get_engine()
    with Session(engine) as session:
        site_day_count = session.query(func.count(SiteDay.id)).scalar()
        assert site_day_count == 30 * 1096

        # Check S13 has missing data flags
        s13_missing = (
            session.query(func.count(SiteDay.id))
            .filter(SiteDay.site_id == "S13", SiteDay.signal_available_clinic_heat == False)
            .scalar()
        )
        assert s13_missing > 100, f"S13 should have persistent missing gaps, found {s13_missing}"
