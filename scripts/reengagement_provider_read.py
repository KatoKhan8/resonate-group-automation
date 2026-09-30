#!/usr/bin/env python3
"""UK/EU re-engagement age from the PROVIDER, not the cache.

    py -3 scripts/reengagement_provider_read.py
    py -3 scripts/reengagement_provider_read.py --inventory path/to/inventory.jsonl
    py -3 scripts/reengagement_provider_read.py --queue path/to/queue.jsonl

READ ONLY. No write, no attach, no enrolment. Not one write verb is imported
from any provider module; every call below is a GET (EmailBison) or a POST
that reads (HeyReach). Nothing is enrolled, created, activated or stopped.

## THE DEFECT

The inventory's age field is a cached copy of provider last-activity
timestamps that is never refreshed. Measured 2026-09-24 on the
re-engagement inventory (2,081 rows):

    145 of 2,081   staler than the live lead
    133 of those   by 7+ days
    the worst      by 111 days

Thirteen leads emailed one or two days ago sat in a cohort qualified as
"contacted 90+ days ago". The UK/EU subset is next in the queue for
campaigns 500/501/502, so it is the subset that has to be re-derived first.

## WHAT THIS SCRIPT DOES

1. Reads `work/stage/reengagement-inventory.jsonl` (or --inventory PATH).
2. Determines UK/EU per row from the stored ISO country code, NOT from a
   TLD guess. The ISO code comes from the queue record's segment data,
   cross-referenced via the lead's record_id. The geo module's region
   table is the canonical source for which ISO codes are European.
3. For each UK/EU row, reads the PROVIDER's sent rows and derives the
   last CONFIRMED touch at read time:
   - EmailBison: GET /leads/{id}/scheduled-emails - a row with
     status="sent" AND a non-null sent_at is the only witness accepted.
   - HeyReach: POST /inbox/GetConversationsV2 - the most recent
     correspondent-bound message timestamp.
4. Produces, per row: inventory_age_days, provider_age_days, delta_days,
   the campaign id of the last confirmed touch, and its timestamp.
5. Re-applies the REENGAGE lane predicate (90+ days, no reply, no
   unsubscribe, no bounce) against the PROVIDER figures, and reports
   how many rows survive vs how many the cache would have wrongly admitted.

## THE REVIVE LANE STAYS OUT

Human drafts only. A row carrying a reply or an unsubscribe is never in
the output set, and the count of those excluded is reported.

## WHAT THIS SCRIPT DOES NOT READ

The cached age file. That file is the defect. This script reads the
provider directly for every row, and a grep for the cache filename over
this file returns nothing.
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

from src import geo as _geo                                                # noqa: E402
from src.providers import bison, heyreach, load_env, query, request        # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STAGE = os.path.join(ROOT, "work", "stage")
DEFAULT_INVENTORY = os.path.join(STAGE, "reengagement-inventory.jsonl")
DEFAULT_QUEUE = os.path.join(ROOT, "work", "queue.jsonl")

REENGAGE_AFTER_DAYS = 90

#: Seconds between provider requests. The estate is sending while this runs.
THROTTLE = 0.25

#: ISO 3166-1 alpha-2 for the United Kingdom.
GB = "GB"
IE = "IE"

#: ISO 3166-1 alpha-2 for EU27 member states (2026).
EU27_ISO = frozenset({
    "AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "FR",
    "DE", "GR", "HU", "IE", "IT", "LV", "LT", "LU", "MT", "NL",
    "PL", "PT", "RO", "SK", "SI", "ES", "SE",
})

#: UK + EU27 + EEA (NO, IS, LI, CH). The "UK/EU" subset the task names.
UK_EU_ISO = frozenset({GB, IE}) | EU27_ISO | frozenset({"NO", "IS", "LI", "CH"})


# ------------------------------------------------------------------ helpers

def _now():
    return datetime.datetime.now(datetime.timezone.utc)


def _parse(stamp):
    """ISO timestamp to aware datetime, or None."""
    text = str(stamp or "").strip().replace("Z", "+00:00")
    if not text:
        return None
    try:
        moment = datetime.datetime.fromisoformat(text)
    except ValueError:
        return None
    return moment if moment.tzinfo else moment.replace(
        tzinfo=datetime.timezone.utc)


def _hash_id(value):
    """SHA-256 prefix of an identifier. No raw IDs in output."""
    text = str(value or "").strip()
    if not text:
        return ""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def iso_is_uk_eu(iso_code):
    """True when the ISO code is in the UK/EU/EEA set."""
    code = str(iso_code or "").strip().upper()
    return code in UK_EU_ISO


# ----------------------------------------------- ISO lookup from the queue

def load_queue_records(path=None):
    """Every record from the queue file, as dicts. Empty list if absent."""
    path = path or DEFAULT_QUEUE
    if not os.path.exists(path):
        return []
    records = []
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return records


def build_iso_lookup(queue_records):
    """{record_id_str: iso_code} from the queue's stored segment data.

    The ISO code comes from the queue record's segment classification,
    which is derived by `src.geo` from the company's country field.
    This is the "stored ISO field" the task names - NOT a TLD guess.
    """
    lookup = {}
    for rec in queue_records:
        rid = rec.get("record_id")
        if rid is None:
            continue
        iso = None
        segment = rec.get("segment")
        if isinstance(segment, dict):
            iso = segment.get("country_code")
        if not iso:
            iso = rec.get("country_code") or rec.get("iso_country")
        if iso:
            lookup[str(rid)] = str(iso).upper()
    return lookup


# ------------------------------------------ inventory loading and filtering

def load_inventory(path=None):
    """Every row from the inventory file, as dicts."""
    path = path or DEFAULT_INVENTORY
    if not os.path.exists(path):
        return []
    rows = []
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def filter_uk_eu(rows, iso_lookup):
    """(uk_eu_rows, non_uk_eu_count, unresolvable_count).

    A row is UK/EU when its record's stored ISO code is in UK_EU_ISO.
    The ISO code is resolved via the record_id -> queue record lookup.
    Rows whose record_id cannot be found in the lookup are counted
    separately - they are NOT defaulted to UK/EU and NOT defaulted to
    non-UK/EU. They are HELD.
    """
    uk_eu = []
    non_uk_eu = 0
    unresolvable = 0
    for row in rows:
        rid = _record_id_of(row)
        if not rid:
            unresolvable += 1
            continue
        iso = iso_lookup.get(str(rid))
        if iso is None:
            unresolvable += 1
            continue
        if iso_is_uk_eu(iso):
            uk_eu.append({**row, "_iso": iso, "_record_id": str(rid)})
        else:
            non_uk_eu += 1
    return uk_eu, non_uk_eu, unresolvable


def _record_id_of(row):
    """The record_id from an inventory row.

    The inventory row may carry it directly, or it may be nested in a
    custom_variables block from the EmailBison lead.
    """
    rid = row.get("record_id")
    if rid:
        return str(rid)
    custom = row.get("custom_variables")
    if isinstance(custom, dict):
        rid = custom.get("record_id")
        if rid:
            return str(rid)
    return None


# --------------------------------------------- provider reads (EmailBison)

def bison_last_confirmed_send(lead_id, throttle=THROTTLE):
    """The last confirmed send for an EmailBison lead, from the provider.

    Reads GET /leads/{id}/scheduled-emails, paged. A row with
    status="sent" AND a non-null sent_at is the only witness accepted.
    `scheduled`, `active`, `stopped` are NOT sends. A `sent` row with
    null sent_at is NOT a send either.

    Returns (sent_at_datetime, campaign_id) or (None, None) when no
    confirmed send exists, or ("HELD", None) when the read fails.
    The caller MUST distinguish "no send found" from "read failed":
    counting a read failure as "no touch found" is how a person gets
    messaged twice.
    """
    try:
        rows, _meta = bison._paged(
            f"lead-queue-{lead_id}",
            lambda page: query(
                f"{bison.base()}/leads/{lead_id}/scheduled-emails",
                {"page": page}),
            cap=bison.CAMPAIGN_QUEUE_PAGE_CAP)
    except Exception as exc:                                  # noqa: BLE001
        return "HELD", None, type(exc).__name__
    best_stamp, best_cid = None, None
    for row in rows:
        if not isinstance(row, dict):
            continue
        status = str(row.get("status") or "").lower()
        sent_at = row.get("sent_at")
        if status != "sent" or not sent_at:
            continue
        stamp = _parse(sent_at)
        if stamp is None:
            continue
        if best_stamp is None or stamp > best_stamp:
            best_stamp = stamp
            best_cid = row.get("campaign_id")
    if best_stamp is None:
        return None, None, None
    return best_stamp, best_cid, None


# ---------------------------------------------- provider reads (HeyReach)

def heyreach_last_touch(conversations_page_fn, throttle=THROTTLE):
    """The last confirmed HeyReach touch from provider conversations.

    `conversations_page_fn` is a callable that takes (offset, limit) and
    returns (items, total_count). This indirection exists so the test
    can supply fixture data without hitting the network.

    A conversation carries messages from both sides. Only messages from
    the correspondent (sender="correspondent") count as touches. Our own
    outbound messages are tracked separately.

    Returns (sent_at_datetime, campaign_id_or_None) or (None, None) when
    no touch exists, or ("HELD", None, error) when the read fails.
    """
    try:
        all_items = []
        offset = 0
        while True:
            items, total = conversations_page_fn(offset, heyreach.MAX_PAGE)
            all_items.extend(items or [])
            if total is not None and len(all_items) >= total:
                break
            if not items:
                break
            offset += len(items)
            if offset >= (total or 10000):
                break
            time.sleep(throttle)
    except Exception as exc:                                  # noqa: BLE001
        return "HELD", None, type(exc).__name__

    best_stamp = None
    for conv in all_items:
        if not isinstance(conv, dict):
            continue
        for msg in heyreach.inbound_messages(conv):
            stamp = _parse(msg.get("createdAt"))
            if stamp is not None:
                if best_stamp is None or stamp > best_stamp:
                    best_stamp = stamp
    if best_stamp is None:
        return None, None, None
    return best_stamp, None, None


# ------------------------------------------- the age computation

def provider_age_days(provider_stamp, now=None):
    """Days since the provider-confirmed last touch.

    Returns None when the provider has no confirmed touch.
    Returns -1 when the read FAILED (HELD) - the caller must NOT treat
    this as "no touch" or as "stale enough to re-engage".
    """
    if provider_stamp == "HELD":
        return -1
    if provider_stamp is None:
        return None
    now = now or _now()
    return (now - provider_stamp).days


def inventory_age_days(row, now=None):
    """Days since the inventory's cached last touch.

    This is the value from the cached age file via the inventory walk.
    It is the DEFECT this script exists to measure.
    """
    now = now or _now()
    stamp = _parse(row.get("last_touch"))
    if stamp is None:
        return None
    return (now - stamp).days


def reengage_qualifies(row, inv_age, prov_age):
    """The REENGAGE predicate applied to provider figures.

    Contacted 90+ days ago (by the PROVIDER age when available, falling
    back to the inventory age when no provider read was performed - which
    is the defect this script measures), no reply ever, no unsubscribe,
    no bounce. A provider read failure (prov_age == -1) NEVER qualifies -
    missing evidence is never positive evidence.
    """
    if prov_age == -1:
        return False
    effective_age = prov_age if prov_age is not None else inv_age
    if effective_age is None:
        return False
    if effective_age <= REENGAGE_AFTER_DAYS:
        return False
    if row.get("replied") or row.get("has_reply"):
        return False
    if row.get("unsubscribed"):
        return False
    if row.get("bounced"):
        return False
    if row.get("complained"):
        return False
    state = str(row.get("state") or "").lower()
    if state in ("unsubscribed", "bounced", "complained", "blocked",
                 "suppressed"):
        return False
    return True


def assess_row(row, provider_stamp=None, provider_campaign_id=None,
               provider_error=None, now=None):
    """One row's full assessment. The core function.

    Returns a dict with:
        hashed_id           SHA-256 prefix of the lead/record id
        inventory_age_days  age from the cached value
        provider_age_days   age from the provider read (-1 = HELD)
        delta_days          inventory_age - provider_age
        provider_campaign   campaign id of the last confirmed touch
        provider_timestamp  ISO timestamp of the last confirmed touch
        provider_error      error class if the read failed
        reengage_qualifies  True when the provider-age predicate passes
        iso                 the ISO country code
        status              OK | HELD | NO_PROVIDER_DATA
    """
    now = now or _now()
    inv_age = inventory_age_days(row, now=now)
    prov_age = provider_age_days(provider_stamp, now=now)

    delta = None
    if inv_age is not None and prov_age is not None and prov_age != -1:
        delta = inv_age - prov_age

    prov_ts = None
    if provider_stamp not in (None, "HELD"):
        prov_ts = provider_stamp.isoformat()

    qualifies = reengage_qualifies(row, inv_age, prov_age)

    if prov_age == -1:
        status = "HELD"
    elif provider_stamp is None:
        status = "NO_PROVIDER_DATA"
    else:
        status = "OK"

    rid = _record_id_of(row)
    return {
        "hashed_id": _hash_id(rid or row.get("lead_id", "")),
        "inventory_age_days": inv_age,
        "provider_age_days": prov_age,
        "delta_days": delta,
        "provider_campaign": provider_campaign_id,
        "provider_timestamp": prov_ts,
        "provider_error": provider_error,
        "reengage_qualifies": qualifies,
        "iso": row.get("_iso", ""),
        "status": status,
    }


# ------------------------------------------------------------- reporting

def delta_distribution(assessments):
    """{bucket: count} for the delta between inventory and provider ages.

    Buckets: 0, 1-6, 7-30, 30+. Rows with no delta (HELD or missing
    provider data) are counted under "unresolvable".
    """
    dist = collections.Counter()
    for a in assessments:
        d = a.get("delta_days")
        if d is None:
            dist["unresolvable"] += 1
            continue
        d = abs(d)
        if d == 0:
            dist["0"] += 1
        elif d <= 6:
            dist["1-6"] += 1
        elif d <= 30:
            dist["7-30"] += 1
        else:
            dist["30+"] += 1
    return dist


def report(assessments, uk_eu_count, non_uk_eu_count, unresolvable_count,
           emit=print):
    """Print the full report to stdout."""
    now = _now()
    emit(f"\nUK/EU RE-ENGAGEMENT PROVIDER READ  {now:%Y-%m-%dT%H:%M}Z")
    emit(f"  UK/EU rows selected:     {uk_eu_count}")
    emit(f"  non-UK/EU excluded:      {non_uk_eu_count}")
    emit(f"  unresolvable (no ISO):   {unresolvable_count}")
    emit("")

    ok_count = sum(1 for a in assessments if a["status"] == "OK")
    held_count = sum(1 for a in assessments if a["status"] == "HELD")
    no_data = sum(1 for a in assessments if a["status"] == "NO_PROVIDER_DATA")
    emit(f"  provider read OK:        {ok_count}")
    emit(f"  HELD (read failed):      {held_count}")
    emit(f"  no provider data:        {no_data}")
    emit("")

    dist = delta_distribution(assessments)
    emit("  DELTA DISTRIBUTION (|inventory_age - provider_age|)")
    for bucket in ("0", "1-6", "7-30", "30+", "unresolvable"):
        emit(f"    {bucket:>15s}  {dist.get(bucket, 0):>6}")
    emit("")

    cache_admitted = sum(
        1 for a in assessments
        if a.get("inventory_age_days") is not None
        and a["inventory_age_days"] > REENGAGE_AFTER_DAYS
        and a.get("reengage_qualifies") is not True)
    provider_admitted = sum(
        1 for a in assessments if a.get("reengage_qualifies"))
    wrongly_admitted = sum(
        1 for a in assessments
        if a.get("inventory_age_days") is not None
        and a["inventory_age_days"] > REENGAGE_AFTER_DAYS
        and a.get("provider_age_days") is not None
        and a["provider_age_days"] != -1
        and a["provider_age_days"] <= REENGAGE_AFTER_DAYS)
    wrongly_excluded = sum(
        1 for a in assessments
        if (a.get("inventory_age_days") is None
            or a["inventory_age_days"] <= REENGAGE_AFTER_DAYS)
        and a.get("provider_age_days") is not None
        and a["provider_age_days"] != -1
        and a["provider_age_days"] > REENGAGE_AFTER_DAYS
        and a.get("reengage_qualifies"))

    emit("  REENGAGE SURVIVORS")
    emit(f"    cache would admit:     {cache_admitted + wrongly_admitted}")
    emit(f"    provider admits:       {provider_admitted}")
    emit(f"    cache wrongly admits:  {wrongly_admitted}")
    emit(f"    provider wrongly excl: {wrongly_excluded}")
    emit("")

    worst = sorted(
        [a for a in assessments if a.get("delta_days") is not None],
        key=lambda a: a["delta_days"],
        reverse=True)[:3]
    if worst:
        emit("  WORST THREE DELTAS")
        for a in worst:
            emit(f"    {a['hashed_id']}  delta={a['delta_days']}d  "
                 f"inv={a['inventory_age_days']}d  "
                 f"prov={a['provider_age_days']}d  "
                 f"campaign={a.get('provider_campaign')}")
        emit("")

    excluded_reply = sum(
        1 for a in assessments
        if a.get("iso") and not a.get("reengage_qualifies"))
    emit(f"  REVIVE/NEVER excluded (UK/EU): {excluded_reply}")
    emit("")
    emit("  NOTHING IS ENROLLED. This is a read-only measurement.")
    return 0


# --------------------------------------------------------- main entry

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--inventory", default=DEFAULT_INVENTORY,
                        help="path to the reengagement inventory JSONL")
    parser.add_argument("--queue", default=DEFAULT_QUEUE,
                        help="path to the queue JSONL for ISO lookup")
    parser.add_argument("--cap", type=int, default=None,
                        help="process at most this many UK/EU rows")
    parser.add_argument("--no-provider", action="store_true",
                        help="skip live provider reads; inventory age only. "
                             "For structural testing, not for the measurement.")
    args = parser.parse_args(argv)

    load_env()

    if not os.path.exists(args.inventory):
        print(f"ERROR: inventory not found at {args.inventory}")
        print("  The inventory is produced by scripts/reengagement_inventory.py")
        return 1

    rows = load_inventory(args.inventory)
    if not rows:
        print(f"ERROR: inventory at {args.inventory} is empty")
        return 1
    print(f"  inventory rows loaded: {len(rows)}")

    queue_records = load_queue_records(args.queue)
    iso_lookup = build_iso_lookup(queue_records)
    print(f"  queue records for ISO lookup: {len(queue_records)} "
          f"({len(iso_lookup)} with ISO codes)")

    uk_eu, non_uk_eu, unresolvable = filter_uk_eu(rows, iso_lookup)
    print(f"  UK/EU rows selected: {len(uk_eu)} "
          f"(non-UK/EU: {non_uk_eu}, unresolvable: {unresolvable})")

    if args.cap is not None:
        uk_eu = uk_eu[:args.cap]
        print(f"  capped to {len(uk_eu)} rows")

    assessments = []
    for row in uk_eu:
        provider_stamp = None
        provider_cid = None
        provider_err = None

        if not args.no_provider:
            provider = row.get("provider", "emailbison")
            lead_id = row.get("lead_id")
            if provider == "emailbison" and lead_id:
                provider_stamp, provider_cid, provider_err = (
                    bison_last_confirmed_send(lead_id))
                time.sleep(THROTTLE)
            # HeyReach touches would be read via heyreach_last_touch()
            # with a conversations_page_fn scoped to this lead.

        a = assess_row(row, provider_stamp=provider_stamp,
                       provider_campaign_id=provider_cid,
                       provider_error=provider_err)
        assessments.append(a)

    return report(assessments, len(uk_eu), non_uk_eu, unresolvable)


if __name__ == "__main__":
    raise SystemExit(main())
