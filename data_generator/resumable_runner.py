"""
Resumable wrapper around generate_pargo_data.py.

Same logic, same seed(42), but checkpoints RNG state + ID sequences after
every month so generation can be split across multiple short invocations
(sandbox enforces a 45s wall clock per call).

Usage:  python3 resumable_runner.py --scale 0.04 --out ../data/raw --budget 30
Run repeatedly until it prints ALL_DONE.
"""
import argparse, os, pickle, time
import numpy as np
import pandas as pd

from generate_pargo_data import (  # noqa: F401
    RNG, MONTHS, FULL_SCALE, PROV_NAMES, TIERS, HISTORY_END,
    P_COLLECTED, P_RTS, P_LOST, P_DAMAGED, P_IN_FLIGHT,
    RETURN_RATE_BY_INDUSTRY, RETURN_REASONS, RETURN_REASON_W,
    gen_retailers, gen_pickup_points, gen_couriers, gen_customers,
    month_weights, inject_dirt_parcels, inject_dirt_events,
)

CKPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".gen_checkpoint.pkl")


def phase0(scale, out):
    """Dimensions + customers + sampling weights. Run once."""
    retailers = gen_retailers(FULL_SCALE["retailers"])
    points = gen_pickup_points(FULL_SCALE["pickup_points"])
    couriers = gen_couriers(FULL_SCALE["couriers"])
    for name, df in [("retailers", retailers), ("pickup_points", points), ("couriers", couriers)]:
        df.to_parquet(os.path.join(out, f"{name}.parquet"), index=False)
        df.to_csv(os.path.join(out, f"{name}.csv"), index=False)
    n_cust = gen_customers(int(FULL_SCALE["customers"] * scale), out)

    n_parcels_total = int(FULL_SCALE["parcels"] * scale)
    tier_w = retailers.tier.map(TIERS).values
    zipf = 1.0 / np.arange(1, len(retailers) + 1) ** 0.7
    ret_w = tier_w * zipf
    ret_w = ret_w / ret_w.sum()
    pt_w = RNG.lognormal(0, 1.1, len(points))
    pt_w[points.status.values != "Active"] *= 0.05
    pt_w = pt_w / pt_w.sum()
    cust_w = RNG.pareto(1.6, n_cust) + 1
    cust_w = cust_w / cust_w.sum()

    state = dict(
        scale=scale, mi=0, n_customers=n_cust, n_parcels_total=n_parcels_total,
        ret_w=ret_w, pt_w=pt_w, cust_w=cust_w, mw=month_weights(MONTHS),
        parcel_id_seq=0, order_id_seq=0, return_id_seq=0, event_id_seq=0,
        totals=dict(orders=0, parcels=0, events=0, returns=0),
        rng_state=RNG.bit_generator.state,
    )
    with open(CKPT, "wb") as f:
        pickle.dump(state, f)
    print(f"PHASE0_DONE retailers={len(retailers)} points={len(points)} "
          f"couriers={len(couriers)} customers={n_cust:,}", flush=True)


