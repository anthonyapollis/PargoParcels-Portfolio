-- ============================================================
-- PARGO DW -- ML Stored Procedures & Feature Store Views
-- ============================================================
USE DATABASE PARGO_DW;
CREATE SCHEMA IF NOT EXISTS PARGO_DW.ML_STORE;
USE SCHEMA PARGO_DW.ML_STORE;

-- -------------------------------------------------------
-- View: RTS Risk Feature Store
-- -------------------------------------------------------
CREATE OR REPLACE VIEW PARGO_DW.ML_STORE.V_RTS_FEATURES AS
SELECT
    p.PARCEL_ID,
    p.PARCEL_WEIGHT_KG,
    p.PARCEL_VALUE_ZAR,
    p.DELIVERY_COST_ZAR,
    DATEDIFF('hour', p.DISPATCHED_AT, p.ARRIVED_AT_POINT_AT)   AS TRANSIT_HOURS,
    DATEDIFF('day',  p.ARRIVED_AT_POINT_AT, p.COLLECTED_AT)    AS DWELL_DAYS,
    p.PROVINCE,
    p.SERVICE_TYPE,
    r.TIER                  AS RETAILER_TIER,
    c.CUSTOMER_SEGMENT,
    c.ACTIVE_FLAG,
    COALESCE(t.EVENT_COUNT, 0)      AS TRACKING_EVENT_COUNT,
    COALESCE(t.EXCEPTION_COUNT, 0)  AS EXCEPTION_COUNT,
    CASE WHEN p.PARCEL_STATUS = 'RTS' THEN 1 ELSE 0 END AS LABEL_IS_RTS
FROM PARGO_DW.RAW.FACT_PARCELS p
LEFT JOIN PARGO_DW.RAW.DIM_RETAILERS  r ON p.RETAILER_ID  = r.RETAILER_ID
LEFT JOIN PARGO_DW.RAW.DIM_CUSTOMERS  c ON p.CUSTOMER_ID  = c.CUSTOMER_ID
LEFT JOIN (
    SELECT PARCEL_ID,
           COUNT(*)                                           AS EVENT_COUNT,
           SUM(CASE WHEN EVENT_TYPE='EXCEPTION' THEN 1 ELSE 0 END) AS EXCEPTION_COUNT
    FROM PARGO_DW.RAW.FACT_TRACKING_EVENTS
    GROUP BY 1
) t ON p.PARCEL_ID = t.PARCEL_ID
WHERE p.PARCEL_STATUS IN ('COLLECTED','RTS');

-- -------------------------------------------------------
-- View: Customer LTV Feature Store
-- -------------------------------------------------------
CREATE OR REPLACE VIEW PARGO_DW.ML_STORE.V_CUSTOMER_LTV_FEATURES AS
SELECT
    c.CUSTOMER_ID,
    c.PROVINCE,
    c.CUSTOMER_SEGMENT,
    c.ACTIVE_FLAG,
    COALESCE(os.ORDER_COUNT, 0)        AS ORDER_COUNT,
    COALESCE(os.TOTAL_ORDER_VALUE, 0)  AS TOTAL_ORDER_VALUE,
    COALESCE(os.AVG_ORDER_VALUE, 0)    AS AVG_ORDER_VALUE,
    COALESCE(os.TENURE_DAYS, 0)        AS TENURE_DAYS,
    COALESCE(ps.PARCEL_COUNT, 0)       AS PARCEL_COUNT,
    COALESCE(ps.RTS_COUNT, 0)          AS RTS_COUNT
FROM PARGO_DW.RAW.DIM_CUSTOMERS c
LEFT JOIN (
    SELECT CUSTOMER_ID,
           COUNT(*)             AS ORDER_COUNT,
           SUM(ORDER_VALUE_ZAR) AS TOTAL_ORDER_VALUE,
           AVG(ORDER_VALUE_ZAR) AS AVG_ORDER_VALUE,
           DATEDIFF('day', MIN(ORDER_CREATED_AT), MAX(ORDER_CREATED_AT)) AS TENURE_DAYS
    FROM PARGO_DW.RAW.FACT_ORDERS
    GROUP BY 1
) os ON c.CUSTOMER_ID = os.CUSTOMER_ID
LEFT JOIN (
    SELECT CUSTOMER_ID,
           COUNT(*) AS PARCEL_COUNT,
           COUNT_IF(PARCEL_STATUS='RTS') AS RTS_COUNT
    FROM PARGO_DW.RAW.FACT_PARCELS
    GROUP BY 1
) ps ON c.CUSTOMER_ID = ps.CUSTOMER_ID;

