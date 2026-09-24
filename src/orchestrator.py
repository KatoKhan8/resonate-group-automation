#!/usr/bin/env python3
"""The lifecycle of a campaign, composed from modules that already exist.

This module owns *sequence and permission*, nothing else. It does not enrich,
verify, generate, lint, or build a provider request - each of those already has
a home, and duplicating any of them would mean two answers to the same question
and eventually two different answers. What lives here is the part no existing
module can own alone: when a campaign may move, who may move it, and what must
be true first.

The gate that matters is in `launch_readiness()`, and it is deliberately
boring: campaign approval is *one* of seventeen conditions, not a master key. A
campaign that is approved but whose recipient is unverified does not launch. An
approval given before a sender changed does not launch. The approval says "this
run, as it stood, may go" - and the fingerprint is what makes "as it stood"
mean something.

  python -m src.orchestrator create --client demo --name "Q3 revive"
  python -m src.orchestrator request-approval <campaign-id>
  python -m src.orchestrator readiness <campaign-id>
"""
import argparse
import json
import sys

from . import (cadencearms, campaigns, clients, events, notify,
               observability, roles, senders, store)
from .providers import slack


class OrchestratorError(RuntimeError):
    pass


class NotPermitted(OrchestratorError):
    pass


class NotReady(OrchestratorError):
    pass


# ------------------------------------------------------------------ create

def create(campaign_id, client, name, record_ids=(), created_by="unknown",
           batch_id=None, lanes=(), personas=(), geos=(), rows=None):
    """A new campaign in `draft`. Nothing is prepared and nothing is spent."""
    if not clients.exists(client):
        raise OrchestratorError(f"no config for client {client!r}")
    own = rows is None
    rows = campaigns.load() if own else rows
    if campaigns.get(campaign_id, rows):
        raise OrchestratorError(f"campaign {campaign_id} already exists")
    campaign = campaigns.new_campaign(campaign_id, client, name,
                                      batch_id=batch_id, created_by=created_by,
                                      lanes=lanes, personas=personas, geos=geos)
    campaign["record_ids"] = sorted(set(record_ids))
    _note(campaign, events.CAMPAIGN_CREATED, by=created_by)
    rows.append(campaign)
    if own:
        campaigns.save(rows)
    return campaign


def _note(campaign, event_type, **fields):
    """Campaign events live on the campaign, in the same shape as record
    events, so one reporting reader can walk both.

    The parameter is `event_type`, not `kind`: `kind` is a field name several
    of these events carry, and a positional that shadows it silently swallows
    the caller's value.
    """
    entry = {"type": event_type, "at": store.now()}
    entry.update({k: v for k, v in fields.items() if v not in (None, "", [], {})})
    entry["id"] = events.event_id({**entry, "record_id": campaign.get("campaign_id")})
    existing = campaign.setdefault("events", [])
    if entry.get("interaction_id") and any(
            e.get("interaction_id") == entry["interaction_id"] for e in existing):
        return None
    if any(e.get("id") == entry["id"] for e in existing):
        return None
    existing.append(entry)
    return entry


def set_records(campaign, record_ids):
    """Change the population. This moves the fingerprint, which is the point."""
    campaign["record_ids"] = sorted(set(record_ids))
    campaigns.log(campaign, "records", f"{len(campaign['record_ids'])} record(s)")
    return _invalidate_if_needed(campaign, "the records in the campaign changed")


def set_cadence_experiment(campaign, experiment, by="unknown",
                           role=roles.ADMIN, recs=None, config=None):
    """Put a cadence experiment on a campaign, or raise.

    Eight modules read `campaign["cadence_experiment"]` and until this
    existed nothing wrote it, so a cadence experiment could not be created
    by any path an operator could reach - the arms model, the assignment,
    the exposure accounting and the whole report were unreachable from a
    real campaign. Which is the failure this repository keeps producing and
    the one the cadence mission was written to measure.

    Validated before it is stored, because `cadence.steps_for` resolves an
    arm on every page load and a malformed experiment would surface as a
    broken timeline rather than as a bad edit.

    Launch-sensitive by construction: the arms decide what each contact is
    sent, so setting or changing one voids an approval that predates it,
    the same as changing the records or the senders.
    """
    roles.require(role, roles.CHANGE_MAPPING, by)
    cadencearms.require(experiment)

    if (campaign.get("launch") or {}).get("state") == "launched":
        raise campaigns.CampaignError(
            "this campaign has launched; its cadence experiment cannot be "
            "changed while people are part-way through an arm")

    orphaned = _orphaned_arms(campaign, experiment, recs)
    if orphaned:
        raise campaigns.CampaignError(
            "these arms have contacts assigned to them and are not in the "
            "new experiment: " + ", ".join(orphaned)
            + ". Their assignments would resolve to nothing and those "
              "contacts would silently fall back to the default cadence")

    campaign[cadencearms.EXPERIMENT_KEY] = experiment
    campaigns.log(campaign, "cadence_experiment",
                  f"{len(cadencearms.arms_of(experiment))} arm(s): "
                  + ", ".join(entry["arm_id"]
                              for entry in cadencearms.arms_of(experiment)))
    return _invalidate_if_needed(campaign, "the cadence experiment changed",
                                 recs, config)


