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


def angles_for_contact(contact, client):
    """The angles configured for THIS contact's persona, as {key: phrase}.

    THE DEFECT THIS CLOSES. `context_for` passed `client.get("angles")` into
    the `persona_angle` prompt, and no client config has a top-level `angles`
    key - `config/clients/productive.yaml` keeps them under
    `personas.<persona>.angles`, which is where `clients.angles_for` has always
    read them from. So the rendered prompt literally ended `"angles": null`
    while its own contract told the model the angle "must be one of the angles
    configured for that persona". Measured 2026-10-01: the model answered
    `{"angle": null, "evidence": []}` on every attempt - correct behaviour for
    a closed list it was never shown.

    The persona is on the CONTACT, written by `personas.select` and the one
    thing that decides which of the client's angle sets applies. An account-
    level persona is NOT substituted for it: `clients.angles_for` with no
    persona returns `{}`, and `llm.check_angle` refuses on an empty mapping
    rather than letting a guess through - the same answer `default_angle`
    gives, which holds the contact.
    """
    persona = (contact or {}).get("persona")
    # `personas.select` writes a string, but `generate_campaign` already
    # defends against a dict here and this is read by a gate: same shape.
    if isinstance(persona, dict):
        persona = persona.get("key")
    return clients.angles_for(client or {}, persona or "")


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
        # The persona's own angles, keyed - see `angles_for_contact`. The KEY
        # is what the model must answer with and `llm.check_angle` enforces,
        # and the phrase beside it is what the key MEANS.
        block["angles"] = angles_for_contact(contact, client)
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
    # UNDER THE CLIENT'S OWN VERIFICATION POLICY, like `lint.check` and
    # `channels.email_verdict`. This asked `lint.sendable(c)` - the DEFAULTS -
    # and it is the gate that decides whether an email is DRAFTED at all.
    #
    # MEASURED 2026-09-30: 787 contacts across the estate are cleared by
    # Productive's own policy and refused by the defaults, because the client
    # moved primary verification to Deliverable and dropped ContactOut on
    # 2026-09-21. Every one of them was silently excluded from email
    # drafting - which is why so many records carry em1..em3 and stop, and
    # why a contact whose address every other authority accepts had no em4 or
    # em5 to stage. `policy_for_record` already records what this cost the
    # last time two callers disagreed: "lint kept answering under the
    # defaults and refused 564 steps whose addresses the client's own policy
    # had cleared".
    #
    # The rule above it is untouched: no email is generated for an unverified
    # address. This asks the client's question about what "verified" means.
    sendable = [c for c in rec.get("contacts") or []
                if lint.sendable(c, lint.policy_for_record(rec))]
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

        # AND THE SEQUENCE GATE, WHICH IS THE FOURTH OF THE SAME KIND, and
        # the last one still invisible here. Lint asks whether the words
        # break a rule, claims whether they assert something untrue, quality
        # whether they repeat a sibling - and `sequencegate` asks whether the
        # sequence climbs the offer's approved ladder. It refuses at staging,
        # so a sequence it rejects is stored, reported as finished work, and
        # stopped two gates later with no path back: the planner schedules
        # nothing, so regeneration cannot converge.
        #
        # MEASURED 2026-09-29 on the Rachele canary: the gate refused em3 and
        # em4 for `step_objectives`, and FOUR canonical whole-set
        # regenerations left all eleven steps BYTE-IDENTICAL, because the
        # planner emitted no email op at all. That is the same shape as the
        # three gates above, one level up.
        #
        # AFTER the per-step loop, not inside it: the ladder is a property of
        # the sequence, and one step in isolation cannot be out of order.
        for key, why in _ladder_failures(rec, c, stored, sequence,
                                         client).items():
            if any(o.get("day") == key and o.get("contact") == c.get("name")
                   for o in ops):
                continue
            ops.append({"step": "draft",
                        "why": f"{c['name']}'s {key} email is out of the "
                               f"offer's approved order ({why})",
                        "contact": c.get("name"), "day": key,
                        "ladder_order": True})

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
            data, attempts, errors = llm.ask(model, "linkedin_note",
                                             prompt, rec=rec,
                                             client=client or rec.get("client"))
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
    data, attempts, errors = llm.ask(model, "diagnose",
                                     render_prompt("diagnose", rec), rec=rec,
                                     client=rec.get("client"))
    rec["diagnosis"] = {"died_on": data.get("died_on"),
                        "died_because": data["died_because"],
                        "failure_mode": data["failure_mode"],
                        "last_position": data.get("last_position"),
                        "what_changed": data.get("what_changed")}
    store.log(rec, "diagnose", f"{data['failure_mode']} on {data.get('died_on')}",
              attempts=attempts, rejected=errors)
    return rec["diagnosis"]


def hook(rec, model):
    data, attempts, errors = llm.ask(model, "hook", render_prompt("hook", rec), rec=rec,
                                     client=rec.get("client"))
    rec["hook"] = data["hook"]
    store.log(rec, "hook", data["hook"][:80], attempts=attempts, rejected=errors)
    return rec["hook"]


def persona_angle(rec, contact, model, client=None, config=None):
    """The angle plus its evidence. Evidence that is not traceable is rejected.

    THE CONFIG IS LOADED WHEN IT WAS NOT PASSED, the same way `note_mode` does
    it, because the angles are now load-bearing in both directions: they are
    what the prompt SHOWS the model and what `llm.check_angle` holds the answer
    to. Every caller in `src/` passes it; the ones that do not are tests and
    scripts, and leaving them with `{}` would mean an empty angle list in the
    prompt and a refusal on every answer - failing closed, but on configuration
    rather than on the behaviour. A client with no config file still resolves to
    `{}` and still fails closed; that is deliberate and unchanged.
    """
    if config is None:
        config = client if isinstance(client, dict) else None
    if config is None:
        try:
            config = clients.load(rec.get("client"))
        except clients.ConfigError:
            config = {}
    data, attempts, errors = llm.ask(
        model, "persona_angle", render_prompt("persona_angle", rec, contact, config),
        rec=rec, client=client or rec.get("client"),
        angles=angles_for_contact(contact, config))
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
        data, attempts, errors = llm.ask(model, "linkedin_note", prompt,
                                         rec=rec,
                                         client=client or rec.get("client"))
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
        data, _, schema_errors = llm.ask(model, "draft", prompt, rec=rec,
                                         client=client or rec.get("client"))
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


#: The ops the CAMPAIGN PIPELINE answers. TASK-400: `draft`, `linkedin_note`
#: and `linkedin_set` are no longer written by the old per-step stage functions
#: - `generate_campaign.generate()` writes the whole set once per record and
#: these ops are satisfied by reading back what it stored. The research ops
#: (`diagnose`, `hook`, `persona_angle`) are NOT copy and stay where they are:
#: the campaign pipeline has no diagnose stage, and a revive record's thread
#: diagnosis is the only thing that says what killed the conversation.
_WRITER_OPS = frozenset({"draft", "linkedin_note", "linkedin_set"})


