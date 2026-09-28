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
import os
import re

from . import (cadencelibrary, clients, copyprompts, copystages, copylint, llm,
               offers as offers_mod, secondbrain, sequencegate, sequenceplan,
               skills)

ENTRYPOINT_VERSION = sequenceplan.ENTRYPOINT_VERSION

DRY_RUN_STAMP = "DRY-RUN / OFFERS PENDING"

#: How many times the writer is asked again after a gate refuses its output.
#: Same budget as `generate.MAX_DRAFT_ATTEMPTS`, which is the rule this
#: replaces on the campaign path: three attempts, then the copy is refused and
#: nothing is stored.
MAX_WRITER_ATTEMPTS = 3

#: WHAT THE MODEL IS TOLD WHEN A GATE REFUSES. The reason, never the code, and
#: never an instruction to edit the old draft - "never widen a lint rule to make
#: a draft pass. Regenerate the draft." A model told `filler_phrase` three times
#: has been told nothing three times, which is how six contacts went unstaged
#: for want of one message each on 2026-09-13.
RETRY_BLOCK = ("\n## Your previous draft failed lint\n\n"
               "%s\n\nWrite a new one. Do not patch the old one.\n")

#: THE RETRY BLOCK THAT CARRIES EVERY EARLIER REFUSAL, NOT ONLY THE LAST ONE.
#:
#: `RETRY_BLOCK % rejected[-1]` fed back the MOST RECENT attempt's failures and
#: nothing else, so attempt 3 was told nothing about what attempt 1 broke and
#: was free to reintroduce it. Measured 2026-09-28 on the TASK-425 artifact,
#: contact `task425-brightmoor-studio-c3`, whose three refusals walk in a
#: circle rather than converging:
#:
#:   1. `channels_complement/msg3` - msg3 asks a question em5 already asked
#:   2. a merge field survived, and ALL FIVE emails repeat each other
#:      (`repetition_across_rungs` on em1..em5), plus an unfilled placeholder
#:   3. one of the five steps is EMPTY, em3 and em5 are under 40 words
#:
#: Told "every step repeats another step" at attempt 2, the writer shortened and
#: emptied steps at attempt 3 - fixing what it was last told and breaking
#: something it had not been told about. Three attempts, three different
#: failures, no accumulation, and the record held.
#:
#: SO THE HISTORY IS CUMULATIVE AND DEDUPLICATED, and the block says plainly
#: that anything not named was acceptable. That last sentence is the one that
#: stops the oscillation: without it a full rewrite is the model's safest
#: reading of "do not patch the old one", and a full rewrite re-rolls the four
#: cross-step relationships (`step_objectives`, `channels_complement`,
#: `followup_adds_value`, `repetition_across_rungs`) that the gates measure.
#:
#: "Do not patch the old one" STAYS, and is not in tension with this. The rule
#: it enforces is OPERATOR DECISION 1 - never hand-edit an offending phrase to
#: slip past a rule - not "discard what you learned". Regeneration is still
#: whole-sequence and no draft that failed a gate is ever stored.
RETRY_BLOCK_CUMULATIVE = (
    "\n## Your previous %d draft(s) were REFUSED by a gate\n\n"
    "Every reason below was raised on some earlier attempt. ALL of them must "
    "be absent from your next draft - fixing the most recent one and "
    "reintroducing an earlier one is the most common way this fails.\n\n"
    "%s\n\n"
    "Anything NOT named above was acceptable: keep what worked and change "
    "only what these reasons require. Write a complete new sequence. Do not "
    "patch the old one, and do not reword an offending sentence to slip past "
    "the rule it broke.\n")


