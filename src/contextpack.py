#!/usr/bin/env python3
"""The brief a person reads before a campaign goes anywhere.

## What this is for

`/campaigns/<id>` answers *is this campaign in order* - lint, QA, mapping,
whether the steps will run. The outreach preview answers *what would
arrive, at whom, on what day*. Neither answers the question somebody
actually asks before approving:

    why these companies, why now, and what may we say to them?

That question has four different answers living in four different places -
the segment that put them together, the priority that says they are worth
attention, the strategy that says which pain to lead with, and the claim
policy that says what a message may assert. A person assembling those by
hand is a person who will miss one.

## It asserts nothing of its own

Every number here is counted from records this caller could already read,
and every sentence is one some other module already stands behind:

    segments      why these companies are one group
    priority      which of them are worth attention now, and why
    signals       what is happening, with the evidence quoted
    strategy      which angle the evidence supports
    outreachclaims  what a message is allowed to say

There is no fifth opinion. Where two of them disagree, the pack shows both
rather than picking - a brief that resolves a contradiction silently is a
brief that hides the one thing worth reading.

## The three rules it exists to hold

**Supported and hypothetical never merge.** `strategy` already splits a
pain into "the company's own evidence fired this" and "typical for the
vertical, but nothing here supports it". Aggregating those into one list
of angles would turn a guess into a brief, so the two stay apart all the
way to the screen, and a pain no account in the campaign supports is
called out rather than quietly included.

**Priority is not permission, at campaign scale.** The pack reports how
many accounts are high priority *and* how many cannot be written to at
all, in the same block. A campaign of thirty high-priority accounts where
eleven are suppressed is a different campaign, and one number without the
other invites somebody to think otherwise.

**A signal is not a claim.** This is the rule most likely to be broken by
somebody reading this pack, because the evidence is right there and quotable.
`outreachclaims` decides what a message may assert, every claim type it
knows is about a prior touch or a relationship, and none of them licenses
mentioning an observation. So the pack carries the signals *and* says
plainly that they are a reason to prioritise rather than something to
write. See ACCOUNT-INTELLIGENCE.md.
"""
from . import (account, outreachclaims, priority as priority_module,
               senderidentity as si, signals as signals_module,
               strategy, touch)

# How many of each list a brief can carry before it stops being a brief.
# Capped rather than truncated silently: every block reports its own total
# beside what it shows.
TOP_ACCOUNTS = 8
EVIDENCE_PER_TYPE = 3


def _messaging(rec):
    """The strategy `qualify` already stored. Never recomputed here.

    Same reasoning as `priority._icp_fit` reading the verdict rather than
    scoring again: a second opinion about the angle would be a second
    angle, and the one on the record is the one the drafts were built to.
    """
    return ((rec.get("qualification") or {}).get("messaging") or {})


def _segment(rec):
    return ((rec.get("qualification") or {}).get("segment") or {})


def why_these(recs):
    """What put these companies in one group, and whether that is one thing.

    A campaign spanning four segments is not necessarily wrong, but it is
    something the person approving it should be told rather than left to
    infer from a list of company names.
    """
    keys = {}
    for rec in recs:
        qualification = rec.get("qualification") or {}
        key = qualification.get("segment_key")
        if not key:
            keys.setdefault(None, {"segment_key": None, "companies": 0,
                                   "reason": "not qualified yet",
                                   "rung": None})["companies"] += 1
            continue
        found = keys.setdefault(key, {
            "segment_key": key,
            "reason": qualification.get("segment_reason"),
            "rung": qualification.get("segment_rung"),
            "companies": 0,
        })
        found["companies"] += 1
    rows = sorted(keys.values(), key=lambda r: -r["companies"])
    return {
        "segments": rows,
        "one_segment": len([r for r in rows if r["segment_key"]]) == 1,
        "unqualified": sum(r["companies"] for r in rows
                           if not r["segment_key"]),
    }


