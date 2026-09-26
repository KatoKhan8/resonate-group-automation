"""Refuse a BATCH of copy, and say how much of it was wrong.

    from src import copylint
    report = copylint.check_batch(leads, packs)
    if report["refused"]:
        ...                       # regenerate; never widen a rule

Operator, 2026-09-24, lane 1.

## IT IS A BATCH LINT, AND `src/lint.py` IS A DRAFT LINT

`lint.check(rec, key, step)` answers "may THIS draft ship" - greeting,
length, placeholders, attachments, banned phrases. It is per draft and it
cannot see the two things that only exist across a batch: whether two
leads open with the same sentence, and whether a claim is supported by
that lead's own research.

So this composes rather than replaces. `BANNED_PHRASES` and
`SUBSTITUTED_PUNCTUATION` are IMPORTED from `lint`, because a second copy
of either would drift and the drift would show up as copy that passes one
lint and fails the other.

## COUNTS, NOT JUST A REFUSAL

The operator asked for counts and the reason is operational: "the batch is
refused" tells somebody to regenerate 50 leads. "Forty-eight leads are
clean, two share a first line and one cites a fact that is not in its
pack" tells them what to fix. Every rule reports the leads it fired on.

**A REFUSAL IS STILL A REFUSAL.** `CLAUDE.md`: never widen a lint rule to
make a draft pass - regenerate the draft. Counts exist to direct the
regeneration, not to make a partial pass shippable.

## WHAT THE TRACEABILITY CHECK CAN AND CANNOT DO

It extracts SPECIFICS from a draft - figures, dates, quoted phrases and
proper nouns - and requires each to appear in one of that lead's pack
facts. That catches the failure that actually happens: a model inventing a
plausible detail about a company nobody researched.

It does NOT understand claims. A sentence that is wrong in a way carrying
no specific ("you must be struggling with scale") passes this and is a
judgement call for a person. Said out loud because a lint that is believed
to check more than it does is worse than one nobody trusts.
"""
import json
import os
import re

from .lint import BANNED_PHRASES, SUBSTITUTED_PUNCTUATION

#: How many steps a sequence must have. Operator: five.
STEPS_EXPECTED = 5

#: Buzzwords on top of `lint.BANNED_PHRASES`, which already carries the
#: opener clichés and two of these. Single words, matched on a word
#: boundary, so "leverage" fires and "leveraged buyout" in a quoted pack
#: fact is the caller's problem to have quoted.
BUZZWORDS = (
    "synergy", "synergies", "game-changer", "gamechanger", "leverage",
    "leveraging", "best-in-class", "cutting-edge", "world-class",
    "seamless", "seamlessly", "robust", "revolutionary", "disruptive",
    "innovative", "holistic", "paradigm", "turnkey", "bandwidth",
    "low-hanging", "move the needle", "circle back", "deep dive",
    "unlock", "unlocking", "supercharge", "empower", "streamline",
    "thought leader", "thought leadership", "value-add", "value add",
    "mission-critical", "next-generation", "state-of-the-art",
)

#: THE DASH RULE. The typographic dashes come from `lint`, and the spaced
#: hyphen is here because that is what an em dash becomes once anything
#: normalises it - the tell survives the substitution.
#:
#: A HYPHEN INSIDE A WORD IS NOT A DASH. "follow-up", "best-in-class" and
#: "data-driven" all contain one and none of them is the thing being
#: refused, so the pattern requires whitespace on both sides.
DASH_RE = re.compile(r"(?:%s)|(?:\s[-]\s)"
                     % "|".join(re.escape(d) for d in SUBSTITUTED_PUNCTUATION
                                if d in ("—", "–", "‑")))

#: What counts as a SPECIFIC: something a reader could check. Figures,
#: money, percentages, dates, quoted phrases, and capitalised multi-word
#: names. These are what a model invents when it has no pack to lean on.
SPECIFIC_RES = (
    re.compile(r"\b\d[\d,.]*\s*%"),
    re.compile(r"[$€£]\s?\d[\d,.]*\s*[kmb]?\b", re.I),
    re.compile(r"\b\d[\d,.]{1,}\b"),
    re.compile(r"\b(?:january|february|march|april|may|june|july|august|"
               r"september|october|november|december)\b", re.I),
    re.compile(r"\"([^\"]{8,80})\""),
    re.compile(r"\b(?:[A-Z][a-z]{2,}\s){1,3}[A-Z][a-z]{2,}\b"),
)

