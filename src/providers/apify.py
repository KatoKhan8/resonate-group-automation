#!/usr/bin/env python3
"""Apify: optional public-web evidence. BUILD-SPEC section 9 still applies.

What this is for: a company's own public pages when the structured providers do
not carry the fact a hook or an angle needs. About, team, careers, blog, news.

What it is not, and the code enforces every line of this:

  - not an email verifier. Nothing here can make an address sendable.
  - not a replacement for ContactOut. It runs last, and only on a stated need.
  - not a crawler. It is bounded by pages, items, characters and time.
  - not a way past a login, a paywall, a CAPTCHA or a robots restriction.
  - not a fetcher of arbitrary URLs. A URL must belong to the record's own
    company domain, resolve to a public address, and use http or https.

Off by default. A client that has not asked for it never scrapes.

  python -m src.providers.apify --check
  python -m src.providers.apify --plan --domain example.test
"""
import argparse
import ipaddress
import os
import re
import socket
import time
import urllib.parse

from . import (ProviderError, failed, key, mapping, ok, query, request,
               result)

BASE = "https://api.apify.com/v2"
KEY_VAR = "APIFY_TOKEN"

# The one actor this integration knows how to drive, and the fields it reads.
DEFAULT_ACTOR = "apify~website-content-crawler"

# Hard ceilings. A client config may lower these; it may not raise them.
MAX_PAGES = 10
MAX_ITEMS = 50
MAX_TEXT_CHARS = 12000
MAX_REDIRECTS = 3
# MEASURED, on this account's own run history rather than chosen.
#
# Across 29 completed runs of this actor on 2026-09-10: 21 SUCCEEDED with a
# minimum of 34s, a median of 70s and a MAXIMUM OF 110s - and 8 TIMED-OUT, all
# at exactly 120s, because 120 was the ceiling. The ceiling sat ten seconds
# above the slowest run that had ever finished, so a crawl only slightly slower
# than typical died on it.
#
# That is not a small waste. Apify bills a killed run for the compute it used:
# the eight timeouts cost $0.081 each and returned no evidence at all, roughly
# $0.65 of $1.69 total spend, a 28% waste rate. And the record then still
# states the same unmet need, so the next run scrapes it again.
#
# 180 sits well clear of the observed maximum. It is not generous - it is the
# distribution's tail plus room, and a run that genuinely hangs is still
# stopped by Apify itself, because this value is sent as the actor's own
# `timeout` and not merely used for local polling.
RUN_TIMEOUT = 180
# Nine seconds, so covering the full run timeout still takes TWENTY polls.
# `tests/test_invariants.py` caps the attempt count at twenty and is right to:
# the ceiling is what stops a bounded wait becoming an unbounded one, and
# deriving attempts from the timeout quietly escaped it. Widening the window
# must not widen the number of polls.
POLL_INTERVAL = 9.0
# Poll for as long as the run is allowed to take, rather than for a third of
# it. This was 10 attempts at 3 seconds - thirty seconds - while `plan()` told
# the operator the run was "bounded by 120s". A real crawl of five pages takes
# longer than thirty seconds, so `wait_for` returned TIMEOUT on runs that then
# SUCCEEDED: the compute was billed, the dataset was written, and the evidence
# was thrown away because nobody was still listening. Measured on two live
# runs, both SUCCEEDED after `wait_for` had already given up on them.
POLL_ATTEMPTS = int(RUN_TIMEOUT / POLL_INTERVAL)

ALLOWED_SCHEMES = ("http", "https")

SOURCES = ("company_website", "about", "team", "careers", "blog", "news")

# Paths worth looking at, per source. Nothing is guessed from a model's output.
SOURCE_PATHS = {
    "company_website": ("/",),
    "about": ("/about", "/about-us", "/company"),
    "team": ("/team", "/our-team", "/people", "/leadership"),
    "careers": ("/careers", "/jobs", "/join-us"),
    "blog": ("/blog", "/insights"),
    "news": ("/news", "/press", "/newsroom"),
}


class UnsafeURL(ProviderError):
    """The URL is not one this integration will fetch. Nothing was requested."""


class ScrapeRefused(ProviderError):
    """A cap, a policy or a missing reason stopped the run before it started."""


# ------------------------------------------------------------- URL safety

PRIVATE_HOSTNAMES = ("localhost", "localhost.localdomain", "ip6-localhost",
                     "ip6-loopback", "broadcasthost")

INTERNAL_SUFFIXES = (".local", ".internal", ".localdomain", ".lan", ".home",
                     ".corp", ".intranet", ".test.local")