def clear_cadence_experiment(campaign, by="unknown", role=roles.ADMIN,
                             recs=None, config=None):
    """Take the experiment off. Every contact returns to the campaign's own
    sequence, or to the default if it has none.

    Refused while anybody is assigned, for the same reason as removing an
    arm: their recorded assignment would resolve to nothing.
    """
    roles.require(role, roles.CHANGE_MAPPING, by)
    existing = campaign.get(cadencearms.EXPERIMENT_KEY)
    if not existing:
        return campaign
    assigned = _assigned_arms(campaign, existing, recs)
    if assigned:
        raise campaigns.CampaignError(
            "contacts are assigned to " + ", ".join(sorted(assigned))
            + "; removing the experiment would leave their assignments "
              "pointing at nothing")
    campaign[cadencearms.EXPERIMENT_KEY] = None
    campaigns.log(campaign, "cadence_experiment", "removed")
    return _invalidate_if_needed(campaign, "the cadence experiment was removed",
                                 recs, config)


def _assigned_arms(campaign, experiment, recs=None):
    """Which of this experiment's arms actually have somebody in them."""
    from . import account

    recs = store.load() if recs is None else recs
    ids = set(campaign.get("record_ids") or [])
    found = set()
    for rec in recs:
        if rec.get("id") not in ids:
            continue
        for contact in account.contacts_of(rec):
            entry = cadencearms.recorded(experiment, rec, contact)
            if entry and entry.get("arm_id"):
                found.add(entry["arm_id"])
    return found


def _orphaned_arms(campaign, experiment, recs=None):
    """Arms somebody is in that the replacement experiment does not have."""
    existing = campaign.get(cadencearms.EXPERIMENT_KEY)
    if not existing:
        return []
    if existing.get("experiment_id") != experiment.get("experiment_id"):
        # A different experiment entirely. Assignments are recorded against
        # an experiment id and will not be read by the new one, so nothing
        # is orphaned - they are simply no longer in an experiment.
        return []
    keeping = {entry["arm_id"] for entry in cadencearms.arms_of(experiment)}
    return sorted(_assigned_arms(campaign, existing, recs) - keeping)


def map_external(campaign, bison_campaign_id=None, heyreach_campaign_id=None,
                 by="unknown", role=roles.ADMIN):
    """Point the campaign at existing external campaigns (mode A).

    Mode B is simply not calling this: a campaign with no external id is
    perfectly valid until the moment a channel with work needs one, which the
    launch checklist reports rather than assumes.
    """
    roles.require(role, roles.CHANGE_MAPPING, by)
    if bison_campaign_id is not None:
        campaign["bison_campaign_id"] = str(bison_campaign_id)
    if heyreach_campaign_id is not None:
        campaign["heyreach_campaign_id"] = str(heyreach_campaign_id)
    _note(campaign, events.EXTERNAL_CAMPAIGN_MAPPED, by=by,
          bison=campaign.get("bison_campaign_id"),
          heyreach=campaign.get("heyreach_campaign_id"))
    return _invalidate_if_needed(campaign, "the external campaign mapping changed")


def set_senders(campaign, email=None, linkedin=None, by="unknown",
                role=roles.ADMIN):
    roles.require(role, roles.CHANGE_MAPPING, by)
    mapping = campaign.setdefault("senders", {"email": [], "linkedin": []})
    if email is not None:
        mapping["email"] = list(email)
    if linkedin is not None:
        mapping["linkedin"] = list(linkedin)
    return _invalidate_if_needed(campaign, "the sender accounts changed")


def set_daily_volume(campaign, email=None, linkedin=None, by="unknown",
                     role=roles.ADMIN):
    roles.require(role, roles.CHANGE_MAPPING, by)
    volume = campaign.setdefault("daily_volume", {})
    if email is not None:
        volume["email"] = int(email)
    if linkedin is not None:
        volume["linkedin"] = int(linkedin)
    return _invalidate_if_needed(campaign, "the daily volume changed")


def _invalidate_if_needed(campaign, why, recs=None, config=None):
    """Any launch-sensitive edit voids an approval that predates it."""
    given = campaign.get("approval") or {}
    if given.get("action") != "approve":
        return campaign
    if campaigns.approval_is_current(campaign, recs, config):
        return campaign
    campaign["approval"] = None
    campaign["fingerprint"] = None
    _note(campaign, events.CAMPAIGN_APPROVAL_INVALIDATED, reason=why)
    campaigns.log(campaign, "approval", f"invalidated: {why}")
    if campaign.get("status") in (campaigns.APPROVED, campaigns.LAUNCH_READY):
        campaigns.set_status(campaign, campaigns.PREPARING,
                             why, allow=(campaigns.PREPARING,))
    return campaign


