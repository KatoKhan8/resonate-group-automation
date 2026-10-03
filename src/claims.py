#!/usr/bin/env python3
"""Every specific claim in a message must be traceable to something we know.

## Why a lint rule is not enough

lint.py already refuses placeholders, banned phrases and the wrong length. None
of that catches the failure that actually damages a client: a fluent, confident
sentence about a company event that never happened. "Congratulations on the
Series B" reads perfectly and passes every stylistic check, and if there was no
Series B the prospect knows immediately that nobody read anything.

So specific claims are extracted from the finished text and each one is checked
against what the record actually holds: stored company facts, contact facts, the
evidence chosen for this message, and known thread context. A claim with no
support is a rejection, and the draft is regenerated.

## Rejected, never patched

There is no code here that edits a sentence to make it true. Deleting the
offending clause leaves a message shaped around a fact it no longer states, and
softening it ("I think you might be growing") is worse than either. The draft
goes back.

## What counts as a claim

Numbers, dates, place names, named events - the things a reader could check.
Ordinary sales prose is not a claim: "most operations leads we speak to lose a
day a month" is a statement about us, not about them, and needs no evidence
about their company.
"""
import re

from . import evidence, packfacts

# ------------------------------------------------------ CLIENT_SUPPLIED
#
# A CLIENT-CSV FIGURE IS NOT A CLAIM LICENCE. TEMPORARY, CONSERVATIVE,
# DELIBERATELY BLUNT.
#
# OPERATOR DECISION "B", Zvonimir, 2026-09-28. The six `company_facts` keys
# the client CSV carries in may still be used for qualification,
# segmentation, prioritisation, strategy, offer selection and internal
# reasoning. They may NOT license a prospect-facing factual claim through
# EITHER claim-validation path. If the only evidence for a claim is one of
# those keys, this module FAILS CLOSED and refuses.
#
# THE PACK PATH WAS THE OTHER HALF, and it was closed first:
# `packfacts.pack_for` returns the claim licence as `pack["facts"]` and the
# client's own facts separately under `unused[CLIENT_SUPPLIED]`, so
# `copylint.untraceable` and `sequencegate.check` no longer see them. This
# module is the SECOND, independent gate, and until now its support model was
# every `company_facts` key and value - so a spreadsheet number still ground
# an assertion to a stranger. Reproduced twice, 2026-09-27 and 2026-09-28:
#
#     "You have 4000 employees."  + company_facts{headcount: 4000}  -> clean
#     "You have 4000 employees."  with that fact removed  -> "the figure 4000
#                                    appears in no stored fact"
#
# WHY IT IS BLUNT, AND WHAT THAT COSTS. `company_facts` carries NO per-key
# provenance, so a value typed into the client's CSV and the same value
# returned by a provider are INDISTINGUISHABLE once stored. Erring toward
# refusal therefore refuses MORE than strictly necessary: two of the six keys
# are also written by real providers - `headcount` by `headcount.observe`
# (ContactOut people-count, `blitz.company`) and `industry` by
# `enrich`'s merge of `contactout.company_info` - so a claim a provider-sourced
# value would legitimately support is refused as well, purely because it
# happens to live under one of these names. THAT IS THE ACCEPTED COST OF
# FAILING CLOSED, AND IT IS TEMPORARY.
#
# THE REAL FIX IS FACT-LEVEL PROVENANCE, recorded as required post-slice work
# (`TASK-462`, decision "A", `STATUS: BLOCKED` on purpose until `TASK-425`).
# Nobody should read this as the final data architecture: it is the hour-long
# conservative fix chosen over the day-long correct one so that no unverified
# spreadsheet figure can reach a prospect in the meantime.
#
# WHEN TASK-462 LANDS, THIS REFUSAL IS DELETED IN THE SAME CHANGE. That is the
# operator's rule, not a preference - a system carrying two answers to one
# question lets the blunt one win silently, and a stopgap nobody deletes is how
# a stopgap becomes the architecture. There are exactly two places:
# `CLIENT_SUPPLIED_FACT_KEYS` here and the `key in` skip in `support_text`. The
# proof module - `tests/test_a_client_supplied_figure_licenses_no_claim_in_
# either_gate.py` - is REWRITTEN against per-fact provenance, never deleted: the
# behaviour it pins (a spreadsheet figure grounds nothing) survives A, only the
# mechanism changes.
#
# TAKEN FROM `packfacts`, NEVER RETYPED, so the two gates cannot drift: the
# list of keys the ingest carries in is `packfacts.INGEST_FACT_KEYS`, and
# `src/ingest.py`'s `INGEST_TO_FACTS` is what fills them. A key added there
# becomes unlicensed here with no edit to this file.
CLIENT_SUPPLIED_FACT_KEYS = packfacts.INGEST_FACT_KEYS

# A sentence containing one of these is making a checkable assertion about the
# prospect rather than a general statement.
CLAIM_MARKERS = (
    "you", "your", "you're", "youre", "they", "their",
)

# Things that make a sentence specific enough to be wrong.
NUMBER = re.compile(r"\b\d[\d,.]*\b")
MONTH = re.compile(
    r"\b(january|february|march|april|may|june|july|august|september|october"
    r"|november|december|last month|this month|last week|recently|"
    r"two weeks ago|last quarter)\b", re.I)
EVENT_WORDS = (
    "raised", "funding", "series a", "series b", "series c", "acquired",
    "acquisition", "merger", "merged", "ipo", "launched", "launch", "opened",
    "opening", "expanded", "expansion", "hiring", "hired", "announced",
    "announcement", "partnership", "award", "certified", "moved to",
    "relocated", "office in", "offices in", "appointed", "promoted",
    "published", "wrote", "posted", "spoke at", "keynote",
)
# THE PLURAL WAS THE HOLE, FOR THE FOURTH TIME IN THIS MODULE.
#
# MEASURED 2026-09-30. `is_claim` returned False for all nineteen sentences
# of a five-email sequence, including the only hard factual assertion about
# the prospect in it:
#
#     "OBE has offices in Los Angeles, New York, San Francisco, and London."
#
# so `check_sentence` never ran on it and `verify` reported "no unsupported
# claim" having inspected nothing. Every EVENT_WORD is tested with `w in low`,
# a SUBSTRING test, and "office in" is not a substring of "offices in" - the
# `s` sits between them. The sentence carries no figure, no month, no
# second-person assertion and no other event word, so the `not any(...)`
# guard four hundred lines down returned False before anything else ran.
#
# This is a DEFECT and not intended scope: the singular "office in" is in the
# list precisely because opening an office is the kind of checkable event
# this module exists to catch, and one letter decided whether it was caught.
# The module already records the identical bug twice - `discussion` matching
# and `discussions` not, and the singular case-study nouns in
# `_BENCHMARK_PHRASE` - and the lesson was not carried here.
#
# FIXED NARROWLY, as the plural of one entry. The wider gap it exposes is NOT
# fixed here and is recorded instead: `CLAIM_MARKERS` is you/your/they/their,
# so a factual assertion whose subject is the prospect's company BY NAME
# ("OBE has ...") is only ever reached through an event word. Widening the
# marker set is a different change with a different blast radius and no
# measurement behind it yet.

# Words that make a sentence about us or about the world, not about them.
GENERIC_SUBJECTS = ("we ", "our ", "i ", "most ", "many ", "teams ", "companies ")


def sentences(text):
    parts = re.split(r"(?<=[.!?])\s+|\n+", str(text or ""))
    return [p.strip() for p in parts if p.strip()]


# A DECLARATIVE STATEMENT ABOUT WHAT THE PROSPECT DOES.
#
# `is_claim` recognised two things: a number and an event word. The sentence
# that actually went out to a real person was "you are running utilisation at
# the canary's company" - no number, no event, and a flat assertion about how somebody
# else's company operates, made on no evidence at all. It was not a claim as
# far as this module was concerned.
#
# These are second-person VERBS, not possessives. "your size" and "your team"
# appear in perfectly honest copy - the approved canary note says "curious how
# the canary's company handles it at your size" - and matching those would refuse the
# very sentences this system is trying to write. What is being caught is the
# form "you ARE X", "you HAVE X", "you RUN X": telling somebody a fact about
# their own business.
#
# Questions are still exempt by the rule below, so "are you running
# utilisation?" is a question and stays one.
# Constructions that suppose rather than state. A sentence carrying one of
# these is not telling the prospect a fact about themselves, whatever verb
# follows.
#
# The day-21 template is the reason this exists: "if {angle_phrase} is not
# something you are looking at right now, that is a fair answer in itself."
# Conditional, negated, and asserting nothing - the comment above it in
# `cadence.py` says as much - and a first version of the rule below refused
# it, which would have blocked the whole demo cadence. A guard that stops
# honest copy gets deleted rather than fixed.
HEDGES = ("if ", "unless ", "whether ", "in case ", "should you ",
          "suppose ", "assuming ", "not something", "maybe ", "perhaps ")

SECOND_PERSON_ASSERTIONS = (
    "you are ", "you're ", "you have ", "you've ", "you run ", "you use ",
    "you manage ", "you rely ", "you operate ", "you track ", "you bill ",
    "you struggle", "you need ", "you must be ", "your team is ",
    "your team has ", "your agency is ", "your studio is ",
)

