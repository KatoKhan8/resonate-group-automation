#!/usr/bin/env python3
"""What a bounce MEANS. One hard bounce closes an address; three soft ones do.

The operator approved this rule in full on 2026-10-15 23:30 and it is written
out in `resonate-ops/DECISION-bounce-rule-2026-10-15.md`:

  1. a HARD bounce suppresses immediately
  2. a SOFT bounce is counted, and the THIRD consecutive one with no delivery
     between is treated as a derived hard bounce
  3. an out-of-office is not a bounce and must never reach this rule
  4. where the provider does not say which it was, suppress on the first
     bounce only if the address has NEVER accepted mail from us

## Rule 3 is a precondition, and it was measured before this file existed

An out-of-office reaching this module would make it remove the most engaged
people on the list while looking like it was working. Measured 2026-10-15 on
`1c77a06c1`, three ways, and all three are asserted by
`tests/test_the_bounce_rule_the_operator_approved.py` so a later wiring cannot
undo them quietly:

  * BY IMPORT GRAPH. The transitive import closure of every module that
    produces or consumes a bounce - `leadobserve`, `adapters`, `channels`,
    `eligibility`, `providers.bison` - is 111 modules and contains neither
    `ooo`, nor `oooreturn`, nor `replies`. The two classifiers cannot reach
    each other.
  * BY CLASSIFIER INPUT. Both bounce producers decide on PROVIDER STRUCTURE
    and never on a body: `leadobserve._email_state` reads the queue row's
    `status` against an allowlist, and `bison.classify_reply_row` reads
    `event`, `type` and `folder` against three more. Neither reads text.
  * BY CONTROL FLOW. `inbound.handle` returns at "delivered, bounced,
    connected" before any text classifier runs, so an event that is not a
    reply never reaches the words at all.

And structurally, for the one caller this repository actually wires: an
out-of-office is an INBOUND REPLY and the recorder reads the OUTBOUND
scheduled-email queue. An out-of-office is not a row on that surface.

What is NOT proven here is EmailBison's own filing. If the provider ever put
an autoresponder in its `bounced` folder we would follow it, because its
status is the authority we read. That needs a provider probe to settle and
this lane may not make one; it is named in the task report rather than
guessed at.

## Rule 4 is the classifier, because the provider does not carry one

MEASURED 2026-10-15, no probe: no EmailBison surface this repository reads
carries a bounce code, class, SMTP status or diagnostic field.

    queue rows      `status`, one word, from
                    (scheduled, sent, bounced, stopped)
    /replies rows   `type` and `folder`; BOUNCE_TYPES is ("bounced","bounce")
    /events         `EMAIL_BOUNCED`, 15 of 1,200 real events walked
                    2026-09-17, with no class beside it

`hard_bounced` and `soft_bounced` are honoured below, and they are OUR words
rather than observed ones - they sit in `suppression.PROVIDER_STOPPED` and in
`scripts/reengagement_provider_confirmed.py:109`, and the 2026-10-15 status
snapshot contains neither. They cost nothing to honour and they stop a future
vocabulary change from arriving as a silent "nothing happened".

So in practice the class is DERIVED, from data we hold and no provider has to
cooperate with: has this address ever accepted mail from us?

## What "accepted" means, and the number that matters

`EMAIL_DELIVERED` or `REPLY_RECEIVED`, for this address. Not `PUSH_MARKED`:
EmailBison's `sent` says it handed the message to SMTP and says nothing about
a mailbox accepting it, which `leadobserve` already states twice.

MEASURED 2026-10-15 on the production store, 1,584 records: **0**
`email_delivered` events exist - nothing produces them, and
`adapters.emailbison_delivered` has no caller on the confirmed surface - and
29 `reply_received` across 23 contacts. Of 1,313 contacts holding an address,
**23 (1.75%) have ever accepted mail from us**. So today rule 4 classifies
98.25% of this estate HARD on a first bounce, and rule 2 protects the other
1.75%.

THAT IS THE HONEST SIZE OF THE RULE AND IT IS NOT A DEFECT IN IT. The rule
gets stronger exactly as the delivery evidence does; the asymmetry the
decision rests on - a wrong suppression costs one lead, an unsuppressed hard
bounce costs the reputation of 181 shared mailboxes - is what makes it the
right default while the evidence is thin.

## Where the counter lives, and why it survives a restore

In the record's own append-only event log, in `work/queue.jsonl`, as
`EMAIL_BOUNCED_SOFT` entries - DERIVED on read by `consecutive_soft`, never
stored as a number. Three reasons, in order:

  * The decision requires it outside `agencydnc`, and this is outside it.
    `agencydnc.REASONS` is a closed four with no free-text field, so the list
    could not hold a count even if it should.
  * A stored counter would be a second representation of a fact the event log
    already holds, free to drift from it. Derivation cannot drift.
  * `suppression/0050` proved by drill what a restore keeps: the fixture
    estate's BLOCK rows survived `scripts/server/backup.py` by NAME, read
    back through `src/suppression.py`, and the mutation that dropped one row
    from the restored copy went red naming it. Those rows were rows of
    `work/queue.jsonl` and `work/agency-dnc.jsonl`. An event on a queue
    record is inside the half of suppression that drill covers; a new file
    beside it would be in the half nothing has ever restored.

## What it does NOT do

It does not write to the agency DNC. `src/agencydnc.py` says a row there is
"written deliberately by a super admin, never derived", and this is a
mechanism. It closes an ADDRESS on the EMAIL channel, by the canonical event
the send path already reads, and says nothing about the same person on
LinkedIn.
"""
from . import events

