#!/usr/bin/env python3
"""What a reply from one person does to everybody else at the company.

## The question account-based outreach forces

John replies positively. Sarah has outreach planned for Thursday. Michael has
outreach planned for Friday.

Under the old one-contact model this had no answer because it could not
happen. Under the new one it happens constantly, and leaving it implicit
means the software picks - which is the one thing it must not do with a
decision this consequential.

So it is a policy, written down, with a stated default and a stated reason.

## What today's behaviour actually is

Before this module, **any** reply paused the whole company: `events.apply`
sets `rec["paused"]` and every contact reads as paused. That is conservative
and it is not always right - "not interested" from a junior contact stopping
an account where the CFO has not been approached is a lost account, and
"please remove our company" stopping only one person is a compliance problem.

This module does not change what happens today. It **names** the policies,
resolves which one applies, and reports the decision so the Reply Center and
campaign QA can show it. Wiring an alternative to the current pause is a
separate, deliberate change - see `POSITIVE_DEFAULT` below.

## The safe default is HOLD, not CONTINUE

A positive reply from one decision maker is the moment an account is most
likely to be mishandled. Continuing to cold-approach three of their
colleagues while a conversation is starting reads, from inside the company,
as one agency that does not talk to itself.

So the default is HOLD: other decision makers stop advancing and a person
decides. It is recoverable in a way that a sent message is not.
"""
from . import account, events, store

# --------------------------------------------------- what a reply may mean
#
# The canonical outcomes a reply gets classified into, and what each one is
# about. Deliberately a closed set: a free-text outcome is a category nobody
# can report on.
POSITIVE = "positive"
NEUTRAL = "neutral"
NEGATIVE = "negative"
NOT_NOW = "not_now"
NOT_ICP = "not_icp"
WRONG_PERSON = "wrong_person"
LEFT_COMPANY = "left_company"
EXISTING_CLIENT = "existing_client"
REFERRAL = "referral"
UNSUBSCRIBE = "unsubscribe"
ACCOUNT_DNC = "account_do_not_contact"
UNKNOWN = "unknown"

OUTCOMES = (POSITIVE, NEUTRAL, NEGATIVE, NOT_NOW, NOT_ICP, WRONG_PERSON,
            LEFT_COMPANY, EXISTING_CLIENT, REFERRAL, UNSUBSCRIBE,
            ACCOUNT_DNC, UNKNOWN)

OUTCOME_LABEL = {
    POSITIVE: "Positive", NEUTRAL: "Neutral", NEGATIVE: "Not interested",
    NOT_NOW: "Not now", NOT_ICP: "Not a fit", WRONG_PERSON: "Wrong person",
    LEFT_COMPANY: "Left the company", EXISTING_CLIENT: "Existing client",
    REFERRAL: "Referral", UNSUBSCRIBE: "Unsubscribe",
    ACCOUNT_DNC: "Company-wide do not contact", UNKNOWN: "Unclassified",
}

# ------------------------------------------------------------ what happens

CONTINUE = "continue"
HOLD = "hold"
STOP = "stop"
REVIEW = "review"
ACTIONS = (CONTINUE, HOLD, STOP, REVIEW)

ACTION_LABEL = {
    CONTINUE: "Carry on",
    HOLD: "Hold - a person decides",
    STOP: "Stop",
    REVIEW: "Needs review before anything else goes out",
}

# The scope a reply's effect reaches.
CONTACT = "contact"
ACCOUNT = "account"

