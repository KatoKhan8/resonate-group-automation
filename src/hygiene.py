#!/usr/bin/env python3
"""Whether a lead we are about to work is one we have already worked.

## The failure this exists to prevent

A CSV arrives. Somewhere in it is a person who replied to us in March, a
company that asked to be removed in June, and a colleague of somebody we are
mid-conversation with. Every one of them looks like a fresh cold prospect,
because a CSV row carries no history. Writing to them is not a data-quality
problem; it is the thing a client notices and remembers.

So a list is checked against what we already know **before** anything is
enriched, drafted or made campaign-eligible.

## It is one taxonomy, not a new one

There is no engagement state machine here. The canonical facts already exist
and this reads them:

    accountpolicy.contact_state   what a reply did to this person
    accountpolicy.account_state   what it did to their company
    accountpolicy.classify_outcome what the reply was classified as
    account.touches / replies      what actually happened
    dedupe.keys_for                who this is, if we can prove it

What is new is the *verdict*: what to do about a candidate row given those
facts. That is `VERDICTS` below, and it is a decision, not a state.

## Previously engaged is not permanently excluded

The distinction the whole module turns on. "Remove us" suppresses. "Not
right now" is a follow-up. "My colleague is talking to you" is a hold that
somebody lifts. Collapsing them into `exclude` throws away the most valuable
rows in the list, and collapsing them into `eligible` is how a client finds
out we do not read our own history.

## Nothing is deleted, and every verdict says why

A row that is not cold-eligible keeps its place in the preview with the
evidence that put it there - the contact, the event, the date, the policy.
An operator who cannot see why a row was held cannot tell a wrong hold from
a right one.

## Identity is proved, never guessed

Matching uses `dedupe.keys_for`: normalised email, canonical LinkedIn URL,
provider lead id, or our own record+contact key. A name and a company are
never identity, here or anywhere. A row with no strong identifier is matched
at the *account* level only, on its domain, and says so.
"""
import collections

from . import account, accountpolicy as ap, dedupe, events, linkedin, store

# ------------------------------------------------------------- the verdicts
#
# What to do with a candidate row. Ordered most-final first: `worst` below
# relies on this order, and a row that matches several histories gets the
# most conservative of them.
#
# The three columns are the whole design: what happens to the row, whether a
# person has to look, and whether the company is still workable.

SUPPRESSED_ACCOUNT = "suppressed_account"
SUPPRESSED_CONTACT = "suppressed_contact"
AGENCY_SUPPRESSED = "agency_suppressed"
INVALID_CONTACT = "invalid_contact"
MEETING_BOOKED = "meeting_booked"
ACTIVE_CONVERSATION = "active_conversation"
PREVIOUSLY_ENGAGED = "previously_engaged"
FUTURE_FOLLOW_UP = "future_follow_up"
REFERRAL = "referral"
WRONG_PERSON = "wrong_person"
PREVIOUSLY_CONTACTED = "previously_contacted"
FRESH = "fresh"

VERDICTS = (SUPPRESSED_ACCOUNT, SUPPRESSED_CONTACT, AGENCY_SUPPRESSED,
            INVALID_CONTACT, MEETING_BOOKED, ACTIVE_CONVERSATION,
            PREVIOUSLY_ENGAGED, FUTURE_FOLLOW_UP, REFERRAL, WRONG_PERSON,
            PREVIOUSLY_CONTACTED, FRESH)

# What an operator does with each. Deliberately a small set, and deliberately
# not the same words as the reply policy's - a reply *causes* a state and a
# hygiene verdict *routes* a row, and one word for both would hide which was
# being talked about.
SUPPRESS = "suppress"
EXCLUDE = "exclude"
HOLD = "hold"
ROUTE = "route"
REVIEW = "review"
ELIGIBLE = "eligible"
ACTIONS = (SUPPRESS, EXCLUDE, HOLD, ROUTE, REVIEW, ELIGIBLE)

ACTION_OF = {
    SUPPRESSED_ACCOUNT: SUPPRESS,
    SUPPRESSED_CONTACT: SUPPRESS,
    AGENCY_SUPPRESSED: SUPPRESS,
    INVALID_CONTACT: EXCLUDE,
    MEETING_BOOKED: EXCLUDE,
    ACTIVE_CONVERSATION: HOLD,
    PREVIOUSLY_ENGAGED: HOLD,
    FUTURE_FOLLOW_UP: ROUTE,
    REFERRAL: ROUTE,
    WRONG_PERSON: SUPPRESS,
    PREVIOUSLY_CONTACTED: REVIEW,
    FRESH: ELIGIBLE,
}