def _op_now_stored(rec, contact, op, written):
    """Did THIS campaign write satisfy this op? Asked of both the write and the
    record.

    `written` is the (contact_key, step_key) set `_adapt_plan_to_cadence`
    actually stored. Both halves are load-bearing:

    - the record, because a contact whose copy every gate refused produces a
      plan entry and no cadence row, and counting that as done is how a run
      reports GENERATED with nothing to send;
    - and `written`, because a REGENERATION starts with rows already there. Only
      reading the record made a `linkedin_set` op "done" whenever any generated
      LinkedIn step existed, which is true of every record being regenerated -
      so a campaign write that stored nothing still reported the set replaced.
      Caught by pointing `test_set_regeneration`'s falsification test at the new
      consumer.
    """
    ck = lint.contact_key(contact)
    stored = (rec.get("cadence") or {}).get(ck) or {}

    def present(step_key):
        step = stored.get(step_key) or {}
        return bool(step.get("generated")
                    and (step.get("body") or step.get("note")))

    if op["step"] == "linkedin_set":
        return any(k == ck and present(s) for k, s in written)
    day = op.get("day")
    return (ck, day) in written and present(day)


def research_rows(rec):
    """How many research rows this record carries. The raw count.

    NOT `research_block`'s filtered count, deliberately. `research_block`
    returns only `medium`/`strong` rows for the PROMPT; the claims gate reads
    `rec["research"]` whole, and `sequencegate.reason_for_outreach` already
    refuses an em1 that shares no content word with a researched fact. So the
    quality question has an owner and this is the other one: does the input
    exist at all. Widening this to "zero USABLE rows" would be a second rule
    about quality in a place that is asking about existence.
    """
    return len(rec.get("research") or [])


def entry_gates(rec, client=None, steps=("em1", "em3")):
    """The holds that must be answered BEFORE the writer is called.

    Returns `[(step_key, hold_code), ...]`, empty when nothing is held.

    THE OPERATOR'S TWO GENERATION-SIDE GATES, TASK-976 scope items 2 and 3:

      em1  with NOTHING TO WRITE FROM -> `research_required`. The alternative
           to holding is a model call that produces filler the claims gate
           then refuses.

           TWO CONDITIONS, AND THE SECOND ONE IS A CORRECTION FORCED BY
           MEASUREMENT. The operator's words are "em1 with zero research
           rows", and that is condition one. Measured 2026-10-03 across this
           repository's generation fixtures: EVERY one of them carries zero
           `research` rows, and four of the five carry 2 to 8 facts that
           `facts_block` - the canonical list of what a prompt may see about
           a company - returns happily. So the literal trigger holds records
           that demonstrably have something true and specific to open with,
           which is not what the hold is for: it fired on eleven tests whose
           records were never short of evidence. `research` is ONE store of
           company evidence and `facts_block` is the authority on what the
           writer may use; a record with neither has nothing, and a record
           with either does not need this hold. Reported to the operator as a
           named deviation with this measurement rather than applied quietly.
      em3  with fewer than two CLIENT_APPROVED proof rows for the client ->
           `proof_required`. `claims.proof_rotation_satisfied` is the
           authority and the count is `claims.licensed_proof_rows`; TASK-964's
           rule 4 refuses the same proof in two steps, so ONE licensed row is
           a sequence that must repeat itself.

    WHAT IS DELIBERATELY NOT HERE: the offer. An unapproved offer must
    GENERATE and must not SEND - the operator's explicit split - so it is
    `eligibility._offer_unapproved` and nothing in this function looks at
    `client_approved`. A gate here that refused generation would have broken
    the copy-review loop this whole order exists to feed.

    `steps` is the set under consideration so a caller generating only the
    thread replies is not held on em3's proof rows. It is narrowed by the
    caller and never widened here.
    """
    from . import holdreasons
    name = client if isinstance(client, str) else (
        (client or {}).get("name") if isinstance(client, dict) else None)
    name = name or rec.get("client")
    held = []
    if ("em1" in steps and research_rows(rec) == 0
            and not facts_block(rec)):
        held.append(("em1", holdreasons.GENERATION_RESEARCH_REQUIRED))
    # `is False`, NOT `not`, AND THE DIFFERENCE IS A TENANT.
    # `proof_rotation_satisfied` has three answers: True, False, and None for
    # a client the single-tenant offer library does not describe. `not None`
    # is True, so `not` would have held em3 for every client but Productive
    # on the strength of a question nobody asked - the blanket refusal
    # TASK-976's own negative control warned about, one layer along. UNKNOWN
    # is still never a pass on the SEND path, where `eligibility` fails closed
    # on the offer's `client_approved` flag and `claims.check` refuses an
    # unlicensed customer-outcome sentence whatever the tenant.
    if "em3" in steps and claims.proof_rotation_satisfied(name) is False:
        held.append(("em3", holdreasons.GENERATION_PROOF_REQUIRED))
    return held


def generate_record(rec, model, client=None, campaign=None,
                    regen_stale_ladder=False, live=False,
                    allow_pending_offers=False,
                    allow_whole_set_regeneration=False):
    """Every step this record needs, in order, stopping at the first that fails.

    `client` reaches `plan` now and did not before. It always mattered -
    `channels.linkedin_verdict` and `note_mode` both take it - and it matters
    more since the sequence decides which steps are written: planning without
    the config resolves the module constant and would draft `day1`/`day15`
    for a record whose client runs `em1`..`em5`.

    `regen_stale_ladder` is threaded through to `plan` (TASK-083).

    TASK-400: every COPY op is answered by `generate_campaign.generate()`, once
    per record, through `_generate_via_campaign`. `NotApproved` and
    `CampaignPipelineError` propagate; a `llm.ModelError` holds the record the
    same way it always did.
    """
    done = []
    campaign_plan = None
    written = set()

    def _entry_gate_hold():
        """The two entry gates, applied BEFORE the writer is called.

        Returns True when the record is held. See `entry_gates`.

        WHY IT IS HERE AND NOT ABOVE THE LOOP, and this was measured rather
        than reasoned: holding before `plan()` ran also skipped `diagnose`
        and `hook`, which are not writer steps, cost no copy, and are what
        several modules drive this function for - and it swallowed the
        `NoModelConfigured` RAISE those ops produce, turning "nobody
        configured a model" back into a held record, which is the exact
        defect the `llm.NoModelConfigured` branch below exists to prevent.
        Checked at the writer instead: nothing the gate protects has been
        spent, because the writer is the only step that writes copy, and it
        is checked ONCE because `_generate_via_campaign` emits the whole set.
        """
        gates = entry_gates(rec, client)
        if not gates:
            return False
        from . import holdreasons
        detail = ", ".join("%s: %s" % (step, code) for step, code in gates)
        store.log(rec, "entry_gate", "held: %s" % detail)
        if rec.get("state") not in ("dropped", "pushed"):
            rec["state"] = "held"
            holdreasons.set_hold_reason(rec, gates[0][1], detail=detail)
        return True

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
            elif op["step"] in _WRITER_OPS and contact:
                # ONE CAMPAIGN CALL PER RECORD, not one per step. The writer
                # emits the whole set, so asking it again for the second step
                # would rewrite the first - which is precisely why
                # `_refuse_partial_regeneration` exists.
                if campaign_plan is None:
                    # THE CALLER'S CONTRACT FIRST, THEN THE RECORD'S VERDICT.
                    #
                    # Order measured, not chosen: with the gate first,
                    # `test_a_half_drafted_record_is_refused_by_name_without_
                    # the_flag` went green-to-red because a held record never
                    # reached the refusal, so a caller that would have
                    # destroyed half a generated set was told the record was
                    # held instead. `_refuse_partial_regeneration` is a
                    # refusal of the REQUEST and must surface whatever the
                    # record's own state is; `_entry_gate_hold` is a verdict
                    # ABOUT the record. Both are before any model call, so
                    # the gate still costs nothing either way.
                    _refuse_partial_regeneration(
                        rec, allow_whole_set_regeneration)
                    # THE ENTRY GATES. Before the writer, after nothing has
                    # been spent on copy.
                    if _entry_gate_hold():
                        break
                    campaign_plan = _generate_via_campaign(
                        rec, model, client, live=live,
                        allow_pending_offers=allow_pending_offers)
                    written = set(campaign_plan.get("stored_pairs") or ())
                if not _op_now_stored(rec, contact, op, written):
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


