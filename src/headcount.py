#!/usr/bin/env python3
"""How many people work here, who said so, and what two disagreeing answers mean.

## Why a company's size needs a module and its industry does not

Size is the only structural criterion this client rejects on numerically, and
it is the one every provider states differently. ContactOut's `/domain/enrich`
returns `employees`, which `src/icpstructural.py` establishes is frequently
the LOWER BOUND OF A BAND rather than a headcount. Blitz returns
`employees_on_linkedin`, a count, beside `size`, a band - and on the one live
Blitz response this repository holds, those two disagree with each other
(`employees_on_linkedin: 19` beside `size: "1-10"`).

So "how many people work here" is not a field. It is a set of statements by
named sources, and the useful question is whether they agree about the only
thing the client's criteria turn on: which side of the tolerated floor the
company falls.

## A CONFLICT IS NEVER A FAIL AND NEVER A PASS

One provider says four people, another says sixty. Taking the larger
qualifies a company on evidence half of which says it does not qualify;
taking the smaller rejects one on evidence half of which says it does. Both
are a guess wearing a number.

    AGREED          every estimating source falls the same side of the floor
    SINGLE_SOURCE   one source has spoken and nothing contradicts it
    CONFLICT        two sources fall on opposite sides of the floor
    UNESTABLISHED   nobody has stated a size that can be read as one

`CONFLICT` resolves to no value at all, and `src/icpstructural.py` reads that
as UNKNOWN - "we could not establish it". That is the honest answer, and it is
the one that leaves the company eligible with uncertainty rather than
rejected on half the evidence or qualified on the other half.

## The floor comes from the client's config and is derived in one place

`icpstructural.settings` computes `effective_min_employees` from `min` and
`tolerance`, and this module asks it rather than deriving it again. The number
14 appears nowhere here: it is 20 x (1 - 0.30) for this client and something
else for the next one. A conflict is a fact about a client's criteria, not
about arithmetic.

## What a profile count is, and is not

`company_facts.headcount_signal` is how many profiles a provider actually
found at the domain. That is a FLOOR - a sixty-person company can easily show
two - so it can raise a lower bound and can never contradict anybody. It is
deliberately not an estimating witness here, and `icpstructural` goes on using
it exactly as it did.

## Revenue is not here

Revenue may TRIGGER a recheck and may never replace a headcount, so it stays
where it already is: `icpstructural._employees` reads it as a contradiction of
a small stored number and turns the criterion UNKNOWN, never PASS. A module
about how many people work somewhere has no business holding a turnover.
"""
from . import icpstructural, store

# What the estimating sources add up to.
AGREED = "agreed"
SINGLE_SOURCE = "single_source"
CONFLICT = "conflict"
UNESTABLISHED = "unestablished"
STATES = (AGREED, SINGLE_SOURCE, CONFLICT, UNESTABLISHED)

# How much the answer is worth. A different question from what the answer is.
HIGH = "high"
MEDIUM = "medium"
LOW = "low"

# Which side of the client's tolerated floor a statement puts the company.
ABOVE = "at_or_above"
BELOW = "below"

# The witness that is already on every record: what ContactOut's company
# lookup wrote into `company_facts` before anything went through `observe`. It
# is named so a conflict can say who disagreed instead of saying "the record".
STORED = "company_facts.employees"


def _int(value):
    return value if isinstance(value, int) and value > 0 else None


def _observation(source, value=None, band=None, at=None):
    """One source's statement. `at` stays None when it is genuinely unknown.

    `band` may be a provider's own spelling of it - Blitz answers `"1-10"` -
    or a (low, high) pair. Parsed through `icpstructural._band` either way, so
    a band is read in one place and not in each caller.
    """
    if isinstance(band, str):
        band = icpstructural._band(band)
    low, high = band if band else (None, None)
    return {
        "source": str(source),
        "value": _int(value),
        "range": [low, high] if (low is not None or high is not None) else None,
        "at": at,
    }


def block_of(rec):
    return ((rec or {}).get("company_facts") or {}).get("headcount") or {}


