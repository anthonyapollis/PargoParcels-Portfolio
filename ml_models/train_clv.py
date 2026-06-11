"""
Customer Lifetime Value (CLV) Model
=====================================
Computes CLV three ways:
  1. Historical CLV  -- simple sum of past spend
  2. Annualised CLV  -- historical / tenure years
  3. Predicted CLV   -- XGBoost regression on customer features

Also produces:
  - CLV distribution plots by segment and province
  - CLV decile analysis
  - Churn risk vs CLV scatter (2x2 strategic matrix)

Run:  python train_clv.py [--sample] [--snowflake]
"""
import argparse, warnings
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import seaborn as sns
import joblib
warnings.filterwarnings("ignore")

from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.metrics import mean_absolute_error, r2_score
import xgboost as xgb
import lightgbm as lgb

PLOTS = Path("plots")
ARTS  = Path("artifacts")
PLOTS.mkdir(exist_ok=True)
ARTS.mkdir(exist_ok=True)

DARK_BG  = "#1F2937"
PALETTE  = ["#3B82F6","#10B981","#F59E0B","#EF4444","#8B5CF6",
            "#06B6D4","#EC4899","#84CC16","#F97316","#6366F1"]

plt.rcParams.update({
    "figure.facecolor": DARK_BG, "axes.facecolor": "#111827",
    "axes.edgecolor": "#374151", "axes.labelcolor": "#D1D5DB",
    "xtick.color": "#9CA3AF", "ytick.color": "#9CA3AF",
    "text.color": "#E5E7EB", "grid.color": "#374151",
    "figure.dpi": 150, "font.size": 10,
})

SF = dict(account=os.environ.get("SNOWFLAKE_ACCOUNT", ""), user=os.environ.get("SNOWFLAKE_USER", ""),
          password=os.environ.get("SNOWFLAKE_PASSWORD", ""), role="ACCOUNTADMIN",
          warehouse="LYRA_LOAD_WH", database="PARGO_DW", schema="RAW")

PROVINCES = ["Gauteng","Western Cape","KwaZulu-Natal","Eastern Cape",
             "Limpopo","Mpumalanga","North West","Free State","Northern Cape"]
SEGMENTS  = ["Premium","Regular","Occasional","New"]


# ================================================================
# DATA
# ================================================================

def load_from_snowflake():
    import snowflake.connector
    print("Connecting to Snowflake for CLV data...")
    con = snowflake.connector.connect(**SF)
    cur = con.cursor()
    cur.execute("""
        SELECT
            c.CUSTOMER_ID,
            c.PROVINCE,
            c.CUSTOMER_SEGMENT,
            c.ACTIVE_FLAG,
            DATEDIFF('day', c.REGISTRATION_DATE, CURRENT_DATE) AS DAYS_SINCE_REG,
            COALESCE(o.ORDER_COUNT, 0)        AS ORDER_COUNT,
            COALESCE(o.TOTAL_SPEND, 0)        AS TOTAL_SPEND,
            COALESCE(o.AVG_ORDER_VALUE, 0)    AS AVG_ORDER_VALUE,
            COALESCE(o.TENURE_DAYS, 1)        AS TENURE_DAYS,
            COALESCE(o.MONTHS_ACTIVE, 1)      AS MONTHS_ACTIVE,
            COALESCE(p.PARCEL_COUNT, 0)       AS PARCEL_COUNT,
            COALESCE(p.RTS_COUNT, 0)          AS RTS_COUNT,
            COALESCE(p.COLLECTED_COUNT, 0)    AS COLLECTED_COUNT,
            COALESCE(p.AVG_DWELL, 0)          AS AVG_DWELL
        FROM PARGO_DW.RAW.DIM_CUSTOMERS c
        LEFT JOIN (
            SELECT CUSTOMER_ID,
                   COUNT(*)              AS ORDER_COUNT,
                   SUM(ORDER_VALUE_ZAR)  AS TOTAL_SPEND,
                   AVG(ORDER_VALUE_ZAR)  AS AVG_ORDER_VALUE,
                   DATEDIFF('day', MIN(ORDER_CREATED_AT), MAX(ORDER_CREATED_AT)) AS TENURE_DAYS,
                   DATEDIFF('month', MIN(ORDER_CREATED_AT), MAX(ORDER_CREATED_AT))+1 AS MONTHS_ACTIVE
            FROM PARGO_DW.RAW.FACT_ORDERS GROUP BY 1
        ) o ON c.CUSTOMER_ID = o.CUSTOMER_ID
        LEFT JOIN (
            SELECT CUSTOMER_ID,
                   COUNT(*)                                    AS PARCEL_COUNT,
                   COUNT_IF(PARCEL_STATUS='RTS')               AS RTS_COUNT,
                   COUNT_IF(PARCEL_STATUS='COLLECTED')         AS COLLECTED_COUNT,
                   AVG(DATEDIFF('day', ARRIVED_AT_POINT_AT, COLLECTED_AT)) AS AVG_DWELL
            FROM PARGO_DW.RAW.FACT_PARCELS GROUP BY 1
        ) p ON c.CUSTOMER_ID = p.CUSTOMER_ID
        SAMPLE (300000 ROWS)
    """)
    cols = [d[0] for d in cur.description]
    df = pd.DataFrame(cur.fetchall(), columns=cols)
    cur.close(); con.close()
    return df


