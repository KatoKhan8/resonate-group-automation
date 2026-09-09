#!/usr/bin/env python3
"""Somebody pointing at somebody else, and how sure we are who that is.

## Why this is not the existing referral edge

`events.REFERRAL_RECORDED` already models one contact referring another, and
`account.referrals` reads it. That edge needs both ends to be contacts we
already hold, and it is deliberately never inferred - its own comment says
so: "a classifier reading 'Sarah handles this' out of free text and writing
an edge would manufacture an introduction that never happened, and the next
message would open by claiming it did."

That rule stands. What was missing is the step before it. A reply saying
"I'm not the right person, talk to Sarah" carries something worth keeping
even though Sarah is nobody we know, and throwing it away was losing the
most useful thing a wrong-person reply contains.

So this records a *mention*: what the reply said, and what could be proved
about it. A mention is never an edge and never a contact.

## Identity is exact or it is unknown

An address or a canonical profile URL is identity. A name is not - two
people share one and one person has three - so a name alone resolves to
`UNKNOWN` and waits for a person, however obvious it looks.

The four answers:

    EXACT_MATCH  an address or profile in the reply is already a contact here
    CANDIDATE    an address or profile, but nobody we hold
    AMBIGUOUS    it matches more than one contact, so it identifies nobody
    UNKNOWN      a name, or nothing usable

## What it will not do

It creates no contact, selects nobody, and sends nothing. The referrer's own
reply keeps its meaning: a referral is not a refusal, and marking somebody
negative because they helped is the other way to get this wrong.
"""
import re

from . import dedupe, linkedin

VERSION = "referral-1"

EXACT_MATCH = "exact_match"
CANDIDATE = "candidate"
AMBIGUOUS = "ambiguous"
UNKNOWN = "unknown"

STATUSES = (EXACT_MATCH, CANDIDATE, AMBIGUOUS, UNKNOWN)

STATUS_LABEL = {
    EXACT_MATCH: "already a contact here",
    CANDIDATE: "an address or profile we do not hold",
    AMBIGUOUS: "matches more than one contact",
    UNKNOWN: "a name only - a person has to say who this is",
}

# The phrases that hand somebody on. Deliberately narrow: this decides
# whether a reply is a referral at all, and a loose cue turns "I spoke to
# Sarah last week" into an introduction nobody made.
CUES = (
    r"(?:talk|speak|reach out|reach|write) to",
    r"(?:contact|email|ping|try|ask|approach)",
    r"(?:you )?(?:should|want|need) to (?:talk|speak|contact|email)",
    r"(?:that|this) (?:would be|is)",
    r"(?:the )?(?:right|best|correct) person is",
    r"(?:forward|forwarding|passed?|passing) (?:this |it )?(?:on )?to",
    r"copying in", r"cc(?:'?ing)?",
)

EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")

# A name is one or two capitalised words. It is captured as evidence and
# never as identity, so the pattern only has to be good enough to show a
# person what was said - not good enough to act on.
#
# The cue is matched case-insensitively and the name is not, which is the
# whole reason for the scoped flag: "Copying in Dana Reed" starts a
# sentence, and a case-sensitive cue missed every referral that opened one.
# Making the *whole* pattern insensitive would be worse - "talk to someone
# else" would come back as the name "someone".
NAME = re.compile(
    r"\b(?i:" + "|".join(CUES) + r")\s+"
    r"((?:[A-Z][\w'-]+)(?:\s+[A-Z][\w'-]+)?)")


def evidence(text):
    """What the reply actually contains. No interpretation."""
    body = str(text or "")
    emails = []
    for found in EMAIL.findall(body):
        address = dedupe.normalise_email(found)
        if address and address not in emails:
            emails.append(address)

    profiles = []
    for token in re.findall(r"https?://[^\s<>\")]+", body):
        canonical = linkedin.canonical(token)
        if canonical and canonical not in profiles:
            profiles.append(canonical)

    names = []
    for found in NAME.findall(body):
        name = " ".join(found.split())
        if name and name not in names:
            names.append(name)

    return {"emails": emails[:5], "profiles": profiles[:5],
            "names": names[:5], "reader": VERSION}


def _contacts(rec):
    for contact in (rec or {}).get("contacts") or []:
        yield contact


