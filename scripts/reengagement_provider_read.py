#!/usr/bin/env python3
"""UK/EU re-engagement age from the PROVIDER, not the cache.

    py -3 scripts/reengagement_provider_read.py --report
    py -3 scripts/reengagement_provider_read.py --walk
    py -3 scripts/reengagement_provider_read.py --walk --cap 10

READ ONLY. No write, no attach, no enrolment. Not one write verb is imported
from a provider module; every call below is a GET (EmailBison) or a confirmed
read POST (HeyReach inbox). Nothing is enrolled, created, activated or
stopped.

## WHY THIS EXISTS

`work/stage/reengagement-inventory.jsonl` carries a `last_touch` derived from
`lead.updated_at` at walk time. That value is cached: the walk writes it once
and the on-disk cache holds it until the next walk. Measured 2026-09-24,
145 of 2,081 inventory rows were staler than the provider truth, 133 by 7+
days, the worst by 111 days. Lead 133283 read 111 days untouched in the
inventory; its last confirmed send was two days earlier, from our own
campaign 491.

The UK/EU subset is next in the queue for campaigns 500/501/502. It has to be
re-derived from the provider before any enrolment.

## WHAT THE SCRIPT DOES

1. Reads `work/stage/reengagement-inventory.jsonl`.
2. Selects UK/EU rows by ISO 3166-1 alpha-2 country code. The code comes from
   the inventory row's `country_code` field when present, otherwise from the
   store record's `country_code` field via `bison_lead_id` matching. Geo is
   never guessed from a TLD or a name.
3. For each UK/EU row, reads the provider's confirmed sends:
   - EmailBison: `GET /leads/{id}/scheduled-emails`, every page, filtered to
     `status=sent` with a non-null `sent_at`.
   - HeyReach: `POST /inbox/GetConversationsV2` filtered by `leadProfileUrl`,
     every message with `sender=me` is a touch.
4. Computes per row: `inventory_age_days`, `provider_age_days`, `delta_days`,
   the campaign id of the last confirmed touch, and its timestamp.
5. Re-applies the REENGAGE lane predicate against the PROVIDER figures:
   contacted 90+ days ago, no reply ever, no unsubscribe, no bounce.
6. Reports survivors, excluded rows, and the delta distribution.

## THE REVIVE LANE STAYS OUT

A row carrying a reply or an unsubscribe is never in the REENGAGE output.
The count of those excluded is reported. `replies.is_automated` decides
whether a reply classification is automated; automated replies do not count
as human replies and do not move a row to REVIVE.

## WHAT COUNTS AS A PROVIDER READ FAILURE

A provider error (HTTP non-2xx, transport failure, partial page) for a lead
marks that row HELD. HELD rows are never defaulted to the inventory value
and never treated as stale-enough. Missing evidence is never positive
evidence.
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

from src.providers import bison, heyreach, load_env, query, request  # noqa: E402
from src import replies                                               # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STAGE = os.path.join(ROOT, "work", "stage")
INVENTORY = os.path.join(STAGE, "reengagement-inventory.jsonl")

# Staged provider data from a --walk run.
STAGED_BISON_SENDS = os.path.join(STAGE, "rpr-bison-sends.jsonl")
STAGED_HR_TOUCHES = os.path.join(STAGE, "rpr-hr-touches.jsonl")
STAGED_ROWS = os.path.join(STAGE, "rpr-rows.jsonl")

REENGAGE_AFTER_DAYS = 90
THROTTLE = 0.25

# ---------------------------------------------------------------- UK/EU ISO
#
# The UK region and every EU-27 member state, plus the EEA countries
# (Norway, Iceland, Liechtenstein) and Switzerland. This matches the GTM
# regions in src/geo.py: UK, DACH, Nordics, Benelux, CEE, Southern Europe -
# minus the European micro-states that are not in the country table and
# minus Croatia's neighbours that were never in the estate.
#
# The point is campaign eligibility, not treaty accuracy: these are the
# ISO codes the inventory's `country_code` field can hold for a lead that
# is in the UK/EU subset.
UK_EU_ISO = frozenset({
    # UK region (geo.py: UK)
    "GB", "IE",
    # DACH
    "DE", "AT", "CH",
    # Nordics
    "SE", "NO", "DK", "FI", "IS",
    # Benelux
    "NL", "BE", "LU",
    # CEE (EU members + neighbours in the estate)
    "PL", "CZ", "SK", "HU", "RO", "BG", "HR", "SI",
    "EE", "LV", "LT",
    # Southern Europe
    "ES", "PT", "IT", "GR", "MT", "CY", "FR",
})


def is_uk_eu(iso_code):
    """True when the ISO code is in the UK/EU set. None or empty is False."""
    code = str(iso_code or "").strip().upper()
    return code in UK_EU_ISO


# --------------------------------------------------------------- helpers

def _now():
    return datetime.datetime.now(datetime.timezone.utc)


def _parse(stamp):
    """An ISO timestamp into a timezone-aware datetime, or None."""
    text = str(stamp or "").strip().replace("Z", "+00:00")
    if not text:
        return None
    try:
        moment = datetime.datetime.fromisoformat(text)
    except ValueError:
        return None
    return moment if moment.tzinfo else moment.replace(
        tzinfo=datetime.timezone.utc)


def _age_days(stamp, now=None):
    """Integer days between `stamp` and `now`, or None when stamp is None."""
    if stamp is None:
        return None
    now = now or _now()
    return (now - stamp).days


def _hash_id(value):
    """SHA-256 prefix of an identifier. No raw PII in output."""
    text = str(value or "").strip()
    if not text:
        return ""
    return hashlib.sha256(text.encode()).hexdigest()[:12]


# --------------------------------------------------- inventory and store

def load_inventory(path=None):
    """Every row from the re-engagement inventory JSONL."""
    path = path or INVENTORY
    rows = []
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def load_store_country_map(queue_path=None):
    """`{bison_lead_id_str: country_code}` from the store queue.

    Reads `work/queue.jsonl` (or the path supplied). Each record has
    `contacts`, each contact may have `bison_lead_id`. The record's
    `country_code` (set by enrichment) is the value. Records without a
    `country_code` or without contacts with `bison_lead_id` contribute
    nothing.
    """
    queue_path = queue_path or os.path.join(ROOT, "work", "queue.jsonl")
    if not os.path.exists(queue_path):
        return {}
    out = {}
    with open(queue_path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except (ValueError, TypeError):
                continue
            cc = str(record.get("country_code") or "").upper()
            if not cc:
                continue
            for contact in record.get("contacts") or []:
                lid = contact.get("bison_lead_id")
                if lid:
                    out[str(int(lid))] = cc
    return out


def load_store_linkedin_map(queue_path=None):
    """`{bison_lead_id_str: linkedin_url}` from the store queue.

    The HeyReach conversation read needs a profile URL. The store's
    contact carries `linkedin` (the canonical field) or `linkedin_url`
    (the fallback). Either is accepted; `linkedin` wins.
    """
    queue_path = queue_path or os.path.join(ROOT, "work", "queue.jsonl")
    if not os.path.exists(queue_path):
        return {}
    out = {}
    with open(queue_path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except (ValueError, TypeError):
                continue
            for contact in record.get("contacts") or []:
                lid = contact.get("bison_lead_id")
                url = contact.get("linkedin") or contact.get("linkedin_url")
                if lid and url:
                    out[str(int(lid))] = url
    return out


def filter_uk_eu(rows, country_map):
    """`(uk_eu_rows, non_uk_eu_count, no_country_count)`.

    A row's country_code comes from the row itself when present, otherwise
    from the store map keyed by `lead_id` (which IS the bison_lead_id for
    EmailBison rows). A row with no country from either source is counted
    separately; it is NOT included in the UK/EU set.
    """
    uk_eu, non_uk_eu, no_country = [], 0, 0
    for row in rows:
        iso = str(row.get("country_code") or "").upper()
        if not iso:
            lid = str(row.get("lead_id") or "")
            iso = country_map.get(lid, "")
        if not iso:
            no_country += 1
            continue
        if is_uk_eu(iso):
            row = dict(row)
            row["country_code"] = iso
            uk_eu.append(row)
        else:
            non_uk_eu += 1
    return uk_eu, non_uk_eu, no_country


# ------------------------------------------------ provider reads

def bison_confirmed_sends(lead_id, throttle=THROTTLE):
    """Every confirmed send for one EmailBison lead. READ ONLY.

    `GET /leads/{id}/scheduled-emails` returns every queue row for one
    person ACROSS EVERY CAMPAIGN, including campaigns the inventory walk
    never read. This is the authoritative per-lead send history.

    Returns a list of `{campaign_id, sent_at, step}` dicts, one per
    confirmed send. A row is confirmed when `status` is `sent` AND
    `sent_at` is non-null. `scheduled`, `active`, `stopped` and `bounced`
    are NOT sends. A `sent` row with a null `sent_at` is not one either.

    Raises on provider failure. The caller marks the row HELD.
    """
    rows, total, page = [], None, 1
    while True:
        url = query(f"{bison.base()}/leads/{lead_id}/scheduled-emails",
                     {"page": page})
        status, data = request("GET", url, bison.headers())
        if not bison.ok(status):
            raise bison.ProviderError(
                f"bison lead sends {lead_id}: page {page} -> {status}")
        if not isinstance(data, dict):
            raise bison.ProviderError(
                f"bison lead sends {lead_id}: unexpected shape")
        chunk = data.get("data")
        if not isinstance(chunk, list):
            raise bison.ProviderError(
                f"bison lead sends {lead_id}: no `data` array")
        meta = data.get("meta") if isinstance(data.get("meta"), dict) else {}
        if total is None:
            total = meta.get("total")
        for row in chunk:
            if not isinstance(row, dict):
                continue
            state = str(row.get("status") or "").lower()
            sent_at = row.get("sent_at")
            if state == "sent" and sent_at:
                lead_data = row.get("lead") if isinstance(
                    row.get("lead"), dict) else {}
                rows.append({
                    "campaign_id": row.get("campaign_id"),
                    "sent_at": str(sent_at),
                    "step": row.get("sequence_step_id"),
                })
        try:
            last = int(meta.get("last_page"))
        except (TypeError, ValueError):
            break
        if page >= last:
            break
        page += 1
        time.sleep(throttle)
    if isinstance(total, int) and len(rows) > total:
        raise bison.PartialInventory(
            f"bison lead sends {lead_id}: more confirmed sends ({len(rows)}) "
            f"than meta.total ({total})")
    return rows


def heyreach_confirmed_touches(profile_url, throttle=THROTTLE):
    """Every outbound message in one person's HeyReach conversations.

    `POST /inbox/GetConversationsV2` with `leadProfileUrl` filter. Each
    conversation carries a `messages` array; each message from `me` is a
    confirmed LinkedIn touch. Returns `[{campaign_id, sent_at}]`.

    Raises on provider failure. The caller marks the row HELD.
    """
    if not profile_url:
        return []
    touches = []
    offset = 0
    while True:
        data = heyreach._read(
            "/inbox/GetConversationsV2",
            {"filters": {"leadProfileUrl": profile_url},
             "offset": offset, "limit": heyreach.MAX_PAGE})
        items = data.get("items")
        if not isinstance(items, list):
            raise heyreach.ProviderError(
                f"heyreach conversations: no items array")
        for conv in items:
            if not isinstance(conv, dict):
                continue
            campaign_ids = conv.get("campaignIds") or []
            for msg in conv.get("messages") or []:
                if not isinstance(msg, dict):
                    continue
                sender = str(msg.get("sender") or "").lower()
                if sender != "me":
                    continue
                touches.append({
                    "campaign_id": (campaign_ids[0] if campaign_ids
                                    else None),
                    "sent_at": str(msg.get("createdAt") or ""),
                })
        total = data.get("totalCount")
        offset += len(items)
        if not items or (total is not None and offset >= int(total)):
            break
        time.sleep(throttle)
    return touches


# ---------------------------------------- comparison and predicate (PURE)

def derive_last_touch(bison_sends, hr_touches):
    """`(sent_at_parsed, campaign_id, source)` from the union of both.

    Returns `(None, None, None)` when neither source has a confirmed touch.
    The most recent send across both providers wins.
    """
    best_stamp, best_cid, best_source = None, None, None
    for s in bison_sends:
        stamp = _parse(s.get("sent_at"))
        if stamp and (best_stamp is None or stamp > best_stamp):
            best_stamp, best_cid, best_source = stamp, s.get("campaign_id"), "emailbison"
    for t in hr_touches:
        stamp = _parse(t.get("sent_at"))
        if stamp and (best_stamp is None or stamp > best_stamp):
            best_stamp, best_cid, best_source = stamp, t.get("campaign_id"), "heyreach"
    return best_stamp, best_cid, best_source


def compare_row(row, bison_sends, hr_touches, now=None):
    """Per-row comparison. Pure: no I/O.

    Returns a dict with:
      - hashed_lead_id
      - country_code
      - inventory_last_touch (raw string)
      - inventory_age_days
      - provider_last_touch (ISO string or None)
      - provider_age_days (int or None)
      - delta_days (int or None)
      - last_touch_campaign_id
      - last_touch_source (emailbison / heyreach / None)
      - status: OK | HELD | READ_ERROR
    """
    now = now or _now()
    inv_stamp = _parse(row.get("last_touch"))
    inv_age = _age_days(inv_stamp, now)
    provider_stamp, provider_cid, provider_source = derive_last_touch(
        bison_sends, hr_touches)
    prov_age = _age_days(provider_stamp, now)
    delta = None
    if inv_age is not None and prov_age is not None:
        delta = abs(inv_age - prov_age)
    return {
        "hashed_lead_id": _hash_id(row.get("lead_id")),
        "country_code": str(row.get("country_code") or ""),
        "inventory_last_touch": str(row.get("last_touch") or ""),
        "inventory_age_days": inv_age,
        "provider_last_touch": (provider_stamp.isoformat()
                                if provider_stamp else None),
        "provider_age_days": prov_age,
        "delta_days": delta,
        "last_touch_campaign_id": provider_cid,
        "last_touch_source": provider_source,
    }


def reengage_predicate(row, provider_age_days, has_reply=False,
                       has_unsubscribe=False, has_bounce=False,
                       reply_is_automated=False):
    """The REENGAGE lane predicate against PROVIDER figures.

    Returns `(lane, reason)`.

    REENGAGE requires:
      - provider_age_days >= 90 (contacted 90+ days ago)
      - no reply ever (unless the reply is automated)
      - no unsubscribe
      - no bounce

    A row the provider could not answer for (provider_age_days is None)
    is HELD, never defaulted to the inventory value and never treated as
    stale-enough.

    `reply_is_automated` uses `replies.is_automated`: an automated reply
    (out-of-office, assistant redirect, ticketing ack) does NOT count as
    a human reply and does not move the row to REVIVE.
    """
    if has_unsubscribe:
        return "NEVER", "unsubscribe on record"
    if has_bounce:
        return "NEVER", "bounce on record"
    if has_reply and not reply_is_automated:
        return "REVIVE", "human reply, then silence"
    if provider_age_days is None:
        return "HELD", "provider could not confirm last touch"
    if provider_age_days <= REENGAGE_AFTER_DAYS:
        return "TOO_RECENT", (f"last confirmed send {provider_age_days}d ago "
                              f"(<= {REENGAGE_AFTER_DAYS})")
    return "REENGAGE", (f"no reply, no unsubscribe, no bounce, last "
                        f"confirmed send {provider_age_days}d ago")


# ------------------------------------------- staged data (walk + report)

def _walk_bison(uk_eu_rows, throttle=THROTTLE, emit=print):
    """Live provider read for every UK/EU EmailBison lead.

    Returns `{lead_id_str: [send_dicts]}`. A provider failure for one lead
    is recorded under the lead id as a string error message; the caller
    marks it HELD.
    """
    results = {}
    for i, row in enumerate(uk_eu_rows, 1):
        if str(row.get("provider") or "") != "emailbison":
            continue
        lid = str(row.get("lead_id") or "")
        if not lid:
            continue
        try:
            sends = bison_confirmed_sends(lid, throttle=throttle)
            results[lid] = sends
        except Exception as exc:                                  # noqa: BLE001
            results[lid] = f"READ_ERROR: {type(exc).__name__}: {exc}"
        if i % 20 == 0:
            emit(f"    {i}/{len(uk_eu_rows)} EmailBison leads read")
        time.sleep(throttle)
    return results


def _walk_heyreach(uk_eu_rows, linkedin_map, throttle=THROTTLE, emit=print):
    """Live provider read for every UK/EU lead with a LinkedIn URL.

    Returns `{lead_id_str: [touch_dicts]}`.
    """
    results = {}
    n = 0
    for row in uk_eu_rows:
        lid = str(row.get("lead_id") or "")
        url = linkedin_map.get(lid)
        if not url:
            continue
        n += 1
        try:
            touches = heyreach_confirmed_touches(url, throttle=throttle)
            results[lid] = touches
        except Exception as exc:                                  # noqa: BLE001
            results[lid] = f"READ_ERROR: {type(exc).__name__}: {exc}"
        if n % 20 == 0:
            emit(f"    {n} HeyReach leads read")
    return results


def stage_walk(uk_eu_rows, bison_data, hr_data, path=None):
    """Write staged provider data for offline --report runs."""
    path = path or STAGED_ROWS
    with open(path, "w", encoding="utf-8") as handle:
        for row in uk_eu_rows:
            handle.write(json.dumps(row) + "\n")
    bison_path = path.replace(".jsonl", "-bison.jsonl")
    with open(bison_path, "w", encoding="utf-8") as handle:
        for lid, sends in sorted(bison_data.items()):
            if isinstance(sends, list):
                for s in sends:
                    rec = dict(s)
                    rec["lead_id"] = lid
                    handle.write(json.dumps(rec) + "\n")
    hr_path = path.replace(".jsonl", "-hr.jsonl")
    with open(hr_path, "w", encoding="utf-8") as handle:
        for lid, touches in sorted(hr_data.items()):
            if isinstance(touches, list):
                for t in touches:
                    rec = dict(t)
                    rec["lead_id"] = lid
                    handle.write(json.dumps(rec) + "\n")
    return path, bison_path, hr_path


def load_staged(rows_path=None):
    """Load staged provider data from a previous --walk run.

    Returns `(rows, bison_sends, hr_touches)` where bison_sends and
    hr_touches are `{lead_id_str: [dicts]}`.
    """
    rows_path = rows_path or STAGED_ROWS
    rows = []
    if os.path.exists(rows_path):
        with open(rows_path, encoding="utf-8") as h:
            for line in h:
                line = line.strip()
                if line:
                    rows.append(json.loads(line))
    bison_sends = collections.defaultdict(list)
    bison_path = rows_path.replace(".jsonl", "-bison.jsonl")
    if os.path.exists(bison_path):
        with open(bison_path, encoding="utf-8") as h:
            for line in h:
                line = line.strip()
                if line:
                    rec = json.loads(line)
                    bison_sends[str(rec.pop("lead_id", ""))].append(rec)
    hr_touches = collections.defaultdict(list)
    hr_path = rows_path.replace(".jsonl", "-hr.jsonl")
    if os.path.exists(hr_path):
        with open(hr_path, encoding="utf-8") as h:
            for line in h:
                line = line.strip()
                if line:
                    rec = json.loads(line)
                    hr_touches[str(rec.pop("lead_id", ""))].append(rec)
    return rows, dict(bison_sends), dict(hr_touches)


# --------------------------------------------------------- the report

def run_comparison(uk_eu_rows, bison_data, hr_data,
                   reply_flags=None, now=None):
    """Compare every UK/EU row against provider data. Pure.

    `reply_flags` is an optional `{lead_id_str: {replied, unsubscribed,
    bounced, reply_classification}}` map. When absent, the row's own flags
    are used.

    Returns `(comparisons, lane_counts, excluded)`.
    """
    now = now or _now()
    comparisons = []
    lanes = collections.Counter()
    excluded = collections.Counter()
    for row in uk_eu_rows:
        lid = str(row.get("lead_id") or "")
        bison_sends = bison_data.get(lid, [])
        hr_touches = hr_data.get(lid, [])
        if isinstance(bison_sends, str) or isinstance(hr_touches, str):
            comp = compare_row(row, [], [], now=now)
            comp["status"] = "HELD"
            comp["held_reason"] = (bison_sends if isinstance(bison_sends, str)
                                   else hr_touches)
            comparisons.append(comp)
            lanes["HELD"] += 1
            continue
        comp = compare_row(row, bison_sends, hr_touches, now=now)
        flags = (reply_flags or {}).get(lid, {})
        has_reply = bool(flags.get("replied") or row.get("replied"))
        has_unsub = bool(flags.get("unsubscribed") or row.get("unsubscribed"))
        has_bounce = bool(flags.get("bounced") or row.get("bounced"))
        reply_class = str(flags.get("reply_classification") or "")
        automated = replies.is_automated(reply_class)
        lane, reason = reengage_predicate(
            row, comp["provider_age_days"],
            has_reply=has_reply, has_unsubscribe=has_unsub,
            has_bounce=has_bounce, reply_is_automated=automated)
        comp["lane"] = lane
        comp["reason"] = reason
        comp["status"] = "OK"
        comparisons.append(comp)
        lanes[lane] += 1
        if lane == "REVIVE":
            excluded["reply"] += 1
        elif lane == "NEVER":
            if has_unsub:
                excluded["unsubscribe"] += 1
            if has_bounce:
                excluded["bounce"] += 1
    return comparisons, lanes, excluded


def delta_distribution(comparisons):
    """Bucket the deltas: 0, 1-6, 7-30, 30+."""
    buckets = {"0": 0, "1-6": 0, "7-30": 0, "30+": 0, "unknown": 0}
    for c in comparisons:
        d = c.get("delta_days")
        if d is None:
            buckets["unknown"] += 1
        elif d == 0:
            buckets["0"] += 1
        elif d <= 6:
            buckets["1-6"] += 1
        elif d <= 30:
            buckets["7-30"] += 1
        else:
            buckets["30+"] += 1
    return buckets


def report(comparisons, lanes, excluded, deltas, emit=print):
    """Print the report."""
    emit("")
    emit("UK/EU RE-ENGAGEMENT PROVIDER READ")
    emit(f"  run at {_now():%Y-%m-%dT%H:%M}Z")
    emit(f"  total UK/EU rows compared: {len(comparisons)}")
    emit("")
    emit("  LANE COUNTS (provider-derived)")
    for lane in ("REENGAGE", "TOO_RECENT", "HELD", "REVIVE", "NEVER"):
        emit(f"    {lane:12s} {lanes.get(lane, 0):>6}")
    emit("")
    emit("  DELTA DISTRIBUTION (inventory vs provider age)")
    for bucket in ("0", "1-6", "7-30", "30+", "unknown"):
        emit(f"    {bucket:>8s} {deltas.get(bucket, 0):>6}")
    emit("")
    emit("  EXCLUDED FROM REENGAGE")
    for reason in ("reply", "unsubscribe", "bounce"):
        emit(f"    {reason:12s} {excluded.get(reason, 0):>6}")
    emit("")
    worst = sorted(
        [c for c in comparisons if c.get("delta_days") is not None],
        key=lambda c: c["delta_days"], reverse=True)[:10]
    if worst:
        emit("  WORST DELTAS (top 10)")
        for c in worst:
            emit(f"    {c['hashed_lead_id']}  delta={c['delta_days']}d  "
                 f"inv={c['inventory_age_days']}d  "
                 f"prov={c['provider_age_days']}d  "
                 f"campaign={c['last_touch_campaign_id']}  "
                 f"source={c['last_touch_source']}")
    emit("")
    cache_admitted = sum(1 for c in comparisons
                         if c.get("inventory_age_days") is not None
                         and c["inventory_age_days"] >= REENGAGE_AFTER_DAYS)
    provider_admitted = lanes.get("REENGAGE", 0)
    wrongly_admitted = sum(
        1 for c in comparisons
        if (c.get("inventory_age_days") is not None
            and c["inventory_age_days"] >= REENGAGE_AFTER_DAYS
            and c.get("lane") != "REENGAGE"))
    wrongly_excluded = sum(
        1 for c in comparisons
        if (c.get("inventory_age_days") is not None
            and c["inventory_age_days"] < REENGAGE_AFTER_DAYS
            and c.get("lane") == "REENGAGE"))
    emit(f"  ROWS THE CACHE WOULD HAVE WRONGLY ADMITTED: {wrongly_admitted}")
    emit(f"  ROWS THE CACHE WOULD HAVE WRONGLY EXCLUDED: {wrongly_excluded}")
    emit(f"  cache said {cache_admitted}, provider says {provider_admitted}")
    emit("")
    return comparisons


# --------------------------------------------------------------- main

def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--walk", action="store_true",
                   help="live provider read for every UK/EU lead")
    p.add_argument("--report", action="store_true",
                   help="report from staged data (no provider calls)")
    p.add_argument("--inventory", default=INVENTORY,
                   help="path to the inventory JSONL")
    p.add_argument("--queue", default=None,
                   help="path to the store queue (for country lookup)")
    p.add_argument("--cap", type=int, default=None,
                   help="limit the number of UK/EU leads to read")
    p.add_argument("--staged", default=None,
                   help="path to staged rows from a previous --walk")
    p.add_argument("--ignore-window", action="store_true")
    args = p.parse_args(argv)

    if args.report:
        rows, bison_data, hr_data = load_staged(args.staged)
        if not rows:
            print("no staged data - run --walk first")
            return 1
        comparisons, lanes, excluded = run_comparison(rows, bison_data, hr_data)
        deltas = delta_distribution(comparisons)
        report(comparisons, lanes, excluded, deltas)
        return 0

    if args.walk:
        load_env()
        ws = bison.bound_workspace()
        print(f"\nUK/EU RE-ENGAGEMENT PROVIDER READ - workspace "
              f"{ws.get('id')} ({ws.get('name')})")
        print(f"  started {_now():%Y-%m-%dT%H:%M}Z\n")
        all_rows = load_inventory(args.inventory)
        print(f"  inventory rows: {len(all_rows)}")
        country_map = load_store_country_map(args.queue)
        uk_eu, non_uk_eu, no_country = filter_uk_eu(all_rows, country_map)
        print(f"  UK/EU rows: {len(uk_eu)}")
        print(f"  non-UK/EU: {non_uk_eu}")
        print(f"  no country: {no_country}")
        if args.cap:
            uk_eu = uk_eu[:args.cap]
            print(f"  capped to {len(uk_eu)}")
        linkedin_map = load_store_linkedin_map(args.queue)
        print(f"  LinkedIn URLs in store: {len(linkedin_map)}")
        print(f"\n  Reading EmailBison sends...")
        bison_data = _walk_bison(uk_eu)
        print(f"  EmailBison leads read: {len(bison_data)}")
        print(f"\n  Reading HeyReach touches...")
        hr_data = _walk_heyreach(uk_eu, linkedin_map)
        print(f"  HeyReach leads read: {len(hr_data)}")
        paths = stage_walk(uk_eu, bison_data, hr_data)
        print(f"\n  staged to {paths[0]}")
        comparisons, lanes, excluded = run_comparison(
            uk_eu, bison_data, hr_data)
        deltas = delta_distribution(comparisons)
        report(comparisons, lanes, excluded, deltas)
        return 0

    p.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