def witnesses(rec):
    """Every source that has stated a size for this company.

    The stored ContactOut fields count as a witness even though nothing wrote
    them through `observe`: they are a statement by a named provider, and a
    conflict cannot be seen without them. Its `at` is None because the record
    does not say when it was retrieved, and a timestamp nobody recorded is not
    one this module may invent.
    """
    facts = (rec or {}).get("company_facts") or {}
    found = []
    value = _int(facts.get("employees"))
    low, high = icpstructural._band(facts.get("employee_range"))
    if value is not None or low is not None:
        found.append(_observation(STORED, value,
                                  (low, high) if low is not None else None))
    for row in block_of(rec).get("observations") or ():
        if isinstance(row, dict) and row.get("source") != STORED:
            found.append(row)
    return found


def side(observation, floor):
    """Which side of the floor this statement puts the company, or None.

    A band that STRADDLES the floor has no side: which side it falls is
    exactly what is unestablished, so it can neither agree with anybody nor
    contradict them.
    """
    low, high = (observation.get("range") or [None, None])
    stated = [n for n in (low, observation.get("value")) if n is not None]
    lower = max(stated) if stated else None
    if lower is not None and lower >= floor:
        return ABOVE
    if high is not None and high >= floor:
        return None
    return BELOW if lower is not None else None


def _lower_of(observation):
    stated = [n for n in (observation.get("value"),
                          (observation.get("range") or [None])[0])
              if n is not None]
    return max(stated) if stated else None


def resolve(rec, config=None, rules=None):
    """This company's size, who said so, and whether the sources agree.

    The shape stored on the record. Spends nothing and writes nothing.
    """
    rules = rules if rules is not None else icpstructural.settings(config)
    floor = rules["effective_min_employees"]
    seen = witnesses(rec)
    sided = [(o, side(o, floor)) for o in seen]
    with_side = [o for o, s in sided if s is not None]
    sides = {s for _o, s in sided if s is not None}

    empty = {"value": None, "range": None, "source": None,
             "confidence": LOW, "retrieved_at": None, "contradictions": [],
             "observations": seen, "floor": floor}

    if not seen:
        return {**empty, "state": UNESTABLISHED}

    if len(sides) > 1:
        # Two sources, opposite sides of the floor. There is no value here -
        # picking one would be choosing which half of the evidence to believe.
        return {**empty, "state": CONFLICT, "contradictions": [
            {"source": o["source"], "value": o.get("value"),
             "range": o.get("range"), "side": s,
             "why": "%s puts this company %s the tolerated floor of %g"
                    % (o["source"], s.replace("_", " "), floor)}
            for o, s in sided if s is not None]}

    # They agree, or only one of them has a side. The lower bound is the
    # largest anybody states, which is the reading `icpstructural` has always
    # applied: a lower bound is a floor, and the best floor is the highest.
    best = max(seen, key=lambda o: _lower_of(o) or 0)
    return {
        "value": _lower_of(best),
        "range": list(best.get("range")) if best.get("range") else None,
        "source": best["source"],
        "confidence": (HIGH if len(with_side) > 1 else
                       MEDIUM if len(with_side) == 1 else LOW),
        "retrieved_at": best.get("at"),
        "contradictions": [],
        "observations": seen,
        "floor": floor,
        "state": AGREED if len(with_side) > 1 else SINGLE_SOURCE,
    }


def observe(rec, source, value=None, band=None, config=None, at=None,
            rules=None):
    """Record one source's statement about this company's size.

    Appends rather than overwrites: a second opinion that replaced the first
    would destroy the only evidence that a conflict exists. Returns the
    resolved block, which is what is stored.
    """
    facts = rec.setdefault("company_facts", {})
    kept = [row for row in (block_of(rec).get("observations") or ())
            if isinstance(row, dict)
            and row.get("source") not in (source, STORED)]
    kept.append(_observation(source, value, band, at or store.now()))
    facts["headcount"] = {"observations": kept}
    facts["headcount"] = resolve(rec, config, rules)
    return facts["headcount"]


def conflicted(rec, config=None, rules=None):
    """Do two sources disagree about which side of the floor this company is?"""
    return resolve(rec, config, rules)["state"] == CONFLICT
