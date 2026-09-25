#!/usr/bin/env python3
"""Build a real EmailBison campaign from canonical state, and prove it.

The campaign row in `work/campaigns.jsonl` is the specification. There is no
second one: `campaigns.material()` already assembles every field an approval
decision covers, `campaigns.fingerprint()` already digests it, and
`providerwrites.staged_already()` already remembers what reached the provider.
This module orchestrates those; it invents no new state.

WHAT MAKES IT IDEMPOTENT. `bison_campaign_id` on the campaign row is the
anchor. It is written the instant the provider answers, inside the same
transaction that reads it. A crash between the POST and the persist leaves a
real campaign that no local state names, and this paragraph used to say that
case "is reported as ambiguous rather than retried" - it was not. Nothing
looked, and the next run built a second campaign: measured on 2026-09-13, two
campaigns with byte-identical names. The name is now DERIVED from the campaign
row (`provider_campaign_name`) and looked up before anything is created, so an
orphan is recovered and bound; two orphans are the ambiguity that paragraph
claimed, and they are refused.

THE OTHER THING THAT MAKES IT IDEMPOTENT IS THE ORDER. The campaign is
stopped BEFORE its leads are attached, because a lead in a campaign that has
not been stopped reads `in_sequence` and a lead that is `in_sequence`
anywhere cannot be attached anywhere else. See `stage`.

WHAT IT WILL NOT DO. It never resumes a campaign. Activation is what makes a
staged sequence start emailing real people, `bison.activate` is not in
`providerwrites.SUPPORTED`, and a factory that could start sending would make
every gate above it advisory. The campaign it leaves behind is populated,
sequenced and stopped.
"""
import argparse
import sys

from . import campaigns, clients, providerwrites, store
from .providers import ProviderError, bison
# THE CONSTANT, NOT THE TRANSPORT. Tests swap `bison` for a fake provider,
# and this number is not something a provider answers - it is how many pairs
# of copy variables this engine declares. Reading it off the swapped module
# made a fake without the attribute crash a check that has nothing to do
# with the wire.
from .providers.bison import MAX_SEQUENCE_STEPS


class FactoryRefused(Exception):
    """The campaign must not be staged, and the reason is not the provider's."""


class FactoryAmbiguous(Exception):
    """The provider may have acted. Read provider truth; do NOT retry."""


def stage(campaign_id, *, recs=None, config=None, live=False, by="system"):
    """Bring one campaign into existence at EmailBison, or confirm it is there.

    Returns a report: what was already true, what was done, and what the
    provider said afterwards. Dry run by default - `live=True` is explicit,
    because everything below this line writes to a real estate.
    """
    rows = campaigns.load()
    campaign = campaigns.require(str(campaign_id), rows)
    client = campaign.get("client")
    if not client:
        raise FactoryRefused(
            f"campaign {campaign_id} names no client; every provider write is "
            f"tenant-bound and an untenanted one cannot be attributed")
    if config is None:
        config = clients.load(client)
    recs = store.load() if recs is None else recs

    plan = _plan(campaign, recs, config)
    report = {"campaign": str(campaign_id), "client": client, "live": bool(live),
              "workspace": None, "plan": plan, "did": [], "provider": {}}
    if not live:
        report["did"].append("dry run: nothing was sent")
        return report

    # TENANCY, AGAINST THE PROVIDER, BEFORE ANYTHING IS WRITTEN.
    #
    # `workspace_id` is accepted and discarded by every list route on this
    # API, and the answer for a workspace that does not exist is identical to
    # the answer for the one that does - so a caller can believe it scoped a
    # read and be holding another client's estate. `GET /users` is the only
    # route that states which workspace the credential is actually bound to.
    workspace = bison.bound_workspace()
    report["workspace"] = workspace
    expected = ((config.get("providers") or {}).get("emailbison") or {}).get(
        "workspace")
    if expected is not None and str(workspace.get("id")) != str(expected):
        raise FactoryRefused(
            f"this credential is bound to EmailBison workspace "
            f"{workspace.get('id')} ({workspace.get('name')!r}) and {client!r} "
            f"is configured for workspace {expected}. Refusing to build one "
            f"client's campaign inside another client's estate")

    provider_id, provider_name = _find_or_create(campaign, report, by=by)
    report["provider"]["campaign_id"] = provider_id
    report["provider"]["name"] = provider_name

    _ensure_limits(provider_id, campaign, provider_name, report)
    _ensure_schedule(provider_id, plan, report)
    _ensure_senders(provider_id, campaign, report)
    _ensure_sequence(provider_id, campaign, plan, report, by=by)
    # STOPPED BEFORE IT HOLDS ANYBODY, for the reason `_ensure_limits` is
    # applied before the leads and for one more that is not about this
    # campaign at all. A lead attached to a campaign that has not been stopped
    # reads `in_sequence` AT ONCE - draft is enough - and a lead that is
    # `in_sequence` anywhere cannot be attached to any other campaign; the
    # provider refuses the whole batch with one unattributed 422. So the old
    # order left every lead of this campaign unattachable elsewhere for the
    # length of a staging run, and two campaigns staged at the same time
    # raced: measured 2026-09-13, the second one failed outright.
    _ensure_stopped(provider_id, report, by=by)
    _ensure_leads(provider_id, campaign, plan, report, by=by)

    report["provider"]["readback"] = _readback(provider_id)
    report["review"] = _review_file(provider_id, campaign, config, report)
    return report


def _review_file(provider_id, campaign, config, report):
    """The operator's review file, built AFTER attach, FROM the provider.

    THE STANDING DIRECTIVE, 2026-09-25: every push produces
    `work/review/<campaign>-<date>.xlsx` and a rendered `.html`, one row per
    lead, with the sender mailbox, the sender's NAME, and the subject and
    full body of every step exactly as the provider will send it.

    It runs here - last, after `_ensure_leads` - because the whole point is
    to read back what the provider now holds. A review file assembled from
    `plan` would be this module checking its own arithmetic, and the push
    that made this necessary never built a plan at all: it POSTed string
    literals straight at `bison.create_lead`.

    NEVER RAISES OUT OF `stage`. A staging run that succeeded and then
    failed to write a spreadsheet has still staged; reporting the failure
    in the report is honest and aborting on it would make a reporting bug
    look like a provider one. The report carries the paths or the reason,
    and an operator reading `"error"` here knows there is no file to
    approve from - which is a refusal to activate, not a refusal to stage.
    """
    from . import reviewfile

    try:
        snapshot = {
            "provider_campaign_id": str(provider_id),
            "campaign": bison.campaign(provider_id),
            "senders": bison.campaign_senders(provider_id),
            "sender_pool": bison.campaign_sender_emails(provider_id),
            "sequence": bison.sequence_steps(provider_id),
            "leads": bison.campaign_leads(provider_id),
            "queue": bison.scheduled_emails(provider_id, cap=200),
        }
        rows = reviewfile.rows(snapshot, config=config,
                               client=campaign.get("client"))
        return reviewfile.write(str(campaign.get("campaign_id") or provider_id),
                                rows)
    except Exception as e:
        return {"error": "%s: %s" % (type(e).__name__, e)}


def provider_campaign_name(campaign):
    """The name this campaign row has at EmailBison. Derived, never chosen.

    THE ONLY HANDLE ON A CAMPAIGN NOBODY WROTE DOWN. `bison_campaign_id` is
    the anchor and it is written the instant the provider answers - but if the
    process dies in between, the provider holds a campaign that no local state
    names and the next run builds another. Measured 2026-09-13: two campaigns,
    byte-identical names, one of them orphaned.

    So the name carries the canonical identity, and `_find_or_create` looks it
    up before it creates anything. `client` is in it because `campaign_id` is
    unique per client and this workspace holds more than one tenant's work,
    and the operator's own name stays at the front because this string is what
    a person sees in EmailBison's UI.

    WHAT IS DELIBERATELY NOT IN IT: `campaigns.fingerprint`. That digest moves
    whenever a draft, a sender, a volume or a client setting changes, which is
    exactly right for "is this still what was approved" and exactly wrong for
    "which provider campaign is this". A name carrying it would stop matching
    the moment copy was regenerated, and the next re-stage would build a
    second campaign for the same row - the defect this function exists to
    close, reintroduced. Identity is stable; material is not; they are
    different questions and the fingerprint answers the other one.
    """
    human = str(campaign.get("name") or "").strip() or "resonate"
    return f"{human} [{campaign.get('client')}/{campaign.get('campaign_id')}]"


# WHAT `wait_in_days` MEANS, MEASURED RATHER THAN ASSUMED.
#
# It is the wait AFTER the step that carries it, before the next one - not a
# wait before it. Read off the client's own live campaign 352 on 2026-09-13:
# 381 consecutive scheduled-email pairs whose two steps declare DIFFERENT
# waits, which are the only pairs that can tell the two readings apart.
#
#     earlier wait 3, later wait 1  ->  delta 3 in 59 of 87 pairs
#     earlier wait 3, later wait 4  ->  delta 3 in 115 of 168
#     earlier wait 4, later wait 3  ->  delta 4 in 77 of 126
#
# The mode is the EARLIER step's wait in all three groups. The one-to-two day
# spread around it is the sending window and the weekend, which is why the
# mode is the evidence and an exact match is not: pairs whose two steps
# declare the SAME wait cannot discriminate at all and are excluded.
#
# So a five-step cadence declares four meaningful waits and one that has no
# successor to be a wait before. See `_sequence_steps`.


