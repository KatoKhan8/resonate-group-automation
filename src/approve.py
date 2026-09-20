#!/usr/bin/env python3
"""Human approval. Nothing is push eligible until a person says so.

A draft can be generated, lint clean and scheduled and still not be sendable:
approval is a separate, explicit, recorded act. It is granted per step, not per
record, and it is bound to the exact words that were approved. Change a word
and the approval is gone, because what a human signed off no longer exists.

Refused outright:
  - a record that is dropped or already pushed
  - a record that is held, which means its address never cleared
  - a step that fails lint
  - a recipient who is not sendable

  python -m src.approve pending
  python -m src.approve step --id meridian --contact ivana-saric --step day1 --by zb
  python -m src.approve record --id meridian --by zb
  python -m src.approve revoke --id meridian --contact ivana-saric --step day1
"""
import argparse

from . import approval, cadence, clients, events, lint, store
from .approval import approval_of, fingerprint, is_approved, stored

# A record in one of these states has nothing approvable on any channel.
REFUSED_STATES = ("dropped", "pushed")

# `held` is deliberately not in that list. It is an *email* judgement -
# `enrich.outcome` sets it when no address cleared verification - and refusing
# every step on the record because of it silently takes LinkedIn away from a
# contact whose profile is perfectly usable. That is the failure `channels.py`
# exists to prevent, undone one module later.
#
# So a held record refuses its email steps and allows its LinkedIn ones, and
# each still has to pass every other gate on its own. `lint.UNSHIPPABLE` has
# always drawn the line in this place, which is why `eligibility.decide` never
# had the bug: only the approver did.
EMAIL_REFUSED_STATES = ("held",)


def _is_threaded_follow_up(step_key, config):
    """True when ``step_key`` is a threaded follow-up in the email sequence.

    TASK-219: a threaded follow-up's subject is NOT sendable content. The
    provider continues the original thread and prepends ``Re:`` itself. The
    approval fingerprint must therefore exclude the subject.

    Reads ``email_sequence.thread_reply_pattern`` and the step ordering from
    the config. Returns False when the question cannot be answered (no config,
    no sequence, single-step, or step is the opener).
    """
    if not config or not step_key:
        return False
    seq = (config.get("email_sequence") or {})
    steps_block = seq.get("steps") or {}
    if step_key not in steps_block:
        return False
    pattern = seq.get("thread_reply_pattern") or []
    if not pattern:
        return False
    email_keys = sorted(
        steps_block,
        key=lambda k: (steps_block[k] or {}).get("order", 0))
    try:
        idx = email_keys.index(step_key)
    except (ValueError, TypeError):
        return False
    if idx < 1 or idx >= len(pattern):
        return False
    return bool(pattern[idx])


class NotApprovable(RuntimeError):
    """This step cannot be approved, and the reason is on the exception."""


def why_not(rec, contact_key, step_key, step=None, config=None,
            campaign=None):
    """The reason this step cannot be approved, or None if it can."""
    if rec.get("state") in REFUSED_STATES:
        return f"record is {rec['state']}"
    if cadence.pause_state(rec):
        return "company is paused"
    contact = lint.find_contact(rec, contact_key)
    if contact is None:
        return "no such contact on this record"

    if step is None:
        config = config or clients.load(rec.get("client"))
        timeline = cadence.build(rec, config, campaign=campaign)
        step = (timeline["contacts"].get(contact_key) or {}).get(step_key)
    if not step:
        return "no such step"

    # Checked here rather than beside the record-level refusal above, because
    # it needs to know which channel the step is on and the step is only
    # resolved by this point.
    if (rec.get("state") in EMAIL_REFUSED_STATES
            and step.get("channel") == "email"):
        return f"record is {rec['state']}"

    if step.get("channel") == "email":
        if not lint.sendable(contact):
            return "recipient is not sendable"
        failures = lint.check(rec, contact_key, step)
        if failures:
            return "fails lint: " + ", ".join(failures)
    else:
        if not contact.get("linkedin"):
            return "no LinkedIn profile"
        if not (step.get("note") or "").strip():
            return "empty note"
    return None


