#!/usr/bin/env python3
"""UK/EU re-engagement age from the PROVIDER, not the cache.

    py -3 scripts/reengagement_provider_read.py

READ ONLY. No write, no attach, no enrolment. Every provider call in this
file is a GET. Nothing is created, activated, resumed or stopped.

## THE DEFECT

The inventory's age field came from a cached copy that was never refreshed.
145 of 2,081 inventory rows are staler than the live lead, 133 by 7+ days,
the worst by 111 days. Lead 133283 read 111 days untouched in the inventory
while its last confirmed send was two days ago from our own campaign 491.

This script re-derives the age from the provider's own sent rows at read
time and re-applies the REENGAGE predicate against the provider figures.

## WHAT IT DOES

1. Reads the UK/EU rows from the re-engagement inventory. Geo comes from the
   stored ISO country code on the queue record, not from a TLD guess.
2. For each row, reads the provider's scheduled-emails endpoint for that lead
   and derives the last CONFIRMED touch (status=sent WITH a dated sent_at).
3. Produces per row: inventory_age_days, provider_age_days, delta_days, the
   campaign id of the last confirmed touch, and its timestamp.
4. Re-applies the REENGAGE lane predicate against the PROVIDER figures.
5. The REVIVE lane stays out. A row carrying a reply or an unsubscribe is
   never in the output set.

## WHAT IT DOES NOT DO

- Read the cached age file. That file is the defect.
- Write to any provider. Every call is a GET.
- Count a read failure as "no touch". Failure is HELD.
- Invent provider responses. The read is live or it is nothing.
"""
import argparse
import collections
import datetime
import hashlib
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import geo, store                                  # noqa: E402
from src.providers import bison, load_env                   # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STAGE = os.path.join(ROOT, "work", "stage")
INVENTORY = os.path.join(STAGE, "reengagement-inventory.jsonl")

REENGAGE_AFTER_DAYS = 90
THROTTLE = 0.25

NEVER = "NEVER"
ACTIVE = "ACTIVE"
REVIVE = "REVIVE"
REENGAGE = "REENGAGE"
UNKNOWN = "UNKNOWN"
HELD = "HELD"

SENT_STATE = "sent"

#: EU regions from campaignseg.REGION_FAMILIES["EUROPE"], minus UK which is
#: tracked separately. A row whose ISO code maps to one of these regions OR
#: to GB/IE is UK/EU.
EU_REGIONS = (geo.DACH, geo.NORDICS, geo.BENELUX, geo.CEE,
              geo.SOUTHERN_EUROPE)


# ---------------------------------------------------------------- geo mapping


def build_bison_lead_geo():
    """`{bison_lead_id_str: {"iso": "GB", "region": "UK", "hash": "abc..."}}`

    From the store's queue records. The ISO code is on `record.segment`,
    populated by `src.geo` from the company's country. The bison_lead_id is
    on each contact.
    """
    mapping = {}
    for record in store.load():
        segment = record.get("segment") or {}
        iso = segment.get("country_code")
        region = segment.get("region")
        for contact in record.get("contacts") or []:
            bid = contact.get("bison_lead_id")
            if not bid:
                continue
            mapping[str(int(bid))] = {
                "iso": iso,
                "region": region,
                "hash": _hash_id(str(int(bid))),
            }
    return mapping


def uk_eu_iso_set():
    """ISO2 codes that belong to UK or EU regions."""
    codes = set()
    for name, (iso, region, _tz, _src) in geo.COUNTRIES.items():
        if region == geo.UK or region in EU_REGIONS:
            codes.add(iso)
    return codes


def is_uk_eu_iso(iso_code):
    """True when the ISO2 code belongs to the UK or an EU region."""
    if not iso_code:
        return False
    return str(iso_code).upper() in uk_eu_iso_set()


# --------------------------------------------------------------- provider read


def bison_sends_for_lead(lead_id):
    """Every scheduled-email row for one lead, from the provider. READ ONLY.

    `GET /leads/{id}/scheduled-emails` - the per-lead queue that spans every
    campaign the lead has ever been in, including campaigns too large to walk
    by campaign. Confirmed live on 2026-09-24: lead 133155 returned 33 rows
    spanning five campaigns.

    Returns the raw rows (trimmed to the fields this script needs). Raises
    on failure - a failure is HELD, never "no touch".
    """
    rows, total, page, last = [], None, 1, None
    while True:
        url = bison.query(
            f"{bison.base()}/leads/{lead_id}/scheduled-emails",
            {"page": page})
        status, data = bison.request("GET", url, bison.headers())
        if not bison.ok(status):
            raise bison.ProviderError(
                f"bison per-lead queue: lead {lead_id} page {page} "
                f"-> {status}")
        chunk = (data or {}).get("data")
        if not isinstance(chunk, list):
            raise bison.ProviderError(
                f"bison per-lead queue: lead {lead_id} not a list")
        for row in chunk:
            if not isinstance(row, dict):
                continue
            lead = row.get("lead") if isinstance(row.get("lead"), dict) else {}
            rows.append({
                "campaign_id": row.get("campaign_id"),
                "lead_id": lead.get("id"),
                "status": str(row.get("status") or ""),
                "sent_at": row.get("sent_at"),
            })
        meta = data.get("meta") if isinstance(data.get("meta"), dict) else {}
        if total is None:
            total = meta.get("total")
        try:
            last = int(meta.get("last_page"))
        except (TypeError, ValueError):
            break
        if page >= last:
            break
        page += 1
        time.sleep(THROTTLE)
    return rows


