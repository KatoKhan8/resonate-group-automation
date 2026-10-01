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
import re

import urllib.request
import urllib.error

from . import casestudies, optout
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
    re.compile(r"\b\d[\d,.]*\b"),
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
    r"shipped|released|grew|expanded|acquired|published|posted|closed)\b",
    re.I)

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
    """A step's body, under any of the three names in use.

    `email_body` is the provider's spelling and `body` is ours; the sequence
    rows carry `email_body` and nothing else, so reading only `body` made
    every body read as empty and every lead fire `empty_step`.
    """
    if isinstance(step, dict):
        return (step.get("body") or step.get("email_body")
                or step.get("text") or "")
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


#: CONTENT WORDS THAT CARRY NO CLAIM MEANING. A draft and a pack sentence
#: that share only one of these are not about the same thing - "$50M"
#: appears in both "raised $50M in 2019" and "grew revenue by $50M last
#: quarter", and "in" and "by" are the only overlap. Filtering these out
#: before counting shared words is what stops a reused number from
#: laundering a new claim.
_STOPWORDS = frozenset(
    "a an the in on at to for of by with from as is are was were be been "
    "being has have had do does did will would shall should may might can "
    "could this that these those it its their our your my he she we they "
    "them us not but and or if so than also".split()
)


def _pack_sentences(pack):
    """Each pack snippet as a list of normalised sentences.

    THE FIX FOR TASK-330. `pack_text` flattens everything into one token
    stream, so `_traces` could only ask "does this string appear
    ANYWHERE" - never "does it appear in a sentence about the same
    thing". This returns the sentences individually, so the traceability
    check can bind a specific to the sentence it came from.
    """
    facts = (pack or {}).get("facts") or []
    out = []
    for f in facts:
        snippet = str(f.get("snippet") or "")
        if not snippet.strip():
            continue
        for sent in re.split(r"(?<=[.!?])\s+", snippet.strip()):
            n = _norm(sent)
            if n:
                out.append(n)
    return out


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


def _traces(value, pack_sents, draft_sentence=""):
    """Is this specific grounded in a pack sentence about the same thing?

    A specific traces in two ways:

    1. DIRECT: a pack sentence contains the specific AND shares at least
       two content words with the draft sentence (excluding the specific
       and stopwords). This is what stops "raised $50M in 2019" from
       laundering "grew revenue by $50M last quarter".

    2. CAPITAL FALLBACK: the proper-noun pattern cannot tell a name from
       the capitalised first word of a sentence, so "Your Senior Platform
       Engineer role" is extracted whole. Dropping the leading token and
       finding the rest in a pack sentence is already a strong signal -
       an invented name does not become traceable by losing its first
       word, so a stripped match passes without the content threshold.
    """
    token = _norm(value)
    if not token:
        return True

    draft_tokens = set(_norm(draft_sentence).split())
    draft_content = draft_tokens - set(token.split()) - _STOPWORDS

    for ps in pack_sents:
        # DIRECT MATCH: the full specific appears in this pack sentence.
        # Require content-word overlap so a reused number in a different
        # context does not satisfy the gate.
        if token in ps:
            pack_tokens = set(ps.split())
            pack_content = pack_tokens - set(token.split()) - _STOPWORDS
            if len(draft_content & pack_content) >= 2:
                return True

        # CAPITAL FALLBACK: the leading word was a sentence-initial
        # capital, not part of the name. If the stripped form appears in
        # the pack sentence, the match is genuine - an invented multi-word
        # name would not survive losing its first word and still matching.
        parts = token.split(" ")
        if len(parts) > 2:
            stripped = " ".join(parts[1:])
            if stripped in ps:
                return True
    return False


def licensed_names(pack):
    """The CLIENT's own product names, which are not prospect specifics.

    `SPECIFIC_RES` treats a capitalised multi-word name as something "a model
    invents when it has no pack to lean on". True of a prospect's customer,
    office or product; FALSE of the client's own capabilities, which are
    named in the operator-approved offer library and carry their own licensed
    `page_text`.

    MEASURED 2026-09-30, and it is why the canary could not be written.
    "Report Intelligence answers a question about your own data" is refused
    as an untraceable claim about the prospect, because the name is
    capitalised, two words, and absent from the PROSPECT's pack - which it
    always will be. Offer A's rung 4 is literally "Report Intelligence as
    mechanism", so the approved ladder required a step that the copy lint
    then refused. Rachele's em4 was refused ten times over.

    "Productive" alone passes, being one word, which is why this went unseen.

    The names come from the offer record the caller is writing against -
    canonical, operator-approved data - never a list spelled here, and never
    from the offer library directly: `offers.py` is single-tenant (TASK-564
    finding 3) and would hand one client's licensed names to another.
    """
    return tuple(n for n in ((pack or {}).get("licensed_names") or ())
                 if str(n or "").strip())


def licensed_capabilities(pack):
    """The client's own capabilities AND the licensed text for each.

    `{name: page_text}`. `licensed_names` above answers "is this capitalised
    name the client's own?" and is what exempts the NAME from
    `untraceable_company_claim`. This answers the question that exemption
    left open: WHAT IS THE COPY ALLOWED TO SAY THE CAPABILITY DOES.

    MEASURED 2026-09-30. An email said Report Intelligence "surfaces margin
    and budget patterns as they happen, flagging trends you might want to act
    on early" and "highlights when something could be impacting margin right
    in the moment". Its licensed source - `ai_capabilities['Report
    Intelligence'].page_text` in the offer library - says only "Ask anything
    about your business data. Productive understands it and delivers the
    insights you're looking for already interpreted, in plain language."

    That is a PULL-based question-answering feature sold as PROACTIVE
    real-time monitoring, and no gate caught it: `licensed_names` exempted the
    NAME and nothing looked at the DESCRIPTION.

    A capability named in `licensed_names` but absent here carries `None`,
    which is NOT the same as `""` and not the same as absent: a described
    capability with no stored page text is REFUSED. See
    `capability_description_violations`.
    """
    caps = {}
    raw = (pack or {}).get("licensed_capabilities") or {}
    if isinstance(raw, dict):
        for name, value in raw.items():
            if not str(name or "").strip():
                continue
            if isinstance(value, dict):
                caps[str(name).strip()] = value.get("page_text")
            else:
                caps[str(name).strip()] = value
    for name in licensed_names(pack):
        caps.setdefault(str(name).strip(), None)
    return caps


#: WORDS THAT EXPRESS CONTAINMENT, AND NOTHING ELSE.
#:
#: The second licensing authority, operator-approved 2026-10-01. A sentence
#: can make two different claims about a capability and they do not have the
#: same authority behind them:
#:
#:   "Report Intelligence monitors your business data"   what it DOES
#:   "The premium trial includes Report Intelligence"    what the OFFER HAS
#:
#: The first is licensed by `page_text` and nothing else. The second is not a
#: product description at all, and judging it against `page_text` demanded
#: that the words "premium", "trial" and "includes" appear in a feature
#: blurb where they cannot be - so the gate refused the exact phrasing the
#: operator mandated for trial claims, and "AI features in the trial" is one
#: of three approved offers.
#:
#: THE AUTHORITY FOR CONTAINMENT IS THE OFFER FILE, which asserts it
#: STRUCTURALLY: the capability is listed under that offer's
#: `ai_capabilities`. The words below are the vocabulary of that relation,
#: not a vocabulary of claims - which is why they are licensed by the data
#: structure rather than by prose. A capability NOT listed is not licensed by
#: anything here.
_CONTAINMENT_WORDS = frozenset(
    "includ contain cover bundl part compris featur available availabl".split()
)


