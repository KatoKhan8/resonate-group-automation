#!/usr/bin/env python3
"""ContactOut, the primary provider. BUILD-SPEC section 5.1.

Base https://api.contactout.com/v1, headers `authorization: basic` and
`token: <CONTACTOUT_TOKEN>`.

Every function returns a trimmed dict or a list of them. Raw payloads never
leave this module: a single decision-makers call on an eight person company
returns enough JSON to dominate an LLM context (section 9, trap 8).

Costs, from section 5.1:
  people-count                     free
  people-search                    1 search credit per profile returned
  decision-makers                  1 search credit per profile, 1 email credit
                                   per profile with contact info when reveal_info
  email-verifier                   1 verifier credit on a definitive result
  company-information-from-domain  1 search credit

  python -m src.providers.contactout --check
"""
import argparse
import time

from . import (COST, MissingKey, ProviderError, failed, first, key, mapping,
               ok, query, request, result)

BASE = "https://api.contactout.com/v1"

# Bounded retry: 3 attempts total (original + 2 retries). ContactOut's rate
# limit window is per-minute and 5xx errors are typically transient. The
# backoff is 0.5s, 1.0s - enough for the provider to recover without blocking
# the batch. A 401 (bad key) is never retried: a credential that is absent
# will not materialise on the second attempt.
MAX_RETRIES = 2
_RETRY_BACKOFF = (0.5, 1.0)

# Always sent on people-search so the response comes back trimmed at the source.
# Only values ContactOut actually accepts: li_vanity, full_name, title, headline,
# company, company.name, company.website, company.headquarter, company.domain,
# company.size, location, industry, experience, education, skills,
# profile_picture_url. Verified against the live tool schema, 2026-08-25.
OUTPUT_FIELDS = ["full_name", "title", "headline", "company.name", "company.domain",
                 "location", "industry", "li_vanity"]

VERDICTS = ("valid", "invalid", "accept_all", "disposable", "unknown")

# The values ContactOut accepts, not free text.
SENIORITY = ("owner / founder", "cxo", "partner", "vp", "head", "director",
             "manager", "senior", "entry", "intern")


def headers():
    return {"authorization": "basic", "token": key("CONTACTOUT_TOKEN")}


def unwrap(payload):
    """ContactOut wraps its answer in {"status": 200, "data": {...}}."""
    if isinstance(payload, dict) and isinstance(payload.get("data"), dict):
        return payload["data"]
    return payload or {}


# The REST routes, confirmed against ContactOut's own API reference on
# 2026-08-26 after every call 404ed. An earlier build used the MCP *tool* name
# as the path ("/v1/people-count"), which is not a REST route: the operation
# names below are ours, and this table is the only place they become URLs.
# Where the parameters travel is part of the route, not a caller's choice.
ROUTES = {
    "people-count": ("POST", "/people/count"),
    "people-search": ("POST", "/people/search"),
    "decision-makers": ("GET", "/people/decision-makers"),
    # Confirmed live 2026-09-07: `GET /v1/email/verify?email=` answers 200
    # {"status_code", "data": {"status"}}. "/email-verifier/verify" was the MCP
    # tool name with a verb bolted on and 404s the same way the bare tool names
    # did - "The route v1/email-verifier/verify could not be found".
    "email-verifier": ("GET", "/email/verify"),
    "company-information-from-domain": ("POST", "/domain/enrich"),
    # Added 2026-09-22 for agency sourcing. BILLED: one search credit per
    # COMPANY RETURNED, so a page of 25 costs 25. Every caller counts first
    # with the free `people-count` and only then decides to buy a page.
    "company-search": ("POST", "/company/search"),
}


def classify_failure(status, error_text=""):
    """Map a ContactOut failure to one of the five outcome classes.

    The classification decides whether a fallback is licensed. An error, a
    timeout and a rate limit are transient - they must NOT license paying a
    second provider for data ContactOut has and was simply not asked properly.
    """
    text = str(error_text).lower()
    if status == 429 or "rate" in text and "limit" in text:
        return "contactout_rate_limited"
    if status is None and ("timeout" in text or "timed out" in text):
        return "contactout_timeout"
    if status is None and ("timeout" not in text):
        return "contactout_error"
    if status is not None and 500 <= status < 600:
        return "contactout_error"
    return "contactout_error"


