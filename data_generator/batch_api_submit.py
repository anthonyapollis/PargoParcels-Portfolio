"""
Pargo Portfolio -- Claude Batch API Submission
==============================================
Submits 20 requests at 50% discount (async batch):
  - 5 ebook variant outlines
  - 15 ML model descriptions

Usage:
    python batch_api_submit.py --submit        # create batch, save batch_id to batch_id.txt
    python batch_api_submit.py --retrieve      # poll status and write results to batch_results/
"""
import argparse, json, time
from pathlib import Path
import anthropic

ANTHROPIC_API_KEY = "YOUR_ANTHROPIC_API_KEY"   # set here or via env ANTHROPIC_API_KEY

MODEL = "claude-opus-4-8"

# -------------------------------------------------------
# 5 Ebook variant prompts
# -------------------------------------------------------
EBOOK_PROMPTS = [
    (
        "ebook_executive_summary",
        """You are a senior business consultant writing for a C-suite audience.
Write a 2,000-word executive summary ebook chapter for the Pargo Parcels Data Warehouse completed project.
Cover: business problem solved, scale (30M parcels, 150M tracking events, 36 months), key KPIs,
ROI justification, and recommended next steps for a last-mile logistics company in South Africa.
Use professional tone, include a 5-point summary at the start."""
    ),
    (
        "ebook_technical_deepdive",
        """You are a senior data engineer writing for a technical audience.
Write a 2,500-word technical deep-dive ebook chapter for the Pargo Parcels DW.
Cover: Snowflake architecture (RAW/STAGING/MARTS/ML_FEATURES layers), DBT model DAG,
batch loading strategy (PUT + COPY INTO, cost optimisation), clustering keys, Snowflake Tasks and Alerts.
Include a diagram description in ASCII art and SQL code examples."""
    ),
    (
        "ebook_operations_focus",
        """You are an operations analyst writing for logistics operations managers.
Write a 2,000-word ebook chapter focused on parcel operations insights from the Pargo DW.
Cover: SLA tracking (dwell days, transit hours), RTS rate analysis, courier performance,
pickup point capacity utilisation, and actionable recommendations.
Include a sample KPI scorecard table."""
    ),
    (
        "ebook_business_case",
        """You are a business analyst writing a business case for a data warehouse investment.
Write a 1,800-word ebook chapter making the business case for the Pargo Parcels DW.
Cover: before/after state, time-to-insight reduction, cost per query vs legacy approach,
ML capability unlocked, competitive differentiation in last-mile logistics.
Include ROI calculation assumptions and a 3-year cost-benefit table."""
    ),
    (
        "ebook_ml_analytics",
        """You are an ML engineer writing for a data science audience.
Write a 2,500-word ebook chapter on the ML and analytics layer of the Pargo Parcels DW.
Cover: 15 ML models (RTS risk, customer LTV, courier reliability, demand forecasting,
anomaly detection), feature engineering from tracking events, model evaluation metrics,
Snowflake ML stored procedures, and production deployment pattern.
Include Python pseudocode for the XGBoost RTS risk model."""
    ),
]

# -------------------------------------------------------
# 15 ML model description prompts
# -------------------------------------------------------
ML_MODELS = [
    ("ml_logistic_regression",   "logistic regression",  "RTS risk binary classification"),
    ("ml_random_forest",          "random forest",        "parcel delay multiclass classification"),
    ("ml_xgboost",                "XGBoost",              "RTS risk with feature importance"),
    ("ml_lightgbm",               "LightGBM",             "customer churn prediction"),
    ("ml_mlp_neural_net",         "MLP neural network",   "delivery time regression"),
    ("ml_ridge_regression",       "ridge regression",     "parcel value prediction"),
    ("ml_decision_tree",          "decision tree",        "SLA breach root cause analysis"),
    ("ml_kmeans",                 "K-Means clustering",   "customer segmentation"),
    ("ml_isolation_forest",       "isolation forest",     "anomaly detection in tracking events"),
    ("ml_arima",                  "ARIMA",                "monthly parcel volume forecasting"),
    ("ml_prophet",                "Facebook Prophet",     "seasonal demand forecasting"),
    ("ml_svm",                    "SVM",                  "courier performance classification"),
    ("ml_naive_bayes",            "naive Bayes",          "return reason classification"),
    ("ml_autoencoder",            "autoencoder",          "fraud/anomaly detection in parcel values"),
    ("ml_ensemble",               "stacked ensemble",     "final RTS prediction combining all models"),
]

