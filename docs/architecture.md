# Workforce Health Early Warning System - Technical Architecture

## 1. System Pipeline Overview
The Workforce Health Early Warning System (EWS) operates across four distinct data streams, five processing stages, and three primary user scopes:

```
[ Weather (Real Open-Meteo) ]  [ Air Quality (Real Open-Meteo) ]  [ Clinic Visits (Simulated) ]  [ Incidents/Absence (Simulated) ]
                                                │
                                                ▼
                                   ┌─────────────────────────┐
                                   │      site_day Table     │
                                   │  1 row/site-day, NO PII │
                                   └────────────┬────────────┘
                                                │
                       ┌────────────────────────┴────────────────────────┐
                       ▼                                                 ▼
             ┌───────────────────┐                             ┌───────────────────┐
             │   GLM Baselines   │                             │  Direct Threshold │
             │  NegBin / Poisson │                             │ HI ≥ 41°C / PM2.5 │
             └─────────┬─────────┘                             └─────────┬─────────┘
                       │                                                 │
                       ▼                                                 ▼
             ┌───────────────────┐                             ┌───────────────────┐
             │   Anomaly Detect  │                             │  Exceedance Feats │
             │   CUSUM & EWMA    │                             │  + District Peers │
             └─────────┬─────────┘                             └─────────┬─────────┘
                       │                                                 │
                       └────────────────────────┬────────────────────────┘
                                                │
                                                ▼
                                   ┌─────────────────────────┐
                                   │    Risk Score Fusion    │
                                   │ L2 Logistic + Isotonic  │
                                   │ Faithful Linear Explain │
                                   └────────────┬────────────┘
                                                │
                                                ▼
                                   ┌─────────────────────────┐
                                   │  Anti-Fatigue Alerting  │
                                   │   Persistence Rule (2d) │
                                   │  District Budget (5/wk) │
                                   │    Confidence Scoring   │
                                   └────────────┬────────────┘
                                                │
                                                ▼
                                   ┌─────────────────────────┐
                                   │     Action Playbook     │
                                   │  Rule Engine (playbook) │
                                   │ Role, Action & Evidence │
                                   └────────────┬────────────┘
                                                │
                       ┌────────────────────────┼────────────────────────┐
                       ▼                        ▼                        ▼
             ┌───────────────────┐    ┌───────────────────┐    ┌───────────────────┐
             │Site Safety Officer│    │Occupational Health│    │ District Regulator│
             │   Own site only   │    │District aggregates│    │Critical & summary │
             └───────────────────┘    └───────────────────┘    └───────────────────┘
```

## 2. Core Modules
- **`ews/ingest/weather.py`**: Interacts with Open-Meteo Historical Archive API to pull daily $T_{max}$, $RH_{mean}$, and hourly PM2.5 / PM10. Computes the official NOAA Rothfusz heat index regression in Celsius. Caches data in local Parquet format for offline execution.
- **`ews/sim/generate.py`**: Reproducible pseudo-random generator modeling 30 industrial and port sites in Dubai. Simulates microclimates, headcount dynamics (20–400 workers), baseline Poisson clinic visits and incidents, and injects 14 ground-truth events (heat waves, localised clusters, air quality episodes) with realistic lag curves (Environmental $\to$ Clinic: $+1-2$ days $\to$ Incidents/Absence: $+2-4$ days).
- **`ews/models/baseline.py`**: Per-site Negative Binomial GLMs with log(headcount) offset, day-of-week terms, Fourier harmonics (2 frequencies), and environmental covariates. Standardized Pearson residuals protect against flagging ordinary hot summer days.
- **`ews/models/detect.py`**: One-sided CUSUM ($k=0.5, h=4.0$) on Pearson residuals and EWMA smoother ($\lambda=0.3$).
- **`ews/models/fuse.py`**: Fuses CUSUM metrics, direct environmental exceedances, and district peer means into a calibrated risk probability using regularized logistic regression and isotonic calibration. Per-signal contributions in log-odds ($\beta_j \cdot x_j$) are exact and mathematically faithful to the model score.
- **`ews/models/alerting.py`**: Evaluates alert thresholds (Watch $\ge 0.30$, Warning $\ge 0.55$, Critical $\ge 0.75$), enforces 2-day persistence, respects weekly district budgets (max 5 Warning/Critical), and dynamically calculates confidence penalties (0.7 per missing signal, 0.8 for fallback baseline).
- **`ews/privacy/policy.py`**: Role-based scoping, small-cell suppression ($<5$), complementary suppression to defeat differencing attacks, persistent purpose limitation enforcement, and audit logging.
- **`ews/decision/playbook.py`**: Matches alert level, dominant signal, and confidence score to specific actions and responsible roles.
- **`ews/validation/backtest.py`**: Strictly replays the held-out test year (2025) against `events_truth` without feeding back labels to the detector. Computes lead time, sensitivity, PPV, false alarms, and runs all 6 required experimental sweeps.