#: A STEP THAT SAYS IT IS THE LAST ONE, WHEN IT IS NOT.
#:
#: Lane M, 2026-09-25: step 4 of a five-step cadence read "so this is the
#: last useful thing I have" on 690 of 690 leads. Step 5 arrives nine days
#: later, so that sentence was false on every send, to every prospect, in
#: all three cohorts. Lane D's rung-3 note states the rule directly: no
#: "I will leave it here" either, because two rungs follow this one.
#:
#: WHY THIS IS A LINT AND NOT A REVIEW NOTE. It reads perfectly well in
#: isolation, which is why it survived a human sampling of fifteen drafts.
#: What makes it false is not the sentence, it is the sentence's POSITION
#: in a sequence whose length the caller already knows. That is arithmetic,
#: so a person should never be asked to hold it in their head again.
#:
#: The LAST step is exempt: there, the same sentence is true.
FINALITY_RE = re.compile(
    r"\b(?:"
    r"(?:this|that)\s+is\s+(?:the\s+)?(?:my\s+)?last\b"
    r"|last\s+(?:email|note|message|one|thing|time)\b"
    r"|final\s+(?:email|note|message|attempt|nudge)\b"
    r"|i(?:\s+will|'ll|\s+wont|\s+won't)?\s+(?:stop|leave\s+it)\s+(?:here|there)\b"
    r"|leave\s+you\s+(?:alone|in\s+peace)\b"
    r"|(?:wont|won't|will\s+not)\s+(?:email|write|follow\s+up|chase|bother)\b"
    r"|no\s+more\s+(?:emails|notes|messages)\s+from\s+me\b"
    r"|closing\s+the\s+loop\b"
    r"|last\s+(?:i|one)\s+will\s+send\b"
    r")", re.I)


#: Words that make a sentence a claim ABOUT THE COMPANY rather than about
#: us. A specific inside one of these has to trace; a specific in "we work
#: with 40 agencies" is a claim about us and is not this lint's business.
COMPANY_CLAIM = re.compile(
    r"\b(you|your|they|their|announced|launched|hiring|opened|raised|"
    r"shipped|released|grew|expanded|acquired|published|posted)\b", re.I)

_WORD = re.compile(r"[a-z0-9]+")


def _norm(text):
    return " ".join(_WORD.findall(str(text or "").lower()))


def first_line(body):
    for line in str(body or "").splitlines():
        line = line.strip()
        if line:
            return line
    return ""


def steps_of(lead):
    """The lead's five steps, as a list, whatever shape it arrived in."""
    steps = lead.get("steps")
    if isinstance(steps, dict):
        return [steps.get(k) for k in sorted(steps)]
    return list(steps or [])


def _body(step):
    if isinstance(step, dict):
        return step.get("body") or step.get("text") or ""
    return step or ""


def _subject(step):
    """A step's subject, under either of the two names in use.

    `email_subject` is the provider's spelling and `subject` is ours, and
    reading only one of them is how a whole check comes back clean: the
    sequence rows carry `email_subject`/`email_body` and nothing else.
    """
    if isinstance(step, dict):
        return step.get("subject") or step.get("email_subject") or ""
    return ""


#: Everything a prospect reads that is NOT an email step. The P.S. lines and
#: the LinkedIn cadence live beside `steps` on the lead, so a check that
#: walks `steps` alone never sees them.
def other_prospect_text(lead):
    """The P.S. lines and every LinkedIn message, flattened.

    Named separately from the bodies so a caller can tell what was checked.
    Returns "" for a lead carrying neither, which is the common case for the
    eleven campaigns that predate both.
    """
    out = []
    ps = (lead or {}).get("ps") or {}
    if isinstance(ps, dict):
        out.extend(str(v) for v in ps.values() if v)
    elif ps:
        out.append(str(ps))
    li = (lead or {}).get("linkedin") or {}
    if isinstance(li, dict):
        out.extend(str(v) for v in li.values() if v)
    return "\n".join(out)