# A CLAIM ABOUT THE RELATIONSHIP IS STILL A CLAIM.
#
# Every rule above asks what a sentence says about the PROSPECT, so a
# sentence about US was treated as harmless - `GENERIC_SUBJECTS` exits early
# for anything starting "we", "our" or "I". An assertion of shared history is
# about us AND them, and it fell straight through that exit.
#
# What reached a real draft on 2026-09-13, lint clean and claims clean:
#
#   "I want to make sure our last conversation landed clearly"
#   "We missed the deadline for the brand audit deliverable last week."
#
# There was no conversation, no deliverable and no deadline. This is worse
# than an unsupported figure: a wrong headcount is an error, an invented
# relationship is a lie, and it is the recipient - not us - who discovers it.
#
# Matched on the STEM so ordinary inflection is covered without a list per
# tense: spoke/spoken, discussed/discussing, connected/connecting. Bounded at
# the start so "as discussed" is caught and "we discussed our roadmap
# internally" is not - the second says nothing about them.
RELATIONSHIP = tuple(re.compile(p, re.I) for p in (
    # prior conversation, in any direction. PAST AND PERFECT ONLY: "we spoke"
    # names an event that either happened or did not, while "we speak" is
    # habitual and says nothing about this person. A first draft included the
    # present tense and refused "most operations leads we speak to are
    # running scheduling in one place", which is honest copy about our own
    # experience - and a guard that refuses honest copy gets switched off.
    r"\b(?:we|i|you)\s+(?:\w+\s+){0,2}"
    r"(?:spoke|spoken|talked|chatted|connected|met|corresponded)\b",
    # THE PLURAL WAS A HOLE. These nouns were singular and the `\b` after
    # "discussion" refuses to match inside "discussions", so "our previous
    # discussions" passed while "our previous discussion" was refused - the
    # same invented relationship, one letter apart. Measured 2026-09-14:
    # that exact subject, "Final note on our previous discussions", was
    # generated for a contact this system has never written to and reached
    # EmailBison as a per-lead variable on lead 203708.
    r"\b(?:our|the|your|that|a)\s+(?:last|previous|recent|earlier|first|"
    r"initial|prior)\s+(?:conversation|call|chat|exchange|email|message|"
    r"note|discussion|meeting|thread)s?\b",
    # AND THE ADJECTIVE WAS THE HOLE, exactly as it was for the email thread
    # four rules down - whose comment already records that "the first version
    # of this rule wanted an adjective" and was beaten by copy that did not
    # supply one. The lesson was not carried up here.
    #
    # "our previous conversation" was refused and "our conversation" was not.
    # Measured 2026-09-14, on a live regeneration of `ogpartner-dk` - a record
    # with `prior_contact` False and zero confirmed touches - em5 came back
    # with the subject "Closing the loop on our conversation with &Partner
    # ApS" and passed every gate.
    #
    # `our` ONLY, and the nouns that cannot be shared without a history. "the
    # conversation" is a thing that can happen in somebody's blog post and
    # "your call" is a thing they can make to somebody else; "our call" is a
    # claim about us and them. `email`, `message` and `note` stay OUT of this
    # list - "our email" is how somebody refers to the one they are writing,
    # and "I will keep the email short" is already pinned as clean.
    r"\bour\s+(?:conversation|call|chat|exchange|discussion|meeting|"
    r"thread)s?\b",
    r"\b(?:as|like)\s+(?:we\s+)?(?:discussed|mentioned|agreed|promised|"
    r"said|covered|noted)\b",
    # A DEFINITE REFERENCE TO A SHARED ARTEFACT. The first version of this
    # rule wanted an adjective - "our last email" - and the generator wrote
    # "The 2026-09-10 email thread highlights a gap", which names a thread by
    # date and passed. A date is not a weaker claim than "last"; it is a
    # stronger one. "the email" alone stays allowed, because "I will keep the
    # email short" asserts nothing.
    r"\b(?:the|that|this|our)\s+(?:\S+\s+){0,2}"
    r"(?:email|message|mail)\s+(?:thread|chain|exchange)\b",
    r"\b(?:the|our|that)\s+(?:initial|original|earlier|first)\s+"
    r"(?:outreach|contact|approach|introduction|intro)\b",
    r"\b(?:the|our|your)\s+(?:\S+\s+){0,2}"
    r"(?:call|meeting|demo|walkthrough)\s+(?:last|on|earlier)\b",
    r"\bfollow(?:ing)?[- ]?up\s+(?:on|from|about|to)\s+(?:our|your|the|my|"
    r"that|last|previous)\b",
    r"\b(?:circling|circle|looping|loop|checking|reaching)\s+back\b",
    r"\b(?:when|since|after|before)\s+we\s+(?:last\s+)?"
    r"(?:spoke|talked|met|connected|chatted)\b",
    # NOTE: the "you told/said/wrote" group is NOT here. It is the only one
    # where the same words can describe a publication rather than a
    # conversation, so it is matched separately below and tested against what
    # FOLLOWS the verb.
    r"\b(?:per|from)\s+(?:our|your)\s+(?:last\s+)?(?:conversation|call|"
    r"email|note|message|chat|discussion)s?\b",
    # an ongoing relationship or engagement
    r"\bwe(?:'ve| have)?\s+(?:\w+\s+){0,2}"
    r"(?:worked|partnered|collaborated|engaged)\s+(?:together|with you)\b",
    r"\b(?:our|the)\s+(?:ongoing|current|existing)\s+"
    r"(?:work|engagement|project|partnership|relationship|account)\b",
    r"\b(?:your|the)\s+(?:current|existing|last)\s+"
    r"(?:project|engagement|deliverable|scope|retainer|invoice)\s+with\s+us\b",
    # us having been watching them, which implies a history we cannot show
    r"\b(?:i|we)(?:'ve| have)?\s+(?:been\s+)?(?:following|watching|tracking|"
    r"admiring)\s+(?:your|you)\b",
    # apologies and commitments, which only exist inside a relationship
    r"\bwe\s+(?:\w+\s+){0,2}(?:missed|delayed|slipped|overran|rescheduled)\s+"
    r"(?:the|your|our)\b",
    r"\b(?:sorry|apolog\w+)\s+(?:for|about)\s+(?:the|our|my|any)\s+"
    r"(?:delay|miss|mistake|error|confusion|mix[- ]?up)\b",
    r"\b(?:as\s+)?promised\b",
    r"\b(?:my|our)\s+(?:last|previous|earlier)\s+(?:email|message|note)\b",
    r"\bdid\s+you\s+(?:get|receive|see)\s+(?:my|our)\b",
    # SILENCE IS ONLY EVIDENCE IF SOMETHING WAS SENT.
    #
    # "Since you have not replied" was already refused. "I have not heard
    # from you" was not, and it says the same thing from the other end: it
    # asserts we wrote and they did not answer. On a record with zero
    # confirmed touches both are false.
    #
    # Measured 2026-09-14 on a live regeneration of `ogpartner-dk`,
    # `prior_contact` False. em5 was STORED with "I have not heard from you
    # regarding how &Partner ApS approaches campaign measurement".
    #
    # Third phrasing of this same rule found in one day - after the plural
    # `discussions` and the bare possessive `our conversation`. The rule is
    # right and keeps turning out to be one phrase short, which is worth
    # saying plainly here rather than discovering a fourth time.
    r"\b(?:i|we)\s+(?:have\s+not|haven't|hadn't|had\s+not|did\s+not|didn't)"
    r"\s+(?:yet\s+)?hear(?:d)?\s+(?:back\s+)?from\s+you\b",
    r"\b(?:no|any)\s+(?:response|reply|word)\s+from\s+you\b",
    # ASSERTIONS ABOUT THE SENDER'S IDENTITY OR SHARED CATEGORY.
    #
    # TASK-075: `portsidemarketing-com` carried "as a fellow founder" - an
    # assertion about the SENDER that may be false. The unsupported-claim gate
    # watched claims about the PROSPECT, and this one pointed the other way.
    # It was the fourth phrase this rule turned out to be short of. Checkpoint
    # C predicted there would be a fourth. There was.
    #
    # "as a fellow founder", "as someone who also runs an agency", "speaking
    # as a fellow X" - these assert a shared identity or category with the
    # recipient. If the record does not support the sender being a founder,
    # an agency owner, or whatever the phrase claims, the sentence is an
    # unsupported assertion about the relationship between sender and prospect.
    #
    # Added to the EXISTING rule; not a second one. The task said so, and a
    # second tuple would need its own `implies_prior_contact` branch, its own
    # tests, and its own place in the check flow - all for the same question:
    # does the record support what this sentence asserts?
    r"\bas\s+a\s+fellow\s+\w+\b",
    r"\bas\s+someone\s+who\s+(?:also\s+)?(?:runs?|owns?|manages?|leads?|"
    r"founded|built|works?|operates)\b",
    r"\bspeaking\s+as\s+a\s+fellow\s+\w+\b",
))

# What the record must show before any of the above may ship. Deliberately
# NOT the research blob: prior contact is a fact about what WE did, not about
# what a scraper read, and no amount of company research makes a conversation
# have happened.
PRIOR_CONTACT_EVENTS = ("reply_received", "email_delivered",
                        "linkedin_connected", "push_marked")


# A POPULATION IS NOT THIS PERSON. "the agencies we worked with", "most
# leads we spoke to", "clients we met last year" - all describe our own
# experience, and the relative clause puts the verb next to "we" without
# saying anything about the recipient. Looked for in the words immediately
# BEFORE the phrase, because that is where the antecedent sits.
POPULATION = re.compile(
    r"\b(?:most|many|some|several|few|every|all|other|the|those|these)?\s*"
    r"(?:operations\s+|marketing\s+|creative\s+)?"
    r"(?:leads|clients|customers|agencies|studios|teams|companies|founders|"
    r"people|prospects|firms|partners|accounts)\s+$", re.I)