#: THE LADDER, STEP BY STEP, IN THE WORDS THE GATE MEASURES AGAINST.
#:
#: WHY THIS EXISTS AND WHY THE JSON BLOB WAS NOT ENOUGH. The offer's objectives
#: already reach the writer inside `plan_json` as
#: `offer_step_objectives: {"1": "margin visibility", ..., "5": "reframe and
#: close"}`. That tells the writer the objectives EXIST; it does not tell it
#: which cadence step is which rung, and it does not tell it what
#: `sequencegate.step_objectives` actually measures.
#:
#: WHAT THE GATE ACTUALLY MEASURES, stated here because the writer has to
#: satisfy it and could not previously know it. `objective_overlap` is
#: LEXICAL and stemmed to four characters, and the coverage threshold is
#: EXACTLY ZERO: a step is refused only when it shares NOT ONE stemmed word
#: with its own rung's objective. The order half then refuses a rung whose
#: distinctive vocabulary sits at another step and is ABSENT from its own
#: (`scored[best] > 0 and not scored[rung]`).
#:
#: So both halves are satisfied by the same discipline: EACH STEP CARRIES ITS
#: OWN RUNG'S WORDS. Saying that plainly is the whole fix, and it is a
#: statement of the gate's existing rule rather than a relaxation of it.
#:
#: MEASURED, 2026-09-28, TASK-425 artifact: `step_objectives` is the single
#: largest cause among the refused drafts - 8 of the 23 named failure
#: instances - and rung 5 (`reframe and close`) accounts for most of them.
#: Its two stems are `refr` and `clos`, which are the vocabulary of the
#: email's own rhetorical MOVE rather than of its subject, so a competent
#: breakup email that says "last note" and "circle back" carries neither and
#: is refused for copy that reads correctly. The writer cannot guess that. Told
#: it, it writes "before I close this out" and passes the gate unchanged.
#:
#: REGENERATION IS THE WRONG RESPONSE TO THIS FAILURE and that is the point of
#: the column it sits in: every attempt was a fresh roll of the same blind
#: dice, so the retry budget was spent re-rolling rather than converging.
#: NO `%` FORMATTING IN THIS BLOCK. It carries literal percent signs - the
#: gates' own thresholds, which is the whole point of quoting them - and
#: `HEADER % offer_id` raised `TypeError: not enough arguments for format
#: string` the moment one was added. `TypeError` is in `PIPELINE_DEFECTS`, so
#: it propagated as a pipeline error rather than a per-contact hold, which is
#: correct and is how it was caught. The offer id is concatenated instead.
LADDER_BRIEF_HEADER = """
## THE OFFER'S LADDER - WHICH STEP PURSUES WHICH RUNG

This is the operator-approved spine for offer {OFFER_ID}. Each email below has
ONE objective and the sequence is refused if a step does not pursue its own.

THE RULE THE GATE ENFORCES, so you can satisfy it deliberately: each step must
use ITS OWN rung's own words. The check is lexical - it looks for the
objective's vocabulary in that step - so a step that argues its rung in
entirely different words is still refused, and a step that borrows ANOTHER
rung's distinctive words while its own step omits them is refused as an
out-of-order ladder.

So: write each step's own objective words into that step, and do not carry one
rung's vocabulary into another rung's step.

AND THE STEPS MUST STILL BE FIVE DIFFERENT MESSAGES. This is the trap that
follows directly from the rule above, and it is refused separately:

- Two rungs of this ladder can share a word - "margin" appears in more than
  one objective. Carrying the shared word into both steps is correct. Carrying
  the same ARGUMENT, the same evidence and the same sentence shapes into both
  is not, and `repetition_across_rungs` refuses the whole sequence when two
  steps share three or more distinctive words AND half their vocabulary.
- A follow-up that restates an earlier email's argument is refused by
  `followup_adds_value` at 45% argument overlap.

Each step needs its own POINT, its own evidence and its own question. The rung
objective decides WHAT a step is about; it does not license five variations of
one paragraph. If two steps would make the same argument, change one of them
rather than rewording it.
"""


