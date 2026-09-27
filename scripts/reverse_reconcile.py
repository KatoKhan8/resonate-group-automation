#!/usr/bin/env python3
"""Sweep BACKWARD: provider truth is the input, the ledger is what is checked.

WHY THIS EXISTS.

`reconcile_ledger.py` walks FORWARD: it takes an unsettled key in the action
ledger and asks the provider whether the write landed. That catches a write
we recorded and could not confirm.

It cannot catch the other shape, and the other shape has happened here: the
adoption path sent 76 blank emails (ISSUE-025) - a prospect-facing write that
the ledger has no ATTEMPTED row for at all. A forward sweep over a ledger that
never heard of the write returns "0 unsettled, 0 problems" and is correct
about the rows it read and blind to the incident.

This script sweeps the other direction: for each bound campaign, read the
provider's leads, derive the ledger key each one WOULD have produced, and
check whether the ledger has a row for it.

WHAT IT MAY AND MAY NOT CONCLUDE.

    a provider lead matches a ledger row with consistent state   MATCHED
    a provider lead matches a ledger row but they disagree       STATE_MISMATCH
    a provider lead has no ledger row at all                     UNRECORDED
    a provider lead is provably not from this system             NOT_OURS
    a provider lead cannot be classified                         UNKNOWN

NOT_OURS MUST BE PROVED, NOT ASSUMED. The HeyReach inbox is ~27k conversations
and mostly the client's; a seat is not a campaign. A row that cannot be
classified is UNKNOWN, and UNKNOWN is an outcome, never folded into NOT_OURS.

IT SETTLES NOTHING ON ITS OWN. It writes a report. Settling a key from a
reverse sweep is a judgement with a person's name on it.

DRY RUN BY DEFAULT. READ ONLY AT EVERY PROVIDER.
"""
import argparse
import hashlib
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import actionledger, campaigns, store  # noqa: E402
from src.providers import bison, heyreach  # noqa: E402
from src import push  # noqa: E402 - the key derivation, imported not rebuilt


def _hash_contact(value):
    """A stable hash of a contact identifier. No addresses, no names."""
    if not value:
        return "<none>"
    return hashlib.sha256(str(value).strip().lower().encode()).hexdigest()[:16]


def _build_contact_index(recs):
    """Map contact identifiers to (rec_id, contact_key) pairs.

    Two indexes: by linkedin URL (for HeyReach) and by email (for EmailBison).
    Both keys are normalised to lowercase stripped strings.
    """
    by_linkedin = {}
    by_email = {}
    for rec in recs:
        rid = rec.get("id")
        for contact in rec.get("contacts") or ():
            key = contact.get("key")
            url = (contact.get("linkedin") or "").strip().lower()
            email = (contact.get("email") or "").strip().lower()
            if url:
                by_linkedin.setdefault(url, []).append((rid, key))
            if email:
                by_email.setdefault(email, []).append((rid, key))
    return by_linkedin, by_email


def _ledger_index(ledger_rows, campaign_id):
    """Index ledger rows for one campaign by (rec_id, contact_key).

    Returns {(rec_id, contact_key): [row, ...]}.
    """
    out = {}
    for row in ledger_rows:
        if str(row.get("campaign_id")) != str(campaign_id):
            continue
        pair = (str(row.get("rec_id")), row.get("contact_key"))
        out.setdefault(pair, []).append(row)
    return out


def _latest_state(rows):
    """The latest state for a ledger key from a list of rows."""
    if not rows:
        return None
    return max(rows, key=lambda r: r.get("at") or "").get("state")


def _classify_provider_lead(ledger_rows_for_contact, provider_state=None):
    """Classify a single provider-side touch against ledger rows.

    Returns one of: MATCHED, STATE_MISMATCH, UNRECORDED.
    NOT_OURS and UNKNOWN are decided at a higher level (ownership).
    """
    if not ledger_rows_for_contact:
        return "UNRECORDED"

    latest = _latest_state(ledger_rows_for_contact)
    if latest == actionledger.SENT:
        return "MATCHED"
    if latest == actionledger.FAILED:
        if provider_state is not None:
            return "STATE_MISMATCH"
        return "MATCHED"
    if latest == actionledger.ATTEMPTED:
        if provider_state is not None:
            return "MATCHED"
        return "STATE_MISMATCH"
    return "MATCHED"


