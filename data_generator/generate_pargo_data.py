"""
PargoParcels — Enterprise-scale synthetic data generator
=========================================================
Generates a realistic SA last-mile logistics dataset:
customers, orders, parcels, tracking events, returns + dimensions.

Design notes (deliberate improvements over naive generation):
  * numpy vectorised generation — faker is only used for small dimensions.
    (faker at 150M rows ≈ days of runtime; numpy ≈ minutes)
  * Generated month-by-month so memory stays flat and SCALE=1.0
    (30M parcels / 150M events) runs on a 16GB workstation.
  * Parquet partitioned by year/month ONLY. Province partitioning would
    create a small-file problem (36mo x 12 files x 9 provinces x N tables);
    in Snowflake we CLUSTER BY (province) instead.
  * Parcel lifecycle is milestone-driven: tracking events are derived from
    the same milestone timestamps that feed FACT_PARCEL, so the event log
    and the fact table always reconcile (a classic interview gotcha).
  * ~0.5% deliberately dirty rows are injected into RAW exports
    (dupes, null/negative weights, orphan events) so dbt tests have
    something real to catch. Cleaning happens in staging, as it should.

Usage:
    python generate_pargo_data.py --scale 0.04   # demo  (~8M rows)
    python generate_pargo_data.py --scale 1.0    # full  (220M+ rows)
"""

import argparse
import os
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from datetime import datetime
from faker import Faker

RNG = np.random.default_rng(42)
fake = Faker("en_GB")
Faker.seed(42)

# ----------------------------------------------------------------------------
# CONFIG
# ----------------------------------------------------------------------------
HISTORY_START = pd.Timestamp("2023-07-01")
HISTORY_END = pd.Timestamp("2026-06-30")
MONTHS = pd.period_range(HISTORY_START, HISTORY_END, freq="M")

FULL_SCALE = dict(
    customers=10_000_000,
    orders=25_000_000,
    parcels=30_000_000,
    returns=5_000_000,
    pickup_points=4_000,
    retailers=150,
    couriers=500,
)

PROVINCES = {
    "Gauteng": dict(w=0.26, cities=["Johannesburg", "Pretoria", "Soweto", "Benoni", "Centurion", "Sandton", "Midrand", "Roodepoort"]),
    "KwaZulu-Natal": dict(w=0.19, cities=["Durban", "Pietermaritzburg", "Umhlanga", "Richards Bay", "Newcastle", "Pinetown"]),
    "Western Cape": dict(w=0.13, cities=["Cape Town", "Bellville", "Stellenbosch", "Paarl", "George", "Table View", "Somerset West"]),
    "Eastern Cape": dict(w=0.11, cities=["Gqeberha", "East London", "Mthatha", "Uitenhage"]),
    "Limpopo": dict(w=0.10, cities=["Polokwane", "Tzaneen", "Thohoyandou", "Mokopane"]),
    "Mpumalanga": dict(w=0.08, cities=["Mbombela", "Witbank", "Secunda", "Middelburg"]),
    "North West": dict(w=0.06, cities=["Rustenburg", "Potchefstroom", "Mahikeng", "Klerksdorp"]),
    "Free State": dict(w=0.05, cities=["Bloemfontein", "Welkom", "Bethlehem", "Kroonstad"]),
    "Northern Cape": dict(w=0.02, cities=["Kimberley", "Upington", "Springbok"]),
}
PROV_NAMES = list(PROVINCES.keys())
PROV_W = np.array([v["w"] for v in PROVINCES.values()])
PROV_W = PROV_W / PROV_W.sum()

# rough geographic bounding boxes per province for plausible lat/lon
PROV_BOX = {
    "Gauteng": (-26.7, -25.2, 27.3, 29.1),
    "KwaZulu-Natal": (-30.9, -27.0, 29.0, 32.0),
    "Western Cape": (-34.6, -31.5, 18.0, 23.0),
    "Eastern Cape": (-34.0, -30.5, 24.0, 29.5),
    "Limpopo": (-25.0, -22.3, 27.0, 31.0),
    "Mpumalanga": (-27.0, -24.5, 29.0, 32.0),
    "North West": (-27.5, -25.0, 24.0, 27.5),
    "Free State": (-30.5, -26.7, 24.5, 29.5),
    "Northern Cape": (-31.5, -26.5, 17.0, 25.0),
}

