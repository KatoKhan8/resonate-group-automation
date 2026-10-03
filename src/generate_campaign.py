"""The single versioned production entrypoint for campaign generation.

TASK-369. Every model call goes through `src/llm.py`. No `urllib`, no
`requests`, no API base URL in this file. The spend ledger sees every call.

The pipeline:
    1. Select this prospect's offer and check it is approved (fail-closed).
    2. Load Second Brain facts; only verified facts inform strategy.
    3. Decide strategy ONCE per segment+persona.
    4. Per contact: ICP -> extract -> hypothesis -> match -> plan -> write.
    5. copylint, then sequencegate, before any provider call.
    6. Return a SequencePlan.

`work/v2_run.py` is the reference. This module promotes it: same stages,
same prompts, but every model call is ledgered and every offer is checked.
"""
import json
import re

from . import (cadencelibrary, clients, copyprompts, copystages, copylint, lint,
               llm, offers as offers_mod, secondbrain, sequencegate,
               sequenceplan, skills)
from .packfacts import CLIENT_SUPPLIED

ENTRYPOINT_VERSION = sequenceplan.ENTRYPOINT_VERSION

DRY_RUN_STAMP = "DRY-RUN / OFFERS PENDING"

#: How many times the writer is asked again after a gate refuses its output.
#: Same budget as `generate.MAX_DRAFT_ATTEMPTS`, which is the rule this
#: replaces on the campaign path: attempts, then the copy is refused and
#: nothing is stored.
#:
#: RAISED FROM 3 TO 6, 2026-09-29. The budget was set when the campaign path
#: ran a handful of gates. It now runs lint, claims (TASK-914 through 921),
#: copylint including the P.S. and subject rules, the repetition gate and the
#: quality gate, and the writer's whole set is refused if ANY step fails ANY
#: of them. Measured on Rachele: four consecutive runs were refused, and each
#: one died on a DIFFERENT gate - a buzzword on one attempt, a repetition
#: collision on the next, an unsupported claim on the third. Every individual
#: fault was fixable and the writer was fixing them; it simply ran out of
#: attempts before it had them all right at once.
#:
#: THIS WEAKENS NOTHING. Every gate still refuses exactly what it refused
#: before, and a set that never passes is still refused with nothing stored.
#: It buys more tries at the same bar, at the cost of model calls on a
#: contact that would otherwise have been lost entirely.
#:
#: RAISED FROM 6 TO 10 on 2026-09-29, and the number was only ever worth
#: raising because the attempts stopped being repeats of each other. Six was
#: chosen when a retry saw ONE reason and ran at temperature 0, so attempts 2
#: to 6 largely re-derived attempt 1 - measured on the Rachele canary, two
#: models, twelve attempts, cycling between the same two or three violations.
#: With every distinct reason fed back, a located offence ("dash -> em3
#: (' - ')") and a rising temperature, the attempts now differ and the
#: failures move. Ten is the budget that has to clear about fifteen
#: independent constraints across eleven messages AT ONCE.
#:
#: THE BAR IS UNCHANGED. Not one gate is relaxed by this, and a contact whose
#: tenth draft still offends is still refused and still held.
MAX_WRITER_ATTEMPTS = 10

#: THE LINKEDIN KEYS THE WRITER PRODUCES AND THE CADENCE CONSUMES.
#: Canonical names li1-li5 match the cadence library and heyreachfactory's
#: COPY_MAPPING, so the writer-to-cadence mapping is an identity. The single
#: authority is `cadencelibrary.LINKEDIN_WRITER_KEYS`; this module re-exports
#: it so existing import sites keep working, and every consumer reads one
#: tuple.
LINKEDIN_WRITER_KEYS = cadencelibrary.LINKEDIN_WRITER_KEYS

# ---------------------------------------------------------------------------
# THE WRITER'S TOKEN BUDGET. TASK-942.
#
# `grep -c max_tokens src/generate.py` returned 0, and so did
# `src/generate_campaign.py` and `src/llm.py`: the writer was NEVER TOLD HOW
# LONG ITS ANSWER MAY BE. `llm.OpenAICompatibleModel._estimate_cost` passed
# 4096 to the spend ledger as a guess, and the HTTP body carried no cap at all,
# so the real bound was whatever default the endpoint applied that day.
#
# MEASURED 2026-10-01, bigfish canary round 3:
#   JSONDecodeError: Expecting ',' delimiter: line 1 column 2724
# 2724 characters of a single-line JSON object is about 680 tokens. The answer
# was a prefix.
#
# WHY NOT A ROUND NUMBER. 2048 or 4096 would be a guess about a payload whose
# every field already has a hard ceiling somewhere in this repository. The
# writer returns one JSON object holding five email bodies, three subjects,
# five LinkedIn notes and up to two P.S. lines, and `lint` refuses each of them
# past a stated size. So the budget is the sum of those ceilings, and it is
# computed from the SAME constants the gates read: raise `lint.MAX_WORDS` and
# this rises with it, which is the only way the two cannot drift.
#
# THE RATES ARE MEASURED, NOT ASSUMED. Both come from the production queue,
# `work/queue.jsonl`, encoded with `cl100k_base`:
#   - 4076 real stored email bodies of 20 words or more, each JSON-escaped as
#     the writer must emit it (so `\n` and `\"` are paid for): 1.188 tokens per
#     word mean, 1.180 median, 1.250 at p95, 1.589 worst. p95 is used.
#   - 482 real stored LinkedIn notes: 0.2128 tokens per character median,
#     0.2443 at p95. 0.25 is used.
#
# AND THE RESULT IS CHECKED AGAINST REALITY. The same queue yields 48 complete
# five-email-plus-subjects payloads reconstructed field by field; the largest
# is 3942 characters / 795 tokens (`waynemedia-com`, contact `julia-piehler`),
# the median 709. The budget below is about 2.2x the richest answer this
# pipeline has ever actually produced, and still below anything a gate would
# accept, so it cannot cut a draft that would have passed.
#
# NOT A CEILING ON LENGTH, A CEILING ON WASTE. A model that writes past this is
# writing copy `lint` would refuse anyway; now it is refused as a named
# truncation that costs one attempt, instead of a `JSONDecodeError` that used
# to cost the round.
_TOKENS_PER_WORD = 1.25       # p95 of 4076 real bodies, JSON-escaped
_TOKENS_PER_CHAR = 0.25       # p95 of 482 real LinkedIn notes
#: The longest P.S. the pipeline has stored is 98 characters (4 samples, median
#: 93). No gate caps a P.S., so this is the one number not read off a contract:
#: 200 is double the longest ever seen, and two P.S. lines are asked for.
_PS_MAX_CHARS = 200
#: `json.dumps` of the full answer with every value emptied: the keys, braces,
#: commas and quotes the writer must emit whatever it writes. Measured, not
#: estimated, with `cl100k_base`.
_WRITER_JSON_SCAFFOLD_TOKENS = 98
#: Models prefix ```json and suffix ``` unasked. `_parse_json` strips fences,
#: but they are emitted INSIDE the budget, so they have to be paid for.
_FENCE_ALLOWANCE_TOKENS = 16

#: What the writer may spend on one answer, in completion tokens. 1759 as the
#: constants stand today.
WRITER_MAX_TOKENS = int(
    5 * lint.MAX_WORDS * _TOKENS_PER_WORD              # em1-em5 bodies
    + len(LINKEDIN_WRITER_KEYS) * lint.NOTE_MAX_CHARS * _TOKENS_PER_CHAR
    + 3 * lint.MAX_SUBJECT * _TOKENS_PER_CHAR          # subject, alt, breakup
    + 2 * _PS_MAX_CHARS * _TOKENS_PER_CHAR             # ps.em1, ps.em3
    + _WRITER_JSON_SCAFFOLD_TOKENS
    + _FENCE_ALLOWANCE_TOKENS)

#: WHAT THE MODEL IS TOLD WHEN A GATE REFUSES. The reason, never the code, and
#: never an instruction to edit the old draft - "never widen a lint rule to make
#: a draft pass. Regenerate the draft." A model told `filler_phrase` three times
#: has been told nothing three times, which is how six contacts went unstaged
#: for want of one message each on 2026-09-13.
RETRY_BLOCK = ("\n## Your previous draft failed lint\n\n"
               "%s\n\nWrite a new one. Do not patch the old one.\n")