def _do_request(method, url, hdrs, params):
    """One HTTP attempt. Returns (status, data)."""
    if method == "POST":
        return request("POST", url, hdrs, params)
    return request("GET", query(url, params), hdrs)


def call(name, params=None, _sleep=time.sleep):
    """One ContactOut operation with bounded retry on transient failures.

    The route decides where the parameters go. 429, 5xx and network errors
    are retried up to MAX_RETRIES times with exponential backoff. 4xx client
    errors and MissingKey are never retried.

    A retry is invisible to the spend audit: ContactOut bills only successful
    calls, so a retry that fails costs nothing, and a retry that succeeds
    costs the same as a first attempt that succeeds.
    """
    if name not in ROUTES:
        raise ProviderError(f"contactout: no route for {name}")
    method, path = ROUTES[name]
    params = {k: v for k, v in (params or {}).items()
              if v not in (None, "", [], {})}
    url = f"{BASE}{path}"

    hdrs = headers()
    max_attempts = MAX_RETRIES + 1
    last_status, last_error = None, None

    for attempt in range(max_attempts):
        try:
            last_status, data = _do_request(method, url, hdrs, params)
            if ok(last_status):
                return unwrap(data)
            # 4xx (except 429) is a client error; retrying won't help.
            if 400 <= last_status < 500 and last_status != 429:
                raise ProviderError(f"contactout {name}: {last_status}")
            # 429 and 5xx are transient; fall through to retry.
            last_error = f"contactout {name}: {last_status}"
        except MissingKey:
            raise
        except ProviderError:
            # A 4xx ProviderError must not be retried - re-raise immediately.
            if last_status is not None and 400 <= last_status < 500:
                raise
            if attempt >= max_attempts - 1:
                raise
            last_error = f"contactout {name}: transient failure"
        if attempt < max_attempts - 1:
            _sleep(_RETRY_BACKOFF[attempt])

    raise ProviderError(last_error or f"contactout {name}: exhausted retries")


def listed(value):
    """ContactOut takes arrays for its filters, not scalars."""
    if value in (None, "", [], {}):
        return None
    return list(value) if isinstance(value, (list, tuple)) else [value]


def _company_name(raw):
    company = raw.get("company") if isinstance(raw, dict) else None
    if isinstance(company, dict):
        return company.get("name")
    return company or (raw.get("company_name") if isinstance(raw, dict) else None)


def _email(raw):
    """With reveal_info, addresses arrive under contact_info, not at the top."""
    info = raw.get("contact_info") if isinstance(raw, dict) else None
    if isinstance(info, dict):
        work = info.get("work_email") or info.get("work_emails")
        personal = info.get("email") or info.get("emails")
        for candidate in (work, personal):
            if isinstance(candidate, list) and candidate:
                return candidate[0]
            if isinstance(candidate, str) and candidate:
                return candidate
    return first(raw, "work_email", "email")


def _person(raw):
    """One person, eight fields, nothing else."""
    raw = raw if isinstance(raw, dict) else {}
    return {
        "name": first(raw, "full_name", "name"),
        "title": first(raw, "title", "job_title", "headline"),
        "company": _company_name(raw),
        "linkedin": first(raw, "linkedin_url", "linkedin", "profile_url", "li_vanity"),
        "email": _email(raw),
        "location": first(raw, "location", "country"),
        "seniority": raw.get("seniority"),
        "current": raw.get("current") if raw.get("current") is not None
                   else raw.get("is_current"),
    }


def _people(data, containers=("profiles", "people", "decision_makers", "data")):
    for name in containers:
        rows = mapping(data, "contactout people").get(name)
        if isinstance(rows, list):
            return [_person(r) for r in rows]
        if isinstance(rows, dict):
            return [_person(r) for r in rows.values()]
    return []


def decision_makers(domain, reveal_info=False):
    """Roles held today plus work history. Costs credits per profile returned.

    reveal_info defaults to False: an address costs an email credit, so the
    caller has to ask for it deliberately.
    """
    return _people(call("decision-makers",
                        {"domain": domain, "reveal_info": str(bool(reveal_info)).lower()}))


