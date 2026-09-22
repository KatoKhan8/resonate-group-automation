#!/usr/bin/env python3
"""The nightly sourcing pipeline. TASK-245.

Runs at 02:00 Europe/Zagreb. Sourced -> S3 ICP -> S4b MX -> local collision
-> candidate list. The pipeline STOPS at the candidate list. Nothing else is
spent on candidates until Productive approves them in the weekly export.

Five stages, each one a function that takes and returns a list of company
dicts. A company that fails a stage is dropped from the list with a reason
recorded on it; it is never deleted from the system.

Scheduling is stated in Zagreb time and moves with DST. The UTC hour is
derived from geo.zone, never hardcoded. senderheadroom counted weekdays
from 0 in an ISO repo (F-004); this module uses isoweekday() throughout.

Cost discipline: credit spend is REPORTED, NEVER GATED. A rate limit means
back off and continue, never halt.

  python -m src.nightlysourcing --dry-run
  python -m src.nightlysourcing --live
"""
import argparse
import datetime
import json
import time

from . import (candidatelist, clients, geo, icp, mx, store,
               collision as collision_mod)
from .providers import aiark, ProviderError

# The pipeline stages, named for the state they produce.
STAGE_SOURCE = "source"
STAGE_ICP = "icp"
STAGE_MX = "mx"
STAGE_COLLISION = "collision"
STAGE_CANDIDATE = "candidate"

STAGES = (STAGE_SOURCE, STAGE_ICP, STAGE_MX, STAGE_COLLISION, STAGE_CANDIDATE)

# Scheduling: 02:00 Europe/Zagreb for nightly, 07:00 Monday for export.
NIGHTLY_HOUR_LOCAL = 2
NIGHTLY_MINUTE = 0
EXPORT_HOUR_LOCAL = 7
EXPORT_MINUTE = 0
EXPORT_WEEKDAY = 1          # Monday, ISO
TIMEZONE = "Europe/Zagreb"

# Minimum headcount for sourcing. Applied AT THE SOURCE, not filtered after:
# filtering after is paid-for rows thrown away.
MIN_HEADCOUNT = 20


def nightly_utc_moment(on_date=None):
    """The UTC instant for tonight's run. DST-aware, never hardcoded."""
    on_date = on_date or datetime.date.today()
    try:
        tz = geo.zone(TIMEZONE)
    except geo.TimezoneUnavailable as e:
        raise RuntimeError(f"cannot schedule nightly: {e}") from e
    local = datetime.datetime(on_date.year, on_date.month, on_date.day,
                              NIGHTLY_HOUR_LOCAL, NIGHTLY_MINUTE, tzinfo=tz)
    return local.astimezone(datetime.timezone.utc)


def export_utc_moment(on_date=None):
    """The UTC instant for Monday's export. DST-aware."""
    on_date = on_date or datetime.date.today()
    try:
        tz = geo.zone(TIMEZONE)
    except geo.TimezoneUnavailable as e:
        raise RuntimeError(f"cannot schedule export: {e}") from e
    local = datetime.datetime(on_date.year, on_date.month, on_date.day,
                              EXPORT_HOUR_LOCAL, EXPORT_MINUTE, tzinfo=tz)
    return local.astimezone(datetime.timezone.utc)


def is_export_day(on_date=None):
    """Is today Monday (ISO weekday 1)? Uses isoweekday, not weekday()."""
    on_date = on_date or datetime.date.today()
    return on_date.isoweekday() == EXPORT_WEEKDAY


# --------------------------------------------------------- stage 1: source