#: How warm each retry runs. Attempt 1 is DELIBERATELY 0 - the first draft of
#: a prospect-facing message should be the model's best single answer, not a
#: sample - and only the retries, which exist because that answer was refused,
#: explore. Capped well below 1: the gates bound correctness, this bounds how
#: far the writer wanders from a plan the strategy step already chose.
RETRY_TEMPERATURES = (0.0, 0.3, 0.5, 0.7, 0.8, 0.9)


def _retry_temperature(attempt):
    idx = max(0, min(int(attempt) - 1, len(RETRY_TEMPERATURES) - 1))
    return RETRY_TEMPERATURES[idx]


def _retry_reasons(rejected, keep=3):
    """EVERY distinct reason so far, newest first - not just the last one.

    The retry block quoted `rejected[-1]` alone, so a writer told about a
    banned phrase fixed it, was then told about a dash, fixed that, and
    brought the banned phrase back: each attempt only ever knew about the
    previous attempt's complaint. Measured across twelve attempts on the
    Rachele canary, both models cycled between two and three violations
    without ever holding all of them at once.

    Deduplicated and capped, because the whole point is a list short enough
    to be read. Newest first so the most recent refusal still leads.
    """
    seen, out = set(), []
    for reason in reversed(list(rejected or ())):
        for part in str(reason).split("; "):
            part = part.strip()
            if not part or part in seen:
                continue
            seen.add(part)
            out.append(part)
    if not out:
        return ""
    head, tail = out[:keep * 4], out[keep * 4:]
    lines = ["- %s" % p for p in head]
    if tail:
        lines.append("- ...and %d more earlier refusal(s)" % len(tail))
    return ("Your last %d draft(s) were refused for ALL of the following. "
            "The new draft must satisfy every one of them AT ONCE - fixing "
            "the newest and reintroducing an earlier one is the commonest "
            "way this fails:\n%s" % (len(rejected or ()), "\n".join(lines)))

#: EXCEPTION TYPES THAT MEAN THE CODE IS WRONG, not that the prospect is
#: unusable. `_process_contact` caught every `Exception` and wrote it onto the
#: contact as `hold_kind="error"`, so a shape error in canonical state became a
#: per-contact hold and a run that stored nothing reported no crash. These
#: propagate as `CampaignPipelineError` instead - the same treatment
#: `llm.ModelError` gets, for the same stated reason.
#:
#: `ValueError` is deliberately ABSENT: `_parse_json` raises it for a model
#: answer that is not JSON, and that is a model failure on a record, which holds
#: the contact and always has.
PIPELINE_DEFECTS = (AttributeError, TypeError, KeyError, IndexError, NameError)


class NotApproved(Exception):
    """The offer this run selected is not approved, or no offer was selected.

    Raised by name, fail-closed. Production does not approve its own offers.
    Both halves are this one class deliberately: a caller that handles "the
    offer gate refused" must not be able to handle one half and miss the other.
    """


class CampaignPipelineError(Exception):
    """A configuration or pipeline error that stops generation.

    Raised by name with the client and the missing config. A missing client
    config is a configuration error, not a reason to silently use a different
    pipeline.
    """


def dry_run_stamp_of(rec):
    """The dry-run stamp this record carries, or None.

    ONE READER FOR THE TWO PLACES THE STAMP CAN SIT, because the provider
    refusals and the approval gate must agree about what "stamped" means. A
    second copy of this lookup is how one of them would start answering No while
    the other answers Yes.
    """
    stamp = ((rec or {}).get("generation_stamp")
             or ((rec or {}).get("cadence") or {}).get("generation_stamp"))
    return stamp if stamp == DRY_RUN_STAMP else None


def refuse_dry_run_records(recs):
    """Refuse to attach or activate records stamped by a dry run.

    A dry run produces artifacts marked with `DRY_RUN_STAMP`. Those records
    must not reach a provider - not at attach, not at activation. This
    function checks a list of records and raises if any carry the stamp.

    Called by both HeyReach and EmailBison at the attach and activation
    boundaries, so neither channel can send a dry-run artifact.
    """
    stamped = []
    for rec in (recs or ()):
        if dry_run_stamp_of(rec):
            stamped.append(rec.get("id") or "?")
    if stamped:
        raise CampaignPipelineError(
            "%d record(s) carry the dry-run stamp %r and may not be "
            "attached or activated: %s. A dry run produced no approved "
            "copy." % (len(stamped), DRY_RUN_STAMP, ", ".join(stamped[:5])))


def generate(client, account, contacts, *, config=None, model=None, live=False,
             allow_pending_offers=False, validate=None, client_slug=None):
    """Generate a SequencePlan for one account's outreach.

    `client` is a client name (str) or a loaded config dict.
    `account` has `company`, `domain`, and optionally `sources` (research pack)
    and `persona`.
    `contacts` is a list of dicts with `email`, `first_name`, `title`,
    `contact_key`, optionally `linkedin`, `sender_name`, `sender_email`.

    `model` is injectable. Tests pass `llm.ScriptedModel`; production passes
    `llm.OpenAICompatibleModel` or `llm.from_env()`.

    Returns a SequencePlan dict. Projections (preview, provider payloads,
    approval hash) derive from it via `sequenceplan.derive_*`.

    `validate` is an optional callable taking the per-contact result and
    returning a list of human-readable failures. It is how a caller that holds
    the RECORD - `generate.py` - brings the per-draft gates (`lint.check`,
    `claims.check`, the repetition gate) to bear on the writer's output, which
    this module cannot do because it has no record. A non-empty return
    REGENERATES the whole set; it never edits it.

    `client_slug` is the canonical client identity from the record
    (``rec["client"]``). When `client` is a config dict, the display name
    (``config["name"]``) is NOT the authority for client identity - the
    record's own slug is. Pass it here so Second Brain retrieval uses the
    canonical identity rather than deriving one from display text.

    Raises `CampaignPipelineError` if the client config cannot be loaded.
    Raises `NotApproved` if the offer this run SELECTS for the account's segment
    and persona is not approved, or if NO offer is selected at all. A pending
    offer elsewhere in the library that this run does not select does not
    refuse it - `_select_offers` says what "selects" means.
    Raises `CampaignPipelineError` if contacts is empty.
    Raises `llm.ModelError` (including `ModelUnavailable` and
    `NoModelConfigured`) rather than holding a contact and returning: a model
    failure is not a property of the prospect, and passing silently with no
    copy is fail-open.
    """
    if not contacts:
        raise CampaignPipelineError(
            "no contacts provided for account %r; generation requires at "
            "least one contact." % account.get("company", "?"))

    if isinstance(client, str):
        try:
            config = config or clients.load(client)
        except clients.ConfigError as e:
            raise CampaignPipelineError(
                "client %r config could not be loaded: %s. "
                "A missing client config is a configuration error, not a "
                "reason to silently use a different pipeline."
                % (client, e))
        client_name = client
    else:
        config = client
        client_name = config.get("name", "")

    if model is None:
        model = llm.NoModel()

    account_company = account.get("company", "")
    account_domain = account.get("domain", "")

    # WHO THIS RUN IS FOR. Read before the offer gate rather than at step 3,
    # because the gate validates the offer this run SELECTS and selection is a
    # property of the prospect's segment and persona. Nothing else moved: the
    # same two values still decide the strategy below.
    persona = account.get("persona", "champion")
    segment_key = account.get("segment", client_name)

    # 1. OFFERS: fail-closed, and SCOPED TO WHAT THIS RUN SELECTED.
    #
    # TASK-427, operator decision 5 (2026-09-27, restated the same evening):
    # only the offer selected for this prospect is validated, not every offer in
    # the library. This iterated `offers.load()` and raised on the first
    # unapproved record it met, so the six PENDING capability offers - which are
    # correct, are the provenance of the two the operator approved, and which no
    # run selects - refused every run for productive at `OFFER-PM-001`,
    # including a dry run. Fail-closed, and pointed at the wrong question.
    #
    # THE BYPASS IS EXPLICIT AND NARROW, and an earlier version of this got it
    # wrong in a way worth recording. Making `not live` the bypass trigger
    # weakened the gate for EVERY non-live caller, including library callers and
    # the TASK-369 tests that assert `generate()` fail-closes on unapproved
    # offers whatever the mode. A caller now has to ask for the bypass by name.
    #
    # `allow_pending_offers` exists for one purpose the operator named: letting
    # them watch the whole new path execute before any offer is approved. It is
    # not a mode, it is a deliberate request, and it is never implied. It allows
    # a PENDING selected offer and nothing else: an EMPTY selection still
    # refuses under it, because "watch the path run before approval" presumes
    # there is an offer to watch.
    offers_gate_bypassed = bool(allow_pending_offers)
    selected_offers = _select_offers(segment_key, persona)
    _check_offers(selected_offers, segment_key, persona,
                  allow_pending=offers_gate_bypassed)

    # 2. SECOND BRAIN: deferred until the offer is resolved, because the
    # admitted subset depends on the offer's capability and the persona.

    # 3. STRATEGY: once per segment+persona.
    strategy = _decide_strategy(segment_key, persona, model,
                                client=client_name, config=config)

    # 4. SOURCES: account research pack, cleaned.
    sources = _prepare_sources(account)

    # 5. CAPABILITIES: from client config, for the match stage.
    caps_cfg = (config.get("product") or {}).get("capabilities") or {}

    # 6. PER-CONTACT pipeline.
    cadence_info = _cadence_stub(config)

    batch_capabilities = []

    # THE ONE OFFER THIS RUN SELECTED, AND THE LIBRARY'S MESSAGING RULES.
    #
    # `_select_offers` returns the shippable offer for this segment and persona
    # and `_check_offers` has already refused anything unapproved, so by this
    # line there is exactly one offer for a client whose library composes one
    # per persona. It is resolved HERE rather than inside `_process_contact`
    # because it is a property of the run, not of the contact: every contact in
    # one `generate()` call shares the segment and the persona, and resolving it
    # per contact would invite two contacts of the same run being written
    # against two different spines.
    #
    # A library with more than one shippable offer in scope leaves this None and
    # the gate reports the ladder as UNCHECKED rather than picking one, because
    # "which of these two spines is this sequence following" is not a question
    # code may answer by taking the first.
    offer = (next(iter(selected_offers.values()))
             if len(selected_offers) == 1 else None)
    offer_id = (next(iter(selected_offers)) if len(selected_offers) == 1
                else None)
    messaging = offers_mod.messaging_rules()

    # 2 (deferred). SECOND BRAIN: admitted facts for internal strategy.
    # VERIFIED and CLIENT_SUPPLIED for the relevant subset - this persona,
    # this offer's capabilities. Never prospect-facing.
    #
    # IDENTITY: use the canonical slug from the record, not the display name.
    # When `client` is a config dict, `client_name` is `config["name"]` - the
    # presentation label ("Productive"). The record's own `client` field is
    # the canonical identity ("productive"), threaded in as `client_slug`.
    # A Second Brain retrieved by display name is a Second Brain retrieved by
    # guess; the slug is the authority.
    sb_identity = client_slug or client_name
    sb_facts = _load_admitted_facts(sb_identity, persona, offer)

    plan = sequenceplan.new(
        client_name, account, [],
        strategy=strategy,
        second_brain_facts=sb_facts,
        offers=selected_offers,
        cadence=cadence_info,
    )

    for contact in contacts:
        contact_result = _process_contact(
            contact, account_company, account_domain, sources,
            caps_cfg, strategy, sb_facts, config, model,
            client_name=client_name, validate=validate,
            offer=offer, offer_id=offer_id, messaging_rules=messaging,
            # THE ACCOUNT DICT, which `_process_contact` referenced by name and
            # never had. `personalization.level_for` needs it; see the comment
            # on that call.
            account=account,
        )
        plan["contacts"].append(contact_result)
        cap = (contact_result.get("match") or {}).get("capability_key")
        if cap and contact_result.get("qualification") not in (
                "UNQUALIFIED", "INSUFFICIENT"):
            batch_capabilities.append(cap)

    # 7. BATCH-LEVEL sequence gate.
    if batch_capabilities:
        batch_gate = sequencegate.check(
            {"emails": {"em1": "x"}, "linkedin": {}, "ps": {},
             "subjects": {}},
            batch_capabilities=batch_capabilities,
        )
        plan["batch_gate"] = batch_gate

    # 8. STAMP. Two independent reasons an artifact is not provider-ready, and
    # either is sufficient: it came from a non-live run, or the offer gate was
    # bypassed. Bypass therefore ALWAYS implies a stamp, so a gate that was
    # skipped can never produce an artifact a provider would accept.
    if offers_gate_bypassed or not live:
        plan["generation_stamp"] = DRY_RUN_STAMP

    return plan


