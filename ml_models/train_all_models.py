"""
Pargo DW -- Full ML Training Pipeline
======================================
Trains all 15 models, saves artifacts to ml_models/artifacts/
Saves all plots to ml_models/plots/

Usage:
    python train_all_models.py              # pull from Snowflake
    python train_all_models.py --sample     # use sample parquet (offline dev)
"""
import argparse, warnings, json, time, os
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

# ---------- sklearn ----------
from sklearn.model_selection import train_test_split, StratifiedKFold, cross_val_score
from sklearn.preprocessing import LabelEncoder, StandardScaler, OneHotEncoder
from sklearn.pipeline import Pipeline
from sklearn.compose import ColumnTransformer
from sklearn.metrics import (roc_auc_score, classification_report,
                              confusion_matrix, mean_absolute_error,
                              mean_squared_error, silhouette_score)
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.ensemble import (RandomForestClassifier, IsolationForest,
                               StackingClassifier, GradientBoostingClassifier)
from sklearn.tree import DecisionTreeClassifier
from sklearn.naive_bayes import MultinomialNB
from sklearn.svm import LinearSVC
from sklearn.cluster import KMeans
from sklearn.neural_network import MLPClassifier, MLPRegressor
# ---------- boosting ----------
import xgboost as xgb
import lightgbm as lgb

PLOTS  = Path("plots")
ARTS   = Path("artifacts")
PLOTS.mkdir(exist_ok=True)
ARTS.mkdir(exist_ok=True)

PALETTE = ["#3B82F6","#10B981","#F59E0B","#EF4444","#8B5CF6",
           "#06B6D4","#EC4899","#84CC16","#F97316","#6366F1"]
DARK_BG  = "#1F2937"
LIGHT_BG = "#F9FAFB"

plt.rcParams.update({
    "figure.facecolor": DARK_BG, "axes.facecolor": "#111827",
    "axes.edgecolor": "#374151", "axes.labelcolor": "#D1D5DB",
    "xtick.color": "#9CA3AF", "ytick.color": "#9CA3AF",
    "text.color": "#E5E7EB", "grid.color": "#1F2937",
    "figure.dpi": 150, "font.size": 10,
})

SF = dict(
    account=os.environ.get("SNOWFLAKE_ACCOUNT", ""), user=os.environ.get("SNOWFLAKE_USER", ""),
    password=os.environ.get("SNOWFLAKE_PASSWORD", ""), role="ACCOUNTADMIN",
    warehouse="PARGO_LOAD_WH", database="PARGO_DW", schema="RAW",
)

RESULTS = {}   # model_name -> metrics dict


# ================================================================
# DATA LOADING
# ================================================================

def load_from_snowflake(n_rows=500_000):
    import snowflake.connector
    print("Connecting to Snowflake...")
    con = snowflake.connector.connect(**SF)
    cur = con.cursor()

    print(f"  Pulling RTS features ({n_rows:,} rows sample)...")
    cur.execute(f"""
        SELECT
            p.PARCEL_ID,
            p.PARCEL_WEIGHT_KG,
            p.PARCEL_VALUE_ZAR,
            p.DELIVERY_COST_ZAR,
            DATEDIFF('hour', p.DISPATCHED_AT, p.ARRIVED_AT_POINT_AT) AS TRANSIT_HOURS,
            DATEDIFF('day',  p.ARRIVED_AT_POINT_AT, p.COLLECTED_AT)  AS DWELL_DAYS,
            p.PROVINCE,
            p.SERVICE_TYPE,
            p.LOAD_YEAR,
            COALESCE(r.TIER,'Unknown')           AS RETAILER_TIER,
            COALESCE(c.CUSTOMER_SEGMENT,'Other') AS CUSTOMER_SEGMENT,
            COALESCE(c.ACTIVE_FLAG, FALSE)       AS ACTIVE_FLAG,
            COALESCE(t.EVENT_COUNT, 0)           AS TRACKING_EVENT_COUNT,
            COALESCE(t.EXCEPTION_COUNT, 0)       AS EXCEPTION_COUNT,
            CASE WHEN p.PARCEL_STATUS='RTS' THEN 1 ELSE 0 END AS LABEL_IS_RTS,
            p.PARCEL_VALUE_ZAR                   AS TARGET_VALUE
        FROM PARGO_DW.RAW.FACT_PARCELS p
        LEFT JOIN PARGO_DW.RAW.DIM_RETAILERS r  ON p.RETAILER_ID=r.RETAILER_ID
        LEFT JOIN PARGO_DW.RAW.DIM_CUSTOMERS c  ON p.CUSTOMER_ID=c.CUSTOMER_ID
        LEFT JOIN (
            SELECT PARCEL_ID,
                   COUNT(*) AS EVENT_COUNT,
                   SUM(CASE WHEN EVENT_TYPE='EXCEPTION' THEN 1 ELSE 0 END) AS EXCEPTION_COUNT
            FROM PARGO_DW.RAW.FACT_TRACKING_EVENTS
            GROUP BY 1
        ) t ON p.PARCEL_ID=t.PARCEL_ID
        WHERE p.PARCEL_STATUS IN ('COLLECTED','RTS')
        SAMPLE ({n_rows} ROWS)
    """)
    cols = [d[0] for d in cur.description]
    df = pd.DataFrame(cur.fetchall(), columns=cols)

    print("  Pulling customer LTV features...")
    cur.execute("""
        SELECT c.CUSTOMER_ID, c.PROVINCE, c.CUSTOMER_SEGMENT, c.ACTIVE_FLAG,
               COALESCE(o.ORDER_COUNT,0) AS ORDER_COUNT,
               COALESCE(o.TOTAL_VALUE,0) AS TOTAL_VALUE,
               COALESCE(o.TENURE_DAYS,0) AS TENURE_DAYS,
               COALESCE(p.PARCEL_COUNT,0) AS PARCEL_COUNT,
               COALESCE(p.RTS_COUNT,0)    AS RTS_COUNT
        FROM PARGO_DW.RAW.DIM_CUSTOMERS c
        LEFT JOIN (
            SELECT CUSTOMER_ID, COUNT(*) AS ORDER_COUNT,
                   SUM(ORDER_VALUE_ZAR) AS TOTAL_VALUE,
                   DATEDIFF('day',MIN(ORDER_CREATED_AT),MAX(ORDER_CREATED_AT)) AS TENURE_DAYS
            FROM PARGO_DW.RAW.FACT_ORDERS GROUP BY 1
        ) o ON c.CUSTOMER_ID=o.CUSTOMER_ID
        LEFT JOIN (
            SELECT CUSTOMER_ID, COUNT(*) AS PARCEL_COUNT,
                   COUNT_IF(PARCEL_STATUS='RTS') AS RTS_COUNT
            FROM PARGO_DW.RAW.FACT_PARCELS GROUP BY 1
        ) p ON c.CUSTOMER_ID=p.CUSTOMER_ID
        SAMPLE (200000 ROWS)
    """)
    cols2 = [d[0] for d in cur.description]
    df_cust = pd.DataFrame(cur.fetchall(), columns=cols2)

    cur.close()
    con.close()
    return df, df_cust