#: The per-record context `generate.py` supplies and `generate_campaign.py` does
#: not. Named here because the refusal below has to say what is missing rather
#: than fail vaguely.
_CONTEXT_THE_CAMPAIGN_PATH_LACKS = (
    "prior_contact", "already_sent", "siblings", "sender_identity", "purpose",
)


def _generated_steps(rec):
    """Every (contact_key, step_key) already carrying generated copy."""
    out = []
    for ck, steps in (rec.get("cadence") or {}).items():
        if not isinstance(steps, dict):
            continue
        for step_key, step in steps.items():
            if isinstance(step, dict) and step.get("generated"):
                out.append((ck, step_key))
    return out


def _refuse_partial_regeneration(rec, allow_whole_set_regeneration):
    """Refuse to regenerate ONE step through a batch writer. By name.

    TASK-391 rejected wiring the five skills into `generate.py`'s stages because
    that loses the rich per-record context. Routing generation through
    `generate_campaign` loses the SAME context: that module contains zero
    occurrences of `prior_contact`, `already_sent`, `siblings`,
    `sender_identity` or `purpose`, while `generate.py:context_for` supplies all
    five (`prior_contact` 641/663, `already_sent` 646, `siblings` 648,
    `sender_identity` 635/688, `purpose` via step_block/history_block/
    siblings_block).

    Two of them are correctness rather than polish. `sender_identity` decides
    which mailbox is writing, and the standing launch blocker is that 155 email
    steps render an empty signature - a default here would manufacture exactly
    that blocker. `purpose` is what the specific step is for, and a step written
    without it is a step written for no reason.

    And the shapes do not match: `_regenerate_linkedin_set` regenerates ONE
    step, while `copystages.WRITER_SYSTEM` emits eleven artifacts per call (em1
    to em5, ps on em1 and em3, connect, msg1 to msg3). Satisfying a one-step
    request through it means discarding ten outputs, or silently replacing the
    other ten - a whole-set regeneration where one step was asked for, which is
    invisible in a test that only inspects the step it asked about.

    So this REFUSES rather than defaulting. Chosen over threading the five
    fields into the campaign prompts because that is a redesign of
    `generate_campaign`'s prompt contract, it belongs with TASK-364/391 rather
    than inside a three-defect rework, and a refusal is honest today where a
    default would be silently wrong.

    `allow_whole_set_regeneration=True` is the deliberate escape: the caller is
    saying it accepts that all eleven artifacts are rewritten.
    """
    from . import generate_campaign

    if allow_whole_set_regeneration:
        return
    existing = _generated_steps(rec)
    if not existing:
        return
    raise generate_campaign.CampaignPipelineError(
        "record %r already carries %d generated step(s) %s. The campaign path's "
        "writer emits the whole set in one call and receives none of %s, so "
        "regenerating part of a record through it would either discard ten "
        "artifacts or rewrite steps nobody asked to change, and would render "
        "without a sender identity. Refusing. Pass "
        "allow_whole_set_regeneration=True to rewrite the entire set "
        "deliberately."
        % (rec.get("id"), len(existing), sorted(existing)[:4],
           ", ".join(_CONTEXT_THE_CAMPAIGN_PATH_LACKS)))


#: The order the campaign writer emits its steps in, per channel. These are the
#: WRITER's keys and they are not a cadence: `copystages.WRITER_SYSTEM` always
#: emits five emails and five LinkedIn steps whatever sequence the record is on.
#: LinkedIn keys come from `cadencelibrary.LINKEDIN_WRITER_KEYS` — one authority.
_PLAN_EMAIL_ORDER = ("em1", "em2", "em3", "em4", "em5")

#: Which of the writer's three subjects each of its email steps belongs to. A is
#: em1's thread and em2 replies inside it; B is em3's and em4 replies inside
#: that one; C is em5's. A step's subject is the subject of the THREAD it
#: belongs to, which is what `EMAILBISON-COPY-REQUIREMENTS.md` means by "a
#: sequence is one conversation" - and why em2's subject is em1's rather than
#: the empty string that refused every lead this pipeline produced.
_PLAN_SUBJECT_OF = {"em1": "A", "em2": "A", "em3": "B", "em4": "B", "em5": "C"}

#: WHICH OF THE WRITER'S FIVE EMAILS A SHORTER CADENCE TAKES, and in what order.
#: A cadence with two generated email steps is two NEW conversations, not an
#: opener and its reply, so it takes the writer's new-thread emails (em1, em3,
#: em5) before its replies. Taking em1 and em2 instead handed a reply to a step
#: that starts a thread, and gave both steps the same subject - which the
#: repetition gate then refused, correctly, for copy that was fine.
_PLAN_EMAIL_PREFERENCE = ("em1", "em3", "em5", "em2", "em4")


def _generated_keys(sequence, channel):
    """The steps of one channel this sequence says are GENERATED, in order."""
    return [s.get("key") for s in (sequence or ())
            if s.get("channel") == channel and s.get("generated")
            and s.get("key")]


def _linkedin_candidate_keys(rec, client_config, contact, sequence):
    """The LinkedIn steps generated copy is written for, ASKED THE SAME WAY
    `plan` asks.

    `plan`'s LinkedIn branch is `if note_mode(rec, client) == "llm" and c in
    on_linkedin:` and then EVERY linkedin spec in the sequence - not only the
    ones the cadence marks `generated`. Reading `spec["generated"]` instead
    missed `li1` under `productive_li_heavy_v1`, whose spec is a template with a
    generated ALTERNATIVE, so a colliding connection note could never be
    replaced; and in template mode it would have written notes `plan` never
    asked for. Two modules answering "which notes are generated" differently is
    how they drift, so this one defers.
    """
    if not (contact or {}).get("linkedin"):
        return []
    if note_mode(rec or {}, client_config) != "llm":
        return []
    return [s.get("key") for s in (sequence or ())
            if s.get("channel") == "linkedin" and s.get("key")]


