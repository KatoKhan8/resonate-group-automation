#!/usr/bin/env python3
"""Approve and ACTIVATE EmailBison campaign 487 - the 10-contact CONTROL cohort.

    py -3 scripts/activate_control_campaign_v3.py            # dry run
    py -3 scripts/activate_control_campaign_v3.py --live      # ACTIVATE

THIS SENDS. `bison.resume_campaign` starts the campaign and it emails every
lead it holds. There is no recalling an email.

EXACT MAXIMUM EXPOSURE: 10 leads x 3 steps = 30 EMAILS, paced by the campaign's
own 20/day cap. Steps wait 3, 4 and 1 days, so the cap is not the binding
constraint on any single day; the cohort size is.

WHY 487 AND NOT 485. 485's sequence violates the threading invariant twice -
step 2 carries `Re: {SUBJECT_2}` and step 3 is `thread_reply: false` with its
own `{SUBJECT_3}` - and `bison.set_sequence` APPENDS, so it cannot be corrected
in place. 487 is the clean replacement, built with the sender named on the row
BEFORE staging so the provider's archive-the-senderless-campaign behaviour
could not reach it.

WHAT IS PROVEN BEFORE ANYTHING IS ACTIVATED, all of it read from EmailBison:

  the sequence      3 steps, thread_reply [false, true, true], every step
                    referencing {SUBJECT_1}. No SUBJECT_2 or SUBJECT_3 exists.
                    The "Re: " on steps 2 and 3 is the PROVIDER's own -
                    measured across 153 follow-ups by TASK-159 - not ours.
  the words         `configdiff.compare_bison` compares the provider's held
                    LEAD VARIABLES against the approved resolved copy. Not
                    placeholders, not the approved copy against itself: the
                    strings that render into {BODY_N} for each person.
  the lead set      WHO, not how many.
  the sender        2736, attached and verified.
  the caps          20/day, read back.

ONE AUTHORIZATION PER CONTACT. `executionguard.authorize` runs every gate for
one named person, and a read-back is single use - it refuses a second use by
design, so each contact gets its own fresh comparison. Ten contacts, ten
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

CANONICAL = "productive-email-control-v3"
PROVIDER_ID = 487
SENDER_ID = 2736
WORKSPACE = 10
EXPECT_LEADS = 10
STEPS = 3
DAILY_CAP = 20


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
    facts["senders"] = bison.campaign_senders(PROVIDER_ID)
    facts["leads"] = bison.campaign_lead_count(PROVIDER_ID)
    steps = bison.sequence_steps(PROVIDER_ID)
    facts["steps"] = len(steps)
    facts["threading"] = [(s.get("order"), s.get("email_subject"),
                           s.get("thread_reply")) for s in steps]

    if str(facts["status"]) not in ("paused", "draft"):
        problems.append(f"campaign is {facts['status']!r}; expected paused")
    if SENDER_ID not in (facts["senders"] or []):
        problems.append(f"sender {SENDER_ID} is not attached")
    if facts["leads"] != EXPECT_LEADS:
        problems.append(f"campaign holds {facts['leads']} lead(s), expected "
                        f"{EXPECT_LEADS}")
    if facts["steps"] != STEPS:
        problems.append(f"sequence has {facts['steps']} step(s), expected "
                        f"{STEPS}; an APPENDED sequence is not the CONTROL")
    if int(facts["cap"] or 0) != DAILY_CAP:
        problems.append(f"daily cap is {facts['cap']}, expected {DAILY_CAP}")

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
                              "{SUBJECT_5}"):
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

    facts, problems = preflight()
    print("=== PRE-ACTIVATION, PROVIDER TRUTH ===")
    print(f"  campaign          : {PROVIDER_ID}")
    print(f"  status            : {facts['status']}")
    print(f"  senders           : {facts['senders']}")
    print(f"  leads             : {facts['leads']}")
    print(f"  daily cap         : {facts['cap']}")
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
                interaction_id="operator-authz-2026-09-17-bison-v3",
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
                print(f"      {failure[:120]}")
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
                  f"{str(exc)[:130]}")
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
        providerwrites.perform(
            providerwrites.EMAIL_ACTIVATE,
            authorization=auths[chosen],
            provider_campaign_id=str(PROVIDER_ID),
            campaign=CANONICAL, tenant="productive",
            step=step,
            payload={"campaign_id": PROVIDER_ID, "expect_leads": EXPECT_LEADS,
                     "provider_lead_variables": held},
            transport=lambda p: bison.resume_campaign(
                p["campaign_id"], expect_leads=p["expect_leads"]),
            readback=lambda: {"status": bison.campaign(PROVIDER_ID).get(
                "status")},
            expected=None, by="operator")
    except Exception as exc:
        print(f"  REFUSED / FAILED: {type(exc).__name__}: {exc}")
        print("\n  READ PROVIDER TRUTH before anything else - the campaign may "
              "have started. Read bison.campaign(487).")
        return 3

    print("\n=== 4. PROVIDER TRUTH AFTER ACTIVATION ===")
    after = bison.campaign(PROVIDER_ID) or {}
    print(json.dumps({k: after.get(k) for k in (
        "id", "name", "status", "max_emails_per_day", "total_leads",
        "emails_sent", "sent")}, indent=1))
    print(f"  senders           : {bison.campaign_senders(PROVIDER_ID)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