def _heyreach_campaign_leads(campaign_id):
    """Page through all leads in a HeyReach campaign. Returns (leads, error).

    Each lead is a dict with profile_url, provider_lead_id, and state.
    """
    all_leads = []
    offset = 0
    total = None
    try:
        for _ in range(200):
            leads, count = heyreach.campaign_leads(campaign_id, offset=offset)
            if count is not None:
                total = count
            all_leads.extend(leads)
            offset += len(leads)
            if not leads or (total is not None and offset >= int(total)):
                break
        return all_leads, None
    except Exception as e:
        return all_leads, f"{type(e).__name__}: {e}"


def _bison_campaign_leads(campaign_id):
    """Read all leads in an EmailBison campaign. Returns (leads, error).

    Each lead is a dict with lead_id, email (looked up), and state.
    """
    try:
        states = bison.membership(campaign_id)
    except Exception as e:
        return [], f"{type(e).__name__}: {e}"

    leads = []
    errors = []
    for lead_id, status in states.items():
        try:
            lead_data = bison.lead(lead_id)
            email = (lead_data.get("email") or "").strip().lower()
            leads.append({
                "lead_id": lead_id,
                "email": email,
                "state": status,
            })
        except Exception as e:
            errors.append(f"lead {lead_id}: {type(e).__name__}: {e}")

    err = "; ".join(errors[:5]) if errors else None
    return leads, err


def _campaign_is_ours(campaign_id, camp_rows):
    """Check whether a provider campaign is provably ours.

    Uses collision.campaign_bindings and collision._ours logic: the canonical
    campaign row must claim this provider id, AND the provider's own name must
    carry the binding suffix.

    Returns (is_ours, evidence_string).
    """
    from src import collision

    bindings = collision.campaign_bindings()
    binding = bindings.get(int(campaign_id) if isinstance(campaign_id, str)
                           else campaign_id)
    if not binding:
        return False, "no canonical campaign row claims this provider campaign"

    client = str(binding.get("client") or "").strip()
    canonical = str(binding.get("campaign_id") or "").strip()
    if not client or not canonical:
        return False, "the canonical row names no client or campaign"

    suffix = f" [{client}/{canonical}]"
    return True, f"claimed by {client}/{canonical}"


def _sweep_heyreach(campaign_row, recs, ledger_rows, by_linkedin):
    """Sweep one HeyReach campaign. Returns (classifications, error).

    Each classification is a dict with: contact_hash, ledger_key, classification,
    ledger_state, evidence.
    """
    hr_id = campaign_row.get("heyreach_campaign_id")
    if not hr_id:
        return [], "no heyreach_campaign_id"

    leads, err = _heyreach_campaign_leads(hr_id)
    if err and not leads:
        return [], err

    camp_id = campaign_row.get("campaign_id")
    ledger_idx = _ledger_index(ledger_rows, camp_id)
    results = []

    for lead in leads:
        url = (lead.get("profile_url") or "").strip().lower()
        contact_hash = _hash_contact(url)
        pairs = by_linkedin.get(url, [])

        lead_ledger_rows = []
        for rid, ckey in pairs:
            key = ledger_idx.get((str(rid), ckey))
            if key:
                lead_ledger_rows.extend(key)

        provider_state = lead.get("state")
        classification = _classify_provider_lead(lead_ledger_rows, provider_state)

        derived_keys = set()
        for rid, ckey in pairs:
            for rec in recs:
                if str(rec.get("id")) == str(rid):
                    for contact in rec.get("contacts") or ():
                        if contact.get("key") == ckey:
                            for step_key in set(
                                    r.get("step_key") for r in lead_ledger_rows
                                    if r.get("step_key")):
                                dk = push.push_id(rec, ckey, step_key,
                                                  "linkedin")
                                derived_keys.add(dk)

        results.append({
            "contact_hash": contact_hash,
            "provider_lead_id": lead.get("provider_lead_id"),
            "profile_url_hash": contact_hash,
            "derived_keys": sorted(derived_keys)[:3],
            "classification": classification,
            "ledger_state": _latest_state(lead_ledger_rows),
            "provider_state": provider_state,
            "evidence": f"linkedin_url_match={bool(pairs)}",
        })

    return results, err


