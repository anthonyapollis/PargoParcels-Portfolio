"""
Correlation & statistical analysis charts for Pargo Parcels ML portfolio.
Generates plots 30-38.
"""
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from matplotlib.colors import TwoSlopeNorm
from pathlib import Path
import warnings
warnings.filterwarnings("ignore")

OUT = Path(__file__).parent / "plots"
OUT.mkdir(exist_ok=True)

np.random.seed(42)
N = 80_000

DARK   = "#0d1117"
SURF   = "#161b22"
BORDER = "#30363d"
BLUE   = "#58a6ff"
GREEN  = "#3fb950"
RED    = "#f85149"
AMBER  = "#d29922"
PURPLE = "#bc8cff"
TEAL   = "#39d353"
WHITE  = "#e6edf3"
MUTED  = "#8b949e"

PROVINCES = ["Gauteng","Western Cape","KZN","Eastern Cape","Limpopo",
             "Mpumalanga","North West","Free State","Northern Cape"]
PROV_WEIGHTS = np.array([0.35,0.20,0.18,0.10,0.06,0.05,0.03,0.02,0.01])

# ── Synthetic data matching the project's real distributions ──────────────────
province_idx = np.random.choice(9, N, p=PROV_WEIGHTS)
vehicle_idx  = np.random.choice(4, N, p=[0.40,0.30,0.20,0.10])   # Bakkie,Sedan,Van,Moto
cat_idx      = np.random.choice(5, N, p=[0.42,0.22,0.15,0.12,0.09])  # Fashion,Elec,Health,Home,Sports

# Province-based RTS tendency
rts_base = np.array([0.142,0.118,0.161,0.183,0.198,0.175,0.191,0.172,0.210])
rts_by_prov = rts_base[province_idx]

# Raw features
parcel_weight  = np.random.lognormal(1.0, 0.7, N)
parcel_value   = np.random.lognormal(5.5, 0.8, N)
delivery_cost  = np.random.lognormal(4.4, 0.4, N)
transit_hours  = np.abs(np.random.normal(48, 24, N)) + 6
dwell_days     = np.random.exponential(3.2, N)
event_count    = np.random.poisson(5, N) + 1
exception_count= np.random.poisson(0.3, N)
parcel_age_days= np.random.randint(1, 400, N)
order_value    = parcel_value * np.random.uniform(1.0, 3.5, N)

# RTS label -- influenced by multiple features
rts_score = (
    rts_by_prov * 2
    + (dwell_days > 5).astype(float) * 0.3
    + (exception_count > 0).astype(float) * 0.25
    + (transit_hours > 96).astype(float) * 0.2
    - (parcel_value > 1000).astype(float) * 0.15
    + np.random.normal(0, 0.1, N)
)
rts = (rts_score > np.percentile(rts_score, 85)).astype(int)

# Category-based RTS
cat_rts_rate = np.array([0.172, 0.091, 0.143, 0.138, 0.157])
rts_cat = cat_rts_rate[cat_idx]

FEAT_NAMES = [
    "Parcel Weight (kg)", "Parcel Value (ZAR)", "Delivery Cost (ZAR)",
    "Transit Hours", "Dwell Days", "Event Count",
    "Exception Count", "Parcel Age (days)", "Order Value (ZAR)"
]
X = np.column_stack([
    parcel_weight, parcel_value, delivery_cost,
    transit_hours, dwell_days, event_count,
    exception_count, parcel_age_days, order_value
])


def apply_dark(ax):
    ax.set_facecolor(SURF)
    ax.tick_params(colors=WHITE, labelsize=8)
    for s in ax.spines.values():
        s.set_color(BORDER)


# ── 30: Full correlation matrix heatmap ──────────────────────────────────────
print("30 Correlation matrix...")
corr_cols = np.column_stack([X, rts])
corr_names = FEAT_NAMES + ["RTS Label"]
C = np.corrcoef(corr_cols.T)

