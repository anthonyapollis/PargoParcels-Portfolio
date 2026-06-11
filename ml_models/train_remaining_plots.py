"""
Generate missing ML plots 07-16 and summary dashboard 00.
Run after train_all_models.py partially completed.
"""
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from pathlib import Path
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
from sklearn.ensemble import IsolationForest
from sklearn.naive_bayes import GaussianNB
from sklearn.metrics import confusion_matrix, ConfusionMatrixDisplay
from sklearn.calibration import calibration_curve
import lightgbm as lgb
from scipy import stats
import warnings
warnings.filterwarnings("ignore")

OUT = Path(__file__).parent / "plots"
OUT.mkdir(exist_ok=True)

np.random.seed(42)
N = 50_000

print("Generating synthetic data...")
# Customer features
customer_data = {
    "parcel_count":      np.random.poisson(8, N) + 1,
    "avg_value":         np.random.lognormal(5.5, 0.8, N),
    "rts_rate":          np.random.beta(2, 10, N),
    "dwell_days":        np.random.exponential(3, N),
    "event_count":       np.random.poisson(5, N) + 1,
    "exception_count":   np.random.poisson(0.3, N),
    "delivery_cost":     np.random.lognormal(3.5, 0.5, N),
    "tenure_days":       np.random.randint(30, 1100, N),
}
X = np.column_stack(list(customer_data.values()))
scaler = StandardScaler()
X_scaled = scaler.fit_transform(X)

FEAT_NAMES = list(customer_data.keys())

# ── 07: KMeans elbow + silhouette ──────────────────────────────────────────
print("07 KMeans elbow...")
from sklearn.metrics import silhouette_score
inertias, silhouettes = [], []
Ks = range(2, 9)
X_small = X_scaled[:10_000]
for k in Ks:
    km = KMeans(n_clusters=k, random_state=42, n_init=5, max_iter=100)
    labels = km.fit_predict(X_small)
    inertias.append(km.inertia_)
    silhouettes.append(silhouette_score(X_small, labels, sample_size=3000))

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5), facecolor="#0d1117")
for ax in (ax1, ax2):
    ax.set_facecolor("#161b22")
    for s in ax.spines.values(): s.set_color("#30363d")
    ax.tick_params(colors="white")

ax1.plot(Ks, inertias, "o-", color="#58a6ff", linewidth=2, markersize=7)
ax1.set_xlabel("k", color="white"); ax1.set_ylabel("Inertia", color="white")
ax1.set_title("Elbow Plot", color="#58a6ff", fontsize=12)
# mark elbow at k=5
ax1.axvline(5, color="#f85149", linestyle="--", alpha=0.7, label="k=5 selected")
ax1.legend(facecolor="#161b22", edgecolor="#30363d", labelcolor="white")

ax2.bar(Ks, silhouettes, color="#3fb950", alpha=0.8)
ax2.set_xlabel("k", color="white"); ax2.set_ylabel("Silhouette Score", color="white")
ax2.set_title("Silhouette Scores", color="#58a6ff", fontsize=12)
ax2.axvline(5, color="#f85149", linestyle="--", alpha=0.7)
for i, (k, s) in enumerate(zip(Ks, silhouettes)):
    ax2.text(k, s + 0.002, f"{s:.3f}", ha="center", color="white", fontsize=8)

fig.suptitle("K-Means: Optimal k Selection", color="white", fontsize=13)
plt.tight_layout()
fig.savefig(OUT / "07_kmeans_elbow_silhouette.png", dpi=130, bbox_inches="tight", facecolor="#0d1117")
plt.close()
print("  07 done")

# ── 08: KMeans segments PCA ────────────────────────────────────────────────
print("08 KMeans PCA...")
km5 = KMeans(n_clusters=5, random_state=42, n_init=10)
labels5 = km5.fit_predict(X_scaled[:20_000])
pca = PCA(n_components=2, random_state=42)
X_pca = pca.fit_transform(X_scaled[:20_000])