ANCHOR_RETAILERS = [
    ("Bash", "Fashion & Apparel", "Enterprise"),
    ("Woolworths", "Retail - Premium", "Enterprise"),
    ("Clicks", "Health & Pharmacy", "Enterprise"),
    ("Sportscene", "Fashion & Apparel", "Enterprise"),
    ("FILA South Africa", "Fashion & Apparel", "Mid-Market"),
    ("Cape Union Mart", "Outdoor & Lifestyle", "Enterprise"),
    ("OneDayOnly", "E-commerce Marketplace", "Enterprise"),
    ("Loot.co.za", "E-commerce Marketplace", "Mid-Market"),
    ("Wellness Warehouse", "Health & Pharmacy", "Mid-Market"),
]
INDUSTRIES = ["Fashion & Apparel", "Health & Pharmacy", "E-commerce Marketplace",
              "Electronics", "Outdoor & Lifestyle", "Beauty & Cosmetics",
              "Books & Media", "Home & Garden", "Retail - Premium", "Fintech"]
TIERS = {"Enterprise": 0.55, "Mid-Market": 0.33, "SMB": 0.12}  # share of volume
POINT_PARTNERS = ["Clicks", "PEP", "Caltex Freshstop", "Waltons", "Spar",
                  "Lewis", "Independent Spaza", "PostNet", "Build it"]
VEHICLES = ["Motorcycle", "Panel Van", "1-Ton Bakkie", "4-Ton Truck", "8-Ton Truck"]

# Parcel terminal-state mix (calibrated to Pargo's public claims)
P_COLLECTED = 0.918      # collected by customer
P_RTS = 0.055            # expired at point -> returned to sender
P_LOST = 0.002
P_DAMAGED = 0.005        # delivered but damaged
P_IN_FLIGHT = 0.020      # still moving (recent parcels)

RETURN_RATE_BY_INDUSTRY = {
    "Fashion & Apparel": 0.28, "E-commerce Marketplace": 0.16, "Electronics": 0.12,
    "Beauty & Cosmetics": 0.10, "Retail - Premium": 0.09, "Outdoor & Lifestyle": 0.11,
    "Health & Pharmacy": 0.04, "Books & Media": 0.05, "Home & Garden": 0.08, "Fintech": 0.02,
}
RETURN_REASONS = np.array(["Wrong size", "Changed mind", "Item damaged", "Wrong item shipped",
                           "Not as described", "Defective product", "Better price elsewhere", "Arrived too late"])
RETURN_REASON_W = np.array([0.31, 0.18, 0.13, 0.10, 0.10, 0.08, 0.05, 0.05])

DIRTY_RATE = 0.005  # injected into RAW only


# ----------------------------------------------------------------------------
# DIMENSIONS (small — faker is fine here)
# ----------------------------------------------------------------------------
def gen_retailers(n):
    rows = []
    for i, (name, ind, tier) in enumerate(ANCHOR_RETAILERS):
        rows.append((i + 1, name, ind, tier))
    for i in range(len(ANCHOR_RETAILERS), n):
        name = f"{fake.company().split(',')[0]} {RNG.choice(['SA', 'Online', 'Direct', 'Store', ''])}".strip()
        tier = RNG.choice(["Enterprise", "Mid-Market", "SMB"], p=[0.10, 0.30, 0.60])
        rows.append((i + 1, name, RNG.choice(INDUSTRIES), tier))
    df = pd.DataFrame(rows, columns=["retailer_id", "retailer_name", "industry", "tier"])
    df["contract_start_date"] = pd.to_datetime("2018-01-01") + pd.to_timedelta(
        RNG.integers(0, 365 * 7, n), unit="D")
    df.loc[df.contract_start_date > HISTORY_START, "contract_start_date"] = HISTORY_START
    # rate card: enterprise gets volume discount
    base = {"Enterprise": 45.0, "Mid-Market": 55.0, "SMB": 65.0}
    df["rate_per_parcel_zar"] = df.tier.map(base) + RNG.normal(0, 3, n).round(2)
    df["integration_type"] = RNG.choice(["API", "Shopify Plugin", "WooCommerce Plugin", "Manual Portal"],
                                        n, p=[0.45, 0.25, 0.15, 0.15])
    return df


