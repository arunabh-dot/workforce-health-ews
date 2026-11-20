# System Limitations Stated Openly

In adherence to the **Future Health Digital Innovation Challenge** evaluation criteria, all technical, epidemiological, and deployment boundaries are stated openly below:

## 1. Synthetic Workforce Data Boundary
- **Simulated Performance:** The workforce signals (clinic heat visits, respiratory complaints, safety incidents, and sick absence) are generated using a seeded epidemiological simulation. Consequently, metrics such as 80%+ sensitivity and 2.0-day lead time demonstrate the algorithmic behavior on synthetic injected anomalies, not proven clinical efficacy in human workforces.
- **Parametric Lag Assumptions:** The simulation hard-codes an assumed cascade ($t=0$ environment $\to$ $t=+1-2$ clinic visits $\to$ $t=+2-4$ injuries). In actual municipal deployments, behavioural adaptations (spontaneous slowdowns, hydration adjustments) may warp or truncate these delays.

## 2. Privacy & Disclosure Controls
- **Baseline Cell Suppression:** The current suppression rules ($<5$ and secondary cell suppression) protect against direct algebraic differencing in standard aggregations. A production system handling protected health information (PHI) requires a formal disclosure-risk assessment and formal differential privacy guarantees.
- **Demo RBAC Authentication:** The sidebar role selector demonstrates role-based views and redaction (e.g. hiding site-level clinic counts from regulators). Production deployment requires enterprise single sign-on (OAuth2 / OIDC) with cryptographic session tokens.

## 3. Threshold Calibration & Climate Transferability
- **Regional Specialization:** Environmental trigger bands (Heat Index $\ge 41^\circ\text{C}$, PM2.5 $\ge 55.5\,\mu\text{g/m}^3$) reflect hot arid desert climates (Dubai / Gulf region). Deploying the system to humid subtropical or temperate zones requires re-calibrating baseline comfort thresholds using local meteorological guidelines.
- **Advisory Decision Support:** Alerts and playbook recommendations are operational tools for Site Safety Officers and Occupational Health Leads. The system does not deliver diagnostic medicine or substitute for licensed clinician judgment.

## 4. Path to Production Pilot
1. **Shadow Operation (Season 1):** Integrate live badge swipe / headcount feeds and aggregated first-aid logs from a single pilot industrial terminal. Log model predictions silently without initiating work-stop interventions.
2. **Concordance Audit:** At season end, evaluate false-alarm rates against verified incident logs and calibrate alarm thresholds.
3. **Operational Rollout (Season 2):** Deploy real-time push alerts to mobile dashboards with assigned role-based escalation playbooks.