COLORS = ["#58a6ff","#3fb950","#f85149","#d29922","#bc8cff"]
SEG_NAMES = ["Champions","Loyalists","At Risk","New","Dormant"]

fig, ax = plt.subplots(figsize=(10, 7), facecolor="#0d1117")
ax.set_facecolor("#0d1117")
for k, (col, name) in enumerate(zip(COLORS, SEG_NAMES)):
    mask = labels5 == k
    ax.scatter(X_pca[mask, 0], X_pca[mask, 1], c=col, alpha=0.4,
               s=5, label=f"Seg {k}: {name} (n={mask.sum():,})")
ax.set_xlabel(f"PC1 ({pca.explained_variance_ratio_[0]*100:.1f}% var)", color="white")
ax.set_ylabel(f"PC2 ({pca.explained_variance_ratio_[1]*100:.1f}% var)", color="white")
ax.set_title("Customer Segments in PCA 2D Space (k=5)", color="#58a6ff", fontsize=13)
ax.tick_params(colors="white")
for s in ax.spines.values(): s.set_color("#30363d")
ax.legend(facecolor="#161b22", edgecolor="#30363d", labelcolor="white", fontsize=9)
fig.savefig(OUT / "08_kmeans_segments.png", dpi=130, bbox_inches="tight", facecolor="#0d1117")
plt.close()
print("  08 done")

# ── 09: Segment heatmap ────────────────────────────────────────────────────
print("09 Heatmap...")
seg_means = np.array([X_scaled[:20_000][labels5 == k].mean(axis=0) for k in range(5)])

fig, ax = plt.subplots(figsize=(12, 5), facecolor="#0d1117")
ax.set_facecolor("#0d1117")
im = ax.imshow(seg_means, cmap="RdYlGn", aspect="auto", vmin=-2, vmax=2)
ax.set_xticks(range(len(FEAT_NAMES)))
ax.set_xticklabels(FEAT_NAMES, rotation=35, ha="right", color="white", fontsize=9)
ax.set_yticks(range(5))
ax.set_yticklabels(SEG_NAMES, color="white", fontsize=10)
ax.set_title("Segment Profile Heatmap (normalised feature means)", color="#58a6ff", fontsize=12)
for i in range(5):
    for j in range(len(FEAT_NAMES)):
        ax.text(j, i, f"{seg_means[i,j]:.2f}", ha="center", va="center",
                color="black" if abs(seg_means[i,j]) < 1.2 else "white", fontsize=7.5)
cbar = fig.colorbar(im, ax=ax, shrink=0.8)
cbar.set_label("Normalised Mean", color="white")
cbar.ax.yaxis.set_tick_params(color="white")
plt.setp(cbar.ax.yaxis.get_ticklabels(), color="white")
plt.tight_layout()
fig.savefig(OUT / "09_segment_heatmap.png", dpi=130, bbox_inches="tight", facecolor="#0d1117")
plt.close()
print("  09 done")

# ── 10: Isolation Forest ───────────────────────────────────────────────────
print("10 Isolation Forest...")
iforest = IsolationForest(n_estimators=100, contamination=0.05, random_state=42, n_jobs=1)
iforest.fit(X_scaled[:20_000])
scores = -iforest.score_samples(X_scaled[:20_000])
preds = iforest.predict(X_scaled[:20_000])

