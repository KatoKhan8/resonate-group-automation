#!/usr/bin/env python3
"""What a message may say about outreach we have already done.

## Two different kinds of claim, two different modules

`src/claims.py` checks claims about *the prospect*: "congratulations on the
Series B", "your team of 200". Those are checked against stored company
evidence.

This module checks claims about *us*: "my colleague Anna emailed you", "John
suggested I reach out", "I've been speaking with your COO". Those are checked
against the account's own event log, because they are statements about things
Resonate did, and Resonate's record of what it did is authoritative.

Both exist because the failure modes are different and both are fatal. A wrong
fact about the prospect reads as not having done the homework. A wrong fact
about our own outreach reads as a lie, because the prospect can simply ask the
colleague who supposedly wrote to them.

## Every claim has a type, and every type has a minimum

There is no generic "is this sentence supportable" check. A claim is one of
the types in `CLAIMS`, and each names the exact evidence it needs. That makes
the rule readable in one place and makes "what would it take to say this"
answerable without reading the generator.

The ladder runs from cheap to expensive:

    SAME_CONTACT_PRIOR_TOUCH      we wrote to this person before
    SAME_CONTACT_COLLEAGUE_TOUCH  a named colleague wrote to this person
    OTHER_DM_PRIOR_TOUCH          we wrote to somebody else here
    OTHER_DM_COLLEAGUE_TOUCH      a named colleague wrote to somebody else here
    OTHER_DM_REPLY                somebody else here answered
    REFERRAL                      somebody here told us to talk to this person
    ACTIVE_CONVERSATION           we are actually in a conversation

`ACTIVE_CONVERSATION` is deliberately the hardest. "I've been speaking with
John" is the claim most likely to be made carelessly and most likely to be
checked: a sent message is not a conversation, and a prospect who forwards
that sentence to John gets an immediate denial.

## Fails closed, always

`resolve()` returns a decision with `allowed` false and a reason whenever it
cannot establish the evidence. There is no path that returns a maybe, and no
caller can obtain the boolean without the reason - so a preview screen cannot
show a permitted claim without also showing what permits it.

## A claim is not a sentence

The claim is *semantic*: `SAME_CONTACT_COLLEAGUE_TOUCH`, actor Mark, target
Sarah, channel email, confirmed on 6 August. The sentence is what a message
would say about it.

Those were conflated once, and the result was the worst kind of bug in this
system: the screen showed

    ALLOWED  "my colleague Anna emailed you earlier this week"
             evidence: Mark Weber confirmed email on day 6

The resolver was right - the evidence really was Mark's - but the sentence
beside it was a hardcoded illustration naming a different colleague. An
operator reading that row would have believed the system had cleared a
sentence about Anna.

So `CLAIMS` now holds a *template* with named slots and no person in it, and
`phrase()` fills the slots from the decision's own evidence. A sentence and
its evidence cannot disagree, because the sentence is built out of the
evidence.

## Temporal language is evidence too

"Earlier this week" is a claim about a date. `when()` derives it from the
evidence timestamp and refuses to guess: a touch whose date cannot be read,
or which is too old to describe crisply, gets no temporal phrase at all
rather than a plausible one. "Recently" is the safe fallback; a wrong "last
week" is a small lie that a prospect can check against their own inbox.

## Permission is not obligation

A campaign switches each claim type on or off (`POLICY_KEYS`). Evidence
existing does not mean a message should use it: being told that four people
at your company have been contacted by three different strangers is not
warmth, it is surveillance. The defaults are conservative and the widening is
a deliberate campaign setting.
"""
import collections
import datetime

from . import account, senderidentity as si

# ------------------------------------------------------------- claim types

SAME_CONTACT_PRIOR_TOUCH = "same_contact_prior_touch"
SAME_CONTACT_COLLEAGUE_TOUCH = "same_contact_colleague_touch"
OTHER_DM_PRIOR_TOUCH = "other_dm_prior_touch"
OTHER_DM_COLLEAGUE_TOUCH = "other_dm_colleague_touch"
OTHER_DM_REPLY = "other_dm_reply"
REFERRAL = "referral"
ACTIVE_CONVERSATION = "active_conversation"

