"""Pipeline runner: Fits baselines, anomaly detection, fusion model, and generates alerts."""

import json
from pathlib import Path
from datetime import datetime
import pandas as pd
import numpy as np
from sqlalchemy.orm import Session

from ews.config import load_settings, load_playbook
from ews.db import get_engine, init_db, SiteDay, Alert
from ews.models.baseline import compute_site_day_baselines
from ews.models.detect import apply_anomaly_detection
from ews.models.fuse import extract_fusion_features, FusionRiskModel, MODEL_SAVE_PATH
from ews.models.alerting import evaluate_site_alert_stream, apply_alert_budget_and_playbook


def run_model_training_and_scoring(engine=None):
    """End-to-end model pipeline: baselines -> detection -> training -> scoring -> alerting."""
    if engine is None:
        engine = get_engine()
    settings = load_settings()

    print("1. Loading site_day from database...")
    df = pd.read_sql_table("site_day", con=engine)
    df["date"] = pd.to_datetime(df["date"]).dt.date
    print(f"Loaded {len(df)} site-day rows.")

    print("2. Computing GLM baselines and Pearson residuals...")
    baseline_df = compute_site_day_baselines(df)

    print("3. Running CUSUM and EWMA anomaly detection...")
    detected_df = apply_anomaly_detection(baseline_df)

    print("4. Extracting fusion features and district peer metrics...")
    feature_df, X_features = extract_fusion_features(detected_df)

    # Train/Test Split: First 2 years (2023-01-01 to 2024-12-31) train, 2025 test
    train_end = pd.to_datetime(settings.dates.train_end_date).date()
    train_mask = feature_df["date"] <= train_end
    test_mask = ~train_mask

    print(f"Training rows: {train_mask.sum()}, Test rows (held out): {test_mask.sum()}")

    # Generate training targets from high environmental + workforce signals
    y_pseudo = (
        (X_features["heat_index_exceed"] > 2.0)
        | (X_features["pm25_exceed"] > 15.0)
        | (X_features["clinic_heat_cusum"] > 2.0)
        | (X_features["clinic_resp_cusum"] > 2.0)
        | (X_features["incident_cusum"] > 1.8)
        | (X_features["district_peer_heat_cusum"] > 1.5)
    ).astype(int).values

    print("5. Fitting L2 Logistic Regression & Isotonic Calibrator on training years...")
    fusion_model = FusionRiskModel()
    fusion_model.fit(X_features[train_mask], y_pseudo[train_mask])
    fusion_model.save(MODEL_SAVE_PATH)
    print(f"Model saved to {MODEL_SAVE_PATH}")

    print("6. Predicting calibrated risk scores and exact contributions across full dataset...")
    calibrated_scores, raw_log_odds, contributions = fusion_model.predict(X_features)

    feature_df["calibrated_score"] = calibrated_scores
    feature_df["raw_log_odds"] = raw_log_odds

    print("7. Generating alerts with persistence, district budget, and playbook mapping...")
    raw_alerts = []
    playbook_rules = load_playbook()

    for sid, s_group in feature_df.groupby("site_id", sort=False):
        s_indices = s_group.index.tolist()
        s_scores = calibrated_scores[s_indices]
        s_contribs = [contributions[idx] for idx in s_indices]

        s_alerts = evaluate_site_alert_stream(s_group, s_scores, s_contribs, settings=settings)
        raw_alerts.extend(s_alerts)

    final_alerts = apply_alert_budget_and_playbook(
        raw_alerts,
        playbook_rules=playbook_rules,
        max_alerts_per_district_per_week=settings.alerting.max_alerts_per_district_per_week,
    )
    print(f"Total alerts generated: {len(final_alerts)} (Watch: {sum(1 for a in final_alerts if a['level']=='Watch')}, Warning: {sum(1 for a in final_alerts if a['level']=='Warning')}, Critical: {sum(1 for a in final_alerts if a['level']=='Critical')})")

    print("8. Storing alerts to database...")
    alert_records = []
    now = datetime.utcnow()
    for a in final_alerts:
        alert_records.append({
            "site_id": a["site_id"],
            "date": a["date"],
            "level": a["level"],
            "score": a["score"],
            "contributions": json.dumps(a["contributions"]),
            "action_id": a.get("action_id", "RULE_DEFAULT"),
            "role": a.get("role", "Site safety officer"),
            "confidence": a.get("confidence", 1.0),
            "created_at": now,
        })

    with engine.begin() as conn:
        conn.exec_driver_sql("DELETE FROM alerts")

    if alert_records:
        pd.DataFrame(alert_records).to_sql("alerts", con=engine, if_exists="append", index=False)

    print("Pipeline completed successfully.")
    return feature_df, fusion_model, final_alerts


if __name__ == "__main__":
    run_model_training_and_scoring()
