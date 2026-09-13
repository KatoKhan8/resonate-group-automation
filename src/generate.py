#!/usr/bin/env python3
"""The LLM steps. BUILD-SPEC phase 5, prompt contracts in section 8.

Deterministic work happens here; only the reasoning happens in the model. The
context handed to a prompt is assembled from trimmed record fields, never from
a provider payload, and it is small on purpose (section 9, trap 8).

WHICH EMAILS ARE GENERATED IS THE CLIENT'S SEQUENCE, not a constant. This
said "day 1 and day 15" and had not been true since `productive_li_heavy_v1`
became Productive's cadence: that sequence generates all five of `em1`..`em5`,
which is what `plan` actually asks for. The count matters for cost, so a
stale one here is a stale estimate everywhere it is quoted.

A generated draft is linted before it is stored. A draft that breaks a rule is
regenerated, never patched, and never widened away (CLAUDE.md).

  python -m src.generate                dry run: what would be asked, and of what
  python -m src.generate --live         uses the model in config/.env, and
                                        refuses rather than holding records
                                        when none is configured
"""
import argparse
import os

from . import claims, clients, events, lint, llm, research, store


def cadence_note_words():
    """The cross channel word list, imported late to avoid a cycle."""
    from .cadence import NOTE_MENTIONS_EMAIL
    return NOTE_MENTIONS_EMAIL
from .providers import ProviderError, contactout

PROMPTS = os.path.join(store.ROOT, "prompts")

GENERATED_DAYS = ("day1", "day15")
MAX_DRAFT_ATTEMPTS = 3

# --------------------------------------------------------- the step ladder
#
# EVERY STEP HAS A DIFFERENT JOB, AND THE PROMPT IS TOLD WHICH ONE.
#
# Without this the only thing distinguishing message four from message one is
# the model's own appetite for variety, and what came back was four
# paraphrases of the same pitch - the failure the operator named. A cadence is
# not one argument repeated at intervals; it is several arguments, each of
# which is the reason THIS message exists.
#
# Keyed on the step's ORDINAL WITHIN ITS CHANNEL rather than on its key,
# because step keys belong to the sequence and the sequence is configuration:
# `cadence.STEPS` spells them `day1`/`day15`, `cadencelibrary` spells the same
# shape `em1`..`em5` and `li1`..`li6`, and a campaign may carry its own. The
# second email is the second email whatever it is called.
#
# These are jobs, not wording. Nothing here is a sentence a prospect ever
# sees, and none of it licenses a claim: the evidence rung below says what
# kind of thing to reach for, never that we have one.
EMAIL_LADDER = (
    "Relevance. Why you are writing to THIS person at THIS company, in their "
    "own operational language. One question they can answer in a line.",
    "A different angle from the first email. Not the same argument rephrased: "
    "a different part of how the business runs, and a different question.",
    "New value. One concrete use case or consequence a team their size would "
    "recognise, and what changes when it is visible rather than reconstructed.",
    "A short bump that makes a DIFFERENT argument from every email before it. "
    "Shortest message in the sequence. One idea, one question, no recap.",
    "Close the loop. Give them an easy no, make no new pitch, ask for nothing "
    "beyond permission to stop.",
)

# Rung one is the CONNECTION REQUEST, which is a different object from a
# message: it has no subject, it is read beside a profile photo, and asking a
# question that needs thought in it is how it gets ignored. Rungs two onward
# are messages to somebody who accepted.
LINKEDIN_LADDER = (
    "A connection request note. One line on why you are writing to them "
    "specifically, in the operational language of their angle. No ask beyond "
    "connecting, and no question that needs a considered answer.",
    "A short first message. One operational angle, put as a question about "
    "how they handle it today. Different words and a different angle from the "
    "connection note.",
    "A second, different operational angle. Name the consequence of not "
    "having it rather than the feature that provides it.",
    "The use case. What a team their size actually changed, and what it was "
    "costing them before. This is the rung where evidence belongs, if there "
    "is any; if there is none, describe the pattern as ours rather than "
    "theirs.",
    "A concise final follow-up. One line, one question, no new argument and "
    "no summary of the previous ones.",
    "Close the loop. An easy no, and leave it there.",
)

LADDERS = {"email": EMAIL_LADDER, "linkedin": LINKEDIN_LADDER}

