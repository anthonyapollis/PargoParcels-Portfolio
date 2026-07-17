<div align="center">

# Pargo Parcels — Data Warehouse & ML Platform

![Snowflake](https://img.shields.io/badge/Snowflake-29B5E8?style=for-the-badge&logo=snowflake&logoColor=white)
![dbt](https://img.shields.io/badge/dbt-FF694B?style=for-the-badge&logo=dbt&logoColor=white)
![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)
![XGBoost](https://img.shields.io/badge/XGBoost-FF6600?style=for-the-badge)
![LightGBM](https://img.shields.io/badge/LightGBM-02569B?style=for-the-badge)

**End-to-end analytics platform for South Africa's leading parcel pickup-point network.**  
Raw Parquet → Snowflake → dbt → 15 ML Models → Interactive Dashboard

[![Live Dashboard](https://img.shields.io/badge/Open_Live_Dashboard-3B82F6?style=for-the-badge)](https://pargoparcels.netlify.app/)
[![ML Visuals](https://img.shields.io/badge/ML_Visual_Portfolio-8B5CF6?style=for-the-badge)](https://pargoparcels.netlify.app/pargo_ml_visuals.html)

</div>

---

## ⚡ Key Numbers

| | |
|--|--|
| 📦 **30.2 million** parcels | 📡 **210 million** tracking events |
| 🗓 **36 months** of data (Jul 2023 – Jun 2026) | 🗺 **9** SA provinces |
| 🤖 **15** ML models trained | 🏆 **0.81** ROC-AUC (Stacking Ensemble) |
| 💰 **R10.1M** projected RTS cost saving (5.5% baseline, ML intervention scenario) | 📊 **6-tab** interactive dashboard |

---

## 🏗 Architecture

```
Parquet files (partitioned by year/month)
        │
        ▼  PUT + COPY INTO
 Snowflake RAW schema (8 tables)
        │
        ▼  dbt
  Staging views  →  Mart tables  →  ML Feature tables
        │
        ▼  Python (scikit-learn · XGBoost · LightGBM)
   15 ML models + correlation analysis
        │
        ▼
  HTML dashboard  +  Excel workbook  +  Portfolio ebook PDF
```

---

## 🤖 Machine Learning Models

| Category | Models | Best Metric |
|----------|--------|-------------|
| **RTS Classification** | Logistic Regression, Decision Tree, Random Forest, XGBoost, LightGBM, SVM, MLP, Stacking Ensemble | **AUC 0.81** (Stacking) |
| **Regression** | Ridge, Lasso, XGBoost Regressor | Delivery time prediction |
| **Clustering** | K-Means (5 clusters) | Customer segmentation |
| **Forecasting** | Time-series parcel volume | 12-month outlook |
| **CLV** | 3 methods + XGBoost | Customer lifetime value |

> **Dataset note:** ML metrics validated on a held-out 20% test split. Business impact figures are projections based on modelled RTS rates and operational cost assumptions.

---

## 📁 What's in This Repo

| File / Folder | What it is |
|---------------|-----------|
| `pargo_dashboard.html` | Interactive 6-tab Chart.js dashboard — open directly in browser |
| `pargo_ml_visuals.html` | 33 ML visualisation plots (ROC, confusion matrix, SHAP, etc.) |
| `pargo_dbt/` | Full dbt project: 8 staging views, 4 marts, 3 ML feature tables |
| `ml_models/` | Training scripts for all 15 models |
| `data/` | Sample parquet data + generated CSVs |
| `snowflake/` | DDL + COPY INTO scripts |
| `excel/` | Excel workbook (1.2M parcel sample, pivot-ready) |
| `ebook/` | Portfolio PDF ebook |
| `plots/` | All 33 saved PNG plots |

---

## 🚀 Quick Start

**1. Open the dashboard (no install needed)**
```
Download pargo_dashboard.html → double-click to open in any browser
```

**2. Run dbt models**
```bash
cd pargo_dbt
dbt deps && dbt run
```

**3. Retrain ML models**
```bash
pip install -r requirements.txt
python ml_models/train_all_models.py
```

---

## 📊 Dashboard Tabs

1. **Overview** — KPIs, volume trend, province map
2. **Operations** — Transit hours, dwell days, courier exceptions
3. **Retailers** — Revenue ranking, SLA compliance by retailer tier
4. **SLA** — Breach types, long-dwell parcels, slow-transit rates
5. **ML Models** — ROC-AUC comparison, feature importance, model inventory
6. **Architecture** — Data pipeline layers, dbt model graph, tech stack

---

<div align="center">

[![Full Portfolio](https://img.shields.io/badge/Full_Portfolio-anthonyapollis.github.io-3B82F6?style=for-the-badge)](https://anthonyapollis.github.io)
[![GitHub Profile](https://img.shields.io/badge/GitHub_Profile-anthonyapollis-181717?style=for-the-badge&logo=github)](https://github.com/anthonyapollis)

**Anthony Apollis · Data Engineer & Analytics Specialist · South Africa**

</div>