# Every policy this system understands, its key, its default, and why.
#
# The defaults lean towards holding. Every one of them is recoverable: a hold
# somebody lifts costs a day, and a message sent into a conversation that had
# already started cannot be recalled.
POLICIES = (
    ("reply.on_positive", HOLD, ACCOUNT,
     "Another decision maker replied positively",
     "Cold-approaching three colleagues while a conversation is starting "
     "reads as one agency that does not talk to itself."),
    ("reply.on_neutral", HOLD, CONTACT,
     "A contact replied without saying yes or no",
     "Somebody should read it before the next step goes out to them. It says "
     "nothing about their colleagues."),
    ("reply.on_negative", CONTINUE, CONTACT,
     "A contact said they are not interested",
     "One person declining is not the company declining. Their own sequence "
     "stops; their colleagues are a separate question."),
    ("reply.on_unsubscribe", STOP, CONTACT,
     "A contact asked to be removed",
     "An explicit request, honoured immediately and permanently, for that "
     "person."),
    ("reply.on_account_dnc", STOP, ACCOUNT,
     "Somebody asked us to stop contacting the company",
     "A company-wide request must reach every contact there, not only the "
     "person who sent it."),
    ("reply.on_referral", HOLD, CONTACT,
     "A contact pointed us at somebody else",
     "The referrer usually stops and the referred contact is activated - but "
     "which of those happens is a campaign decision."),
    ("reply.on_wrong_person", CONTINUE, CONTACT,
     "We wrote to the wrong person",
     "Their colleagues may still be right. Only this sequence stops."),
    ("reply.on_left_company", STOP, CONTACT,
     "The contact has left",
     "Nothing more can usefully be sent to that address."),
    ("reply.activate_referred_contact", HOLD, CONTACT,
     "A referral names somebody we are not yet working",
     "Activating the referred contact automatically is usually right and is "
     "still a decision about who gets contacted, so it is off until somebody "
     "turns it on."),
    ("reply.on_existing_client", REVIEW, ACCOUNT,
     "They are already a client",
     "Somebody needs to know before anything else goes out."),
)

ACTIVATE_REFERRED = "reply.activate_referred_contact"

BY_KEY = {key: (default, scope, title, why)
          for key, default, scope, title, why in POLICIES}

# `src/replies.py` classifies into its own smaller vocabulary. Map it here
# rather than letting an unmapped word fall through to UNKNOWN: an
# out-of-office reviewed by a person is a person reading autoresponders.
CLASSIFIER_OUTCOME = {
    "positive": POSITIVE,
    "neutral": NEUTRAL,
    "negative": NEGATIVE,
    "unsubscribe": UNSUBSCRIBE,
    "account_do_not_contact": ACCOUNT_DNC,
    "out_of_office": NOT_NOW,
    "not_now": NOT_NOW,
    "referral": REFERRAL,
    "not_relevant": NOT_ICP,
    "unknown": UNKNOWN,
}

# Which policy each outcome consults.
OUTCOME_POLICY = {
    POSITIVE: "reply.on_positive",
    NEUTRAL: "reply.on_neutral",
    NEGATIVE: "reply.on_negative",
    NOT_NOW: "reply.on_negative",
    NOT_ICP: "reply.on_negative",
    UNSUBSCRIBE: "reply.on_unsubscribe",
    ACCOUNT_DNC: "reply.on_account_dnc",
    REFERRAL: "reply.on_referral",
    WRONG_PERSON: "reply.on_wrong_person",
    LEFT_COMPANY: "reply.on_left_company",
    EXISTING_CLIENT: "reply.on_existing_client",
}

# What this build actually does today, whatever the policy says.
#
# `events.apply` pauses the whole company on any reply. That is stated here
# rather than left for somebody to discover, because a policy screen showing
# "carry on" beside behaviour that pauses would be worse than no screen.
CURRENT_BEHAVIOUR = (
    "These policies are in force. `accountpolicy.apply_reply` is the only "
    "thing that moves reply state, and every entry point - the provider "
    "event, the hand-recorded reply, the classifier - comes through it. An "
    "unclassified reply still holds the whole company, because the "
    "uncertain case is the one that must not narrow.")


def _at(config, dotted):
    node = config or {}
    for part in dotted.split("."):
        if not isinstance(node, dict):
            return None
        node = node.get(part)
    return node


def policy(key, config=None):
    """The action in force for one policy, and whether anybody chose it."""
    default, scope, title, why = BY_KEY.get(key, (HOLD, ACCOUNT, key, ""))
    value = _at(config or {}, key)
    chosen = value is not None and str(value).strip().lower() in ACTIONS
    return {
        "key": key,
        "action": str(value).strip().lower() if chosen else default,
        "configured": chosen,
        "default": default,
        "scope": scope,
        "title": title,
        "why": why,
    }


def policies(config=None):
    return [policy(key, config) for key, _, _, _, _ in POLICIES]


