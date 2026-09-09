#!/usr/bin/env python3
"""BlitzAPI, the second structured provider. Never first.

Base `https://api.blitz-api.ai`, every path under `/v2`, and the credential
travels as `x-api-key: <BLITZ_API_KEY>` - the raw key, not a Bearer token.

ContactOut is always first. This module exists for the two cases ContactOut
cannot answer: a confirmed ContactOut miss, and an operation ContactOut does
not have at all (the mail domain behind a company, which `contactout.py`
records as absent from every response under any spelling). The policy lives in
`src/waterfall.py` as `requires_reason`, not here: nothing in this module
decides that it may run.

Four properties of this API decide the shape of everything below.

**A miss is HTTP 200 with `found: false`.** Every single-subject enrichment
answers 200 and states, at the top level, whether it found the subject. That
boolean is the only confirmed miss there is. A 200 whose body does not carry
it is confusion, and confusion is raised rather than read as absence -
"missing evidence is never positive evidence" (CLAUDE.md).

**404 means the API key does not exist.** It is an authentication failure and
never a data miss. Read as a miss, a dead key would look like a universe in
which no subject is ever found: the waterfall would fan its paid fallbacks out
across every record while the spend audit reported a clean run. `_refuse`
raises on it, loudly, naming what it is.

**`fair_usage.records_used` is the real cost of the call**, in Blitz's own
records, and it is the only number that may reach `waterfall.entry`'s
`actual_cost`. When the block is absent the cost is *unknown*, which is `None`
here and stays `None` in the ledger. It is never zero: a ledger that reports a
metered call as free is worse than one that reports nothing.
`fair_usage.request_id` is generated per *response*, so it identifies an answer
and cannot deduplicate a request.

**There is no idempotency of any kind, so nothing here retries.** A read
timeout is not a failed call; it is a call whose answer was lost, and the
server may already have billed it. `providers.request` raises `ProviderError`
on a timeout and this module lets it out untouched. A caller that wraps these
functions in a retry loop is buying the record twice.

Rate limit: 10 requests per second per endpoint by default, and
`key_info()["max_requests_per_seconds"]` is the authority for this key.
Nothing here throttles - there is no concurrent caller in this build - and a
429 is raised, classified, and not slept through.

  python -m src.providers.blitz --check      free: key-info, 0 records
  python -m src.providers.blitz --costs
"""
import argparse

from . import (COST, ProviderError, failed, first, key, mapping, ok, query,
               request, result)

BASE = "https://api.blitz-api.ai"

# The documented per-endpoint ceiling. key-info is the authority for a given
# key; this is what to assume before it has been read, and a *missing*
# `max_requests_per_seconds` means unknown rather than this number.
DEFAULT_RATE_LIMIT = 10

# The REST routes. Operation names are ours; this table is the only place they
# become URLs, and the method is part of the route rather than a caller's
# choice - the same discipline as `contactout.ROUTES`, which exists because an
# earlier build used MCP tool names as paths and 404ed on every call.
#
# LIVE CONTRACT VALIDATION REQUIRED (methods): the paths below are the ones
# named in the capability matrix and verified against both OpenAPI specs. The
# verbs are the specs' - GET for the free account read, POST with a JSON body
# for everything that takes a subject. No live call has been made from this
# repository, so a verb that is wrong is wrong in exactly one place.
ROUTES = {
    "key-info": ("GET", "/v2/account/key-info"),
    # Domain -> the company's LinkedIn URL. The keystone: every Blitz *search*
    # is addressed by company LinkedIn URL, not by domain, so nothing else
    # here can run for a company until this has answered once.
    "domain-to-linkedin": ("POST", "/v2/enrichment/domain-to-linkedin"),
    # Company LinkedIn URL -> the EMAIL domain, which is not always the
    # website domain (BUILD-SPEC section 9, trap 3) and which ContactOut does
    # not return at all.
    "linkedin-to-domain": ("POST", "/v2/enrichment/linkedin-to-domain"),
    "company": ("POST", "/v2/enrichment/company"),
    "waterfall-icp-keyword": ("POST", "/v2/search/waterfall-icp-keyword"),
    "employee-finder": ("POST", "/v2/search/employee-finder"),
    "email": ("POST", "/v2/enrichment/email"),
    "phone": ("POST", "/v2/enrichment/phone"),
}