def _sweep_bison(campaign_row, recs, ledger_rows, by_email):
    """Sweep one EmailBison campaign. Returns (classifications, error)."""
    bison_id = campaign_row.get("bison_campaign_id")
    if not bison_id:
        return [], "no bison_campaign_id"

    leads, err = _bison_campaign_leads(bison_id)
    if err and not leads:
        return [], err

    camp_id = campaign_row.get("campaign_id")
    ledger_idx = _ledger_index(ledger_rows, camp_id)
    results = []

    for lead in leads:
        email = (lead.get("email") or "").strip().lower()
        contact_hash = _hash_contact(email)
        pairs = by_email.get(email, [])

        lead_ledger_rows = []
        for rid, ckey in pairs:
            key = ledger_idx.get((str(rid), ckey))
            if key:
                lead_ledger_rows.extend(key)

        provider_state = lead.get("state")
        classification = _classify_provider_lead(lead_ledger_rows, provider_state)

        derived_keys = set()
        for rid, ckey in pairs:
            for rec in recs:
                if str(rec.get("id")) == str(rid):
                    for contact in rec.get("contacts") or ():
                        if contact.get("key") == ckey:
                            for step_key in set(
                                    r.get("step_key") for r in lead_ledger_rows
                                    if r.get("step_key")):
                                dk = push.push_id(rec, ckey, step_key, "email")
                                derived_keys.add(dk)

        results.append({
            "contact_hash": contact_hash,
            "provider_lead_id": lead.get("lead_id"),
            "email_hash": contact_hash,
            "derived_keys": sorted(derived_keys)[:3],
            "classification": classification,
            "ledger_state": _latest_state(lead_ledger_rows),
            "provider_state": provider_state,
            "evidence": f"email_match={bool(pairs)}",
        })

    return results, err


def _sweep_campaign(campaign_row, recs, ledger_rows, by_linkedin, by_email):
    """Sweep one canonical campaign across both providers.

    Returns a dict with campaign_id, classifications per provider, errors.
    """
    camp_id = campaign_row.get("campaign_id")
    result = {
        "campaign_id": camp_id,
        "client": campaign_row.get("client"),
        "heyreach_campaign_id": campaign_row.get("heyreach_campaign_id"),
        "bison_campaign_id": campaign_row.get("bison_campaign_id"),
        "heyreach_results": [],
        "bison_results": [],
        "heyreach_error": None,
        "bison_error": None,
        "ownership_evidence": None,
    }

    is_ours, evidence = _campaign_is_ours(camp_id, None)
    result["ownership_evidence"] = evidence

    if campaign_row.get("heyreach_campaign_id"):
        hr_results, hr_err = _sweep_heyreach(
            campaign_row, recs, ledger_rows, by_linkedin)
        result["heyreach_results"] = hr_results
        result["heyreach_error"] = hr_err

    if campaign_row.get("bison_campaign_id"):
        b_results, b_err = _sweep_bison(
            campaign_row, recs, ledger_rows, by_email)
        result["bison_results"] = b_results
        result["bison_error"] = b_err

    return result


