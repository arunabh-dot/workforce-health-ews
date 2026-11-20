"""About & Governance Page: Data sources, privacy guarantees, stated limitations, and path to pilot."""

import streamlit as st
from ews.privacy.policy import PURPOSE_LIMITATION_BANNER

st.set_page_config(page_title="Governance & Boundaries", page_icon="⚖️", layout="wide")

# Persistent Purpose Limitation Banner
st.markdown(
    f"""
    <div style="background-color: #fff3cd; color: #856404; padding: 10px 14px; border-radius: 6px; border-left: 5px solid #ffeeba; margin-bottom: 16px; font-size: 0.9em;">
        🛡️ <strong>PURPOSE LIMITATION:</strong> {PURPOSE_LIMITATION_BANNER}
    </div>
    """,
    unsafe_allow_html=True,
)

st.title("⚖️ System Architecture, Governance & Limitations")

# Section 1: Data Provenance & Honesty Disclosure
st.subheader("1. Data Provenance & Honesty Disclosure")
st.markdown(
    """
    To preserve scientific and ethical integrity in competition evaluation, this prototype strictly distinguishes between observed and simulated data:
    - **Real Observed Data:**
      * **Meteorology:** Daily maximum temperature, mean relative humidity, and derived Rothfusz heat index obtained from the **Open-Meteo Historical Weather API**.
      * **Air Quality:** Particulate matter (PM2.5 and PM10) obtained from the **Open-Meteo Air Quality API**.
      * **Geospatial Anchor:** Centered on the Al-Sharq Industrial Zone (Dubai, UAE; Lat: 25.20°N, Lon: 55.27°E).
    - **Simulated Synthetic Data:**
      * Workforce clinic visits (heat-related and respiratory complaints), safety incidents, and sick absence rates are generated via an epidemiological simulator with known ground-truth events.
      * **Disclosure:** Workforce signals are simulated. They must **never** be presented as real patient medical records.
    """
)

st.markdown("---")

# Section 2: Privacy-by-Design Architecture
st.subheader("2. Privacy-by-Design Technical Architecture")
st.markdown(
    """
    The platform enforces strict privacy safeguards directly in Python and database schema:
    1. **Aggregation Only:** No worker identifiers, names, badge numbers, or individual timestamps exist anywhere in the pipeline. All data reduces to a unified `site_day` table.
    2. **Small-Cell Suppression (<5):** Any displayed cell with a frequency under 5 is suppressed to `"<5"` and blocked from CSV exports.
    3. **Complementary Suppression:** If a single site within a district has count `<5`, the system automatically suppresses the second-smallest cell in that district group, mathematically blocking algebraic differencing from the district total.
    4. **Role-Based Access Control (RBAC):**
       - *Site Safety Officer:* Scoped strictly to their designated site.
       - *Occupational Health Lead:* District-level clinical trend aggregates.
       - *District Regulator:* Macro district summaries and Critical alerts; site-level clinic counts are completely redacted.
    5. **Purpose Limitation:** Persistent banner displayed on every screen and query. The API explicitly rejects any query keyed to an individual.
    6. **Comprehensive Audit Trail:** All dashboard views and API data fetches are logged to the `audit_log` table with role and timestamp.
    """
)

st.markdown("---")

# Section 3: Limitations Stated Openly
st.subheader("3. Limitations Stated Openly")
st.warning(
    """
    As required by the Future Health Innovation Challenge brief, the following operational boundaries are stated openly:
    - **Synthetic Performance Boundary:** Because workforce signals are simulated, validation metrics describe algorithmic fidelity on synthetic events, not clinical efficacy in real-world human populations.
    - **Assumed Lag Structures:** Real-world biological and administrative delays may deviate from modeled lag curves (environmental: Day 0, clinic: Day 1-2, incidents: Day 2-4).
    - **Demo Authentication Stand-In:** The role selector in the sidebar serves as a demonstration stand-in for enterprise OAuth2/OIDC single sign-on.
    - **Preliminary Disclosure-Risk Protection:** Small-cell and complementary suppression represent baseline controls; a full production rollout requires formal differential privacy or disclosure review.
    - **Advisory Decision Support:** The system provides preventative operational guidance and **does not diagnose clinical medical illness**.
    """
)

st.markdown("---")

# Section 4: Path to Production Pilot
st.subheader("4. Path to Production Pilot")
st.markdown(
    """
    Transitioning this prototype to an active municipal or corporate deployment:
    1. **Phase 1 (Shadow Operation - 1 Hot Season):**
       Connect real site attendance and aggregated clinic logs from one participating industrial contractor. Run models in shadow mode (alerts logged and timestamped without triggering operational stoppages).
    2. **Phase 2 (Concordance Verification):**
       At season end, audit shadow alerts against recorded Occupational Health and Safety (OHS) incident logs to calibrate site-specific sensitivity and false alarm rates.
    3. **Phase 3 (Role-Based Pilot):**
       Equip Site Safety Officers with automated mobile playbooks, evaluating early hydration and rest intervention compliance.
    """
)