def refresh_approval(campaign, recs=None, config=None):
    """Re-check an existing approval against the campaign as it stands now.

    Called before anything that depends on approval, so a change made anywhere
    else - a redrafted email, a dropped record - invalidates without that code
    needing to know campaigns exist.
    """
    return _invalidate_if_needed(campaign, "a launch-sensitive field changed",
                                 recs, config)


# ----------------------------------------------------------------- prepare

def summarise(campaign, recs=None, config=None):
    """The numbers a human needs to decide. Counted, never estimated."""
    recs = store.load() if recs is None else recs
    if config is None:
        try:
            config = clients.load(campaign.get("client"))
        except Exception:
            config = {}
    from . import lint
    mine = [r for r in recs if r["id"] in set(campaign.get("record_ids") or [])]
    contacts = [c for r in mine for c in (r.get("contacts") or [])]
    return {
        "campaign_id": campaign.get("campaign_id"),
        "client": campaign.get("client"),
        "name": campaign.get("name"),
        "domains": len({r.get("domain") for r in mine if r.get("domain")}),
        "records": len(mine),
        "contacts": len(contacts),
        "sendable": sum(1 for c in contacts if lint.sendable(c)),
        "held": sum(1 for r in mine if r.get("state") == "held"),
        "dropped": sum(1 for r in mine if r.get("state") == "dropped"),
        "suppressed": sum(1 for r in mine
                          if (r.get("drop_reason") or "").startswith("suppress")),
        "email_senders": [a["id"] for a in senders.enabled(campaign, "email")],
        "linkedin_senders": [a["id"] for a in senders.enabled(campaign, "linkedin")],
        "daily_volume": campaign.get("daily_volume") or {},
        "cadence": campaign.get("cadence_version") or (config or {}).get("cadence"),
        "estimate": campaigns.cost_estimate(campaign, recs, config),
        "fingerprint": campaigns.fingerprint(campaign, recs, config),
    }


def prepare(campaign, recs=None, config=None):
    """Move a draft to ready_for_review once it has something to review."""
    campaigns.set_status(campaign, campaigns.PREPARING, "preparing")
    summary = summarise(campaign, recs, config)
    if not campaign.get("record_ids"):
        campaigns.set_status(campaign, campaigns.FAILED, "no records")
        raise NotReady(f"{campaign['campaign_id']} has no records")
    assigned = assign_cadence_arms(campaign, recs)
    campaigns.set_status(campaign, campaigns.READY_FOR_REVIEW, "prepared")
    _note(campaign, events.CAMPAIGN_READY_FOR_REVIEW,
          contacts=summary["contacts"], sendable=summary["sendable"])
    summary["cadence_arms_assigned"] = assigned
    return summary


def assign_cadence_arms(campaign, recs=None):
    """Put every unit in this campaign into an arm, once.

    Here rather than in `cadence.build` on purpose. Building a timeline
    happens on every page load, and an assignment written there would be
    an assignment made by whoever happened to look. Preparing a campaign
    is deliberate, happens once, and happens *before* the approval
    fingerprint is taken - so what a reviewer approves already includes
    which arm each contact is in.

    Idempotent: `cadencearms.assign` keeps an existing assignment and
    writes nothing, so re-preparing a campaign never moves anybody.

    Returns how many units it put in an arm. The caller saves the records;
    this mutates them, in keeping with every other assignment in this
    build.
    """
    exp = (campaign or {}).get(cadencearms.EXPERIMENT_KEY)
    if not exp:
        return 0
    recs = store.load() if recs is None else recs
    ids = set(campaign.get("record_ids") or [])
    count = 0
    for rec in recs:
        if rec.get("id") not in ids:
            continue
        before = cadencearms.recorded(exp, rec)
        cadencearms.assign(exp, rec)
        if not before and cadencearms.recorded(exp, rec):
            count += 1
    return count