# What each operation is called in `enrich.COSTS`, `enrich.CALL_STAGE` and the
# waterfall ledger. Derived rather than typed twice: a route with no cost entry
# is a call the cap cannot see, and the test asserts the two sets line up.
CALLS = {op: f"blitz-{op}" for op in ROUTES}

# Free: 0 records, and the only call that may be made to prove the key works.
FREE = frozenset({"key-info"})

# Operations that return a person, or a person's contact details. Every one of
# these must appear in `enrich.PERSON_LEVEL` or the ICP spend gate - "no paid
# person-level call before a company reaches an explicit ICP verdict" - is
# bypassed by whichever call was forgotten. Named here so the gate can be
# asserted mechanically instead of remembered.
PERSON_LEVEL_OPS = ("employee-finder", "email", "phone")

# US numbers only, and only on the top plan. `key_info()["allowed_apis"]` is
# what actually says whether this key may call it.
US_ONLY_OPS = ("phone",)


def headers():
    """The raw key under `x-api-key`. Read at call time, never at import."""
    return {"x-api-key": key("BLITZ_API_KEY")}


# ------------------------------------------------------------------- the wire

def _refuse(status, op):
    """Classify every non-2xx explicitly. Nothing here returns quietly.

    The 404 branch is the reason this function exists rather than a bare
    `if not ok(status)`.
    """
    if ok(status):
        return
    if status == 404:
        raise ProviderError(
            f"blitz {op}: 404 means this API key does not exist. That is an "
            "authentication error, not a data miss - a miss is HTTP 200 with "
            "found=false. Read as a miss it would send a paid fallback after "
            "every record while the spend audit reported a clean run.")
    if status in (401, 403):
        raise ProviderError(
            f"blitz {op}: {status}, the key was refused for this endpoint. "
            "allowed_apis in key-info is what says whether it may call it.")
    if status == 429:
        raise ProviderError(
            f"blitz {op}: 429, rate limited. The ceiling is per endpoint "
            f"(max_requests_per_seconds, {DEFAULT_RATE_LIMIT}/s by default). "
            "Not retried here: Blitz supports no idempotency, so a retry is a "
            "second billable call.")
    raise ProviderError(f"blitz {op}: {status}")


def call(name, params=None):
    """One Blitz operation, as (status, body). The route decides the verb.

    No retry, no backoff, no second attempt of any kind. See the module
    docstring: a lost answer is not an unbilled call.
    """
    if name not in ROUTES:
        raise ProviderError(f"blitz: no route for {name}")
    method, path = ROUTES[name]
    params = {k: v for k, v in (params or {}).items()
              if v not in (None, "", [], {})}
    if method == "POST":
        return request("POST", f"{BASE}{path}", headers(), params)
    return request("GET", query(f"{BASE}{path}", params), headers())


# --------------------------------------------------------------- the outcome

def _count(value):
    """A record count, or None for "the provider did not say".

    `bool` is rejected before `int` because `True` is an `int` in Python and a
    boolean billed as one record is a number nobody typed.
    """
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    text = str(value).strip()
    if text.lstrip("-").isdigit():
        return int(text)
    return None                      # unreadable is unknown, never zero


def _text(value):
    """A scalar, or None. Never the string form of a container.

    `hq` on a live `enrichment/company` response is an object, and the first
    version of this returned `"{'city': None, 'country_name': None, ...}"` for
    any field spelled the same way. A stringified dict in a trimmed field is a
    raw payload escaping under a different shape, which is the one thing the
    trim exists to prevent.
    """
    if isinstance(value, (dict, list, tuple, set)):
        return None
    return str(value) if value not in (None, "") else None


def _place(value):
    """A human-readable location out of Blitz's nested `hq` object.

    Confirmed live 2026-09-09: `hq` carries city, region, state, country_name,
    country_code and continent, every one of them null for our own company. So
    the join can legitimately produce nothing, and nothing is None rather than
    an empty string - a location we do not have must not read as one we do.
    """
    if not isinstance(value, dict):
        return _text(value)
    parts = [_text(value.get(k)) for k in
             ("city", "state", "region", "country_name")]
    kept, seen = [], set()
    for part in parts:
        if part and part not in seen:
            seen.add(part)
            kept.append(part)
    return ", ".join(kept) or None