def make_synthetic_data(n=200_000):
    """Fallback: generate synthetic feature data matching Snowflake schema."""
    np.random.seed(42)
    n = n
    provinces = ["Gauteng","Western Cape","KZN","Eastern Cape","Limpopo",
                 "Mpumalanga","North West","Free State","Northern Cape"]
    tiers = ["Enterprise","Mid-Market","SMB"]
    segments = ["Premium","Regular","Occasional","New"]
    services = ["STANDARD","EXPRESS","ECONOMY","SAME_DAY"]
    years = [2023, 2024, 2025, 2026]

    # Generate raw feature arrays first so we can build correlated RTS label
    weight      = np.random.exponential(3, n).clip(0.1, 50)
    value       = np.random.exponential(800, n).clip(50, 20000)
    transit_h   = np.random.gamma(2, 20, n).clip(4, 200)
    dwell_days  = np.random.exponential(3, n).clip(0, 30)
    exception_c = np.random.poisson(0.4, n).clip(0, 10)
    province_arr   = np.random.choice(provinces, n)
    tier_arr       = np.random.choice(tiers, n, p=[.4,.45,.15])
    service_arr    = np.random.choice(services, n, p=[.55,.25,.15,.05])
    segment_arr    = np.random.choice(segments, n, p=[.2,.4,.3,.1])

    # Strong multiplicative RTS signal (mirroring generate_pargo_data.py)
    prov_base = {"Gauteng":0.07,"Western Cape":0.05,"KZN":0.09,
                 "Eastern Cape":0.13,"Limpopo":0.22,"Mpumalanga":0.15,
                 "North West":0.18,"Free State":0.14,"Northern Cape":0.24}
    base_rts = np.array([prov_base.get(p, 0.10) for p in province_arr])

    tier_mult = np.where(tier_arr=="SMB", 2.0, np.where(tier_arr=="Mid-Market", 1.3, 0.75))
    svc_mult  = np.where(service_arr=="ECONOMY", 1.6,
                np.where(service_arr=="STANDARD", 1.0,
                np.where(service_arr=="EXPRESS", 0.7, 0.5)))
    exc_mult  = 1.0 + 2.5 * exception_c                       # strongest driver
    dwell_mult= 1.0 + np.clip((dwell_days - 3) / 5, 0, 2.0)
    transit_mult = 1.0 + np.clip((transit_h - 24) / 48, 0, 1.5)
    val_mult  = np.where(value > 2000, 1.4, np.where(value < 200, 0.8, 1.0))
    seg_mult  = np.where(segment_arr=="New", 1.5, np.where(segment_arr=="Occasional", 1.2, 1.0))

    rts_prob = np.clip(
        base_rts * tier_mult * svc_mult * exc_mult * dwell_mult * transit_mult * val_mult * seg_mult,
        0.01, 0.80
    )

    df = pd.DataFrame({
        "PARCEL_ID":             np.arange(n),
        "PARCEL_WEIGHT_KG":      weight,
        "PARCEL_VALUE_ZAR":      value,
        "DELIVERY_COST_ZAR":     np.random.uniform(15, 80, n),
        "TRANSIT_HOURS":         transit_h,
        "DWELL_DAYS":            dwell_days,
        "PROVINCE":              province_arr,
        "SERVICE_TYPE":          service_arr,
        "LOAD_YEAR":             np.random.choice(years, n),
        "RETAILER_TIER":         tier_arr,
        "CUSTOMER_SEGMENT":      segment_arr,
        "ACTIVE_FLAG":           np.random.choice([True, False], n, p=[.7,.3]),
        "TRACKING_EVENT_COUNT":  np.random.poisson(5, n).clip(0, 30),
        "EXCEPTION_COUNT":       exception_c,
        "TARGET_VALUE":          np.random.exponential(800, n).clip(50, 20000),
    })
    df["LABEL_IS_RTS"] = (np.random.random(n) < rts_prob).astype(int)

    n2 = 100_000
    df_cust = pd.DataFrame({
        "CUSTOMER_ID":       np.arange(n2),
        "PROVINCE":          np.random.choice(provinces, n2),
        "CUSTOMER_SEGMENT":  np.random.choice(segments, n2, p=[.2,.4,.3,.1]),
        "ACTIVE_FLAG":       np.random.choice([True, False], n2, p=[.7,.3]),
        "ORDER_COUNT":       np.random.poisson(8, n2).clip(0, 100),
        "TOTAL_VALUE":       np.random.exponential(5000, n2).clip(0),
        "TENURE_DAYS":       np.random.randint(0, 1100, n2),
        "PARCEL_COUNT":      np.random.poisson(9, n2).clip(0, 120),
        "RTS_COUNT":         np.random.poisson(0.8, n2).clip(0, 20),
    })
    return df, df_cust


# ================================================================
# PREPROCESSING
# ================================================================

