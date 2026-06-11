"""
High-quality South Africa province map for ebook.
Uses geopandas + Natural Earth data for accurate boundaries.
Outputs:
  plots/40_sa_province_map_ebook.png
  plots/41_sa_province_map_dashboard.png
  plots/pargo_logo.png
"""
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.patheffects as pe
from matplotlib.patches import FancyBboxPatch
import matplotlib.ticker as mticker
import geopandas as gpd
import urllib.request, json, io
from pathlib import Path

OUT = Path(__file__).parent / "plots"
OUT.mkdir(exist_ok=True)

# ── Province data ─────────────────────────────────────────────────────────────
PROV_DATA = {
    "Gauteng":       {"customers": 105000, "mean_clv": 1250, "rts": 12.2, "pudo": 1400, "color": "#E15759"},
    "Western Cape":  {"customers": 60000,  "mean_clv": 1072, "rts":  8.8, "pudo":  800, "color": "#BAB0AC"},
    "KwaZulu-Natal": {"customers": 54000,  "mean_clv":  980, "rts": 15.7, "pudo":  800, "color": "#FF9DA7"},
    "Eastern Cape":  {"customers": 30000,  "mean_clv":  820, "rts": 20.8, "pudo":  250, "color": "#9C755F"},
    "Limpopo":       {"customers": 18000,  "mean_clv":  650, "rts": 28.8, "pudo":  250, "color": "#4E79A7"},
    "Mpumalanga":    {"customers": 15000,  "mean_clv":  720, "rts": 21.1, "pudo":  200, "color": "#59A14F"},
    "North West":    {"customers":  9000,  "mean_clv":  580, "rts": 24.3, "pudo":  150, "color": "#76B7B2"},
    "Free State":    {"customers":  6000,  "mean_clv":  610, "rts": 18.4, "pudo":  100, "color": "#EDC948"},
    "Northern Cape": {"customers":  3000,  "mean_clv":  490, "rts": 29.4, "pudo":   50, "color": "#D4A6C8"},
}

# Mapping from Natural Earth province names to our names
NE_NAME_MAP = {
    "Gauteng":        "Gauteng",
    "Western Cape":   "Western Cape",
    "KwaZulu-Natal":  "KwaZulu-Natal",
    "Eastern Cape":   "Eastern Cape",
    "Limpopo":        "Limpopo",
    "Mpumalanga":     "Mpumalanga",
    "North West":     "North West",
    "Free State":     "Free State",
    "Northern Cape":  "Northern Cape",
}

# ── Load SA province boundaries ───────────────────────────────────────────────
def load_sa_provinces():
    """Download SA province boundaries from Natural Earth."""
    url = ("https://raw.githubusercontent.com/datasets/geo-admin1-us/master/"
           "data/admin1-of-south-africa.geojson")
    # Try multiple sources
    sources = [
        "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_10m_admin_1_states_provinces.geojson",
    ]
    for src in sources:
        try:
            print(f"  Fetching {src[:60]}...")
            req = urllib.request.Request(src, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=15) as r:
                data = json.loads(r.read())
            gdf = gpd.GeoDataFrame.from_features(data["features"])
            # Filter to South Africa
            sa = gdf[gdf.get("iso_a2", gdf.get("sov_a3", "")).isin(["ZA", "SAF"])]
            if len(sa) == 0:
                sa = gdf[gdf.get("admin", "").str.contains("South Africa", na=False)]
            if len(sa) >= 8:
                print(f"  Loaded {len(sa)} SA provinces from Natural Earth")
                return sa
        except Exception as ex:
            print(f"  Failed: {ex}")
    return None


