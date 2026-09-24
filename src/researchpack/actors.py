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
        "actor": "harvestapi~linkedin-company-posts",
        "kind": "company_post",
        "needs_session": False,
        "cost": 5,
        "limit": 3,
        "why": "the last 3 company posts: what they are saying in public",
    },
    "open_roles": {
        "actor": "fantastic-jobs~career-site-job-listing-api",
        "kind": "open_role",
        "needs_session": False,
        "cost": 4,
        "limit": 10,
        "why": "open roles: what they are building and where it hurts",
    },
    "person_posts": {
        "actor": "harvestapi~linkedin-profile-posts",
        "kind": "person_post",
        "needs_session": False,
        "cost": 6,
        "limit": 5,
        "why": "a champion's or exec's own posts, in their words",
    },
}

#: How far back a post may be and still be a hook. From the actor's own
#: enum. Six months because a quarter is too tight for a company that
#: posts rarely and a year is long enough to quote something stale.
POSTED_LIMIT = "6months"

#: The profiles a person-level actor may be run for. Named rather than
#: free-text so a pack cannot quietly grow a third person per account,
#: which is the shape that makes a per-account cost unbounded.
PERSON_PROFILES = ("champion", "exec")


def build_input(name, target, limit=None):
    """The actor's own input payload, in ITS OWN field names.

    ## THESE WERE GUESSED ONCE AND EVERY RUN 404ed

    The first version of this module carried `apify~job-listings-scraper`,
    `apify~linkedin-company-posts-scraper` and
    `apify~linkedin-profile-posts-scraper`, with inputs called `companyUrl`,
    `companyDomain` and `profileUrl`. **None of those actors exists.** Three
    live runs on 2026-09-24 came back 404 from `POST /acts/<id>/runs`, and
    `GET /acts/<id>` confirms it: 404 for all three, 200 for
    `apify~website-content-crawler`, which is the one somebody had actually
    used. Plausible is not verified.

    The ids and the field names below are read from the Apify store and
    from each actor's own published input schema. `tests/test_researchpack.py`
    pins them, and `scripts/check_researchpack_actors.py` re-asks the API.

    ## AND `proxyConfiguration` IS NOT UNIVERSAL

    `providers/apify.start_run` requires it because the website content
    crawler does. These three declare NO required fields and the two
    LinkedIn ones are "No Cookies" actors, so sending it is at best ignored.
    It is passed only where an actor asks for it, which is currently none of
    them - the blanket version of this rule was inherited from the crawler
    and was never true here.
    """
    spec = ACTORS[name]
    limit = int(limit or spec["limit"])
    if name in ("company_posts", "person_posts"):
        # A LINKEDIN COMPANY URL for the first, a profile url for the
        # second. See `NEEDS_COMPANY_LINKEDIN`.
        #
        # `postedLimit` IS NOT OPTIONAL IN PRACTICE. The 2026-09-24 capture
        # ran without it and came back with posts from FEBRUARY 2020 - the
        # actor returns a profile's history, and a six-year-old post is not
        # a hook, it is an embarrassment waiting to be quoted. "6months" is
        # from the actor's own enum (`any`, `1h`, `24h`, `week`, `month`,
        # `3months`, `6months`, `year`), read off the published schema
        # rather than guessed, which is how `timeRange` was got wrong.
        return {"targetUrls": [target], "maxPosts": limit,
                "postedLimit": POSTED_LIMIT,
                "scrapeReactions": False, "scrapeComments": False}
    if name == "open_roles":
        # "6m", NOT "Last 30 days". The actor answers 400 invalid-input
        # for anything else: allowed values are "1h", "24h", "7d", "6m",
        # read off the live API on 2026-09-24 after guessing wrong. Six
        # months because a role posted last week is rare and a role posted
        # this quarter is still a real signal about what they are building.
        return {"domainFilter": [target], "limit": limit,
                "timeRange": "6m", "includeCompanyDetails": False}
    raise KeyError(name)


#: `company_posts` CANNOT BE TARGETED FROM WHAT WE STORE. Measured
#: 2026-09-24 across the whole record store: 1,543 records carry ZERO
#: company-level LinkedIn urls, and this actor takes LinkedIn company urls
#: in `targetUrls`. 1,316 CONTACT-level profile urls do exist, which is why
#: `person_posts` and `open_roles` can run today and this one cannot.
#:
#: It is left in the registry rather than deleted because the actor is real
#: and the gap is in our data, not in the adapter. Closing it means either
#: resolving a company page per account - another paid lookup - or reading
#: the company from a contact profile.
NEEDS_COMPANY_LINKEDIN = ("company_posts",)


def targetable(name, record=None):
    """Can this actor be aimed with what we hold for that account?"""
    if name not in NEEDS_COMPANY_LINKEDIN:
        return True
    record = record or {}
    return bool(record.get("linkedin") or record.get("company_linkedin"))


def cost_of(names):
    """Planned cost for a set of actor runs, in the ledger's cents."""
    return sum(ACTORS[n]["cost"] for n in names if n in ACTORS)
