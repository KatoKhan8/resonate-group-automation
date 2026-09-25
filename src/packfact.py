#!/usr/bin/env python3
"""GATE 3. What a personalised line is allowed to quote, and when to HOLD.

    from src import packfact
    verdict = packfact.check_span(span, fact)     # one quoted span
    best = packfact.quotable(fact)                # what MAY be quoted
    if not best:
        ...                                       # HOLD the lead. Do not send.

Operator's standing directive, 2026-09-25, after 64 emails went to real
prospects quoting navigation bars.

## THE FAILURE THIS EXISTS FOR, IN ITS OWN WORDS

Sixty-four emails on campaigns 503, 504 and 505 opened with

    "I was reading the Havas site this week and the line about
     content back to homepage havas investors/shareholders en fr
     is what made me write."

    "...the line about check out a few of our case studies..."

    "...the line about request a demo error: contact form not found..."

Those are the site's own navigation bar, a call-to-action button and a
broken contact form, presented to a stranger as the thing we noticed about
their company. They are not defects of the model that wrote the sentence.
They are what `researchpack.facts.SNIPPET_CHARS = 400` returns: a crawler
takes the first 400 characters of a page, and on 80.9% of pages the first
400 characters are the menu.

## WHY "A COMPLETE SENTENCE WITH A VERB" IS NOT ENOUGH ON ITS OWN

`check out a few of our case studies` has a verb. So does `Book a Meeting`,
`Request a Demo`, `Skip to content` and `Learn how we help agencies grow`.
Every one of them is chrome and every one of them would pass a test that
asks only "is there a verb in here".

Nav chrome is IMPERATIVE and body prose is DECLARATIVE, and that is the
distinction that actually separates them. So the verb has to be a FINITE
verb with a SUBJECT IN FRONT OF IT - `We solve the complexities of
enterprise Oracle environments.` has one; `Check out a few of our case
studies` has a bare imperative at position zero and no subject anywhere.

## AND WHY TERMINAL PUNCTUATION IS LOAD-BEARING

The snippet is cut at 400 characters, mid-word: real cached facts end
`...focused on Oracl`, `...The platform for compliant wor`,
`...Post-Development Su`. A span that runs to the end of the snippet was
truncated by us, so we do not know what it said. A span is only complete if
the SOURCE closed it with `.`, `!` or `?` - a terminator we can see, inside
the text, not at the cut.

That single rule refuses most chrome for free, because a menu has no full
stops in it.

## FAILS CLOSED, AND THE ABSENT FIELD IS NOT A PASS

`check_span` refuses a span with no fact, a fact with no `source_url`, and a
fact whose snippet does not literally contain the span. Lane S found the
shape this is avoiding an hour before this was written: a gate that asks
"does this row have a LinkedIn URL" passed 12,407 of 12,407 rows, because
the supplier had already put a URL in every one of them. Asking whether a
field is non-empty is not asking where its contents came from.

So the question here is never "is there a pack fact". It is "is THIS span a
complete declarative sentence that appears verbatim inside the body of a
page at THIS url" - and if no span in the whole pack can answer it, the
lead is HELD. Generic is not the fallback. There is no fallback.
"""
import re

#: Terminal punctuation. A span that does not end on one of these was cut by
#: `SNIPPET_CHARS`, not closed by its author.
TERMINATORS = ".!?"

#: The shortest thing that can be a sentence worth quoting. Six words.
#: Measured against the shipped chrome: `check out a few of our case
#: studies` is seven, so length alone was never going to do this job - but
#: below six, a fragment is a fragment.
MIN_WORDS = 6

#: The longest. A 60-word span is a paragraph and quoting it back is not
#: personalisation, it is transcription.
MAX_WORDS = 45

#: Words that make a token a SUBJECT. Personal pronouns, demonstratives and
#: determiners that can head a noun phrase.
SUBJECT_WORDS = frozenset("""
i we you he she it they our your their his her its this that these those
""".split())

DETERMINERS = frozenset("""
the a an our your their his her its this that these those every each some
any no one both all most many few several another other
""".split())