# Wording that would make the note reference the email. Section 7.
# The schema in llm.py rejects the obvious cases; this is the fuller list the
# cadence checks with, so the storer is strictly stricter than the contract.
NOTE_MUST_NOT_MENTION = cadence_note_words()

# Cost accounting hook: every model call this module makes, by step.
model_calls = {}


def count_model_call(step, attempts=1):
    model_calls[step] = model_calls.get(step, 0) + int(attempts)
    return model_calls


def reset_model_calls():
    model_calls.clear()


def prompt_text(name):
    with open(os.path.join(PROMPTS, f"{name}.md"), encoding="utf-8") as f:
        return f.read()


# --------------------------------------------------------------- context

def facts_block(rec):
    """The trimmed facts a prompt is allowed to see. No provider payloads.

    FACTS ABOUT THE COMPANY, NEVER FACTS ABOUT OUR OWN PROCESS. `icp_flags`
    and `headcount_signal` were on this list, and the model did exactly what
    it was asked: it wrote about them. The one campaign-ready Productive
    contact's approved-pending day1 email read

        Subject: HSMG geo flag and headcount
        "The specific signal triggering this outreach is the geo outside
         client's stated markets flag."
        "We failed to filter our outreach by geography, and we own that
         failure completely without excuse."
        "Your headcount signal is 23."

    to a stranger, and day15 opened "The ICP flag indicates geographic
    targeting outside stated markets."

    `lint` and `claims` both passed it, and were right to by their own rules:
    every sentence IS grounded in this record's stored evidence. The evidence
    was our qualification verdict about our own targeting, and our provider's
    internal people-count. Grounding checks that a claim is supported; it
    cannot know that the support is a note we wrote to ourselves.

    So the allowlist is the boundary, and it is drawn at what a person at the
    company would recognise as being about their company. `icp_flags` is our
    verdict. `headcount_signal` is our estimate in our vocabulary, and
    `employees` already carries the same number in theirs.
    """
    facts = rec.get("company_facts") or {}
    keep = ("name", "employees", "revenue", "founded", "industry", "offices",
            "specialties", "notable", "email_domain")
    return {k: facts[k] for k in keep if facts.get(k) not in (None, "", [], {})}


def contact_block(contact):
    return {k: contact.get(k) for k in ("name", "title", "persona", "angle")
            if contact.get(k)}


# ------------------------------------------------- which step is this, and
#                                                    what has already gone out

def sequence_for(rec, client=None, contact=None, campaign=None):
    """The steps this contact will actually receive, asked of the authority.

    `cadence.steps_for` resolves the assigned experiment arm, then the
    campaign's own sequence, then the client's named one, then the module
    constant. Re-deriving any of that here would be a second opinion about
    which cadence is running, and the two would drift the first time an arm
    was assigned. Imported late for the same reason `cadence_note_words` is.
    """
    from . import cadence

    if client is None:
        # Same precedent as `note_mode` directly below: the config is the
        # client's, so it is read from the client's own file when a caller did
        # not already have it. A config that cannot be read leaves
        # `steps_for` on the module constant, which is what ran before any
        # client named a sequence - not a guess at which one they meant.
        try:
            client = clients.load(rec.get("client"))
        except clients.ConfigError:
            client = None
    return cadence.steps_for(campaign, client, rec, contact)


def position(sequence, step_key):
    """Where this step sits in its own channel: (channel, ordinal, total).

    Ordinal is 1-based and counts only steps on the same channel, because the
    ladders are per channel - the second email is the second email whether or
    not three LinkedIn steps happened in between. Returns (None, None, None)
    for a step the sequence does not contain, which is what a step from an
    older cadence looks like after the sequence changed.
    """
    for spec in sequence or ():
        if spec.get("key") != step_key:
            continue
        channel = spec.get("channel")
        same = [s for s in sequence if s.get("channel") == channel]
        keys = [s.get("key") for s in same]
        return channel, keys.index(step_key) + 1, len(same)
    return None, None, None


def purpose_for(channel, ordinal):
    """This step's distinct job, or None when the ladder does not name one.

    None rather than the last rung repeated. A sequence longer than its
    ladder has steps nobody has decided the job of, and silently handing one
    of them "close the loop" produces a second closing message - which is
    exactly the duplication the ladder exists to stop. The prompt is told it
    has no assigned job and what to do about it, which is a stated case
    rather than a fallback that looks like an answer.
    """
    ladder = LADDERS.get(channel) or ()
    if not ordinal or ordinal > len(ladder):
        return None
    return ladder[ordinal - 1]