def _applies_to(offer, segment_key, persona):
    """Is this offer in scope for this prospect's segment and persona?

    THE SAME PREDICATE `campaignstrategy._offers_for_segment` ALREADY USES, on
    purpose: segment `all` matches everything, an offer that declares no persona
    matches every persona. Two places that answer "which offers is this run
    about" with different rules is how the gate comes to validate one set while
    the strategy plans around another.
    """
    offer_segment = offer.get("segment", "all")
    if offer_segment != "all" and offer_segment != segment_key:
        return False
    offer_persona = offer.get("persona", "")
    if offer_persona and offer_persona != persona:
        return False
    return True


def _select_offers(segment_key, persona):
    """The offers THIS run has selected for this prospect. TASK-427.

    Selection, in order, and every step reads the offer library's own recorded
    structure rather than a rule invented here:

    1. **Scope.** The offers whose segment and persona apply (`_applies_to`).
    2. **Constituents are PROVENANCE, not shippable offers.** An offer named in
       another offer's `composes` list is one of the parts that offer was built
       from. The operator reviewed and approved the COMPOSED record; its
       constituents record where its clauses came from. This is the conservative
       reading of the two available: the alternative - that approving a composed
       offer implicitly approves its parts as independently shippable records -
       would let this code treat six offers nobody reviewed as approved, which
       is exactly the pressure this defect creates rather than its fix.
    3. **A composed offer is the shippable unit.** Where the scope contains an
       offer that composes others, THAT is what the prospect is offered and the
       bare capability offers beside it are building blocks. `productive` has
       one composed offer per persona - `OFFER-A-ECONOMIC-BUYER` for
       `economic_buyer`, `OFFER-B-OPERATIONS` for `champion` - so selection is
       single-valued, which is what "the offer selected for that prospect"
       means. A library with no composed offers keeps every non-constituent
       offer in scope, so this step narrows and never widens.

    Returns a dict of offer id -> offer. An EMPTY result is a real answer and
    `_check_offers` refuses it; it is never silently treated as "nothing to
    check".
    """
    library = offers_mod.load()

    constituents = set()
    for offer in library.values():
        for part in (offer.get("composes") or ()):
            constituents.add(part)

    selected = {
        oid: offer for oid, offer in library.items()
        if oid not in constituents and _applies_to(offer, segment_key, persona)
    }

    composed = {oid: offer for oid, offer in selected.items()
                if offer.get("composes")}
    return composed or selected


def _check_offers(selected, segment_key, persona, allow_pending=False):
    """Every offer this run SELECTED must be approved. Fail-closed.

    Raises `NotApproved` naming the first unapproved SELECTED offer, in a stable
    order so the refusal names the same offer on every run.

    NO OFFER SELECTED REFUSES. An empty selection is the likeliest way to turn
    this fail-closed gate fail-open: `for oid in {}` is a silent pass, and a run
    with no offer has nothing licensing the copy it is about to write. It raises
    `NotApproved` rather than a second exception class so that a caller handling
    "the offer gate refused" cannot handle one half and miss the other.

    `allow_pending` is `generate()`'s explicit `allow_pending_offers` request and
    covers ONLY the approval status of a selected offer. It never excuses an
    empty selection and it is never inferred from `live`.
    """
    if not selected:
        raise NotApproved(
            f"no offer is selected for segment {segment_key!r} persona "
            f"{persona!r}, so nothing licenses this campaign's copy. "
            f"Selection refuses rather than passes: an empty selection is not "
            f"'no offer to check'. Production does not approve its own offers."
        )
    if allow_pending:
        return
    for oid in sorted(selected):
        offer = selected[oid]
        if offer.get("approval_status") != offers_mod.APPROVED:
            raise NotApproved(
                f"selected offer {oid} has approval_status="
                f"{offer.get('approval_status')!r}, not 'approved'. "
                f"Production does not approve its own offers."
            )


def _offer_capability_names(offer):
    """The product capability keys this offer covers.

    Reads the offer's own `capability` field - NOT `ai_capabilities`, which is
    a different concept (AI feature pages). For a composed offer, also includes
    the `capability` of each composed offer from the library.
    """
    if not offer:
        return set()
    names = set()
    cap = offer.get("capability")
    if cap:
        names.add(cap)
    for part_id in (offer.get("composes") or ()):
        part = offers_mod.load().get(part_id)
        if part:
            part_cap = part.get("capability")
            if part_cap:
                names.add(part_cap)
    return names


