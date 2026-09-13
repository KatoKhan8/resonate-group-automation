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

from . import evidence

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
    "relocated", "office in", "appointed", "promoted", "published", "wrote",
    "posted", "spoke at", "keynote",
)

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
    r"\b(?:our|the|your|that|a)\s+(?:last|previous|recent|earlier|first|"
    r"initial|prior)\s+(?:conversation|call|chat|exchange|email|message|"
    r"note|discussion|meeting|thread)\b",
    r"\b(?:as|like)\s+(?:we\s+)?(?:discussed|mentioned|agreed|promised|"
    r"said|covered|noted)\b",
    r"\bfollow(?:ing)?[- ]?up\s+(?:on|from|about|to)\s+(?:our|your|the|my|"
    r"that|last|previous)\b",
    r"\b(?:circling|circle|looping|loop|checking|reaching)\s+back\b",
    r"\b(?:when|since|after|before)\s+we\s+(?:last\s+)?"
    r"(?:spoke|talked|met|connected|chatted)\b",
    # things they are said to have told us
    r"\byou\s+(?:\w+\s+){0,2}"
    r"(?:mentioned|told|said|asked|replied|responded|wrote|confirmed|"
    r"agreed|promised|requested|shared with)\b",
    r"\b(?:per|from)\s+(?:our|your)\s+(?:last\s+)?(?:conversation|call|"
    r"email|note|message|chat|discussion)\b",
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
    return None


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
    # diagnosis saying so was stored. `rec["context"]` is the operator-written
    # version of the same story and is still support.
    #
    # `research`, `company_facts` and `chosen` stay: those come from providers
    # and from research. The line between them is not how trustworthy the text
    # reads, it is who wrote it.
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
        if word not in support and not _is_paraphrase(low, support,
                                                        identity):
            return False, (f"'{word}' is asserted but nothing stored "
                           "mentions it")
    return True, None


def identity_tokens(rec, contact=None):
    """The words that are in support no matter what, so prove nothing.

    Who this is and where they work: the company, its domain, the industry and
    size we filed it under, and the person's own name and title. Every one of
    them is in `support_text` by construction, which is why they cannot be
    allowed to count as coverage - see `_is_paraphrase`.
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


def check(text, rec, contact=None, chosen=()):
    """Every unsupported claim in this text. Empty means it may ship."""
    support = support_text(rec, contact, chosen)
    identity = identity_tokens(rec, contact)
    contacted = prior_contact(rec, contact)
    problems = []
    for sentence in sentences(text):
        if not is_claim(sentence):
            continue
        ok, why = check_sentence(sentence, support, identity, contacted)
        if not ok:
            problems.append({"sentence": sentence[:160], "why": why})
    return problems


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
