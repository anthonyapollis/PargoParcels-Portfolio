"""
Pargo DW -- Portfolio ZIP Builder
===================================
Assembles the complete portfolio deliverable into a single ZIP.

Usage:
    python build_portfolio_zip.py

Output: PargoParcels_Portfolio_v1.zip (in project root)
"""
import zipfile
from pathlib import Path

ROOT = Path("..").resolve()

FILES = [
    # Dashboards
    ("pargo_dashboard.html",               "dashboard/pargo_dashboard.html"),
    ("pargo_ml_visuals.html",              "dashboard/pargo_ml_visuals.html"),
    # Data Dictionary
    ("pargo_data_dictionary.md",           "docs/pargo_data_dictionary.md"),
    # DBT project
    ("pargo_dbt/dbt_project.yml",          "dbt/dbt_project.yml"),
    ("pargo_dbt/profiles.yml",             "dbt/profiles.yml"),
    ("pargo_dbt/models/staging/sources.yml","dbt/models/staging/sources.yml"),
    ("pargo_dbt/models/staging/schema.yml","dbt/models/staging/schema.yml"),
    ("pargo_dbt/models/staging/stg_couriers.sql","dbt/models/staging/stg_couriers.sql"),
    ("pargo_dbt/models/staging/stg_customers.sql","dbt/models/staging/stg_customers.sql"),
    ("pargo_dbt/models/staging/stg_pickup_points.sql","dbt/models/staging/stg_pickup_points.sql"),
    ("pargo_dbt/models/staging/stg_retailers.sql","dbt/models/staging/stg_retailers.sql"),
    ("pargo_dbt/models/staging/stg_orders.sql","dbt/models/staging/stg_orders.sql"),
    ("pargo_dbt/models/staging/stg_parcels.sql","dbt/models/staging/stg_parcels.sql"),
    ("pargo_dbt/models/staging/stg_tracking_events.sql","dbt/models/staging/stg_tracking_events.sql"),
    ("pargo_dbt/models/staging/stg_returns.sql","dbt/models/staging/stg_returns.sql"),
    ("pargo_dbt/models/marts/mart_parcel_performance.sql","dbt/models/marts/mart_parcel_performance.sql"),
    ("pargo_dbt/models/marts/mart_daily_ops.sql","dbt/models/marts/mart_daily_ops.sql"),
    ("pargo_dbt/models/marts/mart_retailer_scorecard.sql","dbt/models/marts/mart_retailer_scorecard.sql"),
    ("pargo_dbt/models/marts/mart_sla_breaches.sql","dbt/models/marts/mart_sla_breaches.sql"),
    ("pargo_dbt/models/ml_features/feat_parcel_rts_risk.sql","dbt/models/ml_features/feat_parcel_rts_risk.sql"),
    ("pargo_dbt/models/ml_features/feat_customer_ltv.sql","dbt/models/ml_features/feat_customer_ltv.sql"),
    ("pargo_dbt/models/ml_features/feat_courier_reliability.sql","dbt/models/ml_features/feat_courier_reliability.sql"),
    # Snowflake SQL
    ("data_generator/snowflake_tasks_alerts.sql","snowflake/snowflake_tasks_alerts.sql"),
    ("data_generator/snowflake_ml_procedures.sql","snowflake/snowflake_ml_procedures.sql"),
    ("data_generator/snowflake_batch_loader.py","snowflake/snowflake_batch_loader.py"),
    # Build scripts
    ("data_generator/batch_api_submit.py","scripts/batch_api_submit.py"),
    ("data_generator/build_excel.py","scripts/build_excel.py"),
    ("data_generator/build_ebook.py","scripts/build_ebook.py"),
    ("data_generator/generate_pargo_data.py","scripts/generate_pargo_data.py"),
    ("data_generator/resumable_runner.py","scripts/resumable_runner.py"),
    ("ml_models/train_all_models.py",     "ml_models/train_all_models.py"),
    ("ml_models/train_clv.py",            "ml_models/train_clv.py"),
    ("ml_models/train_geo_chart.py",      "ml_models/train_geo_chart.py"),
]