TYPES = (SAME_CONTACT_PRIOR_TOUCH, SAME_CONTACT_COLLEAGUE_TOUCH,
         OTHER_DM_PRIOR_TOUCH, OTHER_DM_COLLEAGUE_TOUCH, OTHER_DM_REPLY,
         REFERRAL, ACTIVE_CONVERSATION)

# type -> (label, sentence template, the minimum evidence in words)
#
# The template carries slots, never a person. `{actor}` is the human whose
# touch is the evidence, `{other}` the third party, `{verb}` the channel's
# past tense, `{when}` a temporal phrase derived from the evidence date - and
# each is filled by `phrase()` from the decision that was actually resolved.
#
# A hardcoded name here is how the screen once offered "my colleague Anna
# emailed you" beside evidence belonging to Mark.
CLAIMS = {
    SAME_CONTACT_PRIOR_TOUCH: (
        "Own prior touch",
        "I {verb} you{when}",
        "a confirmed touch from this sender to this contact"),
    SAME_CONTACT_COLLEAGUE_TOUCH: (
        "Colleague handoff",
        "my colleague {actor} {verb} you{when}",
        "a confirmed touch from the named colleague to this contact"),
    OTHER_DM_PRIOR_TOUCH: (
        "Other decision maker",
        "I also reached out to {other} on your team{when}",
        "a confirmed touch from this sender to the named colleague of theirs"),
    OTHER_DM_COLLEAGUE_TOUCH: (
        "Colleague to other decision maker",
        "my colleague {actor} {verb} {other}{when}",
        "a confirmed touch from the named colleague to the named contact"),
    OTHER_DM_REPLY: (
        "Other decision maker replied",
        "{other} came back to us{when}",
        "a recorded reply event from the named contact"),
    REFERRAL: (
        "Referral",
        "{other} suggested I reach out",
        "a recorded referral edge from the named contact to this one"),
    ACTIVE_CONVERSATION: (
        "Active conversation",
        "I have been speaking with {other}",
        "a reply from the named contact AND a confirmed touch after it"),
}

# What a message may call a touch on each channel. "Messaged" rather than
# "DMed" because a prospect reads it, and past tense because every claim is
# about something that already happened.
VERBS = {"email": "emailed", "linkedin": "messaged"}
DEFAULT_VERB = "contacted"

# The campaign switch for each, and whether it is on when nobody has decided.
#
# Everything that names a *third party* is off by default. A prospect hearing
# that we have also been working their CFO has learned something about how
# they are being sold to rather than about their own problem, and the burden
# of turning that on belongs on whoever wants it.
POLICY_KEYS = {
    SAME_CONTACT_PRIOR_TOUCH: ("outreach.claim_same_contact", True),
    SAME_CONTACT_COLLEAGUE_TOUCH: ("outreach.claim_colleague", True),
    OTHER_DM_PRIOR_TOUCH: ("outreach.claim_other_dm", False),
    OTHER_DM_COLLEAGUE_TOUCH: ("outreach.claim_other_dm_colleague", False),
    OTHER_DM_REPLY: ("outreach.claim_other_dm_reply", False),
    REFERRAL: ("outreach.claim_referral", True),
    ACTIVE_CONVERSATION: ("outreach.claim_conversation", False),
}


class Decision(dict):
    """A claim decision. Truthy only when the claim is allowed.

    A dict so it renders and serialises like everything else here, and a
    class so `if decision:` reads correctly at a call site - a caller that
    forgets `["allowed"]` gets the right answer rather than a silent yes.
    """

    def __bool__(self):
        return bool(self.get("allowed"))


def _no(claim_type, why, **extra):
    return Decision(allowed=False, claim=claim_type, why=why, evidence=None,
                    **extra)


def _yes(claim_type, why, evidence, **extra):
    return Decision(allowed=True, claim=claim_type, why=why,
                    evidence=evidence, **extra)