def _fair_usage(data):
    """The three fields that matter, trimmed off any metered response.

    `records_used` is the real per-call cost and the only value that may be
    reported as `actual_cost`. Absent means unknown - `waterfall.entry`
    already reads `None` as "the provider did not tell us" - and never zero.

    `request_id` is server-generated per response. It is a support reference
    and it cannot deduplicate a retry, which is why nothing here retries.
    """
    block = data.get("fair_usage") if isinstance(data, dict) else None
    block = block if isinstance(block, dict) else {}
    return {"records_used": _count(block.get("records_used")),
            "records_remaining": _count(block.get("records_remaining")),
            "request_id": _text(block.get("request_id"))}


def _outcome(status, data, op="blitz"):
    """Found, a confirmed miss, or a raise. There is no fourth answer.

    Single-subject enrichment only: every one of those endpoints answers 200
    with a top-level `found` boolean. Search has no `found` and goes through
    `_search` instead.

    Returns an internal envelope - `{"found", "body", "fair_usage"}` - which
    never leaves the module. The accessors trim `body` and return that.
    """
    _refuse(status, op)
    body = mapping(data, f"blitz {op}")
    if "found" not in body:
        raise ProviderError(
            f"blitz {op}: HTTP 200 with no `found` in the body. Every "
            "single-subject enrichment states whether it found the subject; a "
            "body without it is confusion, and confusion is not a miss.")
    found = body["found"]
    if not isinstance(found, bool):
        raise ProviderError(
            f"blitz {op}: `found` is {type(found).__name__}, not a boolean. "
            "A miss has to be stated, not inferred from a truthy value.")
    return {"found": found, "body": body, "fair_usage": _fair_usage(body)}


def _search(status, data, op):
    """A search result set. No `found` here: a miss is a length of zero."""
    _refuse(status, op)
    body = mapping(data, f"blitz {op}")
    rows = body.get("results")
    if rows is None:
        rows = body.get("data")
    if not isinstance(rows, list):
        raise ProviderError(
            f"blitz {op}: no `results` list in the body. A search miss is "
            "results_length 0 with a list present; a body with no list at all "
            "is a contract failure, not an empty result set.")
    declared = first(body, "results_length", "total_results")
    return {"results": rows,
            "count": declared if declared is not None else len(rows),
            "fair_usage": _fair_usage(body)}


def _payload(body, *containers):
    """The subject out of whatever envelope it arrived in.

    `found` is top-level; the record itself may be beside it or nested. Both
    are read, and nothing is invented: an envelope that is neither returns the
    body, and a field that is not there trims to None.
    """
    for name in containers + ("data", "result"):
        nested = body.get(name)
        if isinstance(nested, dict):
            return nested
        if isinstance(nested, list) and nested and isinstance(nested[0], dict):
            return nested[0]
    return body


# --------------------------------------------------------------- accessors
#
# Every one returns a trimmed dict. Raw payloads never leave this module
# (BUILD-SPEC section 9, trap 8), and every metered answer carries its own
# `fair_usage` so the caller can write a true `actual_cost` into the ledger.
#
# LIVE CONTRACT VALIDATION REQUIRED (field spellings): the key names read
# below come from the OpenAPI specs by way of the capability matrix. No
# response has been observed from this repository. `first()` reads the
# documented spelling and the obvious alternates, and anything absent trims to
# None rather than to a guess.


def _key_info():
    """(status, trimmed). `check()` needs the status; nothing else does."""
    status, data = call("key-info")
    _refuse(status, "key-info")
    body = mapping(data, "blitz key-info")
    apis = body.get("allowed_apis")
    if not isinstance(apis, list):
        raise ProviderError(
            "blitz key-info: no allowed_apis list in the body. That list is "
            "the only authority on what this key may call; without it, "
            "capability is unknown rather than unlimited.")
    return status, {
        "allowed_apis": [str(a) for a in apis],
        # None means the response did not say. Assuming DEFAULT_RATE_LIMIT
        # here would invent a ceiling for a key that may have a lower one.
        "max_requests_per_seconds": _count(
            first(body, "max_requests_per_seconds", "max_requests_per_second")),
        "plan": _text(first(body, "plan", "plan_name", "tier")),
        "records_remaining": _count(
            first(body, "records_remaining", "credits_remaining")),
    }