# PUBLISHING IS NOT CORRESPONDING. "You wrote about cutting month-end
# reconciliation from nine days to three" refers to something the prospect
# PUBLISHED - a post, a talk, a case study - and citing it is the whole point
# of research-backed personalisation. "You wrote to me" is a different claim
# entirely, and only the second one asserts a history.
#
# The discriminator is what follows the verb: an object they addressed to US
# (me, us, back) versus a topic or a public artefact. Looked for in the words
# AFTER the phrase. Whether the publication itself is real is already the
# evidence check's job - this only decides that it is not a relationship.
#
# Only a TOPIC or an ARTEFACT counts. A complement clause does not: "you
# mentioned that resourcing was the bottleneck" names no publication and is
# on the operator's own list of things that must be refused, so `that`, `how`
# and `why` are deliberately absent here.
PUBLIC_OBJECT = re.compile(
    r"^\s*(?:about|on|in|regarding|re:)\b"
    r"|^\s*(?:a|an|the|your|this)\s+"
    r"(?:post|article|piece|blog|newsletter|talk|podcast|episode|thread|"
    r"case\s+study|manifesto|paper|report|deck|video|interview)", re.I)

# The same verbs, but pointed at us. These stay a relationship claim whatever
# follows them.
DIRECTED = re.compile(r"^\s*(?:to\s+(?:me|us)|me|us|back)\b", re.I)

# The one ambiguous group. "You wrote about margins" cites a publication;
# "you wrote to me" asserts a conversation. Matched on its own so the
# publication test applies HERE and nowhere else - applying it to every
# pattern let "circling back ON this" and "sorry for the delay ON our end"
# read as publications, because both are followed by a preposition.
SAID_TO_US = re.compile(
    r"\byou\s+(?:\w+\s+){0,2}"
    r"(?:mentioned|told|said|asked|replied|responded|wrote|confirmed|"
    r"agreed|promised|requested|shared with)\b", re.I)


# THE MIRROR OF `RELATIONSHIP`, AND IT WAS MISSING. TASK-981.
#
# `implies_prior_contact` catches a draft that INVENTS a history. Nothing
# caught a draft that DENIES one that happened. Measured 2026-10-03 against a
# record carrying three confirmed `email_delivered` events:
#
#     "I am reaching out for the first time about ..."   claims.check -> []
#     "this is the first time we have written to you"    claims.check -> []
#     "apologies for the cold outreach - we have never
#      been in touch before"                             claims.check -> []
#
# All three are false on the record's own event log, and all three are the
# sentence a recipient is in the best position of anybody to disprove. This
# is the exact case the brief calls "the copy must not claim a first
# contact", and it matters most for a lead the client's own legacy campaign
# has already written to: the system knows about the touch
# (`prior_contact` is truthy) and could still ship a message denying it.
#
# NARROW ON PURPOSE. Only phrases whose whole content is "we have not been in
# touch". "you do not know me" is deliberately absent - it is a statement
# about recognition rather than correspondence, and three delivered emails
# nobody opened do not make it false.
NO_PRIOR_CONTACT = (
    re.compile(r"\bfor\s+the\s+first\s+time\b", re.I),
    re.compile(r"\bthis\s+is\s+the\s+first\s+"
               r"(?:time|email|e-mail|message|note)\b", re.I),
    re.compile(r"\b(?:we|i)\s+(?:have\s+)?(?:never|not)\s+(?:yet\s+)?"
               r"(?:been\s+in\s+touch|written|contacted|emailed|e-mailed|"
               r"messaged|reached\s+out|spoken)\b", re.I),
    re.compile(r"\b(?:we|i)\s+(?:haven't|havent|hadn't|hadnt)\s+"
               r"(?:been\s+in\s+touch|written|contacted|emailed|messaged|"
               r"reached\s+out|spoken)\b", re.I),
    re.compile(r"\bnever\s+been\s+in\s+touch\b", re.I),
    re.compile(r"\bout\s+of\s+the\s+blue\b", re.I),
    re.compile(r"\bcold\s+(?:email|outreach|message|note|intro|"
               r"introduction|approach)\b", re.I),
    re.compile(r"\bunsolicited\s+(?:email|message|note)\b", re.I),
)


def denies_prior_contact(sentence):
    """The phrase asserting we have NEVER written to this person, or None.

    Returns the matched text, like `implies_prior_contact`, so a refusal can
    quote the clause that caused it.

    The `POPULATION` guard applies here for the same reason it applies there:
    "agencies we have never contacted" describes our own estate and says
    nothing about the recipient.
    """
    for pattern in NO_PRIOR_CONTACT:
        found = pattern.search(sentence)
        if not found:
            continue
        if POPULATION.search(sentence[:found.start()]):
            continue
        return found.group(0)
    return None


def implies_prior_contact(sentence):
    """The phrase asserting a shared history WITH THIS PERSON, or None.

    Returns the matched text rather than a bool so a refusal can quote the
    words that caused it - somebody rewriting the draft needs to know which
    clause was the problem, not merely that one was.
    """
    for pattern in RELATIONSHIP:
        found = pattern.search(sentence)
        if not found:
            continue
        if POPULATION.search(sentence[:found.start()]):
            continue                 # "leads we spoke to", not "we spoke"
        return found.group(0)

    # The ambiguous group, decided on what follows the verb.
    found = SAID_TO_US.search(sentence)
    if found:
        rest = sentence[found.end():]
        if DIRECTED.match(rest) or not PUBLIC_OBJECT.match(rest):
            return found.group(0)    # "you wrote to me" / "you mentioned that"
    return None                      # "you wrote about margins" is a citation


def prior_contact(rec, contact=None):
    """Has this system actually reached this person before?

    Read from the record's own event log, which is where a confirmed touch is
    written and what `fatigue` and `collision` already read. A planned or
    attempted step is not contact: `PRIOR_CONTACT_EVENTS` names only outcomes
    the provider confirmed, so a message that was drafted and never sent
    cannot license "as discussed".
    """
    key = (contact or {}).get("key")
    for entry in (rec or {}).get("events") or []:
        if entry.get("type") not in PRIOR_CONTACT_EVENTS:
            continue
        # An event naming a different colleague is that colleague's history.
        # "We spoke last week" to somebody we have never written to is false
        # however busy their inbox has been.
        if key and entry.get("contact") and entry.get("contact") != key:
            continue
        return entry
    return None


def asserts_about_them(low):
    """Is this a flat statement about how the prospect OPERATES?

    Both halves are required, and the second half is what keeps this usable.
    "you are welcome to book a slot" is a second-person assertion and asserts
    nothing about their business; "you are running utilisation" says something
    about how they work that somebody could check. Only the second kind needs
    evidence, and demanding it of the first would refuse ordinary politeness.
    """
    if any(hedge in low for hedge in HEDGES):
        return False
    if not any(marker in low for marker in SECOND_PERSON_ASSERTIONS):
        return False
    return [t for t in evidence.OPERATIONAL_TERMS if t in low]


def is_claim(sentence):
    """Does this sentence assert something checkable about the prospect?"""
    low = sentence.lower()
    # BEFORE EVERY EXEMPTION BELOW. A shared history is asserted in the first
    # person - "we spoke", "as discussed", "I've been following your work" -
    # so `GENERIC_SUBJECTS` waves it through as a sentence about us, and the
    # question branch waves through "did you get my last email?". Both were
    # measured passing on a real draft. This is the one kind of claim whose
    # subject is the RELATIONSHIP rather than either party.
    if implies_prior_contact(sentence):
        return True
    if not any(marker in low.split() or marker in low for marker in CLAIM_MARKERS):
        # No second person and no third party: it is about us.
        if not any(w in low for w in EVENT_WORDS):
            return False
    if low.startswith(GENERIC_SUBJECTS):
        # "We help teams like yours" - about us, even though it says yours.
        if not (NUMBER.search(low) or any(w in low for w in EVENT_WORDS)):
            return False
    if "?" in sentence and not NUMBER.search(low):
        return False                     # a question asserts nothing
    return bool(NUMBER.search(low) or MONTH.search(low)
                or asserts_about_them(low)
                or any(w in low for w in EVENT_WORDS))