fig, ax = plt.subplots(figsize=(12, 10), facecolor=DARK)
ax.set_facecolor(DARK)
norm = TwoSlopeNorm(vmin=-1, vcenter=0, vmax=1)
im = ax.imshow(C, cmap="RdYlGn", norm=norm, aspect="auto")

ax.set_xticks(range(len(corr_names)))
ax.set_yticks(range(len(corr_names)))
ax.set_xticklabels(corr_names, rotation=40, ha="right", color=WHITE, fontsize=8)
ax.set_yticklabels(corr_names, color=WHITE, fontsize=8)

for i in range(len(corr_names)):
    for j in range(len(corr_names)):
        val = C[i, j]
        text_color = "black" if abs(val) < 0.5 else "white"
        ax.text(j, i, f"{val:.2f}", ha="center", va="center",
                color=text_color, fontsize=7.5, fontweight="bold" if abs(val) > 0.6 else "normal")

cbar = fig.colorbar(im, ax=ax, shrink=0.85, pad=0.02)
cbar.set_label("Pearson r", color=WHITE, fontsize=10)
cbar.ax.tick_params(colors=WHITE)
plt.setp(cbar.ax.yaxis.get_ticklabels(), color=WHITE)

ax.set_title("Feature Correlation Matrix -- All Parcel & Customer Attributes",
             color=WHITE, fontsize=13, fontweight="bold", pad=12)
fig.tight_layout()
fig.savefig(OUT / "30_correlation_matrix.png", dpi=150, bbox_inches="tight", facecolor=DARK)
plt.close()
print("  30 done")


# ── 31: Feature vs RTS target correlation bar chart ──────────────────────────
print("31 Feature-target correlation...")
target_corr = np.array([np.corrcoef(X[:, i], rts)[0, 1] for i in range(X.shape[1])])
sort_idx = np.argsort(np.abs(target_corr))[::-1]

fig, ax = plt.subplots(figsize=(10, 6), facecolor=DARK)
apply_dark(ax)
colors = [RED if v > 0 else GREEN for v in target_corr[sort_idx]]
bars = ax.barh(range(len(FEAT_NAMES)), target_corr[sort_idx], color=colors, alpha=0.85, height=0.65)
ax.set_yticks(range(len(FEAT_NAMES)))
ax.set_yticklabels([FEAT_NAMES[i] for i in sort_idx], color=WHITE, fontsize=9)
ax.axvline(0, color=BORDER, linewidth=1)
ax.set_xlabel("Pearson Correlation with RTS Label", color=WHITE, fontsize=10)
ax.set_title("Feature Correlation with RTS (Return to Sender) Target",
             color=WHITE, fontsize=13, fontweight="bold")
for bar, v in zip(bars, target_corr[sort_idx]):
    ax.text(v + (0.003 if v >= 0 else -0.003), bar.get_y() + bar.get_height()/2,
            f"{v:+.3f}", va="center", ha="left" if v >= 0 else "right",
            color=WHITE, fontsize=8)
ax.legend(handles=[
    plt.Rectangle((0,0),1,1, color=RED, alpha=0.85, label="Positive (increases RTS risk)"),
    plt.Rectangle((0,0),1,1, color=GREEN, alpha=0.85, label="Negative (reduces RTS risk)"),
], facecolor=SURF, edgecolor=BORDER, labelcolor=WHITE, fontsize=8)
fig.tight_layout()
fig.savefig(OUT / "31_feature_target_correlation.png", dpi=150, bbox_inches="tight", facecolor=DARK)
plt.close()
print("  31 done")


# ── 32: Scatter matrix (pairplot) for top 4 features ─────────────────────────
print("32 Scatter matrix...")
top4_idx = np.argsort(np.abs(target_corr))[::-1][:4]
top4_names = [FEAT_NAMES[i] for i in top4_idx]
X4 = X[:, top4_idx][:5000]  # subsample
rts4 = rts[:5000]

fig, axes = plt.subplots(4, 4, figsize=(14, 12), facecolor=DARK)
fig.suptitle("Scatter Matrix: Top 4 Predictive Features vs RTS",
             color=WHITE, fontsize=13, fontweight="bold", y=0.99)

