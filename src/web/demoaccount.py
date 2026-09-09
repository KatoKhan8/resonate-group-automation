#!/usr/bin/env python3
"""One account rich enough to demonstrate what the new model can hold.

The rest of the demo estate shows a working pipeline. It does not show the
thing this mission was about, because a company with one decision maker and
one sender per channel looks identical under the old model and the new one.

So: **Acme Ltd**, three decision makers, four humans, two channels, one reply,
one referral, and - deliberately - one claim the evidence does *not* support.

    JOHN SMITH, COO          Anna    email      confirmed sent
                             Petar   LinkedIn   confirmed sent
                             John    reply      positive, referring to Sarah

    SARAH JONES, CEO         Mark    email      confirmed sent
                             Sara S  LinkedIn   PLANNED, not sent

    MICHAEL GREEN, CFO       Petar   LinkedIn   PLANNED, not sent

What each part demonstrates:

  * a message to Sarah **may** say "John suggested I reach out" - there is a
    recorded referral edge
  * a message to Sarah **may not** say "my colleague Sara messaged you" - that
    LinkedIn touch is planned, and planned is not sent
  * a message to Michael **may not** mention John's reply unless the campaign
    switches that claim on, which it does not by default
  * the account timeline reads as one story rather than three tables

Every company, person and quotation is fictional. Nothing here posts, sends,
or calls a provider.
"""
from .. import (account, assignment, events,
                senderidentity as si, senderteam, store)

WORKSPACE = "productive"
RECORD_ID = "demo-acme"

JOHN = "john-smith"
SARAH = "sarah-jones"
MIKE = "michael-green"

# Two email humans and two LinkedIn humans - four, which is the shape the old
# one-per-channel model could not express.
SENDERS = (
    ("anna", "Anna Novak", "Senior Consultant"),
    ("mark", "Mark Reilly", "Consultant"),
    ("petar", "Petar Horvat", "Partner"),
    ("sara_s", "Sara Simic", "Consultant"),
)

# Fixed timestamps, so the demo tells the same story on every machine and two
# runs produce byte-identical account timelines.
AUG = "2026-08-%02dT%02d:00:00+00:00"


def _at(day, hour=9):
    return AUG % (day, hour)


def install(rows=None):
    """Add Acme to the demo estate. Returns the record.

    Called after `demodata.install()` has seeded workspaces, senders and
    records, so the roster it needs already exists.
    """
    roster = si.load() if rows is None else list(rows)
    roster = _ensure_senders(roster)

    senderteam.install([senderteam.new_team(
        WORKSPACE, "alpha", "Team Alpha",
        email_senders=["anna", "mark"],
        linkedin_senders=["petar", "sara_s"],
        note="Two email humans and two LinkedIn humans, working one account "
             "together. A sender outside this team cannot enter a cadence "
             "here.")], roster)

    rec = _record(roster)
    _plant(rec)

    existing = [r for r in store.load() if r["id"] != RECORD_ID]
    store.save(existing + [rec])
    return rec


def _ensure_senders(rows):
    """Add the four humans and their accounts if the estate lacks them."""
    have = {s["sender_id"] for s in si.senders(WORKSPACE, rows)}
    new = []
    for sender_id, name, title in SENDERS:
        if sender_id not in have:
            new.append(si.new_sender(WORKSPACE, sender_id, name, title=title,
                                     team="growth"))
    accounts = {a["account_id"] for a in si.email_accounts(WORKSPACE, rows)}
    profiles = {a["account_id"] for a in si.linkedin_accounts(WORKSPACE, rows)}
    # Anna owns several inboxes; the human is the identity, the inbox is
    # infrastructure. Two are enough to show the distinction.
    for account_id, sender_id, address in (
            ("anna-01", "anna", "anna01@productive.test"),
            ("anna-02", "anna", "anna02@productive.test"),
            ("mark-01", "mark", "mark01@productive.test")):
        if account_id not in accounts:
            new.append(si.new_email_account(WORKSPACE, account_id, sender_id,
                                            address))
    for account_id, sender_id, url in (
            ("petar-li", "petar", "https://www.linkedin.com/in/petarhorvat"),
            ("sara-li", "sara_s", "https://www.linkedin.com/in/sarasimic")):
        if account_id not in profiles:
            new.append(si.new_linkedin_account(WORKSPACE, account_id,
                                               sender_id, url))
    # `si.install` REPLACES the whole roster - it is documented as such and
    # the demo estate uses it that way. Passing only the new rows wiped every
    # sender the rest of the demo had already created, which showed up as a
    # timeline printing raw sender ids because the names no longer existed.
    if new:
        si.install(list(rows) + new)
    return si.load()