def _resolve_client_slug(client_name):
    """Resolve a client slug.

    The caller must provide a canonical slug - the identity the record
    carries, not a display name. If `client_name` is a valid slug that
    exists, returns it. Otherwise raises ConfigError: an unreadable
    authority is UNKNOWN, never silently empty, and canonical identity is
    never derived from display text by lowercasing, case folding, or
    normalisation.
    """
    if clients.valid_slug(client_name) and clients.exists(client_name):
        return client_name
    clients.load(client_name)
    return client_name


def _load_admitted_facts(client_slug, persona, offer):
    """Second Brain facts admitted for internal strategy use.

    Admits VERIFIED and CLIENT_SUPPLIED facts for the RELEVANT SUBSET:
    this contact's persona and the selected offer's capability. Excludes
    linkedin_sequence.fallbacks (message templates, not strategy knowledge)
    and restricts angle_labels to the persona's own angles.

    CLIENT_SUPPLIED knowledge informs strategy and hypothesis but NEVER becomes
    a prospect-facing assertion. The writer's prospect-facing `facts` argument
    comes from the account pack - those two streams stay separate.

    `client_slug` MUST be the canonical slug from the record (e.g. "productive"),
    NOT a display name (e.g. "Productive"). A ConfigError from an unresolvable
    slug propagates - an unreadable authority is UNKNOWN, never an empty list.
    """
    slug = _resolve_client_slug(client_slug)
    brain = secondbrain.for_task("campaign_strategy", slug)

    cap_names = _offer_capability_names(offer)
    config = clients.load(slug)
    persona_cfg = (clients.personas(config) or {}).get(persona) or {}
    persona_angles = set((persona_cfg.get("angles") or {}).keys())

    admitted = []
    for section, facts in brain.items():
        for fact in facts:
            if not (fact.get("verified") or
                    fact.get("canonical_status") == CLIENT_SUPPLIED):
                continue
            source = fact.get("source", "")
            key = source.split(" ", 1)[-1] if " " in source else ""

            if key == "linkedin_sequence.fallbacks":
                continue

            if key == "angle_labels":
                text = fact.get("text", "")
                angle_name = ""
                m = _ANGLE_LABEL_RE.search(text)
                if m:
                    angle_name = m.group(1)
                if angle_name not in persona_angles:
                    continue

            if key == "product.capabilities":
                cap_key = (fact.get("text", "").split(":"))[0].strip()
                if cap_key not in cap_names:
                    continue

            if key == "product.capability_by_persona":
                if persona not in fact.get("text", ""):
                    continue

            if key.startswith("personas."):
                parts = key.split(".")
                if len(parts) >= 2 and parts[1] != persona:
                    continue

            admitted.append(fact)
    return admitted


_ANGLE_LABEL_RE = re.compile(r"Angle label '([^']+)':")


def _decide_strategy(segment_key, persona, model, client=None, config=None):
    """Strategy decided ONCE per segment+persona.

    Delegates to `campaignstrategy.for_segment`, which caches and counts.
    The system prompt comes from the `campaign_strategy` skill's procedure,
    not from the raw constant.
    """
    from . import campaignstrategy
    skill = skills.load("campaign_strategy")
    return campaignstrategy.for_segment(
        segment_key, persona, model=model, system_prompt=skill.procedure,
        client=client, config=config)


def _prepare_sources(account):
    """Clean the account's research sources for the prompts.

    Sources come from the account dict, not from hardcoded work/ paths.
    """
    raw = account.get("sources") or []
    out = []
    for src in raw:
        text = _clean(src.get("text", ""))
        if text:
            out.append({
                "label": src.get("label") or "site",
                "url": src.get("url"),
                "text": text,
            })
    return out


_NAV = re.compile(
    r"^(?:\s*(?:login|about|home|menu|contact|services|work|"
    r"recent work|blog|pricing|team|careers|portfolio|our work|"
    r"skip to main content)\b[\s|,-]*)+", re.I)


def _clean(text, limit=2500):
    return re.sub(r"\s+", " ", _NAV.sub("", str(text or "").strip()))[:limit]


def _cadence_stub(config):
    """The cadence the plan uses, with resolved steps from cadencelibrary.

    The steps are stored on the plan so every consumer reads timing and
    thread relation from the plan rather than from the library directly.
    """
    name = config.get("cadence", "productive_li_heavy_v1")
    steps = cadencelibrary.named(name)
    return {"name": name, "steps": tuple(steps or ())}


#: The two things that can go wrong reading a writer's answer, as the caller
#: sees them. TASK-942: machine-readable because a hold reason is prose and an
#: operator asking "was my budget too small, or is the model answering
#: rubbish?" must not have to parse a sentence to find out. `"truncated"` means
#: ask again unchanged; `"unusable"` means ask again with the reason attached.
TRUNCATED, UNUSABLE = "truncated", "unusable"


def _unreadable_refusal(exc):
    """`(kind, reason)` for an answer that could not be read. TASK-942.

    ONE PLACE THAT TURNS A CLASS INTO WORDS, so the machine-readable kind on
    the result and the sentence the writer is told next can never disagree
    about which failure happened - a second copy of this mapping is how they
    would start to.

    The two reasons give DIFFERENT instructions on purpose. A cut-off answer is
    told to write less; an unusable one is told what was wrong with its shape.
    Telling a truncated writer "return valid JSON" wastes the attempt: its JSON
    was valid as far as it got.
    """
    detail = " ".join(str(exc).split())[:160]
    if isinstance(exc, llm.TruncatedAnswer):
        return TRUNCATED, (
            "your previous answer WAS CUT OFF before it finished - it stopped "
            "in the middle of the JSON, so none of it could be used (%s). The "
            "JSON you were writing was fine as far as it got. Write the same "
            "object again and make it SHORTER: fewer words per email, no "
            "commentary, no repeated text, and nothing outside the one JSON "
            "object" % detail)
    return UNUSABLE, (
        "the answer was not valid JSON and nothing could be read from it (%s). "
        "Return ONE JSON object and nothing else, and keep it short enough to "
        "finish" % detail)