def gen_pickup_points(n):
    prov = RNG.choice(PROV_NAMES, n, p=PROV_W)
    cities = np.array([RNG.choice(PROVINCES[p]["cities"]) for p in prov])
    partner = RNG.choice(POINT_PARTNERS, n, p=[0.22, 0.18, 0.12, 0.08, 0.10, 0.06, 0.12, 0.07, 0.05])
    lat = np.empty(n); lon = np.empty(n)
    for p in PROV_NAMES:
        m = prov == p
        s, nn, w, e = PROV_BOX[p]
        lat[m] = RNG.uniform(s, nn, m.sum())
        lon[m] = RNG.uniform(w, e, m.sum())
    df = pd.DataFrame(dict(
        pickup_point_id=np.arange(1, n + 1),
        store_name=[f"{pa} {c} {sfx}" for pa, c, sfx in
                    zip(partner, cities, RNG.choice(["Central", "Mall", "Plaza", "Junction", "Square", "Park", ""], n))],
        partner_name=partner, province=prov, city=cities,
        latitude=lat.round(6), longitude=lon.round(6),
        opening_date=pd.to_datetime("2016-01-01") + pd.to_timedelta(RNG.integers(0, 365 * 10, n), unit="D"),
        capacity_per_day=RNG.choice([20, 35, 50, 80, 120, 200], n, p=[0.15, 0.25, 0.25, 0.20, 0.10, 0.05]),
        status=RNG.choice(["Active", "Active", "Active", "Suspended"], n, p=[0.94, 0.02, 0.02, 0.02]),
    ))
    df.loc[df.opening_date > HISTORY_END, "opening_date"] = HISTORY_END - pd.Timedelta(days=90)
    return df


def gen_couriers(n):
    region = RNG.choice(PROV_NAMES, n, p=PROV_W)
    return pd.DataFrame(dict(
        courier_id=np.arange(1, n + 1),
        courier_name=[fake.name() for _ in range(n)],
        region=region,
        vehicle_type=RNG.choice(VEHICLES, n, p=[0.30, 0.30, 0.22, 0.12, 0.06]),
        hired_date=pd.to_datetime("2017-01-01") + pd.to_timedelta(RNG.integers(0, 365 * 9, n), unit="D"),
    ))


def gen_customers(n, out):
    """Chunked — at full scale this is 10M rows."""
    chunk = 1_000_000
    first = np.array(["Thabo","Lerato","Sipho","Nomvula","Anika","Pieter","Aisha","Johan","Zanele","Kagiso",
                      "Megan","Riaan","Fatima","Bongani","Chloe","Tshepo","Sarah","Lwazi","Emma","Mandla",
                      "Precious","Dineo","Werner","Naledi","Ayanda","Jaco","Refilwe","Liam","Khanyi","Daniel"])
    last = np.array(["Mokoena","Naidoo","Botha","Dlamini","Khumalo","van der Merwe","Pillay","Nkosi","Smith",
                     "Mthembu","Petersen","Sithole","Jacobs","Mahlangu","Pretorius","Ngcobo","Adams","Zulu",
                     "Fourie","Molefe","Hendricks","Mabaso","Venter","Tshabalala","Daniels","Maluleke","Steyn"])
    writer = None
    for start in range(0, n, chunk):
        m = min(chunk, n - start)
        ids = np.arange(start + 1, start + m + 1)
        prov = RNG.choice(PROV_NAMES, m, p=PROV_W)
        city = np.array([RNG.choice(PROVINCES[p]["cities"]) for p in prov])
        df = pd.DataFrame(dict(
            customer_id=ids,
            customer_name=np.char.add(np.char.add(RNG.choice(first, m), " "), RNG.choice(last, m)),
            mobile_number=np.char.add("+2747", RNG.integers(1000000, 9999999, m).astype(str)),
            province=prov, city=city,
            registration_date=HISTORY_START - pd.Timedelta(days=900)
                + pd.to_timedelta(RNG.integers(0, 1995, m), unit="D"),
            customer_segment=RNG.choice(["Frequent", "Regular", "Occasional", "Dormant"], m, p=[0.08, 0.27, 0.45, 0.20]),
            active_flag=RNG.random(m) > 0.12,
        ))
        t = pa.Table.from_pandas(df, preserve_index=False)
        if writer is None:
            writer = pq.ParquetWriter(os.path.join(out, "customers.parquet"), t.schema, compression="snappy")
        writer.write_table(t)
    writer.close()
    return n