def offer_containment_text(pack):
    """The offer's own words for WHAT IT CONTAINS. Narrow on purpose.

    `mechanism_text` and `mechanism_secondary_text` ONLY - the operator's
    description of the thing being offered ("a walkthrough with a Productive
    AE", "the walkthrough may also offer the premium trial").

    WHAT IS DELIBERATELY EXCLUDED, and this is the whole safety of the second
    authority: `value_proposition`, `concrete_deliverable`, `business_problem`
    and `cta`. Offer A's read "margin per project while it is running", "margin
    is visible only after a project closes", "see project margin and budget
    burn while the project is still running". Those are BEHAVIOUR vocabulary -
    margin, visible, running, burn - and licensing a capability description
    with them would hand an overclaim the exact words the founding defect was
    made of. The offer file may say what the offer contains; it may not say
    what a capability does.
    """
    parts = []
    raw = (pack or {}).get("offer_containment_text")
    if isinstance(raw, (list, tuple)):
        parts.extend(str(x or "") for x in raw)
    elif raw:
        parts.append(str(raw))
    return " ".join(p for p in parts if p.strip())


def untraceable(body, pack):
    """Specifics in a COMPANY CLAIM that no pack fact supports.

    TASK-330: a specific now traces only when the pack sentence containing
    it shares at least two content words with the draft sentence. A number
    that appears in the pack but in a different context no longer satisfies
    the gate.

    The client's own licensed capability names are NOT specifics about the
    prospect - see `licensed_names`. Nothing else is relaxed: a figure, a
    date, a quoted phrase or any other capitalised name in the same sentence
    is still checked against the pack exactly as before, and a name the
    caller does not declare is still a specific.
    """
    pack_sents = _pack_sentences(pack)
    allowed = {n.strip().lower() for n in licensed_names(pack)}
    out = []
    for sentence in re.split(r"(?<=[.!?])\s+", str(body or "")):
        if not COMPANY_CLAIM.search(sentence):
            continue
        for value in specifics_in(sentence):
            if str(value).strip().lower() in allowed:
                continue
            if not _traces(value, pack_sents, sentence):
                out.append(value)
    return out


def buzzwords_in(text):
    low = " %s " % _norm(text)
    hits = [w for w in BUZZWORDS if " %s " % _norm(w) in low]
    hits += [p for p in BANNED_PHRASES if _norm(p) and _norm(p) in low]
    return sorted(set(hits))


# ------------------------------------------------- case-study claims (TASK-365)
#
# The operator's rule: copy may name a case study and quote only what the
# page itself states. The lint traces every case-study claim to the stored
# page text and refuses anything not on it.
#
# FAIL CLOSED. No stored page for a named study means REFUSE, not pass.
# An empty store refuses every case-study claim. This was the defect the
# rework fixed: the original code returned [] on an empty store, which
# let every claim through.
#
# SENTENCE-LEVEL BINDING. A claim's specifics must all appear in ONE
# sentence on the stored page, not scattered across the document. This
# prevents a number from an unrelated part of the page satisfying a claim.
# TASK-330 is fixing the same weakness in _traces; this is a separate
# mechanism for a separate rule.
#
# ONE STUDY PER EMAIL. A second named study in one message is a refusal.

def _split_sentences(text):
    """Split text into sentences on punctuation and newlines."""
    parts = re.split(r'(?<=[.!?])\s+|\n+', str(text or ""))
    return [s.strip() for s in parts if s and s.strip()]


def _claim_supported(claim_sentence, page_text, required_specifics):
    """Does one page sentence carry every required specific?

    Returns the supporting page sentence, or None. The binding is
    deterministic: every required token must appear in a single page
    sentence. Where that cannot be established, the claim is refused.

    TOKEN-LEVEL MATCHING. "70" must match the token "70", not appear as a
    substring of "370". Python's `in` on strings would let "70" pass
    against "370 people" - that is how the fail-open direction sneaks back
    in through the back door.
    """
    if not page_text or not required_specifics:
        return None
    required_tokens = [_norm(s) for s in required_specifics]
    required_tokens = [t for t in required_tokens if t]
    if not required_tokens:
        return None
    page_sentences = _split_sentences(page_text)
    for ps in page_sentences:
        ps_tokens = set(_WORD.findall(ps.lower()))
        if all(tok in ps_tokens for tok in required_tokens):
            return ps
    return None


def case_study_violations(text):
    """Refuse case-study claims that are not on the stored page.

    Three refusals, all fail-closed:

    1. A sentence names a study but no page is stored for it.
    2. A sentence names a study with specifics not bound to any page sentence.
    3. Two or more distinct studies are named in one body.

    Returns a list of (rule_name, message) tuples. Empty means no case-study
    mention (which passes) or every claim traced successfully.
    """
    violations = []
    names = casestudies.study_names()
    sentences = _split_sentences(text)

    named = {}
    for sentence in sentences:
        low = sentence.lower()
        for key, display in names.items():
            if display.lower() in low:
                named.setdefault(key, display)
                specifics = [s for s in specifics_in(sentence)
                             if s.lower() != display.lower()
                             and _norm(s) != _norm(display)]
                if not specifics:
                    continue
                study = casestudies.load_study(key)
                if study is None:
                    violations.append((
                        "case_study_unsupported",
                        "No stored page for '%s' - claim cannot be verified"
                        % display
                    ))
                    continue
                page_text = study.get("page_text", "")
                if not page_text:
                    violations.append((
                        "case_study_unsupported",
                        "No stored page for '%s' - claim cannot be verified"
                        % display
                    ))
                    continue
                supporting = _claim_supported(
                    sentence, page_text, specifics)
                if supporting is None:
                    violations.append((
                        "case_study_unsupported",
                        "Claim '%s' by '%s' not found on stored page"
                        % (", ".join(specifics), display)
                    ))

    if len(named) > 1:
        violations.append((
            "case_study_multiple",
            "More than one case study named: %s"
            % ", ".join(sorted(named.values()))
        ))

    return violations