def attention(assessments):
    """Priority across the campaign, with what cannot be written to beside it.

    The two counts are returned together and the caller cannot have one
    without the other. That is the whole point of the block: "22 high
    priority" and "9 of them blocked" are the same sentence.
    """
    tiers = {tier: 0 for tier in priority_module.TIERS}
    blocked = []
    for found in assessments:
        tiers[found["tier"]] += 1
        if not found["eligibility"]["eligible"]:
            blocked.append({
                "record_id": found["record_id"],
                "company": found["company"],
                "score": found["score"],
                "tier": found["tier"],
                "why": found["eligibility"]["blocked"],
                "action": found["eligibility"]["action"],
            })

    ranked = sorted(assessments, key=lambda f: -f["score"])
    return {
        "tiers": [{"tier": tier,
                   "label": priority_module.TIER_LABEL[tier],
                   "count": tiers[tier]}
                  for tier in priority_module.TIERS],
        "accounts": len(assessments),
        # Not a footnote. A campaign is only as big as the part of it that
        # may actually be worked.
        "blocked": blocked,
        "blocked_count": len(blocked),
        "workable": len(assessments) - len(blocked),
        "top": [{"record_id": f["record_id"], "company": f["company"],
                 "score": f["score"], "tier": f["tier"],
                 "why_now": f["why_now"],
                 "eligible": f["eligibility"]["eligible"],
                 "blocked": f["eligibility"]["blocked"]}
                for f in ranked[:TOP_ACCOUNTS]],
        "shown": min(len(ranked), TOP_ACCOUNTS),
    }


def live_signals(assessments, config=None):
    """What is happening across these accounts, with the evidence quoted.

    Quoted rather than summarised. "Three accounts are hiring" is a claim
    somebody could put in an email; "7 open delivery roles listed on the
    careers page" is a thing that was seen, and the difference is the whole
    reason the evidence field is mandatory.

    Stale signals are excluded from the counts and reported separately:
    they are still true, they are just no longer a reason to do anything
    today.
    """
    by_type = {}
    stale = 0
    for found in assessments:
        for entry in found["signals"]:
            if entry["freshness"] == signals_module.STALE:
                stale += 1
                continue
            bucket = by_type.setdefault(entry["type"], {
                "type": entry["type"], "label": entry["label"],
                "scope": entry["scope"], "count": 0, "accounts": set(),
                "evidence": [],
            })
            bucket["count"] += 1
            bucket["accounts"].add(found["record_id"])
            if len(bucket["evidence"]) < EVIDENCE_PER_TYPE:
                bucket["evidence"].append({
                    "company": found["company"],
                    "evidence": entry["evidence"],
                    "freshness": entry["freshness"],
                    "source": entry["source_label"],
                })

    rows = sorted(({**bucket, "accounts": len(bucket["accounts"])}
                   for bucket in by_type.values()),
                  key=lambda r: (-r["count"], r["label"]))
    # Split by scope, because "they are hiring" and "we have written to
    # them twice" are not the same kind of fact and only one of them is a
    # reason to start. Listing our own touches under "what is happening at
    # this account" is circular: it makes contacting somebody into evidence
    # that they were worth contacting.
    external = [r for r in rows if r["scope"] != signals_module.ENGAGEMENT]
    engagement = [r for r in rows if r["scope"] == signals_module.ENGAGEMENT]
    return {
        "types": rows,
        "external": external,
        "engagement": engagement,
        "live": sum(r["count"] for r in rows),
        "external_live": sum(r["count"] for r in external),
        "engagement_live": sum(r["count"] for r in engagement),
        "stale": stale,
        "accounts_with_signals": len(
            [f for f in assessments if f["signals"]]),
        "accounts_with_external": len(
            [f for f in assessments
             if any(s["scope"] != signals_module.ENGAGEMENT
                    and s["freshness"] != signals_module.STALE
                    for s in f["signals"])]),
        # Said here rather than left to the reader, because the evidence is
        # quotable and right there. What a message may assert is
        # `outreachclaims`, and no claim type it knows covers an
        # observation.
        "note": ("A signal is a reason to prioritise an account. It is not "
                 "permission to mention it: what a message may say is "
                 "decided by the claim rules, and none of them covers an "
                 "observation about the company."),
    }


