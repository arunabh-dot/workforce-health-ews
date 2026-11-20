import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from pathlib import Path

out = Path('ppt_images')
out.mkdir(exist_ok=True)

# ── 1. Architecture Diagram ──────────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(16, 9))
ax.set_xlim(0, 16); ax.set_ylim(0, 9)
ax.axis('off')
fig.patch.set_facecolor('#FFFFFF')

TEAL   = '#004B55'
LTEAL  = '#E0F2F1'
ACCENT = '#009688'
WHITE  = '#FFFFFF'
ORANGE = '#E65100'
BLUE   = '#1565C0'
GREEN  = '#2E7D32'
GREY   = '#F5F5F5'

def box(ax, x, y, w, h, text, facecolor=TEAL, textcolor=WHITE, fontsize=9, radius=0.2):
    fancy = mpatches.FancyBboxPatch((x-w/2, y-h/2), w, h,
        boxstyle=f'round,pad={radius}', facecolor=facecolor,
        edgecolor=TEAL, linewidth=1.5)
    ax.add_patch(fancy)
    ax.text(x, y, text, ha='center', va='center', fontsize=fontsize,
            color=textcolor, fontweight='bold', wrap=True,
            multialignment='center')

def arrow(ax, x1, y1, x2, y2):
    ax.annotate('', xy=(x2, y2), xytext=(x1, y1),
        arrowprops=dict(arrowstyle='->', color=ACCENT, lw=2))

# Title
ax.text(8, 8.6, 'Workforce Health Early Warning System — Technical Architecture', ha='center',
        fontsize=15, fontweight='bold', color=TEAL)

# Source boxes
sources = [
    (2.5,  7.8, 'Open-Meteo\nWeather API\n(Real Data)'),
    (5.5,  7.8, 'Open-Meteo\nAir Quality API\n(Real Data)'),
    (9.5,  7.8, 'Clinic First-Aid\nVisits\n(Simulated)'),
    (13.0, 7.8, 'Safety Incidents\n& Absence\n(Simulated)'),
]
for x, y, t in sources:
    box(ax, x, y, 2.4, 0.9, t, facecolor=LTEAL, textcolor=TEAL, fontsize=8)
    arrow(ax, x, y-0.45, 7.5, 7.0)

# Central DB
box(ax, 7.5, 6.65, 6.0, 0.75,
    'site_day Database Table  —  Zero PII  —  1 Row per Site-Day',
    facecolor=TEAL, fontsize=9)

# Pipeline stages
stages = [
    (5.8, 'GLM Baselines: NegBin / Poisson + OLS (Rolling 365d Window, 14d Pre-Event Buffer)'),
    (5.0, 'Anomaly Detection: Tabular CUSUM (k=0.5, h=4.0) + EWMA Smoother (lambda=0.3)'),
    (4.2, 'Risk Score Fusion: Regularized L2 Logistic Regression + Isotonic Calibration (17 Features)'),
    (3.4, 'Anti-Fatigue Alert Engine: 2-Day Persistence Rule + Weekly District Budget (Max 5)'),
    (2.6, 'Action Playbook: Role-Based Automated Action Mapping & Evidence Synthesis'),
]
for y, t in stages:
    box(ax, 7.5, y, 9.5, 0.65, t, facecolor='#00636E', fontsize=8)
    if y > 2.6:
        arrow(ax, 7.5, y-0.33, 7.5, y-0.47)

arrow(ax, 7.5, 6.27, 7.5, 6.13)

# Output boxes
out_boxes = [
    (3.0,  1.4, 'Site Safety Officer\nOwn site only · Playbook actions', GREEN),
    (8.0,  1.4, 'Occupational Health Lead\nDistrict aggregates · Resource readiness', BLUE),
    (13.0, 1.4, 'District Regulator\nCritical alerts · Summary compliance', ORANGE),
]
for x, y, t, c in out_boxes:
    arrow(ax, 7.5, 2.27, x, y+0.45)
    box(ax, x, y, 3.8, 0.75, t, facecolor=c, fontsize=8.5)

plt.tight_layout(pad=0.3)
plt.savefig(str(out / 'arch_diagram.png'), dpi=180, bbox_inches='tight', facecolor='white')
plt.close()
print('arch_diagram.png successfully created')