# -------------------------------- a DESCRIBED capability (TASK-922)
#
# THE DEFECT, measured 2026-09-30 on live copy:
#
#   "Report Intelligence in Productive surfaces margin and budget patterns
#    as they happen, flagging trends you might want to act on early. It
#    highlights when something could be impacting margin right in the
#    moment."
#
# Licensed source, `ai_capabilities['Report Intelligence'].page_text`:
#
#   "Ask anything about your business data. Productive understands it and
#    delivers the insights you're looking for already interpreted, in plain
#    language."
#
# A PULL feature - the user asks, the product answers - sold as PROACTIVE
# REAL-TIME MONITORING. Nothing refused it. `licensed_names` exempts the
# capability NAME from `untraceable_company_claim`, and that exemption was
# the whole of the licensing story: the DESCRIPTION traced to nothing.
# `_claim_supported` is wired only to case studies.
#
# ## THE MECHANISM: COVERAGE BY THE LICENSED TEXT, NOT A LIST OF BAD WORDS
#
# The support set is DERIVED from the capability's own `page_text`. A
# description passes when most of what it asserts is already vocabulary of
# the licensed text; it is refused when it is not.
#
# THIS IS WHY IT IS NOT A BLACKLIST, and the distinction is the point of the
# rule. A blacklist enumerates the wrong words, so "surfaces ... as they
# happen" is caught and the synonym "spots ... the moment they emerge" walks
# through. Here nothing is enumerated: BOTH are refused, and they are
# refused for the same reason - neither "surfaces" nor "spots", neither
# "flagging" nor "alerting", appears anywhere in the licensed text. A
# synonym of an unlicensed claim is another unlicensed claim. The only way
# to pass is to say what the licensed text says.
#
# ## THE DEFAULT IS REFUSE. THAT IS THE SECOND AND LARGER IDEA HERE.
#
# SEVEN BYPASSES, 2026-10-01. The rule shipped asking "is the capability in
# a position I recognise as the subject?" and seven different sentence
# shapes answered no while making a false product claim: sentence-initial
# only, fronted PP, anchored pronoun, the 50% ratio, the content floor, the
# four-word window, the relative clause. Five were reported by review. Two
# more were found here in minutes, by trying - which is the whole argument.
# An enumeration cannot converge, because the adversary picks the shape and
# the defender lists them.
#
# SO THE DEFAULT IS INVERTED, on review's instruction:
#
#   IN SCOPE  = the sentence names a licensed capability, OR it carries any
#               word that can refer back to one and the previous sentence
#               was in scope. No position, no window, no clause test.
#   IN SCOPE + asserts a predicate  =>  must trace to that capability's
#               page_text, or REFUSE.
#   UNCLASSIFIABLE  =>  REFUSE. Never `continue`.
#
# There is no shape machinery left to evade. `_capability_subject`,
# `_starts_with_name`, `_continues_previous_subject`, `_SUBJECT_PREFIX`,
# `_FRONTED_INSTRUMENT` and `_CONTINUATION_WINDOW` are DELETED rather than
# extended, because every one of them was an answer to "which shapes count"
# and that question is the defect.
#
# ## THE FIVE `continue`s THAT REMAIN, EACH JUSTIFIED
#
# 1. OUT OF SCOPE: no capability name and no referring word. Nothing is
#    attributed to a capability, so there is nothing to verify. This is the
#    only one that can let an unexamined sentence past, and it is the
#    definition of scope rather than a hole in it.
#
#    AND IT DOES NOT CLEAR THE REFERENT. It used to, and that was BYPASS 8,
#    found here by mutating this very line rather than by review: one
#    neutral sentence between the name and the claim dropped the referent
#    and the claim walked. A capability named once stays referable for the
#    rest of the text - no sentence count, so no count to walk past. The
#    cost is that a later "it" about something else is read as the
#    capability; measured on the production store, that costs nothing (the
#    refusal count is 7 either way) and it closes the filler attack.
# 2. ALREADY REFUSED on this sentence for a missing page_text; falling
#    through would report it twice.
# 3. NO PREDICATE AT ALL - a sentence with no content words beyond the
#    capability's own name asserts nothing, so there is nothing to
#    license. This replaced a CONTENT FLOOR of two, which option (b)
#    dissolved: see the comment where that constant used to be.
# 4. IT TRACED. The licensed text supports it.
# 5. ALREADY RECORDED - the same refusal, the same sentence. Reached only
#    after the sentence has been judged unsupported, so it cannot pass one.
#
# ## FAIL CLOSED, IN FOUR PLACES
#
# 1. A capability with no stored `page_text` is REFUSED for any in-scope
#    sentence at any length, as `case_study_unsupported` refuses a named
#    study with no stored page. DECIDED FIRST, in front of every word count:
#    it is a question about the CAPABILITY, and sitting behind the floor let
#    a two-word claim trim past it twice.
# 2. ANY referring word continues the subject - any pronoun, any position,
#    any clause - so the claim cannot be moved one word further from the
#    name until it falls outside a window.
# 3. COVERAGE IS TESTED PER COORDINATED PREDICATE as well as over the whole
#    sentence, so a conjoined fabrication cannot average itself down against
#    the licensed vocabulary of the clause beside it.
# 4. The ratio is on the DESCRIPTION's content, so padding the sentence with
#    licensed vocabulary raises coverage only by saying licensed things.
#
# ## WHAT THE INVERSION COSTS, MEASURED RATHER THAN ESTIMATED
#
# Over the production store, 2026-10-01, read-only: 1,582 records, 4,565
# generated steps, of which SEVEN name a licensed capability. The gate
# before the inversion refused four of those seven. This one refuses all
# seven, and all seven are genuine overclaims - zero false positives on the
# copy that actually exists. The three it newly catches are live:
#
#   "Report Intelligence in Productive highlights trends that affect margin
#    while a project is running"
#
# which escaped because the lint reads subject and body joined, so the name
# is never sentence-initial. The position test failing on real copy, not on
# an invented probe.
#
# ## AND WHAT IT GIVES UP, WHICH IS A POLICY CHANGE, NOT A DETAIL
#
# "Naming was always allowed" no longer holds in full. Three mention forms
# that used to pass are now refused:
#
#   "Worth thirty minutes to walk you through Report Intelligence."
#   "Happy to show you Report Intelligence on a call if it is useful."
#   "I can send over what Report Intelligence looks like."
#
# Each predicates something of the SENDER with the capability as the object,
# each asserts nothing false, and each is a true false positive. Telling
# them apart from "With Report Intelligence you can watch margin live" needs
# syntax; every closed-class approximation of it leaked, so the undecided
# cases now go to REFUSE. NONE of these three forms occurs in any of the
# 4,565 generated steps, so the measured price today is zero.
#
# Offer A's rung 4 still ships: a sentence that names the capability and
# says what it does IN LICENSED WORDS passes, which is what `licensed_names`
# was built to protect. What no longer ships is naming it while saying
# something else.

#: Closed-class GRAMMATICAL words, dropped before coverage is counted.
#: Function words, not subject matter: they carry no claim in either text,
#: and leaving them in would let "in the moment" score 2 of 4 covered on the
#: strength of "in" and "the". Deliberately a CLOSED class - every word here
#: is a determiner, pronoun, preposition, conjunction, auxiliary or modal,
#: which is what keeps this from becoming a semantic list somebody extends.
_FUNCTION_WORDS = frozenset(
    "a an the this that these those there here it its it's their them they "
    "you your yours we us our ours i me my mine he she his her who whom "
    "whose which what when where why how "
    "am is are was were be been being get gets got "
    "do does did done doing have has had having "
    "can could will would shall should may might must let lets "
    "of in on at to for from by with without within into onto over under "
    "about across after before during through between among against as "
    # Subordinating conjunctions. They became clause SPLIT points for
    # bypass 9, which removes them from every clause - but the
    # whole-sentence unit still saw them, so a refusal could be reported
    # with "since" or "although" named as a word the page text does not
    # carry. A conjunction is not a claim, and a refusal whose evidence is
    # a conjunction is a refusal nobody can act on.
    "since whenever wherever unless until though although whereby whilst "
    "whereas plus "
    "and or but so if then than because while both each any all some more "
    "most such no not only just also too very own else other others "
    "up down out off back again further once now ever never "
    "s t re ve ll d m".split()
)

#: THE RATIO IS RETIRED. BYPASS 10, reported 2026-10-01.
#:
#: It was 0.5 - "most of the clause has to be licensed vocabulary" - and it
#: is gone rather than raised, because a ratio is a VOTE and the claim is not
#: one voter among several:
#:
#:   "Report Intelligence monitors your business data."
#:
#: `business` and `data` come straight out of the page text; `monitor` is the
#: entire assertion, and the page text licenses asking and answering, not
#: watching. Two borrowed object nouns outvoted it, 2 of 3, and it shipped.
#:
#: WHAT MAKES THIS ONE DIFFERENT FROM THE NINE BEFORE IT. Those were
#: reachability - a sentence shaped so the rule never looked at it - and
#: could be argued as adversarial. This one is not adversarial at all: it is
#: the sentence a language model writes by default when asked what a feature
#: does. Borrowed nouns are what an overclaim pads itself with, which is
#: bypass 9's move one level down, and the padding wins any vote.
#:
#: SO THE RULE IS NOW: EVERY CONTENT WORD OF AN IN-SCOPE CLAUSE MUST APPEAR
#: IN THE LICENSED TEXT. No threshold to tune, no tokens to weigh, and - the
#: reason this was chosen over identifying the verb - NOTHING TO IDENTIFY.
#: A predicate-head heuristic was built and measured against the same matrix
#: (`tmp/compare.py`, 2026-10-01): it closed the same six escapes at exactly
#: the same three false positives, while adding a positional proxy that nine
#: rounds of this gate say will itself be defeated. Equal cost, strictly more
#: surface. The ratio earns nothing beside this, so it is not kept alongside
#: it - the whole-sentence unit was already removed for the same reason.

#: THERE IS NO CONTENT FLOOR ANY MORE. It was 2, and for three rounds it was
#: the one exemption left in this rule, kept because at a floor of one
#: "Report Intelligence is available." refused - a single content word, and
#: "available" appears in no feature blurb.
#:
#: Option (b) dissolved that. The sentence is a CONTAINMENT claim and the
#: containment authority licenses it, which is the authority that was always
#: the right one for it; the floor had been standing in for a missing
#: authority. So the floor came out, and what it was hiding is now inspected:
#: "Report Intelligence predicts." - one content word, a false product claim -
#: was passing it.
#:
#: What remains is not a floor but the absence of a predicate: a sentence with
#: NO content words beyond the capability's own name asserts nothing, and
#: there is nothing to license.