def _sequence_steps(configured, cadence_steps):
    """The provider sequence this campaign writes, declared and checked.

    TWO SHAPES, AND THE OLD ONE IS NOT DEPRECATED. A client naming `subject`,
    `body` and `wait_in_days` directly gets the single step it always got -
    that is what EmailBison campaign 451 carries and it is production
    evidence. A client naming a `steps` block gets one provider step per
    entry, keyed BY CADENCE STEP KEY.

    THE KEY IS THE WHOLE POINT. `em1: {...}` does not mean "the first step",
    it means "the step `cadencelibrary` calls em1", and that is what lets the
    declared delays be checked against the cadence instead of trusted. A
    `steps` block naming keys the cadence does not have, or missing keys it
    does, is refused: the alternative is a provider sending five emails on a
    schedule the cadence never described, with every readback agreeing.

    THE DELAYS ARE DECLARED AND VERIFIED, NOT DERIVED. `CAMPAIGN-FACTORY.md`
    is explicit that a provider node delay is declared, because the cadence
    day is a position in a schedule and a node delay is a property of the
    provider graph - two different quantities that happen to agree. Deriving
    one from the other would hide the day they stop agreeing. So the config
    states the number and this refuses if it does not reproduce the cadence.

    THE LAST STEP'S WAIT IS NOT CHECKED, because there is nothing after it to
    wait for. A five-step cadence defines four gaps. That wait is carried to
    the provider as declared and means nothing; saying so here is better than
    a check that invents a fifth gap to validate against.

    THREAD-REPLY: each step carries `thread_reply` from the ladder's pattern,
    or from the client config's `email_sequence.thread_reply_pattern` override.
    A follow-up step STILL CARRIES `email_subject` - the flag is the mechanism,
    not subject omission. The pattern is configurable per client or campaign
    because TASK-080 is measuring whether the shape is right.
    """
    configured = configured or {}
    block = configured.get("steps")
    if not isinstance(block, dict) or not block:
        if not (configured.get("subject") and configured.get("body")):
            return []
        return [{"order": 1,
                 "email_subject": configured["subject"],
                 "email_body": configured["body"],
                 "wait_in_days": configured.get("wait_in_days") or 3}]

    # The cadence's email steps, in the order the cadence runs them. `day` is
    # the position; equal days are legal (day 1 carries both channels) and the
    # key breaks the tie so the order is total rather than merely sorted.
    email_days = [(s.get("day"), s.get("key")) for s in cadence_steps or ()
                  if s.get("channel") == "email" and s.get("key")]
    email_days.sort(key=lambda pair: (pair[0], pair[1]))
    if not email_days:
        raise FactoryRefused(
            "`email_sequence.steps` names a multi-step sequence and the "
            "client's cadence carries no email steps at all, so there is "
            "nothing to check the declared delays against. A sequence nobody "
            "can check is a sequence nobody knows the shape of")

    if len(email_days) > MAX_SEQUENCE_STEPS:
        raise FactoryRefused(
            f"the cadence carries {len(email_days)} email steps and only "
            f"{MAX_SEQUENCE_STEPS} pairs of copy variables are declared "
            f"at the provider, so steps past the "
            f"{MAX_SEQUENCE_STEPS}th would send with nothing in them. "
            f"Raise `MAX_SEQUENCE_STEPS` and re-run "
            f"`ensure_custom_variables` before lengthening the cadence")

    wanted = [key for _day, key in email_days]
    declared = sorted(block, key=lambda k: _order_of(block[k], k))
    if declared != wanted:
        raise FactoryRefused(
            f"`email_sequence.steps` declares {declared} and the cadence's "
            f"email steps are {wanted}. These must be the same keys in the "
            f"same order: the key is how a declared delay is matched to the "
            f"cadence gap it claims to reproduce, so a mismatch means the "
            f"delays were checked against the wrong steps or against none")

    # THREAD-REPLY PATTERN: the client config may override the ladder's
    # default. The override is a list of booleans, one per email step in
    # cadence order. When absent, the ladder's pattern is used; when the
    # ladder has none, every step is a new thread (False).
    thread_pattern = _resolve_thread_pattern(configured, cadence_steps)

    steps = []
    for position, (day, key) in enumerate(email_days, start=1):
        entry = block[key] or {}
        subject, body = entry.get("subject"), entry.get("body")
        if not subject or not body:
            raise FactoryRefused(
                f"`email_sequence.steps.{key}` declares no "
                f"{'subject' if not subject else 'body'}. A step staged "
                f"without one sends an email that has none")
        wait = entry.get("wait_in_days")
        if wait is None:
            raise FactoryRefused(
                f"`email_sequence.steps.{key}` declares no `wait_in_days`. "
                f"EmailBison takes whatever it defaults to, and 'nobody "
                f"chose' must not look the same as a chosen delay")
        # Every gap but the last, against the cadence that defines it.
        if position < len(email_days):
            gap = email_days[position][0] - day
            if int(wait) != int(gap):
                raise FactoryRefused(
                    f"`email_sequence.steps.{key}` declares a "
                    f"{int(wait)}-day wait and the cadence puts {key} on day "
                    f"{day} and {email_days[position][1]} on day "
                    f"{email_days[position][0]}, a gap of {gap}. `wait_in_days` "
                    f"is the wait AFTER a step - measured on campaign 352, see "
                    f"the note above - so this campaign would send on a "
                    f"schedule the cadence does not describe")
        step = {"order": position,
                "email_subject": subject,
                "email_body": body,
                "wait_in_days": int(wait),
                "step_key": key}
        # A follow-up step STILL CARRIES email_subject - the flag is the
        # mechanism, not subject omission. The provider stores both.
        tr = thread_pattern[position - 1] if position <= len(thread_pattern) \
            else False
        step["thread_reply"] = bool(tr)
        steps.append(step)
    # THREAD-REPLY INVARIANT: only the opener owns a subject. When the
    # sequence has at least one threaded follow-up, every follow-up must
    # either be threaded or reference the opener's subject. A mixed shape
    # - some follow-ups threaded, others opening new threads with their own
    # subjects - violates the invariant and is refused.
    if len(steps) > 1:
        has_any_threading = any(s.get("thread_reply") for s in steps[1:])
        if has_any_threading:
            opener_subject = steps[0].get("email_subject", "")
            for step in steps[1:]:
                if (not step.get("thread_reply")
                        and step.get("email_subject") != opener_subject):
                    raise FactoryRefused(
                        f"step {step.get('order')} is not a thread reply but "
                        f"carries a distinct subject "
                        f"({step.get('email_subject')!r} vs opener "
                        f"{opener_subject!r}). Only the opener owns a "
                        f"subject; follow-ups must be thread replies "
                        f"referencing the opener's subject. Set thread_reply "
                        f"to true or change the subject to match the opener")
    return steps


def _resolve_thread_pattern(configured, cadence_steps):
    """The thread_reply pattern for this campaign's email steps.

    The client config's `email_sequence.thread_reply_pattern` wins when
    present: it is the per-client override TASK-080 needs. When absent, the
    ladder's default pattern is used. When the ladder has none, every step
    is a new thread (all False).

    Returns a tuple of bools, one per email step in cadence order.
    """
    from . import cadencelibrary

    override = (configured or {}).get("thread_reply_pattern")
    if isinstance(override, (list, tuple)) and override:
        return tuple(bool(v) for v in override)
    ladder_name = cadencelibrary.ladder_name_for(cadence_steps, "email")
    if ladder_name:
        pattern = cadencelibrary.THREAD_REPLY_PATTERNS.get(ladder_name)
        if pattern:
            return tuple(pattern)
    email_count = sum(1 for s in (cadence_steps or ())
                      if isinstance(s, dict) and s.get("channel") == "email"
                      and s.get("key"))
    return tuple(False for _ in range(email_count))


def _order_of(entry, key):
    """A declared step's position, for reporting a mismatch readably.

    Only used to sort the declared keys into a stable order before comparing
    them with the cadence's. A step that declares no `order` sorts by its key,
    which keeps the refusal message deterministic rather than dependent on
    dict insertion.
    """
    order = (entry or {}).get("order")
    try:
        return (0, int(order), key)
    except (TypeError, ValueError):
        return (1, 0, key)


def _plan(campaign, recs, config):
    """What this campaign is, from canonical state. No provider call."""
    material = campaigns.material(campaign, recs=recs, config=config)
    # WHICH contacts comes from the approval material, because that is what
    # was blessed. Their NAMES come from the record: `_contact_material`
    # deliberately carries only what launching cares about - who, where, may
    # we send - and a name is none of those. Reading names out of it silently
    # produced empty ones, which the provider then rejected.
    by_id = {r.get("id"): r for r in recs}
    # THE SEQUENCE IS BUILT BEFORE THE LEADS, because it decides how many
    # approved steps each lead has to carry. A lead is words plus an address;
    # which words depends on how many the sequence will ask for.
    from . import cadence as _cadence
    cadence_steps = _cadence.steps_for(campaign, config=config)
    sequence = _sequence_steps((config or {}).get("email_sequence"),
                               cadence_steps)
    leads = []
    for record in material.get("records") or []:
        if record.get("missing") or record.get("dropped") or record.get("paused"):
            continue
        source = by_id.get(record.get("id")) or {}
        names = {c.get("key"): c for c in (source.get("contacts") or [])}
        for contact in record.get("contacts") or []:
            if not contact.get("email") or not contact.get("sendable"):
                continue
            person = names.get(contact.get("key")) or {}
            # `name` is what this estate actually stores - the split fields
            # are empty on every Productive contact - so the first token is
            # taken from it, which is the convention `push.build_rows` has
            # used since it was written. Following it rather than inventing a
            # second one: two places splitting names differently is how the
            # same person gets greeted two ways.
            #
            # Deriving a given name from a full name is not reliable for
            # every name in the world. It is reading what is on the record
            # rather than inventing anything, which is the line that matters,
            # and a contact with no name at all is still refused below.
            first = (person.get("first_name") or "").strip()
            if not first:
                first = ((person.get("name") or "").split() or [""])[0].strip()
            if not first:
                raise FactoryRefused(
                    f"contact {contact.get('key')!r} on record "
                    f"{record.get('id')!r} has no name at all, and EmailBison "
                    f"requires a first name. Refusing to invent one that will "
                    f"greet a real person")
            # THE WORDS, CARRIED WITH THE PERSON.
            #
            # The sequence written to the provider is a template of merge
            # fields - `{SUBJECT}` and `{BODY}` - so the copy itself travels
            # per lead in custom variables. Without this the template renders
            # against nothing: the campaign would be staged, the readback
            # would look right, and the email would go out empty.
            #
            # Only an APPROVED step's words are carried. An unapproved draft
            # is not copy anybody has blessed, and the approval fingerprint
            # is what `executionguard` checks a payload against, so shipping
            # words that carry no approval would put the gate and the wire
            # out of step.
            copy, missing = _approved_copy(source, contact.get("key"),
                                           sequence, record.get("id"),
                                           cadence_steps=cadence_steps,
                                           campaign=campaign,
                                           config=config)
            leads.append({"record_id": record.get("id"),
                          "contact_key": contact.get("key"),
                          "email": contact.get("email"),
                          "first_name": first,
                          "copy": copy,
                          "missing_copy": missing,
                          "unsupported_copy": _unsupported_copy(
                              source, person, copy),
                          "step_key": copy[0]["step_key"] if copy else None,
                          "subject": copy[0]["subject"] if copy else "",
                          "body": copy[0]["body"] if copy else "",
                          "last_name": (
                              (person.get("last_name") or "").strip()
                              or " ".join(
                                  (person.get("name") or "").split()[1:]))})
    return {"fingerprint": campaigns.fingerprint(campaign, recs=recs,
                                                 config=config),
            "name": provider_campaign_name(campaign),
            "leads": leads,
            # THE CAMPAIGN'S OWN WINDOW WINS. EmailBison schedules ONE window
            # per campaign, so the window is a property of the cohort rather
            # than of the client: a Toronto prospect in a campaign on the
            # client's Europe/Zagreb hours would be written to at 03:00 local.
            #
            # Which is why geography belongs in campaign grouping wherever
            # provider scheduling is campaign-level - mixing timezones into
            # one campaign guarantees somebody is mailed in the middle of
            # their night. The client setting stays as the default for a
            # cohort that does not state one.
            "window": (campaign.get("sending_window")
                       or (config or {}).get("sending_window") or {}),
            "sequence": sequence,
            "sequence_config": (config or {}).get("email_sequence") or {},
            "bison_campaign_id": campaign.get("bison_campaign_id")}