def allowed_by_policy(claim_type, config=None):
    """Is this claim type switched on for this campaign? Returns (bool, why)."""
    key, default = POLICY_KEYS.get(claim_type, (None, False))
    if key is None:
        return False, f"{claim_type} is not a claim type this system knows"
    value = _at(config or {}, key)
    if value is None:
        return bool(default), (
            f"{key} is not configured; the default is "
            f"{'on' if default else 'off'}")
    on = str(value).strip().lower() in ("on", "true", "yes", "1")
    return on, f"{key} is {'on' if on else 'off'}"


def _at(config, dotted):
    node = config or {}
    for part in dotted.split("."):
        if not isinstance(node, dict):
            return None
        node = node.get(part)
    return node


def _sender_name(workspace, sender_id, rows=None):
    if not sender_id:
        return None
    entry = si.sender(workspace, sender_id, rows) if workspace else None
    return (entry or {}).get("display_name") or sender_id


def resolve(claim_type, rec, contact_key, workspace=None, sender_id=None,
            about_contact=None, about_sender=None, config=None, rows=None):
    """Can this message make this claim? Returns a `Decision`.

    `contact_key`   who is being written to
    `sender_id`     who is writing
    `about_contact` the third party the claim names, if any
    `about_sender`  the colleague the claim names, if any

    Policy is checked before evidence, deliberately. A campaign that has not
    switched a claim on should not cause the account graph to be walked
    looking for permission it would not use, and the refusal reason should say
    "off" rather than "no evidence" - those are different problems with
    different fixes.
    """
    if claim_type not in TYPES:
        return _no(claim_type, f"unknown claim type: {claim_type!r}")

    on, why = allowed_by_policy(claim_type, config)
    if not on:
        return _no(claim_type, f"this campaign does not allow it: {why}",
                   policy=False)

    rows = si.load() if rows is None else rows
    handler = _HANDLERS[claim_type]
    decision = handler(rec, contact_key, workspace, sender_id, about_contact,
                       about_sender, rows)
    decision["policy"] = True
    return decision


# ------------------------------------------------------------- the handlers
#
# One per claim type. Each returns a Decision and each is written to fail
# closed: every branch that cannot establish a fact ends in `_no`.


def _same_contact_prior(rec, contact_key, workspace, sender_id, about_contact,
                        about_sender, rows):
    if not sender_id:
        return _no(SAME_CONTACT_PRIOR_TOUCH, "no sender was named")
    found = account.has_confirmed_touch(rec, contact_key, sender_id=sender_id)
    if not found:
        return _no(SAME_CONTACT_PRIOR_TOUCH,
                   f"{_sender_name(workspace, sender_id, rows)} has no "
                   f"confirmed touch to this contact")
    return _yes(SAME_CONTACT_PRIOR_TOUCH,
                f"{_sender_name(workspace, sender_id, rows)} confirmed "
                f"{found['channel']} on day {found['day']}", found)


def _same_contact_colleague(rec, contact_key, workspace, sender_id,
                            about_contact, about_sender, rows):
    if not about_sender:
        return _no(SAME_CONTACT_COLLEAGUE_TOUCH, "no colleague was named")
    if about_sender == sender_id:
        return _no(SAME_CONTACT_COLLEAGUE_TOUCH,
                   "that is the sender writing, not a colleague")
    found = account.has_confirmed_touch(rec, contact_key,
                                        sender_id=about_sender)
    name = _sender_name(workspace, about_sender, rows)
    if not found:
        return _no(SAME_CONTACT_COLLEAGUE_TOUCH,
                   f"{name} has no confirmed touch to this contact")
    return _yes(SAME_CONTACT_COLLEAGUE_TOUCH,
                f"{name} confirmed {found['channel']} on day {found['day']}",
                found)