# ----------------------------------------------------------------------------
# FACTS — generated month by month
# ----------------------------------------------------------------------------
def month_weights(months):
    """Seasonality: Black Friday/Dec peak, Jan slump, steady YoY growth."""
    w = []
    for i, p in enumerate(months):
        base = 1.0 + 0.025 * i                       # ~2.5% m/m compound growth
        season = {11: 1.85, 12: 1.45, 1: 0.70, 2: 0.80, 7: 1.05}.get(p.month, 1.0)
        w.append(base * season)
    w = np.array(w)
    return w / w.sum()


def gen_facts(scale, dims, out_root):
    n_parcels_total = int(FULL_SCALE["parcels"] * scale)
    n_customers = int(FULL_SCALE["customers"] * scale)
    retailers, points, couriers = dims["retailers"], dims["points"], dims["couriers"]

    # retailer volume shares: tier-weighted Zipf so anchors dominate (realistic)
    tier_w = retailers.tier.map(TIERS).values
    zipf = 1.0 / np.arange(1, len(retailers) + 1) ** 0.7
    ret_w = tier_w * zipf
    ret_w = ret_w / ret_w.sum()

    # pickup point popularity: log-normal (some points are 50x busier)
    pt_w = RNG.lognormal(0, 1.1, len(points))
    pt_w[points.status.values != "Active"] *= 0.05
    pt_w = pt_w / pt_w.sum()

    # customer ordering propensity: power law (top 10% of customers ≈ 45% of orders)
    cust_w = RNG.pareto(1.6, n_customers) + 1
    cust_w = cust_w / cust_w.sum()

    courier_by_prov = {p: couriers.courier_id.values[couriers.region.values == p] for p in PROV_NAMES}
    point_prov = points.province.values
    ind_by_ret = retailers.industry.values
    rate_by_ret = retailers.rate_per_parcel_zar.values

    mw = month_weights(MONTHS)
    parcel_id_seq = 0
    order_id_seq = 0
    return_id_seq = 0
    event_id_seq = 0
    totals = dict(orders=0, parcels=0, events=0, returns=0)

    for mi, period in enumerate(MONTHS):
        n_p = max(1000, int(n_parcels_total * mw[mi]))
        m_start = period.to_timestamp()
        m_days = period.days_in_month

        # --- ORDERS (≈ parcels / 1.2 : multi-parcel orders exist) ---
        n_o = int(n_p / 1.2)
        order_ids = np.arange(order_id_seq + 1, order_id_seq + n_o + 1); order_id_seq += n_o
        ord_cust = RNG.choice(n_customers, n_o, p=cust_w) + 1
        ord_ret_idx = RNG.choice(len(retailers), n_o, p=ret_w)
        ord_created = m_start + pd.to_timedelta(RNG.uniform(0, m_days * 24 * 3600, n_o), unit="s")
        order_value = np.round(np.exp(RNG.normal(6.1, 0.85, n_o)), 2)            # median ~R450
        orders = pd.DataFrame(dict(
            order_id=order_ids, customer_id=ord_cust,
            retailer_id=retailers.retailer_id.values[ord_ret_idx],
            order_created_at=ord_created, order_value_zar=np.clip(order_value, 49, 25000),
            channel=RNG.choice(["Web", "App", "In-store kiosk"], n_o, p=[0.62, 0.33, 0.05]),
        ))

        # --- PARCELS: map each parcel to an order ---
        par_order_idx = np.sort(RNG.integers(0, n_o, n_p))
        parcel_ids = np.arange(parcel_id_seq + 1, parcel_id_seq + n_p + 1); parcel_id_seq += n_p
        p_cust = ord_cust[par_order_idx]
        p_ret_idx = ord_ret_idx[par_order_idx]
        p_point_idx = RNG.choice(len(points), n_p, p=pt_w)
        p_prov = point_prov[p_point_idx]
        p_courier = np.array([RNG.choice(courier_by_prov[p]) for p in p_prov])

        created = ord_created[par_order_idx] + pd.to_timedelta(RNG.uniform(2, 30, n_p), unit="h")

        # lifecycle durations (hours) — calibrated: created->at point ≈ 30h avg (their 1.25d claim)
        h_dispatch = RNG.gamma(2.0, 3.0, n_p)              # retailer -> courier collect ~6h
        h_hub = RNG.gamma(2.0, 2.5, n_p)                   # -> hub ~5h
        h_linehaul = np.where(p_prov == "Gauteng",
                              RNG.gamma(2.0, 3.5, n_p),    # short haul
                              RNG.gamma(2.5, 5.5, n_p))    # long haul
        h_lastmile = RNG.gamma(2.0, 2.0, n_p)
        arrived = created + pd.to_timedelta(h_dispatch + h_hub + h_linehaul + h_lastmile, unit="h")
        notified = arrived + pd.to_timedelta(RNG.uniform(0.05, 1.5, n_p), unit="h")
        dwell_h = RNG.gamma(1.6, 22, n_p)                  # ~35h avg dwell at point
        collected = notified + pd.to_timedelta(dwell_h, unit="h")

        # RTS probability driven by real operational signals so ML models achieve realistic AUC
        transit_h = h_dispatch + h_hub + h_linehaul + h_lastmile
        prov_rts_base = {"Gauteng": 0.10, "Western Cape": 0.07, "KwaZulu-Natal": 0.13,
                         "Eastern Cape": 0.18, "Limpopo": 0.26, "Mpumalanga": 0.19,
                         "North West": 0.22, "Free State": 0.17, "Northern Cape": 0.27}
        base_rts = np.array([prov_rts_base.get(pv, 0.12) for pv in p_prov])
        ret_cats = retailers.retailer_category.values[p_ret_idx] if "retailer_category" in retailers.columns else np.full(n_p, "Other")
        cat_mult = np.where(ret_cats == "Fashion", 1.35,
                   np.where(ret_cats == "Electronics", 0.65,
                   np.where(ret_cats == "Grocery", 0.80, 1.0)))
        weight_mult = np.where(np.round(np.clip(RNG.lognormal(0.1, 0.9, n_p), 0.05, 30), 2) > 10, 1.3, 1.0)
        transit_mult = 1.0 + np.clip((transit_h - 24) / 72, 0, 0.5)
        dwell_mult   = 1.0 + np.clip((dwell_h   - 48) / 96, 0, 0.8)
        rts_prob = np.clip(base_rts * cat_mult * weight_mult * transit_mult * dwell_mult, 0.01, 0.65)
        rng_draw = RNG.random(n_p)
        base_status = np.where(rng_draw < rts_prob, "ExpiredRTS",
                      np.where(rng_draw < rts_prob + P_LOST, "Lost",
                      np.where(rng_draw < rts_prob + P_LOST + P_DAMAGED, "Damaged", "Collected")))
        status = base_status
        # parcels created near end of history skew in-flight
        recent = created > HISTORY_END - pd.Timedelta(days=4)
        status = np.where(recent & (RNG.random(n_p) < 0.6), "InTransit", status)
        is_delivered = np.isin(status, ["Collected", "Damaged"])
        is_lost = status == "Lost"
        is_rts = status == "ExpiredRTS"
        rts_at = notified + pd.Timedelta(days=8)           # 7-day collection window + 1d processing

        collected_final = pd.Series(collected).where(is_delivered, pd.NaT)
        arrived_final = pd.Series(arrived).where(~is_lost, pd.NaT)

        weight = np.round(np.clip(RNG.lognormal(0.1, 0.9, n_p), 0.05, 30), 2)
        value = np.round(orders.order_value_zar.values[par_order_idx] *
                         RNG.uniform(0.4, 1.0, n_p), 2)
        delivery_cost = np.round(rate_by_ret[p_ret_idx] *
                                 np.where(weight > 5, 1.4, 1.0) *
                                 RNG.uniform(0.95, 1.05, n_p), 2)

        parcels = pd.DataFrame(dict(
            parcel_id=parcel_ids,
            order_id=order_ids[par_order_idx],
            customer_id=p_cust,
            retailer_id=retailers.retailer_id.values[p_ret_idx],
            pickup_point_id=points.pickup_point_id.values[p_point_idx],
            courier_id=p_courier,
            waybill_number=np.char.add("PGO", (parcel_ids + 10_000_000).astype(str)),
            created_at=created,
            dispatched_at=created + pd.to_timedelta(h_dispatch, unit="h"),
            arrived_at_point_at=arrived_final.values,
            notified_at=pd.Series(notified).where(~is_lost, pd.NaT).values,
            collected_at=collected_final.values,
            rts_at=pd.Series(rts_at).where(is_rts, pd.NaT).values,
            parcel_status=status,
            parcel_value_zar=value,
            parcel_weight_kg=weight,
            delivery_cost_zar=delivery_cost,
            service_type=RNG.choice(["Standard", "Express", "Return-to-Retailer"], n_p, p=[0.82, 0.13, 0.05]),
            province=p_prov,
        ))

        # --- TRACKING EVENTS: derived from milestones (always reconciles) ---
        ev_frames = []
        milestones = [
            ("Created", parcels.created_at, None),
            ("CollectedFromRetailer", parcels.dispatched_at, None),
            ("AtHub", parcels.dispatched_at + pd.to_timedelta(h_hub, unit="h"), None),
            ("InLinehaul", parcels.dispatched_at + pd.to_timedelta(h_hub + 0.5, unit="h"), None),
            ("ArrivedAtPickupPoint", parcels.arrived_at_point_at, None),
            ("CustomerNotified", parcels.notified_at, None),
            ("CollectedByCustomer", parcels.collected_at, None),
            ("ExpiredReturnedToSender", parcels.rts_at, None),
        ]
        pt_lat = points.latitude.values[p_point_idx]
        pt_lon = points.longitude.values[p_point_idx]
        for ev_type, ts, _ in milestones:
            mask = ts.notna().values
            if not mask.any():
                continue
            k = mask.sum()
            at_point = ev_type in ("ArrivedAtPickupPoint", "CustomerNotified",
                                   "CollectedByCustomer", "ExpiredReturnedToSender")
            ev_frames.append(pd.DataFrame(dict(
                parcel_id=parcels.parcel_id.values[mask],
                event_type=ev_type,
                event_timestamp=ts.values[mask],
                latitude=np.round(pt_lat[mask] + (0 if at_point else RNG.normal(0, 0.8, k)), 6),
                longitude=np.round(pt_lon[mask] + (0 if at_point else RNG.normal(0, 0.8, k)), 6),
                status=np.where(np.isin(ev_type, ["CollectedByCustomer"]), "Closed",
                                np.where(ev_type == "ExpiredReturnedToSender", "RTS", "Open")),
                source_system=RNG.choice(["ScannerApp", "CourierGPS", "PartnerPOS", "API"], k,
                                         p=[0.45, 0.25, 0.20, 0.10]),
            )))
        # lost parcels: a final LostInTransit event
        lost_mask = is_lost
        if lost_mask.any():
            k = lost_mask.sum()
            ev_frames.append(pd.DataFrame(dict(
                parcel_id=parcels.parcel_id.values[lost_mask], event_type="LostInTransit",
                event_timestamp=(created + pd.to_timedelta(h_dispatch + h_hub + RNG.uniform(1, 40, n_p), unit="h"))[lost_mask],
                latitude=np.round(pt_lat[lost_mask] + RNG.normal(0, 1.0, k), 6),
                longitude=np.round(pt_lon[lost_mask] + RNG.normal(0, 1.0, k), 6),
                status="Lost", source_system="OpsConsole",
            )))
        events = pd.concat(ev_frames, ignore_index=True)
        events.insert(0, "tracking_event_id", np.arange(event_id_seq + 1, event_id_seq + len(events) + 1))
        event_id_seq += len(events)

        # --- RETURNS: industry-driven ---
        ret_rate = np.array([RETURN_RATE_BY_INDUSTRY[i] for i in ind_by_ret[p_ret_idx]])
        ret_mask = (RNG.random(n_p) < ret_rate * 0.55) & is_delivered  # ~55% of "want to return" actually do
        n_r = ret_mask.sum()
        returns = pd.DataFrame(dict(
            return_id=np.arange(return_id_seq + 1, return_id_seq + n_r + 1),
            parcel_id=parcels.parcel_id.values[ret_mask],
            retailer_id=parcels.retailer_id.values[ret_mask],
            return_initiated_at=parcels.collected_at[ret_mask].values
                + pd.to_timedelta(RNG.gamma(2.0, 60, n_r), unit="h"),
            return_reason=RNG.choice(RETURN_REASONS, n_r, p=RETURN_REASON_W),
            return_value_zar=np.round(parcels.parcel_value_zar.values[ret_mask] * RNG.uniform(0.5, 1.0, n_r), 2),
            drop_off_point_id=points.pickup_point_id.values[RNG.choice(len(points), n_r, p=pt_w)],
        ))
        return_id_seq += n_r

        # --- inject dirt into RAW only ---
        parcels_raw = inject_dirt_parcels(parcels)
        events_raw = inject_dirt_events(events)

        # --- write partitioned parquet ---
        y, mo = period.year, period.month
        for name, df in [("orders", orders), ("parcels", parcels_raw),
                         ("tracking_events", events_raw), ("returns", returns)]:
            d = os.path.join(out_root, name, f"year={y}", f"month={mo:02d}")
            os.makedirs(d, exist_ok=True)
            df.to_parquet(os.path.join(d, f"{name}_{y}_{mo:02d}.parquet"),
                          index=False, compression="snappy")
        totals["orders"] += len(orders); totals["parcels"] += len(parcels_raw)
        totals["events"] += len(events_raw); totals["returns"] += len(returns)
        print(f"  {period}: parcels={len(parcels_raw):>9,} events={len(events_raw):>10,} "
              f"orders={len(orders):>9,} returns={len(returns):>7,}", flush=True)
    return totals