def resolve(outcome, config=None):
    """What this reply outcome does, and to whom.

    An outcome nobody has a policy for resolves to REVIEW rather than to a
    guess: an unclassified reply is exactly the case where a person should
    look, and defaulting it to "carry on" would make the unknown case the
    permissive one.
    """
    key = OUTCOME_POLICY.get(outcome)
    if key is None:
        return {
            "outcome": outcome,
            "action": REVIEW,
            # Account scope, not contact. An unclassified reply is the case
            # where the least is known, and letting three colleagues carry
            # on while nobody has read the one message that arrived is the
            # permissive reading of the least information.
            "scope": ACCOUNT,
            "configured": False,
            "why": (f"no policy covers {outcome!r}, so a person decides. An "
                    f"unclassified reply is not a reason to carry on."),
            "key": None,
        }
    found = policy(key, config)
    return {
        "outcome": outcome,
        "action": found["action"],
        "scope": found["scope"],
        "configured": found["configured"],
        "key": key,
        "why": (f"{found['title']}: {ACTION_LABEL[found['action']].lower()}"
                + ("" if found["configured"]
                   else " (default; nobody has configured this)")),
    }


def affected(rec, contact_key, outcome, config=None):
    """Which contacts this reply would reach, and what would happen to them.

    Returns the decision plus a per-contact list, so the Reply Center can
    show "this pauses Sarah and Michael too" rather than leaving somebody to
    work it out from a policy key.
    """
    decision = resolve(outcome, config)
    graph = account.graph(rec)
    people = []
    for entry in graph["contacts"]:
        is_replier = entry["key"] == contact_key
        if decision["scope"] == CONTACT and not is_replier:
            action, why = CONTINUE, "this reply affects only the person who sent it"
        else:
            action = decision["action"]
            why = ("the person who replied" if is_replier
                   else "at the same account")
        people.append({
            "contact_key": entry["key"],
            "contact": entry["name"],
            "state": entry["state"],
            "replier": is_replier,
            "action": action,
            "why": why,
            "planned": len(entry["touches"]) - len(entry["confirmed_touches"]),
        })
    return {
        "decision": decision,
        "contacts": people,
        "held": [p for p in people if p["action"] in (HOLD, REVIEW)],
        "stopped": [p for p in people if p["action"] == STOP],
        "current_behaviour": CURRENT_BEHAVIOUR,
    }


def classify_outcome(rec, contact_key):
    """The recorded outcome for this contact's most recent reply.

    Read from events, never inferred from text - the classifier writes
    `classification` and this reports it. An unclassified reply is UNKNOWN,
    which resolves to REVIEW.
    """
    latest = None
    for entry in rec.get("events") or []:
        if entry.get("contact") != contact_key:
            continue
        if entry.get("type") == events.POSITIVE_REPLY_DETECTED:
            latest = POSITIVE
        elif entry.get("type") == events.REPLY_CLASSIFIED:
            # The recorded decision first. `replies.apply` writes the
            # policy outcome beside the classifier's own word, because the
            # two vocabularies are not the same one: `out_of_office` and
            # `not_relevant` are things a classifier says and not things a
            # policy has, so reading the classifier's word back against
            # `OUTCOMES` turned an autoresponder into UNKNOWN. It held
            # more rather than less, but it said "nobody classified this"
            # about a reply somebody had classified.
            recorded = str(entry.get("outcome") or "").strip().lower()
            if recorded in OUTCOMES:
                latest = recorded
                continue
            # An event written before that was recorded, or by a writer
            # that records a policy word directly. Two vocabularies reach
            # this field and both are legitimate, so both are read:
            # `CLASSIFIER_OUTCOME` first for the words only a classifier
            # says, then `OUTCOMES` for the words a policy has.
            #
            # Reading only one of them loses the other, and it has now been
            # wrong in both directions. Checking `OUTCOMES` alone turned
            # `out_of_office` into UNKNOWN. Checking `CLASSIFIER_OUTCOME`
            # alone turned `wrong_person`, `left_company` and
            # `existing_client` into UNKNOWN - policy outcomes with no
            # classifier word, recorded straight onto the event by
            # `revival` and by a person deciding in the UI. Nothing
            # overlaps between the two tables with a different meaning, so
            # the order settles nothing except which lookup answers first.
            value = str(entry.get("classification") or "").strip().lower()
            latest = CLASSIFIER_OUTCOME.get(
                value, value if value in OUTCOMES else UNKNOWN)
        elif entry.get("type") == events.REFERRAL_RECORDED:
            latest = REFERRAL
    return latest or UNKNOWN