for i in range(4):
    for j in range(4):
        ax = axes[i][j]
        ax.set_facecolor(SURF)
        for sp in ax.spines.values(): sp.set_color(BORDER)
        ax.tick_params(colors=WHITE, labelsize=7)

        if i == j:
            # Diagonal: distribution by class
            ax.hist(X4[rts4==0, i], bins=30, color=GREEN, alpha=0.6,
                    density=True, label="Collected")
            ax.hist(X4[rts4==1, i], bins=30, color=RED, alpha=0.7,
                    density=True, label="RTS")
            ax.set_title(top4_names[i], color=BLUE, fontsize=8, pad=3)
        else:
            sample = np.random.choice(len(X4), 800, replace=False)
            ax.scatter(X4[sample, j], X4[sample, i],
                       c=[RED if r else GREEN for r in rts4[sample]],
                       s=4, alpha=0.4)
            r = np.corrcoef(X4[:, j], X4[:, i])[0, 1]
            ax.text(0.05, 0.92, f"r={r:.2f}", transform=ax.transAxes,
                    color=AMBER, fontsize=8, fontweight="bold")

        if i == 3: ax.set_xlabel(top4_names[j], color=MUTED, fontsize=7)
        if j == 0: ax.set_ylabel(top4_names[i], color=MUTED, fontsize=7)

legend_patches = [
    plt.Line2D([0],[0], marker='o', color='w', markerfacecolor=GREEN,
               markersize=7, label="Collected"),
    plt.Line2D([0],[0], marker='o', color='w', markerfacecolor=RED,
               markersize=7, label="RTS"),
]
fig.legend(handles=legend_patches, loc="upper right", facecolor=SURF,
           edgecolor=BORDER, labelcolor=WHITE, fontsize=9)
plt.tight_layout(rect=[0, 0, 1, 0.97])
fig.savefig(OUT / "32_scatter_matrix.png", dpi=130, bbox_inches="tight", facecolor=DARK)
plt.close()
print("  32 done")


# ── 33: Province x feature heatmap (mean values by province) ─────────────────
print("33 Province feature heatmap...")
prov_means = np.zeros((9, X.shape[1] + 1))
for p in range(9):
    mask = province_idx == p
    prov_means[p, :X.shape[1]] = X[mask].mean(axis=0)
    prov_means[p, -1] = rts[mask].mean() * 100  # RTS %

short_feat = ["Weight", "Value", "Cost", "Transit\nHrs", "Dwell\nDays",
              "Events", "Exceptions", "Age\nDays", "Order\nValue", "RTS\n%"]

# Normalise each feature for visualisation
prov_norm = (prov_means - prov_means.mean(0)) / (prov_means.std(0) + 1e-8)

fig, ax = plt.subplots(figsize=(14, 7), facecolor=DARK)
ax.set_facecolor(DARK)
im = ax.imshow(prov_norm, cmap="RdYlGn_r", aspect="auto", vmin=-2, vmax=2)

ax.set_xticks(range(10))
ax.set_xticklabels(short_feat, color=WHITE, fontsize=9)
ax.set_yticks(range(9))
ax.set_yticklabels(PROVINCES, color=WHITE, fontsize=9)

for i in range(9):
    for j in range(10):
        raw = prov_means[i, j]
        label = f"{raw:.1f}%" if j == 9 else (f"{raw:.0f}" if raw > 99 else f"{raw:.1f}")
        ax.text(j, i, label, ha="center", va="center",
                color="black" if abs(prov_norm[i, j]) < 1.2 else WHITE,
                fontsize=7.5, fontweight="bold" if j == 9 else "normal")

cbar = fig.colorbar(im, ax=ax, shrink=0.8, pad=0.02)
cbar.set_label("Z-score (normalised)", color=WHITE, fontsize=9)
cbar.ax.tick_params(colors=WHITE)
plt.setp(cbar.ax.yaxis.get_ticklabels(), color=WHITE)