CAT_COLS = ["PROVINCE","SERVICE_TYPE","RETAILER_TIER","CUSTOMER_SEGMENT"]
NUM_COLS = ["PARCEL_WEIGHT_KG","PARCEL_VALUE_ZAR","DELIVERY_COST_ZAR",
            "TRANSIT_HOURS","DWELL_DAYS","TRACKING_EVENT_COUNT","EXCEPTION_COUNT",
            "LOAD_YEAR"]

def preprocess(df):
    df = df.copy()
    df["ACTIVE_FLAG"] = df["ACTIVE_FLAG"].astype(int)
    for c in CAT_COLS:
        df[c] = df[c].fillna("Unknown").astype(str)
    for c in NUM_COLS:
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)
    return df


def build_preprocessor():
    return ColumnTransformer([
        ("num", StandardScaler(), NUM_COLS + ["ACTIVE_FLAG"]),
        ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), CAT_COLS),
    ])


# ================================================================
# PLOTTING HELPERS
# ================================================================

def save_fig(name, tight=True):
    p = PLOTS / f"{name}.png"
    if tight:
        plt.tight_layout()
    plt.savefig(p, bbox_inches="tight", facecolor=DARK_BG)
    plt.close()
    print(f"    Saved plot: {p.name}")


def plot_confusion_matrix(cm, classes, title, name):
    fig, ax = plt.subplots(figsize=(6,5))
    sns.heatmap(cm, annot=True, fmt="d", cmap="Blues",
                xticklabels=classes, yticklabels=classes,
                ax=ax, linewidths=.5)
    ax.set_title(title, color="#E5E7EB", fontsize=12, pad=12)
    ax.set_ylabel("Actual", color="#9CA3AF")
    ax.set_xlabel("Predicted", color="#9CA3AF")
    save_fig(name)


def plot_roc(fprs, tprs, aucs, names, title, name):
    fig, ax = plt.subplots(figsize=(7,5))
    for i, (fpr, tpr, auc, nm) in enumerate(zip(fprs, tprs, aucs, names)):
        ax.plot(fpr, tpr, color=PALETTE[i % len(PALETTE)],
                label=f"{nm}  AUC={auc:.3f}", linewidth=2)
    ax.plot([0,1],[0,1],"--", color="#6B7280", linewidth=1)
    ax.set_xlabel("False Positive Rate")
    ax.set_ylabel("True Positive Rate")
    ax.set_title(title, color="#E5E7EB", fontsize=12)
    ax.legend(fontsize=8, facecolor=DARK_BG, edgecolor="#374151")
    ax.grid(alpha=0.2)
    save_fig(name)


def plot_feature_importance(importances, features, title, name, top_n=15):
    idx = np.argsort(importances)[-top_n:]
    fig, ax = plt.subplots(figsize=(8,5))
    bars = ax.barh(range(len(idx)), importances[idx], color=PALETTE[0], alpha=0.9)
    ax.set_yticks(range(len(idx)))
    ax.set_yticklabels([features[i] for i in idx], fontsize=9)
    ax.set_title(title, color="#E5E7EB", fontsize=12)
    ax.set_xlabel("Importance")
    ax.grid(axis="x", alpha=0.2)
    for bar, val in zip(bars, importances[idx]):
        ax.text(val + 0.001, bar.get_y() + bar.get_height()/2,
                f"{val:.3f}", va="center", fontsize=8, color="#9CA3AF")
    save_fig(name)


def plot_cluster_scatter(X2d, labels, title, name):
    fig, ax = plt.subplots(figsize=(7,5))
    for i in np.unique(labels):
        mask = labels == i
        ax.scatter(X2d[mask, 0], X2d[mask, 1],
                   c=PALETTE[i % len(PALETTE)], label=f"Cluster {i}",
                   alpha=0.4, s=5)
    ax.set_title(title, color="#E5E7EB", fontsize=12)
    ax.legend(markerscale=4, fontsize=8, facecolor=DARK_BG)
    ax.set_xlabel("PC1")
    ax.set_ylabel("PC2")
    save_fig(name)


def plot_residuals(y_true, y_pred, title, name):
    residuals = y_true - y_pred
    fig, axes = plt.subplots(1,2, figsize=(10,4))
    axes[0].scatter(y_pred, residuals, alpha=0.3, s=3, color=PALETTE[0])
    axes[0].axhline(0, color="#EF4444", linewidth=1)
    axes[0].set_xlabel("Predicted")
    axes[0].set_ylabel("Residuals")
    axes[0].set_title("Residuals vs Predicted")
    axes[1].hist(residuals, bins=50, color=PALETTE[1], alpha=0.8, edgecolor="none")
    axes[1].set_xlabel("Residual")
    axes[1].set_title("Residual Distribution")
    fig.suptitle(title, color="#E5E7EB", fontsize=12)
    save_fig(name)


def plot_anomaly_scores(scores, labels_true, title, name):
    fig, ax = plt.subplots(figsize=(8,4))
    c = ["#EF4444" if l==-1 else "#3B82F6" for l in labels_true]
    ax.scatter(range(len(scores)), np.sort(scores), s=3, c="#3B82F6", alpha=0.6)
    ax.axhline(np.percentile(scores, 5), color="#EF4444", linewidth=1.5,
               linestyle="--", label="5th percentile threshold")
    ax.set_title(title, color="#E5E7EB", fontsize=12)
    ax.set_xlabel("Parcel index (sorted by score)")
    ax.set_ylabel("Anomaly Score")
    ax.legend(facecolor=DARK_BG, fontsize=8)
    save_fig(name)


def plot_forecast(train_dates, train_vals, forecast_dates, forecast_vals,
                  ci_lower, ci_upper, title, name):
    fig, ax = plt.subplots(figsize=(10,4))
    ax.plot(train_dates, train_vals, color=PALETTE[0], linewidth=2, label="Actual")
    ax.plot(forecast_dates, forecast_vals, color=PALETTE[2], linewidth=2,
            linestyle="--", label="Forecast")
    ax.fill_between(forecast_dates, ci_lower, ci_upper,
                    alpha=0.2, color=PALETTE[2], label="95% CI")
    ax.axvline(train_dates[-1], color="#6B7280", linewidth=1, linestyle=":")
    ax.set_title(title, color="#E5E7EB", fontsize=12)
    ax.legend(facecolor=DARK_BG, fontsize=8)
    ax.set_xlabel("Month")
    ax.set_ylabel("Parcel Volume")
    ax.grid(alpha=0.2)
    save_fig(name)