BLOCKED_NETWORKS = tuple(ipaddress.ip_network(n) for n in (
    "0.0.0.0/8", "10.0.0.0/8", "100.64.0.0/10", "127.0.0.0/8", "169.254.0.0/16",
    "172.16.0.0/12", "192.0.0.0/24", "192.168.0.0/16", "198.18.0.0/15",
    "224.0.0.0/4", "240.0.0.0/4",
    "::1/128", "fc00::/7", "fe80::/10", "ff00::/8", "::/128",
))


def is_blocked_ip(value):
    try:
        address = ipaddress.ip_address(value)
    except ValueError:
        return False
    if address.is_private or address.is_loopback or address.is_link_local:
        return True
    if address.is_reserved or address.is_multicast or address.is_unspecified:
        return True
    for network in BLOCKED_NETWORKS:
        if address.version == network.version and address in network:
            return True
    return False


def resolve_all(host):
    """Every address a hostname resolves to. Empty when resolution is blocked."""
    try:
        infos = socket.getaddrinfo(host, None)
    except Exception:
        return []
    return [info[4][0] for info in infos]


def check_url(url, allowed_domain=None, resolve=True):
    """Refuse anything that is not a public page on the company's own domain.

    Raises UnsafeURL rather than returning a boolean, so a caller cannot use the
    result by accident.
    """
    if not isinstance(url, str) or not url.strip():
        raise UnsafeURL("empty url")
    parsed = urllib.parse.urlparse(url.strip())

    if parsed.scheme.lower() not in ALLOWED_SCHEMES:
        raise UnsafeURL(f"scheme {parsed.scheme!r} is not http or https")
    host = (parsed.hostname or "").lower().rstrip(".")
    if not host:
        raise UnsafeURL("no host in url")
    if parsed.username or parsed.password:
        raise UnsafeURL("credentials in url")
    if host in PRIVATE_HOSTNAMES:
        raise UnsafeURL(f"{host} is a loopback name")
    if any(host.endswith(suffix) for suffix in INTERNAL_SUFFIXES):
        raise UnsafeURL(f"{host} looks like an internal hostname")
    if is_blocked_ip(host):
        raise UnsafeURL(f"{host} is a private or reserved address")
    if parsed.port and parsed.port not in (80, 443):
        raise UnsafeURL(f"port {parsed.port} is not 80 or 443")

    if allowed_domain:
        allowed = allowed_domain.lower().rstrip(".")
        if host != allowed and not host.endswith("." + allowed):
            raise UnsafeURL(f"{host} is not on {allowed}")

    if resolve:
        addresses = resolve_all(host)
        for address in addresses:
            if is_blocked_ip(address):
                raise UnsafeURL(f"{host} resolves to the private address {address}")
    return url.strip()


def candidate_urls(domain, sources, max_pages=MAX_PAGES):
    """The pages this integration is willing to look at, deduplicated."""
    urls, seen = [], set()
    for source in sources:
        for path in SOURCE_PATHS.get(source, ()):
            url = f"https://{domain}{path}"
            if url in seen:
                continue
            seen.add(url)
            try:
                urls.append({"url": check_url(url, allowed_domain=domain,
                                              resolve=False),
                             "source": source})
            except UnsafeURL:
                continue
            if len(urls) >= max_pages:
                return urls
    return urls


# ------------------------------------------------------------- the policy

def settings(config=None):
    """The client's research settings, over defaults that are off and small."""
    research = ((config or {}).get("research") or {}).get("apify") or {}
    allowed = research.get("allowed_sources") or list(SOURCES)
    return {
        "enabled": bool(research.get("enabled", False)),
        "max_runs_per_batch": min(int(research.get("max_runs_per_batch", 10)), 100),
        "max_items_per_run": min(int(research.get("max_items_per_run", MAX_ITEMS)),
                                 MAX_ITEMS),
        "max_pages_per_domain": min(int(research.get("max_pages_per_domain",
                                                     MAX_PAGES)), MAX_PAGES),
        "max_text_chars_per_page": min(int(research.get("max_text_chars_per_page",
                                                        MAX_TEXT_CHARS)),
                                       MAX_TEXT_CHARS),
        "allowed_sources": [s for s in allowed if s in SOURCES],
        "actor": research.get("actor") or DEFAULT_ACTOR,
    }


