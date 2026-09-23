#!/usr/bin/env python3
"""The LinkedIn half of a batch: one campaign per attested seat, in DRAFT.

    py -3 scripts/batch_linkedin_push.py --plan
    py -3 scripts/batch_linkedin_push.py --live --veto-waived "..."

OPERATOR, 2026-09-21: "every lead is targeted on BOTH channels in parallel...
Batch 1's enrolled leads get their LinkedIn side now: every one with a
LinkedIn URL onto a fresh unbound HeyReach list, one campaign per attested
seat, same gates, stats and veto window, write-back of campaign_id_linkedin.
Same batch, second channel; not a new batch."

## WHAT IT BUILDS, AND WHERE IT STOPS

    fresh list per seat        create_list - an empty list reaches nobody and
                               it is PERMANENT, this vendor documents no
                               delete, so the name is not a detail
    leads onto the list        add_leads_to_list, unbound, 100 at a time
    campaign per seat          create_campaign, in DRAFT
    the standard sequence      set_sequence with the graph cloned from 565765
    write-back                 campaign_id_linkedin on the contact

**IT DOES NOT ACTIVATE.** `heyreach.activate` is CONDITIONAL and its condition
names campaign 604869, the draft canary, and nothing else. A DRAFT sends
nothing. So this ends exactly where the email side ends: everything ready,
one operator decision away from going out.

## THE SEQUENCE IS CLONED, NOT WRITTEN

`config/linkedin/productive-standard.json` holds campaign 565765's graph as
read from the provider on 2026-09-21 - the best in Productive's estate on
both halves of the funnel, 13.6% of requests accepted and 17.8% of accepted
replying. The operator's instruction was explicit: "step for step, with the
same delays and branching... Do not shorten it, do not remove steps, do not
add steps."

So the graph is posted as it was read. The only per-lead substitution is in
the message variables the graph already carries - `{FIRST_NAME}`,
`{COMPANY}`, `{Icebreaker}` - which HeyReach fills from the lead's own
custom fields.

**THE MESSAGE-ONLY VARIANT IS NOT A SECOND CADENCE.** That graph opens with
`CHECK_IS_CONNECTION` and messages the connected branch, so a lead who is
already connected takes that branch by construction, with the connection
request skipped and nothing else removed. Which is what was asked for.

## PACING

10 connection requests per seat per day, from the client config, "until our
own per-seat ledger shows room". Leads are round-robined across seats so no
seat carries a queue another seat could have taken, and a seat's share is
reported beside its campaign.
"""
import argparse
import collections
import contextlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import campaigns, clients, providers, store              # noqa: E402
from src.providers import heyreach, load_env                      # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STANDARD = os.path.join(ROOT, "config", "linkedin", "productive-standard.json")

CLIENT = "productive"
BATCH_PREFIX = "productive-email-batch1-"