def key_info():
    """Free. 0 records. What this key is actually allowed to do.

    `allowed_apis` is the authoritative per-key capability list and is the
    only thing that says whether an endpoint is callable - a plan assumption
    is not evidence. A body without it raises: a key whose capabilities are
    unknown must not read as a key that may do everything.
    """
    return _key_info()[1]


def domain_to_linkedin(domain):
    """Domain -> the company's LinkedIn URL. Metered.

    The keystone call: Blitz addresses companies by LinkedIn URL, so nothing
    else here can run for a company until this has answered.

    ContactOut answers this question too - `li_vanity` is on its
    `/domain/enrich` response - so this is a fallback, and the waterfall
    demands a reason for it. See INTEGRATION.md.
    """
    got = _outcome(*call("domain-to-linkedin", {"domain": domain}),
                   op="domain-to-linkedin")
    raw = _payload(got["body"], "company") if got["found"] else {}
    return {
        "found": got["found"],
        "domain": domain,
        "company_linkedin": _text(first(raw, "linkedin_url", "linkedin",
                                        "company_linkedin_url", "url")),
        "fair_usage": got["fair_usage"],
    }


def linkedin_to_domain(company_linkedin):
    """Company LinkedIn URL -> the EMAIL domain. Metered.

    The gap ContactOut cannot fill: `contactout.company_info` carries an
    `email_domain` field that is never populated, because no ContactOut
    response contains one under any spelling. The mail domain is not always
    the website domain (section 9, trap 3), and this is where it comes from.
    """
    got = _outcome(*call("linkedin-to-domain", {"linkedin_url": company_linkedin}),
                   op="linkedin-to-domain")
    raw = _payload(got["body"], "company") if got["found"] else {}
    return {
        "found": got["found"],
        "company_linkedin": company_linkedin,
        "email_domain": _text(first(raw, "email_domain", "mail_domain",
                                    "domain")),
        "website": _text(first(raw, "website", "website_domain")),
        "fair_usage": got["fair_usage"],
    }


def company(company_linkedin):
    """Firmographics for one company. Metered.

    LIVE-CONFIRMED 2026-09-09, at a cost of one record, against
    `https://www.linkedin.com/company/resonategroup`. The raw exchange is in
    `work/validation/blitz-company.json`. Three things the spec reading got
    wrong, all of them silent:

      - the request field is `company_linkedin_url`. Sending `linkedin_url`
        returns 422 and no record is billed, so every call would have failed
        and the ledger would have shown nothing.
      - the headcount is `employees_on_linkedin`. None of `employees`,
        `employee_count` or `headcount` is present, so the trim read None for
        every company - a missing value where the wire had 19.
      - the location is a nested `hq` object, not a `location` /
        `headquarter` / `country` scalar.

    `size` is also on the wire as a band (`"1-10"`), and is deliberately not
    read into `employees`: a band is not a count, and
    `employees_on_linkedin` is the measured number.
    """
    got = _outcome(*call("company", {"company_linkedin_url": company_linkedin}),
                   op="company")
    raw = _payload(got["body"], "company") if got["found"] else {}
    return {
        "found": got["found"],
        "company_linkedin": company_linkedin,
        "name": _text(first(raw, "name", "company_name")),
        "domain": _text(first(raw, "domain", "website")),
        "employees": _count(first(raw, "employees_on_linkedin", "employees",
                                  "employee_count", "headcount")),
        "employee_range": _text(first(raw, "size", "employee_range")),
        "industry": _text(raw.get("industry")),
        "location": _place(first(raw, "hq", "location", "headquarter",
                                 "country")),
        "founded": _count(first(raw, "founded_year", "founded")),
        "fair_usage": got["fair_usage"],
    }


def _person(raw):
    """One person, five fields.

    No address and no phone number: those are separate metered calls, and a
    search result that appeared to carry one would let a person-level credit
    look free.
    """
    raw = raw if isinstance(raw, dict) else {}
    return {
        "name": _text(first(raw, "full_name", "name")),
        "title": _text(first(raw, "title", "job_title", "headline")),
        "company": _text(first(raw, "company_name", "company")),
        "linkedin": _text(first(raw, "linkedin_url", "linkedin",
                                "profile_url")),
        "location": _text(first(raw, "location", "country")),
    }


def _company_row(raw):
    raw = raw if isinstance(raw, dict) else {}
    return {
        "name": _text(first(raw, "name", "company_name")),
        "domain": _text(first(raw, "domain", "website")),
        "linkedin": _text(first(raw, "linkedin_url", "linkedin",
                                "company_linkedin_url")),
        "employees": _count(first(raw, "employees", "employee_count")),
        "industry": _text(raw.get("industry")),
    }


