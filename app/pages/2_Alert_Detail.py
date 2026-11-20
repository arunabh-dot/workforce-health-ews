"""Alert Detail Page: Explain one alert, show exact log-odds contributions, time series vs baseline, and recommended actions."""

import json
from datetime import date, timedelta
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from sqlalchemy.orm import Session

from ews.db import get_engine, Alert, SiteDay
from ews.config import load_settings, load_playbook
from ews.privacy.policy import (
    PURPOSE_LIMITATION_BANNER,
    filter_by_role,
    suppress_small_cell,
)
from ews.models.alerting import match_playbook_rule

st.set_page_config(page_title="Alert Detail & Action Playbook", page_icon="🚨", layout="wide")

# Persistent Purpose Limitation Banner
st.markdown(
    f"""
    <div style="background-color: #fff3cd; color: #856404; padding: 10px 14px; border-radius: 6px; border-left: 5px solid #ffeeba; margin-bottom: 16px; font-size: 0.9em;">
        🛡️ <strong>PURPOSE LIMITATION:</strong> {PURPOSE_LIMITATION_BANNER}
    </div>
    """,
    unsafe_allow_html=True,
)

role = st.session_state.get("role", "Site safety officer")
cur_date = st.session_state.get("date", pd.to_datetime("2025-07-18").date())
selected_site = st.session_state.get("selected_site", "S01")

st.title("🚨 Explainable Alert Drill-Down & Decision Support")

engine = get_engine()

# Fetch active alerts for date or recent dates
with Session(engine) as session:
    alerts_query = session.query(Alert).filter(Alert.date <= cur_date).order_by(Alert.date.desc(), Alert.score.desc()).limit(100).all()

if not alerts_query:
    st.info("No active alerts found in the system.")
    st.stop()

# Convert alerts to DataFrame
alert_dicts = []
for a in alerts_query:
    contrib = a.get_contributions()
    alert_dicts.append({
        "id": a.id,
        "site_id": a.site_id,
        "date": a.date,
        "level": a.level,
        "score": a.score,
        "confidence": a.confidence,
        "action_id": a.action_id,
        "role": a.role,
        "dominant_signal": contrib.get("dominant_signal", "environment"),
        "raw_alert": a,
    })

alerts_df = pd.DataFrame(alert_dicts)

# Role filter
filtered_alerts_df = filter_by_role(
    alerts_df,
    role=role,
    user_site_id=selected_site if role == "Site safety officer" else None,
)

if filtered_alerts_df.empty:
    st.warning(f"No alerts matching role scope '{role}' on or before {cur_date}.")
    st.stop()

# Alert Selector
alert_options = [
    f"Alert #{r['id']} | Site {r['site_id']} | {r['date']} | {r['level'].upper()} (Risk: {r['score']:.1%})"
    for _, r in filtered_alerts_df.iterrows()
]
selected_alert_str = st.selectbox("Select an Alert to Inspect:", alert_options, index=0)
selected_alert_id = int(selected_alert_str.split("#")[1].split(" ")[0])

selected_row = filtered_alerts_df[filtered_alerts_df["id"] == selected_alert_id].iloc[0]
raw_alert = selected_row["raw_alert"]
contrib = raw_alert.get_contributions()

playbook_rules = load_playbook()
action_info = match_playbook_rule(
    raw_alert.level,
    contrib.get("dominant_signal", "environment"),
    raw_alert.confidence,
    playbook_rules,
)

# Top Card: Alert Summary & Confidence Badge
lvl = raw_alert.level
badge_color = "#dc3545" if lvl == "Critical" else ("#fd7e14" if lvl == "Warning" else "#ffc107")
conf_val = raw_alert.confidence
conf_badge = f"🟢 High Confidence ({conf_val})" if conf_val >= 0.8 else (f"🟡 Moderate ({conf_val})" if conf_val >= 0.5 else f"🔴 Low ({conf_val})")