def angles(recs, config=None):
    """Which pain the evidence supports across the campaign, and which it does not.

    The aggregation that matters: a pain supported by two accounts out of
    thirty is not a campaign angle, and a pain supported by none of them is
    a hypothesis that has been repeated until it sounded like a fact.
    """
    supported, hypothesis, verticals = {}, {}, {}
    qualified = 0
    for rec in recs:
        messaging = _messaging(rec)
        if not messaging:
            continue
        if messaging.get("vertical"):
            verticals[messaging["vertical"]] = verticals.get(
                messaging["vertical"], 0) + 1
        found = False
        for pain in messaging.get("relevant_pain_categories") or []:
            supported[pain] = supported.get(pain, 0) + 1
            found = True
        for pain in messaging.get("unsupported_hypotheses") or []:
            hypothesis[pain] = hypothesis.get(pain, 0) + 1
        if found:
            qualified += 1

    def rows(counter, kind):
        return sorted(
            ({"pain": pain,
              "describes": strategy.PAIN_WORDS.get(pain, pain),
              "companies": count,
              "share": (count / len(recs)) if recs else 0.0,
              "kind": kind}
             for pain, count in counter.items()),
            key=lambda r: (-r["companies"], r["pain"]))

    carried = rows(supported, "supported")
    guessed = rows(hypothesis, "hypothesis")
    # A pain that is typical for the vertical and supported by nobody here.
    # Named separately because it is the one most likely to end up in copy
    # on the strength of sounding right.
    unsupported_anywhere = [row for row in guessed
                            if row["pain"] not in supported]
    return {
        "supported": carried,
        "hypotheses": guessed,
        "unsupported_anywhere": unsupported_anywhere,
        "companies_with_supported_angle": qualified,
        "companies": len(recs),
        "verticals": sorted(({"vertical": k, "companies": v}
                             for k, v in verticals.items()),
                            key=lambda r: -r["companies"]),
        "why": (f"{qualified} of {len(recs)} companies have at least one "
                "angle their own evidence supports" if recs
                else "no companies in this campaign"),
    }


def claims(config=None):
    """What a message in this campaign is allowed to say.

    Read straight off `outreachclaims`, which is the only authority on it.
    Listed in the pack because the alternative is somebody inferring the
    policy from the drafts, and a draft is downstream of this.
    """
    rows = []
    for claim_type in outreachclaims.POLICY_KEYS:
        on, why = outreachclaims.allowed_by_policy(claim_type, config)
        rows.append({"claim": claim_type, "allowed": on, "why": why})
    rows.sort(key=lambda r: (not r["allowed"], r["claim"]))
    return {
        "claims": rows,
        "allowed": len([r for r in rows if r["allowed"]]),
        "total": len(rows),
        # The gap this pack is most likely to be misread as filling.
        "not_a_claim_type": (
            "Nothing here licenses mentioning something observed about the "
            "company - a funding round, a job posting, a new hire. Every "
            "claim type is about a prior touch or a relationship. An "
            "observation would need a claim type of its own before a "
            "message could rest on it."),
    }



# ------------------------------------------------------- what already happened
#
# The pack described what a campaign *would* do and said nothing about what
# these accounts have already heard. `account.graph` and `outreachclaims`
# both knew; neither was read here, so a brief about an account somebody had
# already emailed twice looked exactly like a brief about a cold one.

# A history block is a list of facts, and every fact costs a line on a
# screen somebody has to read. Capped, with the total beside it.
TOUCHES_PER_ACCOUNT = 12
ACCOUNTS_WITH_HISTORY = 12


class NotAFact(RuntimeError):
    """Something that has not happened was offered as history.

    Raised rather than filtered. A planned touch silently dropped from a
    list is a list that is quietly wrong; a planned touch that stops the
    build is one somebody fixes.
    """


def _fact(row, contact_name, company, record_id, workspace):
    """One confirmed event, as a fact a message decision may rest on.

    Refuses anything not confirmed. `touch.CONFIRMED_STATES` is the
    authority - sent, delivered, replied, positive reply - and planned,
    approved and payload-ready are none of them. A step that was built and
    never left is not outreach that happened, and this is the boundary
    where that stops being a comment and becomes an exception.

    The actor is read off the *event*. `push.mark_pushed` writes the sender
    onto the event at the moment it is sent precisely so a later
    reassignment cannot rewrite who wrote to whom - so a history built from
    the current assignment would put the wrong colleague's name in front of
    a prospect, which is the failure this whole layer exists to prevent.
    """
    if not row.get("confirmed") or row.get("state") not in touch.CONFIRMED_STATES:
        raise NotAFact(
            f"{row.get('state')!r} is not a confirmed state, so this is not "
            "something that happened: " + str(row.get("push_id") or row))
    return {
        "workspace": workspace,
        "record_id": record_id,
        "account": company,
        "contact_key": row.get("contact_key"),
        "contact": contact_name,
        "channel": row.get("channel"),
        "actor_id": row.get("sender_id"),
        "actor": row.get("actor"),
        "at": row.get("at"),
        "event": row.get("event"),
        "state": row.get("state"),
        "step": row.get("step"),
    }


