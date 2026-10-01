"""The sequence-level gate. docs/COPY-ENGINE-SPEC-v2.md section 5.

WHY THIS IS NOT `copylint`.

`copylint` asks whether each message is acceptable. Every message in the
2026-09-25 batch passed it, and the sequence was still wrong: five emails
making one argument in five phrasings, a LinkedIn note asking the question
email 1 had already asked, and the same capability chosen for every lead.
**A campaign can be built entirely from acceptable messages and still be bad**,
and nothing in this repository could say so.

So this module asks about the WHOLE sequence, and it answers with the STEP
that caused each failure. `sequencegate` does not say "regenerate"; it says
"em4 repeats em2", and one message is rewritten. Regenerating everything
hides which message was wrong and burns the budget hiding it.

WHAT IT DELIBERATELY DOES NOT DO.

It does not judge whether the copy is good. Taste is not a check. It looks for
the specific, mechanical failures that were actually observed: repetition
across steps, a hypothesis written as a finding, a claim with no fact behind
it, a question asked twice across channels, and a capability that never varies
across a batch.
"""
import re

from . import copylint

#: Words that carry no argument. Two messages sharing only these share
#: nothing, so they are removed before any overlap is measured.
STOPWORDS = frozenset("""
a an and are as at be been but by can could did do does for from had has have
how i if in into is it its just like may might more most much must no not of
on one only or our out over own she so some such than that the their them then
there these they this those to too up us was we were what when where which
while who why will with would you your yours
""".split())

#: A hypothesis stated as a finding. These are the shapes that turn "agencies
#: like yours often find X" into "you have X", which is the sentence that
#: earns a reply telling us we know nothing about them.
AS_FACT_RES = (
    re.compile(r"\byou(?:'re| are) (?:losing|struggling|missing|failing|"
               r"leaking|bleeding)\b", re.I),
    re.compile(r"\byour (?:team|agency|projects?|margins?|process) (?:is|are) "
               r"(?:losing|struggling|missing|failing)\b", re.I),
    re.compile(r"\bi know (?:you|your)\b", re.I),
    re.compile(r"\bbecause you (?:do not|don't|cannot|can't)\b", re.I),
)

#: Hedges that make the same sentence honest. Presence of one of these near a
#: problem statement is what distinguishes a hypothesis from a claim.
HEDGES = ("often", "tend to", "usually", "typically", "many", "most",
          "curious", "wondering", "guess", "imagine", "may", "might",
          "whether", "if ", "do you", "does that", "how early", "how do")

#: WHICH RUNG OF THE OFFER'S LADDER A CADENCE STEP IS.
#:
#: The offer records its objectives under `1`..`5` (`step_objectives` in
#: `config/clients/productive-offers.yaml`); a cadence names its steps `em1`..
#: `em5` and `li1`..`li5` (`cadencelibrary.PRODUCTIVE_LI_HEAVY_V1`). The digit
#: is the join, and it is the only join available: the two vocabularies are
#: independent and nothing else relates them.
#:
#: A step key this cannot read is REPORTED as unchecked rather than skipped.
#: The writer's own LinkedIn keys (`connect`, `msg1`..`msg3`) carry no rung, so
#: a caller handing those over is told the ladder was not checked on them - the
#: alternative is a gate that silently checks the emails and passes four
#: LinkedIn messages nobody looked at.
_RUNG_RE = re.compile(r"^(?:em|li)([1-9])$")

#: The default when the offer library states none. It is the operator's rule of
#: 2026-09-27 - "at most ONE AI capability per prospect-facing message" - and it
#: is a default rather than a requirement on the caller because the absent case
#: must fail CLOSED: a caller that forgets to pass `messaging_rules` gets the
#: strict rule, not no rule.
DEFAULT_MAX_AI_PER_MESSAGE = 1


def _rung_of(step_key):
    """The offer-ladder rung this cadence step key is, or None."""
    found = _RUNG_RE.match(str(step_key or "").strip().lower())
    return found.group(1) if found else None


def _ai_named_in(text, ai_names):
    """Which of the offer's OWN AI capability names this message names.

    The names come from the offer record's `ai_capabilities` map, so this
    recognises exactly what the operator licensed for that offer and nothing
    else. A hardcoded list here would go stale the moment the client's AI page
    changed, and would also start refusing another client's copy for naming a
    feature Productive happens to have.

    CASE-SENSITIVE, ON WORD BOUNDARIES, because these are PRODUCT NAMES and
    several of them are also ordinary English. The first version lower-cased both
    sides and matched a substring, and an adversarial review found two false
    positives that hard-refuse correct copy - both reproduced 2026-09-28:

        "I can send a one page project summary of what I mean."
            -> matched the licensed name "Project Summary", refused em1
        "rather than four agents chasing four spreadsheets"
            -> matched the licensed name "Agents", refused em5

    Neither names a product. Naming one means writing it as the page writes it,
    which is also what `evidence.productive_ai.naming_rule` requires - "individual
    features are named exactly as the page names them" - so the capitalised form
    is the licensed form and matching it is reading the rule rather than
    approximating it.

    THE COST IS NAMED: a model that writes "report intelligence" in lower case
    evades this. That is deliberate - a lower-case mention is not naming the
    product - and it is the direction that refuses good copy less often.
    """
    text = str(text or "")
    found = []
    for name in ai_names:
        if re.search(r"\b%s\b" % re.escape(str(name)), text):
            found.append(name)
    return sorted(found)


def _content_words(text):
    # THREE CHARACTERS, NOT FOUR. At `{3,}` the pattern required four letters
    # and silently dropped every industry term this client's market runs on:
    # `_content_words("CRM PPC SEO ads")` returned the empty set, so two
    # messages differing only in which of those they named scored zero
    # overlap. Found by GLM, 2026-09-26.
    words = re.findall(r"[a-z][a-z'-]{2,}", str(text or "").lower())
    return {w for w in words if w not in STOPWORDS}