# ------------------------------------------------------- what a reply does
#
# `resolve` answers *what the policy says*. This section answers *what
# happens to the record*, which is a different question with three subjects:
# the person who replied, everybody else at the account, and the account
# itself. One action word cannot carry all three, so the action and scope
# resolve into a triple.
#
# Four effects, and the difference between them is who can undo them:
#
#   CONTINUE   nothing changes
#   HOLD       stops advancing; an operator lifts it
#   STOP       this sequence ends; an operator can still reopen it
#   SUPPRESS   permanent, and honoured as a compliance decision
#
# SUPPRESS is deliberately not reachable from anything except an explicit
# request - an unsubscribe, or a company-wide do-not-contact. No amount of
# "not interested" adds up to one, because "not interested" is an answer
# about this quarter and a removal request is an answer about us.

SUPPRESS = "suppress"
EFFECTS = (CONTINUE, HOLD, STOP, SUPPRESS)

EFFECT_LABEL = {
    CONTINUE: "carries on",
    HOLD: "held until a person lifts it",
    STOP: "sequence ended",
    SUPPRESS: "suppressed permanently",
}

# (action, scope) -> (what happens to the replier, what happens to the
#                     account, does a person have to look)
#
# The replier is never CONTINUE. Somebody who answered is not somebody to
# keep cold-sequencing, whatever they said - so the mildest thing that can
# happen to them is that their own sequence ends. That is the one rule here
# that is not a policy choice: it follows from them having replied at all.
_TRANSITION = {
    (CONTINUE, CONTACT): (STOP, CONTINUE, False),
    (CONTINUE, ACCOUNT): (STOP, CONTINUE, False),
    (HOLD, CONTACT): (HOLD, CONTINUE, False),
    (HOLD, ACCOUNT): (HOLD, HOLD, False),
    (STOP, CONTACT): (STOP, CONTINUE, False),
    (STOP, ACCOUNT): (STOP, SUPPRESS, False),
    (REVIEW, CONTACT): (HOLD, CONTINUE, True),
    (REVIEW, ACCOUNT): (HOLD, HOLD, True),
}

# The only outcomes that suppress a person permanently. Everything else that
# stops a sequence merely stops it.
#
# "They left the company" and "please remove me" both end the sequence and
# they are not the same fact: one is a dead address, the other is a decision
# about us that we are obliged to keep. Collapsing them would let an
# operator reopening a stale contact quietly reopen a removal request.
REMOVAL_REQUESTS = (UNSUBSCRIBE, ACCOUNT_DNC)


def effects(outcome, config=None):
    """What this outcome does to the replier, the account, and whether a
    person has to look.

    Derived from the policy rather than tabulated per outcome, so a
    workspace that reconfigures `reply.on_positive` to CONTINUE gets a
    different transition without anything here changing.
    """
    decision = resolve(outcome, config)
    replier, account_, review = _TRANSITION[
        (decision["action"], decision["scope"])]
    if replier == STOP and outcome in REMOVAL_REQUESTS:
        replier = SUPPRESS
    return {
        "outcome": outcome,
        "decision": decision,
        "replier": replier,
        "others": account_,
        "account": account_,
        "review": review,
        "activate_referred": (outcome == REFERRAL
                              and policy(ACTIVATE_REFERRED,
                                         config)["action"] == CONTINUE),
    }


# ------------------------------------------------------- applying a reply

def _touch(rec, kind, contact_key=None, at=None, **fields):
    from . import events as event_model

    return event_model.record(rec, kind, contact_key=contact_key, at=at,
                              **fields)


def _hold_contact(rec, contact, outcome, at, why):
    if contact.get("paused"):
        return False
    contact["paused"] = {"since": at, "reason": outcome, "why": why}
    _touch(rec, events.CONTACT_HELD, contact_key=contact.get("key"), at=at,
           outcome=outcome)
    return True


def _stop_contact(rec, contact, outcome, at, why):
    if contact.get("stopped") or contact.get("unsubscribed"):
        return False
    contact["stopped"] = {"since": at, "reason": outcome, "why": why}
    _touch(rec, events.CONTACT_STOPPED, contact_key=contact.get("key"), at=at,
           outcome=outcome)
    return True


def _suppress_contact(rec, contact, outcome, at, why):
    """Permanent, and it outranks every other contact state.

    `unsubscribed` is the field the eligibility gate and the channel
    evaluator already read, so an unsubscribe honoured here is honoured
    everywhere without a second list to keep in step.
    """
    if contact.get("unsubscribed"):
        return False
    contact["unsubscribed"] = True
    contact["suppressed"] = {"since": at, "reason": outcome, "why": why}
    _touch(rec, events.CONTACT_SUPPRESSED, contact_key=contact.get("key"),
           at=at, outcome=outcome)
    return True