def _candidate_steps(contact_result, sequence, rec=None, contact=None,
                     client_config=None):
    """What a contact result would write onto THIS record's sequence.

    A CHANNEL THIS CONTACT HAS NO ADDRESS ON IS NOT A CANDIDATE. The writer
    emits five emails and four notes for everybody, and `plan` has always
    refused to ask for an email step for a contact with no sendable address and
    a LinkedIn step for a contact with no profile - `cadence.status_for` answers
    `blocked` for the second. Building candidates for them anyway made a
    LinkedIn-only contact fail lint five times on `recipient_missing`, which no
    rewrite can fix, and took the four notes down with them. `rec` and `contact`
    are optional only so a caller inspecting the mapping alone need not supply
    them; production always does.

    THE SEQUENCE NAMES THE STEPS, NOT THE WRITER. This was a hardcoded
    `em1`..`em5`, so a record on `productive_balanced_v1` - whose generated
    email steps are `day1` and `day15`, the module default and therefore what
    every record whose client names no cadence runs - had NOTHING written to it:
    the pipeline generated five emails and four notes, none of the keys matched,
    and the loop stored nothing while reporting success. `cadence.steps_for` is
    the authority on which steps exist (CLAUDE.md: prefer canonical state to a
    second representation of it), so the writer's output is mapped onto it by
    ordinal.

    Returns [(step_key, step_dict)] and never writes anything.
    """
    sequences = contact_result.get("sequences") or {}
    subjects = contact_result.get("subjects") or {}
    out = []

    email_ok = True
    if contact is not None:
        email_ok = bool(contact.get("email")) and lint.sendable(
            contact, lint.policy_for_record(rec or {}))

    # PART B (TASK-914): when the email branch is skipped, log WHY. The
    # reason exists - `verification.decide` returns a reason string - but
    # nothing surfaced it at generation time. The silence cost two
    # misdiagnoses: the drop looked like a consumer-migration bug and was
    # in fact a deliberate verification hold.
    if not email_ok and contact is not None and rec is not None:
        from . import verification
        if not contact.get("email"):
            _email_hold_reason = "no email address on contact"
        else:
            decision = verification.resolve(
                contact, lint.policy_for_record(rec))
            _email_hold_reason = decision.get("reason", "held")
        store.log(rec, "email_held",
                  "%s: %s" % (contact.get("name", "?"), _email_hold_reason))

    email_keys = _generated_keys(sequence, "email") if email_ok else []
    if len(email_keys) >= len(_PLAN_EMAIL_ORDER):
        source_order = _PLAN_EMAIL_ORDER
    else:
        source_order = _PLAN_EMAIL_PREFERENCE
    for n, step_key in enumerate(email_keys):
        if n >= len(source_order):
            break
        source = source_order[n]
        body = sequences.get(source)
        if not body:
            continue
        subject = (subjects.get(_PLAN_SUBJECT_OF[source])
                   or subjects.get("A") or "")
        step = {"channel": "email", "generated": True,
                "subject": subject, "body": body}
        ps = sequences.get("ps_" + source)
        if ps:
            step["ps"] = ps
        out.append((step_key, step))

    li_keys = ([] if contact is None
               else _linkedin_candidate_keys(rec, client_config, contact,
                                             sequence))
    for step_key in li_keys:
        note = sequences.get(step_key)
        if not note:
            continue
        out.append((step_key, {"channel": "linkedin", "generated": True,
                               "note": note}))
    return out


def _trial_cadence(rec, contact_key, pairs):
    """`rec` with `pairs` written into one contact's cadence, without writing."""
    existing = dict((rec.get("cadence") or {}).get(contact_key) or {})
    existing.update(dict(pairs))
    trial = dict(rec)
    trial["cadence"] = {**(rec.get("cadence") or {}), contact_key: existing}
    return trial


def _selected_offer(rec, contact=None):
    """The ONE offer this record's contact would be generated against, or None.

    The same selection `generate_campaign` makes, read here so that the gates
    this module runs - the word range today, and anything else that is a
    property of the offer tomorrow - use the offer's own record rather than a
    second opinion assembled locally.

    THE PERSONA IS THE CONTACT'S, for the reason `_ladder_failures` records
    against itself: reading it off the record defaults every record to
    `champion` and selects the wrong offer SILENTLY rather than failing.

    Returns None for anything it cannot determine - no offer, more than one in
    scope, another tenant's client, a library that will not load. None means the
    caller falls back to its own default, never to a widened rule.
    """
    try:
        from . import generate_campaign as _gc
        persona = (contact or {}).get("persona") or (rec or {}).get("persona")
        if isinstance(persona, dict):
            persona = persona.get("key")
        selected = _gc._select_offers(
            (rec or {}).get("segment") or (rec or {}).get("client")
            or _SEQUENCE_GATE_TENANT,
            persona or "champion")
        if len(selected) != 1:
            return None
        return next(iter(selected.values()))
    except Exception:                                         # noqa: BLE001
        return None


def _step_refusals(rec, contact, pairs, client_config=None):
    """Why each candidate step may not be stored. Sentences, not codes.

    THE SAME THREE GATES `draft()` APPLIES, and for the same reason: lint says
    whether these words may ship, `claims.check` says whether the record
    supports what they assert, and the quality gate says whether this step
    repeats a sibling. The campaign path ran NONE of them - it stored whatever
    the writer returned - so a draft that lint refuses was written into the
    cadence, which is the shape of the 09-23 incident.

    Judged against a TRIAL record carrying all the candidate steps, so each step
    is compared with the siblings as they WOULD be stored, and nothing is
    written if any of them fails.

    Returns {step_key: [sentence, ...]} for the steps that failed.
    """
    key = lint.contact_key(contact)
    trial = _trial_cadence(rec, key, pairs)
    refusals = {}
    for step_key, step in pairs:
        if step.get("channel") == "linkedin":
            failures = lint.check_linkedin(trial, key, step)
            content = [f for f in failures if f not in lint.LINKEDIN_HELD_CODES]
            text = step.get("note") or ""
            # THE SAME CLAIMS AUTHORITY AS EMAIL. A customer-outcome claim
            # that escaped through LinkedIn was the defect TASK-914 fixes:
            # the email path ran `claims.check` and the LinkedIn path did
            # not, so a weaker channel was the path of least resistance.
            # Both channels now consult one authority.
            unsupported = claims.check(text, trial, contact)
            if unsupported:
                content = content + ["unsupported claim: %s" % c
                                     for c in unsupported[:3]]
        else:
            # THE STEP KEY, EXPLICITLY, AND THE OFFER'S OWN REPLY RUNGS.
            #
            # `lint.check` can recover the key from the trial cadence, but this
            # is the call site that FEEDS THE WRITER its retry reason, so it
            # says which step it means rather than relying on a lookup. The
            # offer is the authority for which rungs are thread replies - the
            # same field `sequencegate` reads - so the word range and the step
            # objective ladder cannot disagree about what em2 and em4 are.
            failures = lint.check(trial, key, step, step_key=step_key,
                                  reply_steps=lint.reply_steps_for(
                                      _selected_offer(rec, contact)))
            content = [f for f in failures if f not in lint.HELD_CODES]
            # A NEWLINE, NOT A SPACE. `claims.sentences` splits on `[.!?]\s+`
            # or `\n+`, and a subject line carries no terminator - so joining
            # with a space FUSES the subject to the body's first sentence and
            # the gate then judges a sentence nobody wrote.
            #
            # MEASURED 2026-09-30, from a real refusal: "how live margin and
            # budget data actually look Productive shows margin per project
            # and budget burn live..." - the subject's noun phrase and the
            # body's opening clause, reported as one assertion.
            #
            # The sibling call site in this same module already joins with
            # "\n". Two call sites, one authority, and only one of them right.
            text = f"{step.get('subject') or ''}\n{step.get('body') or ''}"
            unsupported = claims.check(text, trial, contact)
            if unsupported:
                content = content + ["unsupported claim: %s" % c
                                     for c in unsupported[:3]]
            repeats = _quality_of(trial, contact,
                                  (trial.get("cadence") or {}).get(key) or {},
                                  step_key, client_config)
            if repeats:
                content = content + [
                    "this repeats another step in the sequence; say something "
                    "the others do not (%s)" % ", ".join(repeats)]
        if content:
            refusals[step_key] = [lint.explain(content, text)]
    return refusals


