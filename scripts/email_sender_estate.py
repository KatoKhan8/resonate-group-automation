#!/usr/bin/env python3
"""The email sender estate as three joins the provider never joins for you.

    py -3 scripts/email_sender_estate.py            # the table
    py -3 scripts/email_sender_estate.py --json     # machine-readable

READ-ONLY. Writes nothing to any provider and nothing to canonical state.

## The question this answers

`production_status.py` answers it for ONE mailbox: campaign 487's sender 2736
also serves three other ACTIVE campaigns, so its 15/day is a share rather than
an allowance. That is the right question asked once. This asks it for all 225.

Three facts have to be joined, and the provider publishes them in three places
that do not reference each other:

    WHO      `/sender-emails` gives an inbox a `name`. Several inboxes can
             carry the SAME name on different domains - and that is the whole
             point, because `docs/SENDER-ATTRIBUTION-DESIGN-2026-09-17.md`
             says email's honest ceiling is any number of inboxes belonging to
             exactly ONE attested human. A multi-inbox human is capacity; two
             humans on one campaign is an unattributable send.
    WHERE    No sender field names the campaigns it serves. The only way to
             know is to walk `/campaigns` and ask each ACTIVE one for its
             senders.
    HOW MUCH `emails_sent_count` is a LIFETIME counter and says nothing about
             today. `bison_mailbox_utilisation.py` differences it over time;
             this reads that file if it exists and reports the movement.

## What "free" means here, and what it does not

An inbox attached to NO active campaign is UNCOMMITTED. That is a statement
about contention, NOT a promise of deliverability: three uncommitted inboxes
in this estate have zero lifetime sends, and a mailbox that has never sent is
a reputation risk rather than spare capacity. Both facts are printed and
neither is collapsed into a score.

UNKNOWN IS NEVER 0. A campaign whose senders cannot be read is recorded as
unreadable and its senders are NOT assumed absent - an inbox that looks
uncommitted because a read failed is the most dangerous row this could print.

## PII

An inbox is a real person at the client. Addresses and display names are
hashed in `--json`; the human-readable table prints the name because grouping
inboxes by human is the entire point of it, and this output is for an operator
looking at their own estate. It is not committed.
"""

import argparse
import collections
import hashlib
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src.providers import bison, load_env  # noqa: E402

UTILISATION = os.path.join(ROOT, "work", "bison-mailbox-utilisation.jsonl")


def h(value):
    text = " ".join(str(value or "").split()).lower()
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12] if text else None


def active_campaign_senders():
    """`{campaign_id: [sender_id]}` for every ACTIVE campaign, plus failures.

    Returns `(mapping, unreadable)`. A campaign in `unreadable` is one whose
    sender list could not be read; its mailboxes are NOT counted as free.
    """
    rows, _total = bison._paged(
        "campaigns",
        lambda page: bison.query(f"{bison.base()}/campaigns",
                                 {"page": page, "per_page": 100}))
    mapping, unreadable = {}, []
    for row in rows or []:
        if str(row.get("status") or "").lower() != "active":
            continue
        cid = row.get("id")
        if not cid:
            continue
        try:
            mapping[int(cid)] = [int(s) for s in
                                 (bison.campaign_senders(cid) or [])]
        except Exception as exc:                  # noqa: BLE001 - classified
            unreadable.append({"campaign": int(cid),
                               "error": f"{type(exc).__name__}: {exc}"})
    return mapping, unreadable


