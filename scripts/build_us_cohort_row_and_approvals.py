#!/usr/bin/env python3
"""The US cohort: one canonical row, and the operator's approval of five people.

    py -3 scripts/build_us_cohort_row_and_approvals.py            # dry run
    py -3 scripts/build_us_cohort_row_and_approvals.py --live      # write

NO PROVIDER CALL OF ANY KIND. This writes `work/campaigns.jsonl` and takes
fifteen approvals in `work/queue.jsonl`. Staging and activation are separate
scripts and separate decisions.

## Why a second email campaign exists at all

Campaign 487 is correct and cannot send before 2026-09-23. Its only mailbox,
2736, is booked to its 15/day limit on the 18th, the 21st and the 22nd by the
client's own campaigns - read from a COMPLETE cursor walk of every scheduled
row in every active campaign, 183,239 of them. Nothing about 487 is wrong and
nothing about it should be changed to make a date.

The five contacts here are a DIFFERENT cohort, approved separately, and the
mailbox they send from has room today.

## The sender, and why it is not a new human

    3437   <sender-3437-address>

<sender-3437-owner> - **the same human 487 already sends as**, on a different one
of his six inboxes. Measured 2026-09-18:

    health          ok        (1,784 emails sent from it; genuinely warm)
    daily_limit     15
    booked today     6        by client campaign 352
    room today       9

This matters more than the capacity. The three inboxes with an EMPTY forward
book - 3941, 3930, 3919 - are empty because they have **never sent an
email**: created 2026-06-11, `emails_sent_count` 0, which is exactly the
condition `senderinventory.health_of` calls HEALTH_WARMING and
`senderinventory.readiness` calls **DEGRADED**. Choosing one of those would
have meant sending the first email of a cold `.shop` mailbox to five real
prospects, from a human none of them has ever heard from, to gain capacity.
`ACCOUNT-OUTREACH.md` and the standing sender-identity rule both refuse that
trade. 3437 needs no new human decision because the operator already made it
for 487.

## The window, and what it is NOT

    monday-friday  09:00-17:00  America/New_York

`bisonfactory._plan` reads `sending_window` off the CAMPAIGN before falling
back to the client's, and its own comment says why: EmailBison schedules one
window per campaign, so the window belongs to the cohort. The client default
is Europe/Zagreb, which is 03:00 Eastern - the defect that comment describes,
applied to a cohort that is entirely American.

Evidence, from `company_facts.offices`, which is what is actually recorded:

    New York NY        Eastern
    Chicago IL         Central
    Greensboro NC      Eastern
    Scottsdale AZ      Arizona, no DST
    US, no city        country only - timezone UNKNOWN, not guessed

**The deviation is stated rather than averaged away**: the Arizona recipient's
window opens at 06:00 local. Four of five sit inside local business hours and
the fifth is early rather than nocturnal. That is not a resolved cohort and
this file does not claim it is - `geo.propose_cohort_window` would correctly
return NO PROPOSAL for a cohort spanning three zones. What is claimed is
narrower and checkable: every recipient is in the United States, and
America/New_York is the best-supported single window for them. Europe/Zagreb
is the worst.

## The order these two things happen in, and why it is not the obvious one

The row is written BEFORE the approvals, and that is load-bearing.
`approve.approve_step` fingerprints the step as `cadence.build` expands it
UNDER THE CAMPAIGN. Called without one it expands under the client cadence and
fingerprints a step the send path never resolves. Measured 2026-09-16: thirty
approvals taken that way read valid under `is_approved(rec, ck, sk)` - which
compares the stored step to itself and so agrees unconditionally - and INVALID
under the three-argument form `configdiff.compare_bison` actually uses.

So the row first, then the approvals against it.

## What the dry run proves before anything is written

That the words expanded under this new row are **byte-identical** to the words
in the approval packet the operator read. The packet is the artefact the
approval attaches to; a row that changed a single character of it would make
the approval cover a message that does not exist. The comparison is per step
and it is a refusal, not a warning.
"""
import argparse
import difflib
import hashlib
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import (approval as approval_mod, approve, cadence,           # noqa
                 campaigns, clients, store)