def _other_dm_prior(rec, contact_key, workspace, sender_id, about_contact,
                    about_sender, rows):
    if not about_contact:
        return _no(OTHER_DM_PRIOR_TOUCH, "no other contact was named")
    if about_contact == contact_key:
        return _no(OTHER_DM_PRIOR_TOUCH,
                   "that is the recipient, not another decision maker")
    if not sender_id:
        return _no(OTHER_DM_PRIOR_TOUCH, "no sender was named")
    found = account.has_confirmed_touch(rec, about_contact,
                                        sender_id=sender_id)
    if not found:
        return _no(OTHER_DM_PRIOR_TOUCH,
                   f"{_sender_name(workspace, sender_id, rows)} has no "
                   f"confirmed touch to that contact")
    return _yes(OTHER_DM_PRIOR_TOUCH,
                f"confirmed {found['channel']} to that contact on day "
                f"{found['day']}", found)


def _other_dm_colleague(rec, contact_key, workspace, sender_id, about_contact,
                        about_sender, rows):
    if not about_contact or not about_sender:
        return _no(OTHER_DM_COLLEAGUE_TOUCH,
                   "both a colleague and a contact must be named")
    if about_contact == contact_key:
        return _no(OTHER_DM_COLLEAGUE_TOUCH,
                   "that is the recipient, not another decision maker")
    found = account.has_confirmed_touch(rec, about_contact,
                                        sender_id=about_sender)
    name = _sender_name(workspace, about_sender, rows)
    if not found:
        return _no(OTHER_DM_COLLEAGUE_TOUCH,
                   f"{name} has no confirmed touch to that contact")
    return _yes(OTHER_DM_COLLEAGUE_TOUCH,
                f"{name} confirmed {found['channel']} to that contact on day "
                f"{found['day']}", found)


def _other_dm_reply(rec, contact_key, workspace, sender_id, about_contact,
                    about_sender, rows):
    if not about_contact:
        return _no(OTHER_DM_REPLY, "no other contact was named")
    if about_contact == contact_key:
        return _no(OTHER_DM_REPLY, "that is the recipient")
    found = account.has_reply(rec, about_contact)
    if not found:
        return _no(OTHER_DM_REPLY, "that contact has not replied")
    return _yes(OTHER_DM_REPLY,
                f"reply recorded on {found['channel'] or 'unknown channel'}",
                found)


def _referral(rec, contact_key, workspace, sender_id, about_contact,
              about_sender, rows):
    edge = account.referred_by(rec, contact_key)
    if not edge:
        return _no(REFERRAL, "no referral to this contact is recorded")
    if about_contact and edge["from_contact"] != about_contact:
        return _no(REFERRAL,
                   "the referral on record came from somebody else")
    return _yes(REFERRAL,
                f"referral recorded from {edge['from_name']}", edge,
                referred_by=edge["from_contact"])


def _active_conversation(rec, contact_key, workspace, sender_id, about_contact,
                         about_sender, rows):
    """The hardest one, and the one most often claimed carelessly.

    A sent message is not a conversation. Two-way traffic is: they replied,
    and somebody answered that reply. A prospect who forwards "I've been
    speaking with John" to John will find out immediately whether it is true.
    """
    target = about_contact or contact_key
    reply = account.has_reply(rec, target)
    if not reply:
        return _no(ACTIVE_CONVERSATION,
                   "that contact has not replied, so there is no conversation")
    after = [t for t in account.touches(rec, target, confirmed_only=True)
             if str(t.get("at") or "") > str(reply.get("at") or "")]
    if not after:
        return _no(ACTIVE_CONVERSATION,
                   "they replied, but nobody has answered - a reply alone is "
                   "not a conversation")
    return _yes(ACTIVE_CONVERSATION,
                "they replied and we answered", {"reply": reply,
                                                 "response": after[0]})


_HANDLERS = {
    SAME_CONTACT_PRIOR_TOUCH: _same_contact_prior,
    SAME_CONTACT_COLLEAGUE_TOUCH: _same_contact_colleague,
    OTHER_DM_PRIOR_TOUCH: _other_dm_prior,
    OTHER_DM_COLLEAGUE_TOUCH: _other_dm_colleague,
    OTHER_DM_REPLY: _other_dm_reply,
    REFERRAL: _referral,
    ACTIVE_CONVERSATION: _active_conversation,
}


