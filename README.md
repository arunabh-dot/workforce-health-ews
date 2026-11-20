# Workforce Health Early Warning System (EWS)

> **Submission for the Future Health Digital Innovation Challenge (Nov 2026)**  
> **Problem Statement:** Population and Workforce Health Early Warning (under Population Health)  
> **Lead Developer:** @arunabh

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/API-FastAPI-009688.svg)](https://fastapi.tiangolo.com)
[![Streamlit](https://img.shields.io/badge/Dashboard-Streamlit-FF4B4B.svg)](https://streamlit.io)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## 📌 Executive Summary
The **Workforce Health Early Warning System (EWS)** is a multi-signal surveillance platform protecting outdoor and industrial workers (construction, logistics yards, port facilities) from escalating environmental hazards, specifically **extreme heat stress and particulate air pollution (PM2.5)**.

The system continuously fuses:
1. **Real Meteorological Data** (Open-Meteo Archive: Temperature, Humidity, and NOAA Rothfusz Heat Index).
2. **Real Air Quality Telemetry** (Open-Meteo: PM2.5 and PM10).
3. **Simulated Clinical Surveillance** (Onsite first-aid visits for heat exhaustion and respiratory distress).
4. **Simulated Workforce Records** (OSHA safety incidents and sick absenteeism rates).

By detecting early physiological and cluster anomalies, the system raises **explainable alerts with a median lead time of 2.0 days** before safety incident surges occur, recommending proportionate, role-based protective interventions.

---

## 🚀 One-Command Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run end-to-end pipeline (Data Ingest -> Simulation -> Model Fit -> Backtest)
make all

# 3. Launch the Interactive Dashboard
make app
```
The Streamlit interface will open automatically at `http://localhost:8501`.

To launch the FastAPI REST backend:
```bash
make run-api
# OpenAPI Swagger UI will be available at http://localhost:8000/docs
```

---

## 🏗️ Architecture & Pipeline

```
[ Open-Meteo Weather ]    [ Open-Meteo PM2.5 ]    [ Clinic First-Aid ]    [ Safety Incidents ]
          │                         │                      │                      │
          └─────────────────────────┴──────────┬───────────┴──────────────────────┘
                                               │
                                               ▼
                                    ┌─────────────────────┐
                                    │    site_day Table   │
                                    │  No worker-level ID │
                                    └──────────┬──────────┘
                                               │
                                               ▼
                                    ┌─────────────────────┐
                                    │ GLM Baselines &     │
                                    │ CUSUM / EWMA Detect │
                                    └──────────┬──────────┘
                                               │
                                               ▼
                                    ┌─────────────────────┐
                                    │ Logistic Fusion &   │
                                    │ Isotonic Calibrator │
                                    └──────────┬──────────┘
                                               │
                                               ▼
                                    ┌─────────────────────┐
                                    │ Anti-Fatigue Engine │
                                    │ Persistence & Budget│
                                    └──────────┬──────────┘
                                               │
                     ┌─────────────────────────┼─────────────────────────┐
                     ▼                         ▼                         ▼
           ┌───────────────────┐     ┌───────────────────┐     ┌───────────────────┐
           │Site Safety Officer│     │Occupational Health│     │ District Regulator│
           │   Own site only   │     │District aggregates│     │Critical & summary │
           └───────────────────┘     └───────────────────┘     └───────────────────┘
```

---

## 🔒 Privacy-by-Design Technical Safeguards
- **Aggregation Only:** No worker names, employee IDs, or individual health records exist in the database.
- **Small-Cell Suppression ($<5$):** Any cell frequency below 5 is masked to `"<5"` and withheld from exports.
- **Complementary Suppression:** Prevents algebraic differencing attacks by suppressing complementary site cells within district totals.
- **Role-Based Access Control (RBAC):**
  * *Site Safety Officer:* Scoped strictly to single-site operational guidance.
  * *Occupational Health Lead:* District-wide clinical readiness.
  * *District Regulator:* Regional summaries; site-level clinic counts are completely redacted.
- **Purpose Limitation Banner:** Displayed persistently across every screen:  
  `"FOR PREVENTION ONLY. Not for individual employment, performance or disciplinary decisions."`
- **Tamper-Evident Audit Trail:** All queries and exports logged to SQLite `audit_log`.

---

## 🧪 Backtest Validation Highlights (Held-Out Test Year 2025)

| Metric | Brief Requirement | Backtest Result | Status |
| :--- | :---: | :---: | :---: |
| **Median Lead Time** | $\ge 2.0$ days | **2.0 days** | **MET** |
| **Event Sensitivity** | $\ge 80\%$ | **80.0%** | **MET** |
| **Positive Predictive Value (PPV)** | $\ge 60\%$ | **66.7%** | **MET** |
| **False Alarms per Month** | $< 3.0$ / mo | **0.83 / mo** | **MET** |
| **Weekly Alert Load per District** | $\le 5.0$ / wk | **0.42 / wk** | **MET** |
| **Brier Calibration Score** | $< 0.15$ | **0.048** | **CALIBRATED** |

*Full audit report and figures located in `validation/report.md` and `validation/figures/`.*

---

## 🎬 5-Minute Demo Walkthrough Script

Follow these steps for a live demonstration or recording:

1. **Overview on Calm Date (March 15, 2025):**
   - Open the **1_Overview** page.
   - Note that all sites are **Clear** or **Watch**.
   - Point out the data provenance banner: Weather is real (Open-Meteo), workforce signals are simulated.
2. **Replay Into Heat Wave (July 18, 2025):**
   - Select the preset bookmark *"Severe Summer Heat Wave"* on the sidebar date slider.
   - Watch the map transition to amber and red. Heat index crosses 41°C.
   - Notice the first Watch alerts fire before any clinic surge occurs.
3. **Inspect Alert Detail (Site S01):**
   - Navigate to **2_Alert_Detail**.
   - Review the **Faithful Signal Attribution bar chart** (exact log-odds and % share).
   - Inspect the **Action Playbook**: Recommended Action, Responsible Role, and Evidence Basis.
4. **Demonstrate Privacy Scoping (Switch to District Regulator):**
   - Change the role in the sidebar to **District regulator**.
   - Return to **Overview** and **Trends**: Site-level clinic counts are immediately **[REDACTED]**, and small cells display `"<5"`.
   - Point out the persistent Purpose Limitation banner.
5. **Interactive What-If Drop-Signal Stress Test:**
   - Open **4_Data_Health**.
   - Toggle the *"Drop Clinic Health Visits feed"* checkbox and click *"Recompute Early Warning Status"*.
   - Watch the risk score adjust, the confidence badge drop from 100% to 70%, and the system gracefully adapt to an environmental advisory alert rather than crashing.
6. **Validation Proof & Economic Impact:**
   - Open **5_Validation** to review the backtest metrics, threshold sweep curve, and economic impact estimate (~28 heat incidents avoided, ~98 workdays preserved).
7. **Governance & Limitations:**
   - Review **6_About_and_Governance** for the stated limitations, synthetic boundaries, and 3-phase path to pilot.

---

## 📂 Repository Layout
```
workforce-ews/
├── README.md
├── requirements.txt
├── Makefile
├── config/
│   ├── settings.yaml
│   └── playbook.yaml
├── data/
│   ├── raw/
│   └── ews.db
├── ews/
│   ├── ingest/weather.py
│   ├── sim/generate.py
│   ├── models/
│   │   ├── baseline.py
│   │   ├── detect.py
│   │   ├── fuse.py
│   │   └── alerting.py
│   ├── decision/playbook.py
│   ├── privacy/policy.py
│   ├── validation/backtest.py
│   └── db.py
├── api/main.py
├── app/
│   ├── Home.py
│   └── pages/
│       ├── 1_Overview.py
│       ├── 2_Alert_Detail.py
│       ├── 3_Trends.py
│       ├── 4_Data_Health.py
│       ├── 5_Validation.py
│       └── 6_About_and_Governance.py
├── tests/
└── docs/
    ├── architecture.md
    ├── assumptions.md
    └── limitations.md
```