#: THERE IS NO REFERRING-EXPRESSION LIST ANY MORE. BYPASS 12 killed it.
#:
#: It was a closed set of pronouns - it, its, they, them, their, this, that,
#: these, those, which, who, whose - and the sentence that walked through was
#: a definite noun phrase carrying no pronoun at all:
#:
#:   "Report Intelligence is available. The feature watches your margins
#:    in real time."                                              PASSED
#:   "Report Intelligence is available. The tool predicts churn."  PASSED
#:
#: while "This capability monitors spend" was refused, and "The module flags
#: overruns as they happen" was refused only BY ACCIDENT - "they" appears in
#: "as they happen". A list that catches by accident is worse than one that
#: misses, because nobody can predict it.
#:
#: TWELVE ROUNDS, AND EVERY ONE WAS A CLOSED-CLASS LIST STANDING IN FOR A
#: LANGUAGE FACT: sentence position, the fronted-PP list, the pronoun window,
#: the predicate splitter, the subordinator list, and finally this. Each list
#: is finite and the language is not. So this one is not extended - it is
#: deleted, and scope is decided without enumerating anything:
#:
#:   ONCE A CAPABILITY IS NAMED IN A MESSAGE, EVERY LATER SENTENCE OF THAT
#:   MESSAGE IS IN SCOPE FOR IT, UNTIL ANOTHER CAPABILITY IS NAMED.
#:
#: PER MESSAGE IS WHAT MAKES THAT AFFORDABLE, and it was measured rather than
#: assumed. Across the whole sequence pooled - which is how `check_batch` used
#: to hand copy to this rule - sticky scope refused 52 extra sentences in the
#: seven real sequences that name a capability, and they were greetings, CTAs
#: and research openers: "Hi <first name>, Ivan here at Productive", "Sent you a
#: note by email too", "Would a quick example be useful?". Unusable.
#:
#: Reset at the message boundary it refuses ONE extra sentence in the whole
#: store - "No guesswork, just the metrics in front of you as things change" -
#: which is a real-time claim and a true positive. A reader reads one message
#: at a time and a referent does not survive a nine-day gap, so the message is
#: the right scope unit; the pooling was the defect, not the stickiness.
#: `check_batch` now calls this rule once per surface for that reason.


def _stem(word):
    """Crude, symmetric morphology. Applied to BOTH texts or to neither.

    Not a stemmer with opinions - plural and participle endings only, so
    "questions"/"question" and "delivers"/"deliver" are one token. It is
    applied identically to the copy and to the licensed text, so it can
    make a match easier but can never make one side mean something the
    other does not.
    """
    w = str(word or "").lower()
    if w.endswith("'s"):
        w = w[:-2]
    for suffix, keep in (("ies", 1), ("ing", 3), ("ed", 2), ("es", 2),
                         ("s", 1)):
        if not w.endswith(suffix) or len(w) - len(suffix) < 3:
            continue
        if suffix == "ies":
            return w[:-3] + "y"
        if suffix in ("s", "es") and w.endswith("ss"):
            continue
        return w[:-keep] if keep != 3 else w[:-3]
    return w


def _content_tokens(text, drop=frozenset()):
    """Stemmed content words: no function words, no `drop`, in order."""
    out = []
    for raw in _WORD.findall(str(text or "").lower()):
        if raw in _FUNCTION_WORDS:
            continue
        stem = _stem(raw)
        if not stem or stem in drop:
            continue
        out.append(stem)
    return out


def _named_in(sentence, names):
    """The longest capability name appearing ANYWHERE in this sentence.

    Position is not consulted. Under the inverted default the question is
    only whether the sentence is in scope; what grammatical slot the name
    occupies was the whole of the old shape machinery and the whole of the
    attack surface.
    """
    low = str(sentence or "").lower()
    found = [n for n in names if str(n or "").strip().lower() in low]
    return max(found, key=lambda n: len(str(n))) if found else None


#: WHERE ONE PREDICATE ENDS AND THE NEXT BEGINS.
#:
#: BYPASS 4, reported 2026-10-01 and reproduced. It is the one worth thinking
#: hardest about, because unlike the other three the sentence WAS inspected
#: and the coverage test itself let it through:
#:
#:   "Report Intelligence understands your business data and predicts churn."
#:
#: understands / business / data are all licensed; predicts / churn are not.
#: Three covered of five is 60%, over the bar, so an entirely unlicensed
#: SECOND CLAIM rode in on the licensed vocabulary of the first. A ratio over
#: a whole sentence buys tolerance for paraphrase and pays for it by letting
#: a conjoined fabrication average itself down.
#:
#: THE FIX IS THE UNIT, NOT THE THRESHOLD. Raising the bar to 100% would
#: refuse the positive control ("questions", "answer" are honest words that
#: are not in the page text), and the honest cost already pinned in
#: `TheMeasuredCostOfFailingClosed` would grow without bound. Instead the
#: coverage test runs on each COORDINATED PREDICATE as well as on the whole
#: sentence, and BOTH must pass. Paraphrase tolerance survives inside a
#: clause, where it belongs; a conjoined claim now has to stand on its own
#: vocabulary, because averaging across the conjunction is exactly the move
#: being refused.
#:
#: BYPASS 9 AND THE CLAUSE SPLITTER IT PRODUCED, both recorded because the
#: splitter is GONE and the reason it went matters more than the splitter did.
#:
#: Bypass 9 was an overclaim riding in a subordinate clause:
#:
#:   "Report Intelligence delivers plain language insights about your
#:    business data that anticipate customer defection."
#:
#: deliver / plain / language / insight / business / data are six content
#: stems lifted from the page text; anticipate / customer / defection are the
#: claim. Six of nine was 67%, over the 50% bar, and with no comma or
#: coordinator anywhere the clause unit saw one clause identical to the
#: sentence and agreed with it. The answer then was to split on subordinators
#: so each clause had to stand on its own vocabulary.
#:
#: BYPASS 10 MADE THE SPLITTER REDUNDANT, in the same way it made the
#: whole-sentence unit redundant one round earlier. Once EVERY content word
#: of a clause must be licensed, and clauses partition the sentence's content
#: words, "every clause fully licensed" IS "every sentence word licensed" -
#: the split cannot change a verdict. Measured 2026-10-01: deleting it
#: changed nothing on 28 probes, 79 tests and the production store.
#:
#: What the splitter's existence still buys is the word list below, now part
#: of `_FUNCTION_WORDS`: a subordinator is a conjunction, not a claim, and a
#: refusal whose evidence is the word "although" is a refusal nobody can act
#: on. That is the only part of the mechanism that survives.
#:
#: A SPLITTER WOULD HAVE TO COME BACK with any ratio, floor or per-unit
#: threshold, because all three re-create the averaging it existed to stop.


def _uncovered(tokens, licensed):
    """The tokens of this unit that the licensed text does not carry."""
    return [t for t in tokens if t not in licensed]


def _coverage_failure(sentence, licensed, name_tokens):
    """The words of this sentence the capability's licensed text does not
    carry, or None when every one of them is licensed.

    ONE RULE, AND IT IS THE WHOLE RULE: every content word of an in-scope
    sentence must appear in that capability's `page_text`. No positions, no
    clause units, no thresholds, no weights, nothing identified.

    ## HOW IT GOT THIS SMALL, WHICH IS THE POINT

    Ten bypasses. The first eight were REACHABILITY - a sentence shaped so
    the rule never looked at it - and each was answered by widening what the
    rule looked at, until the inversion removed the question entirely: in
    scope is any sentence naming a capability or referring back to one.

    The last two were the rule itself, and both were the same move: an
    unlicensed claim averaging itself down against licensed words. Bypass 9
    did it across a subordinate clause; bypass 10 did it inside one, where
    two borrowed object nouns outvoted the verb carrying the entire claim
    ("Report Intelligence MONITORS your business data" - business and data
    are the page text's, monitors is not).

    Each answer made the previous machinery redundant, and each piece was
    DELETED rather than kept as a comfort:

    - the whole-sentence unit, once a clause was judged at any length;
    - the clause splitter and its subordinator list, once every word had to
      be licensed - clauses partition the sentence's words, so "every clause
      licensed" IS "every word licensed" and the split cannot change a
      verdict;
    - the 50% ratio itself, retired rather than raised.

    All three deletions were established by mutation, not argument: deleting
    each changed no verdict on the probe matrix, the test module or the
    production store.

    ## WHAT WOULD BRING THEM BACK

    ANY ratio, floor or per-unit threshold re-creates averaging, and clause
    splitting plus a whole-sentence unit would have to return with it. This
    is the one place to look if that is ever proposed.

    ## WHAT IT COSTS, AND THE FLOOR THAT IS NOT HERE

    Every content word licensed means honest paraphrase is refused when it
    reaches for a word the page text does not use - "questions" where the
    page says "anything", "gives" where it says "get". Three such sentences
    are pinned in `TheMeasuredCostOfEveryWordLicensed`, each with a licensed
    rewrite, and zero of them occur in the production store.

    The one exemption is the CALLER's content floor, which keeps "Report
    Intelligence is available." shippable. It is not here because it answers
    a different question - whether the sentence characterises the capability
    at all - and review named it as the line this gate may not cross.
    """
    tokens = _content_tokens(sentence, drop=name_tokens)
    return _uncovered(tokens, licensed) or None