#: FINITE VERB FORMS. Auxiliaries and copulas first - those are what a
#: declarative sentence hangs on and what an imperative almost never has.
FINITE_VERBS = frozenset("""
is are was were am be been being has have had do does did
can could will would shall should may might must
""".split())

#: Third-person singular and past forms of the verbs a company site actually
#: uses about itself. Matched as whole words. This is a list rather than a
#: morphological guess because `focus`/`focuses` and `need`/`needs` differ by
#: exactly the letter that separates a heading from a sentence.
FINITE_VERBS_LEXICAL = frozenset("""
makes made helps helped builds built works worked runs ran uses used
offers offered provides provided delivers delivered creates created
designs designed focuses focused specialises specialized specializes
serves served combines combined brings brought turns turned starts started
stops stopped knows knew believes believed solves solved supports supported
grows grew needs needed wants wanted sees saw gets got takes took gives gave
keeps kept lets means meant includes included covers covered spans spanned
handles handled manages managed operates operated partners partnered
launches launched ships shipped hires hired opens opened raised acquired
published posted announced expanded employs employed founded
""".split())

#: A span may not OPEN on one of these. A subordinate clause is a fragment
#: however many verbs it has: `because that is what makes good video` has a
#: subject and a copula and is half of somebody's heading.
SUBORDINATORS = frozenset("""
because although though while if when since unless whereas whether
and or but so yet for nor plus also then thus hence
""".split())

#: Chrome that names itself. Lower-cased substring match on the span. Every
#: one of these was read off a real 400-character cache entry or off the
#: sixty-four emails that shipped.
NAV_MARKERS = (
    "skip to content", "skip to main content", "skip to main", "skip to footer",
    "skip to navigation", "skip navigation", "your browser does not support",
    "enable javascript", "back to homepage", "back to top", "sign in",
    "sign up", "log in", "login", "logout", "book a demo", "book a meeting",
    "request a demo", "request a quote", "get a quote", "contact us",
    "get started", "get in touch", "learn more", "read more", "view all",
    "see all", "find out more", "privacy policy", "cookie policy",
    "terms of service", "terms and conditions", "all rights reserved",
    "copyright", "toggle navigation", "main menu", "close menu",
    "subscribe to our", "newsletter", "follow us", "share this",
    "case studies", "our work", "meet the team", "careers", "job openings",
    "error: contact form not found", "page not found", "404",
    "add to cart", "checkout", "search for", "select language",
    "check out a few of our",
)

#: Punctuation and glyphs that only ever appear in chrome. A pipe or a
#: chevron inside a span means the span crossed a menu separator.
NAV_GLYPHS = ("|", "»", "«", "›", "‹", "→", "←", "•", "▸", "▶", "©", "™",
              "»", "›")

#: Language-switcher runs. A menu that offers four languages puts their
#: names in a row, and the row has no verb - but it lands INSIDE a span that
#: does, because the span before it ran on. Named explicitly because
#: `content back to homepage havas investors/shareholders en fr` shipped.
LANGUAGE_TOKENS = frozenset("""
en fr de es it nl pt ru ja zh ko pl sv da fi no cs tr ar he hi
english deutsch espanol francais nederlands portugues italiano
""".split())

#: HOW MANY TITLE-CASE WORDS IN A ROW MAKE A MENU.
#:
#: The rule that catches the chrome the others let through. A crawler takes
#: the first 400 characters and the menu runs straight into the first line of
#: prose, so the span that comes out is a menu WITH a sentence bolted on the
#: end and it satisfies every other test:
#:
#:   "Platform Meeting Operations Where governance moves from discussion
#:    to decisive action Governance Foundations ..."
#:   "Why Adora Product Guest Experience & Operations Online ordering ..."
#:   "The Coca-Cola Company Coca-Cola is a global brand ..."
#:
#: Each has a finite verb, a subject in front of it and a title-case ratio
#: under half, because the prose on the end dilutes the ratio. What none of
#: them can hide is the RUN: four capitalised words with nothing between
#: them is a navigation bar in every one of these and in none of the 3,636
#: spans the gate accepts.
MAX_CAPITALISED_RUN = 4