def step_block(sequence, step_key, channel=None):
    """What the prompt is told about the step it is writing."""
    found, ordinal, total = position(sequence, step_key)
    channel = found or channel
    return {"key": step_key, "channel": channel,
            "number": ordinal, "of": total,
            "purpose": purpose_for(channel, ordinal)}


def _day_of(sequence, step_key):
    for spec in sequence or ():
        if spec.get("key") == step_key:
            return spec.get("day")
    return None


def sent_so_far(rec, contact, sequence=None, before_day=None):
    """What this person has ACTUALLY received, from the durable event log.

    ## Why not from the record's current state

    `rec["cadence"]` holds the copy, `contact["angle"]` holds the argument and
    `contact["persona"]` holds the family - and all three are overwritten by
    the next generation, the next routing pass, or a human editing a persona
    in the product. A step-four prompt that reconstructed "what we already
    said" from those would be reading today's intentions and calling them
    history. `push.mark_pushed` exists precisely because that is not good
    enough: it pins the persona, the angle, the evidence ids and the variant
    onto the confirming event at the moment of sending, so what was sent stays
    what was sent.

    ## What counts as sent

    `touch.CONFIRMING_EVENTS` decides, not this function. Those are
    `push_marked`, `email_delivered` and `linkedin_connected`, and
    `push_prepared` is absent from them by name - a payload that was built is
    not a message that arrived, and on this build every payload is built and
    none is sent. A second opinion about what "sent" means is how a planned
    step becomes "as I mentioned last week".

    ## The words

    The event does not carry the subject and the body; it carries `push_id`,
    and so does the step that was pushed. Where the two agree, the stored copy
    IS the copy that went out and may be shown to the next prompt. Where they
    do not - no push id, a different one, a step nothing stored - the words
    are withheld and the row still says the touch happened, with its channel,
    its day and the angle pinned on the event. Withholding words is a smaller
    error than showing words that were not sent.
    """
    from . import touch

    key = lint.contact_key(contact or {})
    cadence_rows = (rec.get("cadence") or {}).get(key) or {}
    by_step = {}
    for entry in rec.get("events") or []:
        state = touch.CONFIRMING_EVENTS.get(entry.get("type"))
        if state is None or not touch.is_confirmed(state):
            continue
        if entry.get("contact") != key:
            continue
        step_key = entry.get("step")
        if not step_key:
            continue                       # a touch that names no step
        by_step.setdefault(step_key, []).append(entry)

    out = []
    for step_key, entries in by_step.items():
        # The push is the event that knows why this message said what it
        # said; a provider delivery confirmation knows only that it landed.
        pushed = next((e for e in entries
                       if e.get("type") == events.PUSH_MARKED), None)
        first = pushed or entries[0]
        day = first.get("day")
        if day is None:
            day = _day_of(sequence, step_key)
        if before_day is not None and day is not None and day >= before_day:
            continue
        channel = first.get("channel")
        _, ordinal, _ = position(sequence, step_key)
        row = {"step": step_key, "channel": channel, "day": day,
               "at": first.get("at"),
               "purpose": purpose_for(channel, ordinal),
               # OUR argument as it was at the time, off the event. Never
               # `contact["angle"]`, which is whatever the last routing pass
               # decided and may now be a different angle entirely.
               "angle": (pushed or {}).get("angle"),
               "persona": (pushed or {}).get("persona")}
        stored = cadence_rows.get(step_key) or {}
        push_id = (pushed or {}).get("push_id")
        if push_id and stored.get("push_id") == push_id:
            row["subject"] = stored.get("subject")
            row["opening"] = _opening(stored)
        else:
            row["copy_withheld"] = (
                "the stored step is not provably the one that was sent, so "
                "what it says now is not evidence of what went out")
        out.append(row)
    out.sort(key=lambda r: (r.get("day") if r.get("day") is not None else 0,
                            str(r.get("at") or ""), r["step"]))
    return out


def _opening(step):
    """The first sentence of what was sent. Enough not to repeat it."""
    text = (step.get("body") or step.get("note") or "").strip()
    first = text.split("\n", 1)[0].strip()
    return first[:200] or None


