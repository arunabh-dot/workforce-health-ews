# Modeling Assumptions and Epidemiological Rationale

The Workforce Health Early Warning System (EWS) models the interaction between environmental extremes (heat stress and particulate pollution) and human workforce vulnerability. The underlying assumptions are documented below:

## 1. Multi-Signal Surveillance Rationale
- **Single-Signal Failure Mode (Environmental Only):** Relying solely on ambient temperature or heat index triggers chronic false alarms in desert and tropical climates (e.g., Dubai summer daily highs exceed 42°C for 90+ consecutive days). Workers become desensitized to generic weather advisories.
- **Single-Signal Failure Mode (Workforce Only):** Relying solely on clinic visit surges or injury records detects harm *after* physiological injury has already occurred (zero lead time).
- **Multi-Signal Solution:** Fusing environmental threshold exceedances with early physiological indicators (first-aid clinic visits) and localized peer cluster metrics provides **actionable lead time** prior to severe safety incident escalation.

## 2. Signal Lag Structure
- **Day 0 ($t = 0$):** Ambient meteorological peak / extreme heat dome or PM2.5 dust storm event.
- **Day 1–2 ($t = +1$ to $+2$):** Mild heat exhaustion, dehydration, and early respiratory distress manifest as elevated onsite first-aid or clinic visits.
- **Day 2–4 ($t = +2$ to $+4$):** Cumulative physical fatigue, reduced cognitive alertness, and systemic dehydration culminate in severe safety incidents (falls, equipment accidents) and sharp rises in sick absenteeism.

## 3. Modeling & Statistical Design
- **GLM Baseline Offset:** Count signals scale proportionally with active headcount; modeled via $\log(\text{headcount})$ exposure offset in Poisson GLM.
- **Seasonality & Day of Week:** Modeled via 2nd-order Fourier harmonics and day-of-week fixed effects. UAE industrial workweek dynamics (reduced Friday headcount) are accounted for.
- **Exclusion Buffer:** Baselines are fit over rolling 365-day history, excluding the preceding 14 days, preventing ongoing outbreaks from contaminating their own baseline.
- **Faithful Explainability:** Additive linear models ($\beta_j \cdot x_j$) guarantee that per-signal percentage shares and log-odds contributions sum exactly to the uncalibrated linear predictor.

## 4. Economic & Health Impact Assumptions
- **Workforce Base:** 30 industrial and port sites with ~5,200 total active workers.
- **Baseline Heatwave Incident Rate:** Estimated at 0.45 severe heat-stress incidents per site per heat wave day.
- **Intervention Efficacy:** Early preventive action (hydration staging, rest-shade cycles, heavy task rescheduling) initiated with $\ge 2.0$ days lead time is assumed to prevent 42% of incident escalation.
- **Productivity Value:** An average of 3.5 lost workdays is preserved per avoided severe heat illness case.
- **Honesty Disclosure:** These figures represent an epidemiological model estimate evaluated on synthetic test year data; they do not represent clinical trial outcomes.
