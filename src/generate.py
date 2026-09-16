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
import hashlib
import os

from . import cadencelibrary, claims, clients, events, lint, llm, research, store


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
# sees, and none of it licenses a claim: the evidence rung says what kind of
# thing to reach for, never that we have one.
#
# ONE REPRESENTATION, AND IT LIVES IN `cadencelibrary`.
#
# These texts existed TWICE - here and in `cadencelibrary.LADDER_REGISTRY` -
# and production resolves through the registry, because a sequence names its
# ladder. So the copies here were the fallback for a sequence that names none,
# and `test_five_step_purposes_unchanged` existed to assert the two agreed.
#
# They drifted the moment anybody edited one. Measured 2026-09-14: rung 3 of
# the email ladder was rewritten here to give the product rung its job, the
# rendered `em3` prompt still carried the old wording, and the LinkedIn edit
# beside it DID take effect - because `productive_li_heavy_v1` names an email
# ladder and no LinkedIn one. Same edit, two outcomes, no error.
#
# A test asserting two representations agree is a smoke alarm, not a fix. The
# names below are the defaults for a channel; the texts have one home.
EMAIL_LADDER = cadencelibrary.EMAIL_FIVE_LADDER
LINKEDIN_LADDER = cadencelibrary.LINKEDIN_DEFAULT_LADDER

LADDERS = {"email": EMAIL_LADDER, "linkedin": LINKEDIN_LADDER}

# Wording that would make the note reference the email. Section 7.
# The schema in llm.py rejects the obvious cases; this is the fuller list the
# cadence checks with, so the storer is strictly stricter than the contract.
NOTE_MUST_NOT_MENTION = cadence_note_words()

# Cost accounting hook: every model call this module makes, by step.
model_calls = {}

# ------------------------------------------------- company evidence cache
#
# TASK-162: every company-derived key in the context block is byte-identical
# across all contacts at the same record. At 2.5 contacts per domain that is
# 2.5x the input tokens for the same text. Built once per record per pass,
# cached for the duration of the pass. The cache does not outlive the process
# that built it, so evidence cannot age out during a pass and a stale cache
# is structurally impossible.
#
# `clear_company_cache()` resets between passes (and in tests).

_company_cache = {}


def clear_company_cache():
    """Reset the company evidence cache. Call between passes and in tests."""
    _company_cache.clear()


def _evidence_fingerprint(rec):
    """Hash of (field, source_url, retrieved_at) for every research row.

    Changes when the record's research rows change (a refresh replaced stale
    rows), so the cache misses. The cache does not outlive the pass, so a
    stale fingerprint cannot survive.
    """
    parts = []
    for entry in rec.get("research") or []:
        parts.append(f"{entry.get('field', '')}|"
                     f"{entry.get('source_url', '')}|"
                     f"{entry.get('retrieved_at', '')}")
    material = "\n".join(parts)
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]


def company_evidence(rec):
    """Company-level context, built once per record per generation pass.

    Returns a dict with the fields every contact at this record shares:
    company, domain, facts, public_evidence, research, evidence_fingerprint,
    and built_at. The cache is keyed by rec["id"] and lives for the duration
    of one pass.

    Provenance survives: every fact in public_evidence and research keeps
    source_url and retrieved_at verbatim. The claims gate reads rec["research"]
    directly and is not affected by this projection.
    """
    rid = rec.get("id")
    if rid and rid in _company_cache:
        return _company_cache[rid]

    block = {
        "company": rec.get("company"),
        "domain": rec.get("domain"),
        "facts": facts_block(rec),
    }
    public = research.for_prompt(rec)
    if public:
        block["public_evidence"] = public
    rb = research_block(rec)
    if rb:
        block["research"] = rb
    block["evidence_fingerprint"] = _evidence_fingerprint(rec)
    from datetime import datetime, timezone
    block["built_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")

    if rid:
        _company_cache[rid] = block
    return block


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


def research_block(rec, contact=None, limit=5, chars=400):
    """Sourced facts from crawled pages, filtered for usability.

    TASK-135: 695 research rows sit on 203 records, but `for_prompt` returns
    the first three regardless of quality - and 236 of 695 are "unusable"
    (raw navigation text). The model received the furniture, not the facts,
    and wrote filler that the claims gate correctly refused.

    This function is contact-aware: entries with a matching `contact_key`
    come first, then company-level entries fill the remainder. When no entry
    has a `contact_key` (the current state of all 695 rows), all are
    company-level and the contact match is a no-op.

    Only entries whose quality is "medium" or "strong" are returned. The
    claims gate reads `rec["research"]` directly and is not affected by this
    filter - it sees everything, including the unusable rows.
    """
    entries = rec.get("research") or []
    if not entries:
        return []
    usable = [e for e in entries
              if e.get("quality") in ("medium", "strong")]
    key = lint.contact_key(contact or {})
    contact_specific = [e for e in usable if e.get("contact_key") == key]
    company_level = [e for e in usable if not e.get("contact_key")]
    ordered = contact_specific + company_level
    out = []
    for entry in ordered[:limit]:
        out.append({
            "fact": (entry.get("fact") or "")[:chars],
            "source_url": entry.get("source_url"),
            "retrieved_at": entry.get("retrieved_at"),
        })
    return out


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


def _resolve_ladder(channel, sequence=None):
    """The ladder for this channel in the context of a given sequence.

    A sequence may name a per-channel ladder via `cadencelibrary.ladder_name_for`.
    When it does, the named ladder is looked up in the registry. When it
    does not, or when no sequence is passed, the default ladder for the
    channel is returned - which is the five-step email ladder that has
    been production since the beginning.

    `cadencelibrary` is imported at module level rather than here. It was a
    late import against a circular one, and `cadencelibrary` imports nothing
    at all - it is a data module. The module-level import is what lets the
    channel defaults below BE the registry's entries instead of a second copy
    of them.
    """
    if sequence is not None:
        ladder_name = cadencelibrary.ladder_name_for(sequence, channel)
        if ladder_name:
            found = cadencelibrary.LADDER_REGISTRY.get(ladder_name)
            if found:
                return found
    return LADDERS.get(channel) or ()


def purpose_for(channel, ordinal, sequence=None):
    """This step's distinct job, or None when the ladder does not name one.

    None rather than the last rung repeated. A sequence longer than its
    ladder has steps nobody has decided the job of, and silently handing one
    of them "close the loop" produces a second closing message - which is
    exactly the duplication the ladder exists to stop. The prompt is told it
    has no assigned job and what to do about it, which is a stated case
    rather than a fallback that looks like an answer.

    `sequence` selects which ladder to use. A five-step cadence and an
    eight-step cadence carry different ladders; the same ordinal resolves
    to a different purpose in each. Without a sequence the default ladder
    is used, which is the five-step one - backward compatible with every
    caller that existed before ladders became selectable.
    """
    ladder = _resolve_ladder(channel, sequence)
    if not ordinal or ordinal > len(ladder):
        return None
    return ladder[ordinal - 1]


def ladder_fingerprint(channel, ordinal, sequence=None):
    """Hash of the ladder rung this step was generated against.

    TASK-083. A step generated against a ladder that later changed carries
    a fingerprint of the OLD rung. Recomputing against the CURRENT ladder
    produces a different hash, so the mismatch is the signal that the copy
    is stale. The fingerprint covers the channel and the purpose TEXT, so
    any edit to the ladder brief - a word, a reorder, a new rung - moves it.

    Returns None when the step has no ladder context (no channel, no
    ordinal, or ordinal beyond the ladder). A step without a fingerprint
    cannot be checked for staleness.
    """
    purpose = purpose_for(channel, ordinal, sequence=sequence)
    if not channel or not ordinal or purpose is None:
        return None
    material = f"{channel}:{ordinal}:{purpose}"
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]


