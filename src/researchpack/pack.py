"""Assemble one account's research pack. READ-ONLY, CACHED, COSTED.

    pack = researchpack.build("acme.test")                   # cache only
    pack = researchpack.build("acme.test", live=True,
                              company="Acme Ltd",
                              champion="https://.../in/ada")

## DRY RUN IS THE DEFAULT, AS EVERYWHERE ELSE HERE

`CLAUDE.md`: "Dry run is the default for anything that sends. --live is
always explicit." Nothing here sends, but everything here SPENDS, and the
same rule is the right one. `live=False` reads the cache and starts no
actor. A pack built without `live` is still a usable pack - it is the part
that was already paid for.

## THE ORDER OF THE FOUR SOURCES IS LOAD-BEARING

`open_roles` runs FIRST, and not because roles matter most. The estate holds
domains; `company_posts` needs a LinkedIn company URL. The jobs actor is the
only one of the four that can be aimed with a company NAME and that returns
`companyUrl` - so the slug comes out of the roles run and makes the posts run
addressable. `actors.slug_from_jobs` will only accept a slug whose row also
names this record's own website, so a name collision cannot hand one company
another company's posts.

A company with no public LinkedIn job listing yields no slug. That is not a
failure to be worked around: the pack records `company_posts` as
UNADDRESSABLE, with the reason, and buys nothing. Measured coverage of that
case is in `docs/RESEARCH-PACK-PILOT-2026-09-24.md`.

## COST IS RECORDED AT THE MOMENT OF THE CALL, THROUGH THE ONE LEDGER

`CLAUDE.md`: "Every paid call goes through enrich's `spend()`, which writes
the waterfall ledger. A provider call that skips it is invisible to the
spend audit, and an audit that reports clean because it watched nothing is
worse than none."

`enrich.spend` is a closure over one record and cannot be imported, so this
calls `spendledger.record` - the module-level API that closure itself
writes through. A run served from cache records NOTHING, because nothing
was bought.

## EVERY FACT CARRIES ITS PROVENANCE OR IT IS NOT STORED

See `facts.make`. A pack is worth having because a first line can be traced
back through it, and `src/copylint.py` is the thing that traces.
"""
from .. import spendledger, store
from . import actors as actorspec
from . import cache, facts


class PackRefused(RuntimeError):
    """A pack that cannot be built honestly is refused, never half-built."""


def _items(run_output, limit):
    rows = run_output if isinstance(run_output, list) else []
    return [r for r in rows if isinstance(r, dict)][:limit]


def _dotted(row, path):
    """`postedAt.date` is where harvestapi puts a post's date.

    The old flat key list could not see it, so every company and person post
    would have come back undated - and an undated fact is the one `quality`
    demands a higher relevance score of before it will call it strong. A
    date that exists and is not read is worse than no date, because the pack
    reports UNKNOWN about something it was told.
    """
    value = row
    for part in str(path).split("."):
        if not isinstance(value, dict):
            return None
        value = value.get(part)
    return value


def _first(row, keys):
    for key in keys or ():
        value = _dotted(row, key)
        if value:
            return value
    return None


def _facts_from(name, rows, subject=None, domain=None):
    spec = actorspec.ACTORS[name]
    if not spec["kind"]:
        # `company_slug` answers a question rather than asserting anything.
        # Its rows reach the caller through `raw`; nothing it returns is
        # quotable, so nothing it returns becomes a fact.
        return []
    fields = spec["fields"]
    status_field = spec.get("status_field")
    identity = spec.get("identity")
    out = []
    for row in rows:
        # A ROW THAT CANNOT PROVE IT IS THIS COMPANY MAKES NO FACT.
        # `open_roles` is aimed with a company NAME and the actor returns
        # whatever that name matched; 70% of the rows in the 2026-09-24
        # pilot were somebody else. See `actors.ACTORS["open_roles"]`.
        if identity and not actorspec.is_this_company(row, domain, identity):
            continue
        if status_field:
            from ..providers import ok
            status = _dotted(row, status_field)
            if status is not None and not ok(status):
                continue
        try:
            out.append(facts.make(
                spec["kind"],
                _first(row, fields["url"]),
                _first(row, fields["date"]),
                _first(row, fields["body"]),
                subject=subject,
                extra={"actor": spec["actor"]}))
        except facts.UnusableFact:
            # DROPPED, NOT PATCHED. A row with no url or no text cannot
            # support a claim, and inventing either to keep the count up is
            # how an unattributable sentence reaches a client.
            continue
    return out


