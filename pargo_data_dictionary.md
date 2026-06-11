# Pargo Parcels Data Warehouse -- Data Dictionary

**Project:** PargoParcels Portfolio  
**Platform:** Snowflake (account: <your-account>.region.aws  
**Database:** PARGO_DW  
**Schemas:** RAW | STAGING | MARTS | ML_FEATURES | ML_STORE  
**Date range:** 2023-07-01 to 2026-06-30 (36 months)

---

## Table of Contents
1. [Dimension Tables (RAW)](#dimension-tables)
2. [Fact Tables (RAW)](#fact-tables)
3. [STAGING Views (DBT)](#staging-views)
4. [MARTS Tables (DBT)](#marts-tables)
5. [ML Features Tables (DBT)](#ml-features)
6. [ML Store Views & Procedures](#ml-store)
7. [Business Glossary](#business-glossary)

---

## Dimension Tables

### DIM_COURIERS
| Column | Type | Description |
|--------|------|-------------|
| COURIER_ID | NUMBER | Surrogate key, unique courier identifier |
| COURIER_NAME | VARCHAR(200) | Full name of the courier |
| REGION | VARCHAR(100) | Geographic region (e.g., Gauteng, Western Cape) |
| VEHICLE_TYPE | VARCHAR(100) | Delivery vehicle: Motorcycle, Car, Van, Truck |
| HIRED_DATE | TIMESTAMP_NTZ | Date the courier was onboarded |

**Row count:** 500  
**Notes:** Static dimension — no partitioning

---

### DIM_CUSTOMERS
| Column | Type | Description |
|--------|------|-------------|
| CUSTOMER_ID | NUMBER | Surrogate key, unique customer identifier |
| CUSTOMER_NAME | VARCHAR(300) | Full name |
| MOBILE_NUMBER | VARCHAR(50) | Contact number (masked in production) |
| PROVINCE | VARCHAR(100) | South African province of registration |
| CITY | VARCHAR(150) | City of registration |
| REGISTRATION_DATE | TIMESTAMP_NTZ | Date customer registered on platform |
| CUSTOMER_SEGMENT | VARCHAR(100) | Segment: Premium, Regular, Occasional, New |
| ACTIVE_FLAG | BOOLEAN | TRUE if customer placed order in last 90 days |

**Row count:** 10,000,000  
**Notes:** Static dimension; ~0.5% intentionally dirty rows for data quality testing

---

### DIM_PICKUP_POINTS
| Column | Type | Description |
|--------|------|-------------|
| PICKUP_POINT_ID | NUMBER | Surrogate key |
| STORE_NAME | VARCHAR(300) | Name of the partner store |
| PARTNER_NAME | VARCHAR(200) | Retail partner name (Pick n Pay, Pep, Checkers, etc.) |
| PROVINCE | VARCHAR(100) | Province location |
| CITY | VARCHAR(150) | City location |
| LATITUDE | FLOAT | GPS latitude |
| LONGITUDE | FLOAT | GPS longitude |
| OPENING_DATE | TIMESTAMP_NTZ | Date point became active |
| CAPACITY_PER_DAY | NUMBER | Max parcels storable simultaneously |
| STATUS | VARCHAR(50) | active / inactive / suspended |

**Row count:** 4,000

---

### DIM_RETAILERS
| Column | Type | Description |
|--------|------|-------------|
| RETAILER_ID | NUMBER | Surrogate key |
| RETAILER_NAME | VARCHAR(300) | Retailer name |
| INDUSTRY | VARCHAR(150) | Industry vertical: E-commerce, Fashion, Health, etc. |
| TIER | VARCHAR(50) | Contract tier: Enterprise, Mid-Market, SMB |
| CONTRACT_START_DATE | TIMESTAMP_NTZ | Date of first contract |
| RATE_PER_PARCEL_ZAR | FLOAT | Billed delivery rate per parcel (ZAR) |
| INTEGRATION_TYPE | VARCHAR(100) | API, Webhook, Manual, EDI |

**Row count:** 150

---

## Fact Tables

### FACT_ORDERS
| Column | Type | Description |
|--------|------|-------------|
| ORDER_ID | NUMBER | Surrogate key |
| CUSTOMER_ID | NUMBER | FK -> DIM_CUSTOMERS |
| RETAILER_ID | NUMBER | FK -> DIM_RETAILERS |
| ORDER_CREATED_AT | TIMESTAMP_NTZ | Order placement timestamp |
| ORDER_VALUE_ZAR | FLOAT | Total order value in ZAR |
| CHANNEL | VARCHAR(100) | Sales channel: WEB, APP, MOBILE_WEB |
| LOAD_YEAR | NUMBER | Partition year (2023-2026) |
| LOAD_MONTH | VARCHAR(7) | Partition month (YYYY-MM) |

**Row count:** ~25,000,000  
**Clustering:** CLUSTER BY (LOAD_YEAR, TO_DATE(ORDER_CREATED_AT))

---

### FACT_PARCELS
| Column | Type | Description |
|--------|------|-------------|
| PARCEL_ID | NUMBER | Surrogate key |
| ORDER_ID | NUMBER | FK -> FACT_ORDERS |
| CUSTOMER_ID | NUMBER | FK -> DIM_CUSTOMERS |
| RETAILER_ID | NUMBER | FK -> DIM_RETAILERS |
| PICKUP_POINT_ID | NUMBER | FK -> DIM_PICKUP_POINTS |
| COURIER_ID | NUMBER | FK -> DIM_COURIERS |
| WAYBILL_NUMBER | VARCHAR(50) | External tracking number |
| CREATED_AT | TIMESTAMP_NTZ | Parcel creation (order fulfilled) |
| DISPATCHED_AT | TIMESTAMP_NTZ | Handed to courier |
| ARRIVED_AT_POINT_AT | TIMESTAMP_NTZ | Arrived at pickup point |
| NOTIFIED_AT | TIMESTAMP_NTZ | Customer notification sent |
| COLLECTED_AT | TIMESTAMP_NTZ | Customer collected parcel (NULL if not collected) |
| RTS_AT | TIMESTAMP_NTZ | Return-to-sender initiated (NULL if collected) |
| PARCEL_STATUS | VARCHAR(50) | CREATED, IN_TRANSIT, AT_PICKUP, COLLECTED, RTS |
| PARCEL_VALUE_ZAR | FLOAT | Declared parcel value |
| PARCEL_WEIGHT_KG | FLOAT | Weight in kilograms |
| DELIVERY_COST_ZAR | FLOAT | Cost charged to retailer |
| SERVICE_TYPE | VARCHAR(50) | STANDARD, EXPRESS, ECONOMY, SAME_DAY |
| PROVINCE | VARCHAR(100) | Destination province |
| LOAD_YEAR | NUMBER | Partition year |
| LOAD_MONTH | VARCHAR(7) | Partition month |

**Row count:** ~30,000,000  
**Clustering:** CLUSTER BY (LOAD_YEAR, TO_DATE(CREATED_AT))  
**Key metrics:** TRANSIT_HOURS = DISPATCHED_AT -> ARRIVED_AT_POINT_AT; DWELL_DAYS = ARRIVED_AT_POINT_AT -> COLLECTED_AT

---

### FACT_TRACKING_EVENTS
| Column | Type | Description |
|--------|------|-------------|
| TRACKING_EVENT_ID | NUMBER | Surrogate key |
| PARCEL_ID | NUMBER | FK -> FACT_PARCELS |
| EVENT_TYPE | VARCHAR(100) | SCAN, EXCEPTION, DELIVERED, ATTEMPTED, CUSTOMS |
| EVENT_TIMESTAMP | TIMESTAMP_NTZ | When event occurred |
| LATITUDE | FLOAT | GPS latitude at event (nullable) |
| LONGITUDE | FLOAT | GPS longitude at event (nullable) |
| STATUS | VARCHAR(100) | Carrier status code |
| SOURCE_SYSTEM | VARCHAR(100) | COURIER_APP, WAREHOUSE_WMS, CUSTOMER_PORTAL, IOT_SCANNER |
| LOAD_YEAR | NUMBER | Partition year |
| LOAD_MONTH | VARCHAR(7) | Partition month |

**Row count:** ~150,000,000  
**Clustering:** CLUSTER BY (LOAD_YEAR, TO_DATE(EVENT_TIMESTAMP))  
**Notes:** Largest table; avg ~5 events per parcel

---

### FACT_RETURNS
| Column | Type | Description |
|--------|------|-------------|
| RETURN_ID | NUMBER | Surrogate key |
| PARCEL_ID | NUMBER | FK -> FACT_PARCELS |
| RETAILER_ID | NUMBER | FK -> DIM_RETAILERS |
| RETURN_INITIATED_AT | TIMESTAMP_NTZ | When RTS was triggered |
| RETURN_REASON | VARCHAR(200) | NOT_COLLECTED, DAMAGED, WRONG_ITEM, ADDRESS_ERROR, OTHER |
| RETURN_VALUE_ZAR | FLOAT | Refund value |
| DROP_OFF_POINT_ID | NUMBER | FK -> DIM_PICKUP_POINTS (where returned) |
| LOAD_YEAR | NUMBER | Partition year |
| LOAD_MONTH | VARCHAR(7) | Partition month |

**Row count:** ~5,000,000  
**Clustering:** CLUSTER BY (LOAD_YEAR, TO_DATE(RETURN_INITIATED_AT))

---

## STAGING Views (DBT)

All staging models are **views** in the STAGING schema with zero storage cost.

| Model | Source | Key Transformations |
|-------|--------|---------------------|
| stg_couriers | DIM_COURIERS | trim(COURIER_NAME), cast date |
| stg_customers | DIM_CUSTOMERS | trim(CUSTOMER_NAME), cast date |
| stg_pickup_points | DIM_PICKUP_POINTS | Filter STATUS='active', cast date |
| stg_retailers | DIM_RETAILERS | trim(RETAILER_NAME), cast date |
| stg_orders | FACT_ORDERS | upper(CHANNEL), filter ORDER_VALUE_ZAR>0 |
| stg_parcels | FACT_PARCELS | upper(PARCEL_STATUS/SERVICE_TYPE), add TRANSIT_HOURS, DWELL_DAYS |
| stg_tracking_events | FACT_TRACKING_EVENTS | upper(EVENT_TYPE/STATUS) |
| stg_returns | FACT_RETURNS | trim(RETURN_REASON) |

---

## MARTS Tables (DBT)

All mart models are **tables** in the MARTS schema.

| Model | Description | Grain |
|-------|-------------|-------|
| mart_parcel_performance | Enriched parcels joined to all dims + SLA_STATUS | One row per parcel |
| mart_daily_ops | Daily aggregated ops metrics by province/status | Daily/province/status |
| mart_retailer_scorecard | Annual retailer KPIs: GMV, RTS rate, on-time, revenue | Retailer x year |
| mart_sla_breaches | Parcels that breached SLA (RTS, long dwell, slow transit) | One row per breached parcel |

### SLA_STATUS logic (mart_parcel_performance)
- **ON_TIME**: COLLECTED and DWELL_DAYS <= 5
- **LATE**: COLLECTED and DWELL_DAYS > 5
- **RETURNED**: PARCEL_STATUS = 'RTS'
- **IN_PROGRESS**: All other statuses

---

## ML Features

| Model | Description | Label Column |
|-------|-------------|--------------|
| feat_parcel_rts_risk | Features for RTS binary classifier | LABEL_IS_RTS |
| feat_customer_ltv | Features for LTV/churn modelling | ANNUALISED_VALUE |
| feat_courier_reliability | Aggregated courier KPIs per year | RTS_RATE_PCT |

---

## ML Store

| Object | Type | Description |
|--------|------|-------------|
| V_RTS_FEATURES | View | Full feature set for RTS risk model inference |
| V_CUSTOMER_LTV_FEATURES | View | Customer features for LTV/segmentation |
| SP_SCORE_RTS_RISK | Stored Procedure | Scores new parcels for RTS risk using Snowpark Python |
| SP_SEGMENT_CUSTOMERS | Stored Procedure | K-Means clustering of customers into 5 LTV segments |
| RTS_RISK_SCORES | Table | Output of SP_SCORE_RTS_RISK |
| CUSTOMER_LTV_SEGMENTS | Table | Output of SP_SEGMENT_CUSTOMERS |

---

## Business Glossary

| Term | Definition |
|------|------------|
| **RTS (Return-to-Sender)** | Parcel not collected within the holding period and returned to the retailer |
| **Dwell Days** | Number of days a parcel sits at the pickup point awaiting collection |
| **Transit Hours** | Time from courier dispatch to parcel arriving at pickup point |
| **SLA** | Service Level Agreement -- typically 5 dwell days and 48 transit hours |
| **Waybill** | External tracking reference number printed on the parcel label |
| **PUDO (Pickup/Drop-off)** | Pickup point at a retail partner store |
| **Collection Rate** | Percentage of arrived parcels that are collected (not RTS) |
| **GMV** | Gross Merchandise Value -- total declared value of all parcels |
| **Courier** | Last-mile delivery agent responsible for transporting parcels to pickup points |
| **Tier** | Retailer contract tier determining pricing and SLA terms (Enterprise > Mid-Market > SMB) |
| **Source System** | System that generated a tracking event: COURIER_APP, WAREHOUSE_WMS, CUSTOMER_PORTAL, IOT_SCANNER |
| **Feature Store** | Pre-computed ML feature tables (feat_* and V_* views) for model training and inference |