# ------------------------------------------------------------ the language

# How far back a touch may be and still be described crisply. Beyond this the
# phrase becomes "recently", because "last month" invites the prospect to
# check and a month is long enough that they will not remember either way.
CRISP_DAYS = 13


def when(evidence, now=None):
    """A temporal phrase for this evidence, or "" if none is safe.

    Derived, never assumed. An unreadable date, a future date, or one far
    enough back that no short phrase is honest all produce no phrase at all -
    a sentence with no "when" in it is always true, and a wrong "earlier this
    week" is a small lie the prospect can check against their own inbox.
    """
    at = (evidence or {}).get("at") if isinstance(evidence, dict) else None
    if not at:
        return ""
    try:
        stamp = datetime.datetime.fromisoformat(str(at))
    except ValueError:
        return ""
    current = now or datetime.datetime.now(datetime.timezone.utc)
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=datetime.timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=datetime.timezone.utc)
    days = (current.date() - stamp.date()).days
    if days < 0:
        return ""                       # in the future; say nothing
    if days == 0:
        return " earlier today"
    if days == 1:
        return " yesterday"
    if days <= 6 and stamp.isocalendar()[:2] == current.isocalendar()[:2]:
        return " earlier this week"
    if days <= 6:
        return " a few days ago"
    if days <= CRISP_DAYS:
        return " last week"
    return " recently"


def phrase(claim_type, decision, rec=None, workspace=None, rows=None,
           now=None):
    """The sentence this decision licenses, built from its own evidence.

    Returns None for a refused claim. There is no path that produces a
    sentence without a decision to build it from, which is what stops a
    screen showing an illustration and calling it cleared copy.
    """
    if not decision or not decision.get("allowed"):
        return None
    template = CLAIMS.get(claim_type, (None, None, None))[1]
    if not template:
        return None

    evidence = decision.get("evidence") or {}
    if claim_type == ACTIVE_CONVERSATION and isinstance(evidence, dict):
        evidence = evidence.get("response") or evidence.get("reply") or {}

    actor = _sender_name(workspace, decision.get("about_sender")
                         or evidence.get("sender_id"), rows)
    other = _contact_name(rec, decision.get("about_contact")
                          or decision.get("referred_by")
                          or evidence.get("from_contact")
                          or evidence.get("contact_key"))
    verb = VERBS.get(evidence.get("channel"), DEFAULT_VERB)

    # A template naming somebody we cannot name produces no sentence at all.
    if "{actor}" in template and not actor:
        return None
    if "{other}" in template and not other:
        return None

    return template.format(actor=actor or "", other=other or "", verb=verb,
                           when=when(evidence, now)).strip()


def _contact_name(rec, contact_key):
    if not rec or not contact_key:
        return None
    for contact in rec.get("contacts") or []:
        if contact.get("key") == contact_key:
            return contact.get("name") or contact_key
    return contact_key


def describe_template(claim_type):
    """The template with its slots spelled out, for a refused claim.

    A refused row still has to say what it *would* let a message say, and it
    has no evidence to build a real sentence from. Naming the roles is honest
    where naming a person would not be.
    """
    template = CLAIMS.get(claim_type, (None, "", None))[1]
    return (template.format(actor="[colleague]", other="[contact]",
                            verb="contacted", when="").strip())


