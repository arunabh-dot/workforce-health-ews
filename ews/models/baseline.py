"""Per-site GLM baselines for Workforce Health Early Warning System.

Fits Poisson / Negative-Binomial GLMs for count signals and OLS for rate
signals over a rolling 365-day window with a 14-day pre-event exclusion
buffer.  Falls back to pooled district-level baselines when a site has
fewer than ``min_history_days`` of data.

Numerical safety guarantees
----------------------------
* ``expected`` is always a **writable** NumPy array (copy=True) so that
  ``expected[invalid] = np.nan`` never raises ``ValueError: assignment
  destination is read-only``.
* All design-matrix NaNs are filled with 0 before fitting.
* Response values are clipped to [1e-6, ∞) for GLMs to avoid log(0).
* ``RuntimeWarning`` and ``SingularMatrixWarning`` from statsmodels are
  suppressed during fitting; the solver still returns a usable solution.
* GLM prediction is done *manually* (X·β + offset → exp) so that the
  ``offset`` kwarg issue in older statsmodels versions is avoided.
"""

import warnings
from datetime import date, timedelta
from typing import Any, Dict, Optional, Tuple

import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.tools import sm_exceptions

from ews.config import load_settings


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def generate_fourier_terms(day_of_year: np.ndarray, harmonics: int = 2) -> Dict[str, np.ndarray]:
    """Return sin/cos Fourier columns for annual seasonality."""
    terms: Dict[str, np.ndarray] = {}
    for h in range(1, harmonics + 1):
        angle = 2.0 * np.pi * h * day_of_year / 365.25
        terms[f"sin_{h}"] = np.sin(angle)
        terms[f"cos_{h}"] = np.cos(angle)
    return terms


def build_design_matrix(
    df: pd.DataFrame,
    include_exposure: bool = True,
    harmonics: int = 2,
) -> pd.DataFrame:
    """Build a feature matrix: day-of-week dummies + Fourier seasonality.

    Parameters
    ----------
    df:               DataFrame with a ``date`` column.
    include_exposure: Whether to append ``log_headcount`` (count models).
    harmonics:        Number of Fourier harmonic pairs.
    """
    design = pd.DataFrame(index=df.index)

    # Day-of-week dummies (Mon=0 is baseline; drop to avoid collinearity)
    dows = pd.to_datetime(df["date"]).dt.dayofweek
    for dow in range(1, 7):
        design[f"dow_{dow}"] = (dows == dow).astype(float)

    # Fourier seasonality
    doy = pd.to_datetime(df["date"]).dt.dayofyear.values.astype(float)
    for k, v in generate_fourier_terms(doy, harmonics=harmonics).items():
        design[k] = v

    if include_exposure and "headcount" in df.columns:
        hc = np.clip(df["headcount"].values, 1, None)
        design["log_headcount"] = np.log(hc)

    return design.fillna(0.0)


# ---------------------------------------------------------------------------
# Per-site model
# ---------------------------------------------------------------------------

