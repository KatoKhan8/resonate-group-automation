"""Which Apify actors this pack may run, and what each costs.

## READ-ONLY, AND NO LINKEDIN SESSION

Operator, 2026-09-24: "actors that need no LinkedIn session". Every actor
here reads a PUBLIC surface. None authenticates as a person, none needs a
cookie, and none is a scraper of a logged-in view - which is a scope
decision about what this system is willing to do, not a capability gap.

`needs_session` is carried on every entry and asserted in the tests, so an
actor added later has to answer the question rather than inherit a silence.

## THE INPUT SHAPES ARE NOT THE CRAWLER'S

`providers/apify.start_run` builds `startUrls`/`maxCrawlPages`, which is
the website-content-crawler's input and nothing else's. So each actor
carries its own `build_input`. The RUN LIFECYCLE is shared and imported
from that module rather than copied: start, poll, read the dataset.

## AND THAT MODULE CARRIES A WARNING WORTH REPEATING

`providers/apify.start_run` records that every run it ever started was
rejected before it began - `proxyConfiguration` is required and was
missing - so no Apify scrape in this repository has ever returned
evidence. `proxyConfiguration` is therefore set on every input built here.
It is also why the cassettes in `tests/fixtures/cassettes/` are the only
responses this package has been exercised against.
"""

#: Apify charges per run and per compute unit. These are the PLANNED costs
#: used for the ledger and the per-account total, in the same integer cents
#: the rest of the spend ledger speaks. They are estimates until a live run
#: returns a real charge, and `pack.py` records the planned figure at the
#: moment of the call - which is what `spendledger.record` documents as the
#: honest moment to record an EXPECTED charge.
ACTORS = {
    "company_posts": {
        "actor": "apify~linkedin-company-posts-scraper",
        "kind": "company_post",
        "needs_session": False,
        "cost": 5,
        "limit": 3,
        "why": "the last 3 company posts: what they are saying in public",
    },
    "open_roles": {
        "actor": "apify~job-listings-scraper",
        "kind": "open_role",
        "needs_session": False,
        "cost": 4,
        "limit": 10,
        "why": "open roles: what they are building and where it hurts",
    },
    "person_posts": {
        "actor": "apify~linkedin-profile-posts-scraper",
        "kind": "person_post",
        "needs_session": False,
        "cost": 6,
        "limit": 5,
        "why": "a champion's or exec's own posts, in their words",
    },
}

#: The profiles a person-level actor may be run for. Named rather than
#: free-text so a pack cannot quietly grow a third person per account,
#: which is the shape that makes a per-account cost unbounded.
PERSON_PROFILES = ("champion", "exec")


def build_input(name, target, limit=None):
    """The actor's own input payload. Read-only in every branch."""
    spec = ACTORS[name]
    limit = int(limit or spec["limit"])
    common = {
        # SEE THE MODULE DOCSTRING. Without this the run is rejected with
        # 400 `invalid-input` before it starts, which is how this provider
        # spent months appearing to work and returning nothing.
        "proxyConfiguration": {"useApifyProxy": True},
        "maxItems": limit,
    }
    if name == "company_posts":
        return dict(common, companyUrl=target, maxPosts=limit)
    if name == "open_roles":
        return dict(common, companyDomain=target, maxJobs=limit)
    if name == "person_posts":
        return dict(common, profileUrl=target, maxPosts=limit)
    raise KeyError(name)


def cost_of(names):
    """Planned cost for a set of actor runs, in the ledger's cents."""
    return sum(ACTORS[n]["cost"] for n in names if n in ACTORS)