def make_synthetic(n=300_000):
    np.random.seed(99)
    seg_params = {
        "Premium":    dict(orders=15, aov=1200, tenure=900),
        "Regular":    dict(orders=8,  aov=600,  tenure=600),
        "Occasional": dict(orders=3,  aov=400,  tenure=400),
        "New":        dict(orders=1,  aov=350,  tenure=60),
    }
    province_weights = [0.32,0.21,0.17,0.11,0.06,0.05,0.04,0.03,0.01]
    seg_weights      = [0.20, 0.40, 0.30, 0.10]

    segs = np.random.choice(SEGMENTS, n, p=seg_weights)
    provs = np.random.choice(PROVINCES, n, p=province_weights)

    orders, aov, tenure = [], [], []
    for s in segs:
        p = seg_params[s]
        orders.append(max(1, int(np.random.poisson(p["orders"]))))
        aov.append(max(50, np.random.exponential(p["aov"])))
        tenure.append(max(1, int(np.random.normal(p["tenure"], p["tenure"]*0.3))))

    orders  = np.array(orders)
    aov     = np.array(aov)
    tenure  = np.array(tenure)
    total_spend = orders * aov * (1 + np.random.normal(0, 0.1, n))
    months_active = np.maximum(1, tenure / 30)
    rts_rate = np.where(segs == "New", 0.15,
               np.where(segs == "Occasional", 0.12,
               np.where(segs == "Regular", 0.08, 0.04)))
    parcel_count = (orders * 1.2).astype(int)
    rts_count    = (parcel_count * rts_rate).astype(int)

    return pd.DataFrame({
        "CUSTOMER_ID":      np.arange(n),
        "PROVINCE":         provs,
        "CUSTOMER_SEGMENT": segs,
        "ACTIVE_FLAG":      np.random.choice([True,False], n, p=[0.70,0.30]),
        "DAYS_SINCE_REG":   np.random.randint(30, 1200, n),
        "ORDER_COUNT":      orders,
        "TOTAL_SPEND":      total_spend.clip(0),
        "AVG_ORDER_VALUE":  aov,
        "TENURE_DAYS":      tenure,
        "MONTHS_ACTIVE":    months_active,
        "PARCEL_COUNT":     parcel_count,
        "RTS_COUNT":        rts_count,
        "COLLECTED_COUNT":  (parcel_count - rts_count).clip(0),
        "AVG_DWELL":        np.random.exponential(3, n).clip(0, 20),
    })