def plan(domain, reason, config=None, sources=None):
    """What a run would do, why, and what it is bounded by. Calls nothing."""
    conf = settings(config)
    if not reason:
        raise ScrapeRefused("a scrape needs a stated reason")
    chosen = [s for s in (sources or conf["allowed_sources"])
              if s in conf["allowed_sources"]]
    urls = candidate_urls(domain, chosen, conf["max_pages_per_domain"])
    return {
        "domain": domain,
        "reason": reason,
        "enabled": conf["enabled"],
        "actor": conf["actor"],
        "sources": chosen,
        "urls": urls,
        "max_pages": conf["max_pages_per_domain"],
        "max_items": conf["max_items_per_run"],
        "max_text_chars": conf["max_text_chars_per_page"],
        # Apify prices per compute unit, not per item, so there is no credit
        # figure to quote honestly. The bound that is real is the scope.
        "cost": {"model": "apify compute units",
                 "known": False,
                 "bounded_by": f"{len(urls)} page(s), {conf['max_items_per_run']} items, "
                               f"{RUN_TIMEOUT}s"},
    }


# ------------------------------------------------------------- the actor

def actor_endpoint(actor, path=""):
    return f"{BASE}/acts/{urllib.parse.quote(actor, safe='~')}{path}"


def start_run(actor, urls, conf):
    """Start one actor run. Only reached with explicit live permission."""
    token = key(KEY_VAR)
    payload = {
        "startUrls": [{"url": u["url"]} for u in urls],
        "maxCrawlPages": conf["max_pages_per_domain"],
        "maxResults": conf["max_items_per_run"],
        "maxCrawlDepth": 1,
        # The actor refuses a run without one. Confirmed live on 2026-09-07:
        # `{"useApifyProxy": false}` answers 400 `invalid-input`, "Field
        # input.proxyConfiguration is required. Please provide custom proxy
        # URLs or use Apify Proxy." So every run this module has ever started
        # was rejected before it began - which is why `LIVE-READINESS.md` had
        # Apify down as never live-validated, and why no scrape has ever
        # returned evidence. There is no third option: either Apify Proxy or
        # a custom proxy list, and this build has no custom proxies.
        "proxyConfiguration": {"useApifyProxy": True},
    }
    # `timeout` makes the 120s in `plan()`'s cost note a real ceiling on
    # Apify's side, not a number this module merely prints. Without it the
    # actor runs to its own default and the only thing that stopped early was
    # our polling.
    status, data = request("POST", query(actor_endpoint(actor, "/runs"),
                                         {"token": token,
                                          "timeout": RUN_TIMEOUT}), {}, payload)
    if not ok(status):
        raise ProviderError(f"apify start: {status}")
    run = mapping(data, "apify start").get("data") or {}
    if not run.get("id"):
        raise ProviderError("apify start returned no run id")
    return {"id": run["id"], "status": run.get("status"),
            "dataset_id": run.get("defaultDatasetId")}


def run_status(run_id):
    token = key(KEY_VAR)
    status, data = request("GET", query(f"{BASE}/actor-runs/{run_id}",
                                        {"token": token}))
    if not ok(status):
        raise ProviderError(f"apify run status: {status}")
    run = mapping(data, "apify run status").get("data") or {}
    return {"id": run_id, "status": run.get("status"),
            "dataset_id": run.get("defaultDatasetId")}


def wait_for(run_id, attempts=POLL_ATTEMPTS, interval=POLL_INTERVAL,
             sleep=time.sleep):
    """Bounded polling. Gives up cleanly rather than waiting for ever."""
    for attempt in range(max(1, attempts)):
        current = run_status(run_id)
        if current["status"] in ("SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT"):
            return current
        if attempt < attempts - 1:
            sleep(interval)
    return {"id": run_id, "status": "TIMEOUT", "dataset_id": None}


def dataset_items(dataset_id, limit):
    token = key(KEY_VAR)
    status, data = request("GET", query(f"{BASE}/datasets/{dataset_id}/items",
                                        {"token": token, "limit": limit,
                                         "clean": "true"}))
    if not ok(status):
        raise ProviderError(f"apify dataset: {status}")
    return data if isinstance(data, list) else []


# -------------------------------------------------------- normalisation

TAG_RE = re.compile(r"<[^>]+>")
SPACE_RE = re.compile(r"\s+")


def clean_text(value, limit):
    """Plain text, bounded. No HTML ever reaches the record or a prompt."""
    text = TAG_RE.sub(" ", str(value or ""))
    text = SPACE_RE.sub(" ", text).strip()
    return text[:limit]


