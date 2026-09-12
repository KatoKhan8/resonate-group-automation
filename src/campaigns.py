#!/usr/bin/env python3
"""The campaign: what a batch of work becomes once a human is asked to bless it.

## Why this is not in the queue

work/queue.jsonl holds records, and a record is one company. A campaign is not
a company: it has no domain, no contacts, no lane, and it would fail every
invariant store.validate() enforces. Rather than bend the record schema around
it, campaigns get their own append-only file next to the queue,
work/campaigns.jsonl, with the same lock, the same atomic write and the same
"never delete, always log" discipline. store.py owns both files; this module
owns the shape of one row in this one.

## What a campaign is for

Two things, and only two:

  1. It is the unit a human approves. A draft approval says "these words are
     fine". A campaign approval says "this whole run may go". Both are needed
     before anything can be sent, and neither can substitute for the other.
  2. It is the thing that goes stale. Approval is bound to a fingerprint of
     every launch-sensitive fact - contacts, drafts, cadence, senders, external
     campaign ids, daily volume, sending config. Move any of them and the
     approval is void, automatically, with no one having to remember.

The campaign holds no message text and no contact data. It holds the ids of the
records in it and reads the rest from the queue, so there is exactly one copy
of every fact.

  python -m src.campaigns list
  python -m src.campaigns show <campaign-id>
  python -m src.campaigns validate <campaign-id>
  python -m src.campaigns dry-run <campaign-id>
"""
import argparse
import hashlib
import json
import os
import sys

from . import approval, cadence, clients, lint, store

# ------------------------------------------------------------------ status

DRAFT = "draft"
PREPARING = "preparing"
READY_FOR_REVIEW = "ready_for_review"
AWAITING_APPROVAL = "awaiting_approval"
APPROVED = "approved"
LAUNCH_READY = "launch_ready"
RUNNING = "running"
PAUSED = "paused"
COMPLETED = "completed"
REJECTED = "rejected"
FAILED = "failed"

STATUSES = (DRAFT, PREPARING, READY_FOR_REVIEW, AWAITING_APPROVAL, APPROVED,
            LAUNCH_READY, RUNNING, PAUSED, COMPLETED, REJECTED, FAILED)

# Where a campaign may go from where it is. A campaign never moves backwards
# into approval: a rejected or invalidated one is re-prepared, not un-rejected.
TRANSITIONS = {
    DRAFT: (PREPARING, FAILED),
    PREPARING: (READY_FOR_REVIEW, FAILED, DRAFT),
    READY_FOR_REVIEW: (AWAITING_APPROVAL, PREPARING, FAILED),
    AWAITING_APPROVAL: (APPROVED, REJECTED, PREPARING, FAILED),
    APPROVED: (LAUNCH_READY, PREPARING, REJECTED, FAILED),
    LAUNCH_READY: (RUNNING, PAUSED, PREPARING, REJECTED, FAILED),
    RUNNING: (PAUSED, COMPLETED, FAILED),
    PAUSED: (RUNNING, COMPLETED, FAILED),
    COMPLETED: (),
    REJECTED: (PREPARING,),
    FAILED: (PREPARING,),
}

# Statuses in which no step may be prepared or pushed, whatever else is true.
UNLAUNCHABLE = (DRAFT, PREPARING, READY_FOR_REVIEW, AWAITING_APPROVAL,
                REJECTED, FAILED, COMPLETED, PAUSED)


class CampaignError(RuntimeError):
    """Something about the campaign itself is wrong. Nothing was written."""


class NotFound(CampaignError):
    pass


class BadTransition(CampaignError):
    pass


# ------------------------------------------------------------------- state

def path():
    return store.campaigns_path()


def load():
    return store.Snapshot(store.read_jsonl(path()), key="campaign_id")


def save(rows, timeout=None):
    """Write the campaign file back, merging when `rows` came from `load`.

    THE STOP BUTTON WAS REVERTIBLE BY ANY CONCURRENT WRITE. This replaced the
    whole file, and `interactions.decide` loads it, runs `orchestrator.decide`
    and saves the snapshot back across that window. A `freeze` written in
    between - the flag `eligibility` reads to block every step of a campaign,
    written because a client asked us to stop - was gone, lifted by a write
    that had no opinion about it and by a caller that never knew.

    There is no `refuse_history_loss` for this file, so the queue's answer is
    the one used here too: `store.Snapshot` remembers what each row was when
    it was read, rows this caller did not touch keep whatever is on disk now,
    and a plain list still replaces the file for callers that built their rows
    from somewhere else.
    """
    with store.lock(timeout, for_path=path()):
        if isinstance(rows, store.Snapshot):
            rows = rows.merge_onto(store.read_jsonl(path()))
        store.write_jsonl(path(), rows)


