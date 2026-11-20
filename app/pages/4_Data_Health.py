"""Data Health Page: Signal availability grid and interactive What-If Drop-Signal simulator."""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from sqlalchemy.orm import Session

from ews.db import get_engine, SiteDay
from ews.privacy.policy import PURPOSE_LIMITATION_BANNER
from ews.models.fuse import FusionRiskModel, extract_fusion_features
from ews.models.baseline import compute_site_day_baselines
from ews.models.detect import apply_anomaly_detection
from ews.models.alerting import calculate_confidence, match_playbook_rule
from ews.config import load_playbook

st.set_page_config(page_title="Data Health & Missing-Input Resilience", page_icon="📡", layout="wide")

# Persistent Purpose Limitation Banner
st.markdown(
    f"""
    <div style="background-color: #fff3cd; color: #856404; padding: 10px 14px; border-radius: 6px; border-left: 5px solid #ffeeba; margin-bottom: 16px; font-size: 0.9em;">
        🛡️ <strong>PURPOSE LIMITATION:</strong> {PURPOSE_LIMITATION_BANNER}
    </div>
    """,
    unsafe_allow_html=True,
)

cur_date = st.session_state.get("date", pd.to_datetime("2025-07-18").date())
selected_site = st.session_state.get("selected_site", "S01")

st.title("📡 Data Feed Health & Graceful Degradation")
st.markdown(
    """
    Early warning systems in high-risk industrial environments must maintain **graceful operational resilience**.
    When data feeds suffer sensor dropout or telecommunication lag, the system must **never crash or leave workers unprotected**.
    Instead, it transparently downscales confidence and issues advisory alerts on available environmental evidence.
    """
)

# -------------------------------------------------------------
# FEATURE HIGHLIGHT: The Interactive What-If Drop-Signal Simulator
# -------------------------------------------------------------
st.markdown("---")
st.markdown(
    """
    <div style="background: linear-gradient(135deg, #e3f2fd, #bbdefb); border: 2px solid #2196f3; padding: 16px 20px; border-radius: 10px; margin-bottom: 24px;">
        <h3 style="margin: 0 0 8px 0; color: #0d47a1;">⚡ Interactive Stress Test: What-If Drop-Signal Simulator</h3>
        <p style="margin: 0; color: #1565c0; font-size: 0.95em;">
            <strong>Demonstration Moment:</strong> Actively sever data feeds for <strong>Site {selected_site}</strong> on <strong>{cur_date}</strong>. 
            Watch the risk score dynamically recalculate and the confidence badge penalize down, triggering the automated Data Steward playbook rule.
        </p>
    </div>
    """.format(selected_site=selected_site, cur_date=cur_date),
    unsafe_allow_html=True,
)

col_ctrl, col_out = st.columns([2, 3])

with col_ctrl:
    st.markdown("##### 🎛️ Simulate Feed Dropouts")
    drop_weather = st.checkbox("Drop Weather / Ambient Temp feed", value=False)
    drop_pm25 = st.checkbox("Drop PM2.5 Air Quality sensor", value=False)
    drop_clinic = st.checkbox("Drop Clinic Health Visits feed", value=False, help="Simulates clinic offline reporting")
    drop_incidents = st.checkbox("Drop Safety Incident log", value=False)
    drop_all_wf = st.checkbox("Drop ALL Workforce Feeds at once", value=False)

    if drop_all_wf:
        drop_clinic = True
        drop_incidents = True

    stress_test_btn = st.button("🚀 Recompute Early Warning Status", type="primary")

engine = get_engine()

# Fetch baseline recent window for selected site
target_dt = cur_date
start_dt = target_dt - pd.Timedelta(days=12)

with Session(engine) as session:
    df_window = pd.read_sql_query(
        f"SELECT * FROM site_day WHERE site_id = '{selected_site}' AND date >= '{start_dt}' AND date <= '{target_dt}' ORDER BY date ASC",
        con=engine,
    )

if df_window.empty:
    st.error("No historical data available for selected site window.")
    st.stop()

# 1. Baseline Evaluation (All available)
fusion_model = FusionRiskModel.load()
playbook_rules = load_playbook()

base_df = compute_site_day_baselines(df_window)
det_df = apply_anomaly_detection(base_df)
_, X_orig = extract_fusion_features(det_df)
probs_orig, _, contribs_orig = fusion_model.predict(X_orig)

orig_score = float(probs_orig[-1])
orig_contrib = contribs_orig[-1]
orig_level = "Warning" if orig_score >= 0.55 else ("Watch" if orig_score >= 0.30 else "Clear")
orig_conf = 1.0

# 2. Modified Simulation
mod_df = df_window.copy()
dropped_count = 0

if drop_weather:
    mod_df["temp_max_c"] = np.nan
    mod_df["heat_index_c"] = np.nan
    mod_df["signal_available_weather"] = False
    dropped_count += 1

