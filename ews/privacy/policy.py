"""Privacy-by-Design policy module: role-based access control, small-cell & complementary suppression, and audit logging."""

from datetime import datetime
from typing import Dict, Any, List, Optional, Union
import numpy as np
import pandas as pd
from sqlalchemy.orm import Session
from ews.db import get_engine, AuditLog

PURPOSE_LIMITATION_BANNER = (
    "FOR PREVENTION ONLY. Not for individual employment, performance, or disciplinary decisions."
)

VALID_ROLES = [
    "Site safety officer",
    "Occupational health lead",
    "District regulator",
    "Data steward",
]


class PrivacyViolationError(Exception):
    """Raised when an unauthorized or individual-level query is attempted."""
    pass


def log_audit_event(
    user_role: str,
    view: str,
    details: Optional[str] = None,
    engine=None,
):
    """Log every view and export to the audit_log table."""
    if engine is None:
        engine = get_engine()
    with Session(engine) as session:
        entry = AuditLog(
            user_role=user_role,
            view=view,
            details=details,
            timestamp=datetime.utcnow(),
        )
        session.add(entry)
        session.commit()


def suppress_small_cell(val: Optional[Union[int, float]], threshold: int = 5) -> str:
    """Format count: if < 5, return '<5', else return formatted number."""
    if val is None or pd.isna(val) or val < 0:
        return "N/A"
    if val < threshold:
        return f"<{threshold}"
    return str(int(val))


def apply_small_cell_and_complementary_suppression(
    df: pd.DataFrame,
    count_columns: List[str],
    group_col: Optional[str] = None,
    threshold: int = 5,
) -> pd.DataFrame:
    """Apply small-cell suppression (<5) and complementary suppression to prevent differencing.
    
    If exactly 1 cell in a grouped total is < 5, differencing (Total - sum(others)) would reveal it.
    Therefore, the second-smallest non-zero cell in that group must also be suppressed!
    """
    out_df = df.copy()

    for col in count_columns:
        if col not in out_df.columns:
            continue

        out_df[col] = out_df[col].astype(object)

        if group_col and group_col in out_df.columns:
            secondary_suppress_indices = set()
            for _, group in out_df.groupby(group_col):
                indices = list(group.index)
                raw_vals = [group.loc[idx, col] for idx in indices]

                # Identify which cells are naturally < threshold
                suppressed_indices = [
                    idx for idx, v in zip(indices, raw_vals)
                    if pd.notna(v) and v >= 0 and v < threshold
                ]

                # Complementary suppression rule:
                # If exactly 1 cell is suppressed in a group with >1 elements,
                # suppress the 2nd smallest to block differencing
                if len(suppressed_indices) == 1 and len(indices) > 1:
                    unsuppressed = [
                        idx for idx, v in zip(indices, raw_vals)
                        if pd.notna(v) and v >= threshold
                    ]
                    if unsuppressed:
                        sec_idx = min(unsuppressed, key=lambda idx: out_df.loc[idx, col])
                        secondary_suppress_indices.add(sec_idx)

            for idx in out_df.index:
                val = out_df.loc[idx, col]
                if pd.isna(val) or val < 0:
                    out_df.loc[idx, col] = "N/A"
                elif val < threshold or idx in secondary_suppress_indices:
                    out_df.loc[idx, col] = f"<{threshold}"
                else:
                    out_df.loc[idx, col] = str(int(val))

        else:
            # Standalone table suppression
            indices = list(out_df.index)
            raw_vals = [out_df.loc[idx, col] for idx in indices]
            suppressed_indices = [
                idx for idx, v in zip(indices, raw_vals)
                if pd.notna(v) and v >= 0 and v < threshold
            ]
            sec_idx = None
            if len(suppressed_indices) == 1 and len(indices) > 1:
                unsuppressed = [
                    idx for idx, v in zip(indices, raw_vals)
                    if pd.notna(v) and v >= threshold
                ]
                if unsuppressed:
                    sec_idx = min(unsuppressed, key=lambda idx: out_df.loc[idx, col])

            for idx in indices:
                val = out_df.loc[idx, col]
                if pd.isna(val) or val < 0:
                    out_df.loc[idx, col] = "N/A"
                elif val < threshold or idx == sec_idx:
                    out_df.loc[idx, col] = f"<{threshold}"
                else:
                    out_df.loc[idx, col] = str(int(val))

    return out_df


def filter_by_role(
    df: pd.DataFrame,
    role: str,
    user_site_id: Optional[str] = "S01",
    user_district: Optional[str] = None,
) -> pd.DataFrame:
    """Enforce role-based access control and scopes.
    
    Roles:
    1. Site safety officer:
       - Own site only (user_site_id)
       - Site-level alerts and actions
    2. Occupational health lead:
       - All sites in assigned district (or all districts)
       - Aggregated clinic detail (with small-cell suppression)
    3. District regulator:
       - District-level summaries and Critical alerts only
       - NO site-level clinic counts (clinic counts column redacted)
    4. Data steward:
       - Data availability, sensor health, and missingness metrics
    """
    if role not in VALID_ROLES:
        raise PrivacyViolationError(f"Unauthorized role '{role}'")

    out = df.copy()

    # Refuse any query keyed to an individual worker
    for forbidden in ["worker_id", "employee_id", "ssn", "name", "national_id"]:
        if forbidden in out.columns:
            raise PrivacyViolationError(f"Individual identifier '{forbidden}' strictly prohibited by policy")

    if role == "Site safety officer":
        if "site_id" in out.columns and user_site_id:
            out = out[out["site_id"] == user_site_id]

    elif role == "Occupational health lead":
        if user_district and "district" in out.columns:
            out = out[out["district"] == user_district]

    elif role == "District regulator":
        # Redact site-level clinic counts completely
        for clinic_col in ["clinic_heat_visits", "clinic_resp_visits"]:
            if clinic_col in out.columns:
                out[clinic_col] = "[REDACTED - REGULATOR SCOPE]"

        # Regulators only see Critical alerts if alerts table
        if "level" in out.columns:
            out = out[out["level"] == "Critical"]

    return out