def movement():
    """Today's per-sender send movement, or {} when nothing has been sampled."""
    if not os.path.exists(UTILISATION):
        return {}, None
    samples = []
    with open(UTILISATION, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                row = json.loads(line)
                if row.get("ok"):
                    samples.append(row)
    if len(samples) < 2:
        return {}, None
    first, last = samples[0], samples[-1]
    out = {}
    for ident, now in (last.get("senders") or {}).items():
        was = (first.get("senders") or {}).get(ident)
        if not was:
            continue
        a, b = was.get("emails_sent_count"), now.get("emails_sent_count")
        if isinstance(a, int) and isinstance(b, int):
            out[ident] = b - a
    return out, (first["at"], last["at"])


def build():
    senders, meta = bison.sender_emails()
    campaigns, unreadable = active_campaign_senders()
    serves = collections.defaultdict(list)
    for cid, ids in campaigns.items():
        for sid in ids:
            serves[sid].append(cid)
    moved, window = movement()

    humans = collections.defaultdict(list)
    rows = []
    for row in senders:
        sid = row.get("id")
        if sid is None:
            continue
        entry = {
            "id": int(sid),
            "name": row.get("name"),
            "domain": str(row.get("email") or "").split("@")[-1] or None,
            "status": row.get("status"),
            "type": row.get("type"),
            "daily_limit": row.get("daily_limit"),
            "lifetime_sends": row.get("emails_sent_count"),
            "bounced": row.get("bounced_count"),
            "warmup": row.get("warmup_enabled"),
            "active_campaigns": sorted(serves.get(int(sid), [])),
            "moved_in_window": moved.get(str(sid), "UNKNOWN"),
        }
        rows.append(entry)
        humans[str(row.get("name") or "").strip().lower()].append(entry)
    return {"senders": rows, "humans": humans, "window": window,
            "unreadable_campaigns": unreadable,
            "active_campaigns": len(campaigns),
            "roster_total": meta.get("total")}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    load_env(os.path.join(ROOT, "config", ".env"))
    data = build()
    rows = data["senders"]

    if args.json:
        out = []
        for row in rows:
            row = dict(row)
            row["name"] = h(row["name"])
            out.append(row)
        print(json.dumps({"senders": out,
                          "window": data["window"],
                          "active_campaigns": data["active_campaigns"],
                          "unreadable_campaigns": data["unreadable_campaigns"],
                          "roster_total": data["roster_total"]},
                         indent=2, sort_keys=True))
        return 0

    uncommitted = [r for r in rows if not r["active_campaigns"]]
    committed = [r for r in rows if r["active_campaigns"]]
    print(f"=== ESTATE === {len(rows)} inboxes, "
          f"{data['active_campaigns']} ACTIVE campaigns")

    # A DISCONNECTED MAILBOX REPORTS A DAILY LIMIT AND CANNOT SEND. The roster
    # gives every inbox `daily_limit: 15` whatever its status, so a nominal
    # capacity computed from the row count counts inboxes that have not sent in
    # some time and will not send today. Measured 2026-09-17: fifteen of 225
    # read `Not connected`, each with 328-371 lifetime sends, and every one of
    # them moved ZERO over a 6h44m window while 73 others were sending.
    # Reconnecting those fifteen is worth more than any uncommitted mailbox in
    # this estate.
    dead = [r for r in rows if str(r["status"]) != "Connected"]
    live = [r for r in rows if str(r["status"]) == "Connected"]
    nominal = sum(int(r["daily_limit"] or 0) for r in rows)
    real = sum(int(r["daily_limit"] or 0) for r in live)
    print(f"  CONNECTED       {len(live)} inboxes, {real}/day")
    print(f"  NOT CONNECTED   {len(dead)} inboxes, {nominal - real}/day that "
          f"the roster counts and nothing can send")
    if dead:
        by_status = collections.Counter(str(r["status"]) for r in dead)
        print(f"    statuses: {dict(by_status)}")
        print(f"    lifetime sends: "
              f"{sorted(r['lifetime_sends'] or 0 for r in dead)}")
    if data["unreadable_campaigns"]:
        print(f"  UNREADABLE campaigns: {len(data['unreadable_campaigns'])} - "
              f"their senders are NOT counted as free")
        for row in data["unreadable_campaigns"][:5]:
            print(f"    {row['campaign']}: {row['error']}")
    if data["window"]:
        print(f"  send movement window: {data['window'][0]} -> "
              f"{data['window'][1]}")
    else:
        print("  send movement window: UNKNOWN - fewer than two samples in "
              "work/bison-mailbox-utilisation.jsonl")

    print(f"\n=== UNCOMMITTED ({len(uncommitted)}) === attached to no ACTIVE "
          f"campaign. Contention-free, NOT proven deliverable.")
    for row in sorted(uncommitted, key=lambda r: -(r["lifetime_sends"] or 0)):
        never = "  NEVER SENT" if not row["lifetime_sends"] else ""
        print(f"  {row['id']:>5}  {str(row['name'])[:24]:<24} "
              f"{str(row['domain'])[:28]:<28} {str(row['status'])[:10]:<10} "
              f"limit {row['daily_limit']}  lifetime "
              f"{row['lifetime_sends']}  bounced {row['bounced']}{never}")

    print(f"\n=== HUMANS WITH MORE THAN ONE INBOX ===")
    print("  The unit email can attribute is a HUMAN, not a mailbox. These are")
    print("  the only groupings where a campaign may hold several inboxes.")
    multi = {k: v for k, v in data["humans"].items() if len(v) > 1 and k}
    for name, entries in sorted(multi.items()):
        total_free = sum(1 for e in entries if not e["active_campaigns"])
        print(f"  {name[:30]:<30} {len(entries)} inboxes, {total_free} "
              f"uncommitted")
        for entry in sorted(entries, key=lambda e: e["id"]):
            print(f"      {entry['id']:>5} {str(entry['domain'])[:28]:<28} "
                  f"lifetime {str(entry['lifetime_sends']):>6}  "
                  f"campaigns {entry['active_campaigns'] or '-'}")

    print(f"\n=== MOVED IN WINDOW ===")
    sending = [r for r in rows if isinstance(r["moved_in_window"], int)
               and r["moved_in_window"] > 0]
    if not data["window"]:
        print("  UNKNOWN")
    else:
        print(f"  {len(sending)} of {len(rows)} inboxes sent anything at all")
        for row in sorted(sending, key=lambda r: -r["moved_in_window"])[:15]:
            print(f"  {row['id']:>5}  {str(row['name'])[:24]:<24} "
                  f"+{row['moved_in_window']:<4} of {row['daily_limit']}/day  "
                  f"campaigns {row['active_campaigns']}")

    # MEASURED HEADROOM BY HUMAN, which is the only capacity number that means
    # anything for this system. A campaign may hold several inboxes belonging
    # to exactly ONE attested human without becoming unattributable, so the
    # unit capacity is planned in is a PERSON and not a mailbox - and neither
    # the roster nor `production_status` had ever grouped it that way.
    #
    # `used` is measured from the utilisation samples, so a human with no
    # samples reads zero used and full headroom. That is why the window is
    # printed above it: an unsampled estate would otherwise look entirely free.
    if data["window"]:
        print(f"\n=== MEASURED HEADROOM BY HUMAN ===")
        print("  cap/day counts CONNECTED inboxes only. `used` is what moved "
              "in the window above,")
        print("  so a short window understates use and overstates headroom. "
              "Read it against the window.")
        print(f"  {'human':<16}{'inbox':>6}{'conn':>6}{'cap/day':>9}"
              f"{'used':>6}{'headroom':>10}{'idle mb':>9}")
        people = collections.defaultdict(
            lambda: {"inboxes": 0, "connected": 0, "limit": 0, "used": 0,
                     "idle": 0})
        for row in rows:
            entry = people[h(row["name"]) or "unnamed"]
            entry["inboxes"] += 1
            if str(row["status"]) != "Connected":
                continue
            entry["connected"] += 1
            entry["limit"] += int(row["daily_limit"] or 0)
            moved = row["moved_in_window"]
            if isinstance(moved, int):
                entry["used"] += moved
                if moved == 0:
                    entry["idle"] += 1
        total = collections.Counter()
        for name, entry in sorted(people.items(),
                                  key=lambda kv: -(kv[1]["limit"]
                                                   - kv[1]["used"])):
            head = entry["limit"] - entry["used"]
            total["limit"] += entry["limit"]
            total["used"] += entry["used"]
            total["idle"] += entry["idle"]
            print(f"  {name:<16}{entry['inboxes']:>6}{entry['connected']:>6}"
                  f"{entry['limit']:>9}{entry['used']:>6}{head:>10}"
                  f"{entry['idle']:>9}")
        print(f"  {'TOTAL':<16}{'':>6}{'':>6}{total['limit']:>9}"
              f"{total['used']:>6}{total['limit'] - total['used']:>10}"
              f"{total['idle']:>9}")

    print(f"\n=== COMMITTED, BY CONTENTION ===")
    for row in sorted(committed, key=lambda r: -len(r["active_campaigns"]))[:12]:
        print(f"  {row['id']:>5}  {str(row['name'])[:24]:<24} "
              f"{len(row['active_campaigns'])} active campaigns "
              f"{row['active_campaigns'][:6]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