# Optional: ebooks and Excel if they exist
OPTIONAL = [
    ("ebook/pargo_ebook_portfolio.pdf",           "ebook/pargo_ebook_portfolio.pdf"),
    ("ebook/pargo_ebook_executive_summary.pdf",  "ebook/pargo_ebook_executive_summary.pdf"),
    ("ebook/pargo_ebook_technical_deepdive.pdf", "ebook/pargo_ebook_technical_deepdive.pdf"),
    ("ebook/pargo_ebook_operations_focus.pdf",    "ebook/pargo_ebook_operations_focus.pdf"),
    ("ebook/pargo_ebook_business_case.pdf",      "ebook/pargo_ebook_business_case.pdf"),
    ("ebook/pargo_ebook_ml_analytics.pdf",       "ebook/pargo_ebook_ml_analytics.pdf"),
    ("PargoParcels_Analytics.xlsx",              "excel/PargoParcels_Analytics.xlsx"),
    ("ml_models/plots/00_ml_summary_dashboard.png",  "ml_models/plots/00_ml_summary_dashboard.png"),
    ("ml_models/plots/01_rts_roc_curves.png",        "ml_models/plots/01_rts_roc_curves.png"),
    ("ml_models/plots/02_xgb_feature_importance.png","ml_models/plots/02_xgb_feature_importance.png"),
    ("ml_models/plots/03_best_confusion_matrix.png", "ml_models/plots/03_best_confusion_matrix.png"),
    ("ml_models/plots/04_mlp_loss_curve.png",        "ml_models/plots/04_mlp_loss_curve.png"),
    ("ml_models/plots/05_svm_confusion_matrix.png",  "ml_models/plots/05_svm_confusion_matrix.png"),
    ("ml_models/plots/06_ridge_residuals.png",       "ml_models/plots/06_ridge_residuals.png"),
    ("ml_models/plots/07_kmeans_elbow_silhouette.png","ml_models/plots/07_kmeans_elbow_silhouette.png"),
    ("ml_models/plots/08_kmeans_segments.png",       "ml_models/plots/08_kmeans_segments.png"),
    ("ml_models/plots/09_segment_heatmap.png",       "ml_models/plots/09_segment_heatmap.png"),
    ("ml_models/plots/10_isolation_forest.png",      "ml_models/plots/10_isolation_forest.png"),
    ("ml_models/plots/11_anomaly_feature_dist.png",  "ml_models/plots/11_anomaly_feature_dist.png"),
    ("ml_models/plots/12_naive_bayes_cm.png",        "ml_models/plots/12_naive_bayes_cm.png"),
    ("ml_models/plots/13_volume_forecast.png",       "ml_models/plots/13_volume_forecast.png"),
    ("ml_models/plots/14_prophet_decomposition.png", "ml_models/plots/14_prophet_decomposition.png"),
    ("ml_models/plots/15_lgb_churn_importance.png",  "ml_models/plots/15_lgb_churn_importance.png"),
    ("ml_models/plots/16_churn_calibration.png",     "ml_models/plots/16_churn_calibration.png"),
    ("ml_models/artifacts/model_results.json",       "ml_models/artifacts/model_results.json"),
    ("ml_models/plots/17_clv_distributions.png",    "ml_models/plots/17_clv_distributions.png"),
    ("ml_models/plots/18_clv_by_province.png",      "ml_models/plots/18_clv_by_province.png"),
    ("ml_models/plots/19_clv_deciles.png",           "ml_models/plots/19_clv_deciles.png"),
    ("ml_models/plots/20_clv_churn_matrix.png",     "ml_models/plots/20_clv_churn_matrix.png"),
    ("ml_models/plots/21_clv_feature_importance.png","ml_models/plots/21_clv_feature_importance.png"),
    ("ml_models/plots/22_sa_province_map.png",      "ml_models/plots/22_sa_province_map.png"),
    ("ml_models/plots/23_province_detail.png",      "ml_models/plots/23_province_detail.png"),
    ("ml_models/artifacts/clv_sample.csv",           "ml_models/artifacts/clv_sample.csv"),
    ("ml_models/plots/30_correlation_matrix.png",       "ml_models/plots/30_correlation_matrix.png"),
    ("ml_models/plots/31_feature_target_correlation.png","ml_models/plots/31_feature_target_correlation.png"),
    ("ml_models/plots/32_scatter_matrix.png",            "ml_models/plots/32_scatter_matrix.png"),
    ("ml_models/plots/33_province_feature_heatmap.png",  "ml_models/plots/33_province_feature_heatmap.png"),
    ("ml_models/plots/34_rts_by_category_province.png",  "ml_models/plots/34_rts_by_category_province.png"),
    ("ml_models/plots/35_feature_distributions.png",     "ml_models/plots/35_feature_distributions.png"),
    ("ml_models/plots/36_clv_correlations.png",          "ml_models/plots/36_clv_correlations.png"),
    ("ml_models/plots/37_timeseries_correlation.png",    "ml_models/plots/37_timeseries_correlation.png"),
    ("ml_models/plots/38_multifeature_relationships.png","ml_models/plots/38_multifeature_relationships.png"),
    ("ml_models/train_correlation_charts.py",            "ml_models/train_correlation_charts.py"),
]


def main():
    out = ROOT / "PargoParcels_Portfolio_v1.zip"
    total = 0
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for src_rel, arc_name in FILES:
            src = ROOT / src_rel
            if src.exists():
                zf.write(src, arc_name)
                size = src.stat().st_size
                total += size
                print(f"  + {arc_name} ({size//1024}KB)")
            else:
                print(f"  ! MISSING: {src_rel}")

        for src_rel, arc_name in OPTIONAL:
            src = ROOT / src_rel
            if src.exists():
                zf.write(src, arc_name)
                size = src.stat().st_size
                total += size
                print(f"  + {arc_name} ({size//1024}KB) [optional]")

    zip_size = out.stat().st_size
    print(f"\nZIP: {out.name}")
    print(f"  Uncompressed: {total//1024//1024}MB")
    print(f"  Compressed:   {zip_size//1024//1024}MB")
    print(f"  Saved to: {out}")


if __name__ == "__main__":
    main()
