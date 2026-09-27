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
BLOCKING_QUALIFICATIONS = ("UNQUALIFIED", "INSUFFICIENT", "DISQUALIFIED",
                           "HELD", "NOT_QUALIFIED")


def _is_blocking(qualification):
    q = str(qualification or "").strip().upper().replace("-", "_")
    return any(q.startswith(b) for b in BLOCKING_QUALIFICATIONS)


def overlap(a, b):
    """How much of the SHORTER message's argument the longer one repeats."""
    wa, wb = _content_words(a), _content_words(b)
    if not wa or not wb:
        return 0.0
    return len(wa & wb) / float(min(len(wa), len(wb)))


# ---------------------------------------------------------------- offer rules
#
# THE OPERATOR'S MESSAGING RULE, ENFORCED HERE RATHER THAN DESCRIBED.
#
# `config/clients/productive-offers.yaml` carries `messaging_rules` and, per
# offer, `step_objectives` and `ai_capabilities`. Until this block existed
# nothing in `src/` read any of them - `grep -rn step_objectives --include=*.py
# src/` returned nothing - so the rule was data that no gate consumed, which is
# this repository's signature defect.
#
# EVERYTHING BELOW READS THE OFFER RECORD IT IS HANDED. No objective, feature
# name or page sentence is copied into this module: a second copy of the spine
# here would drift from the operator's file, and the file is the one truth.
# `check()` receives the record rather than loading it, because a gate that
# reads config is a gate that cannot be tested on a fixture.

def _normalise_objectives(offer):
    """`{step_key: objective}` from an offer's `step_objectives`.

    TWO SHAPES, because two loaders disagree and neither is wrong. PyYAML gives
    a list of `{step, objective}` dicts; `clients.parse` cannot express a block
    list at all (only `[a, b]`), so the same data arrives from it as a mapping
    of step number to objective. This normalises both and RAISES on anything
    else rather than returning an empty dict, because an unrecognised shape
    silently disabling the check is the failure this whole block exists to stop.
    """
    raw = (offer or {}).get("step_objectives")
    if not raw:
        return {}
    out = {}
    if isinstance(raw, dict):
        for num, objective in raw.items():
            out["em%s" % str(num).strip()] = str(objective)
    elif isinstance(raw, (list, tuple)):
        for entry in raw:
            if not isinstance(entry, dict):
                raise ValueError(
                    "step_objectives entry is %r, expected a mapping with "
                    "'step' and 'objective'" % (entry,))
            out["em%s" % str(entry.get("step")).strip()] = \
                str(entry.get("objective") or "")
    else:
        raise ValueError(
            "step_objectives is %s, expected a list or a mapping"
            % type(raw).__name__)
    return {k: v for k, v in out.items() if v}


def _normalise_ai_capabilities(offer):
    """`{feature: page_text or None}` from an offer's `ai_capabilities`.

    Same two shapes as `_normalise_objectives`, same refusal to guess. A
    feature whose `page_text` is missing maps to None, and None means UNUSABLE
    rather than unconstrained: a claim needs stored text to trace to.
    """
    raw = (offer or {}).get("ai_capabilities")
    if not raw:
        return {}
    out = {}
    if isinstance(raw, dict):
        for feature, body in raw.items():
            if isinstance(body, dict):
                out[str(feature)] = body.get("page_text")
            else:
                out[str(feature)] = body
    elif isinstance(raw, (list, tuple)):
        for entry in raw:
            if not isinstance(entry, dict):
                raise ValueError(
                    "ai_capabilities entry is %r, expected a mapping with "
                    "'feature' and 'page_text'" % (entry,))
            out[str(entry.get("feature"))] = entry.get("page_text")
    else:
        raise ValueError(
            "ai_capabilities is %s, expected a list or a mapping"
            % type(raw).__name__)
    return out


def _mentions(text, phrase):
    """Does `text` name `phrase` as a whole phrase?

    Case-insensitive and whitespace-tolerant, because copy wraps lines. NOT a
    substring test: `\\b` boundaries stop `Agents` matching inside another word.
    The residual imprecision is reported by `check()` rather than hidden - a
    single common word as a feature name ("Agents") can match a sentence that
    was not naming the feature, and this module does not pretend otherwise.
    """
    pattern = r"\b%s\b" % r"\s+".join(
        re.escape(w) for w in str(phrase).split())
    return re.search(pattern, str(text or ""), re.I) is not None