ML_PROMPT_TEMPLATE = """You are a senior ML engineer documenting a production model for a last-mile logistics portfolio.
Write a 600-word technical description for a {model_type} model applied to {use_case} in the Pargo Parcels Data Warehouse.

Include:
1. Problem statement and why this model type is appropriate
2. Feature set (draw from: TRANSIT_HOURS, DWELL_DAYS, EXCEPTION_COUNT, PARCEL_WEIGHT_KG,
   PARCEL_VALUE_ZAR, PROVINCE, SERVICE_TYPE, TRACKING_EVENT_COUNT, RETAILER_TIER, CUSTOMER_SEGMENT)
3. Training approach (train/validation/test split, cross-validation strategy)
4. Key hyperparameters and tuning approach
5. Evaluation metrics (with expected ranges for logistics data)
6. Production deployment pattern in Snowflake (stored procedure or Python UDF)
7. Business impact and how predictions are consumed

Use technical but clear language. Include a short Python code snippet showing model training."""


def build_requests():
    requests = []

    for custom_id, system_prompt in EBOOK_PROMPTS:
        requests.append({
            "custom_id": custom_id,
            "params": {
                "model": MODEL,
                "max_tokens": 4096,
                "messages": [{"role": "user", "content": system_prompt}],
            }
        })

    for custom_id, model_type, use_case in ML_MODELS:
        prompt = ML_PROMPT_TEMPLATE.format(model_type=model_type, use_case=use_case)
        requests.append({
            "custom_id": custom_id,
            "params": {
                "model": MODEL,
                "max_tokens": 2048,
                "messages": [{"role": "user", "content": prompt}],
            }
        })

    return requests


def submit_batch(client):
    reqs = build_requests()
    print(f"Submitting {len(reqs)} requests to Claude Batch API...")
    batch = client.messages.batches.create(requests=reqs)
    batch_id = batch.id
    print(f"Batch created: {batch_id}")
    print(f"Status: {batch.processing_status}")
    Path("batch_id.txt").write_text(batch_id)
    print("Saved batch_id to batch_id.txt")
    return batch_id


def retrieve_results(client):
    batch_id = Path("batch_id.txt").read_text().strip()
    print(f"Checking batch {batch_id}...")

    while True:
        batch = client.messages.batches.retrieve(batch_id)
        print(f"  Status: {batch.processing_status} | "
              f"succeeded={batch.request_counts.succeeded} "
              f"errored={batch.request_counts.errored} "
              f"processing={batch.request_counts.processing}")

        if batch.processing_status == "ended":
            break
        print("  Not done yet, waiting 60s...")
        time.sleep(60)

    out_dir = Path("batch_results")
    out_dir.mkdir(exist_ok=True)

    for result in client.messages.batches.results(batch_id):
        cid = result.custom_id
        if result.result.type == "succeeded":
            text = result.result.message.content[0].text
            (out_dir / f"{cid}.md").write_text(text, encoding="utf-8")
            print(f"  Saved {cid}.md ({len(text)} chars)")
        else:
            err = result.result.error
            print(f"  ERROR {cid}: {err.type} -- {getattr(err, 'message', '')}")

    print(f"\nAll results saved to {out_dir}/")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--submit",   action="store_true")
    ap.add_argument("--retrieve", action="store_true")
    a = ap.parse_args()

    import os
    api_key = os.environ.get("ANTHROPIC_API_KEY", ANTHROPIC_API_KEY)
    client = anthropic.Anthropic(api_key=api_key)

    if a.submit:
        submit_batch(client)
    elif a.retrieve:
        retrieve_results(client)
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