def account_history(rec, workspace=None, rows=None, config=None, cap=None):
    """What this account has actually heard, and from whom.

    Built from `account.graph`, which is the canonical answer to every
    account-level question - not from a second walk of the event log with
    its own idea of what counts.

    Confirmed and planned are two different collections rather than one
    list with a flag. A caller iterating a mixed list and writing "we
    contacted" gets it wrong on the first planned row, and a boolean is
    exactly the kind of thing a template forgets to read. Planned work is
    counted, never described.
    """
    cap = TOUCHES_PER_ACCOUNT if cap is None else cap
    found = account.graph(rec, workspace, rows, config)
    names = {c["key"]: c.get("name") or c["key"] for c in found["contacts"]}
    company = found.get("company")
    record_id = found.get("record_id")

    senders = si.load() if rows is None else rows
    display = {row.get("sender_id"): row.get("display_name")
               for row in senders or []
               if row.get("workspace") in (None, workspace)}

    confirmed = []
    for row in found["confirmed_touches"]:
        confirmed.append(_fact(
            {**row, "actor": display.get(row.get("sender_id"))
             or row.get("sender_id")},
            names.get(row.get("contact_key"), row.get("contact_key")),
            company, record_id, workspace))
    confirmed.sort(key=lambda t: (str(t.get("at") or ""),
                                  str(t.get("contact_key") or "")))

    replies = [{
        "workspace": workspace,
        "record_id": record_id,
        "account": company,
        "contact_key": r.get("contact_key"),
        "contact": names.get(r.get("contact_key"), r.get("contact_key")),
        "channel": r.get("channel"),
        "at": r.get("at"),
        "classification": r.get("classification"),
        "positive": bool(r.get("positive")),
    } for r in found["replies"]]

    referrals = [{
        "workspace": workspace,
        "record_id": record_id,
        "account": company,
        "from_contact": edge.get("from_contact"),
        "from": edge.get("from_name"),
        "to_contact": edge.get("to_contact"),
        "to": edge.get("to_name"),
        "at": edge.get("at"),
        "channel": edge.get("channel"),
    } for edge in found["referrals"]]

    # Who this account has heard from, per channel, from confirmed touches
    # only. This is the set a "my colleague Anna emailed you" claim has to
    # be checked against, and `outreachclaims` is what does the checking -
    # the pack carries the evidence, it does not license the sentence.
    heard_from = {}
    for row in confirmed:
        if row["channel"] and row["actor"]:
            heard_from.setdefault(row["channel"], set()).add(row["actor"])

    planned = found["counts"]["planned"]
    return {
        "record_id": record_id,
        "account": company,
        "domain": found.get("domain"),
        "workspace": workspace,
        "confirmed_touches": confirmed[:cap],
        "confirmed_total": len(confirmed),
        "capped": len(confirmed) > cap,
        "replies": replies,
        "referrals": referrals,
        "heard_from": {channel: sorted(people)
                       for channel, people in sorted(heard_from.items())},
        "channels": sorted({t["channel"] for t in confirmed if t["channel"]}),
        "contacts_reached": len({t["contact_key"] for t in confirmed}),
        # Counted, never described. A number cannot be mistaken for a
        # sentence about something that happened.
        "planned_not_sent": planned,
        "cold": not confirmed,
        "note": "confirmed events only. Planned, approved and payload-ready "
                "steps are counted and never described: a step that was "
                "built and never left is not outreach that happened",
    }


def history(recs, workspace=None, rows=None, config=None,
            cap=ACCOUNTS_WITH_HISTORY):
    """Confirmed history for the campaign, accounts with any of it first.

    `rows` is the sender roster, read once by the caller. Left to itself
    `account.graph` loads it per account, which at campaign scale is the
    same file opened once per company.
    """
    rows = si.load() if rows is None else rows
    found = [account_history(rec, workspace, rows, config) for rec in recs]
    warm = [h for h in found if not h["cold"]]
    warm.sort(key=lambda h: (-h["confirmed_total"], str(h["record_id"])))

    return {
        "accounts": warm[:cap],
        "shown": min(len(warm), cap),
        "with_history": len(warm),
        "cold": len(found) - len(warm),
        "companies": len(found),
        "touches": sum(h["confirmed_total"] for h in found),
        "replies": sum(len(h["replies"]) for h in found),
        "referrals": sum(len(h["referrals"]) for h in found),
        "planned_not_sent": sum(h["planned_not_sent"] for h in found),
        "channels": sorted({c for h in found for c in h["channels"]}),
        "heard_from": sorted({person for h in found
                              for people in h["heard_from"].values()
                              for person in people}),
        "note": "what these accounts have already heard, and from whom. "
                "Confirmed events only - what this campaign *would* do is "
                "the rest of the pack",
    }