def request_approval(campaign, recs=None, config=None):
    """Build the approval request and plan its notification. Nothing posts."""
    if config is None:
        config = clients.load(campaign.get("client"))
    if campaign.get("status") == campaigns.READY_FOR_REVIEW:
        campaigns.set_status(campaign, campaigns.AWAITING_APPROVAL,
                             "approval requested")
    summary = summarise(campaign, recs, config)
    campaign["fingerprint"] = summary["fingerprint"]
    payload = slack.campaign_approval_request(campaign, summary, config)
    _note(campaign, events.CAMPAIGN_APPROVAL_REQUESTED,
          fingerprint=summary["fingerprint"])
    plan = plan_notification(campaign, slack.CAMPAIGN_READY, payload, config)
    # The global operations feed. Deliberately separate from the client's own
    # channel: held counts, credit exposure and QA verdicts are how the
    # machine is run, and none of it is a client's business. The workspace is
    # carried so the feed can say *whose* campaign this is, which is not the
    # same as routing it to them.
    routed = notify.notify(
        notify.CAMPAIGN_APPROVAL_REQUIRED,
        notify.workspace_for_client(campaign.get("client")),
        fields={
            "campaign": campaign.get("name") or campaign.get("campaign_id"),
            "segment": campaign.get("segment_key"),
            "companies": summary.get("records"),
            "contacts": summary.get("contacts"),
            "sendable": summary.get("sendable"),
            "held": summary.get("held"),
            "suppressed": summary.get("suppressed"),
            "estimated_credits": (summary.get("estimate") or {}).get("expected"),
            "fingerprint": summary.get("fingerprint"),
        },
        ids={"campaign_id": campaign.get("campaign_id"),
             "fingerprint": summary.get("fingerprint")},
        actions=[{"action_id": "approve_campaign", "text": "Approve",
                  "style": "primary"},
                 {"action_id": "reject_campaign", "text": "Reject",
                  "style": "danger"},
                 {"action_id": "open_review", "text": "Open in Web App"}])
    return {"summary": summary, "payload": payload, "notification": plan,
            "routed": routed}


# ---------------------------------------------------------------- approval

def decide(campaign, slack_user_id, action, fingerprint=None, interaction_id=None,
           config=None, recs=None, at=None, role=None):
    """Apply one approval decision. Idempotent, permissioned, fingerprint-bound.

    Every refusal below has cost someone a bad afternoon somewhere:
      - an unknown user approving because the button was visible to the channel
      - the same click counted twice because Slack retried the delivery
      - an approval landing on a campaign that had changed since it was posted
    """
    if config is None:
        config = clients.load(campaign.get("client"))

    # Idempotency first: a retried interaction must not even be evaluated
    # twice, or a second refusal would be logged for an action already applied.
    if interaction_id:
        for entry in campaign.get("events") or []:
            if entry.get("interaction_id") == interaction_id:
                return {"status": "duplicate", "action": entry.get("type"),
                        "why": "this interaction was already applied"}

    # Authorisation has three doors now, and the third is the one the web
    # layer needs.
    #
    # `slack.allowed_approvers` names somebody when the decision arrives from
    # Slack. `roles:` in the client config names them by any other route.
    # Both live in the *client config*, which knows nothing about workspaces -
    # so a workspace reviewer whose right to approve was already established
    # from the membership table resolved to VIEWER here and was refused, and
    # the approval screen could not approve anything for anybody.
    #
    # An earlier fix made the role check run before the Slack check, which
    # opened the door for an actor the config names. It did not help an actor
    # the config has never heard of, because there was no way to tell this
    # function that somebody else had already done the authorising.
    #
    # `role` is that way. Three things keep it from being a hole:
    #
    #   - It is validated against `roles.ROLES`. An unknown string is refused
    #     rather than trusted.
    #   - `roles.require` still runs. A role that does not carry the
    #     permission is refused exactly as before - passing `viewer` here
    #     buys nothing.
    #   - The caller is the *server*, never the request. `src/web/app.py`
    #     derives it from the workspace membership it already resolved and
    #     already checked `campaign.approve` against; nothing from the browser
    #     reaches this argument.
    #
    # Omitting it keeps the previous behaviour exactly, which is what the
    # Slack path does.
    if role is None:
        role = roles.role_of(config, slack_user_id, default=roles.VIEWER)
        if role is roles.VIEWER and not slack.may_approve(config, slack_user_id):
            slack.require_approver(config, slack_user_id)
    elif role not in roles.ROLES:
        raise roles.NotPermitted(
            f"{role!r} is not a role; approval is refused rather than "
            "attempted against a role nobody defined")
    permission = (roles.APPROVE_CAMPAIGN if action == "approve"
                  else roles.REJECT_CAMPAIGN)
    roles.require(role, permission, slack_user_id)

    current = campaigns.fingerprint(campaign, recs, config)
    if action == "approve":
        if fingerprint and fingerprint != current:
            return {"status": "stale", "why": (
                "the campaign changed since this approval request was posted"),
                "expected": current, "given": fingerprint}
        campaign["approval"] = {
            "action": "approve", "by": slack_user_id, "at": at or store.now(),
            "fingerprint": current, "interaction_id": interaction_id,
            "source": "slack",
        }
        campaign["fingerprint"] = current
        campaigns.set_status(campaign, campaigns.APPROVED,
                             f"approved by {slack_user_id}",
                             allow=(campaigns.APPROVED,))
        _note(campaign, events.CAMPAIGN_APPROVED, by=slack_user_id,
              fingerprint=current, interaction_id=interaction_id)
        campaigns.log(campaign, "approval", f"approved by {slack_user_id}")
        return {"status": "approved", "fingerprint": current}

    if action == "reject":
        campaign["approval"] = {
            "action": "reject", "by": slack_user_id, "at": at or store.now(),
            "fingerprint": current, "interaction_id": interaction_id,
            "source": "slack",
        }
        campaigns.set_status(campaign, campaigns.REJECTED,
                             f"rejected by {slack_user_id}",
                             allow=(campaigns.REJECTED,))
        _note(campaign, events.CAMPAIGN_REJECTED, by=slack_user_id,
              interaction_id=interaction_id)
        campaigns.log(campaign, "approval", f"rejected by {slack_user_id}")
        return {"status": "rejected", "fingerprint": current}

    raise OrchestratorError(f"unknown action: {action}")


