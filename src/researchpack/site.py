"""`site_content` comes from OUR OWN crawler. Apify runs LinkedIn only.

## THE RULING, AND THE MEASUREMENT BEHIND IT

Operator, 2026-09-24, after the pilot in `docs/RESEARCH-PACK-PILOT-2026-09-24.md`
measured `apify~website-content-crawler` at **$0.02888 per account - 72% of
the whole per-account bill** and $566 of the $781.94 a month that all four
sources on 19,612 accounts would cost against a $199 budget. The three
LinkedIn sources plus the slug resolver are $215 on the same estate; the
site crawl alone is more than twice that.

`src/webfetch.py` reads the same pages for the price of a socket, and it
already existed: `enrich` costs `webfetch-crawl` at 0 credits and
`research._from_the_site_itself` already prefers it and falls back to Apify
only for the sites that genuinely defeat it. The pack was paying for the
fallback on every account without ever trying the free layer.

So this module is not a new crawler. It is the pack consuming the one this
repository already has, and `actors.ACTORS` no longer carries a website
actor at all - which is the ruling made unrepresentable rather than merely
documented.

## WHAT IT REFUSES TO PRETEND

`webfetch` classifies rather than guesses: `JS_RENDERING_REQUIRED` for a
page `urllib` cannot execute, `BLOCKED` for robots or a 403, `NON_2XX`,
`TIMEOUT`, `HTTP_INSUFFICIENT` for a site that answered and says too little.
Every one of those is carried out of here as the outcome and reported as
UNCOVERED with its reason. None of them silently becomes an empty pack, and
none of them is now a reason to spend: falling back to the paid crawler is
the decision the ruling took away.

## AND THE IDENTITY QUESTION IS ASKED HERE TOO

`actors.is_this_company` guards the LinkedIn sources because `companyName`
is a text filter that returned 50 rows of somebody else out of 71. A site
crawl cannot make that mistake the same way - `webfetch.same_domain` bounds
every fetch to the record's own domain - but "cannot" is what was said about
the job rows. The host of every retained page is checked against the
record's domain HERE, at the point the fact is made, so the guarantee is one
this module proves rather than one it inherits.
"""
from .. import webfetch
from . import facts

#: What the pack calls this source. Not in `actors.ACTORS`: nothing here
#: starts an Apify run, nothing here is billed, and a registry of "which
#: Apify actors this pack may run" is the wrong place for a free HTTP read.
NAME = "site_content"

KIND = "site_page"

#: `webfetch` is free, so there is no ledger row and no dollars. It is not
#: costless - it spends requests and wall-clock, and `webfetch.research`
#: reports both - but nothing it does can reach a spend ceiling.
PROVIDER = "local_http"


def _host(url):
    from urllib.parse import urlparse
    host = (urlparse(str(url or "")).hostname or "").lower().rstrip(".")
    return host[4:] if host.startswith("www.") else host


def on_this_domain(url, domain):
    """The same question `actors.is_this_company` asks, for a page.

    Fail-closed on a missing domain or a missing host, for the same reason:
    missing evidence is never positive evidence.
    """
    domain = str(domain or "").strip().lower().lstrip("@")
    if domain.startswith("www."):
        domain = domain[4:]
    host = _host(url)
    if not domain or not host:
        return False
    return host == domain or host.endswith("." + domain)


def research(domain, config=None, now=None, crawler=None):
    """Read one company's own site, free, and make `site_page` facts.

    Returns `(facts, outcome)`. `outcome` is `webfetch`'s own report - the
    classification, the pages kept, the requests and the seconds - so a
    caller can say WHY a site is uncovered rather than only that it is.

    `crawler` is the seam a test drives. It is the same signature
    `webfetch.research` has, because a test that drives a different shape
    proves something about the double.
    """
    domain = str(domain or "").strip().lower().lstrip("@")
    if not domain:
        raise ValueError("a site read needs a domain")
    result = (crawler or webfetch.research)(domain, config=config, now=now) or {}
    made, off_domain = [], 0
    for page in result.get("pages") or []:
        url = (page or {}).get("source_url")
        if not on_this_domain(url, domain):
            # Cannot happen through `webfetch.same_domain` today. Counted
            # rather than assumed, so if it ever does the number says so
            # instead of the fact going out under this company's name.
            off_domain += 1
            continue
        try:
            made.append(facts.make(
                KIND, url,
                # A CRAWLED PAGE CARRIES NO PUBLICATION DATE WORTH TRUSTING.
                # `retrieved_at` is when WE looked, and passing it here would
                # make every site fact read as published today.
                None,
                page.get("fact"),
                extra={"actor": PROVIDER,
                       "field": page.get("field"),
                       "http_status": page.get("http_status")}))
        except facts.UnusableFact:
            # A page with no readable prose supports no claim. Dropped, and
            # the outcome below still says the crawl itself succeeded.
            continue
    outcome = {"outcome": result.get("outcome"),
               "stats": result.get("stats") or {},
               "retrieved_at": result.get("retrieved_at"),
               "pages_kept": len((result.get("pages") or [])),
               "facts": len(made),
               "off_domain_pages_dropped": off_domain,
               "provider": PROVIDER,
               "usd": 0.0}
    return made, outcome
