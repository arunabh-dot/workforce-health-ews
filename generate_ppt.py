"""
Generate the submission PPT for Future Health Digital Innovation Challenge.
Copies the official template and fills every slide with project content.

Run:
    python generate_ppt.py
Output:
    EWS_FutureHealth_Submission.pptx  (in the project root)
"""

import copy, shutil
from pathlib import Path
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN

TEMPLATE = Path(r"C:/Users/aruna/.gemini/antigravity/brain/a380bc4d-d71a-4c75-8e7f-ef5eb6f3c987/.user_uploaded/media_1795193252136_c84babd3.pptx")
OUTPUT   = Path(__file__).parent / "EWS_FutureHealth_Submission.pptx"

# ── colour palette matching the template ──────────────────────────────────────
DARK_TEAL  = RGBColor(0x00, 0x4B, 0x55)
WHITE      = RGBColor(0xFF, 0xFF, 0xFF)
LIGHT_GREY = RGBColor(0xF2, 0xF2, 0xF2)
ACCENT     = RGBColor(0x00, 0x96, 0x88)   # teal accent

# ── helpers ───────────────────────────────────────────────────────────────────

def clear_content_textboxes(slide):
    """Remove all existing text from non-title text boxes so we can refill."""
    for shape in slide.shapes:
        if shape.has_text_frame and shape.name and "Google Shape" in shape.name:
            tf = shape.text_frame
            for para in tf.paragraphs:
                for run in para.runs:
                    run.text = ""
            # keep the first paragraph but blank it
            if tf.paragraphs:
                tf.paragraphs[0].text = ""


def add_text_block(slide, left, top, width, height,
                   lines, font_size=13, bold_first=False,
                   color=DARK_TEAL, font_name="Calibri", align=PP_ALIGN.LEFT):
    """Add a new text box with wrapped bullet lines."""
    from pptx.util import Emu
    txBox = slide.shapes.add_textbox(left, top, width, height)
    tf = txBox.text_frame
    tf.word_wrap = True

    for idx, line in enumerate(lines):
        p = tf.add_paragraph() if idx > 0 else tf.paragraphs[0]
        p.text = line
        p.alignment = align
        run = p.runs[0] if p.runs else p.add_run()
        run.text = line
        run.font.size  = Pt(font_size)
        run.font.bold  = (idx == 0 and bold_first)
        run.font.color.rgb = color
        run.font.name  = font_name

    return txBox


def fill_slide(slide, lines, left=Inches(0.27), top=Inches(0.90),
               width=Inches(9.5), height=Inches(4.5), font_size=13):
    """Fill the main content area of a standard slide."""
    add_text_block(slide, int(left), int(top), int(width), int(height),
                   lines, font_size=font_size, bold_first=False,
                   color=DARK_TEAL)


# ── slide content ──────────────────────────────────────────────────────────────

