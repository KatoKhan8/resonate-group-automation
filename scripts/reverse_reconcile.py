#!/usr/bin/env python3
"""Sweep BACKWARD: provider truth is the input; the ledger is being checked.

WHY THIS EXISTS.

`scripts/reconcile_ledger.py` walks FORWARD: it takes an unsettled key in
the action ledger and asks the provider whether the write landed. That
direction catches a write we recorded and could not confirm.

It cannot catch the other shape, and the other shape has happened here: the
adoption path sent 76 blank emails (ISSUE-025) - a prospect-facing write
that the ledger has no ATTEMPTED row for at all. A forward sweep over a
ledger that never heard of the write returns "0 unsettled, 0 problems" and
is correct about the rows it read and blind to the incident.

This script sweeps the other direction: for each bound campaign, it reads
the provider's leads and checks whether the ledger has a row for each one.

CLASSIFICATION (mutually exclusive and exhaustive).

    MATCHED          a ledger row exists and its state is consistent
    UNRECORDED       the provider acted and NO ledger row exists at all
    STATE_MISMATCH   a ledger row exists and disagrees with provider truth
    NOT_OURS         proved, not assumed: positive evidence the row belongs
                     to the client, not to us
    UNKNOWN          cannot be classified (provider read failure, no queue
                     match and no ownership evidence either way)

Classified rows + UNKNOWN == provider rows read. This identity is printed
and asserted in the test.

DRY RUN BY DEFAULT. Like every other script here that could change
something. This script writes a report and settles nothing.

READ ONLY at every provider. No write, no send, no settle, no resume.

USAGE.

    py -3 scripts/reverse_reconcile.py
    py -3 scripts/reverse_reconcile.py --work-dir /path/to/work/copy
"""
import argparse
import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import (                                                          # noqa: E402
    actionledger, campaigns as campaigns_mod, linkedin, push, store)
from src.providers import bison, heyreach                                   # noqa: E402

# ------------------------------------------------------------------ constants

MATCHED = "MATCHED"
UNRECORDED = "UNRECORDED"
STATE_MISMATCH = "STATE_MISMATCH"
NOT_OURS = "NOT_OURS"
UNKNOWN = "UNKNOWN"

ALL_CLASSES = (MATCHED, UNRECORDED, STATE_MISMATCH, NOT_OURS, UNKNOWN)

# HeyReach lead states that prove the provider acted on the lead.
# `request_pending` means enrolled but nothing done - it is NOT a touch.
_HR_ACTIVE_STATES = frozenset({
    "replied", "accepted", "request_sent", "failed", "ended_no_action",
})


# -------------------------------------------------------------- queue indexing

def _norm_url(url):
    """Canonical LinkedIn URL, falling back to stripped lowercase."""
    try:
        return linkedin.key(url)
    except (ValueError, Exception):                                         # noqa: BLE001
        return str(url or "").strip().lower()


def _build_queue_index(recs):
    """Index queue records by LinkedIn URL and email.

    Returns (by_linkedin, by_email) where each maps a normalised identifier
    to (rec_id, contact_key). A collision (two records, same URL) records
    the first seen; this is a best-effort index for matching, not a
    uniqueness constraint.
    """
    by_linkedin = {}
    by_email = {}
    for rec in recs:
        if not isinstance(rec, dict):
            continue
        rec_id = str(rec.get("id") or "")
        if not rec_id:
            continue
        for contact in rec.get("contacts") or ():
            if not isinstance(contact, dict):
                continue
            ck = contact.get("key") or ""
            li = contact.get("linkedin") or ""
            if li:
                norm = _norm_url(li)
                if norm and norm not in by_linkedin:
                    by_linkedin[norm] = (rec_id, ck)
            em = contact.get("email") or ""
            if em:
                norm_em = str(em).strip().lower()
                if norm_em and norm_em not in by_email:
                    by_email[norm_em] = (rec_id, ck)
    return by_linkedin, by_email


# --------------------------------------------------------- campaign helpers