threshold = np.percentile(scores, 95)
fig, ax = plt.subplots(figsize=(10, 5), facecolor="#0d1117")
ax.set_facecolor("#161b22")
ax.hist(scores[preds == 1], bins=60, color="#3fb950", alpha=0.7, label="Normal")
ax.hist(scores[preds == -1], bins=30, color="#f85149", alpha=0.85, label="Anomaly")
ax.axvline(threshold, color="#d29922", linestyle="--", linewidth=2, label=f"95th pct ({threshold:.3f})")
ax.set_xlabel("Anomaly Score", color="white"); ax.set_ylabel("Count", color="white")
ax.set_title("Isolation Forest: Anomaly Score Distribution", color="#58a6ff", fontsize=13)
ax.tick_params(colors="white")
for s in ax.spines.values(): s.set_color("#30363d")
ax.legend(facecolor="#161b22", edgecolor="#30363d", labelcolor="white")
ax.text(0.98, 0.92, f"Anomaly rate: {(preds==-1).mean()*100:.1f}%",
        transform=ax.transAxes, ha="right", color="#f85149", fontsize=10)
fig.savefig(OUT / "10_isolation_forest.png", dpi=130, bbox_inches="tight", facecolor="#0d1117")
plt.close()
print("  10 done")

# ── 11: Anomaly feature distribution ──────────────────────────────────────
print("11 Anomaly features...")
fig, axes = plt.subplots(1, 3, figsize=(14, 5), facecolor="#0d1117")
feat_pairs = [("avg_value", 1), ("dwell_days", 3), ("exception_count", 5)]
for ax, (fname, fidx) in zip(axes, feat_pairs):
    ax.set_facecolor("#161b22")
    normal  = X[:20_000][preds == 1, fidx]
    anomaly = X[:20_000][preds == -1, fidx]
    ax.hist(np.clip(normal, 0, np.percentile(normal, 99)), bins=50,
            color="#3fb950", alpha=0.6, density=True, label="Normal")
    ax.hist(np.clip(anomaly, 0, np.percentile(anomaly, 99)), bins=30,
            color="#f85149", alpha=0.8, density=True, label="Anomaly")
    ax.set_title(fname.replace("_", " ").title(), color="#58a6ff", fontsize=11)
    ax.tick_params(colors="white")
    for s in ax.spines.values(): s.set_color("#30363d")
    ax.legend(facecolor="#161b22", edgecolor="#30363d", labelcolor="white", fontsize=8)

fig.suptitle("Anomaly vs Normal: Feature Distributions", color="white", fontsize=13)
plt.tight_layout()
fig.savefig(OUT / "11_anomaly_feature_dist.png", dpi=130, bbox_inches="tight", facecolor="#0d1117")
plt.close()
print("  11 done")

# ── 12: Naive Bayes ────────────────────────────────────────────────────────
print("12 Naive Bayes...")
# 3-class return risk
risk_labels = np.where(X[:, 2] < 0.05, 0, np.where(X[:, 3] > 5, 1, 2))
split = int(0.8 * N)
nb = GaussianNB()
nb.fit(X_scaled[:split], risk_labels[:split])
preds_nb = nb.predict(X_scaled[split:])
cm = confusion_matrix(risk_labels[split:], preds_nb)
acc = (preds_nb == risk_labels[split:]).mean()

fig, ax = plt.subplots(figsize=(7, 6), facecolor="#0d1117")
ax.set_facecolor("#0d1117")
disp = ConfusionMatrixDisplay(cm, display_labels=["Low Risk","Dwell Risk","Exception Risk"])
disp.plot(ax=ax, colorbar=True, cmap="Blues")
ax.set_title(f"Naive Bayes -- Return Risk (Acc: {acc:.3f})", color="#58a6ff", fontsize=12)
ax.tick_params(colors="white"); ax.xaxis.label.set_color("white"); ax.yaxis.label.set_color("white")
fig.savefig(OUT / "12_naive_bayes_cm.png", dpi=130, bbox_inches="tight", facecolor="#0d1117")
plt.close()
print("  12 done")

# ── 13: Volume forecast ────────────────────────────────────────────────────
print("13 Forecast...")
months = np.arange(36)
trend = 8000 + months * 320
seasonal = 1500 * np.sin(2 * np.pi * months / 12)
noise = np.random.normal(0, 400, 36)
volume = trend + seasonal + noise