#: Qualification values that must never produce a sequence, matched by PREFIX.
#:
#: This was exact tuple membership against ("UNQUALIFIED", "INSUFFICIENT"),
#: and this codebase's own sentinel is `INSUFFICIENT_DATA`, which is not equal
#: to `INSUFFICIENT`. So the one value most likely to arrive here sailed
#: through the check written to stop it. Found by GLM, 2026-09-26.
#: The last five are the vocabulary of `qualify.state_of`, the canonical
#: resolver for a company's own ICP state, and they are here because
#: `bisonfactory` now hands this check that resolver's answer. Without them the
#: staging path would have handed over a real qualification that this function
#: was incapable of refusing: `rejected` and `review_required` and the word for
#: a company nobody ever qualified would all have read as acceptable, and the
#: `qualified` check would have been able to refuse nothing but a None. That is
#: the same defect this tuple was already corrected for once - a check written
#: to stop a value that does not match the value that actually arrives.
#:
#: `REVIEW` covers `review_required`; `NOT_PROCESSED` and `CLASSIFIED` are the
#: resolver's words for "never qualified" and "scored, no verdict reached".
#: `qualified` and `dm_enrichment_approved` are the only two it returns that
#: mean a sequence may exist.
#: `OPERATOR_EXCLUDED` is `qualify.state_of`'s word for a permanent operator
#: exclusion, added with the state itself. It is here because this tuple is
#: the reason the staging path refuses anything at all: `bisonfactory` hands
#: `qualify.state_of`'s answer to `check()`, so a state the resolver can
#: return and this tuple does not name reads as acceptable. That is the exact
#: defect this tuple has already been corrected for twice.
BLOCKING_QUALIFICATIONS = ("UNQUALIFIED", "INSUFFICIENT", "DISQUALIFIED",
                           "HELD", "NOT_QUALIFIED",
                           "REJECTED", "REVIEW", "NOT_PROCESSED",
                           "CLASSIFIED", "OPERATOR_EXCLUDED")


def _is_blocking(qualification):
    q = str(qualification or "").strip().upper().replace("-", "_")
    return any(q.startswith(b) for b in BLOCKING_QUALIFICATIONS)


def overlap(a, b):
    """How much of the SHORTER message's argument the longer one repeats."""
    wa, wb = _content_words(a), _content_words(b)
    if not wa or not wb:
        return 0.0
    return len(wa & wb) / float(min(len(wa), len(wb)))


#: HOW LONG A WORD HAS TO BE BEFORE ITS INFLECTION IS IGNORED.
#:
#: `_stem` below truncates a content word to its first four characters so that
#: an objective and the copy pursuing it are not missed for a suffix:
#: `resourcing` against `resource`, `visibility` against `visible`, `margins`
#: against `margin`. A word of four characters or fewer is compared whole,
#: because truncating `time` or `burn` any further stops distinguishing them
#: from each other.
#:
#: WHY THIS IS A STEM AND NOT A REAL MORPHOLOGY. It is deterministic, it needs
#: no dictionary, and it errs toward matching, which is the right direction for
#: the `step_objectives` check specifically: the failure that check exists to
#: catch is a step pursuing ANOTHER rung's objective, and that comparison is
#: made between two scores computed the same way, so a stem that merges two
#: inflections cannot invent an out-of-order ladder. What it can do is stop the
#: check refusing a step that is plainly on its rung in a different tense.
#:
#: IT IS ALSO WHERE THIS CHECK IS BLUNTEST, and that is reported: four
#: characters merge `resource` with `resourcing` and also with `resourceful`,
#: and the warning on every run says the matching is lexical.
#:
#: CALIBRATED ONCE, BEFORE ANY VERDICT WAS TAKEN. The exact-token form of this
#: check was measured against the first real generated sequence on 2026-09-28
#: and refused `em3` for `resource allocation` against a rung reading
#: `resourcing`, which is the same subject in a different form. The negative
#: test is what keeps the calibration honest: with the stem in place, a sequence
#: whose `em1` and `em3` are SWAPPED must still be refused by name, and it is.
_STEM_FLOOR = 4


def _stem(word):
    word = str(word or "")
    return word[:_STEM_FLOOR] if len(word) > _STEM_FLOOR else word


def _stems(text):
    return {_stem(w) for w in _content_words(text)}


def objective_overlap(body, objective):
    """How much of an objective's vocabulary this message carries, stemmed.

    Separate from `overlap` deliberately. `overlap` measures repetition between
    two MESSAGES, where an exact word is the right unit because the failure is
    two steps saying the same thing; this measures a message against a two or
    three word OBJECTIVE, where a single suffix decides the whole verdict.
    """
    wanted = _stems(objective)
    if not wanted:
        return 0.0
    return len(wanted & _stems(body)) / float(len(wanted))


def _questions(text):
    return [s.strip() for s in re.split(r"(?<=[?])\s+", str(text or ""))
            if s.strip().endswith("?")]


