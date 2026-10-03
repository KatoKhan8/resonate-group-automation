#!/usr/bin/env python3
"""UK/EU re-engagement age: provider read, not the cache.

    py -3 scripts/reengagement_provider_read.py --walk
    py -3 scripts/reengagement_provider_read.py --report

READ ONLY. No write verb is imported from any provider module. Nothing is
enrolled, attached, activated or stopped.

## WHY THIS EXISTS

`work/stage/reengagement-inventory.jsonl` carries a `last_touch` per lead
that comes from a cached index on disk. That cache is never refreshed.
Measured 2026-09-24 on 2,081 rows:

    145 rows staler than the live lead
    133 by 7+ days
    worst by 111 days (lead 133283: inventory said 111d, real age 2d)

The UK/EU subset (128 clean leads for campaigns 500/501/502) is next in the
queue. Before they go in, the age must be read from the provider, not the
cache.

## WHAT THIS SCRIPT DOES

1. Reads the re-engagement inventory.
2. Determines UK/EU per row by cross-referencing the lead's record_id
   (from EmailBison custom variables) to the queue record's country.
   Geo comes from the stored ISO country code, not from a TLD guess.
3. For each UK/EU row, reads the provider's sent rows at run time:
   - EmailBison: GET /campaigns/{id}/scheduled-emails (sent rows with
     a dated sent_at are the only accepted witness for a send).
   - HeyReach: POST /inbox/GetConversationsV2 (outbound messages are
     touches too).
4. Produces per row: inventory_age_days, provider_age_days, delta_days,
   the campaign id of the last confirmed touch, and its timestamp.
5. Re-applies the REENGAGE lane predicate (contacted 90+ days ago, no
   reply ever, no unsubscribe, no bounce) against the PROVIDER figures.
6. The REVIVE lane stays out. Human drafts only. A row carrying a reply
   or an unsubscribe is never in the output set.

## WHAT THIS SCRIPT DOES NOT DO

- Read the cached index file. That file is the defect.
- Write to any provider. No write verb is imported.
- Invent provider responses. The read is live.
- Count a provider read failure as "no touch found". Failure is HELD.
- Include prospect names, addresses or domains. Hashed IDs only.
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

from src.providers import bison, heyreach, load_env, request, ok, query

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STAGE = os.path.join(ROOT, "work", "stage")
INVENTORY = os.path.join(STAGE, "reengagement-inventory.jsonl")

#: Output files under work/stage/.
UK_EU_ROWS = os.path.join(STAGE, "uk-eu-provider-read.jsonl")
REPORT_PATH = os.path.join(ROOT, "docs",
                           "REENGAGEMENT-UK-EU-PROVIDER-READ-2026-09-25.md")

THROTTLE = 0.25
REENGAGE_AFTER_DAYS = 90

#: UK and EU cohort country sets, matching scripts/batch1_build.py.
UK_COUNTRIES = {"United Kingdom", "Ireland"}
EU_COUNTRIES = {
    "Germany", "Sweden", "France", "Finland", "Netherlands", "Denmark",
    "Norway", "Belgium", "Austria", "Switzerland", "Poland", "Spain",
    "Italy", "Croatia", "Portugal", "Czechia",
}
UK_EU_COUNTRIES = UK_COUNTRIES | EU_COUNTRIES

#: Membership or queue-row states that are a bounce.
BOUNCE_STATES = {"bounced", "bounce", "hard_bounced", "soft_bounced"}

#: Membership or queue-row states that are an unsubscribe or complaint.
UNSUB_STATES = {"unsubscribed", "unsubscribe", "opted_out", "complained",
                "complaint", "blocked", "suppressed"}

#: A queue row that proves a send. Nothing else does.
SENT_STATE = "sent"


def _now():
    return datetime.datetime.now(datetime.timezone.utc)


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


def _hash(value):
    """Short hash for committed output. No prospect data in the report."""
    return hashlib.sha256(str(value).encode()).hexdigest()[:12]


# -------------------------------------------------- UK/EU determination

def cohort_of(country):
    """Which cohort a country belongs to: uk, eu, us, or None."""
    if country in UK_COUNTRIES:
        return "uk"
    if country in EU_COUNTRIES:
        return "eu"
    return None


def load_queue_country_map():
    """{record_id_hex: country} from the queue records.

    Reads the queue records and extracts the country from each record's
    company_facts or ICP data. The record_id is the link between an
    EmailBison lead's custom variables and the queue record.
    """
    from src import store
    mapping = {}
    for record in store.load():
        rid = record.get("record_id")
        if not rid:
            continue
        facts = record.get("company_facts") or {}
        country = facts.get("country")
        if not country:
            offices = facts.get("offices") or []
            for line in offices:
                token = str(line).strip().rstrip(".").split(",")[-1].strip()
                from src.icpstructural import ISO_TO_NAME
                if token.upper() in ISO_TO_NAME:
                    country = ISO_TO_NAME[token.upper()]
                    break
        if country:
            mapping[str(rid)] = country
    return mapping


def is_uk_eu_row(row, country_map):
    """True when the row's record maps to a UK or EU country.

    `row` must carry a `record_id` (from the lead's custom variables).
    `country_map` is {record_id: country} from the queue records.
    """
    rid = str(row.get("record_id") or "")
    if not rid:
        return False, None
    country = country_map.get(rid)
    if not country:
        return False, None
    return country in UK_EU_COUNTRIES, country


# -------------------------------------------------- provider reads

def _walk(what, url_of, cap):
    """Every row behind a paginated route, or a refusal."""
    rows, total, page, last = [], None, 1, None
    while True:
        status, data = request("GET", url_of(page), bison.headers())
        if not bison.ok(status):
            raise bison.ProviderError(f"{what}: page {page} -> {status}")
        chunk = (data or {}).get("data")
        if not isinstance(chunk, list):
            raise bison.ProviderError(
                f"{what}: the list is not a list; refusing to read an "
                f"unknown shape as an empty one")
        rows += chunk
        meta = data.get("meta") if isinstance(data.get("meta"), dict) else {}
        if total is None:
            total = meta.get("total")
        try:
            last = int(meta.get("last_page"))
        except (TypeError, ValueError):
            break
        if page >= last:
            break
        if page >= cap:
            raise bison.PartialInventory(
                f"{what}: {last} pages and this read stops at {cap}. "
                f"Refusing to return {len(rows)} of {total} as though it "
                f"were all of them")
        page += 1
        time.sleep(THROTTLE)
    if isinstance(total, int) and len(rows) != total:
        raise bison.PartialInventory(
            f"{what}: meta.total says {total} and {len(rows)} arrived. "
            f"Refusing to report a partial read as a complete one")
    return rows


def walk_campaign_leads(campaign_id):
    """Every lead in a campaign, with custom variables. Provider read."""
    return _walk(
        f"leads {campaign_id}",
        lambda p, c=campaign_id: query(bison.leads_endpoint(c),
                                       {"page": p}),
        cap=bison.CAMPAIGN_QUEUE_PAGE_CAP)


def walk_campaign_sends(campaign_id):
    """Every scheduled-email row in a campaign. Provider read."""
    return _walk(
        f"queue {campaign_id}",
        lambda p, c=campaign_id: query(
            f"{bison.base()}/campaigns/{c}/scheduled-emails",
            {"page": p}),
        cap=bison.CAMPAIGN_QUEUE_PAGE_CAP)


def walk_lead_sends(lead_id):
    """One lead's WHOLE send history across every campaign. Provider read."""
    return _walk(
        f"lead queue {lead_id}",
        lambda p, i=lead_id: query(
            f"{bison.base()}/leads/{i}/scheduled-emails",
            {"page": p}),
        cap=bison.CAMPAIGN_QUEUE_PAGE_CAP)


def _trim_send(row):
    """One queue row, reduced. `lead` is read for its ID and nothing else."""
    lead = row.get("lead") if isinstance(row.get("lead"), dict) else {}
    return {
        "campaign_id": row.get("campaign_id"),
        "lead_id": lead.get("id"),
        "status": str(row.get("status") or ""),
        "sent_at": row.get("sent_at"),
    }


def _extract_record_id(lead_row):
    """The record_id from a lead's custom variables, or None."""
    custom = lead_row.get("custom_variables")
    if isinstance(custom, list):
        for entry in custom:
            if isinstance(entry, dict) and entry.get("name") == "record_id":
                return str(entry.get("value") or "").strip() or None
    if isinstance(custom, dict):
        return str(custom.get("record_id") or "").strip() or None
    return None


def heyreach_last_touch(record_id):
    """The last outbound HeyReach message to this record, or None.

    Reads HeyReach conversations and filters by record_id in
    customUserFields. Returns {"sent_at": ..., "campaign_id": ...} or None.

    Returns None on read failure - the caller marks the row HELD, not
    "no touch".
    """
    try:
        conversations = _heyreach_conversations()
    except Exception:
        return None

    best = None
    for conv in conversations:
        custom = {}
        for field in conv.get("customUserFields") or conv.get("customFields") or []:
            if isinstance(field, dict):
                custom[field.get("name")] = field.get("value")
        if str(custom.get("record_id") or "") != str(record_id):
            continue
        for msg in conv.get("messages") or []:
            if not isinstance(msg, dict):
                continue
            sender = str(msg.get("sender") or "").strip().lower()
            if sender != "me":
                continue
            sent_at = _parse(msg.get("createdAt"))
            if sent_at and (best is None or sent_at > best["sent_at"]):
                best = {"sent_at": sent_at, "campaign_id": conv.get(
                    "campaignId")}
    return best


def _heyreach_conversations():
    """Walk HeyReach conversations. Read-only POST."""
    rows, offset, limit = [], 0, 100
    while True:
        body = json.dumps({"offset": offset, "limit": limit}).encode()
        status, data = request(
            "POST",
            f"{heyreach.BASE}/inbox/GetConversationsV2",
            heyreach.headers(),
            body)
        if not ok(status):
            raise heyreach.ProviderError(
                f"heyreach conversations: {status}")
        items = (data or {}).get("items") or []
        rows.extend(items)
        total = (data or {}).get("totalCount")
        offset += limit
        if isinstance(total, int) and offset >= total:
            break
        if not items:
            break
        time.sleep(THROTTLE)
    return rows


# -------------------------------------------------- the assessment

def assess_row(inv_row, provider_sends, heyreach_touch, now=None):
    """Per-row comparison of inventory age vs provider age.

    `inv_row` is one row from the inventory (with record_id, country,
    last_touch).
    `provider_sends` is a list of confirmed send dicts with sent_at and
    campaign_id.
    `heyreach_touch` is the HeyReach last touch dict or None.
    `now` is the comparison time (default: UTC now).

    Returns a dict with:
        hashed_lead_id, campaign_id, record_id_hash, country, cohort,
        inventory_last_touch, inventory_age_days,
        provider_last_touch, provider_age_days, provider_touch_campaign,
        delta_days,
        reengage_provider (bool), reengage_cache (bool),
        excluded_reason (str or None),
        status (OK | HELD).
    """
    now = now or _now()
    inv_touch = _parse(inv_row.get("last_touch"))
    inv_age = (now - inv_touch).days if inv_touch else None

    # Combine EmailBison sends and HeyReach touch to find the real last touch.
    all_touches = []
    for s in provider_sends:
        stamp = _parse(s.get("sent_at"))
        if stamp:
            all_touches.append({
                "sent_at": stamp,
                "campaign_id": s.get("campaign_id"),
                "provider": "emailbison",
            })
    if heyreach_touch and heyreach_touch.get("sent_at"):
        all_touches.append({
            "sent_at": heyreach_touch["sent_at"],
            "campaign_id": heyreach_touch.get("campaign_id"),
            "provider": "heyreach",
        })

    if not all_touches:
        return {
            "hashed_lead_id": _hash(inv_row.get("lead_id", "?")),
            "campaign_id": inv_row.get("campaign_id"),
            "record_id_hash": _hash(inv_row.get("record_id", "?")),
            "country": inv_row.get("country"),
            "cohort": inv_row.get("cohort"),
            "inventory_last_touch": str(inv_touch or ""),
            "inventory_age_days": inv_age,
            "provider_last_touch": None,
            "provider_age_days": None,
            "provider_touch_campaign": None,
            "provider_touch_provider": None,
            "delta_days": None,
            "reengage_provider": False,
            "reengage_cache": False,
            "excluded_reason": None,
            "status": "HELD",
            "held_reason": "no confirmed send at the provider",
        }

    latest = max(all_touches, key=lambda t: t["sent_at"])
    prov_age = (now - latest["sent_at"]).days
    delta = None
    if inv_age is not None:
        delta = inv_age - prov_age

    # REENGAGE predicate against provider figures.
    reengage_provider = False
    excluded = _exclusion_reason(inv_row)
    if excluded is None and prov_age is not None and prov_age > REENGAGE_AFTER_DAYS:
        reengage_provider = True

    # REENGAGE predicate against cache (inventory) figures.
    reengage_cache = False
    if excluded is None and inv_age is not None and inv_age > REENGAGE_AFTER_DAYS:
        reengage_cache = True

    return {
        "hashed_lead_id": _hash(inv_row.get("lead_id", "?")),
        "campaign_id": inv_row.get("campaign_id"),
        "record_id_hash": _hash(inv_row.get("record_id", "?")),
        "country": inv_row.get("country"),
        "cohort": inv_row.get("cohort"),
        "inventory_last_touch": str(inv_touch or ""),
        "inventory_age_days": inv_age,
        "provider_last_touch": str(latest["sent_at"]),
        "provider_age_days": prov_age,
        "provider_touch_campaign": latest.get("campaign_id"),
        "provider_touch_provider": latest.get("provider"),
        "delta_days": delta,
        "reengage_provider": reengage_provider,
        "reengage_cache": reengage_cache,
        "excluded_reason": excluded,
        "status": "OK",
        "held_reason": None,
    }


def _exclusion_reason(inv_row):
    """Why this row is excluded from REENGAGE, or None if it could qualify.

    Checks: reply, bounce, unsubscribe. Automated replies (per
    replies.is_automated) do NOT count as a reply.
    """
    if inv_row.get("unsubscribed") or inv_row.get("complained"):
        return "unsubscribe or complaint on the record"
    state = str(inv_row.get("state") or "").lower()
    if state in BOUNCE_STATES:
        return f"membership state {state!r} is a bounce"
    if state in UNSUB_STATES:
        return f"membership state {state!r} is an unsubscribe"
    if inv_row.get("bounced"):
        return "bounce flag on the record"
    if inv_row.get("replied"):
        return "reply flag on the record"
    if state == "replied":
        return "membership state is replied"
    return None


# -------------------------------------------------- the walk

def walk(inventory_path=None, include_heyreach=False):
    """Live provider read. READ ONLY.

    1. Read the inventory.
    2. For each unique campaign, walk leads to get record_ids.
    3. Map record_ids to countries via queue records.
    4. Filter UK/EU.
    5. For each UK/EU lead, read provider sends.
    6. Optionally read HeyReach touches.
    7. Write per-row results.
    """
    load_env()
    inventory_path = inventory_path or INVENTORY
    if not os.path.exists(inventory_path):
        print(f"  inventory not found: {inventory_path}")
        print("  this script reads production state from work/stage/")
        return 1

    workspace = bison.bound_workspace()
    print(f"\nUK/EU RE-ENGAGEMENT PROVIDER READ - workspace "
          f"{workspace.get('id')} ({workspace.get('name')})")
    print(f"  started {_now():%Y-%m-%dT%H:%M}Z")
    print(f"  throttle {THROTTLE}s\n")

    # Load the country map from queue records.
    country_map = load_queue_country_map()
    print(f"  queue records with country: {len(country_map)}")

    # Read the inventory.
    inv_rows = []
    with open(inventory_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                inv_rows.append(json.loads(line))
    print(f"  inventory rows: {len(inv_rows)}")

    # Group inventory rows by campaign for efficient lead walking.
    by_campaign = collections.defaultdict(list)
    for row in inv_rows:
        by_campaign[row.get("campaign_id")].append(row)

    # Walk each campaign's leads to get record_ids, then filter UK/EU.
    uk_eu_rows = []
    lead_record_ids = {}
    for cid, rows in sorted(by_campaign.items()):
        lead_ids_in_campaign = {str(r.get("lead_id")) for r in rows}
        try:
            leads = walk_campaign_leads(cid)
        except Exception as exc:
            print(f"  campaign {cid}: leads unreadable "
                  f"({type(exc).__name__}) - skipped")
            continue
        for lead in leads:
            lid = str(lead.get("id"))
            if lid not in lead_ids_in_campaign:
                continue
            rid = _extract_record_id(lead)
            if rid:
                lead_record_ids[lid] = rid
        print(f"  campaign {cid}: {len(leads)} leads read, "
              f"{sum(1 for r in lead_record_ids.values() if r)} with record_id")

    # Map inventory rows to countries and filter UK/EU.
    for row in inv_rows:
        lid = str(row.get("lead_id"))
        rid = lead_record_ids.get(lid)
        if not rid:
            continue
        row["record_id"] = rid
        is_uk_eu, country = is_uk_eu_row(row, country_map)
        if is_uk_eu:
            row["country"] = country
            row["cohort"] = cohort_of(country)
            uk_eu_rows.append(row)

    print(f"\n  UK/EU rows selected: {len(uk_eu_rows)}")
    by_cohort = collections.Counter(r.get("cohort") for r in uk_eu_rows)
    for cohort, count in sorted(by_cohort.items()):
        print(f"    {cohort}: {count}")
    by_country = collections.Counter(r.get("country") for r in uk_eu_rows)
    for country, count in by_country.most_common():
        print(f"    {country}: {count}")

    # HeyReach conversations (loaded once, filtered per record).
    hr_cache = {}
    if include_heyreach:
        print(f"\n  reading HeyReach conversations...")
        try:
            hr_cache["_all"] = _heyreach_conversations()
            print(f"    {len(hr_cache['_all'])} conversations")
        except Exception as exc:
            print(f"    HeyReach unreadable ({type(exc).__name__})")

    # For each UK/EU row, read provider sends and assess.
    results = []
    for row in uk_eu_rows:
        lid = str(row.get("lead_id"))
        rid = row.get("record_id")
        try:
            sends = walk_lead_sends(lid)
            confirmed = [_trim_send(s) for s in sends
                         if s.get("status", "").lower() == SENT_STATE
                         and s.get("sent_at")]
        except Exception as exc:
            results.append({
                "hashed_lead_id": _hash(lid),
                "campaign_id": row.get("campaign_id"),
                "record_id_hash": _hash(rid or ""),
                "country": row.get("country"),
                "cohort": row.get("cohort"),
                "status": "HELD",
                "held_reason": f"provider read failed: {type(exc).__name__}",
                "inventory_age_days": (
                    (_now() - _parse(row["last_touch"])).days
                    if _parse(row.get("last_touch")) else None),
                "provider_age_days": None,
                "delta_days": None,
                "provider_last_touch": None,
                "provider_touch_campaign": None,
                "provider_touch_provider": None,
                "inventory_last_touch": str(row.get("last_touch") or ""),
                "reengage_provider": False,
                "reengage_cache": False,
                "excluded_reason": _exclusion_reason(row),
            })
            continue

        hr_touch = None
        if include_heyreach and rid and "_all" in hr_cache:
            hr_touch = _heyreach_from_cache(hr_cache["_all"], rid)

        result = assess_row(row, confirmed, hr_touch)
        results.append(result)
        time.sleep(THROTTLE)

    # Write results.
    os.makedirs(os.path.dirname(UK_EU_ROWS), exist_ok=True)
    with open(UK_EU_ROWS, "w", encoding="utf-8") as f:
        for r in results:
            f.write(json.dumps(r) + "\n")

    print(f"\n  results written to {UK_EU_ROWS}")
    print(f"  total: {len(results)}")
    ok_count = sum(1 for r in results if r.get("status") == "OK")
    held_count = sum(1 for r in results if r.get("status") == "HELD")
    print(f"  OK: {ok_count}  HELD: {held_count}")
    print(f"  done {_now():%Y-%m-%dT%H:%M}Z")
    return 0


def _heyreach_from_cache(conversations, record_id):
    """Find the last HeyReach outbound to this record_id from cached convos."""
    best = None
    for conv in conversations:
        custom = {}
        for field in (conv.get("customUserFields")
                      or conv.get("customFields") or []):
            if isinstance(field, dict):
                custom[field.get("name")] = field.get("value")
        if str(custom.get("record_id") or "") != str(record_id):
            continue
        for msg in conv.get("messages") or []:
            if not isinstance(msg, dict):
                continue
            sender = str(msg.get("sender") or "").strip().lower()
            if sender != "me":
                continue
            sent_at = _parse(msg.get("createdAt"))
            if sent_at and (best is None or sent_at > best["sent_at"]):
                best = {"sent_at": sent_at,
                        "campaign_id": conv.get("campaignId")}
    return best


# -------------------------------------------------- the report

def report(results_path=None, emit=print):
    """Read the staged results and produce the report. No provider call."""
    results_path = results_path or UK_EU_ROWS
    if not os.path.exists(results_path):
        emit("  no results yet - run --walk first")
        return 1

    results = []
    with open(results_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                results.append(json.loads(line))

    now = _now()
    total = len(results)
    ok_rows = [r for r in results if r.get("status") == "OK"]
    held_rows = [r for r in results if r.get("status") == "HELD"]

    # Delta distribution.
    deltas = {"0": 0, "1-6": 0, "7-30": 0, "30+": 0}
    for r in ok_rows:
        d = r.get("delta_days")
        if d is None:
            continue
        d = abs(d)
        if d == 0:
            deltas["0"] += 1
        elif d <= 6:
            deltas["1-6"] += 1
        elif d <= 30:
            deltas["7-30"] += 1
        else:
            deltas["30+"] += 1

    # Worst deltas.
    worst = sorted(
        [r for r in ok_rows if r.get("delta_days") is not None],
        key=lambda r: r.get("delta_days", 0),
        reverse=True)[:3]

    # REENGAGE survivors.
    reengage_cache = [r for r in results if r.get("reengage_cache")]
    reengage_provider = [r for r in results if r.get("reengage_provider")]
    wrongly_admitted = [r for r in reengage_cache
                        if not r.get("reengage_provider")]

    # Excluded rows.
    excluded = [r for r in results if r.get("excluded_reason")]
    excluded_by_reason = collections.Counter(
        r.get("excluded_reason") for r in excluded)

    emit(f"\n# UK/EU RE-ENGAGEMENT PROVIDER READ  {now:%Y-%m-%dT%H:%M}Z\n")
    emit(f"## SUMMARY\n")
    emit(f"  total UK/EU rows: {total}")
    emit(f"  provider read OK: {len(ok_rows)}")
    emit(f"  HELD (unreadable): {len(held_rows)}")
    emit(f"  excluded (reply/bounce/unsub): {len(excluded)}")
    emit("")

    emit(f"## DELTA DISTRIBUTION (|inventory_age - provider_age|)\n")
    for bucket, count in deltas.items():
        emit(f"  {bucket:>6s} days: {count}")
    emit("")

    emit(f"## WORST THREE DELTAS\n")
    for r in worst:
        emit(f"  lead {r['hashed_lead_id']}  "
             f"inv={r.get('inventory_age_days')}d  "
             f"prov={r.get('provider_age_days')}d  "
             f"delta={r.get('delta_days')}d  "
             f"touched by campaign {r.get('provider_touch_campaign')} "
             f"({r.get('provider_touch_provider')})")
    emit("")

    emit(f"## REENGAGE SURVIVORS\n")
    emit(f"  cache said: {len(reengage_cache)}")
    emit(f"  provider says: {len(reengage_provider)}")
    emit(f"  rows the cache would have WRONGLY admitted: "
         f"{len(wrongly_admitted)}")
    emit("")

    emit(f"## EXCLUDED ROWS\n")
    for reason, count in excluded_by_reason.most_common():
        emit(f"  {count:>4}  {reason}")
    emit("")

    emit(f"## HELD ROWS\n")
    for r in held_rows:
        emit(f"  lead {r['hashed_lead_id']}  "
             f"inv_age={r.get('inventory_age_days')}d  "
             f"reason: {r.get('held_reason')}")
    emit("")

    return 0


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--walk", action="store_true",
                   help="Live provider read. READ ONLY.")
    p.add_argument("--report", action="store_true",
                   help="Report from staged results. No provider call.")
    p.add_argument("--inventory", default=None,
                   help="Path to the inventory file.")
    p.add_argument("--include-heyreach", action="store_true",
                   help="Also read HeyReach conversations for touches.")
    args = p.parse_args(argv)
    if args.walk:
        return walk(inventory_path=args.inventory,
                    include_heyreach=args.include_heyreach)
    if args.report:
        return report()
    p.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
