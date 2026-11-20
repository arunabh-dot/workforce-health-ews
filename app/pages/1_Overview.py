"""Overview Page: One-glance geographical and operational status for selected role and date."""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from sqlalchemy.orm import Session

from ews.db import get_engine, SiteDay, Alert
from ews.privacy.policy import (
    PURPOSE_LIMITATION_BANNER,
    filter_by_role,
    apply_small_cell_and_complementary_suppression,
)

st.set_page_config(page_title="Operational Overview", page_icon="🗺️", layout="wide")

# Persistent Purpose Limitation Banner
st.markdown(
    f"""
    <div style="background-color: #fff3cd; color: #856404; padding: 10px 14px; border-radius: 6px; border-left: 5px solid #ffeeba; margin-bottom: 16px; font-size: 0.9em;">
        🛡️ <strong>PURPOSE LIMITATION:</strong> {PURPOSE_LIMITATION_BANNER}
    </div>
    """,
    unsafe_allow_html=True,
)

# Retrieve global state
role = st.session_state.get("role", "Site safety officer")
cur_date = st.session_state.get("date", pd.to_datetime("2025-07-18").date())
selected_site = st.session_state.get("selected_site", "S01")
selected_district = st.session_state.get("selected_district", "District-1 (North Logistics Port)")

st.title("🗺️ District Surveillance Overview")
st.caption(f"Active Role: **{role}** | Timeline Date: **{cur_date}**")

engine = get_engine()

# Load site_day records for today
with Session(engine) as session:
    site_records = (
        session.query(SiteDay)
        .filter(SiteDay.date == cur_date)
        .all()
    )

    alert_records = (
        session.query(Alert)
        .filter(Alert.date == cur_date)
        .all()
    )

if not site_records:
    st.warning(f"No records available for date {cur_date}.")
    st.stop()

# Convert to DataFrame
sites_df = pd.DataFrame([
    {
        "site_id": s.site_id,
        "district": s.district,
        "headcount": s.headcount,
        "lat": s.lat,
        "lon": s.lon,
        "temp_max_c": s.temp_max_c,
        "humidity_mean": s.humidity_mean,
        "heat_index_c": s.heat_index_c,
        "pm25": s.pm25,
        "clinic_heat_visits": s.clinic_heat_visits,
        "incident_count": s.incident_count,
    }
    for s in site_records
])

alerts_map = {a.site_id: a for a in alert_records}

# Assign alert level and score to sites
site_levels = []
site_scores = []
site_confidences = []
site_actions = []

for sid in sites_df["site_id"]:
    if sid in alerts_map:
        alt = alerts_map[sid]
        site_levels.append(alt.level)
        site_scores.append(round(alt.score, 3))
        site_confidences.append(round(alt.confidence, 2))
        site_actions.append(alt.action_id)
    else:
        site_levels.append("Clear")
        site_scores.append(0.0)
        site_confidences.append(1.0)
        site_actions.append("None")

sites_df["alert_level"] = site_levels
sites_df["risk_score"] = site_scores
sites_df["confidence"] = site_confidences
sites_df["action_id"] = site_actions

# Role-based filtering of the overview dataset
filtered_sites_df = filter_by_role(
    sites_df,
    role=role,
    user_site_id=selected_site if role == "Site safety officer" else None,
    user_district=selected_district if role == "Occupational health lead" else None,
)

# Metric KPIs
watch_count = sum(1 for lvl in filtered_sites_df["alert_level"] if lvl == "Watch")
warn_count = sum(1 for lvl in filtered_sites_df["alert_level"] if lvl == "Warning")
crit_count = sum(1 for lvl in filtered_sites_df["alert_level"] if lvl == "Critical")
clear_count = sum(1 for lvl in filtered_sites_df["alert_level"] if lvl == "Clear")

kpi1, kpi2, kpi3, kpi4, kpi5 = st.columns(5)
with kpi1:
    st.metric("Sites in Scope", len(filtered_sites_df))
with kpi2:
    st.metric("🟢 Clear", clear_count)
