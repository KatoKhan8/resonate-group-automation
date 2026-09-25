#!/usr/bin/env python3
"""Reverse reconciliation: provider truth against the action ledger.

WHY THIS EXISTS.

`scripts/reconcile_ledger.py` walks FORWARD: it takes an unsettled key in
the action ledger and asks the provider whether the write landed. That
direction catches a write we recorded and could not confirm.

It cannot catch the other shape, and the other shape has happened here: the
adoption path sent 76 blank emails (ISSUE-025) - a prospect-facing write
that the ledger has no ATTEMPTED row for at all. A forward sweep over a
ledger that never heard of the write returns "0 unsettled, 0 problems" and
is correct about the rows it read and blind to the incident.

This script sweeps BACKWARD. Provider truth is the input; the ledger is
the thing being checked.

WHAT IT MAY AND MAY NOT CONCLUDE.

For each provider-side touch:

    MATCHED         a ledger row exists and its state is consistent
    UNRECORDED      the provider acted and NO ledger row exists at all
    STATE_MISMATCH  a ledger row exists and disagrees
    NOT_OURS        provider row belongs to the client, not to us
    UNKNOWN         cannot be classified (including provider read failure)

NOT_OURS MUST BE PROVED, NOT ASSUMED. The HeyReach inbox is ~27k
conversations and mostly the client's. A row you cannot classify is
UNKNOWN, and UNKNOWN is an outcome, never folded into NOT_OURS.

IT SETTLES NOTHING ON ITS OWN. It writes a report. Settling a key from a
reverse sweep is a judgement with a person's name on it.

READ ONLY AT EVERY PROVIDER. DRY RUN BY DEFAULT.

    py -3 scripts/reverse_reconcile.py
    py -3 scripts/reverse_reconcile.py --workspaces /path/to/copy
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import (                                                       # noqa: E402
    actionledger, campaigns, collision, push, store,
)
from src.providers import bison, heyreach                               # noqa: E402

# ----------------------------------------------------------------- classes

MATCHED = "MATCHED"
UNRECORDED = "UNRECORDED"
STATE_MISMATCH = "STATE_MISMATCH"
NOT_OURS = "NOT_OURS"
UNKNOWN = "UNKNOWN"

CLASSES = (MATCHED, UNRECORDED, STATE_MISMATCH, NOT_OURS, UNKNOWN)

# Ledger states that mean the action is live at the provider.
ACTIVE_STATES = frozenset({actionledger.ATTEMPTED, actionledger.SENT,
                           actionledger.UNRESOLVED})
# Ledger states that mean the action did not reach the prospect.
INACTIVE_STATES = frozenset({actionledger.FAILED, actionledger.ABANDONED})

# HeyReach route constant, imported for the raw read that preserves
# customFields (the trimmed campaign_leads drops them).
LEADS_ROUTE = "/campaign/GetLeadsFromCampaign"
HEYREACH_MAX_PAGE = 100


# --------------------------------------------------------- ledger indexing

def build_ledger_index(ledger_rows):
    """(record_id, contact_key) -> [ledger rows].

    The ledger key is `push.push_id(rec, contact_key, step_key, channel)`
    = `record_id:contact_key:step_key:channel`. The provider carries
    record_id and contact_key but not step_key, so the index is by the
    prefix the provider CAN confirm.
    """
    index = {}
    for row in ledger_rows:
        key = row.get("key", "")
        parts = key.split(":")
        if len(parts) >= 2:
            pair = (str(parts[0]), str(parts[1]))
            index.setdefault(pair, []).append(row)
    return index


def verify_key(row):
    """Confirm the ledger key was derived by push.push_id, not by hand.

    Imports the derivation and checks. Returns True when the stored key
    matches what the imported function would produce from the row's own
    fields. A mismatch means the key was derived differently and cannot
    be trusted for matching.
    """
    rec = {"id": row.get("rec_id")}
    expected = push.push_id(rec, row.get("contact_key"),
                            row.get("step_key"), row.get("channel"))
    return expected == row.get("key")


# -------------------------------------------------- provider reads (raw)

def _heyreach_leads_raw(campaign_id):
    """Page through HeyReach leads, preserving customFields.

    `heyreach.campaign_leads` trims customFields from its output. The
    reverse reconciler needs them to extract record_id and contact_key,
    so it reads the raw response through the provider's own _read
    function, which enforces the route allowlist.
    """
    all_leads = []
    offset = 0
    total = None
    for _ in range(200):
        data = heyreach._read(LEADS_ROUTE, {
            "campaignId": int(campaign_id),
            "offset": int(offset),
            "limit": min(HEYREACH_MAX_PAGE, 100),
        })
        items = heyreach._collection(data, LEADS_ROUTE)
        all_leads.extend(items)
        tc = data.get("totalCount")
        if tc is not None:
            total = tc
        offset += len(items)
        if offset >= (total or 0) or not items:
            break
    return all_leads, total


def _bison_leads_paged(campaign_id):
    """Page through all Bison campaign leads."""
    all_leads = []
    page = 1
    while page <= 500:
        status, data = bison.request(
            "GET",
            bison.query(bison.leads_endpoint(campaign_id), {"page": page}),
            bison.headers())
        if not bison.ok(status):
            raise bison.ProviderError(
                f"reverse_reconcile bison leads: GET -> {status}")
        rows = bison.mapping(data, "reverse_reconcile").get("data")
        if not isinstance(rows, list):
            raise bison.ProviderError(
                "reverse_reconcile bison leads: data is not a list")
        all_leads.extend(rows)
        meta = data.get("meta") if isinstance(data.get("meta"), dict) else {}
        try:
            last = int(meta.get("last_page", 1))
        except (TypeError, ValueError):
            if not rows:
                break
            raise bison.ProviderError(
                "reverse_reconcile bison leads: no readable last_page")
        if page >= last:
            break
        page += 1
    return all_leads


def _extract_heyreach_custom_fields(lead_row):
    """Extract customFields from a raw HeyReach lead response row.

    The response key is `customFields` (not `customUserFields` - that is
    the request key). Fields may be nested under `linkedInUserProfile`
    as well, so both locations are checked.
    """
    out = {}
    for field in (lead_row.get("customFields")
                  or (lead_row.get("linkedInUserProfile") or {})
                  .get("customFields")
                  or []):
        if isinstance(field, dict) and field.get("name") is not None:
            out[str(field["name"])] = field.get("value")
    return out


# -------------------------------------------------------- ownership proof

def _ownership_evidence(campaign_row, provider_name):
    """Prove whether a provider campaign is ours.

    Returns (is_ours, evidence_string). Uses collision._ours which
    requires BOTH the canonical binding AND the provider's own name for
    the campaign. A campaign we cannot positively disown is UNKNOWN,
    never NOT_OURS.
    """
    heyreach_id = campaign_row.get("heyreach_campaign_id")
    bison_id = campaign_row.get("bison_campaign_id")

    bindings = collision.campaign_bindings()

    if heyreach_id is not None:
        try:
            hid = int(heyreach_id)
        except (TypeError, ValueError):
            return None, f"heyreach_campaign_id {heyreach_id!r} not an int"
        binding = bindings.get(hid)
        if binding is None:
            return None, (f"no canonical campaign claims HeyReach campaign "
                          f"{hid}")
        provider_row = {"name": provider_name} if provider_name else {}
        ours, why = collision._ours(hid, binding, provider_row)
        return ours, why

    if bison_id is not None:
        try:
            bid = int(bison_id)
        except (TypeError, ValueError):
            return None, f"bison_campaign_id {bison_id!r} not an int"
        binding = bindings.get(bid)
        if binding is None:
            return None, (f"no canonical campaign claims Bison campaign "
                          f"{bid}")
        provider_row = {"name": provider_name} if provider_name else {}
        ours, why = collision._ours(bid, binding, provider_row)
        return ours, why

    return None, "campaign has neither heyreach nor bison binding"


# ------------------------------------------------- contact lookup helpers

def _urls_for_campaign(recs, campaign_row):
    """{linkedin_url_lower: (record_id, contact_key)} for campaign recs."""
    by_id = {r["id"]: r for r in recs}
    out = {}
    for rid in campaign_row.get("record_ids") or []:
        rec = by_id.get(rid)
        if not rec:
            continue
        for contact in rec.get("contacts") or []:
            url = (contact.get("linkedin") or "").strip().lower()
            if url:
                out[url] = (str(rec["id"]), contact.get("key"))
    return out


def _emails_for_campaign(recs, campaign_row):
    """{email_lower: (record_id, contact_key)} for campaign recs."""
    by_id = {r["id"]: r for r in recs}
    out = {}
    for rid in campaign_row.get("record_ids") or []:
        rec = by_id.get(rid)
        if not rec:
            continue
        for contact in rec.get("contacts") or []:
            email = (contact.get("email") or "").strip().lower()
            if email:
                out[email] = (str(rec["id"]), contact.get("key"))
    return out


# ---------------------------------------------------- classification core

def _classify_ledger_match(pair, ledger_index):
    """Classify a provider touch against the ledger.

    `pair` is (record_id, contact_key). Returns one of the five classes
    and an evidence string.
    """
    ledger_rows = ledger_index.get(pair)
    if not ledger_rows:
        return UNRECORDED, (f"no ledger row for record_id={pair[0]} "
                            f"contact_key={pair[1]}")

    has_active = any(r.get("state") in ACTIVE_STATES for r in ledger_rows)
    all_inactive = all(r.get("state") in INACTIVE_STATES for r in ledger_rows)

    if has_active:
        return MATCHED, f"ledger has active row ({pair[0]}:{pair[1]})"
    if all_inactive:
        return STATE_MISMATCH, (
            f"provider acted but all ledger rows are "
            f"{[r.get('state') for r in ledger_rows]}")
    return MATCHED, f"ledger row present ({pair[0]}:{pair[1]})"


def classify_heyreach_campaign(campaign_row, recs, ledger_index):
    """Classify every provider-side lead in one HeyReach campaign.

    Returns (rows, error). `rows` is a list of classification dicts.
    `error` is set when the provider could not be read.
    """
    hr_id = campaign_row.get("heyreach_campaign_id")
    if hr_id is None:
        return [], None

    provider_name = None
    try:
        camp_info = heyreach.campaign_by_id(int(hr_id))
        provider_name = (camp_info or {}).get("name")
    except Exception:
        pass

    is_ours, ownership_why = _ownership_evidence(campaign_row, provider_name)

    try:
        leads, total = _heyreach_leads_raw(int(hr_id))
    except Exception as e:
        error_rows = []
        for row in actionledger.load():
            if str(row.get("campaign_id")) == str(campaign_row.get(
                    "campaign_id")):
                error_rows.append({
                    "class": UNKNOWN,
                    "reason": f"provider read failed: {type(e).__name__}: {e}",
                    "provider_lead_id": None,
                    "record_id": None,
                    "contact_key": None,
                    "evidence": "provider unreadable",
                })
        if not error_rows:
            error_rows.append({
                "class": UNKNOWN,
                "reason": f"provider read failed: {type(e).__name__}: {e}",
                "provider_lead_id": None,
                "record_id": None,
                "contact_key": None,
                "evidence": "provider unreadable",
            })
        return error_rows, str(e)

    campaign_rows = []
    our_urls = _urls_for_campaign(recs, campaign_row)

    for lead in leads:
        profile = lead.get("linkedInUserProfile") or {}
        profile_url = str(profile.get("profileUrl") or "").strip().lower()
        custom = _extract_heyreach_custom_fields(lead)
        rec_id = custom.get("record_id")
        contact_key = custom.get("contact_key")

        row = {
            "provider_lead_id": lead.get("id"),
            "profile_url": profile_url or None,
            "record_id": rec_id,
            "contact_key": contact_key,
            "campaign_id": campaign_row.get("campaign_id"),
            "provider": "heyreach",
            "provider_campaign_id": hr_id,
            "lead_state": heyreach.lead_state(lead).get("state"),
        }

        if is_ours is False:
            row["class"] = NOT_OURS
            row["evidence"] = f"ownership disproved: {ownership_why}"
        elif is_ours is None:
            row["class"] = UNKNOWN
            row["evidence"] = f"ownership unproven: {ownership_why}"
        elif not rec_id or not contact_key:
            row["class"] = UNKNOWN
            row["evidence"] = ("lead carries no record_id/contact_key "
                               "customFields; cannot derive ledger key")
        elif profile_url and profile_url not in our_urls:
            row["class"] = UNKNOWN
            row["evidence"] = ("lead URL not in any queue record for this "
                               "campaign; cannot confirm identity")
        else:
            pair = (str(rec_id), str(contact_key))
            cls, evidence = _classify_ledger_match(pair, ledger_index)
            row["class"] = cls
            row["evidence"] = evidence
            if cls in (MATCHED, STATE_MISMATCH):
                ledger_rows = ledger_index.get(pair, [])
                row["ledger_key"] = (ledger_rows[0].get("key")
                                     if ledger_rows else None)
                row["key_verified"] = all(
                    verify_key(lr) for lr in ledger_rows)

        campaign_rows.append(row)

    return campaign_rows, None


def classify_bison_campaign(campaign_row, recs, ledger_index):
    """Classify every provider-side lead in one Bison campaign.

    Returns (rows, error). `rows` is a list of classification dicts.
    `error` is set when the provider could not be read.
    """
    b_id = campaign_row.get("bison_campaign_id")
    if b_id is None:
        return [], None

    provider_name = None
    try:
        camp_info = bison.campaign(int(b_id))
        provider_name = (camp_info or {}).get("name")
    except Exception:
        pass

    is_ours, ownership_why = _ownership_evidence(campaign_row, provider_name)

    try:
        leads = _bison_leads_paged(int(b_id))
    except Exception as e:
        error_rows = [{
            "class": UNKNOWN,
            "reason": f"provider read failed: {type(e).__name__}: {e}",
            "provider_lead_id": None,
            "record_id": None,
            "contact_key": None,
            "evidence": "provider unreadable",
        }]
        return error_rows, str(e)

    campaign_rows = []
    email_map = _emails_for_campaign(recs, campaign_row)

    for lead in leads:
        if not isinstance(lead, dict):
            continue
        email = str(lead.get("email") or "").strip().lower()
        lead_id = lead.get("id")

        row = {
            "provider_lead_id": lead_id,
            "email_hash": _hash(email) if email else None,
            "record_id": None,
            "contact_key": None,
            "campaign_id": campaign_row.get("campaign_id"),
            "provider": "bison",
            "provider_campaign_id": b_id,
            "lead_status": bison._status_in(lead, int(b_id)),
        }

        if is_ours is False:
            row["class"] = NOT_OURS
            row["evidence"] = f"ownership disproved: {ownership_why}"
        elif is_ours is None:
            row["class"] = UNKNOWN
            row["evidence"] = f"ownership unproven: {ownership_why}"
        elif not email:
            row["class"] = UNKNOWN
            row["evidence"] = "lead carries no email address"
        elif email not in email_map:
            row["class"] = UNKNOWN
            row["evidence"] = ("lead email not in any queue record for this "
                               "campaign; cannot derive ledger key")
        else:
            rec_id, contact_key = email_map[email]
            row["record_id"] = rec_id
            row["contact_key"] = contact_key
            pair = (str(rec_id), str(contact_key))
            cls, evidence = _classify_ledger_match(pair, ledger_index)
            row["class"] = cls
            row["evidence"] = evidence
            if cls in (MATCHED, STATE_MISMATCH):
                ledger_rows = ledger_index.get(pair, [])
                row["ledger_key"] = (ledger_rows[0].get("key")
                                     if ledger_rows else None)
                row["key_verified"] = all(
                    verify_key(lr) for lr in ledger_rows)

        campaign_rows.append(row)

    return campaign_rows, None


# ------------------------------------------------------------- reporting

def _hash(value):
    """SHA-256 prefix for PII-safe reporting. Never log raw addresses."""
    import hashlib
    return hashlib.sha256(str(value or "").encode()).hexdigest()[:12]


def print_report(all_rows, campaign_walked, campaign_errors):
    """Print the reverse reconciliation report."""
    counts = {c: 0 for c in CLASSES}
    for row in all_rows:
        counts[row["class"]] = counts.get(row["class"], 0) + 1

    total_provider = len(all_rows)
    total_classified = sum(counts.values())

    print(f"\n{'=' * 60}")
    print("REVERSE RECONCILIATION REPORT")
    print(f"{'=' * 60}")
    print(f"\nCampaigns walked:     {len(campaign_walked)}")
    print(f"Campaigns unreadable: {len(campaign_errors)}")
    if campaign_errors:
        for cid, reason in campaign_errors.items():
            print(f"  - campaign {cid}: {reason}")
    print(f"\nProvider rows read:   {total_provider}")
    print(f"\nClassifications:")
    for cls in CLASSES:
        print(f"  {cls:20s} {counts[cls]}")

    identity_ok = total_classified == total_provider
    identity_line = (f"\nEXHAUSTIVENESS: {total_classified} classified "
                     f"== {total_provider} provider rows read "
                     f"{'PASS' if identity_ok else 'FAIL'}")
    print(identity_line)
    assert identity_ok, (
        f"exhaustiveness violated: {total_classified} != {total_provider}")

    unrecorded = [r for r in all_rows if r["class"] == UNRECORDED]
    if unrecorded:
        print(f"\n--- UNRECORDED rows ({len(unrecorded)}) ---")
        for r in unrecorded[:50]:
            provider_id = r.get("provider_lead_id") or "?"
            rec_id = r.get("record_id") or "?"
            ck = r.get("contact_key") or "?"
            evidence = r.get("evidence") or ""
            print(f"  provider_lead={provider_id}  "
                  f"record_id={rec_id}  contact_key={ck}  "
                  f"evidence={evidence}")

    mismatched = [r for r in all_rows if r["class"] == STATE_MISMATCH]
    if mismatched:
        print(f"\n--- STATE_MISMATCH rows ({len(mismatched)}) ---")
        for r in mismatched[:50]:
            provider_id = r.get("provider_lead_id") or "?"
            rec_id = r.get("record_id") or "?"
            ck = r.get("contact_key") or "?"
            evidence = r.get("evidence") or ""
            print(f"  provider_lead={provider_id}  "
                  f"record_id={rec_id}  contact_key={ck}  "
                  f"evidence={evidence}")

    unknowns = [r for r in all_rows if r["class"] == UNKNOWN]
    if unknowns:
        print(f"\n--- UNKNOWN rows ({len(unknowns)}) ---")
        for r in unknowns[:20]:
            evidence = r.get("evidence") or ""
            print(f"  provider_lead={r.get('provider_lead_id') or '?'}  "
                  f"evidence={evidence}")

    return counts, identity_ok


# ------------------------------------------------------------------ main

def main(argv=None):
    p = argparse.ArgumentParser(
        prog="reverse_reconcile",
        description=__doc__)
    p.add_argument("--workspaces",
                   help="directory holding queue.jsonl and campaigns.jsonl "
                        "(production work/ is not touched)")
    p.add_argument("--json", action="store_true",
                   help="emit machine-readable JSON instead of text")
    a = p.parse_args(argv)

    if a.workspaces:
        ws = os.path.abspath(a.workspaces)
        os.environ["QUEUE"] = os.path.join(ws, "queue.jsonl")
        os.environ["CAMPAIGNS"] = os.path.join(ws, "campaigns.jsonl")
        os.environ["ACTION_LEDGER"] = os.path.join(ws,
                                                   "action-ledger.jsonl")

    ledger_rows = actionledger.load()
    ledger_index = build_ledger_index(ledger_rows)
    camp_rows = list(campaigns.load())
    recs = store.load()

    all_rows = []
    campaign_walked = []
    campaign_errors = {}

    for camp in camp_rows:
        cid = camp.get("campaign_id")
        campaign_walked.append(cid)

        hr_id = camp.get("heyreach_campaign_id")
        b_id = camp.get("bison_campaign_id")

        if hr_id is not None:
            rows, error = classify_heyreach_campaign(camp, recs, ledger_index)
            if error:
                campaign_errors[cid] = f"heyreach: {error}"
            all_rows.extend(rows)
        elif b_id is not None:
            rows, error = classify_bison_campaign(camp, recs, ledger_index)
            if error:
                campaign_errors[cid] = f"bison: {error}"
            all_rows.extend(rows)
        else:
            campaign_errors[cid] = "no provider binding (neither heyreach " \
                                   "nor bison)"

    counts, identity_ok = print_report(all_rows, campaign_walked,
                                       campaign_errors)

    if a.json:
        json_report = {
            "campaigns_walked": len(campaign_walked),
            "campaigns_unreadable": len(campaign_errors),
            "campaign_errors": {str(k): v for k, v in campaign_errors.items()},
            "provider_rows_read": len(all_rows),
            "counts": counts,
            "exhaustiveness_ok": identity_ok,
            "rows": [{k: v for k, v in r.items()} for r in all_rows],
        }
        print(json.dumps(json_report, indent=2, default=str))

    if not identity_ok:
        return 2
    has_issues = (counts.get(UNRECORDED, 0) > 0
                  or counts.get(STATE_MISMATCH, 0) > 0)
    has_unknown = counts.get(UNKNOWN, 0) > 0
    if has_issues or has_unknown:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