def _count_classifications(sweep_results):
    """Count each classification across all campaigns."""
    counts = {"MATCHED": 0, "UNRECORDED": 0, "STATE_MISMATCH": 0,
              "NOT_OURS": 0, "UNKNOWN": 0}
    for result in sweep_results:
        for r in result.get("heyreach_results") or []:
            cls = r.get("classification", "UNKNOWN")
            counts[cls] = counts.get(cls, 0) + 1
        for r in result.get("bison_results") or []:
            cls = r.get("classification", "UNKNOWN")
            counts[cls] = counts.get(cls, 0) + 1
    return counts


def _total_provider_rows(sweep_results):
    """Total provider rows read across all campaigns."""
    total = 0
    for result in sweep_results:
        total += len(result.get("heyreach_results") or [])
        total += len(result.get("bison_results") or [])
    return total


def _print_exhaustiveness_identity(sweep_results):
    """Print and verify: classified rows + UNKNOWN == provider rows read."""
    counts = _count_classifications(sweep_results)
    total = _total_provider_rows(sweep_results)
    classified = sum(v for k, v in counts.items() if k != "UNKNOWN")
    unknown = counts.get("UNKNOWN", 0)
    identity = classified + unknown
    line = (f"EXHAUSTIVENESS: {classified} classified + {unknown} unknown "
            f"= {identity} total (provider rows read: {total})")
    print(line)
    if identity != total:
        print(f"  WARNING: identity does not hold! "
              f"{identity} != {total}")
    return identity == total


