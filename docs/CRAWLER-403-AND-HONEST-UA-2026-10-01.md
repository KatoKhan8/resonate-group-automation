# The 403 was the User-Agent, and the claim about robots.txt was false

2026-10-01. Branch `task-honest-crawler-ua`, from `d98c83ce`.

Today's scoped generation produced **0 research rows** for the email candidate
`bigfish.co.uk`. The previous session's recorded claim was:

> the research fetch got HTTP 403 because of the User-Agent, even though
> robots.txt allows the path

**Half of that was right and the stated premise was wrong.** It was never
measured. This is the measurement.

## robots.txt, verbatim

`https://bigfish.co.uk/robots.txt` **answered 403 to our own User-Agent.**
Nothing had read it, so "robots.txt allows the path" was not a finding about
the site - it was an assumption. With a UA the host does serve, the file reads
(200, `Content-Type: text/plain`, 327 bytes, and a `Vary: User-Agent` header
that is itself the admission that the host answers differently per agent):

    # START WPFORMS BLOCK
    # ---------------------------
    User-agent: *
    Disallow: /wp-content/uploads/wpforms/
    # ---------------------------
    # END WPFORMS BLOCK

    # START YOAST BLOCK
    # ---------------------------
    User-agent: *
    Disallow:

    Sitemap: https://bigfish.co.uk/sitemap_index.xml
    # ---------------------------
    # END YOAST BLOCK

There is **no group for our agent**, so the `*` group governs. `/` is allowed
either way. Two separate `*` groups is malformed - RFC 9309 says merge them,
`urllib.robotparser` keeps the LAST one, which here is the permissive
`Disallow:` - so the stricter reading (`/wp-content/uploads/wpforms/` denied)
is the one to assume, and this crawler never requests that path.

`https://thirstcraft.com/robots.txt` reads 200 (Cloudflare in front of WP
Engine):

    User-agent: *
    Disallow: /wp-admin/
    Allow: /wp-admin/admin-ajax.php
    Crawl-delay: 10

    Sitemap: https://thirstcraft.com/sitemap_index.xml

**`Crawl-delay: 10` was parsed by `RobotFileParser` and read by nobody.**

## The experiment: one variable at a time

`https://bigfish.co.uk/`, HTTP/1.1, requests spaced 7-8s, no retries. The
baseline is the exact header set `webfetch.fetch` sends.

| # | one thing changed | status | bytes |
|---|---|---|---|
| V1 | baseline - our UA, `Accept: text/html,application/xhtml+xml`, `Accept-Language: en,*` | **403** | 75193 |
| V2 | UA -> `Python-urllib/3.13` | **200** | 479168 |
| V3 | UA -> `ResonateResearch/1.0 (+https://…/bot)` | **200** | 479168 |
| V4 | UA -> a full Chrome string (diagnostic only, once) | **200** | 479168 |
| V5 | Accept + Accept-Language removed, our UA kept | **403** | 75193 |
| V6 | HTTP/2, our UA | NOT RUN | - |
| V7 | HTTP/2 + full browser header set | NOT RUN | - |
| B1 | `Mozilla/5.0 (compatible; ResonateResearch/1.0; +https://…)` | **403** | 75193 |
| B2 | `Mozilla/5.0 (compatible; ResonateBot/1.0; +company qualification, …)` | **403** | 75193 |
| C1 | `ResonateResearch/1.0 (compatible; +https://…)` - `compatible`, no `Mozilla/5.0` | **200** | 479168 |
| C2 | `Mozilla/5.0 (ResonateResearch/1.0; +https://…)` - `Mozilla/5.0`, no `compatible` | **200** | 479168 |

**V6 and V7 DID NOT RUN.** The local curl is built against Schannel without
HTTP/2 support and refused the option; the headers printed under those labels
were the previous variant's file. **HTTP version is therefore UNTESTED and is
not claimed either way.** It is also not needed: the result already flips on a
header, with the transport held constant.

## The cause

**A static User-Agent deny rule at the host, matching the literal
`Mozilla/5.0 (compatible;`.** Not a WAF challenge, not rate limiting, not the
`Accept` headers, not robots.txt.

- B1 and B2 isolate it from both halves of the old suffix: changing the product
  token, and replacing the prose contact with a real URL, each still 403.
- C1 and C2 isolate the token pair: `compatible` alone is served, `Mozilla/5.0`
  alone is served, the two together are refused. V4 confirms it is not an
  anti-`Mozilla` rule - a browser string is served.
- It is **not a bot-manager challenge.** The body is a 75,193-byte static
  nginx error page whose entire visible text is "403 - Forbidden / Access to
  this page is forbidden." No captcha, no JS challenge, no `cf-ray`, no
  `Server: cloudflare`, no Sucuri/Incapsula/Akamai marker. `Server: nginx` with
  a `Host-Header:` hash and `X-Proxy-Cache-Info: DT:1`.
- It is **not rate limiting.** Every request was single and spaced; the 403s
  returned in ~0.18-0.23s from proxy cache while the 200s took ~1.1-1.6s, which
  is a cached deny page rather than a throttle that would have let the first
  request through.

So: the previous session's conclusion ("the UA") was right, its premise
("robots.txt allows the path", implying the file had been read) was false, and
the mechanism is narrower than "the UA" - it is the declared-bot prefix
specifically. The irony is load-bearing: `Mozilla/5.0 (compatible; <Bot>/1.0;
+<url>)` is the conventional honest-bot form that Googlebot uses, and this host
denies exactly that while serving both a browser and a bare product token.