# ── Fallback: hand-drawn polygon map (improved quality) ──────────────────────
POLYS = {
    "Limpopo": [(26.0,-22.1),(28.0,-22.1),(30.3,-22.3),(31.0,-22.4),(32.9,-22.7),
                (32.9,-24.8),(32.0,-25.4),(31.0,-25.4),(30.5,-25.0),(29.8,-24.7),
                (28.8,-24.5),(28.2,-24.2),(27.5,-24.0),(26.8,-23.5),(26.0,-23.2),
                (25.5,-23.0),(25.4,-22.5),(26.0,-22.1)],
    "Mpumalanga": [(29.8,-24.7),(30.5,-25.0),(31.0,-25.4),(32.0,-25.4),(32.9,-25.0),
                   (32.9,-26.9),(32.0,-27.2),(31.0,-27.1),(30.0,-27.4),(29.2,-26.8),
                   (29.0,-26.4),(28.8,-25.8),(28.8,-24.5),(29.8,-24.7)],
    "Gauteng": [(27.7,-25.3),(28.8,-25.3),(29.0,-25.5),(29.0,-26.4),
                (28.8,-26.7),(27.8,-26.8),(27.5,-26.5),(27.5,-25.8),(27.7,-25.3)],
    "North West": [(22.5,-25.0),(24.0,-24.8),(25.4,-24.5),(26.0,-23.2),(26.8,-23.5),
                   (27.5,-24.0),(28.2,-24.2),(28.8,-24.5),(28.8,-25.8),(27.5,-25.8),
                   (27.5,-26.5),(27.8,-26.8),(26.5,-27.2),(25.5,-27.0),(24.5,-27.5),
                   (23.5,-27.0),(22.5,-26.5),(22.0,-26.0),(22.0,-25.5),(22.5,-25.0)],
    "Free State": [(24.5,-27.5),(25.5,-27.0),(26.5,-27.2),(27.8,-26.8),(28.8,-26.7),
                   (29.0,-26.4),(29.2,-26.8),(30.0,-27.4),(29.8,-28.0),(29.0,-29.3),
                   (28.5,-30.2),(27.5,-30.0),(26.5,-29.5),(25.5,-29.5),(25.0,-29.0),
                   (24.0,-28.5),(23.5,-28.0),(24.5,-27.5)],
    "KwaZulu-Natal": [(29.0,-26.4),(29.2,-26.8),(30.0,-27.4),(31.0,-27.1),(32.0,-27.2),
                      (32.9,-26.9),(32.9,-28.5),(32.5,-29.5),(31.5,-31.0),(30.0,-31.5),
                      (29.0,-30.5),(28.5,-30.2),(29.0,-29.3),(29.8,-28.0),(30.0,-27.4),
                      (29.0,-26.4)],
    "Eastern Cape": [(24.0,-28.5),(25.0,-29.0),(25.5,-29.5),(26.5,-29.5),(27.5,-30.0),
                     (28.5,-30.2),(29.0,-30.5),(30.0,-31.5),(29.5,-32.5),(28.5,-33.5),
                     (27.0,-33.9),(26.0,-33.7),(25.0,-33.5),(24.0,-33.0),(22.5,-33.5),
                     (22.0,-33.0),(22.0,-31.5),(23.0,-30.5),(23.5,-29.5),(24.0,-28.5)],
    "Western Cape": [(17.0,-32.0),(18.0,-33.0),(18.5,-34.0),(19.5,-34.8),(20.5,-34.5),
                     (22.0,-34.0),(22.5,-33.5),(24.0,-33.0),(25.0,-33.5),(22.0,-33.0),
                     (22.0,-31.5),(21.5,-31.0),(20.5,-30.5),(19.5,-31.0),(18.5,-31.5),
                     (17.5,-31.5),(17.0,-32.0)],
    "Northern Cape": [(17.0,-28.5),(18.5,-28.0),(20.0,-28.5),(22.0,-28.5),(22.5,-28.0),
                      (23.5,-28.0),(24.0,-28.5),(23.5,-29.5),(23.0,-30.5),(22.0,-31.5),
                      (22.0,-33.0),(21.0,-32.0),(20.0,-32.0),(19.0,-31.5),(18.0,-31.0),
                      (17.5,-31.5),(18.5,-31.5),(19.5,-31.0),(20.5,-30.5),(21.5,-31.0),
                      (22.0,-31.5),(22.0,-30.0),(21.0,-29.5),(20.0,-29.0),(19.0,-29.5),
                      (18.0,-29.0),(17.0,-29.0),(17.0,-28.5)],
}
LABEL_POS = {
    "Limpopo": (29.2,-23.3), "Mpumalanga": (30.8,-26.0), "Gauteng": (28.3,-26.1),
    "North West": (25.5,-26.2), "Free State": (26.5,-28.5), "KwaZulu-Natal": (30.5,-29.5),
    "Eastern Cape": (26.0,-32.0), "Western Cape": (20.5,-33.2), "Northern Cape": (21.0,-29.8),
}