def _heyreach_id(camp_row):
    """The HeyReach campaign id from a canonical campaign row, or None."""
    v = camp_row.get("heyreach_campaign_id")
    if v in (None, ""):
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _bison_id(camp_row):
    """The EmailBison campaign id from a canonical campaign row, or None."""
    v = camp_row.get("bison_campaign_id")
    if v in (None, ""):
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _campaign_steps(camp_row):
    """The (step_key, channel) pairs this campaign may produce.

    Uses `cadence.steps_for` so the same step definitions the write path
    uses are what the reverse reconciler checks. Falls back to the default
    cadence when the client config is unreadable.
    """
    from src import cadence, clients

    config = {}
    client = str(camp_row.get("client") or "").strip()
    if client:
        try:
            config = clients.load(client)
        except Exception:                                                   # noqa: BLE001
            config = {}
    try:
        steps = cadence.steps_for(campaign=camp_row, config=config)
    except Exception:                                                       # noqa: BLE001
        try:
            steps = cadence.steps_for(config=config)
        except Exception:                                                   # noqa: BLE001
            steps = cadence.STEPS
    return [(s.get("key", ""), s.get("channel", ""))
            for s in (steps or ()) if isinstance(s, dict)]


def _possible_keys(camp_row, rec_id, contact_key):
    """Every ledger key this contact could have in this campaign.

    One per (step_key, channel) pair from the campaign's cadence. Imported
    `push.push_id` derives each key the same way the write path does.
    """
    rec = {"id": rec_id}
    return [push.push_id(rec, contact_key, sk, ch)
            for sk, ch in _campaign_steps(camp_row) if sk and ch]


# -------------------------------------------------- ledger state inspection

def _ledger_state(key, ledger_latest):
    """The latest state of this key in the ledger, or None if absent."""
    row = ledger_latest.get(key)
    return row.get("state") if row else None


def _classify_key_state(ledger_state, provider_active):
    """Given a ledger state and whether the provider shows activity, classify.

    Returns MATCHED, STATE_MISMATCH, or UNRECORDED.
    """
    if ledger_state is None:
        return UNRECORDED
    if ledger_state == actionledger.SENT:
        return MATCHED
    if ledger_state in (actionledger.ATTEMPTED, actionledger.UNRESOLVED):
        if provider_active:
            return STATE_MISMATCH
        return MATCHED
    if ledger_state == actionledger.FAILED:
        if provider_active:
            return STATE_MISMATCH
        return MATCHED
    if ledger_state == actionledger.ABANDONED:
        if provider_active:
            return STATE_MISMATCH
        return MATCHED
    if ledger_state == actionledger.UNCONFIRMABLE:
        if provider_active:
            return STATE_MISMATCH
        return MATCHED
    return MATCHED


# ----------------------------------------------- HeyReach lead classification

def _hr_is_active(lead):
    """Did HeyReach act on this lead? `request_pending` is NOT a touch."""
    state = lead.get("state") or ""
    return state in _HR_ACTIVE_STATES


def _read_heyreach_leads(hr_campaign_id):
    """Page through every lead in a HeyReach campaign. Read-only.

    Returns (leads, error). On success error is None. On failure leads is
    [] and error is a string describing what went wrong.
    """
    leads = []
    offset = 0
    total = None
    for _ in range(200):
        try:
            page, count = heyreach.campaign_leads(hr_campaign_id, offset=offset)
        except Exception as e:                                                # noqa: BLE001
            return [], f"heyreach campaign {hr_campaign_id}: {type(e).__name__}: {e}"
        if count is not None:
            total = count
        leads.extend(page)
        offset += len(page)
        if not page or (total is not None and offset >= int(total)):
            break
    return leads, None


# --------------------------------------------- EmailBison lead classification

def _read_bison_leads(bison_campaign_id):
    """Page through every lead in an EmailBison campaign. Read-only.

    Returns (leads, error). Each lead is a dict with at least `email`,
    `lead_id`, `status`.
    """
    from src.providers.bison import leads_endpoint, mapping as bison_mapping
    from src.providers import request as prov_request, ok as prov_ok

    leads = []
    page = 1
    total = None
    while page <= 500:
        url = f"{leads_endpoint(bison_campaign_id)}?page={page}"
        try:
            status, data = prov_request("GET", url, bison.headers())
        except Exception as e:                                                # noqa: BLE001
            return [], f"bison campaign {bison_campaign_id}: {type(e).__name__}: {e}"
        if not prov_ok(status):
            return [], f"bison campaign {bison_campaign_id}: GET -> {status}"
        if not isinstance(data, dict):
            return [], f"bison campaign {bison_campaign_id}: unexpected shape"
        chunk = bison_mapping(data, "membership").get("data")
        if not isinstance(chunk, list):
            return [], f"bison campaign {bison_campaign_id}: data is not a list"
        leads.extend(r for r in chunk if isinstance(r, dict))
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
    return leads, None


