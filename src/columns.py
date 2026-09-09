#!/usr/bin/env python3
"""What the columns in somebody else's export actually mean.

## The problem this solves

`upload.parse` required a literal `domain` column and read `company`,
`email` and `title` by their exact lowercase names. No real export uses
those words. An Apollo file says "Company Website" and "Work Email"; a CRM
export says "Organization" and "Job Title"; a spreadsheet somebody
maintains by hand says "Website" and "Role". Every one of them was refused
outright, with an error naming a column the user had never heard of.

So this maps foreign headers onto canonical fields, and the whole design is
about being deterministic rather than clever. A mapping that guesses is
worse than one that refuses: the guess writes a person's *personal* address
into the field the sender uses, or a company's LinkedIn page into the field
that identifies a human being.

## Matching

Separators carry no meaning here. `First Name`, `first_name` and
`FirstName` are the same column with different punctuation, so a header is
reduced to its letters and digits before anything is compared. Nothing else
is normalised - no stemming, no edit distance, no substring search. A
header either is a spelling this module knows or it is unmapped.

## Two exclusions that are safety, not tidiness

**`personal email` never means `email`.** The canonical email is the one we
would write to, and a personal address arriving in a work export is exactly
the address nobody consented to be contacted at. It is preserved as source
metadata and never mapped.

**`company linkedin url` never means `linkedin`.** The contact's LinkedIn
identity is a *person*; a company page is not one. `dedupe` treats a
canonical profile URL as identity, so mapping a company page there would
merge every employee at that company into one contact.

## Ambiguity

Spellings are ranked, most specific first. When a file carries both `Work
Email` and `Email`, the more specific one wins and the decision is
reported rather than hidden - an operator can see which column was used
and which was set aside.

The one case that cannot be resolved is a file carrying the *same* header
twice. There is no rule that distinguishes them, so neither is mapped and
the field is reported as needing a person.

## What is not mapped is not lost

Every header this module does not recognise is returned as `unmapped`, and
`apply` keeps those values on the row under `source`. They are provenance,
never a decision: nothing downstream may read them to answer a question
about eligibility, identity or safety.
"""
import re

VERSION = "columns-1"

DOMAIN = "domain"
COMPANY = "company"
EMAIL = "email"
LINKEDIN = "linkedin"
NAME = "name"
FIRST_NAME = "first_name"
LAST_NAME = "last_name"
TITLE = "title"

CANONICAL = (DOMAIN, COMPANY, EMAIL, LINKEDIN, NAME, FIRST_NAME, LAST_NAME,
             TITLE)

# Canonical field -> spellings, most specific first. Rank is position: when
# two headers in one file both claim a field, the earlier spelling wins.
#
# Deliberately absent, and each absence is load-bearing:
#   personalemail, homeemail   never the address we would write to
#   companylinkedinurl         a company page is not a person
#   url, link, id, notes       too vague to mean one thing
ALIASES = {
    DOMAIN: ("companydomain", "companywebsite", "websitedomain", "domain",
             "companyurl", "website", "companysite", "webaddress",
             "organizationwebsite", "organisationwebsite", "accountdomain",
             "accountwebsite"),
    COMPANY: ("companyname", "organizationname", "organisationname",
              "accountname", "company", "organization", "organisation",
              "account", "employer", "employername"),
    EMAIL: ("workemail", "businessemail", "companyemail", "professionalemail",
            "emailaddress", "email", "primaryemail", "contactemail",
            "workemailaddress", "businessemailaddress"),
    LINKEDIN: ("personlinkedinurl", "contactlinkedinurl", "linkedinprofileurl",
               "linkedinprofile", "linkedinurl", "linkedin", "lilink",
               "linkedinlink", "profileurl"),
    NAME: ("fullname", "contactname", "personname", "leadname", "name"),
    FIRST_NAME: ("contactfirstname", "firstname", "givenname", "forename",
                 "fname"),
    LAST_NAME: ("contactlastname", "lastname", "surname", "familyname",
                "lname"),
    TITLE: ("jobtitle", "contacttitle", "positiontitle", "title", "position",
            "jobrole", "role", "designation"),
}

