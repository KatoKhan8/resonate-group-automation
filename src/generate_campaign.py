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
#: replaces on the campaign path: three attempts, then the copy is refused and
#: nothing is stored.
MAX_WRITER_ATTEMPTS = 3

#: THE LINKEDIN KEYS THE WRITER PRODUCES AND THE CADENCE CONSUMES.
#: Canonical names li1-li5 match the cadence library and heyreachfactory's
#: COPY_MAPPING, so the writer-to-cadence mapping is an identity. The single
#: authority is `cadencelibrary.LINKEDIN_WRITER_KEYS`; this module re-exports
#: it so existing import sites keep working, and every consumer reads one
#: tuple.
LINKEDIN_WRITER_KEYS = cadencelibrary.LINKEDIN_WRITER_KEYS

#: WHAT THE MODEL IS TOLD WHEN A GATE REFUSES. The reason, never the code, and
#: never an instruction to edit the old draft - "never widen a lint rule to make
#: a draft pass. Regenerate the draft." A model told `filler_phrase` three times
#: has been told nothing three times, which is how six contacts went unstaged
#: for want of one message each on 2026-09-13.
RETRY_BLOCK = ("\n## Your previous draft failed lint\n\n"
               "%s\n\nWrite a new one. Do not patch the old one.\n")

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

    TASK-367: the new offer format uses a `capabilities` list directly.
    Falls back to the singular `capability` field and the `composes` lookup
    for backward compatibility with the old composed offer format.
    """
    if not offer:
        return set()
    names = set()
    # TASK-367: the new format carries capabilities as a list on the offer.
    caps = offer.get("capabilities")
    if caps:
        names.update(caps)
        return names
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


def _process_contact(contact, company, domain, sources, caps_cfg,
                     strategy, sb_facts, config, model, client_name=None,
                     validate=None, offer=None, offer_id=None,
                     messaging_rules=None):
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
        writer_base = copystages.writer_user(
            {"name": name, "title": title, "sender_name": sender_name},
            company, facts, plan_json, cap_sentence, variant,
            bool(contact.get("linkedin")))

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
                writer_prompt = writer_base + (RETRY_BLOCK % rejected[-1])
            writer_raw = _call_model(model, writer_system, writer_prompt,
                                     client=client_name, config=config)
            w = _parse_json(writer_raw)
            result["gate_attempts"] = attempt

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
                "pack": {"facts": [{"snippet": f.get("quote") or f.get("text")}
                                   for f in facts]},
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

            failures = copylint_failures(result["copylint"], contact_key)
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


def _call_model(model, system, user, client=None, config=None):
    """Route a model call through the injected model.

    The system and user prompts are concatenated into a single prompt for the
    `complete()` seam. The model's `complete()` method handles the HTTP call,
    the spend ledger, and the retry loop.

    `client` and `config` thread into the spend gate. TASK-373.
    """
    return model.complete(system + "\n\n" + user, client=client, config=config)


def _parse_json(text):
    """Extract JSON from model output, tolerating fences."""
    if isinstance(text, dict):
        return text
    t = re.sub(r"^```(?:json)?|```$", "", str(text or "").strip(), flags=re.M)
    i, j = t.find("{"), t.rfind("}")
    if i == -1 or j == -1:
        raise ValueError("no JSON in model output: %r" % t[:160])
    return json.loads(t[i:j + 1], strict=False)


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