def _ladder_failures(rec, contact, stored, sequence, client=None):
    """`{step_key: why}` for every email step the offer's ladder refuses.

    ONLY `step_objectives`. The gate's other checks are already reachable
    from the planner through lint, claims and the quality gate, and acting on
    a verdict whose other inputs this function does not supply would schedule
    a regeneration for something it did not actually measure. The offer and
    the messaging rules are the two inputs `step_objectives` reads, and both
    come from the library rather than from anything assembled here.

    REFUSING IS NOT THIS FUNCTION'S JOB. Anything it cannot determine - no
    offer for the persona, a single-tenant offer library pointed at another
    client, a gate that raises - returns NOTHING TO DO, because the staging
    gate still refuses the push and a planner that raised would take the
    whole estate's generation run down with it.
    """
    if (rec or {}).get("client") not in (None, _SEQUENCE_GATE_TENANT):
        return {}
    emails, subjects = {}, {}
    for spec in sequence or ():
        if spec.get("channel") != "email":
            continue
        step = (stored or {}).get(spec["key"]) or {}
        if step.get("body"):
            emails[spec["key"]] = step.get("body")
            subjects[spec["key"]] = step.get("subject") or ""
    if len(emails) < 2:
        return {}
    try:
        from . import generate_campaign as _gc, offers as _offers
        from . import sequencegate as _sg

        # THE PERSONA IS THE CONTACT'S, NOT THE RECORD'S, and reading it off
        # the record silently selects the WRONG OFFER rather than failing:
        # `2020companies-com` carries no record persona, so the default
        # `champion` picked `OFFER-B-OPERATIONS` and checked an economic
        # buyer's sequence against the operations ladder. Measured against
        # the staging gate, whose verdict named different steps entirely -
        # which is how a divergent second assembler announces itself.
        persona = contact.get("persona") or rec.get("persona")
        if isinstance(persona, dict):
            persona = persona.get("key")
        selected = _gc._select_offers(
            rec.get("segment") or rec.get("client") or "productive",
            persona or "champion")
        if len(selected) != 1:
            return {}
        offer = next(iter(selected.values()))
        verdict = _sg.check({"emails": emails, "subjects": subjects},
                            offer=offer,
                            messaging_rules=_offers.messaging_rules())
    except Exception:                                         # noqa: BLE001
        return {}
    out = {}
    for f in (verdict or {}).get("failures") or ():
        if f.get("check") != "step_objectives":
            continue
        key = f.get("step")
        if key in emails and key not in out:
            out[key] = " ".join(str(f.get("why") or "").split())[:120]
    return out


def _campaign_validator(rec, client_config=None, campaign=None):
    """The per-draft gates, as the callback `generate_campaign` retries on.

    `generate_campaign` holds no record, so it can run the BATCH lint and not
    the per-draft one. This closes that half: a writer whose output lint,
    claims or the repetition gate refuses is asked again, with the reason named
    - never patched, and never accepted because the batch lint happened to pass.
    """
    def validate(contact_result):
        ck = contact_result.get("contact_key")
        contact = lint.find_contact(rec, ck) if ck else None
        if contact is None:
            return []
        sequence = sequence_for(rec, client_config, contact, campaign)
        pairs = _candidate_steps(contact_result, sequence, rec, contact,
                                 client_config)
        if not pairs:
            return ["the writer produced no copy for any generated step of "
                    "this record's sequence (%s)"
                    % ", ".join(_generated_keys(sequence, "email")
                                + _generated_keys(sequence, "linkedin"))]
        out = []
        for step_key, sentences in sorted(
                _step_refusals(rec, contact, pairs, client_config).items()):
            out.append("%s: %s" % (step_key, "; ".join(sentences)))
        out.extend(_sequence_gate_failures(rec, contact_result, client_config))
        return out

    return validate


#: The tenant whose approved ladder `offers.py` actually serves.
#:
#: `offers._offers_path()` resolves `productive-offers.yaml` whatever client is
#: being generated for - TASK-564 finding 3, confirmed. So the sequence gate's
#: step objectives are PRODUCTIVE's, and folding its failures into the writer's
#: retry loop for any other client would enforce a ladder that client never
#: approved. That is the exact objection `generate_campaign` records against
#: doing this unconditionally, and it is why this is tenant-guarded rather than
#: global.
_SEQUENCE_GATE_TENANT = "productive"


def _sequence_gate_failures(rec, contact_result, client_config=None):
    """The sequence gate's own refusals, fed back to the writer.

    WHY THIS IS HERE AND NOT IN `generate_campaign`. That module computes
    `result["sequence_gate"]` and its own comment records that nothing reads
    it: "the retry loop breaks on `copylint` alone, so a sequence the gate
    REFUSED is returned exactly like one it passed, written into the record
    by `generate._adapt_plan_to_cadence`, and stopped two gates later by
    `bisonfactory._refuse_sequence_gate`."

    Measured 2026-09-29 on the Rachele canary: staging refused at
    `_refuse_sequence_gate` for `step_objectives` on em3 and em4, after the
    copy had been generated, gated, stored and approved. The writer was never
    told the rule existed, so it could not satisfy it, and the refusal arrived
    at the last possible moment instead of the first.

    `validate` is the seam built for exactly this - a non-empty return
    regenerates the whole set with the reason named - so the gate now refuses
    at generation time, where a regeneration is free, rather than at staging,
    where it costs an approval.
    """
    client = (rec or {}).get("client")
    if client != _SEQUENCE_GATE_TENANT:
        return []
    verdict = (contact_result or {}).get("sequence_gate") or {}
    if not verdict or verdict.get("passed"):
        return []
    # `failures` entries are {check, step, why}; warnings are NOT failures and
    # are deliberately ignored - the gate says so about itself, and retrying a
    # draft over a warning would spend attempts on something it declined to
    # assert.
    out = []
    for f in verdict.get("failures") or ():
        out.append("%s (%s): %s" % (f.get("step") or "sequence",
                                    f.get("check") or "sequence_gate",
                                    f.get("why") or ""))
    return out


def _protected_reason(rec, contact_key, step_key, step):
    """Why this stored step may never be overwritten, or None.

    OPERATOR DECISION, 2026-09-27: an UNAPPROVED draft may be regenerated;
    an APPROVED or SENT one never is, because regeneration after approval
    invalidates the approval hash - the approval stays bound to exactly the copy
    a person read. `store_step` keeps a superseded approval as history, which is
    the audit half of the same rule and NOT a licence to overwrite: history
    records what happened, it does not make the overwrite allowed.
    """
    from . import approval as _approval, stepstate

    if not isinstance(step, dict):
        return None
    status = step.get("status")
    if stepstate.is_terminal(status):
        return "step status %r is terminal: it has already been sent" % status
    if _approval.is_approved(rec, contact_key, step_key, step):
        return ("the stored copy is APPROVED and the approval hash is bound to "
                "exactly those words")
    return None


