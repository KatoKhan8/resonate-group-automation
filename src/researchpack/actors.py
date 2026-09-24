"""Which Apify actors this pack may run, what each costs, and what it reads.

## EVERY ACTOR ID HERE WAS ASKED OF APIFY, NOT REMEMBERED

Operator, 2026-09-24: "do not guess an actor id". The three ids this module
carried until today were guesses and all three were wrong:
`apify~linkedin-company-posts-scraper`, `apify~job-listings-scraper` and
`apify~linkedin-profile-posts-scraper` each answer **404 record-not-found**
on `GET /v2/acts/{id}`. Nothing in the package could ever have run - the
cassettes matched on those names, so the tests were green against actors
that do not exist.

The ids below were chosen from `GET /v2/store`, confirmed to exist with
`GET /v2/acts/{id}`, and then RUN, on 2026-09-24, against public targets.
The input shapes are each actor's own declared input schema read from its
latest build, not a shape inferred from its name.

## READ-ONLY, AND NO LINKEDIN SESSION

`needs_session` is carried on every entry and asserted in the tests, so an
actor added later has to answer the question rather than inherit a silence.
For each one the answer was confirmed twice: in the actor's own README,
fetched from `GET /v2/actor-builds/{id}` (harvestapi: "No cookies or account
required"; bebity: "no LinkedIn account, no cookies, no login required"),
and by a live run from this account, which holds no LinkedIn cookie of any
kind and got rows back.

## PROXIES: DATACENTER, AND THERE IS NO PATH TO RESIDENTIAL

Operator, 2026-09-24: datacenter pool unless a specific actor is blocked.
`{"useApifyProxy": true}` with no `apifyProxyGroups` is Apify's automatic
DATACENTER pool; residential requires naming the RESIDENTIAL group, and no
input built here names a proxy group at all. Nothing was blocked in the
pilot, so nothing moved, and the code has no branch that could move it
without an edit.

Note the shape of the field, which the old module got wrong for a different
reason: `proxyConfiguration` is the website crawler's input, and the three
LinkedIn actors do not declare it - they route their own requests. It is
sent only where the actor's schema declares it, which is what `proxy` below
records.

## COST IS AN ARITHMETIC, NOT A GUESS

All four actors bill PAY_PER_EVENT and this account is on the SCALE plan at
tier SILVER, so the per-event prices are the SILVER rows of each actor's
`eventTieredPricingUsd`, read from `GET /v2/acts/{id}`:

    company_posts / person_posts   start $0.00005 + $0.00175 per post
                                   ($0.001 "no-result" when a target has none)
    open_roles                     start $0.00005 + $0.00110 per job
    company_slug                   start $0.00005 + $0.00350 per company
    site_content                   compute units, measured per run

MEASURED per account over 24 real accounts on 2026-09-24: site $0.02888,
roles $0.00335, person posts $0.00265, company posts $0.00260, slug resolver
$0.00238 - $0.03987 in total, which is $781.94 at 19,612 accounts against a
$199 budget. The full arithmetic and the options are in
`docs/RESEARCH-PACK-PILOT-2026-09-24.md`.

`usd_per_account` is that arithmetic at this entry's own limit. `cost` is the
same number in the spend ledger's integer cents, ROUNDED UP: the ledger's
unit is an integer and a sub-cent call recorded honestly as `int(0.5)` is a
call recorded as free. Rounding up overstates, which fails closed - a
ceiling is reached sooner than it truly would be - and the exact figure
travels in `usd_per_account` for the reporting that needs it.
"""
import math

#: Every LinkedIn target must be on one of these, checked through
#: `providers.apify.check_url` before any run starts. See that module's
#: `RESEARCH_HOSTS`: this is the widening, and it is the whole of it.
LINKEDIN_HOSTS = ("linkedin.com",)