def build(recs, campaign=None, workspace=None, config=None, now=None,
          suppressed=None):
    """The pack. Nothing in it is computed twice and nothing is asserted.

    `recs` is already scoped - it comes from `repo.records()` - so this
    never widens what it was handed. Passing `suppressed` in once matters:
    `channels.evaluate` reads the suppression file whenever it is not given
    one, which at campaign scale is once per contact.
    """
    # Both read once for the whole campaign. Left to themselves,
    # `channels.evaluate` re-reads the suppression file per contact and
    # `signals.for_record` re-reads the signal file per account.
    index = signals_module.index(workspace)
    # The sender roster, once. `account.graph` loads it per account
    # otherwise, which at campaign scale opens one file per company.
    senders = si.load()
    assessments = [
        priority_module.assess(rec, workspace, config, now=now,
                               suppressed=suppressed, signal_index=index)
        for rec in recs]

    return {
        "campaign": ({"campaign_id": campaign.get("campaign_id"),
                      "name": campaign.get("name"),
                      "status": campaign.get("status")}
                     if campaign else None),
        "workspace": workspace,
        "companies": len(recs),
        "why_these": why_these(recs),
        "attention": attention(assessments),
        "signals": live_signals(assessments, config),
        "angles": angles(recs, config),
        "claims": claims(config),
        # What these accounts have already heard, and from whom. The pack
        # answered "why these, why now, what may we say" and said nothing
        # about what had already been said - so a brief for an account
        # somebody emailed twice last month read exactly like a brief for a
        # cold one.
        "history": history(recs, workspace, senders, config),
        "check": checklist(recs, assessments),
    }


def checklist(recs, assessments):
    """What the pack cannot settle, phrased as things to go and look at.

    Every item is conditional on something actually being the case, so an
    orderly campaign produces a short list rather than a ritual one. A
    checklist that always says the same six things is one nobody reads.
    """
    items = []
    grouping = why_these(recs)
    if not grouping["one_segment"] and len(grouping["segments"]) > 1:
        items.append({
            "what": "This campaign spans "
                    f"{len([s for s in grouping['segments'] if s['segment_key']])}"
                    " segments",
            "why": "one campaign means one story. Confirm the copy holds for "
                   "all of them, or split it."})
    if grouping["unqualified"]:
        items.append({
            "what": f"{grouping['unqualified']} company(s) have no ICP verdict",
            "why": "they score zero on fit, which reads as a low priority "
                   "rather than as an unanswered question."})

    blocked = [f for f in assessments if not f["eligibility"]["eligible"]]
    if blocked:
        items.append({
            "what": f"{len(blocked)} account(s) cannot be written to",
            "why": "suppressed or held. They are in the campaign and will "
                   "not receive anything; confirm that is intended rather "
                   "than an oversight."})

    angle_block = angles(recs)
    if angle_block["unsupported_anywhere"]:
        names = ", ".join(row["pain"] for row
                          in angle_block["unsupported_anywhere"][:3])
        items.append({
            "what": f"No company here supports: {names}",
            "why": "typical for the vertical and evidenced by nobody in this "
                   "campaign. If the copy leads with one of these, it is "
                   "leading with a guess."})
    if recs and not angle_block["companies_with_supported_angle"]:
        items.append({
            "what": "No company has an evidence-backed angle",
            "why": "every angle available to this campaign is a hypothesis."})

    manual = 0
    for found in assessments:
        manual += len([s for s in found["signals"]
                       if s.get("source") == signals_module.MANUAL])
    if manual:
        items.append({
            "what": f"{manual} signal(s) were entered by a person",
            "why": "nothing checks whether a hand-entered signal is an "
                   "observation or an impression. Read them as sentences "
                   "somebody may have to defend."})
    return items