# ------------------------------------------------------------- launch gate

def launch_readiness(campaign, recs=None, config=None):
    """Every condition, re-checked now. Approval is one of them, not a bypass."""
    refresh_approval(campaign, recs, config)
    result = campaigns.validate(campaign.get("campaign_id"), recs=recs,
                                config=config, campaign=campaign)
    if result["ok"] and campaign.get("status") == campaigns.APPROVED:
        campaigns.set_status(campaign, campaigns.LAUNCH_READY, "all checks pass")
        _note(campaign, events.CAMPAIGN_LAUNCH_READY,
              fingerprint=result.get("fingerprint"))
    return result


def may_launch(campaign, recs=None, config=None):
    return launch_readiness(campaign, recs, config)["ok"]


def freeze(campaign, why, by="unknown", role=roles.ADMIN):
    """The stop button. It must say why, and anyone who may pause may hit it.

    Nothing about the campaign's status or approval changes, so this is safe
    to hit in a hurry and cheap to undo. What it does change is
    `eligibility.decide()`, which blocks every step of a frozen campaign.

    Stopping is deliberately easier than starting again: freezing needs
    PAUSE_CAMPAIGN, which a reviewer holds, while lifting one needs
    RESUME_CAMPAIGN, which only an admin does.
    """
    roles.require(role, roles.PAUSE_CAMPAIGN, by)
    if not why:
        raise NotPermitted("a freeze must say why")
    frozen = campaigns.freeze(campaign, why, by=by)
    if frozen:
        _note(campaign, events.CAMPAIGN_FROZEN, by=by, why=why)
    return campaign


def unfreeze(campaign, by="unknown", why="", role=roles.ADMIN):
    """Lift a freeze. The approval it had before is the approval it has now."""
    roles.require(role, roles.RESUME_CAMPAIGN, by)
    lifted = campaigns.unfreeze(campaign, by=by, why=why)
    if lifted:
        _note(campaign, events.CAMPAIGN_UNFROZEN, by=by,
              frozen_at=lifted.get("at"), was=lifted.get("why"))
    return campaign


def pause(campaign, why="paused", by="unknown", role=roles.ADMIN,
          provider=True):
    """Stop planning steps AND tell the provider, where a route is proven.

    This used to be canonical state only, and said so: it wrote
    `campaign["pause"]` while a campaign already running at the vendor kept
    running. That was honest when no pause verb was supported.

    It is no longer, and the gap had a consequence. `executionguard`'s
    `stoppability` gate lifts a promotion ceiling the moment
    `providerwrites.is_supported(pause_op)` answers True - which it now does
    for both channels - so the ceiling that bounds unrecallable exposure was
    resting on a stop that only a hand-written script could invoke. A declared
    capability nothing calls is the defect this repository keeps finding.

    The provider leg NEVER prevents the local one. If the vendor call fails,
    this system must still stop planning steps: refusing to record a local
    pause because a provider was unreachable would leave the campaign running
    at both ends. The outcome is recorded either way, so nobody reads a local
    pause as a provider stop again.
    """
    roles.require(role, roles.PAUSE_CAMPAIGN, by)
    campaign["pause"] = {"since": store.now(), "reason": why, "by": by}
    campaigns.set_status(campaign, campaigns.PAUSED, why,
                         allow=(campaigns.PAUSED,))
    stopped = _pause_at_provider(campaign, by=by) if provider else None
    _note(campaign, events.CAMPAIGN_PAUSED, by=by, reason=why,
          provider_stop=stopped)
    return campaign


def _pause_at_provider(campaign, by="unknown"):
    """Halt this campaign at whichever vendors it is actually bound to.

    Returns what happened per channel, never raising: see `pause` above for
    why a provider failure must not block the local stop.
    """
    from . import providerwrites

    bindings = (("linkedin", providerwrites.LINKEDIN_PAUSE,
                 campaign.get("heyreach_campaign_id")),
                ("email", providerwrites.EMAIL_PAUSE,
                 campaign.get("bison_campaign_id")))
    out = {}
    for channel, operation, provider_id in bindings:
        if not provider_id:
            continue
        if not providerwrites.is_supported(operation):
            out[channel] = {"stopped": False, "why": "not supported"}
            continue
        try:
            out[channel] = _perform_pause(operation, channel, campaign,
                                          provider_id, by)
        except Exception as e:
            # Classified, never swallowed. An unstopped provider campaign is
            # precisely the thing somebody has to go and look at.
            out[channel] = {"stopped": False, "error": type(e).__name__,
                            "why": str(e)[:200]}
    return out or None