def capability_surfaces(lead):
    """Everything a prospect reads, AS SEPARATE MESSAGES.

    One entry per thing somebody reads in one sitting: each email (its
    subject and body together, because they arrive together), each P.S. line
    and each LinkedIn message. `other_prospect_text` deliberately flattens
    those into one string for the rules that want a single haystack; this
    keeps them apart for the one rule whose scope must not cross a send.
    """
    out = []
    for step in steps_of(lead):
        subject, body = _subject(step), _body(step)
        joined = "%s. %s" % (str(subject or "").strip(), str(body or ""))
        if joined.strip(". "):
            out.append(joined)
    ps = (lead or {}).get("ps") or {}
    if isinstance(ps, dict):
        out.extend(str(v) for v in ps.values() if str(v or "").strip())
    elif ps:
        out.append(str(ps))
    li = (lead or {}).get("linkedin") or {}
    if isinstance(li, dict):
        out.extend(str(v) for v in li.values() if str(v or "").strip())
    return out


def capability_description_violations(text, pack):
    """Descriptions of a licensed capability its page text does not support.

    Returns a list of `(rule_name, message)` tuples, the same shape
    `case_study_violations` returns. Empty means no capability was
    characterised, or every characterisation traced.

    The message names the capability AND quotes the licensed text, because
    the person regenerating the draft has to see what they are allowed to
    say, not merely that they said something else.
    """
    caps = licensed_capabilities(pack)
    if not caps:
        return []
    names = sorted(caps, key=lambda n: -len(str(n)))
    name_tokens = {t for n in names for t in _content_tokens(n)}

    # THE CONTAINMENT AUTHORITY, built once. `None` when the pack carries no
    # offer containment text at all, which disables the second authority
    # rather than defaulting it to something - a capability listed by no
    # offer is licensed for containment by nothing.
    _offer_words = offer_containment_text(pack)
    offer_licensed = (set(_content_tokens(_offer_words)) | _CONTAINMENT_WORDS
                      if _offer_words.strip() else None)

    violations = []
    seen = set()
    current = None
    for sentence in _split_sentences(text):
        # SCOPE, AND NOTHING ELSE, IS WHAT THIS DECIDES.
        #
        # CONTINUE 1 of 4, and the only one that can let an unexamined
        # sentence past: nothing in it refers to a licensed capability, so
        # there is no attribution to verify. A sentence with no name and no
        # referring word cannot be a claim about a capability.
        subject = _named_in(sentence, names)
        if subject is None:
            if current is None:
                continue               # nothing named yet in this message
            subject = current          # sticky: no list consulted
        current = subject

        # NO LICENSED TEXT MEANS NOTHING MAY BE PREDICATED OF IT, AT ANY
        # LENGTH - AND THIS IS DECIDED FIRST.
        #
        # BYPASS 5: the content-word floor ran BEFORE this branch, so
        # "Productive includes SmartCap. It predicts churn." was trimmed away
        # on length and never reached the refusal built for exactly it. THIRD
        # time this branch was bypassed rather than reached (3 and 5 were the
        # others), so it sits in front of every count. The question it
        # answers is about the CAPABILITY, not the sentence.
        #
        # CONTINUE 2 of 4: the sentence has already been refused here, so
        # falling through to the coverage test would only report it twice.
        page_text = caps.get(subject)
        if not str(page_text or "").strip():
            key = ("missing", subject)
            if key not in seen:
                seen.add(key)
                violations.append((
                    "capability_description_unsupported",
                    "'%s' is described as %r and no licensed page text is "
                    "stored for it - the description cannot be verified"
                    % (subject, sentence[:160])))
            continue

        # NO PREDICATE, NOTHING TO LICENSE. A sentence whose only content
        # words are the capability's own name asserts nothing about it.
        # This is NOT the old content floor of two - that is gone, and
        # "Report Intelligence predicts." is now refused.
        content = _content_tokens(sentence, drop=name_tokens)
        if not content:
            continue                   # nothing predicated at all

        # The capability's OWN name is dropped from the sentence's
        # content rather than added to the licensed set. The two were
        # both present and only one can matter: a dropped token can
        # never need licensing. The DROP is the load-bearing half,
        # because the caller counts the same dropped list to decide
        # whether anything is predicated at all. Found by a mutation
        # that removed the drop and broke nothing.
        licensed = set(_content_tokens(page_text))
        uncovered = _coverage_failure(sentence, licensed, name_tokens)
        if uncovered is None:
            continue                       # CONTINUE 4 of 5: it traced

        # THE SECOND AUTHORITY. The sentence is not supported as a
        # description of what the capability DOES; it may still be a claim
        # about what the OFFER CONTAINS, and that has a different licence.
        #
        # ALL OR NOTHING, PER AUTHORITY, AND THAT IS WHAT STOPS THE DOOR
        # OPENING WIDER THAN THE OFFER FILE. The two vocabularies are never
        # unioned: a sentence passes because EVERY one of its words is
        # licensed by page_text, or because every one is licensed by the
        # offer, never because some are licensed by each. So
        #
        #   "The premium trial includes Report Intelligence"        passes
        #   "The premium trial includes Report Intelligence,
        #    which predicts churn"                                 REFUSED
        #
        # - the second mixes containment vocabulary with a behaviour claim
        # and satisfies neither authority whole. Naming the trial licenses
        # the containment and nothing that follows it.
        #
        # CONTINUE 5 of 6.
        if offer_licensed is not None:
            if _coverage_failure(sentence, offer_licensed, name_tokens) is None:
                continue

        key = ("unsupported", subject, sentence[:160])
        if key in seen:
            continue                       # CONTINUE 6 of 6: already
                                           # refused, do not report twice.
                                           # Reached only AFTER the sentence
                                           # has been judged unsupported, so
                                           # it cannot let one past.
        seen.add(key)
        violations.append((
            "capability_description_unsupported",
            "'%s' is described as %r, which its licensed page text does "
            "not support. The licensed text says only: %r. Not in it: %s"
            % (subject, sentence[:160], str(page_text),
               ", ".join(sorted(set(uncovered))))))
    return violations


# ------------------------------------------------- service-list P.S. (TASK-918)
#
# THE DEFECT: a P.S. line generically enumerates the prospect's own
# services - "Their services include retail merchandising, product
# training, and display installation." - and nothing refuses it. The P.S.
# carries no relevance to the outreach: it restates what the prospect
# already knows about themselves, which is the opposite of personalisation.
#
# WHY THIS IS A LINT RULE, NOT A CLAIM CHECK. The service list is not an
# unsupported claim - it is factually supported by the prospect's own
# website. It is worthless: a generic enumeration that carries no
# relevance and no evidence of reading. The copylint layer is the right
# home because it already refuses copy-quality failures that are not
# claim failures (buzzwords, dashes, finality-before-last).
#
# READS lead["ps"] ONLY. The existing `other_prospect_text` helper merges
# P.S. lines with LinkedIn messages into one string. Using it would apply
# the service-list heuristic to LinkedIn notes, where listing services
# in a body can be contextually legitimate. This rule reads `lead["ps"]`
# directly and must not touch email bodies.
#
# THE CLASS, NOT A PREFIX. The rule targets generic enumeration of the
# prospect's services, not one opening phrase. "Their services include",
# "You offer", "Your services include", "I saw you provide", "Company
# offers" - all are the same class: a verb introducing a list of generic
# service terms. The rule matches the pattern, not the words.
#
# WHAT THIS IS NOT. A specific, evidenced P.S. is allowed. "Since 2022,
# 2020 Companies has supported Christ's Haven through donations and
# volunteerism" names a specific entity, carries a date, and describes a
# specific activity. The rule does not require a date or a charity - it
# requires that the P.S. is NOT a generic service enumeration.