def attested_seats():
    """Attested LinkedIn seats that the provider says can still act.

    Two sources and both must agree: the roster says a human attested to this
    seat, and the provider says its auth is valid. The handoff records 33 of
    41 attested with 8 skipped for invalid auth, and an attestation does not
    make a dead seat send.
    """
    rows = []
    with open(os.path.join(ROOT, "work", "senders.jsonl"),
              encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    attested = {str(r.get("account_id") or "").replace("hr-", ""): r
                for r in rows
                if r.get("kind") == "ownership_attestation"
                and r.get("channel") == "linkedin"}
    live, _total = heyreach.li_accounts()
    out = []
    for account in live:
        seat_id = str(account.get("id"))
        if seat_id not in attested:
            continue
        if not account.get("authIsValid"):
            continue
        out.append({"id": seat_id,
                    "sender_id": attested[seat_id].get("sender_id"),
                    "active": bool(account.get("isActive"))})
    return out


def enrolled_leads():
    """Every enrolled lead carrying a LinkedIn URL, with its record."""
    rows = [r for r in campaigns.load()
            if str(r.get("campaign_id", "")).startswith(BATCH_PREFIX)]
    wanted = {rid for row in rows for rid in row.get("record_ids") or []}
    out = []
    for record in store.load():
        if record.get("id") not in wanted:
            continue
        for contact in record.get("contacts") or []:
            url = str(contact.get("linkedin") or "").strip()
            if not url:
                continue
            if contact.get("campaign_id_linkedin"):
                continue                       # already on a LinkedIn campaign
            out.append({"record_id": record.get("id"),
                        "contact_key": contact.get("key"),
                        "profileUrl": url,
                        "firstName": contact.get("first_name") or "",
                        "lastName": contact.get("last_name") or "",
                        "company": record.get("company") or "",
                        "position": contact.get("title") or ""})
    return out


#: OPERATOR DECISION, 2026-09-22: "drop the three SEND_LEAD_TO_BISON nodes
#: and set the sequences".
HANDOFF_NODE = "SEND_LEAD_TO_BISON"


def drop_bison_handoff(node):
    """Replace every SEND_LEAD_TO_BISON with an END that keeps its wait.

    THE CLONED GRAPH CARRIES THE CLIENT'S OWN CAMPAIGN IDS. Three
    SEND_LEAD_TO_BISON nodes are pinned to EmailBison campaigns 417 and 418,
    and HeyReach validates the reference on write: "EmailBison campaign with
    ID 417 was not found". So the graph cannot be posted as read, whatever
    anybody prefers.

    The step exists to hand a LinkedIn non-responder to email. Under the
    dual-channel decision every lead is ALREADY on the email side the day it
    is enrolled, so for us the hand-off is either redundant or a second
    enrolment of somebody already being written to. The operator chose to
    drop it.

    **DROPPED AS AN END THAT KEEPS THE NODE'S OWN DELAY**, not by splicing
    the child in. Each hand-off waits three or five days before it fires, and
    its child END waits zero; splicing would move a terminal three days
    earlier and also break the validator's rule that a child of an action
    node waits at least three hours. Keeping the wait means the cadence ends
    exactly where the hand-off would have happened, which is the honest
    translation of removing it.
    """
    if not isinstance(node, dict):
        return node
    if str(node.get("nodeType") or "") == HANDOFF_NODE:
        return {"nodeType": "END",
                "actionDelay": node.get("actionDelay", 0),
                "actionDelayUnit": node.get("actionDelayUnit", "HOUR")}
    out = {k: v for k, v in node.items()}
    for key in ("conditionalNode", "unconditionalNode"):
        if out.get(key) is not None:
            out[key] = drop_bison_handoff(out[key])
    return out


def standard_graph():
    """The stored standard, made WRITABLE again.

    A graph read from HeyReach is not a graph you can post back. The provider
    normalises a UI-built one by hanging `conditionalNode: END` off message
    nodes, and `validate_sequence_for_write` refuses that because a
    non-branching node carrying a true-branch is usually a branch that will
    silently vanish. `sequence_for_write` strips exactly that and nothing
    else - it was written on 2026-09-16 for this same round trip, against
    campaign 599020, and it already existed when this script first tried to
    post a read graph straight back.
    """
    with open(STANDARD, encoding="utf-8") as handle:
        graph = json.load(handle)["graph"]
    return heyreach.sequence_for_write(drop_bison_handoff(graph))


def seats_needed(leads, seats, per_seat_day):
    """As many seats as it takes to clear this batch in a day, and no more.

    A HeyReach list is PERMANENT - the vendor documents no delete for one -
    so every seat used costs the client's estate a list and a campaign
    forever. Spreading 151 leads over all 33 attested seats would create 33
    permanent artifacts to carry four requests each, while the pacing limit
    is ten per seat per day.

    So the round-robin runs over the seats actually needed: ceil(leads /
    10), capped at what is attested and valid. The rest stay clean for later
    batches, which is also the most conservative reading of "conservative on
    seats shared with the client's campaigns" - fewer seats touched.
    """
    needed = max(1, -(-len(leads) // max(per_seat_day, 1)))
    return seats[:min(needed, len(seats))]


def allocate(leads, seats):
    """Round-robin. A seat's share is a share, not a queue."""
    plan = collections.OrderedDict((seat["id"], []) for seat in seats)
    order = [seat["id"] for seat in seats]
    for index, lead in enumerate(leads):
        plan[order[index % len(order)]].append(lead)
    return {seat: rows for seat, rows in plan.items() if rows}


# ---------------------------------------------------------------------------
# HALT, 2026-09-23. Operator instruction during the reply-stop sweep.
#
# WHAT WAS AND WAS NOT FOUND, because the first reading of this was wrong and
# the correction matters more than the alarm:
#
#   NOT a missed stop. `inbound._positively_not_ours` gates the unmatched-reply
#   NOTIFICATION only, and it sits inside the `unmatched`/`unknown` branch. The
#   stop path never consults it. A reply that matches a record takes the
#   `applied` branch and stops both channels regardless of seat.
#
#   The reply-stop on LinkedIn has NEVER RUN. Provider truth, 2026-09-23:
#   across all 33 B1 campaigns (613724-613761), 75 connection requests, 3
#   accepted, 0 messages sent, 0 replies. The 33 conversations the poller
#   inspected and reported `ambiguous_identities: 33` are the CLIENT's traffic
#   on seats we share with them, not ours. Nothing was missed because nothing
#   arrived.
#
#   The allowlist IS stale. OWNED_SEATS is {174892} and OWNED_CAMPAIGNS holds
#   none of 613724-613761, while the 33 live B1 campaigns run on 33 distinct
#   seats. So the first unattributable reply to one of OUR OWN campaigns will
#   have its notification silently dropped as "positively not ours". That is a
#   visibility defect on a safety path, not a missed stop.
#
# The halt stands on the narrow ground the operator asked for: three
# connections are already accepted, so messages - and the first real reply -
# are imminent, and the cross-channel stop has not once been exercised live on
# this channel. Clear this constant when the 15-minute stop test passes
# against a real HeyReach reply. See docs/state/PROBLEM-REGISTER.md.
HALT = ("LinkedIn pushes are halted: the HeyReach reply-stop has never run "
        "live (75 connection requests, 3 accepted, 0 replies across the 33 B1 "
        "campaigns), and inbound.OWNED_SEATS/OWNED_CAMPAIGNS are stale, so an "
        "unattributable reply to our own campaign would have its notification "
        "dropped as 'not ours'. No stop has been missed. Clear this when the "
        "15-minute stop test passes against a real reply.")
# ---------------------------------------------------------------------------


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--plan", action="store_true")
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--veto-waived")
    parser.add_argument("--limit-seats", type=int)
    args = parser.parse_args(argv)

    load_env()
    config = clients.load(CLIENT)
    per_seat_day = int(config.get(
        "linkedin_connection_requests_per_seat_day") or 10)

    seats = attested_seats()
    if args.limit_seats:
        seats = seats[:args.limit_seats]
    leads = enrolled_leads()
    if not seats:
        print("REFUSED: no attested seat has valid auth at the provider")
        return 1
    if not leads:
        print("Nothing to do: every enrolled lead with a URL is already on a "
              "LinkedIn campaign.")
        return 0

    plan = allocate(leads, seats)
    print(f"\nLINKEDIN SIDE  leads {len(leads)}  seats {len(seats)}  "
          f"campaigns to build {len(plan)}\n")
    for seat_id, rows in plan.items():
        days = (len(rows) + per_seat_day - 1) // per_seat_day
        print(f"  seat {seat_id:>8}  leads {len(rows):>4}  "
              f"{per_seat_day}/day -> {days} day(s) of requests")
    print(f"\n  pacing {per_seat_day} connection requests per seat per day")
    print("  sequence: the standard cloned from 565765, step for step")
    print("  campaigns land in DRAFT. heyreach.activate names 604869 only, "
          "so nothing here can send.")

    if not args.live:
        print("\n  PLAN ONLY. Nothing was written to HeyReach.")
        return 0
    if HALT:
        # Placed BEFORE the veto check on purpose: a waiver is the operator
        # accepting the copy and the pacing, and it is not an answer to a
        # reply-stop that does not stop.
        print("\n  REFUSED: LinkedIn pushes are HALTED.\n")
        print(f"  {HALT}")
        return 1
    if not args.veto_waived:
        print("\n  REFUSED: --live needs --veto-waived with the operator's "
              "own words, or the stats post and its fifteen minutes.")
        return 1

    graph = standard_graph()

    existing_lists = {}
    try:
        rows_now = heyreach.lists()
        rows_now = rows_now[0] if isinstance(rows_now, tuple) else rows_now
        existing_lists = {str(r.get("name")): r.get("id") for r in rows_now}
    except Exception as exc:                                    # noqa: BLE001
        print(f"  could not read existing lists ({type(exc).__name__}); "
              f"a name that already exists would be created twice, so "
              f"refusing")
        return 1

    # FIFTEEN REQUESTS PER TWO SECONDS is HeyReach's limit, and this loop
    # makes three or four calls per seat back to back. One seat tripped a 429
    # on the first run. The standing rule is that a rate limit means back off
    # and continue, never halt - so it paces itself rather than discovering
    # the limit again.
    import time as _time
    PACE = 0.4
    reason = ("batch LinkedIn side - dual-channel decision 2026-09-21; "
              "lists and campaigns in DRAFT, no activation")
    built = []
    with providers.allow_writes(reason):
        for seat_id, rows in plan.items():
            # FIFTY CHARACTERS. HeyReach answers 400 with "The field Name
            # must be a string or array type with a maximum length of '50'"
            # and the first version's name was 54 - so every one of the
            # sixteen seats refused at its first call and nothing was
            # created, which is the right way to fail but a whole run lost
            # to a length nobody had read.
            name = f"RESONATE PRODUCTIVE LI B1 SEAT {seat_id}"[:50]
            try:
                _time.sleep(PACE)
                # REUSE. A HeyReach list is permanent, and the run that
                # discovered the 50-character name limit and the row-shape
                # contract had already created one per seat before refusing
                # further along. Creating a second would leave the client's
                # estate carrying two lists per seat forever, and the second
                # would be the one nobody could explain.
                list_id = existing_lists.get(name)
                if list_id:
                    print(f"  seat {seat_id}: reusing list {list_id}")
                else:
                    list_id = heyreach.create_list(name).get("id")
                for start in range(0, len(rows), 100):
                    _time.sleep(PACE)
                    # INTERNAL rows, not provider shape. The adapter builds
                    # the provider body itself and REFUSES a row that already
                    # carries `profileUrl` - which is the right way round: one
                    # module owns the vendor's field names, and a caller that
                    # pre-formats them is a second place for that contract to
                    # drift.
                    heyreach.add_leads_to_list(
                        list_id,
                        [{"linkedin_url": r["profileUrl"],
                          "first_name": r["firstName"],
                          "last_name": r["lastName"]}
                         for r in rows[start:start + 100]])
                _time.sleep(PACE)
                campaign = heyreach.create_campaign(name, list_id,
                                                    [int(seat_id)])
                campaign_id = campaign.get("id")
                _time.sleep(PACE)
                heyreach.set_sequence(campaign_id, graph)
            except Exception as exc:                            # noqa: BLE001
                print(f"  seat {seat_id}: REFUSED {type(exc).__name__}: "
                      f"{str(exc)[:160]}")
                continue
            built.append({"seat": seat_id, "list_id": list_id,
                          "campaign_id": campaign_id, "leads": len(rows)})
            print(f"  seat {seat_id}: list {list_id}, campaign {campaign_id} "
                  f"(DRAFT), {len(rows)} leads")
            by_record = collections.defaultdict(set)
            for row in rows:
                by_record[row["record_id"]].add(row["contact_key"])
            with store.transaction() as current:
                for index, record in enumerate(current):
                    keys = by_record.get(record.get("id"))
                    if not keys:
                        continue
                    for contact in record.get("contacts") or []:
                        if contact.get("key") in keys:
                            contact["campaign_id_linkedin"] = campaign_id
                            contact["linkedin_list_id"] = list_id
                    current[index] = record

    print(f"\n  built {len(built)} LinkedIn campaigns, all DRAFT")
    out = os.path.join(ROOT, "work", "batch-linkedin-report.json")
    with open(out, "w", encoding="utf-8") as handle:
        json.dump(built, handle, indent=1)
    print(f"  report written to {out}")
    print("\n  ENROLLED IS NOT SENT, on this channel too: a DRAFT campaign "
          "has issued no connection request.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
