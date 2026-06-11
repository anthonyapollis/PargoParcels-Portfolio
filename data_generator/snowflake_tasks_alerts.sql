-- ============================================================
-- PARGO DW -- Snowflake Tasks & Alerts
-- Run as ACCOUNTADMIN on PARGO_DW
-- ============================================================
USE DATABASE PARGO_DW;
USE SCHEMA RAW;

-- -------------------------------------------------------
-- TASK 1: Nightly parcel status summary refresh
-- -------------------------------------------------------
CREATE OR REPLACE TASK PARGO_DW.RAW.TASK_NIGHTLY_PARCEL_SUMMARY
  WAREHOUSE = LYRA_LOAD_WH
  SCHEDULE  = 'USING CRON 0 2 * * * Africa/Johannesburg'
AS
  CREATE OR REPLACE TABLE PARGO_DW.MARTS.PARCEL_STATUS_DAILY_SUMMARY AS
  SELECT
      TO_DATE(CREATED_AT)         AS SUMMARY_DATE,
      PROVINCE,
      PARCEL_STATUS,
      SERVICE_TYPE,
      COUNT(*)                    AS PARCEL_COUNT,
      SUM(PARCEL_VALUE_ZAR)       AS TOTAL_VALUE,
      AVG(DATEDIFF('hour', DISPATCHED_AT, ARRIVED_AT_POINT_AT)) AS AVG_TRANSIT_HRS,
      AVG(DATEDIFF('day',  ARRIVED_AT_POINT_AT, COLLECTED_AT))  AS AVG_DWELL_DAYS
  FROM PARGO_DW.RAW.FACT_PARCELS
  WHERE CREATED_AT >= DATEADD('day', -7, CURRENT_DATE)
  GROUP BY 1,2,3,4;

-- -------------------------------------------------------
-- TASK 2: Hourly RTS rate spike detection
-- -------------------------------------------------------
CREATE OR REPLACE TASK PARGO_DW.RAW.TASK_HOURLY_RTS_CHECK
  WAREHOUSE = LYRA_LOAD_WH
  SCHEDULE  = 'USING CRON 0 * * * * Africa/Johannesburg'
AS
  INSERT INTO PARGO_DW.RAW.RTS_SPIKE_LOG (CHECKED_AT, RTS_RATE_PCT, THRESHOLD_PCT, FLAGGED)
  WITH recent AS (
      SELECT
          COUNT_IF(PARCEL_STATUS='RTS')::FLOAT / NULLIF(COUNT(*),0) * 100 AS RTS_PCT
      FROM PARGO_DW.RAW.FACT_PARCELS
      WHERE CREATED_AT >= DATEADD('hour', -1, CURRENT_TIMESTAMP)
  )
  SELECT CURRENT_TIMESTAMP, RTS_PCT, 15.0, (RTS_PCT > 15.0)
  FROM recent;

-- Support table for TASK 2
CREATE TABLE IF NOT EXISTS PARGO_DW.RAW.RTS_SPIKE_LOG (
    CHECKED_AT      TIMESTAMP_NTZ,
    RTS_RATE_PCT    FLOAT,
    THRESHOLD_PCT   FLOAT,
    FLAGGED         BOOLEAN
);

-- -------------------------------------------------------
-- TASK 3: Daily SLA breach report
-- -------------------------------------------------------
CREATE OR REPLACE TASK PARGO_DW.RAW.TASK_DAILY_SLA_REPORT
  WAREHOUSE = LYRA_LOAD_WH
  SCHEDULE  = 'USING CRON 30 6 * * * Africa/Johannesburg'