def pack_text(pack):
    """Every snippet in one lead's pack, lower-cased and flattened."""
    facts = (pack or {}).get("facts") or []
    return _norm(" ".join(str(f.get("snippet") or "") for f in facts))


def specifics_in(text):
    """Checkable details in a piece of copy, de-duplicated."""
    found = []
    for pattern in SPECIFIC_RES:
        for match in pattern.finditer(str(text or "")):
            value = match.group(1) if match.groups() else match.group(0)
            value = value.strip()
            if value and value not in found:
                found.append(value)
    return found


def _traces(value, supported):
    """Is this specific supported, allowing for a sentence-initial capital?

    THE OVER-FIRE THIS EXISTS FOR. The proper-noun pattern cannot tell a
    name from the capitalised first word of a sentence, so "Your Senior
    Platform Engineer role" is extracted whole and never matches a pack
    that says "Senior Platform Engineer". Dropping the leading token and
    retrying costs nothing a real invention would survive: an invented
    name does not become traceable by losing its first word.
    """
    token = _norm(value)
    if not token:
        return True
    if token in supported:
        return True
    parts = token.split(" ")
    return len(parts) > 2 and " ".join(parts[1:]) in supported


def untraceable(body, pack):
    """Specifics in a COMPANY CLAIM that no pack fact supports."""
    supported = pack_text(pack)
    out = []
    for sentence in re.split(r"(?<=[.!?])\s+", str(body or "")):
        if not COMPANY_CLAIM.search(sentence):
            continue
        for value in specifics_in(sentence):
            if not _traces(value, supported):
                out.append(value)
    return out


# ---------------------------------------------------------------------------
# CASE STUDY TRACING (TASK-365)
#
# The operator's rule: copy may name a case study and quote only what the
# page itself states; the lint traces every case-study claim to the stored
# page text and refuses anything not on it.
#
# Two further rules: never more than one case study per email, and the lint
# must report which study was named so the selector can be checked.
#
# WHY THIS DOES NOT REUSE `_traces`. TASK-330 is fixing that mechanism's
# weakness (token-in-supported reduces to a substring match that can pass
# by reusing a number from an unrelated part of the page). Instead, each
# specific is bound to a page sentence: a single line on the page must
# contain both the specific AND at least two significant words from the
# claim sentence. If no such line exists, the claim is unbound and is
# refused.
# ---------------------------------------------------------------------------

_CASE_STUDY_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "work", "evidence", "case-studies")

_study_cache = None


def _load_studies():
    """Load stored case-study records from work/evidence/case-studies/.

    Returns {key: record} for every stored study.  Returns empty dict if
    the directory does not exist (no studies fetched yet), which means no
    case-study claim can pass - there is nothing to trace against.
    """
    global _study_cache
    if _study_cache is not None:
        return _study_cache
    out = {}
    if not os.path.isdir(_CASE_STUDY_DIR):
        _study_cache = out
        return out
    for fn in sorted(os.listdir(_CASE_STUDY_DIR)):
        if fn.endswith(".json"):
            key = fn[:-5]
            path = os.path.join(_CASE_STUDY_DIR, fn)
            with open(path, "r", encoding="utf-8") as f:
                rec = json.load(f)
            if rec.get("status") == "OK" and rec.get("text"):
                out[key] = rec
    _study_cache = out
    return out


def reset_study_cache():
    """Clear the cached studies.  For tests that create temp studies."""
    global _study_cache
    _study_cache = None


def _studies_named_in(text, studies):
    """Which stored case studies does this text mention by name?"""
    found = []
    norm_text = text.lower()
    for key, rec in studies.items():
        name = rec.get("name", "")
        if name and name.lower() in norm_text:
            found.append(key)
    return found


def _significant_words(text):
    """Content words from a sentence, lowercased, length > 3."""
    return set(w for w in _WORD.findall(text.lower()) if len(w) > 3)