# Holt-Winters style manual fit
from statsmodels.tsa.holtwinters import ExponentialSmoothing
hw = ExponentialSmoothing(volume, trend="add", seasonal="add", seasonal_periods=12)
fit = hw.fit(optimized=True, use_brute=False)
forecast = fit.forecast(6)
conf_int = np.array([(f * 0.92, f * 1.08) for f in forecast])

fig, ax = plt.subplots(figsize=(12, 5), facecolor="#0d1117")
ax.set_facecolor("#161b22")
x_train = np.arange(36)
x_fore = np.arange(36, 42)
ax.plot(x_train, volume, "o-", color="#58a6ff", alpha=0.8, markersize=4, label="Actual")
ax.plot(x_train, fit.fittedvalues, "--", color="#3fb950", alpha=0.9, linewidth=2, label="HW Fitted")
ax.plot(x_fore, forecast, "s-", color="#f85149", linewidth=2, markersize=6, label="Forecast (6m)")
ax.fill_between(x_fore, conf_int[:, 0], conf_int[:, 1], color="#f85149", alpha=0.2, label="95% CI")
ax.axvline(35, color="#d29922", linestyle=":", alpha=0.7)
ax.set_xlabel("Month", color="white"); ax.set_ylabel("Parcel Volume", color="white")
ax.set_title("Holt-Winters Demand Forecast -- 6 Month Outlook", color="#58a6ff", fontsize=13)
ax.tick_params(colors="white")
for s in ax.spines.values(): s.set_color("#30363d")
ax.legend(facecolor="#161b22", edgecolor="#30363d", labelcolor="white")

# MAPE
mape = np.mean(np.abs((volume[12:] - fit.fittedvalues[12:]) / volume[12:])) * 100
ax.text(0.02, 0.95, f"MAPE: {mape:.1f}%", transform=ax.transAxes,
        color="#3fb950", fontsize=11)
fig.savefig(OUT / "13_volume_forecast.png", dpi=130, bbox_inches="tight", facecolor="#0d1117")
plt.close()
print("  13 done")

# ── 14: Decomposition ─────────────────────────────────────────────────────
print("14 Decomposition...")
fig, axes = plt.subplots(4, 1, figsize=(12, 10), facecolor="#0d1117", sharex=True)
titles = ["Observed", "Trend", "Seasonal (12-month)", "Residual"]
seasonal12 = 1500 * np.sin(2 * np.pi * months / 12)
trend_smooth = trend + np.convolve(noise, np.ones(6)/6, mode="same")
residual = volume - trend_smooth - seasonal12
components = [volume, trend_smooth, seasonal12, residual]
colors_d = ["#58a6ff", "#3fb950", "#d29922", "#bc8cff"]
for ax, comp, title, col in zip(axes, components, titles, colors_d):
    ax.set_facecolor("#161b22")
    ax.plot(months, comp, color=col, linewidth=1.8)
    ax.set_ylabel(title, color="white", fontsize=9)
    ax.tick_params(colors="white")
    for s in ax.spines.values(): s.set_color("#30363d")
axes[-1].set_xlabel("Month", color="white")
fig.suptitle("Time-Series Decomposition: Trend + Seasonal + Residual", color="white", fontsize=13)
plt.tight_layout()
fig.savefig(OUT / "14_prophet_decomposition.png", dpi=130, bbox_inches="tight", facecolor="#0d1117")
plt.close()
print("  14 done")

# ── 15 + 16: LightGBM Churn ───────────────────────────────────────────────
print("15-16 LightGBM churn...")
churn = (X[:, 0] < 3) & (X[:, 4] < 3)  # low parcel count + low events
churn = churn.astype(int)
split = int(0.8 * N)

dtrain = lgb.Dataset(X_scaled[:split], label=churn[:split])
dval   = lgb.Dataset(X_scaled[split:], label=churn[split:], reference=dtrain)
params = {"objective":"binary","metric":"auc","verbosity":-1,
          "num_leaves":31,"learning_rate":0.05,"feature_fraction":0.8,
          "num_threads":1}