-- -------------------------------------------------------
-- Stored Procedure: Score new parcels for RTS risk
-- (Python UDF pattern -- requires Snowpark)
-- -------------------------------------------------------
CREATE OR REPLACE PROCEDURE PARGO_DW.ML_STORE.SP_SCORE_RTS_RISK(BATCH_DATE VARCHAR)
RETURNS VARCHAR
LANGUAGE PYTHON
RUNTIME_VERSION = '3.11'
PACKAGES = ('snowflake-snowpark-python', 'scikit-learn', 'pandas', 'numpy')
HANDLER = 'score_rts_risk'
AS $$
import pandas as pd
import numpy as np
from snowflake.snowpark.functions import col

def score_rts_risk(session, batch_date: str) -> str:
    """
    Score parcels created on batch_date for RTS risk.
    Returns count of high-risk parcels flagged.
    """
    df = session.table('PARGO_DW.ML_STORE.V_RTS_FEATURES') \
        .filter(col('PARCEL_ID').isNotNull()) \
        .to_pandas()

    if df.empty:
        return "No parcels to score"

    # Feature engineering
    features = ['PARCEL_WEIGHT_KG','PARCEL_VALUE_ZAR','TRANSIT_HOURS',
                'DWELL_DAYS','TRACKING_EVENT_COUNT','EXCEPTION_COUNT']
    X = df[features].fillna(0)

    # Heuristic RTS risk score (replace with trained model coefficients)
    weights = [0.05, -0.02, 0.08, 0.15, -0.03, 0.25]
    risk_score = (X * weights).sum(axis=1)
    risk_score = 1 / (1 + np.exp(-risk_score))   # sigmoid

    df['RTS_RISK_SCORE'] = risk_score
    df['HIGH_RISK'] = (risk_score > 0.6).astype(int)

    high_risk_count = int(df['HIGH_RISK'].sum())

    # Write scores back
    out = df[['PARCEL_ID','RTS_RISK_SCORE','HIGH_RISK']].copy()
    out['SCORED_AT'] = batch_date
    session.write_pandas(out, 'RTS_RISK_SCORES',
                         database='PARGO_DW', schema='ML_STORE',
                         auto_create_table=True, overwrite=False)

    return f"Scored {len(df)} parcels; {high_risk_count} flagged high risk"
$$;

-- Support table
CREATE TABLE IF NOT EXISTS PARGO_DW.ML_STORE.RTS_RISK_SCORES (
    PARCEL_ID       NUMBER,
    RTS_RISK_SCORE  FLOAT,
    HIGH_RISK       NUMBER,
    SCORED_AT       VARCHAR(20)
);

-- -------------------------------------------------------
-- Stored Procedure: Customer LTV segments
-- -------------------------------------------------------
CREATE OR REPLACE PROCEDURE PARGO_DW.ML_STORE.SP_SEGMENT_CUSTOMERS()
RETURNS VARCHAR
LANGUAGE PYTHON
RUNTIME_VERSION = '3.11'
PACKAGES = ('snowflake-snowpark-python', 'scikit-learn', 'pandas', 'numpy')
HANDLER = 'segment_customers'
AS $$
import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans

def segment_customers(session) -> str:
    df = session.table('PARGO_DW.ML_STORE.V_CUSTOMER_LTV_FEATURES').to_pandas()

    features = ['ORDER_COUNT','TOTAL_ORDER_VALUE','AVG_ORDER_VALUE',
                'TENURE_DAYS','PARCEL_COUNT','RTS_COUNT']
    X = df[features].fillna(0)

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    km = KMeans(n_clusters=5, random_state=42, n_init=10)
    df['LTV_SEGMENT'] = km.fit_predict(X_scaled)

    seg_map = {0: 'HIGH_VALUE', 1: 'OCCASIONAL', 2: 'CHURNED',
               3: 'NEW', 4: 'AT_RISK'}
    df['SEGMENT_LABEL'] = df['LTV_SEGMENT'].map(seg_map)

    out = df[['CUSTOMER_ID','LTV_SEGMENT','SEGMENT_LABEL']].copy()
    session.write_pandas(out, 'CUSTOMER_LTV_SEGMENTS',
                         database='PARGO_DW', schema='ML_STORE',
                         auto_create_table=True, overwrite=True)

    counts = df.groupby('SEGMENT_LABEL').size().to_dict()
    return f"Segmented {len(df)} customers: {counts}"
$$;

CREATE TABLE IF NOT EXISTS PARGO_DW.ML_STORE.CUSTOMER_LTV_SEGMENTS (
    CUSTOMER_ID     NUMBER,
    LTV_SEGMENT     NUMBER,
    SEGMENT_LABEL   VARCHAR(50)
);