def _refuse_unsupported(plan):
    """Refuse the whole stage if any lead's approved copy asserts something
    the record does not support.

    A separate function from `_ensure_leads` so it can be exercised without a
    provider, an estate or a campaign row - the refusal is the part that has
    to be right, and a guard only reachable through four other guards is a
    guard nobody tests.

    IT STOPS THE WHOLE STAGE rather than skipping the lead. `bisonfactory`
    already takes that position for missing copy and for the same reason: a
    campaign meant for nine that quietly stages eight is a campaign whose
    reach nobody stated, and `resume_campaign`'s `expect_leads` count is
    built on the caller knowing that number.
    """
    wanted = plan.get("leads") or []
    untrue = [(lead["record_id"], lead["contact_key"], lead["unsupported_copy"])
              for lead in wanted if lead.get("unsupported_copy")]
    if not untrue:
        return
    detail = "; ".join(f"{rid}/{key} {steps[0][0]}: {steps[0][1]}"
                       for rid, key, steps in untrue[:4])
    raise FactoryRefused(
        f"{len(untrue)} of {len(wanted)} contact(s) carry approved copy that "
        f"asserts something the record does not support: {detail}"
        f"{' and more' if len(untrue) > 4 else ''}. An approval proves a human "
        f"blessed these words, not that they are true of this person, and "
        f"after staging the provider sends on its own - there is no later "
        f"gate. REGENERATE the affected steps; do not edit them and do not "
        f"widen the claim rules to let them through")


def _refuse_bad_greetings(plan):
    """TASK-082. Refuse if any lead's body text has a broken greeting.

    THE DEFECT THIS PREVENTS. EmailBison does NOT have a {first_name} merge
    variable. The greeting is part of the generated body text that travels
    as {BODY_N}. If the generator produces "Hey ," or "Hi undefined," that
    goes straight to the provider and out the door. There is no provider-side
    substitution to save it.

    THREE CLASSES OF DEFECT:
    1. Empty greeting: "Hey ," "Hi ," "Hello ," - name is missing
    2. Literal placeholder: "Hi undefined," "Hi null," "Hi None,"
    3. Planted cohort name: one contact's body contains another contact's
       first name (the hi-jacob defect class for email)

    CALLED BY _ensure_leads, which is called by stage(). Deleting the call
    makes the test fail - that is the wiring proof.
    """
    import re as _re

    wanted = plan.get("leads") or []
    if not wanted:
        return

    # Collect cohort first names for planted-name detection.
    cohort_names = set()
    for lead in wanted:
        first = (lead.get("first_name") or "").strip()
        if first and len(first) > 1:
            cohort_names.add(first)

    problems = []
    for lead in wanted:
        contact_key = lead.get("contact_key", "?")
        record_id = lead.get("record_id", "?")
        own_first = (lead.get("first_name") or "").strip()
        copy = lead.get("copy") or []

        for entry in copy:
            body = entry.get("body") or ""
            step_key = entry.get("step_key", "?")
            if not body:
                continue
            first_line = body.split("\n")[0] if body else ""

            # Check 1: empty greeting.
            if _re.match(r'^(Hey|Hi|Hello)\s*,', first_line):
                problems.append(
                    f"{record_id}/{contact_key} step {step_key}: "
                    f"empty greeting - {first_line[:50]!r}")

            # Check 2: literal placeholder.
            for bad in ("undefined", "null", "None"):
                if bad in first_line:
                    problems.append(
                        f"{record_id}/{contact_key} step {step_key}: "
                        f"greeting contains literal {bad!r} - "
                        f"{first_line[:50]!r}")

            # Check 3: planted cohort name, IN A SALUTATION POSITION.
            #
            # ISSUE-015. This used to flag any occurrence of another cohort
            # member's first name anywhere in the body, and that is not the
            # defect it names. Measured 2026-09-22 across the five campaigns
            # carrying batch 3: 275 flags, every one a false positive.
            #
            #   269 of them on the single name 'Will', which is a first name
            #     AND an ordinary English auxiliary verb - so one cohort
            #     member named Will made every body containing the word
            #     "will" a defect
            #   the rest were company names carrying a person's name:
            #     russellherder.com, terrisandy.com, bigstarbranding.com,
            #     wearerichlifestyle.com, sobepromos.com
            #
            # The hi-jacob defect is a MIS-PERSONALISED GREETING - a letter to
            # Michael that opens by addressing Jacob. Checks 1 and 2 above
            # already read only the greeting line, for exactly that reason.
            # So this looks where a greeting puts a name and nowhere else:
            # after a salutation word, or opening a line as a bare vocative,
            # which is the form the approved Productive copy actually uses
            # ("Janie, I work with ...").
            #
            # NARROWED TO THE DEFECT, NOT WIDENED PAST IT. A planted name in a
            # salutation still fails, on any step and anywhere in the body -
            # the suite asserts that on a second-step follow-up. What no
            # longer fails is the word "will" inside a sentence.
            for name in cohort_names:
                if name == own_first:
                    continue
                planted = (r'^\s*(?:(?:Hi|Hey|Hello|Dear)\s+)?'
                           + _re.escape(name) + r'\s*[,.!:]')
                if _re.search(planted, body,
                              _re.IGNORECASE | _re.MULTILINE):
                    problems.append(
                        f"{record_id}/{contact_key} step {step_key}: "
                        f"body greets cohort name {name!r} "
                        f"(hi-jacob defect class)")

    if problems:
        detail = "; ".join(problems[:4])
        raise FactoryRefused(
            f"{len(problems)} greeting/copy defect(s) detected: {detail}"
            f"{' and more' if len(problems) > 4 else ''}. "
            f"EmailBison has no provider-side variable for first name - "
            f"the greeting is baked into the body text and travels as "
            f"{{BODY_N}}. A broken greeting reaches the prospect as-is. "
            f"REGENERATE the affected steps")


def _unsupported_copy(rec, contact, copy):
    """Every approved step whose words assert something the record cannot
    support. Returns `(step_key, why)` pairs.

    AN APPROVAL IS NOT A FACT-CHECK. `_approved_copy` proves a human blessed
    these exact words - the fingerprint is per step key and the gate checks
    the payload against it - and that is a different question from whether
    the words are true of this person. This module checked the first and
    never the second, so the only thing standing between a stored draft and
    a real person was whoever clicked approve.

    It matters because `_ensure_leads` writes the words into per-lead
    variables and the campaign then sends on its own. `executionguard` runs
    `claims.check` before a SEND, but it never sees these: staging is not a
    send, and after staging the provider does the sending. So for email there
    is no later gate at all - this is the last one.

    Measured 2026-09-14: the 9 live leads on campaign 481 are CLEAN, checked
    against the words actually held at the provider rather than the local
    store. They are clean because they were regenerated after `claims.check`
    was added to `generate.draft`, not because anything here checked. 17
    stored email steps elsewhere in the estate still assert something
    unsupported, and the only reason they cannot be staged is a collision
    gate that is answering a different question.
    """
    from . import claims

    found = []
    for entry in copy or []:
        text = f"{entry.get('subject') or ''} {entry.get('body') or ''}"
        for problem in claims.check(text, rec, contact) or []:
            found.append((entry.get("step_key"),
                          problem.get("why") or "unsupported"))
            break
    return found


def _approved_copy(source, contact_key, sequence, record_id, *,
                   cadence_steps=None, campaign=None, config=None):
    """The APPROVED words this contact carries, one entry per sequence step.

    Returns `(copy, missing)`. It REPORTS rather than refuses, and
    `_ensure_leads` is what refuses: this runs inside `_plan`, which is what
    a dry run returns and which happens before the workspace check, so
    raising here would mask a tenancy refusal with a copy complaint and would
    leave an operator no way to ask "what is missing" without being stopped
    at the first answer.

    WHY ANYTHING REFUSES AT ALL. The sequence written to the provider is a
    template of merge fields, so every step's words travel with the lead. A
    step whose variable is absent renders as nothing: the campaign is staged,
    the sequence reads back correctly, the sender is bound, the membership is
    right, and on day eight a real person receives an email with no subject
    and no body. `_variables_for` already said this about the single-step
    case; it was said and not enforced, and the code staged the lead with
    `""` for both. Five steps make it five times as likely and no more
    visible.

    MATCHED BY STEP KEY, NOT BY POSITION. `_sequence_steps` keys each provider
    step to the cadence step it came from, and the record's approvals are
    stored under those same keys - `approval.fingerprint` is per step key and
    `push_id` is `record:contact:step:channel`. Matching by position instead
    would put a day-twelve approval into the day-one slot the first time a
    contact was approved out of order, and the approval fingerprint on the
    wire would still be the one the gate checked.

    An EMPTY sequence reports nothing missing: a campaign the client has
    configured no sequence for stages leads with attribution and no words,
    which is what `_ensure_sequence` already reports and permits.

    VARIANTS ARE RESOLVED HERE, not downstream. A step carrying five variants
    assigns one per contact deterministically (see `cadence.variant_for`),
    and the variant's words - not the base template's - are what the provider
    receives. Each variant is approved independently: five variants means
    five approvals, not one stretched over five. A variant whose words have
    not been approved is treated the same as a step with no approval at all:
    it is reported missing and the stage refuses on it.
    """
    if not sequence:
        return [], []
    steps = ((source or {}).get("cadence") or {}).get(contact_key) or {}
    # Index cadence step specs by key so variant lookup is O(1).
    spec_by_key = {}
    for spec in (cadence_steps or ()):
        if spec.get("key"):
            spec_by_key[spec["key"]] = spec
    copy, missing = [], []
    for node in sequence:
        key = node.get("step_key")
        if key is None:
            # The single-step shape carries no cadence key, so the earliest
            # approved email step is the opener, exactly as before.
            found = _earliest_approved_email(steps)
        else:
            step = steps.get(key) or {}
            spec = spec_by_key.get(key) or {}
            found = _resolve_step_copy(step, spec, key, contact_key,
                                       campaign, config)
        if not found or not found.get("subject") or not found.get("body"):
            missing.append(str(key) if key is not None
                           else f"step {node['order']}")
            continue
        copy.append(found)
    return copy, missing