def transaction(timeout=None):
    return store.file_transaction(path(), timeout)


def get(campaign_id, rows=None):
    for row in rows if rows is not None else load():
        if row.get("campaign_id") == campaign_id:
            return row
    return None


def require(campaign_id, rows=None):
    found = get(campaign_id, rows)
    if found is None:
        raise NotFound(f"no such campaign: {campaign_id}")
    return found


def new_campaign(campaign_id, client, name, batch_id=None, created_by="unknown",
                 lanes=(), personas=(), geos=()):
    """The campaign skeleton. Field shape lives here and nowhere else."""
    return {
        "campaign_id": campaign_id,
        "client": client,
        "name": name,
        "status": DRAFT,
        "created_at": store.now(),
        "created_by": created_by,
        "batch_id": batch_id,
        "lanes": list(lanes),
        "personas": list(personas),
        "geos": list(geos),
        "record_ids": [],
        "daily_volume": {"email": 0, "linkedin": 0},
        "senders": {"email": [], "linkedin": []},
        "cadence_version": None,
        "approval": None,              # set by the orchestrator, never by hand
        "fingerprint": None,           # what the approval was taken against
        "bison_campaign_id": None,
        "heyreach_campaign_id": None,
        "launch": {"state": "not_launched", "at": None},
        "pause": None,
        "started_at": None,
        "completed_at": None,
        "log": [],
        "events": [],
    }


def log(campaign, step, note, **extra):
    entry = {"at": store.now(), "step": step, "note": note}
    entry.update({k: v for k, v in extra.items() if v not in (None, "", [], {})})
    campaign.setdefault("log", []).append(entry)
    return entry


def set_status(campaign, status, why="", allow=None):
    """Move a campaign, or refuse. The map above is the whole rulebook."""
    if status not in STATUSES:
        raise BadTransition(f"unknown status: {status}")
    current = campaign.get("status", DRAFT)
    if status == current:
        return campaign
    allowed = TRANSITIONS.get(current, ())
    if status not in allowed and status not in (allow or ()):
        raise BadTransition(
            f"{campaign.get('campaign_id')} cannot go {current} -> {status}. "
            f"From {current} it may only go to: {', '.join(allowed) or 'nowhere'}")
    campaign["status"] = status
    log(campaign, "status", f"{current} -> {status}" + (f": {why}" if why else ""))
    return campaign


# ------------------------------------------------------------- fingerprint
#
# Everything below is launch-sensitive: change any of it and the run that goes
# out is not the run that was approved. The digest is deterministic - sorted,
# canonical JSON - so the same campaign always fingerprints the same way in any
# process, on any machine, in any order.

def _contact_material(rec, contact):
    """A contact as far as launching cares: who, where, and may we send."""
    return {
        "key": contact.get("key"),
        "email": (contact.get("email") or "").lower(),
        "linkedin": (contact.get("linkedin") or "").lower(),
        "sendable": bool(contact.get("sendable")),
        "persona": contact.get("persona"),
        # The angle selects which words get rendered, so it already moves the
        # step text digest. Named here anyway because it is a decision somebody
        # approved, and a field that only matters transitively is a field that
        # stops mattering the day the template changes.
        "angle": contact.get("angle"),
    }


def _step_material(rec, contact_key, step_key, step):
    """The words, as approved, plus whether they still carry an approval."""
    return {
        "step": step_key,
        "channel": step.get("channel"),
        "day": step.get("day"),
        "text": approval.fingerprint(step),
        "approved": bool(approval.is_approved(rec, contact_key, step_key, step)),
    }


def sending_config(config):
    """Only the parts of a client config that change what is sent or when."""
    config = config or {}
    return {
        "cadence": config.get("cadence"),
        "sender": config.get("sender"),
        "tone": config.get("tone"),
        "booking_link": config.get("booking_link"),
        "linkedin_note_mode": clients.linkedin_note_mode(config),
        "verification": clients.verification_policy(config),
    }