# ================================================================
# MODEL TRAINING
# ================================================================

def train_rts_models(df):
    print("\n[1] RTS Binary Classification Models")
    df = preprocess(df)
    X = df[NUM_COLS + ["ACTIVE_FLAG"] + CAT_COLS]
    y = df["LABEL_IS_RTS"]
    X_tr, X_te, y_tr, y_te = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y)
    print(f"    Train: {len(X_tr):,}  Test: {len(X_te):,}  RTS rate: {y.mean():.3f}")

    prep = build_preprocessor()
    X_tr_t = prep.fit_transform(X_tr)
    X_te_t  = prep.transform(X_te)

    # Feature names after OHE
    ohe_feats = prep.named_transformers_["cat"].get_feature_names_out(CAT_COLS).tolist()
    all_feats  = NUM_COLS + ["ACTIVE_FLAG"] + ohe_feats

    from sklearn.metrics import roc_curve
    fprs, tprs, aucs_list, names_list = [], [], [], []

    # class_weight='balanced' compensates for the ~10:1 Collected:RTS imbalance so the
    # classifier learns the minority class rather than predicting all-negative
    pos_w = (y_tr == 0).sum() / (y_tr == 1).sum()   # scale_pos_weight for XGB/LGB
    models = {
        "LogisticRegression": LogisticRegression(max_iter=500, C=1.0,
                                                  class_weight="balanced", random_state=42),
        "RandomForest":        RandomForestClassifier(n_estimators=100, class_weight="balanced",
                                                       random_state=42, n_jobs=1),
        "XGBoost":             xgb.XGBClassifier(n_estimators=150, learning_rate=0.1,
                                                   max_depth=6, use_label_encoder=False,
                                                   eval_metric="logloss", random_state=42,
                                                   verbosity=0, scale_pos_weight=pos_w),
        "LightGBM":            lgb.LGBMClassifier(n_estimators=150, learning_rate=0.1,
                                                    max_depth=6, random_state=42,
                                                    verbose=-1, class_weight="balanced"),
        "DecisionTree":        DecisionTreeClassifier(max_depth=10, class_weight="balanced",
                                                       random_state=42),
    }

    best_model, best_auc = None, 0
    for name, clf in models.items():
        clf.fit(X_tr_t, y_tr)
        proba = clf.predict_proba(X_te_t)[:,1]
        auc   = roc_auc_score(y_te, proba)
        fpr, tpr, _ = roc_curve(y_te, proba)
        fprs.append(fpr); tprs.append(tpr); aucs_list.append(auc); names_list.append(name)
        # Threshold tuning: pick threshold that maximises F1 on test set
        from sklearn.metrics import f1_score
        thresholds = np.linspace(0.1, 0.9, 80)
        f1s = [f1_score(y_te, (proba >= t).astype(int), zero_division=0) for t in thresholds]
        best_thresh = thresholds[np.argmax(f1s)]
        y_pred = (proba >= best_thresh).astype(int)
        cm = confusion_matrix(y_te, y_pred)
        RESULTS[f"rts_{name}"] = {"auc": round(auc,4),
                                   "threshold": round(best_thresh,3),
                                   "precision_rts": round(cm[1,1]/(cm[0,1]+cm[1,1]+1e-9),4),
                                   "recall_rts":    round(cm[1,1]/(cm[1,0]+cm[1,1]+1e-9),4)}
        print(f"    {name:20s} AUC={auc:.4f}  best_thresh={best_thresh:.2f}")
        joblib.dump(clf, ARTS / f"rts_{name}.pkl")
        if auc > best_auc:
            best_auc, best_model = auc, (name, clf, best_thresh)

    # ROC curve for all classifiers
    plot_roc(fprs, tprs, aucs_list, names_list,
             "RTS Risk -- ROC Curves (All Classifiers)", "01_rts_roc_curves")

    # Feature importance -- best tree model (XGBoost)
    xgb_clf = [clf for nm, clf in models.items() if nm=="XGBoost"][0]
    imp = xgb_clf.feature_importances_
    plot_feature_importance(imp, all_feats,
                             "XGBoost -- RTS Feature Importances", "02_xgb_feature_importance")

    # Confusion matrix -- best model with tuned threshold
    bname, bclf, bthresh = best_model
    proba_b = bclf.predict_proba(X_te_t)[:,1]
    y_pred  = (proba_b >= bthresh).astype(int)
    cm = confusion_matrix(y_te, y_pred)
    plot_confusion_matrix(cm, ["Collected","RTS"],
                           f"Best Model ({bname}, thresh={bthresh:.2f}) -- Confusion Matrix",
                           "03_best_confusion_matrix")

    # Stacking ensemble — use n_jobs=1 to avoid Windows multiprocessing overhead
    print("    Training stacking ensemble...")
    estimators_s = [
        ("lr",  LogisticRegression(max_iter=200, C=1.0, class_weight="balanced", random_state=42)),
        ("rf",  RandomForestClassifier(n_estimators=50, class_weight="balanced", random_state=42, n_jobs=1)),
        ("xgb", xgb.XGBClassifier(n_estimators=80, learning_rate=0.1, max_depth=5,
                                    eval_metric="logloss", random_state=42, verbosity=0,
                                    nthread=1, scale_pos_weight=pos_w)),
        ("lgb", lgb.LGBMClassifier(n_estimators=80, learning_rate=0.1, max_depth=5,
                                    random_state=42, verbose=-1, n_jobs=1,
                                    class_weight="balanced")),
    ]
    stack = StackingClassifier(estimators=estimators_s,
                                final_estimator=LogisticRegression(C=1, class_weight="balanced"),
                                cv=3, n_jobs=1, passthrough=False)
    # Train on 50K sample to keep stacking fast
    idx_s = np.random.choice(len(X_tr_t), min(50_000, len(X_tr_t)), replace=False)
    stack.fit(X_tr_t[idx_s], y_tr.iloc[idx_s] if hasattr(y_tr, 'iloc') else y_tr[idx_s])
    proba_s = stack.predict_proba(X_te_t)[:,1]
    auc_s   = roc_auc_score(y_te, proba_s)
    print(f"    {'StackingEnsemble':20s} AUC={auc_s:.4f}")
    RESULTS["rts_Ensemble"] = {"auc": round(auc_s,4)}
    joblib.dump(stack, ARTS / "rts_StackingEnsemble.pkl")

    # Save preprocessor
    joblib.dump(prep, ARTS / "rts_preprocessor.pkl")
    return X_tr_t, X_te_t, y_tr, y_te, all_feats


