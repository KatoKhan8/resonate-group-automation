#!/usr/bin/env python3
"""Approve and ACTIVATE EmailBison campaign 489 - the 5-contact US cohort.

    py -3 scripts/activate_us_cohort_campaign.py            # dry run
    py -3 scripts/activate_us_cohort_campaign.py --live      # ACTIVATE

THIS SENDS. `bison.resume_campaign` starts the campaign and it emails every
lead it holds. There is no recalling an email.

EXACT MAXIMUM EXPOSURE: 5 leads x 3 steps = 15 EMAILS, paced by the campaign's
own 5/day cap. Steps wait 3, 4 and 1 days, so the cohort size binds before the
cap does on any single day.

## Why this campaign exists rather than an edit to 487

487 is correct and must not be touched. Its only mailbox, 2736, is booked to
its 15/day limit on the 18th, the 21st and the 22nd by the client's own
campaigns - read from a COMPLETE cursor walk of all 183,239 scheduled rows,
and reproduced on 2026-09-18. Pause/resume re-plans against the same full
mailbox, swapping onto another of that human's inboxes finds them booked the
same days, and the step delay was ruled out by canary 451. The date is a
consequence of a full mailbox, so the answer is a different mailbox.

## The sender, and the trade that was NOT taken

    3437   rendulicbojan@gproductive.com   Bojan Rendulic

The SAME HUMAN 487 already sends as, on a different one of his six inboxes:
health `ok`, 1,784 emails sent from it, 6 of 15 booked today by campaign 352,
**9 free**. Its forward book is clear on every day this sequence needs.

The three inboxes with a completely EMPTY forward book - 3941, 3930, 3919 -
were rejected. They are empty because they have never sent an email: created
2026-06-11, `emails_sent_count` 0, which is exactly what
`senderinventory.health_of` calls HEALTH_WARMING and `readiness` calls
DEGRADED. Taking them would have meant sending the first email of a cold
`.shop` mailbox, from a human none of these five has heard from, to gain
capacity we did not need.

## What is proven before anything is activated, all read from EmailBison

  the sequence      3 steps, thread_reply [false, true, true], every step
                    referencing {SUBJECT_1}. No SUBJECT_2 or SUBJECT_3 is
                    referenced anywhere. The "Re: " the provider shows on
                    steps 2 and 3 is the PROVIDER's own - measured across 153
                    follow-ups by TASK-159 - and `configdiff` normalises it.
  the words         `configdiff.compare_bison` compares the provider's held
                    LEAD VARIABLES against the approved resolved copy: the
                    strings that render into {BODY_N} for each person, not the
                    placeholders and not the approved copy against itself.
  the lead set      WHO, not how many.
  the sender        3437, attached and verified.
  the caps          5/day, read back.
  the window        09:00-17:00 America/New_York, read back. The client
                    default is Europe/Zagreb, which for these five is 03:00.

## The collision that had to be read rather than assumed

FOUR of these five are already leads in campaign 481 - the paused historical
campaign. Measured 2026-09-18, each reads `status: "stopped"`, `emails_sent:
0` in `lead_campaign_data`. `stopped` is not `in_sequence`, so they attach
here; and zero sent means nobody has ever been written to. Had any read
`in_sequence`, the provider would have refused the whole batch with one
unattributed 422 and this campaign would not exist.

`providerwrites._NEVER_ACTIVATE` refuses 481 and 485 whatever canonical row
names them, which is what keeps that history from becoming a second message.

ONE AUTHORIZATION PER CONTACT. `executionguard.authorize` runs every gate for
one named person and a read-back is single use - it refuses a second use by
design - so each contact gets its own fresh comparison. Five contacts, five
authorizations; if any one refuses, nothing is activated, because the campaign
emails all of them or none.
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import (campaigns, clients, configdiff, executionguard,      # noqa
                 orchestrator, providerwrites, store)
from src.providers import bison, load_env                             # noqa

CANONICAL = "productive-email-us-cohort-v1"
PROVIDER_ID = 489
SENDER_ID = 3437
WORKSPACE = 10
EXPECT_LEADS = 5
STEPS = 3
DAILY_CAP = 5
INTERACTION = "operator-authz-2026-09-18-us-cohort"


def h12(value):
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:12]


def approver():
    who = subprocess.run(["git", "config", "user.email"],
                         capture_output=True, text=True).stdout.strip()
    if not who:
        raise SystemExit("REFUSED: git config user.email is unset, so the "
                         "approval would be attributed to nobody.")
    return who


def cohort_contacts(campaign, recs):
    """(rec, contact) for every contact on the row with an approved em1."""
    out = []
    for rec in recs:
        if rec["id"] not in (campaign.get("record_ids") or []):
            continue
        for contact in rec.get("contacts") or []:
            steps = (rec.get("cadence") or {}).get(contact.get("key")) or {}
            if (steps.get("em1") or {}).get("approval"):
                out.append((rec, contact))
    return out


def preflight():
    problems, facts = [], {}
    row = bison.campaign(PROVIDER_ID) or {}
    facts["status"] = row.get("status")
    facts["cap"] = row.get("max_emails_per_day")
    facts["sent"] = row.get("emails_sent")
    facts["senders"] = bison.campaign_senders(PROVIDER_ID)
    facts["leads"] = bison.campaign_lead_count(PROVIDER_ID)
    facts["schedule"] = bison.schedule(PROVIDER_ID)
    steps = bison.sequence_steps(PROVIDER_ID)
    facts["steps"] = len(steps)
    facts["threading"] = [(s.get("order"), s.get("email_subject"),
                           s.get("thread_reply")) for s in steps]

    if str(facts["status"]) not in ("paused", "draft"):
        problems.append(f"campaign is {facts['status']!r}; expected paused")
    if SENDER_ID not in (facts["senders"] or []):
        problems.append(f"sender {SENDER_ID} is not attached")
    if set(facts["senders"] or []) != {SENDER_ID}:
        problems.append(f"senders are {facts['senders']}, expected exactly "
                        f"[{SENDER_ID}] - an extra inbox is another human")
    if facts["leads"] != EXPECT_LEADS:
        problems.append(f"campaign holds {facts['leads']} lead(s), expected "
                        f"{EXPECT_LEADS}")
    if facts["steps"] != STEPS:
        problems.append(f"sequence has {facts['steps']} step(s), expected "
                        f"{STEPS}; an APPENDED sequence is not the CONTROL")
    if int(facts["cap"] or 0) != DAILY_CAP:
        problems.append(f"daily cap is {facts['cap']}, expected {DAILY_CAP}")
    if int(facts["sent"] or 0) != 0:
        problems.append(f"campaign reports {facts['sent']} email(s) already "
                        f"sent; this is meant to be its first")

    # THE WINDOW, ASSERTED AGAINST THE PROVIDER. A cohort of Americans on the
    # client's Zagreb hours is written to at 03:00 local, which is the defect
    # this campaign exists partly to avoid. Verified rather than assumed.
    schedule = facts["schedule"] or {}
    if str(schedule.get("timezone")) != "America/New_York":
        problems.append(f"schedule timezone is "
                        f"{schedule.get('timezone')!r}, expected "
                        f"'America/New_York'")
    if str(schedule.get("start_time") or "")[:5] != "09:00":
        problems.append(f"window starts {schedule.get('start_time')!r}")
    if str(schedule.get("end_time") or "")[:5] != "17:00":
        problems.append(f"window ends {schedule.get('end_time')!r}")
    if schedule.get("saturday") or schedule.get("sunday"):
        problems.append("the window includes a weekend day")

    # THE THREADING INVARIANT, ASSERTED AGAINST THE PROVIDER.
    # Only the opener owns a subject. A follow-up that is not a thread reply,
    # or that carries a subject of its own, must stop this.
    for order, subject, thread_reply in facts["threading"]:
        text = str(subject or "")
        if order == 1:
            if thread_reply:
                problems.append("step 1 is a thread reply; the opener starts "
                                "the thread")
            if "{SUBJECT_1}" not in text:
                problems.append(f"step 1 subject {text!r} is not SUBJECT_1")
        else:
            if not thread_reply:
                problems.append(
                    f"step {order} is NOT a thread reply, so it would open a "
                    f"new thread with its own subject")
            if "{SUBJECT_1}" not in text:
                problems.append(
                    f"step {order} subject {text!r} does not reference "
                    f"SUBJECT_1")
            for forbidden in ("{SUBJECT_2}", "{SUBJECT_3}", "{SUBJECT_4}",
                              "{SUBJECT_5}", "{SUBJECT_6}"):
                if forbidden in text:
                    problems.append(
                        f"step {order} carries an independent {forbidden}; "
                        f"only the opener owns a subject")
    return facts, problems


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--live", action="store_true",
                        help="approve and ACTIVATE; omit for a dry run")
    args = parser.parse_args(argv)

    load_env(os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "config", ".env"))

    config = clients.load("productive")
    recs = store.load()
    campaign = campaigns.require(CANONICAL)

    if str(campaign.get("bison_campaign_id")) != str(PROVIDER_ID):
        raise SystemExit(
            f"REFUSED: {CANONICAL} is bound to "
            f"{campaign.get('bison_campaign_id')!r}, not {PROVIDER_ID}. A "
            f"mismatched binding is how a send reaches a campaign nobody "
            f"approved.")

    facts, problems = preflight()
    print("=== PRE-ACTIVATION, PROVIDER TRUTH ===")
    print(f"  campaign          : {PROVIDER_ID}")
    print(f"  status            : {facts['status']}")
    print(f"  emails_sent       : {facts['sent']}")
    print(f"  senders           : {facts['senders']}")
    print(f"  leads             : {facts['leads']}")
    print(f"  daily cap         : {facts['cap']}")
    sched = facts["schedule"] or {}
    print(f"  window            : {sched.get('start_time')}-"
          f"{sched.get('end_time')} {sched.get('timezone')}")
    print(f"  sequence          : {facts['steps']} steps")
    for order, subject, thread_reply in facts["threading"]:
        print(f"    step {order}: subject={subject!r} "
              f"thread_reply={thread_reply}")

    found = cohort_contacts(campaign, recs)
    print(f"  cohort contacts   : {len(found)}")
    if len(found) != EXPECT_LEADS:
        problems.append(f"{len(found)} approved contact(s) on the row, "
                        f"expected {EXPECT_LEADS}")

    if problems:
        print("\nREFUSED. Nothing was activated:")
        for problem in problems:
            print(f"  - {problem}")
        return 2
    print("  preflight         : PASS")
    print(f"  max send exposure : {EXPECT_LEADS} people x {STEPS} steps = "
          f"{EXPECT_LEADS * STEPS} emails, paced at {DAILY_CAP}/day")

    if not args.live:
        print("\nDRY RUN: nothing was activated.")
        return 0

    # 1. THE CAMPAIGN APPROVAL.
    print("\n=== 1. RECORD THE CAMPAIGN APPROVAL ===")
    who = approver()
    fingerprint = campaigns.fingerprint(campaign, recs, config)
    if campaigns.is_approved(campaign, recs, config):
        print("  decide            : already approved, unchanged")
    else:
        with campaigns.transaction() as rows:
            target = campaigns.get(CANONICAL, rows)
            orchestrator.decide(
                target, who, "approve", fingerprint=fingerprint,
                interaction_id=INTERACTION,
                config=config, recs=recs, role="admin")
        campaign = campaigns.require(CANONICAL)
        print("  decide            : approved")
    print(f"  fingerprint       : {fingerprint}")
    if not campaigns.is_approved(campaign, recs, config):
        print("  REFUSED: the campaign approval is not current. Not "
              "activating.")
        return 3

    # 2. ONE AUTHORIZATION PER CONTACT, EACH WITH ITS OWN READBACK.
    print("\n=== 2. MINT THE AUTHORIZATIONS ===")
    auths = {}
    for rec, contact in found:
        label = h12(f"{rec['id']}:{contact.get('key')}")
        readback = configdiff.compare_bison(campaign, recs=recs, config=config)
        verdict = (readback.diff or {}).get("verdict")
        if verdict != configdiff.PASS:
            print(f"  {label}      : REFUSED readback {verdict}")
            for failure in (readback.diff or {}).get("failures", [])[:4]:
                print(f"      {str(failure)[:130]}")
            continue
        try:
            auths[label] = executionguard.authorize(
                operation=providerwrites.EMAIL_ACTIVATE, channel="email",
                campaign=campaign, rec=rec, contact=contact, step_key="em1",
                workspace=WORKSPACE, config=config, recs=recs,
                readback=readback, by="operator")
            print(f"  {label}      : authorized")
        except Exception as exc:
            print(f"  {label}      : REFUSED {type(exc).__name__}: "
                  f"{str(exc)[:200]}")
    if len(auths) != EXPECT_LEADS:
        print(f"\n  REFUSED: {len(auths)}/{EXPECT_LEADS} authorized, and the "
              f"campaign emails every lead it holds. Nothing was activated.")
        return 3

    # 3. ACTIVATION.
    print("\n=== 3. ACTIVATE ===")
    chosen = sorted(auths)[0]
    rec, contact = next((r, c) for r, c in found
                        if h12(f"{r['id']}:{c.get('key')}") == chosen)
    step = ((rec.get("cadence") or {}).get(contact.get("key")) or {}).get("em1")
    # The payload carries the words the PROVIDER holds for this lead, so
    # `_require_approved_words` compares the approval against what will
    # actually be sent rather than against the approved copy itself.
    held = {}
    for lead_id in (bison.campaign_lead_ids(PROVIDER_ID) or []):
        variables = bison.variables_of(bison.lead(lead_id)) or {}
        if variables.get("contact_key") == contact.get("key"):
            held = variables
            break
    print(f"  proving words for : {chosen}")
    print(f"  provider variables: {sorted(held)}")
    try:
        result = providerwrites.perform(
            providerwrites.EMAIL_ACTIVATE,
            authorization=auths[chosen],
            provider_campaign_id=str(PROVIDER_ID),
            campaign=CANONICAL, tenant="productive",
            step=step,
            payload={"campaign_id": PROVIDER_ID, "expect_leads": EXPECT_LEADS,
                     "provider_lead_variables": held},
            # `expect_leads` is read from the provider by `resume_campaign`
            # and compared against this number: passing the wrong count is how
            # a campaign meant for five reaches twenty-three.
            transport=lambda p: bison.resume_campaign(
                p["campaign_id"], expect_leads=p["expect_leads"]),
            readback=lambda: {"status": bison.campaign(PROVIDER_ID).get(
                "status")},
            # EXPECTED IS NAMED, AND THE FIRST RUN IS WHY.
            #
            # v3's script passes `expected=None`, so `perform` has nothing to
            # compare the read-back against and raises `WriteUnverified:
            # read-back says unknown` - on a write that SUCCEEDED. Measured
            # here 2026-09-18: campaign 489 went `active` and the script
            # reported a failure, which is the worst shape an ambiguous result
            # can take, because the safe response to ambiguity is to READ and
            # the tempting one is to retry.
            #
            # Naming it turns the same read into a verdict: `active` passes,
            # anything else is a real discrepancy.
            expected={"status": "active"}, by="operator")
    except Exception as exc:
        print(f"  REFUSED / FAILED: {type(exc).__name__}: {exc}")
        print(f"\n  READ PROVIDER TRUTH BEFORE ANYTHING ELSE - the campaign "
              f"may have started. `bison.campaign({PROVIDER_ID})`. An "
              f"ambiguous write is READ, never retried.")
        return 3
    print(f"  perform           : {json.dumps(result, default=str)[:400]}")

    # 4. READ BACK FROM THE PROVIDER. A 200 is not a running campaign.
    print("\n=== 4. READ BACK ===")
    after = bison.campaign(PROVIDER_ID) or {}
    print(f"  status            : {after.get('status')}")
    print(f"  leads             : {after.get('total_leads')}")
    print(f"  emails_sent       : {after.get('emails_sent')}")
    scheduled = bison.scheduled_emails(PROVIDER_ID)
    print(f"  scheduled_emails  : {len(scheduled)}")
    for row in scheduled:
        print(f"    step={row.get('sequence_step_id')} "
              f"status={row.get('status')} "
              f"at={row.get('scheduled_date')} sent_at={row.get('sent_at')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