CANONICAL = "productive-email-us-cohort-v1"
NAME = "RESONATE - PRODUCTIVE - EMAIL - US-HOURS - CONTROL - COHORT B"
CLIENT = "productive"
SENDER_ID = "3437"
STEPS = ("em1", "em2", "em3")

# THE SEQUENCE IS COPIED FROM v3, NOT RETYPED, AND THE FIRST DRY RUN IS WHY.
#
# `cadence.build` expands a step from the CAMPAIGN's `cadence_steps`. A row
# without them expands the words STORED on the record instead - which for
# these five is the model-generated copy TASK-210 replaced, not the audited
# CONTROL. The first run of this script produced exactly that and the packet
# comparison below refused all fifteen steps: subject and body differed on
# every one, and one record expanded no `em2` at all.
#
# So the approved words are not a property of the contact. They are
# `persona_pain -> comparable_proof -> breakup` resolved under a campaign that
# names them, which is what `scripts/next_ready_cohort.py` builds the approval
# packet under (`SHAPE_CAMPAIGN["email"]` is v3) and therefore what the
# operator actually read.
#
# Read from the live row rather than written here so the two cannot drift: if
# somebody edits v3's sequence, this cohort either follows it or refuses at
# the packet comparison. A retyped copy would silently keep running the old
# one.
SEQUENCE_FROM = "productive-email-control-v3"

# The five the operator approved on 2026-09-18, named exactly. A list rather
# than a query: an approval that covers "whatever the screen returns today" is
# not an approval of anybody in particular.
#
# THE NAMES LIVE IN `work/`, NOT HERE - moved 2026-09-20. They are five real
# prospects, and the standing rule is that `work/` is gitignored because "it
# is 300 real companies and 92 real contacts and it is not ours to publish".
# This file is TRACKED, so it carries the pointer and the count while the
# cohort itself is read from the sidecar.
#
# This list is why `tests/test_fixture_hygiene` was RED from 2026-09-18 -
# and a red PII guard cannot catch the next leak, which is the real cost.
# Record ids derive from prospect domains and so leak by construction;
# TASK-189's verdict was that the guard is right to flag that and an
# allowlist would open a hole the size of the queue. The fix is not to
# exempt the data, it is to not track it.
COHORT_FILE = os.path.join(os.path.dirname(store.queue_path()),
                           "us-cohort-2026-09-18.json")


def _load_cohort():
    """The approved five, from the sidecar. REFUSES rather than defaulting.

    An empty cohort here would build a campaign row naming nobody and pass
    every count check that compares one derived number against another.
    """
    if not os.path.exists(COHORT_FILE):
        raise SystemExit(
            f"the approved cohort is not on this machine: {COHORT_FILE}. "
            f"It holds real prospects, so it is gitignored and travels "
            f"separately from the repository. Restore it before running.")
    with open(COHORT_FILE, encoding="utf-8") as handle:
        rows = (json.load(handle) or {}).get("cohort") or []
    pairs = [(r["record_id"], r["contact_key"]) for r in rows]
    if not pairs:
        raise SystemExit(f"{COHORT_FILE} names nobody")
    return pairs


FIVE = _load_cohort()

WINDOW = {
    "days": ["monday", "tuesday", "wednesday", "thursday", "friday"],
    "start": "09:00",
    "end": "17:00",
    "timezone": "America/New_York",
}

PACKET = os.path.join("work", "approval", "NEAR-MISS-PACKET-2026-09-17.md")


def h12(value):
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:12]


def approver():
    """The operator's address, read from git config rather than written here.

    The PII guard requires every address in a tracked file to be on a reserved
    domain, and an exception for the person who set the rule is not a rule.
    The attribution lands in work/queue.jsonl, which is gitignored.
    """
    out = subprocess.run(["git", "config", "user.email"],
                         capture_output=True, text=True).stdout.strip()
    if not out:
        raise SystemExit("REFUSED: git config user.email is unset, so the "
                         "approval would be attributed to nobody.")
    return f"{out} (operator authorisation 2026-09-18 US cohort)"