def employee_finder(company_linkedin, job_title=None, page=None):
    """People at one company, addressed by its LinkedIn URL. Metered.

    Person-level: `blitz-employee-finder` must be in `enrich.PERSON_LEVEL`.
    A zero-length result set is a miss, not a failure.
    """
    got = _search(*call("employee-finder",
                        {"linkedin_url": company_linkedin,
                         "job_title": job_title, "page": page}),
                  op="employee-finder")
    return {"people": [_person(r) for r in got["results"]],
            "count": got["count"],
            "fair_usage": got["fair_usage"]}


def icp_keyword_search(keyword=None, page=None, **filters):
    """Companies matching an ICP keyword. Metered. Company-level.

    NOT WIRED INTO THE WATERFALL. It answers "which companies exist", which is
    not a question any stage in `src/waterfall.py` asks, and there is no
    ContactOut step to put in front of it. Until a stage exists it must not be
    reached from `src/enrich.py`: a call with no stage cannot be justified,
    and `waterfall.record_step` will refuse it rather than pay for it.
    `src/discovery.py` is the module that would own it. See INTEGRATION.md.
    """
    params = {"keyword": keyword, "page": page}
    params.update(filters)
    got = _search(*call("waterfall-icp-keyword", params),
                  op="waterfall-icp-keyword")
    return {"companies": [_company_row(r) for r in got["results"]],
            "count": got["count"],
            "fair_usage": got["fair_usage"]}


def email(person_linkedin):
    """LinkedIn profile -> work email. Metered, person-level.

    Returns the address and nothing about whether it may be written to: an
    address from here is unverified, and BUILD-SPEC section 6.1 decides
    `sendable`, not this module.
    """
    got = _outcome(*call("email", {"linkedin_url": person_linkedin}),
                   op="email")
    raw = _payload(got["body"], "person", "profile") if got["found"] else {}
    return {
        "found": got["found"],
        "linkedin": person_linkedin,
        "email": _text(first(raw, "email", "work_email")),
        "fair_usage": got["fair_usage"],
    }


def phone(person_linkedin):
    """LinkedIn profile -> phone. US numbers only, top plan only. Metered.

    NOT WIRED INTO THE WATERFALL, and nothing in this build consumes a phone
    number: no stage asks for one, no channel dials one. It is here because
    the capability exists and because leaving it out would hide it; calling it
    from `src/enrich.py` before something reads the answer would be spending
    on a field nobody looks at. Person-level whenever it is wired.
    """
    got = _outcome(*call("phone", {"linkedin_url": person_linkedin}),
                   op="phone")
    raw = _payload(got["body"], "person", "profile") if got["found"] else {}
    return {
        "found": got["found"],
        "linkedin": person_linkedin,
        "phone": _text(first(raw, "phone", "phone_number", "mobile")),
        "fair_usage": got["fair_usage"],
    }


# ------------------------------------------------------------------- health

def check():
    """Free: key-info costs 0 records and reports what the key may call.

    The note carries `allowed_apis` because that list is the answer an
    operator needs before planning a run - a green tick that does not say
    which endpoints are permitted is a tick for a key that may refuse the
    only call the batch needs.
    """
    try:
        status, info = _key_info()
        allowed = ", ".join(info["allowed_apis"]) or "none"
        rate = info["max_requests_per_seconds"]
        return result("Blitz", status,
                      f"allowed_apis: {allowed}; "
                      f"{rate if rate is not None else 'unstated'} rps")
    except ProviderError as e:
        return failed("Blitz", e)


def main(argv=None):
    p = argparse.ArgumentParser(prog="python -m src.providers.blitz")
    p.add_argument("--check", action="store_true")
    p.add_argument("--costs", action="store_true")
    a = p.parse_args(argv)
    if a.costs:
        for op, name in CALLS.items():
            print(f"{name:<34} "
                  f"{COST.get(name, 'NOT IN providers.COST - add it')}")
        return 0
    r = check()
    print(f"{'ok  ' if r['ok'] else 'FAIL'} {r['provider']:<12} "
          f"{r['status'] if r['status'] is not None else '-'}  {r['note']}")
    return 0 if r["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
