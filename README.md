# Pargo Parcels — Data Warehouse Portfolio

End-to-end analytics platform for South Africa's leading parcel pickup network.
Built on **Snowflake + DBT + Python + XGBoost + LightGBM**.

---

## Overview

| Metric | Value |
|--------|-------|
| Parcels | 30.2 million |
| Tracking events | 152.8 million |
| Data window | July 2023 – June 2026 (36 months) |
| Provinces | All 9 SA provinces |
| ML models | 15 trained |
| Best ROC-AUC | 0.89 (Stacking Ensemble) |

> **Dataset note:** Dashboard KPIs reflect the full 30.2M parcel enterprise-scale dataset.
> The Excel workbook uses a 1.2M parcel representative sample for spreadsheet demonstration — totals and averages will differ slightly from the dashboard figures.
> ML model metrics are validated on a held-out 20% test split of the training dataset.
> Business case impact figures (e.g. R10.1M RTS saving) are projections based on modelled RTS rates and operational cost assumptions.

## Architecture

```
Parquet files (partitioned by year/month)
        │
        ▼  PUT + COPY INTO
 Snowflake RAW schema (8 tables)
        │
        ▼  DBT
  Staging views  →  Mart tables  →  ML Feature tables
        │
        ▼  Python (scikit-learn / XGBoost / LightGBM)
   15 ML models + correlation analysis
        │
        ▼
  HTML dashboard  +  Portfolio ebook PDF
```

## Repository Structure

```
PargoParcels/
├── pargo_dashboard.html          # Interactive 6-tab Chart.js dashboard
├── pargo_ml_visuals.html         # ML model visual portfolio (33 plots)
├── pargo_data_dictionary.md      # Full column-level data dictionary
│
├── pargo_dbt/                    # DBT project
│   ├── models/staging/           # 8 staging views (stg_*)
│   ├── models/marts/             # 4 analytical mart tables
│   └── models/ml_features/       # 3 ML feature tables
│
├── ml_models/
│   ├── train_all_models.py       # 15 ML models (RTS, regression, clustering, forecasting)
│   ├── train_clv.py              # Customer Lifetime Value (3 methods + XGBoost)
│   ├── train_geo_chart.py        # SA province geographical charts
│   ├── train_correlation_charts.py # Correlation & statistical analysis (9 charts)
│   └── plots/                    # 33 generated PNG plots
│
├── data_generator/
│   ├── snowflake_batch_loader.py # Bulk parquet loader (PUT + COPY INTO)
│   ├── snowflake_tasks_alerts.sql# 3 Tasks + 2 Alerts
│   ├── snowflake_ml_procedures.sql# Snowpark ML stored procedures
│   ├── build_ebook.py            # Portfolio ebook PDF builder
│   ├── build_excel.py            # 7-sheet Excel analytics workbook
│   └── build_portfolio_zip.py    # ZIP packager for all deliverables
│
└── ebook/
    └── pargo_ebook_portfolio.pdf # Full portfolio ebook (10 sections)
```

## Tech Stack

- **Cloud Warehouse**: Snowflake (af-south-1, AWS)
- **Open-Source Alternative**: PostgreSQL (all SQL is ANSI-compatible)
- **Transformation**: DBT (staging → marts → ML features)
- **ML**: scikit-learn, XGBoost, LightGBM, statsmodels, Snowpark ML
- **Dashboards**: HTML5, Chart.js
- **PDF Generation**: ReportLab
- **Language**: Python 3.11

## ML Models Summary

| # | Model | Algorithm | Metric | Score |
|---|-------|-----------|--------|-------|
| 1 | RTS Risk v1 | Logistic Regression | ROC-AUC | 0.71 |
| 2 | RTS Risk v2 | Random Forest | ROC-AUC | 0.82 |
| 3 | RTS Risk v3 (Champion) | XGBoost | ROC-AUC | 0.87 |
| 4 | RTS Risk v4 | LightGBM | ROC-AUC | 0.86 |
| 5 | MLP Classifier | Neural Network | ROC-AUC | 0.83 |
| 6 | SVM Classifier | LinearSVC | F1 Macro | 0.76 |
| 7 | Transit Regression | Ridge Regression | MAE | 4.1h |
| 8 | Customer Segments | K-Means (k=5) | Silhouette | 0.68 |
| 9 | Anomaly Detector | Isolation Forest | Anomaly % | 5% |
| 10 | Return Classifier | Naive Bayes | Accuracy | 0.73 |
| 11 | Volume Forecast | Holt-Winters | MAPE | 12.1% |
| 12 | Seasonal Decomp | Prophet-style | R² | 77.8% |
| 13 | Churn Predictor | LightGBM | ROC-AUC | 0.79 |
| 14 | Stacking Ensemble (Champion) | Meta-learner | ROC-AUC | 0.89 |
| 15 | CLV Regressor | XGBoost | R² | 0.987 |

## Getting Started

### Snowflake Setup
```bash
pip install snowflake-connector-python pyarrow pandas scikit-learn xgboost lightgbm reportlab statsmodels
python data_generator/snowflake_batch_loader.py
```

### PostgreSQL Setup
All mart and feature table SQL is ANSI-compatible. See Section 8 of the ebook
(`ebook/pargo_ebook_portfolio.pdf`) for the Snowflake → PostgreSQL migration guide.

### Run DBT
```bash
cd pargo_dbt
dbt run
dbt test
```

### Train ML Models
```bash
python ml_models/train_all_models.py
python ml_models/train_clv.py
python ml_models/train_geo_chart.py
python ml_models/train_correlation_charts.py
```

### Build Deliverables
```bash
python data_generator/build_ebook.py
python data_generator/build_excel.py
```

## Dashboards

Open `pargo_dashboard.html` in any browser — no server required.
Open `pargo_ml_visuals.html` for the full ML visual portfolio (33 plots).

---

*Data is synthetic but structurally and statistically representative of real-world
last-mile logistics operations. Platform is production-ready on Snowflake or PostgreSQL.*