def check(sequence, facts=None, capability=None, qualification=None,
          batch_capabilities=None, repeat_threshold=0.45, offer=None,
          messaging_rules=None, threads=None):
    """Every sequence-level failure, each naming the step responsible.

    `sequence` is `{"emails": {...}, "linkedin": {...}, "subjects": {...},
    "hypothesis": str, "ps": {...}}`. Returns
    `{"passed", "failures", "warnings", "checks"}` where a failure is
    `{"check", "step", "why"}` - the step is the point of the whole module.

    `offer` is the offer record this sequence is selling, as
    `src/offers.py` loads it. Two of its fields are read and neither is
    invented here: `step_objectives`, the rung-by-rung spine the operator
    approved, and `ai_capabilities`, the AI features licensed for that offer.
    `messaging_rules` is the library's own `messaging_rules` block.

    BOTH DEFAULT TO None AND ABSENCE IS REPORTED, NEVER PASSED. `TASK-425`
    acceptance criterion 3 asks for offer sequencing "enforced by
    `sequencegate`"; a caller that hands over no offer has not had its
    sequencing checked, and saying so is the difference between "the ladder
    holds" and "nobody looked". The same convention `batch_capabilities`
    already follows below.
    """
    emails = {k: v for k, v in (sequence.get("emails") or {}).items() if v}
    linkedin = {k: v for k, v in (sequence.get("linkedin") or {}).items() if v}
    ps = {k: v for k, v in (sequence.get("ps") or {}).items() if v}
    subjects = sequence.get("subjects") or {}
    hypothesis = sequence.get("hypothesis") or ""
    facts = facts or []
    failures, warnings = [], []

    def fail(check_name, step, why):
        failures.append({"check": check_name, "step": step, "why": why})

    def warn(check_name, step, why):
        warnings.append({"check": check_name, "step": step, "why": why})

    # 0. THERE IS SOMETHING TO CHECK -------------------------------------
    #
    # `check({})` RETURNED passed=True. A gate that approves an empty
    # sequence approves anything a caller fails to pass it, and the most
    # likely way to pass it nothing is a key mismatch upstream - which this
    # module already has form for. Found by GLM, 2026-09-26.
    #
    # Emptiness is a REFUSAL, not a pass. A caller with nothing to gate has
    # a bug, and it should hear about it here rather than downstream.
    if not emails:
        fail("has_content", "sequence",
             "no email steps to check: an empty sequence is refused, never "
             "passed. If the caller has a sequence, the keys do not match")
    if qualification is None:
        fail("qualified", "lead",
             "no qualification supplied: absence is refused rather than read "
             "as qualified")

    # 1. QUALIFIED -------------------------------------------------------
    elif _is_blocking(qualification):
        fail("qualified", "lead",
             "qualification is %s: this sequence should not exist"
             % qualification)

    # 2 + 9. EVERY CLAIM TRACEABLE ---------------------------------------
    # Reuses copylint's own untraceable-claim machinery rather than a second
    # opinion about what a claim is: two definitions of "specific" would
    # drift, and this one has been wrong in production and corrected.
    # AND THE OFFER'S OWN LICENSED CAPABILITY NAMES, for the reason the batch
    # lint is given them: `copylint` reads a capitalised multi-word name as an
    # invention, which is right for a prospect's customer and wrong for
    # "Report Intelligence" - an operator-approved capability with its own
    # licensed page text that will never appear in the PROSPECT's pack.
    #
    # Offer A's rung 4 is "Report Intelligence as mechanism", so this check
    # refused the one step the ladder requires naming it at. MEASURED
    # 2026-09-30, after the same fix had been applied to the batch path:
    # `em4 (claims_supported)` failed on TEN of ten attempts and was the
    # contact's last remaining blocker.
    #
    # `offer.get("ai_capabilities")` is read here exactly as `ai_names` reads
    # it below, from the offer this sequence is being written against, so a
    # client's names never reach another client's copy.
    pack = {"facts": [{"snippet": f.get("quote") or f.get("text")}
                      for f in facts],
            "licensed_names": tuple(
                str(n) for n in (((offer or {}).get("ai_capabilities")) or {}))}
    for step, body in sorted(emails.items()):
        if copylint.untraceable(body, pack):
            fail("claims_supported", step,
                 "a specific claim in this step traces to no supplied fact")

    # 3. THE HYPOTHESIS IS NOT A FINDING ---------------------------------
    for step, body in sorted(list(emails.items()) + list(linkedin.items())):
        for pattern in AS_FACT_RES:
            m = pattern.search(body)
            if m:
                fail("hypothesis_not_asserted", step,
                     "states an inferred problem as fact: %r" % m.group(0))
                break
    if hypothesis and not any(h in hypothesis.lower() for h in HEDGES):
        warn("hypothesis_not_asserted", "hypothesis",
             "the hypothesis carries no hedge, so copy built from it is "
             "likely to read as a finding")

    # 4. THE CAPABILITY IS NAMED -----------------------------------------
    if capability:
        body_all = " ".join(emails.values()).lower()
        key_words = _content_words(capability)
        if key_words and not (key_words & _content_words(body_all)):
            warn("capability_matches", "em1",
                 "the chosen capability (%s) appears nowhere in the emails"
                 % capability)

    # 5. EMAIL 1 SAYS WHY WE ARE WRITING ---------------------------------
    em1 = emails.get("em1", "")
    if em1:
        words = len(em1.split())
        if words > 130:
            fail("em1_concise", "em1",
                 "%d words: email 1 is the one that must be read in seconds"
                 % words)
        elif words > 95 or words < 45:
            warn("em1_concise", "em1", "%d words, target 60 to 90" % words)
        if facts and not (_content_words(em1) &
                          _content_words(" ".join(str(f.get("text") or "")
                                                  for f in facts))):
            fail("reason_for_outreach", "em1",
                 "shares no content word with any researched fact, so it "
                 "states no reason for writing to this company specifically")

    # 6. EACH FOLLOW-UP ADDS SOMETHING -----------------------------------
    #
    # THIS CHECK CANNOT SEE A PARAPHRASE, AND THAT IS THE FAILURE IT EXISTS
    # FOR. Measured 2026-09-26:
    #
    #   "Your margins are thin on fixed scope work and nobody sees it
    #    until later."
    #   "Profit on flat fee projects gets squeezed, invisible until
    #    afterwards."
    #
    # One argument, two wordings, overlap 0.125 against a 0.45 threshold.
    # The 2026-09-25 incident was five emails making one argument in five
    # phrasings; if those phrasings differ lexically this check is blind to
    # exactly the thing it was written to catch. The test that passed it was
    # mine and used a VERBATIM copy, which lexical overlap catches trivially
    # - a test built to pass rather than to probe.
    #
    # Lexical overlap stays because it is deterministic, free, and catches
    # near-duplicates that a model might rationalise. What changes is that
    # its blind spot is now REPORTED rather than silent: a caller is told
    # that semantic repetition was not checked, so nobody reads a pass as
    # "these five messages make five arguments". The semantic check is a
    # cheap-model call and belongs to phase 2 of the upgrade spec.
    order = [k for k in ("em1", "em2", "em3", "em4", "em5") if k in emails]
    for i, step in enumerate(order):
        for earlier in order[:i]:
            score = overlap(emails[step], emails[earlier])
            if score >= repeat_threshold:
                fail("followup_adds_value", step,
                     "repeats %s: %.0f%% of its argument is the same"
                     % (earlier, 100 * score))
                break
    if len(order) > 1:
        warn("followup_adds_value", "sequence",
             "lexical overlap only: two steps arguing the same thing in "
             "different words pass this check. Semantic repetition is NOT "
             "verified here")

    # 7. LINKEDIN COMPLEMENTS, NOT DUPLICATES ----------------------------
    email_questions = [q.lower() for b in emails.values() for q in _questions(b)]
    for step, body in sorted(linkedin.items()):
        for q in _questions(body):
            for eq in email_questions:
                if overlap(q, eq) >= 0.6:
                    fail("channels_complement", step,
                         "asks a question email already asked: %r" % q[:70])
                    break
        for estep, ebody in emails.items():
            if overlap(body, ebody) >= 0.55:
                fail("channels_complement", step,
                     "is %s in shorter form" % estep)
                break

    # 8 + 10. NO UNNECESSARY REPETITION ----------------------------------
    # ONE SUBJECT PER THREAD, WHEN THE CALLER KNOWS THE THREADS.
    #
    # This check's own message says "two of the THREE THREAD subjects are the
    # same". It was written for the writer's `{A, B, C}` - one entry per thread -
    # and it compares whatever mapping it is handed. A caller that hands it one
    # entry per STEP is asking a different question, because
    # `EMAILBISON-COPY-REQUIREMENTS.md` requires that "a sequence is one
    # conversation, same-thread follow-ups use the provider's thread_reply rather
    # than a new subject every step": em2 legitimately carries em1's subject, and
    # five steps in three threads look to this check like three duplicates.
    # Measured 2026-09-28 on `bisonfactory`'s staging path: it REFUSED copy that
    # had passed every other gate, and 256 of 1,323 stored contacts are refused
    # by this check and by nothing else.
    #
    # `threads` maps step key -> thread key. Given it, one subject per thread is
    # compared and the check asks what it was written to ask. WITHOUT it the
    # behaviour is EXACTLY what it always was, so no existing caller changes.
    #
    # AND WHEN THERE IS NOTHING TO COMPARE IT SAYS SO. Every cadence configured
    # in this repository declares `thread_reply_pattern` with exactly ONE thread
    # starter, so per-thread comparison has one subject and CANNOT FIRE. A check
    # that cannot fire is not a check, and the difference between "the subjects
    # are fine" and "there was only one subject to look at" has to survive onto
    # the report - otherwise moving this check to per-thread would quietly retire
    # it, which was the first version of this change and was wrong.
    if threads:
        per_thread = {}
        for step, subject in (subjects or {}).items():
            if not subject:
                continue
            per_thread.setdefault(threads.get(step, step), subject)
        subs = list(per_thread.values())
        if len(subs) < 2:
            warn("no_repetition", "subjects",
                 "this cadence opens %d thread(s), so there are %d thread "
                 "subject(s) to compare and duplicate thread subjects could NOT "
                 "be checked" % (len(per_thread), len(subs)))
    else:
        subs = [s for s in (subjects or {}).values() if s]
    if len(subs) != len({str(s).strip().lower() for s in subs}):
        fail("no_repetition", "subjects",
             "two of the %d thread subjects are the same" % len(subs))
    if len(ps) == 2 and overlap(*ps.values()) >= 0.5:
        fail("no_repetition", "ps", "both P.S. lines make the same point")
    # The company's name in every paragraph is the tell of a merge, not of
    # personalisation.
    company = sequence.get("company")
    if company and em1:
        n = em1.lower().count(str(company).lower())
        if n > 2:
            warn("no_repetition", "em1",
                 "names the company %d times in one short email" % n)

    # 11. THE OFFER'S SPINE, AS STEP OBJECTIVES --------------------------
    #
    # `TASK-425` acceptance criterion 3, and the wiring `messaging_rules` in
    # `config/clients/productive-offers.yaml` has been waiting for: that block
    # recorded `enforced_by: sequencegate checks step_objectives` beside
    # `enforcement_status: DATA_ONLY_NOT_YET_ENFORCED`, which is this
    # repository's signature defect written down in its own config - a rule
    # computed, recorded, and read by nothing.
    #
    # WHAT THE LADDER IS. The offer stays fixed and the reason to read evolves
    # per step. For Offer A: margin visibility, quote versus burn, resource
    # decisions that move margin, Report Intelligence as mechanism, reframe and
    # close. For Offer B: project visibility, time, resourcing, AI Time
    # Tracking as mechanism, one operational view. Those are the operator's
    # words, they live in the offer record, and this function reads them rather
    # than restating them - a second copy here is a second thing to drift.
    #
    # WHAT IS MEASURED, AND ITS BLIND SPOT NAMED UP FRONT. Each message is
    # scored against EVERY rung by `overlap`, which is lexical. Two failures
    # are refused:
    #
    #   - a step that pursues NO rung of the ladder at all;
    #   - a step that pursues a DIFFERENT rung more closely than its own,
    #     which is what a ladder in the wrong order looks like.
    #
    # The second is the one that makes this a gate rather than a presence
    # check: swap em1 and em3 and both steps are refused by name. The first
    # alone would pass a sequence that climbed the ladder backwards, because
    # every step would still be on it somewhere.
    #
    # THE BLIND SPOT IS THE SAME ONE `followup_adds_value` HAS, and it is
    # warned about for the same reason: a step can carry its rung's vocabulary
    # while arguing something else, and this check cannot see that. A pass here
    # is not "these five steps make the offer's argument in the offer's order";
    # it is "no step is lexically closer to another step's objective than to
    # its own". Semantic objective-following is NOT verified.
    objectives = {str(k): str(v) for k, v in
                  (((offer or {}).get("step_objectives")) or {}).items()}
    ai_names = [str(n) for n in (((offer or {}).get("ai_capabilities")) or {})]
    rules = messaging_rules or {}
    try:
        max_ai = int(rules.get("max_ai_capabilities_per_message",
                               DEFAULT_MAX_AI_PER_MESSAGE))
    except (TypeError, ValueError):
        max_ai = DEFAULT_MAX_AI_PER_MESSAGE

    # EVERY PROSPECT-FACING MESSAGE, BOTH CHANNELS. The AI rules are about what
    # a person reads, and a LinkedIn message is read by the same person.
    messages = sorted(list(emails.items()) + list(linkedin.items()))

    # AT MOST ONE AI CAPABILITY PER MESSAGE. Operator, 2026-09-27.
    #
    # Counted from the offer's own licensed names, so a message naming two of
    # them is refused and a message naming none is not - `ai_required: false`
    # is in the same block and "no AI capability is forced" is part of the
    # acceptance. A message with none passes this and every check below it.
    if ai_names:
        for step, body in messages:
            named = _ai_named_in(body, ai_names)
            if len(named) > max_ai:
                fail("ai_one_per_message", step,
                     "names %d AI capabilities (%s) and at most %d is licensed "
                     "per prospect-facing message"
                     % (len(named), ", ".join(named), max_ai))

    if not objectives:
        warn("step_objectives", "sequence",
             "no offer step objectives supplied: whether this sequence follows "
             "the offer's spine was NOT checked. Absence is reported rather "
             "than read as a pass")
    else:
        # WHICH STEP SITS ON WHICH RUNG, so the ORDER can be checked ACROSS
        # steps after the loop rather than inside one step.
        on_rung = {}
        # The offer's own list of rungs that are thread replies. Absent means
        # every rung is a distinct argument, which is the old behaviour.
        reply_rungs = {str(r) for r in
                       (((offer or {}).get("thread_reply_rungs")) or ())}
        for step, body in messages:
            rung = _rung_of(step)
            if rung is None:
                warn("step_objectives", step,
                     "step key %r carries no ladder rung, so its objective was "
                     "NOT checked" % step)
                continue
            mine = objectives.get(rung)
            if mine is None:
                warn("step_objectives", step,
                     "the offer declares no objective for rung %s, so this "
                     "step's objective was NOT checked" % rung)
                continue
            # THE LADDER IS THE EMAIL SPINE, AND `on_rung` MUST NOT COLLAPSE
            # TWO CHANNELS ONTO ONE RUNG.
            #
            # `_rung_of` reads the digit, so `em3` and `li3` are both rung 3.
            # This dict is keyed by the rung alone, and `messages` is sorted,
            # so `li3` OVERWROTE `em3` for every rung whenever LinkedIn was
            # supplied - and the order check below then examined the LinkedIn
            # sequence while reporting on the offer's email spine. The emails
            # were never looked at.
            #
            # MEASURED 2026-09-30: a PERFECT email ladder plus five unrelated
            # LinkedIn messages produces four `step_objectives` failures, all
            # attributed to `li1`..`li5`, and not one mention of the emails.
            # `bisonfactory` passes no `linkedin` key, so staging enforced the
            # email ladder and generation silently did not - the same gate
            # answering two different questions depending on its caller.
            #
            # AND THE RULE WAS UNSATISFIABLE ON LINKEDIN ANYWAY: coverage
            # demands `li3` carry rung 3's vocabulary while
            # `channels_complement` refuses `li3` for being "em3 in shorter
            # form". Both fired five times in the same run. A step cannot
            # carry a rung's words and also not resemble the email carrying
            # the same rung's words.
            #
            # So the ladder is checked on the channel the offer declares it
            # for - `step_objectives` is keyed 1..5 and the writer prompt says
            # "keyed 1 to 5 for em1 to em5" - and LinkedIn is REPORTED as
            # unchecked rather than silently passed, which is this module's
            # convention everywhere else. The AI rules below still cover both
            # channels, because those are about what a person reads.
            # A THREAD REPLY CARRIES NO RUNG OF ITS OWN.
            #
            # Operator decision, Zvonimir, 2026-09-30: "em2 and em4 are
            # replies inside threads A and B. They are short follow-ups that
            # build on em1 and em3 and do NOT need their own new rung.
            # Distinct rungs are required only for em1, em3 and em5."
            #
            # Read from the OFFER's own `thread_reply_rungs`, not spelled
            # here, so a different offer with a different shape is not
            # forced into Offer A's. The objectives for those rungs are NOT
            # deleted and the writer still reads them as the reason a
            # follow-up exists; what stops is the demand that the step carry
            # that vocabulary and take part in the ladder ORDER comparison.
            #
            # `followup_adds_value` is what governs them instead, and it
            # REFUSES a step repeating an earlier one - so "must still add
            # something" is enforced, not assumed.
            if rung in reply_rungs:
                warn("step_objectives", step,
                     "rung %s is a THREAD REPLY (operator, 2026-09-30): it "
                     "builds on the previous email and is not required to "
                     "carry its own rung. `followup_adds_value` refuses it "
                     "if it repeats one" % rung)
            elif not str(step).lower().startswith("em"):
                warn("step_objectives", step,
                     "the offer's ladder is the EMAIL spine (rungs 1..5 are "
                     "em1..em5), so this LinkedIn step was NOT checked "
                     "against rung %s. `channels_complement` is what governs "
                     "its relationship to the emails" % rung)
            else:
                on_rung[rung] = (step, body)
            # A MECHANISM RUNG IS CONDITIONAL, BY THE OFFER'S OWN WORDS.
            #
            # Rung 4 is "Report Intelligence as mechanism, only if it
            # strengthens the angle". The operator's rule is that no AI
            # capability is ever forced, so a rung whose objective NAMES one of
            # the offer's licensed AI capabilities may legitimately go unnamed
            # in the copy - and a check that demanded it would be the
            # "AI feature first" direction the same block forbids, enforced by
            # us. It is recognised STRUCTURALLY, by the objective naming one of
            # this offer's own `ai_capabilities` keys, not by matching the
            # phrase "only if" in a config string.
            mechanism = _ai_named_in(mine, ai_names)
            if mechanism:
                # WARNED, NEVER REFUSED FOR ABSENCE. Saying "this rung was not
                # enforced" is the difference between a conditional rule and an
                # unchecked one.
                warn("step_objectives", step,
                     "rung %s's objective is CONDITIONAL (%r names an AI "
                     "capability and no AI capability is ever forced), so this "
                     "step's coverage of it was NOT enforced" % (rung, mine))
            elif (str(step).lower().startswith("em")
                  and rung not in reply_rungs
                  and not objective_overlap(body, mine)):
                # COVERAGE, against the rung's WHOLE vocabulary, and the easy
                # half: a step that says nothing at all about its own objective
                # is refused outright.
                fail("step_objectives", step,
                     "pursues none of the offer's step objectives: rung %s is "
                     "%r and this step shares no word with it" % (rung, mine))
            # AI IS A SUPPORTING ANGLE, NEVER THE OFFER AND NEVER THE PROBLEM.
            #
            # The forbidden direction the offer library names is "ai feature
            # first, then invent a problem around it". Structurally that is an
            # AI capability appearing at a rung the operator did not make a
            # mechanism rung: rung 1 states the problem and rung 4 carries the
            # mechanism, so an AI feature in rung 1 IS leading with the feature.
            named = _ai_named_in(body, ai_names)
            if named and not mechanism:
                fail("ai_is_supporting", step,
                     "names the AI capability %s, but rung %s's objective is "
                     "%r and names no AI capability. AI is a supporting angle "
                     "at the mechanism step, never the problem or the offer"
                     % (", ".join(named), rung, mine))

        # ORDER, against each rung's DISTINCTIVE vocabulary, ACROSS STEPS.
        #
        # THIS IS THE HALF THAT MAKES IT A GATE, and its shape was measured
        # rather than chosen. The first version compared rungs WITHIN one step -
        # "does this step resemble another rung more than its own" - and that
        # cannot work for a ladder whose first rung states the offer's theme:
        # rung 1 of Offer A is "margin visibility", every step of a margin
        # campaign legitimately touches it, and a perfectly good close at rung 5
        # was refused for resembling rung 1. Measured 2026-09-28 against real
        # generated copy, three regeneration attempts in a row.
        #
        # Asked the other way round it is robust to that AND a stronger
        # statement: FOR EACH RUNG, WHICH STEP PURSUES IT BEST? If the best step
        # for rung N is not step N, the ladder is out of order, however much of
        # the theme the other steps carry. A TIE GOES TO THE RUNG'S OWN STEP,
        # because a tie is not evidence of a shuffle.
        #
        # DISTINCTIVE vocabulary, because a rung can only be told apart from
        # another rung by what differs between them. "margin" is in rung 1 and
        # rung 3 of Offer A and identifies neither; "visibility", "resource",
        # "decisions" and "move" do. A rung with nothing of its own is reported
        # as indistinguishable rather than decided by a coin toss.
        # A RUNG WITH NO STEP IS REPORTED, NOT SKIPPED.
        #
        # `emails` drops empty bodies before any of this runs, so a step that
        # rendered to nothing removes its rung from BOTH halves of the check and
        # the sequence passes with that objective never examined. Found by an
        # adversarial review and reproduced: `em3 = ""` gave `passed: True`, no
        # `step_objectives` failure, and not one word about rung 3.
        #
        # `_ensure_leads` refuses that lead for missing copy one gate later, so
        # nothing ships - but a gate that cannot tell "checked and fine" from
        # "there was nothing there" is the shape this whole module exists to
        # avoid, and it must not be the sequence gate that is silent about it.
        for rung in sorted(objectives):
            if rung not in on_rung:
                warn("step_objectives", "em%s" % rung,
                     "no step carries rung %s, whose objective is %r, so that "
                     "objective was NOT checked. A step that rendered to nothing "
                     "is dropped before this check sees it"
                     % (rung, objectives[rung]))

        appearances = {}
        for text in objectives.values():
            for word in _stems(text):
                appearances[word] = appearances.get(word, 0) + 1
        for rung, text in sorted(objectives.items()):
            own = on_rung.get(rung)
            if own is None:
                continue
            # A CONDITIONAL RUNG IS OUT OF THE ORDER TEST TOO, not just out of
            # the coverage one. If the rung need not be pursued at all, another
            # step carrying a word from it proves nothing about the order -
            # measured 2026-09-28, `em3` said "report" and rung 4 reads "Report
            # Intelligence as mechanism, only if it strengthens the angle", so
            # one generic word in the wrong step refused a sequence whose ladder
            # was in order and whose mechanism step was legitimately silent
            # about the mechanism. Enforcing the order of an optional rung is
            # requiring the AI capability by the back door.
            if _ai_named_in(text, ai_names):
                continue
            distinctive = {w for w in _stems(text)
                           if appearances.get(w) == 1}
            if not distinctive:
                warn("step_objectives", own[0],
                     "rung %s (%r) shares every word with another rung, so "
                     "which step pursues it could NOT be told apart"
                     % (rung, text))
                continue
            scored = {}
            for other_rung, (_step, other_body) in on_rung.items():
                covered = distinctive & _stems(other_body)
                scored[other_rung] = len(covered) / float(len(distinctive))
            best = max(sorted(scored), key=lambda r: (scored[r], r == rung))
            # THE THRESHOLD IS ABSENCE, NOT A MARGIN, and that was measured too.
            #
            # "another step covers this rung better than its own step does"
            # refuses on a one-word difference: measured 2026-09-28, em4 covered
            # 3 of rung 3's three distinctive words and em3 covered 2, and the
            # gate refused a sequence whose ladder was in order. A 33 point gap
            # on a three word vocabulary is not evidence of a shuffle.
            #
            # A SHUFFLE LOOKS LIKE 100 AGAINST 0, and that is what is refused:
            # the rung's vocabulary is at another step and ABSENT from its own.
            # Verified against the negative test in both directions - em1/em3
            # swapped and em2/em5 swapped each still raise two failures by name,
            # so the narrower threshold did not hollow the check out. What it
            # stops doing is refusing copy that is on its rung and merely less
            # word-dense than a neighbour.
            if best != rung and scored[best] > 0 and not scored[rung]:
                fail("step_objectives", on_rung[best][0],
                     "carries rung %s's own vocabulary (%r) while rung %s's own "
                     "step %s carries NONE of it, %.0f%% against 0%%, so the "
                     "offer's ladder is out of order"
                     % (rung, text, rung, own[0], 100 * scored[best]))

        warn("step_objectives", "sequence",
             "lexical overlap only: a step carrying its rung's vocabulary "
             "while arguing something else passes this check. Semantic "
             "objective-following is NOT verified here")

    # A BATCH-LEVEL CHECK, AND THE MOST IMPORTANT ONE -------------------
    # Stage D exists because `profitability` was the answer for every lead.
    # One sequence cannot show that; a batch can.
    if batch_capabilities:
        # CASE-FOLDED. One lead tagged "Profitability" among nineteen
        # "profitability" made distinct == 2 and the check passed while stage
        # D was plainly defaulting. Found by GLM, 2026-09-26.
        distinct = {str(c).strip().lower() for c in batch_capabilities if c}
        if len(batch_capabilities) >= 5 and len(distinct) == 1:
            fail("capability_matches", "batch",
                 "every lead in this batch was matched to %r: stage D is not "
                 "choosing, it is defaulting" % distinct.pop())

    # AN ABSENT BATCH CHECK IS REPORTED, NOT SILENT. `batch_capabilities`
    # defaults to None, which disables the check the module's own comment
    # calls the most important one - and a per-lead caller cannot supply it
    # at all. Saying so is the difference between "stage D is choosing" and
    # "nobody looked".
    if batch_capabilities is None:
        warn("capability_matches", "batch",
             "batch_capabilities not supplied: whether stage D is choosing "
             "or defaulting was NOT checked")

    return {"passed": not failures,
            "failures": failures,
            "warnings": warnings,
            "checks": ["qualified", "claims_supported",
                       "hypothesis_not_asserted", "capability_matches",
                       "em1_concise", "reason_for_outreach",
                       "followup_adds_value", "channels_complement",
                       "no_repetition", "step_objectives",
                       "ai_one_per_message", "ai_is_supporting"]}