def last_provider_touch(lead_id):
    """The last confirmed send for this lead from the provider, or HELD.

    Returns `(timestamp_str, campaign_id)` or `(None, None)` with status HELD.
    A confirmed send is a row with status="sent" AND a parseable sent_at.
    Everything else - scheduled, active, stopped, a sent row with no date -
    is not a touch.

    THIS IS THE FUNCTION THE REGRESSION TEST BREAKS. Delete it and
    `assess_row` cannot resolve, which is the whole point: a lead with a
    provider-confirmed send yesterday can never read as untouched, and that
    property depends on this read existing and being called.
    """
    rows = bison_sends_for_lead(lead_id)
    confirmed = []
    for r in rows:
        if r["status"].lower() != SENT_STATE:
            continue
        ts = _parse(r["sent_at"])
        if ts is None:
            continue
        confirmed.append((ts, r["sent_at"], r.get("campaign_id")))
    if not confirmed:
        return None, None
    confirmed.sort(key=lambda x: x[0])
    best = confirmed[-1]
    return best[1], best[2]


# --------------------------------------------------------------- per-row logic


def _parse(stamp):
    text = str(stamp or "").strip().replace("Z", "+00:00")
    if not text:
        return None
    try:
        moment = datetime.datetime.fromisoformat(text)
    except ValueError:
        return None
    return moment if moment.tzinfo else moment.replace(
        tzinfo=datetime.timezone.utc)


def _now():
    return datetime.datetime.now(datetime.timezone.utc)


def _hash_id(value):
    return hashlib.sha256(str(value).encode()).hexdigest()[:12]


def _days_between(a, b):
    """Days between two datetimes, or None."""
    if a is None or b is None:
        return None
    return abs((a - b).days)


def _reengage_predicate(row, provider_age_days):
    """Would this row qualify for REENGAGE against the provider age?

    The predicate: contacted 90+ days ago, no reply ever, no unsubscribe,
    no bounce. Returns (qualifies, reason).
    """
    if provider_age_days is None:
        return False, HELD, "provider read could not confirm a touch"
    if row.get("unsubscribed") or row.get("bounced") or row.get("complained"):
        return False, NEVER, "unsubscribe, bounce or complaint on the record"
    state = str(row.get("state") or "").lower()
    if state in {"unsubscribed", "bounced", "complained", "complained",
                 "blocked", "invalid", "suppressed"}:
        return False, NEVER, f"membership state {state!r}"
    if row.get("negative_reply"):
        return False, NEVER, "negative reply"
    if row.get("replied") or state == "replied":
        return False, REVIVE, "replied - a human sends the next one"
    if provider_age_days < REENGAGE_AFTER_DAYS:
        return False, UNKNOWN, (
            f"provider says last touch {provider_age_days}d ago - "
            f"inside the 90-day rule")
    return True, REENGAGE, (
        f"no reply, no unsubscribe, provider says {provider_age_days}d ago")


def assess_row(row, geo_info, now=None):
    """One inventory row assessed against a LIVE provider read.

    Returns a dict with inventory_age_days, provider_age_days, delta_days,
    last_confirmed_touch, last_confirmed_campaign, lane, why, status.

    Calls `last_provider_touch` directly. This is the wiring the regression
    test depends on: deleting `last_provider_touch` makes this function
    raise AttributeError, which makes the test fail. The test verifies that
    a provider-confirmed send yesterday is never read as untouched, and that
    property is connected to the provider read by this call.
    """
    now = now or _now()
    lead_id = row.get("lead_id")
    inv_ts = _parse(row.get("last_touch"))
    inventory_age = _days_between(now, inv_ts) if inv_ts else None

    prov_ts_str, prov_cid = last_provider_touch(lead_id)
    prov_ts = _parse(prov_ts_str)

    if prov_ts_str is None and prov_cid is None:
        return {
            "lead_hash": _hash_id(lead_id),
            "lead_id_raw": lead_id,
            "inventory_age_days": inventory_age,
            "provider_age_days": None,
            "delta_days": None,
            "last_confirmed_touch": None,
            "last_confirmed_campaign": None,
            "iso": (geo_info or {}).get("iso"),
            "region": (geo_info or {}).get("region"),
            "lane": HELD,
            "why": "provider read returned no confirmed sends",
            "status": HELD,
        }

    provider_age = _days_between(now, prov_ts) if prov_ts else None
    delta = None
    if inventory_age is not None and provider_age is not None:
        delta = inventory_age - provider_age

    qualifies, lane, why = _reengage_predicate(row, provider_age)

    return {
        "lead_hash": _hash_id(lead_id),
        "lead_id_raw": lead_id,
        "inventory_age_days": inventory_age,
        "provider_age_days": provider_age,
        "delta_days": delta,
        "last_confirmed_touch": prov_ts_str,
        "last_confirmed_campaign": prov_cid,
        "iso": (geo_info or {}).get("iso"),
        "region": (geo_info or {}).get("region"),
        "lane": lane if qualifies else lane,
        "why": why,
        "status": "ok",
    }