def packet_copy():
    """The exact words the operator read, parsed back out of the packet.

    Returns {(record_id, contact_key, step_key): (subject, body)}.
    """
    if not os.path.exists(PACKET):
        raise SystemExit(
            f"REFUSED: {PACKET} is missing. It is the artefact the operator's "
            f"approval attaches to, it lives outside git because it names real "
            f"people, and without it there is nothing to check the expansion "
            f"against. Re-run scripts/near_miss_approval_packet.py.")
    out, rec, contact, step, subject, body, in_body = {}, None, None, None, None, [], False
    for line in open(PACKET, encoding="utf-8").read().splitlines():
        if line.startswith("## "):
            if step:
                out[(rec, contact, step)] = (subject, "\n".join(body).strip())
            rec = contact = step = subject = None
            body, in_body = [], False
        elif line.startswith("- record `"):
            rec = line.split("`")[1]
            contact = line.split("`")[3]
        elif line.startswith("### "):
            if step:
                out[(rec, contact, step)] = (subject, "\n".join(body).strip())
            step, subject, body, in_body = line[4:].strip(), None, [], False
        elif line.startswith("**Subject:**"):
            subject = line.split("**Subject:**", 1)[1].strip()
        elif line.strip() == "```":
            in_body = not in_body
        elif in_body:
            body.append(line)
    if step:
        out[(rec, contact, step)] = (subject, "\n".join(body).strip())
    return out


def expanded_steps(rec, contact_key, config, campaign):
    timeline = cadence.build(rec, config, campaign=campaign)
    return (timeline["contacts"].get(contact_key) or {})