## What changed, and the argument from the requirement

Operator decision 2c: an honest, identifying UA; respects robots.txt; sane rate
limits; no browser spoofing.

    - Mozilla/5.0 (compatible; ResonateResearch/1.0; +company qualification, respects robots.txt)
    + ResonateResearch/1.0 (+https://resonategroup.co)

The token `Mozilla` is not by itself the violation. Two other things are:

1. **`+company qualification, respects robots.txt` IS NOT A URL.** The `+` in
   that convention introduces a dereferenceable URI an operator can open to
   find out who is reading their site and how to stop it. Prose there
   identifies nobody and is contactable by no one. The old string announced a
   bot while withholding the one affordance that makes announcing it useful -
   and a UA that asserts "respects robots.txt" while the code respected it on
   the first request only was asserting something untrue.
2. **This build already decided it the other way.** `providers.USER_AGENT` is
   `resonate-group-automation/1.0 (+https://resonategroup.co)` and
   `tests/test_wire_contracts.py::test_the_user_agent_names_this_tool_rather_than_a_browser`
   asserts no browser token appears in it. `webfetch` was the one HTTP client
   in the repo that escaped that test. Two conventions for the same decision is
   how the second one drifts.

The measurement is evidence that the honest form is also the form that gets
served. It is not the reason for the shape.

## Three things that were not what they looked like

**1. `respect_robots` covered the FIRST url only.** `research` asks
`robots_allows` about each page it is about to request, and `urllib` then
follows redirects by itself. `_BoundedRedirects` enforced same-domain and a hop
limit and asked robots nothing, so an allowed page that redirected to a
disallowed path was read anyway. The handler now consults robots on every hop;
a refused hop returns `None`, which surfaces the 3xx and classifies `NON_2XX`
rather than looking like a page we read.

**2. The paid fallback asked robots nothing at all.** `src/providers/apify.py`'s
docstring says it is "not a way past a login, a paywall, a CAPTCHA or a robots
restriction" and lists that among the things "the code enforces every line of".
**Nothing in that module reads robots.txt** - not `plan`, not `candidate_urls`,
not `start_run` - and `start_run` sends
`proxyConfiguration: {"useApifyProxy": True}`. The one leg with no robots check
was the one going through rotating proxies, and it is the leg that runs
*because* the free leg came back `BLOCKED`: a site that refuses us was answered
with a harder request. `candidate_urls` also GUESSES paths (`/about`, `/team`,
`/careers`), so robots is the only consent signal available for a page the site
never published a link to. The gate is now in `research.run`, before `spend` is
called, and it fails closed: no allowed candidate means no run and no ledger
entry. It is in `research.py` because `src/providers/*` is off-limits on this
branch - **the provider module itself is still unguarded if called directly.**

**3. Nothing in `DEFAULTS` was a rate limit.** `request_timeout`,
`domain_timeout` and `max_pages` bound how long one read may take and how much
of a site it may touch. **None of them put any gap between two requests**, so a
six-page read arrived as six back-to-back hits, and the robots.txt read was the
one request with no pacing at all. Added: `min_request_interval` (1.0s floor,
per host) and `max_crawl_delay` (10.0s ceiling on what we will honour from a
site), both clamped by `settings()` like every other bound. A stated
`Crawl-delay` is now read and obeyed up to that ceiling; a site that states
none gets `None`, never `0.0`.

Interaction worth knowing: pacing counts against `domain_timeout` (45s).
thirstcraft.com's `Crawl-delay: 10` therefore caps a read of that site at
roughly four pages rather than six. Politeness wins; the wall-clock bound is
not widened to buy pages back.

## What it is worth: measured, read-only

`webfetch.research` run directly against both candidates with the new UA.
Nothing was written to any record, to `work/`, or to the crawl cache.

| domain | outcome | pages | rows after boilerplate | **admitted by `evidence.select`** |
|---|---|---|---|---|
| bigfish.co.uk | HTTP_SUCCESS | 2 | 2 | **2** (both `quality=medium`, `relevance 0.7`) |
| thirstcraft.com | HTTP_SUCCESS | 2 | 2 | **0** (`weak` 0.35 and `unusable` 0.1) |

bigfish.co.uk goes from `BLOCKED` / 0 rows to 2 admissible rows. **thirstcraft.com
crawls fine and yields nothing a prompt may use** - which is the shape this repo
has already recorded once ("rows went 0 -> 2 ... and ADMITTED STAYED 0"): a
successful crawl is not admissible evidence, and the reserve candidate is not
rescued by this fix.

Evidence ids and the facts they rest on are in the session scratchpad, not here.
Both domains have exactly one record in the queue, so a row attaches to a
record; `evidence_id` hashes `record_id`, so an id is only valid for the record
it was minted against.

## Still unproven

- **HTTP/2 and TLS fingerprint**: untested, no HTTP/2 client available here.
- **Whether `bigfish.co.uk`'s rule is the host's default or this site's
  choice.** The `Host-Header:` hash and the error-page shape suggest a shared
  nginx layer, which would mean every site on it denies declared bots. One
  host's deny rule is all that was measured.
- **The repo-wide grep is clean** - `webfetch` and `providers` are the only two
  UA-setting HTTP clients, plus `web/oidc.py` sending `resonate-oidc` to our own
  identity provider. A test now asserts both by import rather than by grep.