# ================================================================
# CLV COMPUTATION
# ================================================================

GROSS_MARGIN = 0.18   # Pargo earns ~18% net margin per parcel (delivery fee)
DISCOUNT_RATE = 0.10  # annual discount rate for DCF CLV

def compute_clv(df):
    df = df.copy()
    for c in ["ORDER_COUNT","TOTAL_SPEND","AVG_ORDER_VALUE","TENURE_DAYS",
              "MONTHS_ACTIVE","PARCEL_COUNT","RTS_COUNT","COLLECTED_COUNT","AVG_DWELL"]:
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)

    # 1. Historical CLV — total gross profit earned from customer to date
    df["HISTORICAL_CLV"] = df["TOTAL_SPEND"] * GROSS_MARGIN

    # 2. Annualised CLV — historical CLV per year of tenure
    years = (df["TENURE_DAYS"] / 365).clip(lower=1/12)
    df["ANNUALISED_CLV"] = df["HISTORICAL_CLV"] / years

    # 3. Purchase frequency (orders per month)
    df["PURCHASE_FREQ_MONTHLY"] = df["ORDER_COUNT"] / df["MONTHS_ACTIVE"].clip(lower=1)

    # 4. Average revenue per order (gross margin applied)
    df["GROSS_PER_ORDER"] = df["AVG_ORDER_VALUE"] * GROSS_MARGIN

    # 5. Predicted future CLV (BG/NBD-style simplified):
    #    CLV_future = (freq × aov × margin) / discount × churn_factor
    #    churn_factor: Active=1.0, RTS heavy=0.6, Inactive=0.3
    rts_rate = (df["RTS_COUNT"] / df["PARCEL_COUNT"].clip(lower=1)).fillna(0)
    active   = df["ACTIVE_FLAG"].astype(int)
    churn_factor = np.where(active==1, 1.0 - 0.5*rts_rate, 0.3)
    df["PREDICTED_CLV_1YR"] = (
        df["PURCHASE_FREQ_MONTHLY"] * 12
        * df["GROSS_PER_ORDER"]
        * churn_factor
    ).clip(lower=0)

    # 6. CLV tier
    thresholds = df["PREDICTED_CLV_1YR"].quantile([0.25, 0.50, 0.75, 0.90])
    df["CLV_TIER"] = pd.cut(
        df["PREDICTED_CLV_1YR"],
        bins=[-1, thresholds[0.25], thresholds[0.50],
               thresholds[0.75], thresholds[0.90], np.inf],
        labels=["Low","Below Avg","Average","High","VIP"]
    )

    return df


# ================================================================
# ML-PREDICTED CLV (XGBoost Regression)
# ================================================================

def train_clv_model(df):
    print("\n[CLV-3] XGBoost CLV Regression...")
    le = LabelEncoder()
    df2 = df.copy()
    df2["PROV_ENC"] = le.fit_transform(df2["PROVINCE"].fillna("Unknown"))
    df2["SEG_ENC"]  = le.fit_transform(df2["CUSTOMER_SEGMENT"].fillna("Other"))
    df2["ACTIVE"]   = df2["ACTIVE_FLAG"].astype(int)

    feats = ["ORDER_COUNT","AVG_ORDER_VALUE","TENURE_DAYS","MONTHS_ACTIVE",
             "PARCEL_COUNT","RTS_COUNT","COLLECTED_COUNT","AVG_DWELL",
             "PURCHASE_FREQ_MONTHLY","PROV_ENC","SEG_ENC","ACTIVE"]
    target = "ANNUALISED_CLV"

    X = df2[feats].fillna(0)
    y = df2[target].clip(upper=df2[target].quantile(0.99))  # cap outliers

    X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.2, random_state=42)
    model = xgb.XGBRegressor(n_estimators=150, learning_rate=0.1, max_depth=6,
                               random_state=42, verbosity=0, nthread=2)
    model.fit(X_tr, y_tr)
    y_pred = model.predict(X_te)
    mae  = mean_absolute_error(y_te, y_pred)
    r2   = r2_score(y_te, y_pred)
    print(f"    XGBoost CLV  MAE=R{mae:.2f}  R2={r2:.4f}")
    joblib.dump(model, ARTS / "clv_xgboost.pkl")

    df2["ML_PREDICTED_CLV"] = model.predict(X).clip(0)
    return df2, model, feats


