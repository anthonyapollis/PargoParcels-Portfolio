"""
Geographical chart of customer location by SA province.
Generates:
  22_sa_province_map.png  -- choropleth map (customer density + CLV)
  23_province_rts_rates.png -- province bar chart
"""
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyArrowPatch
from pathlib import Path
import sys, os

OUT = Path(__file__).parent / "plots"
OUT.mkdir(exist_ok=True)

# Province data from CLV synthetic data (matches train_clv.py distribution)
PROVINCES = [
    "Gauteng", "Western Cape", "KwaZulu-Natal", "Eastern Cape",
    "Limpopo", "Mpumalanga", "North West", "Free State", "Northern Cape"
]

# Population-weighted customer distribution (matches data generator)
np.random.seed(42)
WEIGHTS = np.array([0.35, 0.20, 0.18, 0.10, 0.06, 0.05, 0.03, 0.02, 0.01])
N_CUSTOMERS = 300_000
counts = (WEIGHTS * N_CUSTOMERS).astype(int)
counts[-1] = N_CUSTOMERS - counts[:-1].sum()

mean_clv    = np.array([1250, 1320, 980, 820, 650, 720, 580, 610, 490])
mean_rts    = np.array([0.142, 0.118, 0.161, 0.183, 0.198, 0.175, 0.191, 0.172, 0.210])
order_freq  = np.array([4.8, 5.1, 3.9, 3.2, 2.8, 3.1, 2.6, 2.7, 2.1])

# ── 22: SA Province choropleth-style bar map ──────────────────────────────────
fig, axes = plt.subplots(1, 2, figsize=(16, 8), facecolor="#0d1117")
fig.suptitle("South Africa -- Customer Geography by Province",
             color="white", fontsize=16, fontweight="bold", y=0.98)

# Left: simplified SA province map (SVG-style rectangles as proxies)
# Approximate layout positions (x, y, w, h) on a 10x8 grid
LAYOUT = {
    "Northern Cape":  (0.5, 2.0, 3.5, 3.0),
    "Western Cape":   (0.5, 0.0, 3.0, 2.2),
    "Eastern Cape":   (3.5, 0.0, 3.5, 2.5),
    "Free State":     (3.8, 2.5, 2.5, 2.0),
    "North West":     (3.5, 4.5, 2.2, 2.0),
    "Gauteng":        (5.7, 4.5, 1.8, 1.5),
    "Mpumalanga":     (7.0, 4.0, 2.5, 2.0),
    "Limpopo":        (5.5, 6.0, 3.5, 2.2),
    "KwaZulu-Natal":  (6.5, 1.5, 2.5, 2.8),
}

ax = axes[0]
ax.set_facecolor("#0d1117")
ax.set_xlim(0, 10)
ax.set_ylim(-0.5, 9)
ax.set_aspect("equal")
ax.axis("off")
ax.set_title("Customer Density by Province", color="#58a6ff", fontsize=12, pad=10)

# Color scale: customer count normalised
norm_counts = counts / counts.max()
cmap = plt.cm.YlOrRd

prov_idx = {p: i for i, p in enumerate(PROVINCES)}
for prov, (x, y, w, h) in LAYOUT.items():
    idx = prov_idx[prov]
    color = cmap(0.2 + 0.78 * norm_counts[idx])
    rect = plt.Rectangle((x, y), w, h, facecolor=color,
                          edgecolor="#30363d", linewidth=1.5)
    ax.add_patch(rect)
    # Label
    short = {"KwaZulu-Natal": "KZN", "Northern Cape": "NC",
             "Western Cape": "WC", "Eastern Cape": "EC",
             "North West": "NW", "Mpumalanga": "MP",
             "Free State": "FS", "Limpopo": "LP", "Gauteng": "GP"}.get(prov, prov[:3])
    ax.text(x + w/2, y + h*0.6, short,
            ha="center", va="center", color="black", fontsize=9, fontweight="bold")
    ax.text(x + w/2, y + h*0.25, f"{counts[idx]/1000:.0f}K",
            ha="center", va="center", color="black", fontsize=7.5)

# Colorbar
sm = plt.cm.ScalarMappable(cmap=cmap, norm=plt.Normalize(0, counts.max()))
sm.set_array([])
cbar = fig.colorbar(sm, ax=ax, orientation="vertical", shrink=0.6, pad=0.02)
cbar.set_label("Customer Count", color="white", fontsize=9)
cbar.ax.yaxis.set_tick_params(color="white")
plt.setp(cbar.ax.yaxis.get_ticklabels(), color="white", fontsize=8)

# Right: horizontal bar charts (CLV + RTS)
ax2 = axes[1]
ax2.set_facecolor("#0d1117")