def people_search(domain=None, job_title=None, seniority=None, location=None,
                  current_company_only=True, page=None, **extra):
    """The domains lane workhorse. output_fields is always sent (trap 8)."""
    _reject_work_location(extra)
    params = {"domain": listed(domain), "job_title": listed(job_title),
              "seniority": listed(seniority), "location": listed(location),
              "current_company_only": str(bool(current_company_only)).lower(),
              "output_fields": OUTPUT_FIELDS, "page": page}
    params.update(extra)
    return _people(call("people-search", params))


def people_count(job_title=None, location=None, domain=None, **extra):
    """Free: ContactOut does not consume credits for a count.

    Confirms a company is real and staffed before a credit is spent, and sizes
    a prospect's own market for the email.

    Section 9, trap 7: `location`, never `current_work_location`. The latter
    returned 86 where location returned 230,222 for the same query.
    """
    _reject_work_location(extra)
    params = {"job_title": listed(job_title), "location": listed(location),
              "domain": listed(domain)}
    params.update(extra)
    data = call("people-count", params)
    # Live field names, confirmed against the API on 2026-08-25: total_results
    # and estimated_phones. The record schema calls them profiles and mobiles.
    return {
        "query": ", ".join(listed(job_title) or listed(domain) or []) or None,
        "profiles": first(data, "total_results", "profiles", "total", "count"),
        "mobiles": first(data, "estimated_phones", "mobiles", "mobile_phones"),
    }


#: Fields kept off a sourced company row. The rest is noise for the ICP
#: verdict and would bloat `work/` by an order of magnitude.
COMPANY_FIELDS = ("domain", "name", "employees", "size", "industry",
                  "country", "headquarter", "revenue", "specialties",
                  "overview", "url", "founded_at", "type")


def company_search(industry=None, size=None, location=None, page=1,
                   hq_only=True):
    """Companies matching the filters. **BILLED PER COMPANY RETURNED.**

    Measured 2026-09-22 and this is why the sourcing route is ContactOut
    rather than AI Ark: industry, size and location are all HONOURED here.
    Varying one at a time moved the count every time, and a page asked for
    UK / Advertising Services / 51-200 came back with all twenty-five rows on
    that industry, that bucket and a GB headquarters. AI Ark's company
    filters are accepted and INERT - identical `totalElements` and
    byte-identical row hashes across every filter combination.

    **`size` IS A SELF-REPORTED BAND AND `employees` IS A DIFFERENT NUMBER.**
    A row in the `51_200` bucket came back reading `employees: 392`. The
    bucket narrows the page; it does not establish headcount. Any floor or
    ceiling has to be applied to `employees`, which is what the caller does.

    Returns `{"companies": [...], "total": n, "page": p, "page_size": k}` so a
    caller can walk to exhaustion without guessing when it has finished.
    """
    params = {"industry": listed(industry), "size": listed(size),
              "location": listed(location), "page": int(page)}
    if hq_only:
        params["hq_only"] = True
    data = call("company-search", params)
    meta = data.get("metadata") if isinstance(data, dict) else None
    meta = meta if isinstance(meta, dict) else {}
    rows = []
    for raw in (data.get("companies") or []):
        if not isinstance(raw, dict):
            continue
        row = {k: raw.get(k) for k in COMPANY_FIELDS}
        if row.get("domain"):
            row["domain"] = str(row["domain"]).strip().lower()
            rows.append(row)
    return {"companies": rows,
            "total": first(meta, "total_results", "total") or 0,
            "page": meta.get("page") or int(page),
            "page_size": meta.get("page_size") or len(rows)}


def _reject_work_location(params):
    if "current_work_location" in params:
        raise ValueError(
            "use location, not current_work_location: it returned 86 where "
            "location returned 230,222 for the same query (BUILD-SPEC section 9, trap 7)")


def email_verifier(email):
    """valid | invalid | accept_all | disposable | unknown.

    Confirmed live 2026-09-07 on two real addresses: `accept_all` on a
    catch-all domain and `invalid` on a dead mailbox. The verdict arrives as
    `data.status`, which is why `unwrap` runs before `first`; anything outside
    VERDICTS becomes `unknown` rather than travelling on as free text.
    """
    data = call("email-verifier", {"email": email})
    verdict = first(data, "status", "verdict", "result", default="unknown")
    verdict = str(verdict).lower()
    return {"email": email, "verdict": verdict if verdict in VERDICTS else "unknown"}