def _certified_copy(step, key, extra=None):
    """The staged words for one step, or None unless an approval certifies
    THESE EXACT WORDS.

    THE ONLY PLACE EMAIL COPY BECOMES STAGEABLE. Every branch below - variant,
    no-variant, single-step opener - returns through here, because "a human
    approved this step" and "a human approved the words this step is about to
    ship" are two different questions and only the second one is safe to ask
    at staging time.

    The entry is built FIRST and the fingerprint is then computed over the
    entry's own `subject` and `body`, so the material that is hashed is the
    same string the provider receives in `{SUBJECT_N}` / `{BODY_N}`. A check
    that hashed the step instead could agree while the words in the payload
    came from somewhere else, which is exactly the defect this closes:
    `approve.approve_step` stamped a fingerprint taken over the
    campaign-expanded step onto a slot that still held older generated copy,
    and the no-variant branch staged the slot's words after checking only that
    an approval EXISTED. Measured 2026-09-16 on campaign 485: ten leads, zero
    reported missing, thirty steps of words no operator had approved.

    `channel` and `note` come from the step because `approval.fingerprint`
    covers them too, and an approval taken over a step carrying a note does
    not certify the same step with the note removed.

    FAILS CLOSED, always by returning None, which `_approved_copy` reports as
    missing copy and `_ensure_leads` refuses the whole stage on:
      - no approval on the step at all
      - an approval with no fingerprint recorded on it
      - a fingerprint that does not cover the words being staged
    """
    from . import approval

    stamp = (step or {}).get("approval") or {}
    recorded = stamp.get("fingerprint")
    if not recorded:
        # No approval, or an approval that records nothing about the words it
        # was given for. Neither certifies anything.
        return None
    if not approval.is_accountable_approver(stamp.get("by")):
        # An approval this system recorded for itself is not an approval. The
        # fingerprint proves the words have not moved; it cannot prove a person
        # ever read them, and on a `generated: true` step the words never move,
        # so a self-stamp would stay current forever.
        return None
    entry = {"step_key": key, "subject": (step or {}).get("subject"),
             "body": (step or {}).get("body")}
    material = dict(step or {})
    material["subject"] = entry["subject"]
    material["body"] = entry["body"]
    if approval.fingerprint(material) != recorded:
        return None
    if extra:
        # `extra` IS METADATA AND MAY NEVER BE COPY.
        #
        # The merge happens AFTER the fingerprint proof, so a caller passing
        # `subject` or `body` here would overwrite certified words with
        # uncertified ones and every layer downstream would still report
        # success. Today the single caller passes variant_id/style/version, so
        # the hatch is unused - but "unused" is a fact about this week's
        # callers, and the next caller is exactly how a hatch like this gets
        # walked through. Found by an independent model reading the function
        # cold, which is the whole reason for asking one.
        forbidden = sorted(set(extra) & {"subject", "body", "note", "message"})
        if forbidden:
            raise FactoryRefused(
                f"_certified_copy was handed prospect-facing field(s) "
                f"{forbidden} as metadata for step {key!r}. `extra` is merged "
                f"after the approval is verified, so copy arriving that way "
                f"would reach a prospect uncertified. Put the words in the "
                f"step before it is fingerprinted")
        entry.update(extra)
    return entry


def _resolve_step_copy(stored_step, spec, key, contact_key, campaign, config):
    """The approved words for one step, resolving variants when present.

    When the step spec carries variants, the assigned variant's words are
    used and the variant_id is recorded on the result. The variant is
    resolved deterministically so the same contact always gets the same arm.

    Every variant must be approved independently. The approval fingerprint
    covers the variant's words because `variants.apply_to_step` puts them
    into the step before `approval.fingerprint` hashes it. A variant whose
    words do not match any stored approval is not copy anybody has blessed.

    NEITHER BRANCH RETURNS WORDS AN APPROVAL DOES NOT COVER. The variant
    branch always compared; the no-variant branch asked only whether an
    approval existed, so a stored slot whose copy had moved on from the
    fingerprint stamped on it staged clean. Both go through
    `_certified_copy` now, which is the one place that comparison happens.
    """
    from . import cadence as _cadence
    from . import variants

    entry = None
    if spec.get(_cadence.VARIANTS_KEY):
        recorded = (stored_step or {}).get("variant_id")
        entry = _cadence.variant_for(spec, campaign, contact_key,
                                     recorded=recorded, config=config)
    if entry is not None:
        # The variant's words, applied to the stored step so the approval
        # fingerprint covers them.
        stepped = variants.apply_to_step(dict(stored_step or {}), entry)
        return _certified_copy(
            stepped, key,
            extra={"variant_id": entry.get("variant_id"),
                   "variant_style": entry.get("style"),
                   "variant_version": entry.get("version")})
    # No variant: the stored step's own words - and only if the approval on
    # the step is an approval OF those words.
    if stored_step.get("channel") == "email":
        return _certified_copy(stored_step, key)
    return None


def _earliest_approved_email(steps):
    """The first APPROVED email step by key, or None.

    Used only for the single-step sequence shape, where the one step that
    goes out is the opener and a later step's words in its place would be a
    message arriving out of order.

    Which is why an approval that does not certify the opener's stored words
    returns None rather than walking on to the next step: falling through
    would answer "this contact has no approved opener" with a day-eight
    message, and a refusal is the only honest answer to it.
    """
    for step_key in sorted(steps or {}):
        step = (steps or {})[step_key] or {}
        if step.get("channel") != "email" or not step.get("approval"):
            continue
        return _certified_copy(step, step_key)
    return None


def _find_or_create(campaign, report, by="system"):
    """The provider campaign for this row, reused if it exists.

    Reuse comes first and is checked against the PROVIDER, not against the
    row: a `bison_campaign_id` naming a campaign that has since been deleted
    is a stale binding, and building on it would attach leads to nothing.
    """
    bound = campaign.get("bison_campaign_id")
    if bound:
        try:
            live_row = bison.campaign(bound)
        except ProviderError as e:
            raise FactoryRefused(
                f"campaign {campaign.get('campaign_id')} is bound to EmailBison "
                f"campaign {bound}, which the provider will not return "
                f"({e}). Refusing to create a second one behind a binding "
                f"that may still be valid; reconcile by hand") from None
        status = str(live_row.get("status") or "").lower()
        if status == bison.PENDING_DELETION:
            # DELETE IS ASYNCHRONOUS HERE AND THE ROW SURVIVES IT FOR A FEW
            # SECONDS. Measured 2026-09-13: `DELETE /campaigns/{id}` answers
            # 200 "queued for deletion", the GET keeps answering 200 with this
            # status, and two seconds later the same GET is a 404. Staging
            # into that window writes a cap, a schedule, a sequence and a set
            # of leads into a campaign that is about to stop existing, and
            # every readback in between looks correct.
            raise FactoryRefused(
                f"campaign {campaign.get('campaign_id')} is bound to "
                f"EmailBison campaign {bound}, which is {status!r}. It is on "
                f"its way out and anything staged into it goes with it. Clear "
                f"the binding once the provider has finished deleting it")
        report["did"].append(f"reused EmailBison campaign {bound}")
        report["provider"]["status_before"] = live_row.get("status")
        return bound, str(live_row.get("name") or report["plan"]["name"])

    # BEFORE CREATING: IS ONE ALREADY THERE UNDER THIS ROW'S NAME?
    #
    # This is the crash-between-POST-and-persist case, and until now the
    # module's own docstring claimed it was "reported as ambiguous rather than
    # retried" while the code went straight to a second POST. `bison_campaign_
    # id` is written inside the transaction that reads it, so the window is
    # small - and a window that is only small is one that eventually opens.
    #
    # The lookup is exact and the name is derived, so this finds the campaign
    # this row would have built and nothing else. Two of them is not a case to
    # choose between: both are real campaigns that can hold real people.
    planned = report["plan"]["name"]
    orphans = bison.find_campaigns_by_name(planned)
    orphans = [o for o in orphans
               if str(o.get("status") or "").lower() != bison.PENDING_DELETION]
    if len(orphans) > 1:
        raise FactoryAmbiguous(
            f"EmailBison holds {len(orphans)} campaigns named {planned!r} "
            f"({sorted(o.get('id') for o in orphans)}) and this row is bound "
            f"to none of them. Both can hold real people. Bind the right one "
            f"by hand and delete the other; do NOT re-run this")
    if orphans:
        found = orphans[0]
        _bind(campaign, found["id"], "found by name and bound: it was created "
                                     "and never recorded")
        report["did"].append(
            f"recovered EmailBison campaign {found['id']} by name: it existed "
            f"already and this row was bound to nothing")
        report["provider"]["recovered"] = True
        report["provider"]["status_before"] = found.get("status")
        return found["id"], str(found.get("name") or planned)

    payload = {"name": planned}
    # `perform` reports the response as trimmed JSON TEXT, which is right for
    # an audit line and useless for reading an id back out of. The transport
    # holds the real row, so it is captured here rather than reparsed.
    created = {}

    def _create(p):
        created.update(bison.create_campaign(p["name"]))
        return created

    providerwrites.perform(
        providerwrites.EMAIL_CREATE_CAMPAIGN,
        campaign=str(campaign.get("campaign_id")), tenant=campaign.get("client"),
        payload=payload, transport=_create,
        readback=lambda: {"exists": bool(created.get("id"))},
        expected={"exists": True}, by=by)
    provider_id = created.get("id")
    if not provider_id:
        raise FactoryAmbiguous(
            "EmailBison accepted the campaign but returned no id. A campaign "
            "may now exist that nothing here can name. Find it by name and "
            "bind it by hand; do NOT re-run this")

    # PERSIST IMMEDIATELY, IN ITS OWN TRANSACTION.
    # Everything after this point can be retried. This cannot: an unpersisted
    # id is a campaign nobody can find, and the next run would build another -
    # which is now recoverable by name above rather than merely narrow.
    _bind(campaign, provider_id, "created and bound")
    report["did"].append(f"created EmailBison campaign {provider_id}")
    return provider_id, planned