def support_text(rec, contact=None, chosen=()):
    """Everything a claim is allowed to lean on, as one searchable blob."""
    parts = []
    facts = rec.get("company_facts") or {}
    for key, value in facts.items():
        # THE SIX CLIENT-CSV KEYS ARE NOT SUPPORT. See CLIENT_SUPPLIED_FACT_KEYS
        # at the top of this module: operator decision B, 2026-09-28, Zvonimir.
        # They stay on the record and stay readable by qualification, strategy
        # and the dossier - this is the only place that is narrowed, and it is
        # narrowed because this is the list a prospect-facing claim leans on.
        if key in CLIENT_SUPPLIED_FACT_KEYS:
            continue
        if isinstance(value, (list, tuple)):
            # THE FIELD NAME AS WELL AS THE VALUES. A populated `offices` list
            # holding five city names is knowledge that this company has
            # offices, and dropping the key meant the word "office" appeared
            # nowhere in support - so "you run finance across five offices",
            # which the record fully supports, read as a fabrication.
            #
            # Only when it is POPULATED. An empty list is not evidence that we
            # know anything about the field, and appending the key regardless
            # would make every absent fact quietly assertable.
            if value:
                parts.append(str(key))
                parts.extend(str(v) for v in value)
        elif value not in (None, "", {}):
            parts.append(f"{key} {value}")
    parts.append(str(rec.get("company") or ""))
    parts.append(str(rec.get("domain") or ""))
    # NOT `rec["hook"]`. A hook is generated prose - `generate.hook` writes it
    # from a model - so reading it back as support let the generator certify
    # its own output and then be believed. Measured on 2026-09-11: the claim
    # "You are rebuilding utilisation reporting by hand" was REFUSED against a
    # record holding an industry and a headcount, and PASSED once an invented
    # hook saying so was stored on the same record.
    #
    # NOR `rec["diagnosis"]`, which went the same way and for the same reason:
    # `generate.diagnose` writes it from `llm.ask(model, "diagnose", ...)`, and
    # `what_changed` and `last_position` are free text that no schema
    # constrains. Measured on 2026-09-11: "Your utilisation dropped after the
    # Vienna office opened" was REFUSED on a clean record and PASSED once a
    # diagnosis saying so was stored.
    #
    # AND NOT `rec["context"]` OR `rec["signal"]`, WHICH THIS COMMENT USED TO
    # SAY WERE STILL SUPPORT. They are not, and measurably were not: neither
    # appears in the blob this function returns. That matters more under
    # decision B than it did before, because BOTH ARE CLIENT-CSV COLUMNS -
    # `ingest.add` passes them straight into `store.new_record` - so adding
    # either one back would put the client's own spreadsheet text into the claim
    # licence by a different door and undo B without touching the key list.
    # `llm.fact_strings` DOES walk both, which is `ISSUE-050`.
    #
    # `research` and `chosen` stay, and `company_facts` stays MINUS the six keys
    # above: those come from providers and from research. The line between them
    # is not how trustworthy the text reads, it is who wrote it.
    if contact:
        # NOT `persona` AND NOT `angle`. Those two are OUR vocabulary - the
        # routing family we filed this person under and the thing we decided to
        # sell them - and neither is a fact about them. Counting them as
        # support made the gate's answer depend on our own sales choice: on
        # 2026-09-11 the sentence "You run delivery for the studio." was
        # REFUSED for a contact whose angle was `operations` and PASSED,
        # unchanged, for one whose angle was `delivery`. One of the five
        # verified contacts in this estate carries `angle: delivery`, so that
        # was live rather than theoretical.
        #
        # `title` stays, and the distinction is the point: a title is a fact a
        # provider returned about this person, and an angle is a word we chose.
        for key in ("name", "title", "location"):
            if contact.get(key):
                parts.append(str(contact[key]))
    for entry in chosen or []:
        parts.append(str(entry.get("fact") or ""))
        parts.append(str(entry.get("published_at") or ""))
    for entry in rec.get("research") or []:
        parts.append(str(entry.get("fact") or ""))
    # AND NOT `rec["evidence"]`. That is `generate.persona_angle`'s output -
    # the model's own sentences, which `cadence.template_vars` then prints as
    # the first line of the day-5 email. Reading them back as support closed
    # the loop a third time: the model wrote the line, `check_evidence`
    # certified it, the prospect read it, and this function then treated it as
    # the reason it was allowed to be said. `chosen` above is the
    # research-derived parameter and is what legitimately licenses copy.
    return " ".join(parts).lower()


def _tokens(text):
    return set(re.findall(r"[a-z][a-z\-]{3,}", (text or "").lower()))


#: The closed-class prepositions that end a multi-word `EVENT_WORDS` phrase.
#: Exactly four entries carry one - "office in", "offices in", "moved to",
#: "spoke at" - and the preposition is there to stop the bare noun firing on
#: "office furniture", not because support has to contain it.
_EVENT_TAIL_PREPOSITIONS = ("in", "to", "at")


def _event_supported(word, support):
    """Does support mention this event, allowing for a glue preposition?

    FOUND BY THE PLURAL FIX ABOVE, 2026-09-30, and it is a second defect
    rather than a consequence of the first. `support` is a token join of the
    record's structured facts, so the BIGRAM "offices in" can never appear in
    it however completely the record knows the answer:

        company_facts.offices = ["Zagreb HR", "Varazdin HR", "Rijeka HR",
                                 "Beograd RS", "Ljubljana SI"]
        support ... "offices zagreb hr varazdin hr rijeka hr ..."

    so every office claim fell through to `_is_paraphrase`, which is a RATIO
    over the whole sentence and therefore fails on any long one. Measured on
    `tests/fixtures/phase7.jsonl` the moment the plural started matching:
    three stored day1 steps refused, all three TRUE - "you run finance across
    five offices in three countries" against a record holding five offices in
    three countries. `support_text`'s own comment records the authors hitting
    this wall for the singular and patching it by appending the FIELD NAME to
    support; that half-fix is why "offices" is in support at all, and this is
    the other half.

    NOT A LOOSENING OF WHAT COUNTS AS EVIDENCE. Only the glue preposition is
    dropped, and only from the end; the event noun itself must still appear
    in support as a whole token. A record that knows nothing about offices
    still refuses "OBE has offices in Los Angeles, New York, San Francisco
    and London", which is the sentence this whole investigation started from.
    """
    if word in support:
        return True
    parts = word.split()
    if len(parts) < 2 or parts[-1] not in _EVENT_TAIL_PREPOSITIONS:
        return False
    head = " ".join(parts[:-1])
    return bool(re.search(r"\b%s\b" % re.escape(head), support))


def check_sentence(sentence, support, identity=frozenset(), contacted=None):
    """Is this claim supported? Returns (ok, why_not).

    `contacted` is the confirmed prior-contact event for this person, or None.
    It is a separate argument rather than part of `support` because it answers
    a different question: `support` is what we know ABOUT them, and this is
    what we have actually DONE to them. Company research can never make a
    conversation have happened, so the two must not share a haystack.
    """
    low = sentence.lower()

    # A RELATIONSHIP WE CANNOT SHOW IS NOT A RELATIONSHIP.
    #
    # Checked first: it needs no figure, no event word and no second-person
    # verb, so every rule below would pass it. And unlike a wrong number, the
    # recipient is the person who finds out it is false.
    asserted = implies_prior_contact(sentence)
    if asserted and not contacted:
        return False, (f"{asserted!r} asserts we have contacted this person "
                       f"before, and no confirmed touch says we have")

    # A FIGURE IS A WHOLE TOKEN, NOT A SUBSTRING. `cleaned not in support` ran
    # against one joined blob, so a founding year licensed its own digits and
    # a headcount BAND licensed its endpoints: with "founded 2014" and
    # "employee_range 11-50" stored, 20, 01, 14, 11 and 50 were all "stored
    # facts". Measured across the 300 real records - a mean of 8.3 of the 90
    # two-digit numbers passed per record, and "You lost 50 billable hours
    # last month" passed on 67 of them.
    stored = set(NUMBER.findall(support))
    stored |= {n.strip(".,") for n in stored}
    for number in NUMBER.findall(low):
        cleaned = number.strip(".,")
        if len(cleaned) >= 2 and cleaned not in stored:
            return False, f"the figure {cleaned} appears in no stored fact"

    # A STATEMENT ABOUT HOW THEY OPERATE NEEDS SOMETHING BEHIND IT.
    #
    # "you are running utilisation at <their company>" carries no figure and no
    # event word, so every check below passed it and it went to a real person.
    #
    # STRICTER than the event-word branch, deliberately. The event branch
    # allows a paraphrase, because "you opened a Vienna office" against
    # evidence saying exactly that should pass on its content words. That
    # allowance is too generous here: a short second-person sentence is mostly
    # the recipient's own name and company, both of which are always in
    # support, so coverage passes on words that carry no claim at all. The
    # operational term IS the assertion, so it is what has to be supported.
    for term in (asserts_about_them(low) or []):
        if term not in support:
            return False, (f"'{term}' is asserted about them and nothing "
                           f"stored supports it")

    events_named = [w for w in EVENT_WORDS if w in low]
    for word in events_named:
        if _event_supported(word, support):
            continue
        if _is_paraphrase(low, support, identity):
            continue
        return False, (f"'{word}' is asserted but nothing stored "
                       "mentions it")
    return True, None


def identity_tokens(rec, contact=None):
    """The words that are in support no matter what, so prove nothing.

    Who this is and where they work: the company, its domain, the industry and
    size we filed it under, and the person's own name and title. Every one of
    them is in `support_text` by construction, which is why they cannot be
    allowed to count as coverage - see `_is_paraphrase`.

    `industry` STAYS HERE even though `support_text` no longer reads it under
    operator decision B. The two lists answer different questions: this one is
    what a sentence may not buy COVERAGE with, and dropping a client-supplied
    industry from it would let a fabrication pad itself with the industry word
    and lower the missing-token ratio. Absent from support AND absent from
    coverage is the strict reading, which is the one B asks for.
    """
    facts = rec.get("company_facts") or {}
    parts = [rec.get("company"), rec.get("domain"),
             facts.get("industry"), facts.get("name"),
             (contact or {}).get("name"), (contact or {}).get("title")]
    return _tokens(" ".join(str(p) for p in parts if p))


def _is_paraphrase(low, support, identity=frozenset()):
    """Is most of this sentence's substance already in what we know?

    The test the event-word branch has always used, named so the operational
    branch can hold to it too. "Congratulations on your Series B" has nothing
    behind it and fails; "you opened a Vienna office" against stored evidence
    saying exactly that passes.

    `identity` is what the sentence may not buy coverage with. The recipient's
    own name, their company, its domain and the industry and size we recorded
    are in support by construction, so padding a fabrication with them drops
    the missing-token ratio without adding a single supported assertion. That
    defeated this module's own headline example: "Congratulations on the Series
    B." is refused, and "Congratulations, <their name> of <their company> in
    <their industry> with <their headcount> employees, on the Series B."
    passed, on 2026-09-11, with nothing behind the Series B either time.
    """
    content = _tokens(low) - _tokens(" ".join(CLAIM_MARKERS)) - set(identity)
    if not content:
        return False
    missing = [t for t in content if t not in support]
    return len(missing) * 2 <= len(content)