def _ladder_brief(offer, offer_id):
    """The per-step rung brief, or "" when this run resolved no offer.

    Absence produces NOTHING rather than a default ladder: a client whose
    library declares no objectives must not be written against another
    client's spine, which is the same reason `sequencegate` reports an absent
    ladder as UNCHECKED instead of passing it.
    """
    objectives = {str(k): str(v) for k, v in
                  ((offer or {}).get("step_objectives") or {}).items()}
    if not objectives:
        return ""
    lines = [LADDER_BRIEF_HEADER.replace(
        "{OFFER_ID}", str(offer_id or "this run's offer"))]
    for rung in sorted(objectives):
        lines.append("- em%s pursues rung %s: %r - this step must carry these "
                     "words." % (rung, rung, objectives[rung]))
    # THE CONDITIONAL RUNG IS NAMED AS CONDITIONAL, matching the gate, which
    # WARNS on a mechanism rung rather than refusing it. Telling the writer a
    # rung is required when the gate does not require it would push an AI
    # capability into copy the operator's own rule says never forces one.
    ai_names = [str(n) for n in ((offer or {}).get("ai_capabilities") or {})]
    for rung in sorted(objectives):
        if any(n in objectives[rung] for n in ai_names):
            lines.append(
                "- em%s's objective names an AI capability. That rung is "
                "CONDITIONAL: use it only if it genuinely strengthens the "
                "angle, and never lead with the feature." % rung)
    return "\n".join(lines) + "\n"


#: THE TWO CHANNELS MUST NOT BE THE SAME MESSAGE TWICE.
#:
#: `sequencegate.channels_complement` refuses a LinkedIn message that asks a
#: question an email already asked (question overlap >= 0.6) or that is an
#: email in shorter form (body overlap >= 0.55). Measured 2026-09-28: 4 of the
#: 23 named failure instances, EVERY ONE of them on `msg3`, which is the last
#: LinkedIn message and the one most likely to become a short recap of `em5`.
#:
#: The writer was never told this rule. `copystages`' own LinkedIn brief tells
#: `msg1` not to reuse email 1's question and tells `msg2` to reference the
#: email deliberately, but nothing states the rule for the SET - and nothing
#: tells the writer that a short close which restates em5 is refused.
CHANNEL_BRIEF = """
## THE TWO CHANNELS ARE ONE PERSON, NOT ONE MESSAGE SENT TWICE

Every LinkedIn message is checked against every email and refused if it
repeats one. Two specific refusals, both measured:

- A LinkedIn message may NOT ask a question any email asks. Not a reworded
  version of it - the check compares the content words of the questions.
- A LinkedIn message may NOT be an email in shorter form. Your closing
  LinkedIn message is the usual offender: do not summarise the final email.

Each LinkedIn message needs its OWN argument and its OWN question. If you have
nothing new for a step, say less rather than restating an email.

THE LAST LINKEDIN MESSAGE IS THE ONE THIS CATCHES MOST OFTEN. Measured
2026-09-28: every `channels_complement` refusal in the run this brief was
written for landed on the FINAL LinkedIn message, because a closing message and
a breakup email want to say the same thing. Your closing LinkedIn message must
not restate the final email, must not reuse its question, and must not be a
condensed version of it. Give it a different reason to exist - a single
concrete thing they can look at, or a plain offer to stop - and do not
summarise anything.
"""