LABEL = {
    SUPPRESSED_ACCOUNT: "Company asked not to be contacted",
    SUPPRESSED_CONTACT: "Asked not to be contacted",
    AGENCY_SUPPRESSED: "Suppressed by agency safety policy",
    INVALID_CONTACT: "Has left the company",
    MEETING_BOOKED: "Meeting booked",
    ACTIVE_CONVERSATION: "Conversation in progress",
    PREVIOUSLY_ENGAGED: "Replied to us before",
    FUTURE_FOLLOW_UP: "Asked us to come back later",
    REFERRAL: "Came to us through a referral",
    WRONG_PERSON: "Not the right person here",
    PREVIOUSLY_CONTACTED: "Contacted before, never replied",
    FRESH: "No prior history",
}

# How each action reads on a screen. Here rather than in the template for
# the same reason the labels are.
KIND = {
    SUPPRESS: "block", EXCLUDE: "block", HOLD: "warn",
    ROUTE: "info", REVIEW: "warn", ELIGIBLE: "pass",
}

ACTION_LABEL = {
    SUPPRESS: "Suppressed",
    EXCLUDE: "Not for cold outreach",
    HOLD: "Held",
    ROUTE: "Route to a different sequence",
    REVIEW: "Needs a look",
    ELIGIBLE: "Cold-eligible",
}

# Which reply outcomes produce which verdict, when the outcome is the
# strongest thing known about a contact. Anything absent falls to the
# touch-history rules below.
_OUTCOME_VERDICT = {
    ap.ACCOUNT_DNC: SUPPRESSED_ACCOUNT,
    ap.UNSUBSCRIBE: SUPPRESSED_CONTACT,
    ap.LEFT_COMPANY: INVALID_CONTACT,
    ap.WRONG_PERSON: WRONG_PERSON,
    ap.POSITIVE: ACTIVE_CONVERSATION,
    ap.EXISTING_CLIENT: ACTIVE_CONVERSATION,
    ap.NOT_NOW: FUTURE_FOLLOW_UP,
    ap.REFERRAL: REFERRAL,
    ap.NEGATIVE: PREVIOUSLY_ENGAGED,
    ap.NOT_ICP: PREVIOUSLY_ENGAGED,
    ap.NEUTRAL: PREVIOUSLY_ENGAGED,
}


def worst(verdicts):
    """The most conservative verdict in a set. `VERDICTS` is the order."""
    order = {name: i for i, name in enumerate(VERDICTS)}
    found = [v for v in verdicts if v in order]
    return min(found, key=lambda v: order[v]) if found else FRESH


# --------------------------------------------------------- what we know
#
# One pass over history, indexed by every strong identity a contact carries
# and by the account's domain. Built once per check run: a per-row scan of
# the whole queue is what makes a 5,000-row import unusable.

def _sendable(contact):
    """Deferred so `hygiene` stays importable from the import path, which
    has no business pulling in the verification providers to read a CSV."""
    from . import lint

    return bool(contact.get("email")) and lint.sendable(contact)


def _facts(rec, contact, workspace):
    """What is authoritatively known about one contact we have worked."""
    key = contact.get("key")
    confirmed = [t for t in account.touches(rec, key) if t["confirmed"]]
    replies = account.replies(rec, key)
    outcome = ap.classify_outcome(rec, key) if replies else None
    meeting = any(e.get("type") == events.MEETING_MARKED
                  and e.get("contact") == key
                  for e in rec.get("events") or [])
    contact_action, contact_why = ap.contact_state(contact)
    return {
        "workspace": workspace,
        "record_id": rec.get("id"),
        "company": rec.get("company"),
        "domain": rec.get("domain"),
        "contact_key": key,
        "name": contact.get("name"),
        "campaigns": list(rec.get("campaign_ids") or []),
        "confirmed_touches": len(confirmed),
        "replies": len(replies),
        "outcome": outcome,
        "meeting": meeting,
        "contact_state": contact_action,
        "contact_why": contact_why,
        "last_touch_at": confirmed[-1]["at"] if confirmed else None,
        "last_reply_at": replies[-1]["at"] if replies else None,
        # Whether this address has already been cleared to write to.
        # Recomputed from the stored evidence rather than read from a
        # stored flag, which is the same thing `lint.sendable` does and
        # for the same reason: a state written once can outlive the
        # evidence under it.
        "sendable": _sendable(contact),
    }