def _prospect_names(rec, contact=None):
    """The names that refer to the PROSPECT, not to a third party."""
    out = []
    facts = (rec or {}).get("company_facts") or {}
    for value in (facts.get("name"), (rec or {}).get("company"),
                  (rec or {}).get("domain"), (contact or {}).get("name"),
                  (contact or {}).get("first_name")):
        value = str(value or "").strip()
        if value:
            out.append(value)
            # `azonetwork.com` also refers to them as `AZoNetwork`.
            head = value.split(".")[0].strip()
            if head and head != value:
                out.append(head)
    return tuple(out)


def check(text, rec, contact=None, chosen=()):
    """Every unsupported claim in this text. Empty means it may ship."""
    support = support_text(rec, contact, chosen)
    identity = identity_tokens(rec, contact)
    contacted = prior_contact(rec, contact)
    problems = []
    # CUSTOMER-OUTCOME CLAIMS: checked on the whole text, not per sentence
    # through `is_claim`, because the existing claim detector does not
    # recognise "clients have improved margins" as a claim at all. TASK-914.
    # THE PROSPECT'S OWN NAMES ARE NOT A THIRD PARTY. Their company and the
    # person being written to are excluded, so "AZoNetwork improved its
    # margin" is judged by the rules about the PROSPECT rather than reported
    # as a fabricated case study - the wrong reason is nearly as bad as no
    # refusal, because it sends a reviewer looking in the wrong place.
    outcome_reason = customer_outcome_claim(
        text, exclude=_prospect_names(rec, contact))
    if outcome_reason:
        problems.append({"sentence": text[:160], "why": outcome_reason})
    # A FIRST CONTACT THAT IS NOT ONE. TASK-981, and asked HERE rather than
    # through `is_claim` so that nothing changes for a record with no
    # confirmed touch: a cold draft saying "apologies for the cold outreach"
    # is true, must keep shipping, and must not be dragged through
    # `check_sentence`'s other rules by a widened claim detector.
    if contacted:
        for sentence in sentences(text):
            denied = denies_prior_contact(sentence)
            if not denied:
                continue
            problems.append({"sentence": sentence[:160], "why": (
                "%r says this is a first contact, and a confirmed %s on %s "
                "says it is not" % (denied, contacted.get("type"),
                                    contacted.get("at")))})
    for sentence in sentences(text):
        if not is_claim(sentence):
            continue
        ok, why = check_sentence(sentence, support, identity, contacted)
        if not ok:
            problems.append({"sentence": sentence[:160], "why": why})
    return problems


# --------------------------------------------------- a product of our own
#
# THE ONE CLAIM NOTHING ABOVE CAN CATCH.
#
# Everything in this module judges a sentence against the RECORD: what we
# know about their company, and what we have confirmed doing to this person.
# "our software, ProjectSync, joins up creative project tracking" asserts
# nothing about them, so `is_claim` passes it, `check_sentence` never sees it,
# `lint` has no rule for it and `quality` is about repetition. It shipped
# clean through all four.
#
# Measured 2026-09-14, on the first live regeneration after the client config
# gained a `product:` block: the prompt carried `"name": "Productive"` and the
# model returned `ProjectSync`. It is not a product. It does not exist.
#
# WHAT THIS CATCHES, STATED NARROWLY: a self-referential product phrase -
# "our software", "we built", "we call it" - followed closely by a capitalised
# token that is not the client's own product name. That is the shape the
# failure took and the shape a reviewer can reason about. It is NOT a general
# hallucination detector, and nothing here should be read as one: a model that
# invents a capability rather than a name still passes this.
#
# A client with no stated product is not checked. There is nothing to compare
# against, and a rule that guesses what somebody sells would refuse correct
# copy for every client who has not filled the block in.
OUR_PRODUCT = re.compile(
    r"\b(?:our|the)\s+(?:software|product|platform|tool|app|system|solution)"
    r"\b|\bwe\s+(?:built|call\s+it|make|created|named\s+it)\b", re.I)

# A capitalised token that could be a name. Two or more characters so an
# initial does not count, and it may carry internal capitals - `ProjectSync`
# is exactly that shape.
CAPITALISED = re.compile(r"\b[A-Z][A-Za-z0-9]{1,}\b")

# How far after the phrase a name still counts as attached to it. Beyond this
# a capitalised word is more likely the next sentence's first word.
PRODUCT_NAME_WINDOW = 60

# Capitalised words that begin sentences or name nothing. Kept short on
# purpose: every entry is a word this rule would otherwise report, and a long
# list is how a check quietly stops checking.
NOT_A_PRODUCT_NAME = frozenset((
    "i", "it", "we", "our", "the", "this", "that", "they", "you", "your",
    "a", "an", "and", "but", "for", "if", "in", "is", "of", "on", "or",
    "so", "to", "with", "what", "when", "where", "which", "who", "why",
    "how", "there", "these", "those", "monday", "tuesday", "wednesday",
    "thursday", "friday", "saturday", "sunday",
))


def foreign_product(text, product, rec=None):
    """Names of products we do not sell, asserted as ours. Empty means clean.

    `product` is `clients.product(config)`. A falsy one, or one with no
    `name`, disables the check rather than guessing - see the note above.

    `rec` supplies the prospect's own company name, which is the one
    capitalised token that legitimately appears beside a sentence about our
    software ("our platform, used by agencies like Acme"). It is discounted
    rather than reported.
    """
    name = (product or {}).get("name") or ""
    if not str(name).strip():
        return []
    allowed = {w.lower() for w in CAPITALISED.findall(str(name))}
    allowed |= NOT_A_PRODUCT_NAME
    if rec:
        for source in ((rec.get("company_facts") or {}).get("name"),
                       rec.get("company"), rec.get("domain")):
            allowed |= {w.lower() for w in CAPITALISED.findall(str(source or ""))}
            # A domain and a company name are frequently lowercase in the
            # record and capitalised in the copy, so both cases are taken.
            allowed |= {w.lower()
                        for w in re.findall(r"[A-Za-z0-9]{2,}", str(source or ""))}
    found = []
    for match in OUR_PRODUCT.finditer(text):
        window = text[match.end():match.end() + PRODUCT_NAME_WINDOW]
        for token in CAPITALISED.findall(window):
            if token.lower() in allowed:
                continue
            found.append({
                "name": token,
                "why": (f"{token!r} is named as our own software and this "
                        f"client sells {name!r}. A product we do not sell "
                        f"cannot be described to a prospect")})
            break
    return found


# ----------------------------------------- customer-outcome claims (TASK-914)
#
# THE DEFECT: a LinkedIn message said "clients using report intelligence have
# improved resource allocation and project margins noticeably" and every gate
# allowed it. The system already knows it has no customer-outcome evidence -
# `offers.missing()` reports "customer case studies" and "verified benchmarks"
# as gaps - and still the claim shipped.
#
# WHY `is_claim` DID NOT CATCH IT. The sentence starts with "clients" (not in
# CLAIM_MARKERS), carries no number, no date, no event word, and no operational
# term from `evidence.OPERATIONAL_TERMS` in a second-person form. It is a
# claim about what OUR customers achieved, not about the prospect, and the
# existing detectors watch the prospect.
#
# WHY `copylint.case_study_unsupported` DID NOT CATCH IT. That rule traces a
# NAMED study to its stored page. This claim names no study - it is a general
# customer-outcome assertion without any evidence behind it at all.
#
# THE FIX: detect the pattern (customer subject + outcome verb/benchmark
# phrase) and refuse it when the offers file says no licensed evidence exists.
# If evidence IS supplied (the gaps are filled), the claim passes through to
# the existing evidence rules, which remain authoritative.
#
# WHAT THIS IS NOT. A capability statement - "Productive shows margin per
# project while it is running" - is NOT a customer-outcome claim. The subject
# is the product, not a customer, and the verb is "shows" not "improved". The
# detector must not fire on it.

# Outcome verb stems. Each stem combines with _VERB_INFLECTION to cover
# all English inflections (base, -s, -ed, -ing). This models the semantic
# class of outcome achievement rather than listing individual conjugations,
# so the detector is robust across tense, aspect, modality and adverbs.
#
# TASK-915: the previous list held only past tense / past participle, so
# "clients improve" (base), "clients are improving" (progressive) and
# "clients can improve" (modal + base) all escaped. 14 of 23 matrix
# assertions passed. The fix models the paradigm, not the conjugation.
_OUTCOME_VERB_STEMS = (
    "improv", "reduc", "sav", "increas", "decreas",
    "boost", "lower", "lift", "rais", "acceler",
    "maximis", "maximiz", "minimis", "minimiz",
    "optimis", "optimiz",
)

# Inflection suffix covering base (-e), third-person -s, past -ed, and
# progressive -ing. The leading 'e' handles stems that need it:
# improv + e = improve, improv + ed = improved, improv + es = improves,
# improv + ing = improving. For stems already ending in a consonant
# (boost, lower), the 'e' alternative produces a non-word ("booste")
# that never appears in real text, while the other suffixes work:
# boost + ed = boosted, boost + s = boosts, boost + ing = boosting.
_VERB_INFLECTION = r"(?:e|ed|es|ing|s)?"

# Irregular outcome verbs whose inflections cannot be derived from a
# single stem + suffix pattern. Listed explicitly.
_OUTCOME_VERB_IRREGULAR = (
    r"cut(?:ting|s)?",               # cut/cuts/cutting (past = base)
    r"trim(?:med|ming|s)?",          # trim/trims/trimmed/trimming
    r"gr[oe]w|grown|grows|growing",  # grow/grew/grown/grows/growing
)