st.markdown(
    f"""
    <div style="background: white; border: 1px solid #ddd; border-left: 7px solid {badge_color}; border-radius: 8px; padding: 18px; margin-bottom: 20px;">
        <div style="display: flex; justify-content: space-between; align-items: center;">
            <h3 style="margin: 0; color: #222;">Site {raw_alert.site_id} — <span style="color: {badge_color};">{lvl.upper()} ALERT</span></h3>
            <span style="font-size: 1.05em; font-weight: bold; background: #f0f0f0; padding: 4px 12px; border-radius: 12px;">{conf_badge}</span>
        </div>
        <p style="margin: 8px 0 0 0; color: #555; font-size: 0.95em;">
            <strong>Event Date:</strong> {raw_alert.date} &nbsp;|&nbsp; 
            <strong>Calibrated Risk Probability:</strong> <span style="font-size: 1.1em; font-weight: bold; color: {badge_color};">{raw_alert.score:.1%}</span> &nbsp;|&nbsp;
            <strong>Dominant Driver:</strong> <span style="text-transform: capitalize;">{contrib.get('dominant_signal', 'environment')}</span>
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)

# Action Playbook Recommendation Section (Section 6)
st.subheader("🎯 Actionable Decision Support (Rule-Based Playbook)")
act_col1, act_col2, act_col3 = st.columns(3)

with act_col1:
    st.markdown("##### 📌 Recommended Action")
    st.info(f"**{action_info.get('action')}**")

with act_col2:
    st.markdown("##### 👤 Responsible Role")
    st.success(f"**{action_info.get('role')}**")

with act_col3:
    st.markdown("##### 🔍 Evidence Basis")
    st.warning(f"**{action_info.get('evidence_shown', action_info.get('evidence'))}**")

st.markdown("---")

# Explainability: Faithful Contribution Breakdown (Section 5)
st.subheader("📊 Faithful Signal Attribution (Log-Odds & Percentage Share)")
st.caption("Exact linear decomposition: each contribution equals the fitted regularized coefficient multiplied by the observed feature value.")

col_bar, col_table = st.columns([3, 2])

grouped_pcts = contrib.get("grouped_pct", {})
grouped_logodds = contrib.get("grouped_log_odds", {})

# Prepare chart data
cat_labels = ["Environmental Heat", "PM2.5 Air Quality", "Clinic Visits", "Safety Incidents"]
cat_keys = ["environment", "pm25", "clinic", "incidents"]
pct_values = [grouped_pcts.get(k, 0.0) for k in cat_keys]
logodds_values = [grouped_logodds.get(k, 0.0) for k in cat_keys]

with col_bar:
    fig_bar = go.Figure()
    fig_bar.add_trace(go.Bar(
        x=cat_labels,
        y=pct_values,
        text=[f"{p:.1f}%" for p in pct_values],
        textposition="outside",
        marker_color=["#ff7f0e", "#9467bd", "#d62728", "#1f77b4"],
    ))
    fig_bar.update_layout(
        title="Signal Contribution Share (% of Positive Log-Odds)",
        yaxis_title="Contribution (%)",
        yaxis=dict(range=[0, max(pct_values + [20]) * 1.25]),
        height=320,
        margin=dict(l=20, r=20, t=40, b=20),
    )
    st.plotly_chart(fig_bar, use_container_width=True)

with col_table:
    contrib_df = pd.DataFrame({
        "Signal Category": cat_labels,
        "Log-Odds Impact (β·x)": [f"{lo:+.3f}" for lo in logodds_values],
        "Contribution Share": [f"{p:.1f}%" for p in pct_values],
    })
    st.dataframe(contrib_df, use_container_width=True, hide_index=True)
    st.markdown(
        f"""
        <div style="font-size: 0.85em; color: #555; background: #f8f9fa; padding: 8px 12px; border-radius: 4px;">
            <strong>Intercept:</strong> {contrib.get('intercept', 0.0):+.3f} &nbsp;|&nbsp; 
            <strong>Total Linear Score:</strong> {contrib.get('total_log_odds', 0.0):+.3f} log-odds<br/>
            <em>Rule Check: Workforce signal share = {(grouped_pcts.get('clinic', 0) + grouped_pcts.get('incidents', 0)):.1f}% (Critical threshold requires ≥25%)</em>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.markdown("---")

# Signal Time Series Against GLM Baseline
st.subheader(f"📈 Signal Trajectory vs GLM Baseline (Site {raw_alert.site_id})")
st.caption("Time window: 14 days preceding through 7 days following the alert date.")

start_window = raw_alert.date - timedelta(days=14)
end_window = raw_alert.date + timedelta(days=7)

with Session(engine) as session:
    ts_rows = (
        session.query(SiteDay)
        .filter(SiteDay.site_id == raw_alert.site_id, SiteDay.date >= start_window, SiteDay.date <= end_window)
        .order_by(SiteDay.date.asc())
        .all()
    )

if ts_rows:
    ts_df = pd.DataFrame([
        {
            "date": r.date,
            "heat_index_c": r.heat_index_c,
            "pm25": r.pm25,
            "clinic_heat_visits": r.clinic_heat_visits,
            "incident_count": r.incident_count,
        }
        for r in ts_rows
    ])

    fig_ts = go.Figure()
    
    # Heat Index line
    fig_ts.add_trace(go.Scatter(
        x=ts_df["date"],
        y=ts_df["heat_index_c"],
        name="Heat Index (°C)",
        line=dict(color="red", width=2.5),
        mode="lines+markers",
    ))
    
    # 41 C threshold line
    fig_ts.add_trace(go.Scatter(
        x=ts_df["date"],
        y=[41.0] * len(ts_df),
        name="WHO High-Risk Band (41°C)",
        line=dict(color="darkred", width=1.5, dash="dash"),
    ))

    # Clinic visits bar
    # Check if role can see clinic counts
    if role != "District regulator":
        fig_ts.add_trace(go.Bar(
            x=ts_df["date"],
            y=ts_df["clinic_heat_visits"].fillna(0),
            name="Clinic Heat Visits",
            marker_color="orange",
            opacity=0.6,
            yaxis="y2",
        ))

    # Shaded alert window
    fig_ts.add_vrect(
        x0=raw_alert.date - timedelta(days=1),
        x1=raw_alert.date + timedelta(days=1),
        fillcolor="rgba(255, 0, 0, 0.12)",
        layer="below",
        line_width=1,
        line_color="red",
        annotation_text="Alert Active Window",
        annotation_position="top left",
    )

    fig_ts.update_layout(
        title=f"Multi-Signal Dynamics: Site {raw_alert.site_id}",
        xaxis_title="Date",
        yaxis=dict(title="Heat Index (°C)", side="left"),
        yaxis2=dict(title="Clinic Visits (Daily Count)", side="right", overlaying="y", showgrid=False),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        height=400,
        margin=dict(l=20, r=20, t=50, b=20),
    )
    st.plotly_chart(fig_ts, use_container_width=True)
else:
    st.info("Timeseries data unavailable for this window.")

# Assumptions Card
st.markdown("---")
st.markdown("##### 📖 Model Assumptions & Governance Card")
st.markdown(
    """
    - **Baseline Model:** Negative Binomial GLM trained on a 365-day rolling window excluding preceding 14 days.
    - **Fusion Formulation:** L2-regularized logistic regression calibrated via non-parametric isotonic regression.
    - **Persistence Requirement:** Alerts require sustained 2-day elevation to prevent single-day false alarms.
    - **Workforce Signal Disclosure:** Simulated based on industrial epidemiology parameters; not real worker EHR records.
    """
)