#: WHOSE OFFER LIBRARY `offers.py` ACTUALLY RESOLVES.
#:
#: THIS EXISTS BECAUSE `offers.py` IS SINGLE-TENANT AND MUST BE DELETED WHEN IT
#: IS NOT. `offers._offers_path()` joins `productive-offers.yaml` onto the
#: clients directory whatever client is being generated for, and `offers.load()`
#: takes no client argument. So `_select_offers` returns PRODUCTIVE'S offer for
#: every client in the estate.
#:
#: THE MISTAKE THIS CORRECTS WAS MINE, AND IT IS WORTH RECORDING. Folding the
#: sequence gate's verdict into the retry loop was scoped on `offer is not
#: None`, described as "the client whose approved offer this run resolved".
#: That is not what it tests: because the library is single-tenant, `offer` is
#: non-None for EVERY client, so the condition imposed Productive's approved
#: five-rung ladder on clients that never approved it - precisely the fault the
#: comment below refuses to introduce, reintroduced by the fix for it.
#:
#: Caught by `tests/test_generate.py`'s acceptance tests, which generate for
#: `harbourline` (client `contactout`) and began failing on
#: `reason_for_outreach` and `channels_complement` against an offer that is not
#: that client's.
#:
#: Read from the module's own path resolution rather than hardcoded here, so
#: there is no second copy of the tenant's name to drift.
def _client_slug(config):
    """This client's SLUG - the identity `offers.py` is keyed on - or None.

    B4, AND IT MADE THIS BRANCH'S HEADLINE CHANGE INERT IN PRODUCTION.
    The tenant guard compared `_offer_library_tenant()`, a FILENAME SLUG
    derived from `config/clients/productive-offers.yaml`, against
    `client_name`, which for a dict caller is `config["name"]` - a
    human-readable DISPLAY label. `clients.load("productive")["name"]` is
    `'Productive'`, so the comparison was `'Productive' == 'productive'` and
    never true.

    `src/generate.py:_generate_via_campaign` calls
    `generate(client_config or client_name, ...)` and `client_config` is always
    set there, so PRODUCTION ALWAYS TAKES THE DICT BRANCH. The sequence gate's
    verdict therefore went on being computed and read by nobody on the only
    path that generates copy - exactly the defect the change was written to
    close, reported as closed. It fired in one place: a caller passing the
    literal lowercase string, which is a single test.

    I OBSERVED THIS AND CONCLUDED THE OPPOSITE. The sibling tests getting the
    ladder reported UNCHECKED was read as the tenancy scoping working; it was
    the guard failing to match. Mutation M7 surviving - "the sequencegate
    verdict is no longer read in the retry loop" - was the same hole seen from
    the other side, and it was the signal.

    RESOLVED ON BOTH SIDES OF THE COMPARISON, in precedence order:

      1. `client_slug=`, threaded explicitly by the caller that knows it.
         `_generate_via_campaign` reads `rec["client"]`, which IS the slug, so
         production now passes the exact identity rather than a derived one.
      2. `config["client"]`, if a config ever carries it. None does today;
         reading it costs nothing and means a config that grows the field is
         served without another change here.
      3. The display name, NORMALISED. Last resort, and it is a heuristic
         rather than an authority: it matches when a client's label slugifies
         to its filename, which is the common case and is true of Productive.
         A client whose label does not - "Acme Corp" against `acme.yaml` -
         resolves to something that matches no tenant, and the guard then
         declines to apply an offer ladder. That is the CONSERVATIVE direction
         for the question the guard asks, and the same one documented at
         `_offer_library_tenant`: refusing to guess beats applying one
         client's approved spine to another's copy.
    """
    if not isinstance(config, dict):
        return None
    declared = config.get("client")
    if declared:
        return str(declared).strip().lower()
    name = str(config.get("name") or "").strip().lower()
    return re.sub(r"[\s_]+", "-", name) or None


def _offer_library_tenant():
    """The one client `offers.py` can answer for, or None if it cannot say.

    NO BARE `except` HERE, and the first version of this had one - which
    swallowed a `NameError` (this module did not import `os`) and returned
    None, silently disabling the gate read for EVERY client including the one
    it was meant to enable. A silent fallback on a safety path is exactly what
    CLAUDE.md forbids, and it took a one-line probe to find.

    UNKNOWN IS THE CONSERVATIVE ANSWER FOR THE QUESTION THIS ASKS. If the
    tenant cannot be determined, the caller does not apply an offer ladder -
    because the failure being guarded against is applying ONE client's approved
    spine to ANOTHER, and refusing to guess is the safe direction for that.
    It is not fail-open in the gate's own sense: `bisonfactory.
    _refuse_sequence_gate` still refuses the whole push before any provider
    write, which is where this gate was enforced before this change and still
    is.
    """
    name = os.path.basename(offers_mod._offers_path())
    return name.split("-offers")[0] or None