def history_block(rec, contact, sequence, step_key, channel):
    """`sent_so_far`, split by whether this step may see the words.

    Same channel keeps its copy: not repeating message two is the whole
    reason message four is given a history. The OTHER channel is reduced to
    the fact, the day and the angle, because the two channels do not know
    about each other - a LinkedIn message holding the text of an email is one
    careless sentence away from "as I wrote to you", which `lint` refuses and
    a prospect would never have to refuse because they would simply stop
    reading.
    """
    rows = sent_so_far(rec, contact, sequence,
                       before_day=_day_of(sequence, step_key))
    out = []
    for row in rows:
        if row.get("channel") == channel:
            out.append(row)
            continue
        out.append({k: row[k] for k in ("step", "channel", "day", "purpose",
                                        "angle") if k in row}
                   | {"words_withheld": "the other channel's copy is never "
                                        "quoted and never referred to"})
    return out


def context_for(step, rec, contact=None, client=None, step_key=None,
                sequence=None):
    """Assemble the smallest context that can answer the question."""
    # `lane` IS OURS, NOT THEIRS. It names the pipeline a record arrived
    # through - "domains", "cold", "revive" - and the model read "domains" as
    # the SUBJECT, writing a cold email to an agency CEO asking who owns
    # their domain portfolio and renewal decisions. Productive sells time
    # tracking and profitability; it has nothing to do with domain names.
    #
    # Routing vocabulary is not something a prospect has ever heard, so it is
    # kept out of the prompt. The branches below still read `rec["lane"]` and
    # add what the lane MEANS - a diagnosis, a hook - which is the part that
    # carries information.
    block = {"company": rec.get("company"), "domain": rec.get("domain"),
             "facts": facts_block(rec)}
    public = research.for_prompt(rec)
    if public:
        # Attributed and trimmed. The fence in llm.py marks it as data.
        block["public_evidence"] = public
    if step == "diagnose":
        block["thread"] = rec.get("context") or ""
    elif step == "hook":
        block["signal"] = rec.get("signal") or ""
    elif step == "persona_angle":
        block["contact"] = contact_block(contact or {})
        block["angles"] = (client or {}).get("angles")
    elif step == "linkedin_note":
        block["contact"] = contact_block(contact or {})
        block["angle"] = (contact or {}).get("angle")
        block["angle_wording"] = ((client or {}).get("personas") or {}).get(
            (contact or {}).get("persona") or "", {}).get("angles")
        block["tone"] = ((client or {}).get("tone") or {}).get("linkedin")
        block["prior_contact"] = bool(claims.prior_contact(rec, contact))
        if step_key:
            sequence = sequence_for(rec, client, contact) if sequence is None \
                else sequence
            block["step"] = step_block(sequence, step_key, "linkedin")
            block["already_sent"] = history_block(rec, contact, sequence,
                                                  step_key, "linkedin")
    elif step == "draft":
        block["contact"] = contact_block(contact or {})
        block["angle"] = (contact or {}).get("angle")
        # HAS THIS PERSON EVER HEARD FROM US? The prompt's shape depends on
        # it, and until this was passed the template assumed yes: it asked
        # for "the date and the sentence", for the model to "own the failure
        # if it was ours", and for "an answer to the question they asked".
        # Against a cold prospect the model obliged, inventing a missed
        # deadline, an apology and a thread - correct behaviour for the
        # instructions it was given.
        #
        # Read from the same confirmed events `claims` checks against, so the
        # prompt and the gate cannot disagree about whether a history exists.
        block["prior_contact"] = bool(claims.prior_contact(rec, contact))
        # WHAT THE ANGLE MEANS, not just its name. `linkedin_note` has passed
        # this since it was written and `draft` never did, so the model was
        # handed `angle: "founder"` and no statement of what the client
        # actually sells. It filled the gap by inventing a pitch - "helping
        # innovative agencies scale their impact" - which is true of nobody
        # and sells nothing. The config already says it:
        # `founder: profitability visible on Monday not two weeks late`.
        block["angle_wording"] = ((client or {}).get("personas") or {}).get(
            (contact or {}).get("persona") or "", {}).get("angles")
        block["evidence"] = (rec.get("evidence") or {}).get(
            lint.contact_key(contact or {}), [])
        block["tone"] = (client or {}).get("tone")
        # WHICH MESSAGE OF THE SEQUENCE THIS IS, AND WHAT THE ONES BEFORE IT
        # SAID. Without both the model has no way to make email four differ
        # from email one except by taste, and what it produced was the same
        # pitch four times. `step.purpose` says what THIS message is for;
        # `already_sent` says what is already spent, and is read from
        # confirmed events rather than from the record's current copy - see
        # `sent_so_far` for why those are not the same question.
        if step_key:
            sequence = sequence_for(rec, client, contact) if sequence is None \
                else sequence
            block["step"] = step_block(sequence, step_key, "email")
            block["already_sent"] = history_block(rec, contact, sequence,
                                                  step_key, "email")
        if rec.get("lane") == "revive":
            block["diagnosis"] = rec.get("diagnosis")
        if rec.get("lane") == "cold":
            block["hook"] = rec.get("hook")
        if rec.get("sizing"):
            block["sizing"] = rec["sizing"]
    return block


