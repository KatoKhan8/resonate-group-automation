#!/usr/bin/env python3
"""The one gate a prospect-facing provider write must pass. Nothing else is.

WHY IT IS SHAPED AS A TOKEN RATHER THAN A FUNCTION CALL.

`killswitch.require`, `pilotcaps.require`, `bison.require_workspace`,
`approval.is_approved` and the collision and fatigue checks all already exist
and all already work. The defect was never that a check was missing - it was
that calling them was OPTIONAL, and on 2026-09-09 exactly that happened twice
in one session: `require_workspace` was skipped on three prior-contact reads
which then answered CLEAR against another client's empty estate, and nothing
compared a provider's configured copy to the approved copy at all.

A convention that every writer should call six guards is a convention somebody
will forget, and the author of the guards forgot within the hour. So the guards
are not something a writer calls; they are the only way to obtain the thing a
writer requires. `authorize()` runs all of them and returns an `Authorization`.
A write layer takes an `Authorization` and cannot be invoked without one, and
one cannot be constructed except by passing every gate - `Authorization` has no
public constructor path that skips them, and a test asserts the write layer
refuses anything that is not one.

ORDER MATTERS, AND IT IS FIXED.

  1. tenancy      - which estate are we even talking about
  2. approval     - are these exact words blessed, by fingerprint
  3. readback     - does the provider currently hold them, and how long ago
                    was that established
  4. jit          - suppression, collision, fatigue, sender health, RE-READ now
  5. cap          - against the DURABLE ledger, not a caller's plan dict
  6. ledger       - reserve the key, refusing an unsettled retry
  7. killswitch   - last, so it is the final word

Tenancy first because every later answer is meaningless if it was read from the
wrong estate. Killswitch last because it is an operator's stop button and must
not be short-circuited by an earlier pass. The ledger reservation is second to
last so that a killswitch refusal does not leave a reservation behind.

NOTHING HERE SENDS. `authorize()` is pure decision plus one ledger write.
"""
import datetime
import json
import sys

from . import (actionledger, approval, cadence, campaigns, claims, clients,
               collision, configdiff, eligibility, fatigue, killswitch, lint,
               pilotcaps, store)

# How long a provider read-back stays good. A vendor UI edit can land between
# verifying a configuration and acting on it, and 594061's own note was changed
# by hand mid-session, so this is a real window rather than a theoretical one.
READBACK_TTL_SECONDS = 15 * 60

CHANNELS = ("linkedin", "email")

# The eligibility reasons that mean somebody must not be contacted. Named from
# `eligibility`'s own constants so the two cannot drift apart.
SUPPRESSION_REASONS = (
    eligibility.BLOCKED_SUPPRESSED,
    eligibility.BLOCKED_CLIENT_SUPPRESSED,
    eligibility.BLOCKED_ACCOUNT_SUPPRESSED,
    eligibility.BLOCKED_UNSUBSCRIBED,
    eligibility.BLOCKED_CONTACT_STOPPED,
    eligibility.BLOCKED_REPLIED,
)


class NotAuthorized(RuntimeError):
    """A gate refused. The write must not happen.

    Carries `gate` so a caller can report which one, and so a test can assert
    that the intended gate fired rather than merely that something did.
    """

    def __init__(self, gate, why, passed=()):
        super().__init__(f"{gate}: {why}")
        self.gate = gate
        self.why = why
        # WHICH GATES DID PASS. A bare "refused at sender" cannot be triaged: it
        # does not say whether tenancy and approval were satisfied and the seat
        # is genuinely wrong, or whether the refusal came so early that nothing
        # downstream was evaluated at all. The canary spent a cycle on exactly
        # that ambiguity, so the trace is part of the refusal rather than
        # something a caller reconstructs by re-running with prints.
        self.passed = tuple(passed)


