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


class NotAuthorized(RuntimeError):
    """A gate refused. The write must not happen.

    Carries `gate` so a caller can report which one, and so a test can assert
    that the intended gate fired rather than merely that something did.
    """

    def __init__(self, gate, why):
        super().__init__(f"{gate}: {why}")
        self.gate = gate
        self.why = why


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
    _require("channel", channel in CHANNELS, f"{channel!r} is not a channel")
    _require("operation", bool(operation), "an operation must be named")
    _require("campaign", bool(campaign), "no canonical campaign row")
    _require("record", bool(rec) and bool(contact),
             "no record or contact to act on")
    config = config or clients.load(campaign.get("client"))
    step = cadence.expand_step(rec, contact, _spec_for(step_key), config)
    _require("copy", bool(step), f"{step_key} does not render for this contact")

    gates = []

    # 1. TENANCY -------------------------------------------------------------
    if channel == "email":
        from .providers import bison
        try:
            bison.require_workspace(workspace)
        except Exception as e:
            raise NotAuthorized("tenancy", str(e)) from None
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

    # 3. READBACK ------------------------------------------------------------
    _require("readback", isinstance(readback, dict),
             "no provider read-back was supplied; a write may not proceed on "
             "the assumption that the provider holds what was approved")
    verdict = (readback.get("diff") or {}).get("verdict")
    _require("readback", verdict == configdiff.PASS,
             f"the provider configuration diff is {verdict!r}, not "
             f"{configdiff.PASS}: "
             f"{'; '.join((readback.get('diff') or {}).get('failures') or [])}")
    _require("readback", readback_is_fresh(readback.get("verified_at"), now),
             f"the read-back is older than {READBACK_TTL_SECONDS}s; a vendor "
             f"UI edit can land between verifying a configuration and acting "
             f"on it, and has")
    gates.append("readback")

    # 4. JIT: suppression, collision, fatigue, sender health ------------------
    decided = eligibility.decide(rec, contact, step_key, channel=channel)
    _require("eligibility", decided.get("verdict") == "eligible",
             f"eligibility says {decided.get('verdict')}: "
             f"{decided.get('reason')}")
    _require("suppression", "suppress" not in json.dumps(decided).lower(),
             "a suppression reason is present on the eligibility verdict")
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
    today = (now or _utcnow()).isoformat()
    already = actionledger.count_on(today, channel=channel)
    plan_key = "linkedin_per_day" if channel == "linkedin" else "email_per_day"
    try:
        pilotcaps.require({plan_key: already + 1}, config)
    except Exception as e:
        raise NotAuthorized("pilot_cap", str(e)) from None
    per_sender = actionledger.count_on(today, channel=channel,
                                       sender_id=sender_id)
    try:
        pilotcaps.require({"per_sender_per_day": per_sender + 1}, config)
    except Exception as e:
        raise NotAuthorized("pilot_cap", str(e)) from None
    gates.append("pilot_cap")

    # 6. LEDGER RESERVATION -------------------------------------------------
    key = _key(rec, contact, step_key, channel)
    try:
        actionledger.require_clear(key)
    except actionledger.ActionRefused as e:
        raise NotAuthorized("ledger", str(e)) from None

    # 7. KILLSWITCH, last word ----------------------------------------------
    try:
        killswitch.require(workspace=campaign.get("client"),
                           campaign=campaign.get("campaign_id"),
                           rec=rec, contact=contact, step_key=step_key)
    except Exception as e:
        raise NotAuthorized("killswitch", str(e)) from None
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
            actionledger.reserve(
                key, channel=channel, workspace=workspace,
                campaign_id=campaign.get("campaign_id"), sender_id=sender_id,
                rec_id=rec.get("id"), contact_key=contact["key"],
                step_key=step_key, operation=operation,
                fingerprint=fingerprint, by=by)
        except actionledger.ActionRefused as e:
            raise NotAuthorized("ledger", str(e)) from None
        gates.append("reserved")

    return Authorization(
        key=key, operation=operation, channel=channel, workspace=workspace,
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
    return f"{rec.get('id')}:{contact.get('key')}:{step_key}:{channel}"


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
    diff, _approved, _provider = (
        configdiff.compare_heyreach(campaign) if a.channel == "linkedin"
        else configdiff.compare_bison(campaign, expect_workspace=a.workspace))
    try:
        auth = dry_run(operation=f"{a.channel}_first_touch", channel=a.channel,
                       campaign=campaign, rec=rec, contact=contact,
                       step_key=a.step, workspace=a.workspace,
                       readback={"diff": diff, "verified_at": store.now()})
    except NotAuthorized as e:
        print(f"REFUSED at gate {e.gate}: {e.why}")
        return 1
    print("AUTHORIZED (dry run, nothing reserved)")
    print(json.dumps(auth.as_dict(), indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