def index(recs=None, workspace=None):
    """Every contact we have worked, keyed by every strong identity they have.

    `workspace` scopes the history. Passing None indexes whatever records are
    handed in, which is how the caller keeps tenancy: `Repo.records()` has
    already narrowed to one workspace, and this never widens it.
    """
    recs = store.load() if recs is None else recs
    by_identity, by_domain = {}, collections.defaultdict(list)
    for rec in recs:
        space = workspace or rec.get("client")
        domain = dedupe.normalise_domain(rec.get("domain"))
        account_action, account_why = ap.account_state(rec)
        entry = {"workspace": space, "record_id": rec.get("id"),
                 "company": rec.get("company"), "domain": domain,
                 "account_state": account_action, "account_why": account_why,
                 "contacts": []}
        for contact in account.contacts_of(rec):
            facts = _facts(rec, contact, space)
            entry["contacts"].append(facts)
            for _kind, key in dedupe.keys_for(rec, contact):
                by_identity.setdefault(key, []).append(facts)
        if domain:
            by_domain[domain].append(entry)
    return {"by_identity": by_identity, "by_domain": dict(by_domain),
            "records": len(recs)}


# ------------------------------------------------------------- the check

def _candidate_keys(candidate):
    """Strong identifiers on an imported row. Never a name, never a company."""
    keys = []
    email = dedupe.normalise_email(candidate.get("email"))
    if email:
        keys.append(f"email:{email}")
    profile = linkedin.canonical(candidate.get("linkedin"))
    if profile:
        keys.append(f"linkedin:{profile}")
    for pid in dedupe.provider_ids(candidate):
        keys.append(f"provider:{pid}")
    return keys


def _from_contact(facts):
    """The verdict one matched contact's history implies, and why."""
    if facts["contact_state"] == ap.SUPPRESS:
        reason = (facts["contact_why"] or {}).get("reason")
        verdict = (SUPPRESSED_ACCOUNT if reason == ap.ACCOUNT_DNC
                   else SUPPRESSED_CONTACT)
        return verdict, f"{facts['name'] or facts['contact_key']} is suppressed"
    if facts["meeting"]:
        return MEETING_BOOKED, f"a meeting is recorded with {facts['name']}"
    if facts["outcome"] in _OUTCOME_VERDICT:
        return (_OUTCOME_VERDICT[facts["outcome"]],
                f"{facts['name'] or facts['contact_key']} replied "
                f"({ap.OUTCOME_LABEL.get(facts['outcome'], facts['outcome'])})"
                + (f" on {facts['last_reply_at'][:10]}"
                   if facts["last_reply_at"] else ""))
    if facts["replies"]:
        return PREVIOUSLY_ENGAGED, f"{facts['name']} replied to us before"
    if facts["confirmed_touches"]:
        return (PREVIOUSLY_CONTACTED,
                f"contacted {facts['confirmed_touches']} time(s)"
                + (f", last on {facts['last_touch_at'][:10]}"
                   if facts["last_touch_at"] else "")
                + ", never replied")
    return FRESH, "no confirmed touch and no reply"


def _from_account(entry, config, exclude=()):
    """What the *company's* history implies for a row we have never seen.

    This is the case the whole module was asked for. Sarah has never appeared
    before; Acme asked to be removed in June. Sarah is not fresh.

    `exclude` is the contact keys already matched on identity. Their own
    history is a better answer about them than the account's is, and letting
    the account restate it would drown a precise verdict in a vague one:
    John's "come back in Q4" would read as "somebody here replied once".

    The account's *own* state - a suppression, a hold - still applies to
    everybody including them, because that is a fact about the company.
    """
    if entry["account_state"] == ap.SUPPRESS:
        return (SUPPRESSED_ACCOUNT,
                f"{entry['company']} asked not to be contacted")
    others = [c for c in entry["contacts"]
              if c["contact_key"] not in set(exclude)]
    engaged = [c for c in others if c["replies"]]
    positive = [c for c in engaged if c["outcome"] == ap.POSITIVE]
    if any(c["meeting"] for c in others):
        who = next(c for c in others if c["meeting"])
        return (MEETING_BOOKED,
                f"a meeting is recorded with {who['name']} at "
                f"{entry['company']}")
    if positive:
        who = positive[0]
        # The account policy already decided what a positive reply does to
        # the other decision makers. Asking it here means a workspace that
        # reconfigured that policy gets a consistent answer at import too.
        plan = ap.effects(ap.POSITIVE, config)
        verdict = (ACTIVE_CONVERSATION if plan["account"] != ap.CONTINUE
                   else PREVIOUSLY_CONTACTED)
        return (verdict,
                f"{who['name']} replied positively"
                + (f" on {who['last_reply_at'][:10]}"
                   if who["last_reply_at"] else "")
                + f" at {entry['company']}")
    if entry["account_state"] == ap.HOLD:
        return (ACTIVE_CONVERSATION,
                f"{entry['company']} is held: "
                + str((entry["account_why"] or {}).get("reason") or "a reply"))
    if engaged:
        who = engaged[0]
        return (PREVIOUSLY_ENGAGED,
                f"{who['name']} at {entry['company']} replied to us before")
    if any(c["confirmed_touches"] for c in others):
        return (PREVIOUSLY_CONTACTED,
                f"{entry['company']} has been contacted before")
    return FRESH, "no history at this company"


