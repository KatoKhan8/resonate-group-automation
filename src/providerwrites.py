#!/usr/bin/env python3
"""The only place a provider may be mutated, and today it may not be.

WHY THIS SHIPS WITH EVERY ALLOWLIST EMPTY.

`push.run(live=True)` raises, `tagsync.send` refuses unconditionally, and
`heyreach._read` rejects any route outside its read allowlist. Sending is
BLOCKING by construction rather than by a flag, which is the property
LIVE-READINESS.md promises and the one thing in this repository that has never
been wrong. Adding a write capability is therefore not a feature; it is the
removal of the only guarantee that has held.

So the machine is built first and given nothing to drive. `OPERATIONS` declares
what a write would need. `SUPPORTED` is empty. Every attempt refuses, and the
tests assert that it refuses. On the day one route is enabled, the brakes -
authorization, idempotency, mandatory read-back, failure classification - are
already there, already tested, and already the only path through.

WHAT IS AND IS NOT AN ESTABLISHED CONTRACT.

An endpoint counts as established only when the provider documented it, or the
existing code already carries its confirmed shape, or a real response has been
read. Guessing a write path against a live client estate is how somebody
discovers a route by mutating production, so anything unestablished is declared
`UNSUPPORTED` with the reason, rather than attempted hopefully.

  HeyReach   /campaign/AddLeadsToCampaignV2   URL known, shape NOT validated
             create campaign                  no documented route
             create list                      no documented route
             configure sequence               no documented route
             assign sender                    no documented route
             configure limits                 no documented route
             pause / activate                 no documented route
  EmailBison /campaigns/{id}/leads            URL known, shape NOT validated
             create campaign                  no documented route
             configure sequence               no documented route
             pause / activate                 no documented route

Every one of those was probed read-only or is named in the provider modules;
none has had a successful write response read back. So `SUPPORTED` stays empty
until each is separately established, reviewed and tested - one route per
change, never a batch.

THE ONE RULE THAT MATTERS MOST.

After a write, READ BACK BEFORE DECIDING ANYTHING. Never retry because the
client did not receive a response: a timeout says nothing about whether the
provider acted, and `actionledger` refuses a retry until provider truth settles
the reservation. That rule is enforced here rather than documented here.
"""
import json
import sys

from . import actionledger, events, executionguard, store

# ------------------------------------------------------------- operations

# What each operation is, and whether it can reach a prospect. The flag is not
# decoration: `PROSPECT_FACING` operations additionally require a full
# `Authorization`, and non-prospect-facing staging does not - which is the
# distinction that lets configuration be built and verified without any risk of
# contacting somebody.
LINKEDIN_ADD_LEAD = "heyreach.add_lead"
LINKEDIN_CREATE_LIST = "heyreach.create_list"
LINKEDIN_CREATE_CAMPAIGN = "heyreach.create_campaign"
LINKEDIN_SET_SEQUENCE = "heyreach.set_sequence"
LINKEDIN_ASSIGN_SENDER = "heyreach.assign_sender"
LINKEDIN_SET_LIMITS = "heyreach.set_limits"
LINKEDIN_PAUSE = "heyreach.pause"
LINKEDIN_ACTIVATE = "heyreach.activate"

EMAIL_ADD_LEAD = "bison.add_lead"
EMAIL_CREATE_CAMPAIGN = "bison.create_campaign"
EMAIL_SET_SEQUENCE = "bison.set_sequence"
EMAIL_ASSIGN_SENDER = "bison.assign_sender"
EMAIL_SET_LIMITS = "bison.set_limits"
EMAIL_PAUSE = "bison.pause"
EMAIL_ACTIVATE = "bison.activate"