# ================================================================
# PLOTS
# ================================================================

def save_fig(name):
    p = PLOTS / f"{name}.png"
    plt.tight_layout()
    plt.savefig(p, bbox_inches="tight", facecolor=DARK_BG)
    plt.close()
    print(f"    Saved: {p.name}")


def plot_clv_distributions(df):
    fig, axes = plt.subplots(2, 2, figsize=(12, 8))

    # 1. CLV histogram
    ax = axes[0,0]
    vals = df["PREDICTED_CLV_1YR"].clip(upper=df["PREDICTED_CLV_1YR"].quantile(0.95))
    ax.hist(vals, bins=50, color=PALETTE[0], alpha=0.85, edgecolor="none")
    ax.axvline(vals.mean(), color=PALETTE[3], linewidth=2, linestyle="--",
               label=f"Mean R{vals.mean():.0f}")
    ax.axvline(vals.median(), color=PALETTE[2], linewidth=2, linestyle="--",
               label=f"Median R{vals.median():.0f}")
    ax.set_title("CLV Distribution (1-year predicted)", color="#E5E7EB")
    ax.set_xlabel("Predicted CLV (ZAR)")
    ax.set_ylabel("Customers")
    ax.legend(facecolor=DARK_BG, fontsize=9)
    ax.grid(alpha=0.2)

    # 2. CLV by segment (box)
    ax = axes[0,1]
    seg_order = ["VIP","Premium","Regular","Occasional","New"] if "VIP" in df["CUSTOMER_SEGMENT"].unique() \
                else SEGMENTS
    data_by_seg = [df[df["CUSTOMER_SEGMENT"]==s]["PREDICTED_CLV_1YR"].clip(
                   upper=df["PREDICTED_CLV_1YR"].quantile(0.95)).values
                   for s in SEGMENTS if s in df["CUSTOMER_SEGMENT"].unique()]
    bp = ax.boxplot(data_by_seg, patch_artist=True, notch=False,
                    medianprops=dict(color="#E5E7EB", linewidth=2))
    for patch, color in zip(bp["boxes"], PALETTE):
        patch.set_facecolor(color)
        patch.set_alpha(0.7)
    ax.set_xticklabels([s for s in SEGMENTS if s in df["CUSTOMER_SEGMENT"].unique()],
                       fontsize=9)
    ax.set_title("CLV by Customer Segment", color="#E5E7EB")
    ax.set_ylabel("Predicted CLV (ZAR)")
    ax.grid(alpha=0.2, axis="y")

    # 3. CLV tier donut
    ax = axes[1,0]
    tier_counts = df["CLV_TIER"].value_counts().sort_index()
    wedges, texts, autotexts = ax.pie(
        tier_counts.values,
        labels=tier_counts.index,
        autopct="%1.1f%%",
        colors=PALETTE[:len(tier_counts)],
        startangle=90,
        wedgeprops=dict(width=0.5)
    )
    for t in texts: t.set_color("#E5E7EB"); t.set_fontsize(9)
    for t in autotexts: t.set_color("#E5E7EB"); t.set_fontsize(8)
    ax.set_title("Customer CLV Tiers", color="#E5E7EB")

    # 4. CLV by segment bar (mean annualised)
    ax = axes[1,1]
    seg_means = df.groupby("CUSTOMER_SEGMENT")["ANNUALISED_CLV"].mean().sort_values(ascending=True)
    bars = ax.barh(seg_means.index, seg_means.values,
                   color=[PALETTE[i] for i in range(len(seg_means))], alpha=0.85)
    ax.set_title("Mean Annualised CLV by Segment", color="#E5E7EB")
    ax.set_xlabel("Mean CLV (ZAR/year)")
    ax.grid(alpha=0.2, axis="x")
    for bar, val in zip(bars, seg_means.values):
        ax.text(val + 5, bar.get_y() + bar.get_height()/2,
                f"R{val:,.0f}", va="center", fontsize=8, color="#E5E7EB")

    fig.suptitle("Customer Lifetime Value Analysis", color="#E5E7EB", fontsize=14)
    save_fig("17_clv_distributions")