def _perform_pause(operation, channel, campaign, provider_id, by):
    from . import providerwrites
    from .providers import bison, heyreach

    if channel == "linkedin":
        transport = lambda _p: heyreach.pause_campaign(provider_id)
        readback = lambda: {"status": heyreach.campaign_status(provider_id)}
        expected = {"status": "PAUSED"}
    else:
        transport = lambda _p: bison.pause_campaign(provider_id)
        readback = lambda: {"status": bison.campaign(provider_id).get("status")}
        expected = {"status": "paused"}
    outcome = providerwrites.perform(
        operation, campaign=str(campaign.get("campaign_id")),
        tenant=campaign.get("client"),
        payload={"campaign_id": provider_id}, transport=transport,
        readback=readback, expected=expected, by=by)
    return {"stopped": True, "provider_campaign": provider_id,
            "class": (outcome or {}).get("class")}


def resume(campaign, by="unknown", role=roles.ADMIN, recs=None, config=None):
    """Resuming re-checks everything. A pause is not undone by forgetting it."""
    roles.require(role, roles.RESUME_CAMPAIGN, by)
    result = campaigns.validate(campaign.get("campaign_id"), recs=recs,
                                config=config, campaign=campaign,
                                ignore_status=True)
    if not result["ok"]:
        raise NotReady("cannot resume: " + ", ".join(result["blockers"]))
    campaign["pause"] = None
    campaigns.set_status(campaign, campaigns.RUNNING, f"resumed by {by}",
                         allow=(campaigns.RUNNING,))
    _note(campaign, events.CAMPAIGN_RESUMED, by=by)

    # THE PROVIDER IS ASKED, AND THE ANSWER IS RECORDED.
    #
    # Until 2026-09-24 this function ended at the line above: it cleared the
    # local pause, wrote a local event, and NEVER TOLD THE PROVIDER. A resumed
    # campaign therefore read RUNNING here while EmailBison still had it
    # paused, and nothing anywhere recorded that divergence - `perform` was
    # never called, so no ledger row existed to notice.
    #
    # It does not raise. A resume that cannot reach the provider is still a
    # local resume, and losing the local state change would trade a visible
    # divergence for an invisible one. The per-channel outcome is returned
    # instead, the same shape `pause` uses, so a caller can see that the
    # provider half did not happen.
    campaign["resume_at_providers"] = _resume_at_providers(campaign, by)
    return campaign


def _resume_at_providers(campaign, by):
    """Ask each provider to resume. Never raises; classifies instead.

    BOTH VERBS ARE SEALED TODAY and that is the point of calling them. A
    sealed verb refuses by name and leaves a ledger row, which is strictly
    better than the silence it replaces: before this, a LinkedIn resume did
    nothing and said nothing, and there was no way to tell that apart from a
    resume that worked.
    """
    from . import providerwrites
    from .providers import bison, heyreach

    out = {}
    for channel, key, operation, transport, readback, expected in (
            ("email", "bison_campaign_id", providerwrites.EMAIL_RESUME,
             lambda pid: bison.resume_campaign(pid),
             lambda pid: {"status": bison.campaign(pid).get("status")},
             {"status": "running"}),
            ("linkedin", "heyreach_campaign_id", providerwrites.LINKEDIN_RESUME,
             lambda pid: heyreach.resume_campaign(pid),
             lambda pid: {"status": heyreach.campaign_status(pid)},
             {"status": "IN_PROGRESS"})):
        provider_id = campaign.get(key)
        if not provider_id:
            out[channel] = {"attempted": False, "resumed": False,
                            "why": "this campaign names no %s" % key}
            continue
        try:
            outcome = providerwrites.perform(
                operation, campaign=str(campaign.get("campaign_id")),
                tenant=campaign.get("client"),
                payload={"campaign_id": provider_id},
                transport=lambda _p, t=transport, pid=provider_id: t(pid),
                readback=lambda r=readback, pid=provider_id: r(pid),
                expected=expected, by=by)
            out[channel] = {"attempted": True, "resumed": True,
                            "class": (outcome or {}).get("class")}
        except Exception as e:
            # Classified, never swallowed. `perform` has already written the
            # ledger row for this by the time we get here.
            out[channel] = {"attempted": True, "resumed": False,
                            "error": type(e).__name__, "why": str(e)[:200]}
    return out


