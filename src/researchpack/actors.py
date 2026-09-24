"""Which Apify actors this pack may run, what each costs, and what it reads.

## APIFY RUNS LINKEDIN ONLY. THE SITE IS OURS, AND IT IS FREE

Operator ruling, 2026-09-24, on the pilot's own numbers:
`apify~website-content-crawler` was 72% of the per-account bill - $0.02888
of $0.03987 - and it is the one source this repository already had a free
reader for. It is DELETED from `ACTORS` below rather than disabled, and
`site_content` now comes from `src/researchpack/site.py`, which wraps
`src/webfetch.py`. See `FREE_SOURCES`.

So every entry in `ACTORS` is a LinkedIn actor, and the per-account Apify
bill for this estate is the $0.01098 the three LinkedIn sources and the
opt-in slug resolver cost, not $0.03987.

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

Every actor left here bills PAY_PER_EVENT and this account is on the SCALE
plan at tier SILVER, so the per-event prices are the SILVER rows of each
actor's `eventTieredPricingUsd`, read from `GET /v2/acts/{id}`:

    company_posts / person_posts   start $0.00005 + $0.00175 per post
                                   ($0.001 "no-result" when a target has none)
    open_roles                     start $0.00005 + $0.00110 per job
    company_slug                   start $0.00005 + $0.00350 per company

MEASURED per account over 24 real accounts on 2026-09-24: roles $0.00335,
person posts $0.00265, company posts $0.00260, slug resolver $0.00238 -
**$0.01098 of Apify per account** now that the site crawl is ours, which is
$215 at 19,612 accounts against a $199 budget rather than $781.94. The site
crawl that made up the other $0.02888 is gone; the full arithmetic and the
options are in `docs/RESEARCH-PACK-PILOT-2026-09-24.md`.

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
}

# ------------------------------------------------- 4, AND NOT AN ACTOR
#
# THE WEBSITE CRAWLER IS GONE FROM THIS REGISTRY, BY RULING.
#
# `apify~website-content-crawler` was the fourth entry here until
# 2026-09-24. The pilot measured it at $0.02888 per account - 72% of the
# whole bill, $566 of the $781.94 a month that all four sources on 19,612
# accounts would cost against a $199 budget - while the three LinkedIn
# sources and the slug resolver together are $215. The operator ruled:
# site content comes from our own free crawler, and Apify runs LinkedIn
# only.
#
# It is DELETED rather than flagged off. A registry entry with a price and
# an `enabled: False` beside it is a cost one edit away from returning, and
# `tests/test_researchpack.py` asserts that no entry above names a website
# crawler at all. `src/researchpack/site.py` is where `site_content` now
# comes from and it names no actor, starts no run and writes no ledger row.
FREE_SOURCES = {
    "site_content": {
        "provider": "local_http",           # `src/webfetch.py`
        "kind": "site_page",
        "usd_per_account": 0.0,
        "why": "the company's own words on its own site: the one source "
               "that needs no LinkedIn presence at all, and now the one "
               "source that costs nothing",
    },
}

#: The four sources a pack is built from, however each is fetched. A caller
#: that wants "everything" asks for this rather than for `ACTORS`, which is
#: three LinkedIn actors and an opt-in resolver.
SOURCES = ("open_roles", "company_posts", "person_posts", "site_content")

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
    # There is no `site_content` branch. It is not an Apify actor any more
    # and asking this function to build its input is a caller still holding
    # the old shape, which is worth a KeyError rather than a payload.
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