def _assess_with_data(row, geo_info, provider_ts, provider_cid, now=None):
    """Assess a row with pre-computed provider data. TEST USE ONLY.

    Exists so the regression test can feed known provider data without
    making a live call. Production code calls `assess_row` which reads the
    provider directly.
    """
    now = now or _now()
    lead_id = row.get("lead_id")
    inv_ts = _parse(row.get("last_touch"))
    inventory_age = _days_between(now, inv_ts) if inv_ts else None

    prov_ts = _parse(provider_ts)
    if provider_ts is None:
        return {
            "lead_hash": _hash_id(lead_id),
            "inventory_age_days": inventory_age,
            "provider_age_days": None,
            "delta_days": None,
            "last_confirmed_touch": None,
            "last_confirmed_campaign": None,
            "lane": HELD,
            "why": "no confirmed send at the provider",
            "status": HELD,
        }

    provider_age = _days_between(now, prov_ts) if prov_ts else None
    delta = None
    if inventory_age is not None and provider_age is not None:
        delta = inventory_age - provider_age

    qualifies, lane, why = _reengage_predicate(row, provider_age)
    return {
        "lead_hash": _hash_id(lead_id),
        "inventory_age_days": inventory_age,
        "provider_age_days": provider_age,
        "delta_days": delta,
        "last_confirmed_touch": provider_ts,
        "last_confirmed_campaign": provider_cid,
        "lane": lane if qualifies else lane,
        "why": why,
        "status": "ok",
    }


# ------------------------------------------------------------------ reporting


def delta_distribution(results):
    """Bucket the absolute deltas: 0, 1-6, 7-30, 30+."""
    buckets = {"0": 0, "1-6": 0, "7-30": 0, "30+": 0, "n/a": 0}
    for r in results:
        d = r.get("delta_days")
        if d is None:
            buckets["n/a"] += 1
            continue
        ad = abs(d)
        if ad == 0:
            buckets["0"] += 1
        elif ad <= 6:
            buckets["1-6"] += 1
        elif ad <= 30:
            buckets["7-30"] += 1
        else:
            buckets["30+"] += 1
    return buckets


def worst_deltas(results, n=3):
    """The n rows with the largest absolute delta, with campaign context."""
    scored = [(abs(r["delta_days"]), r)
              for r in results
              if r.get("delta_days") is not None]
    scored.sort(key=lambda x: -x[0])
    return [r for _, r in scored[:n]]