def _bind(campaign, provider_id, why):
    """Write the provider's campaign id onto the row, in its own transaction."""
    with campaigns.transaction() as rows:
        row = campaigns.get(str(campaign.get("campaign_id")), rows)
        if row is not None:
            row["bison_campaign_id"] = provider_id
            campaigns.log(row, "provider",
                          f"EmailBison campaign {provider_id} {why}")
    return provider_id


def _ensure_limits(provider_id, campaign, provider_name, report):
    """Cap the campaign before it holds anybody.

    The provider's default is 1000 emails a day and `POST /campaigns` accepts
    a cap and stores 1000 anyway, so a campaign is uncapped until something
    explicitly caps it. This runs before leads are attached: the order is the
    point, since a cap applied afterwards is a cap that was briefly absent.

    A campaign whose daily volume nobody configured is REFUSED rather than
    left on the default. "Nobody said" and "a thousand a day" must not be the
    same state.

    `provider_name` IS THE PROVIDER'S OWN NAME, not the planned one. The cap
    route requires `name` in the same body, so writing a cap rewrites the
    name - and re-staging is routine. Passing the planned name here meant
    reconciling a campaign somebody had renamed in EmailBison's UI silently
    renamed it back, which is an edit nobody asked this function to make.
    """
    volume = (campaign.get("daily_volume") or {}).get("email")
    if not volume:
        raise FactoryRefused(
            f"campaign {campaign.get('campaign_id')!r} sets no email daily "
            f"volume. EmailBison defaults to 1000 a day and discards a cap "
            f"passed at create time, so staging this would leave a campaign "
            f"nobody rate-limited")
    state = bison.set_limits(provider_id, provider_name, int(volume))
    report["provider"]["limits"] = state
    report["did"].append(f"capped at {state['max_emails_per_day']}/day")


def _ensure_schedule(provider_id, plan, report):
    """Write the sending window, and refuse a campaign that has none.

    Same argument as the daily cap: a campaign staged without a window takes
    whatever the provider does, and "nobody chose" must not be indistinguish-
    able from "somebody chose that". `GET .../schedule` answers 200 with
    `success: false` when no schedule exists, so absence here is read from the
    body rather than the status.

    "ALREADY CORRECT" MEANS ALL OF IT. This compared the days and the timezone
    and not the hours, so narrowing a window from 09:00-17:00 to 09:00-12:00
    on the same days was reported as "already correct; unchanged" and the
    campaign kept sending until five. The hours are the part of a sending
    window a client actually asks to change.
    """
    window = plan.get("window") or {}
    missing = [k for k in ("days", "start", "end", "timezone")
               if not window.get(k)]
    if missing:
        raise FactoryRefused(
            f"the client config sets no sending window ({', '.join(missing)} "
            f"absent), so this campaign would send on whatever schedule the "
            f"provider defaults to. Set `sending_window` for this client")
    if bison.schedule_matches(bison.schedule(provider_id), window["days"],
                              window["start"], window["end"],
                              window["timezone"]):
        report["did"].append("schedule already correct; unchanged")
        return
    bison.set_schedule(provider_id, window["days"], window["start"],
                       window["end"], window["timezone"])
    report["did"].append(
        f"scheduled {len(window['days'])} day(s) {window['start']}-"
        f"{window['end']} {window['timezone']}")


def _ensure_senders(provider_id, campaign, report):
    """Bind the inboxes this campaign sends from.

    The provider answers 200 with `success: false` when it attaches nothing,
    so `bison.attach_senders` reads the membership back and raises unless
    every sender asked for is actually bound. A campaign with no configured
    senders is left alone rather than guessed at - picking an inbox would be
    choosing which human a prospect hears from.
    """
    wanted = []
    for sender in (campaign.get("senders") or {}).get("email") or []:
        ident = sender.get("provider_account_id") if isinstance(sender, dict) \
            else sender
        if ident:
            wanted.append(int(ident))
    if not wanted:
        report["did"].append(
            "no senders staged: the campaign names none, and choosing an "
            "inbox would be choosing who a prospect hears from")
        return
    bound = bison.campaign_senders(provider_id)
    if set(wanted) <= set(bound):
        report["did"].append(f"{len(wanted)} sender(s) already bound")
        return
    state = bison.attach_senders(provider_id, wanted)
    report["provider"]["senders"] = state["senders"]
    report["did"].append(f"bound {len(state['senders'])} sender inbox(es)")


def _comparable_step(subject, body, thread_reply):
    """One sequence step, in a shape the provider and we can be compared in.

    THE PROVIDER REWRITES THE SUBJECT ON A THREAD REPLY, and it is documented
    behaviour rather than drift. TASK-159 measured it across 153 same-thread
    follow-ups in the estate: EmailBison prepends "Re: " itself, and
    `EMAILBISON-COPY-REQUIREMENTS.md` says not to write it ourselves.

    So a verbatim comparison of what we asked for against what is held is
    guaranteed to disagree on every `thread_reply` step, forever. Measured
    2026-09-16 on campaign 484: five steps written once, the only difference
    being "Re: " on steps 2 and 4, and the read-back called it DRIFTED and
    raised `WriteUnverified`. Nothing had drifted. The campaign was correct.

    A false DRIFTED is expensive in a specific way: `set_sequence` APPENDS,
    so the operator is told not to retry, and the campaign is abandoned as
    unverifiable when it was right all along.

    Normalising ONLY this one leading token, ONLY on a step that declares
    itself a thread reply. Body and `thread_reply` are still compared exactly,
    and a subject that differs by anything else still fails.
    """
    text = str(subject or "")
    if thread_reply and text[:4].lower() == "re: ":
        text = text[4:]
    return (text, body, thread_reply)


def _ensure_sequence(provider_id, campaign, plan, report, by="system"):
    """Write the sequence into an EMPTY campaign, or refuse.

    THE WRITE APPENDS AND NOTHING CAN UNDO IT. Measured 2026-09-13: two writes
    leave two steps, three writes leave four, renumbered 1, 3, 2, 4. There is
    no replace verb and no per-step route - the sequence path is GET, HEAD,
    POST only. A campaign whose sequence is written twice therefore sends
    twice, the second email carrying the older copy, and the only remedy is
    deleting the campaign.

    `providerwrites.staged_already` guarded the IDENTICAL payload, which is
    the case that never needed guarding: a client editing `email_sequence`, or
    a campaign whose derived title changed, produces a DIFFERENT payload, and
    that went straight to a second POST. So the provider is asked what it
    holds, and a campaign already holding a different sequence stops here.

    AND THE READ-BACK IS A READ NOW. It used to be `{"steps": len(steps)}`
    compared against `{"steps": len(steps)}` - the request compared to itself,
    which agreed unconditionally. `bison.sequence_steps` answers the real
    question, so a write that did not take is visible.
    """
    configured = plan.get("sequence_config") or {}
    # `step_key` is this module's own bookkeeping - it is how a lead's
    # approved words are matched to the step that will send them - and the
    # provider has no field for it. Stripped here rather than never carried,
    # because the readback compares what was asked for against what is held.
    steps = [{k: v for k, v in node.items() if k != "step_key"}
             for node in plan.get("sequence") or []]
    if not steps:
        report["did"].append(
            "no sequence staged: the client config names no `email_sequence`")
        return
    held = bison.sequence_steps(provider_id)
    if held:
        wanted = [_comparable_step(s["email_subject"], s["email_body"],
                                   s.get("thread_reply")) for s in steps]
        got = [_comparable_step(s.get("email_subject"), s.get("email_body"),
                                s.get("thread_reply")) for s in held]
        if got == wanted:
            report["did"].append(
                f"sequence already staged ({len(held)} step(s)); unchanged")
            return
        raise FactoryRefused(
            f"EmailBison campaign {provider_id} already holds {len(held)} "
            f"sequence step(s) and they are not the {len(steps)} this "
            f"campaign specifies. The sequence route APPENDS - there is no "
            f"replace and no delete - so writing would leave the campaign "
            f"sending both, the old copy second. Held: "
            f"{[s.get('email_subject') for s in held]}. Wanted: "
            f"{[s['email_subject'] for s in steps]}. Rebuild the campaign, or "
            f"fix it by hand in EmailBison")
    # THE PROVIDER CAMPAIGN IS PART OF WHAT THIS WRITE IS.
    #
    # `providerwrites.perform` refuses a repeat of the same MATERIAL for the
    # same campaign row, and the material used to be the title and the steps
    # alone. So a row whose provider campaign was deleted and rebuilt could
    # never be given its sequence again: the new campaign holds nothing, the
    # row remembers the same words, and the write is refused. Naming the
    # provider campaign makes staging into 501 a different write from staging
    # into 500, which is what it is. The transport reads `title` and
    # `sequence_steps` and ignores this.
    payload = {"title": configured.get("title") or plan["name"],
               "bison_campaign_id": provider_id,
               "sequence_steps": steps}
    providerwrites.perform(
        providerwrites.EMAIL_SET_SEQUENCE,
        campaign=str(campaign.get("campaign_id")), tenant=campaign.get("client"),
        payload=payload,
        transport=lambda p: bison.set_sequence(provider_id, p["title"],
                                               p["sequence_steps"]),
        readback=lambda: {"steps": [
            _comparable_step(s.get("email_subject"), s.get("email_body"),
                             s.get("thread_reply"))
            for s in bison.sequence_steps(provider_id)]},
        expected={"steps": [_comparable_step(s["email_subject"],
                                             s["email_body"],
                                             s.get("thread_reply"))
                            for s in steps]}, by=by)
    report["did"].append(f"staged a {len(steps)}-step sequence")


def _known_lead_ids(campaign, wanted):
    """Provider lead ids this system already recorded, by contact key."""
    recs = store.load()
    by_id = {r.get("id"): r for r in recs}
    known = {}
    for lead in wanted:
        rec = by_id.get(lead["record_id"]) or {}
        for contact in rec.get("contacts") or []:
            if contact.get("key") == lead["contact_key"] and contact.get(
                    "bison_lead_id"):
                known[lead["contact_key"]] = contact["bison_lead_id"]
    return known


def _remember_lead(lead, lead_id):
    """Write the provider's id onto the contact, immediately.

    Immediately, and in its own transaction, for the same reason the campaign
    id is: an id the provider issued and this system did not record is a lead
    that will be created again, and the second attempt is the one that fails.
    """
    with store.transaction() as rows:
        for rec in rows:
            if rec.get("id") != lead["record_id"]:
                continue
            for contact in rec.get("contacts") or []:
                if contact.get("key") == lead["contact_key"]:
                    contact["bison_lead_id"] = lead_id