def _process_contact(contact, company, domain, sources, caps_cfg,
                     strategy, sb_facts, config, model, client_name=None,
                     validate=None, offer=None, offer_id=None,
                     messaging_rules=None, account=None):
    """Run stages A-G for one contact. Returns a contact entry for the plan.

    `offer` is the one offer this run selected, `offer_id` its id, and
    `messaging_rules` the offer library's own block. All three default to None
    and absence is REPORTED by the gate rather than passed - see
    `sequencegate.check`.
    """
    email = contact.get("email", "")
    first_name = contact.get("first_name", "")
    title = contact.get("title", "")
    contact_key = contact.get("contact_key", email)
    sender_name = contact.get("sender_name",
                              (config.get("sender") or {}).get("name", ""))

    result = {
        "contact_key": contact_key,
        "email": email,
        "first_name": first_name,
        "title": title,
        "sequences": {},
        "subjects": {},
        "facts": [],
        "hypothesis": {},
        "match": {},
        "qualification": None,
        "held": None,
        "sequence_gate": {},
        "copylint": {},
        "hold_kind": None,
        "gate_attempts": 0,
        "gate_rejections": [],
        # WHICH ANSWERS COULD NOT BE READ, AND WHY, IN ORDER. TASK-942.
        # `"truncated"` for an answer cut off at the token budget,
        # `"unusable"` for one that finished and finished wrongly. Empty on a
        # contact whose every answer parsed, which is the common case.
        "writer_parse_refusals": [],
    }

    try:
        # A. ICP check — through the signal_verification skill.
        icp_skill = skills.load("signal_verification")
        icp_raw = _call_model(model, icp_skill.procedure,
                              copyprompts.icp_user(company, domain, sources),
                              client=client_name, config=config)
        icp = _parse_json(icp_raw)
        if not icp.get("is_agency"):
            result["qualification"] = "UNQUALIFIED"
            result["held"] = "not an agency: %s" % (
                icp.get("what_they_actually_are") or "?")
            result["hold_kind"] = "qualification"
            return result

        # B. Extract facts — through the account_research skill.
        extract_skill = skills.load("account_research")
        extract_raw = _call_model(
            model, extract_skill.procedure,
            copyprompts.extract_user(company, domain, sources),
            client=client_name, config=config)
        extracted = _parse_json(extract_raw)
        facts = extracted.get("facts") or []
        for f in facts:
            f["source_url"] = copyprompts.source_url_for(f, sources)
        result["facts"] = facts
        if not facts:
            result["qualification"] = "INSUFFICIENT"
            result["held"] = "no verifiable fact in the pack"
            result["hold_kind"] = "qualification"
            return result

        # C. Hypothesis
        br_context = _format_br_context(sb_facts)
        hyp_raw = _call_model(
            model, copystages.HYPOTHESIS_SYSTEM,
            copystages.hypothesis_user(company, domain, title, facts,
                                       br_context),
            client=client_name, config=config)
        hyp = _parse_json(hyp_raw)
        result["hypothesis"] = hyp
        result["qualification"] = hyp.get("qualification") or "QUALIFIED_THIN"
        if result["qualification"] == "INSUFFICIENT":
            result["held"] = "insufficient basis: %s" % hyp.get(
                "hypothesis_basis")
            result["hold_kind"] = "qualification"
            return result

        # D. Match
        match_raw = _call_model(
            model, copystages.MATCH_SYSTEM,
            copystages.match_user(hyp.get("hypothesis"),
                                  hyp.get("role_family"),
                                  title, caps_cfg),
            client=client_name, config=config)
        match = _parse_json(match_raw)
        result["match"] = match
        cap_key = match.get("capability_key")
        cap_sentence = caps_cfg.get(cap_key, "")

        # E. Strategy is already decided (cached per segment+persona).
        # The hypothesis informs the writer's angle. In v2_run.py the strategy
        # was per-lead and took the hypothesis as input; here the strategy is
        # per-segment but the hypothesis still flows to the writer through the
        # capability match and the plan context.
        plan_data = dict(strategy) if strategy else {}
        plan_data["hypothesis"] = hyp.get("hypothesis", "")
        plan_data["what_changes"] = match.get("what_changes", "")
        # THE OFFER'S OWN LADDER, IN THE WRITER'S PROMPT, RUNG BY RUNG.
        #
        # `sequencegate` refuses a step that pursues another rung's objective
        # more closely than its own, and `TASK-425` criterion 3 requires that.
        # A writer that was never told the ladder cannot follow it, so the gate
        # would refuse correct-looking copy on every attempt and the retry
        # budget would be spent telling the model nothing - which is the
        # failure `RETRY_BLOCK`'s own comment describes for `filler_phrase`.
        #
        # It rides `plan_json`, the channel the strategy already travels on,
        # rather than a new prompt section: the writer reads one plan, and a
        # second place for "what this message is for" is a second thing to
        # drift. `offer_step_objectives` is the operator's approved record,
        # copied verbatim and not paraphrased.
        #
        # `ai_capabilities` accompanies it as NAMES ONLY, with the rule that
        # governs them, because the same gate refuses an AI capability named at
        # a rung whose objective does not name one, and refuses two in one
        # message. The page text stays out: it is evidence a claim traces to,
        # not copy, and handing a model verbatim marketing text invites it back
        # out as a quotation.
        # WHICH RUNG OF THE PERSONALIZATION LADDER THIS DRAFT IS WRITTEN AT.
        #
        # Operator decision, 2026-09-30: missing personalization selects a
        # different truthful ANGLE, it does not discard the account. The
        # writer has to know which one, or it manufactures an icebreaker it
        # has no fact for - and `copylint.untraceable_company_claim` then
        # refuses the whole contact for a sentence nobody needed.
        #
        # It rides `plan_json` like `offer_step_objectives`, and it licenses
        # NOTHING: every claim in the draft is still checked by `claims` and
        # `copylint` exactly as before.
        # IT HAS NEVER ONCE REACHED THE WRITER, AND THE BARE EXCEPT IS WHY.
        #
        # This read `_pz.level_for(account, contact)`, and `_process_contact`
        # HAS NO `account` - it takes `company`, `domain` and `sources`. So
        # every call raised `NameError: name 'account' is not defined`, the
        # `except Exception: pass` below swallowed it, and
        # `plan_data["personalization_level"]` was never set on any contact of
        # any run since the field was added. MEASURED 2026-10-01 by rendering
        # the real writer prompt for `bigfish-co-uk` / `rowan-matthews`: the
        # plan block carried `offer_step_objectives` and `offer_mechanism` and
        # no `personalization_level` at all.
        #
        # The cost is not cosmetic. `WRITER_SYSTEM` says "THE PLAN CARRIES
        # `personalization_level`. OBEY IT" and that at levels 2 to 4 the writer
        # has no facts worth opening on and must ask a QUESTION instead of
        # manufacturing an icebreaker. This record is LEVEL 3 with zero research
        # rows, the writer was never told, and the refusals it earned were
        # exactly the predicted ones: "step 1 opens with a line no pack fact
        # supports" and a P.S. that enumerates the prospect's own services.
        #
        # `NameError` is in `PIPELINE_DEFECTS`, so an outer handler would have
        # named this a defect and stopped the run on the first contact. It never
        # got there because this handler is inside it. The account dict is now a
        # PARAMETER, so the name cannot go missing again without a TypeError at
        # the call site, and the handler is narrowed to the one failure that is
        # genuinely tolerable - a personalization module that cannot score this
        # contact - with the reason recorded on the plan instead of discarded.
        try:
            from . import personalization as _pz
            _level = _pz.level_for(account or {}, contact)
            plan_data["personalization_level"] = _pz.describe(_level)
        except PIPELINE_DEFECTS:
            raise
        except Exception as _pz_exc:                          # noqa: BLE001
            result["personalization_unavailable"] = "%s: %s" % (
                type(_pz_exc).__name__, str(_pz_exc)[:160])
        if offer:
            plan_data["offer_id"] = offer_id
            plan_data["offer_step_objectives"] = dict(
                offer.get("step_objectives") or {})
            plan_data["offer_ai_capabilities"] = sorted(
                offer.get("ai_capabilities") or {})
            plan_data["offer_mechanism"] = offer.get("mechanism_text")
            plan_data["ai_rule"] = (
                "at most one AI capability per message, only at the step whose "
                "objective names one, never required")
        plan_json = json.dumps(plan_data, indent=1)

        # F. Writer
        variant = copyprompts.ps_variant_for(email)
        if variant == "ps_none":
            variant = "ps_fact"
        result["ps_variant"] = variant

        # F. Writer — through the cold_email_writing and linkedin_writing
        # skills. Both share WRITER_SYSTEM; the entrypoint loads both so
        # neither is disconnected.
        email_skill = skills.load("cold_email_writing")
        linkedin_skill = skills.load("linkedin_writing")
        writer_system = email_skill.procedure

        name = (first_name + " " + contact.get("last_name", "")).strip()
        # THE LADDER TWICE: ONCE AS DATA, ONCE AS THE RULE THE GATE APPLIES.
        #
        # `plan_json` already carries `offer_step_objectives`, and that was not
        # enough: MEASURED 2026-10-01 on the bigfish canary, the objectives were
        # in the prompt verbatim and `step_objectives` was still the dominant
        # refusal on em3 and em5, because every worked example in
        # `WRITER_SYSTEM` is OFFER A's ladder and the offer selected for persona
        # `champion` is OFFER B. `copystages.step_objective_block` renders THIS
        # offer's rungs with the literal words each step must carry, computed
        # from `sequencegate`'s own `_content_words` so the two cannot drift.
        #
        # `thread_reply_rungs` is passed as the offer records it - absent on
        # OFFER-B-OPERATIONS - so the block states the GATE's exemptions and not
        # a more generous set.
        writer_base = copystages.writer_user(
            {"name": name, "title": title, "sender_name": sender_name},
            company, facts, plan_json, cap_sentence, variant,
            bool(contact.get("linkedin")),
            step_objectives=(offer or {}).get("step_objectives") or {},
            ai_capabilities=sorted((offer or {}).get("ai_capabilities") or {}),
            thread_reply_rungs=(offer or {}).get("thread_reply_rungs") or ())

        # F+G. WRITE, GATE, REGENERATE. Never patch, never widen a rule.
        #
        # THE DEFECT THIS CLOSES. `copylint.check_batch` was called, its report
        # stored on the result, and NOTHING read it: a refused draft was
        # returned exactly like a clean one and `generate.py` wrote it into the
        # cadence. So the batch lint that exists to stop bad copy shipping was a
        # field on a dict, which is the "computed correctly and nothing
        # downstream reads it" defect CLAUDE.md names as this repository's
        # recurring one - and the copy path is the one that reached 77 real
        # prospects with an empty body on 09-23.
        #
        # A refusal now costs the writer another attempt, with the REASON fed
        # back, and after `MAX_WRITER_ATTEMPTS` the copy is REFUSED: the
        # sequences are emptied so no caller can store a draft that failed a
        # gate as a send candidate.
        rejected = []
        for attempt in range(1, MAX_WRITER_ATTEMPTS + 1):
            writer_prompt = writer_base
            if rejected:
                writer_prompt = writer_base + (RETRY_BLOCK
                                               % _retry_reasons(rejected))
            # TEMPERATURE RISES WITH THE ATTEMPT, and attempt 1 is unchanged
            # at 0. `complete()` defaults to 0, so every retry re-derived
            # almost the same draft from almost the same prompt and
            # re-committed violations it had already been told about.
            # MEASURED 2026-09-29 on the Rachele canary, two models, six
            # attempts each: `openai/gpt-4.1-mini` was refused for "would you
            # be interested" on attempts 1, 3 and 5, and `openai/gpt-4.1` for
            # a dash on three of its six. A deterministic writer handed the
            # same instructions writes the same mistake.
            #
            # This changes NO GATE. Every draft still passes the same checks
            # or is refused; a warmer retry only explores more of the space
            # the gates already bound.
            #
            # A TRUNCATED ANSWER COSTS ONE ATTEMPT, NOT THE ROUND.
            #
            # MEASURED 2026-10-01, bigfish canary round 3 of three:
            # `json.JSONDecodeError: Expecting ',' delimiter: line 1 column 2811
            # (char 2810)`. `JSONDecodeError` is a `ValueError`, it is NOT in
            # `PIPELINE_DEFECTS`, so it fell to the `except Exception` handler at
            # the bottom of this function, which emptied the sequences and
            # returned `hold_kind="error"`. One cut-off response therefore threw
            # away the whole round - the five attempts already made and the five
            # still owed - and the operator spent a generation round learning
            # nothing. The writer's answer is eleven messages of JSON on one
            # line; a model stopping early is an ordinary event, not a defect in
            # this code and not a property of the prospect.
            #
            # So it is a REFUSAL LIKE ANY OTHER: it counts the attempt, it names
            # its own reason, that reason is fed back through `RETRY_BLOCK` like
            # every other rejection, and the loop continues. Only if all ten
            # attempts fail does the contact hold - by the same `copy_refused`
            # path as a draft that could not pass lint.
            #
            # NOTHING IS LOOSENED. An unparseable answer is still never stored:
            # `continue` skips every assignment to `result["sequences"]` below,
            # so there is no half-populated draft for a later gate to accept.
            # `PIPELINE_DEFECTS` - a parse that succeeds and yields the wrong
            # TYPES - is deliberately not caught here and still stops the run.
            #
            # TWO CLASSES, NOT ONE REASON STRING. TASK-942. This caught a bare
            # `ValueError` and told the writer "not valid JSON" whatever had
            # happened, which collapsed two different failures into one: an
            # answer CUT OFF at the token budget (the model was writing the
            # right thing and ran out of room - worth asking again with the SAME
            # prompt) and an answer that FINISHED WRONGLY (prose, a trailing
            # comma, the wrong shape - worth asking again only with a reason
            # attached). `llm.TruncatedAnswer` and `llm.UnusableAnswer` name the
            # two, `result["writer_parse_refusals"]` records which happened in
            # order, and both still cost exactly one attempt.
            #
            # THE CALL IS INSIDE THE `try` because truncation has two witnesses:
            # `_parse_json` reads the text's structure, and
            # `llm.OpenAICompatibleModel.complete` reads the endpoint's
            # `finish_reason == "length"` and raises before any text is
            # returned. Only one `except` may be allowed to see either.
            # `llm.ModelError` is NOT caught here and still reaches the handler
            # below that re-raises it, so a rate limit or an outage still stops
            # the run instead of being spent as ten writer attempts.
            result["gate_attempts"] = attempt
            try:
                writer_raw = _call_model(
                    model, writer_system, writer_prompt,
                    client=client_name, config=config,
                    temperature=_retry_temperature(attempt),
                    # AND IT CARRIES A TOKEN BUDGET. Until TASK-942 this call
                    # told the writer nothing about how long its answer may be,
                    # so the only bound was the endpoint's own default and a
                    # long answer came back as a prefix. `WRITER_MAX_TOKENS` is
                    # derived from the ceilings `lint` already enforces on the
                    # eleven messages being asked for; see its definition for
                    # the measurement behind every term.
                    max_tokens=WRITER_MAX_TOKENS)
                w = _parse_json(writer_raw)
            except llm.UnreadableAnswer as parse_exc:
                kind, reason = _unreadable_refusal(parse_exc)
                result["writer_parse_refusals"].append(kind)
                rejected.append(reason)
                result["gate_rejections"] = list(rejected)
                # NO SEPARATE EXHAUSTION BRANCH. `continue` leaves the `for`
                # loop to finish normally, so a tenth unparseable answer falls
                # through to this loop's own `else:` and holds the contact with
                # `copy_refused` and this reason - one exhaustion path, not two
                # that can drift apart.
                continue

            if w.get("hold"):
                result["held"] = "writer held: %s" % w.get("hold_reason")
                result["hold_kind"] = "writer_hold"
                result["sequences"] = {}
                result["subjects"] = {}
                return result

            # Populate sequences from writer output.
            # NORMALISE PUNCTUATION BEFORE LINT. The writer may produce
            # curly apostrophes (U+2019), em dashes (U+2014) and other
            # substituted characters that `lint.normalise_punctuation` maps
            # to their ASCII equivalents. The legacy path in `generate.py`
            # calls it on every body, subject and note; the canonical path
            # must do the same or U+2019 survives into `copylint` and
            # refuses the draft. Applied here, before `copylint.check_batch`,
            # so every prospect-facing string the writer produced is
            # normalised in one place.
            _np = lint.normalise_punctuation
            result["sequences"] = {
                "em1": _np((w.get("emails") or {}).get("em1", "")),
                "em2": _np((w.get("emails") or {}).get("em2", "")),
                "em3": _np((w.get("emails") or {}).get("em3", "")),
                "em4": _np((w.get("emails") or {}).get("em4", "")),
                "em5": _np((w.get("emails") or {}).get("em5", "")),
            }
            result["subjects"] = {
                "A": _np(w.get("subject", "")),
                "B": _np(w.get("subject_alt", "")),
                "C": _np(w.get("subject_breakup", "")),
            }
            for key in LINKEDIN_WRITER_KEYS:
                li_text = (w.get("linkedin") or {}).get(key, "")
                if li_text:
                    result["sequences"][key] = _np(li_text)
            for key in ("em1", "em3"):
                ps_text = (w.get("ps") or {}).get(key, "")
                if ps_text:
                    result["sequences"]["ps_" + key] = _np(ps_text)

            # G. copylint, then sequencegate
            # A REPLY'S SUBJECT IS ITS THREAD'S SUBJECT, NOT AN EMPTY STRING.
            #
            # em2 and em4 were built with `"subject": ""` here because the
            # writer returns three subjects for five steps: A for em1, B for
            # em3, C for em5, with em2 and em4 replying inside those threads.
            # But an empty subject is not "no subject" to a lint that reads the
            # rendered text - `copylint`'s `empty_sentence` rule fired on the
            # blank line the two empties left in the concatenated subjects and
            # REFUSED EVERY LEAD THIS PIPELINE HAS EVER PRODUCED. The rule was
            # right ("a variable rendered to nothing"), nothing read its
            # verdict, so nobody saw it. A same-thread reply carries the subject
            # of the thread it continues, which is what the provider sends as
            # `Re: <subject>` and what `EMAILBISON-COPY-REQUIREMENTS.md` means
            # by one conversation.
            _subj = {
                "em1": result["subjects"].get("A", ""),
                "em2": result["subjects"].get("A", ""),
                "em3": result["subjects"].get("B", ""),
                "em4": result["subjects"].get("B", ""),
                "em5": result["subjects"].get("C", ""),
            }
            lead_for_lint = {
                "id": contact_key,
                "steps": [
                    {"subject": _subj[k],
                     "body": result["sequences"].get(k, "")}
                    for k in ("em1", "em2", "em3", "em4", "em5")
                ],
                "ps": {k: v for k, v in result["sequences"].items()
                       if k.startswith("ps_")},
                "linkedin": {k: v for k, v in result["sequences"].items()
                             if k in LINKEDIN_WRITER_KEYS},
                "pack": {
                    "facts": [{"snippet": f.get("quote") or f.get("text")}
                              for f in facts],
                    # THE CLIENT'S OWN CAPABILITY NAMES, from the offer this
                    # run selected. `copylint` reads a capitalised multi-word
                    # name as something the model invented, which is right
                    # for a prospect's customer and wrong for "Report
                    # Intelligence" - a name the operator approved, with its
                    # own licensed page text, that will never appear in the
                    # PROSPECT's pack. Offer A's rung 4 requires naming it,
                    # so the approved ladder demanded a step the lint then
                    # refused.
                    "licensed_names": tuple(
                        (offer or {}).get("ai_capabilities") or ()),
                    # TASK-922: and the licensed TEXT with them. The name
                    # exemption says the name is not an invention; only the
                    # page text says what the copy may claim it does.
                    # TASK-922 (b): the containment authority, narrow.
                    "offer_containment_text": [
                        (offer or {}).get("mechanism_text"),
                        (offer or {}).get("mechanism_secondary_text")],
                    "licensed_capabilities": {
                        str(n): ((v or {}).get("page_text")
                                 if isinstance(v, dict) else v)
                        for n, v in ((offer or {}).get("ai_capabilities")
                                     or {}).items()},
                },
            }
            result["copylint"] = copylint.check_batch([lead_for_lint])

            seqs_for_gate = {
                "company": company,
                "emails": {k: v for k, v in result["sequences"].items()
                           if k.startswith("em") and v},
                "linkedin": {k: v for k, v in result["sequences"].items()
                             if k in LINKEDIN_WRITER_KEYS and v},
                "ps": {k: v for k, v in result["sequences"].items()
                       if k.startswith("ps_") and v},
                "subjects": result["subjects"],
                "hypothesis": hyp.get("hypothesis", ""),
            }
            result["sequence_gate"] = sequencegate.check(
                seqs_for_gate, facts=facts, capability=cap_sentence,
                qualification=result["qualification"],
                offer=offer, messaging_rules=messaging_rules)
            result["offer_id"] = offer_id

            failures = _locate_copylint(
                copylint_failures(result["copylint"], contact_key),
                result.get("sequences"), result.get("subjects"))
            # THE SEQUENCE GATE'S VERDICT IS STILL NOT READ HERE, AND THAT IS A
            # RECORDED FINDING RATHER THAN AN OVERSIGHT LEFT ALONE.
            #
            # `result["sequence_gate"]` is computed two lines above, stored on
            # the result, and consulted by nothing: the retry loop breaks on
            # `copylint` alone, so a sequence the gate REFUSED is returned
            # exactly like one it passed, written into the record by
            # `generate._adapt_plan_to_cadence`, and stopped two gates later by
            # `bisonfactory._refuse_sequence_gate`. That is the "computed
            # correctly and nothing downstream reads it" shape `CLAUDE.md` names
            # as this repository's recurring defect, and it is what
            # `result["copylint"]` was before `TASK-400`.
            #
            # MEASURED, 2026-09-28, TASK-425's first real run of this
            # entrypoint: the gate refused `em5` for `hypothesis_not_asserted`
            # ("I know your schedule is busy") and the run reported the contact
            # as written, one attempt, no rejections. Separately, this suite's
            # own canonical GOOD draft (`HARBOURLINE_SEQUENCES`) is refused by
            # `channels_complement` on `msg1` and `msg2` and is stored anyway.
            #
            # WHY IT IS NOT FIXED BY FOLDING THE FAILURES IN HERE. `offers.py`
            # is single-tenant: `_offers_path()` resolves
            # `productive-offers.yaml` whatever client is being generated for,
            # so the offer handed to the gate for ANY client is Productive's.
            # Folding the gate's failures into this list would make Productive's
            # approved five-rung ladder refuse copy for a client that never
            # approved it - a worse fault than the one it fixes, and a decision
            # about licensed claims rather than a wiring change.
            #
            # THE CALLER CAN STILL DEMAND IT TODAY, through the seam built for
            # exactly this: `validate` takes the per-contact result and a
            # non-empty return regenerates the whole set. `TASK-425`'s harness
            # passes the gate's own failures through it, which enforces the
            # ladder for the one client whose ladder it is without imposing it
            # on any other.
            #
            # The caller's per-draft gates, which need the RECORD this module
            # does not have: `lint.check`, `claims.check`, the repetition gate.
            if validate is not None:
                failures = failures + list(validate(result) or ())
            if not failures:
                break
            rejected.append("; ".join(failures))
            result["gate_rejections"] = list(rejected)
        else:
            # EVERY ATTEMPT WAS REFUSED, so there is no draft. Emptying the
            # sequences is what makes "never stored as a send candidate" true
            # rather than a comment: a caller cannot store what is not there.
            result["held"] = ("no draft passed lint in %d attempts: %s"
                              % (MAX_WRITER_ATTEMPTS, rejected[-1][:300]))
            result["hold_kind"] = "copy_refused"
            result["sequences"] = {}
            result["subjects"] = {}
            return result

    except llm.ModelError:
        # A MODEL ERROR HOLDS THE RECORD, AND IS NOT THE PROSPECT'S FAULT.
        #
        # This was `except (llm.ModelError, llm.ModelUnavailable): result[
        # "held"] = "model error: ..."`, which turned every model failure into a
        # per-contact hold and returned a plan the caller could not tell from a
        # successful one. `ModelUnavailable` (a rate limit) and
        # `NoModelConfigured` (nobody set LLM_API_KEY) are subclasses, so a
        # configuration mistake of ours was written into canonical state as a
        # property of the company - the exact defect
        # `generate_record`'s own handler exists to prevent, bypassed by
        # catching the exception before it could reach it.
        #
        # Passing silently with no copy is fail-open. It propagates.
        raise
    except PIPELINE_DEFECTS as e:
        # A DEFECT IN THIS CODE IS NOT A PROPERTY OF THE PROSPECT EITHER, and
        # this is the handler that hid one for a whole run.
        #
        # `rec["research"]` carried a shape `claims.support_text` could not
        # read, `support_text` raised `AttributeError: 'str' object has no
        # attribute 'get'` through the `validate` callback, and this `except
        # Exception` turned it into `hold_kind="error"` for every contact. The
        # run reported no crash, stored nothing, and looked complete. That is
        # the most expensive possible outcome: a confident, empty deliverable.
        #
        # Classified explicitly and failing closed, exactly as `llm.ModelError`
        # is directly above: a `NotApproved`-class refusal names a gate, a hold
        # names a reason the prospect is unusable, and THIS names a bug. The
        # three are now tellable apart by an operator reading a run report,
        # because the third one does not produce a run report.
        #
        # THE COST IS NAMED RATHER THAN HIDDEN: a model answer that parses as
        # JSON but carries the wrong types (`{"emails": "..."}`) raises
        # `AttributeError` here too, and now stops the account's run instead of
        # holding one contact. That is the conservative direction - nothing is
        # stored and the operator is told once - and a malformed-shape answer is
        # a fault of ours or of the model, never of the company. `ValueError`
        # from `_parse_json` (no JSON at all, or unparseable JSON) is NOT in
        # this tuple and still holds the contact, which is the case operator
        # decision 3 is about.
        raise CampaignPipelineError(
            "contact %r broke the generation pipeline: %s: %s. This is a defect "
            "in the code or in the shape of the state it was handed, not a "
            "property of the prospect, so it is not converted into a hold: a "
            "crash recorded as `hold_kind=\"error\"` is how a run came back "
            "complete with nothing stored."
            % (contact_key, type(e).__name__, str(e)[:200])) from e
    except llm.UnreadableAnswer as e:
        # CLASSIFIED BEFORE THE BROAD HANDLER, NOT INSIDE IT. TASK-942.
        #
        # The writer's own loop above handles its two classes and retries them;
        # this clause is for the OTHER stages - ICP, extract, hypothesis, match -
        # which also call `_parse_json` and whose answers can also be cut off.
        # Every one of those landed in the `except Exception` below as
        # `hold_kind="error"`, the same anonymous bucket as a crash, so an
        # operator reading a run report could not tell "our token cap was too
        # small" from "this prospect is unusable" from "the code is broken". That
        # is the defect: not the breadth of the handler, but that it answered for
        # a case it could name.
        #
        # STILL A HOLD, STILL FAIL-CLOSED. Nothing is stored and nothing is
        # retried here - these stages ask for a short verdict and a cut-off
        # verdict is not a prospect problem, so it is named and left for the
        # operator rather than silently re-asked. `hold_kind` carries the class;
        # `copy_refused` and `qualification` are untouched, and `"error"` below
        # now means only what it says.
        kind, reason = _unreadable_refusal(e)
        result["held"] = "the model's answer could not be read (%s): %s" % (
            kind, reason)
        result["hold_kind"] = "model_answer_" + kind
        result["writer_parse_refusals"].append(kind)
        result["sequences"] = {}
        result["subjects"] = {}
    except Exception as e:
        result["held"] = "%s: %s" % (type(e).__name__, str(e)[:200])
        result["hold_kind"] = "error"
        result["sequences"] = {}
        result["subjects"] = {}

    return result