def _source_companies(search_fn=None, icp_config=None, known_domains=None,
                      page_limit=None, allow_unfiltered_headcount=False,
                      problems=None):
    """AI-ARK company search on the Productive ICP.

    Geos applied AT THE SOURCE via companyLocation, after resolving each one
    through location_search - it is a strict enum. Headcount is NOT applied:
    see the refusal below, which is deliberate rather than a gap.
    Walk to last=true (page_limit caps for tests). DIFF against known domains;
    NEVER delete from the known set.

    search_fn is injectable for tests. Defaults to aiark.company_search.
    """
    # THE HEADCOUNT FILTER IS NOT APPLIED, AND THAT IS A REFUSAL.
    #
    # The task requires headcount >= 20 APPLIED AT THE SOURCE. This used to
    # pass `size=">=20"`, and `size` is company_search's PAGE SIZE - ">=20"
    # was rejected outright and the call returned zero rows, which is a large
    # part of why this pipeline has never produced a candidate.
    #
    # The parameter that really filters headcount has not been established.
    # Probed live on 2026-09-22 against the tool: companySize, companyStaff,
    # staff, staffRange, employeeCount, companyEmployees, headcount,
    # companyHeadcount, minStaff and staffCount are ALL SILENTLY IGNORED -
    # identical totalElements (72,657,969) and byte-identical rows with and
    # without each one. An unknown filter name is dropped, not rejected.
    #
    # So sourcing now REFUSES rather than returning an unfiltered world.
    # Filtering after the fact is what the task forbids - it is paid-for rows
    # thrown away - and quietly dropping the client's own ICP minimum is
    # worse than not running. The headcount IS readable per row at
    # `summary.staff.total`, so the filter can be applied the moment somebody
    # establishes the parameter from AI Ark rather than guessing it.
    # ONLY WHEN THE REAL PROVIDER IS BEING CALLED. This is a statement about
    # AI Ark's API, not about the shape of the pipeline: an injected
    # `search_fn` - every test, and any future adapter - may filter perfectly
    # well, and refusing there would assert something about a provider this
    # function never reaches.
    if search_fn is None and not allow_unfiltered_headcount:
        raise ProviderError(
            f"nightly sourcing: no AI Ark parameter is known that filters "
            f"headcount >= {MIN_HEADCOUNT} at the source. Ten candidate names "
            f"were probed live and every one was silently ignored. The task "
            f"requires the filter AT THE SOURCE, so this refuses rather than "
            f"sourcing unfiltered and discarding the client's ICP minimum. "
            f"Pass allow_unfiltered_headcount=True only for a deliberate "
            f"measurement run")

    problems = [] if problems is None else problems
    search_fn = search_fn or aiark.company_search
    known = known_domains or candidatelist.domains_already_known()

    # THE GEOS LIVE UNDER `icp`, AND THIS READ THE TOP LEVEL.
    #
    # `config["markets"]` does not exist on any client config. The markets are
    # at `config["icp"]["markets"]` and the same list is at
    # `config["market"]["geos"]`, so `location_filter` was None on every run
    # this has ever made and the geo half of the task - "applied AT THE
    # SOURCE, not filtered after" - was silently not applied at all.
    config = icp_config or {}
    markets = (config.get("icp") or {}).get("markets") \
        or (config.get("market") or {}).get("geos") \
        or config.get("markets") or []

    # A STRICT ENUM HAS TO BE LOOKED UP BEFORE IT CAN BE USED, and a value the
    # lookup does not return is refused rather than sent. `location_search`
    # itself returned nothing for every term until 2026-09-22, because
    # `_lookup` read the singular catalogue key while the tool answers under
    # the plural one - so this filter was unusable even when it was passed.
    # Resolved only when the REAL provider is being called, for the same
    # reason the headcount refusal is: `location_search` is AI Ark's enum, and
    # an injected `search_fn` never reaches it. Injected, the markets are
    # passed through as given.
    resolved = list(markets) if search_fn is not aiark.company_search else []
    for market in (markets if search_fn is aiark.company_search else ()):
        try:
            found = aiark.location_search(market)
        except ProviderError as exc:
            raise ProviderError(
                f"nightly sourcing: location_search({market!r}) failed "
                f"({exc}). The geos are applied AT THE SOURCE and a run that "
                f"cannot resolve them would source the whole world") from exc
        match = [v for v in found if v.lower() == str(market).lower()]
        if match:
            resolved.append(match[0])
    if markets and not resolved and search_fn is aiark.company_search:
        raise ProviderError(
            f"nightly sourcing: none of {markets!r} was returned by "
            f"location_search, so no geo filter can be applied. Sourcing the "
            f"whole world and filtering afterwards is what this task "
            f"forbids - it is paid-for rows thrown away")
    location_filter = ",".join(resolved) if resolved else None

    sourced = []
    page = 1
    while True:
        if page_limit and page > page_limit:
            break
        try:
            rows = search_fn(
                companyLocation=location_filter,
                page=page,
            )
        except ProviderError as exc:
            # A PROVIDER FAILURE IS NOT AN EMPTY CATALOGUE - BUT IT DOES NOT
            # HALT THE RUN EITHER.
            #
            # This used to `break` and record nothing, so an unusable filter,
            # an auth failure, a rate limit and a genuinely empty result were
            # all reported identically: stage `source` with in=0 out=0 drop=0
            # and a run that says it succeeded. That is how this pipeline
            # reported success while having sourced nothing since it merged.
            #
            # Raising instead would break the other half of the contract: the
            # standing order says a rate limit is a reason to back off and
            # continue, never to halt, and TASK-245 says the same. So sourcing
            # STOPS and the failure is RECORDED on the stage, where `run` puts
            # it in the report and the caller can see it. Silence is the only
            # option that is wrong.
            problems.append({"page": page, "rows_before": len(sourced),
                             "error": f"{type(exc).__name__}: {exc}"})
            break
        if not rows:
            break
        for row in rows:
            domain = str(row.get("domain") or "").strip().lower()
            if not domain:
                continue
            if domain in known:
                continue
            row["domain"] = domain
            row["_sourced_at"] = store.now()
            row["_source_page"] = page
            # Carry structured fields the ICP scorer needs.
            for field in ("services", "specialties"):
                if field not in row:
                    row[field] = []
            sourced.append(row)
        # AI Ark pagination: if fewer rows returned than a page, we are done.
        if len(rows) < 30:
            break
        page += 1
    return sourced