def inject_dirt_parcels(df):
    n = len(df)
    out = df.copy()
    # null weights
    idx = RNG.choice(n, int(n * 0.002), replace=False)
    out.loc[out.index[idx], "parcel_weight_kg"] = np.nan
    # negative weights (scanner glitch)
    idx = RNG.choice(n, max(1, int(n * 0.0005)), replace=False)
    out.loc[out.index[idx], "parcel_weight_kg"] = -out.loc[out.index[idx], "parcel_weight_kg"].abs()
    # zero values
    idx = RNG.choice(n, max(1, int(n * 0.0008)), replace=False)
    out.loc[out.index[idx], "parcel_value_zar"] = 0.0
    # duplicate rows (integration retries)
    dup = out.sample(frac=0.0008, random_state=int(RNG.integers(1e6)))
    return pd.concat([out, dup], ignore_index=True)


def inject_dirt_events(df):
    n = len(df)
    out = df.copy()
    # orphan events pointing at non-existent parcels
    k = max(1, int(n * 0.0002))
    orphans = out.sample(k, random_state=int(RNG.integers(1e6))).copy()
    orphans["parcel_id"] = orphans["parcel_id"] + 900_000_000
    orphans["tracking_event_id"] = orphans["tracking_event_id"] + 900_000_000
    # a few future-dated timestamps (clock-skew bug)
    idx = RNG.choice(n, max(1, int(n * 0.0001)), replace=False)
    out.loc[out.index[idx], "event_timestamp"] = pd.Timestamp("2030-01-01")
    return pd.concat([out, orphans], ignore_index=True)