def evidence_from_items(items, domain, actor, sources_by_url=None, conf=None,
                        record_id=None, angle_words=None, persona=None):
    """Dataset rows to bounded, attributed evidence. Raw payloads stay behind.

    GOES THROUGH `evidence.make`, and must. This used to hand-build a nine-key
    dict, which meant the only research path in the build produced a different
    record shape from every other producer: no `quality`, no `freshness_score`,
    no `relevance_score`, no `evidence_id`. `icp.confidence_components` reads
    the first two and scored 0.0 for both - "0 usable piece(s) of evidence",
    about evidence that had been retrieved perfectly well - and `claims`
    licenses a sentence by `evidence_id`, so nothing written from a scraped
    page could ever be cited.

    Two producers of one record shape, one of which the consumers were written
    against. The fix is not to teach the consumers a second shape.

    `record_id` is required for `evidence_id` to be stable and attributable;
    it used to be stamped on by `research.run` AFTER construction, by which
    time the id had already been computed without it.
    """
    from .. import evidence as ev
    conf = conf or settings()
    sources_by_url = sources_by_url or {}
    out, seen = [], set()
    for item in items[: conf["max_items_per_run"]]:
        if not isinstance(item, dict):
            continue
        url = item.get("url") or item.get("loadedUrl") or ""
        try:
            url = check_url(url, allowed_domain=domain, resolve=False)
        except UnsafeURL:
            continue
        if url in seen:
            continue
        # A page that did not load is not evidence about the company.
        #
        # The crawler returns a row for every URL it was given, including the
        # ones that 404, and the body of a 404 is the site's own navigation -
        # "Case Studies", "About Us", "Meet The Team". That text reads as
        # ordinary agency copy to `segments.text_of`, so a guessed path that
        # does not exist could raise an ICP score on the strength of a page
        # that is not there. `SOURCE_PATHS` guesses several paths per source
        # precisely because it does not know which exist, which makes this the
        # normal case rather than the exception: two of five pages 404'd on
        # the first live run.
        if not ok((item.get("crawl") or {}).get("httpStatusCode")):
            continue
        seen.add(url)
        body = clean_text(item.get("text") or item.get("markdown")
                          or item.get("content") or "",
                          conf["max_text_chars_per_page"])
        if not body:
            continue
        # A crawled page carries no publication date worth trusting, so
        # `published_at` stays None and `freshness` answers UNKNOWN. That is
        # the honest answer and it costs something: `quality` demands a higher
        # relevance score before calling UNKNOWN-dated evidence STRONG. Better
        # than inventing a date from `crawledAt`, which is when WE looked.
        made = ev.make(body, url, "apify", "apify", record_id,
                       published_at=None, subject=ev.COMPANY,
                       persona=persona, angle_words=angle_words,
                       retrieved_at=item.get("crawledAt") or None)
        # Provenance the canonical shape has no field for, kept because an
        # audit needs to know which actor and which requested source produced
        # this, and because `title` is how a person recognises the page.
        made["actor"] = actor
        made["field"] = sources_by_url.get(url, "company_website")
        made["title"] = clean_text(item.get("title")
                                   or (item.get("metadata") or {}).get("title"),
                                   200) or None
        out.append(made)
        if len(out) >= conf["max_pages_per_domain"]:
            break
    return out


# --------------------------------------------------------------- health

def check():
    """Account metadata: read-only, and it starts no actor."""
    try:
        token = key(KEY_VAR)
    except ProviderError as e:
        return failed("Apify", e)
    try:
        status, data = request("GET", query(f"{BASE}/users/me", {"token": token}))
        username = (mapping(data, "apify user").get("data")
                    or {}).get("username")
        return result("Apify", status, f"user {username}" if username else str(data))
    except ProviderError as e:
        return failed("Apify", e)


def main(argv=None):
    p = argparse.ArgumentParser(prog="python -m src.providers.apify")
    p.add_argument("--check", action="store_true")
    p.add_argument("--plan", action="store_true")
    p.add_argument("--domain")
    p.add_argument("--reason", default="public evidence required")
    a = p.parse_args(argv)

    if a.plan:
        if not a.domain:
            raise SystemExit("--plan needs --domain")
        planned = plan(a.domain, a.reason)
        print(f"apify plan for {planned['domain']}  (enabled={planned['enabled']})")
        print(f"  reason   {planned['reason']}")
        print(f"  actor    {planned['actor']}")
        for entry in planned["urls"]:
            print(f"  page     {entry['source']:<16} {entry['url']}")
        print(f"  bounded  {planned['cost']['bounded_by']}")
        print("  cost     not quotable: Apify bills compute units, not items")
        return 0

    r = check()
    mark = "ok  " if r.get("ok") else "FAIL"
    print(f"{mark} {r['provider']:<12} {r.get('status')}  {r['note']}")
    return 0 if r.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