def _checked(name, target):
    """A LinkedIn target goes through the provider's own URL guard.

    THIS IS WHERE THE WIDENED ALLOWLIST IS CONSUMED, and it is consumed by
    naming the hosts rather than by switching the check off:
    `providers.apify.check_url` still refuses a scheme that is not http(s),
    an embedded credential, an odd port, a loopback name, an internal suffix
    and a literal private address, exactly as it does for a site crawl.
    """
    spec = actorspec.ACTORS[name]
    hosts = spec.get("hosts")
    if not hosts:
        return target
    from ..providers import apify
    return apify.check_url(str(target), allowed_domain=hosts, resolve=False)


def run_actor(name, target, subject=None, client=None, runner=None,
              raw=None, domain=None):
    """One actor run. Records the planned cost BEFORE reading the result.

    `runner` is the seam the cassette tests drive: it takes
    `(actor, payload, limit)` and returns the dataset rows. The default
    reaches `providers.apify`'s run lifecycle, which is IMPORTED rather
    than reimplemented - the polling, the timeout and the SSRF posture live
    there and a second copy of them would drift.

    `raw`, when a list is passed, receives the untouched rows. The slug this
    pack needs lives on a jobs ROW and not on any fact made from one, and
    re-running the actor to read it again would be paying twice.
    """
    spec = actorspec.ACTORS[name]
    if spec["needs_session"]:
        raise PackRefused(
            "%s needs a logged-in session; this pack reads public surfaces "
            "only" % name)
    payload = actorspec.build_input(name, _checked(name, target))
    # BEFORE the call, not after. A run that starts and then fails still
    # cost something, and a ledger that records only successes understates
    # spend in exactly the runs worth auditing.
    spendledger.record(client or "unattributed", "apify", name,
                       actorspec.planned_cost(name))
    rows = _items((runner or _live_runner)(spec["actor"], payload,
                                           spec["limit"]), spec["limit"])
    if raw is not None:
        raw.extend(rows)
    return _facts_from(name, rows, subject=subject, domain=domain)


def _live_runner(actor, payload, limit):
    """Start, poll, read. The polling is `providers.apify`'s."""
    from ..providers import apify
    run = _start(actor, payload)
    finished = apify.wait_for(run["id"])
    dataset = (finished or {}).get("dataset_id") or run.get("dataset_id")
    if not dataset:
        return []
    return apify.dataset_items(dataset, limit)


def _start(actor, payload):
    """`apify.start_run` builds the CRAWLER's input and cannot carry ours.

    Posting a run is three lines against helpers that module already
    exports. Re-implementing the POLLING would be the part worth refusing,
    and that is imported above rather than copied.

    `maxTotalChargeUsd` is the bound that matters on a pay-per-event actor.
    The actor `timeout` bounds a compute-unit run; it does not bound one that
    bills per row, where a target with ten thousand posts is a large bill
    inside a fast run. Apify stops the run the moment the ceiling is reached.
    """
    from ..providers import apify
    from ..providers import ProviderError, mapping, ok, query, request
    token = apify.key(apify.KEY_VAR)
    status, data = request(
        "POST", query(apify.actor_endpoint(actor, "/runs"),
                      {"token": token, "timeout": apify.RUN_TIMEOUT,
                       "maxTotalChargeUsd": MAX_CHARGE_PER_RUN_USD}),
        {}, payload)
    if not ok(status):
        raise ProviderError("apify start %s: %s" % (actor, status))
    run = mapping(data, "apify start").get("data") or {}
    if not run.get("id"):
        raise ProviderError("apify start returned no run id")
    return {"id": run["id"], "dataset_id": run.get("defaultDatasetId")}


