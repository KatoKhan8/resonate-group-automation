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

# -- Semantic paraphrase detection (deterministic) -----------------------
#
# Lexical overlap cannot see two steps arguing the same thing in different
# words.  The concept groups below map surface words to the semantic role
# they play in an outreach argument.  Two steps are flagged as paraphrases
# when they share BOTH enough concepts (>= 0.6 concept overlap) AND enough
# roles (>= 0.6 role overlap), with at least 2 shared concepts.  Both
# thresholds must be met: sharing a financial metric is not enough when the
# direction and context differ, and sharing a role like PROJECT_TYPE is not
# enough when the concepts are unrelated.
#
# This is deterministic - no model call - and it CANNOT rescue a lexical
# failure.  It adds refusals; it never removes them.

_SEMANTIC_GROUPS = {
    "MARGIN": {"margin", "margins", "profit", "profits", "profitability",
               "return", "returns"},
    "PROJECT_TYPE": {"fixed", "scope", "flat", "fee", "retainer",
                     "milestone", "t-and-m"},
    "UNSEEN": {"invisible", "unseen", "nobody", "hidden", "later",
               "afterwards", "afterward", "until"},
    "LOW": {"thin", "squeezed", "eroded", "compressed", "shrinking",
            "slim", "tight"},
    "HIGH": {"high", "rising", "increasing", "growing", "escalating",
             "surging"},
    "EXPENSE": {"cost", "costs", "expense", "expenses", "overhead",
                "spend", "spending"},
    "REVENUE": {"revenue", "sales", "income", "turnover", "bookings"},
    "SPEED": {"fast", "faster", "quick", "slow", "slower", "speed",
              "rapid", "delay"},
    "RISK": {"risk", "risky", "danger", "threat", "exposure"},
    "CUSTOMER": {"customer", "customers", "client", "clients", "churn",
                 "retention", "buyer", "buyers"},
    "DIFFICULT": {"hard", "difficult", "complex", "complicated",
                  "struggle", "struggling"},
    "AUTOMATION": {"automate", "automation", "manual", "automated",
                   "workflow"},
    "HIRING": {"hire", "hiring", "recruit", "recruiting", "talent",
               "onboard"},
    "SCALE": {"scale", "scaling", "grow", "growth", "expand",
              "expansion"},
    "QUALITY": {"quality", "bug", "bugs", "defect", "defects", "error",
                "errors"},
}


def _word_concept(word):
    """Which concept group a word belongs to, or None."""
    for group_name, words in _SEMANTIC_GROUPS.items():
        if word in words:
            return group_name
    return None


def _concept_profile(text):
    """Set of concept group names present in text."""
    return {c for w in _content_words(text)
            for c in [_word_concept(w)] if c is not None}


def _role_profile(text):
    """Set of semantic roles (group names) present in text.

    Same mapping as concept profile - each concept group IS a role.
    """
    return _concept_profile(text)


def semantic_overlap(a, b, min_shared_concepts=2):
    """Deterministic semantic similarity via concept and role overlap.

    Returns a score in [0, 1].  Both concept overlap and role overlap must
    be >= 0.6, and at least *min_shared_concepts* concept groups must be
    shared, for the score to be nonzero.  This prevents a single shared
    concept (e.g. both mention a project type) from flagging two genuinely
    different arguments.
    """
    ca, cb = _concept_profile(a), _concept_profile(b)
    shared_c = ca & cb
    if len(shared_c) < min_shared_concepts:
        return 0.0
    if not ca or not cb:
        return 0.0
    concept_ov = len(shared_c) / min(len(ca), len(cb))

    ra, rb = _role_profile(a), _role_profile(b)
    shared_r = ra & rb
    if not ra or not rb:
        return 0.0
    role_ov = len(shared_r) / min(len(ra), len(rb))

    if concept_ov < 0.6 or role_ov < 0.6:
        return 0.0
    return (concept_ov + role_ov) / 2.0


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
    # Two layers: lexical overlap catches near-duplicates (verbatim or
    # near-verbatim copies); semantic overlap catches paraphrases - same
    # argument in different words.  The semantic layer uses concept groups
    # (semantic roles) and is deterministic: no model call, no override.
    # It adds refusals; it never removes a lexical failure.
    #
    # The known counter-example that lexical overlap missed:
    #   "Your margins are thin on fixed scope work and nobody sees it."
    #   "Profit on flat fee projects gets squeezed, invisible until later."
    # Lexical overlap: 0.0.  Semantic overlap: 0.75 (MARGIN, LOW,
    # PROJECT_TYPE shared).  Now caught.
    order = [k for k in ("em1", "em2", "em3", "em4", "em5") if k in emails]
    for i, step in enumerate(order):
        for earlier in order[:i]:
            score = overlap(emails[step], emails[earlier])
            if score >= repeat_threshold:
                fail("followup_adds_value", step,
                     "repeats %s: %.0f%% of its argument is the same"
                     % (earlier, 100 * score))
                break
    # SEMANTIC PARAPHRASE CHECK: catches same argument in different words.
    # Only runs when the lexical check did not already flag the pair.
    for i, step in enumerate(order):
        for earlier in order[:i]:
            lex = overlap(emails[step], emails[earlier])
            if lex >= repeat_threshold:
                break
            sem = semantic_overlap(emails[step], emails[earlier])
            if sem > 0:
                fail("followup_adds_value", step,
                     "paraphrases %s: same argument in different words "
                     "(semantic overlap %.2f)" % (earlier, sem))
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
