"""Risk score fusion with regularized logistic regression, calibration, and faithful explanations."""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.isotonic import IsotonicRegression
from sklearn.model_selection import train_test_split

from ews.config import load_settings

MODEL_SAVE_PATH = Path(__file__).resolve().parent / "fusion_model.joblib"

FEATURE_NAMES = [
    "clinic_heat_cusum",
    "clinic_resp_cusum",
    "incident_cusum",
    "heat_index_exceed",
    "pm25_exceed",
    "district_peer_heat_cusum",
    "district_peer_resp_cusum",
    "district_peer_incident_cusum",
    "district_peer_hi_exceed",
    "district_peer_pm25_exceed",
    # Engineered features
    "heat_pm25_interaction",
    "clinic_heat_cusum_lag7",
    "clinic_heat_cusum_lag14",
    "clinic_resp_cusum_lag7",
    "clinic_resp_cusum_lag14",
    "incident_cusum_lag7",
    "incident_cusum_lag14",
]


def extract_fusion_features(df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Compute site features and district peer mean features."""
    df = df.copy()

    # Map raw columns to feature names
    df["clinic_heat_cusum"]  = df.get("clinic_heat_visits_cusum",  pd.Series(0.0, index=df.index)).fillna(0.0)
    df["clinic_resp_cusum"]  = df.get("clinic_resp_visits_cusum",  pd.Series(0.0, index=df.index)).fillna(0.0)
    df["incident_cusum"]     = df.get("incident_count_cusum",       pd.Series(0.0, index=df.index)).fillna(0.0)
    df["heat_index_exceed"]  = df.get("heat_index_exceedance",      pd.Series(0.0, index=df.index)).fillna(0.0)
    df["pm25_exceed"]        = df.get("pm25_exceedance",            pd.Series(0.0, index=df.index)).fillna(0.0)

    # Interaction feature
    df["heat_pm25_interaction"] = df["heat_index_exceed"] * df["pm25_exceed"]

    # Lagged CUSUMs (per site, 7- and 14-day)
    for col in ["clinic_heat_cusum", "clinic_resp_cusum", "incident_cusum"]:
        df[f"{col}_lag7"]  = df.groupby("site_id")[col].shift(7).fillna(0.0)
        df[f"{col}_lag14"] = df.groupby("site_id")[col].shift(14).fillna(0.0)

    base_cols = [
        "clinic_heat_cusum",
        "clinic_resp_cusum",
        "incident_cusum",
        "heat_index_exceed",
        "pm25_exceed",
    ]

    # District peer means: (district_total - site_val) / max(1, n_sites - 1)
    district_sums   = df.groupby(["district", "date"])[base_cols].transform("sum")
    district_counts = df.groupby(["district", "date"])["site_id"].transform("count")
    peer_means = (district_sums - df[base_cols]) / np.maximum(1, district_counts.values[:, None] - 1)
    peer_means.columns = [
        "district_peer_heat_cusum",
        "district_peer_resp_cusum",
        "district_peer_incident_cusum",
        "district_peer_hi_exceed",
        "district_peer_pm25_exceed",
    ]

    extra_cols = [
        "heat_pm25_interaction",
        "clinic_heat_cusum_lag7",  "clinic_heat_cusum_lag14",
        "clinic_resp_cusum_lag7",  "clinic_resp_cusum_lag14",
        "incident_cusum_lag7",     "incident_cusum_lag14",
    ]

    features = pd.concat([df[base_cols], peer_means, df[extra_cols]], axis=1)[FEATURE_NAMES]
    features = features.fillna(0.0)
    return df, features


class FusionRiskModel:
    """L2 Logistic Regression with Isotonic Probability Calibration."""

    def __init__(self):
        self.model = LogisticRegression(
            penalty="l2",
            C=0.5,           # slightly stronger regularisation for small event sets
            solver="lbfgs",
            max_iter=1000,
            random_state=42,
        )
        self.calibrator = IsotonicRegression(out_of_bounds="clip", y_min=0.001, y_max=0.999)
        self.feature_names = FEATURE_NAMES
        self.is_fitted = False

    def fit(self, X_train: pd.DataFrame, y_train: np.ndarray):
        """Fit logistic regression and calibrate on a held-out 30 % split."""
        # Stratified split when both classes present; fallback to simple split
        try:
            X_fit, X_cal, y_fit, y_cal = train_test_split(
                X_train, y_train,
                test_size=0.30,
                stratify=y_train,
                random_state=42,
            )
        except ValueError:
            n = len(X_train)
            split = int(0.70 * n)
            X_fit, y_fit = X_train.iloc[:split],  y_train[:split]
            X_cal, y_cal = X_train.iloc[split:],  y_train[split:]

        self.model.fit(X_fit, y_fit)
        raw_probs_cal = self.model.predict_proba(X_cal)[:, 1]
        self.calibrator.fit(raw_probs_cal, y_cal)
        self.is_fitted = True

    def predict(self, X: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray, List[Dict[str, Any]]]:
        """Return (calibrated_probs, raw_log_odds, contributions)."""
        if not self.is_fitted:
            raise RuntimeError("Model must be fitted before predict")

        intercept = float(self.model.intercept_[0])
        coefs     = self.model.coef_[0]

        X_mat = X[self.feature_names].fillna(0.0).values
        linear_components = X_mat * coefs
        raw_log_odds = np.sum(linear_components, axis=1) + intercept

        raw_probs       = 1.0 / (1.0 + np.exp(-np.clip(raw_log_odds, -15, 15)))
        calibrated_probs = np.clip(self.calibrator.predict(raw_probs), 0.001, 0.999)

        all_contributions: List[Dict[str, Any]] = []
        for i in range(len(X)):
            comp = linear_components[i]
            # Indices in FEATURE_NAMES:
            # 0=clinic_heat_cusum, 1=clinic_resp_cusum, 2=incident_cusum,
            # 3=heat_index_exceed, 4=pm25_exceed,
            # 5=peer_heat, 6=peer_resp, 7=peer_incident, 8=peer_hi, 9=peer_pm25
            # 10=interaction, 11-16=lags
            env_log_odds      = float(comp[3] + comp[8] + comp[10])  # heat + hi_peer + interaction
            aq_log_odds       = float(comp[4] + comp[9])              # pm25 + pm25_peer
            clinic_log_odds   = float(comp[0] + comp[1] + comp[5] + comp[6])  # clinic + peers
            incident_log_odds = float(comp[2] + comp[7])              # incidents + peer
            lag_log_odds      = float(np.sum(comp[11:]))              # all lags

            grouped = {
                "environment": max(0.0, env_log_odds),
                "pm25":        max(0.0, aq_log_odds),
                "clinic":      max(0.0, clinic_log_odds),
                "incidents":   max(0.0, incident_log_odds),
                "lagged":      max(0.0, lag_log_odds),
            }

            pos_sum = sum(grouped.values())
            if pos_sum > 0:
                pcts = {k: round((v / pos_sum) * 100.0, 1) for k, v in grouped.items()}
            else:
                pcts = {k: 0.0 for k in grouped}

            dominant_signal = max(grouped.items(), key=lambda kv: kv[1])[0] if pos_sum > 0 else "environment"
            active_signals  = [k for k, v in pcts.items() if v >= 20.0]
            if len(active_signals) >= 2:
                dominant_signal = "multi_signal"

            all_contributions.append({
                "grouped_log_odds":      {k: round(v, 4) for k, v in grouped.items()},
                "grouped_pct":           pcts,
                "feature_contributions": {feat: round(float(c), 4) for feat, c in zip(self.feature_names, comp)},
                "intercept":             round(intercept, 4),
                "total_log_odds":        round(float(raw_log_odds[i]), 4),
                "dominant_signal":       dominant_signal,
                "active_signal_count":   len(active_signals),
            })

        return calibrated_probs, raw_log_odds, all_contributions

    def save(self, path: Optional[Path] = None):
        target = path or MODEL_SAVE_PATH
        target.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self, target)

    @classmethod
    def load(cls, path: Optional[Path] = None) -> "FusionRiskModel":
        target = path or MODEL_SAVE_PATH
        return joblib.load(target)