if drop_pm25:
    mod_df["pm25"] = np.nan
    mod_df["signal_available_pm25"] = False
    dropped_count += 1

if drop_clinic:
    mod_df["clinic_heat_visits"] = np.nan
    mod_df["clinic_resp_visits"] = np.nan
    mod_df["signal_available_clinic_heat"] = False
    mod_df["signal_available_clinic_resp"] = False
    dropped_count += 1

if drop_incidents:
    mod_df["incident_count"] = np.nan
    mod_df["signal_available_incidents"] = False
    dropped_count += 1

# Recompute
base_mod = compute_site_day_baselines(mod_df)
det_mod = apply_anomaly_detection(base_mod)
_, X_mod = extract_fusion_features(det_mod)
probs_mod, _, contribs_mod = fusion_model.predict(X_mod)

mod_score = float(probs_mod[-1])
mod_contrib = contribs_mod[-1]
mod_conf = calculate_confidence(missing_signal_count=dropped_count, is_district_fallback=False)
mod_level = "Warning" if mod_score >= 0.55 else ("Watch" if mod_score >= 0.30 else "Clear")

action_info = match_playbook_rule(
    mod_level,
    mod_contrib.get("dominant_signal", "environment"),
    mod_conf,
    playbook_rules,
)

with col_out:
    st.markdown("##### 🔬 Comparative Stress-Test Result")
    
    rcol1, rcol2 = st.columns(2)
    with rcol1:
        st.markdown(
            f"""
            <div style="background: white; border: 1px solid #ddd; padding: 12px; border-radius: 8px;">
                <h5 style="margin:0 0 6px 0; color: #555;">Original Baseline State</h5>
                <p style="margin: 2px 0;">Level: <strong>{orig_level}</strong></p>
                <p style="margin: 2px 0;">Risk Score: <strong>{orig_score:.1%}</strong></p>
                <p style="margin: 2px 0;">Confidence: <span style="color: green; font-weight:bold;">100% (High)</span></p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with rcol2:
        conf_style = "green" if mod_conf >= 0.8 else ("orange" if mod_conf >= 0.5 else "red")
        st.markdown(
            f"""
            <div style="background: #fdfefe; border: 2px solid #2196f3; padding: 12px; border-radius: 8px;">
                <h5 style="margin:0 0 6px 0; color: #0d47a1;">Stress-Tested State</h5>
                <p style="margin: 2px 0;">Level: <strong>{mod_level}</strong></p>
                <p style="margin: 2px 0;">Risk Score: <strong>{mod_score:.1%}</strong></p>
                <p style="margin: 2px 0;">Confidence: <span style="color: {conf_style}; font-weight:bold;">{mod_conf:.0%} ({action_info.get('role')})</span></p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("##### 📋 Triggered Action Protocol")
    st.info(f"**Recommended Action:** {action_info.get('action')}")
    st.caption(f"**Responsible Role:** {action_info.get('role')} &nbsp;|&nbsp; **Evidence:** {action_info.get('evidence_shown', action_info.get('evidence'))}")

# -------------------------------------------------------------
# Signal Availability Matrix by Site and Day
# -------------------------------------------------------------
st.markdown("---")
st.subheader("📊 Signal Availability Matrix across All 30 Sites")
st.caption(f"Status snapshot on {cur_date}. Green = Feed Active, Red = Outage Gap.")

with Session(engine) as session:
    all_sites_today = (
        session.query(SiteDay)
        .filter(SiteDay.date == cur_date)
        .order_by(SiteDay.site_id.asc())
        .all()
    )

if all_sites_today:
    grid_data = []
    for s in all_sites_today:
        grid_data.append({
            "Site": s.site_id,
            "District": s.district.split(" ")[0],
            "Weather Feed": "🟢 OK" if s.signal_available_weather else "🔴 Missing",
            "PM2.5 Sensor": "🟢 OK" if s.signal_available_pm25 else "🔴 Missing",
            "Clinic Heat Visits": "🟢 OK" if s.signal_available_clinic_heat else "🔴 Missing",
            "Clinic Resp Visits": "🟢 OK" if s.signal_available_clinic_resp else "🔴 Missing",
            "Incident Reports": "🟢 OK" if s.signal_available_incidents else "🔴 Missing",
            "Absence Records": "🟢 OK" if s.signal_available_absence else "🔴 Missing",
            "Status": "⚠️ Persistent Gaps" if s.site_id == "S13" else "Normal",
        })

    grid_df = pd.DataFrame(grid_data)
    st.dataframe(grid_df, use_container_width=True, hide_index=True)

    st.markdown(
        """
        > **Note on Persistent Bad-Data Site (S13):** As specified in Section 4, Site S13 has an intentional high rate of sensor dropouts and missing telemetry (~35% outage rate) to continuously test the system's resilience to bad instrumentation.
        """
    )