def _record(roster=None):
    rec = store.new_record(RECORD_ID, "domains", WORKSPACE, "Acme Ltd",
                           "acme.test")
    rec["demo"] = True
    rec["state"] = "qualified"
    # Its own batch, so it does not disturb the counts of the batches the
    # rest of the demo builds, and so it is not a record belonging to none.
    rec["batch"] = "abm-demo"
    # A real qualification verdict, not a flag. This account is qualified in
    # the demo story, and every other qualified record carries the evidence
    # that made it so - one that did not would be the only record in the
    # estate whose verdict came from nowhere.
    # The field names `qualify.company` actually writes: `icp_status`,
    # `icp_score`, `icp_tier`. This fixture used `status`/`tier`, which no
    # canonical reader looks at - so the flagship demo account was the one
    # record in the estate whose verdict was invisible to everything that
    # reads a verdict.
    rec["qualification"] = {
        "verdict": {"icp_status": "qualified", "icp_tier": "A",
                    "icp_score": 88.0, "icp_raw_score": 88.0,
                    "icp_confidence": "high",
                    "record_id": rec["id"], "domain": rec.get("domain"),
                    "classification_reasons": [
                        "services business", "operations leadership",
                        "United Kingdom", "50-200 employees"]},
        "segment_key": "PRODUCTIVE-ABM",
        "vertical": "professional_services",
        "subvertical": "consulting",
        "industry": "Management consulting",
        "employee_band": "50-200",
        "country": "United Kingdom",
        "region": "UK & Ireland",
        "timezone": "Europe/London",
    }
    rec["contacts"] = [
        {"key": JOHN, "name": "John Smith", "title": "Chief Operating Officer",
         "email": "john.smith@acme.test", "selected": True, "primary": True,
         "persona": "champion", "priority": account.PRIMARY,
         "linkedin": "https://www.linkedin.com/in/johnsmithacme",
         "verification": {"status": "valid",
                          "checks": ["contactout", "reoon"]}},
        {"key": SARAH, "name": "Sarah Jones", "title": "Chief Executive",
         "email": "sarah.jones@acme.test", "selected": True,
         "persona": "economic_buyer", "priority": account.SECONDARY,
         "linkedin": "https://www.linkedin.com/in/sarahjonesacme",
         "verification": {"status": "valid",
                          "checks": ["contactout", "reoon"]}},
        {"key": MIKE, "name": "Michael Green", "title": "Chief Financial "
                                                       "Officer",
         "email": "michael.green@acme.test", "selected": True,
         "persona": "economic_buyer", "priority": account.TERTIARY,
         "linkedin": "https://www.linkedin.com/in/michaelgreenacme",
         "verification": {"status": "valid",
                          "checks": ["contactout", "reoon"]}},
    ]
    rec["cadence"] = {}
    # Assignments come from the real allocator, not from literals.
    #
    # Hand-writing the shape produced two bugs: the wrong key, and a missing
    # `workspace` field that left a tenancy check unable to confirm the
    # sender belonged to this workspace. `allocate` writes the canonical
    # shape, and `prefer_sender_id` is how a fixture chooses the human
    # without reimplementing the choice.
    #
    # Different humans per person - deliberately, not by rotation.
    _assign(rec["contacts"][0], {"email": "anna", "linkedin": "petar"},
            roster, "campaign strategy: primary DM, senior pairing")
    _assign(rec["contacts"][1], {"email": "mark", "linkedin": "sara_s"},
            roster,
            "campaign strategy: a different human for the second DM at the "
            "same account")
    _assign(rec["contacts"][2], {"linkedin": "petar"}, roster,
            "LinkedIn-only contact; Petar has capacity")
    return rec


def _assign(contact, wanted, roster, reason):
    """Store a real allocation for each channel this contact should have.

    `assignment.allocate` produces the canonical row - workspace, provider,
    account id, address, the lot - so nothing here has to know that shape.
    A channel with no eligible sender is recorded as unavailable rather than
    raised, which is what `assignment.ensure` does too: a contact with no
    LinkedIn sender is an email-only contact, not a broken one.
    """
    block = contact.setdefault("sender_assignment", {})
    for channel, sender_id in wanted.items():
        try:
            row = assignment.allocate(WORKSPACE, contact["key"], channel,
                                      roster, prefer_sender_id=sender_id)
        except assignment.NoEligibleSender as e:
            block.setdefault("unavailable", {})[channel] = str(e)
            continue
        row["at"] = _at(1)
        row["reason"] = reason
        block[channel] = row
    block.setdefault("at", _at(1))
    block.setdefault("by", "demo")
    block["roster_digest"] = si.digest(WORKSPACE, roster)
    return block


def _account_id(rec, contact_key, channel):
    """The inbox or profile the allocator actually chose for this contact.

    Planted events must name the same account the assignment names. Writing
    a literal here produced "via mark01" on one panel and "via mark-01" on
    another - one inbox with two names.
    """
    for contact in rec.get("contacts") or []:
        if contact.get("key") == contact_key:
            row = (contact.get("sender_assignment") or {}).get(channel) or {}
            return row.get("account_id")
    return None