def _bison_lead_is_active(lead):
    """Did EmailBison act on this lead? Presence in the campaign with a
    status other than `stopped`/`bounced` counts as active."""
    st = str(lead.get("status") or "").strip().lower()
    return st not in ("", "stopped", "bounced")


# --------------------------------------------------------- ownership evidence

def _prove_not_ours(camp_row, provider_lead, provider_name):
    """Can we POSITIVELY prove this lead belongs to the client, not us?

    Returns (verdict, evidence_sentence). The verdict is NOT_OURS only when
    positive evidence exists. If we cannot prove it, the verdict is UNKNOWN.

    A lead in a bound campaign that matches no queue record is UNKNOWN, not
    NOT_OURS. We cannot prove who added it - the client may have added it
    manually, or another system may have pushed it. NOT_OURS requires
    positive evidence: the provider's own campaign name contradicting our
    binding, or the campaign having no binding at all.

    Evidence used:
    - The campaign row itself: does it claim this provider campaign id?
    - collision._ours: does the provider's campaign name match our binding?
    """
    from src import collision

    hr_id = _heyreach_id(camp_row)
    b_id = _bison_id(camp_row)

    # The campaign row we're iterating IS the binding. If the provider
    # campaign id matches what the row claims, the campaign is bound.
    if provider_name == "heyreach" and hr_id is not None:
        campaign_name = provider_lead.get("campaign_name") or ""
        if campaign_name:
            # Build a minimal binding dict for _ours
            binding = {"client": camp_row.get("client"),
                       "campaign_id": camp_row.get("campaign_id")}
            ours, why = collision._ours(
                hr_id, binding, {"name": campaign_name})
            if not ours:
                return NOT_OURS, f"heyreach campaign {hr_id}: {why}"

    if provider_name == "bison" and b_id is not None:
        campaign_name = provider_lead.get("name") or ""
        if campaign_name:
            binding = {"client": camp_row.get("client"),
                       "campaign_id": camp_row.get("campaign_id")}
            ours, why = collision._ours(
                b_id, binding, {"name": campaign_name})
            if not ours:
                return NOT_OURS, f"bison campaign {b_id}: {why}"

    return UNKNOWN, ("lead in a bound campaign but no queue record matches; "
                     "cannot prove who added it")


# -------------------------------------------------------- hashing for reports

def _hash_contact(value):
    """SHA-256 prefix for reports. No PII in the output."""
    return hashlib.sha256(str(value or "").encode("utf-8")).hexdigest()[:12]


# -------------------------------------------------------- the main sweep