# Service-enumeration verbs. These introduce a list of what the prospect
# offers/does. Matched on the stem with optional inflection suffixes.
_SERVICE_ENUM_VERBS = re.compile(
    r"\b(?:includ(?:e|es|ed|ing)"
    r"|offer(?:s|ed|ing)?"
    r"|provid(?:e|es|ed|ing)"
    r"|speciali[sz]e(?:s|d)?"
    r"|cover(?:s|ed|ing)?"
    r"|deliver(?:s|ed|ing)?"
    r"|focus(?:es|ed|ing)?"
    r"|deal(?:s|t|ing)?"
    r"|handle(?:s|d|ing)?"
    r"|manag(?:e|es|ed|ing))\b", re.I)

# Generic service/business terms. These are the kinds of things that
# appear in a service list: broad categories, not specific offerings.
_GENERIC_SERVICE_TERMS = (
    "merchandising", "training", "installation", "sales", "marketing",
    "support", "consulting", "advisory", "management", "logistics",
    "recruitment", "staffing", "design", "development", "engineering",
    "analytics", "research", "operations", "maintenance", "repair",
    "cleaning", "catering", "security", "transport", "delivery",
    "retail", "wholesale", "distribution", "manufacturing", "production",
    "accounting", "bookkeeping", "payroll", "legal", "compliance",
    "insurance", "banking", "finance", "hr", "it", "software",
    "hardware", "networking", "hosting", "cloud", "data",
)

# A list of 2+ terms connected by commas and/or "and"/"or". This catches
# "X, Y, and Z", "X and Y", and "X, Y" patterns.
_COMMA_LIST_RE = re.compile(
    r"\b([a-z][a-z\-]+)"        # first term
    r"(?:"
    r"(?:\s*,\s*[a-z][a-z\-]+)" # comma + second term
    r"|(?:\s+and\s+[a-z][a-z\-]+)"  # or "and" + second term
    r"|(?:\s+or\s+[a-z][a-z\-]+)"   # or "or" + second term
    r")"
    r"(?:\s*(?:,?\s*(?:and|or)\s+[a-z][a-z\-]+)" # optional more terms
    r"|(?:\s*,\s*[a-z][a-z\-]+)*)"  # or more comma-separated terms
    , re.I)


# TASK-919: prospect-referring subjects. The service-list rule fires when
# the P.S. is ABOUT THE PROSPECT and consists substantially of a service
# enumeration. A prospect-referring pronoun signals that the P.S. is
# about them.
_PROSPECT_SUBJECT_RE = re.compile(
    r"\b(?:you|your|yours|yourself|yourselves|they|them|their)\b", re.I)

# TASK-919: head nouns that service terms modify as descriptors rather
# than listing as services. "a premier sales and marketing agency" uses
# the terms as adjectives, not as an enumeration. If the service list is
# followed by one of these within a short window, the P.S. is describing
# identity, not enumerating services.
_DESCRIPTOR_HEAD_NOUNS_RE = re.compile(
    r"\b(?:agency|agencies|company|companies|firm|firms|studio|studios"
    r"|provider|providers|partner|partners|consultancy|consultancies"
    r"|practice|practices|organisation|organizations|organisation"
    r"|business|businesses|group|groups|team|teams)\b", re.I)


def service_list_in_ps(lead):
    """Does the P.S. field generically enumerate the prospect's services?

    Returns True when the P.S. is about the prospect and consists
    substantially of an enumeration of 2+ generic service terms.

    TASK-919: the connecting verb is not the signal. The rule now fires on
    EITHER a service-enumeration verb OR a prospect-referring subject, plus
    a list of 2+ generic service terms that are NOT descriptors modifying
    a head noun (e.g. "sales and marketing agency" is allowed).

    Reads lead["ps"] ONLY - not LinkedIn, not email bodies.
    """
    ps = (lead or {}).get("ps")
    if not ps:
        return False
    if isinstance(ps, dict):
        text = " ".join(str(v) for v in ps.values() if v)
    else:
        text = str(ps)
    if not text.strip():
        return False
    low = text.lower()

    # TASK-919: verb OR prospect subject (either signals the P.S. is
    # about what the prospect does/offers).
    has_enum_verb = bool(_SERVICE_ENUM_VERBS.search(low))
    has_prospect_subject = bool(_PROSPECT_SUBJECT_RE.search(low))
    if not (has_enum_verb or has_prospect_subject):
        return False

    # Check for a list of 2+ terms
    list_match = _COMMA_LIST_RE.search(low)
    if not list_match:
        return False

    # Check that the listed terms are generic service terms (not specific)
    list_text = low[list_match.start():]
    for sentence in re.split(r"(?<=[.!?])\s+", list_text):
        if not sentence.strip():
            continue
        generic_terms_found = []
        for term in _GENERIC_SERVICE_TERMS:
            for m in re.finditer(r"\b" + re.escape(term) + r"\b", sentence):
                generic_terms_found.append(m)
        if len(generic_terms_found) < 2:
            continue

        # TASK-919: check that the terms are not descriptors modifying a
        # head noun. If a head noun follows the last service term within
        # a short window, the terms are adjectives, not a service list.
        last_end = max(m.end() for m in generic_terms_found)
        after_terms = sentence[last_end:last_end + 60]
        if _DESCRIPTOR_HEAD_NOUNS_RE.search(after_terms):
            continue

        return True
    return False


# TASK-921 C: fragment-list subjects.
#
# THE DEFECT: a step subject is three or more bare noun-phrase fragments
# concatenated with commas or slashes: "margin visibility, budget burn,
# resource decisions" or "profitability / utilisation / capacity". Nothing
# gates subject quality, so these keyword-fragment lists pass through.
#
# THE STRUCTURE: three or more bare noun-phrase fragments with no
# connecting function word (preposition, verb, clause). Punctuation alone
# is neither sufficient nor necessary - four of six allowed subjects
# contain a comma, colon or full stop. The refused ones lack grammatical
# glue: "during", "vs.", "before", "about", "how you track".
#
# DETECTION: split the subject by commas and slashes. If 3+ parts and
# every part is a bare noun phrase (no function words), refuse.
#
# FUNCTION WORDS that mark a part as NOT bare: prepositions, verbs,
# question words, relative pronouns. Articles (a/an/the) and possessives
# (my/our/your) are NOT disqualifying - "the margin" is still a bare NP.
_FRAGMENT_FUNCTION_WORDS = re.compile(
    r"\b(?:"
    # Prepositions (common ones that would appear in a connected phrase)
    r"about|above|after|against|along|among|around|at|before|behind"
    r"|below|beneath|beside|between|beyond|by|during|except|for|from"
    r"|in|inside|into|like|near|of|off|on|onto|out|over|past|since"
    r"|through|throughout|to|toward|under|underneath|until|up|upon"
    r"|versus|via|with|within|without"
    # Question/relative words (introduce clauses)
    r"|how|what|which|who|whom|whose|where|when|why"
    # Common verbs that indicate a connected phrase
    r"|is|are|was|were|be|been|being|has|have|had|do|does|did"
    r"|will|would|could|should|may|might|can|shall|must"
    r"|vs\.?"
    r")\b", re.I)