def _hold_account(rec, contact_key, outcome, at, channel=None, reason=None):
    """The reversible account-level stop. This is the old blanket pause.

    It is still exactly right for the cases that ask for it - a live
    conversation, an unclassified reply - and wrong only as a response to
    everything.
    """
    if rec.get("paused"):
        return False
    # `reason` is what arrived - `email_reply`, `linkedin_reply`. `outcome`
    # is what we made of it. Two facts, two fields: an audit that collapses
    # them cannot answer "we paused on a reply, but which reading of it".
    rec["paused"] = {"since": at, "reason": reason or outcome,
                     "outcome": outcome, "channel": channel,
                     "by": contact_key}
    _touch(rec, events.COMPANY_PAUSED, contact_key=contact_key, at=at,
           channel=channel)
    store.log(rec, "paused",
              f"{outcome}: both tracks paused for the whole company")
    return True


def _suppress_account(rec, contact_key, outcome, at):
    """A company-wide do-not-contact. Permanent, and it reaches everybody.

    Every contact is suppressed individually as well as the record being
    marked, because a per-contact gate that reads only the record would let
    a contact copied onto another record carry on.
    """
    suppression = dict(rec.get("suppression") or {})
    if suppression.get("unsubscribed"):
        return False
    suppression.update({"unsubscribed": True, "since": at,
                        "reason": outcome, "scope": ACCOUNT,
                        "by": contact_key})
    rec["suppression"] = suppression
    for contact in account.contacts_of(rec):
        _suppress_contact(rec, contact, outcome, at,
                          "the company asked not to be contacted")
    _touch(rec, events.ACCOUNT_SUPPRESSED, contact_key=contact_key, at=at,
           outcome=outcome)
    store.log(rec, "suppressed",
              f"{outcome}: the whole account is suppressed permanently")
    return True


def _require_review(rec, contact_key, outcome, at, why):
    if (rec.get("review") or {}).get("open"):
        return False
    rec["review"] = {"open": True, "since": at, "reason": outcome,
                     "by": contact_key, "why": why}
    _touch(rec, events.REVIEW_REQUIRED, contact_key=contact_key, at=at,
           outcome=outcome)
    return True


def _activate_referred(rec, contact_key, at):
    """Turn on the contact a referral pointed at, if the policy allows it.

    The edge itself is never touched: `account.referrals` reads
    REFERRAL_RECORDED and that event is the relationship. Activation only
    selects the target for outreach, which is a campaign decision and is off
    by default.
    """
    edge = account.referred_to(rec, contact_key)
    if edge is None:
        return None
    target_key = edge.get("to_contact")
    for contact in account.contacts_of(rec):
        if contact.get("key") != target_key:
            continue
        if contact.get("selected"):
            return None
        contact["selected"] = True
        _touch(rec, events.REFERRED_CONTACT_ACTIVATED, contact_key=target_key,
               at=at, referred_by=contact_key)
        store.log(rec, "referral",
                  f"{target_key} activated by a referral from {contact_key}",
                  contact=target_key)
        return target_key
    return None