def plot_clv_by_province(df):
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))

    # Mean CLV by province (bar)
    ax = axes[0]
    prov_clv = df.groupby("PROVINCE")["PREDICTED_CLV_1YR"].mean().sort_values(ascending=True)
    colors = [PALETTE[3] if v < prov_clv.median() else PALETTE[0] for v in prov_clv.values]
    bars = ax.barh(prov_clv.index, prov_clv.values, color=colors, alpha=0.85)
    ax.axvline(prov_clv.mean(), color=PALETTE[2], linewidth=1.5, linestyle="--",
               label=f"National avg R{prov_clv.mean():.0f}")
    ax.set_title("Mean Predicted CLV by Province", color="#E5E7EB")
    ax.set_xlabel("Mean CLV (ZAR/year)")
    ax.legend(facecolor=DARK_BG, fontsize=8)
    ax.grid(alpha=0.2, axis="x")
    for bar, val in zip(bars, prov_clv.values):
        ax.text(val + 2, bar.get_y() + bar.get_height()/2,
                f"R{val:.0f}", va="center", fontsize=8, color="#E5E7EB")

    # Customer count by province
    ax = axes[1]
    prov_count = df.groupby("PROVINCE")["CUSTOMER_ID"].count().sort_values(ascending=True)
    ax.barh(prov_count.index, prov_count.values / 1000,
            color=PALETTE[1], alpha=0.85)
    ax.set_title("Customer Count by Province (K)", color="#E5E7EB")
    ax.set_xlabel("Customers (thousands)")
    ax.grid(alpha=0.2, axis="x")
    for i, (prov, count) in enumerate(prov_count.items()):
        ax.text(count/1000 + 0.1, i, f"{count/1000:.1f}K",
                va="center", fontsize=8, color="#E5E7EB")

    fig.suptitle("Geographic CLV & Customer Distribution", color="#E5E7EB", fontsize=13)
    save_fig("18_clv_by_province")