def check(candidate, history, config=None, agency=None):
    """One row's hygiene verdict, with the evidence behind it.

    `candidate` is a dict with any of `email`, `linkedin`, `domain`,
    `company`, `name`. Only the first two are identity; `domain` matches the
    account and says so.

    Returns the verdict, the action an operator takes, a sentence a person
    can read, and the machine-readable evidence behind it. Never mutates.
    """
    reasons, verdicts, matched = [], [], []

    # 1. The agency-wide index, first and most final. It answers only
    #    "is this person suppressed", never by whom or why - see
    #    `src/agencydnc.py` for the privacy model.
    if agency is not None:
        for key in _candidate_keys(candidate):
            hit = agency.get(key)
            if hit:
                verdicts.append(AGENCY_SUPPRESSED)
                reasons.append(hit)

    # 2. This workspace's own contact history, by strong identity only.
    for key in _candidate_keys(candidate):
        for facts in history["by_identity"].get(key, ()):
            verdict, why = _from_contact(facts)
            verdicts.append(verdict)
            reasons.append(why)
            matched.append({"how": key.split(":", 1)[0], **facts})

    # 3. The account, whether or not the person is known.
    domain = dedupe.normalise_domain(candidate.get("domain"))
    seen_keys = {m["contact_key"] for m in matched}
    if domain:
        for entry in history["by_domain"].get(domain, ()):
            verdict, why = _from_account(entry, config, exclude=seen_keys)
            if verdict != FRESH:
                verdicts.append(verdict)
                reasons.append(why)

    verdict = worst(verdicts) if verdicts else FRESH
    return {
        "verdict": verdict,
        "action": ACTION_OF[verdict],
        "label": LABEL[verdict],
        # Rendered by the template, decided here. `pages.py` may not import
        # an engine module, and a second copy of these tables in the
        # template is how a screen and its engine drift apart.
        "action_label": ACTION_LABEL[ACTION_OF[verdict]],
        "kind": KIND[ACTION_OF[verdict]],
        "why": reasons[0] if reasons else "no prior history",
        "reasons": reasons,
        "matched": matched,
        "identified": bool(_candidate_keys(candidate)),
        "matched_on": ("contact" if matched
                       else "account" if verdicts else None),
    }


def summarise(results):
    """Counts by verdict and by action, for an import preview."""
    by_verdict = collections.Counter(r["verdict"] for r in results)
    by_action = collections.Counter(r["action"] for r in results)
    return {
        "total": len(results),
        "by_verdict": {v: by_verdict.get(v, 0) for v in VERDICTS
                       if by_verdict.get(v)},
        "by_action": {a: by_action.get(a, 0) for a in ACTIONS
                      if by_action.get(a)},
        # The same counts, already labelled, in the order `VERDICTS` defines
        # - most final first, so a preview reads worst-to-best.
        "rows": [{"verdict": v, "label": LABEL[v], "count": by_verdict[v],
                  "action": ACTION_OF[v],
                  "action_label": ACTION_LABEL[ACTION_OF[v]],
                  "kind": KIND[ACTION_OF[v]]}
                 for v in VERDICTS if by_verdict.get(v)],
        "eligible": by_action.get(ELIGIBLE, 0),
        "not_eligible": len(results) - by_action.get(ELIGIBLE, 0),
    }
