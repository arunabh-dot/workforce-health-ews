"""Trends Page: Context for a site or district with EWMA smoother, baseline band, and exceedances."""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from sqlalchemy.orm import Session

from ews.db import get_engine, SiteDay
from ews.config import load_settings
from ews.privacy.policy import PURPOSE_LIMITATION_BANNER, filter_by_role
from ews.models.detect import compute_ewma_series

st.set_page_config(page_title="Surveillance Trends", page_icon="📈", layout="wide")

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
selected_site = st.session_state.get("selected_site", "S01")
selected_district = st.session_state.get("selected_district", "District-1 (North Logistics Port)")

st.title("📈 Contextual Signal Trends & Smoothing")
st.caption(f"Inspection Scope: **{selected_site if role == 'Site safety officer' else selected_district}** | Role: **{role}**")

engine = get_engine()

# Fetch time series for selected site or district
with Session(engine) as session:
    if role == "Site safety officer":
        query = f"SELECT * FROM site_day WHERE site_id = '{selected_site}' ORDER BY date ASC"
    else:
        # District aggregation
        query = f"SELECT * FROM site_day WHERE district = '{selected_district}' ORDER BY date ASC"

    df = pd.read_sql_query(query, con=engine)

if df.empty:
    st.warning("No trend data found.")
    st.stop()

df["date"] = pd.to_datetime(df["date"])

# If district, group by date
if role != "Site safety officer":
    df = df.groupby("date").agg({
        "temp_max_c": "mean",
        "humidity_mean": "mean",
        "heat_index_c": "mean",
        "pm25": "mean",
        "clinic_heat_visits": "sum",
        "incident_count": "sum",
        "absence_rate": "mean",
    }).reset_index()

# Date range filter slider
dates = sorted(df["date"].dt.date.unique())
date_range = st.select_slider(
    "Select Trend Time Horizon:",
    options=dates,
    value=(dates[max(0, len(dates)-180)], dates[-1]),
    format_func=lambda d: d.strftime("%b %Y"),
)

start_dt, end_dt = pd.to_datetime(date_range[0]), pd.to_datetime(date_range[1])
sub_df = df[(df["date"] >= start_dt) & (df["date"] <= end_dt)].sort_values("date").copy()

# Tabs for Different Surveillance Signals
tab_heat, tab_aq, tab_workforce = st.tabs(["🌡️ Heat Stress & Temperature", "💨 Air Quality (PM2.5)", "🏥 Workforce Health & Safety"])

with tab_heat:
    st.subheader("Heat Index & WHO Risk Threshold")
    fig_heat = go.Figure()

    # Observed Heat Index
    fig_heat.add_trace(go.Scatter(
        x=sub_df["date"],
        y=sub_df["heat_index_c"],
        name="Daily Heat Index (°C)",
        line=dict(color="#ff5722", width=1.5),
        opacity=0.6,
    ))

    # EWMA Smoother (lambda = 0.3)
    ewma_hi = compute_ewma_series(sub_df["heat_index_c"].values, lambda_=0.3)
    fig_heat.add_trace(go.Scatter(
        x=sub_df["date"],
        y=ewma_hi,
        name="EWMA Smoother (λ = 0.3)",
        line=dict(color="#b71c1c", width=2.8),
    ))

    # Threshold line 41 C
    fig_heat.add_hline(
        y=41.0,
        line_dash="dash",
        line_color="darkred",
        annotation_text="WHO High-Risk Band (41°C)",
        annotation_position="top left",
    )

    fig_heat.update_layout(
        xaxis_title="Date",
        yaxis_title="Heat Index (°C)",
        height=380,
        margin=dict(l=20, r=20, t=30, b=20),
    )
    st.plotly_chart(fig_heat, use_container_width=True)

with tab_aq:
    st.subheader("Particulate Matter (PM2.5) & EPA Unhealthy Threshold")
    fig_pm = go.Figure()

    fig_pm.add_trace(go.Scatter(
        x=sub_df["date"],
        y=sub_df["pm25"],
        name="Daily PM2.5 (µg/m³)",
        line=dict(color="#9c27b0", width=1.5),
        opacity=0.5,
    ))

    ewma_pm = compute_ewma_series(sub_df["pm25"].values, lambda_=0.3)
    fig_pm.add_trace(go.Scatter(
        x=sub_df["date"],
        y=ewma_pm,
        name="EWMA Smoother (λ = 0.3)",
        line=dict(color="#4a148c", width=2.8),
    ))

    fig_pm.add_hline(
        y=55.5,
        line_dash="dash",
        line_color="purple",
        annotation_text="EPA Unhealthy Level (55.5 µg/m³)",
        annotation_position="top left",
    )

    fig_pm.update_layout(
        xaxis_title="Date",
        yaxis_title="PM2.5 (µg/m³)",
        height=380,
        margin=dict(l=20, r=20, t=30, b=20),
    )
    st.plotly_chart(fig_pm, use_container_width=True)

with tab_workforce:
    st.subheader("Workforce Clinical & Incident Surveillance")
    if role == "District regulator":
        st.warning("⚠️ Site-level clinical visit details are redacted under District Regulator scope in accordance with privacy policy.")
    else:
        fig_wf = go.Figure()
        
        # Clinic visits
        fig_wf.add_trace(go.Bar(
            x=sub_df["date"],
            y=sub_df["clinic_heat_visits"].fillna(0),
            name="Clinic Heat Visits",
            marker_color="#ff9800",
            opacity=0.7,
        ))

        # Incidents
        fig_wf.add_trace(go.Scatter(
            x=sub_df["date"],
            y=sub_df["incident_count"].fillna(0),
            name="Safety Incidents",
            line=dict(color="#e91e63", width=2.0),
            mode="lines+markers",
            yaxis="y2",
        ))

        fig_wf.update_layout(
            xaxis_title="Date",
            yaxis_title="Clinic Visits",
            yaxis2=dict(title="Safety Incidents", overlaying="y", side="right", showgrid=False),
            height=380,
            margin=dict(l=20, r=20, t=30, b=20),
        )
        st.plotly_chart(fig_wf, use_container_width=True)