ACTORS = {
    # ---------------------------------------------------------------- 1
    "open_roles": {
        "actor": "bebity/linkedin-jobs-scraper",
        "kind": "open_role",
        "needs_session": False,
        "proxy": False,
        "hosts": None,                      # targeted by company NAME
        "limit": 10,
        "usd_per_run": 0.00005,
        "usd_per_item": 0.0011,
        "fields": {"url": ("jobUrl",), "body": ("title", "description"),
                   "date": ("publishedAt",)},
        # EVERY ROW HAS TO PROVE IT IS THIS COMPANY, and it is not a
        # formality. `companyName` is a TEXT FILTER: measured over the
        # 2026-09-24 pilot, 50 of the 71 rows returned - 70% - were a
        # different company that merely shares part of a name, and on four
        # of the eight accounts that got any rows at all, ALL TEN were the
        # wrong company. Without this the pack would have made 71
        # `open_role` facts of which 50 assert that somebody else is hiring,
        # and a first line built on one is a wrong-company claim in front of
        # a client. `slug_from_jobs` already applied this test to the SLUG;
        # the facts were going out unchecked beside it.
        "identity": "companyWebsite",
        "why": "open roles: what they are building and where it hurts - and "
               "the only source here that returns the company's LinkedIn "
               "slug, which is what makes company_posts addressable",
    },
    # ------------------------------------------------- 1a, OFF BY DEFAULT
    #
    # NOT ONE OF THE FOUR SOURCES. It makes no fact and its `kind` is only
    # here because the registry requires one; `pack.build` never adds its
    # output to a pack. It exists because the measured answer to "can the
    # jobs actor supply the slug" is "only for a company that has a live
    # LinkedIn job listing", and in this estate most do not - the numbers
    # are in `docs/RESEARCH-PACK-PILOT-2026-09-24.md`.
    #
    # `searches` takes company NAMES and the row comes back with both
    # `linkedinUrl` and `website`, so the same identity test that guards the
    # jobs route guards this one. It is opt-in - `build(..., resolve_slug=
    # True)` - because it is a fifth actor and a cost the operator did not
    # ask for, and a fallback that turns itself on is a cost nobody chose.
    "company_slug": {
        "actor": "harvestapi/linkedin-company",
        "kind": None,
        "needs_session": False,
        "proxy": False,
        "hosts": None,                      # targeted by company NAME
        "limit": 1,
        "usd_per_run": 0.00005,
        "usd_per_item": 0.0035,
        "fields": {"url": (), "body": (), "date": ()},
        "why": "resolve a company NAME to its LinkedIn page when the jobs "
               "run could not, so company_posts is addressable for a "
               "company that happens not to be hiring",
    },
    # ---------------------------------------------------------------- 2
    "company_posts": {
        "actor": "harvestapi/linkedin-company-posts",
        "kind": "company_post",
        "needs_session": False,
        "proxy": False,
        "hosts": LINKEDIN_HOSTS,
        "limit": 3,
        "usd_per_run": 0.00005,
        "usd_per_item": 0.00175,
        "fields": {"url": ("linkedinUrl", "shareLinkedinUrl"),
                   "body": ("content",),
                   "date": ("postedAt.date",)},
        "why": "the last 3 company posts: what they are saying in public",
    },
    # ---------------------------------------------------------------- 3
    "person_posts": {
        "actor": "harvestapi/linkedin-profile-posts",
        "kind": "person_post",
        "needs_session": False,
        "proxy": False,
        "hosts": LINKEDIN_HOSTS,
        "limit": 3,
        "usd_per_run": 0.00005,
        "usd_per_item": 0.00175,
        "fields": {"url": ("linkedinUrl", "shareLinkedinUrl"),
                   "body": ("content",),
                   "date": ("postedAt.date",)},
        "why": "a champion's or exec's own posts, in their words - which is "
               "why `includeReposts` is false: a repost is somebody else's "
               "sentence and quoting it back as theirs is a wrong claim",
    },
    # ---------------------------------------------------------------- 4
    "site_content": {
        "actor": "apify~website-content-crawler",
        "kind": "site_page",
        "needs_session": False,
        "proxy": True,
        "hosts": None,                      # the record's OWN domain only
        "limit": 5,
        # COMPUTE UNITS, NOT EVENTS, AND MEASURED RATHER THAN QUOTED.
        # $0.69316 over 24 accounts in the 2026-09-24 pilot, two of which
        # failed and were billed anyway. It is 72% of the whole per-account
        # bill and the reason all four sources on all 19,612 accounts does
        # not fit in $199: see `docs/RESEARCH-PACK-PILOT-2026-09-24.md`.
        # It varies with the site, so this is this estate's average.
        "usd_per_run": 0.02888,
        "usd_per_item": 0.0,
        "fields": {"url": ("url", "loadedUrl"),
                   "body": ("text", "markdown", "content"),
                   # A crawled page carries no publication date worth
                   # trusting, and `crawledAt` is when WE looked.
                   "date": ()},
        # A PAGE THAT DID NOT LOAD IS NOT EVIDENCE ABOUT THE COMPANY. The
        # crawler returns a row for every URL it was given, and the body of a
        # 404 is the site's own navigation - which reads as ordinary company
        # copy. `providers.apify.evidence_from_items` already drops these;
        # the pack builds facts by a different route and would not have.
        "status_field": "crawl.httpStatusCode",
        "why": "the company's own words on its own site: the one source "
               "that needs no LinkedIn presence at all",
    },
}

#: The profiles a person-level actor may be run for. Named rather than
#: free-text so a pack cannot quietly grow a third person per account,
#: which is the shape that makes a per-account cost unbounded.
PERSON_PROFILES = ("champion", "exec")


def usd_per_account(name, limit=None):
    """The planned dollar cost of one run of `name`, at its own limit."""
    spec = ACTORS[name]
    limit = int(spec["limit"] if limit is None else limit)
    return spec["usd_per_run"] + spec["usd_per_item"] * limit