AS
  CREATE OR REPLACE TABLE PARGO_DW.MARTS.SLA_DAILY_REPORT AS
  SELECT
      TO_DATE(ARRIVED_AT_POINT_AT) AS REPORT_DATE,
      PROVINCE,
      COUNT(*) AS TOTAL_PARCELS,
      COUNT_IF(PARCEL_STATUS='RTS') AS RTS_COUNT,
      COUNT_IF(DATEDIFF('day', ARRIVED_AT_POINT_AT, COLLECTED_AT) > 5) AS LONG_DWELL_COUNT,
      ROUND(100.0 * COUNT_IF(PARCEL_STATUS='RTS') / NULLIF(COUNT(*),0), 2) AS RTS_RATE_PCT,
      ROUND(100.0 * COUNT_IF(DATEDIFF('day', ARRIVED_AT_POINT_AT, COLLECTED_AT) > 5)
            / NULLIF(COUNT(*),0), 2) AS LONG_DWELL_RATE_PCT
  FROM PARGO_DW.RAW.FACT_PARCELS
  WHERE ARRIVED_AT_POINT_AT >= DATEADD('day', -30, CURRENT_DATE)
  GROUP BY 1,2;

-- -------------------------------------------------------
-- ALERT: RTS spike exceeds 15%
-- -------------------------------------------------------
CREATE OR REPLACE ALERT PARGO_DW.RAW.ALERT_RTS_SPIKE
  WAREHOUSE = LYRA_LOAD_WH
  SCHEDULE  = '60 MINUTE'
  IF (EXISTS (
      SELECT 1 FROM PARGO_DW.RAW.RTS_SPIKE_LOG
      WHERE FLAGGED = TRUE
        AND CHECKED_AT >= DATEADD('hour', -1, CURRENT_TIMESTAMP)
  ))
  THEN
    CALL SYSTEM$SEND_EMAIL(
        'pargo_alerts',
        'apollis@pargo.co.za',
        'ALERT: RTS spike detected',
        'RTS rate exceeded 15% threshold in the last hour. Check PARGO_DW.RAW.RTS_SPIKE_LOG.'
    );

-- -------------------------------------------------------
-- ALERT: Tracking event volume drop (>50% below 7-day avg)
-- -------------------------------------------------------
CREATE OR REPLACE ALERT PARGO_DW.RAW.ALERT_EVENT_VOLUME_DROP
  WAREHOUSE = LYRA_LOAD_WH
  SCHEDULE  = '60 MINUTE'
  IF (EXISTS (
      WITH hourly AS (
          SELECT COUNT(*) AS CNT
          FROM PARGO_DW.RAW.FACT_TRACKING_EVENTS
          WHERE EVENT_TIMESTAMP >= DATEADD('hour', -1, CURRENT_TIMESTAMP)
      ),
      baseline AS (
          SELECT AVG(CNT) AS AVG_CNT FROM (
              SELECT DATE_TRUNC('hour', EVENT_TIMESTAMP) AS HR, COUNT(*) AS CNT
              FROM PARGO_DW.RAW.FACT_TRACKING_EVENTS
              WHERE EVENT_TIMESTAMP >= DATEADD('day', -7, CURRENT_TIMESTAMP)
              GROUP BY 1
          )
      )
      SELECT 1 FROM hourly, baseline
      WHERE hourly.CNT < baseline.AVG_CNT * 0.5
  ))
  THEN
    CALL SYSTEM$SEND_EMAIL(
        'pargo_alerts',
        'apollis@pargo.co.za',
        'ALERT: Tracking event volume drop',
        'Hourly tracking event count is >50% below the 7-day average. Possible ingestion failure.'
    );

-- Activate tasks (requires ACCOUNTADMIN)
ALTER TASK PARGO_DW.RAW.TASK_NIGHTLY_PARCEL_SUMMARY RESUME;
ALTER TASK PARGO_DW.RAW.TASK_HOURLY_RTS_CHECK RESUME;
ALTER TASK PARGO_DW.RAW.TASK_DAILY_SLA_REPORT RESUME;
ALTER ALERT PARGO_DW.RAW.ALERT_RTS_SPIKE RESUME;
ALTER ALERT PARGO_DW.RAW.ALERT_EVENT_VOLUME_DROP RESUME;