def ladder_stale(stored_step, step_key, sequence=None):
    """Was this step generated against a ladder that no longer matches?

    True when the stored ladder fingerprint differs from the current one.
    False when the fingerprints match, when the step has no fingerprint
    (generated before this mechanism existed), or when the step's position
    in the sequence cannot be resolved.

    A step without a fingerprint is NOT treated as stale here. The absence
    means the step predates the mechanism, and treating it as stale would
    silently invalidate every stored step in the estate. The opt-in flag
    in `plan` handles that case separately.

    `step_key` is passed separately because stored step dicts carry channel
    and body but not their own key - the key is the dict key in the cadence
    row, not a field on the step.
    """
    stored_fp = (stored_step or {}).get("ladder_fingerprint")
    if not stored_fp:
        return False
    channel = (stored_step or {}).get("channel")
    if not channel or not step_key:
        return False
    _, ordinal, _ = position(sequence, step_key)
    if not ordinal:
        return False
    current_fp = ladder_fingerprint(channel, ordinal, sequence=sequence)
    if not current_fp:
        return False
    return stored_fp != current_fp


def step_block(sequence, step_key, channel=None):
    """What the prompt is told about the step it is writing."""
    found, ordinal, total = position(sequence, step_key)
    channel = found or channel
    base_purpose = purpose_for(channel, ordinal, sequence=sequence)
    # THREAD-REPLY: when the ladder says this rung is a same-thread follow-up,
    # the purpose must tell the model it is continuing a conversation, not
    # starting one. Without this the model writes another cold open and the
    # `thread_reply` flag is the only thing that changed.
    ladder_name = cadencelibrary.ladder_name_for(sequence, channel) if sequence else None
    thread_reply = cadencelibrary.thread_reply_for(ladder_name, ordinal) \
        if ladder_name else None
    purpose = cadencelibrary.purpose_with_thread(
        ladder_name, ordinal, base_purpose=base_purpose) if ladder_name else base_purpose
    block = {"key": step_key, "channel": channel,
             "number": ordinal, "of": total,
             "purpose": purpose}
    if thread_reply is not None:
        block["thread_reply"] = thread_reply
    return block


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
               "purpose": purpose_for(channel, ordinal, sequence=sequence),
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


