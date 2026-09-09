#!/usr/bin/env python3
"""Which provider is next for one FIELD on one person, and why.

WHY A FIELD RATHER THAN A PERSON. Enrichment asked one question -
`enrich.usable_contacts`, which is "does this contact have an email" - and
used the answer to decide whether any person-level work was still worth doing.
So a person with a work address and no LinkedIn URL read as finished. That is
the wrong shape for a waterfall whose whole purpose is per-field fallback:
`blitz-domain-to-linkedin` exists precisely for "ContactOut gave us the
company but not its LinkedIn URL", and that condition could not be stated,
which is why `CONTACTOUT_NO_COMPANY_LINKEDIN` and `CONTACTOUT_INCOMPLETE` were
declared reason codes that nothing in `src/` ever produced.

An email does not suppress a LinkedIn lookup here, and a LinkedIn URL does not
suppress an email lookup. Each field carries its own state and its own next
step.

WHERE THE ORDER COMES FROM. `waterfall.STAGES` already held the ordered
provider list per stage, and `providers_for` / `first_provider` had no caller
outside `waterfall.py` itself - the executed order was the top-to-bottom
position of the `if ... and spend(...)` statements in `enrich.enrich_record`.
A table that appears to define the order while the order actually lives in
statement sequence is two things that can disagree, and they did: the table
put AI Ark ahead of Blitz for email discovery.

This module routes **from the table**. `next_step` walks
`waterfall.providers_for(stage)`, so the declared order is the executed order
by construction rather than by agreement.

WHAT IT MAY NOT DO. It never calls a provider and never writes a record - it
is a pure function of the record, exactly like `enrich.plan`, and
`tests/test_enrich.py::TestPlanIsPure` is the precedent. The difference from
the four planners already in this repository - `enrich.plan`,
`verification.plan`, `refresh.staleness`, `dmplan.for_company` - is that all
four are display-only, and `verification.py` carries a comment about the
production bug caused when its forecast and its execution disagreed. So this
one is written to be the thing execution asks, not a second opinion about it.
"""
import argparse
import json

from . import enrich, store, waterfall

# ------------------------------------------------------------------ states

KNOWN = "known"                     # a value is on the record
MISSING_CONFIRMED = "missing_confirmed"   # somebody was asked and had none
UNKNOWN = "unknown"                 # nobody has been asked
STALE = "stale"                     # known, but older than the field allows
CONFLICTED = "conflicted"           # two sources disagree about the value
UNSUPPORTED = "unsupported"         # no provider in the chain answers this

STATES = (KNOWN, MISSING_CONFIRMED, UNKNOWN, STALE, CONFLICTED, UNSUPPORTED)

# A field in one of these needs nothing bought for it.
SATISFIED = (KNOWN, UNSUPPORTED)


# ------------------------------------------------------------------ fields

PERSON = "person"
COMPANY = "company"


def _contact_email(rec, contact):
    return (contact or {}).get("email")


def _contact_linkedin(rec, contact):
    return (contact or {}).get("linkedin")


def _contact_phone(rec, contact):
    # There is no phone field on a contact anywhere in this build, and
    # `blitz.phone`'s own docstring says nothing consumes a phone number. A
    # field nothing stores is not "missing", it is unmodelled - reporting it
    # as missing would invite a call whose answer has nowhere to go.
    return None


def _company_linkedin(rec, contact):
    return (rec.get("company_facts") or {}).get("linkedin")


def _company_email_domain(rec, contact):
    return (rec.get("company_facts") or {}).get("email_domain")


def _company_profile(rec, contact):
    """The firmographics `company-information-from-domain` comes back with.

    Both, not either: a record holding an industry and no headcount has not
    had this question answered, and treating it as answered is how a company
    is scored on half a profile.
    """
    facts = rec.get("company_facts") or {}
    if facts.get("industry") and facts.get("employees"):
        return {"industry": facts["industry"], "employees": facts["employees"]}
    return None


