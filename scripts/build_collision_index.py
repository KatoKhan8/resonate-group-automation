#!/usr/bin/env python3
"""Every lead of every campaign, from the PROVIDERS. READ ONLY.

Operator, 2026-09-30: read every lead of every campaign in EmailBison (ours
and the client's) and HeyReach, and build a contacted index keyed by email
and by company domain, with campaign id, owner, status, emails sent and last
touch date.

WHY THE LOCAL LEDGER CANNOT ANSWER THIS. `CLAUDE.md` records the
measurement: across our campaigns the provider confirms 912 sends against
ONE recorded touch in 1,582 records, because the code that ingests sent
events had zero production callers. Measured again 2026-09-30 on the first
33 qualified candidates: the ledger called every one of them never
contacted, and the provider said all 33 had been emailed, most 22 or 23
times. So the index is built from provider reads and from nothing else.

UNKNOWN IS NOT CLEAR. A campaign whose walk is incomplete - a page cap, a
timeout, an error - is recorded as INCOMPLETE, and any domain or address
that depends on it is UNKNOWN rather than absent. `senderheadroom`'s rule
applies: a partial walk can only UNDERCOUNT, so "not found" is only true
from a complete one.

Output goes to `work/`, which is gitignored, because it is 33,887 real
people and it is not ours to publish.

    py -3 scripts/build_collision_index.py
    py -3 scripts/build_collision_index.py --limit 5     # first N campaigns
"""
import argparse
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import store
from src.providers import bison

#: The client's own EmailBison campaigns, per CLAUDE.md. Everything else in
#: this workspace is ours. Recorded as data so the report can say who was
#: already talking to somebody.
CLIENT_EMAIL_CAMPAIGNS = {327, 328, 352, 418}

#: A sequence the provider says is running NOW. These are the ones that make
#: a domain untouchable today rather than historically.
ACTIVE_STATUSES = {"in_sequence", "active", "sending", "queued"}


def out_path():
    return os.path.abspath(
        os.path.join(os.path.dirname(store.queue_path()),
                     "collision-index.json"))


def _domain_of(email):
    return (email or "").split("@")[-1].strip().lower()


def _walk_campaign_leads(campaign_id):
    """Every lead row in one campaign. Returns (rows, complete)."""
    rows, complete = [], True
    try:
        # A HIGH CAP, BECAUSE THIS READ EXISTS TO BE COMPLETE.
        #
        # `bison.PAGE_CAP` is 40 and the client's own campaigns are far
        # bigger - 265 alone needs 115 pages. Measured 2026-09-30: the first
        # build of this index read ZERO leads from 327, 328, 352 and 274,
        # the four campaigns that matter most, and then reported two people
        # as never contacted who are both in 328 `in_sequence`. An index
        # that silently omits the biggest campaigns produces FALSE CLEARS,
        # which is the one error this file must never make.
        page_rows, _total = bison._paged(
            "collision-index",
            lambda page: bison.query(bison.leads_endpoint(campaign_id),
                                     {"page": page}),
            cap=bison.CAMPAIGN_QUEUE_PAGE_CAP)
        rows = [r for r in page_rows if isinstance(r, dict)]
    except Exception as exc:                                  # noqa: BLE001
        complete = False
        rows = []
        print("   campaign %s INCOMPLETE: %s %s"
              % (campaign_id, type(exc).__name__, str(exc)[:80]))
    return rows, complete


def build(limit=None):
    index = {"generated_at": datetime.datetime.now(
                 datetime.timezone.utc).replace(microsecond=0).isoformat(),
             "source": "EmailBison + HeyReach public APIs, read-only",
             "by_email": {}, "by_domain": {},
             "campaigns": {}, "incomplete": [], "heyreach": {}}

    try:
        campaigns, _total = bison.list_all_campaigns()
    except Exception as exc:                                  # noqa: BLE001
        print("FATAL: cannot list EmailBison campaigns: %s" % exc)
        return index
    print("EmailBison campaigns: %d" % len(campaigns))

    for n, camp in enumerate(campaigns, 1):
        cid = camp.get("id")
        if cid is None:
            continue
        if limit and n > limit:
            index["incomplete"].append(
                {"campaign": cid, "why": "past --limit, not walked"})
            continue
        owner = "client" if int(cid) in CLIENT_EMAIL_CAMPAIGNS else "ours"
        rows, complete = _walk_campaign_leads(cid)
        index["campaigns"][str(cid)] = {
            "name": camp.get("name"), "status": camp.get("status"),
            "owner": owner, "leads_read": len(rows), "complete": complete}
        if not complete:
            index["incomplete"].append({"campaign": cid,
                                        "why": "walk did not complete"})
        print("  [%2d/%2d] %-6s %-8s %-38s leads=%d%s"
              % (n, len(campaigns), cid, owner,
                 str(camp.get("name"))[:36], len(rows),
                 "" if complete else "  INCOMPLETE"))
        for row in rows:
            email = (row.get("email") or "").strip().lower()
            if not email:
                continue
            domain = _domain_of(email)
            stats = row.get("overall_stats") or {}
            touches = []
            for d in row.get("lead_campaign_data") or []:
                touches.append({
                    "campaign": d.get("campaign_id"),
                    "owner": ("client"
                              if int(d.get("campaign_id") or 0)
                              in CLIENT_EMAIL_CAMPAIGNS else "ours"),
                    "status": d.get("status"),
                    "emails_sent": d.get("emails_sent")})
            entry = index["by_email"].setdefault(
                email, {"domain": domain, "company": row.get("company"),
                        "emails_sent": 0, "touches": [],
                        "last_touch": None})
            entry["emails_sent"] = max(entry["emails_sent"],
                                       int(stats.get("emails_sent") or 0))
            entry["last_touch"] = (row.get("updated_at")
                                   or entry["last_touch"])
            for t in touches:
                if t not in entry["touches"]:
                    entry["touches"].append(t)
            dom = index["by_domain"].setdefault(
                domain, {"people": 0, "emails_sent": 0, "campaigns": [],
                         "active": False, "last_touch": None})
            dom["people"] += 1
            dom["emails_sent"] += int(stats.get("emails_sent") or 0)
            if row.get("updated_at") and (
                    not dom["last_touch"]
                    or row["updated_at"] > dom["last_touch"]):
                dom["last_touch"] = row["updated_at"]
            for t in touches:
                if t["campaign"] not in [c["campaign"]
                                         for c in dom["campaigns"]]:
                    dom["campaigns"].append(t)
                if str(t.get("status") or "").lower() in ACTIVE_STATUSES:
                    dom["active"] = True

    # HeyReach. It timed out on 2026-09-30; absence is recorded as UNKNOWN.
    try:
        from src.providers import heyreach
        index["heyreach"] = {"read": False,
                             "why": "not walked in this pass - EmailBison "
                                    "first; HeyReach timed out 2026-09-30"}
    except Exception as exc:                                  # noqa: BLE001
        index["heyreach"] = {"read": False, "why": str(exc)[:120]}

    return index


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--limit", type=int, default=None,
                    help="walk only the first N campaigns")
    args = ap.parse_args()
    index = build(args.limit)
    path = out_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(index, f, indent=1, sort_keys=True)
    print()
    print("people indexed : %d" % len(index["by_email"]))
    print("domains indexed: %d" % len(index["by_domain"]))
    print("incomplete     : %d" % len(index["incomplete"]))
    print("written to     : %s  (gitignored)" % path)


if __name__ == "__main__":
    main()