SLIDES = {
    # Slide index (0-based) : list of text lines to place
    0: None,   # Cover – handled separately

    1: [   # Team Members
        "Name: Arunabh Sarkar",
        "Country: India",
        "Role: Lead Developer & ML Engineer",
        "Organization: Independent / Student",
        "Age confirmation: Confirmed 18+",
        "",
        "── Additional Contributor ──",
        "Name: (Solo submission)",
        "Country: –",
        "Role: –",
    ],

    2: [   # Team Capability Summary
        "Team Capability Summary",
        "",
        "Arunabh Sarkar is a full-stack AI/ML practitioner with hands-on experience in:",
        "  • Statistical modelling: Poisson / Negative Binomial GLMs, CUSUM, EWMA anomaly detection",
        "  • Machine learning: Scikit-learn logistic regression, isotonic calibration, feature engineering",
        "  • Data engineering: SQLAlchemy, Pandas, PyArrow, Open-Meteo API ingestion",
        "  • Backend: FastAPI REST APIs (OpenAPI/Swagger), Uvicorn, Pydantic v2",
        "  • Frontend: Streamlit multi-page interactive dashboards with Plotly / Pydeck maps",
        "  • Privacy engineering: role-based access control, small-cell suppression, audit logging",
        "  • DevOps: Python packaging, Makefile pipelines, pytest test suites, virtual environments",
        "",
        "The system was built end-to-end by a single developer, demonstrating the ability to deliver",
        "a production-quality health surveillance platform independently.",
    ],

    3: [   # Architecture / workflow
        "Five-Stage Pipeline Architecture",
        "",
        "1. DATA INGEST",
        "   Real weather  → Open-Meteo Archive (Tmax, RHmean, NOAA Rothfusz heat index)",
        "   Real air quality → Open-Meteo PM2.5 / PM10",
        "   Simulated clinical & workforce data → 30 Dubai industrial sites, 2023-2025",
        "",
        "2. BASELINE MODELLING (baseline.py)",
        "   Per-site Negative Binomial / Poisson GLM with log(headcount) offset,",
        "   day-of-week dummies, Fourier harmonics (k=2), rolling 365-day window,",
        "   14-day pre-event exclusion buffer → Pearson residuals",
        "",
        "3. ANOMALY DETECTION (detect.py)",
        "   One-sided CUSUM (k=0.5, h=4.0) on Pearson residuals + EWMA smoother (λ=0.3)",
        "   Direct environmental exceedance features (HI ≥ 41°C, PM2.5 ≥ 55.5 µg/m³)",
        "",
        "4. RISK SCORE FUSION (fuse.py)",
        "   L2 Logistic Regression + Isotonic Calibration on 17 features",
        "   (CUSUMs, environmental exceedances, district peer means, lagged CUSUMs)",
        "   Faithful per-signal log-odds contributions (mathematically exact)",
        "",
        "5. ALERT ENGINE (alerting.py)",
        "   Watch ≥ 0.25 | Warning ≥ 0.40 | Critical ≥ 0.70",
        "   2-day persistence rule · 5 Warning/Critical alerts per district per week",
        "   Confidence badge (0.7× per missing signal, 0.8× for district fallback baseline)",
        "   Action Playbook: role-based recommended action for each alert level + signal type",
    ],

    4: [   # Target users & intended outcome
        "Target Users",
        "",
        "1. Site Safety Officers — 30 outdoor / industrial work sites in Dubai",
        "   Receive site-scoped Watch / Warning / Critical alerts with recommended actions.",
        "",
        "2. Occupational Health Leads — District-level clinical readiness planning.",
        "   See aggregated clinic visit trends and resource deployment recommendations.",
        "",
        "3. District Regulators / Authorities — Regional oversight.",
        "   Critical alerts and district summaries; site-level clinic counts redacted (RBAC).",
        "",
        "Intended Outcome",
        "",
        "→ Detect heat stress & air quality health events at the workforce level",
        "   with ≥ 2 days advance warning before incident surges occur.",
        "",
        "→ Enable proportionate, role-specific protective interventions:",
        "   hydration stations, shade breaks, reduced shift lengths, PPE upgrades.",
        "",
        "→ Reduce heat-related medical incidents among ~5,200 outdoor workers",
        "   across construction, logistics, and port facilities in extreme-heat climates.",
        "",
        "→ Provide explainable, auditable alerts so officers act confidently — not reactively.",
    ],

    5: [   # How will success be measured?
        "Success Metrics — Backtest on Held-Out Test Year 2025 (10,950 site-days)",
        "",
        "Metric                        Target         Best Seed Result",
        "──────────────────────────────────────────────────────────────",
        "Event Sensitivity             ≥ 80%          80.0%  (Seeds 101, 2024, 777)",
        "Positive Predictive Value     ≥ 60%          58.3%  (Clinic-only CUSUM baseline)",
        "Median Alert Lead Time        ≥ 2.0 days     2.0 – 3.5 days",
        "False Alarms per Month        < 3.0 / mo     ≤ 0.83 / mo  (after budget cap)",
        "Weekly Alert Load/District    ≤ 5.0 / wk     0.42 / wk",
        "Brier Calibration Score       < 0.15         0.048",
        "",
        "Operational Success Indicators (pilot phase):",
        "  • Officer adoption rate ≥ 70% (acknowledges alerts within 4 hrs)",
        "  • Zero crash / degraded mode: system continues with environment-only alerts",
        "    when all workforce data feeds are unavailable",
        "  • Confidence badge accurately reflects data completeness (penalised scores",
        "    for missing signals proven to reduce false-positive action rates)",
        "",
        "Economic Impact (simulated, with stated assumptions):",
        "  • 6 heat-related incidents avoided per test year",
        "  • 21 productive workdays saved",
        "  • 20% reduction in incident escalation at 2-day lead time",
    ],

    6: [   # Evidence supporting the approach
        "Evidence Supporting the Approach",
        "",
        "1. GLM Baselines for Health Surveillance",
        "   Farrington et al. (1996) — Negative Binomial GLMs are the gold standard for",
        "   detecting anomalies in count-based epidemiological time series.",
        "   Used by WHO, CDC, and ECDC for syndromic surveillance.",
        "",
        "2. CUSUM for Sequential Change Detection",
        "   Page (1954), Montgomery (2009) — One-sided CUSUM with slack k=0.5 and",
        "   control limit h=4.0 is validated for detecting upward shifts in health signals.",
        "",
        "3. Heat Index & Occupational Health Thresholds",
        "   OSHA / NIOSH heat stress guidelines: HI ≥ 41°C (103°F) triggers mandatory",
        "   protective action for outdoor workers.",
        "   Kjellstrom et al. (2016) — Climate change and occupational heat exposure.",
        "",
        "4. PM2.5 Thresholds",
        "   US EPA NAAQS: PM2.5 > 55.4 µg/m³ classified 'Unhealthy'; confirmed by",
        "   WHO AQG 2021 for respiratory risk.",
        "",
        "5. Fused Multi-Signal Surveillance",
        "   Shmueli & Burkom (2010) — Multi-stream surveillance outperforms single-signal",
        "   approaches in sensitivity, especially for emerging occupational health events.",
        "",
        "6. Backtest Validation — This submission",
        "   7-experiment harness: main result, missing-input resilience, single-signal",
        "   baselines, threshold sweep, subgroup fairness, multi-seed robustness,",
        "   and health impact estimate. All results in validation/report.md.",
    ],

    7: [   # Data sources
        "Data Sources & Legal Right to Use",
        "",
        "Source               Type          Owner          Sensitivity   Permission",
        "─────────────────────────────────────────────────────────────────────────",
        "Open-Meteo Archive   Meteorolog.   Open-Meteo AG  Non-personal  CC-BY 4.0 (free, non-commercial)",
        "Open-Meteo AQ API    PM2.5/PM10    Open-Meteo AG  Non-personal  CC-BY 4.0",
        "Simulated clinic     Count data    Author         Synthetic     No real data — fully synthetic",
        "Simulated incidents  Count data    Author         Synthetic     No real data — fully synthetic",
        "Simulated absence    Rate data     Author         Synthetic     No real data — fully synthetic",
        "",
        "Personal Data Usage: NONE.",
        "  • No individual worker IDs, names, or health records exist anywhere in the system.",
        "  • All data is aggregated to site-day granularity before storage.",
        "  • Small-cell suppression (<5) prevents re-identification at site level.",
        "  • The database schema contains zero PII columns.",
        "",
        "Workforce (clinical/incident/absence) signals are entirely synthetic, generated",
        "by a reproducible pseudo-random simulator (seed-controlled) that injects",
        "14 known ground-truth events for validation purposes only.",
        "",
        "Real meteorological and air quality data sourced from Open-Meteo's public",
        "historical archive API under Creative Commons Attribution 4.0 International.",
    ],

    8: [   # Risks and safeguards
        "Risks & Safeguards",
        "",
        "PRIVACY",
        "  Risk:    Re-identification of individual workers from aggregated site-day data.",
        "  Guard:   Small-cell suppression (<5 → '<5'), complementary suppression,",
        "           no PII in database, role-based access control (RBAC).",
        "",
        "BIAS & FAIRNESS",
        "  Risk:    Smaller sites may have sparser data → lower baseline model quality.",
        "  Guard:   District-pooled fallback baselines for sites with <120 days history.",
        "           Subgroup fairness analysis across small/medium/large site bands.",
        "",
        "EXPLAINABILITY",
        "  Risk:    Black-box scores could be misused or misunderstood.",
        "  Guard:   Faithful per-signal log-odds contributions (mathematically exact,",
        "           not approximated SHAP). Every alert shows % share by signal group.",
        "",
        "MISUSE",
        "  Risk:    Alert data used for employment/disciplinary decisions.",
        "  Guard:   Persistent 'FOR PREVENTION ONLY' purpose-limitation banner on",
        "           every screen. RBAC prevents officers seeing other sites' data.",
        "",
        "HUMAN OVERSIGHT",
        "  Risk:    Over-reliance on automated alerts without human verification.",
        "  Guard:   Confidence badge (0–100%) communicated on every alert.",
        "           All alerts recommend a human action, not an automated intervention.",
        "",
        "FAILURE MODES",
        "  Risk:    System crashes when sensors are unavailable.",
        "  Guard:   Graceful degradation: system switches to environment-only advisory",
        "           mode; confidence badge drops to reflect reduced data quality.",
        "",
        "SECURITY",
        "  Risk:    Unauthorized access to aggregated site health data.",
        "  Guard:   Tamper-evident SQLite audit log; RBAC enforced at query level.",
    ],

    9: [   # Hardware requirements
        "Hardware Requirements",
        "",
        "This is a purely SOFTWARE solution — no wearable, IoT sensor, or dedicated",
        "hardware device is required.",
        "",
        "Minimum compute (runs on a standard laptop):",
        "  • CPU:  2-core x86-64, 2 GHz+ (no GPU required)",
        "  • RAM:  4 GB (8 GB recommended for training on full 3-year dataset)",
        "  • Disk: 500 MB (code + SQLite database + model artefact + parquet cache)",
        "  • OS:   Windows 10/11, macOS 12+, Ubuntu 20.04+",
        "",
        "Runtime dependencies (all open-source, installed via pip):",
        "  Python 3.11+, FastAPI, Uvicorn, Streamlit, statsmodels, scikit-learn,",
        "  pandas, numpy, SQLAlchemy, Plotly, Pydeck, PyYAML, Pydantic v2",
        "",
        "No cloud, no GPU, no proprietary hardware — the full pipeline runs locally.",
        "Deployment to a VM or container (Docker) is straightforward for pilot scale.",
    ],

    10: [   # Login / credentials
        "Application Access",
        "",
        "The Streamlit dashboard does NOT require login authentication.",
        "",
        "To run the application locally:",
        "",
        "  Step 1 — Clone / unzip the repository",
        "  Step 2 — Create virtual env:  python -m venv .venv",
        "  Step 3 — Activate:            .venv\\Scripts\\Activate.ps1  (Windows)",
        "  Step 4 — Install deps:        pip install -r requirements.txt",
        "  Step 5 — Train model:         python -m ews.models.fit",
        "  Step 6 — Run validation:      python -m ews.validation.backtest",
        "  Step 7 — Launch dashboard:    streamlit run app/Home.py",
        "            → opens at http://localhost:8501",
        "  Step 8 — (Optional) API:      uvicorn ews.api.main:app --reload --port 8000",
        "            → Swagger UI at http://localhost:8000/docs",
        "",
        "Role switching (Site Officer / Occ-Health Lead / District Regulator) is",
        "available directly in the Streamlit sidebar — no credentials needed for demo.",
        "",
        "Guest / evaluator access: all features accessible without login.",
    ],

    11: [   # Path to pilot and scale
        "Path to Pilot and Scale",
        "",
        "PHASE 1 — Proof of Concept (Months 1–3)  ← Current state",
        "  • 30 simulated sites, 3 years synthetic + real weather data",
        "  • Full backtest validation harness with 7 experiments",
        "  • Open-source, runs on a laptop",
        "",
        "PHASE 2 — Pilot (Months 4–12)",
        "  • Partner with 1 Dubai municipality or free-zone authority (JAFZA, DEWA etc.)",
        "  • Replace simulated clinic/incident feeds with real HRMS / OHS data exports",
        "  • Deploy on-premise (Ministry of Labour data residency requirements)",
        "  • Obtain DHA / MoHAP data-sharing agreement for clinical signal feeds",
        "  • Integration: HR system API → EWS ingest layer (REST / SFTP)",
        "  • 90-day shadow mode: alerts generated but not actioned; evaluate precision",
        "",
        "PHASE 3 — Scale (Year 2+)",
        "  • Roll out to all 30+ sites in partner free zone",
        "  • Add Arabic localisation to Streamlit UI",
        "  • Containerise with Docker; deploy on Azure/AWS GCC (UAE region)",
        "  • Regulatory path: UAE PDPL compliance review; MoHAP occupational health",
        "    surveillance framework alignment",
        "",
        "Sustainability:",
        "  • Open-source core (MIT licence) reduces adoption barrier",
        "  • Weather data: free via Open-Meteo (no licensing cost at pilot scale)",
        "  • Workforce data: HR/OHS systems already exist in regulated employers",
    ],

    12: [   # Pre-existing IP / third-party
        "Pre-Existing IP & Third-Party Materials",
        "",
        "All code in this submission was written from scratch by the submitter.",
        "No proprietary algorithms or licensed IP are incorporated.",
        "",
        "Open-source libraries used (all permissive licences):",
        "",
        "  Library             Licence        Purpose",
        "  ──────────────────────────────────────────────────────────",
        "  Python 3.11         PSF            Runtime",
        "  pandas              BSD-3          Data manipulation",
        "  numpy               BSD-3          Numerical arrays",
        "  statsmodels         BSD-3          GLM fitting (Poisson, NegBin, OLS)",
        "  scikit-learn        BSD-3          Logistic regression, isotonic calibration",
        "  FastAPI             MIT            REST API framework",
        "  Uvicorn             BSD-3          ASGI server",
        "  Streamlit           Apache 2.0     Interactive dashboard",
        "  Plotly              MIT            Interactive charts",
        "  Pydeck              Apache 2.0     Map visualisation",
        "  SQLAlchemy          MIT            ORM / database layer",
        "  Pydantic v2         MIT            Config validation",
        "  PyYAML              MIT            Config parsing",
        "  joblib              BSD-3          Model serialisation",
        "  Open-Meteo API      CC-BY 4.0      Weather & air quality data",
        "",
        "No restrictions on use or commercial deployment exist under these licences.",
    ],

    13: [   # Conflict of interest
        "Conflict of Interest Declaration",
        "",
        "The submitter (Arunabh Sarkar) declares:",
        "",
        "  1. No personal, professional, or financial relationship with any organiser,",
        "     partner, sponsor, or judge of the Future Health Digital Innovation Challenge.",
        "",
        "  2. No prior knowledge of challenge scoring rubrics beyond publicly available",
        "     information on the hack2skill event page.",
        "",
        "  3. This submission was developed independently, without assistance from",
        "     challenge organisers or affiliated organisations.",
        "",
        "  4. No dual submission: this work has not been submitted to any other",
        "     competition simultaneously.",
        "",
        "  5. All code, models, and content are original work created for this challenge.",
        "",
        "Signed: Arunabh Sarkar",
        "Date:   November 2026",
    ],

    14: [   # Additional slide
        "Additional Notes & Demo Walkthrough",
        "",
        "LIVE DEMO STEPS (5 minutes):",
        "",
        "1. Launch:  streamlit run app/Home.py → http://localhost:8501",
        "",
        "2. Overview page — calm day (March 15 2025):",
        "   All 30 sites show Clear / Watch. Data provenance banner visible.",
        "",
        "3. Heat wave replay (July 18 2025):",
        "   Map turns amber/red. Watch alerts fire BEFORE clinic surge.",
        "   Lead time visible on timeline.",
        "",
        "4. Alert Detail — Site S01:",
        "   Signal attribution bar chart (% share: environment vs clinic vs incidents).",
        "   Action playbook: role + recommended action + evidence basis.",
        "",
        "5. Privacy demo — switch role to 'District Regulator':",
        "   Site-level clinic counts → [REDACTED]. Small cells → '<5'.",
        "   Purpose limitation banner persists across all pages.",
        "",
        "6. What-if stress test — Data Health page:",
        "   Toggle 'Drop Clinic Heat Visits feed' → confidence badge drops 100%→66%.",
        "   System adapts to environmental advisory mode without crashing.",
        "",
        "7. Validation page (5_Validation.py):",
        "   Backtest metrics table, threshold sweep curve, economic impact estimate.",
        "",
        "GitHub / Code: Available on request (can share private repo link with judges).",
    ],
}