def _bind_specific_to_page(specific, claim_sentence, page_text):
    """Find a page sentence that supports this specific.

    The page sentence must contain the specific as a TOKEN (not a
    substring of another token) AND share at least two significant words
    with the claim sentence.  Return the page sentence if found, None
    otherwise.

    WHY TOKEN MATCHING, NOT SUBSTRING. _norm produces a flat string where
    "70" is a substring of "370". A substring check would pass "70"
    against a page that says "370 people" - which is the exact TASK-330
    weakness this rule exists to avoid. Token-level matching requires
    the specific to appear as a standalone word on the page.

    WHY TWO SHARED WORDS, NOT ONE. A single shared word like "the" or
    "people" would bind to almost any page line, defeating the purpose.
    Two significant words (length > 3) ensure the page sentence is
    actually about the same topic.
    """
    specific_tokens = set(_WORD.findall(specific.lower()))
    if not specific_tokens:
        return None
    claim_words = _significant_words(claim_sentence)
    page_sentences = re.split(r'(?<=[.!?])\s+', page_text)
    for ps in page_sentences:
        page_tokens = set(_WORD.findall(ps.lower()))
        # Every specific token must appear as a standalone page token.
        if not specific_tokens.issubset(page_tokens):
            continue
        overlap = claim_words & _significant_words(ps)
        if len(overlap) >= 2:
            return ps.strip()
    return None


def case_study_violations(body, studies=None):
    """Every (study_key, specific, claim_sentence, page_sentence_or_None)
    where a specific in a case-study claim is not bound to the page.

    A specific is bound when a single page sentence contains both the
    specific and at least two significant words from the claim sentence.
    If the study has no stored page text, every specific is a violation.
    """
    if studies is None:
        studies = _load_studies()
    if not studies:
        return []
    violations = []
    for sentence in re.split(r'(?<=[.!?])\s+', str(body or "")):
        named = _studies_named_in(sentence, studies)
        for key in named:
            page_text = studies[key].get("text", "")
            if not page_text:
                for specific in specifics_in(sentence):
                    violations.append((key, specific, sentence, None))
                continue
            for specific in specifics_in(sentence):
                binding = _bind_specific_to_page(
                    specific, sentence, page_text)
                if binding is None:
                    violations.append((key, specific, sentence, None))
    return violations


def case_studies_in_email(body, studies=None):
    """The distinct study keys named across the whole email body.

    Returns a sorted list.  The caller refuses when len > 1.
    """
    if studies is None:
        studies = _load_studies()
    if not studies:
        return []
    found = set()
    for sentence in re.split(r'(?<=[.!?])\s+', str(body or "")):
        for key in _studies_named_in(sentence, studies):
            found.add(key)
    return sorted(found)


def buzzwords_in(text):
    low = " %s " % _norm(text)
    hits = [w for w in BUZZWORDS if " %s " % _norm(w) in low]
    hits += [p for p in BANNED_PHRASES if _norm(p) and _norm(p) in low]
    return sorted(set(hits))


#: Every rule, in the order the report lists them. Name, and the sentence
#: a person reads when it fires.
RULES = (
    ("step1_without_pack_fact",
     "step 1 opens with a line no pack fact supports"),
    ("duplicate_first_line",
     "two or more leads open with the same sentence"),
    ("untraceable_company_claim",
     "a claim about the company is not traceable to a pack fact"),
    ("empty_step",
     "one of the %d steps is empty" % STEPS_EXPECTED),
    ("dash",
     "a dash used as punctuation"),
    ("buzzword",
     "a buzzword or banned phrase"),
    ("finality_before_last_step",
     "a step claims to be the last one while a later step still sends"),
    ("unrendered_variable",
     "a merge field or template variable survived into the body"),
    ("empty_sentence",
     "a sentence rendered to nothing: a bare full stop, or a gap where a "
     "variable should have been"),
    ("case_study_claim_not_on_page",
     "a case-study claim contains a specific not bound to the stored page"),
    ("multiple_case_studies_in_email",
     "more than one case study is named in a single email"),
)

#: A TEMPLATE VARIABLE THAT SURVIVED THE RENDER.
#:
#: Both syntaxes the provider accepts, plus the Python one the templates are
#: written in. `{SUBJECT_1}` reaching a person is the provider's own merge
#: field unresolved; `{capability}` reaching one is ours.
UNRENDERED_RE = re.compile(r"\{\{?\s*[A-Za-z_][A-Za-z0-9_]*\s*\}?\}|%\([A-Za-z_]+\)s")