FIELDS = {
    "work_email": {
        "scope": PERSON,
        "stage": waterfall.EMAIL_DISCOVERY,
        "read": _contact_email,
        "label": "work email address",
    },
    "linkedin_url": {
        "scope": PERSON,
        "stage": waterfall.LINKEDIN_URL,
        "read": _contact_linkedin,
        "label": "LinkedIn profile",
    },
    "company_linkedin": {
        "scope": COMPANY,
        "stage": waterfall.COMPANY_INFO,
        "read": _company_linkedin,
        "label": "company LinkedIn URL",
        # The address every Blitz search is keyed by, which is why dropping it
        # made `blitz-domain-to-linkedin` look unavoidable: the miss could not
        # be stated, so the fallback could never be justified.
        "reason": enrich.CONTACTOUT_NO_COMPANY_LINKEDIN,
        "filled_by": ("company-information-from-domain",
                      "blitz-domain-to-linkedin"),
    },
    "email_domain": {
        "scope": COMPANY,
        "stage": waterfall.COMPANY_INFO,
        "read": _company_email_domain,
        "label": "mail domain",
        "reason": enrich.CONTACTOUT_NO_EMAIL_DOMAIN,
        # ContactOut returns no mail domain under any spelling - that is a
        # gap rather than a miss, and it is why `blitz-linkedin-to-domain`
        # exists. So `company-information-from-domain` is not listed here:
        # counting it would make this field owe that call for ever, and a
        # field nothing can answer would license the same purchase on every
        # run.
        "filled_by": ("blitz-linkedin-to-domain",),
    },
    "company_profile": {
        "scope": COMPANY,
        "stage": waterfall.COMPANY_INFO,
        "read": _company_profile,
        "label": "industry and headcount",
        "reason": enrich.CONTACTOUT_MISSING_COMPANY_DATA,
        "filled_by": ("company-information-from-domain", "blitz-company"),
    },
    "phone": {
        "scope": PERSON,
        "stage": None,                   # deliberately unroutable
        "read": _contact_phone,
        "label": "phone number",
        "unsupported": ("no contact field stores a phone number and no channel "
                        "dials one, so an answer would have nowhere to go"),
    },
}

PERSON_FIELDS = tuple(n for n, f in FIELDS.items() if f["scope"] == PERSON)
COMPANY_FIELDS = tuple(n for n, f in FIELDS.items() if f["scope"] == COMPANY)

# The reason a per-field fallback is allowed to run. Declared by
# `waterfall.STAGES` for every non-ContactOut step on a per-field stage, and
# produced by nothing until this module existed.
DEFAULT_REASON = enrich.CONTACTOUT_INCOMPLETE


class UnknownField(KeyError):
    """A field this module has no routing policy for. Never guessed at."""


def field(name):
    if name not in FIELDS:
        raise UnknownField(
            f"{name} is not a routable field. Known: {', '.join(sorted(FIELDS))}")
    return FIELDS[name]


# ------------------------------------------------------------------- state

def calls_for(stage, provider):
    """Every call this stage lists for one provider."""
    return tuple(step["call"] for step in waterfall.STAGES[stage]["providers"]
                 if step["provider"] == provider)


def tried(rec, stage, provider=None):
    """Which providers have already been asked this stage's question.

    Read from the waterfall ledger rather than from a flag, which is the
    convention `enrich.already_bought` set: the ledger is the durable record
    of what was bought, and a second representation of it is how the two
    drift.

    Matched on the CALL rather than on the row's `stage`, because
    `enrich.CALL_STAGE` maps each call to exactly one stage while several
    calls answer more than one question. `decision-makers` returns a person's
    name, profile and address in one response and is filed under
    `people_discovery`; asking "has anyone been asked for this person's
    LinkedIn URL" by matching `stage == linkedin_url` therefore says no
    forever, and the fallback after it would be bought against a question
    ContactOut had already answered.

    Company-scoped on purpose. `decision-makers` is one call that returns
    every person at a company, so "has ContactOut been asked for people here"
    is a fact about the company, not about one contact. A per-person call -
    `blitz-email` is the first - would need a `contact` column on the ledger
    row, which `waterfall.entry` does not carry today.
    """
    wanted = {}
    for step in waterfall.STAGES[stage]["providers"]:
        wanted.setdefault(step["call"], step["provider"])
    out = []
    for row in rec.get("waterfall") or []:
        who = wanted.get(row.get("call"))
        if who is None:
            continue
        if provider and who != provider:
            continue
        out.append(who)
    return tuple(out)