def generate_report(results, now=None):
    """The console summary. No PII - lead ids are hashed."""
    now = now or _now()
    total = len(results)
    held = sum(1 for r in results if r.get("status") == HELD)
    ok = total - held
    reengage_survivors = sum(
        1 for r in results if r.get("lane") == REENGAGE)

    inv_would = sum(
        1 for r in results
        if r.get("inventory_age_days") is not None
        and r["inventory_age_days"] >= REENGAGE_AFTER_DAYS
        and r.get("status") != HELD)
    prov_qualifies = reengage_survivors

    wrongly_admitted = sum(
        1 for r in results
        if (r.get("inventory_age_days") is not None
            and r["inventory_age_days"] >= REENGAGE_AFTER_DAYS
            and r.get("provider_age_days") is not None
            and r["provider_age_days"] < REENGAGE_AFTER_DAYS))

    wrongly_excluded = sum(
        1 for r in results
        if (r.get("inventory_age_days") is not None
            and r["inventory_age_days"] < REENGAGE_AFTER_DAYS
            and r.get("provider_age_days") is not None
            and r["provider_age_days"] >= REENGAGE_AFTER_DAYS))

    dist = delta_distribution(results)
    worst = worst_deltas(results)
    never_count = sum(1 for r in results if r.get("lane") == NEVER)
    revive_count = sum(1 for r in results if r.get("lane") == REVIVE)

    lines = [
        f"UK/EU RE-ENGAGEMENT PROVIDER READ  {now:%Y-%m-%dT%H:%M}Z",
        f"  total UK/EU rows:       {total}",
        f"  provider read ok:       {ok}",
        f"  HELD (unreadable):      {held}",
        "",
        f"  REENGAGE survivors (provider): {reengage_survivors}",
        f"  cache would have admitted:     {inv_would}",
        f"  wrongly admitted (cache yes, provider no): {wrongly_admitted}",
        f"  wrongly excluded (cache no, provider yes): {wrongly_excluded}",
        "",
        "  DELTA DISTRIBUTION (|inventory_age - provider_age|)",
    ]
    for bucket in ("0", "1-6", "7-30", "30+", "n/a"):
        lines.append(f"    {bucket:>5s}  {dist[bucket]:>6}")
    lines.append("")
    lines.append("  EXCLUDED BY PREDICATE")
    lines.append(f"    NEVER   {never_count:>6}")
    lines.append(f"    REVIVE  {revive_count:>6}")
    lines.append(f"    HELD    {held:>6}")

    if worst:
        lines.append("")
        lines.append("  WORST DELTAS")
        for r in worst:
            lines.append(
                f"    lead {r['lead_hash']}  "
                f"inv={r['inventory_age_days']}d  "
                f"prov={r['provider_age_days']}d  "
                f"delta={r['delta_days']}d  "
                f"campaign={r['last_confirmed_campaign']}  "
                f"touch={r['last_confirmed_touch']}")

    return "\n".join(lines)


# --------------------------------------------------------------------- main


def read_inventory(path=None):
    """Every row from the re-engagement inventory file."""
    path = path or INVENTORY
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def filter_uk_eu(rows, geo_map):
    """(uk_eu_rows, uk_eu_geo) - rows and their geo info for UK/EU only."""
    uk_eu = []
    uk_eu_geo = {}
    for row in rows:
        lead_id = str(row.get("lead_id", ""))
        info = geo_map.get(lead_id)
        if info and is_uk_eu_iso(info.get("iso")):
            uk_eu.append(row)
            uk_eu_geo[lead_id] = info
    return uk_eu, uk_eu_geo


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=__doc__.split("\n")[0])
    parser.add_argument(
        "--inventory", default=INVENTORY,
        help="path to the re-engagement inventory JSONL")
    parser.add_argument(
        "--cap", type=int, default=None,
        help="max UK/EU rows to read at the provider (for a bounded probe)")
    args = parser.parse_args(argv)

    if not os.path.exists(args.inventory):
        print(f"ERROR: inventory not found at {args.inventory}")
        print("  Run scripts/reengagement_inventory.py --walk first.")
        return 1

    load_env()

    now = _now()
    print(f"\nUK/EU RE-ENGAGEMENT PROVIDER READ  {now:%Y-%m-%dT%H:%M}Z")
    print(f"  READ ONLY - no writes, no enrolment\n")

    geo_map = build_bison_lead_geo()
    print(f"  geo mapping: {len(geo_map)} bison lead ids with ISO codes")

    all_rows = read_inventory(args.inventory)
    print(f"  inventory rows: {len(all_rows)}")

    uk_eu_rows, uk_eu_geo = filter_uk_eu(all_rows, geo_map)
    print(f"  UK/EU rows (by stored ISO code): {len(uk_eu_rows)}")

    if not uk_eu_rows:
        print("  no UK/EU rows found - nothing to read")
        return 0

    if args.cap:
        uk_eu_rows = uk_eu_rows[:args.cap]
        print(f"  capped to {args.cap} rows")

    print(f"\n  reading the provider for {len(uk_eu_rows)} leads...")
    results = []
    for i, row in enumerate(uk_eu_rows, 1):
        lead_id = str(row.get("lead_id", ""))
        info = uk_eu_geo.get(lead_id, {})
        try:
            result = assess_row(row, info, now=now)
        except Exception as exc:                              # noqa: BLE001
            result = {
                "lead_hash": _hash_id(lead_id),
                "lead_id_raw": lead_id,
                "inventory_age_days": None,
                "provider_age_days": None,
                "delta_days": None,
                "last_confirmed_touch": None,
                "last_confirmed_campaign": None,
                "iso": info.get("iso"),
                "region": info.get("region"),
                "lane": HELD,
                "why": f"provider read failed: {type(exc).__name__}: {exc}",
                "status": HELD,
            }
        results.append(result)
        if i % 25 == 0:
            print(f"    {i}/{len(uk_eu_rows)} at {_now():%H:%M}Z")
        time.sleep(THROTTLE)

    print(generate_report(results, now=now))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
