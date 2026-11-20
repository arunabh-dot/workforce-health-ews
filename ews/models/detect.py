"""Per-signal anomaly detection using CUSUM, EWMA, and environmental exceedances."""

import numpy as np
import pandas as pd
from typing import Dict, Any, List
from ews.config import load_settings


def compute_cusum_series(
    residuals: np.ndarray,
    k: float = 0.5,
) -> np.ndarray:
    """Compute one-sided tabular CUSUM:
    S(t) = max(0, S(t-1) + z(t) - k)
    """
    n = len(residuals)
    s = np.zeros(n, dtype=float)
    current_s = 0.0

    for i in range(n):
        z = residuals[i]
        if np.isnan(z):
            # Treat missing data neutrally (slack slowly decays)
            current_s = max(0.0, current_s - k)
        else:
            current_s = max(0.0, current_s + z - k)
        s[i] = current_s

    return s


def compute_ewma_series(
    values: np.ndarray,
    lambda_: float = 0.3,
) -> np.ndarray:
    """Compute EWMA smoother for dashboard trend visualization:
    EWMA(t) = lambda * x(t) + (1 - lambda) * EWMA(t-1)
    """
    n = len(values)
    ewma = np.zeros(n, dtype=float)
    if n == 0:
        return ewma

    # Initialize with first non-null
    first_val = values[0] if not np.isnan(values[0]) else 0.0
    current_ewma = first_val
    ewma[0] = current_ewma

    for i in range(1, n):
        val = values[i]
        if not np.isnan(val):
            current_ewma = lambda_ * val + (1.0 - lambda_) * current_ewma
        ewma[i] = current_ewma

    return ewma


def apply_anomaly_detection(
    df: pd.DataFrame,
    k: float = 0.5,
    h: float = 4.0,
    lambda_: float = 0.3,
) -> pd.DataFrame:
    """Apply CUSUM, EWMA, and environmental exceedances per site."""
    settings = load_settings()
    k_val = k or settings.cusum.k
    h_val = h or settings.cusum.h
    lam_val = lambda_ or settings.ewma.lambda_
    hi_threshold = settings.environment.heat_index_high_risk_threshold_c # 41.0 C
    pm25_threshold = settings.environment.pm25_unhealthy_threshold       # 55.5 ug/m3

    df = df.sort_values(["site_id", "date"]).copy()

    # Environmental direct exceedances
    df["heat_index_exceedance"] = np.maximum(0.0, df["heat_index_c"].fillna(0.0) - hi_threshold)
    df["pm25_exceedance"] = np.maximum(0.0, df["pm25"].fillna(0.0) - pm25_threshold)
    df["env_high_risk_flag"] = (df["heat_index_c"] >= hi_threshold) | (df["pm25"] >= pm25_threshold)

    workforce_signals = [
        "clinic_heat_visits",
        "clinic_resp_visits",
        "incident_count",
        "absence_rate",
    ]

    # Process per site
    processed = []
    for sid, s_df in df.groupby("site_id", sort=False):
        s_df = s_df.sort_values("date").copy()

        for sig in workforce_signals:
            res_col = f"{sig}_residual"
            if res_col in s_df.columns:
                residuals = s_df[res_col].values
                cusum_vals = compute_cusum_series(residuals, k=k_val)
                s_df[f"{sig}_cusum"] = cusum_vals
                s_df[f"{sig}_alarm"] = (cusum_vals >= h_val)
                s_df[f"{sig}_ewma"] = compute_ewma_series(residuals, lambda_=lam_val)
            else:
                s_df[f"{sig}_cusum"] = 0.0
                s_df[f"{sig}_alarm"] = False
                s_df[f"{sig}_ewma"] = 0.0

        processed.append(s_df)

    return pd.concat(processed, ignore_index=True)