def normalise(text):
    """Compare the words, not the whitespace the two renderers disagree on."""
    return "\n".join(line.rstrip() for line in
                     str(text or "").replace("\r\n", "\n").strip().splitlines())


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--live", action="store_true",
                        help="write the row and the approvals")
    args = parser.parse_args(argv)

    config = clients.load(CLIENT)
    recs = store.load()
    by_id = {r["id"]: r for r in recs}
    packet = packet_copy()

    print("=== 1. THE ROW ===")
    existing = campaigns.get(CANONICAL)
    if existing:
        print(f"  {CANONICAL}: already exists, status "
              f"{existing.get('status')!r}")
        row = existing
    else:
        row = campaigns.new_campaign(CANONICAL, CLIENT, NAME,
                                     created_by="operator")
        row["record_ids"] = [rid for rid, _ in FIVE]
        row["daily_volume"] = {"email": 5, "linkedin": 0}
        row["senders"] = {"email": [{"provider_account_id": SENDER_ID,
                                     "account_id": f"eb-{SENDER_ID}"}],
                          "linkedin": []}
        row["sending_window"] = dict(WINDOW)
        row[cadence.CADENCE_KEY] = [
            dict(step) for step in
            (campaigns.require(SEQUENCE_FROM).get(cadence.CADENCE_KEY) or [])]
        if not row[cadence.CADENCE_KEY]:
            raise SystemExit(
                f"REFUSED: {SEQUENCE_FROM} carries no {cadence.CADENCE_KEY}, "
                f"so there is no approved sequence to run. A cohort with no "
                f"sequence expands whatever is stored on each record, which "
                f"is the copy the CONTROL replaced.")
        # THE STATE THE OPERATOR APPROVES THIS CAMPAIGN TO BE IN - AND TODAY
        # THAT IS `paused`, WHICH IS NOT A TYPO.
        #
        # `configdiff` builds the approved side's `status` from this field, and
        # `executionguard.authorize` requires that comparison to PASS at the
        # moment it mints an authorization. Activation happens AFTER the
        # authorization, so at the instant it is checked the campaign is
        # legitimately still paused. Writing `active` here makes the readback
        # FAIL on `status` alone - measured on this row 2026-09-18, 14 checks,
        # one failure, and that one failure refuses the activation it was
        # written to permit.
        #
        # It is flipped to `active` after the provider confirms the campaign
        # is running, through `scripts/record_approved_running_state.py`, which
        # retakes the approval in the same pass because the row fingerprint
        # covers this field. That is the same order v3 went through.
        row["provider_status_expected"] = "paused"
        print(f"  {CANONICAL}: NEW")
    print(f"  records   : {len(row.get('record_ids') or [])}")
    print(f"  sender    : {SENDER_ID} (<sender-3437-owner>, the human 487 sends as)")
    print(f"  window    : {WINDOW['start']}-{WINDOW['end']} "
          f"{WINDOW['timezone']}, {len(WINDOW['days'])} days")
    print(f"  daily cap : {row.get('daily_volume', {}).get('email')}")
    print(f"  sequence  : " + " -> ".join(s.get("template","?") for s in (row.get(cadence.CADENCE_KEY) or [])))

    print("\n=== 2. THE WORDS, AGAINST THE PACKET THE OPERATOR READ ===")
    drift = []
    for rid, ck in FIVE:
        rec = by_id.get(rid)
        if rec is None:
            drift.append(f"{h12(rid)}: record is not in the queue")
            continue
        steps = expanded_steps(rec, ck, config, row)
        for sk in STEPS:
            want = packet.get((rid, ck, sk))
            got = steps.get(sk)
            if want is None:
                drift.append(f"{h12(rid)}/{sk}: not in the approval packet")
                continue
            if not got:
                drift.append(f"{h12(rid)}/{sk}: the row expands no such step")
                continue
            if normalise(got.get("subject")) != normalise(want[0]):
                drift.append(f"{h12(rid)}/{sk}: SUBJECT differs from the "
                             f"packet")
            if normalise(got.get("body")) != normalise(want[1]):
                drift.append(f"{h12(rid)}/{sk}: BODY differs from the packet")
                for hunk in list(difflib.unified_diff(
                        normalise(want[1]).splitlines(),
                        normalise(got.get("body")).splitlines(),
                        "packet", "expanded", lineterm="", n=0))[:6]:
                    print(f"      {hunk[:110]}")
    if drift:
        print("  REFUSED - the row does not expand the approved words:")
        for item in drift:
            print(f"    - {item}")
        return 2
    print(f"  {len(FIVE) * len(STEPS)} step(s): IDENTICAL to the packet")

    print("\n=== 3. EVERY GATE, ASKED BEFORE ANYTHING IS WRITTEN ===")
    plan, refusals = [], []
    for rid, ck in FIVE:
        rec = by_id[rid]
        steps = expanded_steps(rec, ck, config, row)
        for sk in STEPS:
            step = steps.get(sk)
            why = approve.why_not(rec, ck, sk, step=step, config=config,
                                  campaign=row)
            if why:
                refusals.append(f"{h12(rid)}/{sk}: {why}")
                continue
            covers = approval_mod.is_approved(rec, ck, sk, step)
            plan.append((rec, ck, sk, step, covers))
    for item in refusals:
        print(f"  REFUSED {item}")
    already = sum(1 for *_, covers in plan if covers)
    print(f"  approvable: {len(plan)}  already current: {already}  "
          f"refused: {len(refusals)}")
    if refusals:
        print("\n  A refused step is HELD. Nothing is approved on a cohort "
              "where a gate said no.")
        return 2
    if len(plan) != len(FIVE) * len(STEPS):
        print(f"\n  REFUSED: {len(plan)} approvable steps, expected "
              f"{len(FIVE) * len(STEPS)}.")
        return 2

    if not args.live:
        print("\nDRY RUN: nothing was written.")
        return 0

    print("\n=== 4. WRITE ===")
    by = approver()
    if not approval_mod.is_accountable_approver(by):
        raise SystemExit(f"REFUSED: {by!r} is not an identity anybody can be "
                         f"held to.")
    if not existing:
        with campaigns.transaction() as rows:
            rows.append(row)
        print(f"  wrote canonical row {CANONICAL}")

    written = 0
    with store.transaction() as live_recs:
        live = {r["id"]: r for r in live_recs}
        for rec, ck, sk, step, covers in plan:
            if covers:
                continue
            target = live[rec["id"]]
            approve.approve_step(target, ck, sk, by=by, config=config,
                                 step=step, sync=False, campaign=row)
            written += 1
        for rid, _ in FIVE:
            approve.sync_state(live[rid], config, row)
    print(f"  took {written} approval(s), attributed to {by.split(' (')[0]}")
    print("\nNo provider call was made. Staging is the next script.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
