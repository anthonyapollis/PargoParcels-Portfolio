-- ============================================================================
-- PargoParcels — PostgreSQL OLTP schema (operational source system)
-- ============================================================================
-- This is the system-of-record the analytics platform extracts FROM.
-- Normalised (3NF), FK-enforced, indexed for operational access patterns
-- (waybill lookups, parcel tracking pages, point capacity checks).
--
-- Run:  psql -d pargo_oltp -f 01_create_schema.sql
-- ============================================================================

CREATE SCHEMA IF NOT EXISTS pargo;
SET search_path TO pargo;

-- ---------------------------------------------------------------- reference
CREATE TABLE retailers (
    retailer_id          INT PRIMARY KEY,
    retailer_name        VARCHAR(120) NOT NULL,
    industry             VARCHAR(60)  NOT NULL,
    tier                 VARCHAR(20)  NOT NULL CHECK (tier IN ('Enterprise','Mid-Market','SMB')),
    contract_start_date  DATE         NOT NULL,
    rate_per_parcel_zar  NUMERIC(8,2) NOT NULL CHECK (rate_per_parcel_zar > 0),
    integration_type     VARCHAR(30)  NOT NULL,
    updated_at           TIMESTAMP    NOT NULL DEFAULT now()   -- CDC / snapshot watermark
);

CREATE TABLE pickup_points (
    pickup_point_id   INT PRIMARY KEY,
    store_name        VARCHAR(150) NOT NULL,
    partner_name      VARCHAR(60)  NOT NULL,
    province          VARCHAR(30)  NOT NULL,
    city              VARCHAR(60)  NOT NULL,
    latitude          NUMERIC(9,6) NOT NULL,
    longitude         NUMERIC(9,6) NOT NULL,
    opening_date      DATE         NOT NULL,
    capacity_per_day  INT          NOT NULL CHECK (capacity_per_day > 0),
    status            VARCHAR(20)  NOT NULL DEFAULT 'Active',
    updated_at        TIMESTAMP    NOT NULL DEFAULT now()
);

CREATE TABLE couriers (
    courier_id    INT PRIMARY KEY,
    courier_name  VARCHAR(100) NOT NULL,
    region        VARCHAR(30)  NOT NULL,
    vehicle_type  VARCHAR(30)  NOT NULL,
    hired_date    DATE         NOT NULL,
    updated_at    TIMESTAMP    NOT NULL DEFAULT now()
);

CREATE TABLE customers (
    customer_id        BIGINT PRIMARY KEY,
    customer_name      VARCHAR(120) NOT NULL,
    mobile_number      VARCHAR(20)  NOT NULL,        -- Pargo's primary notification channel
    province           VARCHAR(30)  NOT NULL,
    city               VARCHAR(60)  NOT NULL,
    registration_date  DATE         NOT NULL,
    customer_segment   VARCHAR(20),
    active_flag        BOOLEAN      NOT NULL DEFAULT TRUE,
    updated_at         TIMESTAMP    NOT NULL DEFAULT now()
);

-- ------------------------------------------------------------ transactional
CREATE TABLE orders (
    order_id          BIGINT PRIMARY KEY,
    customer_id       BIGINT NOT NULL REFERENCES customers(customer_id),
    retailer_id       INT    NOT NULL REFERENCES retailers(retailer_id),
    order_created_at  TIMESTAMP NOT NULL,
    order_value_zar   NUMERIC(10,2) NOT NULL,
    channel           VARCHAR(20)
);

CREATE TABLE parcels (
    parcel_id            BIGINT PRIMARY KEY,
    order_id             BIGINT NOT NULL REFERENCES orders(order_id),
    customer_id          BIGINT NOT NULL REFERENCES customers(customer_id),
    retailer_id          INT    NOT NULL REFERENCES retailers(retailer_id),
    pickup_point_id      INT    NOT NULL REFERENCES pickup_points(pickup_point_id),
    courier_id           INT    NOT NULL REFERENCES couriers(courier_id),
    waybill_number       VARCHAR(20) NOT NULL UNIQUE,
    created_at           TIMESTAMP NOT NULL,
    dispatched_at        TIMESTAMP,
    arrived_at_point_at  TIMESTAMP,
    notified_at          TIMESTAMP,
    collected_at         TIMESTAMP,
    rts_at               TIMESTAMP,
    parcel_status        VARCHAR(20) NOT NULL,
    parcel_value_zar     NUMERIC(10,2),
    parcel_weight_kg     NUMERIC(7,2),
    delivery_cost_zar    NUMERIC(8,2),
    service_type         VARCHAR(25),
    province             VARCHAR(30) NOT NULL
);

CREATE TABLE tracking_events (
    tracking_event_id  BIGINT PRIMARY KEY,
    parcel_id          BIGINT NOT NULL,     -- soft FK: scanner feed can outrun parcel sync
    event_type         VARCHAR(40) NOT NULL,
    event_timestamp    TIMESTAMP   NOT NULL,
    latitude           NUMERIC(9,6),
    longitude          NUMERIC(9,6),
    status             VARCHAR(20),
    source_system      VARCHAR(30)
);

CREATE TABLE returns (
    return_id            BIGINT PRIMARY KEY,
    parcel_id            BIGINT NOT NULL REFERENCES parcels(parcel_id),
    retailer_id          INT    NOT NULL REFERENCES retailers(retailer_id),
    return_initiated_at  TIMESTAMP NOT NULL,
    return_reason        VARCHAR(60),
    return_value_zar     NUMERIC(10,2),
    drop_off_point_id    INT REFERENCES pickup_points(pickup_point_id)
);

-- ------------------------------------------------------- operational indexes
CREATE INDEX idx_parcels_waybill        ON parcels(waybill_number);
CREATE INDEX idx_parcels_status         ON parcels(parcel_status) WHERE parcel_status NOT IN ('Collected');
CREATE INDEX idx_parcels_point          ON parcels(pickup_point_id, created_at);
CREATE INDEX idx_parcels_retailer_date  ON parcels(retailer_id, created_at);
CREATE INDEX idx_events_parcel          ON tracking_events(parcel_id, event_timestamp);
CREATE INDEX idx_events_ts              ON tracking_events(event_timestamp);       -- incremental extract watermark
CREATE INDEX idx_orders_customer        ON orders(customer_id);
CREATE INDEX idx_returns_retailer       ON returns(retailer_id, return_initiated_at);

COMMENT ON TABLE  parcels         IS 'Core parcel lifecycle. Milestone timestamps drive SLA + dwell analytics downstream.';
COMMENT ON TABLE  tracking_events IS 'Append-only scan log, ~5-6 events per parcel. Highest-volume table; watermark = event_timestamp.';
COMMENT ON COLUMN parcels.rts_at  IS 'Set when parcel exceeds 7-day collection window and is returned to sender.';