def copylint_failures(report, lead_id):
    """The batch-lint rules this lead actually offended, as sentences.

    `check_batch` reports counts and offender lists per rule for a whole batch.
    A writer retry needs the rules THIS lead broke, in words - so this reads the
    offender lists rather than the refusal flag, which cannot say who or what.
    Warning-only rules are excluded: `WARNING_RULES` is advisory by definition
    and spending a regeneration attempt on one would starve the real failures.
    """
    out = []
    for rule, offenders in (report or {}).get("offenders", {}).items():
        if rule in copylint.WARNING_RULES:
            continue
        if lead_id in (offenders or ()):
            out.append((report.get("rules") or {}).get(rule, rule))
    return out


#: The batch rules whose offence can be pointed at with the rule's OWN
#: matcher. Nothing is re-implemented here: each entry calls into `copylint`,
#: so a rule that changes there cannot start being described wrongly here.
_LOCATORS = {
    "dash": lambda text: (lambda m: m.group(0) if m else None)(
        copylint.DASH_RE.search(text)),
    "buzzword": lambda text: (lambda hits: ", ".join(sorted(hits)[:3])
                              if hits else None)(copylint.buzzwords_in(text)),
}


def _locate_copylint(failures, sequences, subjects=None):
    """Say WHERE each batch-lint offence is, where the rule can point at it.

    `copylint.check_batch` answers per LEAD - "this lead used a dash" - which
    is the right unit for an operator looking at a push and the wrong one for
    a writer holding eleven messages. Measured 2026-09-29 on the Rachele
    canary: `openai/gpt-4.1` was refused for `dash` on five of six attempts
    and never removed it, while every `lint` failure in the same run named
    its step ("em3: you used ...") and was fixed on the next attempt.

    Only rules with a locator above are annotated. Anything else is returned
    UNCHANGED rather than guessed at - a wrong location would send the writer
    to rewrite a message that was fine.
    """
    texts = dict(sequences or {})
    for key, value in (subjects or {}).items():
        texts["subject of %s" % key] = value
    out = []
    for failure in failures or ():
        rule = next((r for r, sentence in copylint.RULES
                     if sentence == failure and r in _LOCATORS), None)
        if rule is None:
            out.append(failure)
            continue
        found = []
        for key, text in texts.items():
            if not isinstance(text, str) or not text.strip():
                continue
            try:
                hit = _LOCATORS[rule](text)
            except Exception:                                 # noqa: BLE001
                hit = None
            if hit:
                found.append("%s (%r)" % (key, hit))
        out.append("%s -> %s" % (failure, "; ".join(found[:4]))
                   if found else failure)
    return out