def apply_reply(rec, contact_key, outcome=None, config=None, at=None,
                channel=None, reason=None, workspace=None):
    """Move the record's state to what this reply means. The only place that
    does.

    Every caller that learns something about a reply - the provider event
    path in `events.apply`, the hand-recorded path in `cadence.record_event`,
    the classifier in `replies.apply` - comes through here, so there is one
    answer to "what does a reply do" rather than one per entry point.

    **Conservative by construction.** An outcome nobody classified resolves
    to REVIEW at account scope, which is the old blanket pause plus a flag.
    So the uncertain case behaves exactly as this system always has, and only
    a *classified* reply is allowed to do anything narrower.

    **Idempotent.** Every transition checks the state it is about to write.
    A replayed webhook, a reclassification, or the same reply arriving on two
    records changes the state once - requirement of the event log, which
    already dedupes on `provider_event_id`, and of this layer, which must
    hold even for events that carry no provider id.

    Returns a report of what actually moved, so a caller can tell the
    difference between "held the account" and "the account was already held".
    """
    at = at or store.now()
    outcome = outcome or classify_outcome(rec, contact_key)
    plan = effects(outcome, config)
    moved = {"outcome": outcome, "effects": plan, "changed": [],
             "replier": None, "account": None, "review": False,
             "activated": None}

    contacts = {c.get("key"): c for c in account.contacts_of(rec)}
    replier = contacts.get(contact_key)

    # 1. The person who replied.
    if replier is not None:
        why = plan["decision"]["why"]
        if plan["replier"] == HOLD and _hold_contact(rec, replier, outcome,
                                                     at, why):
            moved["changed"].append("replier_held")
        elif plan["replier"] == STOP and _stop_contact(rec, replier, outcome,
                                                      at, why):
            moved["changed"].append("replier_stopped")
        elif plan["replier"] == SUPPRESS and _suppress_contact(
                rec, replier, outcome, at, why):
            moved["changed"].append("replier_suppressed")
        moved["replier"] = plan["replier"]
    elif outcome in REMOVAL_REQUESTS:
        # Somebody at this company asked to be removed and we cannot say
        # who, so it applies to all of them.
        #
        # `events.apply` returns `contact_key = None` whenever the address
        # on the reply matches no contact - an alias, a forward, a person
        # writing from their phone. Every branch below was guarded by
        # `replier is not None`, and `UNSUBSCRIBE` plans
        # `replier=SUPPRESS, account=CONTINUE`, so an unattributable
        # removal request wrote *nothing*: no suppression, no contact
        # state, nothing in `hygiene`, nothing in the agency index. The
        # generic hold every reply produces was the only trace, and an
        # operator clears that once they have read it.
        #
        # Widening rather than dropping is the rule this module already
        # states: uncertainty never narrows. We cannot aim a removal
        # request at one person we are unable to name, and the only
        # honest alternative to aiming it at the account is losing it.
        if _suppress_account(rec, contact_key, outcome, at):
            moved["changed"].append("account_suppressed_unattributed")
        moved["replier"] = SUPPRESS

    # 2. The account. SUPPRESS before HOLD: a company-wide removal is not a
    #    pause somebody can lift, and writing the pause first would leave a
    #    record that reads as recoverable.
    if plan["account"] == SUPPRESS:
        if _suppress_account(rec, contact_key, outcome, at):
            moved["changed"].append("account_suppressed")
    elif plan["account"] == HOLD:
        if _hold_account(rec, contact_key, outcome, at, channel, reason):
            moved["changed"].append("account_held")
    moved["account"] = plan["account"]

    # 3. Whether a person has to look before anything else goes out.
    if plan["review"] and _require_review(rec, contact_key, outcome, at,
                                          plan["decision"]["why"]):
        moved["changed"].append("review_required")
    moved["review"] = plan["review"]

    # 4. A referral may activate the person it pointed at.
    if plan["activate_referred"]:
        activated = _activate_referred(rec, contact_key, at)
        if activated:
            moved["activated"] = activated
            moved["changed"].append("referred_activated")

    # 5. Last, and last on purpose. What the providers should be told is
    #    written *after* every canonical transition above, and writing it
    #    cannot fail in a way that unwinds one - the outbox is a file and a
    #    provider is not called. Same ordering, and the same reason, as the
    #    Slack notification in `replies.apply`.
    moved["tags"] = _queue_tags(rec, contact_key, workspace, config, outcome)
    return moved


def _queue_tags(rec, contact_key, workspace, config, outcome):
    """Record the desired provider tag state. Never raises into the caller.

    A tag is a copy of a conclusion. Losing one delays a label in somebody
    else's UI; losing the transition above loses a suppression. So this is
    allowed to fail and the caller is not allowed to notice.
    """
    if not workspace:
        return None
    try:
        from . import tagsync

        return [r["provider"] for r in
                tagsync.enqueue(rec, contact_key, workspace, config,
                                outcome=outcome)]
    except Exception:                                       # noqa: BLE001
        return None


# --------------------------------------------------- reading the state back

def account_state(rec):
    """Whether anything may go out to this account at all, and why not."""
    if (rec.get("suppression") or {}).get("unsubscribed"):
        return SUPPRESS, rec["suppression"]
    if rec.get("paused"):
        return HOLD, rec["paused"]
    if (rec.get("review") or {}).get("open"):
        return HOLD, rec["review"]
    return CONTINUE, None


def contact_state(contact):
    """Whether anything may go out to this person, and why not."""
    contact = contact or {}
    if contact.get("unsubscribed") or contact.get("suppressed"):
        return SUPPRESS, contact.get("suppressed") or {"reason": "unsubscribed"}
    if contact.get("stopped"):
        return STOP, contact["stopped"]
    if contact.get("paused"):
        return HOLD, contact["paused"]
    return CONTINUE, None