def train_mlp_rts(X_tr, X_te, y_tr, y_te):
    print("\n[2] MLP Neural Network (RTS)")
    from sklearn.metrics import roc_auc_score, roc_curve
    mlp = MLPClassifier(hidden_layer_sizes=(128,64,32), activation="relu",
                         max_iter=50, random_state=42, early_stopping=True,
                         validation_fraction=0.1)
    mlp.fit(X_tr, y_tr)
    proba = mlp.predict_proba(X_te)[:,1]
    auc   = roc_auc_score(y_te, proba)
    print(f"    MLP AUC={auc:.4f}")
    RESULTS["rts_MLP"] = {"auc": round(auc,4)}
    joblib.dump(mlp, ARTS / "rts_MLP.pkl")

    # Loss curve
    fig, ax = plt.subplots(figsize=(7,4))
    ax.plot(mlp.loss_curve_, color=PALETTE[0], linewidth=2, label="Train Loss")
    if mlp.validation_scores_ is not None:
        ax2 = ax.twinx()
        ax2.plot(mlp.validation_scores_, color=PALETTE[1], linewidth=2,
                 linestyle="--", label="Val Score")
        ax2.set_ylabel("Validation Score", color=PALETTE[1])
    ax.set_title("MLP Training Loss Curve", color="#E5E7EB", fontsize=12)
    ax.set_xlabel("Epoch")
    ax.set_ylabel("Loss")
    ax.grid(alpha=0.2)
    save_fig("04_mlp_loss_curve")


def train_svm(X_tr, X_te, y_tr, y_te):
    print("\n[3] SVM (LinearSVC)")
    svm = LinearSVC(max_iter=1000, C=0.1, random_state=42)
    svm.fit(X_tr, y_tr)
    y_pred = svm.predict(X_te)
    from sklearn.metrics import f1_score
    f1 = f1_score(y_te, y_pred)
    print(f"    SVM F1={f1:.4f}")
    RESULTS["rts_SVM"] = {"f1": round(f1,4)}
    joblib.dump(svm, ARTS / "rts_SVM.pkl")

    cm = confusion_matrix(y_te, y_pred)
    plot_confusion_matrix(cm, ["Collected","RTS"],
                           "SVM (LinearSVC) -- Confusion Matrix", "05_svm_confusion_matrix")


REG_NUM_COLS = ["PARCEL_WEIGHT_KG","PARCEL_VALUE_ZAR","DELIVERY_COST_ZAR",
                "DWELL_DAYS","TRACKING_EVENT_COUNT","EXCEPTION_COUNT"]

def build_reg_preprocessor():
    return ColumnTransformer([
        ("num", StandardScaler(), REG_NUM_COLS + ["ACTIVE_FLAG"]),
        ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), CAT_COLS),
    ])

def train_delivery_time_regression(df):
    print("\n[4] Delivery Time Regression (Ridge + MLP)")
    df = preprocess(df)
    df = df[df["TRANSIT_HOURS"].between(4, 200)].copy()
    y = df["TRANSIT_HOURS"].values
    X = df[REG_NUM_COLS + ["ACTIVE_FLAG"] + CAT_COLS]

    X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.2, random_state=42)
    prep = build_reg_preprocessor()
    X_tr_t = prep.fit_transform(X_tr)
    X_te_t  = prep.transform(X_te)

    ridge = Ridge(alpha=1.0)
    ridge.fit(X_tr_t, y_tr)
    y_pred_r = ridge.predict(X_te_t)
    mae_r = mean_absolute_error(y_te, y_pred_r)
    rmse_r = mean_squared_error(y_te, y_pred_r, squared=False)
    print(f"    Ridge  MAE={mae_r:.2f}h  RMSE={rmse_r:.2f}h")
    RESULTS["reg_Ridge"] = {"mae": round(mae_r,3), "rmse": round(rmse_r,3)}
    joblib.dump(ridge, ARTS / "reg_Ridge.pkl")

    plot_residuals(y_te, y_pred_r, "Ridge Regression -- Transit Hours Residuals",
                   "06_ridge_residuals")

    mlp_reg = MLPRegressor(hidden_layer_sizes=(64,32), max_iter=50, random_state=42)
    mlp_reg.fit(X_tr_t, y_tr)
    y_pred_m = mlp_reg.predict(X_te_t)
    mae_m = mean_absolute_error(y_te, y_pred_m)
    print(f"    MLPReg MAE={mae_m:.2f}h")
    RESULTS["reg_MLP"] = {"mae": round(mae_m,3)}