def _threads_for(step_subjects):
    """Step key -> thread key, derived from which subject each step carries.

    Two steps carrying the same subject are in the same thread; that IS what a
    thread is on this provider, and deriving it from the subjects the steps
    actually got means the map cannot disagree with them. A step with no
    subject is its own thread, which is the conservative reading - it makes the
    gate compare MORE subjects rather than fewer.
    """
    return {step: (subject or step)
            for step, subject in (step_subjects or {}).items()}


#: WHOSE OPERATIONS THE COPY MAY ASSERT THINGS ABOUT.
#:
#: THE DOMINANT REMAINING CAUSE, measured 2026-09-28 on this task's own proof
#: runs: the claim family - `copylint.untraceable_company_claim` plus
#: `sequencegate claims_supported` - is the largest single group of refusals
#: once the ladder is fixed, at 25 of roughly 53 named instances in one run.
#:
#: WHAT THE MODEL ACTUALLY DOES WRONG, from the refused sentences themselves:
#:
#:   "Resource allocation across concurrent healthcare projects means you..."
#:   "Since you're planning resources a sprint ahead..."
#:   "If a project was quoted at 40% margin but currently..."
#:
#: Each takes the CAPABILITY SENTENCE's vocabulary - which is Productive's
#: description of its own product - and re-states it as a finding about the
#: prospect's operations. `claims.asserts_about_them` then refuses it, exactly
#: correctly: an operational term asserted in the second person needs something
#: stored behind it, and a product description is not evidence about a
#: prospect.
#:
#: SO THE FIX IS THE GRAMMAR, NOT THE CONTENT. The same capability can be
#: written as what the product does ("Productive shows margin per project while
#: it runs") without asserting anything about them, and that passes the gate
#: unchanged. The writer was never told the difference, and `writer_user` hands
#: it the capability sentence under the heading "The capability, in the
#: client's own words" with no instruction about whose sentence it may become.
CLAIM_BRIEF = """
## WHAT YOU MAY ASSERT ABOUT THEM, AND WHAT YOU MAY NOT

Two different things, and mixing them is the most common reason this copy is
refused:

1. THEIR OPERATIONS. You may state a fact about them ONLY if it is in the
   numbered facts above. Anything else about how they work, bill, resource,
   quote or lose money is a GUESS, and a guess written in the second person is
   refused - "you're planning a sprint ahead", "your quotes slip", "resource
   allocation means you..." all assert something no stored fact supports.
2. THE PRODUCT. You may describe what Productive does without limit, because
   that is a claim about US. "Productive shows margin per project while it
   runs" is always allowed. "You can't see margin while a project runs" is not.

THE REWRITE THAT PASSES: whenever you want to say they have a problem, either
ask it as a question, hedge it as a pattern ("agencies on retained work often
find..."), or say what the product does instead. All three are allowed; the
flat second-person assertion is the only one that is not.

NO FIGURE THAT IS NOT IN THE FACTS. Not a percentage, not a range, not a
multiple, not "three times", not "double" - spelled in digits or in words. A
benchmark you inferred is an invented number and it is refused.
"""


