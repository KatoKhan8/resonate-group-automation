#!/usr/bin/env python3
"""AI Ark, the fallback. BUILD-SPEC section 5.2.

Remote MCP at https://api.ai-ark.com/v1/mcp?token=<AIARK_KEY>, spoken as
JSON-RPC over HTTP so the engine works in cron or n8n with no MCP session.
Run only on ContactOut misses: a different index, and different credits.

Two quirks from section 5.2, both guarded here:

  1. `industry`, `location` and `technology` are strict enums. A search that
     names one without it coming from the matching lookup is refused before it
     is sent, rather than failing at the API.
  2. a `keyword` search needs `keywordSources` or it returns
     "400 sources is required". It is defaulted here.

`email_finder` is async: it returns a trackId, then `email_finder_results` is
polled, bounded, never indefinitely.

  python -m src.providers.aiark --check
"""
import argparse
import json
import time

from . import ProviderError, failed, key, mapping, ok, request, result

BASE = "https://api.ai-ark.com/v1/mcp"

RPC_HEADERS = {"Accept": "application/json, text/event-stream"}

# The strict-enum arguments, verified against the live tool schema 2026-08-25.
# Both the person-level and the company-level variants are enums, and each maps
# to the lookup tool that validates it.
LOOKUP_TOOL = {
    "industry": "industry_search",
    "location": "location_search",
    "companyIndustry": "industry_search",
    "companyLocation": "location_search",
    "companyTechnology": "technology_search",
}
ENUM_FIELDS = tuple(LOOKUP_TOOL)

# Which lookup feeds which cache: companyIndustry and industry share a catalogue.
CATALOGUE = {"industry": "industry", "companyIndustry": "industry",
             "location": "location", "companyLocation": "location",
             "companyTechnology": "technology"}

KEYWORD_SOURCES = "HEADLINE,SUMMARY,ORGANIZATION"

# Values this process has confirmed against the provider's own lookup. Cached
# for the life of the process so a batch does not repeat a lookup per record.
_validated = {catalogue: set() for catalogue in set(CATALOGUE.values())}


def reset_validated():
    """Forget every looked-up enum value. Tests and long-lived runners use this."""
    for values in _validated.values():
        values.clear()

POLL_ATTEMPTS = 5
POLL_INTERVAL = 2.0


class EnumNotLookedUp(ProviderError):
    """A strict-enum value was used without the lookup that validates it."""


def url():
    return f"{BASE}?token={key('AIARK_KEY')}"


_id = 0


def rpc(method, params=None):
    global _id
    _id += 1
    # Streamable-HTTP MCP requires both content types in Accept. A server that
    # gets only application/json answers 400 with an empty body.
    status, data = request("POST", url(), RPC_HEADERS,
                           {"jsonrpc": "2.0", "id": _id, "method": method,
                            "params": params or {}})
    # The message matters more than the status: a 400 here is usually
    # "sources is required", which names the fix.
    if isinstance(data, dict) and data.get("error"):
        error = data["error"]
        detail = error.get("message", error) if isinstance(error, dict) else error
        raise ProviderError(f"aiark {method}: {status}: {detail}")
    if not ok(status):
        raise ProviderError(f"aiark {method}: {status}")
    return mapping(data, f"aiark {method}").get("result", {})


def call_tool(name, arguments):
    return _content(rpc("tools/call", {"name": name, "arguments": arguments}))


def _content(res):
    """MCP returns result.content[{type,text}]. Unwrap it to data."""
    if not isinstance(res, dict):
        return {}
    content = res.get("content")
    if isinstance(content, list):
        for part in content:
            text = mapping(part, "aiark content").get("text")
            if text:
                try:
                    return json.loads(text)
                except (ValueError, TypeError):
                    return {"text": text}
        return {}
    return res.get("structuredContent") or res


def tools():
    res = rpc("tools/list")
    return [t.get("name") for t in mapping(res, "aiark tools").get("tools", [])
            if isinstance(t, dict) and t.get("name")]


def _lookup(catalogue, term, limit=None):
    tool = {"industry": "industry_search", "location": "location_search",
            "technology": "technology_search"}[catalogue]
    args = {"query": term}
    if limit:
        args["limit"] = limit
    values = call_tool(tool, args)
    names = (values.get("results") or values.get("items")
             or values.get(catalogue) or values.get("data") or [])
    out = [v.get("name") if isinstance(v, dict) else v for v in names]
    out = [v for v in out if v]
    _validated[catalogue].update(out)
    return out


def industry_search(term, limit=None):
    return _lookup("industry", term, limit)


def location_search(term, limit=None):
    return _lookup("location", term, limit)


def technology_search(term, limit=None):
    return _lookup("technology", term, limit)


def _guard_enums(params):
    """A strict enum value must have come from its lookup. Comma separated
    strings are checked token by token, which is how AI Ark takes multiples."""
    for field in ENUM_FIELDS:
        value = params.get(field)
        if value in (None, "", [], {}):
            continue
        items = value if isinstance(value, (list, tuple)) else str(value).split(",")
        for item in (i.strip() for i in items):
            if item and item not in _validated[CATALOGUE[field]]:
                tool = LOOKUP_TOOL[field]
                raise EnumNotLookedUp(
                    f"{field}={item!r} was not returned by {tool}. "
                    f"Call {tool}() first: it is a strict enum.")