def _adapt_plan_to_cadence(rec, plan_result, client_config=None,
                           campaign=None):
    """Write a SequencePlan's contact results into the record's cadence.

    WITHOUT THIS THE WHOLE TASK IS POINTLESS, which is why it is back.
    REWORK 2 deleted it and left only a report-formatting helper, which built a
    DISPLAY list of ops and wrote nothing. So the campaign pipeline generated
    copy and discarded it: `rec["cadence"]` was never touched, no preview, provider
    projection, approval or lint could see the output, and Checkpoint A's
    control 4 ("change an approved fact, the artifact changes") had no artifact
    to change. The old pipeline reached the same structure through
    `store_step()`; the new one has to as well or it is not wired.

    Goes through `store_step()` deliberately rather than assigning into the
    cadence directly: that function carries the approval-history rule, and
    bypassing it silently deleted seventy-two audit records once already.

    Held and unqualified contacts are skipped: nothing is written for a contact
    the pipeline refused, so a refusal cannot leave copy behind.

    AND NEITHER IS A DRAFT THAT FAILED A GATE. `_step_refusals` runs lint,
    claims and the quality gate over the whole candidate set, and if ANY step
    fails, NONE of that contact's steps is stored: a half-written sequence is a
    send candidate nobody asked for, and the sibling comparisons that decide the
    other steps were computed against the failing one.

    AND AN APPROVED OR SENT STEP IS NEVER OVERWRITTEN (`_protected_reason`).

    Returns the list of (contact_key, step_key) pairs written.
    """
    stored_pairs = []

    for contact_result in plan_result.get("contacts") or []:
        ck = contact_result.get("contact_key")
        if not ck:
            continue
        if contact_result.get("held"):
            continue
        if contact_result.get("qualification") in ("UNQUALIFIED",
                                                   "INSUFFICIENT"):
            continue

        contact = lint.find_contact(rec, ck)
        if contact is None:
            continue
        sequence = sequence_for(rec, client_config, contact, campaign)
        pairs = _candidate_steps(contact_result, sequence, rec, contact,
                                 client_config)
        if not pairs:
            continue

        refusals = _step_refusals(rec, contact, pairs, client_config)
        # ALL-OR-NOTHING PER CHANNEL, NOT PER CONTACT.
        #
        # Operator decision, Zvonimir, 2026-09-30: "LinkedIn steps are not
        # required for this canary and a LinkedIn failure (e.g. li5) must not
        # hold an email-only candidate."
        #
        # This refused the WHOLE contact when ANY step failed, so one bad
        # LinkedIn note discarded five clean emails. Measured the same day
        # across fourteen qualified candidates: TWELVE had no em4 and no em5
        # on the record at all, because every generation that produced them
        # also produced a LinkedIn step that failed, and nothing was stored.
        #
        # The unit the all-or-nothing rule is protecting is the SEQUENCE
        # whose steps the gates compare against each other - repetition,
        # thread, ladder - and that comparison is within a channel. A clean
        # email sequence is coherent whether or not the LinkedIn notes are.
        # So a channel whose every candidate step passed is stored, and a
        # channel with any failure stores nothing. No step is stored that
        # failed a gate, and the gates are unchanged.
        by_channel = {}
        for step_key, step in pairs:
            by_channel.setdefault(step.get("channel"), []).append(step_key)
        refused_channels = {ch for ch, keys in by_channel.items()
                            if any(k in refusals for k in keys)}
        if refused_channels:
            store.log(rec, "draft",
                      "%s: %s refused, nothing stored for %s (%s)"
                      % (contact.get("name"), "/".join(sorted(refused_channels)),
                         "/".join(sorted(refused_channels)),
                         "; ".join("%s %s" % (k, "; ".join(v))
                                   for k, v in sorted(refusals.items()))[:400]),
                      refused=sorted(refusals))
        if len(refused_channels) == len(by_channel):
            continue
        pairs = [(k, s) for k, s in pairs
                 if s.get("channel") not in refused_channels]

        protected = {k: _protected_reason(rec, ck, k,
                                          ((rec.get("cadence") or {})
                                           .get(ck) or {}).get(k))
                     for k, _ in pairs}
        for step_key, step in pairs:
            reason = protected.get(step_key)
            if reason:
                store.log(rec, "draft",
                          "%s %s: kept the stored copy, not overwritten - %s"
                          % (contact.get("name"), step_key, reason))
                continue
            _, ordinal, _ = position(sequence, step_key)
            fp = ladder_fingerprint(step["channel"], ordinal,
                                    sequence=sequence)
            if fp:
                step["ladder_fingerprint"] = fp
            store_step(rec, ck, step_key, step)
            stored_pairs.append((ck, step_key))
            events.record(rec, events.DRAFT_GENERATED, contact_key=ck,
                          channel=step["channel"], step=step_key,
                          generated=True)

    return stored_pairs


def _account_sources(rec):
    """The account's research pack, as the campaign pipeline's `sources` list.

    `rec["research"]` IS A LIST OF EVIDENCE ENTRIES. That is the only shape
    anything in this repository writes and the only shape `SCHEMA.md` records,
    and this bridge read it as a DICT with a `sources` key:

        "sources": (rec.get("research") or {}).get("sources") or []

    Measured, and this is why it mattered more than an ordinary type error. A
    canonical LIST raised `AttributeError: 'list' object has no attribute 'get'`
    right here. A DICT got past this line and then raised `AttributeError: 'str'
    object has no attribute 'get'` inside `claims.support_text` - reached from
    `_campaign_validator`, inside `_process_contact`'s broad `except Exception`
    - so every contact came back `hold_kind="error"` with `stored_pairs=0` from
    a run that looked like it completed. An absent pack was the only shape that
    produced copy, and it produced copy with no account research in it at all.

    The LIST is canonical by count rather than by preference: `research.py` (the
    production crawl, three call sites), `companies`, `demo`, `demo_outreach`,
    `benchmark`, `synthetic` and `web.demodata` WRITE a list, and `claims`,
    `dossier`, `eligibility`, `icp`, `packfacts`, `preview`, `qa`, `qualify`,
    `quality`, `report`, `segments`, `personalization`, `llm`, `funnel`,
    `simulator`, `web.api` and this module's own `_evidence_fingerprint` and
    `research_block` READ one. The dict read was the single disagreement, and
    the production store agrees with the list: of 1,582 records, 394 carry a
    populated list, 23 an empty list, 1,165 none, and NOT ONE a dict.

    So this is a projection of the canonical shape and never a second
    representation of it. `research.for_prompt` is the existing one - "the
    evidence a prompt may see: attributed, trimmed, and small", quality-filtered
    and re-aged through `evidence.select`, capped at the three entries
    `SCHEMA.md` licenses a prompt to see - and it is what the old pipeline's
    `context_for` already shows a model. Both paths therefore see the same
    evidence, which is what stops them drifting.

    A non-list `research` is REFUSED BY NAME rather than read as an empty pack.
    Reading it as empty is the failure this whole function exists to close: the
    pipeline would write copy from silently dropped evidence and report success.
    """
    from . import generate_campaign

    rows = rec.get("research")
    if rows and not isinstance(rows, list):
        raise generate_campaign.CampaignPipelineError(
            "record %r carries research as %s, and `rec[\"research\"]` is a "
            "LIST of evidence entries (SCHEMA.md, written by `evidence.make`). "
            "A shape this pipeline cannot read is refused by name rather than "
            "treated as an empty research pack, because copy written from "
            "silently dropped evidence is indistinguishable from copy written "
            "from evidence that was never there."
            % (rec.get("id"), type(rows).__name__))

    sources = []
    for entry in research.for_prompt(rec):
        text = entry.get("fact") or ""
        if not text.strip():
            continue
        sources.append({
            # `field` is the page the fact came from ("about", "careers"), which
            # is exactly what `copyprompts._numbered` prints as the block label.
            "label": entry.get("field") or "site",
            "url": entry.get("source_url"),
            "text": text,
        })
    return sources