def resolve(rec, found, referrer=None):
    """Who the reply pointed at, if that can be proved.

    `referrer` is the person who wrote it. Their own address in their own
    signature is not a referral to themselves, and reading it as one would
    turn every signed reply into an introduction.
    """
    referrer_contact = None
    for contact in _contacts(rec):
        if contact.get("key") == referrer:
            referrer_contact = contact
            break

    own_email = dedupe.normalise_email((referrer_contact or {}).get("email"))
    own_profile = linkedin.canonical((referrer_contact or {}).get("linkedin"))

    emails = [e for e in found["emails"] if e and e != own_email]
    profiles = [p for p in found["profiles"] if p and p != own_profile]

    matched = []
    for contact in _contacts(rec):
        if contact.get("key") == referrer:
            continue
        address = dedupe.normalise_email(contact.get("email"))
        profile = linkedin.canonical(contact.get("linkedin"))
        if (address and address in emails) or (profile and profile in profiles):
            if contact.get("key") not in matched:
                matched.append(contact.get("key"))

    if len(matched) > 1:
        return {"status": AMBIGUOUS, "contact": None, "matches": matched,
                "why": "the reply names identifiers belonging to more than "
                       "one contact here, so it identifies nobody"}
    if len(matched) == 1:
        return {"status": EXACT_MATCH, "contact": matched[0],
                "matches": matched,
                "why": "an address or profile in the reply is already a "
                       "contact on this account"}
    if emails or profiles:
        return {"status": CANDIDATE, "contact": None, "matches": [],
                "why": "the reply carries an address or profile we do not "
                       "hold, so somebody has to decide whether to add them"}
    if found["names"]:
        return {"status": UNKNOWN, "contact": None, "matches": [],
                "why": "a name with no address or profile. Two people share "
                       "a name and one person has three, so this is not an "
                       "identity"}
    return {"status": UNKNOWN, "contact": None, "matches": [],
            "why": "the reply names nobody we could act on"}


# Why a recorded mention cannot be turned into a contact.
NOT_A_CANDIDATE = "not_a_candidate"
ALREADY_HERE = "already_here"
SUPPRESSED = "suppressed"
READY = "ready"

PROMOTION_LABEL = {
    NOT_A_CANDIDATE: "there is no address or profile to add",
    ALREADY_HERE: "somebody on this account already has that identifier",
    SUPPRESSED: "that person has asked not to be contacted",
    READY: "this person can be added to the account",
}


def promotable(rec, entry, history=None, agency=None):
    """Whether a recorded mention can become a contact, and why not.

    Decided now rather than read from the status stored when the reply
    arrived. Somebody may have added that person in the meantime, or
    suppressed them, and a button whose answer is minutes old is a button
    that acts on a state that has gone.

    A name is still not an identity, so an `unknown` mention has nothing to
    add and says so. This module still creates nothing: it answers the
    question and the caller does the writing.
    """
    emails = [e for e in (entry or {}).get("emails") or [] if e]
    profiles = [p for p in (entry or {}).get("profiles") or [] if p]
    if not emails and not profiles:
        return {"status": NOT_A_CANDIDATE, "why": PROMOTION_LABEL[NOT_A_CANDIDATE],
                "email": None, "linkedin": None, "hygiene": None}

    email, profile = (emails[0] if emails else None,
                      profiles[0] if profiles else None)

    for contact in _contacts(rec):
        if ((email and dedupe.normalise_email(contact.get("email")) == email)
                or (profile
                    and linkedin.canonical(contact.get("linkedin")) == profile)):
            return {"status": ALREADY_HERE,
                    "why": PROMOTION_LABEL[ALREADY_HERE],
                    "email": email, "linkedin": profile, "hygiene": None,
                    "contact": contact.get("key")}

    verdict = None
    if history is not None or agency is not None:
        from . import hygiene

        verdict = hygiene.check(
            {"email": email, "linkedin": profile,
             "domain": rec.get("domain"), "company": rec.get("company")},
            history if history is not None else hygiene.index([]),
            agency=agency)
        if verdict["action"] == hygiene.SUPPRESS:
            return {"status": SUPPRESSED, "why": verdict["why"],
                    "email": email, "linkedin": profile, "hygiene": verdict}

    return {"status": READY, "why": PROMOTION_LABEL[READY],
            "email": email, "linkedin": profile, "hygiene": verdict}


def read(rec, text, referrer=None):
    """Evidence and resolution together, which is how a caller wants it."""
    found = evidence(text)
    answer = resolve(rec, found, referrer=referrer)
    return {"evidence": found, **answer,
            "label": STATUS_LABEL[answer["status"]],
            "needs_a_person": answer["status"] != EXACT_MATCH}