def render_prompt(step, rec, contact=None, client=None, step_key=None,
                  sequence=None):
    """Contract first, then the record fenced as untrusted data.

    A CRM thread can say anything, including "ignore your instructions". The
    contract is stated before the fence and the fence says the contents are
    data, so a thread cannot promote itself to an instruction.
    """
    import json
    context = json.dumps(
        context_for(step, rec, contact, client, step_key, sequence),
        indent=2, ensure_ascii=False)
    return f"{prompt_text(step)}\n\n{llm.fence(context)}"


# ----------------------------------------------------------------- steps

def note_mode(rec, client=None):
    """template or llm, from the client config. Template unless asked."""
    if client is None:
        try:
            client = clients.load(rec.get("client"))
        except clients.ConfigError:
            return "template"
    return clients.linkedin_note_mode(client)


def plan(rec, client=None, campaign=None):
    """What this record needs from a model, and why. No call without a reason.

    THE SEQUENCE DECIDES WHICH STEPS ARE WRITTEN, not a constant here.
    `GENERATED_DAYS` was `("day1", "day15")` and matched `cadence.STEPS`
    exactly, which was correct for as long as there was one cadence. There is
    not: a campaign may carry its own sequence, a client may name one, and an
    experiment arm may substitute one. A record running a five-email sequence
    got two drafts and three templates, and nothing said so.

    Consumption is the test, not declaration. `cadence.expand_step` uses the
    STORED copy for a step the sequence marks `generated` and re-renders the
    template for every other step, so generating a draft for a step the
    sequence has not marked generated would spend a model call on words
    nothing reads.
    """
    ops = []
    if rec.get("state") in ("dropped", "pushed"):
        return ops
    # Through the resolver, not off a stored flag. src/verification.py is the
    # only module allowed to conclude an address may be written to, and a
    # contact whose evidence says verified must not be skipped merely because
    # nobody copied a boolean onto it.
    sendable = [c for c in rec.get("contacts") or [] if lint.sendable(c)]
    # THE LINKEDIN LANE WAS GATED ON EMAIL VERIFICATION, AND IT IS A DIFFERENT
    # CHANNEL. The early return below said "nothing is drafted for an
    # unverified address", which is exactly right for an email draft and wrong
    # for everything else in this function: the connection note twenty lines
    # down needs a LinkedIn profile and no address at all, and it sat inside
    # the same gate.
    #
    # Measured on the Productive cohort 2026-09-12: of the contacts on
    # qualified companies, ALL carry a usable LinkedIn profile and fewer than
    # a third are email-sendable - the rest are catch-all domains reoon will
    # not clear, or MX gateways the client's own policy closes. Every one of
    # those people was reachable on LinkedIn and got no copy written for them,
    # so `campaign_ready` stood at 1 of 24 while the channel that could
    # actually reach 24 of them was never drafted for.
    #
    # `channels.linkedin_verdict` is the authority and is asked rather than
    # re-implemented: it refuses an unsubscribed or suppressed person, a
    # duplicate, a missing profile, and a URL that is a company page or a
    # search link. What it does not require is an email, because LinkedIn does
    # not.
    from . import channels
    on_linkedin = [c for c in rec.get("contacts") or ()
                   if channels.linkedin_verdict(rec, c, client)[0]]
    keys = {id(c) for c in sendable}
    workable = sendable + [c for c in on_linkedin if id(c) not in keys]
    if not workable:
        return ops
    if rec.get("lane") == "revive" and not (rec.get("diagnosis") or {}).get("died_because"):
        ops.append({"step": "diagnose", "why": "revive record with no diagnosis"})
    if rec.get("lane") == "cold" and not rec.get("hook"):
        ops.append({"step": "hook", "why": "cold record with no hook"})
    for c in workable:
        if rec.get("lane") == "domains" and not c.get("angle"):
            ops.append({"step": "persona_angle", "why": f"{c['name']} has no angle",
                        "contact": c.get("name")})
        sequence = sequence_for(rec, client, c, campaign)
        stored = (rec.get("cadence") or {}).get(lint.contact_key(c), {})
        if note_mode(rec, client) == "llm" and c in on_linkedin:
            for spec in sequence:
                if spec.get("channel") != "linkedin":
                    continue
                note = stored.get(spec["key"]) or {}
                if note.get("generated") and note.get("note"):
                    continue
                ops.append({"step": "linkedin_note",
                            "why": f"{c['name']} has no written "
                                   f"{spec['key']} note",
                            "contact": c.get("name"), "day": spec["key"]})
        # EMAIL DRAFTS STAY BEHIND EMAIL VERIFICATION. CLAUDE.md: no email is
        # generated for an unverified address, and that rule is untouched -
        # only the LinkedIn note moved out from behind it.
        if c not in sendable:
            continue
        for spec in sequence:
            if spec.get("channel") != "email" or not spec.get("generated"):
                continue
            if not (stored.get(spec["key"]) or {}).get("body"):
                ops.append({"step": "draft",
                            "why": f"{c['name']} has no {spec['key']} email",
                            "contact": c.get("name"), "day": spec["key"]})
    return ops