def fragment_list_subject(subject):
    """TASK-921 C: is this subject a list of bare noun-phrase fragments?

    Returns True when the subject consists of 3+ comma/slash-separated
    noun phrases with no connecting function word between them.
    """
    if not subject:
        return False
    text = str(subject).strip()
    if not text:
        return False
    parts = re.split(r'\s*[,/|]\s*', text)
    parts = [p.strip() for p in parts if p.strip()]
    if len(parts) < 3:
        return False
    for part in parts:
        if _FRAGMENT_FUNCTION_WORDS.search(part):
            return False
    return True


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
    ("cta_link_not_allowlisted",
     "a prospect-facing URL is not on the allowed CTA link list"),
    ("cta_link_dead",
     "a CTA link does not resolve (HEAD/GET non-2xx or DNS failure)"),
    ("cta_link_unverified",
     "a CTA link could not be checked (network error or timeout)"),
    ("case_study_unsupported",
     "a case-study claim is not on the stored page (TASK-365)"),
    ("case_study_multiple",
     "more than one case study named in a single message (TASK-365)"),
    ("capability_description_unsupported",
     "copy describes what a licensed capability does in terms its licensed "
     "page text does not support (TASK-922)"),
    ("missing_opt_out",
     "an email body carries no opt-out line (TASK-904)"),
    ("duplicate_opt_out",
     "an email body carries more than one opt-out line (TASK-904)"),
    ("service_list_ps",
     "the P.S. generically enumerates the prospect's own services (TASK-918)"),
    ("fragment_list_subject",
     "a step subject is a list of bare noun-phrase fragments (TASK-921)"),
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


#: DEMOTIONS: RULES THAT REPORT INSTEAD OF REFUSING, WITH EXPIRY.
#:
#: Each entry is (rule_name, until_date, why, who_granted). A demotion
#: stops applying the day after its until_date - mechanical, not remembered.
#: Empty is the normal state; a demotion is an operator exception and
#: expires on its own deadline whether or not anyone renews it.
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
#: WHY THIS IS DATA AND NOT AN `if`. CLAUDE.md: "Never widen a lint rule to
#: make a draft pass." This does not widen the rule - it still fires, is
#: still counted, and every offender is still named in the report. It changes
#: only whether firing stops the push, and the next demotion is recorded the
#: same way and is equally visible. A demotion that outlives its deadline
#: silently reverts - no human has to remember to edit a frozenset.
DEMOTIONS = (
    ("step1_without_pack_fact", "2026-09-28",
     "PROOF MODE - leads in campaigns, proof first",
     "Zvonimir, 2026-09-25"),
)


def warning_rules(today=None):
    """The rules that warn instead of refusing, as of a date.

    A demotion carries its own expiry and stops applying after it. Pass
    `today` as an ISO date string to test behaviour at a point in time;
    omit it to use the current date.

    Returns a frozenset of rule names. An expired demotion is absent from
    the set, so the rule reverts to refusing automatically.
    """
    if today is None:
        from datetime import date
        today = date.today().isoformat()
    return frozenset(
        rule for rule, until, _why, _who in DEMOTIONS
        if today <= until
    )


#: Backward-compatible alias. Code that checked `name in WARNING_RULES`
#: now checks `name in warning_rules()` at call time, so the set reflects
#: the current date rather than the date the module was imported.
class _WarningRulesCompat:
    """A frozenset-like object that evaluates demotions at call time."""
    def __contains__(self, item):
        return item in warning_rules()
    def __iter__(self):
        return iter(warning_rules())
    def __bool__(self):
        return bool(warning_rules())
    def __len__(self):
        return len(warning_rules())
    def __repr__(self):
        return repr(warning_rules())
    def __eq__(self, other):
        return warning_rules() == other
    def __hash__(self):
        return hash(warning_rules())


WARNING_RULES = _WarningRulesCompat()