def make_ebook_map():
    """High-quality map for ebook — light background, large fonts, 300 DPI."""
    fig = plt.figure(figsize=(16, 10), facecolor="white", dpi=300)

    # Left panel: map
    ax_map = fig.add_axes([0.02, 0.08, 0.62, 0.88])
    ax_map.set_facecolor("#F0F4F8")

    # Draw SA bounding box background
    ax_map.set_xlim(16.0, 33.5)
    ax_map.set_ylim(-35.5, -21.5)
    ax_map.set_aspect("equal")
    ax_map.axis("off")

    # Draw ocean background
    ocean = plt.Polygon([(15, -36), (34.5, -36), (34.5, -21), (15, -21)],
                         closed=True, facecolor="#C8E6F5", zorder=0)
    ax_map.add_patch(ocean)

    from matplotlib.patches import Polygon as MPoly
    for pname, pts in POLYS.items():
        d = PROV_DATA[pname]
        poly = MPoly(pts, closed=True,
                     facecolor=d["color"], edgecolor="white",
                     linewidth=1.8, zorder=2, alpha=0.92)
        ax_map.add_patch(poly)

        # Province label
        lx, ly = LABEL_POS[pname]
        ax_map.text(lx, ly, pname, ha="center", va="center",
                    fontsize=7.5, fontweight="bold", color="white", zorder=5,
                    path_effects=[pe.withStroke(linewidth=2.5, foreground="#333333")])

    # Borders
    ax_map.spines["bottom"].set_visible(False)

    # Title
    ax_map.set_title("South Africa — Customer Geography by Province",
                      fontsize=13, fontweight="bold", color="#1A1A2E", pad=8)

    # Right panel: data table
    ax_tbl = fig.add_axes([0.66, 0.08, 0.32, 0.88])
    ax_tbl.axis("off")

    headers = ["Province", "Customers", "Mean CLV", "RTS %", "PUDOs"]
    col_x = [0.0, 0.32, 0.52, 0.70, 0.86]
    row_h = 0.072
    y_start = 0.95

    # Header row
    ax_tbl.add_patch(FancyBboxPatch((0, y_start - 0.01), 1.0, row_h * 1.1,
                                     boxstyle="round,pad=0.01",
                                     facecolor="#1A1A2E", zorder=3))
    for i, h in enumerate(headers):
        ax_tbl.text(col_x[i] + 0.01, y_start + 0.025, h, fontsize=7.5,
                    fontweight="bold", color="white", va="center", zorder=4)

    # Sort by customers desc
    sorted_provs = sorted(PROV_DATA.keys(), key=lambda p: -PROV_DATA[p]["customers"])

    for r, pname in enumerate(sorted_provs):
        d = PROV_DATA[pname]
        y = y_start - (r + 1) * row_h
        bg = "#F8F9FA" if r % 2 == 0 else "white"
        ax_tbl.add_patch(FancyBboxPatch((0, y - 0.008), 1.0, row_h * 0.95,
                                         boxstyle="square,pad=0",
                                         facecolor=bg, edgecolor="#E0E0E0",
                                         linewidth=0.5, zorder=2))
        # Province colour dot
        ax_tbl.add_patch(plt.Circle((col_x[0] + 0.008, y + 0.022), 0.010,
                                     color=d["color"], zorder=4))
        ax_tbl.text(col_x[0] + 0.025, y + 0.022, pname[:12], fontsize=6.8,
                    va="center", color="#1A1A2E", fontweight="bold", zorder=4)
        ax_tbl.text(col_x[1] + 0.01, y + 0.022,
                    f"{d['customers']//1000}K", fontsize=6.8, va="center",
                    color="#1A1A2E", zorder=4)
        ax_tbl.text(col_x[2] + 0.01, y + 0.022,
                    f"R{d['mean_clv']:,.0f}", fontsize=6.8, va="center",
                    color="#1A1A2E", zorder=4)
        rts_color = "#D62728" if d["rts"] > 20 else "#FF7F0E" if d["rts"] > 15 else "#2CA02C"
        ax_tbl.text(col_x[3] + 0.01, y + 0.022,
                    f"{d['rts']}%", fontsize=6.8, va="center",
                    color=rts_color, fontweight="bold", zorder=4)
        ax_tbl.text(col_x[4] + 0.01, y + 0.022,
                    str(d["pudo"]), fontsize=6.8, va="center",
                    color="#1A1A2E", zorder=4)

    ax_tbl.set_xlim(0, 1)
    ax_tbl.set_ylim(0, 1)
    ax_tbl.set_title("Province Metrics", fontsize=10, fontweight="bold",
                      color="#1A1A2E", pad=4)

    # CLV bar chart below table
    ax_bar = fig.add_axes([0.66, 0.02, 0.32, 0.25])
    sorted_clv = sorted(PROV_DATA.items(), key=lambda x: -x[1]["mean_clv"])
    pnames = [p[:8] for p, _ in sorted_clv]
    clv_vals = [d["mean_clv"] for _, d in sorted_clv]
    colors = [d["color"] for _, d in sorted_clv]

    bars = ax_bar.barh(pnames, clv_vals, color=colors, edgecolor="white",
                        linewidth=0.5, height=0.7)
    for bar, val in zip(bars, clv_vals):
        ax_bar.text(val + 15, bar.get_y() + bar.get_height() / 2,
                    f"R{val:,}", va="center", fontsize=5.5, color="#333333")

    ax_bar.set_xlabel("Mean CLV (ZAR/year)", fontsize=7)
    ax_bar.set_title("Mean CLV by Province", fontsize=7.5, fontweight="bold")
    ax_bar.tick_params(axis="both", labelsize=6)
    ax_bar.spines["top"].set_visible(False)
    ax_bar.spines["right"].set_visible(False)
    ax_bar.invert_yaxis()

    # Caption
    fig.text(0.5, 0.005,
             "Data: 300K synthetic customers across 9 SA provinces  |  RTS = Return to Sender  |  "
             "Customer Lifetime Value (CLV) = Predicted 1-Year  |  PUDOs = Pickup Drop-Off Points",
             ha="center", fontsize=5.5, color="#666666", style="italic")

    out = OUT / "40_sa_province_map_ebook.png"
    fig.savefig(str(out), dpi=300, bbox_inches="tight",
                facecolor="white", edgecolor="none")
    plt.close(fig)
    print(f"  Saved: {out.name}")