def material(campaign, recs=None, config=None):
    """Everything the fingerprint covers, assembled in one place so it is
    readable. If a field belongs in an approval decision, it belongs here."""
    recs = store.load() if recs is None else recs
    by_id = {r["id"]: r for r in recs}
    paused_set = cadence.paused_domains(recs)
    if config is None:
        try:
            config = clients.load(campaign.get("client"))
        except Exception:
            config = {}

    records = []
    for rid in sorted(campaign.get("record_ids") or []):
        rec = by_id.get(rid)
        if rec is None:
            records.append({"id": rid, "missing": True})
            continue
        timeline = cadence.build(rec, config, recs=recs, paused_set=paused_set,
                                 campaign=campaign)
        contacts, steps = [], []
        for contact in sorted(rec.get("contacts") or [],
                              key=lambda c: c.get("key") or ""):
            contacts.append(_contact_material(rec, contact))
        for contact_key in sorted(timeline.get("contacts") or {}):
            for step_key in sorted(timeline["contacts"][contact_key]):
                steps.append({"contact": contact_key,
                              **_step_material(rec, contact_key, step_key,
                                               timeline["contacts"][contact_key][step_key])})
        records.append({"id": rid, "state": rec.get("state"),
                        "dropped": bool(rec.get("drop_reason")),
                        "paused": bool(rec.get("paused")),
                        "contacts": contacts, "steps": steps})

    return {
        "client": campaign.get("client"),
        "records": records,
        "senders": {
            "email": sorted(campaign.get("senders", {}).get("email") or [],
                            key=lambda s: json.dumps(s, sort_keys=True)),
            "linkedin": sorted(campaign.get("senders", {}).get("linkedin") or [],
                               key=lambda s: json.dumps(s, sort_keys=True)),
        },
        "daily_volume": campaign.get("daily_volume") or {},
        "bison_campaign_id": campaign.get("bison_campaign_id"),
        "heyreach_campaign_id": campaign.get("heyreach_campaign_id"),
        # The rest of the provider binding. Without these the fingerprint moved
        # when the campaign id changed but NOT when the list, the tenant, the
        # node delay or the expected status did - so a campaign could be
        # re-pointed at a different list, or a different LinkedIn organisation,
        # while still carrying a current approval. `configdiff` compares every
        # one of them against provider truth, which is exactly why each has to
        # be part of what was approved.
        "heyreach_list_id": campaign.get("heyreach_list_id"),
        "org_unit": campaign.get("org_unit"),
        "workspace": campaign.get("workspace"),
        "provider_delays": campaign.get("provider_delays"),
        "provider_status_expected": campaign.get("provider_status_expected"),
        "cadence_version": campaign.get("cadence_version"),
        "config": sending_config(config),
    }


def fingerprint(campaign, recs=None, config=None):
    """A stable digest of every launch-sensitive fact."""
    blob = json.dumps(material(campaign, recs, config), sort_keys=True,
                      ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:20]


def approval_is_current(campaign, recs=None, config=None):
    """Is the approval on this campaign still about this campaign?"""
    given = campaign.get("approval") or {}
    if given.get("action") != "approve":
        return False
    return given.get("fingerprint") == fingerprint(campaign, recs, config)


def is_approved(campaign, recs=None, config=None):
    return (campaign.get("status") in (APPROVED, LAUNCH_READY, RUNNING, PAUSED)
            and approval_is_current(campaign, recs, config))


# -------------------------------------------------------------- the checks
#
# One function per condition, each returning (ok, detail), so the validator can
# print a checklist rather than one opaque pass/fail.

TERMINAL_STATUSES = (COMPLETED, REJECTED, FAILED)


# A record claimed by two live campaigns. Not a campaign, and deliberately
# not `None`: an absence permits, and this has to block. `record_ids` is empty
# so anything that walks it finds nothing to act on.
AMBIGUOUS = {"campaign_id": None, "ambiguous": True, "record_ids": [],
             "status": "ambiguous"}