#: Ten times the dearest planned run in `actors.ACTORS`, so a normal run is
#: nowhere near it and a runaway one stops. It is a circuit breaker, not a
#: budget: the budget is the caller's, and `scripts/researchpack_pilot.py`
#: carries its own total.
MAX_CHARGE_PER_RUN_USD = 0.25


def _label(name, profile):
    return name if not profile else "%s:%s" % (name, profile)


def _vanity(url):
    """The profile's own handle, off the end of its LinkedIn path."""
    from urllib.parse import urlparse
    path = (urlparse(str(url or "")).path or "").strip("/").lower()
    return path.rsplit("/", 1)[-1] or "unknown"


def _profile_key(name, profile, target=None):
    """Company actors share the domain key; person actors get their own.

    THE OPERATOR ASKED FOR BOTH KEYS AND THIS IS WHERE THEY DIVERGE. One
    account whose champion changed must re-buy that champion and not the
    company posts, so a person run is cached under the profile and a
    company run under the actor name.

    AND THE PERSON KEY CARRIES THE PERSON, not only the role. Keyed on
    `champion` alone, an account whose champion changed reads the PREVIOUS
    champion's posts out of the cache and attributes them to the new one -
    which is not a cost defect but a wrong-person claim, the failure this
    repository already has a report about. The test that guarded this
    asserted zero new runs after a champion change and called that the point
    of two keys; it was asserting the defect.
    """
    if name != "person_posts":
        return name
    return "%s:%s" % (profile, _vanity(target))


def _site_urls(domain, limit):
    """The company's own pages, chosen by `providers.apify` and not here.

    `candidate_urls` already answers "which pages of this domain is this
    integration willing to look at", already runs `check_url` against the
    record's own domain, and is already bounded. A second list of guessed
    paths in this module would be the same truth in two places.
    """
    from ..providers import apify
    return [u["url"] for u in apify.candidate_urls(
        domain, apify.SOURCES, max_pages=limit)]