ax.set_title("Province x Feature Heatmap: Mean Values by Province (RTS % in final column)",
             color=WHITE, fontsize=12, fontweight="bold", pad=10)
fig.tight_layout()
fig.savefig(OUT / "33_province_feature_heatmap.png", dpi=150, bbox_inches="tight", facecolor=DARK)
plt.close()
print("  33 done")


# ── 34: RTS rate by category + province (grouped bar) ────────────────────────
print("34 RTS by category + province...")
CAT_NAMES = ["Fashion", "Electronics", "Health & Beauty", "Home & Living", "Sports"]

# RTS rates by province x category
prov_cat_rts = np.zeros((9, 5))
for p in range(9):
    for c in range(5):
        mask = (province_idx == p) & (cat_idx == c)
        if mask.sum() > 10:
            prov_cat_rts[p, c] = rts[mask].mean() * 100
        else:
            prov_cat_rts[p, c] = rts_base[p] * 100 + cat_rts_rate[c] * 100 - 14

fig, axes = plt.subplots(1, 2, figsize=(16, 6), facecolor=DARK)
fig.suptitle("RTS Rate Analysis: Category and Province Breakdown",
             color=WHITE, fontsize=13, fontweight="bold")

# Left: RTS by retailer category
ax = axes[0]
apply_dark(ax)
cat_rts_mean = prov_cat_rts.mean(0)
colors_cat = [RED if v > 15 else AMBER if v > 12 else GREEN for v in cat_rts_mean]
bars = ax.bar(CAT_NAMES, cat_rts_mean, color=colors_cat, alpha=0.85, width=0.6)
ax.set_ylabel("Mean RTS Rate (%)", color=WHITE, fontsize=10)
ax.set_title("RTS Rate by Retailer Category", color=BLUE, fontsize=11)
ax.axhline(cat_rts_mean.mean(), color=WHITE, linestyle="--", alpha=0.5,
           label=f"Overall avg: {cat_rts_mean.mean():.1f}%")
ax.legend(facecolor=SURF, edgecolor=BORDER, labelcolor=WHITE, fontsize=8)
for bar, v in zip(bars, cat_rts_mean):
    ax.text(bar.get_x() + bar.get_width()/2, v + 0.2, f"{v:.1f}%",
            ha="center", va="bottom", color=WHITE, fontsize=9, fontweight="bold")
plt.setp(ax.get_xticklabels(), rotation=15, ha="right")

# Right: RTS by province (sorted)
ax = axes[1]
apply_dark(ax)
prov_rts = prov_cat_rts.mean(1)
sort_idx = np.argsort(prov_rts)
colors_prov = [RED if v > 18 else AMBER if v > 15 else GREEN for v in prov_rts[sort_idx]]
bars = ax.barh(range(9), prov_rts[sort_idx], color=colors_prov, alpha=0.85, height=0.65)
ax.set_yticks(range(9))
ax.set_yticklabels([PROVINCES[i] for i in sort_idx], color=WHITE, fontsize=9)
ax.set_xlabel("Mean RTS Rate (%)", color=WHITE, fontsize=10)
ax.set_title("RTS Rate by Province", color=BLUE, fontsize=11)
ax.axvline(prov_rts.mean(), color=WHITE, linestyle="--", alpha=0.5,
           label=f"Overall avg: {prov_rts.mean():.1f}%")
ax.legend(facecolor=SURF, edgecolor=BORDER, labelcolor=WHITE, fontsize=8)
for bar, v in zip(bars, prov_rts[sort_idx]):
    ax.text(v + 0.1, bar.get_y() + bar.get_height()/2, f"{v:.1f}%",
            va="center", color=WHITE, fontsize=8)

plt.tight_layout()
fig.savefig(OUT / "34_rts_by_category_province.png", dpi=150, bbox_inches="tight", facecolor=DARK)
plt.close()
print("  34 done")


# ── 35: Distribution plots for all key features ───────────────────────────────
print("35 Feature distributions...")
fig, axes = plt.subplots(3, 3, figsize=(15, 10), facecolor=DARK)
fig.suptitle("Feature Distributions: RTS vs Collected Parcels",
             color=WHITE, fontsize=13, fontweight="bold", y=0.99)

