#!/usr/bin/env python3
"""Six ways to stop outbound, and the rule that the most restrictive wins.

## Why this exists before sending does

Nothing in this build can send. `push.run(live=True)` raises and
`tagsync.send` refuses, and neither is a flag. So a kill switch is, today,
a switch on a machine with no engine.

It is written now anyway, and the reason is the order of events on the day
sending is enabled. That day somebody removes one refusal in `push`. If
the layers below it do not already exist, tested, with a default of off,
then the day the engine arrives is the day somebody has to invent the
brakes - under time pressure, with a client waiting.

## The layers, outermost first

    GLOBAL      this build cannot send at all
    WORKSPACE   this tenant has not been switched on
    CAMPAIGN    this campaign is not running
    ACCOUNT     this company is held, paused or suppressed
    CONTACT     this person is suppressed, stopped or has replied
    STEP        this specific step, re-decided right now

The most restrictive wins, and that is not the same as "the first one that
says no". Every layer is evaluated and every verdict is reported, because
an operator who turns a campaign back on needs to see that the account is
still held - otherwise they turn one thing on, nothing happens, and they
go looking for a bug.

## Default off, at every layer that has a setting

A workspace with no `sending.live` override does not send. Not because the
value is missing and something defaulted, but because `off` is what
absence means here and there is a test that says so. The failure this
prevents is the ordinary one: a new workspace created for a demo, and
nobody remembers whether the switch was ever set.

## It cannot turn anything on

This module reads. There is no setter, no environment variable it
consults that would enable anything, and `GLOBAL` is derived from the
refusal in `push` rather than from a flag - so the only way to make
`sending` true here is to change the code that refuses, which is a review
and not a toggle.
"""
import argparse
import json

from . import accountpolicy as ap, campaigns, workspaces

# Outermost first. The order is the report order, and it is also the order
# somebody would have to unlock things in.
GLOBAL = "global"
WORKSPACE = "workspace"
CAMPAIGN = "campaign"
ACCOUNT = "account"
CONTACT = "contact"
STEP = "step"

LAYERS = (GLOBAL, WORKSPACE, CAMPAIGN, ACCOUNT, CONTACT, STEP)

LAYER_LABEL = {
    GLOBAL: "This build",
    WORKSPACE: "This workspace",
    CAMPAIGN: "This campaign",
    ACCOUNT: "This company",
    CONTACT: "This person",
    STEP: "This step",
}

# The workspace override that would switch a tenant on. Named here and
# registered in `workspaces.POLICY_KEYS`, so the setting is a real one with
# an audit trail rather than a constant somebody edits.
WORKSPACE_KEY = "sending.live"

ON = "on"
OFF = "off"


def _verdict(layer, sending, why, **extra):
    return {"layer": layer, "label": LAYER_LABEL[layer], "sending": sending,
            "why": why, **extra}


# ----------------------------------------------------------------- global

def global_state():
    """Can this build send at all?

    Derived from the refusal rather than from a flag. `push.run` raises
    `LiveSendNotEnabled` for any live call, so the answer is no and the
    only way to change it is to change that code - which is a review, not
    a toggle. A boolean here that some environment variable could flip
    would be a second answer to a question `push` has already settled.
    """
    from . import push

    refuses = hasattr(push, "LiveSendNotEnabled")
    return _verdict(
        GLOBAL, not refuses,
        "live sending is refused in code: push.run(live=True) raises and "
        "tagsync.send refuses unconditionally. This is not a flag"
        if refuses else
        "the refusal in push.py is gone, so this layer no longer stops "
        "anything",
        refused_in_code=refuses)


# -------------------------------------------------------------- workspace

def workspace_state(slug, rows=None):
    """Has this tenant been switched on? Absence means no.

    The failure this prevents is a new workspace created for a demo where
    nobody remembers whether the switch was set. Absence is `off`, and
    that is asserted rather than assumed.
    """
    if not slug:
        return _verdict(WORKSPACE, False,
                        "no workspace was named, so nothing is authorised")
    entry = workspaces.workspace(slug, rows)
    if entry is None:
        return _verdict(WORKSPACE, False, f"no such workspace: {slug}")
    value = (workspaces.policy(slug, rows) or {}).get(WORKSPACE_KEY)
    if value is None:
        return _verdict(WORKSPACE, False,
                        "this workspace has never been switched on. No "
                        "setting is not a setting of on")
    on = str(value).strip().lower() == ON
    return _verdict(WORKSPACE, on,
                    f"{WORKSPACE_KEY} is {ON if on else OFF} for {slug}")


# --------------------------------------------------------------- campaign

def campaign_state(campaign):
    """Is this campaign in a state that would send?"""
    if campaign is None:
        return _verdict(CAMPAIGN, False, "no campaign was named")
    status = campaign.get("status")
    # A freeze outranks the status, here as in `eligibility._campaign`,
    # where it is checked before anything else because it is the stop
    # button. This report did not consult it at all, so a frozen campaign
    # whose status was still `running` was reported as one that would send
    # - on the screen an operator opens to ask exactly that question,
    # while the send path was correctly refusing it.
    if campaigns.is_frozen(campaign):
        return _verdict(CAMPAIGN, False, "this campaign is frozen",
                        status=status)
    if status == campaigns.PAUSED or campaign.get("paused"):
        return _verdict(CAMPAIGN, False, "this campaign is paused",
                        status=status)
    # `RUNNING` is the only status that sends. `LAUNCH_READY` means every
    # check passed and a human has not pressed the button - which is a
    # different thing, and treating the two as one would make the button
    # decorative.
    return _verdict(CAMPAIGN, status == campaigns.RUNNING,
                    f"campaign status is {status}"
                    + ("" if status == campaigns.RUNNING else
                       "; only " + campaigns.RUNNING + " sends"),
                    status=status)