OPERATIONS = {
    # operation: (channel, prospect_facing, why it is not supported yet)
    LINKEDIN_ADD_LEAD: ("linkedin", True,
        "the URL is named in heyreach.add_leads_endpoint but no successful "
        "response has ever been read; adding a lead to a RUNNING campaign is "
        "prospect-facing because the sequence acts on it immediately"),
    LINKEDIN_CREATE_LIST: ("linkedin", False,
        "no documented route; the list was created by hand in the vendor UI"),
    LINKEDIN_CREATE_CAMPAIGN: ("linkedin", False,
        "no documented route; POST /campaign/GetById already answers 405 and "
        "nothing suggests a create verb exists on the public API"),
    LINKEDIN_SET_SEQUENCE: ("linkedin", False,
        "no documented route. The graph is READABLE via "
        "/campaign/GetCampaignSequence, so a write would be verifiable the "
        "moment a verb is established - but the sequence, and therefore the "
        "note a prospect reads, was configured by hand in the vendor UI"),
    LINKEDIN_ASSIGN_SENDER: ("linkedin", False,
        "no documented route. campaignAccountIds is readable on the campaign "
        "object, so a write would be verifiable; assignment was done by hand"),
    LINKEDIN_SET_LIMITS: ("linkedin", False,
        "no documented route, and no read route exposes a per-campaign limit "
        "either, so a write could not be verified even if it existed"),
    LINKEDIN_PAUSE: ("linkedin", False,
        "SUPPORTED. POST /campaign/Pause?campaignId=, established by probe on "
        "2026-09-10: an empty body answers 400 there and 404 at "
        "/campaign/PauseCampaign. Not prospect-facing - nothing is sent, and "
        "leads in progress keep their state. This was the most uncomfortable "
        "gap in this table, because until it existed the killswitch could "
        "refuse to start a campaign and could not end one"),
    LINKEDIN_ACTIVATE: ("linkedin", True,
        "the route EXISTS - POST /campaign/Resume and /campaign/StartCampaign "
        "both answer 400 to an empty body - and it is deliberately not "
        "supported yet. Activation is prospect-facing by definition, and the "
        "order matters: a system that can start an outreach campaign before "
        "it can reliably stop one has bought exposure it cannot end"),
    EMAIL_ADD_LEAD: ("email", True,
        "the URL is named in bison.leads_endpoint and bison.build_leads builds "
        "the payload, but no successful response has been read"),
    EMAIL_CREATE_CAMPAIGN: ("email", False,
        "no documented route. GET /campaigns and /campaigns/{id} both answer, "
        "so the read side is fully established and only the create verb is "
        "missing"),
    EMAIL_SET_SEQUENCE: ("email", False,
        "GET /campaigns/{id}/sequence-steps reads them; no write verb is "
        "established"),
    EMAIL_ASSIGN_SENDER: ("email", False,
        "no documented route. /campaigns/{id}/sender-emails reads the set and "
        "pages properly, so a write would be verifiable"),
    EMAIL_SET_LIMITS: ("email", False,
        "the three limit fields are readable on the campaign object; no write "
        "verb is established"),
    EMAIL_PAUSE: ("email", False,
        "no documented route. `status` is readable on the campaign object, so "
        "a pause would be verifiable, but nothing here can perform one"),
    EMAIL_ACTIVATE: ("email", True,
        "no documented route. Prospect-facing by definition: activation is "
        "what makes a staged sequence start emailing real people"),
}

# LINKEDIN_PAUSE IS LIVE-VALIDATED. Every other operation is not.
#
# This was empty, and the note here set the exact condition for changing it:
# "one successful pause, read back as PAUSED from provider truth. Then this
# becomes `(LINKEDIN_PAUSE,)` and the stoppability cap lifts because the stop
# demonstrably exists - which is the order that makes the gate mean
# something." The condition was set deliberately high because
# `executionguard`'s `stoppability` gate reads `is_supported(pause_operation)`
# and LIFTS its one-contact cap on the answer, so this line is a promotion
# ceiling and not merely a permission.
#
# It is met, on 2026-09-12, against HeyReach campaign 594061:
#
#   POST /campaign/Pause          -> 200
#   GET  /campaign/GetById        -> status IN_PROGRESS became PAUSED
#   connectionsSent               -> 0 before and 0 after; nothing was sent
#   lead 304173736                -> request_pending before and after
#   canonical campaign state      -> recorded through `orchestrator.pause`
#   configdiff.compare_heyreach   -> PASS, 13 fields match, 1 unverifiable
#   four-way reconciliation       -> provider = canonical = ledger = touches
#
# The earlier attempt on 2026-09-10 returned a non-2xx and the write layer
# classified it UNVERIFIED, which is why this stayed empty for two days. The
# difference is a successful response that was read back, not a better
# argument about the same code.
#
# What this does NOT license: every other entry in OPERATIONS still says no
# successful response has ever been read, and each stays refused by name. A
# fixture is never a live-validated integration, and one live-validated verb
# does not validate its neighbours.
SUPPORTED = (LINKEDIN_PAUSE,)