def _call_model(model, system, user, client=None, config=None,
                temperature=0, max_tokens=None):
    """Route a model call through the injected model.

    The system and user prompts are concatenated into a single prompt for the
    `complete()` seam. The model's `complete()` method handles the HTTP call,
    the spend ledger, and the retry loop.

    `client` and `config` thread into the spend gate. TASK-373.

    `max_tokens` is the caller's budget for the ANSWER. TASK-942. Passed only
    when there is one, so a caller that has no opinion sends the request it
    always sent and no model seam has to invent a default. The stages that ask
    for a short verdict - ICP, extract, hypothesis, match - deliberately pass
    nothing; the writer, which asks for eleven messages at once, passes
    `WRITER_MAX_TOKENS`.
    """
    extra = {} if max_tokens is None else {"max_tokens": max_tokens}
    return model.complete(system + "\n\n" + user, client=client, config=config,
                          temperature=temperature, **extra)


def _json_unterminated(text):
    """Did this text STOP in the middle of a JSON value?

    TASK-942. The structural witness that an answer is a PREFIX of an answer,
    and the only one available when the model is a stub or a CLI that reports
    no `finish_reason`.

    It is a fact, not a heuristic: scanning once with a string/escape state
    machine, a document that opened a brace or bracket and reached the end of
    the text while still inside a string, or with depth still above zero, DID
    NOT FINISH. There is no other way for a well-formed prefix to end.

    The converse matters just as much. Balanced braces mean the model stopped
    where it meant to, so an invalid document with balanced braces - a trailing
    comma, a missing delimiter between two closed values - is NOT a truncation
    and must not be reported as one. That is the case
    `tests/test_the_writer_is_told_how_long_its_answer_may_be.py` controls for.

    Trailing prose after the object ("...} Hope this helps!") leaves depth at
    zero and is correctly not a truncation; `_parse_json` already trims it.
    """
    depth, in_string, escaped, opened = 0, False, False, False
    for ch in text:
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch in "{[":
            depth += 1
            opened = True
        elif ch in "}]":
            depth -= 1
    return opened and (in_string or depth > 0)