def run_months(out, budget):
    with open(CKPT, "rb") as f:
        st = pickle.load(f)
    RNG.bit_generator.state = st["rng_state"]

    retailers = pd.read_parquet(os.path.join(out, "retailers.parquet"))
    points = pd.read_parquet(os.path.join(out, "pickup_points.parquet"))
    couriers = pd.read_parquet(os.path.join(out, "couriers.parquet"))

    n_customers = st["n_customers"]
    ret_w, pt_w, cust_w, mw = st["ret_w"], st["pt_w"], st["cust_w"], st["mw"]
    n_parcels_total = st["n_parcels_total"]
    courier_by_prov = {p: couriers.courier_id.values[couriers.region.values == p] for p in PROV_NAMES}
    point_prov = points.province.values
    ind_by_ret = retailers.industry.values
    rate_by_ret = retailers.rate_per_parcel_zar.values

    parcel_id_seq = st["parcel_id_seq"]; order_id_seq = st["order_id_seq"]
    return_id_seq = st["return_id_seq"]; event_id_seq = st["event_id_seq"]
    totals = st["totals"]

    t0 = time.time()
    mi = st["mi"]
    while mi < len(MONTHS) and time.time() - t0 < budget:
        period = MONTHS[mi]
        n_p = max(1000, int(n_parcels_total * mw[mi]))
        m_start = period.to_timestamp()
        m_days = period.days_in_month

        n_o = int(n_p / 1.2)
        order_ids = np.arange(order_id_seq + 1, order_id_seq + n_o + 1); order_id_seq += n_o
        ord_cust = RNG.choice(n_customers, n_o, p=cust_w) + 1
        ord_ret_idx = RNG.choice(len(retailers), n_o, p=ret_w)
        ord_created = m_start + pd.to_timedelta(RNG.uniform(0, m_days * 24 * 3600, n_o), unit="s")
        order_value = np.round(np.exp(RNG.normal(6.1, 0.85, n_o)), 2)
        orders = pd.DataFrame(dict(
            order_id=order_ids, customer_id=ord_cust,
            retailer_id=retailers.retailer_id.values[ord_ret_idx],
            order_created_at=ord_created, order_value_zar=np.clip(order_value, 49, 25000),
            channel=RNG.choice(["Web", "App", "In-store kiosk"], n_o, p=[0.62, 0.33, 0.05]),
        ))

        par_order_idx = np.sort(RNG.integers(0, n_o, n_p))
        parcel_ids = np.arange(parcel_id_seq + 1, parcel_id_seq + n_p + 1); parcel_id_seq += n_p
        p_cust = ord_cust[par_order_idx]
        p_ret_idx = ord_ret_idx[par_order_idx]
        p_point_idx = RNG.choice(len(points), n_p, p=pt_w)
        p_prov = point_prov[p_point_idx]
        p_courier = np.array([RNG.choice(courier_by_prov[p]) for p in p_prov])

        created = ord_created[par_order_idx] + pd.to_timedelta(RNG.uniform(2, 30, n_p), unit="h")
        h_dispatch = RNG.gamma(2.0, 3.0, n_p)
        h_hub = RNG.gamma(2.0, 2.5, n_p)
        h_linehaul = np.where(p_prov == "Gauteng",
                              RNG.gamma(2.0, 3.5, n_p),
                              RNG.gamma(2.5, 5.5, n_p))
        h_lastmile = RNG.gamma(2.0, 2.0, n_p)
        arrived = created + pd.to_timedelta(h_dispatch + h_hub + h_linehaul + h_lastmile, unit="h")
        notified = arrived + pd.to_timedelta(RNG.uniform(0.05, 1.5, n_p), unit="h")
        dwell_h = RNG.gamma(1.6, 22, n_p)
        collected = notified + pd.to_timedelta(dwell_h, unit="h")

        status = RNG.choice(["Collected", "ExpiredRTS", "Lost", "Damaged", "InTransit"],
                            n_p, p=[P_COLLECTED, P_RTS, P_LOST, P_DAMAGED, P_IN_FLIGHT])
        recent = created > HISTORY_END - pd.Timedelta(days=4)
        status = np.where(recent & (RNG.random(n_p) < 0.6), "InTransit", status)
        is_delivered = np.isin(status, ["Collected", "Damaged"])
        is_lost = status == "Lost"
        is_rts = status == "ExpiredRTS"
        rts_at = notified + pd.Timedelta(days=8)

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

        ret_rate = np.array([RETURN_RATE_BY_INDUSTRY[i] for i in ind_by_ret[p_ret_idx]])
        ret_mask = (RNG.random(n_p) < ret_rate * 0.55) & is_delivered
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

        parcels_raw = inject_dirt_parcels(parcels)
        events_raw = inject_dirt_events(events)

        y, mo = period.year, period.month
        for name, df in [("orders", orders), ("parcels", parcels_raw),
                         ("tracking_events", events_raw), ("returns", returns)]:
            d = os.path.join(out, name, f"year={y}", f"month={mo:02d}")
            os.makedirs(d, exist_ok=True)
            df.to_parquet(os.path.join(d, f"{name}_{y}_{mo:02d}.parquet"),
                          index=False, compression="snappy")
        totals["orders"] += len(orders); totals["parcels"] += len(parcels_raw)
        totals["events"] += len(events_raw); totals["returns"] += len(returns)
        print(f"  {period}: parcels={len(parcels_raw):>9,} events={len(events_raw):>10,} "
              f"orders={len(orders):>9,} returns={len(returns):>7,}", flush=True)
        mi += 1

        st.update(mi=mi, parcel_id_seq=parcel_id_seq, order_id_seq=order_id_seq,
                  return_id_seq=return_id_seq, event_id_seq=event_id_seq,
                  totals=totals, rng_state=RNG.bit_generator.state)
        with open(CKPT, "wb") as f:
            pickle.dump(st, f)

    if mi >= len(MONTHS):
        grand = (st["n_customers"] + 150 + 4000 + 500 + sum(totals.values()))
        print("ALL_DONE " + " ".join(f"{k}={v:,}" for k, v in totals.items()))
        print(f"GRAND_TOTAL: {grand:,} rows (incl. dimensions)")
    else:
        print(f"PROGRESS {mi}/{len(MONTHS)} months")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--scale", type=float, default=0.04)
    ap.add_argument("--out", default="../data/raw")
    ap.add_argument("--budget", type=float, default=28)
    a = ap.parse_args()
    out = os.path.abspath(a.out)
    os.makedirs(out, exist_ok=True)
    if not os.path.exists(CKPT):
        phase0(a.scale, out)
    else:
        run_months(out, a.budget)