def planned_cost(name, limit=None):
    """The same number in the spend ledger's integer cents, rounded UP."""
    return max(1, int(math.ceil(usd_per_account(name, limit) * 100)))


def build_input(name, target, limit=None):
    """The actor's own input payload. Read-only in every branch.

    Each shape is the actor's declared input schema, read from its latest
    build on 2026-09-24. They have nothing in common, which is why this is
    per-actor rather than one payload with a few keys swapped.
    """
    spec = ACTORS[name]
    limit = int(limit or spec["limit"])
    if name == "open_roles":
        return {
            # `companyName` FILTERS a search to that company and needs no
            # LinkedIn URL, which is the only reason the slug can come out
            # of this actor rather than having to go into it.
            "companyName": [str(target)],
            "rows": limit,
            # Included in the base rate, and it carries `companyUrl` and
            # `companyWebsite` - the slug and the thing that proves the slug
            # belongs to this record.
            "companyProfile": True,
            # A paid add-on for a recruiter's headline and photo. Off: it is
            # money for a field no fact here reads.
            "enrichCompany": False,
        }
    if name == "company_slug":
        return {"searches": [str(target)]}
    if name in ("company_posts", "person_posts"):
        return {
            "targetUrls": [str(target)],
            "maxPosts": limit,
            "includeReposts": False,
            "includeQuotePosts": True,
            # Each is billed as a separate item at the post rate. Neither is
            # a fact this pack can use.
            "scrapeReactions": False,
            "scrapeComments": False,
        }
    if name == "site_content":
        return {
            "startUrls": [{"url": u} for u in (target if isinstance(target, (list, tuple))
                                               else [target])],
            "maxCrawlPages": limit,
            "maxResults": limit,
            "maxCrawlDepth": 1,
            # The crawler REFUSES a run without one - 400 `invalid-input`,
            # confirmed live on 2026-09-07. No `apifyProxyGroups`, so this is
            # Apify's automatic DATACENTER pool and not residential.
            "proxyConfiguration": {"useApifyProxy": True},
        }
    raise KeyError(name)


def _host(url):
    from urllib.parse import urlparse
    host = (urlparse(str(url or "")).hostname or "").lower().rstrip(".")
    return host[4:] if host.startswith("www.") else host


def is_this_company(row, domain, site_key):
    """Does this row's own website say it belongs to this record?

    The one identity test, used for both the slug and the facts. It reads
    the row's website rather than comparing names, because the name is what
    was ambiguous in the first place. A row with no website field proves
    nothing and is refused: missing evidence is never positive evidence.
    """
    domain = str(domain or "").strip().lower().lstrip("@")
    if domain.startswith("www."):
        domain = domain[4:]
    site = _host((row or {}).get(site_key))
    if not domain or not site:
        return False
    return (site == domain or site.endswith("." + domain)
            or domain.endswith("." + site))


def slug_from_jobs(rows, domain):
    """The company's LinkedIn page URL, taken out of the JOBS actor's rows.

    THE OPERATOR'S QUESTION, ANSWERED IN CODE. `company_posts` needs a
    company LinkedIn URL and the estate holds domains, so the slug has to
    come from somewhere. It comes from here: every job row carries
    `companyUrl` (`https://www.linkedin.com/company/<slug>`) alongside
    `companyWebsite`, the company's own site.

    AND IT IS ONLY ACCEPTED WHEN THOSE TWO AGREE. `companyName` is a text
    filter; a search for "Apex" can return Apex Ltd's jobs and hand back
    Apex Ltd's slug. Buying another company's posts and putting them in
    front of this one is a wrong-company claim, which this repository has
    already shipped once. So a slug is returned only when the row's
    `companyWebsite` is on the record's own domain - the same identity test
    the rest of the system uses - and None otherwise, which the pack reports
    as unaddressable rather than papering over.
    """
    return _slug_from(rows, domain, "companyUrl", "companyWebsite")


def slug_from_companies(rows, domain):
    """The same, from `company_slug`'s rows, which name the fields
    differently. Same identity test, because it is the same question."""
    return _slug_from(rows, domain, "linkedinUrl", "website")


def _slug_from(rows, domain, url_key, site_key):
    domain = str(domain or "").strip().lower().lstrip("@")
    if domain.startswith("www."):
        domain = domain[4:]
    if not domain:
        return None
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        url = str(row.get(url_key) or "").strip()
        if url and is_this_company(row, domain, site_key):
            # `?trk=public_jobs_topcard-org-name` rides along on every one.
            return url.split("?")[0].rstrip("/")
    return None


def cost_of(names):
    """Planned cost for a set of actor runs, in the ledger's cents."""
    return sum(planned_cost(n) for n in names if n in ACTORS)
