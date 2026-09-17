#!/usr/bin/env python3
"""Attach a second sending inbox to EmailBison campaign 487, end to end.

    py -3 scripts/attach_sender_to_487.py            # dry run
    py -3 scripts/attach_sender_to_487.py --live      # attach, row, re-approve

THIS DOES NOT SEND. `bison.assign_sender` is declared non-prospect-facing:
binding an inbox changes WHO a message would come from, not whether one is
sent. The campaign is already active and already sending nothing, for the
reason this script exists to fix.

WHY, AND WHAT IT COSTS. Sender 2736 is attached to campaigns 352, 328 and 327
as well as this one - all three ACTIVE, 173,558 emails between them - and its
limit is 15 a day per MAILBOX. Campaign 487's share of that is zero. Of 225
senders in workspace 10, 222 are committed; the three that are free are free
because they are `warming`.

THE OPERATOR WAS TOLD THAT AND SAID TO PROCEED. Recorded here because the
warning is part of the decision, not an argument against it:

  - `senderinventory.health_of` calls these `warming` on the one honest
    ground: warmup enabled AND zero lifetime sends. Created 2026-06-11,
    `emails_sent_count` 0. Cold outreach from a domain with no sending
    history is a deliverability risk, and that is what warmup exists to
    avoid.
  - `executionguard` gate 4 requires `health in (None, "ok")`. A `warming`
    seat cannot be AUTHORIZED, so any future activation naming it refuses.
    487 is already active and does not need re-authorization to keep running,
    which is why attaching works today and would not have before activation.

THE THREE CONSEQUENTIAL WRITES, IN ORDER, EACH READ BACK:

  1. the provider     attach the inbox. `attach_senders` is its own oracle -
                      the route answers 200 with `success: false` for both a
                      repeat and an empty array, so the MEMBERSHIP read is
                      what proves it, and it raises unless every sender asked
                      for is bound afterwards.
  2. canonical state  put the sender on the row. Skipping this breaks
                      `compare_bison`: approved `{2736}` against provider
                      `{2736, N}` is a `sender_ids` mismatch, and the
                      exact-match gate would refuse the next activation.
  3. the approval     adding a sender MOVES `campaigns.fingerprint`, so the
                      approval that authorized activation goes stale. It is
                      retaken through `orchestrator.decide`, never by hand -
                      the fingerprint binding is the point, and an approval
                      stamped by this process would not certify anything
                      anyway.

WHICH INBOX, AND WHY THIS ONE. All three are identical in state. 3941 is
human-9e58861fb87e, and that human already sends for Productive in this workspace
under 3948 - the inbox behind campaign 451's single delivered email. A reply
landing with a name the estate already knows is coherent; introducing a new
human to save a coin toss is not.
"""
import argparse
import json
import os
import sys
import subprocess

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import campaigns, clients, configdiff, orchestrator     # noqa: E402
from src import providerwrites, store                            # noqa: E402
from src.providers import bison, load_env                        # noqa: E402

CANONICAL = "productive-email-control-v3"
PROVIDER_ID = 487
EXISTING_SENDER = 2736
NEW_SENDER = 3941
FREE_SENDERS = (3941, 3930, 3919)


def approver():
    who = subprocess.run(["git", "config", "user.email"],
                         capture_output=True, text=True).stdout.strip()
    if not who:
        raise SystemExit("REFUSED: git config user.email is unset, so the "
                         "approval would be attributed to nobody.")
    return who


