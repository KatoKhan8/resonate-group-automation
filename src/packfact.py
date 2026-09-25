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

#: The verbs a company site actually uses about itself, in every form a
#: declarative sentence puts them in. A list rather than a morphological
#: guess, because `focus`/`focuses` differ by exactly the letter that
#: separates a heading from a sentence.
#:
#: THE BASE FORM HAD TO BE IN HERE AND IT IS SAFE. `We solve the
#: complexities of enterprise Oracle environments.` is the one real body
#: sentence in a whole cached fact, and without `solve` the gate refused it
#: for having no verb - which would have held every lead whose best line
#: takes a plural subject, which is most of them.
#:
#: It does NOT re-admit the imperatives, because `_rule_declarative` refuses
#: a finite verb at position ZERO whatever form it is in: `Book a meeting`,
#: `Check out our case studies` and `Get started today` all still fail, and
#: they fail on the rule that was written for them rather than by accident
#: on a missing dictionary entry.
FINITE_VERBS_LEXICAL = frozenset("""
make makes made help helps helped build builds built work works worked
run runs ran use uses used offer offers offered provide provides provided
deliver delivers delivered create creates created design designs designed
focus focuses focused specialise specialises specialize specializes
serve serves served combine combines combined bring brings brought
turn turns turned start starts started stop stops stopped know knows knew
believe believes believed solve solves solved support supports supported
grow grows grew need needs needed want wants wanted see sees saw
get gets got take takes took give gives gave keep keeps kept let lets
mean means meant include includes included cover covers covered
span spans spanned handle handles handled manage manages managed
operate operates operated partner partners partnered launch launches
launched ship ships shipped hire hires hired open opens opened
raise raises raised acquire acquires acquired publish publishes published
post posts posted announce announces announced expand expands expanded
employ employs employed found founded drive drives drove enable enables
enabled connect connects connected power powers powered reduce reduces
reduced increase increases increased improve improves improved
save saves saved trust trusts trusted think thinks thought
""".split())

#: A span may not OPEN on one of these. A coordinator at the start of a
#: span means the span was CUT - the other half is in the previous 400
#: characters or was never fetched.
COORDINATORS = frozenset("and or but so yet nor plus also then thus hence".split())

#: A span may not open on one of these EITHER - unless it goes on to a main
#: clause, which in written English is marked with a comma.
#:
#: THE OVER-REFUSAL THIS DISTINCTION EXISTS FOR. `because that is what makes
#: good video` is half a heading and must be refused. `Since 2006, we have
#: helped ambitious organizations find the right thing to build.` is a
#: complete sentence off a real site, opens on the same word class, and the
#: first version of this rule refused it - which would have HELD every lead
#: whose best line happens to start with a date clause.
SUBORDINATORS = frozenset("""
because although though while if when since unless whereas whether
""".split())