class Authorization:
    """Proof that every gate passed, for exactly one action.

    Deliberately not a dict. A dict can be assembled by anybody, and the whole
    point is that the write layer can tell the difference between "I checked"
    and "somebody handed me a dict that says I checked".
    """

    __slots__ = ("key", "operation", "channel", "workspace", "campaign_id",
                 "sender_id", "rec_id", "contact_key", "step_key",
                 "fingerprint", "gates", "at", "_spent")

    def __init__(self, **fields):
        for name in self.__slots__:
            if name != "_spent":
                setattr(self, name, fields.get(name))
        self._spent = False

    def spend(self):
        """One authorization, one write. Raises if reused.

        A retry loop that reuses an authorization is the same bug as a retry
        that reuses a reservation, and it is easier to write by accident.
        """
        if self._spent:
            raise NotAuthorized(
                "authorization",
                f"{self.key} has already been spent; obtain a fresh "
                f"authorization rather than reusing one")
        self._spent = True
        return self

    def as_dict(self):
        return {name: getattr(self, name) for name in self.__slots__
                if name != "_spent"}

    def __repr__(self):
        return f"<Authorization {self.key} {self.operation}>"


def _require(gate, ok, why):
    if not ok:
        raise NotAuthorized(gate, why)


def _at(value):
    """An aware datetime, or None.

    A naive timestamp is unreadable rather than assumed to be UTC, which is
    `conversation._at`'s rule and the right one here: guessing a timezone on a
    freshness check would make a stale read-back look current by up to a day.
    """
    try:
        parsed = datetime.datetime.fromisoformat(str(value or ""))
    except (ValueError, TypeError):
        return None
    return parsed if parsed.tzinfo else None


def _utcnow():
    return datetime.datetime.now(datetime.timezone.utc)


def readback_is_fresh(verified_at, now=None, ttl=READBACK_TTL_SECONDS):
    """Was the provider configuration verified recently enough to act on?

    An unparseable, naive or future-dated stamp is NOT fresh. Future-dated
    matters: a clock skew or a hand-edited record must not buy an unlimited
    window, so the age has to be non-negative as well as small.
    """
    then = _at(verified_at)
    if then is None:
        return False
    age = ((now or _utcnow()) - then).total_seconds()
    return 0 <= age <= ttl