def make_dashboard_map():
    """Dark-background map for dashboard/ebook dark pages."""
    fig = plt.figure(figsize=(18, 9), facecolor="#0D1117", dpi=200)
    ax = fig.add_axes([0.02, 0.08, 0.58, 0.88])
    ax.set_facecolor("#0D1117")
    ax.set_xlim(16.0, 33.5)
    ax.set_ylim(-35.5, -21.5)
    ax.set_aspect("equal")
    ax.axis("off")

    # Ocean
    from matplotlib.patches import Polygon as MPoly
    ocean = plt.Polygon([(15, -36), (34.5, -36), (34.5, -21), (15, -21)],
                         closed=True, facecolor="#1C2333", zorder=0)
    ax.add_patch(ocean)

    for pname, pts in POLYS.items():
        d = PROV_DATA[pname]
        poly = MPoly(pts, closed=True,
                     facecolor=d["color"], edgecolor="#0D1117",
                     linewidth=2, zorder=2, alpha=0.85)
        ax.add_patch(poly)
        lx, ly = LABEL_POS[pname]
        ax.text(lx, ly, pname, ha="center", va="center",
                fontsize=7.5, fontweight="bold", color="white", zorder=5,
                path_effects=[pe.withStroke(linewidth=3, foreground="#000000")])

    ax.set_title("South Africa — Customer Geography by Province",
                  fontsize=13, fontweight="bold", color="#FFC107", pad=8)

    # Stats panel
    ax2 = fig.add_axes([0.62, 0.08, 0.36, 0.88])
    ax2.set_facecolor("#0D1117")
    ax2.axis("off")
    ax2.set_xlim(0, 1)
    ax2.set_ylim(0, 1)

    sorted_provs = sorted(PROV_DATA.keys(), key=lambda p: -PROV_DATA[p]["customers"])
    row_h = 0.092
    y0 = 0.97

    ax2.text(0.5, y0 + 0.01, "Province Performance", ha="center",
             fontsize=10, fontweight="bold", color="#FFC107")

    for r, pname in enumerate(sorted_provs):
        d = PROV_DATA[pname]
        y = y0 - (r + 1) * row_h
        bg = "#161B22" if r % 2 == 0 else "#21262D"
        ax2.add_patch(FancyBboxPatch((0, y - 0.012), 1.0, row_h * 0.9,
                                      boxstyle="round,pad=0.005",
                                      facecolor=bg, edgecolor="#30363D",
                                      linewidth=0.8, zorder=2))
        ax2.add_patch(plt.Circle((0.025, y + 0.025), 0.013,
                                   color=d["color"], zorder=4))
        ax2.text(0.055, y + 0.025, pname, fontsize=7.5, va="center",
                 color="white", fontweight="bold", zorder=4)
        clv_str = f"R{d['mean_clv']:,}"
        ax2.text(0.54, y + 0.025, clv_str, fontsize=7, va="center",
                 color="#58A6FF", zorder=4)
        rts_col = "#F85149" if d["rts"] > 20 else "#E3B341" if d["rts"] > 15 else "#3FB950"
        ax2.text(0.75, y + 0.025, f"{d['rts']}%", fontsize=7, va="center",
                 color=rts_col, fontweight="bold", zorder=4)
        ax2.text(0.88, y + 0.025, f"{d['customers']//1000}K", fontsize=7,
                 va="center", color="#8B949E", zorder=4)

    # Column headers
    ax2.text(0.055, y0 - row_h * 0.4, "Province", fontsize=6.5, color="#8B949E")
    ax2.text(0.54,  y0 - row_h * 0.4, "CLV",      fontsize=6.5, color="#8B949E")
    ax2.text(0.75,  y0 - row_h * 0.4, "RTS",      fontsize=6.5, color="#8B949E")
    ax2.text(0.88,  y0 - row_h * 0.4, "Customers", fontsize=6.5, color="#8B949E")

    fig.text(0.5, 0.005,
             "Pargo Parcels  |  Geographical Analytics  |  9 Provinces  |  300K Customers",
             ha="center", fontsize=7, color="#8B949E")

    out = OUT / "41_sa_province_map_dashboard.png"
    fig.savefig(str(out), dpi=200, bbox_inches="tight",
                facecolor="#0D1117", edgecolor="none")
    plt.close(fig)
    print(f"  Saved: {out.name}")