#: ONE TOKEN CARRYING BOTH A SUBJECT AND A FINITE VERB. `We're one flat,
#: integrated team of product professionals in nine countries.` is real
#: prose off a real site and the first version of this module refused it for
#: having no verb: `we’re` is a single token and `re` is not in any verb
#: list. Listed rather than expanded by regex because `Accelo’s` is a
#: possessive and not a copula, and the two spell the same suffix.
CONTRACTED_SUBJECT_VERB = frozenset("""
im ive ill id
were weve well wed
youre youve youll youd
theyre theyve theyll theyd
hes shes its thats theres heres whos whats
isnt arent wasnt werent hasnt havent hadnt dont doesnt didnt
wont wouldnt cant couldnt shouldnt
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
    "toggle navigation", "main menu", "close menu",
    "subscribe to our", "error: contact form not found", "page not found",
    "add to cart", "select language",
)
#
# WHAT WAS TAKEN OUT OF THAT LIST AND WHY IT MATTERS.
#
# `case studies`, `our work`, `careers`, `newsletter`, `follow us`,
# `checkout`, `404` and `copyright` were in it for one draft. They are
# ordinary English: `We check every one of our case studies before we
# publish it.` is a real sentence off a real site and the gate refused it
# for containing two of those words.
#
# A marker earns its place by naming a thing that is ONLY ever chrome. The
# CTAs those entries were meant to catch - `Check out our case studies`,
# `View all our work` - are already refused by `_rule_declarative` for
# opening on a bare imperative, which is the rule written for exactly them.
# Two rules catching the same chrome is fine; one rule catching real prose
# is a lint that gets widened later by somebody who needs a draft to pass.

#: Punctuation and glyphs that only ever appear in chrome. A pipe or a
#: chevron inside a span means the span crossed a menu separator.
NAV_GLYPHS = ("|", "»", "«", "›", "‹", "→", "←", "•", "▸", "▶", "©", "™",
              "»", "›")

#: Language-switcher runs. A menu that offers four languages puts their
#: codes in a row, and the row has no verb - but it lands INSIDE a span that
#: does, because the span before it ran on. Named explicitly because
#: `content back to homepage investors/shareholders en fr` shipped.
#:
#: `it`, `no`, `he` and `hi` ARE LANGUAGE CODES AND ARE NOT IN THIS SET.
#: Italian, Norwegian, Hebrew and Hindi spell themselves exactly as four
#: ordinary English words, and with them in the set this rule refused `Each
#: one is real software in production, told through the problem it solved
#: and the numbers it moved.` - a sentence with no language switcher in it
#: at all, containing the word "it" twice.
LANGUAGE_TOKENS = frozenset("""
en fr de es nl pt ru ja zh ko pl sv cs tr
english deutsch espanol francais nederlands portugues italiano
""".split())

#: How many language codes IN A ROW make a switcher. Adjacency is the point:
#: two codes scattered through a paragraph are two words, and two codes side
#: by side are a menu.
LANGUAGE_RUN = 2

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


def _rule_terminator(text, tokens):
    if text[-1] not in TERMINATORS:
        return ("no terminal punctuation: the source did not close this "
                "sentence, the 400-character cap did")


def _rule_length(text, tokens):
    if len(tokens) < MIN_WORDS:
        return "under %d words" % MIN_WORDS
    if len(tokens) > MAX_WORDS:
        return "over %d words: a paragraph, not a sentence" % MAX_WORDS


def _rule_subordinator(text, tokens):
    if not tokens:
        return None
    first = tokens[0].lower()
    if first in COORDINATORS:
        return ("opens on %r: the other half of this sentence is not in the "
                "snippet" % first)
    if first in SUBORDINATORS and "," not in text:
        return ("opens on %r with no main clause after it: a subordinate "
                "clause is a fragment" % first)


def _bare(token):
    return "".join(c for c in token.lower() if c.isalpha())


def _rule_declarative(text, tokens):
    # A CONTRACTION CARRIES ITS OWN SUBJECT. `We're`, `they've`, `it's`:
    # one token, subject and finite verb both, and it satisfies this rule
    # wherever it appears including position zero.
    if any(_bare(t) in CONTRACTED_SUBJECT_VERB for t in tokens):
        return None
    verb_at = _finite_verb_index(tokens)
    if verb_at < 0:
        return "no finite verb: nothing is being asserted"
    if verb_at == 0:
        return ("opens on the verb %r: an imperative is a button, not a "
                "sentence about them" % tokens[0].lower())
    if not any(_is_subject(t, True) for t in tokens[:verb_at]):
        return "no subject before the verb %r" % tokens[verb_at].lower()


def _rule_nav_marker(text, tokens):
    low = text.lower()
    for marker in NAV_MARKERS:
        if marker in low:
            return "navigation text: %r" % marker


def _rule_nav_glyph(text, tokens):
    for glyph in NAV_GLYPHS:
        if glyph in text:
            return "navigation glyph: %r" % glyph


def _rule_language_switcher(text, tokens):
    run = []
    for token in tokens:
        if token.lower() in LANGUAGE_TOKENS:
            run.append(token)
            if len(run) >= LANGUAGE_RUN:
                return "language switcher: %s" % " ".join(run[:4])
        else:
            run = []


def _rule_title_case(text, tokens):
    ratio = title_case_ratio(text)
    if ratio >= 0.5:
        return ("Title Case throughout (%.0f%%): a menu, not prose"
                % (ratio * 100))


def _rule_capitalised_run(text, tokens):
    run = longest_capitalised_run(text)
    if run >= MAX_CAPITALISED_RUN:
        return ("%d capitalised words in a row: a navigation bar running "
                "into the text" % run)


#: EVERY RULE, BY NAME, AND WHY THE LIST IS ADDRESSABLE.
#:
#: `reasons_against(span, skip=("declarative",))` runs the gate with one
#: rule taken out. That exists for the TEST, and the test is the reason to
#: trust any of this: a guard nobody has watched fail is a guard that might
#: be inert. `test_a_navigation_bar_is_not_a_pack_fact` removes each rule in
#: turn and requires that some piece of real shipped chrome then passes - so
#: a rule that has stopped doing anything turns the suite red rather than
#: sitting there looking reassuring.
#:
#: It is NOT a runtime knob. Nothing in `src/` passes `skip`, and a caller
#: that did would be disabling a gate rather than configuring one.
RULES = (
    ("terminator", _rule_terminator),
    ("length", _rule_length),
    ("subordinator", _rule_subordinator),
    ("declarative", _rule_declarative),
    ("nav_marker", _rule_nav_marker),
    ("nav_glyph", _rule_nav_glyph),
    ("language_switcher", _rule_language_switcher),
    ("title_case", _rule_title_case),
    ("capitalised_run", _rule_capitalised_run),
)


def reasons_against(span, skip=()):
    """Every reason this span may NOT be quoted. Empty means it may.

    A LIST RATHER THAN A BOOLEAN, because the review file has to say WHY a
    lead was held and "failed the pack fact gate" sends somebody back to
    read this module rather than the lead.
    """
    text = str(span or "").strip()
    if not text:
        return ["empty span"]
    tokens = _words(text)
    out = []
    for name, rule in RULES:
        if name in skip:
            continue
        why = rule(text, tokens)
        if why:
            out.append(why)
    return out


def is_body_sentence(span, skip=()):
    """True when this span is a complete declarative sentence from a page body."""
    return not reasons_against(span, skip=skip)


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