# ----------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scale", type=float, default=0.04,
                    help="1.0 = full enterprise scale (220M+ rows). 0.04 ≈ 8M rows demo.")
    ap.add_argument("--out", default="../data/raw")
    args = ap.parse_args()
    out = os.path.abspath(args.out)
    os.makedirs(out, exist_ok=True)

    print(f"PargoParcels generator | scale={args.scale} | target ≈ "
          f"{int(220e6 * args.scale):,} rows | out={out}\n")

    print("Dimensions...")
    retailers = gen_retailers(FULL_SCALE["retailers"])
    points = gen_pickup_points(FULL_SCALE["pickup_points"])
    couriers = gen_couriers(FULL_SCALE["couriers"])
    for name, df in [("retailers", retailers), ("pickup_points", points), ("couriers", couriers)]:
        df.to_parquet(os.path.join(out, f"{name}.parquet"), index=False)
        df.to_csv(os.path.join(out, f"{name}.csv"), index=False)
    n_cust = gen_customers(int(FULL_SCALE["customers"] * args.scale), out)
    print(f"  retailers={len(retailers)}, points={len(points)}, couriers={len(couriers)}, customers={n_cust:,}\n")

    print("Facts (month by month)...")
    totals = gen_facts(args.scale, dict(retailers=retailers, points=points, couriers=couriers), out)

    grand = n_cust + len(retailers) + len(points) + len(couriers) + sum(totals.values())
    print(f"\nDONE. Rows: customers={n_cust:,} " +
          " ".join(f"{k}={v:,}" for k, v in totals.items()) +
          f"\nGRAND TOTAL: {grand:,} rows")


if __name__ == "__main__":
    main()