# spelling -> (canonical field, rank)
_LOOKUP = {}
for _field, _spellings in ALIASES.items():
    for _rank, _spelling in enumerate(_spellings):
        # A spelling belongs to one field. If this ever fires, two alias
        # lists have drifted into claiming the same word.
        assert _spelling not in _LOOKUP, _spelling
        _LOOKUP[_spelling] = (_field, _rank)


def normalise(header):
    """A header reduced to what it says, ignoring punctuation and case."""
    return re.sub(r"[^a-z0-9]+", "", str(header or "").lower())


def resolve(headers):
    """Decide what each column is. Returns a report, decides nothing else.

    `mapping`     original header -> canonical field
    `chosen`      canonical field -> the header used for it
    `set_aside`   canonical field -> headers that also matched, unused
    `unmapped`    headers this module does not recognise
    `ambiguous`   canonical fields no rule could settle
    `duplicates`  headers appearing more than once in the file
    """
    seen = []
    duplicates = []
    for header in headers or ():
        if header is None:
            continue
        key = normalise(header)
        if not key:
            continue
        if key in [normalise(h) for h in seen]:
            duplicates.append(header)
        seen.append(header)

    claims = {}
    unmapped = []
    for header in seen:
        found = _LOOKUP.get(normalise(header))
        if found is None:
            unmapped.append(header)
            continue
        field, rank = found
        claims.setdefault(field, []).append((rank, header))

    mapping, chosen, set_aside, ambiguous = {}, {}, {}, []
    duplicate_keys = {normalise(h) for h in duplicates}
    for field, candidates in claims.items():
        candidates.sort(key=lambda pair: (pair[0], pair[1]))
        # The same header twice is the one case ranking cannot settle:
        # both are equally the field, and picking either would be a coin
        # flip over which column's values are the real ones.
        if any(normalise(header) in duplicate_keys
               for _, header in candidates):
            ambiguous.append(field)
            continue
        best = candidates[0][1]
        mapping[best] = field
        chosen[field] = best
        rest = [header for _, header in candidates[1:]]
        if rest:
            set_aside[field] = rest
            unmapped.extend(rest)

    return {"mapping": mapping, "chosen": chosen, "set_aside": set_aside,
            "unmapped": unmapped, "ambiguous": sorted(ambiguous),
            "duplicates": duplicates, "version": VERSION}


def apply(row, resolution):
    """One raw row as canonical fields, with everything else kept aside.

    Returns `(canonical, source)`. `source` is provenance: the columns this
    file carried that Resonate has no opinion about. Nothing downstream may
    read it to decide eligibility, identity or safety - that is the whole
    reason it is a separate dict rather than extra keys on the row.
    """
    mapping = resolution["mapping"]
    canonical, source = {}, {}
    for header, value in (row or {}).items():
        if header is None:
            continue
        field = mapping.get(header)
        if field is None:
            name = str(header).strip()
            if name:
                source[name] = value
            continue
        canonical[field] = value
    return canonical, source


def missing(resolution, required=(DOMAIN,)):
    """Which required fields no column supplied."""
    return [field for field in required if field not in resolution["chosen"]]


def describe(resolution):
    """A sentence per decision, for an operator rather than a log."""
    lines = []
    for field in CANONICAL:
        header = resolution["chosen"].get(field)
        if header:
            note = ""
            aside = resolution["set_aside"].get(field)
            if aside:
                note = " (also matched, not used: " + ", ".join(aside) + ")"
            lines.append(f"{field} <- {header}{note}")
    for field in resolution["ambiguous"]:
        lines.append(f"{field} <- needs a person: the file carries that "
                     f"column more than once")
    return lines