def by_record(rows=None):
    """{record_id: campaign} for the campaigns still capable of sending.

    Membership is one-directional - a campaign lists its records and a
    record knows nothing - so a caller holding a record had no way to ask
    which sequence it is in. That is why `cadence.build` was given its
    campaign at one call site out of thirty-five: most callers had nothing
    to pass.

    A record in two live campaigns maps to `AMBIGUOUS`, and that used to be
    `None`. The reasoning for `None` was that guessing an arm would put a
    contact in a cadence nobody chose - which is right - but `None` does not
    mean "ambiguous" to anything downstream. It means NO CAMPAIGN, and
    `eligibility._campaign` returns immediately for a campaign of `None`, so
    the freeze, the pause, the rejection, the launch state and the approval
    staleness check all stopped applying at once. Measured on 2026-09-11:

        a frozen campaign alone           -> blocked:campaign_frozen
        the same record in two campaigns  -> eligible

    So duplicating a campaign intent did not merely duplicate - it detached
    the stop button on the original. The ambiguity is real and is now carried
    as a value that blocks rather than as an absence that permits.

    A COMPLETED campaign still does not claim its records: it ran to its end,
    and its records running the default afterwards is the intended behaviour.
    REJECTED and FAILED are different - they mean this campaign was stopped -
    and releasing their records to the default cadence made a rejected
    campaign's records MORE sendable than an approved one's, with no approval
    required at all. They keep their records, and `_campaign` blocks on them.
    """
    rows = load() if rows is None else rows
    index = {}
    for campaign in rows:
        if campaign.get("status") == COMPLETED:
            continue
        for rid in campaign.get("record_ids") or []:
            index[rid] = campaign if rid not in index else AMBIGUOUS
    return index


def _records_of(campaign, recs):
    by_id = {r["id"]: r for r in recs}
    return [by_id[i] for i in campaign.get("record_ids") or [] if i in by_id]


def check_records_present(campaign, recs, config):
    missing = [i for i in campaign.get("record_ids") or []
               if not any(r["id"] == i for r in recs)]
    return (not missing,
            "every record in the campaign is in the queue" if not missing
            else f"{len(missing)} record(s) are not in the queue: "
                 + ", ".join(sorted(missing)[:5]))


def check_not_launched(campaign, recs, config):
    launched = (campaign.get("launch") or {}).get("state") == "launched"
    return (not launched,
            "this campaign has not been launched" if not launched
            else "already launched: relaunching would duplicate every send")


def check_campaign_approved(campaign, recs, config):
    given = campaign.get("approval") or {}
    if given.get("action") == "reject":
        return False, "the campaign was rejected"
    if not given:
        return False, "no campaign approval has been given"
    if not approval_is_current(campaign, recs, config):
        return False, ("the campaign changed since it was approved, so the "
                       "approval no longer applies")
    return True, f"approved by {given.get('by') or 'unknown'}"


def check_drafts_approved(campaign, recs, config):
    missing = []
    paused_set = cadence.paused_domains(recs)
    for rec in _records_of(campaign, recs):
        timeline = cadence.build(rec, config, recs=recs, paused_set=paused_set,
                                 campaign=campaign)
        for contact_key, steps in (timeline.get("contacts") or {}).items():
            for step_key, step in steps.items():
                if step.get("channel") != "email":
                    continue
                if not approval.is_approved(rec, contact_key, step_key, step):
                    missing.append(f"{rec['id']}:{contact_key}:{step_key}")
    return (not missing,
            "every outbound email step carries a current draft approval"
            if not missing else
            f"{len(missing)} step(s) have no current draft approval: "
            + ", ".join(missing[:3]))


def check_lint_clean(campaign, recs, config):
    failures = []
    paused_set = cadence.paused_domains(recs)
    for rec in _records_of(campaign, recs):
        timeline = cadence.build(rec, config, recs=recs, paused_set=paused_set,
                                 campaign=campaign)
        for contact_key, steps in (timeline.get("contacts") or {}).items():
            for step_key, step in steps.items():
                if step.get("channel") != "email":
                    continue
                for failure in lint.check(rec, contact_key, step):
                    failures.append(f"{rec['id']}:{step_key}:{failure}")
    return (not failures,
            "every final email passes lint" if not failures
            else f"{len(failures)} lint failure(s): " + ", ".join(failures[:3]))