def build(domain, live=False, champion=None, exec_profile=None, client=None,
          runner=None, now=None, company_url=None, company=None,
          sources=None, resolve_slug=False):
    """One account's pack. Cache first, actors only with `live=True`.

    `company` is the company's NAME and is what `open_roles` is aimed with.
    Without it there is no roles run, and without a roles run there is no
    slug - so `company_posts` is unaddressable unless `company_url` is
    supplied directly. The pack says which of those happened.
    """
    domain = str(domain or "").strip().lower().lstrip("@")
    if not domain:
        raise PackRefused("a research pack needs a domain")
    now = now or store.now()
    out = {"domain": domain, "built_at": now, "facts": [], "cost": 0,
           "usd": 0.0, "cached": [], "bought": [], "skipped": [],
           "unaddressable": {}, "slug": company_url or None}
    wanted = list(sources or ("open_roles", "company_posts", "person_posts",
                              "site_content"))

    def take(name, target, profile=None, raw=None):
        """Cache, then buy, then record. Returns True if anything was had."""
        label = _label(name, profile)
        key = _profile_key(name, profile, target)
        hit = cache.get(domain, profile=key, now=now)
        if hit:
            out["facts"].extend(hit.get("facts") or [])
            out["cached"].append(label)
            if raw is not None:
                raw.extend(hit.get("rows") or [])
            return True
        if not live:
            out["skipped"].append(label)
            return False
        rows = []
        found = run_actor(name, target, subject=profile, client=client,
                          runner=runner, raw=rows, domain=domain)
        if raw is not None:
            raw.extend(rows)
        out["facts"].extend(found)
        out["cost"] += actorspec.planned_cost(name)
        out["usd"] += actorspec.usd_per_account(name)
        out["bought"].append(label)
        # THE SLUG IS CACHED WITH THE FACTS IT CAME WITH. A pack rebuilt
        # tomorrow must not have to re-buy the roles run to learn where the
        # company's LinkedIn page is.
        extra = {"rows": _slug_rows(name, rows)} if name in SLUG_ACTORS else {}
        cache.put(domain, found, profile=key,
                  cost=actorspec.planned_cost(name), now=now, extra=extra)
        return True

    job_rows = []
    if "open_roles" in wanted:
        if company:
            take("open_roles", company, raw=job_rows)
        else:
            out["unaddressable"]["open_roles"] = (
                "no company name on the record; the jobs actor is aimed by "
                "name and nothing here may invent one from the domain")

    if "company_posts" in wanted:
        slug = company_url or actorspec.slug_from_jobs(job_rows, domain)
        out["slug_source"] = ("supplied" if company_url else
                              "open_roles" if slug else None)
        resolver_ran = False
        if not slug and resolve_slug and company:
            resolver_ran = True
            # OPT-IN, AND ONLY AFTER THE JOBS ROUTE HAS FAILED. See
            # `actors.ACTORS["company_slug"]`: the operator asked for the
            # slug to come out of the jobs run, and it does - for a company
            # that is hiring. This is what the rest cost.
            rows = []
            take("company_slug", company, raw=rows)
            slug = actorspec.slug_from_companies(rows, domain)
            out["slug_source"] = "company_slug" if slug else None
        out["slug"] = slug
        if slug:
            take("company_posts", slug)
        else:
            out["unaddressable"]["company_posts"] = (
                "no LinkedIn company slug: %s%s" % (
                    ("the jobs run returned no row whose companyWebsite is "
                     "on this domain" if job_rows else
                     "no open roles were returned for this company, and the "
                     "jobs actor is the only source of the slug"),
                    ("; the company resolver was asked and its row did not "
                     "name this domain either" if resolver_ran else
                     ". The company resolver was not asked - it is opt-in")))

    if "person_posts" in wanted:
        for profile, url in (("champion", champion), ("exec", exec_profile)):
            if url:
                take("person_posts", url, profile=profile)
            else:
                out["unaddressable"]["person_posts:%s" % profile] = (
                    "no LinkedIn profile url for the %s on this record"
                    % profile)

    if "site_content" in wanted:
        urls = _site_urls(domain, actorspec.ACTORS["site_content"]["limit"])
        if urls:
            take("site_content", urls)
        else:
            out["unaddressable"]["site_content"] = (
                "no candidate url on %s survived the url guard" % domain)

    out["fact_count"] = len(out["facts"])
    out["by_kind"] = {k: len([f for f in out["facts"] if f["kind"] == k])
                      for k in facts.KINDS}
    out["usd"] = round(out["usd"], 6)
    # THE PACK SAYS WHAT IT DOES NOT HAVE. A downstream step that reads an
    # empty pack as "nothing to say about them" and one that reads it as
    # "we never looked" write different emails.
    if out["skipped"]:
        out["note"] = ("built without live: %s were not bought, so an absent "
                       "fact here is an unasked question rather than an "
                       "answer" % ", ".join(out["skipped"]))
    return out


#: What of a slug-bearing row is worth keeping once its facts are made. A
#: jobs row carries a full job description and a company "About" text; the
#: pack needs the fields that identify the company page, and a cache is not
#: a place to park somebody's whole listing.
SLUG_ACTORS = {"open_roles": ("companyUrl", "companyWebsite", "companyName"),
               "company_slug": ("linkedinUrl", "website", "name")}


def _slug_rows(name, rows):
    fields = SLUG_ACTORS.get(name)
    if not fields:
        return []
    return [{k: r.get(k) for k in fields if r.get(k)}
            for r in rows or [] if isinstance(r, dict)]