def authorize(*, operation, channel, campaign, rec, contact, step_key,
              workspace, config=None, recs=None, now=None, by="system",
              readback=None, reserve=True):
    """Run every gate in order and return an `Authorization`, or raise.

    `readback` is the `(diff_result, verified_at)` pair from a provider
    comparison the caller has already performed. It is REQUIRED: this function
    will not perform the comparison itself, because a gate that fetches its own
    evidence can be satisfied by a caller who simply calls it twice, and
    because the read-back must be demonstrably recent rather than incidental.
    """
    gates = []

    def _require(gate, ok, why):
        """`_require` with this attempt's trace attached to any refusal."""
        if not ok:
            raise NotAuthorized(gate, why, gates)

    _require("channel", channel in CHANNELS, f"{channel!r} is not a channel")
    _require("operation", bool(operation), "an operation must be named")
    _require("campaign", bool(campaign), "no canonical campaign row")
    _require("record", bool(rec) and bool(contact),
             "no record or contact to act on")
    config = config or clients.load(campaign.get("client"))
    step = cadence.expand_step(rec, contact, _spec_for(step_key), config)
    _require("copy", bool(step), f"{step_key} does not render for this contact")


    # 1. TENANCY -------------------------------------------------------------
    if channel == "email":
        from .providers import bison
        try:
            bison.require_workspace(workspace)
        except Exception as e:
            raise NotAuthorized("tenancy", str(e), gates) from None
    else:
        _require("tenancy", str(campaign.get("org_unit") or "") != "",
                 "the canonical campaign names no org_unit, so the LinkedIn "
                 "tenant cannot be pinned")
    gates.append("tenancy")

    # 2. APPROVAL ------------------------------------------------------------
    fingerprint = approval.fingerprint(step)
    _require("approval",
             approval.is_approved(rec, contact["key"], step_key, step),
             "these exact words carry no current approval; an edit to the "
             "template, angle or evidence moves the fingerprint and the "
             "approval no longer applies")
    gates.append("approval")

    # 2b. CAMPAIGN APPROVAL --------------------------------------------------
    #
    # Step approval covers the WORDS. It does not cover which sender sends
    # them, which provider campaign and list they go through, which tenant owns
    # that campaign, what the limits are, or which leads are in scope - all of
    # which change what reaches a prospect and none of which touch
    # `approval.fingerprint(step)`.
    #
    # `campaigns.material()` already assembles exactly those facts, and
    # `approval_is_current` compares the recorded approval against a fresh
    # digest of them. So "approve, then swap the sender" is refused here, and
    # so is re-pointing the campaign at a different list.
    _require("campaign_approval",
             campaigns.approval_is_current(campaign, recs, config),
             "the campaign carries no current approval: its senders, limits, "
             "provider binding, tenant or lead set differ from what was "
             "approved, or it was never approved as a campaign at all")
    gates.append("campaign_approval")

    # 3. READBACK ------------------------------------------------------------
    # A SEALED, BOUND, SINGLE-USE READ-BACK - not a dict.
    #
    # This took a plain dict and read three things from it: the verdict, the
    # failures and a `verified_at` the CALLER stamped. Nothing tied it to a
    # campaign, a channel or a provider id, so a diff computed for campaign A
    # satisfied the gate for campaign B; and nothing marked it used, so one
    # dict authorised any number of actions. That is exactly the defect
    # `Authorization` exists to prevent, one level up, and in the same module
    # that argues a dict claiming the gates passed is not proof they did.
    _require("readback", isinstance(readback, configdiff.Readback),
             "no sealed provider read-back was supplied. Obtain one from "
             "configdiff.compare_heyreach/compare_bison, which stamps its own "
             "timestamp after the last provider read; a dict asserting a "
             "provider was verified is not proof that it was")
    _require("readback", readback.channel == channel,
             f"the read-back is for {readback.channel}, not {channel}")
    _require("readback", str(readback.campaign_id) ==
             str(campaign.get("campaign_id")),
             f"the read-back is for campaign {readback.campaign_id!r}, not "
             f"{campaign.get('campaign_id')!r}")
    expected_provider = (campaign.get("heyreach_campaign_id")
                         if channel == "linkedin"
                         else campaign.get("bison_campaign_id"))
    _require("readback",
             str(readback.provider_campaign_id) == str(expected_provider),
             f"the read-back verified provider campaign "
             f"{readback.provider_campaign_id!r}, and this campaign names "
             f"{expected_provider!r}")
    _require("readback", readback.verdict == configdiff.PASS,
             f"the provider configuration diff is {readback.verdict!r}, not "
             f"{configdiff.PASS}: {'; '.join(readback.failures)}")
    _require("readback", readback_is_fresh(readback.verified_at, now),
             f"the read-back is older than {READBACK_TTL_SECONDS}s; a vendor "
             f"UI edit can land between verifying a configuration and acting "
             f"on it, and has")
    gates.append("readback")

    # 4. JIT: suppression, collision, fatigue, sender health ------------------
    decided = eligibility.decide(rec, contact, step_key, channel=channel)
    _require("eligibility", decided.get("verdict") == "eligible",
             f"eligibility says {decided.get('verdict')}: "
             f"{decided.get('reasons') or decided.get('reason')}")
    # BEHAVIOUR, NOT A SUBSTRING. This was
    #     "suppress" not in json.dumps(decided).lower()
    # which refuses on any reason containing the word - including a CLEAR one
    # such as "suppression: none" - and passes a suppression whose reason
    # happens to be spelled differently. Asserting on serialised text is the
    # habit CLAUDE.md names, and a check that misfires is a check somebody
    # deletes. The declared reasons are the contract.
    reasons = decided.get("reasons")
    reasons = reasons if isinstance(reasons, (list, tuple)) else [
        decided.get("reason")]
    named = {str(r) for r in reasons if r}
    _require("suppression", not (named & set(SUPPRESSION_REASONS)),
             f"a suppression reason is present: "
             f"{sorted(named & set(SUPPRESSION_REASONS))}")
    problems = lint.check_step(rec, contact["key"], step)
    _require("copy", not problems, f"lint refuses the copy: {sorted(problems)}")
    text = step.get("note") or step.get("body") or ""
    found = claims.check(text, rec, contact)
    bad = found.get("problems") if isinstance(found, dict) else found
    _require("claims", not bad, f"claims refuses the copy: {bad}")
    state = fatigue.check(rec, contact["key"], config=config)
    _require("fatigue", state.get("state") == "ok",
             f"fatigue says {state.get('state')}")
    gates.extend(["eligibility", "suppression", "copy", "claims", "fatigue"])

    # Collision is re-read here rather than trusted from planning time. This is
    # the check that answered CLEAR against the wrong estate once already.
    if channel == "linkedin":
        verdict_, detail = collision.check_linkedin_profile(
            contact.get("linkedin"), contact.get("name"))
    else:
        verdict_, detail = collision.check_address(
            contact.get("email"), expect_workspace=workspace)
    _require("collision", verdict_ == collision.CLEAR,
             f"{channel} collision is {verdict_}: {detail.get('note') or detail}")
    gates.append("collision")

    # 5. CAP, against the durable ledger ------------------------------------
    sender_id = _sender_for(campaign, channel)
    _require("sender", sender_id not in (None, ""),
             f"the canonical campaign names no {channel} sender")
    # SENDER OWNERSHIP AND HEALTH. The docstring above has always listed
    # "sender health" as part of gate 4 and the code never checked it: this
    # module imported no sender module at all, so `_sender_for` asserting that
    # exactly one id was named was the whole of it. An id typo, or a seat
    # belonging to another client's estate, passed - and provider agreement is
    # no defence, because the read-back compares the sender set against what
    # the PROVIDER campaign holds, so a wrongly-assigned seat that was also
    # assigned by hand in the vendor UI matches perfectly.
    #
    # `senderidentity.require_sender` already raises `CrossWorkspaceSender`,
    # and `senderinventory` already derives readiness from provider truth.
    # Both simply had no caller here.
    # THE PROVIDER SEAT, NOT AN INTERNAL HUMAN ID. The first version of this
    # called `senderidentity.require_sender(client, sender_id)`, which looks up
    # a HUMAN sender - and the id a campaign carries is a `provider_account_id`.
    # Every inventoried seat has `sender_id: None` on purpose, because neither
    # provider knows who owns an inbox, so that lookup could never succeed and
    # the gate refused a correctly-configured canary.
    #
    # What ownership means here is: this provider seat is in THIS client's
    # canonical roster, rebuilt from provider truth, and it is active and
    # healthy. `senderinventory` derives the health; `senderidentity` scopes the
    # roster to one workspace and has no unscoped variant, which is what makes
    # this a tenancy check as well as a health one.
    from . import senderidentity
    roster = [r for r in senderidentity.accounts_for(campaign.get("client"),
                                                     channel)
              if str(r.get("provider_account_id")) == str(sender_id)]
    _require("sender", roster,
             f"{channel} seat {sender_id!r} is not in {campaign.get('client')!r}"
             f"'s canonical sender roster, so its ownership cannot be "
             f"established. A seat nobody inventoried is a seat nobody can "
             f"attribute a message to")
    seat = roster[0]
    _require("sender", seat.get("active"),
             f"{channel} seat {sender_id!r} is inventoried but not active")
    _require("sender", seat.get("health") in (None, "ok"),
             f"{channel} seat {sender_id!r} health is {seat.get('health')!r}")
    gates.append("sender")
    # THE LEDGER'S TENANT IS THE CLIENT, NOT THE PROVIDER'S WORKSPACE NUMBER.
    #
    # `workspace` here is EmailBison's numeric estate id, which is what
    # `require_workspace` and `collision` need. It is the wrong key for a cap:
    # two clients worked from one EmailBison workspace would share a ceiling,
    # and one client worked from two workspaces would have its ceiling split
    # with both halves passing. Everywhere else in this system the tenant is the
    # client slug - `repo` filters on it, `senderidentity` raises
    # `CrossWorkspaceSender` on it, `killswitch` is asked about it - so the
    # ledger uses it too, and records the provider estate separately as
    # evidence of where the action was aimed.
    tenant = campaign.get("client")
    _require("tenancy", bool(tenant),
             "the canonical campaign names no client, so the action cannot be "
             "attributed to a tenant")
    today = (now or _utcnow()).isoformat()
    already = actionledger.count_on(today, channel=channel, workspace=tenant)
    plan_key = "linkedin_per_day" if channel == "linkedin" else "email_per_day"
    try:
        pilotcaps.require({plan_key: already + 1}, config)
    except Exception as e:
        raise NotAuthorized("pilot_cap", str(e), gates) from None
    per_sender = actionledger.count_on(today, channel=channel,
                                       sender_id=sender_id, workspace=tenant)
    try:
        pilotcaps.require({"per_sender_per_day": per_sender + 1}, config)
    except Exception as e:
        raise NotAuthorized("pilot_cap", str(e), gates) from None
    gates.append("pilot_cap")

    # 6. LEDGER RESERVATION -------------------------------------------------
    key = _key(rec, contact, step_key, channel)
    try:
        actionledger.require_clear(key)
    except actionledger.ActionRefused as e:
        raise NotAuthorized("ledger", str(e), gates) from None
    # `gates` is what an audit reads to prove which checks ran, so a gate that
    # runs and does not say so is a gate nobody can demonstrate afterwards.
    gates.append("ledger")

    # 7. KILLSWITCH, last word ----------------------------------------------
    # THE CAMPAIGN ROW, NOT ITS ID. `killswitch.campaign_state` reads
    # `campaign.get("status")` and asks `campaigns.is_frozen(campaign)`, so a
    # string arrived as an AttributeError - which `except Exception` then
    # reported as a one-line type error. Three things were wrong with that and
    # only the third is obvious: the campaign layer never evaluated, so a frozen
    # or not-yet-running campaign was never consulted by the gate this docstring
    # calls the last word; the `SendingRefused` verdict, which names every layer
    # and which to fix first, was flattened away; and the test asserting the
    # gate fires was satisfied by the type error, so it passed for the wrong
    # reason.
    #
    # `SendingRefused` is caught by name and its message preserved. Anything
    # else is a bug in the killswitch itself and must not be laundered into a
    # refusal that reads like policy.
    try:
        killswitch.require(workspace=campaign.get("client"),
                           campaign=campaign, rec=rec, contact=contact,
                           step_key=step_key)
    except killswitch.SendingRefused as e:
        raise NotAuthorized("killswitch", str(e), gates) from None
    gates.append("killswitch")

    if reserve:
        # `require_clear` above already asked, and this asks again under the
        # ledger's own lock - two processes racing the same key is exactly what
        # the reservation exists to stop, so the check that matters is the one
        # inside the transaction. Translated to `NotAuthorized` so a caller has
        # one exception type to handle and one `gate` to report, rather than
        # this path leaking `actionledger.Unsettled` while every other gate
        # raises something else.
        try:
            # The ceilings go WITH the reservation, not before it. The two
            # `count_on` calls above are for the refusal message and for an
            # early exit; the binding check is the one `reserve` performs
            # inside its own transaction, because counting outside the lock and
            # appending inside it lets two workers both pass at the ceiling.
            limits = pilotcaps.effective(config)
            plan_key = ("linkedin_per_day" if channel == "linkedin"
                        else "email_per_day")
            actionledger.reserve(
                key, channel=channel, workspace=tenant,
                provider_workspace=workspace,
                campaign_id=campaign.get("campaign_id"), sender_id=sender_id,
                rec_id=rec.get("id"), contact_key=contact["key"],
                step_key=step_key, operation=operation,
                fingerprint=fingerprint, by=by,
                cap_per_day=limits[plan_key]["limit"],
                cap_per_sender=limits["per_sender_per_day"]["limit"])
        except actionledger.ActionRefused as e:
            raise NotAuthorized("ledger", str(e), gates) from None
        gates.append("reserved")

    return Authorization(
        key=key, operation=operation, channel=channel, workspace=tenant,
        campaign_id=campaign.get("campaign_id"), sender_id=sender_id,
        rec_id=rec.get("id"), contact_key=contact["key"], step_key=step_key,
        fingerprint=fingerprint, gates=tuple(gates), at=store.now())