def available(rec, contact_key, workspace=None, sender_id=None, config=None,
              rows=None):
    """Every claim this message could make, and why each is or is not open.

    What the outreach preview renders. Showing the refused ones matters as
    much as the allowed ones: "why can this message not mention John" is a
    question an operator asks, and the answer is either "no evidence" or
    "the campaign has it switched off", which are different.
    """
    rows = si.load() if rows is None else rows
    graph = account.graph(rec, workspace, rows)
    others = [c for c in graph["contacts"] if c["key"] != contact_key]

    out = []
    for claim_type in TYPES:
        label, _template, minimum = CLAIMS[claim_type]
        # A claim about a third party needs a third party to be about. Try
        # each other decision maker and report the first that works, so the
        # preview can say "allowed, about John" rather than a bare no.
        candidates = [(None, None)]
        if claim_type in (OTHER_DM_PRIOR_TOUCH, OTHER_DM_COLLEAGUE_TOUCH,
                          OTHER_DM_REPLY, ACTIVE_CONVERSATION):
            candidates = [(c["key"], None) for c in others] or [(None, None)]
        if claim_type in (SAME_CONTACT_COLLEAGUE_TOUCH,
                          OTHER_DM_COLLEAGUE_TOUCH):
            colleagues = sorted({t["sender_id"]
                                 for t in graph["confirmed_touches"]
                                 if t.get("sender_id")
                                 and t["sender_id"] != sender_id})
            candidates = ([(about, colleague)
                           for about, _ in candidates
                           for colleague in colleagues]
                          or [(None, None)])

        # A claim about a third party with no third party to be about is
        # refused with that as the reason. Leaving `decision` None would put
        # an unexplained refusal on the preview, and every other refusal here
        # carries its own sentence.
        decision = _no(claim_type,
                       "there is nobody else at this account to name"
                       if claim_type in (OTHER_DM_PRIOR_TOUCH,
                                         OTHER_DM_COLLEAGUE_TOUCH,
                                         OTHER_DM_REPLY)
                       else "no colleague has a confirmed touch here")
        for about_contact, about_sender in candidates:
            decision = resolve(claim_type, rec, contact_key, workspace,
                               sender_id, about_contact, about_sender,
                               config, rows)
            if decision:
                decision["about_contact"] = about_contact
                decision["about_sender"] = about_sender
                break
        # `decision` is always a Decision here, and a refused one is falsy by
        # design - so `(decision or {})` would collapse every refusal to an
        # empty dict and silently drop the reason. Read it directly.
        # The sentence, built from this decision's own evidence. A refused
        # claim gets the slot-named template instead, because there is
        # nobody to name and inventing one is the bug this replaced.
        sentence = phrase(claim_type, decision, rec, workspace, rows)
        out.append({
            "claim": claim_type,
            "label": label,
            "example": sentence or describe_template(claim_type),
            "phrase": sentence,
            "template": describe_template(claim_type),
            "minimum": minimum,
            "allowed": bool(decision),
            "why": decision.get("why"),
            "evidence": decision.get("evidence"),
            "about_contact": decision.get("about_contact"),
            "about_sender": decision.get("about_sender"),
            "policy": decision.get("policy"),
        })
    return out


def summarise(rec, workspace=None, config=None, rows=None):
    """How many claims are open per contact. For the account view."""
    rows = si.load() if rows is None else rows
    graph = account.graph(rec, workspace, rows)
    counts = collections.OrderedDict()
    for contact in graph["contacts"]:
        senders = contact.get("senders") or {}
        sender_id = ((senders.get("email") or {}).get("sender_id")
                     or (senders.get("linkedin") or {}).get("sender_id"))
        open_claims = [c for c in available(rec, contact["key"], workspace,
                                            sender_id, config, rows)
                       if c["allowed"]]
        counts[contact["key"]] = {
            "contact": contact["name"],
            "allowed": [c["claim"] for c in open_claims],
            "count": len(open_claims),
        }
    return counts


# ------------------------------------------------------ the safe context bundle
#
# `available()` answers a diagnostic question: which of the seven claim types
# would resolve, and why. That is the right question for somebody debugging
# the resolver and the wrong one for an operator about to approve a message,
# who is asking:
#
#     What can this message safely say, and what is it about to do?
#
# `bundle()` answers that. It returns the facts a message may draw on, each
# already reduced to a sentence and its evidence, plus what is planned next.
# Nothing in it is a claim type or a policy key - those live in `available()`,
# which the diagnostics view still shows.