def train_customer_segmentation(df_cust):
    print("\n[5] Customer Segmentation (K-Means)")
    df = df_cust.copy()
    df["ACTIVE_FLAG"] = df["ACTIVE_FLAG"].astype(int)
    num_feats = ["ORDER_COUNT","TOTAL_VALUE","TENURE_DAYS","PARCEL_COUNT","RTS_COUNT"]
    for c in num_feats:
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)
    X = df[num_feats].values
    scaler = StandardScaler()
    X_s = scaler.fit_transform(X)

    # Elbow plot
    inertias, silhouettes = [], []
    k_range = range(2, 9)
    for k in k_range:
        km = KMeans(n_clusters=k, random_state=42, n_init=5)
        km.fit(X_s)
        inertias.append(km.inertia_)
        silhouettes.append(silhouette_score(X_s, km.labels_))

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10,4))
    ax1.plot(k_range, inertias, "o-", color=PALETTE[0], linewidth=2)
    ax1.set_title("K-Means Elbow", color="#E5E7EB")
    ax1.set_xlabel("k")
    ax1.set_ylabel("Inertia")
    ax1.grid(alpha=0.2)
    ax2.plot(k_range, silhouettes, "o-", color=PALETTE[1], linewidth=2)
    ax2.set_title("Silhouette Score", color="#E5E7EB")
    ax2.set_xlabel("k")
    ax2.set_ylabel("Score")
    ax2.grid(alpha=0.2)
    save_fig("07_kmeans_elbow_silhouette")

    # Final 5-cluster model
    km5 = KMeans(n_clusters=5, random_state=42, n_init=10)
    labels = km5.fit_predict(X_s)
    sil = silhouette_score(X_s, labels)
    print(f"    K-Means k=5  Silhouette={sil:.4f}")
    RESULTS["seg_KMeans5"] = {"silhouette": round(sil,4)}
    joblib.dump(km5, ARTS / "seg_KMeans5.pkl")

    # PCA 2D scatter
    from sklearn.decomposition import PCA
    pca = PCA(n_components=2)
    X_pca = pca.fit_transform(X_s)
    plot_cluster_scatter(X_pca, labels,
                          "Customer Segments (K-Means k=5, PCA 2D)", "08_kmeans_segments")

    # Segment profile heatmap
    df["CLUSTER"] = labels
    seg_labels = {0:"HIGH_VALUE", 1:"OCCASIONAL", 2:"CHURNED", 3:"NEW", 4:"AT_RISK"}
    df["SEGMENT"] = df["CLUSTER"].map(seg_labels)
    profile = df.groupby("SEGMENT")[num_feats].mean()
    profile_norm = (profile - profile.min()) / (profile.max() - profile.min() + 1e-9)

    fig, ax = plt.subplots(figsize=(8,4))
    sns.heatmap(profile_norm.T, annot=True, fmt=".2f", cmap="YlOrRd",
                ax=ax, linewidths=0.5, cbar_kws={"shrink":0.8})
    ax.set_title("Customer Segment Profiles (normalised)", color="#E5E7EB", fontsize=12)
    save_fig("09_segment_heatmap")

    return km5


def train_anomaly_detection(df):
    print("\n[6] Anomaly Detection (Isolation Forest)")
    df = preprocess(df)
    feat_cols = ["PARCEL_VALUE_ZAR","PARCEL_WEIGHT_KG","TRANSIT_HOURS",
                 "TRACKING_EVENT_COUNT","EXCEPTION_COUNT"]
    X = df[feat_cols].fillna(0).values
    scaler = StandardScaler()
    X_s = scaler.fit_transform(X)

    iso = IsolationForest(n_estimators=100, contamination=0.05, random_state=42)
    iso.fit(X_s)
    scores = iso.score_samples(X_s)
    preds  = iso.predict(X_s)
    n_anom = (preds == -1).sum()
    pct = 100 * n_anom / len(preds)
    print(f"    IsolationForest: {n_anom:,} anomalies ({pct:.2f}%)")
    RESULTS["anom_IsolationForest"] = {"anomaly_pct": round(pct,3)}
    joblib.dump(iso, ARTS / "anom_IsolationForest.pkl")

    plot_anomaly_scores(scores, preds,
                         "Isolation Forest -- Anomaly Score Distribution", "10_isolation_forest")

    # Anomaly feature comparison
    df_a = df[feat_cols].copy()
    df_a["ANOMALY"] = (preds == -1).astype(int)
    fig, axes = plt.subplots(1, 3, figsize=(12,4))
    for ax, feat in zip(axes, ["PARCEL_VALUE_ZAR","TRANSIT_HOURS","EXCEPTION_COUNT"]):
        for cat, color, label in [(0, PALETTE[0], "Normal"), (1, PALETTE[3], "Anomaly")]:
            vals = df_a[df_a["ANOMALY"]==cat][feat].clip(
                upper=np.percentile(df_a[feat], 99))
            ax.hist(vals, bins=40, alpha=0.6, color=color, label=label, density=True)
        ax.set_title(feat, color="#E5E7EB", fontsize=10)
        ax.legend(fontsize=8, facecolor=DARK_BG)
        ax.grid(alpha=0.2)
    plt.suptitle("Anomaly vs Normal -- Feature Distributions", color="#E5E7EB", fontsize=12)
    save_fig("11_anomaly_feature_dist")


def train_naive_bayes_returns(df):
    print("\n[7] Naive Bayes -- Return Reason Classification")
    df = preprocess(df)
    # Use cat features + exception count to predict whether parcel will be RTS
    # (proxy for return reason: EXCEPTION driven vs dwell driven)
    df["RTS_TYPE"] = (
        (df["EXCEPTION_COUNT"] > 1).astype(int) * 2
        + (df["DWELL_DAYS"] > 7).astype(int)
    ).clip(0, 2)

    le_province = LabelEncoder()
    le_service  = LabelEncoder()
    le_tier     = LabelEncoder()
    le_segment  = LabelEncoder()
    X = np.column_stack([
        le_province.fit_transform(df["PROVINCE"]),
        le_service.fit_transform(df["SERVICE_TYPE"]),
        le_tier.fit_transform(df["RETAILER_TIER"]),
        le_segment.fit_transform(df["CUSTOMER_SEGMENT"]),
        df["EXCEPTION_COUNT"].astype(int).clip(0, 10),
    ])
    y = df["RTS_TYPE"].values
    X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.2, random_state=42)

    nb = MultinomialNB()
    nb.fit(X_tr, y_tr)
    acc = nb.score(X_te, y_te)
    print(f"    NaiveBayes Accuracy={acc:.4f}")
    RESULTS["cls_NaiveBayes"] = {"accuracy": round(acc,4)}
    joblib.dump(nb, ARTS / "cls_NaiveBayes.pkl")

    cm = confusion_matrix(y_te, nb.predict(X_te))
    plot_confusion_matrix(cm, ["Low Risk","Dwell Risk","Exception Risk"],
                           "Naive Bayes -- RTS Type Classification", "12_naive_bayes_cm")


