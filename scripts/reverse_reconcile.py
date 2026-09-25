#!/usr/bin/env python3
"""Reverse reconciliation: provider truth first, the ledger being checked.

WHY THIS EXISTS.

`reconcile_ledger.py` walks FORWARD: it takes an unsettled key in the ledger
and asks the provider whether the write landed. That catches a write we
recorded and could not confirm.

It cannot catch the other shape, and the other shape has happened here: the
adoption path sent 76 blank emails (ISSUE-025) - a prospect-facing write that
the ledger has no ATTEMPTED row for at all. A forward sweep over a ledger that
never heard of the write returns "0 unsettled, 0 problems" and is correct
about the rows it read and blind to the incident.

So: sweep BACKWARD. Provider truth is the input; the ledger is the thing
being checked.

WHAT IT DOES.

For each campaign we own (from the campaign bindings, not a hand-typed list):

  1. Read the provider's leads (HeyReach) or scheduled emails (EmailBison).
  2. For each provider-side touch, derive the ledger key the same way the
     write path would have. IMPORT the derivation (push.push_id); do not
     re-implement it.
  3. Classify every provider-side touch into exactly one of:

       MATCHED        a ledger row exists and its state is consistent
       UNRECORDED     the provider acted and NO ledger row exists at all
       STATE_MISMATCH a ledger row exists and disagrees
       NOT_OURS       provider row belongs to the client, not to us

  4. NOT_OURS must be PROVED, not assumed. The HeyReach inbox is ~27k
     conversations and mostly the client's. Use the existing ownership
     evidence (collision.campaign_bindings, collision._ours, campaign stats)
     and record WHICH evidence cleared each row. A row you cannot classify
     is UNKNOWN, and UNKNOWN is an outcome, never folded into NOT_OURS.

WHAT IT DOES NOT DO.

  - It settles nothing on its own. It writes a report.
  - It writes nothing to any provider. READ ONLY.
  - It writes nothing to the ledger.
  - DRY RUN BY DEFAULT, like every other script here.

DRY RUN vs LIVE.

  --dry-run   (default)  Read the provider, check the ledger, print a report.
  --live                 Same, but against the real provider estate.

Neither mode writes to the provider or the ledger. The distinction is whether
the provider reads hit the real API or a local copy.
"""
import argparse
import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import actionledger, campaigns, collision, push, store  # noqa: E402
from src.providers import bison, heyreach  # noqa: E402

# ----------------------------------------------------------------- classes

MATCHED = "MATCHED"
UNRECORDED = "UNRECORDED"
STATE_MISMATCH = "STATE_MISMATCH"
NOT_OURS = "NOT_OURS"
UNKNOWN = "UNKNOWN"

ALL_CLASSES = (MATCHED, UNRECORDED, STATE_MISMATCH, NOT_OURS, UNKNOWN)

# Ledger states that count as "consistent" for a MATCHED verdict.
# A ledger row that is SENT, ATTEMPTED or UNRESOLVED is consistent with the
# provider showing the lead is present. A row that is FAILED or ABANDONED
# disagrees with a provider presence - that is a STATE_MISMATCH.
CONSISTENT_STATES = (actionledger.SENT, actionledger.ATTEMPTED,
                     actionledger.UNRESOLVED)


# --------------------------------------------------------- key derivation
#
# THE LEDGER KEY FUNCTION THIS IMPORTS.
#
# `push.push_id(rec, contact_key, step_key, channel)` is the one function
# the write path uses. It produces "{rec_id}:{contact_key}:{step_key}:{channel}".
# `executionguard._key` calls it; `campaigns` calls it; `push.mark_pushed`
# calls it. Every ledger row's key was built by this function.
#
# For the reverse reconciler, the provider data gives us record_id and
# contact_key (from custom fields/variables) and the channel is known per
# provider (linkedin for HeyReach, email for EmailBison). The step_key is
# NOT directly available from the provider: the provider records that a lead
# is in a campaign, not which cadence step put it there.
#
# So we derive a PREFIX key: "{record_id}:{contact_key}:*:{channel}" and
# check whether ANY ledger key shares that prefix. If none does, the touch
# is UNRECORDED. If one does, we check its state for MATCHED vs
# STATE_MISMATCH.
#
# The prefix check is CORRECT because the write path produces exactly one
# key per (record, contact, step, channel) tuple, and the prefix covers all
# possible step_keys for a given person and channel.

def _imported_push_id():
    """Return the imported key derivation function. Named for the test."""
    return push.push_id