def _parse_json(text):
    """Extract JSON from model output, tolerating fences.

    Raises `llm.TruncatedAnswer` for an answer that stopped early and
    `llm.UnusableAnswer` for one that finished wrongly. TASK-942: both are
    `ValueError` subclasses, so every caller that already caught `ValueError`
    here is unchanged, and a caller that needs to tell "the model was cut off"
    from "the model answered something unusable" now can. Only the first is
    worth asking again with the same prompt.
    """
    if isinstance(text, dict):
        return text
    t = re.sub(r"^```(?:json)?|```$", "", str(text or "").strip(), flags=re.M)
    i, j = t.find("{"), t.rfind("}")
    if i == -1:
        # NO OBJECT AT ALL IS UNUSABLE, EVEN IF IT WAS ALSO CUT OFF. Prose that
        # stops early and prose that runs to the end are indistinguishable from
        # here, and the fail-closed read of "nothing of the requested shape
        # arrived" is that the answer was wrong, not merely short.
        raise llm.UnusableAnswer("no JSON in model output: %r" % t[:160])
    # SCAN THE OBJECT, NOT THE PROSE AFTER IT.
    #
    # This used to pass `t[i:]` - everything from the first brace to the END of
    # the answer - and `_json_unterminated`'s own docstring already said that was
    # wrong: "trailing prose after the object leaves depth at zero and is
    # correctly not a truncation; `_parse_json` already trims it". The
    # documentation was right and the CALL was not.
    #
    # MEASURED, found by GLM reviewing this branch and confirmed on both sides:
    # `{"a":1} She said "maybe` PARSES to `{'a': 1}` on master and raised
    # `TruncatedAnswer` here, because the unmatched quote in the trailing
    # sentence left the scanner `in_string` at the end of the text. That is
    # exactly the shape a model produces when it writes the JSON and then adds a
    # sentence - and since a truncation is the one refusal this module says is
    # worth retrying with the same prompt, it would have spent attempts on an
    # answer that was already complete.
    #
    # When there is no closing brace at all the span IS the rest of the text,
    # which is the genuine prefix case and still raises.
    span = t[i:j + 1] if j > i else t[i:]
    if _json_unterminated(span):
        raise llm.TruncatedAnswer(
            "the JSON opened and never closed, so the %d characters that "
            "arrived are a prefix of an answer and not an answer"
            % len(span))
    if j == -1:
        raise llm.UnusableAnswer("no JSON in model output: %r" % t[:160])
    try:
        return json.loads(t[i:j + 1], strict=False)
    except ValueError as exc:
        # BALANCED AND STILL INVALID: the model finished and finished wrongly.
        # Reported as unusable even though `JSONDecodeError`'s own message often
        # sounds like a cut ("Expecting ',' delimiter"), because the brace scan
        # above has already proved the document closed.
        raise llm.UnusableAnswer(
            "the model finished and what it finished is not valid JSON "
            "(%s: %s)" % (type(exc).__name__,
                          " ".join(str(exc).split())[:120])) from exc


def _format_br_context(facts):
    """Format verified Second Brain facts for the hypothesis prompt."""
    if not facts:
        return None
    lines = []
    for fact in facts:
        lines.append("[%s] %s (source: %s, verified: %s)" % (
            fact.get("source", "unknown"),
            fact.get("text", ""),
            fact.get("source", ""),
            fact.get("verified", False)))
    return "\n".join(lines) if lines else None