_WORD = re.compile(r"[A-Za-z][A-Za-z'’\-]*")
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


class Held(Exception):
    """No span in this pack may be quoted. The lead is HELD, not sent."""


def _words(text):
    return _WORD.findall(str(text or ""))


def _is_subject(token, following):
    """Could this token head the subject of a declarative sentence?"""
    low = token.lower()
    if low in SUBJECT_WORDS:
        return True
    if low in DETERMINERS and following:
        return True
    # A capitalised word that is not a determiner: a company or person name.
    return bool(token[:1].isupper() and low not in DETERMINERS)


def _finite_verb_index(tokens):
    """Where the first FINITE verb is, or -1.

    Deliberately NOT "any verb". An imperative - `Check out our work`,
    `Book a meeting` - is a verb in the bare form at position zero, and
    every piece of navigation chrome that has a verb at all has it in
    exactly that shape.
    """
    for i, token in enumerate(tokens):
        low = token.lower()
        if low in FINITE_VERBS or low in FINITE_VERBS_LEXICAL:
            return i
    return -1


def longest_capitalised_run(span):
    """The longest unbroken run of capitalised words. Menus have long ones.

    Counted over the raw tokens INCLUDING the first, because a menu starts
    at the top of the page and so does the snippet: `Services Engagements
    Domains About` opens at position zero and is the whole of what is wrong
    with that fact.
    """
    best = run = 0
    for token in _words(span):
        if token[:1].isupper():
            run += 1
            best = max(best, run)
        else:
            run = 0
    return best


def title_case_ratio(span):
    """How much of this reads like a menu. Menus are Title Case."""
    tokens = _words(span)
    if len(tokens) < 2:
        return 0.0
    # The first word is capitalised in a sentence too, so it is excluded.
    rest = tokens[1:]
    upper = sum(1 for t in rest if t[:1].isupper())
    return upper / float(len(rest))


def reasons_against(span):
    """Every reason this span may NOT be quoted. Empty means it may.

    A LIST RATHER THAN A BOOLEAN, because the review file has to say WHY a
    lead was held and "failed the pack fact gate" sends somebody back to
    read this module rather than the lead.
    """
    text = str(span or "").strip()
    out = []
    if not text:
        return ["empty span"]

    low = text.lower()
    if text[-1] not in TERMINATORS:
        out.append("no terminal punctuation: the source did not close this "
                   "sentence, the 400-character cap did")
    tokens = _words(text)
    if len(tokens) < MIN_WORDS:
        out.append("under %d words" % MIN_WORDS)
    if len(tokens) > MAX_WORDS:
        out.append("over %d words: a paragraph, not a sentence" % MAX_WORDS)

    if tokens and tokens[0].lower() in SUBORDINATORS:
        out.append("opens on %r: a subordinate clause is a fragment"
                   % tokens[0].lower())

    verb_at = _finite_verb_index(tokens)
    if verb_at < 0:
        out.append("no finite verb: nothing is being asserted")
    elif verb_at == 0:
        out.append("opens on the verb %r: an imperative is a button, not a "
                   "sentence about them" % tokens[0].lower())
    elif not any(_is_subject(t, True) for t in tokens[:verb_at]):
        out.append("no subject before the verb %r" % tokens[verb_at].lower())

    for marker in NAV_MARKERS:
        if marker in low:
            out.append("navigation text: %r" % marker)
            break
    for glyph in NAV_GLYPHS:
        if glyph in text:
            out.append("navigation glyph: %r" % glyph)
            break
    langs = [t for t in tokens if t.lower() in LANGUAGE_TOKENS]
    if len(langs) >= 2:
        out.append("language switcher: %s" % ", ".join(langs[:4]))

    ratio = title_case_ratio(text)
    if ratio >= 0.5:
        out.append("Title Case throughout (%.0f%%): a menu, not prose"
                   % (ratio * 100))
    run = longest_capitalised_run(text)
    if run >= MAX_CAPITALISED_RUN:
        out.append("%d capitalised words in a row: a navigation bar running "
                   "into the text" % run)
    return out


def is_body_sentence(span):
    """True when this span is a complete declarative sentence from a page body."""
    return not reasons_against(span)