def _remember_leads(pairs):
    """Write many provider ids in one transaction instead of one per lead.

    At 30k records each transaction reads and writes the full queue. N leads
    in N transactions moves O(N * queue_size) bytes; one transaction moves it
    once. `_remember_lead` is kept for the single-lead path; this is what
    `_ensure_leads` calls after the create loop.
    """
    if not pairs:
        return
    with store.transaction() as rows:
        by_id = {rec.get("id"): rec for rec in rows}
        for lead, lead_id in pairs:
            rec = by_id.get(lead["record_id"])
            if rec is None:
                continue
            for contact in rec.get("contacts") or []:
                if contact.get("key") == lead["contact_key"]:
                    contact["bison_lead_id"] = lead_id


def _variables_for(lead, campaign, sequence=None):
    """Everything this lead carries at the provider.

    Two kinds, and both are load-bearing.

    ATTRIBUTION. `adapters.from_emailbison` reads `record_id` and
    `contact_key` back off an inbound reply. Without them a reply arrives
    attached to an address and to nothing else, and reply-stop cannot find
    the person it is supposed to stop.

    THE COPY. The sequence is a template of merge fields - `{SUBJECT}` and
    `{BODY}` - so the approved words travel per lead and render into it. A
    lead staged without them produces an email with an empty subject and an
    empty body, and nothing in the staging readback would have shown it: the
    campaign, the schedule, the sender and the membership would all look
    exactly right. `_ensure_leads` refuses that case rather than trusting
    this paragraph to be read.

    ONE VARIABLE PER STEP, NUMBERED BY POSITION. A custom variable holds one
    value per lead, so five steps of generated copy cannot share `subject`:
    the template `{SUBJECT_3}` resolves to the variable `subject_3`, which is
    the third step's approved words. The unnumbered `subject` and `body` are
    still written for a single-step sequence, because campaign 451 is staged
    against `{SUBJECT}` and is production evidence with a scheduled send on
    it. A campaign built from the multi-step shape never reads them.

    ONE SHAPE PER CAMPAIGN, NEVER BOTH. A single-step campaign carries
    `subject` and `body` and no numbered pair; a multi-step one carries the
    numbered pairs and neither unnumbered name. Writing both would leave
    every lead holding a variable its own template never reads, and a reader
    comparing two leads could not tell which shape the campaign was built in.

    THREADED SEQUENCES: SUBJECT_1 ONLY. When the sequence has threaded
    follow-ups (any step declares ``thread_reply: true``), only ``subject_1``
    carries the opener's subject. Follow-up subject variables are written as
    empty strings: the template references ``{SUBJECT_1}`` for every step,
    and the provider prepends ``Re:`` itself. A non-empty ``subject_2`` on a
    threaded lead is a stale value from a previous non-threaded era, and
    ``_stale_clearances`` wipes it during reconciliation.
    """
    values = {"record_id": lead["record_id"],
              "contact_key": lead["contact_key"],
              "client": campaign.get("client") or ""}
    copy = lead.get("copy") or []
    if len(copy) <= 1:
        values["subject"] = lead.get("subject") or ""
        values["body"] = lead.get("body") or ""
    else:
        threaded_keys = set()
        for node in (sequence or ()):
            if node.get("thread_reply") and node.get("step_key"):
                threaded_keys.add(node["step_key"])
        for position, node in enumerate(copy, start=1):
            step_key = node.get("step_key")
            if position > 1 and step_key in threaded_keys:
                values[f"subject_{position}"] = ""
            else:
                values[f"subject_{position}"] = node.get("subject") or ""
            values[f"body_{position}"] = node.get("body") or ""
    return bison._variables(values)


def _stale_clearances(sequence):
    """Empty-valued entries for numbered copy slots the sequence does not use.

    TWO KINDS OF STALE, ONE MECHANISM.

    1. Out-of-range positions: a lead that previously carried a longer
       sequence holds ``subject_N`` and ``body_N`` variables beyond the
       current length. ``_variables_for`` names only the positions the
       sequence reads, so the reconciliation in ``_ensure_leads`` never
       compares - and never clears - the higher ones. Measured on campaign
       485 on 2026-09-16: ten leads held ``subject_4``, ``subject_5``,
       ``body_4`` and ``body_5`` from a five-step era while the campaign had
       shrunk to three steps.

    2. In-range follow-up subjects on a threaded sequence: when the threaded
       shape is in effect (any step declares ``thread_reply: true``), only
       ``subject_1`` carries prospect-facing content. Follow-up subjects at
       positions 2..N are not referenced by the template (all steps reference
       ``{SUBJECT_1}``), but a lead from a previous non-threaded era may still
       hold a non-empty ``subject_2`` or ``subject_3``. Without clearing them,
       a config change from non-threaded to threaded would leave stale
       subjects on the lead that the template no longer reads - but that a
       future template change could resurrect.

    Returns explicit empties for:
    - Every ``subject_{2..N}`` when the sequence is threaded (in-range
      follow-up subjects the threaded shape does not use).
    - Every ``subject_{N+1..MAX}`` and ``body_{N+1..MAX}`` (out-of-range
      positions beyond the sequence length).

    ``_ensure_leads`` merges them into the wanted set; the provider PATCH
    stores the empty value and the template never reads a variable its
    sequence does not declare.

    Single-step campaigns use unnumbered ``subject`` and ``body`` and have
    no numbered positions to clear, so the answer is empty.
    """
    n_steps = len(sequence)
    if n_steps < 2:
        return []
    entries = []
    has_threading = any(s.get("thread_reply") for s in sequence)
    for pos in range(2, MAX_SEQUENCE_STEPS + 1):
        if pos <= n_steps:
            if has_threading:
                entries.append({"name": f"subject_{pos}", "value": ""})
        else:
            entries.append({"name": f"subject_{pos}", "value": ""})
            entries.append({"name": f"body_{pos}", "value": ""})
    return entries


def _already_on_campaign(provider_id):
    """Addresses this campaign ALREADY holds, lowercased.

    Read from the campaign's own queue, which carries `lead.email` per row and
    is one paginated read. A lead enrolled but with no queue row yet is not in
    this set and is therefore still collision-checked - the safe direction, and
    the reason this returns a set of what is KNOWN present rather than a claim
    about what is absent.

    An unreadable queue returns the empty set, so every lead is checked. That
    is the same direction: it can only add checks, never skip one.
    """
    if not provider_id:
        return set()
    try:
        rows = bison.scheduled_emails(provider_id)
    except Exception:                                           # noqa: BLE001
        return set()
    return {str(((row.get("lead") or {}).get("email") or "")).strip().lower()
            for row in rows} - {""}


def _refuse_colliding_leads(wanted, workspace_id, already_on=()):
    """Refuse leads whose account the client's estate says STOP or HOLD.

    ## RE-STAGING AN EXISTING MEMBER IS NOT A NEW TOUCH

    ISSUE-021. `stage` re-submits every lead on the campaign, not only the new
    ones, so once a campaign has emailed somebody that lead collides with ITS
    OWN sent state - and this refuses the WHOLE stage rather than one lead, so
    two already-contacted people blocked 34 good ones on 2026-09-22.

    The account gate exists to stop us ADDING somebody to an account that is
    already in play. A lead that is already on this campaign is not being
    added; it is being re-described. Whether it should have been added was
    decided when it was, and re-deciding it now on a state OUR OWN send
    created is the circular reading that blocked batch 3.

    `already_on` is what the campaign already holds. It never widens the check
    to a lead that is not there: an unreadable queue yields an empty set and
    everything is checked, which is the safe direction.

    Uses `collision.check_account` and `collision.account_policy` - the same
    gates `executionguard` runs at send time. Fetched per domain and cached
    for the duration of this call: a campaign's leads typically span a small
    number of domains, and each `check_account` costs one paginated search.

    WHICH STATES BLOCK AND WHICH MAY PASS, per `account_policy`:
      - `in_sequence`   -> STOP  -> block. A second channel now is the
                        collision this module exists to prevent.
      - `stopped`       -> HOLD  -> block. The status does not say who ended
                        it; it is the state a reply or unsubscribe leaves.
      - `bounced`       -> HOLD  -> block. The data is suspect; a person
                        should look before we spend more.
      - `sequence_finished` -> ALLOW -> may pass. A campaign that ran its
                        course with no reply is history, not a live conflict.
                        It is still REPORTED in the account check, so "cold
                        outreach" is never claimed about a worked account.

    An UNREADABLE estate is refused. "We could not check" and "there is
    nothing there" are the two answers this module exists to keep apart.
    """
    from . import collision

    on_campaign = {str(a).strip().lower() for a in (already_on or ())}

    by_domain = {}
    for lead in wanted:
        address = str(lead["email"]).strip().lower()
        if address in on_campaign:
            # Already a member: being re-described, not added. See ISSUE-021.
            continue
        domain = address.rsplit("@", 1)[-1]
        if domain:
            by_domain.setdefault(domain, []).append(lead)

    refused = []
    for domain, leads in by_domain.items():
        try:
            account = collision.check_account(
                domain, expect_workspace=workspace_id)
        except collision.CollisionUnknown as e:
            raise FactoryRefused(
                f"the provider estate could not be read for {domain}: {e}. "
                f"Refusing to stage leads at an unreadable account: a lead "
                f"that cannot be checked cannot be cleared") from None
        verdict, why = collision.account_policy(account)
        if verdict in (collision.STOP, collision.HOLD):
            for lead in leads:
                refused.append((lead, verdict, why))

    if refused:
        detail = "; ".join(
            f"{lead['contact_key']} ({lead['email']}): {v} - {w}"
            for lead, v, w in refused[:5])
        raise FactoryRefused(
            f"{len(refused)} contact(s) collided with the client's own estate: "
            f"{detail}"
            f"{' and more' if len(refused) > 5 else ''}. "
            f"A contact the client is already emailing or whose data is "
            f"suspect must not be staged into a Resonate campaign")