def check_batch(leads, packs=None, steps_expected=STEPS_EXPECTED, today=None):
    """`{refused, leads, clean, counts, offenders, rules}` for one batch.

    `packs` maps a lead id to its research pack. A lead with NO pack is not
    quietly excused: it cannot open step 1 with a supported line, so it
    fires the first rule. A batch generated before the packs were built is
    exactly the batch this is for.

    `today` is an ISO date string for evaluating demotion expiry. Omit it
    to use the current date. A demotion that has passed its deadline is
    absent from the warning set, so the rule reverts to refusing.
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
        subject_list = [str(_subject(s) or "") for s in steps]
        subjects = "\n".join(subject_list)
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
        # TASK-378: untraceable, buzzwords and finality were pointed at
        # `whole` (email bodies only). A LinkedIn connect note or a P.S.
        # line fabricating a claim passed silently. Now all three see
        # `rendered` — everything the prospect reads — with the last-body
        # exemption preserved for finality.
        if untraceable(rendered, pack):
            offenders["untraceable_company_claim"].append(lead_id)
        # OVER EVERYTHING THE PROSPECT READS, not just the email bodies.
        # Operator, 2026-09-25: dashes are banned in email bodies, subjects,
        # P.S. lines and every LinkedIn message, and the rule REFUSES.
        if DASH_RE.search(rendered):
            offenders["dash"].append(lead_id)
        if buzzwords_in(rendered):
            offenders["buzzword"].append(lead_id)
        # EVERY STEP BUT THE LAST, plus LinkedIn/PS text.
        #
        # The last email body is exempt (it IS the last step), but a
        # LinkedIn message or P.S. line claiming finality while more
        # messages follow is the same bug in a different channel.
        #
        # AND SO IS THE LAST STEP'S SUBJECT, which it was not until now.
        # `subjects` is one pooled blob, so em5's own subject was read as
        # "a step claims to be the last one while a later step still
        # sends" when no later step sends - the rule's own name, its own
        # message and the last-body exemption three lines up all say that
        # is wrong. `copyprompts` asks the writer for a short breakup
        # subject on em5, so the surface has to be read PER STEP.
        #
        # This is the exemption the rule already states, applied
        # symmetrically. It is not a widening: an EARLIER step's subject,
        # every P.S. line and every LinkedIn message are still read in
        # full, and `FINALITY_RE` is untouched.
        non_final = "\n".join(
            [str(b) for b in bodies[:-1]] + subject_list[:-1] + [extra]
        )
        if FINALITY_RE.search(non_final):
            offenders["finality_before_last_step"].append(lead_id)

        # CASE-STUDY CLAIMS (TASK-365). Every figure must trace to the
        # stored page, and only one study per message.
        cs_violations = case_study_violations(rendered)
        for rule_name, _msg in cs_violations:
            if lead_id not in offenders[rule_name]:
                offenders[rule_name].append(lead_id)

        # TASK-922: A DESCRIBED CAPABILITY TRACES TO ITS LICENSED TEXT.
        # `licensed_names` exempts the NAME from the specifics check; this
        # is what licenses the DESCRIPTION.
        #
        # ONCE PER SURFACE, NOT ONCE OVER `rendered`, and that is load
        # bearing rather than tidy. Scope inside the rule is STICKY - a
        # capability named in a sentence puts every later sentence in scope
        # (see the comment where the referring-expression list used to be) -
        # and `rendered` is every body, subject, P.S. and LinkedIn message of
        # the whole sequence concatenated. Pooled, a capability named in em4
        # put the em1 greeting in scope: measured 2026-10-01, 52 extra
        # sentences refused across the seven real sequences that name one,
        # and they were greetings, CTAs and research openers. Per surface it
        # is ONE extra sentence in the whole store, and that one is a
        # real-time claim.
        #
        # A reader reads one message at a time and a referent does not
        # survive a nine-day gap, so the message is the honest scope unit.
        # Every surface is still checked - nothing is skipped by this, the
        # boundaries are simply respected.
        for surface in capability_surfaces(lead):
            for rule_name, _msg in capability_description_violations(
                    surface, pack):
                if lead_id not in offenders[rule_name]:
                    offenders[rule_name].append(lead_id)

        # OPT-OUT PRESENCE (TASK-904). Every email body must carry
        # exactly one opt-out line. The renderer appends one, so the
        # check counts occurrences AFTER appending: zero in the raw body
        # becomes one after append (pass), one in the raw body becomes
        # two (duplicate - the generator included one AND the renderer
        # adds another). The check runs on individual bodies, not the
        # pooled `rendered` blob, because each email is a separate send.
        for body_text in bodies:
            rendered_body = optout.append_opt_out(body_text)
            count = str(rendered_body or "").count(optout.OPT_OUT_LINE)
            if count == 0:
                if lead_id not in offenders["missing_opt_out"]:
                    offenders["missing_opt_out"].append(lead_id)
            elif count > 1:
                if lead_id not in offenders["duplicate_opt_out"]:
                    offenders["duplicate_opt_out"].append(lead_id)

        # TASK-918: SERVICE-LIST P.S. Reads lead["ps"] ONLY - not
        # LinkedIn, not email bodies. A generic enumeration of the
        # prospect's own services carries no relevance and is refused.
        if service_list_in_ps(lead):
            if lead_id not in offenders["service_list_ps"]:
                offenders["service_list_ps"].append(lead_id)

        # TASK-921 C: FRAGMENT-LIST SUBJECT. A step subject that is 3+
        # bare noun-phrase fragments with no connecting function word.
        # "margin visibility, budget burn, resource decisions" is a
        # keyword list, not a real subject.
        for subj in subject_list:
            if fragment_list_subject(subj):
                if lead_id not in offenders["fragment_list_subject"]:
                    offenders["fragment_list_subject"].append(lead_id)
                break

    # CTA LINK CHECK - BATCH LEVEL, NOT PER LEAD.
    #
    # URLs are shared across a cohort (one booking_link, one CTA), so
    # checking per-lead would fire N identical network requests for one
    # link. Instead: collect every URL from every lead, check each distinct
    # URL once, then map failures back to the leads that carry them.
    #
    # The allowlist check is a string comparison and runs always, including
    # offline and in the test suite. The HEAD/GET resolution is the part
    # that needs the network and is controlled by CTA_LINK_SKIP_REASON.
    all_urls = {}
    for lead in leads:
        lead_id = str(lead.get("id") or lead.get("contact") or "?")
        steps = steps_of(lead)
        texts = [_body(s) for s in steps]
        texts.append(str(other_prospect_text(lead) or ""))
        for url in extract_urls("\n".join(texts)):
            all_urls.setdefault(url, []).append(lead_id)

    skip = CTA_LINK_SKIP_REASON
    do_resolve = not skip
    cta = check_cta_links(list(all_urls.keys()), resolve=do_resolve)

    for url in cta["not_allowlisted"]:
        for lid in all_urls.get(url, []):
            if lid not in offenders["cta_link_not_allowlisted"]:
                offenders["cta_link_not_allowlisted"].append(lid)
    for url in cta["dead"]:
        for lid in all_urls.get(url, []):
            if lid not in offenders["cta_link_dead"]:
                offenders["cta_link_dead"].append(lid)
    for url in cta["unverified"]:
        for lid in all_urls.get(url, []):
            if lid not in offenders["cta_link_unverified"]:
                offenders["cta_link_unverified"].append(lid)

    counts = {name: len(offenders[name]) for name, _ in RULES}
    active_warnings = warning_rules(today=today)
    dirty, warned = set(), set()
    for name, ids in offenders.items():
        (warned if name in active_warnings else dirty).update(ids)
    return {
        "leads": len(leads),
        "clean": len(leads) - len(dirty) - len(warned - dirty),
        "refused": bool(dirty),
        "warned": len(warned - dirty),
        "warning_rules": sorted(active_warnings),
        "counts": counts,
        "offenders": {k: sorted(v) for k, v in offenders.items()},
        "rules": dict(RULES),
        "cta_link_skip_reason": skip or None,
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
    if report.get("cta_link_skip_reason"):
        out.append("  CTA LINK RESOLUTION SKIPPED: %s"
                   % report["cta_link_skip_reason"])
    return out


# ---------------------------------------------------------------- CTA links
#
# TASK-354. A prospect-facing URL that is not on the allowlist is refused
# regardless of whether it resolves. A link on the allowlist that does not
# resolve (HEAD 200) is refused as dead. A link that cannot be checked at
# all (network failure, timeout) is refused as unverified - a DISTINCT rule
# name, never folded into dead and never folded into a pass.
#
# The allowlist check is a string comparison and needs no network. It runs
# ALWAYS, including in the test suite and offline. The resolution check
# (HEAD/GET) is the part that needs the network and is opt-in.

#: The ONLY prospect-facing URL allowed in Productive outreach.
#: Operator decision, 2026-09-26. An allowlist of exactly one.
CTA_LINK_ALLOWLIST = frozenset({
    "https://productive.io/get-started/",
})

#: Module-global off switch for the network resolution half of the CTA link
#: check. Set to a non-empty, human-readable reason string to skip HEAD/GET
#: resolution while keeping the allowlist check enforced.
#:
#: WHO MAY SET IT: the operator, deliberately, for a stated reason (offline
#: run, CI without network, etc.). It must be visible in the lint report -
#: a skip that is not named in the output is a silent pass, and a gate with
#: an undocumented off switch is not a gate.
#:
#: THE ALLOWLIST STILL RUNS. Setting this does NOT disable the allowlist
#: check. A non-allowlisted URL is refused whether or not resolution runs.
CTA_LINK_SKIP_REASON = ""

#: Tests override this to avoid real HTTP calls. Production uses
#: ``_default_resolve_url``.
_URL_RESOLVE_HOOK = None

_URL_RE = re.compile(r"https?://[^\s\"'<>\])}]+")


def extract_urls(text):
    """Every URL in a piece of text, de-duplicated, order preserved.

    Strips trailing punctuation that is likely sentence-ending rather than
    part of the URL.
    """
    found = []
    for match in _URL_RE.finditer(str(text or "")):
        url = match.group(0).rstrip(".,;:!?)")
        if url and url not in found:
            found.append(url)
    return found


def _default_resolve_url(url):
    """HEAD with GET fallback for 405. Follows redirects. 4s timeout.

    Returns ``"pass"`` for 2xx, ``"dead"`` for non-2xx / DNS failure, and
    ``"unverified"`` for transport errors (timeout, no network).

    No credentials, no cookies, no custom headers. A liveness check against
    a public page, nothing more.
    """
    timeout = 4
    try:
        req = urllib.request.Request(url, method="HEAD")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if 200 <= resp.status < 300:
                return "pass"
            return "dead"
    except urllib.error.HTTPError as exc:
        if exc.code == 405:
            try:
                req_get = urllib.request.Request(url)
                with urllib.request.urlopen(req_get, timeout=timeout) as resp:
                    if 200 <= resp.status < 300:
                        return "pass"
                    return "dead"
            except urllib.error.HTTPError:
                return "dead"
            except (urllib.error.URLError, OSError, TimeoutError):
                return "unverified"
        return "dead"
    except (urllib.error.URLError, OSError, TimeoutError):
        return "unverified"


def _resolve_url(url, cache):
    """Resolve a URL, using the cache for deduplication within a batch."""
    if url not in cache:
        resolver = _URL_RESOLVE_HOOK or _default_resolve_url
        cache[url] = resolver(url)
    return cache[url]


def check_cta_links(urls, resolve=True):
    """Check CTA links against the allowlist and (optionally) resolve each.

    Returns a dict with four lists:

    - ``allowlisted``: URLs on the allowlist that resolved (or would, if
      resolution is skipped).
    - ``not_allowlisted``: URLs not on the allowlist. Always refused.
    - ``dead``: Allowlisted URLs that returned non-2xx or DNS failure.
    - ``unverified``: Allowlisted URLs that could not be checked at all.

    The three refusal categories map to three distinct RULES entries and
    must not collapse into one another.
    """
    result = {"allowlisted": [], "not_allowlisted": [],
              "dead": [], "unverified": []}
    seen = set()
    for url in urls:
        if url in seen:
            continue
        seen.add(url)
        if url not in CTA_LINK_ALLOWLIST:
            result["not_allowlisted"].append(url)
            continue
        if not resolve or CTA_LINK_SKIP_REASON:
            result["allowlisted"].append(url)
            continue
        cache = {}
        status = _resolve_url(url, cache)
        if status == "pass":
            result["allowlisted"].append(url)
        elif status == "dead":
            result["dead"].append(url)
        else:
            result["unverified"].append(url)
    return result