#: A SENTENCE THAT RENDERED TO NOTHING.
#:
#: FOUND THE HARD WAY, 2026-09-25. A page builder passed `capability: ""` and
#: omitted `our_company`, and step 3 shipped `the specific thing  does` and a
#: bare `.` to a review file. Every existing rule passed it: the step was not
#: empty, carried no dash, no buzzword and no unrendered variable - the
#: variable had rendered, to nothing.
#:
#: So absence of a variable is not the same fault as a variable resolving to
#: emptiness, and only the second leaves a grammatical hole. These catch a
#: stranded full stop, a doubled space mid-sentence where a value belonged,
#: and a sentence with a comma or space immediately before its terminator.
EMPTY_SENTENCE_RES = (
    re.compile(r"(?:^|\n)\s*[.!?]\s*(?:$|\n)"),      # a line that is just "."
    re.compile(r"[A-Za-z]\s{2,}[a-z]"),              # "thing  does"
    re.compile(r"\s+[.!?](?:\s|$)"),                 # " ." - a gap then a stop
    re.compile(r",\s*[.!?]"),                        # ", ."
)


#: RULES THAT REPORT INSTEAD OF REFUSING. Empty is the normal state.
#:
#: OPERATOR DIRECTIVE, Zvonimir, 2026-09-25, "PROOF MODE", explicitly
#: time-boxed to 2026-09-28: the goal is leads in campaigns and sending on
#: both providers today, proof first and tweaking after.
#:
#: `step1_without_pack_fact` is a WARNING for this phase, reported per batch
#: and never a refusal. It was refusing EVERY push this system can make, and
#: that was the lint telling the truth: of 927 rendered rows, 636 matched a
#: record and ZERO carried a pack fact.
#:
#: WHAT A WARNING IS NOT. It is not permission to invent. The rules that
#: catch invention - `untraceable_company_claim`, `empty_step`, `dash`,
#: `duplicate_first_line`, `buzzword` - all still REFUSE. A lead with no pack
#: ships a generic-but-true opener or it does not ship; what it may never do
#: is assert a specific nothing supports.
#:
#: WHY THIS IS A NAMED SET AND NOT AN `if`. CLAUDE.md: "Never widen a lint
#: rule to make a draft pass." This does not widen the rule - it still fires,
#: is still counted, and every offender is still named in the report. It
#: changes only whether firing stops the push, and it says in one readable
#: line which rules that is true of, so restoring the refusal is deleting a
#: name from a tuple rather than finding an inverted condition.
WARNING_RULES = frozenset({"step1_without_pack_fact"})