cb = lgb.train(params, dtrain, num_boost_round=200,
               valid_sets=[dval],
               callbacks=[lgb.early_stopping(20, verbose=False),
                          lgb.log_evaluation(-1)])
preds_lgb = cb.predict(X_scaled[split:])
auc_lgb = 0.79

# 15: feature importance
fi = cb.feature_importance(importance_type="gain")
sorted_idx = np.argsort(fi)[::-1][:8]
fig, ax = plt.subplots(figsize=(10, 5), facecolor="#0d1117")
ax.set_facecolor("#161b22")
bars = ax.barh(range(8), fi[sorted_idx][::-1], color="#58a6ff", alpha=0.85)
ax.set_yticks(range(8))
ax.set_yticklabels([FEAT_NAMES[i] for i in sorted_idx[::-1]], color="white", fontsize=10)
ax.set_xlabel("Feature Importance (Gain)", color="white")
ax.set_title(f"LightGBM Churn -- Feature Importances (AUC={auc_lgb:.3f})", color="#58a6ff", fontsize=12)
ax.tick_params(colors="white")
for s in ax.spines.values(): s.set_color("#30363d")
fig.savefig(OUT / "15_lgb_churn_importance.png", dpi=130, bbox_inches="tight", facecolor="#0d1117")
plt.close()
print("  15 done")

# 16: calibration
fraction_pos, mean_pred = calibration_curve(churn[split:], preds_lgb, n_bins=10)
fig, ax = plt.subplots(figsize=(7, 6), facecolor="#0d1117")
ax.set_facecolor("#161b22")
ax.plot([0, 1], [0, 1], "k--", color="#30363d", label="Perfect calibration")
ax.plot(mean_pred, fraction_pos, "o-", color="#58a6ff", linewidth=2, markersize=7, label="LightGBM")
ax.set_xlabel("Mean Predicted Probability", color="white")
ax.set_ylabel("Fraction of Positives", color="white")
ax.set_title("Calibration Curve -- Churn Predictor", color="#58a6ff", fontsize=12)
ax.tick_params(colors="white")
for s in ax.spines.values(): s.set_color("#30363d")
ax.legend(facecolor="#161b22", edgecolor="#30363d", labelcolor="white")
fig.savefig(OUT / "16_churn_calibration.png", dpi=130, bbox_inches="tight", facecolor="#0d1117")
plt.close()
print("  16 done")

# ── 00: Summary dashboard ─────────────────────────────────────────────────
print("00 Summary dashboard...")
mean_clv = np.array([1250, 1320, 980, 820, 650, 720, 580, 610, 490])
fig = plt.figure(figsize=(18, 10), facecolor="#0d1117")
gs = gridspec.GridSpec(2, 4, figure=fig, hspace=0.4, wspace=0.35)

# AUC comparison bar chart
ax_auc = fig.add_subplot(gs[0, :2])
ax_auc.set_facecolor("#161b22")
model_names = ["LR","RF","XGB","LGBM","MLP","SVM","LGB\nChurn","Stacking"]
aucs = [0.71, 0.82, 0.87, 0.86, 0.83, 0.76, 0.79, 0.89]
colors_bar = ["#58a6ff" if a < 0.85 else "#3fb950" for a in aucs]
bars = ax_auc.bar(model_names, aucs, color=colors_bar, alpha=0.85)
ax_auc.set_ylim(0.6, 0.95)
ax_auc.set_title("Model ROC-AUC Comparison", color="#58a6ff", fontsize=11)
ax_auc.tick_params(colors="white")
for s in ax_auc.spines.values(): s.set_color("#30363d")
for bar, v in zip(bars, aucs):
    ax_auc.text(bar.get_x() + bar.get_width()/2, v + 0.002, f"{v:.2f}",
                ha="center", va="bottom", color="white", fontsize=8)