def diagnose(rec, model):
    data, attempts, errors = llm.ask(model, "diagnose", render_prompt("diagnose", rec))
    rec["diagnosis"] = {"died_on": data.get("died_on"),
                        "died_because": data["died_because"],
                        "failure_mode": data["failure_mode"],
                        "last_position": data.get("last_position"),
                        "what_changed": data.get("what_changed")}
    store.log(rec, "diagnose", f"{data['failure_mode']} on {data.get('died_on')}",
              attempts=attempts, rejected=errors)
    return rec["diagnosis"]


def hook(rec, model):
    data, attempts, errors = llm.ask(model, "hook", render_prompt("hook", rec), rec=rec)
    rec["hook"] = data["hook"]
    store.log(rec, "hook", data["hook"][:80], attempts=attempts, rejected=errors)
    return rec["hook"]


def persona_angle(rec, contact, model, client=None):
    """The angle plus its evidence. Evidence that is not traceable is rejected."""
    data, attempts, errors = llm.ask(
        model, "persona_angle", render_prompt("persona_angle", rec, contact, client),
        rec=rec)
    contact["angle"] = data["angle"]
    rec.setdefault("evidence", {})[lint.contact_key(contact)] = data["evidence"]
    store.log(rec, "angle", f"{contact.get('name')}: {data['angle']}",
              attempts=attempts, rejected=errors, evidence=data["evidence"])
    return data


def linkedin_note(rec, contact, model, client=None, step_key="day3"):
    """One written LinkedIn step. Short, and no crossover.

    `step_key` defaults to `day3` because that is where `cadence.STEPS` puts
    the connection request and every caller before the LinkedIn-heavy
    sequence existed passed nothing. A sequence with several LinkedIn steps
    writes each of them, and the step key is what tells the prompt which rung
    of `LINKEDIN_LADDER` it is on - a connection request and a fourth message
    are not the same object and must not be written from the same brief.

    Cost accounting: every model call is counted here through
    `model_calls`, and the attempts are on the record's log, so the price of
    llm mode is visible before it is turned on for 500 domains.
    """
    key = lint.contact_key(contact)
    data, attempts, errors = llm.ask(
        model, "linkedin_note",
        render_prompt("linkedin_note", rec, contact, client, step_key))
    note = data["note"].strip()
    step = {"channel": "linkedin", "generated": True, "note": note}
    leaks = [w for w in NOTE_MUST_NOT_MENTION if w in note.lower()]
    if leaks:
        store.log(rec, "linkedin_note", f"rejected, mentions {leaks[0]}")
        return None
    rec.setdefault("cadence", {}).setdefault(key, {})[step_key] = step
    count_model_call("linkedin_note", attempts)
    store.log(rec, "linkedin_note", note[:80], attempts=attempts, rejected=errors)
    events.record(rec, events.DRAFT_GENERATED, contact_key=key,
                  channel="linkedin", step=step_key, generated=True)
    return step