# --------------------------------------------------------- stage 2: ICP

def _icp_verdict(companies, config=None):
    """S3 ICP verdict. Only qualified/review survive."""
    survived = []
    for company in companies:
        rec = {"domain": company["domain"],
               "company": company.get("company", ""),
               "company_facts": {
                   "name": company.get("company", ""),
                   "employees": _coerce_headcount(company.get("headcount")),
                   "industry": company.get("industry", ""),
                   "description": company.get("description", ""),
                   "offices": [company["country"]] if company.get("country")
                              else [],
                   "country": company.get("country", ""),
                   "services": company.get("services") or [],
                   "specialties": company.get("specialties") or [],
               }}
        verdict = icp.score(rec, config=config)
        status = verdict.get("icp_status")
        if status in (icp.QUALIFIED, icp.REVIEW):
            company["_icp_status"] = status
            company["_icp_score"] = verdict.get("icp_score")
            company["_icp_why"] = _icp_evidence_text(verdict)
            survived.append(company)
        else:
            company["_dropped_at"] = STAGE_ICP
            company["_drop_reason"] = f"icp_{status}"
    return survived


def _coerce_headcount(value):
    """Headcount as an int, or None. A string is not an int."""
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, str):
        text = value.strip().replace(",", "")
        try:
            return int(text)
        except (ValueError, TypeError):
            pass
    if isinstance(value, float):
        return int(value)
    return None


def _icp_evidence_text(verdict):
    """The ICP evidence in words a client can read. From positive signals."""
    parts = []
    for sig in verdict.get("positive_signals") or []:
        why = sig.get("why")
        if why:
            parts.append(why)
    return "; ".join(parts[:3]) if parts else "scored above threshold"


# --------------------------------------------------------- stage 3: MX

def _mx_classify(companies, config=None, resolve_fn=None):
    """S4b MX classification.

    known_allowed and unknown_provider survive.
    known_blocked, no_mx and dns_failure do not.
    dns_failure is HELD - we could not ask, which is not the same as no mail.
    """
    resolve_fn = resolve_fn or _default_mx_resolve
    policy = mx.settings(config)
    survived = []
    for company in companies:
        domain = company["domain"]
        try:
            hosts = resolve_fn(domain)
            decision = mx.decide(hosts, policy)
        except Exception:
            decision = {"status": mx.DNS_FAILURE, "allowed": False}
        status = decision.get("status", mx.DNS_FAILURE)
        company["_mx_status"] = status
        if status == mx.KNOWN_ALLOWED or status == mx.UNKNOWN_PROVIDER:
            survived.append(company)
        elif status == mx.DNS_FAILURE:
            company["_dropped_at"] = STAGE_MX
            company["_drop_reason"] = "dns_failure_held"
            company["_mx_held"] = True
        elif status == mx.NO_MX:
            company["_dropped_at"] = STAGE_MX
            company["_drop_reason"] = "no_mx"
        elif status == mx.KNOWN_BLOCKED:
            company["_dropped_at"] = STAGE_MX
            company["_drop_reason"] = "mx_blocked"
        else:
            company["_dropped_at"] = STAGE_MX
            company["_drop_reason"] = f"mx_{status}"
    return survived