y_pos = np.arange(len(PROVINCES))
bar_clv = ax2.barh(y_pos + 0.25, mean_clv, height=0.45,
                   color=["#f85149" if r > 0.18 else "#3fb950" if r < 0.15 else "#d29922"
                          for r in mean_rts], alpha=0.85, label="Mean CLV (ZAR)")

ax2_rts = ax2.twinx()
ax2_rts.set_facecolor("#0d1117")
bar_rts = ax2_rts.barh(y_pos - 0.25, mean_rts * 100, height=0.45,
                       color="#58a6ff", alpha=0.55, label="RTS Rate (%)")
ax2_rts.set_xlabel("RTS Rate (%)", color="#58a6ff", fontsize=9)
ax2_rts.tick_params(axis="x", colors="#58a6ff")
ax2_rts.spines["bottom"].set_color("#30363d")
ax2_rts.spines["top"].set_visible(False)
ax2_rts.spines["left"].set_visible(False)
ax2_rts.spines["right"].set_color("#30363d")
ax2_rts.set_xlim(0, 30)

ax2.set_yticks(y_pos)
ax2.set_yticklabels(PROVINCES, color="white", fontsize=9)
ax2.set_xlabel("Mean Customer LTV (ZAR)", color="white", fontsize=9)
ax2.set_title("Mean CLV vs RTS Rate by Province", color="#58a6ff", fontsize=12, pad=10)
ax2.tick_params(colors="white")
for spine in ax2.spines.values():
    spine.set_color("#30363d")
ax2.set_facecolor("#0d1117")

# CLV value labels
for i, (v, r) in enumerate(zip(mean_clv, mean_rts)):
    ax2.text(v + 15, i + 0.25, f"R{v:,}", va="center", color="white", fontsize=7.5)
    ax2_rts.text(r * 100 + 0.3, i - 0.25, f"{r*100:.1f}%", va="center",
                 color="#58a6ff", fontsize=7.5)

legend_patches = [
    mpatches.Patch(color="#3fb950", label="Low RTS (<15%)"),
    mpatches.Patch(color="#d29922", label="Mid RTS (15-18%)"),
    mpatches.Patch(color="#f85149", label="High RTS (>18%)"),
    mpatches.Patch(color="#58a6ff", alpha=0.55, label="RTS Rate"),
]
ax2.legend(handles=legend_patches, loc="lower right",
           facecolor="#161b22", edgecolor="#30363d",
           labelcolor="white", fontsize=8)

plt.tight_layout(rect=[0, 0, 1, 0.96])
fig.savefig(OUT / "22_sa_province_map.png", dpi=150, bbox_inches="tight",
            facecolor="#0d1117")
plt.close()
print("  Saved 22_sa_province_map.png")

# ── 23: Province detail bar chart ────────────────────────────────────────────
fig, axes = plt.subplots(1, 3, figsize=(18, 6), facecolor="#0d1117")
fig.suptitle("Province Performance Dashboard -- Pargo Parcels",
             color="white", fontsize=14, fontweight="bold")

metrics = [
    ("Customer Count", counts / 1000, "K customers", "#58a6ff"),
    ("Mean CLV (ZAR)", mean_clv, "ZAR", "#3fb950"),
    ("RTS Rate (%)", mean_rts * 100, "%", "#f85149"),
]

short_names = ["GP", "WC", "KZN", "EC", "LP", "MP", "NW", "FS", "NC"]

for ax, (title, vals, unit, color) in zip(axes, metrics):
    ax.set_facecolor("#161b22")
    sort_idx = np.argsort(vals)[::-1]
    bars = ax.bar(range(9), vals[sort_idx], color=color, alpha=0.8, width=0.7)
    ax.set_xticks(range(9))
    ax.set_xticklabels([short_names[i] for i in sort_idx], color="white", fontsize=9)
    ax.tick_params(axis="y", colors="white")
    ax.set_title(title, color="#58a6ff", fontsize=11, pad=8)
    ax.set_ylabel(unit, color="white", fontsize=9)
    for spine in ax.spines.values():
        spine.set_color("#30363d")
    ax.set_facecolor("#161b22")
    # value labels on bars
    for bar, v in zip(bars, vals[sort_idx]):
        if unit == "%":
            label = f"{v:.1f}%"
        elif unit == "ZAR":
            label = f"R{v:,.0f}"
        else:
            label = f"{v:.0f}K"
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + vals.max()*0.01,
                label, ha="center", va="bottom", color="white", fontsize=7.5)

plt.tight_layout()
fig.savefig(OUT / "23_province_detail.png", dpi=150, bbox_inches="tight",
            facecolor="#0d1117")
plt.close()
print("  Saved 23_province_detail.png")

print("\nGeographic charts done.")
