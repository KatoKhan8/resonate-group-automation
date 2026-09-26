#!/usr/bin/env python3
"""Register a Resonate-owned provider campaign that has no row in
work/campaigns.jsonl yet.

## Why this exists

Operator decision, 2026-09-26 evening: ownership must not depend on a name
prefix. The source of truth for "did WE create this campaign" is
work/campaigns.jsonl - the record our own factory writes when it creates a
campaign - and the RESONATE name prefix is a fallback only, used when a
campaign was created outside the normal flow (measured: 503/504/505 ARE
already in campaigns.jsonl despite not carrying the prefix, so the prefix
had been silently overriding our own internal record in provider_truth's
classification).

This script closes the other direction of the same gap: a campaign the
provider confirms is ours (RESONATE-prefixed, or explicitly named to this
script) but that our own internal ledger never recorded, because it was
created by a seat-per-inbox process or a manual test rather than through
`campaigns.new_campaign()`. An unregistered real campaign is invisible to
every tool that reads campaigns.jsonl as the list of "what we made."

READ-ONLY toward the providers. It reads `docs/state/PROVIDER-CAMPAIGNS.json`
(already a provider readback, not a live call) and writes only to
work/campaigns.jsonl, through `src/campaigns.py`'s locked, merge-safe
`save()` - never a direct file write, per CLAUDE.md's rule that queue and
campaign state are touched through the store modules or nowhere.

## What a backfilled row means, and does not mean

A row this script creates records "the provider confirms this campaign
exists and is ours" - nothing more. It does NOT mean this campaign was
launched, approved, or sent through our normal flow; `launch.state` is set
to `"launched"` only when the provider's own status says the campaign is
running or finished (never inferred from absence), and every backfilled row
carries `"backfilled_from_provider_truth"` with the source timestamp, so
nobody mistakes a discovered fact for a decision our own workflow made.
"""
import argparse
import json
import os
import sys
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import campaigns  # noqa: E402

PROVIDER_SNAPSHOT = os.path.join(ROOT, "docs", "state", "PROVIDER-CAMPAIGNS.json")

#: HeyReach classification -> our campaign status vocabulary. Conservative:
#: an in-progress provider campaign is "running", a finished one is
#: "completed", anything else is left as "draft" rather than guessed into a
#: state our own workflow never put it through.
HEYREACH_STATUS_MAP = {
    "LIVE": campaigns.RUNNING,
    "FINISHED": campaigns.COMPLETED,
}

#: EmailBison provider status -> our vocabulary. "archived" has no exact
#: match in ours; the closest honest reading is "completed" (retired, not
#: sending), never "draft" or "paused" which would imply it could resume.
BISON_STATUS_MAP = {
    "active": campaigns.RUNNING,
    "paused": campaigns.PAUSED,
    "completed": campaigns.COMPLETED,
    "archived": campaigns.COMPLETED,
}


def _slug_for_heyreach(name, hr_id):
    """A readable internal id. Not the provider id - ours, for our records."""
    low = (name or "").strip().lower()
    if "li b1 seat" in low:
        seat = low.rsplit(" ", 1)[-1]
        return "productive-li-b1-seat-%s" % seat
    if "stop test" in low:
        return "productive-linkedin-stoptest-%s" % hr_id
    safe = "".join(c if c.isalnum() else "-" for c in low).strip("-")
    while "--" in safe:
        safe = safe.replace("--", "-")
    return ("productive-heyreach-%s-%s" % (hr_id, safe))[:80]


def _slug_for_bison(name, bison_id):
    low = (name or "").strip().lower()
    safe = "".join(c if c.isalnum() else "-" for c in low).strip("-")
    while "--" in safe:
        safe = safe.replace("--", "-")
    return ("productive-bison-%s-%s" % (bison_id, safe))[:80]


def missing_heyreach(snapshot_doc, existing_ids):
    out = []
    for m in (snapshot_doc.get("heyreach") or {}).get("resonate_campaigns") or []:
        hr_id = m.get("heyreach_campaign_id")
        if hr_id is None or int(hr_id) in existing_ids:
            continue
        out.append(m)
    return out