feat_clips = [10, 5000, 500, 200, 15, 20, 3, 400, 15000]

for idx, (ax, name, clip) in enumerate(zip(axes.flat, FEAT_NAMES, feat_clips)):
    apply_dark(ax)
    vals_0 = np.clip(X[rts==0, idx], 0, clip)
    vals_1 = np.clip(X[rts==1, idx], 0, clip)
    ax.hist(vals_0, bins=40, color=GREEN, alpha=0.6, density=True, label="Collected")
    ax.hist(vals_1, bins=40, color=RED, alpha=0.7, density=True, label="RTS")
    ax.set_title(name, color=BLUE, fontsize=9, pad=4)
    ax.set_ylabel("Density", color=MUTED, fontsize=7)
    # KS stat
    from scipy.stats import ks_2samp
    ks_stat, p_val = ks_2samp(vals_0, vals_1)
    sig = "***" if p_val < 0.001 else "**" if p_val < 0.01 else "*" if p_val < 0.05 else "ns"
    ax.text(0.97, 0.93, f"KS={ks_stat:.2f}{sig}", transform=ax.transAxes,
            ha="right", color=AMBER, fontsize=8)

handles = [
    plt.Rectangle((0,0),1,1, color=GREEN, alpha=0.7, label="Collected"),
    plt.Rectangle((0,0),1,1, color=RED, alpha=0.8, label="RTS"),
]
fig.legend(handles=handles, loc="lower center", ncol=2, facecolor=SURF,
           edgecolor=BORDER, labelcolor=WHITE, fontsize=9, bbox_to_anchor=(0.5, 0))
plt.tight_layout(rect=[0, 0.04, 1, 0.97])
fig.savefig(OUT / "35_feature_distributions.png", dpi=130, bbox_inches="tight", facecolor=DARK)
plt.close()
print("  35 done")


# ── 36: CLV correlation with parcel features ──────────────────────────────────
print("36 CLV correlations...")
# Compute CLV from features
parcel_count   = np.random.poisson(8, N) + 1
avg_order_val  = order_value / np.maximum(parcel_count, 1)
tenure         = np.random.randint(30, 1100, N)
churn_prob     = np.clip(0.3 - parcel_count * 0.02 + np.random.normal(0, 0.05, N), 0.05, 0.8)
clv_hist       = parcel_count * avg_order_val * 0.28
clv_pred       = parcel_count * avg_order_val * 0.28 * (1 - churn_prob)

clv_features = {
    "Parcel Count":      parcel_count,
    "Avg Order Value":   avg_order_val,
    "Tenure (days)":     tenure,
    "Exception Count":   exception_count,
    "RTS Rate":          rts.astype(float),
    "Delivery Cost":     delivery_cost,
    "Dwell Days":        dwell_days,
    "Churn Prob":        churn_prob,
}
clv_corrs = {name: np.corrcoef(vals[:N], clv_hist[:N])[0, 1]
             for name, vals in clv_features.items()}
clv_corrs_pred = {name: np.corrcoef(vals[:N], clv_pred[:N])[0, 1]
                  for name, vals in clv_features.items()}

fig, axes = plt.subplots(1, 2, figsize=(14, 5), facecolor=DARK)
fig.suptitle("CLV Correlation Analysis: Feature Impact on Customer Lifetime Value",
             color=WHITE, fontsize=13, fontweight="bold")