def draft(rec, contact, day, model, client=None):
    """Generate, lint, regenerate. Never patch, never widen a rule.

    `day` is the STEP KEY, which is what it has always been - `day1`,
    `day15`, and now `em1`..`em5` under a sequence that names them that way.
    It is passed to the prompt so the draft knows which rung of
    `EMAIL_LADDER` it is writing and what the earlier rungs already spent.
    """
    key = lint.contact_key(contact)
    rejected = []
    for attempt in range(1, MAX_DRAFT_ATTEMPTS + 1):
        prompt = render_prompt("draft", rec, contact, client, day)
        if rejected:
            prompt += ("\n## Your previous draft failed lint\n\n"
                       f"{'; '.join(rejected[-1])}\n\nWrite a new one. Do not patch the old one.\n")
        data, _, schema_errors = llm.ask(model, "draft", prompt)
        candidate = {"channel": "email", "generated": True,
                     "subject": data["subject"], "body": data["body"]}
        # Lint the candidate against a copy: a failing draft is never stored.
        trial = dict(rec)
        trial["cadence"] = {**(rec.get("cadence") or {}),
                            key: {**((rec.get("cadence") or {}).get(key) or {}),
                                  day: candidate}}
        failures = lint.check(trial, key, candidate)
        content_failures = [f for f in failures if f not in lint.HELD_CODES]
        if not content_failures:
            rec.setdefault("cadence", {}).setdefault(key, {})[day] = candidate
            store.log(rec, "draft", f"{contact.get('name')} {day}: {data['subject']}",
                      attempts=attempt, rejected=rejected)
            count_model_call("draft", attempt)
            events.record(rec, events.DRAFT_GENERATED, contact_key=key,
                          channel="email", step=day, generated=True)
            return candidate
        rejected.append(content_failures)
        events.record(rec, events.LINT_FAILED, contact_key=key, channel="email",
                      step=day, failures=content_failures, attempt=attempt)
    store.log(rec, "draft",
              f"{contact.get('name')} {day}: no draft passed lint, nothing stored",
              attempts=MAX_DRAFT_ATTEMPTS, rejected=rejected)
    return None


def size(rec, live=False):
    """Free: put the prospect's own market in the email instead of ours."""
    if not live or rec.get("sizing"):
        return rec.get("sizing")
    try:
        count = contactout.people_count(domain=rec["domain"])
    except ProviderError as e:
        store.log(rec, "sizing", f"people-count failed: {e}")
        return None
    rec["sizing"] = {"query": count.get("query") or rec["domain"],
                     "profiles": count.get("profiles"), "mobiles": count.get("mobiles")}
    store.log(rec, "sizing", f"{rec['sizing']['profiles']} profiles (free)")
    return rec["sizing"]


# ---------------------------------------------------------------- runner

def generate_record(rec, model, client=None, campaign=None):
    """Every step this record needs, in order, stopping at the first that fails.

    `client` reaches `plan` now and did not before. It always mattered -
    `channels.linkedin_verdict` and `note_mode` both take it - and it matters
    more since the sequence decides which steps are written: planning without
    the config resolves the module constant and would draft `day1`/`day15`
    for a record whose client runs `em1`..`em5`.
    """
    done = []
    for op in plan(rec, client, campaign):
        contact = next((c for c in rec.get("contacts") or []
                        if c.get("name") == op.get("contact")), None)
        try:
            if op["step"] == "diagnose":
                diagnose(rec, model)
            elif op["step"] == "hook":
                hook(rec, model)
            elif op["step"] == "persona_angle" and contact:
                persona_angle(rec, contact, model, client)
            elif op["step"] == "linkedin_note" and contact:
                if not linkedin_note(rec, contact, model, client, op["day"]):
                    continue
            elif op["step"] == "draft" and contact:
                if not draft(rec, contact, op["day"], model, client):
                    continue
            done.append(op)
        except llm.NoModelConfigured:
            # A CONFIGURATION FAULT IS NOT A RECORD FAULT. Holding here wrote
            # "nobody set LLM_API_KEY" into canonical state as though this
            # company were the problem, once per record, with no event - and
            # the run still printed GENERATED. Raising instead means the
            # operator is told once, before anything is saved, and no record
            # carries the blame.
            raise
        except llm.ModelError as e:
            store.log(rec, op["step"], f"held: {e}")
            if rec.get("state") not in ("dropped", "pushed"):
                rec["state"] = "held"
            break
    # THE FIRST EMAIL OF THE SEQUENCE, not the literal `day1`. Under a
    # sequence that names its opener `em1` the literal matched nothing, so a
    # record with five finished drafts stayed `verified` forever and never
    # reached approval.
    if done and any(_opener_written(rec, c, client, campaign)
                    for c in rec.get("contacts") or []):
        if rec.get("state") not in ("dropped", "pushed", "held"):
            rec["state"] = "drafted"
    return done