def _sentences_naming(text, phrase):
    """The sentences of `text` that name `phrase`.

    Scoped to the sentence rather than the whole message on purpose: a claim is
    licensed or not by the sentence that makes it, and checking the whole body
    lets an unlicensed sentence borrow vocabulary from a licensed one three
    paragraphs away.
    """
    parts = re.split(r"(?<=[.!?])\s+", str(text or ""))
    return [s for s in parts if _mentions(s, phrase)]


def _claim_is_licensed(body, feature, page_text):
    """Does what this copy SAYS about `feature` trace to the stored page text?

    THE FEATURE'S OWN NAME IS EXCLUDED, and that exclusion is the whole check.
    Without it, "AI Time Tracking removes the need to think about admin ever
    again" is licensed by a page that says only that it "analyzes calendar
    events... fills out your time sheets", because the NAME shares the word
    "time" with the page. A check that a token appears somewhere in the source
    is the `_traces` defect this repository already carries as a launch blocker;
    reproducing it here would have shipped a gate that licenses anything.

    So: take the sentences that name the feature, remove the words of the name
    itself, and require what remains to share vocabulary with the page. Copy
    that asserts something the page never says shares nothing and is refused.
    """
    name_words = _content_words(feature)
    page_words = _content_words(page_text)
    for sentence in _sentences_naming(body, feature):
        claim_words = _content_words(sentence) - name_words
        if claim_words and not (claim_words & page_words):
            return False
    return True


def _unlicensed_evidence(evidence):
    """Names from `evidence` that license NOTHING, because page_text is null.

    All twelve Productive customer stories are in this state: CLIENT_APPROVED
    to be named, but with no stored page text there is nothing for a claim to
    trace to, so the file's own comment says no figure on them is quotable.
    """
    out = set()
    for entry in (evidence or {}).values():
        if not isinstance(entry, dict):
            continue
        if entry.get("page_text") in (None, "", {}, []):
            name = entry.get("name")
            if name:
                out.add(str(name))
    return out


def _questions(text):
    return [s.strip() for s in re.split(r"(?<=[?])\s+", str(text or ""))
            if s.strip().endswith("?")]