PROSPECT_FACING = tuple(op for op, (_c, facing, _w) in OPERATIONS.items()
                        if facing)


# ------------------------------------------------------- failure classes

ACCEPTED = "accepted"        # provider confirmed and read-back agreed
REFUSED = "refused"          # provider declined before acting. Retryable
UNKNOWN = "unknown"          # we cannot say whether it acted. NEVER retryable
DRIFTED = "drifted"          # it acted, and read-back disagrees with what we
                             # asked for. Never retryable; needs a human

CLASSES = (ACCEPTED, REFUSED, UNKNOWN, DRIFTED)


class WriteRefused(RuntimeError):
    """The write did not happen and nothing changed at the provider."""


class WriteUnsupported(WriteRefused):
    """This operation has no established provider contract.

    A distinct type because it is not a safety refusal that a future
    authorization could satisfy - it is an absence of knowledge about the
    provider, and the fix is to establish the contract, not to try harder.
    """


class WriteUnverified(RuntimeError):
    """It may have happened and we cannot prove what. Never retry on this.

    Raised after a call, so unlike `WriteRefused` the provider may have acted.
    The ledger row is left UNRESOLVED, which blocks the key permanently until a
    person reconciles it by hand.
    """


def describe(operation):
    """`(channel, prospect_facing, why_unsupported)` or raise."""
    if operation not in OPERATIONS:
        raise WriteUnsupported(
            f"{operation!r} is not a declared provider operation. Add it to "
            f"OPERATIONS with its channel and whether it can reach a prospect "
            f"before writing code that performs it.")
    return OPERATIONS[operation]


def is_supported(operation):
    describe(operation)
    return operation in SUPPORTED


def require_supported(operation):
    channel, facing, why = describe(operation)
    if operation not in SUPPORTED:
        raise WriteUnsupported(
            f"{operation} is not supported in this build: {why}. "
            f"Nothing was sent to {channel}.")
    return True


def _record_confirmed_touch(authorization):
    """Write the canonical confirmed touch for an action the provider took.

    THE DUPLICATION LAW HAD NO DURABLE HALF. `touch.CONFIRMING_EVENTS` maps
    `events.PUSH_MARKED` to SENT, and `push.mark_pushed` was its only writer -
    but `push.run(live=True)` raises, so no live send could ever reach it. A
    real send therefore settled the ledger and left `push.already_pushed`,
    `eligibility._separation` and `fatigue.contact_check` with nothing to see.
    The ledger key is per STEP (`rec:contact:step:channel`), so it refuses a
    repeat of the same step and nothing else: a different step to the same
    person passed every check.

    `push.mark_pushed` is called rather than reimplemented. Two writers of one
    canonical fact is how the live path and the dry path come to disagree, and
    this module exists because that disagreement is expensive.

    `events.record` is already idempotent on the event id, and the id is
    derived from the action key, so recording twice appends once. That is what
    makes this safe to call again during reconciliation.
    """
    from . import push

    with store.transaction() as recs:
        rec = store.get(authorization.rec_id, recs)
        if rec is None:
            raise WriteUnverified(
                f"the provider acted on {authorization.rec_id!r} and that "
                f"record is no longer in the queue, so the touch cannot be "
                f"recorded. Reconcile by hand before anything else runs")
        step = push.stored_step(rec, authorization.contact_key,
                               authorization.step_key)
        push.mark_pushed(rec, authorization.contact_key,
                         authorization.step_key, authorization.key,
                         at=store.now(), day=step.get("day"))