def _opener_written(rec, contact, client=None, campaign=None):
    stored = (rec.get("cadence") or {}).get(lint.contact_key(contact), {})
    for spec in sequence_for(rec, client, contact, campaign):
        if spec.get("channel") == "email":
            return bool(stored.get(spec["key"]))
    return False


def run(model=None, live=False, ids=None, limit=None, client=None):
    """Dry by default: reports what would be asked without asking anything."""
    recs = store.load()
    model = model or llm.NoModel()
    targets = [r for r in recs if ids is None or r["id"] in ids]
    if limit:
        targets = targets[:limit]

    report = []
    for rec in targets:
        ops = generate_record(rec, model, client) if live else plan(rec, client)
        report.append({"id": rec["id"], "lane": rec.get("lane"),
                       "state": rec.get("state"), "ops": ops})
    if live:
        store.save(recs)
    return {"live": live, "model": getattr(model, "name", "unknown"), "records": report}


def main(argv=None):
    p = argparse.ArgumentParser(prog="python -m src.generate")
    p.add_argument("--live", action="store_true",
                   help="actually call the model (none is configured by default)")
    p.add_argument("--id", action="append", dest="ids")
    p.add_argument("--limit", type=int)
    p.add_argument("--client", help="whose cadence and tone the drafts follow")
    a = p.parse_args(argv)

    # `client` IS A CONFIG, NOT A SLUG, everywhere below this line. `plan`
    # hands it to `cadence.steps_for` as `config` and to
    # `channels.linkedin_verdict`, both of which call `.get` on it - so a
    # slug string reaches `_named_sequence` and raises `'str' object has no
    # attribute 'get'`. The parameter is named `client` throughout the
    # module and the loading belongs here, at the edge, once.
    config = clients.load(a.client) if a.client else None

    # THE CONFIGURED MODEL, WHICH THIS COMMAND NEVER REACHED FOR. `--live`
    # called `run()` with no model, `run` fell back to `NoModel`, and the
    # command printed "GENERATED" having asked nothing - while every record
    # it touched was held for a model that was sitting in `config/.env` all
    # along. `run` still defaults to `NoModel` so a library caller cannot
    # turn a dry run into a paid one by accident; asking for a real model is
    # what `--live` MEANS, and it now does it.
    model = llm.from_env() if a.live else None
    if a.live and isinstance(model, llm.NoModel):
        print("no model configured: set LLM_API_KEY, LLM_BASE_URL and "
              "LLM_MODEL in config/.env. Nothing was generated and no record "
              "was changed.")
        return 1

    result = run(model=model, live=a.live, ids=a.ids, limit=a.limit,
                 client=config)
    head = "GENERATED" if a.live else "DRY RUN, no model called"
    print(f"{head}: {len(result['records'])} record(s), model={result['model']}")
    for r in result["records"]:
        print(f"\n  {r['id']} ({r['lane']}) state={r['state']}")
        for o in r["ops"]:
            detail = f" [{o['contact']}{' ' + o['day'] if o.get('day') else ''}]" \
                if o.get("contact") else ""
            print(f"    {o['step']:<14}{detail:<28} {o['why']}")
        if not r["ops"]:
            print("    nothing to generate")
    if not a.live:
        print("\nno model ships with this repo: pass one to run(model=...).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