def state_of(rec, name, contact=None):
    """The canonical state of one field. No I/O, no provider, no guessing."""
    spec = field(name)
    if spec.get("unsupported"):
        return UNSUPPORTED
    value = spec["read"](rec, contact)
    if value not in (None, "", [], {}):
        return KNOWN
    # Nothing on the record. Whether that is "nobody asked" or "somebody
    # asked and there is none" is the difference between a call worth making
    # and a call already made, and the ledger is what tells them apart.
    #
    # Missing evidence is never positive evidence: with no ledger row this is
    # UNKNOWN, never MISSING_CONFIRMED.
    return MISSING_CONFIRMED if tried(rec, spec["stage"]) else UNKNOWN


# -------------------------------------------------------------------- plan

def _reason_for(spec, asked):
    """The reason code a fallback step must carry to be allowed to run."""
    return spec.get("reason") or DEFAULT_REASON


def next_step(rec, name, contact=None):
    """The next provider for this field, taken from the ordered table.

    Returns `(step, reason)` or `(None, why_not)`. The walk is
    `waterfall.providers_for(stage)` in declared order, skipping any provider
    already asked, and refusing any fallback whose `requires_reason` this
    field cannot supply.
    """
    spec = field(name)
    stage = spec["stage"]
    if stage is None:
        return None, spec.get("unsupported", "no stage routes this field")
    asked = tried(rec, stage)
    reason = _reason_for(spec, asked)
    refused = None
    for step in waterfall.STAGES[stage]["providers"]:
        if step["provider"] in asked:
            continue
        if not waterfall.is_fallback(stage, step["provider"], step["call"]):
            return step, "the primary for this stage has not been asked"
        allowed, why = waterfall.may_fall_back(stage, step["provider"], reason,
                                               step["call"])
        if not allowed:
            # This step answers a different question. `company_information`
            # holds three Blitz calls for three different fields, so the one
            # whose `requires_reason` this field cannot supply is not a
            # refusal - it is simply not this field's step. Keep walking, and
            # only report the refusal if nothing later matches.
            refused = refused or why
            continue
        return step, reason
    return None, refused or "every provider for this stage has been asked"


def plan_field(rec, name, contact=None):
    """What this field is, what it still needs, and what that would cost.

    The one shape both execution and audit read. `requires_call` is the
    decision; everything beside it is why.
    """
    spec = field(name)
    stage = spec["stage"]
    state = state_of(rec, name, contact)
    value = spec["read"](rec, contact)
    chain = (waterfall.providers_for(stage) if stage else ())

    plan = {
        "field": name,
        "label": spec["label"],
        "scope": spec["scope"],
        "record": rec.get("id"),
        "contact": (contact or {}).get("key") if spec["scope"] == PERSON else None,
        "stage": stage,
        "state": state,
        "value": value,
        "source": None,
        "fallback_chain": list(chain),
        "asked": list(tried(rec, stage)) if stage else [],
        "next_provider": None,
        "next_call": None,
        "reason": None,
        "expected_cost": 0,
        "requires_call": False,
    }
    if name == "work_email":
        plan["source"] = (contact or {}).get("email_source")

    if state in SATISFIED:
        plan["reason"] = (spec.get("unsupported") if state == UNSUPPORTED
                          else "field already satisfied")
        return plan

    step, why = next_step(rec, name, contact)
    if step is None:
        plan["reason"] = why
        return plan
    plan["next_provider"] = step["provider"]
    plan["next_call"] = step["call"]
    plan["reason"] = why
    plan["expected_cost"] = enrich.COSTS.get(step["call"], 0)
    plan["requires_call"] = True
    return plan