def check_cta(composed, offer, threads=None):
    """Refuse a sequence whose COMPOSED output carries no CTA link.

    WHY THIS IS A SEPARATE ENTRY POINT FROM `check`. Every other check in this
    module reads the writer's raw step bodies, which is the right input for
    "does this message argue its rung". The CTA link is not written by the
    writer at all - `copyprompts` forbids it a URL - it is appended by
    `trailingcontent.compose`. So the only text that can answer "will the
    prospect see the link" is the COMPOSED body, and a gate that re-composed
    the raw bodies itself would be checking its own arithmetic: it would pass
    for exactly as long as it agreed with itself, including on the day the
    staging path stopped passing `cta_link` through. The caller hands over the
    output it is about to ship, and this reads that.

    Measured 2026-09-30: `offer.cta_link` was declared in the offer library and
    read by nothing that composes an email. `copylint.check_cta_links([])`
    returns a clean verdict for an empty URL list, so five canary emails with
    no URL at all passed every CTA rule in the repository.

    `composed` maps step key -> the final body string. `offer` is the offer
    record as `src/offers.py` loads it. `threads` maps step key -> the key of
    the step that OPENED its thread, exactly as `check` takes it.

    IT FAILS CLOSED, IN BOTH DIRECTIONS THAT MATTER.

      - An offer that declares a `cta_link` and a caller that supplies NO
        composed output is REFUSED. "Nobody looked" is not "the link is
        there", and this is the one check where the absent input is also the
        commonest way to ship the defect: the staging path could stop
        composing and the gate would go quiet.
      - A composed step that should carry the link and does not is REFUSED by
        name, so the operator knows which step is wrong.

    WHICH STEPS MUST CARRY IT. Every step that OPENS a thread, and no thread
    reply. A reply already carrying a signature and a compliance footer reads
    as bulk mail the moment a link is added under it, and the offer library
    records which rungs are replies (`thread_reply_rungs: [2, 4]` for Offer A,
    operator, 2026-09-30). `threads` is the authority here rather than that
    field, because it comes off `plan["provider_sequence"]` - the projection
    the wire actually sees - and the reader's experience of "a reply" is the
    provider's threading, not the offer's numbering.

    `threads` IS REQUIRED, AND THE FIRST VERSION OF THIS FUNCTION GOT THAT
    WRONG IN A WAY WORTH RECORDING.

    It defaulted with `starter = (threads or {}).get(step, step) == step`, and
    documented that as "without `threads` every step is a starter, which is
    the strict reading". It is strict for the PRESENCE half - every step must
    then carry the link - and LAX for the PROHIBITION half, because
    `not starter` can never be true, so the reply rule cannot fire at all.
    MEASURED 2026-09-30 by an adversarial review and reproduced:

        composed = {"em1": starter_with_link, "em2": reply_with_link}
        check_cta(composed, offer, threads={"em1": "em1", "em2": "em1"})
            -> passed=False, em2 refused              correct
        check_cta(composed, offer)                    -> passed=True  THE HOLE
        check_cta(composed, offer, threads={"em1": "em1"})
            -> passed=True                            the same hole per step

    The two halves of one guard disagreed about what the default meant, which
    is the shape this repository keeps rediscovering. It was latent rather than
    live - `bisonfactory._refuse_missing_cta` does pass `threads=_thread_map(plan)`
    - but a guard whose safety depends on a caller remembering an optional
    argument is a guard that will be bypassed by the next caller.

    SO ABSENCE IS REFUSED, AND SO IS AN UNCLASSIFIABLE STEP. Without the
    thread map neither half of the rule is knowable: a sequence of N steps has
    between 1 and N threads, so "this step opens a thread" and "this step is a
    reply" are both unanswerable, and the only facts left - at least one step
    carries the link, no step carries it twice - are a strict SUBSET of the
    rule. Enforcing a subset silently is a check that did not run looking
    exactly like a check that passed.

    WHY REFUSE RATHER THAN NARROW. The alternative considered was "an absent
    map means only the first step may carry the link". That contradicts the
    presence half, which requires EVERY starter to carry it: a correctly
    composed five-step, three-thread sequence would then be unsatisfiable, and
    a gate no correct input can pass is as useless as one no incorrect input
    fails. Refusing on the missing INPUT keeps one rule with one meaning and
    names the fix - pass the map. `check` already refuses an absent
    `qualification` on the same grounds ("absence is refused rather than read
    as qualified"), so this is the module's own convention rather than a new
    one, and `bisonfactory._thread_map` produces the map for a sequence of any
    length including one.

    Returns `{"passed", "failures", "checks"}` in `check`'s own shape, so
    `report_lines` reads it unchanged.
    """
    failures = []

    def fail(step, why):
        failures.append({"check": "cta_present", "step": step, "why": why})

    link = str(((offer or {}).get("cta_link") or "")).strip()
    if not link:
        # NOT A FAILURE AND NOT A SILENT PASS. An offer declaring no CTA link
        # has nothing for this to enforce - every capability offer in the
        # current library is in that state - and inventing a link here is the
        # one thing this module must never do.
        return {"passed": True, "failures": [], "checks": ["cta_present"],
                "cta_link": None}

    if not composed:
        fail("sequence",
             "the offer declares cta_link %r but no composed output was "
             "supplied, so whether the prospect ever sees the link could NOT "
             "be checked. Absence is refused, never read as present: the "
             "commonest way to ship this defect is for the composing path to "
             "stop passing the link through, and a gate that goes quiet then "
             "is not a gate" % link)
        return {"passed": False, "failures": failures,
                "checks": ["cta_present"], "cta_link": link}

    if not threads:
        fail("sequence",
             "the offer declares cta_link %r but no thread map was supplied, "
             "so which steps OPEN a thread and which REPLY inside one could "
             "NOT be told - and both halves of this rule need that. Absence "
             "is refused rather than defaulted to 'every step is a starter', "
             "which silently retired the reply prohibition (measured "
             "2026-09-30). Pass `threads=bisonfactory._thread_map(plan)`, "
             "which answers for a sequence of any length including one"
             % link)
        return {"passed": False, "failures": failures,
                "checks": ["cta_present"], "cta_link": link}

    for step in sorted(composed):
        text = str(composed.get(step) or "")
        count = text.count(link)
        if step not in threads:
            # THE SAME HOLE, ONE LEVEL DOWN. `threads.get(step, step) == step`
            # read an unmapped step as a starter, so a reply the map happened
            # not to name was exempt from the prohibition while still being
            # required to carry the link. A step this cannot classify is
            # refused, never assumed.
            fail(step,
                 "is not in the thread map (%s), so whether it opens a thread "
                 "or replies inside one could NOT be told. An unclassifiable "
                 "step is refused, never assumed to be a thread starter"
                 # `str` on every key: a map built from a projection can hold
                 # a non-string key, and a DIAGNOSTIC THAT RAISES turns a
                 # clean refusal into a TypeError from inside a gate.
                 % ", ".join(sorted(str(k) for k in threads)))
            continue
        starter = threads[step] == step
        if count > 1:
            fail(step,
                 "carries the CTA link %d times. EXACTLY ONE CTA per email: "
                 "%r" % (count, link))
        elif starter and count == 0:
            fail(step,
                 "opens a thread and carries no CTA link. The offer declares "
                 "%r and `trailingcontent.compose` is the one place it is "
                 "appended, so a step without it was composed without its "
                 "cta_link" % link)
        elif not starter and count:
            fail(step,
                 "is a thread reply and carries the CTA link. A reply already "
                 "carrying a signature and a compliance footer reads as bulk "
                 "mail with a link under it; the ask belongs on the email that "
                 "opens the thread (%s)" % threads[step])
    return {"passed": not failures, "failures": failures,
            "checks": ["cta_present"], "cta_link": link}


def report_lines(result):
    """Human-readable, one line per failure, naming the step."""
    out = []
    if result.get("passed"):
        out.append("sequence gate: PASSED (%d warnings)"
                   % len(result.get("warnings") or []))
    else:
        out.append("sequence gate: FAILED on %d check(s)"
                   % len(result["failures"]))
    for f in result.get("failures") or []:
        out.append("  FAIL  %-26s %-8s %s" % (f["check"], f["step"], f["why"]))
    for w in result.get("warnings") or []:
        out.append("  warn  %-26s %-8s %s" % (w["check"], w["step"], w["why"]))
    return out