def siblings_block(rec, contact, sequence, step_key, channel):
    """The OTHER generated steps for this contact on this channel.

    These are drafts stored in `rec["cadence"]`, not confirmed sends. They
    exist so the model writing step N can see what steps 1..N-1 already say
    and avoid repeating them. They license NOTHING: no "as I mentioned", no
    "following up on my note", no claim of contact. Their only job is to let
    the model write something different.

    Same channel only, for the same reason `history_block` does: a LinkedIn
    message holding the text of an email is one careless sentence away from
    "as I wrote to you".

    Returns a list of dicts keyed by step, with subject+body (email) or
    note (linkedin) and the step's purpose. Empty when there are no siblings.
    """
    key = lint.contact_key(contact or {})
    cadence_rows = (rec.get("cadence") or {}).get(key) or {}
    out = []
    for sk, stored in cadence_rows.items():
        if sk == step_key:
            continue
        if stored.get("channel") != channel:
            continue
        if not (stored.get("body") or stored.get("note")):
            continue
        _, ordinal, _ = position(sequence, sk)
        entry = {"step": sk, "purpose": purpose_for(channel, ordinal, sequence=sequence)}
        if channel == "email":
            entry["subject"] = stored.get("subject", "")
            entry["opening"] = _opening(stored)
        else:
            entry["note"] = stored.get("note", "")
        out.append(entry)
    out.sort(key=lambda r: r["step"])
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
    # TASK-162: company-level data is built once per record and cached.
    # Every contact at the same record gets the same bytes for company,
    # domain, facts, public_evidence and research. The cache lives for the
    # duration of one pass; clear_company_cache() resets between passes.
    ce = company_evidence(rec)
    block = {"company": ce["company"], "domain": ce["domain"],
             "facts": ce["facts"]}
    if "public_evidence" in ce:
        # Attributed and trimmed. The fence in llm.py marks it as data.
        block["public_evidence"] = ce["public_evidence"]
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
        # WHAT WE SELL, NOT ONLY WHAT WE ARGUE. See the note beside the same
        # line under `draft` below, and the `product:` block in
        # `config/clients/productive.yaml` for the measurement: rendering this
        # very prompt, the word "Productive" occurred zero times in it. A
        # rung whose job is to say what the product does cannot do that job
        # from `angle_wording`, and what the model produced instead was an
        # offer to explain - "i'd love to share how teams like yours have
        # improved their project visibility" - four times over.
        #
        # `clients.product` answers `{}` for a client who has not stated one,
        # and the prompt's rule for an absent block is to say nothing about
        # the product rather than invent one.
        block["product"] = clients.product(client or {})
        # WHO IS WRITING. TASK-075: all 15 generated connection notes were
        # anonymous - no sender name, no company, no role. The recipient
        # received an anonymous compliment and an invitation. The sender
        # block in the client config carries whatever detail is available;
        # when it is empty the prompt must degrade safely and say what the
        # sender does (from the product block) rather than invent a name.
        block["sender_identity"] = clients.sender_identity(client or {})
        # TASK-135: sourced facts for the LinkedIn note, same as draft.
        # TASK-162: from the company evidence cache, not rebuilt per contact.
        if ce.get("research"):
            block["research"] = ce["research"]
        block["tone"] = ((client or {}).get("tone") or {}).get("linkedin")
        block["prior_contact"] = bool(claims.prior_contact(rec, contact))
        if step_key:
            sequence = sequence_for(rec, client, contact) if sequence is None \
                else sequence
            block["step"] = step_block(sequence, step_key, "linkedin")
            block["already_sent"] = history_block(rec, contact, sequence,
                                                  step_key, "linkedin")
            block["siblings"] = siblings_block(rec, contact, sequence,
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
        # AND WHAT THE THING IS. `angle_wording` closed half this gap: the
        # model stopped inventing a pitch and started arguing the client's
        # own phrase. It still could not answer "what is this", because
        # nothing told it. Four of five staged Productive emails opened
        # [company self-description] -> [why I am writing] -> [ask] and never
        # named the product, which is the email half of the same defect the
        # LinkedIn ladder shows more plainly.
        block["product"] = clients.product(client or {})
        # AND WHO IS WRITING IT. TASK-063 read all 165 generated email steps
        # and found sender identity in ZERO of them - not one email says who
        # is writing, with no name, no company and no role. TASK-075 fixed
        # exactly this for `linkedin_note` and stopped here, so the email half
        # of the defect survived its own fix. Same call, same degradation
        # rule: when the block is empty the prompt says what the sender DOES
        # rather than inventing a name.
        block["sender_identity"] = clients.sender_identity(client or {})
        block["evidence"] = (rec.get("evidence") or {}).get(
            lint.contact_key(contact or {}), [])
        # TASK-135: sourced facts from crawled pages, separate from
        # `evidence` (the model's own prior sentences) and from
        # `public_evidence` (unfiltered raw page text). Quality-filtered
        # to medium+strong so the model receives facts, not navigation.
        # TASK-162: from the company evidence cache, not rebuilt per contact.
        if ce.get("research"):
            block["research"] = ce["research"]
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
            block["siblings"] = siblings_block(rec, contact, sequence,
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


def store_step(rec, contact_key, step_key, step):
    """Write a generated step, KEEPING the approval it replaces as history.

    THE DEFECT THIS CLOSES, measured on the live estate 2026-09-15.

    Regeneration replaced the step dict wholesale at three separate call
    sites, so any `approval` on the outgoing step was simply gone. Comparing
    a pre-regeneration backup against the estate afterwards:

        steps approved before regeneration   169
        approval record still present         97
        approval record GONE                  72

    Seventy-two human-readable audit records deleted, silently, by a run that
    reported itself as regenerating copy. They were recoverable only because
    a backup happened to exist.

    THE BINDING ITSELF WAS NEVER BROKEN. `approval.is_approved` compares the
    stored fingerprint against the CURRENT content, so regenerated copy could
    never have inherited an old verdict - proven by changing one character and
    watching the approval lapse. The verdict binds to exact content, which is
    the invariant.

    What was missing is the other half: a lapsed verdict is still EVIDENCE.
    It says a person looked at this position, on this date, and said yes to
    words that no longer exist. That belongs in the audit trail, not in the
    bin. So the live `approval` field is correctly absent on new copy - the
    new copy is unapproved and must be read again - and the old record moves
    to `approval_history`, which accumulates rather than replaces.
    """
    cadence = rec.setdefault("cadence", {}).setdefault(contact_key, {})
    prior = cadence.get(step_key)
    if isinstance(prior, dict):
        history = list(prior.get("approval_history") or [])
        if prior.get("approval"):
            superseded = dict(prior["approval"])
            superseded["superseded_at"] = _now_iso()
            superseded["superseded_by"] = "regeneration"
            # What the approval was GIVEN TO, so the record is meaningful
            # without the copy it referred to.
            superseded["approved_content_fingerprint"] =                 superseded.get("fingerprint")
            history.append(superseded)
        if history:
            step = dict(step)
            step["approval_history"] = history
    cadence[step_key] = step
    return step


def _now_iso():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def plan(rec, client=None, campaign=None, regen_stale_ladder=False):
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

    `regen_stale_ladder` is OPT-IN (TASK-083). When True, a step whose stored
    ladder fingerprint does not match the current ladder is treated as needing
    regeneration, exactly like a failing gate. When False (the default), plan
    behaves exactly as before - no ladder check, no change to idempotence.
    A step without a stored fingerprint (generated before this mechanism) is
    treated as stale only when the flag is set, because its absence means it
    predates the mechanism and was almost certainly generated against an
    older ladder.
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
    # ANGLES FIRST, BEFORE ANY DRAFTS. The lint rule `domains_contact_no_angle`
    # checks ALL contacts in the record, not just the one being drafted. So a
    # draft for contact 1 fails lint if contact 2 has no angle, even though
    # contact 1's angle was just set. Processing all persona_angle ops before
    # any draft ops ensures every contact has an angle before any draft is
    # attempted. Measured 2026-09-14: every email draft in the e2e and
    # preproduction tests failed lint with `domains_contact_no_angle` because
    # the plan interleaved persona_angle and draft ops per contact.
    for c in workable:
        if rec.get("lane") == "domains" and not c.get("angle"):
            ops.append({"step": "persona_angle", "why": f"{c['name']} has no angle",
                        "contact": c.get("name")})
    for c in workable:
        sequence = sequence_for(rec, client, c, campaign)
        stored = (rec.get("cadence") or {}).get(lint.contact_key(c), {})
        if note_mode(rec, client) == "llm" and c in on_linkedin:
            for spec in sequence:
                if spec.get("channel") != "linkedin":
                    continue
                note = stored.get(spec["key"]) or {}
                if not (note.get("generated") and note.get("note")):
                    ops.append({"step": "linkedin_note",
                                "why": f"{c['name']} has no written "
                                       f"{spec['key']} note",
                                "contact": c.get("name"), "day": spec["key"]})
                    continue
                # LADDER STALENESS FIRST (TASK-128). A step whose ladder
                # fingerprint does not match the current ladder was generated
                # against a brief that no longer exists. This check MUST come
                # before lint/claims/quality, because a stale step may also
                # fail those gates (e.g., em_dash from an older ladder), and
                # if the lint check fires first the ladder staleness is never
                # reached - so the impact report counts zero stale steps on
                # an estate full of them. Regenerating against the current
                # ladder fixes both the staleness and the lint failure at
                # once, so reporting ladder-stale is the right op.
                if regen_stale_ladder:
                    has_fp = bool(note.get("ladder_fingerprint"))
                    if ladder_stale(note, spec["key"], sequence=sequence):
                        ops.append({"step": "linkedin_note",
                                    "why": f"{c['name']}'s {spec['key']} note "
                                           f"was generated against a ladder "
                                           f"that has since changed",
                                    "contact": c.get("name"),
                                    "day": spec["key"],
                                    "ladder_stale": True})
                        continue
                    if not has_fp:
                        ops.append({"step": "linkedin_note",
                                    "why": f"{c['name']}'s {spec['key']} note "
                                           f"has no ladder fingerprint "
                                           f"(predates TASK-083)",
                                    "contact": c.get("name"),
                                    "day": spec["key"],
                                    "ladder_stale": True})
                        continue
                # A NOTE THAT DOES NOT PASS IS NOT A NOTE. The same defect
                # the email branch fixed: this asked only whether a note
                # EXISTED, so a stored note that fails the gates counted as
                # work already done - and nothing else regenerates one.
                #
                # The gates are the same ones `linkedin_note` runs before
                # storing: lint, claims, foreign_product and quality. The
                # planner must ask the same questions, or it will re-plan
                # notes that would pass and skip notes that would fail.
                #
                # HELD CODES ARE NOT REGENERABLE. `profile_missing` is in
                # `LINKEDIN_HELD_CODES` for the same reason
                # `recipient_not_sendable` is in `HELD_CODES`: no rewrite
                # fixes a fact about the contact. A note for a contact with
                # no LinkedIn profile must not be regenerated three times.
                trial = dict(rec)
                trial["cadence"] = {**(rec.get("cadence") or {}),
                                    lint.contact_key(c): {
                                        **stored, spec["key"]: note}}
                li_failures = [f for f in lint.check_step(
                    trial, lint.contact_key(c), note)
                    if f not in lint.LINKEDIN_HELD_CODES]
                if lint.classify_linkedin(li_failures) == "failed":
                    ops.append({"step": "linkedin_note",
                                "why": f"{c['name']}'s {spec['key']} note "
                                       f"fails lint "
                                       f"({', '.join(li_failures)})",
                                "contact": c.get("name"), "day": spec["key"]})
                    continue
                unsupported = claims.check(
                    note.get("note") or "", trial, c)
                if unsupported:
                    ops.append({"step": "linkedin_note",
                                "why": f"{c['name']}'s {spec['key']} note "
                                       f"makes an unsupported claim "
                                       f"({unsupported[0].get('why', '')[:60]})",
                                "contact": c.get("name"), "day": spec["key"]})
                    continue
                invented = claims.foreign_product(
                    note.get("note") or "",
                    clients.product(client or {}), rec)
                if invented:
                    ops.append({"step": "linkedin_note",
                                "why": f"{c['name']}'s {spec['key']} note "
                                       f"names a product not sold "
                                       f"({invented[0].get('why', '')[:60]})",
                                "contact": c.get("name"), "day": spec["key"]})
                    continue
                note_repeats = _note_quality(
                    trial, c,
                    (trial.get("cadence") or {}).get(lint.contact_key(c)) or {},
                    spec["key"], client)
                if note_repeats:
                    ops.append({"step": "linkedin_note",
                                "why": f"{c['name']}'s {spec['key']} note "
                                       f"repeats another step "
                                       f"({', '.join(note_repeats)})",
                                "contact": c.get("name"), "day": spec["key"]})
                    continue
        # EMAIL DRAFTS STAY BEHIND EMAIL VERIFICATION. CLAUDE.md: no email is
        # generated for an unverified address, and that rule is untouched -
        # only the LinkedIn note moved out from behind it.
        if c not in sendable:
            continue
        for spec in sequence:
            if spec.get("channel") != "email" or not spec.get("generated"):
                continue
            step = stored.get(spec["key"]) or {}
            if not step.get("body"):
                ops.append({"step": "draft",
                            "why": f"{c['name']} has no {spec['key']} email",
                            "contact": c.get("name"), "day": spec["key"]})
                continue
            # LADDER STALENESS FIRST (TASK-128). Same reason as the LinkedIn
            # path: a stale step may also fail lint/claims/quality, and if
            # those gates fire first the ladder staleness is never reached.
            # The impact report counts zero stale steps on an estate full of
            # them. Regenerating against the current ladder fixes both the
            # staleness and the gate failure at once.
            if regen_stale_ladder:
                has_fp = bool(step.get("ladder_fingerprint"))
                if ladder_stale(step, spec["key"], sequence=sequence):
                    ops.append({"step": "draft",
                                "why": f"{c['name']}'s {spec['key']} email "
                                       f"was generated against a ladder "
                                       f"that has since changed",
                                "contact": c.get("name"),
                                "day": spec["key"],
                                "ladder_stale": True})
                    continue
                if not has_fp:
                    ops.append({"step": "draft",
                                "why": f"{c['name']}'s {spec['key']} email "
                                       f"has no ladder fingerprint "
                                       f"(predates TASK-083)",
                                "contact": c.get("name"),
                                "day": spec["key"],
                                "ladder_stale": True})
                    continue
            # A DRAFT THAT DOES NOT PASS IS NOT A DRAFT. This asked only
            # whether a body EXISTED, so a stored draft that fails lint was
            # counted as work already done - and nothing else regenerates
            # one. `cadence.status_for` blocks the step, `eligibility` refuses
            # the payload, and the planner says there is nothing to do. The
            # step never ships and never gets another attempt.
            #
            # It arises whenever a rule tightens. `SUBSTITUTED_PUNCTUATION`
            # gained three characters on 2026-09-13 and three of the ten
            # drafts in the estate went from clean to failed in that instant,
            # with no path back. It also arises from an older cadence, an
            # edited client tone, or a hand-edited record.
            #
            # ONLY WHEN THE WORDS ARE THE PROBLEM. `lint.classify` already
            # separates the failure that is about this draft from the one
            # that is about the recipient - `recipient_not_sendable` is in
            # `HELD_CODES` and no rewrite fixes it. Regenerating for that
            # would spend three attempts and then hold the record for a fact
            # about an address.
            failures = lint.check_step(rec, lint.contact_key(c), step)
            if lint.classify(failures) == "failed":
                ops.append({"step": "draft",
                            "why": f"{c['name']}'s {spec['key']} email fails "
                                   f"lint ({', '.join(failures)})",
                            "contact": c.get("name"), "day": spec["key"]})
                continue
            # AND THE CLAIMS, for the same reason and with the same
            # consequence. `draft()` now checks claims before storing, but a
            # draft written BEFORE that check existed is already on the
            # record and nothing would ever look at it again - the planner
            # would count it as done and `executionguard` would refuse it
            # forever at send time. Measured 2026-09-14: "Final note on our
            # previous discussions" was staged to EmailBison for a contact
            # this system has never written to, and re-running generation
            # did not touch it.
            unsupported = claims.check(
                f"{step.get('subject') or ''}\n{step.get('body') or ''}",
                rec, c)
            if unsupported:
                ops.append({"step": "draft",
                            "why": f"{c['name']}'s {spec['key']} email makes "
                                   f"an unsupported claim "
                                   f"({unsupported[0].get('why', '')[:60]})",
                            "contact": c.get("name"), "day": spec["key"]})
                continue
            # AND THE QUALITY GATE, which is the third of the same kind. Lint
            # asks whether the words break a rule, claims asks whether they
            # assert something untrue, and this asks whether they say
            # anything the other steps have not already said. All three are
            # reasons a stored draft is not finished work, and all three were
            # invisible to a planner that asked only whether a body existed.
            #
            # Measured 2026-09-14 with the company's own name discounted: 60
            # of 65 stored steps repeat another step in their own sequence.
            quality_out = _quality_of(rec, c, stored, spec["key"], client)
            if quality_out:
                ops.append({"step": "draft",
                            "why": f"{c['name']}'s {spec['key']} email "
                                   f"repeats another step "
                                   f"({', '.join(quality_out)})",
                            "contact": c.get("name"), "day": spec["key"]})
                continue

    # SET REGENERATION DETECTION.
    #
    # A contact whose LinkedIn notes pass the intrinsic gates individually
    # but collide on campaign_repetition cannot be fixed one note at a time:
    # whichever note is rewritten is compared against the old siblings that
    # still say the same thing, so the replacement collides and the old note
    # stays. The stale siblings are why regeneration cannot converge.
    #
    # When this condition is detected, the individual linkedin_note ops for
    # that contact are replaced with a single linkedin_set op that
    # regenerates ALL LinkedIn notes as a transaction: fresh candidates into
    # memory, the whole set gated together, committed only if every member
    # passes. If it fails, nothing is lost.
    #
    # The trigger is established from the data: campaign_repetition
    # collisions among steps that all pass lint, claims and foreign_product.
    # No threshold is picked; the collision set IS the condition.
    if note_mode(rec, client) == "llm":
        for c in workable:
            keys_to_regen = _needs_set_regeneration(rec, c, client)
            if keys_to_regen is None:
                continue
            contact_li_ops = [i for i, o in enumerate(ops)
                             if o.get("step") == "linkedin_note"
                             and o.get("contact") == c.get("name")]
            # TASK-129: propagate ladder_stale from removed individual ops
            # to the set op. Without this, the impact report undercounts
            # stale steps for contacts whose notes are absorbed into a set,
            # and a direct plan() call shows zero ladder_stale ops for
            # records that the CLI reports as stale.
            stale_count = sum(1 for i in contact_li_ops
                              if ops[i].get("ladder_stale"))
            for i in reversed(contact_li_ops):
                ops.pop(i)
            set_op = {"step": "linkedin_set",
                      "why": f"{c['name']}'s notes pass individually but "
                             f"collide on campaign_repetition; "
                             f"regenerating {len(keys_to_regen)} notes "
                             f"as a set",
                      "contact": c.get("name")}
            if stale_count:
                set_op["ladder_stale"] = True
                set_op["stale_step_count"] = stale_count
            ops.append(set_op)

    # VARIANT SETS.
    #
    # After all drafts are planned, check whether any generated step needs
    # a set of five approach-labelled variants. A step with `generated: True`
    # and fewer than five active variants on its spec is a candidate.
    # The variant set is generated as a separate op so it can be run
    # independently of the single-draft path.
    #
    # OPT-IN: variant generation is only planned when the campaign or client
    # config has `generate_variants: true`. This keeps the existing single-draft
    # path unchanged and lets Claude run variant generation explicitly.
    from . import variants as V

    want_variants = False
    if campaign and campaign.get("generate_variants"):
        want_variants = True
    elif client and (client.get("generate_variants") or
                     (client.get("experiments") or {}).get("generate_variants")):
        want_variants = True

    if want_variants:
        for c in workable:
            sequence = sequence_for(rec, client, c, campaign)
            for spec in sequence:
                if not spec.get("generated"):
                    continue
                existing = spec.get("variants") or []
                active = [v for v in existing
                          if v.get("status") == V.ACTIVE]
                if len(active) >= V.MINIMUM_VARIANTS:
                    continue
                # Only plan variant generation when the step already has a draft
                key = lint.contact_key(c)
                stored = (rec.get("cadence") or {}).get(key, {}).get(spec["key"])
                if not stored:
                    continue
                channel = spec.get("channel", "email")
                written = stored.get("body") if channel == "email" \
                    else stored.get("note")
                if not (written or "").strip():
                    continue
                ops.append({"step": "variant_set",
                            "why": (f"{c['name']}'s {spec['key']} has "
                                    f"{len(active)} variant(s); needs "
                                    f"{V.MINIMUM_VARIANTS}"),
                            "contact": c.get("name"),
                            "day": spec["key"],
                            "channel": channel})
    return ops


def _quality_of(rec, contact, stored, step_key, config):
    """The quality gate's reasons for one stored step, or an empty list.

    THE COMPANY'S OWN NAME IS DISCOUNTED. Every message in a sequence to one
    company names that company, and counting those tokens as shared content
    made relevance look like duplication - `acqcom-com` went from two
    colliding pairs to zero with "acqcom", "digital" and "marketing"
    excluded, on copy that was fine.

    A SIBLING THAT FAILS LINT IS NOT A SIBLING. A stored step that does not
    pass the gates cannot ship - `cadence.status_for` holds it, `eligibility`
    refuses the payload - so it is a draft that did not make it, not valid
    copy. Including it in comparisons inflates repetition counts and can
    block a good new note by colliding with copy that will never be sent.
    """
    import re as _re

    from . import quality

    step = (stored or {}).get(step_key) or {}
    if not step.get("body"):
        return []
    contact_key = lint.contact_key(contact)
    siblings = [{"key": k, "text": f"{s.get('subject') or ''} {s.get('body') or ''}"}
                for k, s in sorted((stored or {}).items())
                if s.get("channel") == "email" and s.get("body")
                and not lint.classify(lint.check_step(rec, contact_key, s)) == "failed"]
    name = (rec.get("company_facts") or {}).get("name") or rec.get("company") or ""
    ignore = {w for w in _re.findall(r"[a-z]+", str(name).lower()) if len(w) > 2}
    found = quality.gate(f"{step.get('subject') or ''} {step.get('body') or ''}",
                         config, steps=siblings, channel="email", ignore=ignore)
    return (found or {}).get("reasons") or []


def _note_quality(rec, contact, stored, step_key, config):
    """The quality gate's reasons for one stored LinkedIn note.

    The LinkedIn twin of `_quality_of`, and it is a separate function for the
    same reason `quality.gate` takes a `channel`: the two channels do not
    share a rule set. `_quality_of` reads `body`, filters siblings to email
    and passes `channel="email"`; a note has no body and no subject, and its
    siblings are the other notes.

    `quality.gate` DEFAULTS to `channel="linkedin"`. It was written for this
    channel and, until now, was only ever called for the other one.

    The company's own name is discounted here too. Every message in a
    sequence to one company names that company, and counting those tokens as
    shared content makes relevance look like duplication.

    A SIBLING THAT FAILS LINT IS NOT A SIBLING. See `_quality_of` for the
    full reasoning. A stored LinkedIn note that fails lint cannot ship, so
    it is not valid copy and must not participate in repetition comparisons.
    """
    import re as _re

    from . import quality

    step = (stored or {}).get(step_key) or {}
    note = (step.get("note") or "").strip()
    if not note:
        return []
    contact_key = lint.contact_key(contact)
    siblings = [{"key": k, "text": s.get("note") or ""}
                for k, s in sorted((stored or {}).items())
                if s.get("channel") == "linkedin" and (s.get("note") or "").strip()
                and not lint.classify(lint.check_step(rec, contact_key, s)) == "failed"]
    name = (rec.get("company_facts") or {}).get("name") or rec.get("company") or ""
    ignore = {w for w in _re.findall(r"[a-z]+", str(name).lower()) if len(w) > 2}
    found = quality.gate(note, config, steps=siblings, channel="linkedin",
                         ignore=ignore)
    reasons = list((found or {}).get("reasons") or [])

    # AND THE CHECK THE STAGE WILL RUN, ASKED HERE INSTEAD OF ONLY THERE.
    #
    # `quality.campaign_repetition` is what `heyreachfactory._plan` refuses a
    # campaign on. It was reachable ONLY at stage time, so a note could pass
    # every gate at generation, be stored, and then block the whole campaign
    # - with nothing in the generation loop able to see why, and nothing in
    # the retry feedback able to tell the model.
    #
    # The two checks genuinely disagree. Measured 2026-09-14 on
    # `acqcom-com/brian-price`:
    #
    #     campaign_repetition      li2 vs li5, 4 shared words
    #                              (across, day-to-day, right, tracking)
    #     repetition_across_rungs  NONE
    #
    # `repetition_across_rungs` needs three shared words AND fifty percent
    # overlap of the smaller set, so two long notes sharing four words pass
    # it. `campaign_repetition` discounts the subject vocabulary and the
    # company name and then applies its own threshold, which is stricter on
    # exactly this shape. Both are defensible; having only the stricter one
    # at the far end of the pipeline is not.
    #
    # A full regeneration ran and did not converge, because the storer kept
    # accepting replacements that collided the same way. That is the loop
    # this closes: the storer refuses it, the planner re-plans it, the reason
    # reaches the model, and the stage-time check becomes a backstop that
    # should never fire rather than the only place the question is asked.
    if len(siblings) > 1:
        company = (rec.get("company_facts") or {}).get("name") or rec.get("company")
        for collision in quality.campaign_repetition(siblings,
                                                     company_name=company):
            if step_key not in (collision.get("step_a"), collision.get("step_b")):
                continue
            other = (collision["step_b"] if collision["step_a"] == step_key
                     else collision["step_a"])
            shared = ", ".join(collision.get("shared", [])[:5])
            reasons.append(f"says the same thing as {other} ({shared})")
    return reasons


def _needs_set_regeneration(rec, contact, client=None):
    """Does this contact's LinkedIn set need set-level regeneration?

    Returns the list of LinkedIn step keys to regenerate, or None.

    A set needs regeneration when multiple notes PASS the intrinsic gates
    (lint, claims, foreign_product) but COLLIDE on campaign_repetition.
    That is the state one-at-a-time regeneration cannot escape: each
    replacement is compared against old siblings that still say the same
    thing, so a new note that addresses the same topic collides with four
    others that have not changed.

    The trigger is established from the data: campaign_repetition collisions
    among steps that individually pass. No threshold is picked; the
    collision set IS the condition.
    """
    from . import quality

    key = lint.contact_key(contact)
    stored = (rec.get("cadence") or {}).get(key) or {}

    li_steps = {}
    for sk, step in stored.items():
        if step.get("channel") == "linkedin" and (step.get("note") or "").strip():
            li_steps[sk] = step

    if len(li_steps) < 2:
        return None

    passing = {}
    for sk, step in li_steps.items():
        failures = [f for f in lint.check_step(rec, key, step)
                    if f not in lint.LINKEDIN_HELD_CODES]
        if lint.classify_linkedin(failures) == "failed":
            continue
        note_text = step.get("note") or ""
        unsupported = claims.check(note_text, rec, contact)
        if unsupported:
            continue
        invented = claims.foreign_product(
            note_text, clients.product(client or {}), rec)
        if invented:
            continue
        passing[sk] = step

    if len(passing) < 2:
        return None

    company = (rec.get("company_facts") or {}).get("name") or rec.get("company")
    steps_for_check = [{"key": sk, "text": s.get("note") or ""}
                       for sk, s in sorted(passing.items())]
    collisions = quality.campaign_repetition(steps_for_check,
                                             company_name=company)
    if not collisions:
        return None

    return sorted(li_steps.keys())


def _regenerate_linkedin_set(rec, contact, model, client=None):
    """Regenerate ALL LinkedIn notes for a contact as one transaction.

    Generates fresh candidates into memory, gates the complete set, and
    commits only if every member passes. If any step fails, nothing is
    stored and the original notes are preserved.

    Returns the list of new step dicts on success, None on failure.

    THE COST IS HIGHER than one-at-a-time: N model calls instead of one.
    The whole point is that it terminates where the cheap version cannot.
    Model calls are counted through count_model_call for reporting.
    """
    from . import quality

    key = lint.contact_key(contact)
    sequence = sequence_for(rec, client, contact)
    li_specs = [spec for spec in sequence if spec.get("channel") == "linkedin"]
    if not li_specs:
        return None

    generated = {}
    total_calls = 0

    for spec in li_specs:
        step_key = spec["key"]
        best_note = None
        rejected = []
        step_calls = 0

        for attempt in range(1, MAX_DRAFT_ATTEMPTS + 1):
            prompt = render_prompt("linkedin_note", rec, contact, client,
                                   step_key)
            if rejected:
                prompt += ("\n## Your previous note was refused\n\n"
                           f"{rejected[-1]}\n\nWrite a new one. "
                           "Do not patch the old one.\n")
            data, attempts, errors = llm.ask(model, "linkedin_note", prompt)
            step_calls += attempts
            note = data["note"].strip()
            note = lint.normalise_punctuation(note)

            leaks = [w for w in NOTE_MUST_NOT_MENTION if w in note.lower()]
            if leaks:
                rejected.append(
                    f"rejected: mentions {leaks[0]}, which references email")
                continue

            trial = dict(rec)
            trial["cadence"] = {**(rec.get("cadence") or {}),
                                key: {}}
            failures = [f for f in lint.check_step(trial, key,
                                                   {"channel": "linkedin",
                                                    "generated": True,
                                                    "note": note})
                        if f not in lint.LINKEDIN_HELD_CODES]
            for problem in claims.check(note, trial, contact)[:3]:
                failures.append(
                    f"unsupported claim: {problem['why']}")
            for invented in claims.foreign_product(
                    note, clients.product(client or {}), rec):
                failures.append(invented["why"])

            prev_steps = [{"key": k, "text": v}
                          for k, v in sorted(generated.items())]
            if prev_steps:
                company = ((rec.get("company_facts") or {}).get("name")
                           or rec.get("company"))
                for collision in quality.campaign_repetition(
                        prev_steps + [{"key": step_key, "text": note}],
                        company_name=company):
                    involved = (collision.get("step_a"),
                                collision.get("step_b"))
                    if step_key not in involved:
                        continue
                    shared = ", ".join(
                        collision.get("shared", [])[:5])
                    failures.append(
                        f"says the same thing as "
                        f"{collision['step_a'] if involved[0] != step_key else collision['step_b']} "
                        f"({shared})")

            if not failures:
                best_note = note
                break
            rejected.append(lint.explain(failures, note))

        if best_note is None:
            total_calls += step_calls
            count_model_call("linkedin_set", total_calls)
            return None

        generated[step_key] = best_note
        total_calls += step_calls

    if len(generated) != len(li_specs):
        count_model_call("linkedin_set", total_calls)
        return None

    all_steps = [{"key": k, "text": v} for k, v in sorted(generated.items())]
    company = (rec.get("company_facts") or {}).get("name") or rec.get("company")
    final_collisions = quality.campaign_repetition(all_steps,
                                                   company_name=company)
    if final_collisions:
        count_model_call("linkedin_set", total_calls)
        return None

    committed = []
    for spec in li_specs:
        step_key = spec["key"]
        step = {"channel": "linkedin", "generated": True,
                "note": generated[step_key]}
        # LADDER FINGERPRINT (TASK-083).
        _, ordinal, _ = position(sequence, step_key)
        fp = ladder_fingerprint("linkedin", ordinal, sequence=sequence)
        if fp:
            step["ladder_fingerprint"] = fp
        step = store_step(rec, key, step_key, step)
        committed.append(step)

    count_model_call("linkedin_set", total_calls)
    store.log(rec, "linkedin_set",
              f"{contact.get('name')}: {len(committed)} notes regenerated "
              f"as a set")
    for spec in li_specs:
        events.record(rec, events.DRAFT_GENERATED, contact_key=key,
                      channel="linkedin", step=spec["key"], generated=True)
    return committed


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


def linkedin_note(rec, contact, model, client=None, step_key="day3",
                  sequence=None):
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

    `sequence` is the resolved sequence for this contact. When provided,
    the ladder fingerprint is computed and stored on the step (TASK-083).
    """
    key = lint.contact_key(contact)
    rejected = []
    total_attempts = 0
    for attempt in range(1, MAX_DRAFT_ATTEMPTS + 1):
        prompt = render_prompt("linkedin_note", rec, contact, client, step_key)
        if rejected:
            prompt += ("\n## Your previous note was refused\n\n"
                       f"{rejected[-1]}\n\nWrite a new one. "
                       "Do not patch the old one.\n")
        data, attempts, errors = llm.ask(model, "linkedin_note", prompt)
        total_attempts += attempts
        note = data["note"].strip()
        # NORMALISE PUNCTUATION BEFORE LINT. A character substitution that
        # changes no word is not a content failure and must not spend an
        # attempt. The model is told plainly to use ASCII punctuation and
        # sometimes ignores it; normalising here means the draft never
        # fails on encoding, and the full attempt budget stays available
        # for actual content issues. The mapping is exactly
        # lint.SUBSTITUTED_PUNCTUATION and nothing else.
        note = lint.normalise_punctuation(note)
        step = {"channel": "linkedin", "generated": True, "note": note}
        leaks = [w for w in NOTE_MUST_NOT_MENTION if w in note.lower()]
        if leaks:
            # Unchanged, and still first: a note that mentions the email is
            # refused outright rather than regenerated, because the prompt
            # already states the rule plainly and a retry teaches nothing.
            store.log(rec, "linkedin_note", f"rejected, mentions {leaks[0]}")
            return None
        trial = dict(rec)
        trial["cadence"] = {**(rec.get("cadence") or {}),
                            key: {**((rec.get("cadence") or {}).get(key) or {}),
                                  step_key: step}}
        failures = [f for f in lint.check_step(trial, key, step)
                    if f not in lint.LINKEDIN_HELD_CODES]
        for problem in claims.check(note, trial, contact)[:3]:
            failures.append(f"unsupported claim: {problem['why']}")
        for invented in claims.foreign_product(
                note, clients.product(client or {}), rec):
            failures.append(invented["why"])
        repeats = _note_quality(trial, contact,
                                (trial.get("cadence") or {}).get(key) or {},
                                step_key, client)
        if repeats:
            failures.append(f"this repeats another LinkedIn step in the "
                            f"sequence; say something the others do not "
                            f"({', '.join(repeats)})")
        if not failures:
            # LADDER FINGERPRINT (TASK-083). Stored on the step so a future
            # ladder change can be detected.
            if sequence is not None:
                _, ordinal, _ = position(sequence, step_key)
                fp = ladder_fingerprint("linkedin", ordinal, sequence=sequence)
                if fp:
                    step["ladder_fingerprint"] = fp
            store_step(rec, key, step_key, step)
            count_model_call("linkedin_note", total_attempts)
            store.log(rec, "linkedin_note", note[:80],
                      attempts=total_attempts, rejected=rejected)
            events.record(rec, events.DRAFT_GENERATED, contact_key=key,
                          channel="linkedin", step=step_key, generated=True)
            return step
        rejected.append(lint.explain(failures, note))
        events.record(rec, events.LINT_FAILED, contact_key=key,
                      channel="linkedin", step=step_key, failures=failures,
                      attempt=attempt)
    store.log(rec, "linkedin_note",
              f"{step_key}: no note passed the gates, nothing stored",
              attempts=total_attempts, rejected=rejected)
    return None


def draft(rec, contact, day, model, client=None, sequence=None):
    """Generate, lint, regenerate. Never patch, never widen a rule.

    `day` is the STEP KEY, which is what it has always been - `day1`,
    `day15`, and now `em1`..`em5` under a sequence that names them that way.
    It is passed to the prompt so the draft knows which rung of
    `EMAIL_LADDER` it is writing and what the earlier rungs already spent.

    `sequence` is the resolved sequence for this contact. When provided,
    the ladder fingerprint is computed and stored on the step, so a future
    ladder change can be detected (TASK-083).
    """
    key = lint.contact_key(contact)
    rejected = []
    for attempt in range(1, MAX_DRAFT_ATTEMPTS + 1):
        prompt = render_prompt("draft", rec, contact, client, day)
        if rejected:
            # THE REASON, NOT THE CODE. This fed back `filler_phrase`, and
            # a model told `filler_phrase` three times has been told
            # nothing three times - three uninformative retries is a step
            # that never gets written. Measured 2026-09-13: `em5` failed
            # exactly this way for six of twenty records across two full
            # regeneration passes, and six contacts could not be staged
            # for want of one message each. `lint.explain` names the
            # offending phrase where it can.
            prompt += ("\n## Your previous draft failed lint\n\n"
                       f"{rejected[-1]}\n\nWrite a new one. "
                       "Do not patch the old one.\n")
        data, _, schema_errors = llm.ask(model, "draft", prompt)
        # NORMALISE PUNCTUATION BEFORE LINT. A character substitution that
        # changes no word is not a content failure and must not spend an
        # attempt. The model is told plainly to use ASCII punctuation and
        # sometimes ignores it; normalising here means the draft never
        # fails on encoding, and the full attempt budget stays available
        # for actual content issues. The mapping is exactly
        # lint.SUBSTITUTED_PUNCTUATION and nothing else.
        subject = lint.normalise_punctuation(data["subject"])
        body = lint.normalise_punctuation(data["body"])
        candidate = {"channel": "email", "generated": True,
                     "subject": subject, "body": body}
        # Lint the candidate against a copy: a failing draft is never stored.
        trial = dict(rec)
        trial["cadence"] = {**(rec.get("cadence") or {}),
                            key: {**((rec.get("cadence") or {}).get(key) or {}),
                                  day: candidate}}
        failures = lint.check(trial, key, candidate)
        # AND THE CLAIMS, HERE, NOT ONLY AT SEND TIME.
        #
        # `claims.check` was called in exactly one place - `executionguard`,
        # at the moment of sending - so a draft asserting something the
        # record does not support was generated, stored, approved, and
        # carried to the provider as a per-lead variable before anything
        # looked at it. Measured 2026-09-14 on EmailBison lead 203708: the
        # em5 subject read "Final note on our previous discussions" for a
        # contact this system has never written to.
        #
        # `claims.prior_contact` already exists to license exactly that
        # phrase and reads confirmed touches from the event log. It was
        # being used to TELL the prompt whether prior contact existed, and
        # never to check whether the answer was respected.
        #
        # Checked against the same trial record lint sees, so a claim is
        # judged against the record as it will be stored. A failing draft is
        # regenerated, never patched.
        unsupported = claims.check(
            f"{candidate['subject']}\n{candidate['body']}", trial, contact)
        content_failures = [f for f in failures if f not in lint.HELD_CODES]
        if unsupported:
            content_failures = content_failures + [
                f"unsupported claim: {c}" for c in unsupported[:3]]
        # AND THE QUALITY GATE, INSIDE THE ATTEMPT LOOP. Wiring it only into
        # `plan` made it re-plan a repetitive draft and then store another
        # one, because `draft` was still storing anything lint and claims
        # accepted - so a run regenerated and re-stored copy that repeated,
        # and the next run asked again. The gate has to refuse at the point
        # of storing, exactly as the other two do, or it is advisory.
        #
        # Checked against the trial record, so the step being written is
        # compared with its siblings AS THEY WILL BE STORED. The company's
        # own name is discounted - naming the prospect's company in every
        # message is relevance, not repetition.
        repeats = _quality_of(trial, contact,
                              (trial.get("cadence") or {}).get(key) or {},
                              day, client)
        if repeats:
            content_failures = content_failures + [
                f"this repeats another step in the sequence; say something "
                f"the others do not ({', '.join(repeats)})"]
        if not content_failures:
            # LADDER FINGERPRINT (TASK-083). Stored on the step so a future
            # ladder change can be detected by comparing this against the
            # current ladder's fingerprint for the same channel and ordinal.
            if sequence is not None:
                _, ordinal, _ = position(sequence, day)
                fp = ladder_fingerprint("email", ordinal, sequence=sequence)
                if fp:
                    candidate["ladder_fingerprint"] = fp
            store_step(rec, key, day, candidate)
            store.log(rec, "draft", f"{contact.get('name')} {day}: {data['subject']}",
                      attempts=attempt, rejected=rejected)
            count_model_call("draft", attempt)
            events.record(rec, events.DRAFT_GENERATED, contact_key=key,
                          channel="email", step=day, generated=True)
            return candidate
        rejected.append(lint.explain(
            content_failures,
            f"{candidate.get('subject') or ''} "
            f"{candidate.get('body') or ''}"))
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

def generate_variants(rec, contact, model, spec, client=None, campaign=None):
    """Generate five approach-labelled variants for one step.

    Wires `variantgen` into the production path. Each variant is generated
    against the ladder's purpose for the rung, gated by claims, and stored
    on the step spec with its approach recorded as the style.

    Returns the list of variant entries on success, None on failure.
    """
    from . import variantgen, lint

    key = lint.contact_key(contact)
    # A CHANNEL IS NOT A NODE TYPE, and passing one where the other belongs
    # was silent rather than loud. `variantgen.APPROACH_TO_STYLE` is keyed by
    # node type - "linkedin_message", "connection_request", "email" - and
    # `style_for` falls back to the EMAIL table for anything it does not
    # recognise. So "linkedin" did not miss the mapping; it got the WRONG
    # CHANNEL'S mapping, and every LinkedIn variant built here was styled as
    # email. value_led resolved to `professional` where LinkedIn's table says
    # `peer_to_peer`.
    #
    # `cadence.NODE_TYPE_FOR_CHANNEL` is the canonical translation and already
    # existed; `cadence.variant_node` uses it and this path did not. A step may
    # name its own node_type, and the channel decides otherwise - same
    # precedence as variant_node, so the two cannot disagree.
    from . import cadence as _cadence
    node_type = (spec.get("node_type")
                 or _cadence.NODE_TYPE_FOR_CHANNEL.get(spec.get("channel"))
                 or spec.get("channel", "email"))
    sequence = sequence_for(rec, client, contact, campaign)

    result = variantgen.build_variant_set(
        rec, contact, node_type, spec["key"],
        sequence=sequence, config=client,
        llm_ask=llm.ask, model=model)

    variant_entries = result.get("variants") or []
    skipped = result.get("skipped") or []

    if not variant_entries:
        store.log(rec, "variant_set",
                  f"{spec['key']}: no variants passed the gates",
                  rejected=[s.get("why", "") for s in skipped])
        return None

    # Check differentiation
    if not result.get("different", True):
        problems = result.get("problems") or []
        store.log(rec, "variant_set",
                  f"{spec['key']}: variants are not materially different",
                  rejected=[p.get("why", "") for p in problems])
        return None

    # Store the variants on the step spec
    spec.setdefault("variants", [])
    for entry in variant_entries:
        spec["variants"].append(entry)

    count_model_call("variant_set",
                     sum(1 for _ in variant_entries) + len(skipped))
    store.log(rec, "variant_set",
              f"{spec['key']}: {len(variant_entries)} variants generated, "
              f"{len(skipped)} skipped",
              approaches=[v.get("style") for v in variant_entries])
    return variant_entries


def generate_record(rec, model, client=None, campaign=None,
                    regen_stale_ladder=False):
    """Every step this record needs, in order, stopping at the first that fails.

    `client` reaches `plan` now and did not before. It always mattered -
    `channels.linkedin_verdict` and `note_mode` both take it - and it matters
    more since the sequence decides which steps are written: planning without
    the config resolves the module constant and would draft `day1`/`day15`
    for a record whose client runs `em1`..`em5`.

    `regen_stale_ladder` is threaded through to `plan` (TASK-083).
    """
    done = []
    for op in plan(rec, client, campaign, regen_stale_ladder=regen_stale_ladder):
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
                seq = sequence_for(rec, client, contact, campaign)
                if not linkedin_note(rec, contact, model, client, op["day"],
                                     sequence=seq):
                    continue
            elif op["step"] == "linkedin_set" and contact:
                if not _regenerate_linkedin_set(rec, contact, model, client):
                    continue
            elif op["step"] == "draft" and contact:
                seq = sequence_for(rec, client, contact, campaign)
                if not draft(rec, contact, op["day"], model, client,
                             sequence=seq):
                    continue
            elif op["step"] == "variant_set" and contact:
                spec = _step_spec(rec, client, contact, op.get("day"),
                                  campaign)
                if spec and not generate_variants(rec, contact, model, spec,
                                                  client, campaign):
                    continue
            done.append(op)
        except (llm.NoModelConfigured, llm.ModelUnavailable):
            # A FAULT OF OURS IS NOT A FAULT OF THE RECORD. Holding here
            # wrote "nobody set LLM_API_KEY", or "we are over our daily
            # quota", into canonical state as though this company were the
            # problem - once per record, with no event, and the run still
            # printed GENERATED.
            #
            # And the hold is not recoverable. Nothing in this repository
            # moves a record out of `held`, and `approve.EMAIL_REFUSED_STATES`
            # refuses to approve one, so a rate limit that lasts an hour
            # parks a company forever. Measured 2026-09-13: eighteen of
            # twenty records held on `429 free-models-per-day`, none of which
            # had anything wrong with it.
            #
            # Raising stops the run, tells the operator once, before anything
            # is saved, and leaves no record carrying the blame. A model that
            # failed ON a record - malformed JSON three times over, a draft
            # that will not pass lint - still holds it, below.
            raise
        except llm.ModelError as e:
            store.log(rec, op["step"], f"held: {e}")
            if rec.get("state") not in ("dropped", "pushed"):
                rec["state"] = "held"
                from . import holdreasons
                msg = str(e)
                if "not traceable" in msg:
                    code = holdreasons.GENERATION_EVIDENCE_TRACE
                elif ("non-empty list" in msg
                      or ("evidence" in msg and "empty" in msg)):
                    code = holdreasons.GENERATION_EVIDENCE_EMPTY
                elif "not JSON" in msg or "JSON" in msg:
                    code = holdreasons.GENERATION_JSON_PARSE
                elif "lint" in msg.lower():
                    code = holdreasons.GENERATION_LINT_FAILURE
                else:
                    code = f"generation:{op['step']}:{e}"
                holdreasons.set_hold_reason(rec, code, detail=str(e))
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


def generate_step_variants(step_key, rec, contact, model, client=None,
                           campaign=None, n=5):
    """Generate N materially different variants for one step.

    The caller that proves this is connected: `plan` does not call this
    directly yet (Claude owns live generation), but the function is
    reachable from `generate` and the tests drive it through here, not
    through `variantgen` directly.

    Returns the result dict from `variantgen.generate_variants`:
      - `variants`: list of variant dicts with recorded approaches
      - `skipped`: list of (style, reason) for unavailable approaches
      - `diversity_collisions`: synonym-swap pairs caught by the check
      - `approaches_recorded`: list of style keys that were generated
    """
    from . import variantgen

    config = client if isinstance(client, dict) else None
    if client is not None and not isinstance(client, dict):
        try:
            config = clients.load(client)
        except clients.ConfigError:
            config = None

    sequence = sequence_for(rec, config, contact, campaign)
    channel = None
    purpose = None
    for spec in sequence or ():
        if spec.get("key") == step_key:
            channel = spec.get("channel")
            _, ordinal, _ = position(sequence, step_key)
            purpose = purpose_for(channel, ordinal, sequence=sequence)
            break
    if channel is None:
        return {"variants": [], "skipped": [],
                "diversity_collisions": [], "approaches_recorded": [],
                "error": f"step {step_key!r} not found in sequence"}

    step_context = {"key": step_key, "channel": channel, "purpose": purpose}
    return variantgen.generate_variants(
        step_context, rec, contact, model, channel=channel,
        client=config, campaign=campaign, config=config, n=n)
def _step_spec(rec, client, contact, step_key, campaign=None):
    """Find the sequence spec for a given step key."""
    if not step_key:
        return None
    sequence = sequence_for(rec, client, contact, campaign)
    for spec in sequence:
        if spec.get("key") == step_key:
            return spec
    return None


def run(model=None, live=False, ids=None, limit=None, client=None,
        regen_stale_ladder=False):
    """Dry by default: reports what would be asked without asking anything.

    `regen_stale_ladder` is OPT-IN (TASK-083). When True, plan treats steps
    whose ladder fingerprint does not match the current ladder as needing
    regeneration. When False (the default), plan behaves exactly as before.
    """
    # TASK-162: reset the company evidence cache at the start of each pass.
    # The cache lives for the duration of one pass, not across sessions.
    clear_company_cache()
    recs = store.load()
    model = model or llm.NoModel()
    targets = [r for r in recs if ids is None or r["id"] in ids]
    if limit:
        targets = targets[:limit]

    report = []
    stale_steps = 0
    stale_with_approval = 0
    for rec in targets:
        if live:
            # CHECKPOINT PER RECORD. This loaded the estate, worked, and saved
            # ONCE at the end - so a run across eighteen records that died
            # fifty minutes in wrote nothing at all, and every model call in
            # that window had been paid for. Measured 2026-09-13: no log, no
            # exit code, no drafts.
            #
            # Same argument and same shape as `bisonfactory._remember_lead`,
            # which writes the provider's lead id in its own transaction
            # immediately. Through `store.transaction` so the evidence and
            # history loss guards still run - durability bought by defeating
            # them would be one loss traded for another.
            #
            # No resume flag, no checkpoint file, no new state. The estate IS
            # the checkpoint, because `plan` declines to re-draft a record
            # that already carries a clean one, so re-running the command is
            # the resume.
            #
            # This does NOT make two concurrent runs safe. A second run holds
            # a snapshot from before the first one's write and
            # `refuse_history_loss` correctly kills it. Runs are sequential.
            with store.transaction() as rows:
                target = next(r for r in rows if r["id"] == rec["id"])
                ops = generate_record(target, model, client,
                                      regen_stale_ladder=regen_stale_ladder)
                state = target.get("state")
        else:
            ops = plan(rec, client, regen_stale_ladder=regen_stale_ladder)
            state = rec.get("state")
        # Count ladder-stale ops and their approvals for the impact report.
        if regen_stale_ladder:
            from . import approval as _approval
            for op in ops:
                if not op.get("ladder_stale"):
                    continue
                # TASK-129: a linkedin_set op with ladder_stale represents
                # multiple stale steps (stored in stale_step_count), not one.
                # Without this, the impact report undercounts stale steps
                # for contacts whose notes are absorbed into a set.
                step_weight = op.get("stale_step_count", 1)
                stale_steps += step_weight
                # `op["contact"]` is the DISPLAY NAME ("Jacob Faertz") and the
                # cadence is keyed by the contact KEY ("jacob-faertz"). Building
                # a key out of the display name misses every time, so this
                # counted ZERO approvals on an estate holding them - and
                # "0 approvals would be revoked" is the most reassuring
                # possible wrong answer to the one question the operator has to
                # decide. Resolve the real contact instead.
                ck = None
                for _c in (rec.get("contacts") or []):
                    if op.get("contact") in (_c.get("name"), _c.get("key")):
                        ck = _c.get("key")
                        break
                if ck is None:
                    ck = lint.contact_key(
                        {"name": op.get("contact", ""),
                         "key": op.get("contact", "")})
                # TASK-129: for a linkedin_set op, check each step in the
                # contact's cadence for approval, not just op["day"] (which
                # is None for a set op).
                if op.get("step") == "linkedin_set":
                    contact_steps = ((rec.get("cadence") or {}).get(ck)
                                     or {})
                    for step_key, step_data in contact_steps.items():
                        if not step_data.get("channel") == "linkedin":
                            continue
                        if _approval.is_approved(rec, ck, step_key,
                                                 step_data):
                            stale_with_approval += 1
                else:
                    step_data = ((rec.get("cadence") or {}).get(ck) or {}) \
                        .get(op.get("day")) or {}
                    if _approval.is_approved(rec, ck, op.get("day", ""),
                                             step_data):
                        stale_with_approval += 1
        report.append({"id": rec["id"], "lane": rec.get("lane"),
                       "state": state, "ops": ops})
    return {"live": live, "model": getattr(model, "name", "unknown"),
            "records": report, "regen_stale_ladder": regen_stale_ladder,
            "stale_steps": stale_steps,
            "stale_with_approval": stale_with_approval}


def main(argv=None):
    p = argparse.ArgumentParser(prog="python -m src.generate")
    p.add_argument("--live", action="store_true",
                   help="actually call the model (none is configured by default)")
    p.add_argument("--id", action="append", dest="ids")
    p.add_argument("--limit", type=int)
    p.add_argument("--client", help="whose cadence and tone the drafts follow")
    p.add_argument("--regen-stale-ladder", action="store_true",
                   help="re-plan steps whose ladder fingerprint does not "
                        "match the current ladder (TASK-083). OPT-IN: "
                        "without this flag, plan is unchanged.")
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
                 client=config, regen_stale_ladder=a.regen_stale_ladder)

    # IMPACT REPORT (TASK-083). When the flag is set, report how many steps
    # are ladder-stale and how many carry current approvals BEFORE listing
    # the per-record detail. Running this revokes approvals (correct but
    # expensive), so the operator sees the price before it is paid.
    if a.regen_stale_ladder:
        stale_steps_count = result['stale_steps']
        stale_with_approval_count = result['stale_with_approval']
        print(f"\nLADDER STALENESS REPORT (TASK-083):")
        print(f"  steps to re-plan:              "
              f"{stale_steps_count}")
        print(f"  approvals that would be "
              f"revoked: {stale_with_approval_count}")
        # TASK-128: distinguish "no stale steps" from "stale steps I will not
        # touch". An operator reading "0 steps to re-plan" concludes there is
        # nothing to decide. But if there are stale steps protected by
        # approval, the operator MUST decide: revoke and regenerate, or leave
        # them. These are different answers to the same question, and they
        # previously printed identically.
        if stale_steps_count == 0:
            print(f"  (no ladder-stale steps found)")
        elif stale_with_approval_count > 0:
            protected = stale_with_approval_count
            will_regen = stale_steps_count - stale_with_approval_count
            print(f"  {protected} stale step(s) protected by approval "
                  f"(will not regenerate without explicit revocation)")
            if will_regen > 0:
                print(f"  {will_regen} stale step(s) will be regenerated")
        else:
            print(f"  all {stale_steps_count} stale step(s) will be regenerated")
        if not a.live:
            print(f"  (dry run - nothing was changed)")
        print()

    head = "GENERATED" if a.live else "DRY RUN, no model called"
    print(f"{head}: {len(result['records'])} record(s), model={result['model']}")
    for r in result["records"]:
        print(f"\n  {r['id']} ({r['lane']}) state={r['state']}")
        for o in r["ops"]:
            detail = f" [{o['contact']}{' ' + o['day'] if o.get('day') else ''}]" \
                if o.get("contact") else ""
            stale_mark = " [LADDER STALE]" if o.get("ladder_stale") else ""
            print(f"    {o['step']:<14}{detail:<28} {o['why']}{stale_mark}")
        if not r["ops"]:
            print("    nothing to generate")
    if not a.live:
        print("\nno model ships with this repo: pass one to run(model=...).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
