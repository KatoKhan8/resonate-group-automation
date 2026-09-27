"""The single truth for a generated campaign sequence.

Preview, the XLSX workbook, the approval hash, the EmailBison payload and the
HeyReach payload are projections of this plan. Each derives from it; none
re-implements it. If a projection needs a field the plan does not carry, the
field belongs in the plan.

TASK-369.

THE DIRECTION OF DERIVATION IS THE WHOLE POINT - TASK-364 REWORK 2
------------------------------------------------------------------

The plan is built FIRST, from STRATEGY (the cadence: which steps, which
channel, which day) and COPY (the client's declared templates and fallbacks).
Every provider payload is then a projection OF it. Never the other way round.

The second attempt at this task built the derivation backwards: it built each
provider's sequence first and then generated a "canonical plan" FROM the
result. Plan and payload could not disagree - one was made out of the other -
so a consistency test between them passed by construction and proved nothing,
and a mutation of the plan could not change either payload. That is worse
than dead code, because the system looks verified exactly where it is not.

So this module owns the construction, and the factories own nothing of it:

    strategy (cadence_steps) + copy (client config)
              |
              v
        for_campaign()  ->  ONE canonical SequencePlan
              |                        |
              v                        v
    derive_bison_sequence()   derive_heyreach_sequence()
    (EmailBison steps)        (the HeyReach graph)

`bisonfactory` and `heyreachfactory` call those two functions and build no
sequence of their own. A change to the plan therefore reaches both providers,
and a change that reaches only one is a bug either projection can be asked
about.
"""
import hashlib
import json

ENTRYPOINT_VERSION = "1"

# The HeyReach graph roles the LinkedIn projection fills, and the copy the
# plan must carry one fallback for. Canonical here rather than in the factory:
# a role is part of what the plan says, and `heyreachfactory.REQUIRED_ROLES`
# is an alias of this tuple rather than a second list that can drift from it.
LINKEDIN_ROLES = ("connection_note", "connected_1", "connected_2",
                  "connected_3", "connected_4", "message_2", "message_3",
                  "message_4")

# The client config key holding the per-role fallback copy HeyReach sends when
# a per-lead variable cannot be filled.
LINKEDIN_FALLBACK_KEY = "linkedin_sequence"

# How long a connection request stays outstanding before it is withdrawn.
DEFAULT_WITHDRAW_AFTER_DAYS = 21


class PlanRefused(Exception):
    """Strategy and copy do not agree, so there is no plan to project.

    The factories translate this into their own `FactoryRefused` so a caller
    sees one refusal type per entry point. The message is written once, here,
    because the disagreement is about the plan and not about a provider.
    """


def new(client_name, account, contacts, *, strategy=None, second_brain_facts=None,
        offers=None, cadence=None):
    """Build an empty SequencePlan skeleton.

    The caller fills per-contact sequences as generation proceeds. The
    top-level fields (client, account, strategy, facts, offers) are set once;
    the per-contact entries are the variable part.
    """
    return {
        "version": ENTRYPOINT_VERSION,
        "client": client_name,
        "account": {
            "company": account.get("company", ""),
            "domain": account.get("domain", ""),
        },
        "strategy": strategy or {},
        "second_brain_facts": second_brain_facts or [],
        "offers": offers or {},
        "cadence": cadence or {},
        "contacts": contacts if isinstance(contacts, list) else [],
    }