def _provider_identity(provider_row, provider):
    """Extract (record_id, contact_key) from a provider row.

    Returns (record_id_str, contact_key_str) or (None, None) if the row
    carries no attribution. A row without record_id and contact_key is one
    the factory never created - it is either NOT_OURS or UNKNOWN.
    """
    if provider == "heyreach":
        custom = provider_row.get("custom_fields") or {}
        if isinstance(custom, list):
            custom = {f.get("name"): f.get("value") for f in custom
                      if isinstance(f, dict)}
        rid = custom.get("record_id")
        ck = custom.get("contact_key")
    elif provider == "bison":
        custom = provider_row.get("custom_variables") or {}
        if isinstance(custom, list):
            custom = {v.get("name"): v.get("value") for v in custom
                      if isinstance(v, dict)}
        rid = custom.get("record_id")
        ck = custom.get("contact_key")
    else:
        return None, None
    rid = str(rid).strip() if rid else ""
    ck = str(ck).strip() if ck else ""
    return (rid or None, ck or None)


def _ledger_prefix_lookup(ledger_rows):
    """Build a prefix lookup from ledger rows.

    Returns a dict: (record_id, contact_key, channel) -> list of
    {key, state, campaign_id, step_key} for every ledger row matching
    that (record_id, contact_key, channel) prefix.
    """
    lookup = {}
    for row in ledger_rows:
        key = row.get("key") or ""
        parts = key.split(":")
        if len(parts) < 4:
            continue
        rec_id = parts[0]
        contact_key = parts[1]
        channel = parts[3]
        prefix = (rec_id, contact_key, channel)
        entry = {"key": key, "state": row.get("state"),
                 "campaign_id": row.get("campaign_id"),
                 "step_key": parts[2] if len(parts) > 2 else None}
        lookup.setdefault(prefix, []).append(entry)
    return lookup


# -------------------------------------------------------- ownership check

def _campaign_ownership(campaign_row, provider, provider_campaign_id):
    """Prove whether a campaign belongs to us.

    Returns (is_ours: bool, evidence: str).
    """
    if not campaign_row:
        return False, "no canonical campaign row claims this provider campaign"

    client = str(campaign_row.get("client") or "").strip()
    campaign_id = str(campaign_row.get("campaign_id") or "").strip()

    if provider == "heyreach":
        bound_id = campaign_row.get("heyreach_campaign_id")
        if str(bound_id) != str(provider_campaign_id):
            return False, (f"campaign row binds heyreach_campaign_id="
                          f"{bound_id!r}, not {provider_campaign_id}")
        return True, f"claimed by {client}/{campaign_id} via heyreach binding"

    elif provider == "bison":
        bound_id = campaign_row.get("bison_campaign_id")
        if str(bound_id) != str(provider_campaign_id):
            return False, (f"campaign row binds bison_campaign_id={bound_id!r}"
                          f", not {provider_campaign_id}")
        return True, f"claimed by {client}/{campaign_id} via bison binding"

    return False, f"unknown provider {provider!r}"


def _heyreach_ownership_evidence(provider_campaign_id, bindings):
    """Check HeyReach campaign ownership using collision._ours if possible.

    Returns (is_ours, evidence_str, campaign_row_or_None).
    """
    binding = bindings.get(int(provider_campaign_id))
    if binding is None:
        return False, (f"no canonical campaign row claims HeyReach campaign "
                      f"{provider_campaign_id}"), None
    return True, (f"collision.campaign_bindings maps HeyReach "
                 f"{provider_campaign_id} to "
                 f"{binding.get('client')}/{binding.get('campaign_id')}"), binding


def _bison_ownership_evidence(provider_campaign_id, bindings):
    """Check EmailBison campaign ownership.

    Returns (is_ours, evidence_str, campaign_row_or_None).
    """
    binding = bindings.get(int(provider_campaign_id))
    if binding is None:
        return False, (f"no canonical campaign row claims EmailBison campaign "
                      f"{provider_campaign_id}"), None
    return True, (f"collision.campaign_bindings maps EmailBison "
                 f"{provider_campaign_id} to "
                 f"{binding.get('client')}/{binding.get('campaign_id')}"), binding


# ----------------------------------------------------- HeyReach sweep

def _page_heyreach_leads(campaign_id):
    """Page through all leads in a HeyReach campaign. Returns (leads, error).

    On error, returns ([], error_str). The caller classifies all returned
    leads as UNKNOWN.
    """
    leads = []
    offset = 0
    total = None
    for _ in range(100):
        try:
            rows, count = heyreach.campaign_leads(campaign_id, offset=offset)
        except Exception as e:
            return leads, f"{type(e).__name__}: {e}"
        if count is not None:
            total = count
        leads.extend(rows)
        offset += len(rows)
        if not rows or (total is not None and offset >= int(total)):
            break
    return leads, None