with kpi3:
    st.metric("🟡 Watch Alerts", watch_count)
with kpi4:
    st.metric("🟠 Warning Alerts", warn_count)
with kpi5:
    st.metric("🔴 Critical Alerts", crit_count)

st.markdown("---")

# Map View & Alert Table
col_map, col_details = st.columns([3, 2])

# Color mapping pairing colors with explicit text and icons
color_discrete_map = {
    "Clear": "#28a745",
    "Watch": "#ffc107",
    "Warning": "#fd7e14",
    "Critical": "#dc3545",
}

with col_map:
    st.subheader("📍 Geospatial Risk Map")
    
    # Plotly Scatter Mapbox / Scattergeo
    fig = px.scatter_mapbox(
        filtered_sites_df,
        lat="lat",
        lon="lon",
        color="alert_level",
        color_discrete_map=color_discrete_map,
        size="headcount",
        size_max=18,
        hover_name="site_id",
        hover_data={
            "district": True,
            "alert_level": True,
            "risk_score": True,
            "confidence": True,
            "heat_index_c": ":.1f",
            "lat": False,
            "lon": False,
        },
        zoom=10,
        center={"lat": 25.15, "lon": 55.28},
        mapbox_style="carto-positron",
        title=f"Site Alert Status ({cur_date})",
    )
    fig.update_layout(margin={"r": 0, "t": 40, "l": 0, "b": 0}, height=480)
    st.plotly_chart(fig, use_container_width=True)

with col_details:
    st.subheader("🚨 Active Alerts in Scope")
    active_alerts = filtered_sites_df[filtered_sites_df["alert_level"] != "Clear"].sort_values("risk_score", ascending=False)
    
    if active_alerts.empty:
        st.success("✅ No elevated alerts in active scope. All conditions within normal operating baselines.")
    else:
        for _, alt_row in active_alerts.iterrows():
            lvl = alt_row["alert_level"]
            sid = alt_row["site_id"]
            score = alt_row["risk_score"]
            conf = alt_row["confidence"]
            
            # Confidence badge formatting
            conf_badge = f"🟢 High ({conf})" if conf >= 0.8 else (f"🟡 Mod ({conf})" if conf >= 0.5 else f"🔴 Low ({conf})")
            
            color_border = "#dc3545" if lvl == "Critical" else ("#fd7e14" if lvl == "Warning" else "#ffc107")
            
            with st.container():
                st.markdown(
                    f"""
                    <div style="border-left: 5px solid {color_border}; padding: 10px 14px; background: #fafafa; border-radius: 4px; margin-bottom: 10px;">
                        <strong>Site {sid}</strong> — <span style="color: {color_border}; font-weight:bold;">{lvl.upper()}</span><br/>
                        <span style="font-size:0.88em; color: #555;">Calibrated Risk: <strong>{score:.1%}</strong> | Confidence: <strong>{conf_badge}</strong></span><br/>
                        <span style="font-size:0.85em; color: #777;">Heat Index: {alt_row['heat_index_c']}°C | PM2.5: {alt_row['pm25']} µg/m³</span>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

st.markdown("---")
st.subheader("📋 Tabular Site Surveillance Feed (Privacy-Preserved)")

# Apply small cell suppression before displaying table
display_cols = ["site_id", "district", "headcount", "heat_index_c", "pm25", "clinic_heat_visits", "incident_count", "alert_level", "risk_score", "confidence"]
suppressed_table = apply_small_cell_and_complementary_suppression(
    filtered_sites_df[display_cols],
    count_columns=["clinic_heat_visits", "incident_count"],
    group_col="district",
)

st.dataframe(
    suppressed_table.rename(
        columns={
            "clinic_heat_visits": "Clinic Heat Visits (<5 Suppressed)",
            "incident_count": "Incidents (<5 Suppressed)",
            "heat_index_c": "Heat Index (°C)",
            "pm25": "PM2.5 (µg/m³)",
            "risk_score": "Calibrated Risk",
        }
    ),
    use_container_width=True,
    hide_index=True,
)
