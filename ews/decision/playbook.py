"""Playbook rule engine mapping alert level, dominant signal, and confidence to actions and roles."""

from pathlib import Path
from typing import Dict, Any, List, Optional
import yaml
from ews.config import load_playbook


class PlaybookEngine:
    """Action playbook rule matcher."""

    def __init__(self, rules: Optional[List[Dict[str, Any]]] = None):
        self.rules = rules if rules is not None else load_playbook()

    def get_action(
        self,
        level: str,
        dominant_signal: str = "environment",
        confidence: float = 1.0,
    ) -> Dict[str, Any]:
        """Match an alert level and dominant signal to exactly one recommended action and role.
        
        Guarantees non-empty action, role, and evidence fields.
        """
        # Low confidence condition takes precedence
        if confidence < 0.50:
            low_conf = next((r for r in self.rules if r.get("id") == "RULE_LOW_CONFIDENCE"), None)
            if low_conf:
                return {
                    "rule_id": low_conf["id"],
                    "action": low_conf["action"],
                    "role": low_conf["role"],
                    "evidence": low_conf["evidence_shown"],
                    "is_low_confidence": True,
                }

        # Priority 1: Exact level + exact signal match
        for r in self.rules:
            if r.get("level") == level and r.get("dominant_signal") == dominant_signal:
                return {
                    "rule_id": r["id"],
                    "action": r["action"],
                    "role": r["role"],
                    "evidence": r["evidence_shown"],
                    "is_low_confidence": False,
                }

        # Priority 2: Level match with ANY signal
        for r in self.rules:
            if r.get("level") == level and r.get("dominant_signal") == "ANY":
                return {
                    "rule_id": r["id"],
                    "action": r["action"],
                    "role": r["role"],
                    "evidence": r["evidence_shown"],
                    "is_low_confidence": False,
                }

        # Fallback default
        return {
            "rule_id": "RULE_GENERIC_SAFETY_ACTION",
            "action": f"Implement standard {level} protocol and notify safety officer",
            "role": "Site safety officer",
            "evidence": "Observed multi-signal trend elevation",
            "is_low_confidence": False,
        }