# What ContactOut sends when it has nothing: an empty string, a literal "N/A",
# or a zero year. Left alone, each is truthy or numeric downstream and reads as
# an answer. All three mean absent.
ABSENT = ("", "n/a", "none", "null", "-", "unknown")


def _present(value):
    if isinstance(value, str):
        return None if value.strip().lower() in ABSENT else value.strip()
    if value == 0:                     # a zero head count or founding year
        return None
    return value


def _company_of(data, domain):
    """The one company out of whatever envelope it arrived in.

    Confirmed live on 2026-08-26: `POST /v1/domain/enrich` answers
    {"status_code", "companies"} with companies keyed by the domain asked for. The older spellings
    are kept because they cost nothing and a single-company response under
    `company` is what the documentation's example shows.
    """
    if not isinstance(data, dict):
        return {}
    for name in ("companies", "company"):
        found = data.get(name)
        if isinstance(found, dict):
            keyed = found.get(domain)
            if isinstance(keyed, dict):
                return keyed          # keyed by the domain that was requested
            values = [v for v in found.values() if isinstance(v, dict)]
            return values[0] if values else found
        if isinstance(found, list):
            return found[0] if found and isinstance(found[0], dict) else {}
    if isinstance(data.get(domain), dict):
        return data[domain]
    return data


def company_info(domain):
    """Firmographics, offices, tech stack. Catches rebrands (trap 4) and the
    real mail domain, which is not always the website domain (trap 3).

    Costs 1 search credit per company found. The parameter is `domains`, an
    array of up to 30, per the live schema.
    """
    data = call("company-information-from-domain", {"domains": listed(domain)})
    raw = _company_of(data, domain)
    return {
        "name": _present(first(raw, "name", "company_name")),
        "domain": _present(first(raw, "domain", "website")),
        # ContactOut does not return a mail domain. Confirmed against a real
        # response on 2026-08-26: the key simply is not there, under any
        # spelling. Section 9 trap 3 still stands, so this stays in the model
        # and has to be filled from elsewhere; it is never ContactOut's answer.
        "email_domain": _present(first(raw, "email_domain", "mail_domain")),
        # The company's own LinkedIn URL. Live key is li_vanity, confirmed on
        # the 2026-08-26 response. Kept because it is the address every Blitz
        # search is keyed by, and dropping it here is what made Blitz's
        # domain-to-linkedin look unavoidable - the miss could not even be
        # stated, so the fallback could never be justified.
        "linkedin": _present(first(raw, "li_vanity", "linkedin_url")),
        # `employees` is the head count. `size` is a bucket code and read 2
        # against employees 17, so it is not a fallback for it.
        "employees": _present(first(raw, "employees", "employee_count")),
        "revenue": _present(raw.get("revenue")),
        # Live key is founded_at, and it reads 0 when unknown.
        "founded": _present(first(raw, "founded", "founded_year", "founded_at")),
        "industry": _present(raw.get("industry")),
        # Live key is locations. headquarter and country exist as separate
        # strings and were both empty, so neither is folded in here on a guess.
        "offices": raw.get("locations") or raw.get("offices") or [],
        "specialties": raw.get("specialties") or [],
        "stack": first(raw, "technologies", "tech_stack", default=[]),
    }


def check():
    """Free: usage stats, no search and no credit.

    `period` is a YYYY-MM month, not the word "month"; sending the word earns
    "Invalid date format". Omitted here on purpose, so the account's own idea of
    the current month is used rather than this machine's clock.
    """
    try:
        status, data = request("GET", f"{BASE}/stats", headers())
        return result("ContactOut", status, str(data))
    except ProviderError as e:
        return failed("ContactOut", e)


def main(argv=None):
    p = argparse.ArgumentParser(prog="python -m src.providers.contactout")
    p.add_argument("--check", action="store_true")
    p.add_argument("--costs", action="store_true")
    a = p.parse_args(argv)
    if a.costs:
        for name in ("people-count", "people-search", "decision-makers",
                     "email-verifier", "company-information-from-domain"):
            print(f"{name:<34} {COST[name]}")
        return 0
    r = check()
    print(f"{'ok  ' if r['ok'] else 'FAIL'} {r['provider']:<12} {r['status']}  {r['note']}")
    return 0 if r["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