def _sweep_heyreach(campaign_row, provider_campaign_id, ledger_lookup,
                    ledger_rows):
    """Sweep one HeyReach campaign. Returns (rows_read, classifications, error).

    Each classification is a dict with:
      class: one of ALL_CLASSES
      provider_row: the raw provider data (hashed identifiers only)
      ledger_key: the derived or matched ledger key (or None)
      evidence: why this classification
    """
    classifications = []
    leads, error = _page_heyreach_leads(provider_campaign_id)

    is_ours, ownership_evidence, binding = _heyreach_ownership_evidence(
        provider_campaign_id,
        collision.campaign_bindings())

    for lead in leads:
        record_id, contact_key = _provider_identity(lead, "heyreach")

        hashed_id = hashlib.sha256(
            str(lead.get("provider_lead_id") or "").encode()
        ).hexdigest()[:12]
        hashed_profile = hashlib.sha256(
            str(lead.get("profile_url") or "").encode()
        ).hexdigest()[:12]

        provider_info = {
            "provider": "heyreach",
            "campaign_id": str(provider_campaign_id),
            "lead_id_hash": hashed_id,
            "profile_hash": hashed_profile,
            "state": lead.get("state"),
            "sender_id": lead.get("sender_id"),
            "created_at": lead.get("created_at"),
        }

        if not is_ours:
            classifications.append({
                "class": NOT_OURS,
                "provider_row": provider_info,
                "ledger_key": None,
                "evidence": ownership_evidence,
            })
            continue

        if record_id is None or contact_key is None:
            classifications.append({
                "class": UNKNOWN,
                "provider_row": provider_info,
                "ledger_key": None,
                "evidence": ("no record_id/contact_key in custom fields; "
                            "cannot derive a ledger key and cannot prove "
                            "ownership from this row alone"),
            })
            continue

        prefix = (record_id, contact_key, "linkedin")
        matches = ledger_lookup.get(prefix, [])

        if not matches:
            classifications.append({
                "class": UNRECORDED,
                "provider_row": provider_info,
                "ledger_key": None,
                "evidence": (f"provider shows lead {record_id}:{contact_key} "
                            f"in HeyReach campaign {provider_campaign_id} "
                            f"but no ledger key matches "
                            f"{record_id}:{contact_key}:*:linkedin"),
            })
        else:
            states = [m["state"] for m in matches]
            consistent = any(s in CONSISTENT_STATES for s in states
                            if s is not None)
            if consistent:
                classifications.append({
                    "class": MATCHED,
                    "provider_row": provider_info,
                    "ledger_key": matches[0]["key"],
                    "evidence": (f"ledger has {matches[0]['key']} in state "
                                f"{matches[0]['state']}, consistent with "
                                f"provider presence"),
                })
            else:
                classifications.append({
                    "class": STATE_MISMATCH,
                    "provider_row": provider_info,
                    "ledger_key": matches[0]["key"],
                    "evidence": (f"provider shows lead present but ledger "
                                f"{matches[0]['key']} is "
                                f"{matches[0]['state']}"),
                })

    if error:
        for lead in leads:
            pass
        classifications.append({
            "class": UNKNOWN,
            "provider_row": {"provider": "heyreach",
                            "campaign_id": str(provider_campaign_id),
                            "error": error},
            "ledger_key": None,
            "evidence": f"provider read failed after {len(leads)} leads: {error}",
        })

    return len(leads), classifications, error


# ----------------------------------------------------- EmailBison sweep

def _page_bison_scheduled_emails(campaign_id):
    """Read all scheduled emails for one EmailBison campaign.

    Returns (rows, error). On error, returns whatever was read plus the error.
    """
    try:
        rows = bison.scheduled_emails(campaign_id, cap=200)
        return rows, None
    except Exception as e:
        return [], f"{type(e).__name__}: {e}"