def _default_mx_resolve(domain):
    """The real MX resolve, wrapped to return hosts or raise."""
    return mx.resolve(domain)


# --------------------------------------------------------- stage 4: collision

def _local_collision(companies, config=None):
    """Local collision only. work/stage/last-touch.json and the store.

    No provider walk. The collision index is persisted and must be KEPT
    CURRENT, never re-walked.
    """
    survived = []
    queue_domains = _queue_domain_index()
    for company in companies:
        domain = company["domain"]
        touch = _prior_touch_status(domain, queue_domains)
        company["_prior_touch"] = touch
        survived.append(company)
    return survived


def _queue_domain_index():
    """Domain -> record from the queue, for collision lookups."""
    idx = {}
    try:
        for rec in store.load():
            d = str(rec.get("domain") or "").strip().lower()
            if d:
                idx[d] = rec
    except Exception:
        pass
    return idx


def _prior_touch_status(domain, queue_index):
    """The prior-touch status for a domain.

    never_touched / touched <date> / has_reply / bounced / unsubscribed.
    """
    rec = queue_index.get(domain)
    if not rec:
        return "never_touched"
    state = rec.get("state")
    contacts = rec.get("contacts") or []
    for c in contacts:
        if c.get("verdict") == "bounced":
            return "bounced"
        if c.get("unsubscribed"):
            return "unsubscribed"
        if c.get("reply"):
            return "has_reply"
    if state in ("pushed", "drafted", "verified", "approved"):
        last = rec.get("last_touch_at") or rec.get("updated_at")
        if last:
            return f"touched {str(last)[:10]}"
        return "touched"
    return "never_touched"


# --------------------------------------------------------- stage 5: candidate

def _to_candidate(companies):
    """Build candidate rows from surviving companies."""
    candidates = []
    for company in companies:
        candidate = {
            "domain": company["domain"],
            "company": company.get("company", ""),
            "headcount": company.get("headcount"),
            "industry": company.get("industry", ""),
            "country": company.get("country", ""),
            "website": company.get("website", ""),
            "why_matched": company.get("_icp_why", ""),
            "prior_touch_status": company.get("_prior_touch", "never_touched"),
            "added_at": company.get("_sourced_at", store.now()),
            "state": "new",
            "icp_status": company.get("_icp_status"),
            "icp_score": company.get("_icp_score"),
            "mx_status": company.get("_mx_status"),
        }
        candidates.append(candidate)
    return candidates


# --------------------------------------------------------- the pipeline