def perform(operation, *, authorization=None, tenant=None, campaign=None,
            payload=None, transport=None, readback=None, expected=None,
            by="system"):
    """The single door. Refuses, in this order, before any transport is touched.

    `transport` and `readback` are injected so the contract can be developed
    and tested against fixtures without a live provider, which is the only
    responsible way to build a write path. Neither is optional at call time:
    a write with no read-back is a write nobody can classify.
    """
    channel, facing, _why = describe(operation)

    # 1. Is there a contract at all? Cheapest and most decisive refusal.
    require_supported(operation)

    # 2. A prospect-facing operation needs a real Authorization - the object,
    #    not something shaped like one. `executionguard` is the only thing that
    #    mints one and it does so only after every gate passes.
    if facing:
        if not isinstance(authorization, executionguard.Authorization):
            raise WriteRefused(
                f"{operation} is prospect-facing and requires an "
                f"Authorization from executionguard.authorize(); a dict "
                f"claiming the gates passed is not proof they did")
        if authorization.channel != channel:
            raise WriteRefused(
                f"the authorization is for {authorization.channel} and "
                f"{operation} writes to {channel}")
        authorization.spend()
        key = authorization.key
        # A RESERVATION MUST ALREADY EXIST. `executionguard.authorize` writes
        # one before it mints an Authorization, so in the real path this always
        # holds - but `Authorization` is a plain Python object and can be
        # constructed directly, which is exactly how this check came to be
        # needed: a hand-built one drove a write and `settle` then had nothing
        # to settle. A prospect-facing write with no durable row before it is
        # unreconcilable after it, so it is refused here rather than discovered
        # later.
        if actionledger.state_of(key) != actionledger.ATTEMPTED:
            raise WriteRefused(
                f"{operation} has no open reservation for {key!r} "
                f"(ledger says {actionledger.state_of(key)!r}). A "
                f"prospect-facing write must be reserved before it is "
                f"attempted, or nothing can reconcile it afterwards")
    else:
        key = None

    if not callable(transport):
        raise WriteRefused("no transport supplied; refusing to guess one")
    if not callable(readback):
        raise WriteRefused(
            "no read-back supplied. A provider write whose effect is never "
            "read cannot be classified, and an unclassified write is one "
            "nobody can safely retry or abandon")

    # 2b. THE STOPS, AGAIN, AGAINST DISK.
    #
    # Everything above this line asks whether the TOKEN is good: genuine,
    # unspent, right channel, reserved. None of it asks whether the PERSON
    # still wants to hear from us, and that is a different question with a
    # different answer - `authorize` asked it against whatever record the
    # caller was holding, which may have been loaded before the reply arrived.
    #
    # On 2026-09-11 that gap was demonstrated end to end: an unsubscribe was
    # persisted after the mint, `eligibility.decide` answered
    # `blocked:unsubscribed`, and this function called the transport anyway and
    # settled the ledger to `sent`.
    #
    # A refusal here costs nothing. A sent message cannot be recalled.
    if facing:
        executionguard.revalidate(authorization)

    # 3. Perform, then READ BACK BEFORE DECIDING ANYTHING.
    try:
        response = transport(payload)
    except Exception as e:
        # The provider may or may not have acted. This is the branch that must
        # never become a retry loop.
        if key:
            actionledger.settle(key, actionledger.UNRESOLVED,
                                why=f"{type(e).__name__} during {operation}")
        raise WriteUnverified(
            f"{operation} raised {type(e).__name__}: the provider may have "
            f"acted. Read provider truth and settle {key!r} by hand; do NOT "
            f"retry") from None

    try:
        observed = readback()
    except Exception as e:
        if key:
            actionledger.settle(key, actionledger.UNRESOLVED,
                                why=f"read-back failed: {type(e).__name__}")
        raise WriteUnverified(
            f"{operation} returned a response but the read-back failed "
            f"({type(e).__name__}). The provider's state is unknown; do NOT "
            f"retry") from None

    verdict = _classify(observed, expected)

    # THE TOUCH IS WRITTEN BEFORE THE LEDGER SETTLES, and the order is the
    # whole safety argument. Dying between these two writes must fail closed:
    #
    #   touch first  -> touch recorded, ledger still ATTEMPTED. The next
    #                   attempt is refused by fatigue and by the reservation.
    #   ledger first -> ledger SENT, no touch. Person-level rules see nothing,
    #                   which is precisely the defect being closed here.
    #
    # A touch recorded for an action that did not happen costs one refusal. A
    # missing touch costs a second message to a real person.
    if facing and verdict == ACCEPTED:
        try:
            _record_confirmed_touch(authorization)
        except Exception as e:
            actionledger.settle(
                key, actionledger.UNRESOLVED,
                why=f"touch not recorded: {type(e).__name__}",
                provider_response=_trim(response), readback=_trim(observed))
            raise WriteUnverified(
                f"{operation} reached the provider and was accepted, but the "
                f"confirmed touch could not be recorded ({type(e).__name__}). "
                f"The action is NOT safe to retry - reconcile it by hand"
            ) from None

    if key:
        actionledger.settle(
            key,
            actionledger.SENT if verdict == ACCEPTED else actionledger.UNRESOLVED,
            why=verdict, provider_response=_trim(response),
            readback=_trim(observed))
    if verdict != ACCEPTED:
        raise WriteUnverified(
            f"{operation}: read-back says {verdict}. Expected {expected!r}, "
            f"observed {_trim(observed)!r}. Not retryable")
    return {"operation": operation, "class": verdict, "key": key,
            "response": _trim(response), "readback": _trim(observed),
            "at": store.now()}