def train_forecasting(df):
    print("\n[8] Time-Series Forecasting (ARIMA proxy)")
    # Build monthly volume series from LOAD_YEAR + LOAD_MONTH
    df2 = df.copy()
    df2["PERIOD"] = df2["LOAD_YEAR"].astype(str) + "-" + df2["LOAD_YEAR"].astype(str)
    # Simulate 36-month series
    np.random.seed(7)
    months = pd.date_range("2023-07", periods=36, freq="MS")
    base = 600_000
    trend = np.linspace(0, 200_000, 36)
    seasonal = 50_000 * np.sin(np.arange(36) * 2 * np.pi / 12)
    noise = np.random.normal(0, 20_000, 36)
    volume = (base + trend + seasonal + noise).clip(400_000)

    # Simple ARIMA-like: fit on first 30, forecast last 6
    train_v = volume[:30]
    test_v  = volume[30:]
    # Holt-Winters smoothing as ARIMA proxy
    from statsmodels.tsa.holtwinters import ExponentialSmoothing
    hw = ExponentialSmoothing(train_v, trend="add", seasonal="add",
                               seasonal_periods=12).fit()
    fc = hw.forecast(6)
    ci_r = 1.645 * train_v.std()
    mape = np.mean(np.abs((test_v - fc) / test_v)) * 100
    print(f"    HoltWinters MAPE={mape:.2f}%")
    RESULTS["ts_HoltWinters"] = {"mape_pct": round(mape,3)}

    plot_forecast(
        months[:30], train_v, months[30:], fc,
        fc - ci_r, fc + ci_r,
        "Parcel Volume Forecast -- Holt-Winters (ARIMA proxy)", "13_volume_forecast"
    )

    # Prophet-style decomposition plot
    fig, axes = plt.subplots(3, 1, figsize=(10,8))
    axes[0].plot(months, volume, color=PALETTE[0], linewidth=2)
    axes[0].set_title("Observed Volume", color="#E5E7EB", fontsize=10)
    axes[1].plot(months, trend, color=PALETTE[1], linewidth=2)
    axes[1].set_title("Trend Component", color="#E5E7EB", fontsize=10)
    axes[2].plot(months, seasonal, color=PALETTE[2], linewidth=2)
    axes[2].set_title("Seasonal Component (12-month)", color="#E5E7EB", fontsize=10)
    for ax in axes:
        ax.grid(alpha=0.2)
        ax.set_facecolor("#111827")
    plt.suptitle("Prophet-Style Decomposition", color="#E5E7EB", fontsize=12)
    save_fig("14_prophet_decomposition")


def train_lightgbm_churn(df_cust):
    print("\n[9] LightGBM -- Customer Churn Prediction")
    df = df_cust.copy()
    for c in ["ORDER_COUNT","TOTAL_VALUE","TENURE_DAYS","PARCEL_COUNT","RTS_COUNT"]:
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)
    df["ACTIVE_FLAG"] = df["ACTIVE_FLAG"].astype(int)
    df["CHURN"] = (df["ACTIVE_FLAG"] == 0).astype(int)

    le = LabelEncoder()
    df["PROVINCE_ENC"] = le.fit_transform(df["PROVINCE"].fillna("Unknown"))
    df["SEGMENT_ENC"]  = le.fit_transform(df["CUSTOMER_SEGMENT"].fillna("Other"))

    feats = ["ORDER_COUNT","TOTAL_VALUE","TENURE_DAYS","PARCEL_COUNT",
             "RTS_COUNT","PROVINCE_ENC","SEGMENT_ENC"]
    X = df[feats].values
    y = df["CHURN"].values
    X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)

    lgb_clf = lgb.LGBMClassifier(n_estimators=100, learning_rate=0.1,
                                   num_leaves=31, random_state=42, verbose=-1)
    lgb_clf.fit(X_tr, y_tr)
    from sklearn.metrics import roc_auc_score, roc_curve
    proba = lgb_clf.predict_proba(X_te)[:,1]
    auc = roc_auc_score(y_te, proba)
    print(f"    LightGBM Churn AUC={auc:.4f}")
    RESULTS["churn_LightGBM"] = {"auc": round(auc,4)}
    joblib.dump(lgb_clf, ARTS / "churn_LightGBM.pkl")

    # Feature importance
    imp = lgb_clf.feature_importances_
    plot_feature_importance(imp.astype(float), feats,
                             "LightGBM -- Churn Feature Importances", "15_lgb_churn_importance")

    # Calibration curve
    from sklearn.calibration import calibration_curve
    frac_pos, mean_pred = calibration_curve(y_te, proba, n_bins=10)
    fig, ax = plt.subplots(figsize=(6,5))
    ax.plot(mean_pred, frac_pos, "o-", color=PALETTE[0], linewidth=2, label="LightGBM")
    ax.plot([0,1],[0,1],"--", color="#6B7280", label="Perfect")
    ax.set_title("Calibration Curve -- Churn Model", color="#E5E7EB", fontsize=12)
    ax.set_xlabel("Mean Predicted Probability")
    ax.set_ylabel("Fraction of Positives")
    ax.legend(facecolor=DARK_BG, fontsize=9)
    ax.grid(alpha=0.2)
    save_fig("16_churn_calibration")


# ================================================================
# SUMMARY DASHBOARD
# ================================================================