def _spec_for(step_key):
    for spec in cadence.STEPS:
        if spec.get("key") == step_key:
            return spec
    raise NotAuthorized("copy", f"{step_key!r} is not a cadence step")


def _sender_for(campaign, channel):
    rows = (campaign.get("senders") or {}).get(channel) or []
    ids = [r.get("id") if isinstance(r, dict) else r for r in rows]
    ids = [i for i in ids if i not in (None, "")]
    if len(ids) != 1:
        raise NotAuthorized(
            "sender",
            f"the canonical campaign names {len(ids)} {channel} senders; a "
            f"guarded action is attributed to exactly one")
    return ids[0]


def _key(rec, contact, step_key, channel):
    """The idempotency key, from `push.push_id` rather than reimplemented.

    Both produced the same string, which is exactly the problem: two
    definitions of one identity drift silently, and then the ledger and
    `push.already_pushed` key different things while every test still passes.
    """
    from . import push
    return push.push_id(rec, contact.get("key"), step_key, channel)


def dry_run(**kw):
    """Every gate except the reservation. For reporting, never for writing."""
    kw["reserve"] = False
    return authorize(**kw)


def main(argv=None):
    import argparse
    p = argparse.ArgumentParser(prog="python -m src.executionguard",
                               description=__doc__)
    p.add_argument("--campaign", required=True)
    p.add_argument("--record", required=True)
    p.add_argument("--contact", required=True)
    p.add_argument("--step", default="day3")
    p.add_argument("--channel", default="linkedin", choices=CHANNELS)
    p.add_argument("--workspace", type=int, required=True)
    a = p.parse_args(argv)

    campaign = campaigns.require(a.campaign)
    rec = store.get(a.record)
    if not rec:
        print(f"no record {a.record!r}")
        return 2
    contact = lint.find_contact(rec, a.contact)
    if not contact:
        print(f"no contact {a.contact!r}")
        return 2
    # `compare_*` returns a sealed `Readback` that stamps its own time. It used
    # to return a 3-tuple and this unpacked it, which broke the moment the seal
    # landed - found by running the command rather than by a test, because
    # nothing covers this CLI.
    readback = (
        configdiff.compare_heyreach(campaign) if a.channel == "linkedin"
        else configdiff.compare_bison(campaign, expect_workspace=a.workspace))
    try:
        auth = dry_run(operation=f"{a.channel}_first_touch", channel=a.channel,
                       campaign=campaign, rec=rec, contact=contact,
                       step_key=a.step, workspace=a.workspace,
                       readback=readback)
    except NotAuthorized as e:
        for gate in e.passed:
            print(f"  PASS  {gate}")
        print(f"  STOP  {e.gate}: {e.why}")
        print(f"REFUSED at gate {e.gate} "
              f"({len(e.passed)} gate(s) passed first)")
        return 1
    print("AUTHORIZED (dry run, nothing reserved)")
    print(json.dumps(auth.as_dict(), indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