def complete(campaign, why="finished"):
    campaign["completed_at"] = store.now()
    campaigns.set_status(campaign, campaigns.COMPLETED, why,
                         allow=(campaigns.COMPLETED,))
    _note(campaign, events.CAMPAIGN_COMPLETED)
    return campaign


# --------------------------------------------------------------- launching

def launch(campaign, day=21, recs=None, config=None, live=False, rows=None):
    """The last door. Readiness is checked first, then the door is still shut.

    The order matters for what it proves: an unapproved campaign is refused for
    being unapproved, not for the build being offline. If the live-send refusal
    came first it would mask every other gate, and the day sending is switched
    on all of them would be untested.
    """
    result = launch_readiness(campaign, recs, config)
    if not result["ok"]:
        raise NotReady(
            f"{campaign.get('campaign_id')} is not ready to launch: "
            + ", ".join(result["blockers"]))

    from . import push
    if live:
        raise push.LiveSendNotEnabled(
            "live sending is not enabled in this build. The campaign passed "
            "every launch check, the payloads are built and the mapping is in "
            "place; no code here can reach EmailBison or HeyReach.")

    plan = campaigns.dry_run(campaign.get("campaign_id"), day=day, recs=recs,
                             config=config, campaign=campaign)
    for row in plan["senders"].items():
        _note(campaign, events.SENDER_ASSIGNED, channel=row[0],
              accounts=", ".join(row[1]))
    return {"launched": False, "ready": True, "plan": plan,
            "why": "dry run: this build prepares payloads and sends nothing"}


# ----------------------------------------------------------- notifications

def plan_notification(campaign, kind, payload, config, rec=None,
                      channel=slack.UNSET):
    """Record that a message should go out. Sending is a separate, failable act.

    Planning and sending are two events because they are two facts, and the
    gap between them is where a Slack outage lives. Nothing downstream waits on
    the send.
    """
    allowed, why = slack.should_notify(config, kind, channel)
    entry = {"kind": kind, "channel": payload.get("channel"),
             "planned": allowed, "why": why,
             "metadata": payload.get("metadata") or {}}
    fields = {"notification": kind, "channel": payload.get("channel"),
              "enabled": allowed, "why": None if allowed else why}
    if rec is not None:
        events.record(rec, events.SLACK_NOTIFICATION_PLANNED, **fields)
    if campaign:
        _note(campaign, events.SLACK_NOTIFICATION_PLANNED, **fields)
    return entry


def deliver(payload, config, campaign=None, rec=None, post=None, attempts=2,
            sleep=None):
    """Attempt a post and record the outcome. Failure is recorded, not raised.

    A caller that pauses a company then notifies must not have the pause undone
    by a transport error, so this never propagates one.

    The retry is bounded and small. Slack being down is not an emergency - the
    pause is already in place - and a notification layer that retries hard is a
    notification layer that hammers a provider during an outage.
    """
    import time
    post = post or slack.post
    sleep = sleep or time.sleep
    kind = payload.get("kind")
    observability.count(events.SLACK_POST_PLANNED, kind=kind,
                        channel=payload.get("channel"))

    last = None
    for attempt in range(max(1, attempts)):
        try:
            response = post(payload, config)
        except slack.SlackPostingNotEnabled as e:
            # Not a transport failure and never retryable: posting is off.
            detail = f"{type(e).__name__}: {slack.redact(str(e))}"
            _record_delivery(events.SLACK_NOTIFICATION_FAILED, kind, payload,
                             campaign, rec, detail)
            observability.count(events.SLACK_POST_FAILED, kind=kind,
                                reason="posting disabled")
            return {"sent": False, "retryable": False, "why": detail}
        except Exception as e:
            last = f"{type(e).__name__}: {slack.redact(str(e))}"
            if attempt < attempts - 1:
                observability.count(events.EVENT_RETRY_SCHEDULED, kind=kind,
                                    attempt=attempt + 1)
                sleep(min(2 ** attempt, 4))
                continue
            _record_delivery(events.SLACK_NOTIFICATION_FAILED, kind, payload,
                             campaign, rec, last)
            observability.count(events.SLACK_POST_FAILED, kind=kind)
            return {"sent": False, "retryable": True, "why": last,
                    "attempts": attempt + 1}
        _record_delivery(events.SLACK_NOTIFICATION_SENT, kind, payload,
                         campaign, rec)
        observability.count(events.SLACK_POST_SENT, kind=kind)
        return {"sent": True, "response": response, "attempts": attempt + 1}
    return {"sent": False, "retryable": True, "why": last}


def _record_delivery(event_type, kind, payload, campaign, rec, reason=None):
    fields = {"notification": kind, "channel": payload.get("channel")}
    if reason:
        fields["reason"] = reason
    if rec is not None:
        events.record(rec, event_type, **fields)
    if campaign:
        _note(campaign, event_type, **fields)