class _CountedModel:
    """The injected model, with its calls counted into `model_calls`.

    `count_model_call` was incremented by `draft`, `linkedin_note` and
    `_regenerate_linkedin_set`, and the campaign path replaces all three - so
    without this the in-process counter reads zero for a run that made thirty
    calls, and `scripts/task197_generate.py`'s per-step report silently shows
    nothing. The spend LEDGER (`rec["model_calls"]` via `llm.mark`) is
    unaffected either way and remains the authority on cost; this is the cheap
    per-step counter, and a counter that reads zero while work is happening is
    worse than no counter.

    A wrapper rather than a hook inside `generate_campaign`, so the counting
    lives with the module that owns `model_calls` and the pipeline keeps taking
    any object with `complete()`.
    """

    def __init__(self, inner, step="campaign"):
        self._inner = inner
        self._step = step
        self.name = getattr(inner, "name", "unknown")

    def complete(self, prompt, temperature=0, client=None, config=None):
        count_model_call(self._step)
        return self._inner.complete(prompt, temperature=temperature,
                                    client=client, config=config)


def _generate_via_campaign(rec, model, client_config=None, live=False,
                           allow_pending_offers=False):
    """Route a record through the campaign pipeline.

    TASK-400. The real entrypoint. `generate_campaign.generate()` is the
    single versioned production path. This function bridges the record-based
    interface of `run()` to the campaign pipeline's account/contacts
    interface.

    NotApproved propagates. CampaignPipelineError propagates. No fallback
    to the old stage functions. No ScriptedModel branch.
    """
    from . import generate_campaign

    client_name = rec.get("client") or ""

    # A MISSING CLIENT IS A HARD ERROR, NOT A ROUTE TO THE OLD PIPELINE.
    #
    # This was `except clients.ConfigError: pass`, which swallowed the failure
    # and carried on with `client_config = None`. The campaign pipeline then ran
    # with no offers, no approved mechanism and no client facts, and produced
    # copy anyway. A bare swallow on the path that loads the offer gate's own
    # configuration is the same defect as catching NotApproved: the gate cannot
    # refuse what it was never given.
    #
    # The decision, stated rather than defaulted: the campaign path IS
    # responsible for every record it is handed, so a record it cannot configure
    # is a refusal by name, never a silent handover.
    if client_config is None:
        if not client_name:
            raise generate_campaign.CampaignPipelineError(
                "record %r has no client and no config was supplied; the "
                "campaign pipeline cannot select an offer or a mechanism "
                "without one." % rec.get("id"))
        try:
            client_config = clients.load(client_name)
        except clients.ConfigError as exc:
            raise generate_campaign.CampaignPipelineError(
                "record %r names client %r whose config could not be loaded: "
                "%s" % (rec.get("id"), client_name, exc)) from exc

    raw_contacts = rec.get("contacts") or []
    # TASK-909: the account-level `persona` field is absent on every real
    # record, so `rec.get("persona", "champion")` silently defaulted every
    # record to champion and the contact's stored persona never reached offer
    # selection. The fix reads the contacts' personas when the account did not
    # set one explicitly, and falls back to champion only when the contacts
    # disagree or carry no persona at all.
    _contact_personas = {c.get("persona") for c in raw_contacts
                         if c.get("persona")}
    account = {
        "company": rec.get("company", ""),
        "domain": rec.get("domain", ""),
        "persona": (rec.get("persona")
                    or (next(iter(_contact_personas))
                        if len(_contact_personas) == 1 else None)
                    or "champion"),
        "segment": rec.get("segment", client_name),
        # THE CANONICAL RESEARCH SHAPE, projected. `_account_sources` carries
        # the measurement and the reason this is not a dict read.
        "sources": _account_sources(rec),
    }
    contacts = []
    for c in raw_contacts:
        contacts.append({
            "email": c.get("email", ""),
            "first_name": c.get("name", "").split()[0] if c.get("name") else "",
            "last_name": " ".join(c.get("name", "").split()[1:]) if c.get("name") else "",
            "title": c.get("title", ""),
            # THE CANONICAL CONTACT KEY, not the email address. This was
            # `c.get("key") or c.get("email", "")`, and every record whose
            # contacts carry no stored `key` - which is every record in
            # `tests/fixtures/phase5.jsonl` and the normal case - got its
            # cadence rows written under `rowan.blake@harbourline.test` while
            # `lint`, `approval`, `cadence`, `preview` and the provider
            # projections all look up `rowan-blake`. Two representations of one
            # identity, and the copy was stored under the one nothing reads.
            # `identity.contact_key` (via `lint.contact_key`) is the single
            # authority and prefers a stored key when there is one.
            "contact_key": lint.contact_key(c),
            "linkedin": c.get("linkedin", ""),
            "sender_name": (client_config or {}).get("sender", {}).get("name", "")
                if isinstance(client_config, dict) else "",
        })

    if not contacts:
        raise generate_campaign.CampaignPipelineError(
            "record %r has no contacts; generation requires at least one."
            % rec.get("id"))

    plan = generate_campaign.generate(
        client_config or client_name,
        account,
        contacts,
        model=_CountedModel(model),
        live=live,
        allow_pending_offers=allow_pending_offers,
        validate=_campaign_validator(rec, client_config, None),
        # THE CANONICAL SLUG FROM THE RECORD, not derived from the display
        # name. `client_name` here is `rec.get("client")` - the identity the
        # record carries. `generate_campaign.generate` receives a config dict
        # whose `name` field is the display label ("Productive"); the slug
        # ("productive") is the authority for Second Brain retrieval.
        client_slug=client_name,
    )

    # THE STAMP HAS TO REACH THE RECORD, or the refusal it exists for is inert.
    #
    # `generate_campaign` stamps the PLAN (`plan["generation_stamp"]`), while
    # `refuse_dry_run_records()` reads the stamp off each RECORD. Nothing
    # bridged the two, so every one of the four provider refusal call sites was
    # checking a field production never wrote: a dry-run artifact could be
    # attached and activated on both providers, and the tests passed only
    # because they set `rec["generation_stamp"]` by hand.
    #
    # Written BEFORE the cadence, so a record can never carry dry-run copy
    # without also carrying the stamp that refuses it.
    stamp = plan.get("generation_stamp")
    if stamp:
        rec["generation_stamp"] = stamp
    else:
        rec.pop("generation_stamp", None)

    # A REFUSED CONTACT SAYS SO ON THE RECORD. `copy_refused` means every
    # attempt was regenerated and every attempt failed a gate, so there is no
    # draft - and a run that reports GENERATED while a contact silently got
    # nothing is the failure this whole task is about. The wording is the same
    # one `draft()` logged, because the operator greps for it.
    for contact_result in plan.get("contacts") or []:
        if contact_result.get("hold_kind") != "copy_refused":
            continue
        store.log(rec, "draft",
                  "%s: no draft passed lint, nothing stored (%s)"
                  % (contact_result.get("first_name")
                     or contact_result.get("contact_key"),
                     str(contact_result.get("held"))[:300]),
                  attempts=contact_result.get("gate_attempts"),
                  rejected=contact_result.get("gate_rejections"))

    # WHAT THIS WRITE ACTUALLY STORED, on the plan, because the caller cannot
    # tell a regeneration's new rows from the ones that were already there.
    plan["stored_pairs"] = _adapt_plan_to_cadence(rec, plan, client_config,
                                                  campaign=None)
    return plan