HARD = "hard"
SOFT = "soft"

#: The provider stating the class itself. NEVER OBSERVED on this estate - see
#: the module docstring - and honoured anyway, because the alternative is that
#: the day EmailBison starts saying `hard_bounced` we read it as "the provider
#: did not say" and apply the weaker rule to the stronger evidence.
PROVIDER_HARD_WORDS = frozenset({"hard_bounced", "hard_bounce", "hard"})
PROVIDER_SOFT_WORDS = frozenset({"soft_bounced", "soft_bounce", "soft",
                                 "deferred"})

#: Proof that a mailbox accepted mail from us. See the docstring: `sent` is
#: not here, deliberately, and `PUSH_MARKED` is what `sent` becomes.
ACCEPTANCE_EVENTS = (events.EMAIL_DELIVERED, events.REPLY_RECEIVED)

#: PROVISIONAL IN THE SAME SENSE `suppression.DEFAULTS` IS. The operator
#: confirmed three; it is still config, because a figure that is a constant
#: here and config there is how the two come to disagree, and because the
#: right number is a deliverability question nobody has measured yet.
DEFAULTS = {
    # How many consecutive soft bounces, with no acceptance between, before
    # the address is closed. The third IS the suppression, so 3 means two are
    # survivable.
    "soft_bounces_before_suppression": 3,
}


def thresholds(config=None):
    """The live thresholds. Resolved per call, never cached at import."""
    out = dict(DEFAULTS)
    section = ((config or {}).get("bounces") or {})
    for key in DEFAULTS:
        if key in section and section[key] is not None:
            out[key] = section[key]
    return out


def provider_class(raw_status):
    """`hard`, `soft`, or None when the provider did not say.

    None is the answer on every row this estate has ever produced, and it is
    an answer rather than a failure: it is what sends `classify` to rule 4.
    """
    word = str(raw_status or "").strip().lower()
    if word in PROVIDER_HARD_WORDS:
        return HARD
    if word in PROVIDER_SOFT_WORDS:
        return SOFT
    return None


def _about(entry, contact_key, address):
    """Is this event about THIS address?

    The same rule `channels._bounced` applies, and deliberately the same:
    keyed to the contact, falling back to the address only when the event
    names no contact. One colleague's dead mailbox says nothing about
    anybody else's. `tests/test_the_bounce_rule_the_operator_approved.py`
    asserts that the two agree rather than trusting this comment.
    """
    named = entry.get("contact")
    if named:
        return named == contact_key
    address = (address or "").strip().lower()
    return bool(address) and str(
        entry.get("email") or "").strip().lower() == address