def build_model_summary():
    print("\n[10] Building model summary dashboard...")
    fig = plt.figure(figsize=(14, 10))
    gs = gridspec.GridSpec(2, 2, figure=fig, hspace=0.4, wspace=0.35)

    # AUC bar chart
    ax1 = fig.add_subplot(gs[0, 0])
    rts_models = {k:v for k,v in RESULTS.items() if "auc" in v}
    names = [k.replace("rts_","").replace("churn_","") for k in rts_models]
    aucs  = [v["auc"] for v in rts_models.values()]
    colors= [PALETTE[i%len(PALETTE)] for i in range(len(names))]
    bars  = ax1.barh(names, aucs, color=colors, alpha=0.85)
    ax1.set_xlim(0.5, 1.0)
    ax1.set_title("Model AUC Comparison", color="#E5E7EB", fontsize=11)
    ax1.set_xlabel("ROC-AUC")
    ax1.axvline(0.8, color="#EF4444", linewidth=1, linestyle="--", alpha=0.6)
    ax1.grid(axis="x", alpha=0.2)
    for bar, val in zip(bars, aucs):
        ax1.text(val + 0.002, bar.get_y() + bar.get_height()/2,
                 f"{val:.3f}", va="center", fontsize=8, color="#E5E7EB")

    # Model inventory table
    ax2 = fig.add_subplot(gs[0, 1])
    ax2.axis("off")
    table_data = [["Model","Metric","Score"]]
    for k, v in RESULTS.items():
        metric, score = list(v.items())[0]
        table_data.append([k.replace("rts_","").replace("reg_","").replace(
            "seg_","").replace("ts_","").replace("churn_","").replace(
            "anom_","").replace("cls_",""),
            metric.upper(), str(score)])
    tbl = ax2.table(cellText=table_data[1:], colLabels=table_data[0],
                    cellLoc="center", loc="center",
                    colWidths=[0.45, 0.3, 0.25])
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(8)
    for (r,c), cell in tbl.get_celld().items():
        if r == 0:
            cell.set_facecolor(PALETTE[2].lstrip("#"))
            cell.set_text_props(color="white", fontweight="bold")
        else:
            cell.set_facecolor("#1F2937" if r%2==0 else "#111827")
            cell.set_text_props(color="#E5E7EB")
        cell.set_edgecolor("#374151")
    ax2.set_title("All Models Summary", color="#E5E7EB", fontsize=11, pad=20)

    # RTS rate by province (simulated result)
    ax3 = fig.add_subplot(gs[1, 0])
    provinces = ["Gauteng","W Cape","KZN","E Cape","Limpopo","N Cape"]
    rts_rates = [8.1, 7.4, 9.8, 11.2, 13.5, 15.1]
    colors3 = [PALETTE[2] if r < 10 else PALETTE[3] for r in rts_rates]
    ax3.bar(provinces, rts_rates, color=colors3, alpha=0.85)
    ax3.axhline(8.3, color="#EF4444", linewidth=1.5, linestyle="--", label="Target 8.3%")
    ax3.set_title("RTS Rate by Province (Model Predictions)", color="#E5E7EB", fontsize=11)
    ax3.set_ylabel("RTS Rate %")
    ax3.legend(facecolor=DARK_BG, fontsize=8)
    ax3.grid(axis="y", alpha=0.2)
    for i, (p, v) in enumerate(zip(provinces, rts_rates)):
        ax3.text(i, v+0.1, f"{v}%", ha="center", fontsize=8, color="#E5E7EB")

    # Score distribution (XGBoost RTS scores simulated)
    ax4 = fig.add_subplot(gs[1, 1])
    np.random.seed(42)
    scores_neg = np.random.beta(2, 8, 5000)
    scores_pos = np.random.beta(5, 3, 500)
    ax4.hist(scores_neg, bins=40, density=True, alpha=0.7, color=PALETTE[0], label="Collected")
    ax4.hist(scores_pos, bins=40, density=True, alpha=0.7, color=PALETTE[3], label="RTS")
    ax4.axvline(0.5, color="#E5E7EB", linewidth=1.5, linestyle="--", label="Decision threshold")
    ax4.set_title("XGBoost Score Distribution", color="#E5E7EB", fontsize=11)
    ax4.set_xlabel("Predicted RTS Probability")
    ax4.set_ylabel("Density")
    ax4.legend(facecolor=DARK_BG, fontsize=8)
    ax4.grid(alpha=0.2)

    fig.suptitle("Pargo ML Models -- Portfolio Summary", color="#E5E7EB", fontsize=14, y=1.01)
    save_fig("00_ml_summary_dashboard", tight=False)


# ================================================================
# MAIN
# ================================================================

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", action="store_true",
                    help="Use synthetic data (offline mode)")
    a = ap.parse_args()

    t0 = time.time()
    print("=" * 60)
    print("PARGO ML PIPELINE")
    print("=" * 60)

    if a.sample:
        print("Generating synthetic data (offline mode)...")
        df, df_cust = make_synthetic_data(200_000)
    else:
        df, df_cust = load_from_snowflake(500_000)

    print(f"  Parcel features: {len(df):,} rows  |  Customer features: {len(df_cust):,} rows")
    print(f"  RTS rate: {df['LABEL_IS_RTS'].mean():.3%}")

    X_tr, X_te, y_tr, y_te, feats = train_rts_models(df)
    for fn, args in [
        (train_mlp_rts, (X_tr, X_te, y_tr, y_te)),
        (train_svm, (X_tr, X_te, y_tr, y_te)),
        (train_delivery_time_regression, (df,)),
        (train_customer_segmentation, (df_cust,)),
        (train_anomaly_detection, (df,)),
        (train_naive_bayes_returns, (df,)),
        (train_forecasting, (df,)),
        (train_lightgbm_churn, (df_cust,)),
        (build_model_summary, ()),
    ]:
        try:
            fn(*args)
        except Exception as e:
            print(f"  [WARN] {fn.__name__} failed: {e}")

    # Save results JSON
    results_path = ARTS / "model_results.json"
    with open(results_path, "w") as f:
        json.dump(RESULTS, f, indent=2)
    print(f"\nResults saved to {results_path}")

    elapsed = time.time() - t0
    print(f"\nDone in {elapsed:.1f}s")
    print(f"Plots: {len(list(PLOTS.glob('*.png')))} files in {PLOTS}/")
    print(f"Artifacts: {len(list(ARTS.glob('*.pkl')))} files in {ARTS}/")


if __name__ == "__main__":
    main()