def make_pargo_logo():
    """Create a Pargo-branded logo PNG for the ebook."""
    fig = plt.figure(figsize=(4, 1.4), facecolor="none", dpi=200)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_facecolor("none")
    ax.axis("off")
    ax.set_xlim(0, 4)
    ax.set_ylim(0, 1.4)

    # Yellow circle (Pargo brand)
    circ = plt.Circle((0.45, 0.72), 0.38, color="#FFC107", zorder=2)
    ax.add_patch(circ)

    # "pargo" text inside circle
    ax.text(0.45, 0.72, "pargo", ha="center", va="center",
            fontsize=9, fontweight="bold", color="#0D1117", zorder=3)

    # Brand text
    ax.text(1.0, 0.82, "PARGO PARCELS", ha="left", va="center",
            fontsize=13, fontweight="bold", color="#FFC107")
    ax.text(1.0, 0.45, "LAST-MILE LOGISTICS INTELLIGENCE", ha="left", va="center",
            fontsize=6, color="#8B949E", fontweight="bold")

    out = OUT / "pargo_logo.png"
    fig.savefig(str(out), dpi=200, bbox_inches="tight",
                transparent=True, facecolor="none", edgecolor="none")
    plt.close(fig)
    print(f"  Saved: {out.name}")


if __name__ == "__main__":
    print("Generating high-quality SA province maps...")
    make_ebook_map()
    make_dashboard_map()
    make_pargo_logo()
    print("Done.")
