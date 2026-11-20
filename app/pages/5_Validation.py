"""Validation Page: Comprehensive backtest report, operating curve, calibration, and impact estimate."""

from pathlib import Path
import streamlit as st
import pandas as pd
from PIL import Image

from ews.privacy.policy import PURPOSE_LIMITATION_BANNER

st.set_page_config(page_title="Operational Validation", page_icon="🧪", layout="wide")

# Persistent Purpose Limitation Banner
st.markdown(
    f"""
    <div style="background-color: #fff3cd; color: #856404; padding: 10px 14px; border-radius: 6px; border-left: 5px solid #ffeeba; margin-bottom: 16px; font-size: 0.9em;">
        🛡️ <strong>PURPOSE LIMITATION:</strong> {PURPOSE_LIMITATION_BANNER}
    </div>
    """,
    unsafe_allow_html=True,
)

st.title("🧪 Operational Validation & Backtest Evidence")
st.markdown(
    """
    Validation conducted strictly on the **held-out test year (Jan 1, 2025 to Dec 31, 2025)**.
    The detector never observed ground-truth event labels, and all hyperparameters were **strictly frozen before test evaluation**.
    """
)

# Load generated validation markdown report
report_path = Path(__file__).resolve().parent.parent.parent / "validation" / "report.md"

if not report_path.exists():
    st.info("Validation report is currently compiling. Please refresh in a moment...")
else:
    with open(report_path, "r", encoding="utf-8") as f:
        report_content = f.read()

    # Visual Evidence: Key Plots
    st.subheader("📊 Visual Diagnostic Proof")
    col1, col2, col3 = st.columns(3)

    fig_lag = Path(__file__).resolve().parent.parent.parent / "validation" / "figures" / "lag_structure.png"
    fig_sweep = Path(__file__).resolve().parent.parent.parent / "validation" / "figures" / "threshold_sweep.png"
    fig_cal = Path(__file__).resolve().parent.parent.parent / "validation" / "figures" / "reliability_curve.png"

    with col1:
        st.markdown("**1. Signal Lag Structure (Lead Time)**")
        if fig_lag.exists():
            st.image(str(fig_lag), caption="Environmental Spike -> Clinic Lags 1-2d -> Harm Lags 2-4d")
        else:
            st.caption("Figure compiling...")

    with col2:
        st.markdown("**2. Alert-Fatigue Operating Curve**")
        if fig_sweep.exists():
            st.image(str(fig_sweep), caption="Sensitivity vs False Alarms / Month Sweep")
        else:
            st.caption("Figure compiling...")

    with col3:
        st.markdown("**3. Probability Reliability Diagram**")
        if fig_cal.exists():
            st.image(str(fig_cal), caption="Calibrated Risk vs Empirical Event Frequency")
        else:
            st.caption("Figure compiling...")

    st.markdown("---")
    st.subheader("📑 Full Audit Validation Report")
    st.markdown(report_content)