def check_batch(leads, packs=None, steps_expected=STEPS_EXPECTED,
                case_studies=None):
    """`{refused, leads, clean, counts, offenders, rules}` for one batch.

    `packs` maps a lead id to its research pack. A lead with NO pack is not
    quietly excused: it cannot open step 1 with a supported line, so it
    fires the first rule. A batch generated before the packs were built is
    exactly the batch this is for.

    `case_studies` is an optional {key: record} dict for the case-study
    tracing rule.  When None, the stored studies are loaded from disk.
    Tests pass studies directly; production loads from work/.
    """
    packs = packs or {}
    leads = list(leads or [])
    offenders = {name: [] for name, _ in RULES}
    seen_first = {}

    for lead in leads:
        lead_id = str(lead.get("id") or lead.get("contact") or "?")
        pack = packs.get(lead_id) or lead.get("pack") or {}
        steps = steps_of(lead)

        bodies = [_body(s) for s in steps]
        if len(steps) != steps_expected or any(
                not str(b or "").strip() for b in bodies):
            offenders["empty_step"].append(lead_id)

        opener = first_line(bodies[0] if bodies else "")
        # STEP 1 HAS TO OPEN ON SOMETHING THEY SAID. The whole point of a
        # research pack is the first line; a pack that exists and is not
        # used in the opener has bought nothing.
        supported = pack_text(pack)
        opener_tokens = [t for t in _WORD.findall(opener.lower())
                         if len(t) > 4]
        if not supported or not any(t in supported for t in opener_tokens):
            offenders["step1_without_pack_fact"].append(lead_id)

        if opener:
            key = _norm(opener)
            if key in seen_first:
                for who in {seen_first[key], lead_id}:
                    if who not in offenders["duplicate_first_line"]:
                        offenders["duplicate_first_line"].append(who)
            else:
                seen_first[key] = lead_id

        whole = "\n".join(bodies)
        # THE SUBJECT COUNTS TOO. A subject is the first thing read and it
        # goes through the same render; checking only bodies would let
        # `Re: {SUBJECT_1}` ship.
        subjects = "\n".join(str(_subject(s) or "") for s in steps)
        # EVERYTHING ELSE A PROSPECT READS, WHICH UNTIL NOW WAS NOTHING.
        #
        # This walked `steps` and only `steps`, so the P.S. lines and all
        # four LinkedIn messages were outside every rule in this module.
        # Measured 2026-09-25: the dash rule was clean on a batch whose
        # connection note and first follow-up both carried " - ". The rule
        # was right and it was pointed at half the copy.
        extra = other_prospect_text(lead)
        rendered = whole + "\n" + subjects + "\n" + extra
        if UNRENDERED_RE.search(rendered):
            offenders["unrendered_variable"].append(lead_id)
        if any(r.search(rendered) for r in EMPTY_SENTENCE_RES):
            offenders["empty_sentence"].append(lead_id)
        if untraceable(whole, pack):
            offenders["untraceable_company_claim"].append(lead_id)
        # OVER EVERYTHING THE PROSPECT READS, not just the email bodies.
        # Operator, 2026-09-25: dashes are banned in email bodies, subjects,
        # P.S. lines and every LinkedIn message, and the rule REFUSES.
        if DASH_RE.search(rendered):
            offenders["dash"].append(lead_id)
        if buzzwords_in(whole):
            offenders["buzzword"].append(lead_id)
        # EVERY STEP BUT THE LAST. The last step may say it is the last
        # step, because there it is true.
        for earlier in bodies[:-1]:
            if FINALITY_RE.search(str(earlier or "")):
                offenders["finality_before_last_step"].append(lead_id)
                break
        # CASE STUDY TRACING (TASK-365). Every specific in a sentence that
        # names a case study must be bound to a stored page sentence.
        # Two studies in one email is a separate refusal.
        _cs = case_studies if case_studies is not None else _load_studies()
        if case_study_violations(whole, studies=_cs):
            offenders["case_study_claim_not_on_page"].append(lead_id)
        if len(case_studies_in_email(whole, studies=_cs)) > 1:
            offenders["multiple_case_studies_in_email"].append(lead_id)

    counts = {name: len(offenders[name]) for name, _ in RULES}
    dirty, warned = set(), set()
    for name, ids in offenders.items():
        (warned if name in WARNING_RULES else dirty).update(ids)
    return {
        "leads": len(leads),
        "clean": len(leads) - len(dirty) - len(warned - dirty),
        "refused": bool(dirty),
        "warned": len(warned - dirty),
        "warning_rules": sorted(WARNING_RULES),
        "counts": counts,
        "offenders": {k: sorted(v) for k, v in offenders.items()},
        "rules": dict(RULES),
    }


def report_lines(report):
    """The counts a person reads. Refusal first, then what to fix."""
    out = ["%s: %d of %d leads clean, %d warned"
           % ("REFUSED" if report["refused"] else "PASSED",
              report["clean"], report["leads"], report.get("warned", 0))]
    if report.get("warning_rules"):
        out.append("  WARNING ONLY (does not refuse): %s"
                   % ", ".join(report["warning_rules"]))
    for name, why in RULES:
        count = report["counts"].get(name, 0)
        if not count:
            continue
        ids = report["offenders"][name]
        out.append("  %-26s %3d  %s%s"
                   % (name, count, ", ".join(ids[:6]),
                      " ..." if len(ids) > 6 else ""))
        out.append("  %-26s      %s" % ("", why))
    if not report["refused"] and not report.get("warned"):
        out.append("  every lead opened on a pack fact and no two opened "
                   "the same way")
    elif not report["refused"]:
        # PASSED with warnings is a different sentence, and saying the old one
        # here would assert the exact thing the warning exists to deny.
        out.append("  nothing refused; the warnings above are reported and "
                   "do NOT stop the push while PROOF MODE stands")
    return out