def accepted(rec, contact_key, address):
    """The last event proving this address accepted mail from us, or None."""
    found = None
    for entry in rec.get("events") or []:
        if entry.get("type") not in ACCEPTANCE_EVENTS:
            continue
        if _about(entry, contact_key, address):
            found = entry
    return found


def consecutive_soft(rec, contact_key, address):
    """Soft bounces recorded since this address last accepted mail from us.

    Counted in the log's APPEND ORDER rather than by the provider's
    timestamps, and that is a decision. The log is append-only and its order
    is the order this system learned the facts; sorting by `at` would let a
    reply ingested late, bearing an older provider timestamp, retroactively
    reset a counter that had already fired - which is the unsafe direction.

    It counts EVENTS, not polls. A bounced queue row stays `bounced` for ever
    and twenty watchers re-read their queues every 180 seconds, so a counter
    reading polls would reach three in nine minutes on one soft bounce. What
    stops that is `events.record`, which refuses a repeat on BOTH
    `provider_event_id` and the derived `id` - measured 2026-10-15 to be
    redundant on this path, either one alone being enough - and not anything
    here. `tests/test_the_bounce_rule_the_operator_approved.py` asserts it
    against three polls of one row.
    """
    count = 0
    for entry in rec.get("events") or []:
        if not _about(entry, contact_key, address):
            continue
        if entry.get("type") in ACCEPTANCE_EVENTS:
            count = 0
        elif entry.get("type") == events.EMAIL_BOUNCED_SOFT:
            count += 1
    return count


def classify(rec, contact_key, address, raw_status=None):
    """`(HARD | SOFT, why)` for one bounce. Rules 1, 2 and 4's input.

    Rule 4: the provider's own word wins where it exists, and where it does
    not - which is every row measured to date - an address that has never
    accepted mail from us is treated as HARD.
    """
    stated = provider_class(raw_status)
    if stated is not None:
        word = str(raw_status).strip().lower()
        return stated, f"the provider called it {word!r}"
    proof = accepted(rec, contact_key, address)
    if proof is None:
        return HARD, ("the provider did not say which kind of bounce this is "
                      "and this address has never accepted mail from us, so "
                      "there is no evidence it has ever worked")
    return SOFT, ("the provider did not say which kind of bounce this is and "
                  "this address accepted mail from us at "
                  f"{proof.get('at') or 'an unrecorded time'}, so one failure "
                  "is not evidence that it is dead")


def decide(rec, contact_key, address, raw_status=None, config=None):
    """What to record for one bounce, and whether it closes the address.

    Returns a dict and never writes: the caller owns the store transaction.

        class        `hard` or `soft`
        event        the canonical event to record - `EMAIL_BOUNCED` for a
                     hard one AND for the third soft one, which the decision
                     calls a derived hard bounce
        suppresses   whether recording that event closes this address. True
                     exactly when `event` is `EMAIL_BOUNCED`, because that
                     event IS the closure - `channels._bounced` reads it and
                     `eligibility.decide` consults it before MX and before
                     verification
        soft_count   this bounce included
        why          a sentence a person can read in a watcher log
    """
    limit = thresholds(config)["soft_bounces_before_suppression"]
    kind, why = classify(rec, contact_key, address, raw_status)
    if kind == HARD:
        return {"class": HARD, "event": events.EMAIL_BOUNCED,
                "suppresses": True, "soft_count": 0, "limit": limit,
                "why": f"hard: {why}"}
    count = consecutive_soft(rec, contact_key, address) + 1
    if count >= limit:
        return {"class": SOFT, "event": events.EMAIL_BOUNCED,
                "suppresses": True, "soft_count": count, "limit": limit,
                "why": (f"soft, and the {count}th consecutive with no "
                        "delivery between, which the rule treats as a "
                        f"derived hard bounce: {why}")}
    return {"class": SOFT, "event": events.EMAIL_BOUNCED_SOFT,
            "suppresses": False, "soft_count": count, "limit": limit,
            "why": (f"soft, {count} of {limit} consecutive; counted and the "
                    f"address stays open: {why}")}