def plan_contact(rec, contact):
    """Every person-level field for one person."""
    return [plan_field(rec, name, contact) for name in PERSON_FIELDS]


def plan_record(rec):
    """Every field this record could still route, company and person."""
    rows = [plan_field(rec, name) for name in COMPANY_FIELDS]
    for group in ("contacts", "excluded"):
        for contact in rec.get(group) or []:
            rows += plan_contact(rec, contact)
    return rows


def gaps(rec):
    """Only the fields that would justify a call. The execution question."""
    return [row for row in plan_record(rec) if row["requires_call"]]


CALL = "company-information-from-domain"


def company_info_is_owed(rec):
    """Would `company-information-from-domain` still tell us anything?

    The execution-side question, asked by `enrich.enrich_record` rather than
    computed beside it. False when every company field that call fills is
    already on the record - which is the difference between "no ledger row
    exists" and "we already know this", and on the Productive estate that
    difference was twenty-five records' worth of re-purchase.

    A field in MISSING_CONFIRMED still owes the call nothing: somebody has
    already been asked and had none. UNKNOWN is the only state that owes it.

    Asked only of the fields this call actually fills. `email_domain` is the
    reason that distinction matters: ContactOut never returns one, so a
    predicate over every company field would find it permanently UNKNOWN and
    license the purchase on every run for ever.
    """
    return any(state_of(rec, name) == UNKNOWN
               for name, spec in FIELDS.items()
               if spec["scope"] == COMPANY
               and CALL in (spec.get("filled_by") or ()))


def cost_of(rows):
    """What the planned calls would actually bill.

    Deduplicated per record per call, because one call answers a stage's
    question for everybody at the company: `decision-makers` returns every
    person in one response, so charging it once per person per field reported
    a 50-record estate at hundreds of credits when the real exposure is tens.
    A forecast that over-reports is not the safe direction it looks like - it
    is the number somebody sizes a cap against.
    """
    seen = set()
    total = 0
    for row in rows:
        if not row["requires_call"]:
            continue
        key = (row.get("record"), row.get("next_call"))
        if key in seen:
            continue
        seen.add(key)
        total += row["expected_cost"]
    return total


# --------------------------------------------------------------------- CLI

def _table(rows):
    head = ("COMPANY", "PERSON", "FIELD", "STATE", "SOURCE", "NEXT", "WHY",
            "COST")
    out = [head]
    for r in rows:
        out.append((
            str(r.get("domain") or r.get("record") or ""),
            str(r.get("contact") or "-"),
            r["field"],
            r["state"],
            str(r.get("source") or "-"),
            str(r.get("next_provider") or "-"),
            (r.get("reason") or "")[:52],
            str(r["expected_cost"]) if r["requires_call"] else "0",
        ))
    widths = [max(len(row[i]) for row in out) for i in range(len(head))]
    return "\n".join("  ".join(cell.ljust(widths[i])
                               for i, cell in enumerate(row)).rstrip()
                     for row in out)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--client", help="only this client's records")
    p.add_argument("--id", help="only this record")
    p.add_argument("--gaps", action="store_true",
                   help="only fields that would justify a call")
    p.add_argument("--json", action="store_true")
    a = p.parse_args(argv)

    rows = []
    for rec in store.load():
        if a.client and rec.get("client") != a.client:
            continue
        if a.id and rec.get("id") != a.id:
            continue
        for row in (gaps(rec) if a.gaps else plan_record(rec)):
            row["domain"] = rec.get("domain")
            rows.append(row)

    if a.json:
        print(json.dumps({"fields": rows, "expected_cost": cost_of(rows)},
                         indent=2, sort_keys=True))
    else:
        print(_table(rows))
        print(f"\n{len(rows)} field(s); "
              f"{sum(1 for r in rows if r['requires_call'])} would justify a "
              f"call; expected cost {cost_of(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