def _cumulative_retry_block(rejected):
    """The retry block naming every distinct failure seen so far, in order.

    Deduplicated on the exact sentence, because the same rule firing on three
    attempts is one thing to fix and three copies of it in the prompt crowds
    out the others. Order is first-seen, so the oldest unfixed failure stays
    visible at the top rather than scrolling away.
    """
    seen, lines = set(), []
    for attempt_failures in rejected:
        for sentence in str(attempt_failures).split("; "):
            sentence = sentence.strip()
            if sentence and sentence not in seen:
                seen.add(sentence)
                lines.append("- " + sentence)
    return RETRY_BLOCK_CUMULATIVE % (len(rejected), "\n".join(lines))

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
        client_slug = client_slug or client
    else:
        config = client
        client_name = config.get("name", "")
        # THE SLUG, WHICH IS NOT THE DISPLAY NAME. See `_client_slug`.
        client_slug = client_slug or _client_slug(config)

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

    # 2. SECOND BRAIN: only verified facts inform strategy.
    sb_facts = _load_verified_facts(client_name)

    # 3. STRATEGY: once per segment+persona.
    strategy = _decide_strategy(segment_key, persona, model,
                                client=client_name, config=config)

    # 4. SOURCES: account research pack, cleaned.
    sources = _prepare_sources(account)

    # 5. CAPABILITIES: from client config, for the match stage.
    caps_cfg = (config.get("product") or {}).get("capabilities") or {}

    # 6. PER-CONTACT pipeline.
    cadence_info = _cadence_stub(config)
    plan = sequenceplan.new(
        client_name, account, [],
        strategy=strategy,
        second_brain_facts=sb_facts,
        offers=selected_offers,
        cadence=cadence_info,
    )

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

    for contact in contacts:
        contact_result = _process_contact(
            contact, account_company, account_domain, sources,
            caps_cfg, strategy, sb_facts, config, model,
            client_name=client_name, validate=validate,
            offer=offer, offer_id=offer_id, messaging_rules=messaging,
            tenant_slug=client_slug,
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


def _load_verified_facts(client_name):
    """Second Brain facts that are verified. INFERRED facts inform strategy
    but never become prospect-facing assertions."""
    try:
        brain = secondbrain.for_task("campaign_strategy", client_name)
    except (ValueError, Exception):
        return []
    verified = []
    for section, facts in brain.items():
        for fact in facts:
            if fact.get("verified"):
                verified.append(fact)
    return verified


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
                     messaging_rules=None, tenant_slug=None):
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
        # THE RULES THE GATES ENFORCE, IN THE PROMPT THAT HAS TO SATISFY THEM.
        #
        # Appended here rather than inside `copystages.writer_user` because
        # both blocks are derived from THIS RUN's resolved offer, which that
        # function is not given and should not be: the ladder is a property of
        # the offer the run selected, and a writer prompt that carried a
        # hardcoded copy of it would be a second place for the operator's
        # approved spine to drift from `productive-offers.yaml`.
        #
        # An empty ladder brief appends nothing at all, so a client with no
        # declared objectives is written exactly as before.
        writer_base = writer_base + _ladder_brief(offer, offer_id)
        writer_base = writer_base + CLAIM_BRIEF
        if contact.get("linkedin"):
            writer_base = writer_base + CHANNEL_BRIEF

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
                writer_prompt = writer_base + _cumulative_retry_block(rejected)
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

            # Populate sequences from writer output
            result["sequences"] = {
                "em1": (w.get("emails") or {}).get("em1", ""),
                "em2": (w.get("emails") or {}).get("em2", ""),
                "em3": (w.get("emails") or {}).get("em3", ""),
                "em4": (w.get("emails") or {}).get("em4", ""),
                "em5": (w.get("emails") or {}).get("em5", ""),
            }
            result["subjects"] = {
                "A": w.get("subject", ""),
                "B": w.get("subject_alt", ""),
                "C": w.get("subject_breakup", ""),
            }
            # A MISSING REQUIRED ELEMENT IS RECORDED, NEVER SILENTLY DROPPED.
            #
            # THE DEFECT THIS CLOSES, operator, 2026-09-28, found by reading the
            # certified run's actual copy. Both loops were `if text:` -> store,
            # with NO else: an element the writer returned as "" simply did not
            # appear in `result["sequences"]`, and every downstream reader saw a
            # sequence that was complete except for something nobody had asked
            # about. Two live consequences, both in the certified artifact:
            #
            #   - THE P.S. IS MISSING EVERYWHERE. `variant` above is forced away
            #     from `ps_none` to `ps_fact`, so a P.S. IS required on em1 and
            #     em3 - and `copystages`' own output schema shows it as
            #     `"ps":{"em1":"","em3":""}`, which the writer returns verbatim.
            #     `if ps_text:` then dropped both, and the artifact carries no
            #     P.S. field for any of the nine messages.
            #   - LINKEDIN STEP 5 RENDERS NOTHING. See `_PLAN_LINKEDIN_ORDER`
            #     and `generate._content_shortfall` for the other half of this:
            #     the cadence declares five LinkedIn steps and the writer is
            #     asked for four.
            #
            # `missing_required` is what makes it BLOCK rather than degrade. It
            # is folded into `failures` below, so an absent required element
            # costs a writer attempt exactly as a lint failure does, and after
            # `MAX_WRITER_ATTEMPTS` the contact HOLDS with the sequences
            # emptied. "All required messages must render, and missing content
            # must BLOCK the run" - a gate that cannot tell "checked and fine"
            # from "there was nothing there" is the defect class this module
            # exists to avoid.
            missing_required = []
            for key in ("connect", "msg1", "msg2", "msg3", "msg4"):
                li_text = (w.get("linkedin") or {}).get(key, "")
                if str(li_text or "").strip():
                    result["sequences"][key] = li_text
                elif contact.get("linkedin"):
                    # ONLY WHEN THE CONTACT HAS A PROFILE. A contact with no
                    # LinkedIn is told by `writer_user` to return empty strings
                    # for these, so absence is correct there and refusing it
                    # would hold every email-only contact.
                    missing_required.append(
                        "LinkedIn message %r is required for this contact and "
                        "came back empty" % key)
            for key in ("em1", "em3"):
                ps_text = (w.get("ps") or {}).get(key, "")
                if str(ps_text or "").strip():
                    result["sequences"]["ps_" + key] = ps_text
                elif variant != "ps_none":
                    missing_required.append(
                        "the P.S. for %s is required (P.S. variant %r) and came "
                        "back empty" % (key, variant))

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
            # ONE THREAD, ONE SUBJECT - the same answer the record stores and
            # the provider is told.
            #
            # This map was the SECOND copy of `generate._PLAN_SUBJECT_OF`'s
            # three-thread assumption (A, A, B, B, C), and it is corrected for
            # the reason recorded at that constant: `ISSUE-054` is RULED, the
            # operator's words are *"Same subject across one thread is correct
            # threading"* (`docs/OPERATING-MODE.md` section 17), and the
            # 2026-09-16 invariant is that only the opener owns a subject.
            #
            # IT MATTERS HERE SPECIFICALLY BECAUSE THIS IS WHAT COPYLINT SEES.
            # Feeding the lint three subjects while the record stores one, and
            # while `bisonfactory._variables_for` blanks `subject_2..5` before
            # the wire, means the gate was judging two subjects no prospect can
            # receive - and `no_repetition/subjects` compared them against each
            # other. Correcting the INPUT is the fix; the rule is untouched.
            _subj = {k: result["subjects"].get("A", "")
                     for k in ("em1", "em2", "em3", "em4", "em5")}
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
                             if k in ("connect", "msg1", "msg2", "msg3", "msg4")},
                "pack": {"facts": [{"snippet": f.get("quote") or f.get("text")}
                                   for f in facts]},
            }
            result["copylint"] = copylint.check_batch([lead_for_lint])

            seqs_for_gate = {
                "company": company,
                "emails": {k: v for k, v in result["sequences"].items()
                           if k.startswith("em") and v},
                "linkedin": {k: v for k, v in result["sequences"].items()
                             if k in ("connect", "msg1", "msg2", "msg3", "msg4") and v},
                "ps": {k: v for k, v in result["sequences"].items()
                       if k.startswith("ps_") and v},
                # PER STEP, WITH THE THREAD MAP - the input the check was
                # written to take.
                #
                # This passed `result["subjects"]`, the writer's `{A, B, C}`,
                # and no `threads`. On a ONE-THREAD cadence that asks the gate
                # to compare three subjects of which exactly one is sendable:
                # `bisonfactory._variables_for` blanks `subject_2..5`, so B and
                # C never reach a prospect, and two unused strings colliding
                # would have refused copy that is correct on the wire.
                #
                # `sequencegate`'s own comment prescribes this shape and says
                # the per-thread comparison then WARNS rather than passing
                # silently, which is why this is not a way of switching the
                # check off: with one thread there is one subject to compare
                # and the report says so in those words.
                "subjects": _subj,
                "hypothesis": hyp.get("hypothesis", ""),
            }
            result["sequence_gate"] = sequencegate.check(
                seqs_for_gate, facts=facts, capability=cap_sentence,
                qualification=result["qualification"],
                offer=offer, messaging_rules=messaging_rules,
                threads=_threads_for(_subj))
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
            # ------------------------------------------------------------------
            # RESOLVED, 2026-09-28 (P0-B). THE VERDICT IS NOW READ HERE, and the
            # single-tenancy objection above is answered rather than waived.
            #
            # The objection was correct about the hazard and wrong about the
            # trigger. `offers.py` being single-tenant matters only if this code
            # applies an offer THIS CLIENT DID NOT SELECT. It does not: `offer`
            # is `None` unless `generate()` resolved EXACTLY ONE shippable offer
            # for this run's segment and persona (`_select_offers`), and
            # `_check_offers` has already refused anything unapproved. So the
            # condition is `offer is not None` - the gate's verdict is read for
            # the client whose approved offer this run actually resolved, and a
            # client with no resolved offer is unaffected. That is precisely the
            # scoping the harness achieved from outside, moved to where the
            # retry loop can act on it.
            #
            # WHAT THIS IS NOT. It is not a new rule and it does not change a
            # threshold, an input or a verdict. `sequencegate.check` is called
            # with the same arguments as before, on the same line, and returns
            # the same result; the only change is that a REFUSAL now costs an
            # attempt and reaches the writer, instead of being stored on the
            # result for nobody. It can only ever refuse MORE copy than before,
            # never less - the direction a gate is allowed to move.
            #
            # WHERE THE ENFORCEMENT ALREADY WAS, so this is not load-bearing
            # alone: `bisonfactory._refuse_sequence_gate` refuses the whole push
            # before any provider write, and still does. This closes the gap
            # between the refusal and the only loop that can fix it - the
            # refusal used to arrive after the copy was stored, at a stage whose
            # own message says "REGENERATE the affected steps" to a caller with
            # no regeneration budget left.
            #
            # THE WARNINGS ARE DELIBERATELY NOT FOLDED IN. `sequencegate` warns
            # where it could NOT check something (an absent ladder, a step key
            # with no rung, a conditional mechanism rung). Spending a
            # regeneration attempt on "this was not checked" would starve the
            # real failures, which is the same reason `copylint_failures` skips
            # `WARNING_RULES`.
            # THE CONDITION IS THE TENANT, NOT MERELY "AN OFFER RESOLVED".
            # See `_offer_library_tenant`: `offers.py` hands Productive's offer
            # to every client, so `offer is not None` is true everywhere and
            # would apply one client's approved ladder to all of them.
            # THE SLUG, NOT THE DISPLAY NAME. This compared `client_name`,
            # which is `config["name"]` ('Productive') for every dict caller
            # and so never matched the filename slug ('productive') - making
            # this whole branch dead on the only path production uses. B4.
            if offer is not None and tenant_slug and (
                    tenant_slug == _offer_library_tenant()):
                failures = failures + [
                    "sequencegate %s/%s: %s" % (f.get("check"), f.get("step"),
                                                f.get("why"))
                    for f in (result["sequence_gate"].get("failures") or ())]
            # AND THE REQUIRED ELEMENTS THE WRITER DID NOT RETURN AT ALL.
            # Appended last so a structurally incomplete sequence is refused on
            # the same attempt as its content failures rather than after them.
            failures = failures + missing_required
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
