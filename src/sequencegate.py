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


def _questions(text):
    return [s.strip() for s in re.split(r"(?<=[?])\s+", str(text or ""))
            if s.strip().endswith("?")]


def check(sequence, facts=None, capability=None, qualification=None,
          batch_capabilities=None, repeat_threshold=0.45):
    """Every sequence-level failure, each naming the step responsible.

    `sequence` is `{"emails": {...}, "linkedin": {...}, "subjects": {...},
    "hypothesis": str, "ps": {...}}`. Returns
    `{"passed", "failures", "warnings", "checks"}` where a failure is
    `{"check", "step", "why"}` - the step is the point of the whole module.
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
                       "no_repetition"]}


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