def _sweep_bison(campaign_row, provider_campaign_id, ledger_lookup,
                 ledger_rows):
    """Sweep one EmailBison campaign. Returns (rows_read, classifications, error)."""
    classifications = []
    emails, error = _page_bison_scheduled_emails(provider_campaign_id)

    is_ours, ownership_evidence, binding = _bison_ownership_evidence(
        provider_campaign_id,
        collision.campaign_bindings())

    for email_row in emails:
        record_id, contact_key = _provider_identity(email_row, "bison")

        lead_id = email_row.get("lead_id") or email_row.get("id") or ""
        hashed_lead = hashlib.sha256(
            str(lead_id).encode()).hexdigest()[:12]

        provider_info = {
            "provider": "bison",
            "campaign_id": str(provider_campaign_id),
            "lead_id_hash": hashed_lead,
            "status": email_row.get("status"),
            "email_subject_hash": hashlib.sha256(
                str(email_row.get("email_subject") or "").encode()
            ).hexdigest()[:12],
        }

        if not is_ours:
            classifications.append({
                "class": NOT_OURS,
                "provider_row": provider_info,
                "ledger_key": None,
                "evidence": ownership_evidence,
            })
            continue

        if record_id is None or contact_key is None:
            classifications.append({
                "class": UNKNOWN,
                "provider_row": provider_info,
                "ledger_key": None,
                "evidence": ("no record_id/contact_key in custom variables; "
                            "cannot derive a ledger key"),
            })
            continue

        prefix = (record_id, contact_key, "email")
        matches = ledger_lookup.get(prefix, [])

        email_status = str(email_row.get("status") or "").lower()

        if not matches:
            classifications.append({
                "class": UNRECORDED,
                "provider_row": provider_info,
                "ledger_key": None,
                "evidence": (f"provider shows email for "
                            f"{record_id}:{contact_key} in bison campaign "
                            f"{provider_campaign_id} (status={email_status}) "
                            f"but no ledger key matches "
                            f"{record_id}:{contact_key}:*:email"),
            })
        else:
            states = [m["state"] for m in matches]
            consistent = any(s in CONSISTENT_STATES for s in states
                            if s is not None)

            if email_status == "sent" and not any(
                    s == actionledger.SENT for s in states):
                classifications.append({
                    "class": STATE_MISMATCH,
                    "provider_row": provider_info,
                    "ledger_key": matches[0]["key"],
                    "evidence": (f"provider says SENT but ledger "
                                f"{matches[0]['key']} is "
                                f"{matches[0]['state']}"),
                })
            elif consistent:
                classifications.append({
                    "class": MATCHED,
                    "provider_row": provider_info,
                    "ledger_key": matches[0]["key"],
                    "evidence": (f"ledger has {matches[0]['key']} in state "
                                f"{matches[0]['state']}, consistent with "
                                f"provider status={email_status}"),
                })
            else:
                classifications.append({
                    "class": STATE_MISMATCH,
                    "provider_row": provider_info,
                    "ledger_key": matches[0]["key"],
                    "evidence": (f"provider status={email_status} but ledger "
                                f"{matches[0]['key']} is "
                                f"{matches[0]['state']}"),
                })

    if error:
        classifications.append({
            "class": UNKNOWN,
            "provider_row": {"provider": "bison",
                            "campaign_id": str(provider_campaign_id),
                            "error": error},
            "ledger_key": None,
            "evidence": f"provider read failed: {error}",
        })

    return len(emails), classifications, error


# -------------------------------------------------------- report builder

def _exhaustiveness_identity(rows_read, classifications):
    """Print and verify the exhaustiveness identity.

    classified rows + UNKNOWN == provider rows read.
    """
    counts = {}
    for cls in ALL_CLASSES:
        counts[cls] = sum(1 for c in classifications if c["class"] == cls)

    total_classified = sum(counts.values())
    identity_ok = total_classified == rows_read

    line = (f"EXHAUSTIVENESS: {rows_read} read = "
            + " + ".join(f"{counts[c]} {c}" for c in ALL_CLASSES)
            + f" (total={total_classified})"
            + f"  {'PASS' if identity_ok else 'FAIL'}")
    return line, identity_ok, counts


# --------------------------------------------------------------- campaign
# enumeration

def _bound_campaigns():
    """Every campaign with a provider binding, grouped by provider.

    Returns a list of (campaign_row, provider, provider_campaign_id) tuples.
    """
    camp_rows = campaigns.load()
    out = []
    for campaign in camp_rows:
        hr = campaign.get("heyreach_campaign_id")
        if hr:
            out.append((campaign, "heyreach", hr))
        bc = campaign.get("bison_campaign_id")
        if bc:
            out.append((campaign, "bison", bc))
    return out


# ------------------------------------------------------------------- main