def bundle(rec, contact_key, workspace=None, sender_id=None, campaign=None,
           config=None, rows=None, now=None):
    """Everything a message to this contact may safely draw on.

    Grouped by where the fact comes from rather than by claim type, because
    "what do we know about this person" and "what do we know about their
    company" are different kinds of context and a writer uses them
    differently.

    Every entry carries the sentence it licenses AND the evidence behind it.
    A caller cannot take one without the other, which is the same discipline
    `resolve()` applies to the boolean.
    """
    rows = si.load() if rows is None else rows
    graph = account.graph(rec, workspace, rows, config)
    entry = graph["by_contact"].get(contact_key) or {}
    listed = available(rec, contact_key, workspace, sender_id, config, rows)
    by_claim = {c["claim"]: c for c in listed}

    def usable(claim_type):
        found = by_claim.get(claim_type) or {}
        if not found.get("allowed") or not found.get("phrase"):
            return None
        return {"say": found["phrase"], "because": found["why"],
                "claim": claim_type, "evidence": found["evidence"],
                "about_contact": found.get("about_contact"),
                "about_sender": found.get("about_sender")}

    direct = [u for u in (usable(SAME_CONTACT_PRIOR_TOUCH),
                          usable(SAME_CONTACT_COLLEAGUE_TOUCH)) if u]
    across = [u for u in (usable(OTHER_DM_PRIOR_TOUCH),
                          usable(OTHER_DM_COLLEAGUE_TOUCH),
                          usable(OTHER_DM_REPLY),
                          usable(ACTIVE_CONVERSATION)) if u]
    referral = usable(REFERRAL)

    # What the rest of the account has done, as plain facts rather than as
    # things a message may say. An operator wants to see this even where no
    # claim is permitted - knowing the CFO was approached last week is
    # relevant to writing to the CEO whether or not the letter mentions it.
    elsewhere = []
    for other in graph["contacts"]:
        if other["key"] == contact_key or not other["confirmed_touches"]:
            continue
        last = other["confirmed_touches"][-1]
        elsewhere.append({
            "contact": other["name"] or other["key"],
            "contact_key": other["key"],
            "channel": last.get("channel"),
            "sender": _sender_name(workspace, last.get("sender_id"), rows),
            "at": last.get("at"),
            "replied": bool(other["replies"]),
            "positive": other["positive"],
            "state": other["state"],
        })
    elsewhere.sort(key=lambda e: str(e.get("at") or ""), reverse=True)

    history = [{
        "channel": t.get("channel"),
        "sender": _sender_name(workspace, t.get("sender_id"), rows),
        "account_id": t.get("account_id"),
        "at": t.get("at"),
        "day": t.get("day"),
    } for t in entry.get("confirmed_touches") or []]

    return {
        "contact": entry.get("name") or contact_key,
        "contact_key": contact_key,
        "title": entry.get("title"),
        "state": entry.get("state"),
        "priority": entry.get("priority"),
        # What may be said, grouped by where it comes from.
        "direct": direct,
        "account": across,
        "referral": referral,
        "anything": bool(direct or across or referral),
        # Plain facts, said or not.
        "sender_history": history,
        "account_activity": elsewhere,
        "engagement": {
            "replied": bool(entry.get("replies")),
            "positive": bool(entry.get("positive")),
            "account_positive": graph["counts"]["positive"] > 0,
            "account_engaged": graph["counts"]["engaged"] > 0,
        },
        # The diagnostics, kept available but not the headline.
        "claims": listed,
    }


def suggested(bundle_, limit=3):
    """A few sentences a message could safely open with.

    Deterministic and drawn only from `bundle`. Labelled SUGGESTED wherever
    it is rendered: this is context somebody may use, not copy anybody has
    approved, and the distinction matters because approved copy is a thing
    this system tracks separately.
    """
    out = []
    if bundle_.get("referral"):
        out.append(bundle_["referral"])
    out += bundle_.get("direct") or []
    out += bundle_.get("account") or []
    return out[:limit]