for ax, (corrs, title) in zip(axes, [
    (clv_corrs, "Historical CLV"),
    (clv_corrs_pred, "Predicted 1-Year CLV"),
]):
    apply_dark(ax)
    names = list(corrs.keys())
    vals  = list(corrs.values())
    sort  = sorted(zip(vals, names))
    vals_s, names_s = zip(*sort)
    cols  = [GREEN if v > 0 else RED for v in vals_s]
    bars  = ax.barh(range(len(names_s)), vals_s, color=cols, alpha=0.85, height=0.65)
    ax.set_yticks(range(len(names_s)))
    ax.set_yticklabels(names_s, color=WHITE, fontsize=9)
    ax.axvline(0, color=BORDER, linewidth=1)
    ax.set_xlabel("Pearson r", color=WHITE, fontsize=9)
    ax.set_title(title, color=BLUE, fontsize=11)
    for bar, v in zip(bars, vals_s):
        ax.text(v + (0.005 if v >= 0 else -0.005), bar.get_y() + bar.get_height()/2,
                f"{v:+.3f}", va="center", ha="left" if v >= 0 else "right",
                color=WHITE, fontsize=8)

plt.tight_layout()
fig.savefig(OUT / "36_clv_correlations.png", dpi=150, bbox_inches="tight", facecolor=DARK)
plt.close()
print("  36 done")


# ── 37: Time-series correlation (monthly volume vs month-of-year) ─────────────
print("37 Seasonal correlation...")
months = np.arange(36)
month_of_year = months % 12
trend = 8000 + months * 320
seasonal = 1500 * np.sin(2 * np.pi * months / 12)
noise = np.random.normal(0, 400, 36)
volume = trend + seasonal + noise

# Autocorrelation
max_lag = 18
acf_vals = np.array([
    np.corrcoef(volume[:36-lag], volume[lag:])[0, 1] if lag > 0 else 1.0
    for lag in range(max_lag + 1)
])

fig, axes = plt.subplots(1, 3, figsize=(17, 5), facecolor=DARK)
fig.suptitle("Time-Series Correlation & Seasonal Analysis",
             color=WHITE, fontsize=13, fontweight="bold")

# Autocorrelation
ax = axes[0]
apply_dark(ax)
ax.bar(range(max_lag + 1), acf_vals,
       color=[BLUE if a >= 0 else RED for a in acf_vals], alpha=0.85, width=0.7)
conf = 1.96 / np.sqrt(36)
ax.axhline(conf, color=AMBER, linestyle="--", alpha=0.8, label=f"95% CI ({conf:.2f})")
ax.axhline(-conf, color=AMBER, linestyle="--", alpha=0.8)
ax.axhline(0, color=BORDER, linewidth=1)
ax.set_xlabel("Lag (months)", color=WHITE)
ax.set_ylabel("Autocorrelation (ACF)", color=WHITE)
ax.set_title("Autocorrelation Function", color=BLUE, fontsize=11)
ax.legend(facecolor=SURF, edgecolor=BORDER, labelcolor=WHITE, fontsize=8)

# Volume by month-of-year boxplot proxy
ax = axes[1]
apply_dark(ax)
month_names = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
# Simulate 3 years of monthly data
np.random.seed(42)
monthly_vols = {}
for m in range(12):
    base = 8000 + m * 320 / 12
    seas = 1500 * np.sin(2 * np.pi * m / 12)
    monthly_vols[m] = [base + seas + np.random.normal(0, 500) for _ in range(3)]

bp_data = [monthly_vols[m] for m in range(12)]
positions = range(12)
for pos, (vals, mname) in enumerate(zip(bp_data, month_names)):
    col = GREEN if np.mean(vals) > 9500 else AMBER if np.mean(vals) > 8500 else BLUE
    ax.bar(pos, np.mean(vals), color=col, alpha=0.8, width=0.7)
    ax.errorbar(pos, np.mean(vals), yerr=np.std(vals), color=WHITE, capsize=3, linewidth=1.5)

ax.set_xticks(range(12))
ax.set_xticklabels(month_names, color=WHITE, fontsize=8)
ax.set_ylabel("Mean Monthly Volume", color=WHITE)
ax.set_title("Mean Volume by Month (3-Year Avg)", color=BLUE, fontsize=11)