def check(sequence, facts=None, capability=None, qualification=None,
          batch_capabilities=None, repeat_threshold=0.45,
          offer=None, rules=None, evidence=None):
    """Every sequence-level failure, each naming the step responsible.

    `sequence` is `{"emails": {...}, "linkedin": {...}, "subjects": {...},
    "hypothesis": str, "ps": {...}}`. Returns
    `{"passed", "failures", "warnings", "checks"}` where a failure is
    `{"check", "step", "why"}` - the step is the point of the whole module.

    `offer` is the SELECTED offer record, `rules` is the file's
    `messaging_rules`, `evidence` is its `evidence` block. Supplying them turns
    on the operator's messaging rule: the step-objective spine, the ceiling of
    one AI capability per message, and the requirement that every AI claim and
    every named customer trace to stored page text. Omitting them does not
    silently pass - it warns that the rule was not checked, the same way an
    absent `batch_capabilities` does.
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
    pack = {"facts": [{"snippet": f.get("quote") or f.get("text")}
                      for f in facts]}
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
    subs = [s for s in (subjects or {}).values() if s]
    if len(subs) != len({str(s).strip().lower() for s in subs}):
        fail("no_repetition", "subjects",
             "two of the three thread subjects are the same")
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

    # THE OPERATOR'S MESSAGING RULE ---------------------------------------
    #
    # AI IS A SUPPORTING ANGLE, NEVER THE OFFER. The failure being prevented is
    # Productive outreach turning into a generic AI pitch: the offer spine is
    # the argument, and an AI feature is at most the mechanism at one step.
    prospect_facing = dict(emails)
    prospect_facing.update({"li:%s" % k: v for k, v in linkedin.items()})
    prospect_facing.update({"ps:%s" % k: v for k, v in ps.items()})

    if offer is None:
        warn("offer_rules", "sequence",
             "no offer record supplied: the step-objective spine, the one AI "
             "capability ceiling and AI claim licensing were NOT checked")
    else:
        objectives = _normalise_objectives(offer)
        allowed_ai = _normalise_ai_capabilities(offer)
        max_ai = 1
        ai_required = False
        if rules:
            max_ai = int(rules.get("max_ai_capabilities_per_message", 1))
            ai_required = bool(rules.get("ai_required", False))

        # 11. EACH STEP SERVES ITS OBJECTIVE ------------------------------
        #
        # Mechanical, like `capability_matches` above and for the same reason:
        # taste is not a check. A step that shares no content word with its own
        # objective is not arguing that objective, whatever else it is doing.
        if not objectives:
            warn("step_objectives", "sequence",
                 "the offer record carries no step_objectives: the sequence "
                 "spine was NOT checked")
        for step, objective in sorted(objectives.items()):
            body = emails.get(step)
            if not body:
                fail("step_objectives", step,
                     "the offer defines an objective for this step (%r) and "
                     "the sequence has no such step" % objective)
                continue
            if not (_content_words(objective) & _content_words(body)):
                fail("step_objectives", step,
                     "shares no content word with its objective (%r), so it "
                     "does not advance the offer's spine" % objective)

        # 12. AT MOST ONE AI CAPABILITY PER MESSAGE -----------------------
        for step, body in sorted(prospect_facing.items()):
            named = sorted(f for f in allowed_ai if _mentions(body, f))
            if len(named) > max_ai:
                fail("ai_supporting_only", step,
                     "names %d AI capabilities (%s) and the ceiling is %d: AI "
                     "supports one angle, it is not the pitch"
                     % (len(named), ", ".join(named), max_ai))

            # 13. AN AI CLAIM TRACES TO STORED PAGE TEXT ------------------
            for feature in named:
                page_text = allowed_ai.get(feature)
                if page_text in (None, "", {}, []):
                    fail("ai_claim_licensed", step,
                         "names %r, which has no stored page text: with "
                         "nothing to trace a claim to, the feature is not "
                         "usable in copy" % feature)
                elif not _claim_is_licensed(body, feature, page_text):
                    fail("ai_claim_licensed", step,
                         "asserts something about %r that its stored page text "
                         "does not support: the sentence naming it shares no "
                         "vocabulary with the page once the feature's own name "
                         "is set aside" % feature)

        # AI IS NEVER REQUIRED, and there is deliberately NO check for its
        # absence. `messaging_rules.ai_required` is false, so a message naming
        # no AI capability is valid. The inverse would force a feature into
        # every message, which is the outcome this rule exists to prevent. If
        # the operator ever sets ai_required true, that check belongs here.
        if ai_required:
            for step, body in sorted(prospect_facing.items()):
                if not any(_mentions(body, f) for f in allowed_ai):
                    fail("ai_supporting_only", step,
                         "messaging_rules.ai_required is set and this message "
                         "names no AI capability")

        # 14. A NAMED CUSTOMER NEEDS STORED PAGE TEXT ---------------------
        for name in sorted(_unlicensed_evidence(evidence)):
            for step, body in sorted(prospect_facing.items()):
                if _mentions(body, name):
                    fail("ai_claim_licensed", step,
                         "names the customer %r whose evidence record has no "
                         "stored page text: CLIENT_APPROVED to be named is not "
                         "a licence for a claim with nothing behind it" % name)

        # THE IMPRECISION, REPORTED RATHER THAN HIDDEN. A feature named by a
        # single common word ("Agents") can match a sentence that was not
        # naming the feature at all, so this check can over-refuse. It is
        # reported so a refusal is read as "look at this step", never as proof.
        if any(len(str(f).split()) == 1 for f in allowed_ai):
            warn("ai_supporting_only", "sequence",
                 "one or more AI capability names are a single common word, "
                 "so a mention may be incidental: verify a refusal by reading "
                 "the step")
        if allowed_ai:
            warn("ai_claim_licensed", "sequence",
                 "licensing is LEXICAL: a sentence that reuses the page's own "
                 "vocabulary while asserting something the page does not say "
                 "passes this check. Semantic licensing is NOT verified here")

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
                       "ai_supporting_only", "ai_claim_licensed"]}


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