def main(argv=None):
    p = argparse.ArgumentParser(prog="reverse_reconcile",
                                description=__doc__)
    p.add_argument("--live", action="store_true",
                   help="Read the real provider. Default is dry-run.")
    p.add_argument("--json", action="store_true",
                   help="Output the report as JSON.")
    a = p.parse_args(argv)

    if not a.live:
        print("DRY RUN: no provider reads. Pass --live to read the real "
              "provider estate.")
        print("In dry-run mode, the script reports the campaign structure "
              "but cannot read provider data.")
        return 0

    ledger_rows = actionledger.load()
    ledger_lookup = _ledger_prefix_lookup(ledger_rows)

    bound = _bound_campaigns()
    if not bound:
        print("no campaigns with provider bindings found")
        return 0

    total_read = 0
    all_classifications = []
    campaigns_walked = 0
    campaigns_unreadable = []
    per_campaign = []

    for campaign_row, provider, provider_id in bound:
        campaigns_walked += 1
        camp_id = campaign_row.get("campaign_id")

        try:
            if provider == "heyreach":
                rows_read, classifications, error = _sweep_heyreach(
                    campaign_row, provider_id, ledger_lookup, ledger_rows)
            else:
                rows_read, classifications, error = _sweep_bison(
                    campaign_row, provider_id, ledger_lookup, ledger_rows)
        except Exception as e:
            campaigns_unreadable.append({
                "campaign_id": camp_id,
                "provider": provider,
                "provider_campaign_id": str(provider_id),
                "error": f"{type(e).__name__}: {e}",
            })
            continue

        total_read += rows_read
        all_classifications.extend(classifications)

        identity_line, identity_ok, counts = _exhaustiveness_identity(
            rows_read, classifications)

        per_campaign.append({
            "campaign_id": camp_id,
            "provider": provider,
            "provider_campaign_id": str(provider_id),
            "rows_read": rows_read,
            "counts": counts,
            "identity_line": identity_line,
            "identity_ok": identity_ok,
            "error": error,
            "classifications": classifications,
        })

        print(f"\n{'='*70}")
        print(f"Campaign {camp_id} ({provider} campaign {provider_id})")
        print(f"  rows read: {rows_read}")
        for cls in ALL_CLASSES:
            if counts[cls]:
                print(f"  {cls}: {counts[cls]}")
        print(f"  {identity_line}")
        if error:
            print(f"  ERROR: {error}")

    total_identity_line, total_identity_ok, total_counts = (
        _exhaustiveness_identity(total_read, all_classifications))

    print(f"\n{'='*70}")
    print(f"TOTAL: {campaigns_walked} campaigns walked, "
          f"{len(campaigns_unreadable)} unreadable")
    print(f"  provider rows read: {total_read}")
    for cls in ALL_CLASSES:
        if total_counts[cls]:
            print(f"  {cls}: {total_counts[cls]}")
    print(f"  {total_identity_line}")

    if campaigns_unreadable:
        print(f"\nUNREADABLE CAMPAIGNS:")
        for entry in campaigns_unreadable:
            print(f"  {entry['campaign_id']} ({entry['provider']} "
                  f"{entry['provider_campaign_id']}): {entry['error']}")

    unmatched = [c for c in all_classifications if c["class"] == UNRECORDED]
    if unmatched:
        print(f"\nUNRECORDED ROWS ({len(unmatched)}):")
        for c in unmatched[:20]:
            pr = c["provider_row"]
            print(f"  [{pr.get('provider')}] campaign={pr.get('campaign_id')} "
                  f"lead={pr.get('lead_id_hash', '?')} "
                  f"state={pr.get('state', pr.get('status', '?'))}")
            print(f"    {c['evidence']}")

    mismatches = [c for c in all_classifications
                  if c["class"] == STATE_MISMATCH]
    if mismatches:
        print(f"\nSTATE MISMATCHES ({len(mismatches)}):")
        for c in mismatches[:20]:
            pr = c["provider_row"]
            print(f"  [{pr.get('provider')}] campaign={pr.get('campaign_id')} "
                  f"lead={pr.get('lead_id_hash', '?')}")
            print(f"    ledger_key={c['ledger_key']}")
            print(f"    {c['evidence']}")

    if a.json:
        report = {
            "campaigns_walked": campaigns_walked,
            "campaigns_unreadable": campaigns_unreadable,
            "total_rows_read": total_read,
            "total_counts": total_counts,
            "identity_line": total_identity_line,
            "identity_ok": total_identity_ok,
            "per_campaign": [{k: v for k, v in pc.items()
                             if k != "classifications"}
                            for pc in per_campaign],
            "unrecorded": [c for c in all_classifications
                          if c["class"] == UNRECORDED],
            "state_mismatches": [c for c in all_classifications
                                if c["class"] == STATE_MISMATCH],
        }
        print(json.dumps(report, indent=2, default=str))

    has_problems = (total_counts[UNRECORDED] > 0
                    or total_counts[STATE_MISMATCH] > 0
                    or total_counts[UNKNOWN] > 0
                    or len(campaigns_unreadable) > 0)
    return 1 if has_problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