def run(model=None, live=False, ids=None, limit=None, client=None,
        regen_stale_ladder=False, allow_pending_offers=False,
        allow_whole_set_regeneration=False):
    """Dry by default: reports what would be asked without asking anything.

    `regen_stale_ladder` is OPT-IN (TASK-083). When True, plan treats steps
    whose ladder fingerprint does not match the current ladder as needing
    regeneration. When False (the default), plan behaves exactly as before.

    TASK-400: the real entrypoint is `generate_campaign.generate()`, called
    via `_generate_via_campaign()`. NotApproved and CampaignPipelineError
    propagate - no fallback to the old stage functions.
    """
    # TASK-162: reset the company evidence cache at the start of each pass.
    # The cache lives for the duration of one pass, not across sessions.
    clear_company_cache()
    recs = store.load()
    model = model or llm.NoModel()

    # A LIVE RUN WITH NO MODEL REFUSES, BEFORE ANY RECORD IS TOUCHED.
    #
    # `live=True` means "generate". Reporting a plan instead and printing
    # GENERATED is the shape this repository has been bitten by twice: a batch
    # that looks finished with no copy in it. REWORK 2 made the no-model branch
    # below unconditional, which turned
    # `test_the_estate_is_not_saved_when_no_model_is_configured` red - and that
    # test is the one asserting a run which asked nothing leaves the file
    # exactly as it found it.
    #
    # `NoModelConfigured` BY NAME, so a configuration fault of ours is never
    # written onto a record as though the company were the problem, and raised
    # here rather than per record so nothing at all is saved. `main()` catches
    # the same case earlier and prints; a library caller gets the exception.
    if live and isinstance(model, llm.NoModel):
        raise llm.NoModelConfigured(
            "a live generate run needs a model: pass model= to run(), or set "
            "LLM_BASE_URL, LLM_API_KEY and LLM_MODEL. Nothing was generated "
            "and no record was changed.")
    targets = [r for r in recs if ids is None or r["id"] in ids]
    if limit:
        targets = targets[:limit]

    report = []
    stale_steps = 0
    stale_with_approval = 0
    for rec in targets:
        # WITH NO MODEL CONFIGURED, NOTHING IS GENERATED AND NOTHING IS ASKED.
        # `run()`'s contract is "dry by default: reports what would be asked
        # without asking anything", and `main()` only builds a model under
        # `--live`. The campaign pipeline calls the model in every mode, so
        # routing an unconfigured run into it turned 81 previously-passing tests
        # into NoModelConfigured and would have made `python -m src.generate`
        # crash where it used to print a dry report.
        #
        # THIS IS NOT A FALLBACK TO THE OLD WRITER. `plan()` enumerates what
        # WOULD be asked; it generates no copy and never calls `draft()`,
        # `linkedin_note()` or `_regenerate_linkedin_set()`. "No model" means no
        # generation, not generation by another route. Two axes that TASK-400
        # had conflated stay separate: whether the MODEL is called, and whether
        # a PROVIDER is written.
        if isinstance(model, llm.NoModel):
            ops = plan(rec, client, campaign=None,
                       regen_stale_ladder=regen_stale_ladder)
            state = rec.get("state")
        elif live:
            # CHECKPOINT PER RECORD. This loaded the estate, worked, and saved
            # ONCE at the end - so a run across eighteen records that died
            # fifty minutes in wrote nothing at all, and every model call in
            # that window had been paid for. Measured 2026-09-13: no log, no
            # exit code, no drafts. REWORK 2 removed the transaction entirely
            # and nothing was persisted at all: the campaign pipeline wrote a
            # cadence onto an in-memory dict that was then dropped on the
            # floor, which is the same bug with a shorter window.
            #
            # Through `store.transaction` so the evidence and history loss
            # guards still run - durability bought by defeating them would be
            # one loss traded for another.
            #
            # No resume flag, no checkpoint file, no new state. The estate IS
            # the checkpoint, because `plan` declines to re-draft a record
            # that already carries a clean one, so re-running the command is
            # the resume.
            with store.transaction() as rows:
                target = next(r for r in rows if r["id"] == rec["id"])
                ops = generate_record(
                    target, model, client,
                    regen_stale_ladder=regen_stale_ladder, live=live,
                    allow_pending_offers=allow_pending_offers,
                    allow_whole_set_regeneration=allow_whole_set_regeneration)
                state = target.get("state")
                rec = target
        else:
            # A MODEL, NOT LIVE: the operator watching the new path execute
            # before any offer is approved. The pipeline runs in full and the
            # artifact carries `DRY_RUN_STAMP`, which every provider attach and
            # activation refuses - and NOTHING IS PERSISTED, because a dry run
            # writes nothing (`test_a_dry_run_asks_nothing_and_writes_nothing`).
            ops = generate_record(
                rec, model, client, regen_stale_ladder=regen_stale_ladder,
                live=live, allow_pending_offers=allow_pending_offers,
                allow_whole_set_regeneration=allow_whole_set_regeneration)
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
    # THE ESCAPE HATCH, REACHABLE. `_refuse_partial_regeneration` refuses to
    # regenerate part of a record through a writer that emits the whole set, and
    # names `allow_whole_set_regeneration=True` as the deliberate way to accept
    # that all of it is rewritten. Without a flag that escape existed only for
    # library callers, so an operator facing a partially-drafted record had a
    # refusal and no documented way past it - which is how a refusal gets
    # weakened in a hurry instead. APPROVED and SENT steps are still never
    # overwritten: this flag does not reach `_protected_reason`.
    p.add_argument("--regenerate-whole-set", action="store_true",
                   help="accept that the whole set of a record's generated "
                        "copy is rewritten. Required for a record that already "
                        "carries generated steps, because the campaign writer "
                        "emits all of them in one call. APPROVED and SENT "
                        "steps are still never overwritten.")
    p.add_argument("--allow-pending-offers", action="store_true",
                   help="run the pipeline with the offer gate bypassed. The "
                        "artifact is stamped NOT APPROVABLE and NOT "
                        "PROVIDER-READY and cannot be attached, activated or "
                        "approved. For watching the path execute before any "
                        "offer is approved.")
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
                 client=config, regen_stale_ladder=a.regen_stale_ladder,
                 allow_pending_offers=a.allow_pending_offers,
                 allow_whole_set_regeneration=a.regenerate_whole_set)

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
