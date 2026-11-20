"""Initial scaffold tests to verify environment and schema initialization."""

import pytest
from ews.config import load_settings, load_playbook
from ews.db import get_engine, init_db, Base, SiteDay, Alert, EventTruth, AuditLog
from sqlalchemy import inspect


def test_settings_load():
    settings = load_settings()
    assert settings.district.total_sites == 30
    assert settings.district.num_districts == 5
    assert settings.dates.start_date == "2023-01-01"
    assert settings.alerting.watch_threshold == 0.30


def test_playbook_load():
    rules = load_playbook()
    assert len(rules) >= 5
    rule_ids = [r["id"] for r in rules]
    assert "RULE_CRITICAL_MULTI_SIGNAL" in rule_ids


def test_db_init(tmp_path):
    test_db_file = tmp_path / "test_ews.db"
    engine = get_engine(test_db_file)
    init_db(engine)

    inspector = inspect(engine)
    tables = inspector.get_table_names()
    assert "site_day" in tables
    assert "alerts" in tables
    assert "events_truth" in tables
    assert "audit_log" in tables