def check_no_duplicate_copy(campaign, recs, config):
    """No two email steps for one person may say the same thing.

    Every step here passes lint on its own; what fails is the sequence. This
    is a launch blocker rather than a warning because the second identical
    email is the one the recipient notices, and by then it has been sent.

    A shared subject line with different bodies is reported by QA and does not
    block: the body is what arrives.
    """
    from . import duplicates

    findings = duplicates.blocking(
        duplicates.find(_records_of(campaign, recs), config,
                        campaign=campaign))
    if not findings:
        return True, "no two email steps for one person say the same thing"
    named = ", ".join(f"{f['record_id']}/{f['contact_key']} "
                      f"({' and '.join(f['steps'])})" for f in findings[:3])
    return (False,
            f"{len(findings)} duplicate email body/bodies: {named}"
            + (" ..." if len(findings) > 3 else "")
            + ". Regenerate the step; do not edit it to differ trivially")


def check_recipients_sendable(campaign, recs, config):
    bad = []
    for rec in _records_of(campaign, recs):
        for contact in rec.get("contacts") or []:
            if contact.get("email") and not lint.sendable(contact):
                bad.append(f"{rec['id']}:{contact.get('key')}")
    return (not bad,
            "every email recipient is verified sendable" if not bad
            else f"{len(bad)} recipient(s) are not sendable: " + ", ".join(bad[:3]))


def check_double_verification(campaign, recs, config):
    """No email step may exist for an address short of its confirmations.

    `check_recipients_sendable` above already refuses an unsendable recipient,
    and under the current policy an under-confirmed address is unsendable - so
    this cannot fire while that holds. It is a separate check because it
    answers a separate question, and because the reason a reviewer needs is
    different: "not sendable" sends them looking for a bad address, where the
    truth is that the address is probably fine and one call is missing.

    Scoped to contacts that actually have an email step planned. A contact
    reached on LinkedIn only is not blocking anything by being unverified.
    """
    from . import verification

    policy = verification.policy_for(config)
    short = []
    for rec in _records_of(campaign, recs):
        timeline = cadence.build(rec, config, recs=recs, campaign=campaign)
        for contact in rec.get("contacts") or []:
            if not contact.get("email"):
                continue
            steps = (timeline.get("contacts") or {}).get(contact.get("key")) or {}
            # `skipped` and `not_planned` only: those are channel-level
            # exclusions - MX closed the email channel, or the cadence never
            # scheduled one - and the contact is genuinely not being emailed.
            #
            # `blocked` is deliberately *included*. A step short of its
            # confirmations is blocked precisely because of the shortfall, so
            # filtering blocked steps out would make this check pass for
            # exactly the contacts it exists to catch.
            planned = [s for s in steps.values()
                       if s.get("channel") == "email"
                       and s.get("status") not in ("skipped", "not_planned")]
            if not planned:
                continue
            decision = verification.resolve(contact, policy)
            if decision["confirmation_count"] < decision["required_confirmations"]:
                short.append(f"{rec['id']}:{contact.get('key')} "
                             f"({decision['confirmation_count']}/"
                             f"{decision['required_confirmations']})")
    return (not short,
            "every email recipient has the required independent verification "
            "confirmations" if not short
            else f"{len(short)} recipient(s) have an email step and too few "
                 "confirmations: " + ", ".join(short[:3]))


def check_no_unshippable_records(campaign, recs, config):
    bad = [f"{r['id']}({r.get('state')})" for r in _records_of(campaign, recs)
           if r.get("state") in lint.UNSHIPPABLE]
    return (not bad,
            "no dropped or already-pushed record is in the campaign" if not bad
            else f"{len(bad)} unshippable record(s): " + ", ".join(bad[:3]))


def check_no_paused_companies(campaign, recs, config):
    paused = [r["id"] for r in _records_of(campaign, recs) if cadence.pause_state(r)]
    return (not paused,
            "no company in the campaign is paused" if not paused
            else f"{len(paused)} company/companies are paused: "
                 + ", ".join(paused[:3]))


# ------------------------------------------------------------------- freeze
#
# A freeze is the stop button, and it is deliberately not a status. Statuses
# describe where a campaign is in its life; a freeze describes a decision a
# human made about it, and the two are independent - a running campaign and a
# campaign awaiting approval can both be frozen, and both must come back to
# exactly where they were.
#
# It does not touch the fingerprint either. Freezing an approved campaign and
# unfreezing it must leave the approval intact, because invalidating it would
# punish the person who hit stop by making them re-approve everything.

def is_frozen(campaign):
    return bool((campaign or {}).get("freeze"))