def _ensure_leads(provider_id, campaign, plan, report, by="system"):
    """Create the leads this campaign needs, then attach exactly those.

    Attachment is checked against provider membership on both sides, so a
    re-run costs reads and writes nothing. `bison.attach_leads` raises unless
    the readback contains what was asked for, which is what stops a partial
    attach being reported as a full one.

    A LEAD WITHOUT THE WORDS ITS SEQUENCE WILL ASK FOR STOPS THE WHOLE RUN.
    This is the last point at which nothing has reached a person: the
    sequence is written, the campaign is stopped, and no lead exists yet. A
    step whose copy variable is absent sends an email with an empty subject
    and an empty body, and `_readback` would report that campaign correct -
    the sequence, the schedule, the sender and the membership are all exactly
    right. The whole run stops rather than the one lead being skipped,
    because a campaign that quietly stages four of five people is a cohort
    nobody can reason about afterwards. `_plan` lists them without raising,
    so a dry run answers "which contacts, and which steps" in one pass.
    """
    wanted = plan.get("leads") or []
    if not wanted:
        report["did"].append("no leads staged: the plan carries none")
        return
    _refuse_unsupported(plan)
    _refuse_bad_greetings(plan)
    short = [(lead["record_id"], lead["contact_key"], lead["missing_copy"])
             for lead in wanted if lead.get("missing_copy")]
    if short:
        detail = "; ".join(f"{rid}/{key} missing {', '.join(steps)}"
                           for rid, key, steps in short[:5])
        raise FactoryRefused(
            f"{len(short)} of {len(wanted)} contact(s) carry no approved copy "
            f"for every step of this campaign's {len(plan.get('sequence') or [])}"
            f"-step sequence: {detail}"
            f"{' and more' if len(short) > 5 else ''}. Each missing step sends "
            f"a real person an email with an empty subject and an empty body, "
            f"and every readback would agree the campaign was correct. "
            f"Generate and approve the missing steps, then stage again")
    # THE ESTATE IS CHECKED BEFORE ANY LEAD IS CREATED OR ATTACHED.
    # `_ensure_leads` calls `bison.create_lead` and `bison.attach_leads`
    # directly, bypassing `executionguard.authorize()` and every gate it
    # runs. The killswitch check below closes the tenant-level half of that
    # gap; this closes the person-level half. A contact already mid-sequence,
    # stopped, bounced or replied in the client's own estate must not be
    # staged into a Resonate campaign. Measured 2026-09-13: nineteen contacts
    # were staged into EmailBison campaign 481, nine of them already in the
    # client's own campaigns, and nothing objected.
    #
    # THE CHECK IS ACCOUNT-LEVEL, USING `collision.check_account` AND
    # `collision.account_policy`. The account is the unit of outreach per
    # `ACCOUNT-OUTREACH.md`, and `account_policy` already draws the line
    # between what blocks and what is history. This does not invent a new
    # verdict; it applies the existing one at the staging boundary.
    #
    # CACHED PER DOMAIN. A campaign's leads typically span a small number of
    # domains, and each `check_account` costs one paginated provider search.
    # The cache lives for the duration of this call only.
    workspace_id = (report.get("workspace") or {}).get("id")
    if workspace_id:
        _refuse_colliding_leads(wanted, workspace_id,
                                already_on=_already_on_campaign(provider_id))
    # The variables must exist on the workspace before a lead may carry one:
    # the provider refuses an undeclared name outright. Idempotent, and it
    # creates nothing that can reach a person.
    bison.ensure_custom_variables()
    # THE KILLSWITCH IS CONSULTED BEFORE ANY LEAD IS CREATED OR ATTACHED.
    # `_ensure_leads` does not go through `providerwrites.perform` - it calls
    # `bison.create_lead` and `bison.attach_leads` directly - so the write
    # door's killswitch gate does not cover it. The workspace layer is the
    # meaningful control at staging time: `sending.live` is the tenant switch
    # that says whether this workspace's outreach is active. A workspace that
    # has never been switched on, or that has been switched off, must not have
    # leads created for it. The GLOBAL layer is excluded because it refuses
    # sending (which staging is not); the CAMPAIGN layer is excluded because
    # the canonical campaign is not RUNNING during staging and that is the
    # correct state for a campaign being built.
    from . import killswitch

    ws_state = killswitch.workspace_state(campaign.get("client"))
    if not ws_state["sending"]:
        raise FactoryRefused(
            f"the killswitch for workspace {campaign.get('client')!r} is off: "
            f"{ws_state['why']}. No leads were created or attached")
    before = bison.campaign_lead_count(provider_id)
    known = _known_lead_ids(campaign, wanted)
    ids, created, reconciled, refreshed = [], 0, 0, 0
    adopted = 0
    #: provider lead id -> the lead we staged, for the pre-attach check.
    _wanted_by_id = {}
    remember_pairs = []
    for lead in wanted:
        existing = known.get(lead["contact_key"])
        if existing:
            # THE COPY MAY HAVE CHANGED SINCE THIS LEAD WAS MADE. A
            # regenerated draft, a fresh approval, a corrected angle - all
            # change the words without changing who they go to, and a lead
            # created before that still holds the old ones. Reconciled rather
            # than assumed: the provider is asked what it has, and told only
            # what differs.
            #
            # STALE NUMBERED VARIABLES BEYOND THE SEQUENCE LENGTH ARE
            # CLEARED HERE. `_variables_for` names only the positions the
            # sequence reads; `_stale_clearances` adds explicit empties for
            # every numbered slot above that, so a lead that previously
            # carried a longer sequence has its out-of-range copy wiped.
            # Without this, subject_4/body_4/subject_5/body_5 from a five-
            # step era survive silently on a three-step campaign, and the
            # stale comparison never names them because they are not in the
            # wanted set.
            wanted_vars = _variables_for(lead, campaign,
                                         sequence=plan.get("sequence") or [])
            clearances = _stale_clearances(plan.get("sequence") or [])
            all_wanted = wanted_vars + clearances
            held = bison.variables_of(bison.lead(existing))
            stale = [v for v in all_wanted
                     if held.get(v["name"]) != v["value"]]
            if stale:
                bison.update_lead(existing, {"custom_variables": stale})
                refreshed += 1
                report["did"].append(
                    f"refreshed {len(stale)} variable(s) on lead {existing}: "
                    f"{sorted(v['name'] for v in stale)}")
            ids.append(existing)
            _wanted_by_id[existing] = lead
            continue
        try:
            row = bison.create_lead({
                "email": lead["email"],
                "first_name": lead["first_name"],
                "last_name": lead["last_name"],
                # WHO THIS IS, IN THE PROVIDER'S OWN RECORD.
                # `adapters.from_emailbison` reads these back off an inbound
                # reply. Without them a reply arrives attached to an address
                # and to nothing else, and reply-stop cannot find the person
                # it is supposed to stop.
                "custom_variables": _variables_for(
                    lead, campaign,
                    sequence=plan.get("sequence") or [])})
            created += 1
        except ProviderError as e:
            # ALREADY THERE, AND WE NEVER WROTE IT DOWN.
            # Creating it again is what the provider just refused, and
            # guessing an id would attach a stranger to this campaign. So the
            # address is looked up exactly, or this stops.
            #
            # THE LOOKUP WAITS, because the commonest way to get here is a
            # race this process just lost: two campaigns for the same client
            # staged at once, both needing the same person, one of them
            # creating the lead a fraction of a second earlier. The provider's
            # lead search is an index and the index is about a second behind,
            # so asking once meant the loser reported AMBIGUOUS and stopped -
            # measured 2026-09-13. Six tries over five seconds, and if it is
            # still not there this stops exactly as before: a lead that exists
            # and cannot be named must not be guessed at.
            if "already been taken" not in str(e):
                raise
            row = bison.find_lead_by_email(lead["email"], attempts=6,
                                           interval=1.0)
            if not row:
                raise FactoryAmbiguous(
                    f"EmailBison says {lead['email']} already exists but will "
                    f"not return it - its lead search lags behind creation. "
                    f"Wait and re-run; do NOT create a duplicate") from None
            # THE ADOPTED LEAD IS NOT OURS YET, AND THIS IS WHERE 73 BLANK
            # EMAILS CAME FROM.
            #
            # "already been taken" does NOT only mean we lost a race with
            # ourselves. It also means the address is already in the CLIENT'S
            # OWN ESTATE - and then this lookup returns THEIR lead, months
            # old, carrying THEIR custom variables (`headline`, `location`)
            # and none of ours. Until 2026-09-23 this branch took that id and
            # attached it, and the variables were never written: our sequence
            # is a template of merge fields, so `{BODY_1}` resolved against
            # nothing and the provider sent `<p></p>`.
            #
            # Measured: 90 of the 91 foreign leads in campaigns 491-498 are
            # recorded in our own store as `bison_lead_id` on our own
            # contacts, and 85 of them are `sequence_finished` members of the
            # client's campaign 352.
            # `docs/INCIDENT-2026-09-23-BLANK-EMAILS.md`.
            #
            # So the copy is written HERE, before the lead can be attached,
            # and the `_verified` check below refuses if it did not land.
            bison.update_lead(row["id"], {"custom_variables": _variables_for(
                lead, campaign, sequence=plan.get("sequence") or [])})
            adopted += 1
            reconciled += 1
        remember_pairs.append((lead, row["id"]))
        ids.append(row["id"])
        _wanted_by_id[row["id"]] = lead
    _remember_leads(remember_pairs)
    _refuse_unvariabled_leads(ids, _wanted_by_id, campaign, plan, report)
    # FRESH READ, NOT ASSUMED FROM `_ensure_stopped` FOUR CALLS AGO.
    # The invariant that makes lead attachment safe is "the campaign is
    # stopped at the provider". `_ensure_stopped` established that earlier,
    # but the campaign's provider status is read from the provider, not
    # assumed from local state, so it is re-confirmed here immediately
    # before the attach. A campaign that became active between the two
    # reads - resumed by hand in the provider UI, or by another process -
    # is caught here rather than discovered from a readback that agrees
    # with a send already in flight.
    #
    # SKIPPED WHEN `_ensure_stopped` DELIBERATELY LEFT THE CAMPAIGN RUNNING.
    # Re-staging a live campaign reconciles material but does not stop the
    # send - that is a deliberate design choice, not a race. The fresh read
    # is there to catch a STATUS CHANGE between the two calls, not a status
    # that was already active when `_ensure_stopped` saw it. The
    # `left_running` flag in the report records that `_ensure_stopped`
    # chose not to stop it, so the fresh read would be asking the wrong
    # question.
    if not report.get("provider", {}).get("left_running"):
        pre_attach_status = str(bison.campaign(provider_id).get("status") or
                                "").lower()
        if pre_attach_status in bison.STARTED_STATES or pre_attach_status in bison.STARTING_STATES:
            raise FactoryRefused(
                f"EmailBison campaign {provider_id} is {pre_attach_status} "
                f"and leads were about to be attached to a running campaign. "
                f"Refusing: a lead attached to an active campaign is acted "
                f"on immediately")
    outcome = bison.attach_leads(provider_id, ids)
    report["provider"]["attached"] = outcome
    # Counted, not just narrated. Which PATH found each lead matters: the
    # remembered id is authoritative, while reconciliation leans on a provider
    # search that lags behind creation. A run that quietly stopped using the
    # first and started relying on the second would still avoid duplicates -
    # and would be one indexing delay away from not avoiding them.
    report["provider"]["leads"] = {"created": created, "reused": len(known),
                                   "reconciled": reconciled,
                                   "refreshed": refreshed,
                                   # Adopted from an address that already
                                   # existed - usually the CLIENT's own
                                   # estate. Counted separately because it is
                                   # the path that crossed a lane.
                                   "adopted": adopted}
    report["did"].append(
        f"created {created} lead(s), reused {len(known)}, reconciled "
        f"{reconciled}; attached {len(outcome['attached'])}, "
        f"{len(outcome['already'])} already present, "
        f"{outcome['count']} in campaign now")
    # The SIZE before and after, not a list of members: the campaign lead
    # route serves fifteen rows however many the campaign holds, so a list
    # here was a page pretending to be a membership.
    report["provider"]["leads_before"] = before
    _refuse_blank_render(provider_id, report)


