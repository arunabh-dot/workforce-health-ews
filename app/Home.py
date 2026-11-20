"""Workforce Health Early Warning System - Streamlit Web Application Entrypoint."""

import streamlit as st
import pandas as pd
from datetime import date, timedelta
from pathlib import Path

from ews.config import load_settings
from ews.db import get_engine, SiteDay, Alert
from ews.privacy.policy import PURPOSE_LIMITATION_BANNER, VALID_ROLES

st.set_page_config(
    page_title="Workforce Health Early Warning System",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Persistent Purpose Limitation Banner on Every Screen (Hard Privacy Constraint)
st.markdown(
    f"""
    <div style="background-color: #fff3cd; color: #856404; padding: 12px 16px; border-radius: 8px; border-left: 6px solid #ffeeba; margin-bottom: 20px; font-weight: 500;">
        ⚠️ <strong>PURPOSE LIMITATION:</strong> {PURPOSE_LIMITATION_BANNER}
    </div>
    """,
    unsafe_allow_html=True,
)

# Sidebar: Role Selector, Date Slider, and Global Context
st.sidebar.title("🛡️ Surveillance Control")
st.sidebar.markdown("---")

# 1. Role Selection (Demo stand-in for RBAC authentication)
selected_role = st.sidebar.selectbox(
    "User Role (Access Scope):",
    VALID_ROLES,
    index=0,
    help="Changes visible data scope and privacy redaction rules.",
)
st.session_state["role"] = selected_role

# Role Scope Guidance
if selected_role == "Site safety officer":
    st.sidebar.info("Scope: Single Work Site (S01). Access to site-level operational alerts and action playbooks.")
elif selected_role == "Occupational health lead":
    st.sidebar.info("Scope: Assigned District. Aggregated clinic trends and clinical readiness actions.")
elif selected_role == "District regulator":
    st.sidebar.warning("Scope: District Overview. Critical alerts only. Site-level clinic counts redacted.")
else:
    st.sidebar.info("Scope: Data Steward. Signal availability, sensor health, and data quality metrics.")

# Site & District selection based on role
if selected_role == "Site safety officer":
    site_options = [f"S{i:02d}" for i in range(1, 31)]
    selected_site = st.sidebar.selectbox("Active Work Site:", site_options, index=0)
    st.session_state["selected_site"] = selected_site
else:
    st.session_state["selected_site"] = "S01"

district_options = [
    "District-1 (North Logistics Port)",
    "District-2 (South Industrial Hub)",
    "District-3 (Eastern Construction Zone)",
    "District-4 (Western Maritime Terminal)",
    "District-5 (Central Manufacturing District)",
]
selected_district = st.sidebar.selectbox("Active District:", district_options, index=0)
st.session_state["selected_district"] = selected_district

st.sidebar.markdown("---")
st.sidebar.subheader("📅 Timeline Replay (2025 Test Year)")

# Date Slider: Replay 2025 test timeline day by day
min_date = date(2025, 1, 1)
max_date = date(2025, 12, 31)

# Preset scenario bookmarks for quick demo jumping
scenario_bookmark = st.sidebar.selectbox(
    "Jump to Simulated Scenario:",
    [
        "Normal Baseline (Calm Spring Day)",
        "Severe Summer Heat Wave (July 2025)",
        "Industrial Safety Cluster (April 2025)",
        "Hazardous PM2.5 Air Episode (October 2025)",
    ],
    index=1,
)

if scenario_bookmark == "Normal Baseline (Calm Spring Day)":
    default_date = date(2025, 3, 15)
elif scenario_bookmark == "Severe Summer Heat Wave (July 2025)":
    default_date = date(2025, 7, 18)
elif scenario_bookmark == "Industrial Safety Cluster (April 2025)":
    default_date = date(2025, 4, 12)
else:
    default_date = date(2025, 10, 24)

selected_date = st.sidebar.slider(
    "Simulation Date:",
    min_value=min_date,
    max_value=max_date,
    value=default_date,
    format="YYYY-MM-DD",
)
st.session_state["date"] = selected_date

st.sidebar.markdown("---")
# Data Freshness & Open Disclosure Banner
st.sidebar.markdown(
    """
    <div style="font-size: 0.82em; color: #6c757d; line-height: 1.4;">
        <strong>📡 Data Provenance & Honesty:</strong><br/>
        • Weather & PM2.5: Real Open-Meteo Archive<br/>
        • Clinic & Workforce: Seeded Synthetic Simulation<br/>
        • Location: Al-Sharq Industrial Zone (Dubai)<br/>
        • Freshness: Batch recomputed daily
    </div>
    """,
    unsafe_allow_html=True,
)

# Landing Page Content
st.title("🛡️ Workforce Health Early Warning System")
st.subheader("Multi-Signal Surveillance for Heat Stress and Air Quality Risks")

st.markdown(
    """
    Welcome to the **Workforce Health Early Warning System (EWS)** prototype submitted to the **Future Health Digital Innovation Challenge (Nov 2026)**.
    
    This platform continuously fuses four disparate signal streams across **30 outdoor and industrial work sites** to detect impending harm before medical escalation occurs.
    """
)

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Covered Work Sites", "30 Sites", "5 Industrial Districts")
with col2:
    st.metric("Total Workforce", "~5,200", "Outdoor / Logistics")
with col3:
    st.metric("Surveillance Signals", "4 Streams", "Weather, PM2.5, Clinic, Incidents")
with col4:
    st.metric("Backtested Lead Time", "2.0 Days", "Pre-Harm Warning")

st.markdown("---")
st.markdown("### 🗺️ System Navigation")
st.markdown(
    """
    Use the navigation menu in the left sidebar to explore the application:
    - **1_Overview**: Real-time district map, open alert counts by severity, and site status.
    - **2_Alert_Detail**: Faithful explanation bar chart (log-odds), multi-signal time series against GLM baseline, and proportionate role-based actions.
    - **3_Trends**: 3-year contextual trajectories with EWMA smoothers and WHO/EPA exceedance markers.
    - **4_Data_Health**: Sensor availability matrix and interactive **What-If Drop-Signal Toggle** (graceful degradation demo).
    - **5_Validation**: Full backtest report across the held-out test year (lead time, sensitivity, PPV, false alarms, threshold sweep, and economic impact).
    - **6_About_and_Governance**: Architectural blueprint, privacy-by-design policy, and stated limitations.
    """
)