def freeze(campaign, why, by="unknown"):
    """Stop everything about this campaign, without losing where it was."""
    if not why:
        raise CampaignError("a freeze must say why")
    if is_frozen(campaign):
        return campaign["freeze"]
    campaign["freeze"] = {"at": store.now(), "by": by, "why": why,
                          "status_when_frozen": campaign.get("status")}
    log(campaign, "freeze", why, by=by)
    return campaign["freeze"]


def unfreeze(campaign, by="unknown", why=""):
    """Lift the freeze. The status was never changed, so nothing is restored."""
    if not is_frozen(campaign):
        return None
    lifted = campaign.pop("freeze")
    log(campaign, "unfreeze", why or "freeze lifted", by=by,
        frozen_at=lifted.get("at"))
    return lifted


def check_not_frozen(campaign, recs, config):
    frozen = campaign.get("freeze") or {}
    return (not frozen,
            "the campaign is not frozen" if not frozen
            else f"frozen by {frozen.get('by')} at {frozen.get('at')}: "
                 f"{frozen.get('why')}")


def check_senders(campaign, recs, config):
    from . import senders
    return senders.check_mapping(campaign)


def check_external_mapping(campaign, recs, config):
    """An external campaign id is required only for a channel that has work."""
    needed = channels_in_use(campaign, recs, config)
    missing = []
    if "email" in needed and not campaign.get("bison_campaign_id"):
        missing.append("bison_campaign_id")
    if "linkedin" in needed and not campaign.get("heyreach_campaign_id"):
        missing.append("heyreach_campaign_id")
    return (not missing,
            "every channel in use is mapped to an external campaign"
            if not missing else
            "no external campaign mapped for: " + ", ".join(missing))


def check_daily_volume(campaign, recs, config):
    volume = campaign.get("daily_volume") or {}
    bad = [f"{k}={v}" for k, v in volume.items()
           if not isinstance(v, int) or v < 0]
    if bad:
        return False, "daily volume is not a whole number: " + ", ".join(bad)
    if not any((volume.get(c) or 0) > 0 for c in channels_in_use(campaign, recs, config)):
        return False, "daily volume is zero for every channel in use"
    return True, f"daily volume: {json.dumps(volume, sort_keys=True)}"


def check_no_duplicate_pushes(campaign, recs, config):
    from . import push
    seen, dupes = set(), []
    paused_set = cadence.paused_domains(recs)
    for rec in _records_of(campaign, recs):
        timeline = cadence.build(rec, config, recs=recs, paused_set=paused_set,
                                 campaign=campaign)
        for contact_key, steps in (timeline.get("contacts") or {}).items():
            for step_key, step in steps.items():
                pid = push.push_id(rec, contact_key, step_key, step.get("channel"))
                if pid in seen:
                    dupes.append(pid)
                seen.add(pid)
                if push.already_pushed(rec, contact_key, step_key):
                    dupes.append(f"{pid} (already pushed)")
    return (not dupes,
            f"{len(seen)} push id(s), all distinct and none already sent"
            if not dupes else
            f"{len(dupes)} duplicate or already-sent push id(s): "
            + ", ".join(dupes[:3]))


def check_credentials(campaign, recs, config):
    """The keys the channels in use would need. Read, never called."""
    from .providers import key, ProviderError
    needed = {"email": ("BISON_KEY", "BISON_BASE"), "linkedin": ("HEYREACH_KEY",)}
    missing = []
    for channel in channels_in_use(campaign, recs, config):
        for var in needed.get(channel, ()):
            try:
                key(var)
            except ProviderError:
                missing.append(var)
    return (not missing,
            "credentials are configured for every channel in use" if not missing
            else "missing credentials: " + ", ".join(sorted(set(missing))))


def check_cost_estimate(campaign, recs, config):
    estimate = cost_estimate(campaign, recs, config)
    return (estimate is not None,
            f"cost estimate available: {json.dumps(estimate, sort_keys=True)}"
            if estimate is not None else "no cost estimate could be produced")


CHECKS = (
    ("records present", check_records_present),
    ("not frozen", check_not_frozen),
    ("not already launched", check_not_launched),
    ("campaign approved", check_campaign_approved),
    ("drafts approved", check_drafts_approved),
    ("lint clean", check_lint_clean),
    ("no duplicate copy", check_no_duplicate_copy),
    ("recipients sendable", check_recipients_sendable),
    ("double verification", check_double_verification),
    ("no dropped or pushed records", check_no_unshippable_records),
    ("no paused companies", check_no_paused_companies),
    ("sender mapping", check_senders),
    ("external campaign mapping", check_external_mapping),
    ("daily volume", check_daily_volume),
    ("no duplicate push ids", check_no_duplicate_pushes),
    ("provider credentials", check_credentials),
    ("cost estimate", check_cost_estimate),
)