def plot_clv_deciles(df):
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))

    # CLV decile revenue concentration (Pareto)
    ax = axes[0]
    df_s = df.sort_values("PREDICTED_CLV_1YR", ascending=False).reset_index(drop=True)
    n = len(df_s)
    cumulative_clv = df_s["PREDICTED_CLV_1YR"].cumsum() / df_s["PREDICTED_CLV_1YR"].sum() * 100
    pct_customers = np.arange(1, n+1) / n * 100
    ax.plot(pct_customers, cumulative_clv, color=PALETTE[0], linewidth=2)
    ax.plot([0,100],[0,100], "--", color="#6B7280", linewidth=1, label="Perfect equality")
    # Mark 20/80 point
    idx_20 = int(n * 0.20)
    ax.axvline(20, color=PALETTE[2], linewidth=1, linestyle=":", alpha=0.8)
    ax.axhline(cumulative_clv.iloc[idx_20], color=PALETTE[2], linewidth=1,
               linestyle=":", label=f"Top 20% = {cumulative_clv.iloc[idx_20]:.1f}% of CLV")
    ax.set_title("CLV Lorenz Curve (Pareto)", color="#E5E7EB")
    ax.set_xlabel("% of Customers (ranked by CLV)")
    ax.set_ylabel("% of Total CLV")
    ax.legend(facecolor=DARK_BG, fontsize=8)
    ax.grid(alpha=0.2)

    # CLV decile bar chart
    ax = axes[1]
    df_s["DECILE"] = pd.qcut(df_s["PREDICTED_CLV_1YR"], 10, labels=False) + 1
    decile_means = df_s.groupby("DECILE")["PREDICTED_CLV_1YR"].mean()
    ax.bar(decile_means.index, decile_means.values,
           color=[PALETTE[min(i//3, len(PALETTE)-1)] for i in range(10)], alpha=0.85)
    ax.set_title("Mean CLV by Decile (1=Lowest, 10=Highest)", color="#E5E7EB")
    ax.set_xlabel("CLV Decile")
    ax.set_ylabel("Mean Predicted CLV (ZAR)")
    ax.grid(alpha=0.2, axis="y")
    for i, (dec, val) in enumerate(decile_means.items()):
        ax.text(dec, val + val*0.02, f"R{val:.0f}", ha="center", fontsize=7, color="#E5E7EB")

    fig.suptitle("CLV Concentration & Decile Analysis", color="#E5E7EB", fontsize=13)
    save_fig("19_clv_deciles")


def plot_clv_churn_matrix(df):
    """Strategic 2x2: CLV vs Churn Risk."""
    fig, ax = plt.subplots(figsize=(9, 7))

    clv_med   = df["PREDICTED_CLV_1YR"].median()
    churn_med = (df["RTS_COUNT"] / df["PARCEL_COUNT"].clip(lower=1)).median()
    rts_rate  = (df["RTS_COUNT"] / df["PARCEL_COUNT"].clip(lower=1)).fillna(0)

    # Sample for scatter
    sample = df.sample(min(5000, len(df)), random_state=42)
    rts_s  = (sample["RTS_COUNT"] / sample["PARCEL_COUNT"].clip(lower=1)).fillna(0)
    clv_s  = sample["PREDICTED_CLV_1YR"].clip(upper=sample["PREDICTED_CLV_1YR"].quantile(0.97))

    scatter_colors = []
    labels = []
    for c, r in zip(clv_s, rts_s):
        if c >= clv_med and r <= churn_med:
            scatter_colors.append(PALETTE[1]); labels.append("Champions")
        elif c >= clv_med and r > churn_med:
            scatter_colors.append(PALETTE[2]); labels.append("At Risk")
        elif c < clv_med and r <= churn_med:
            scatter_colors.append(PALETTE[0]); labels.append("Loyalists")
        else:
            scatter_colors.append(PALETTE[3]); labels.append("Lost Causes")

    ax.scatter(rts_s, clv_s, c=scatter_colors, alpha=0.4, s=8)
    ax.axvline(churn_med, color="#6B7280", linewidth=1, linestyle="--")
    ax.axhline(clv_med,   color="#6B7280", linewidth=1, linestyle="--")

    # Quadrant labels
    ax.text(churn_med*0.1, clv_s.max()*0.92, "CHAMPIONS\n(High CLV, Low Risk)",
            color=PALETTE[1], fontsize=10, fontweight="bold")
    ax.text(churn_med*1.5, clv_s.max()*0.92, "AT RISK\n(High CLV, High Churn)",
            color=PALETTE[2], fontsize=10, fontweight="bold")
    ax.text(churn_med*0.1, clv_s.max()*0.08, "LOYALISTS\n(Low CLV, Low Risk)",
            color=PALETTE[0], fontsize=10, fontweight="bold")
    ax.text(churn_med*1.5, clv_s.max()*0.08, "LOST CAUSES\n(Low CLV, High Risk)",
            color=PALETTE[3], fontsize=10, fontweight="bold")

    ax.set_title("Strategic Customer Matrix: CLV vs RTS Risk", color="#E5E7EB", fontsize=12)
    ax.set_xlabel("RTS Rate (churn proxy)")
    ax.set_ylabel("Predicted 1-Year CLV (ZAR)")
    ax.grid(alpha=0.15)
    save_fig("20_clv_churn_matrix")


def plot_feature_importance_clv(model, feats):
    imp = model.feature_importances_
    idx = np.argsort(imp)
    fig, ax = plt.subplots(figsize=(8, 5))
    bars = ax.barh(range(len(idx)), imp[idx], color=PALETTE[0], alpha=0.85)
    ax.set_yticks(range(len(idx)))
    ax.set_yticklabels([feats[i] for i in idx], fontsize=9)
    ax.set_title("XGBoost CLV Model -- Feature Importances", color="#E5E7EB", fontsize=12)
    ax.set_xlabel("Importance")
    ax.grid(alpha=0.2, axis="x")
    for bar, val in zip(bars, imp[idx]):
        ax.text(val + 0.001, bar.get_y() + bar.get_height()/2,
                f"{val:.3f}", va="center", fontsize=8, color="#9CA3AF")
    save_fig("21_clv_feature_importance")


def print_clv_summary(df):
    print("\n=== CLV Summary Statistics ===")
    print(f"  Total customers analysed:   {len(df):,}")
    print(f"  Mean Historical CLV:        R{df['HISTORICAL_CLV'].mean():,.2f}")
    print(f"  Mean Annualised CLV:        R{df['ANNUALISED_CLV'].mean():,.2f}")
    print(f"  Mean Predicted 1yr CLV:     R{df['PREDICTED_CLV_1YR'].mean():,.2f}")
    print(f"  Median Predicted 1yr CLV:   R{df['PREDICTED_CLV_1YR'].median():,.2f}")
    print(f"\n  Top-20% customers account for:")
    df_s = df.sort_values("PREDICTED_CLV_1YR", ascending=False)
    top20 = df_s.head(int(len(df_s)*0.2))
    pct = top20["PREDICTED_CLV_1YR"].sum() / df_s["PREDICTED_CLV_1YR"].sum() * 100
    print(f"    {pct:.1f}% of total predicted CLV")
    print("\n  CLV by tier:")
    print(df.groupby("CLV_TIER")["PREDICTED_CLV_1YR"].agg(["count","mean"]).to_string())
    print("\n  CLV by province (top 5):")
    print(df.groupby("PROVINCE")["PREDICTED_CLV_1YR"].mean().sort_values(ascending=False).head().to_string())
    print("\n  CLV by segment:")
    print(df.groupby("CUSTOMER_SEGMENT")[["HISTORICAL_CLV","ANNUALISED_CLV","PREDICTED_CLV_1YR"]].mean().to_string())


# ================================================================
# MAIN
# ================================================================

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--snowflake", action="store_true")
    a = ap.parse_args()

    print("="*55)
    print("PARGO CLV MODEL")
    print("="*55)

    if a.snowflake:
        df = load_from_snowflake()
    else:
        print("Using synthetic data (run --snowflake for live data)")
        df = make_synthetic(300_000)

    print(f"  {len(df):,} customers loaded")

    # Compute CLV metrics
    print("\n[CLV-1] Computing CLV metrics...")
    df = compute_clv(df)

    # Train XGBoost CLV model
    df, clv_model, feats = train_clv_model(df)

    print("\n[CLV-2] Generating plots...")
    plot_clv_distributions(df)
    plot_clv_by_province(df)
    plot_clv_deciles(df)
    plot_clv_churn_matrix(df)
    plot_feature_importance_clv(clv_model, feats)

    print_clv_summary(df)

    # Save enriched dataset sample
    df.sample(min(10_000, len(df))).to_csv(ARTS / "clv_sample.csv", index=False)
    print(f"\nSaved CLV sample to {ARTS}/clv_sample.csv")
    print("\nDone.")


if __name__ == "__main__":
    main()