# ---------------------------------------------------------------- account

def account_state(rec):
    """Is this company open to outreach at all?

    Delegated to `accountpolicy`, which owns the question. A second
    opinion here would be a second account policy, and the one that gets
    forgotten is always the one guarding the expensive mistake.
    """
    if rec is None:
        return _verdict(ACCOUNT, False, "no company was named")
    if rec.get("state") == "dropped":
        return _verdict(ACCOUNT, False,
                        rec.get("drop_reason") or "this record was dropped")
    state, why = ap.account_state(rec)
    if state == ap.SUPPRESS:
        return _verdict(ACCOUNT, False, "this company asked us to stop",
                        state=state)
    if state == ap.HOLD:
        return _verdict(ACCOUNT, False,
                        (why or {}).get("reason")
                        or "held while a conversation is live", state=state)
    return _verdict(ACCOUNT, True, "nothing holds this company", state=state)


# ---------------------------------------------------------------- contact

def contact_state(contact):
    if contact is None:
        return _verdict(CONTACT, False, "no person was named")
    state, why = ap.contact_state(contact)
    if state == ap.CONTINUE:
        return _verdict(CONTACT, True, "nothing holds this person",
                        state=state)
    return _verdict(CONTACT, False,
                    (why or {}).get("reason") or f"this person is {state}",
                    state=state)


# ------------------------------------------------------------------- step

def step_state(rec, contact, step_key, **kw):
    """The pre-send recheck: may this exact step go out right now?

    Delegated to `eligibility`, which is the only authority on the
    question. Imported here rather than at module scope because
    `eligibility` imports half the engine and this module is read by
    screens that need none of it.
    """
    if not (rec and contact and step_key):
        return _verdict(STEP, False, "no step was named")
    from . import eligibility

    decision = eligibility.decide(rec, contact, step_key, **kw)
    return _verdict(STEP, bool(decision.eligible),
                    ", ".join(eligibility.explain(r)
                              for r in decision["reasons"])
                    or "every condition passes",
                    verdict=decision["verdict"],
                    reasons=list(decision["reasons"]))


# ------------------------------------------------------------- the answer

def state(workspace=None, campaign=None, rec=None, contact=None,
          step_key=None, rows=None, **kw):
    """Every layer, and whether anything may be sent.

    All six are evaluated even after one has said no. An operator who
    turns a campaign back on needs to see that the account is still held;
    reporting only the first refusal sends them looking for a bug in the
    thing they just fixed.
    """
    layers = [global_state(), workspace_state(workspace, rows)]
    if campaign is not None:
        layers.append(campaign_state(campaign))
    if rec is not None:
        layers.append(account_state(rec))
    if contact is not None:
        layers.append(contact_state(contact))
    if step_key:
        layers.append(step_state(rec, contact, step_key, **kw))

    blocking = [row for row in layers if not row["sending"]]
    return {
        "sending": not blocking,
        # The outermost refusal, because that is the one to fix first.
        "blocked_by": blocking[0]["layer"] if blocking else None,
        "why": blocking[0]["why"] if blocking else "every layer permits it",
        "blocked_count": len(blocking),
        "layers": layers,
        "note": "the most restrictive layer wins, and every layer is "
                "reported. Turning one on does not send anything while "
                "another still refuses",
    }


class SendingRefused(RuntimeError):
    """A layer of the kill switch refused. Carries every layer's verdict."""

    def __init__(self, verdict):
        self.verdict = verdict
        blocked = [row["layer"] for row in verdict["layers"]
                   if not row["sending"]]
        super().__init__(
            f"{verdict['blocked_by']}: {verdict['why']} "
            f"({verdict['blocked_count']} of {len(verdict['layers'])} layers "
            f"refuse: {', '.join(blocked)})")


def require(workspace=None, campaign=None, rec=None, contact=None,
            step_key=None, rows=None, **kw):
    """Raise unless every layer permits. The enforcing form of `state`.

    `state` reports and this refuses, and the difference matters on the day
    sending is enabled. Until now this module had no importer outside its own
    tests, so `sending.live` was a real setting with an audit entry that
    stopped nothing - `workspaces.POLICY_KEYS` says so in as many words. It was
    safe only because `push.run(live=True)` raises in code, which is a
    guarantee about this build rather than about the policy.

    So this exists to be called by whatever eventually sends, and the reason it
    is written before that caller is the order of events: on the day somebody
    deletes the refusal in `push`, the brakes have to already be here, tested,
    defaulting to off. Wiring it into `eligibility.decide` instead would not
    work and is worth recording as a dead end - `decide` runs during dry
    previews, the global layer correctly answers "this build cannot send", and
    a preview that refuses every step is the whole product refusing itself.
    """
    verdict = state(workspace=workspace, campaign=campaign, rec=rec,
                    contact=contact, step_key=step_key, rows=rows, **kw)
    if not verdict["sending"]:
        raise SendingRefused(verdict)
    return verdict


def main(argv=None):
    p = argparse.ArgumentParser(prog="python -m src.killswitch",
                                description=__doc__)
    p.add_argument("--workspace")
    p.add_argument("--json", action="store_true")
    a = p.parse_args(argv)

    found = state(workspace=a.workspace)
    if a.json:
        print(json.dumps(found, indent=2, default=str))
        return 0
    for row in found["layers"]:
        mark = "SENDS" if row["sending"] else "STOPS"
        print(f"  {mark:<6} {row['label']:<16} {row['why']}")
    print()
    print("SENDING" if found["sending"]
          else f"NOT SENDING - outermost refusal: {found['blocked_by']}")
    print(found["note"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