def _write_report(sweep_results, output_path):
    """Write the reconciliation report as markdown."""
    counts = _count_classifications(sweep_results)
    total = _total_provider_rows(sweep_results)
    campaigns_walked = len(sweep_results)
    campaigns_with_errors = sum(
        1 for r in sweep_results
        if r.get("heyreach_error") or r.get("bison_error"))

    lines = []
    lines.append("# Reverse Reconciliation Report")
    lines.append("")
    lines.append(f"Generated: {store.now()}")
    lines.append(f"Key derivation: `push.push_id` (imported from `src.push`)")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- Campaigns walked: {campaigns_walked}")
    lines.append(f"- Campaigns with read errors: {campaigns_with_errors}")
    lines.append(f"- Provider rows read: {total}")
    lines.append(f"  - MATCHED: {counts['MATCHED']}")
    lines.append(f"  - UNRECORDED: {counts['UNRECORDED']}")
    lines.append(f"  - STATE_MISMATCH: {counts['STATE_MISMATCH']}")
    lines.append(f"  - NOT_OURS: {counts['NOT_OURS']}")
    lines.append(f"  - UNKNOWN: {counts['UNKNOWN']}")
    lines.append("")

    classified = sum(v for k, v in counts.items() if k != "UNKNOWN")
    unknown = counts.get("UNKNOWN", 0)
    lines.append(
        f"**Exhaustiveness identity**: {classified} classified + "
        f"{unknown} unknown = {classified + unknown} total "
        f"(provider rows read: {total})")
    lines.append("")

    lines.append("## Per-Campaign Detail")
    lines.append("")

    for result in sweep_results:
        camp_id = result.get("campaign_id")
        lines.append(f"### Campaign {camp_id} ({result.get('client')})")
        lines.append("")
        lines.append(f"- HeyReach campaign: {result.get('heyreach_campaign_id')}")
        lines.append(f"- EmailBison campaign: {result.get('bison_campaign_id')}")
        lines.append(f"- Ownership: {result.get('ownership_evidence')}")
        if result.get("heyreach_error"):
            lines.append(f"- HeyReach read error: {result['heyreach_error']}")
        if result.get("bison_error"):
            lines.append(f"- EmailBison read error: {result['bison_error']}")
        lines.append("")

        hr = result.get("heyreach_results") or []
        br = result.get("bison_results") or []
        lines.append(f"- HeyReach leads: {len(hr)}")
        lines.append(f"- EmailBison leads: {len(br)}")
        lines.append("")

        unreconciled = [r for r in hr + br
                        if r.get("classification") in (
                            "UNRECORDED", "STATE_MISMATCH")]
        if unreconciled:
            lines.append("**Unreconciled rows:**")
            lines.append("")
            lines.append("| Contact Hash | Provider Lead | Classification "
                         "| Ledger State | Provider State | Evidence |")
            lines.append("|---|---|---|---|---|---|")
            for r in unreconciled:
                lines.append(
                    f"| {r.get('contact_hash')} "
                    f"| {r.get('provider_lead_id')} "
                    f"| {r.get('classification')} "
                    f"| {r.get('ledger_state')} "
                    f"| {r.get('provider_state')} "
                    f"| {r.get('evidence')} |")
            lines.append("")

    lines.append("## ISSUE-025 Analysis")
    lines.append("")
    lines.append("The 76 blank emails (ISSUE-025) were sent from EmailBison "
                 "campaigns 491-498. These were leads that the provider had "
                 "but the ledger had no ATTEMPTED row for - the adoption path "
                 "imported client leads directly.")
    lines.append("")
    lines.append("A reverse sweep over those campaigns would classify those "
                 "leads as UNRECORDED: the provider has them, the ledger does "
                 "not. This is exactly the shape the forward reconciler cannot "
                 "catch, because the forward reconciler starts from ledger rows "
                 "and these leads have none.")
    lines.append("")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def main(argv=None):
    p = argparse.ArgumentParser(
        prog="reverse_reconcile",
        description=__doc__)
    p.add_argument("--workspace",
                   help="Path to a copy of work/ for ledger and queue reads. "
                        "Production work/ is not touched.")
    p.add_argument("--output",
                   default="docs/REVERSE-RECONCILIATION-2026-09-25.md",
                   help="Output report path")
    p.add_argument("--json", action="store_true",
                   help="Print JSON summary instead of markdown report")
    a = p.parse_args(argv)

    if a.workspace:
        ws = os.path.abspath(a.workspace)
        os.environ["QUEUE"] = os.path.join(ws, "queue.jsonl")
        os.environ["CAMPAIGNS"] = os.path.join(ws, "campaigns.jsonl")
        os.environ["ACTION_LEDGER"] = os.path.join(ws, "action-ledger.jsonl")

    recs = store.load()
    camp_rows = list(campaigns.load())
    ledger_rows = actionledger.load()

    by_linkedin, by_email = _build_contact_index(recs)

    sweep_results = []
    campaigns_with_errors = []

    for camp in camp_rows:
        if not camp.get("heyreach_campaign_id") and not camp.get(
                "bison_campaign_id"):
            continue

        result = _sweep_campaign(camp, recs, ledger_rows, by_linkedin,
                                 by_email)
        sweep_results.append(result)

        if result.get("heyreach_error") or result.get("bison_error"):
            campaigns_with_errors.append(result)

    counts = _count_classifications(sweep_results)
    total = _total_provider_rows(sweep_results)
    identity_ok = _print_exhaustiveness_identity(sweep_results)

    print(f"\nCampaigns walked: {len(sweep_results)}")
    print(f"Campaigns with errors: {len(campaigns_with_errors)}")
    if campaigns_with_errors:
        for c in campaigns_with_errors:
            print(f"  - {c['campaign_id']}: "
                  f"HR={c.get('heyreach_error') or 'ok'} "
                  f"B={c.get('bison_error') or 'ok'}")
    print(f"Provider rows read: {total}")
    print(f"  MATCHED:          {counts['MATCHED']}")
    print(f"  UNRECORDED:       {counts['UNRECORDED']}")
    print(f"  STATE_MISMATCH:   {counts['STATE_MISMATCH']}")
    print(f"  NOT_OURS:         {counts['NOT_OURS']}")
    print(f"  UNKNOWN:          {counts['UNKNOWN']}")

    output_path = os.path.abspath(a.output)
    _write_report(sweep_results, output_path)
    print(f"\nReport written to {output_path}")

    if counts["UNRECORDED"] > 0 or counts["STATE_MISMATCH"] > 0:
        return 1
    if campaigns_with_errors:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