def _plant(rec):
    """The story, in order. Confirmed and planned kept strictly apart."""
    # --- John: two confirmed touches, then a positive reply with a referral.
    events.record(rec, events.PUSH_MARKED, contact_key=JOHN, channel="email",
                  step="day1", day=1, at=_at(1), sender_id="anna",
                  account_id=_account_id(rec, JOHN, "email"))
    events.record(rec, events.PUSH_MARKED, contact_key=JOHN,
                  channel="linkedin", step="day3", day=3, at=_at(3),
                  sender_id="petar",
                  account_id=_account_id(rec, JOHN, "linkedin"))
    events.record(rec, events.REPLY_RECEIVED, contact_key=JOHN,
                  channel="email", at=_at(5), provider="emailbison",
                  provider_event_id="demo-acme-reply-1")
    events.record(rec, events.REPLY_CLASSIFIED, contact_key=JOHN,
                  channel="email", at=_at(5), classification="positive",
                  confidence=0.82)
    events.record(rec, events.POSITIVE_REPLY_DETECTED, contact_key=JOHN,
                  channel="email", at=_at(5))
    # The referral is a recorded edge with both ends named. Nothing read it
    # out of the reply text; a classifier that did would be manufacturing an
    # introduction.
    # A distinct id. Reusing the reply's would have been deduplicated away by
    # `events.record`, which is right - the same provider event must not apply
    # twice - and would have left the referral silently missing.
    events.record(rec, events.REFERRAL_RECORDED, contact_key=JOHN,
                  referred_to=SARAH, channel="email", at=_at(5, 10),
                  provider_event_id="demo-acme-referral-1",
                  note="reply demo-acme-reply-1 was classified as a referral "
                       "and an operator named the target; the edge is "
                       "recorded, never read out of the text")

    # --- Sarah: one confirmed email from a *different* human, and a LinkedIn
    #     touch that is only planned. That pair is the whole demonstration.
    events.record(rec, events.PUSH_MARKED, contact_key=SARAH, channel="email",
                  step="day6", day=6, at=_at(6), sender_id="mark",
                  account_id=_account_id(rec, SARAH, "email"))
    events.record(rec, events.PUSH_PREPARED, contact_key=SARAH,
                  channel="linkedin", step="day8", day=8, at=_at(8),
                  sender_id="sara_s",
                  account_id=_account_id(rec, SARAH, "linkedin"))

    # --- Michael: planned only. Nothing may be claimed about him at all.
    events.record(rec, events.PUSH_PREPARED, contact_key=MIKE,
                  channel="linkedin", step="day9", day=9, at=_at(9),
                  sender_id="petar",
                  account_id=_account_id(rec, MIKE, "linkedin"))
    return rec


def scenarios(rec=None, rows=None):
    """What this account demonstrates, resolved live rather than asserted.

    Each row asks the real resolver rather than describing what it should
    say, so a demo that disagreed with the engine would show it.
    """
    from .. import outreachclaims as oc

    if rec is None:
        rec = next((r for r in store.load() if r["id"] == RECORD_ID), None)
    if rec is None:
        return []
    rows = si.load() if rows is None else rows
    permissive = {"outreach": {"claim_other_dm": "on",
                               "claim_other_dm_reply": "on"}}

    asked = (
        ("Sarah may cite John's referral",
         oc.REFERRAL, SARAH, None, None, None),
        ("Sarah may not claim Sara messaged her - that touch is planned",
         oc.SAME_CONTACT_COLLEAGUE_TOUCH, SARAH, "mark", None, "sara_s"),
        ("Sarah may cite Mark's own confirmed email",
         oc.SAME_CONTACT_PRIOR_TOUCH, SARAH, "mark", None, None),
        ("Michael may not mention John's reply - the claim is off by default",
         oc.OTHER_DM_REPLY, MIKE, "petar", JOHN, None),
        ("Michael may mention John's reply once the campaign allows it",
         oc.OTHER_DM_REPLY, MIKE, "petar", JOHN, None),
        ("Nobody may claim a conversation with John - he replied, we have "
         "not answered",
         oc.ACTIVE_CONVERSATION, SARAH, "mark", JOHN, None),
    )

    out = []
    for index, (title, claim, contact, sender, about, colleague) in \
            enumerate(asked):
        config = permissive if index == 4 else None
        decision = oc.resolve(claim, rec, contact, WORKSPACE, sender, about,
                              colleague, config, rows)
        out.append({
            "title": title,
            "claim": claim,
            "contact": contact,
            "allowed": bool(decision),
            "why": decision.get("why"),
            "policy": decision.get("policy"),
        })
    return out