def missing_bison(snapshot_doc, existing_ids):
    out = []
    for c in (snapshot_doc.get("emailbison") or {}).get("campaigns") or []:
        if c.get("owner") != "resonate":
            continue
        bid = c.get("bison_campaign_id")
        if bid is None or int(bid) in existing_ids:
            continue
        out.append(c)
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true",
                        help="Report what would be registered; write nothing.")
    args = parser.parse_args(argv)

    with open(PROVIDER_SNAPSHOT, encoding="utf-8") as fh:
        snap_doc = json.load(fh)
    snap_at = snap_doc.get("generated_at")

    rows = campaigns.load()
    existing_hr = {int(r["heyreach_campaign_id"]) for r in rows
                  if r.get("heyreach_campaign_id") is not None}
    existing_bison = {int(r["bison_campaign_id"]) for r in rows
                      if r.get("bison_campaign_id") is not None}

    to_add_hr = missing_heyreach(snap_doc, existing_hr)
    to_add_bison = missing_bison(snap_doc, existing_bison)

    if not to_add_hr and not to_add_bison:
        print("Nothing to backfill: every Resonate-owned campaign in "
              "%s already has a row in %s" % (PROVIDER_SNAPSHOT, campaigns.path()))
        return 0

    registered = []
    for m in to_add_hr:
        hr_id = int(m["heyreach_campaign_id"])
        name = m.get("name") or ""
        cid = _slug_for_heyreach(name, hr_id)
        row = campaigns.new_campaign(
            cid, client="productive", name=name,
            created_by="scripts/backfill_resonate_campaigns.py")
        row["heyreach_campaign_id"] = hr_id
        status = HEYREACH_STATUS_MAP.get(m.get("classification"), campaigns.DRAFT)
        row["status"] = status
        row["launch"] = {
            "state": ("launched" if status in (campaigns.RUNNING, campaigns.COMPLETED)
                     else "not_launched"),
            "at": None,
        }
        row["backfilled_from_provider_truth"] = {
            "source": PROVIDER_SNAPSHOT,
            "source_generated_at": snap_at,
            "provider_classification": m.get("classification"),
            "backfilled_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "reason": "Resonate-owned per provider read; no internal record existed",
        }
        rows.append(row)
        registered.append(("heyreach", hr_id, cid, name, status))

    for c in to_add_bison:
        bid = int(c["bison_campaign_id"])
        name = c.get("name") or ""
        cid = _slug_for_bison(name, bid)
        row = campaigns.new_campaign(
            cid, client="productive", name=name,
            created_by="scripts/backfill_resonate_campaigns.py")
        row["bison_campaign_id"] = bid
        status = BISON_STATUS_MAP.get((c.get("status") or "").lower(), campaigns.DRAFT)
        row["status"] = status
        row["launch"] = {
            "state": ("launched"
                     if status in (campaigns.RUNNING, campaigns.PAUSED,
                                   campaigns.COMPLETED)
                     else "not_launched"),
            "at": None,
        }
        row["backfilled_from_provider_truth"] = {
            "source": PROVIDER_SNAPSHOT,
            "source_generated_at": snap_at,
            "provider_status": c.get("status"),
            "backfilled_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "reason": "Resonate-owned per provider read; no internal record existed",
        }
        rows.append(row)
        registered.append(("bison", bid, cid, name, status))

    print("Registering %d campaign(s) missing from %s, per %s (%s):"
          % (len(registered), campaigns.path(), PROVIDER_SNAPSHOT, snap_at))
    for provider, pid, cid, name, status in registered:
        print("  %-9s %-8s %-40s status=%s  ->  %s" % (provider, pid, cid, status, name))

    if args.dry_run:
        print("\n--dry-run: nothing written.")
        return 0

    campaigns.save(rows)
    print("\nWritten. %d row(s) now in %s." % (len(rows), campaigns.path()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