def approve_step(rec, contact_key, step_key, by="unknown", config=None,
                 step=None, sync=True, campaign=None):
    """Approve one step. Raises NotApprovable rather than approving quietly.

    `sync=False` skips the record-state recomputation, for a caller approving
    many steps in a row that will sync once at the end. The recomputation
    rebuilds the whole cadence, so doing it per step turns one timeline build
    into one per step - and cadence is the most expensive thing in this
    codebase at batch size.
    """
    config = config or clients.load(rec.get("client"))
    if step is None:
        timeline = cadence.build(rec, config, campaign=campaign)
        step = (timeline["contacts"].get(contact_key) or {}).get(step_key)
    reason = why_not(rec, contact_key, step_key, step=step, config=config,
                     campaign=campaign)
    if reason:
        raise NotApprovable(f"{rec['id']}:{contact_key}:{step_key}: {reason}")

    # TASK-219: for a threaded follow-up, the subject is NOT sendable content.
    # The provider continues the original thread and prepends Re: itself.
    # The approval fingerprint must therefore exclude the subject: it covers
    # what reaches a prospect, and a follow-up's own subject does not.
    threaded = _is_threaded_follow_up(step_key, config)
    fp_step = dict(step) if threaded else step
    if threaded:
        fp_step["subject"] = ""
    stamp = {"by": by, "at": store.now(),
             "fingerprint": fingerprint(fp_step, skip_subject=threaded)}
    slot = rec.setdefault("cadence", {}).setdefault(contact_key, {}).setdefault(step_key, {})
    # A template step is expanded at read time, so record what was approved.
    #
    # WHAT WAS APPROVED, NOT WHAT WAS ALREADY THERE. This was `and field not
    # in slot`, which meant the slot kept whatever words it already held while
    # the stamp above was taken over `step` - the freshly expanded one. The
    # two then disagreed, and nothing downstream noticed: `_resolve_step_copy`
    # staged the slot's words under the stamp's authority. Measured
    # 2026-09-16, campaign `productive-email-control-v2`: thirty approvals
    # fingerprinting the CONTROL text sat on thirty slots still holding the
    # model-generated text they replaced, and all ten leads planned with
    # nothing reported missing.
    #
    # A field the expanded step does not carry is REMOVED rather than left,
    # for the same reason. `fingerprint` covers channel, subject, body and
    # note, so a stale `note` under an email approval - or a subject left
    # behind by a threaded follow-up that no longer has one - is a word the
    # stamp does not cover sitting in the slot the sender reads.
    for field in ("channel", "subject", "body", "note", "template"):
        if step.get(field) is not None:
            slot[field] = step[field]
        else:
            slot.pop(field, None)
    # TASK-219: for a threaded follow-up, blank the subject on the slot so
    # the sender reads "" (matching what the provider stores) and the flag
    # tells `is_approved` and `_certified_copy` to skip the subject in the
    # fingerprint.
    if threaded:
        slot["subject"] = ""
        slot["threaded_follow_up"] = True
    else:
        slot.pop("threaded_follow_up", None)
    slot["approval"] = stamp
    store.log(rec, "approved", f"{contact_key}:{step_key} by {by}",
              fingerprint=stamp["fingerprint"])
    events.record(rec, events.DRAFT_APPROVED, contact_key=contact_key,
                  channel=step.get("channel"), step=step_key, by=by)
    if sync:
        sync_state(rec, config, campaign)
    return stamp


def revoke(rec, contact_key, step_key, why="revoked"):
    slot = stored(rec, contact_key, step_key)
    if slot.get("approval"):
        slot.pop("approval")
        store.log(rec, "approval_revoked", f"{contact_key}:{step_key}: {why}")
    sync_state(rec)
    return slot