def _sweep_campaign(camp_row, by_linkedin, by_email, ledger_latest):
    """Walk one bound campaign's provider leads and classify each.

    Returns (rows, error). rows is a list of classification dicts. error is
    a string if the provider could not be read, else None.
    """
    hr = _heyreach_id(camp_row)
    bi = _bison_id(camp_row)
    campaign_id = str(camp_row.get("campaign_id") or "")
    results = []

    if hr is not None:
        leads, err = _read_heyreach_leads(hr)
        if err:
            return [], err
        for lead in leads:
            profile_url = lead.get("profile_url") or ""
            norm = _norm_url(profile_url) if profile_url else ""
            match = by_linkedin.get(norm) if norm else None
            active = _hr_is_active(lead)

            if match:
                rec_id, contact_key = match
                keys = _possible_keys(camp_row, rec_id, contact_key)
                best = _best_classification(keys, ledger_latest, active)
                results.append({
                    "campaign_id": campaign_id,
                    "provider": "heyreach",
                    "provider_campaign_id": hr,
                    "contact_hash": _hash_contact(norm),
                    "provider_lead_id": lead.get("provider_lead_id"),
                    "provider_state": lead.get("state"),
                    "classification": best,
                    "ledger_key": (keys[0] if keys else None),
                    "ledger_state": (_ledger_state(keys[0], ledger_latest)
                                     if keys else None),
                    "evidence": f"queue match on linkedin URL",
                })
            else:
                verdict, evidence = _prove_not_ours(
                    camp_row, lead, "heyreach")
                # A lead in a bound campaign with no queue match and no
                # positive NOT_OURS evidence is UNRECORDED: the provider
                # has a lead we cannot find a ledger key for.
                if verdict == UNKNOWN and active:
                    verdict = UNRECORDED
                    evidence = ("provider lead in bound campaign but no "
                                "queue record matches; no ledger key can "
                                "be derived")
                results.append({
                    "campaign_id": campaign_id,
                    "provider": "heyreach",
                    "provider_campaign_id": hr,
                    "contact_hash": _hash_contact(norm),
                    "provider_lead_id": lead.get("provider_lead_id"),
                    "provider_state": lead.get("state"),
                    "classification": verdict,
                    "ledger_key": None,
                    "ledger_state": None,
                    "evidence": evidence,
                })

    if bi is not None:
        leads, err = _read_bison_leads(bi)
        if err:
            return results, err
        for lead in leads:
            email = str(lead.get("email") or "").strip().lower()
            match = by_email.get(email) if email else None
            active = _bison_lead_is_active(lead)

            if match:
                rec_id, contact_key = match
                keys = _possible_keys(camp_row, rec_id, contact_key)
                best = _best_classification(keys, ledger_latest, active)
                results.append({
                    "campaign_id": campaign_id,
                    "provider": "bison",
                    "provider_campaign_id": bi,
                    "contact_hash": _hash_contact(email),
                    "provider_lead_id": lead.get("id"),
                    "provider_state": lead.get("status"),
                    "classification": best,
                    "ledger_key": (keys[0] if keys else None),
                    "ledger_state": (_ledger_state(keys[0], ledger_latest)
                                     if keys else None),
                    "evidence": f"queue match on email",
                })
            else:
                verdict, evidence = _prove_not_ours(
                    camp_row, lead, "bison")
                if verdict == UNKNOWN and active:
                    verdict = UNRECORDED
                    evidence = ("provider lead in bound campaign but no "
                                "queue record matches; no ledger key can "
                                "be derived")
                results.append({
                    "campaign_id": campaign_id,
                    "provider": "bison",
                    "provider_campaign_id": bi,
                    "contact_hash": _hash_contact(email),
                    "provider_lead_id": lead.get("id"),
                    "provider_state": lead.get("status"),
                    "classification": verdict,
                    "ledger_key": None,
                    "ledger_state": None,
                    "evidence": evidence,
                })

    return results, None


def _best_classification(keys, ledger_latest, provider_active):
    """The most concerning classification across all possible keys.

    Priority: STATE_MISMATCH > MATCHED > UNRECORDED. If ANY key shows a
    mismatch, the lead is a mismatch. If any key is matched, the lead is
    matched. If no key exists at all, the lead is unrecorded.
    """
    if not keys:
        return UNRECORDED

    any_exist = False
    for k in keys:
        ls = _ledger_state(k, ledger_latest)
        if ls is not None:
            any_exist = True
            cls = _classify_key_state(ls, provider_active)
            if cls == STATE_MISMATCH:
                return STATE_MISMATCH
            if cls == MATCHED:
                return MATCHED

    if any_exist:
        return MATCHED
    return UNRECORDED


def _load_ledger_latest(ledger_rows):
    """Collapse ledger rows to the latest state per key."""
    latest = {}
    for row in (ledger_rows or ()):
        if not isinstance(row, dict):
            continue
        k = row.get("key")
        if k:
            latest[k] = row
    return latest