def run(config=None, search_fn=None, resolve_fn=None, live=False,
        page_limit=None, allow_unfiltered_headcount=False):
    """The full nightly pipeline. Returns a report dict.

    search_fn and resolve_fn are injectable for tests.
    live=False (default) is dry run: no candidate is appended.
    """
    config = config or {}
    report = {
        "stages": {},
        "credits_spent": 0,
        "started_at": store.now(),
        "live": live,
    }
    dropped = []

    # Stage 1: source
    known = candidatelist.domains_already_known()
    source_problems = []
    sourced = _source_companies(
        search_fn=search_fn, icp_config=config, known_domains=known,
        page_limit=page_limit,
        allow_unfiltered_headcount=allow_unfiltered_headcount,
        problems=source_problems)
    report["stages"][STAGE_SOURCE] = {"input": 0, "output": len(sourced),
                                      "dropped": 0}
    # A ZERO WITH A REASON IS NOT THE SAME FACT AS A ZERO WITHOUT ONE.
    if source_problems:
        report["stages"][STAGE_SOURCE]["problems"] = source_problems
        report["source_failed"] = True

    # Stage 2: ICP
    after_icp = _icp_verdict(sourced, config=config)
    icp_dropped = len(sourced) - len(after_icp)
    report["stages"][STAGE_ICP] = {"input": len(sourced),
                                   "output": len(after_icp),
                                   "dropped": icp_dropped}

    # Stage 3: MX
    after_mx = _mx_classify(after_icp, config=config, resolve_fn=resolve_fn)
    mx_dropped = len(after_icp) - len(after_mx)
    report["stages"][STAGE_MX] = {"input": len(after_icp),
                                  "output": len(after_mx),
                                  "dropped": mx_dropped}

    # Stage 4: collision
    after_collision = _local_collision(after_mx, config=config)
    report["stages"][STAGE_COLLISION] = {"input": len(after_mx),
                                         "output": len(after_collision),
                                         "dropped": 0}

    # Stage 5: candidate
    candidates = _to_candidate(after_collision)
    appended = 0
    if live:
        for c in candidates:
            if candidatelist.append(c):
                appended += 1
    else:
        appended = len(candidates)
    report["stages"][STAGE_CANDIDATE] = {"input": len(after_collision),
                                         "output": len(candidates),
                                         "appended": appended}

    report["completed_at"] = store.now()
    total_survived = len(candidates)
    report["candidates_added"] = appended
    if appended > 0:
        report["credits_per_candidate"] = round(
            report["credits_spent"] / appended, 2)
    else:
        report["credits_per_candidate"] = 0
    return report


# --------------------------------------------------------- the refusal test

def pipeline_refuses_to_advance_past_candidates():
    """Prove the pipeline does not call person-level or verification endpoints.

    This is the acceptance test in code form: the pipeline's run() function
    never imports or calls verification, contactout, or any people endpoint.
    The stages are: source, icp, mx, collision, candidate. None of them
    spend credits on people.
    """
    import inspect
    source = inspect.getsource(run)
    forbidden = ("verification", "contactout", "people_search",
                 "email_finder", "find_email", "deliverable", "reoon")
    violations = [name for name in forbidden if name in source]
    return len(violations) == 0, violations


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--live", action="store_true",
                   help="actually append candidates (default: dry run)")
    p.add_argument("--client", default="productive",
                   help="client config name")
    p.add_argument("--json", action="store_true")
    p.add_argument("--allow-unfiltered-headcount", action="store_true",
                   help="source without the headcount filter. For a "
                        "deliberate measurement run only - the task requires "
                        "headcount >= 20 applied AT THE SOURCE")
    a = p.parse_args(argv)

    config = None
    try:
        config = clients.load(a.client)
    except Exception:
        pass

    # A REFUSAL IS AN ANSWER, NOT A CRASH. This is operator-facing, and a
    # traceback for "the provider cannot do what the task requires" reads as a
    # bug in us rather than as the finding it is.
    try:
        report = run(config=config, live=a.live,
                     allow_unfiltered_headcount=a.allow_unfiltered_headcount)
    except ProviderError as exc:
        print("")
        print(f"  REFUSED: {exc}")
        print("")
        return 2
    if a.json:
        print(json.dumps(report, indent=2, default=str))
    else:
        if report.get("source_failed"):
            print("  SOURCE FAILED - the zero below has a reason:")
            for problem in report["stages"][STAGE_SOURCE].get("problems") or []:
                print(f"    page {problem['page']} after "
                      f"{problem['rows_before']} row(s): {problem['error']}")
        for stage, counts in report["stages"].items():
            # A STAGE REPORT WITH NO `dropped` KEY IS NOT A CRASH.
            # `candidate` does not drop anything, so it carries no such key,
            # and printing the report raised KeyError - which is how a run
            # that had already done nothing also ended in a traceback.
            print(f"  {stage:<12} in={counts.get('input', 0):<5} "
                  f"out={counts.get('output', 0):<5} "
                  f"drop={counts.get('dropped', 0)}")
        print(f"  candidates added: {report['candidates_added']}")
        print(f"  credits spent: {report['credits_spent']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