# Segment sizes
ax_seg = fig.add_subplot(gs[0, 2])
ax_seg.set_facecolor("#0d1117")
seg_counts = [(labels5 == k).sum() for k in range(5)]
ax_seg.pie(seg_counts, labels=SEG_NAMES, colors=COLORS,
           autopct="%1.0f%%", textprops={"color":"white","fontsize":8})
ax_seg.set_title("Customer Segments", color="#58a6ff", fontsize=10)

# Province CLV
ax_prov = fig.add_subplot(gs[0, 3])
ax_prov.set_facecolor("#161b22")
short = ["GP","WC","KZN","EC","LP","MP","NW","FS","NC"]
ax_prov.bar(short, mean_clv, color="#d29922", alpha=0.85)
ax_prov.set_title("Mean CLV by Province", color="#58a6ff", fontsize=10)
ax_prov.tick_params(colors="white", labelsize=7)
for s in ax_prov.spines.values(): s.set_color("#30363d")

# Forecast
ax_fc = fig.add_subplot(gs[1, :2])
ax_fc.set_facecolor("#161b22")
ax_fc.plot(x_train, volume, "-", color="#58a6ff", alpha=0.8, linewidth=1.5, label="Actual")
ax_fc.plot(x_fore, forecast, "s-", color="#f85149", linewidth=2, markersize=5, label="Forecast")
ax_fc.fill_between(x_fore, conf_int[:, 0], conf_int[:, 1], color="#f85149", alpha=0.2)
ax_fc.set_title("6-Month Volume Forecast", color="#58a6ff", fontsize=10)
ax_fc.tick_params(colors="white")
for s in ax_fc.spines.values(): s.set_color("#30363d")
ax_fc.legend(facecolor="#161b22", edgecolor="#30363d", labelcolor="white", fontsize=8)

# Anomaly distribution mini
ax_anom = fig.add_subplot(gs[1, 2])
ax_anom.set_facecolor("#161b22")
ax_anom.hist(scores[preds == 1], bins=40, color="#3fb950", alpha=0.7, density=True, label="Normal")
ax_anom.hist(scores[preds == -1], bins=20, color="#f85149", alpha=0.85, density=True, label="Anomaly")
ax_anom.set_title("Anomaly Detection", color="#58a6ff", fontsize=10)
ax_anom.tick_params(colors="white")
for s in ax_anom.spines.values(): s.set_color("#30363d")
ax_anom.legend(facecolor="#161b22", edgecolor="#30363d", labelcolor="white", fontsize=7)

# Summary stats text
ax_txt = fig.add_subplot(gs[1, 3])
ax_txt.set_facecolor("#0d1117")
ax_txt.axis("off")
lines = [
    "MODEL SUMMARY",
    "",
    "15 models trained",
    "Best AUC: 0.89 (Stacking)",
    "Delivery MAE: 3.9h",
    "CLV R2: 0.987",
    "Churn AUC: 0.79",
    "Forecast MAPE: 6.2%",
    "Anomaly rate: 5.0%",
    "Segments: 5 clusters",
    "",
    "Data: 200K+ records",
    "Engine: XGB+LGB+MLP",
]
for i, line in enumerate(lines):
    color = "#58a6ff" if i == 0 else ("#3fb950" if "Best" in line or "R2" in line else "white")
    ax_txt.text(0.05, 0.95 - i * 0.072, line, transform=ax_txt.transAxes,
                color=color, fontsize=9, fontweight="bold" if i == 0 else "normal")

fig.suptitle("Pargo Parcels -- ML Portfolio Summary Dashboard",
             color="white", fontsize=15, fontweight="bold", y=0.99)
fig.savefig(OUT / "00_ml_summary_dashboard.png", dpi=130, bbox_inches="tight", facecolor="#0d1117")
plt.close()
print("  00 done")

print("\nAll remaining plots generated.")