def _outcome_verb_pattern():
    """Build a regex alternation for outcome verbs in any inflection.

    Stems + inflection cover regular verbs; irregular verbs are listed
    in full. The result is wrapped in \\b by the caller.
    """
    parts = [re.escape(s) + _VERB_INFLECTION for s in _OUTCOME_VERB_STEMS]
    parts.extend(_OUTCOME_VERB_IRREGULAR)
    return "|".join(parts)


# Benchmark / typical-result phrases. A sentence offering to share a
# benchmark or citing a "typical result" is asserting customer outcomes
# even when shaped as a question.
#
# TASK-915: the trailing \\b after `typical\\s+client` refused to match
# "typical clients" (plural) because 's' is a word character and the
# boundary fell inside the word. Every branch that names a countable
# noun now carries an optional plural 's?'.
_BENCHMARK_PHRASE = re.compile(
    r"\b(?:"
    r"benchmark(?:s|example|data|result|metric|figure)?s?"
    r"|typical\s+results?"
    r"|typical\s+clients?"
    r"|average\s+(?:clients?|results?|improvements?|customers?)"
    r"|case\s+stud(?:y|ies)"
    r"|success\s+stor(?:y|ies)"
    r"|before[- ]and[- ]after"
    r"|real\s+(?:results?|examples?|outcomes?)"
    r"|proven\s+(?:results?|outcomes?|track\s+records?)"
    r")\b", re.I)

# TASK-917: shared outcome-metric vocabulary. ONE list used by BOTH the
# achievement branch (as a complement requirement) and the comparative
# branch (as the terminal metric alternation). An earlier version had two
# separate lists that drifted: the comparative branch refused "clients see
# faster turnaround" because "turnaround" was missing from its list, while
# the achievement branch over-blocked on "clients raise this constantly"
# because it had no complement requirement at all.
#
# The vocabulary covers the client's real domain, not just the words that
# fit a narrow business template. Multi-word metrics are matched on their
# head noun: "reporting cycle" fires on "reporting", "month-end close" on
# "close", "cash flow" on "cash", "billable hours" on "billable".
_OUTCOME_METRICS = (
    # Original set from TASK-916
    "margin", "cost", "time", "revenue", "profitability",
    "utilisation", "overhead", "hour", "allocation", "efficiency",
    "growth", "spend", "output", "performance",
    # TASK-917: expanded to the client's real outcome vocabulary
    "turnaround", "reporting", "close", "capacity", "throughput",
    "productivity", "billable", "write[- ]off", "rework",
    "delay", "backlog", "cash", "forecasting",
    "admin", "resource", "project",
)


def _outcome_metric_pattern():
    """Build a regex alternation for outcome-metric nouns.

    Each metric gets an optional trailing 's' for plurals and an optional
    trailing 'ed'/'ing' for participial forms ('reduced costs', 'saved
    time'). Multi-word metrics like 'write-off' use the literal pattern.
    """
    parts = []
    for m in _OUTCOME_METRICS:
        if "[-" in m:
            parts.append(r"\b(?:" + m + r")s?\b")
        else:
            parts.append(r"\b" + re.escape(m) + r"(?:s|ed|ing)?\b")
    return "|".join(parts)


# TASK-916: comparative-outcome pattern. "see" is not an achievement verb -
# in "clients see better margins" the OUTCOME is "better margins", not "see".
# But perception phrasings with a comparative direction word DO assert an
# outcome: "clients see higher profitability" claims our customers achieved
# higher profitability. This branch catches those without making bare "see"
# an outcome verb (which would refuse "finance teams see budget against
# actuals" and "saw your team's post about the Dallas office").
#
# Structure: customer subject + perception verb (see/saw/seen/sees/seeing)
# + direction word (better, higher, lower, ...) + outcome metric from the
# shared _OUTCOME_METRICS vocabulary.
#
# TASK-917: metric list now uses the shared _outcome_metric_pattern().
_COMPARATIVE_OUTCOME_RE = re.compile(
    r"(?<!\byour\s)"
    r"\b(?:clients?|customers?|users?|teams?|companies?|firms?"
    r"|agencies?|studios?)\b"
    r".{0,20}"
    r"\b(?:see|sees|saw|seen|seeing)\b"
    r".{0,20}"
    r"\b(?:better|higher|lower|greater|stronger|faster)\b"
    r".{0,20}"
    r"(?:" + _outcome_metric_pattern() + r")"
    r"|(?<!\byour\s)"
    r"\b(?:clients?|customers?|users?|teams?|companies?|firms?"
    r"|agencies?|studios?)\b"
    r".{0,20}"
    r"\b(?:more|less|fewer)\b"
    r".{0,20}"
    r"(?:" + _outcome_metric_pattern() + r")",
    re.I)

# TASK-916: second-person-possessive exclusion. "your team/teams/agency/..."
# is the PROSPECT, not our customer. This pattern catches those in the
# benchmark-phrase branch, where the customer noun is part of a fixed phrase
# rather than a subject-verb pair. The main _CUSTOMER_OUTCOME_RE already
# carries its own negative lookbehind for the outcome-verb branch.
_SECOND_PERSON_CUSTOMER = re.compile(
    r"\byour\s+(?:clients?|customers?|users?|teams?|companies?|firms?"
    r"|agencies?|studios?)\b", re.I)

# TASK-921: clause-scoped attribution replaces the fixed 40-char window.
#
# THE DEFECT: the 40-char window between customer subject and outcome verb
# was a bypass: "companies using real-time margin visibility make better
# resource decisions that improve profitability" pushed the outcome verb
# past 40 chars with a long modifier. Same subject, same verb, same metric.
#
# THE FIX: attribute a customer subject and an outcome verb to each other
# when they appear in the SAME CLAUSE, whatever the distance. A clause
# boundary (sentence terminator, semicolon) breaks the attribution. This
# preserves the safety property the window was protecting (preventing
# cross-sentence false attribution like "your studios. utilisation")
# without a fixed distance that a modifier can walk past.
#
# The regex now matches customer subjects and outcome verbs independently;
# the clause co-occurrence check is in _customer_outcome_clause_match().
_CUSTOMER_SUBJECT_RE = re.compile(
    r"(?<!\byour\s)"
    r"\b(?:clients?|customers?|users?|teams?|companies?|firms?"
    r"|agencies?|studios?|organisations?|organizations?)\b", re.I)

_CUSTOMER_OUTCOME_VERB_RE = re.compile(
    r"\b(?:" + _outcome_verb_pattern() + r")\b", re.I)

# A NAMED ORGANISATION AS THE SUBJECT OF AN OUTCOME. The third hole in the
# same wall.
#
# `_CUSTOMER_SUBJECT_RE` watches GENERIC subjects (clients, teams, agencies)
# and TASK-919 watches INDEFINITE and analogous ones (other teams, peers in
# your industry). Nothing watched a subject that is simply NAMED, which is
# the form a model reaches for first and the form a reader believes most.
#
# MEASURED 2026-09-30 against both gates, on a real record:
#
#     "One agency reduced overruns by 20% after switching."   REFUSED
#     "Our customers see margin improve within a quarter."    REFUSED
#     "Acme Corp cut costs by 30% with Productive."           PASSED
#     "We helped Acme Corp cut costs by 30%."                 PASSED
#
# The two that passed are fabricated case studies with a named customer and
# a figure, and they cleared `claims` AND `copylint`. Naming the customer
# made the claim more credible and less detectable.
#
# WHAT IT MATCHES: a capitalised name of one to three words in the same
# clause as an outcome verb. It does NOT require a metric, for the reason
# the generic branch does not: "Acme Corp improved their margin" asserts an
# outcome whether or not a number follows.
#
# WHAT IT DELIBERATELY DOES NOT MATCH, because these are not outcomes:
# "Productive shows margin while the work is still running", "Report
# Intelligence answers a question about your own data". `shows`, `answers`
# and `connects` are not outcome verbs, so a capability description stays
# clean without any name having to be allowlisted.
#
# THE PROSPECT'S OWN NAME IS EXCLUDED by the caller, which knows the record.
# A sentence about the prospect's own situation is a different rule's job
# (`_SECOND_PERSON_CUSTOMER`) and refusing it here would report the wrong
# reason.
#
# EVIDENCE-SENSITIVE like every rule here: the refusal disappears when
# `offers.missing()` stops reporting customer case studies and verified
# benchmarks.
#
# TWO CAPITALISED WORDS AT LEAST, which is the convention
# `copylint.SPECIFIC_RES` already uses for "a name a model invented". A
# single capitalised word cannot be told apart from the first word of a
# sentence, and trying cost eleven false refusals on TASK-921's own
# matrices: "Would better margin visibility improve resource decisions?"
# and "Agencies track utilisation." were both read as named organisations
# achieving an outcome. A single-word customer name is therefore missed
# here, which is the safe direction: this branch exists to catch a
# fabricated case study, and the copy lint still treats an untraceable
# capitalised name as a specific.
_NAMED_ORG_RE = re.compile(
    r"\b(?!(?:The|This|That|These|Those|It|We|Our|You|Your|If|How|What|When|"
    r"Where|Why|And|But|So|A|An|In|On|At|For|With|Most|Many|Some|Every|Each|"
    r"Would|Could|Should|Will|Can|Does|Do|Did|Is|Are|Was|Were|Have|Has)\b)"
    r"[A-Z][A-Za-z0-9&.'-]{1,}(?:\s+[A-Z][A-Za-z0-9&.'-]{1,}){1,3}\b")