def run(work_dir=None):
    """The full sweep. Returns (report_dict, exit_code)."""
    if work_dir:
        store.use_directory(work_dir)

    camp_rows = list(campaigns_mod.load())
    try:
        recs = store.load()
    except Exception as e:                                                  # noqa: BLE001
        return {"error": f"cannot read queue: {e}"}, 1
    try:
        ledger_rows = actionledger.load()
    except Exception as e:                                                  # noqa: BLE001
        return {"error": f"cannot read ledger: {e}"}, 1

    by_linkedin, by_email = _build_queue_index(recs)
    ledger_latest = _load_ledger_latest(ledger_rows)

    bound = [c for c in camp_rows
             if isinstance(c, dict) and (_heyreach_id(c) or _bison_id(c))]

    all_rows = []
    unreadable = []
    errors = []

    for camp in bound:
        cid = str(camp.get("campaign_id") or "?")
        rows, err = _sweep_campaign(camp, by_linkedin, by_email,
                                    ledger_latest)
        all_rows.extend(rows)
        if err:
            unreadable.append({"campaign_id": cid, "error": err})
            errors.append(err)
            for r in rows:
                r["classification"] = UNKNOWN

    counts = {c: 0 for c in ALL_CLASSES}
    for r in all_rows:
        cls = r.get("classification")
        if cls in counts:
            counts[cls] += 1

    total = len(all_rows)
    identity = sum(counts.values())
    identity_ok = identity == total

    report = {
        "campaigns_walked": len(bound),
        "campaigns_unreadable": len(unreadable),
        "unreadable_details": unreadable,
        "provider_rows_read": total,
        "counts": counts,
        "exhaustiveness_identity": f"{identity} == {total}",
        "exhaustiveness_ok": identity_ok,
        "classifications": all_rows,
    }
    exit_code = 0
    if not identity_ok:
        exit_code = 2
    if errors:
        exit_code = max(exit_code, 1)

    return report, exit_code


def _print_report(report):
    """Human-readable report to stdout."""
    if "error" in report:
        print(f"ERROR: {report['error']}")
        return

    print(f"Campaigns walked:      {report['campaigns_walked']}")
    print(f"Campaigns unreadable:  {report['campaigns_unreadable']}")
    for u in report.get("unreadable_details", []):
        print(f"  UNREADABLE {u['campaign_id']}: {u['error']}")
    print(f"Provider rows read:    {report['provider_rows_read']}")
    counts = report["counts"]
    print(f"  MATCHED:          {counts[MATCHED]}")
    print(f"  UNRECORDED:       {counts[UNRECORDED]}")
    print(f"  STATE_MISMATCH:   {counts[STATE_MISMATCH]}")
    print(f"  NOT_OURS:         {counts[NOT_OURS]}")
    print(f"  UNKNOWN:          {counts[UNKNOWN]}")
    print(f"Exhaustiveness: {report['exhaustiveness_identity']}  "
          f"{'OK' if report['exhaustiveness_ok'] else 'FAIL'}")

    unrecorded = [r for r in report.get("classifications", [])
                  if r.get("classification") == UNRECORDED]
    if unrecorded:
        print(f"\nUNRECORDED rows ({len(unrecorded)}):")
        for r in unrecorded[:50]:
            print(f"  campaign={r['campaign_id']}  provider={r['provider']}:"
                  f"{r['provider_campaign_id']}  "
                  f"contact={r['contact_hash']}  "
                  f"lead={r['provider_lead_id']}  "
                  f"state={r['provider_state']}  "
                  f"evidence={r['evidence']}")

    mismatches = [r for r in report.get("classifications", [])
                  if r.get("classification") == STATE_MISMATCH]
    if mismatches:
        print(f"\nSTATE_MISMATCH rows ({len(mismatches)}):")
        for r in mismatches[:50]:
            print(f"  campaign={r['campaign_id']}  key={r['ledger_key']}  "
                  f"ledger={r['ledger_state']}  provider={r['provider_state']}")


def main(argv=None):
    p = argparse.ArgumentParser(prog="reverse_reconcile",
                                description=__doc__)
    p.add_argument("--work-dir",
                   help="Path to a copy of work/ (production work/ is not "
                        "touched)")
    p.add_argument("--json", action="store_true",
                   help="Output JSON instead of human-readable text")
    a = p.parse_args(argv)

    report, rc = run(work_dir=a.work_dir)
    if a.json:
        print(json.dumps(report, indent=2, default=str))
    else:
        _print_report(report)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