def _classify(observed, expected):
    """Did the provider end up in the state we asked for?"""
    if expected is None:
        return UNKNOWN
    # AN EMPTY EXPECTATION VERIFIES NOTHING. `{}` used to fall through to the
    # dict branch, whose loop then had nothing to check, and returned ACCEPTED
    # - so a caller that forgot to say what it wanted got a read-back that
    # agreed with it and a ledger row settled to SENT. Asking for nothing is
    # not the same as getting what you asked for. `0` and `False` stay real
    # expectations; only an empty container is the absence of one.
    if isinstance(expected, (dict, list, tuple, set, str)) and not expected:
        return UNKNOWN
    if isinstance(expected, dict) and isinstance(observed, dict):
        for name, want in expected.items():
            if observed.get(name) != want:
                return DRIFTED
        return ACCEPTED
    return ACCEPTED if observed == expected else DRIFTED


def _trim(value, limit=2000):
    try:
        text = json.dumps(value, default=str)
    except Exception:
        text = str(value)
    return text[:limit]


def report():
    rows = []
    for operation in sorted(OPERATIONS):
        channel, facing, why = OPERATIONS[operation]
        rows.append({"operation": operation, "channel": channel,
                     "prospect_facing": facing,
                     "supported": operation in SUPPORTED, "why": why})
    return {"supported": list(SUPPORTED), "operations": rows,
            "sealed": not SUPPORTED}


def main(argv=None):
    import argparse
    p = argparse.ArgumentParser(prog="python -m src.providerwrites",
                                description=__doc__)
    p.add_argument("--json", action="store_true")
    a = p.parse_args(argv)
    found = report()
    if a.json:
        print(json.dumps(found, indent=1))
        return 0
    print(f"provider write layer: "
          f"{'SEALED - no operation is supported' if found['sealed'] else 'OPEN'}")
    for row in found["operations"]:
        mark = "ENABLED " if row["supported"] else "unsupported"
        facing = " PROSPECT-FACING" if row["prospect_facing"] else ""
        print(f"  {mark} {row['operation']:28}{facing}")
        if not row["supported"]:
            print(f"      {row['why']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