def preflight():
    problems, facts = [], {}
    row = bison.campaign(PROVIDER_ID) or {}
    facts["status"] = str(row.get("status") or "").lower()
    facts["senders_before"] = bison.campaign_senders(PROVIDER_ID) or []
    facts["leads"] = row.get("total_leads")
    facts["sent"] = row.get("emails_sent")

    rows, _meta = bison.sender_emails()
    chosen = next((r for r in rows or []
                   if int(r.get("id") or 0) == NEW_SENDER), None)
    if chosen is None:
        problems.append(f"sender {NEW_SENDER} is not in workspace 10")
        return facts, problems
    facts["sender"] = {k: chosen.get(k) for k in
                       ("id", "status", "daily_limit", "warmup_enabled",
                        "emails_sent_count")}
    if str(chosen.get("status") or "").lower() != "connected":
        problems.append(f"sender {NEW_SENDER} status is "
                        f"{chosen.get('status')!r}, not Connected")

    # STILL UNCOMMITTED? Free is the whole reason this one was chosen, and a
    # sender that acquired a campaign since the audit is no longer free.
    committed = []
    listing, _total = bison._paged(
        "campaigns",
        lambda page: bison.query(f"{bison.base()}/campaigns",
                                 {"page": page, "per_page": 100}))
    for entry in listing or []:
        if str(entry.get("status") or "").lower() != "active":
            continue
        cid = entry.get("id")
        if cid and int(cid) != PROVIDER_ID and NEW_SENDER in (
                bison.campaign_senders(cid) or []):
            committed.append(int(cid))
    facts["already_serving_active"] = committed
    if committed:
        problems.append(f"sender {NEW_SENDER} now serves active campaigns "
                        f"{committed}; it is no longer free capacity")

    if NEW_SENDER in facts["senders_before"]:
        problems.append(f"sender {NEW_SENDER} is already attached; nothing "
                        f"to do")
    return facts, problems


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--live", action="store_true",
                        help="attach, update the row and re-approve")
    args = parser.parse_args(argv)

    load_env(os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "config", ".env"))
    config = clients.load("productive")
    recs = store.load()
    campaign = campaigns.require(CANONICAL)

    facts, problems = preflight()
    print("=== PROVIDER TRUTH, BEFORE ===")
    for key in ("status", "senders_before", "leads", "sent",
                "already_serving_active"):
        print(f"  {key:22s}: {facts.get(key)}")
    print(f"  chosen sender         : {facts.get('sender')}")
    print(f"  other free inboxes    : "
          f"{[s for s in FREE_SENDERS if s != NEW_SENDER]}")
    if problems:
        print("\nREFUSED. Nothing was changed:")
        for problem in problems:
            print(f"  - {problem}")
        return 2
    print("  preflight             : PASS")
    print("  health caveat         : this inbox is `warming` (0 lifetime "
          "sends). The operator was told and chose to proceed.")
    print("  send exposure         : ZERO from this script; it binds an "
          "inbox and does not start anything")

    if not args.live:
        print("\nDRY RUN: nothing was attached, no row written, no approval "
              "taken.")
        return 0

    # 1. THE PROVIDER.
    print("\n=== 1. ATTACH AT THE PROVIDER ===")
    wanted = sorted(set(facts["senders_before"]) | {NEW_SENDER})
    try:
        providerwrites.perform(
            providerwrites.EMAIL_ASSIGN_SENDER,
            provider_campaign_id=str(PROVIDER_ID),
            campaign=CANONICAL, tenant="productive",
            payload={"campaign_id": PROVIDER_ID, "sender_ids": wanted},
            transport=lambda p: bison.attach_senders(p["campaign_id"],
                                                     p["sender_ids"]),
            readback=lambda: {"senders": sorted(
                bison.campaign_senders(PROVIDER_ID) or [])},
            expected={"senders": wanted}, by="operator")
    except Exception as exc:
        print(f"  REFUSED / FAILED: {type(exc).__name__}: {exc}")
        print("\n  READ PROVIDER TRUTH before retrying - the attach may have "
              "landed. bison.campaign_senders(487).")
        return 3
    after = sorted(bison.campaign_senders(PROVIDER_ID) or [])
    print(f"  senders now           : {after}")

    # 2. CANONICAL STATE.
    print("\n=== 2. PUT IT ON THE ROW ===")
    with campaigns.transaction() as rows:
        target = campaigns.get(CANONICAL, rows)
        senders = target.setdefault("senders", {})
        senders["email"] = [{"provider_account_id": str(s),
                             "account_id": f"eb-{s}"} for s in after]
    campaign = campaigns.require(CANONICAL)
    print(f"  row senders.email     : "
          f"{[s.get('provider_account_id') for s in campaign['senders']['email']]}")

    # 3. THE APPROVAL, WHICH THE ROW CHANGE JUST STALED.
    print("\n=== 3. RETAKE THE APPROVAL ===")
    fingerprint = campaigns.fingerprint(campaign, recs, config)
    print(f"  new fingerprint       : {fingerprint}")
    if campaigns.is_approved(campaign, recs, config):
        print("  approval              : still current, unchanged")
    else:
        with campaigns.transaction() as rows:
            target = campaigns.get(CANONICAL, rows)
            orchestrator.decide(
                target, approver(), "approve", fingerprint=fingerprint,
                interaction_id="operator-authz-2026-09-17-bison-v3-sender",
                config=config, recs=recs, role="admin")
        campaign = campaigns.require(CANONICAL)
        print(f"  approval              : retaken by {approver()}")
    if not campaigns.is_approved(campaign, recs, config):
        print("  REFUSED: the approval is not current after retaking it. The "
              "provider and the row now disagree with canonical approval; "
              "settle by hand before any activation.")
        return 3

    # 4. THE EXACT-MATCH GATE, WHICH IS WHY 2 AND 3 EXIST AT ALL.
    print("\n=== 4. DOES THE PROVIDER STILL HOLD WHAT WAS APPROVED? ===")
    readback = configdiff.compare_bison(campaign, recs=recs, config=config)
    diff = readback.diff or {}
    print(f"  verdict               : {diff.get('verdict')}")
    for failure in (diff.get("failures") or [])[:6]:
        print(f"    {failure[:130]}")
    fields = diff.get("fields") or {}
    print(f"  sender_ids            : {fields.get('sender_ids', {}).get('verdict')}")
    return 0 if diff.get("verdict") == configdiff.PASS else 4


if __name__ == "__main__":
    raise SystemExit(main())