def _person(raw):
    raw = raw if isinstance(raw, dict) else {}
    company = raw.get("company") or raw.get("organization") or raw.get("companyName")
    if isinstance(company, dict):
        company = company.get("name")
    return {
        "name": raw.get("fullName") or raw.get("full_name") or raw.get("name"),
        "title": raw.get("title") or raw.get("headline"),
        "company": company,
        "linkedin": raw.get("linkedin") or raw.get("linkedin_url") or raw.get("profile_url"),
        "email": raw.get("email"),
        "location": raw.get("location"),
    }


def _rows(data):
    for name in ("people", "content", "results", "data", "items"):
        rows = mapping(data, "aiark people").get(name)
        if isinstance(rows, list):
            return rows
    return []


def _search_args(filters, keyword_sources):
    """Shared by people_search and email_finder: they take the same filters."""
    _guard_enums(filters)
    args = {k: v for k, v in filters.items() if v not in (None, "", [], {})}
    if args.get("keyword"):
        # Without keywordSources the API answers 400 sources is required.
        args["keywordSources"] = keyword_sources or KEYWORD_SOURCES
    return args


def people_search(companyDomain=None, companyName=None, title=None, seniority=None,
                  keyword=None, industry=None, location=None, companyIndustry=None,
                  companyLocation=None, companyTechnology=None,
                  keyword_sources=KEYWORD_SOURCES, size=None, page=None, **extra):
    """Fallback people search. Enum guard and keywordSources both enforced.

    Argument names are AI Ark's own, verified against the live tool schema.
    """
    filters = {"companyDomain": companyDomain, "companyName": companyName,
               "title": title, "seniority": seniority, "keyword": keyword,
               "industry": industry, "location": location,
               "companyIndustry": companyIndustry, "companyLocation": companyLocation,
               "companyTechnology": companyTechnology, "size": size, "page": page}
    filters.update(extra)
    data = call_tool("people_search", _search_args(filters, keyword_sources))
    return [_person(r) for r in _rows(data)]


DONE = ("done", "completed", "complete", "finished", "success")
DEAD = ("failed", "error", "not_found", "cancelled")


def email_finder(keyword_sources=KEYWORD_SOURCES, **filters):
    """Async. Takes the same filters as people_search, returns a trackId."""
    data = call_tool("email_finder", _search_args(filters, keyword_sources))
    track = data.get("trackId") or data.get("track_id")
    if not track:
        raise ProviderError("aiark email_finder returned no trackId")
    return track


def _state(data):
    """The live schema calls it `state` (PENDING/DONE); accept `status` too."""
    return str(data.get("state") or data.get("status") or "pending").lower()


def email_finder_results(track_id, page=None, size=None):
    args = {"trackId": track_id}
    if page is not None:
        args["page"] = page
    if size is not None:
        args["size"] = size
    data = call_tool("email_finder_results", args)
    return {"track_id": track_id, "state": _state(data),
            "people": [_person(r) for r in _rows(data)]}


def find_email(attempts=POLL_ATTEMPTS, interval=POLL_INTERVAL, sleep=time.sleep,
               **filters):
    """Bounded poll. Gives up cleanly rather than looping for ever."""
    track = email_finder(**filters)
    for attempt in range(max(1, attempts)):
        res = email_finder_results(track)
        if res["state"] in DONE or res["state"] in DEAD:
            return res
        if attempt < attempts - 1:
            sleep(interval)
    return {"track_id": track, "state": "timeout", "people": []}


def _company(raw):
    """A company row from AI Ark into the neutral shape the pipeline reads."""
    raw = raw if isinstance(raw, dict) else {}
    return {
        "domain": raw.get("domain") or raw.get("website") or "",
        "company": (raw.get("companyName") or raw.get("name")
                    or raw.get("organization") or ""),
        "headcount": raw.get("employeeCount") or raw.get("headcount")
                     or raw.get("employees") or raw.get("size"),
        "industry": raw.get("industry") or "",
        "country": raw.get("country") or raw.get("location") or "",
        "website": raw.get("website") or raw.get("url") or "",
        "description": raw.get("description") or "",
    }


def company_search(companyIndustry=None, companyLocation=None,
                   companyTechnology=None, keyword=None, size=None,
                   keyword_sources=KEYWORD_SOURCES, page=None, **extra):
    """Company-level search. Enum guard enforced, same as people_search.

    Returns trimmed company dicts via _company. Pagination via page argument;
    the caller walks to last=true.
    """
    filters = {"companyIndustry": companyIndustry,
               "companyLocation": companyLocation,
               "companyTechnology": companyTechnology,
               "keyword": keyword, "size": size, "page": page}
    filters.update(extra)
    data = call_tool("company_search", _search_args(filters, keyword_sources))
    return [_company(r) for r in _rows(data)]


def check():
    """Free: list the tools the endpoint exposes. No search, no credit."""
    try:
        names = tools()
        return result("AI Ark", 200, f"{len(names)} tools", healthy=bool(names))
    except ProviderError as e:
        return failed("AI Ark", e)


def main(argv=None):
    p = argparse.ArgumentParser(prog="python -m src.providers.aiark")
    p.add_argument("--check", action="store_true")
    p.parse_args(argv)
    r = check()
    print(f"{'ok  ' if r['ok'] else 'FAIL'} {r['provider']:<12} {r['status']}  {r['note']}")
    return 0 if r["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