def _named_third_party_outcomes(text, exclude=()):
    """Named organisations asserted to have achieved an outcome."""
    skip = {str(e or "").strip().lower() for e in exclude if str(e or "").strip()}
    out = []
    for m in _NAMED_ORG_RE.finditer(str(text or "")):
        name = m.group(0).strip()
        low = name.lower()
        if low in skip or any(low in s or s in low for s in skip if s):
            continue
        clause = _clause_containing(text, m.start())
        if _CUSTOMER_OUTCOME_VERB_RE.search(clause):
            out.append(name)
    return out


def _clause_containing(text, pos):
    """The clause of text that contains position pos.

    Clauses are split at sentence terminators (.!?) followed by whitespace
    or end-of-string, and at semicolons. Returns the clause substring.
    """
    starts = [0]
    for m in re.finditer(r'[.!?]\s+|;', text):
        starts.append(m.end())
    start = 0
    for s in starts:
        if s > pos:
            break
        start = s
    end = len(text)
    for m in re.finditer(r'[.!?]\s+|;', text):
        if m.start() >= pos:
            end = m.end()
            break
    return text[start:end]


_COMPARATIVE_WORD_RE = re.compile(
    r"\b(?:better|higher|lower|greater|stronger|faster|more|less|fewer)\b",
    re.I)

_CAUSATIVE_VERB_RE = re.compile(
    r"\b(?:mak(?:e|es|ing)|made|deliver(?:s|ed|ing)?|driv(?:e|es|ing)"
    r"|achiev(?:e|es|ed|ing))\b", re.I)


def _customer_outcome_clause_match(low):
    """TASK-921: customer subject + outcome assertion in the same clause.

    Returns a truthy value when a customer subject and an outcome assertion
    co-occur in the same clause, or None. Replaces the fixed 40-char window
    of _CUSTOMER_OUTCOME_RE with clause-scoped attribution.

    An outcome assertion is either:
    1. An outcome verb (improve, reduce, ...) from the shared stem list.
    2. A causative verb (make, deliver, ...) + comparative + metric.
    """
    metric_re = _outcome_metric_pattern()
    for cm in _CUSTOMER_SUBJECT_RE.finditer(low):
        clause = _clause_containing(low, cm.start())
        # Branch 1: outcome verb in the same clause
        if _CUSTOMER_OUTCOME_VERB_RE.search(clause):
            return cm
        # Branch 2: causative + comparative + metric
        if _CAUSATIVE_VERB_RE.search(clause) and _COMPARATIVE_WORD_RE.search(clause):
            if re.search(metric_re, clause, re.I):
                return cm
    return None


# TASK-921 A: subjectless realized-outcome assertions.
#
# THE DEFECT: "Can I share a brief example of how real-time margin insights
# have improved resource allocation?" asserts that an intervention HAS
# PRODUCED an outcome, while offers.missing() reports no customer case
# studies and no verified benchmarks. No customer subject, no third party
# - so nothing in the existing detectors fires.
#
# THE STRUCTURE: capability/intervention + REALIZED outcome assertion,
# beneficiary implicit or absent. The whole distinction is REALIZED vs
# POSSIBLE. "has improved", "have reduced", "improved" (past) assert
# something happened. "would improve", "could reduce", "can help",
# "provides", "shows" do not. Grammatical aspect is the signal.
#
# DETECTION: outcome verb in past-tense or perfect-aspect form, with no
# preceding modal hedge. The perfect auxiliary (have/has/had) before the
# participle, or the -ed suffix for simple past, marks realized aspect.
# A modal (would/could/may/might/should) before the auxiliary or verb
# marks possible aspect and disqualifies the match.
_REALIZED_OUTCOME_VERB_RE = re.compile(
    r"\b(?:"
    # Perfect aspect: have/has/had + past participle
    r"(?:has|have|had)\s+(?:" + _outcome_verb_pattern() + r")"
    r"|"
    # Simple past: outcome verb with -ed suffix (excludes base form)
    r"(?:" + "|".join(re.escape(s) + r"ed" for s in _OUTCOME_VERB_STEMS)
    + r")"
    r"|"
    # Irregular past forms (excludes "cut" which is ambiguous with base)
    r"(?:trimmed?|grew|grown)"
    r")\b", re.I)

# Modal hedges that make an outcome POSSIBLE rather than REALIZED.
_MODAL_HEDGE_RE = re.compile(
    r"\b(?:would|could|may|might|should)\b", re.I)

# Person-type subjects: "your" + customer/group noun, or bare pronouns.
# These indicate the subject is a person/group, not a capability.
_YOUR_CUSTOMER_RE = re.compile(
    r"\byour\s+(?:clients?|customers?|users?|teams?"
    r"|compan(?:y|ies)|firms?"
    r"|agenc(?:y|ies)|studios?"
    r"|organisations?|organizations?)\b", re.I)
_BARE_PRONOUN_SUBJECT_RE = re.compile(
    r"\b(?:they|we|you|he|she)\b", re.I)
# Question auxiliaries that indicate the verb is base form, not past.
_QUESTION_AUX_RE = re.compile(r"\b(?:do|does|did)\b", re.I)
# "your"/"yours" in a scope/analogy phrase - the third-party branch
# handles these. The subjectless detector must not intercept them.
_YOUR_SCOPE_RE = re.compile(r"\byour(?:s)?\b", re.I)


def _subjectless_realized_outcome(text):
    """TASK-921 A: realized outcome assertion with no person-type subject.

    Returns True when the text contains an outcome verb in realized aspect
    (past tense or perfect) without a preceding modal hedge AND without a
    person-type subject (your + customer noun, bare pronoun). This catches
    capability-as-subject assertions like "real-time margin insights have
    improved resource allocation" that the customer-subject detectors miss.

    Exclusions:
    - Modal hedges (would/could/may/might/should) make it POSSIBLE.
    - "your teams/clients/..." is a person subject (handled by other branches).
    - Bare pronouns (they/we/you) are person subjects.
    - do/does/did before the verb means base form, not past tense.
    """
    low = text.lower()
    for m in _REALIZED_OUTCOME_VERB_RE.finditer(low):
        preceding = low[max(0, m.start() - 40):m.start()]
        if _MODAL_HEDGE_RE.search(preceding):
            continue
        if _QUESTION_AUX_RE.search(preceding):
            continue
        if _YOUR_CUSTOMER_RE.search(preceding):
            continue
        if _BARE_PRONOUN_SUBJECT_RE.search(preceding):
            continue
        # "your"/"yours" in a scope/analogy phrase: the third-party
        # branch handles these ("operators in your sector", "shops of
        # your size", "outfits like yours"). Let it.
        if _YOUR_SCOPE_RE.search(preceding):
            continue
        return True
    return False


# TASK-918: indefinite/analogous third-party outcome claims.
#
# THE DEFECT: "Can I share a brief example of how real-time margin insights
# have improved resource decisions for others?" passes every gate. The
# existing customer-outcome detector watches named customer subjects
# (clients, customers, teams, ...) but "others" is indefinite - it names
# no specific group. The same escape applies to "other teams", "similar
# firms", "companies like yours", "someone in your position", "elsewhere",
# "other businesses", "organisations like yours".
#
# THE SEMANTIC CLASS: a product/capability/intervention + an asserted
# business outcome + an indefinite or analogous third party. The third
# party phrase alone is NOT the claim - "How do teams like yours currently
# track project margin?" carries the same phrase but asserts no outcome
# and must NOT be refused. The claim is the phrase PLUS an asserted
# outcome (verb + metric, or comparative + metric).
#
# WHY NOT ADD "others" TO THE SUBJECT LIST. TASK-917's subject alternation
# is clients|customers|users|teams|companies|firms|agencies|studios. Adding
# indefinite references there would conflate two different detectors: one
# watches named customer subjects, the other watches indefinite/analogous
# third parties. They share the evidence gate but not the pattern.
#
# EVIDENCE-SENSITIVE: every refusal disappears when offers.missing() no
# longer reports "customer case studies" / "verified benchmarks".

# TASK-919: model the CLASS of indefinite/analogous third-party references
# instead of listing phrases. The previous fixed-phrase list knew "other
# teams", "similar firms", "teams like yours", "someone in your position"
# and missed "comparable businesses", "another agency in your space",
# "others in retail", "peers in your industry", "several organisations",
# "folks in your position", "businesses of your size".
#
# The class: [modifier] + [group noun] (+ [scope]), plus bare indefinites
# that carry indefiniteness on their own (peers, folks, others).
#
# Modifiers: other, another, similar, comparable, several, many, some,
# most, various, certain, a few.
# Group nouns: businesses, organisations/organizations, firms, companies,
# agencies, studios, teams, clients, customers, peers, folks, people,
# operators, providers.
# Scope: like yours, in your industry/space/sector/market/position,
# of your size, in <sector>.
# Bare: elsewhere, for others.
_TP_GROUP_NOUNS = (
    r"businesses?|organisations?|organizations?|firms?|companies?"
    r"|agenc(?:y|ies)|studios?|teams?|clients?|customers?"
    r"|peers?|folks|people|operators?|providers?"
)
_TP_MODIFIERS = (
    r"other|another|similar|comparable|several|many|some|most"
    r"|various|certain|a\s+few"
)
_TP_SCOPE = (
    r"like\s+yours"
    r"|in\s+your\s+(?:industry|space|sector|market|position)"
    r"|of\s+your\s+size"
    r"|in\s+(?:retail|healthcare|finance|technology|manufacturing"
    r"|consulting|education|media|hospitality|construction"
    r"|real\s+estate|energy|telecommunications|logistics)"
)