def sentences_in(snippet):
    """Candidate spans inside one cached snippet, in order.

    The LAST fragment is included even though it is almost always the
    truncated tail - `reasons_against` refuses it for having no terminator,
    and dropping it here instead would hide the commonest reason a pack
    holds nothing quotable.
    """
    text = re.sub(r"\s+", " ", str(snippet or "")).strip()
    if not text:
        return []
    return [part.strip() for part in _SENTENCE_SPLIT.split(text) if part.strip()]


def quotable(fact):
    """Every span in ONE fact that may be quoted. Possibly empty.

    A fact with no `source_url` yields nothing however good its prose is:
    the review file has to print where the line came from, and a quote whose
    origin cannot be printed is the thing this gate exists to stop.
    """
    fact = fact or {}
    if not str(fact.get("source_url") or "").strip():
        return []
    return [s for s in sentences_in(fact.get("snippet")) if is_body_sentence(s)]


def facts_of(pack):
    """The FACT OBJECTS in a pack, or nothing - never a count read as facts.

    `work/researchpack-us-cohort-2026-09-25.jsonl` carries `"facts": 3`, an
    integer, because that file is a per-domain SUMMARY and not a pack. Three
    other files in the same directory, spelled almost identically, carry the
    real list. A reader that iterates `pack["facts"]` crashes on the first
    of them and - worse - a reader that asks `if pack.get("facts")` scores
    the summary row as having three usable facts without ever looking at
    one. Anything that is not a list of mappings is NO facts here, which
    holds the lead rather than quoting a number.
    """
    facts = (pack or {}).get("facts")
    if not isinstance(facts, (list, tuple)):
        return []
    return [f for f in facts if isinstance(f, dict)]


def quotable_in_pack(pack):
    """`[(span, fact)]` across a whole pack. Empty means HOLD."""
    out = []
    for fact in facts_of(pack):
        for span in quotable(fact):
            out.append((span, fact))
    return out


def choose(pack):
    """The span this lead may open on, or raise `Held`.

    THE ONLY WAY TO GET A LINE OUT OF THIS MODULE. It raises rather than
    returning a generic fallback, because the fallback is what shipped: 775
    leads on campaigns 491-498 opened with `I work with Marketing &
    Advertising teams on <angle>, and I do not know how <Company> handles
    it` - a sentence that mentions the prospect only as the thing we admit
    we know nothing about.
    """
    found = quotable_in_pack(pack)
    if not found:
        raise Held(
            "no fact in this pack contains a complete declarative sentence "
            "from a page body. The lead is HELD. Generic copy is not the "
            "fallback: %d fact(s) examined" % len(facts_of(pack)))
    return found[0]


def _normalise(text):
    return re.sub(r"\s+", " ", str(text or "")).strip().lower()


def check_span(span, fact):
    """Verdict on one quoted span against the fact it claims to come from.

    `{ok, span, fact_id, source_url, reasons}`. `ok` is False whenever the
    span cannot be shown to be a body sentence AT that url - including when
    there is no fact at all, which is the case the absent-field trap would
    have scored as a pass.
    """
    fact = fact or {}
    span_text = str(span or "").strip()
    verdict = {"ok": False, "span": span_text,
               "fact_id": fact.get("fact_id"),
               "source_url": fact.get("source_url"), "reasons": []}
    if not span_text:
        verdict["reasons"].append("no quoted span")
        return verdict
    if not fact:
        verdict["reasons"].append(
            "the quoted line names no pack fact: there is nothing to check "
            "it against and nowhere to say it came from")
        return verdict
    if not str(fact.get("source_url") or "").strip():
        verdict["reasons"].append("the fact carries no source url")
    snippet = _normalise(fact.get("snippet"))
    if not snippet:
        verdict["reasons"].append("the fact carries no snippet")
    elif _normalise(span_text) not in snippet:
        verdict["reasons"].append(
            "the quoted line does not appear in the fact's snippet: it was "
            "not read off that page")
    verdict["reasons"] += reasons_against(span_text)
    verdict["ok"] = not verdict["reasons"]
    return verdict