def positive_reply_notification(rec, contact_key, verdict, config, campaign=None,
                                source=None, step=None, post=None):
    """The full path for a positive reply: pause first, notify second.

    The ordering is the safety property. `replies.apply()` has already paused
    the account through `accountpolicy.apply_reply()` (a positive reply maps
    to HOLD at ACCOUNT scope) before this function runs; this function only
    tells someone. If Slack is off, misconfigured or broken, the pause is
    untouched and the alert stays retryable.

    Where it goes is the workspace's decision, not the client config's. When
    the record's client resolves to exactly one workspace, that workspace's
    `slack.workspace_channel` is the channel - and if it has none, this alert
    has no channel either. The client config's `positive_replies_channel` is
    not consulted in that case and is not a fallback: two routers with two
    answers is how a client's reply ends up in the wrong room.
    """
    contact = next((c for c in rec.get("contacts") or []
                    if c.get("key") == contact_key), {})
    detail = {
        "client": rec.get("client"),
        "campaign_id": (campaign or {}).get("campaign_id"),
        "company": rec.get("company"),
        "contact": contact.get("name") or contact_key,
        "contact_key": contact_key,
        "title": contact.get("title"),
        "channel": verdict.get("channel") or (contact.get("channel")),
        "source": source,
        "angle": contact.get("angle"),
        "persona": contact.get("persona"),
        "step": step,
        "record_id": rec.get("id"),
        "excerpt": verdict.get("excerpt"),
    }
    workspace = notify.workspace_for_client(rec.get("client"))
    channel = (notify.workspace_channel(workspace) if workspace
               else slack.UNSET)
    payload = slack.positive_reply_alert(detail, config, channel=channel)
    plan = plan_notification(campaign or {}, slack.POSITIVE_REPLY, payload,
                             config, rec=rec, channel=channel)
    outcome = {"sent": False, "why": plan["why"]}
    if plan["planned"]:
        outcome = deliver(payload, config, campaign=campaign, rec=rec, post=post)
    return {"payload": payload, "notification": plan, "delivery": outcome,
            "paused": bool(rec.get("paused"))}


def operational_alerts(config, held_count=0, provider_failures=0, batch=None):
    """Threshold-gated alerts, so the channel stays worth reading."""
    out = []
    if held_count >= slack.threshold(config, "held_count_threshold"):
        out.append(slack.operational_alert(
            slack.LARGE_HELD_COUNT, config,
            text=f"{held_count} records held",
            detail={"held": held_count}))
    if provider_failures >= slack.threshold(config, "provider_failure_threshold"):
        out.append(slack.operational_alert(
            slack.PROVIDER_FAILURE, config,
            text=f"{provider_failures} provider failures",
            detail={"failures": provider_failures}))
    if batch:
        out.append(slack.batch_summary(batch, config))
    return [p for p in out if slack.should_notify(config, p["kind"])[0]]


# ---------------------------------------------------------------- the CLI

def main(argv=None):
    p = argparse.ArgumentParser(prog="python -m src.orchestrator")
    sub = p.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("create")
    c.add_argument("campaign_id")
    c.add_argument("--client", required=True)
    c.add_argument("--name", required=True)
    c.add_argument("--record", action="append", dest="records", default=[])
    c.add_argument("--by", default="cli")

    for name in ("readiness", "request-approval", "summary"):
        s = sub.add_parser(name)
        s.add_argument("campaign_id")

    a = p.parse_args(argv)

    if a.cmd == "create":
        with campaigns.transaction() as rows:
            campaign = create(a.campaign_id, a.client, a.name,
                              record_ids=a.records, created_by=a.by, rows=rows)
        print(f"created {campaign['campaign_id']} for {campaign['client']} "
              f"({campaign['status']})")
        return 0

    try:
        campaign = campaigns.require(a.campaign_id)
    except campaigns.NotFound as e:
        print(f"REFUSED: {e}")
        return 2

    if a.cmd == "summary":
        print(json.dumps(summarise(campaign), indent=2, ensure_ascii=False))
        return 0

    if a.cmd == "request-approval":
        with campaigns.transaction() as rows:
            campaign = campaigns.require(a.campaign_id, rows)
            result = request_approval(campaign)
        print(json.dumps(result["payload"], indent=2, ensure_ascii=False))
        print("\nNothing was posted. This build builds payloads only.")
        return 0

    if a.cmd == "readiness":
        with campaigns.transaction() as rows:
            campaign = campaigns.require(a.campaign_id, rows)
            result = launch_readiness(campaign)
        print(f"campaign {result['campaign_id']}: "
              + ("READY" if result["ok"] else
                 f"NOT READY ({len(result['blockers'])} blocker(s))"))
        for row in result["checks"]:
            print(f"  {'ok  ' if row['ok'] else 'BLOCK'} {row['check']:<32} "
                  f"{row['detail']}")
        return 0 if result["ok"] else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
