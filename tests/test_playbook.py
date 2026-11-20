"""Acceptance tests for Playbook Engine (Step 7)."""

import pytest
from ews.decision.playbook import PlaybookEngine


def test_every_level_and_signal_maps_to_action_and_role():
    """Verify that every alert level and signal type maps to exactly one action and role."""
    engine = PlaybookEngine()

    levels = ["Watch", "Warning", "Critical"]
    signals = ["environment", "pm25", "clinic", "incidents", "multi_signal"]

    for lvl in levels:
        for sig in signals:
            decision = engine.get_action(lvl, dominant_signal=sig, confidence=1.0)
            assert decision is not None
            assert isinstance(decision["rule_id"], str) and len(decision["rule_id"]) > 0
            assert isinstance(decision["action"], str) and len(decision["action"]) > 0
            assert isinstance(decision["role"], str) and len(decision["role"]) > 0
            assert isinstance(decision["evidence"], str) and len(decision["evidence"]) > 0


def test_low_confidence_override():
    """Verify that confidence < 0.50 triggers the data steward verification rule."""
    engine = PlaybookEngine()
    decision = engine.get_action("Critical", dominant_signal="environment", confidence=0.45)
    assert decision["rule_id"] == "RULE_LOW_CONFIDENCE"
    assert "Data steward" in decision["role"]
    assert "Verify data feeds" in decision["action"]