# ------------------------------------------------- the record-level state
#
# BUILD-SPEC section 3 documents the lifecycle as
# `drafted -> approved -> pushed`, and `approved` sat in `store.STATES`
# unwritten by anything for the whole build. Approval is per step, which is
# the right granularity, so the record-level state is *derived* from the steps
# rather than being a second thing a human sets: it means "every sendable step
# on this record currently carries a human's blessing".
#
# Derived, never latched. `is_approved` compares the approval's fingerprint to
# the step's current text, so editing an approved draft drops that step out of
# the set and this state falls back to `drafted` on the next sync - which is
# exactly the invalidation WEB-READINESS promises. A latched boolean would
# have to be remembered to un-latch; a recomputation cannot be forgotten.

DERIVED_FROM_STEPS = ("drafted", "approved")


def approvable_steps(rec, config=None, campaign=None):
    """Every step on this record a human could be asked to approve.

    A step that can never ship - blocked by lint, by eligibility or by a
    channel being closed - is not counted, because a record whose remaining
    steps are all unshippable would otherwise never reach `approved` however
    many times a human said yes.
    """
    config = config or clients.load(rec.get("client"))
    timeline = cadence.build(rec, config, campaign=campaign)
    out = []
    for contact_key, steps in timeline["contacts"].items():
        for step_key, step in steps.items():
            if why_not(rec, contact_key, step_key, step=step, config=config,
                       campaign=campaign):
                continue
            out.append((contact_key, step_key, step))
    return out


def fully_approved(rec, config=None, campaign=None):
    """True when there is something to approve and all of it is approved."""
    pending_steps = approvable_steps(rec, config, campaign)
    if not pending_steps:
        return False
    return all(approval.is_approved(rec, ck, sk, step, campaign=campaign)
               for ck, sk, step in pending_steps)


def sync_state(rec, config=None, campaign=None):
    """Move the record between `drafted` and `approved` to match its steps.

    Only ever moves between those two. A record that is dropped, held, pushed
    or still upstream of drafting has a state that means something this
    function has no business overwriting.
    """
    if rec.get("state") not in DERIVED_FROM_STEPS:
        return rec.get("state")
    rec["state"] = ("approved" if fully_approved(rec, config, campaign)
                    else "drafted")
    return rec["state"]


def approve_record(rec, by="unknown", config=None, step_keys=None,
                   campaign=None):
    """Approve everything on this record that is currently approvable."""
    config = config or clients.load(rec.get("client"))
    timeline = cadence.build(rec, config, campaign=campaign)
    done, refused = [], []
    for contact_key, steps in timeline["contacts"].items():
        for step_key, step in steps.items():
            if step_keys and step_key not in step_keys:
                continue
            try:
                # sync=False: the record state is recomputed once below,
                # rather than rebuilding the cadence for every step.
                approve_step(rec, contact_key, step_key, by=by, config=config,
                             step=step, sync=False, campaign=campaign)
                done.append(f"{contact_key}:{step_key}")
            except NotApprovable as e:
                refused.append({"step": f"{contact_key}:{step_key}", "why": str(e)})
    sync_state(rec, config, campaign)
    return {"approved": done, "refused": refused, "state": rec.get("state")}


def _opening(note, width=60):
    """The first line of a LinkedIn note, ending in an ellipsis if cut.

    A note has no subject. Showing its opening under a Subject column is
    right; showing it sliced mid-word with no mark that it was sliced is not.
    """
    text = " ".join(str(note or "").split())
    return text if len(text) <= width else text[:width - 1].rstrip() + "…"