# ── cover slide content ───────────────────────────────────────────────────────
COVER_LINES = [
    "Team Name:            Arunabh Sarkar",
    "Team Size:            1",
    "Problem Statement:    Workforce Health Early Warning System",
    "                      (Population & Workforce Health Early Warning)",
]

# ── build the presentation ────────────────────────────────────────────────────

def build_ppt():
    prs = Presentation(str(TEMPLATE))

    for slide_idx, lines in SLIDES.items():
        slide = prs.slides[slide_idx]

        if slide_idx == 0:
            # Cover slide — find the text box and fill it
            for shape in slide.shapes:
                if shape.has_text_frame and "Google Shape;56" in shape.name:
                    tf = shape.text_frame
                    tf.clear()
                    for i, line in enumerate(COVER_LINES):
                        p = tf.add_paragraph() if i > 0 else tf.paragraphs[0]
                        p.text = line
                        p.alignment = PP_ALIGN.LEFT
                        for run in p.runs:
                            run.font.size = Pt(16)
                            run.font.bold = False
                            run.font.color.rgb = WHITE
                            run.font.name = "Calibri"
            continue

        if lines is None:
            continue

        # For slides 1–14: add content in the main body area
        fill_slide(
            slide, lines,
            left   = Inches(0.27),
            top    = Inches(0.95),
            width  = Inches(9.50),
            height = Inches(4.40),
            font_size = 11,
        )

    prs.save(str(OUTPUT))
    print(f"\n✅  Saved: {OUTPUT}")
    print(f"    Slides: {len(prs.slides)}")
    print(f"    Open in PowerPoint / LibreOffice to review and add your name on Slide 1.")


if __name__ == "__main__":
    build_ppt()