class SiteBaselineModel:
    """GLM / OLS baseline estimation for one site (or a district fallback)."""

    def __init__(self, site_id: str, district: str):
        self.site_id = site_id
        self.district = district
        self.models: Dict[str, Any] = {}
        self.is_fallback: bool = False

    # ------------------------------------------------------------------
    def fit_signal(
        self,
        train_df: pd.DataFrame,
        signal_name: str,
        signal_type: str = "count",
        covariate_col: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Fit a GLM (Poisson → NegBin fallback) or OLS model for one signal.

        Returns a dict with keys ``type``, ``model``, (``std`` for OLS),
        and ``covariate``; or ``None`` when there are too few valid rows.
        """
        # --- filter valid rows ------------------------------------------
        valid_mask = train_df[signal_name].notna() & (train_df[signal_name] >= 0)
        if covariate_col:
            valid_mask &= train_df[covariate_col].notna()
        data = train_df[valid_mask].copy()
        if len(data) < 20:
            return None

        # --- design matrix ----------------------------------------------
        X = build_design_matrix(data, include_exposure=False, harmonics=2)
        X = sm.add_constant(X, has_constant="add")
        if covariate_col and covariate_col in data.columns:
            X[covariate_col] = data[covariate_col].fillna(0.0).values
        X = X.fillna(0.0)

        # Clip response to avoid log(0) in GLM
        y = np.clip(data[signal_name].values.astype(float), 1e-6, None)

        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=sm_exceptions.SingularMatrixWarning)
            warnings.filterwarnings("ignore", category=RuntimeWarning)

            if signal_type == "count":
                offset = np.log(np.clip(data["headcount"].values, 1, None))
                # --- try Poisson first, then NegBin ---------------------
                for family, label in [
                    (sm.families.Poisson(), "poisson"),
                    (sm.families.NegativeBinomial(alpha=0.1), "negbin"),
                ]:
                    try:
                        model = sm.GLM(y, X, family=family, offset=offset).fit(
                            maxiter=30, disp=False
                        )
                        return {"type": label, "model": model, "covariate": covariate_col}
                    except Exception:
                        continue
                return None

            else:  # rate / continuous signal
                try:
                    model = sm.OLS(y, X).fit()
                    res_std = float(np.std(model.resid)) if len(model.resid) > 1 else 0.01
                    return {
                        "type": "ols",
                        "model": model,
                        "std": max(res_std, 0.005),
                        "covariate": covariate_col,
                    }
                except Exception:
                    return None

    # ------------------------------------------------------------------
    def predict_slice(
        self,
        slice_df: pd.DataFrame,
        signal_name: str,
        signal_type: str = "count",
        fitted_info: Optional[Dict[str, Any]] = None,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Return ``(expected, residuals)`` for a slice of site-days.

        Always returns **writable** NumPy arrays.
        """
        n = len(slice_df)
        if n == 0:
            return np.array([]), np.array([])

        if fitted_info is None or fitted_info.get("model") is None:
            actual = slice_df[signal_name].fillna(0.0).values.astype(float)
            return np.array(actual, copy=True), np.zeros(n)

        model = fitted_info["model"]
        covariate_col = fitted_info.get("covariate")

        # --- build prediction matrix -----------------------------------
        X = build_design_matrix(slice_df, include_exposure=False, harmonics=2)
        X = sm.add_constant(X, has_constant="add")
        # Add any columns the model was trained with but are absent now
        for col in model.params.index:
            if col not in X.columns:
                if covariate_col and col == covariate_col and covariate_col in slice_df.columns:
                    X[col] = slice_df[covariate_col].fillna(0.0).values
                else:
                    X[col] = 0.0
        X = X[model.params.index].fillna(0.0)

        actual_vals = slice_df[signal_name].values.astype(float)

        if signal_type == "count":
            offset = np.log(np.clip(slice_df["headcount"].values, 1, None))
            # Manual GLM prediction: avoids statsmodels offset kwarg issues
            linear = np.dot(X.values, model.params.values) + offset
            pred = np.exp(np.clip(linear, -20, 20))
            expected = np.array(np.maximum(pred, 1e-6), copy=True)  # writable

            if fitted_info["type"] == "negbin":
                variance = expected + 0.1 * (expected ** 2)
            else:
                variance = expected

            with np.errstate(divide="ignore", invalid="ignore"):
                residuals = (actual_vals - expected) / np.sqrt(np.maximum(variance, 1e-6))

        else:  # OLS
            pred = np.asarray(model.predict(X))
            expected = np.array(pred, copy=True)  # writable
            std = max(fitted_info.get("std", 0.01), 1e-6)
            with np.errstate(divide="ignore", invalid="ignore"):
                residuals = (actual_vals - expected) / std

        # Mask invalid actuals
        invalid = np.isnan(actual_vals) | (~np.isfinite(actual_vals))
        residuals = np.array(residuals, copy=True)
        residuals[invalid] = 0.0
        expected[invalid] = np.nan

        return expected, residuals


# ---------------------------------------------------------------------------
# Public entry-point
# ---------------------------------------------------------------------------

def compute_site_day_baselines(
    site_day_df: pd.DataFrame,
    progress_callback=None,
) -> pd.DataFrame:
    """Compute GLM baselines and Pearson residuals for every site-day.

    Rolling 365-day window with a 14-day pre-event exclusion buffer.
    Falls back to district-pooled models when site history < ``min_history_days``.
    """
    settings = load_settings()
    min_history = settings.baseline.min_history_days      # 120
    window_days = settings.baseline.rolling_window_days   # 365
    buffer_days = settings.baseline.exclusion_buffer_days # 14

    df = site_day_df.sort_values(["site_id", "date"]).copy()
    df["date"] = pd.to_datetime(df["date"]).dt.date

    signals_config = [
        ("clinic_heat_visits", "count", "heat_index_c"),
        ("clinic_resp_visits", "count", "pm25"),
        ("incident_count",     "count", None),
        ("absence_rate",       "rate",  None),
    ]

    for sig, _, _ in signals_config:
        df[f"{sig}_expected"] = np.nan
        df[f"{sig}_residual"] = 0.0
    df["baseline_district_fallback"] = False

    # ---- Pre-fit district fallback models on first 180 days -----------
    early_dates = sorted(df["date"].unique())[:180]
    district_models: Dict[Tuple, Any] = {}
    for dist, dist_df in df[df["date"].isin(early_dates)].groupby("district"):
        fb = SiteBaselineModel(site_id="DISTRICT_FALLBACK", district=dist)
        for sig, sig_type, cov in signals_config:
            district_models[(dist, sig)] = fb.fit_signal(dist_df, sig, sig_type, cov)

    # ---- Iterate sites and days ---------------------------------------
    for site_id, site_df in df.groupby("site_id"):
        bm = SiteBaselineModel(site_id=site_id, district=site_df["district"].iloc[0])
        site_dates = sorted(site_df["date"].unique())

        for cur_date in site_dates:
            w_start = cur_date - timedelta(days=window_days)
            w_end   = cur_date - timedelta(days=buffer_days + 1)
            train_mask  = (site_df["date"] >= w_start) & (site_df["date"] <= w_end)
            train_slice = site_df[train_mask]
            cur_slice   = site_df[site_df["date"] == cur_date]

            row_mask = (df["site_id"] == site_id) & (df["date"] == cur_date)

            if len(train_slice) < min_history:
                # Use district fallback
                bm.is_fallback = True
                df.loc[row_mask, "baseline_district_fallback"] = True
                for sig, sig_type, _ in signals_config:
                    fallback = district_models.get((bm.district, sig))
                    exp, res = bm.predict_slice(cur_slice, sig, sig_type, fallback)
                    if len(exp) > 0:
                        df.loc[row_mask, f"{sig}_expected"] = exp[0] if not np.isnan(exp[0]) else np.nan
                        df.loc[row_mask, f"{sig}_residual"] = res[0]
            else:
                for sig, sig_type, cov in signals_config:
                    fitted = bm.fit_signal(train_slice, sig, sig_type, cov)
                    exp, res = bm.predict_slice(cur_slice, sig, sig_type, fitted)
                    if len(exp) > 0:
                        df.loc[row_mask, f"{sig}_expected"] = exp[0] if not np.isnan(exp[0]) else np.nan
                        df.loc[row_mask, f"{sig}_residual"] = res[0]

    return df