_THIRD_PARTY_INDEFINITE_RE = re.compile(
    r"\b(?:"
    # Bare indefinites that carry indefiniteness alone: peers, folks, others.
    # May carry an optional scope ("peers in your industry").
    r"(?:peers|folks|others)"
    r"(?:\s+(?:" + _TP_SCOPE + r"))?"
    # Modifier + group noun, with optional scope.
    r"|(?:for\s+(?:other\s+)?)?others?"
    r"|(?:another|" + _TP_MODIFIERS + r")"
    r"\s+(?:" + _TP_GROUP_NOUNS + r")"
    r"(?:\s+(?:" + _TP_SCOPE + r"))?"
    # Group noun + scope (no modifier needed when scope is present).
    r"|(?:another|(?:" + _TP_MODIFIERS + r"))?\s*(?:" + _TP_GROUP_NOUNS + r")"
    r"\s+(?:" + _TP_SCOPE + r")"
    # TASK-920: scope marker is the signal, not the noun. When an explicit
    # analogy/scope marker follows ANY noun, treat that noun as a third-party
    # reference without consulting the group list. The markers are: like yours,
    # in your industry/sector/space/market/position, of your size.
    r"|\w+\s+(?:" + _TP_SCOPE + r")"
    # "elsewhere" (standalone adverb)
    r"|elsewhere"
    # "across other businesses"
    r"|across\s+other\s+businesses?"
    # "someone in your position"
    r"|someone\s+in\s+your\s+position"
    r")\b", re.I)

# TASK-919: widen the outcome assertion for the third-party branch.
# The shared _outcome_verb_pattern() and _outcome_metric_pattern() cover
# the core stems and metrics. The third-party branch adds:
# - "gain" as an extra metric (e.g. "delivered similar gains")
# - "similar" as an extra comparative direction word
# - "work(s/ed) well" as an effectiveness pattern
_TP_EXTRA_METRICS = r"\bgains?\b"
_TP_EXTRA_COMPARATIVES = r"similar"

_THIRD_PARTY_OUTCOME_RE = re.compile(
    r"(?:"
    # outcome verb ... metric (forward, shared + extra metrics)
    r"\b(?:" + _outcome_verb_pattern() + r")\b.{0,40}"
    r"(?:" + _outcome_metric_pattern() + r"|" + _TP_EXTRA_METRICS + r")"
    r"|"
    # metric ... outcome verb (reversed, shared + extra metrics)
    r"(?:" + _outcome_metric_pattern() + r"|" + _TP_EXTRA_METRICS + r").{0,40}"
    r"\b(?:" + _outcome_verb_pattern() + r")\b"
    r"|"
    # comparative + metric (shared comparatives + "similar", shared + extra metrics)
    r"\b(?:" + r"better|higher|lower|greater|stronger|faster" + r"|"
    + _TP_EXTRA_COMPARATIVES + r")\b.{0,30}"
    r"(?:" + _outcome_metric_pattern() + r"|" + _TP_EXTRA_METRICS + r")"
    r"|"
    # effectiveness: "work(s/ed) well" - asserts the thing was effective
    r"\bwork(?:ed|s)?\s+well\b"
    r")", re.I)


def _customer_outcome_gaps():
    """The gap keys that make a customer-outcome claim unlicensed.

    Read from `offers.missing()`. If neither "customer case studies" nor
    "verified benchmarks" is reported as a gap, evidence exists and the
    claim passes through to the normal evidence rules.
    """
    from . import offers
    gaps = offers.missing()
    return [g for g in gaps
            if g.get("gap") in ("customer case studies",
                                "verified benchmarks")]


def _has_outcome_complement(low, m):
    """TASK-917 + TASK-921: does an outcome-metric noun appear in the clause?

    An outcome claim needs an object. "Our customers improved" is not a
    claim about anything until it names WHAT improved. This function
    checks whether a business-outcome noun from the shared _OUTCOME_METRICS
    vocabulary appears in the SAME CLAUSE as the match.

    TASK-921: replaced the 60-char window with clause-scoping. The metric
    must be in the same clause as the verb, not just within a fixed
    distance. This prevents a modifier from pushing the metric past the
    window while keeping it in the same assertion.
    """
    metric_re = _outcome_metric_pattern()
    clause = _clause_containing(low, m.start())
    if re.search(metric_re, clause, re.I):
        return True
    return False


def customer_outcome_claim(text, exclude=()):
    """Does this text assert customer outcomes with no licensed evidence?

    Returns a refusal reason string when the text contains a customer-outcome
    pattern AND the system has no licensed evidence for one. Returns None
    when the text is clean or when evidence exists.

    A capability statement ("Productive shows margin per project") is NOT a
    customer-outcome claim: the subject is the product, not a customer.

    TASK-916: three refinements over TASK-915:
    1. "see" is no longer an outcome verb (perception != achievement).
    2. "your team/agency/..." is the prospect, excluded from customer
       subjects in every branch.
    3. Perception phrasings with a comparative direction word ("clients
       see higher profitability") still refuse via a dedicated branch.

    TASK-917: two fixes, one idea - an outcome claim needs an object:
    1. The achievement branch now requires an outcome-metric complement
       within a 60-char window. "clients raise this constantly" has no
       outcome noun, so it is no longer refused.
    2. The comparative branch metric list is widened to the client's
       real vocabulary (turnaround, reporting cycle, throughput, ...),
       shared via _OUTCOME_METRICS with the achievement complement check.

    TASK-918: indefinite/analogous third-party outcome claims.
    A fourth branch catches outcomes asserted for unspecified audiences:
    "for others", "other teams", "similar firms", "companies like yours",
    "someone in your position", "elsewhere", "across other businesses".
    The third-party phrase alone is not the claim - it must co-occur with
    an outcome assertion (verb + metric, or comparative + metric). This
    prevents overblocking: "How do teams like yours currently track
    project margin?" carries the phrase but asserts no outcome.
    """
    if not text:
        return None
    low = text.lower()

    # TASK-921 A: subjectless realized-outcome assertion. A capability or
    # intervention as subject + a realized outcome verb (past/perfect
    # aspect, no modal hedge). "Real-time margin insights have improved
    # resource allocation" - no customer subject, no third party, but
    # asserts that something HAS PRODUCED an outcome.
    if _subjectless_realized_outcome(text):
        gaps = _customer_outcome_gaps()
        if gaps:
            gap_names = ", ".join(g.get("gap", "") for g in gaps)
            return (f"customer-outcome claim with no licensed evidence "
                    f"(missing: {gap_names})")

    # Branch 0: a NAMED organisation credited with an outcome. Placed with
    # the other subject branches and gated on the same evidence, because it
    # is the same claim with a more believable subject - see `_NAMED_ORG_RE`
    # for the four measured sentences that motivated it, two refused and two
    # that cleared both gates.
    if _named_third_party_outcomes(text, exclude=exclude):
        gaps = _customer_outcome_gaps()
        if gaps:
            gap_names = ", ".join(g.get("gap", "") for g in gaps)
            return (f"customer-outcome claim with no licensed evidence "
                    f"(missing: {gap_names})")

    # Branch 1: benchmark phrase (e.g. "typical clients", "case study").
    bm = _BENCHMARK_PHRASE.search(low)
    if bm:
        # TASK-916: "your typical clients" is the prospect's clients, not
        # ours. But "your team" elsewhere in the text must NOT defeat a
        # standalone benchmark phrase ("benchmark example ... your team").
        # Only exclude when the "your customer" span overlaps the benchmark.
        sp = _SECOND_PERSON_CUSTOMER.search(low)
        if sp and sp.start() < bm.end() and sp.end() > bm.start():
            # TASK-918: fall through to the third-party branch before
            # giving up. A "your typical clients" exclusion does not
            # mean the text is clean - it may still carry an indefinite
            # third-party outcome elsewhere.
            if not (_THIRD_PARTY_INDEFINITE_RE.search(low)
                    and _THIRD_PARTY_OUTCOME_RE.search(low)):
                return None
        # If benchmark matched and was not excluded, fall through to
        # the evidence gate below.
    else:
        # Branch 2: customer subject + outcome verb (achievement).
        # TASK-921: clause-scoped attribution replaces the 40-char window.
        # A customer subject and outcome verb in the same clause are
        # attributed to each other whatever the distance; across a clause
        # boundary they are not.
        ach = _customer_outcome_clause_match(low)
        if ach:
            if not _has_outcome_complement(low, ach):
                # TASK-918: the named-customer branch did not match
                # (no complement). Check the third-party branch before
                # giving up.
                if not (_THIRD_PARTY_INDEFINITE_RE.search(low)
                        and _THIRD_PARTY_OUTCOME_RE.search(low)):
                    return None
        # Branch 3: customer subject + see + comparative + metric.
        elif _COMPARATIVE_OUTCOME_RE.search(low):
            pass
        else:
            # TASK-918: neither named-customer branch matched. Check
            # the indefinite/analogous third-party branch.
            if not (_THIRD_PARTY_INDEFINITE_RE.search(low)
                    and _THIRD_PARTY_OUTCOME_RE.search(low)):
                return None

    gaps = _customer_outcome_gaps()
    if not gaps:
        return None
    gap_names = ", ".join(g.get("gap", "") for g in gaps)
    return (f"customer-outcome claim with no licensed evidence "
            f"(missing: {gap_names})")


def verify(step, rec, contact=None, chosen=()):
    """Check a whole step - subject and body together."""
    text = " ".join(str(step.get(k) or "") for k in ("subject", "body", "note"))
    return check(text, rec, contact, chosen)


class UnsupportedClaim(RuntimeError):
    """A draft asserted something nothing supports. It is regenerated, not
    edited: a patched sentence leaves a message built around a fact it no
    longer makes."""


def require(step, rec, contact=None, chosen=()):
    problems = verify(step, rec, contact, chosen)
    if problems:
        raise UnsupportedClaim("; ".join(
            f"{p['sentence']!r}: {p['why']}" for p in problems[:2]))
    return True