def _refuse_unvariabled_leads(ids, wanted_by_id, campaign, plan, report):
    """NEVER ATTACH A LEAD WHOSE COPY IS NOT ALREADY ON IT.

    OPERATOR DECISION 2026-09-23, the structural half of the incident fix.
    Set the variables first, READ THE LEAD BACK, and only then attach.

    WHY AN INVARIANT OVER ALL IDS AND NOT A FIX TO ONE BRANCH. The adoption
    branch is the one that did this, and fixing it there is necessary and not
    sufficient: `ids` is assembled from three paths - remembered, created,
    adopted - and the property that matters is about what goes on the wire,
    not about which branch put it there. A fourth path added later inherits
    this check instead of having to remember the lesson.

    IT READS THE PROVIDER. The write we are guarding against is one where our
    PATCH was accepted and did not take, and our own copy of what we sent
    cannot see that. The read is per lead touched this run, not per lead in
    the campaign: leads already carrying their copy from an earlier stage are
    not re-read, so a 300-lead re-stage does not pay 300 GETs to re-prove a
    property nothing changed.

    A REFUSAL HERE LEAVES LEADS CREATED AND UNATTACHED, which is the safe
    direction and is stated so nobody 'fixes' it: an unattached lead sends
    nothing to anybody, while an attached one is in a campaign's queue within
    the minute.
    """
    from . import emptyrender
    sequence = plan.get("sequence") or []
    unverified = []
    for lead_id in ids:
        lead = wanted_by_id.get(lead_id)
        if lead is None:
            # Not staged by this run: it was already on the campaign and
            # nothing here changed it. Naming it rather than passing it
            # silently, because "we did not look" is not "it is fine".
            unverified.append((lead_id, "not staged by this run"))
            continue
        wanted = {v["name"]: v["value"]
                  for v in _variables_for(lead, campaign, sequence=sequence)}
        held = bison.variables_of(bison.lead(lead_id))
        for name, value in sorted(wanted.items()):
            if held.get(name) != value:
                unverified.append((lead_id, f"{name} did not take"))
                break
        else:
            # And the copy itself must be sendable, by the SAME predicate the
            # queue is judged by - not by a truthiness check, which is what
            # let `'None'` through.
            body = held.get("body_1") or held.get("body") or ""
            fault = emptyrender.classify_body(body)
            if fault:
                unverified.append((lead_id, f"body_1 is {fault}"))

    report.setdefault("provider", {})["leads_variable_verified"] = (
        len(ids) - len(unverified))
    if unverified:
        detail = "; ".join(f"lead {i}: {w}" for i, w in unverified[:5])
        raise FactoryRefused(
            f"{len(unverified)} of {len(ids)} lead(s) would be attached "
            f"without their copy on them: {detail}"
            f"{' and more' if len(unverified) > 5 else ''}. A lead attached "
            f"without `subject_1`/`body_1` renders the sequence template "
            f"against nothing and the provider SENDS the empty result - it "
            f"did so 76 times on 2026-09-22/23. Nothing was attached")


def _refuse_blank_render(provider_id, report):
    """Control (a): read back what the provider WILL SEND, and refuse a blank.

    OPERATOR DECISION 2026-09-23, the incident gate. Refuse any push where a
    step for any lead would send an empty, `"None"` or placeholder subject or
    body - verified by reading the provider's own rendered queue rather than
    by checking what we intended to send.
    `docs/INCIDENT-2026-09-23-BLANK-EMAILS.md`.

    WHY THE RENDERED ROW AND NOT OUR OWN MATERIAL. Every other guard in this
    file inspects `wanted` - the leads we are staging - and each one of them
    passed while 76 blank emails went out, because 73 of those went to leads
    this factory never created and had no reason to look at. And the three
    that WERE ours carry correct copy to this day: they were patched up to 54
    minutes after the empty row had already been queued and sent, because the
    render is a snapshot and patching a lead does not rebuild it. There is
    exactly one object that answers "what will this person receive", and it
    is the queue row.

    IT REPORTS HOW MANY ROWS IT CHECKED, AND ZERO IS NOT A PASS.

    A campaign is paused while it is staged, and the provider may not have
    built the queue yet - so this can legitimately find nothing to look at.
    That is a different fact from "every row is fine", and conflating the two
    is how a guard becomes ceremony: it would report clean on every push, for
    ever, and nobody would know. So `blank_render_checked` carries the row
    count and `blank_render_verified` is False when it is zero. The live
    window is covered by the watcher check, which is control (b) and is not
    optional precisely because this one can come up empty.
    """
    from . import emptyrender
    try:
        rows = bison.scheduled_emails(
            provider_id, cap=bison.CAMPAIGN_QUEUE_PAGE_CAP) or []
    except Exception as exc:                                  # noqa: BLE001
        # A queue that cannot be read is not a queue that is fine. Refusing
        # costs a re-run; assuming costs an empty email.
        raise FactoryRefused(
            f"the rendered queue for EmailBison campaign {provider_id} could "
            f"not be read ({type(exc).__name__}: {str(exc)[:160]}), so what "
            f"it would send cannot be verified. Refusing the push: an "
            f"unreadable queue is the state the blank-email incident was "
            f"invisible in") from None

    found = emptyrender.scan(rows)
    provider = report.setdefault("provider", {})
    provider["blank_render_checked"] = len(rows)
    provider["blank_render_verified"] = bool(rows)
    offending = found["pending"] + found["already"]
    if not offending:
        report.setdefault("did", []).append(
            f"read back {len(rows)} rendered queue row(s): none empty"
            if rows else
            "rendered queue is EMPTY - nothing was verified, and the watcher "
            "check is what covers this campaign once the provider builds it")
        return

    reasons = sorted({f"{f}/{r}" for e in offending for f, r in e["faults"]})
    steps = sorted({str(e["step"]) for e in offending if e.get("step")})
    raise FactoryRefused(
        f"{len(offending)} of {len(rows)} rendered queue row(s) on EmailBison "
        f"campaign {provider_id} would send nothing a person can read - "
        f"steps {','.join(steps) or '?'}, {', '.join(reasons)} "
        f"({len(found['pending'])} still sendable). This is read from the "
        f"PROVIDER's own rendered queue, not from our material, and it is the "
        f"check that 76 blank emails got past on 2026-09-22/23. Fix the "
        f"lead variables and re-stage; do not activate this campaign")


def _ensure_stopped(provider_id, report, by="system"):
    """Stop the campaign BEFORE it holds anybody. Do not stop a running one.

    A campaign this factory builds must not be able to send, so it is paused -
    that part is unchanged, and the factory still never STARTS anything. What
    changed is when: the pause now happens before the leads are attached, and
    `stage` says why.

    What it must not do is pause a campaign that is ALREADY LIVE. Re-staging
    is routine: it reconciles copy, limits and membership, and it is run again
    whenever a draft changes. Pausing unconditionally meant a routine re-stage
    silently stopped a running campaign - measured on 2026-09-13, when the
    duplicate-refusal check re-staged the authorised canary and suspended the
    send it had just committed. Nothing raised, because pausing looks like the
    safe direction.

    Stopping a live campaign is a decision somebody takes on purpose, through
    `orchestrator.pause`, which records who and why. It is not a side effect
    of reconciling a draft.

    AND "NOT DRAFT OR PAUSED" IS NOT THE SAME AS "RUNNING". That test reported
    a campaign the provider had marked `failed` as LEFT RUNNING - an operator
    reading that line would believe a dead campaign was sending. The statuses
    this instance actually uses are enumerated in `bison`, so they are
    classified here rather than divided into one name and everything else.
    """
    status = str(bison.campaign(provider_id).get("status") or "").lower()
    if status in bison.STARTED_STATES or status in bison.STARTING_STATES:
        report["did"].append(
            f"campaign is {status} and was LEFT RUNNING: re-staging "
            f"reconciles material, it does not stop a live campaign. Use "
            f"orchestrator.pause to stop it")
        report["provider"]["left_running"] = True
        return
    if status in bison.FAILED_STATES:
        # It is not sending and it is not a campaign this factory built into
        # shape either. Pausing it below is honest - it cannot send afterwards
        # and it could not before - but the reason it is here has to survive
        # into the report, because `failed` means the provider refused to
        # start it and a staged-looking readback would hide that.
        report["provider"]["provider_failed"] = True
        report["did"].append(
            f"campaign reads {status}: the provider tried to start it and "
            f"gave up. It is NOT sending")
    state = bison.pause_campaign(provider_id)
    report["did"].append(f"campaign left {state['status']}")


def _readback(provider_id):
    """What the provider says is true, after everything above."""
    row = bison.campaign(provider_id)
    return {"id": row.get("id"), "name": row.get("name"),
            "status": row.get("status"),
            "leads": bison.campaign_lead_count(provider_id)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("campaign", help="a canonical campaign id")
    parser.add_argument("--live", action="store_true",
                        help="actually write to EmailBison")
    args = parser.parse_args(argv)
    try:
        report = stage(args.campaign, live=args.live)
    except (FactoryRefused, FactoryAmbiguous, ProviderError) as e:
        print(f"{type(e).__name__}: {e}")
        return 1
    for line in report["did"]:
        print(" ", line)
    print(" provider:", report["provider"].get("readback"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