def approval_hash(plan):
    """A stable digest of everything the operator approved.

    Used by the execution guard to detect drift between what was approved and
    what the provider payload carries. Two plans with the same approval hash
    produce the same prospect-facing copy.
    """
    material = {
        "client": plan.get("client"),
        "account": plan.get("account"),
        "strategy_id": (plan.get("strategy") or {}).get("strategy_id"),
        "contacts": [],
    }
    for contact in plan.get("contacts") or []:
        material["contacts"].append({
            "email": contact.get("email"),
            "sequences": contact.get("sequences") or {},
            "subjects": contact.get("subjects") or {},
        })
    blob = json.dumps(material, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


def derive_preview_data(plan):
    """Extract the fields the preview page needs from the plan.

    Returns a dict shaped for `preview.gather`-like consumption. Every value
    is read from the plan; nothing is recomputed.
    """
    rows = []
    for contact in plan.get("contacts") or []:
        rows.append({
            "contact_key": contact.get("contact_key"),
            "email": contact.get("email"),
            "first_name": contact.get("first_name", ""),
            "company": plan.get("account", {}).get("company", ""),
            "qualification": contact.get("qualification"),
            "hypothesis": (contact.get("hypothesis") or {}).get("hypothesis"),
            "capability": (contact.get("match") or {}).get("capability_key"),
            "sequences": contact.get("sequences") or {},
            "subjects": contact.get("subjects") or {},
            "gate": contact.get("sequence_gate") or {},
        })
    return {
        "client": plan.get("client"),
        "account": plan.get("account"),
        "strategy": plan.get("strategy"),
        "rows": rows,
        "approval_hash": approval_hash(plan),
    }


def derive_bison_payload(plan):
    """Extract the EmailBison custom-variable payload from the plan.

    Each lead gets per-step subject and body merge fields. The sequence
    template is set at the campaign level.
    """
    leads = []
    for contact in plan.get("contacts") or []:
        if contact.get("qualification") in ("UNQUALIFIED", "INSUFFICIENT"):
            continue
        steps = []
        sequences = contact.get("sequences") or {}
        subjects = contact.get("subjects") or {}
        for key in ("em1", "em2", "em3", "em4", "em5"):
            body = sequences.get(key)
            if not body:
                continue
            subject_key = {"em1": "A", "em3": "B", "em5": "C"}.get(key, "")
            steps.append({
                "step_key": key,
                "subject": subjects.get(subject_key, ""),
                "body": body,
            })
        if steps:
            leads.append({
                "contact_key": contact.get("contact_key"),
                "email": contact.get("email"),
                "first_name": contact.get("first_name", ""),
                "steps": steps,
            })
    return {"leads": leads, "approval_hash": approval_hash(plan)}


def derive_heyreach_payload(plan):
    """Extract the HeyReach LinkedIn graph payload from the plan.

    Maps the cadence step keys (em1..em5, connect, msg1..msg3) to the graph
    roles HeyReach expects: connection_note, connected_1..4, message_2..4.
    """
    leads = []
    for contact in plan.get("contacts") or []:
        if contact.get("qualification") in ("UNQUALIFIED", "INSUFFICIENT"):
            continue
        sequences = contact.get("sequences") or {}
        li = {}
        for key in ("connect", "msg1", "msg2", "msg3"):
            text = sequences.get(key)
            if text:
                li[key] = text
        if li:
            leads.append({
                "contact_key": contact.get("contact_key"),
                "linkedin": li,
            })
    return {"leads": leads, "approval_hash": approval_hash(plan)}


# ===========================================================================
# THE CAMPAIGN-LEVEL PLAN: strategy x copy, built before anything else
# ===========================================================================
#
# `new()` above holds the WORDS - one entry per contact, written by
# `generate_campaign`. This half holds the SHAPE of the conversation: which
# steps run, on which day, in which channel, with which template, and how long
# each one waits. Both halves are the same plan; neither is derived from a
# provider payload, and a provider payload is derived from nothing else.
#
# WHAT `wait_in_days` MEANS, MEASURED RATHER THAN ASSUMED. It is the wait AFTER
# the step that carries it, before the next one - read off the client's own
# live campaign 352 on 2026-09-13 across 381 consecutive scheduled pairs whose
# two steps declare different waits. So a five-step cadence declares four
# meaningful waits and one that has no successor to be a wait before, and the
# last one is carried as declared and checked against nothing.


def for_campaign(campaign, config, *, cadence_steps=None,
                 withdraw_after_days=DEFAULT_WITHDRAW_AFTER_DAYS):
    """The canonical SequencePlan for one campaign. No leads, no provider call.

    `campaign` is a campaign row (or None, when a caller already resolved the
    cadence and only wants the shape). `config` is the client config: the copy
    templates live in `email_sequence` and `linkedin_sequence`.

    Built from two inputs and nothing else:

      * STRATEGY - `cadence_steps`, the steps this campaign declared. Resolved
        through `cadence.steps_for` when the caller does not pass them, which
        is the same resolution every other reader of the cadence uses.
      * COPY - the client's declared templates: per-step subject and body for
        email, per-role fallbacks for LinkedIn.

    Raises `PlanRefused` when the two disagree - a declared step the cadence
    does not have, a wait that does not reproduce the cadence gap, a follow-up
    carrying its own subject. Those are plan-level facts: they are true before
    any provider is named, so they are decided here rather than twice.

    MISSING LINKEDIN FALLBACKS ARE RECORDED, NOT REFUSED. An email-only
    campaign for a client who declared no LinkedIn copy must still stage, and
    it did before this module existed. So the absence is carried in the plan
    (`linkedin.missing_fallbacks`) and only `derive_heyreach_sequence` - the
    projection that cannot be built without them - refuses. One plan, built
    the same way for both channels; the projection that needs a thing is the
    one that insists on it.
    """
    config = config or {}
    if cadence_steps is None:
        # Deferred: `cadence` imports the campaign machinery, which reaches
        # back here through the factories.
        from . import cadence as _cadence

        cadence_steps = _cadence.steps_for(campaign, config=config)
    cadence_steps = list(cadence_steps or ())

    email_config = config.get("email_sequence") or {}
    # THE REFUSAL IS CARRIED, NOT SWALLOWED, for the same reason a missing
    # LinkedIn fallback is: a campaign whose LinkedIn half is correct must not
    # be stopped by an email block it never sends, and it was not before this
    # module existed. So a disagreement between the cadence and the declared
    # email copy is recorded here and raised by `derive_bison_sequence` - the
    # projection that cannot be built without those steps, and the only one
    # that reaches EmailBison. Nothing can produce an email payload from a
    # plan carrying this string.
    try:
        steps = _email_steps(email_config, cadence_steps)
        email_refused = None
    except PlanRefused as refusal:
        steps, email_refused = [], str(refusal)
    # WHICH OF THE TWO DECLARED SHAPES THIS IS. The multi-step shape is the
    # only one checked against the cadence, so it is the only one a provider's
    # step ceiling applies to - a single-step campaign carries one step whatever
    # the cadence says, and campaign 451 is staged that way. Recorded rather
    # than re-derived, because a projection asking "was a `steps` block
    # declared" would be reading the config a second time.
    declared_block = email_config.get("steps")
    if isinstance(declared_block, dict) and declared_block:
        email_shape = "steps"
    elif steps:
        email_shape = "single"
    else:
        email_shape = "none"

    linkedin_steps = _linkedin_steps(cadence_steps)
    steps.extend(linkedin_steps)

    # THE SAME RULE ON THIS SIDE: a LinkedIn disagreement is carried and raised
    # by the LinkedIn projection. A cadence whose message days leave no room
    # between two messages is a real refusal - a node delay below a day sends
    # both at once - but it is not a reason to stop an email stage that has
    # nothing to do with it.
    delays, delays_from, linkedin_refused = None, None, None
    try:
        delays = _message_delays(linkedin_steps)
        delays_from = "campaign_cadence"
    except PlanRefused as refusal:
        linkedin_refused = str(refusal)
    if delays is None and linkedin_refused is None:
        # THE SUBSTITUTION IS RECORDED RATHER THAN SILENT. The HeyReach graph
        # carries four messages per branch, so it needs three inter-message
        # gaps; a cadence that does not describe five LinkedIn steps cannot
        # supply them. Every campaign whose cadence does describe them drives
        # the graph from its own days, which is the behaviour this task adds -
        # the delays used to come from the library constant whatever the
        # campaign said. A cadence that cannot supply them lands on the
        # canonical ladder, exactly as it did before, and the plan says so.
        from . import cadencelibrary

        delays = _message_delays(
            _linkedin_steps(cadencelibrary.PRODUCTIVE_LI_HEAVY_V1))
        delays_from = "canonical_ladder"

    linkedin_copy, missing_fallbacks = _linkedin_copy(config)

    return {
        "version": ENTRYPOINT_VERSION,
        "client": (campaign or {}).get("client") or config.get("name") or "",
        "campaign_id": (campaign or {}).get("campaign_id"),
        "cadence_steps": cadence_steps,
        "steps": steps,
        "email": {"title": email_config.get("title") or "",
                  "shape": email_shape,
                  "refused": email_refused},
        "linkedin": {
            "copy": linkedin_copy,
            "missing_fallbacks": missing_fallbacks,
            # None, never a substituted number, when the cadence's own days
            # were refused: a plan does not carry delays it rejected, and the
            # projection raises before anything could read them.
            "message_delays": list(delays) if delays else None,
            "delays_from": delays_from,
            "refused": linkedin_refused,
            "withdraw_after_days": int(withdraw_after_days),
        },
    }


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


def _email_steps(configured, cadence_steps):
    """The plan's email steps: the cadence's shape carrying the client's copy.

    TWO SHAPES, AND THE OLD ONE IS NOT DEPRECATED. A client naming `subject`,
    `body` and `wait_in_days` directly gets the single step it always got -
    that is what EmailBison campaign 451 carries and it is production
    evidence. A client naming a `steps` block gets one step per entry, keyed
    BY CADENCE STEP KEY.

    THE KEY IS THE WHOLE POINT. `em1: {...}` does not mean "the first step", it
    means "the step `cadencelibrary` calls em1", and that is what lets the
    declared delays be checked against the cadence instead of trusted. A
    `steps` block naming keys the cadence does not have, or missing keys it
    does, is refused: the alternative is a provider sending five emails on a
    schedule the cadence never described, with every readback agreeing.

    THE DELAYS ARE DECLARED AND VERIFIED, NOT DERIVED. `CAMPAIGN-FACTORY.md`
    is explicit that a provider node delay is declared, because the cadence
    day is a position in a schedule and a node delay is a property of the
    provider graph - two different quantities that happen to agree. Deriving
    one from the other would hide the day they stop agreeing.

    THE LAST STEP'S WAIT IS NOT CHECKED, because there is nothing after it to
    wait for. A five-step cadence defines four gaps.
    """
    configured = configured or {}
    block = configured.get("steps")
    if not isinstance(block, dict) or not block:
        if not (configured.get("subject") and configured.get("body")):
            return []
        # The single-step shape declares no cadence key and no threading:
        # there is nothing after it to thread onto. `step_key` is None so the
        # provider projection omits both fields, which is the payload campaign
        # 451 is staged against.
        return [{"step_key": None, "channel": "email", "day": None,
                 "order": 1,
                 "subject": configured["subject"],
                 "body": configured["body"],
                 "wait_in_days": configured.get("wait_in_days") or 3,
                 "thread_reply": None}]

    # The cadence's email steps, in the order the cadence runs them. `day` is
    # the position; equal days are legal (day 1 carries both channels) and the
    # key breaks the tie so the order is total rather than merely sorted.
    email_days = [(s.get("day"), s.get("key")) for s in cadence_steps or ()
                  if s.get("channel") == "email" and s.get("key")]
    email_days.sort(key=lambda pair: (pair[0], pair[1]))
    if not email_days:
        raise PlanRefused(
            "`email_sequence.steps` names a multi-step sequence and the "
            "client's cadence carries no email steps at all, so there is "
            "nothing to check the declared delays against. A sequence nobody "
            "can check is a sequence nobody knows the shape of")

    wanted = [key for _day, key in email_days]
    declared = sorted(block, key=lambda k: _order_of(block[k], k))
    if declared != wanted:
        raise PlanRefused(
            f"`email_sequence.steps` declares {declared} and the cadence's "
            f"email steps are {wanted}. These must be the same keys in the "
            f"same order: the key is how a declared delay is matched to the "
            f"cadence gap it claims to reproduce, so a mismatch means the "
            f"delays were checked against the wrong steps or against none")

    thread_pattern = _thread_pattern(configured, cadence_steps)

    steps = []
    for position, (day, key) in enumerate(email_days, start=1):
        entry = block[key] or {}
        subject, body = entry.get("subject"), entry.get("body")
        if not subject or not body:
            raise PlanRefused(
                f"`email_sequence.steps.{key}` declares no "
                f"{'subject' if not subject else 'body'}. A step staged "
                f"without one sends an email that has none")
        wait = entry.get("wait_in_days")
        if wait is None:
            raise PlanRefused(
                f"`email_sequence.steps.{key}` declares no `wait_in_days`. "
                f"EmailBison takes whatever it defaults to, and 'nobody "
                f"chose' must not look the same as a chosen delay")
        # Every gap but the last, against the cadence that defines it.
        if position < len(email_days):
            gap = email_days[position][0] - day
            if int(wait) != int(gap):
                raise PlanRefused(
                    f"`email_sequence.steps.{key}` declares a "
                    f"{int(wait)}-day wait and the cadence puts {key} on day "
                    f"{day} and {email_days[position][1]} on day "
                    f"{email_days[position][0]}, a gap of {gap}. `wait_in_days` "
                    f"is the wait AFTER a step - measured on campaign 352, see "
                    f"the note above - so this campaign would send on a "
                    f"schedule the cadence does not describe")
        tr = thread_pattern[position - 1] if position <= len(thread_pattern) \
            else False
        steps.append({"step_key": key, "channel": "email", "day": day,
                      "order": position,
                      "subject": subject,
                      "body": body,
                      "wait_in_days": int(wait),
                      "thread_reply": bool(tr)})

    # THREAD-REPLY INVARIANT: only the opener owns a subject. When the
    # sequence has at least one threaded follow-up, every follow-up must
    # either be threaded or reference the opener's subject. A mixed shape
    # - some follow-ups threaded, others opening new threads with their own
    # subjects - violates the invariant and is refused.
    if len(steps) > 1 and any(s["thread_reply"] for s in steps[1:]):
        opener_subject = steps[0]["subject"]
        for step in steps[1:]:
            if not step["thread_reply"] and step["subject"] != opener_subject:
                raise PlanRefused(
                    f"step {step['order']} is not a thread reply but "
                    f"carries a distinct subject "
                    f"({step['subject']!r} vs opener "
                    f"{opener_subject!r}). Only the opener owns a "
                    f"subject; follow-ups must be thread replies "
                    f"referencing the opener's subject. Set thread_reply "
                    f"to true or change the subject to match the opener")
    return steps


def _thread_pattern(configured, cadence_steps):
    """Whether each email step is a same-thread follow-up, in cadence order.

    The client config's `email_sequence.thread_reply_pattern` wins when
    present: it is the per-client override TASK-080 needs. When absent, the
    ladder's default pattern is used. When the ladder has none, every step is
    a new thread (all False).
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


def _linkedin_steps(cadence_steps):
    """The plan's LinkedIn steps, in the order the cadence runs them."""
    found = [s for s in cadence_steps or ()
             if isinstance(s, dict) and s.get("channel") == "linkedin"
             and s.get("key") and s.get("day") is not None]
    found.sort(key=lambda s: (s["day"], s["key"]))
    return [{"step_key": s["key"], "channel": "linkedin", "day": s["day"],
             "order": position, "action": s.get("linkedin_action")}
            for position, s in enumerate(found, start=1)]


def _message_delays(linkedin_steps):
    """Days between consecutive LinkedIn MESSAGE steps, or None.

    The graph's two branches each carry four messages, so it needs exactly
    three inter-message gaps::

        d1 = li3.day - li2.day   (connected_1 -> connected_2)
        d2 = li4.day - li3.day   (connected_2 -> connected_3)
        d3 = li5.day - li4.day   (connected_3 -> connected_4)

    The first step is the invite and is not a gap. Returns None when the steps
    cannot supply exactly three - the caller decides what to do about that -
    and raises `PlanRefused` when they can but one of them is not a real wait:
    a provider node whose delay is zero or negative sends two messages at once
    to the same person, and "the cadence said so" is not a defence.
    """
    days = [s["day"] for s in linkedin_steps or ()]
    # One invite plus four messages. Three gaps, and any other count cannot
    # describe this graph.
    if len(days) != 5:
        return None
    gaps = tuple(days[i + 1] - days[i] for i in range(1, len(days) - 1))
    for position, gap in enumerate(gaps, start=1):
        if int(gap) < 1:
            raise PlanRefused(
                f"the cadence puts LinkedIn message {position} and message "
                f"{position + 1} {gap} days apart, and a message node with a "
                f"delay below one day sends both to the same person at once. "
                f"Fix the cadence days rather than the graph")
    return tuple(int(g) for g in gaps)


def _linkedin_copy(config):
    """The role-keyed copy block the GRAPH carries: variables, never words.

    Returns `(block, missing)`. `block` is None when any role's fallback is
    missing, because a partial block cannot build a graph and a half-built one
    would look like a whole one to a reader.

    The graph is campaign-level - one graph serves every lead - so it may not
    contain anything true of only one person. Each role's message is the merge
    variable `{role}` and the words travel per lead in `customUserFields`.

    THE FALLBACK IS THE CLIENT'S OR IT IS MISSING. HeyReach sends
    `fallbackMessage` whenever a per-lead variable cannot be filled, so a
    fallback invented here would be unapproved copy that this system wrote and
    nobody read, reaching a real person at the moment something has already
    gone wrong.
    """
    configured = ((config or {}).get(LINKEDIN_FALLBACK_KEY) or {}).get(
        "fallbacks") or {}
    block, missing = {}, []
    for role in LINKEDIN_ROLES:
        fallback = str(configured.get(role) or "").strip()
        if not fallback:
            missing.append(role)
            continue
        block[role] = {"messages": ["{" + role + "}"],
                       "fallbackMessage": fallback}
    if missing:
        return None, sorted(missing)
    return block, []


# ------------------------------------------------- the provider projections


def derive_bison_sequence(plan, *, max_steps=None):
    """The EmailBison sequence template, projected from the plan's email steps.

    One provider step per plan email step, in cadence order. `max_steps` is
    how many pairs of copy variables the provider declares: a cadence longer
    than that would send steps with nothing in them, and it is a property of
    the provider rather than of the plan, so it is checked here.

    A follow-up step STILL CARRIES `email_subject` - the thread_reply flag is
    the mechanism, not subject omission. The provider stores both.
    """
    email = plan.get("email") or {}
    # THE CEILING IS CHECKED FIRST, AND AGAINST THE CADENCE. A cadence longer
    # than the provider has copy variables for is the more fundamental problem:
    # the steps past the ceiling would send with nothing in them and every
    # readback would agree. It is counted off the cadence rather than off the
    # built steps because the build may have refused for a smaller reason -
    # one step's declared wait, say - and the operator needs to be told about
    # the ceiling before being sent to fix a delay on a sequence that cannot
    # be staged at any delay. This is the order the check has always fired in.
    if max_steps is not None and email.get("shape") == "steps":
        declared = [s for s in plan.get("cadence_steps") or []
                    if isinstance(s, dict) and s.get("channel") == "email"
                    and s.get("key")]
        if len(declared) > int(max_steps):
            raise PlanRefused(
                f"the cadence carries {len(declared)} email steps and only "
                f"{int(max_steps)} pairs of copy variables are declared "
                f"at the provider, so steps past the "
                f"{int(max_steps)}th would send with nothing in them. "
                f"Raise `MAX_SEQUENCE_STEPS` and re-run "
                f"`ensure_custom_variables` before lengthening the cadence")
    refused = email.get("refused")
    if refused:
        raise PlanRefused(refused)
    steps = [s for s in plan.get("steps") or []
             if s.get("channel") == "email"]
    if max_steps is not None and len(steps) > int(max_steps):
        raise PlanRefused(
            f"the cadence carries {len(steps)} email steps and only "
            f"{int(max_steps)} pairs of copy variables are declared "
            f"at the provider, so steps past the "
            f"{int(max_steps)}th would send with nothing in them. "
            f"Raise `MAX_SEQUENCE_STEPS` and re-run "
            f"`ensure_custom_variables` before lengthening the cadence")
    out = []
    for step in steps:
        node = {"order": step["order"],
                "email_subject": step["subject"],
                "email_body": step["body"],
                "wait_in_days": int(step["wait_in_days"])}
        if step.get("step_key"):
            node["step_key"] = step["step_key"]
            node["thread_reply"] = bool(step.get("thread_reply"))
        out.append(node)
    return out


def derive_heyreach_sequence(plan, *, include_inmail=False):
    """The HeyReach graph, projected from the plan. Returns `(graph, report)`.

    Every number in the graph comes from the plan: the message delays from the
    cadence's LinkedIn days, the withdrawal window and the per-role copy from
    the plan's LinkedIn block. Nothing here reads a cadence, a client config or
    a library constant of its own.
    """
    linkedin = plan.get("linkedin") or {}
    refused = linkedin.get("refused")
    if refused:
        raise PlanRefused(refused)
    copy = linkedin.get("copy")
    if not copy:
        missing = linkedin.get("missing_fallbacks") or []
        raise PlanRefused(
            f"this client declares no LinkedIn fallback copy for "
            f"{', '.join(sorted(missing))}. HeyReach sends `fallbackMessage` "
            f"whenever a per-lead variable cannot be filled, so a graph "
            f"without one would reach a real person as a blank - and a "
            f"fallback invented here would be words nobody approved. Declare "
            f"them under `{LINKEDIN_FALLBACK_KEY}.fallbacks` in the client "
            f"config")
    return heyreach_graph(
        copy,
        message_delays=linkedin.get("message_delays"),
        withdraw_after_days=linkedin.get("withdraw_after_days",
                                         DEFAULT_WITHDRAW_AFTER_DAYS),
        include_inmail=include_inmail)


def canonical_message_delays():
    """The canonical ladder's inter-message gaps, for a caller with no plan."""
    from . import cadencelibrary

    return _message_delays(
        _linkedin_steps(cadencelibrary.PRODUCTIVE_LI_HEAVY_V1))


def heyreach_graph(copy, *, message_delays=None,
                   withdraw_after_days=DEFAULT_WITHDRAW_AFTER_DAYS,
                   include_inmail=False):
    """The LinkedIn graph for one role-keyed copy block. THE ONLY BUILDER.

    Returns `(sequence, touch_report)`. `message_delays` is the three-tuple
    `derive_heyreach_sequence` reads off the plan; a caller that has no plan -
    a preview of one contact's copy, a test of the graph shape - gets the
    canonical ladder's gaps rather than a number this function chose.

    WITHOUT INMAIL, THE GRAPH CHANGES IN TWO PLACES:

    1. The not-accepted branch: instead of VIEW -> INMAIL -> END, it becomes
       VIEW -> END. The profile view remains as a warm-up; the InMail is gone.
    2. The open-profile branch: instead of INMAIL -> CONNECT -> ..., it becomes
       the same as the cold path. CHECK_IS_OPEN_PROFILE is kept (it is free and
       the provider supports it) but both branches lead to the same cold path.

    `INMAIL_ELIGIBILITY_DETECTABLE` is False, so an InMail is attempted rather
    than targeted and no InMail copy is ever approved - which is why omitting
    it is the default and including it is the caller's explicit request.
    """
    # Deferred: the provider module carries the transport, and the generation
    # entrypoint imports this module. A plan is not a reason to import a
    # socket.
    from .providers import heyreach

    if message_delays is None:
        message_delays = canonical_message_delays()
    d1, d2, d3 = (int(d) for d in message_delays)

    if include_inmail:
        sequence = heyreach.linkedin_sequence(
            copy, withdraw_after_days=int(withdraw_after_days),
            message_delays=(d1, d2, d3))
        inmail_present = True
    else:
        sequence = _graph_without_inmail(
            heyreach, copy, (d1, d2, d3), int(withdraw_after_days))
        inmail_present = False

    nodes, types, _truncated = heyreach.walk_sequence(sequence)
    messages = sum(1 for n in nodes
                   if str(n.get("nodeType") or "") in ("MESSAGE", "INMAIL",
                                                       "CONNECTION_REQUEST"))
    return sequence, {
        "nodes": len(nodes),
        "message_nodes": messages,
        "inmail": inmail_present,
        "node_types": sorted(types),
    }


def _graph_without_inmail(heyreach, copy, delays, withdraw_after_days):
    """The LinkedIn-primary graph with no InMail nodes."""
    d1, d2, d3 = delays

    def end(delay=3, unit="HOUR"):
        return heyreach._node("END", delay, unit)

    def chain(copy_block):
        return heyreach._node(
            "MESSAGE", 3, "HOUR", heyreach._copy("message_2", copy_block),
            nxt=heyreach._node("VIEW_PROFILE", d1, "DAY",
                nxt=heyreach._node(
                    "MESSAGE", d2, "DAY",
                    heyreach._copy("message_3", copy_block),
                    nxt=heyreach._node(
                        "MESSAGE", d3, "DAY",
                        heyreach._copy("message_4", copy_block),
                        nxt=end()))))

    invite = heyreach._copy("connection_note", copy)
    invite["toBeWithdrawnAfterDays"] = int(withdraw_after_days)

    # Not-accepted: view, then end. No InMail.
    not_accepted = heyreach._node("VIEW_PROFILE", 5, "DAY", nxt=end())

    ask_to_connect = heyreach._node(
        "CONNECTION_REQUEST", 1, "DAY", dict(invite),
        nxt=not_accepted, cond=chain(copy))

    # Cold path: view, follow, connect. Same for open and non-open profiles.
    cold_path = heyreach._node(
        "VIEW_PROFILE", 3, "HOUR",
        nxt=heyreach._node("FOLLOW", 3, "HOUR", nxt=ask_to_connect))

    # The already-connected branch. The VIEW_PROFILE between connected_2
    # and connected_3 is a real action (re-viewing the prospect) with a
    # fixed 2-day delay. The MESSAGE delays compensate so that the total
    # time between consecutive messages matches the cadence:
    #   connected_2 -> connected_3 = VIEW_PROFILE(2d) + MESSAGE(d2-2d) = d2
    #   connected_3 -> connected_4 = MESSAGE(d3) = d3
    already = heyreach._node(
        "MESSAGE", 3, "HOUR", heyreach._copy("connected_1", copy),
        nxt=heyreach._node("MESSAGE", d1, "DAY",
                           heyreach._copy("connected_2", copy),
            nxt=heyreach._node("VIEW_PROFILE", 2, "DAY",
                nxt=heyreach._node("MESSAGE", max(d2 - 2, 1), "DAY",
                    heyreach._copy("connected_3", copy),
                    nxt=heyreach._node("MESSAGE", d3, "DAY",
                        heyreach._copy("connected_4", copy),
                        nxt=end())))))

    sequence = heyreach._node("CHECK_IS_CONNECTION", 0, "HOUR",
                              cond=already, nxt=cold_path)
    heyreach.validate_sequence_for_write(sequence)
    return sequence