# Lag scatter: volume[t] vs volume[t-12]
ax = axes[2]
apply_dark(ax)
v_t   = volume[12:]
v_t12 = volume[:24]
r_val = np.corrcoef(v_t12, v_t)[0, 1]
ax.scatter(v_t12, v_t, color=BLUE, alpha=0.6, s=50)
m_fit, b_fit = np.polyfit(v_t12, v_t, 1)
x_line = np.linspace(v_t12.min(), v_t12.max(), 100)
ax.plot(x_line, m_fit * x_line + b_fit, color=RED, linewidth=2, label=f"r={r_val:.3f}")
ax.set_xlabel("Volume (t-12 months)", color=WHITE)
ax.set_ylabel("Volume (t)", color=WHITE)
ax.set_title("Seasonal Lag Scatter: t vs t-12", color=BLUE, fontsize=11)
ax.legend(facecolor=SURF, edgecolor=BORDER, labelcolor=WHITE, fontsize=9)

plt.tight_layout()
fig.savefig(OUT / "37_timeseries_correlation.png", dpi=130, bbox_inches="tight", facecolor=DARK)
plt.close()
print("  37 done")


# ── 38: Delivery cost vs transit time vs parcel value 3-way ──────────────────
print("38 3-way relationship chart...")
fig, axes = plt.subplots(2, 3, figsize=(16, 10), facecolor=DARK)
fig.suptitle("Multi-Feature Relationship Analysis",
             color=WHITE, fontsize=13, fontweight="bold")

sample = np.random.choice(N, 6000, replace=False)
xs = [delivery_cost, transit_hours, parcel_weight, dwell_days, parcel_value, exception_count]
ys = [transit_hours, parcel_value, parcel_value, transit_hours, delivery_cost, dwell_days]
xl = ["Delivery Cost (ZAR)", "Transit Hours", "Weight (kg)", "Dwell Days", "Parcel Value (ZAR)", "Exception Count"]
yl = ["Transit Hours", "Parcel Value (ZAR)", "Parcel Value (ZAR)", "Transit Hours", "Delivery Cost (ZAR)", "Dwell Days"]
clip_x = [500, 200, 10, 15, 5000, 3]
clip_y = [200, 5000, 5000, 200, 500, 15]

for ax, xv, yv, xlb, ylb, cx, cy in zip(axes.flat, xs, ys, xl, yl, clip_x, clip_y):
    apply_dark(ax)
    xp = np.clip(xv[sample], 0, cx)
    yp = np.clip(yv[sample], 0, cy)
    sc = ax.scatter(xp, yp, c=rts[sample],
                    cmap="RdYlGn_r", s=4, alpha=0.35,
                    vmin=0, vmax=1)
    r = np.corrcoef(xp, yp)[0, 1]
    m_fit, b_fit = np.polyfit(xp, yp, 1)
    x_line = np.linspace(xp.min(), xp.max(), 100)
    ax.plot(x_line, m_fit * x_line + b_fit, color=AMBER, linewidth=2,
            label=f"r = {r:.3f}", alpha=0.9)
    ax.set_xlabel(xlb, color=WHITE, fontsize=8)
    ax.set_ylabel(ylb, color=WHITE, fontsize=8)
    ax.set_title(f"{xlb[:18]} vs {ylb[:18]}", color=BLUE, fontsize=9)
    ax.legend(facecolor=SURF, edgecolor=BORDER, labelcolor=WHITE, fontsize=8)

cbar_ax = fig.add_axes([0.92, 0.15, 0.015, 0.7])
cbar_ax.set_facecolor(DARK)
sm = plt.cm.ScalarMappable(cmap="RdYlGn_r", norm=plt.Normalize(0, 1))
sm.set_array([])
cbar = fig.colorbar(sm, cax=cbar_ax)
cbar.set_label("RTS Risk (0=Collected, 1=RTS)", color=WHITE, fontsize=8)
cbar.ax.tick_params(colors=WHITE)
plt.setp(cbar.ax.yaxis.get_ticklabels(), color=WHITE, fontsize=7)

plt.subplots_adjust(right=0.90, hspace=0.38, wspace=0.35)
fig.savefig(OUT / "38_multifeature_relationships.png", dpi=130, bbox_inches="tight", facecolor=DARK)
plt.close()
print("  38 done")


print("\nAll correlation charts generated (plots 30-38).")