def channels_in_use(campaign, recs=None, config=None):
    """Which channels this campaign actually has work on."""
    recs = store.load() if recs is None else recs
    if config is None:
        try:
            config = clients.load(campaign.get("client"))
        except Exception:
            config = {}
    found = set()
    paused_set = cadence.paused_domains(recs)
    for rec in _records_of(campaign, recs):
        timeline = cadence.build(rec, config, recs=recs, paused_set=paused_set,
                                 campaign=campaign)
        for steps in (timeline.get("contacts") or {}).values():
            for step in steps.values():
                if step.get("channel"):
                    found.add(step["channel"])
    return found


def cost_estimate(campaign, recs=None, config=None):
    """What running this campaign is expected to cost, in what it is billed in.

    Enrichment and verification are already spent by the time a campaign is
    approved, so what is estimated here is what a launch would still consume.
    Nothing here is invented: a figure this system cannot know is reported as
    unknown rather than guessed.
    """
    recs = store.load() if recs is None else recs
    if config is None:
        try:
            config = clients.load(campaign.get("client"))
        except Exception:
            config = {}
    email_steps = linkedin_steps = 0
    paused_set = cadence.paused_domains(recs)
    for rec in _records_of(campaign, recs):
        timeline = cadence.build(rec, config, recs=recs, paused_set=paused_set,
                                 campaign=campaign)
        for steps in (timeline.get("contacts") or {}).values():
            for step in steps.values():
                if step.get("channel") == "email":
                    email_steps += 1
                elif step.get("channel") == "linkedin":
                    linkedin_steps += 1
    return {
        "email_steps": email_steps,
        "linkedin_steps": linkedin_steps,
        "contactout_credits": 0,        # enrichment happened before approval
        "verification_credits": 0,      # likewise
        "apify_compute_units": "unknown",
        "llm_cost": "unknown",
    }


def validate(campaign_id, recs=None, config=None, campaign=None,
             ignore_status=False):
    """Every launch condition, each answered separately. Nothing is called.

    `ignore_status` is for resuming: a paused campaign is unlaunchable *because*
    it is paused, so checking that on the way out of a pause would make resume
    impossible. Everything else is still checked, which is the point - a pause
    is not lifted by forgetting it.
    """
    recs = store.load() if recs is None else recs
    campaign = campaign if campaign is not None else require(campaign_id)
    if config is None:
        try:
            config = clients.load(campaign.get("client"))
        except Exception as e:
            return {"campaign_id": campaign_id, "ok": False, "checks": [],
                    "blockers": [f"client config: {e}"]}

    results = []
    for label, fn in CHECKS:
        try:
            ok, detail = fn(campaign, recs, config)
        except Exception as e:                      # a broken check blocks launch
            ok, detail = False, f"{type(e).__name__}: {e}"
        results.append({"check": label, "ok": bool(ok), "detail": detail})

    blockers = [r["check"] for r in results if not r["ok"]]
    if not ignore_status and campaign.get("status") in UNLAUNCHABLE:
        blockers.append(f"status is {campaign.get('status')}")
        results.append({"check": "status", "ok": False,
                        "detail": f"a campaign in {campaign.get('status')} "
                                  "cannot launch"})
    return {"campaign_id": campaign_id, "ok": not blockers, "checks": results,
            "blockers": blockers,
            "fingerprint": fingerprint(campaign, recs, config)}


# ------------------------------------------------------------------ dry run

def _linkedin_account(campaign, assignment):
    """The LinkedIn account the assigned steps use, if they agree on one.

    HeyReach takes one account per lead pair; where the assignment spreads
    across several this returns None rather than picking one, because a wrong
    account sends from the wrong person.
    """
    used = {row.get("external_id") or row.get("account")
            for row in assignment.get("assigned") or []
            if row.get("channel") == "linkedin"}
    used = {u for u in used if u}
    return next(iter(used)) if len(used) == 1 else None