def pending(recs, config_cache=None, campaign_rows=None):
    """Every step waiting on a human, and every step that cannot wait on one.

    `recs` is required. A default of `store.load()` silently returned every
    tenant's queue when a caller forgot to scope, and silence was
    indistinguishable from an empty tenant. A caller that wants the whole
    estate passes `store.load()` explicitly - the CLI handler does.
    """
    from . import campaigns
    config_cache = config_cache if config_cache is not None else {}
    # Which sequence each record is in. A record in no campaign, or in two
    # live ones, resolves to None and is judged against the default - the
    # same answer `push.collect` gives for the same question.
    of_record = campaigns.by_record(campaign_rows)
    waiting, blocked = [], []
    for rec in recs:
        client = rec.get("client")
        if client not in config_cache:
            try:
                config_cache[client] = clients.load(client)
            except clients.ConfigError:
                config_cache[client] = None
        config = config_cache[client]
        if config is None:
            continue
        timeline = cadence.build(rec, config,
                                 campaign=of_record.get(rec["id"]))
        # A key identifies; a name is what an approver reads. The screen was
        # showing `dach-software-009-jonas-nagy` beside a record column that
        # already said `dach-software-009`.
        names = {lint.contact_key(c): c.get("name")
                 for c in (rec.get("contacts") or [])}
        for contact_key, steps in timeline["contacts"].items():
            for step_key, step in steps.items():
                if approval.is_approved(rec, contact_key, step_key, step,
                                        campaign=of_record.get(rec["id"])):
                    continue
                entry = {"id": rec["id"], "contact": contact_key,
                         "name": names.get(contact_key) or contact_key,
                         "step": step_key,
                         "channel": step["channel"], "day": step["day"],
                         "subject": step.get("subject")
                                    or _opening(step.get("note"))}
                reason = why_not(rec, contact_key, step_key, step=step, config=config)
                if reason:
                    blocked.append({**entry, "why": reason})
                else:
                    waiting.append(entry)
    return {"waiting": waiting, "blocked": blocked}


def main(argv=None):
    p = argparse.ArgumentParser(prog="python -m src.approve")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("pending")

    ps = sub.add_parser("step")
    ps.add_argument("--id", required=True)
    ps.add_argument("--contact", required=True)
    ps.add_argument("--step", required=True)
    ps.add_argument("--by", required=True)

    pr = sub.add_parser("record")
    pr.add_argument("--id", required=True)
    pr.add_argument("--by", required=True)

    pv = sub.add_parser("revoke")
    pv.add_argument("--id", required=True)
    pv.add_argument("--contact", required=True)
    pv.add_argument("--step", required=True)

    a = p.parse_args(argv)

    if a.cmd == "pending":
        result = pending(store.load())
        print(f"{len(result['waiting'])} step(s) waiting for approval")
        for entry in result["waiting"]:
            print(f"  {entry['id']}:{entry['contact']}:{entry['step']:<6} "
                  f"day {entry['day']:>2}  {entry['channel']:<9} {entry['subject'][:48]}")
        print(f"\n{len(result['blocked'])} step(s) cannot be approved")
        for entry in result["blocked"]:
            print(f"  {entry['id']}:{entry['contact']}:{entry['step']:<6} {entry['why']}")
        return 0

    with store.transaction() as recs:
        rec = store.get(a.id, recs)
        if rec is None:
            raise SystemExit(f"no record {a.id}")
        if a.cmd == "step":
            try:
                stamp = approve_step(rec, a.contact, a.step, by=a.by)
            except NotApprovable as e:
                raise SystemExit(f"REFUSED: {e}")
            print(f"approved {a.id}:{a.contact}:{a.step} by {a.by} "
                  f"({stamp['fingerprint']})")
        elif a.cmd == "record":
            result = approve_record(rec, by=a.by)
            print(f"approved {len(result['approved'])} step(s) on {a.id}")
            for refusal in result["refused"]:
                print(f"  refused {refusal['step']}: {refusal['why']}")
        else:
            revoke(rec, a.contact, a.step, why="revoked from the CLI")
            print(f"revoked {a.id}:{a.contact}:{a.step}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