def dry_run(campaign_id, day=21, recs=None, config=None, campaign=None):
    """What a launch would do, with the payloads it would build. No network."""
    from . import push
    recs = store.load() if recs is None else recs
    campaign = campaign if campaign is not None else require(campaign_id)
    if config is None:
        try:
            config = clients.load(campaign.get("client"))
        except Exception:
            config = {}

    ids = set(campaign.get("record_ids") or [])
    mine = [r for r in recs if r["id"] in ids]
    ready, skipped = push.collect(mine, day=day,
                                  client=campaign.get("client"),
                                  campaign_rows=[campaign])

    from . import senders
    assignment = senders.assign_all(campaign, ready)
    payloads = push.payloads(
        ready,
        bison_campaign_id=campaign.get("bison_campaign_id"),
        heyreach_campaign_id=campaign.get("heyreach_campaign_id"),
        linkedin_account_id=_linkedin_account(campaign, assignment))
    held = sum(1 for r in mine if r.get("state") == "held")
    blocked = len(skipped)
    return {
        "campaign_id": campaign_id,
        "client": campaign.get("client"),
        "day": day,
        "records": len(mine),
        "contacts": sum(len(r.get("contacts") or []) for r in mine),
        "channels": sorted(channels_in_use(campaign, recs, config)),
        "senders": assignment["by_channel"],
        "external": {"bison": campaign.get("bison_campaign_id"),
                     "heyreach": campaign.get("heyreach_campaign_id")},
        "payload_count": payloads["emailbison"]["count"] + payloads["heyreach"]["count"],
        "payloads": payloads,
        "estimate": cost_estimate(campaign, recs, config),
        "held": held,
        "blocked": blocked,
        "skipped": skipped,
    }


# ---------------------------------------------------------------- the CLI

def _print_validation(result):
    print(f"campaign {result['campaign_id']}")
    print(f"  fingerprint {result.get('fingerprint')}\n")
    print("  launch checklist:")
    for row in result["checks"]:
        mark = "ok  " if row["ok"] else "BLOCK"
        print(f"    {mark} {row['check']:<32} {row['detail']}")
    print()
    if result["ok"]:
        print("  READY. Every launch condition passes.")
    else:
        print(f"  NOT READY. {len(result['blockers'])} blocker(s): "
              + ", ".join(result["blockers"]))
    print("\n  Nothing was sent. This build cannot send.")


def main(argv=None):
    p = argparse.ArgumentParser(prog="python -m src.campaigns")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list")
    for name in ("show", "validate"):
        s = sub.add_parser(name)
        s.add_argument("campaign_id")
    d = sub.add_parser("dry-run")
    d.add_argument("campaign_id")
    d.add_argument("--day", type=int, default=21)
    a = p.parse_args(argv)

    if a.cmd == "list":
        rows = load()
        if not rows:
            print("no campaigns")
            return 0
        for row in rows:
            print(f"  {row['campaign_id']:<24} {row.get('client', ''):<12} "
                  f"{row.get('status', ''):<18} {row.get('name', '')}")
        return 0

    try:
        campaign = require(a.campaign_id)
    except NotFound as e:
        print(f"REFUSED: {e}")
        return 2

    if a.cmd == "show":
        print(json.dumps(campaign, indent=2, ensure_ascii=False))
        return 0

    if a.cmd == "validate":
        result = validate(a.campaign_id, campaign=campaign)
        _print_validation(result)
        return 0 if result["ok"] else 1

    if a.cmd == "dry-run":
        result = dry_run(a.campaign_id, day=a.day, campaign=campaign)
        print(f"campaign {result['campaign_id']}  ({result['client']})")
        print(f"  records      {result['records']}")
        print(f"  contacts     {result['contacts']}")
        print(f"  channels     {', '.join(result['channels']) or 'none'}")
        print(f"  day          {result['day']}")
        print(f"  external     bison={result['external']['bison']} "
              f"heyreach={result['external']['heyreach']}")
        print(f"  payloads     {result['payload_count']}")
        print(f"  held         {result['held']}")
        print(f"  blocked      {result['blocked']}")
        print(f"  estimate     {json.dumps(result['estimate'], sort_keys=True)}")
        print("\n  senders:")
        for channel, used in sorted(result["senders"].items()):
            print(f"    {channel:<10} {', '.join(used) or 'none'}")
        print("\nDRY RUN. No network call was made and nothing was sent.")
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
