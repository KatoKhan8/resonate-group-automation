"""Read a company's own website, for free, inside strict bounds.

Apify costs compute units this system is never told the price of. A company's
homepage costs a socket. So the waterfall reads the site directly first and
falls back to a paid crawl only for the sites that genuinely defeat this.

Three things this module refuses to do, because each of them turns a free
layer into a liability:

**It never pretends.** A page that needed JavaScript, answered 403, timed out
or returned a 404 is classified as exactly that. `urllib` cannot execute
JavaScript, so a single-page application returns a shell with no prose, and
scoring a company on that shell would be inventing evidence. `JS_RENDERING_REQUIRED`
is a real answer that routes the account onward, not a failure to hide.

**It never wanders.** Only the company's own domain, only pages the site
itself links to or that a sitemap declares, only `text/html`, and a hard
ceiling on pages, bytes, redirects and wall-clock. A crawler that follows
what it finds is how a five-page read becomes a calendar trap.

**It never guesses a URL into evidence.** `research` used to hand Apify a list
of paths it hoped existed - `/about`, `/about-us`, `/company` - and two of
five 404'd on the first live run, whose navigation text was then kept as
though the page were real. Here the homepage is fetched, its own links are
read, and only pages that answered 200 with usable prose are retained.
"""
import datetime
import hashlib
import html.parser
import io
import re
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser

# ------------------------------------------------------------- outcomes

HTTP_SUCCESS = "HTTP_SUCCESS"
HTTP_INSUFFICIENT = "HTTP_INSUFFICIENT"
JS_RENDERING_REQUIRED = "JS_RENDERING_REQUIRED"
BLOCKED = "BLOCKED"
TIMEOUT = "TIMEOUT"
NON_2XX = "NON_2XX"
RESEARCH_FAILED = "RESEARCH_FAILED"

OUTCOMES = (HTTP_SUCCESS, HTTP_INSUFFICIENT, JS_RENDERING_REQUIRED, BLOCKED,
            TIMEOUT, NON_2XX, RESEARCH_FAILED)

# Outcomes that leave a paid fallback worth trying. A site that answered
# perfectly well and simply says little is not one of them: paying Apify to
# read the same short page again buys nothing.
FALLBACK_WORTHY = (JS_RENDERING_REQUIRED, BLOCKED, TIMEOUT, RESEARCH_FAILED)

# WHAT THIS STRING IS FOR, and why it is not the conventional bot form.
#
# `Mozilla/5.0 (compatible; <Bot>/1.0; +<url>)` is the conventional honest-bot
# shape and Googlebot uses it, so the token `Mozilla` is not itself a lie. Two
# things made the old string wrong anyway:
#
# `+company qualification, respects robots.txt` IS NOT A URL. The `+` prefix in
# that convention introduces a dereferenceable URI an operator can open to find
# out who is reading their site and how to make it stop. Prose there identifies
# nobody and is contactable by no one, so the string announced a bot without
# offering the one affordance that makes announcing it useful.
#
# And this build already decided the question the other way. `providers.USER_AGENT`
# is `resonate-group-automation/1.0 (+https://resonategroup.co)` and
# `tests/test_wire_contracts.py` asserts it contains no browser token at all.
# `webfetch` was the one HTTP client in the repo that escaped that test.
#
# MEASURED 2026-10-01 against bigfish.co.uk, one variable at a time: the host
# denies `Mozilla/5.0 (compatible;` with a 403 (its robots.txt included) and
# serves 200 to a bare product token plus a `+https://` URL. `compatible`
# without `Mozilla/5.0`, and `Mozilla/5.0` without `compatible`, both answer
# 200 - so the deny rule matches the declared-bot form specifically. That is a
# measurement of one host's rule, not the reason for this shape; the reason is
# the two paragraphs above. It is recorded because it is the evidence that the
# honest form is also the one that gets served.
USER_AGENT = "ResonateResearch/1.0 (+https://resonategroup.co)"

DEFAULTS = {
    "max_pages": 6,
    "max_bytes_per_page": 512 * 1024,
    "request_timeout": 10.0,
    "domain_timeout": 45.0,
    "max_redirects": 3,
    "retries": 1,
    "min_useful_chars": 400,
    "max_text_chars_per_page": 8000,
    "respect_robots": True,
    # Pacing, per host, applied to every request this module makes including
    # the robots.txt read itself. `min_request_interval` is the floor we apply
    # whatever the site says; `max_crawl_delay` is the ceiling we will honour
    # from a robots.txt `Crawl-delay`, so a site asking for 3600 cannot turn one
    # company into an all-day job. thirstcraft.com declares `Crawl-delay: 10`
    # and nothing in this module read it before 2026-10-01.
    "min_request_interval": 1.0,
    "max_crawl_delay": 10.0,
}

# Pages worth having, in the order they are worth having them. Matched against
# a link the site itself published, never requested blind.
WANTED = (
    ("about", ("about", "about-us", "who-we-are", "our-story", "company")),
    ("services", ("services", "what-we-do", "solutions", "expertise",
                  "capabilities", "offer")),
    ("work", ("work", "case-studies", "cases", "clients", "customers",
              "portfolio", "projects")),
    ("team", ("team", "our-team", "people", "leadership")),
    ("industries", ("industries", "sectors", "markets")),
)


def settings(config=None):
    """Bounds, over defaults that are small."""
    given = ((config or {}).get("research") or {}).get("local_http") or {}
    out = dict(DEFAULTS)
    for key, default in DEFAULTS.items():
        if key not in given:
            continue
        value = given[key]
        if isinstance(default, bool):
            out[key] = bool(value)
        elif isinstance(default, int):
            out[key] = max(0, min(int(value), default * 4))
        else:
            out[key] = max(0.0, min(float(value), default * 4))
    return out


# --------------------------------------------------------------- parsing

class _Links(html.parser.HTMLParser):
    """Every href the page declares, in document order."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.hrefs = []

    def handle_starttag(self, tag, attrs):
        if tag != "a":
            return
        for name, value in attrs:
            if name == "href" and value:
                self.hrefs.append(value.strip())


class _Text(html.parser.HTMLParser):
    """Readable text, with script, style and template noise dropped."""

    SKIP = {"script", "style", "noscript", "svg", "canvas", "template",
            "iframe", "head"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self._skip += 1

    def handle_endtag(self, tag):
        if tag in self.SKIP and self._skip:
            self._skip -= 1

    def handle_data(self, data):
        if self._skip:
            return
        text = data.strip()
        if text:
            self.parts.append(text)


def readable_text(markup, limit=None):
    """Prose only. Repeated lines collapse, because a nav bar is not evidence."""
    parser = _Text()
    try:
        parser.feed(markup)
    except Exception:                       # malformed markup is common
        pass
    seen, kept = set(), []
    for part in parser.parts:
        key = part.lower()
        if key in seen or len(part) < 2:
            continue
        seen.add(key)
        kept.append(part)
    text = re.sub(r"\s+", " ", " ".join(kept)).strip()
    return text[:limit] if limit else text


def script_weight(markup):
    """How much of the document is script. High plus no prose means an app."""
    if not markup:
        return 0.0
    scripts = sum(len(m) for m in re.findall(r"(?is)<script\b.*?</script>", markup))
    return scripts / float(len(markup))


def looks_like_an_app(markup, text, conf):
    """A shell served to a browser that was expected to render it.

    Not a guess dressed up: it asks whether the document is mostly script and
    carries almost no prose, which is what a single-page application looks
    like to something that cannot run JavaScript.
    """
    if len(text) >= conf["min_useful_chars"]:
        return False
    return script_weight(markup) > 0.30 or bool(
        re.search(r'(?i)<div[^>]+id=["\'](root|app|__next)["\']', markup or ""))


# -------------------------------------------------------------- fetching

class _BoundedRedirects(urllib.request.HTTPRedirectHandler):
    """A redirect chain is bounded, may not leave the domain, and obeys robots.

    THE ROBOTS CHECK USED TO APPLY TO THE FIRST URL ONLY. `research` asks
    `robots_allows` about the page it is about to request and `urllib` then
    follows redirects on its own, so a site that allowed `/about` and
    redirected it to a disallowed path was read anyway. Same-domain was
    enforced the whole time, which bounds the damage to one site but does not
    make it consent. A refused redirect returns `None`, which `urllib` surfaces
    as the 3xx itself - classified `NON_2XX`, not silently a success.
    """

    def __init__(self, domain, limit, conf=None):
        self.domain = domain
        self.limit = limit
        self.conf = conf or DEFAULTS
        self.count = 0

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        self.count += 1
        if self.count > self.limit or not same_domain(newurl, self.domain):
            return None
        if not robots_allows(newurl, self.domain, self.conf):
            return None
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def host_of(url):
    try:
        return (urllib.parse.urlsplit(url).hostname or "").lower().rstrip(".")
    except ValueError:
        return ""


def same_domain(url, domain):
    """The company's own site, and `www.` of it. Nothing else.

    Deliberately narrow. A blog on a marketing platform or a careers page on a
    hiring host is somebody else's domain, and following it is how a bounded
    read of one company becomes an unbounded read of the web.
    """
    host = host_of(url)
    domain = (domain or "").lower().rstrip(".")
    return bool(host) and host in (domain, "www." + domain)


# When each host was last spoken to. Module-level because politeness is a
# property of the host, not of one `research()` call: `enrich` walks many
# records and several of them share a domain, and a per-call structure would
# reset the clock on every one.
_LAST_REQUEST_AT = {}


def _wait(host, gap):
    """The only thing that reads or writes `_LAST_REQUEST_AT`. Returns the wait.

    Split out from `_pace` because `_pace` has to ask robots.txt what the gap
    is, and reading robots.txt is itself a request that has to be paced - so a
    single function that both asked and recorded called itself through
    `_robots_for` and charged a host's first request for its own robots read.
    Two tests caught that (`the_first_request_to_a_host_does_not_wait` and
    `a_different_host_is_not_made_to_wait`), which is what the positive controls
    are for.
    """
    if not host:
        return 0.0
    last = _LAST_REQUEST_AT.get(host)
    now = time.monotonic()
    wait = 0.0
    if last is not None and gap > 0:
        wait = max(0.0, gap - (now - last))
        if wait > 0:
            time.sleep(wait)
    _LAST_REQUEST_AT[host] = time.monotonic()
    return wait


def _gap_for(host, conf):
    """How long between two requests to this host: our floor, or the site's.

    May fetch robots.txt the first time it is asked, which paces itself against
    the floor only - the stated delay cannot be honoured on the request that
    discovers it.
    """
    gap = float(conf.get("min_request_interval", 0.0) or 0.0)
    stated = robots_crawl_delay(host, conf)
    if stated is not None:
        gap = max(gap, min(stated,
                           float(conf.get("max_crawl_delay", 0.0) or 0.0)))
    return gap


def _pace(host, conf):
    """Wait, if the last request to this host was too recent. Returns the wait.

    THE OLD BOUNDS WERE NOT RATE LIMITS. `request_timeout`, `domain_timeout`
    and `max_pages` bound how long one read may take and how much of a site it
    may touch; none of them put any gap between two consecutive requests, so a
    six-page read arrived as six back-to-back hits. And `Crawl-delay`, which a
    site states precisely so that a crawler will slow down, was parsed by
    `RobotFileParser` and read by nobody.
    """
    if not host:
        return 0.0
    return _wait(host, _gap_for(host, conf))


def robots_crawl_delay(domain, conf):
    """The site's own `Crawl-delay`, or None when it states none.

    None is "no rule", never "zero". Returning 0.0 for a site that said
    nothing would be the same conflation `robots_allows` was written to avoid.
    """
    if not conf.get("respect_robots", True):
        return None
    parser = _robots_for(domain, conf)
    if parser is None:
        return None
    try:
        value = parser.crawl_delay(USER_AGENT)
    except Exception:
        return None
    if value is None:
        return None
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None


def robots_allows(url, domain, conf):
    """The site's own answer - when the site actually gave one.

    `RobotFileParser.read()` is not used, for two reasons that between them
    reported thirty per cent of a real batch as "asked us not to":

    It fetches with `urllib`'s default User-Agent rather than ours, so a site
    that blocks that agent makes the robots check fail even though the page
    fetch would have succeeded. Measured: `1gslab.com` serves
    `User-agent: * / Disallow:` - allow everything - and was recorded as
    disallowed.

    And it treats 401/403 as "disallow everything". A WAF refusing to serve
    robots.txt has not stated a rule; it has refused a request. Conflating the
    two turns bot protection into consent and hides it behind the one word an
    operator would never question. `4imprint.com` disallows a handful of admin
    paths and was recorded as refusing the homepage.

    So: fetch it ourselves, as ourselves. If the site serves rules, obey them.
    If it does not serve them at all, there are no rules to obey - and if it
    refuses us, the refusal shows up honestly on the page request itself,
    which is where BLOCKED belongs.
    """
    if not conf["respect_robots"]:
        return True
    parser = _robots_for(domain, conf)
    if parser is None:
        return True
    try:
        return parser.can_fetch(USER_AGENT, url)
    except Exception:
        return True


def _robots_for(domain, conf, _cache={}):
    """The parsed robots.txt for one host, fetched once. `None` when off.

    One cache, read by `robots_allows` and by `robots_crawl_delay`, so asking
    about the delay can never cost a second request - and so the two can never
    disagree about what the file said.
    """
    if not conf.get("respect_robots", True):
        return None
    if domain not in _cache:
        parser = urllib.robotparser.RobotFileParser()
        parser.parse([])                      # no rules until we read some
        request = urllib.request.Request(
            "https://%s/robots.txt" % domain,
            headers={"User-Agent": USER_AGENT})
        try:
            # Paced like any other request - robots.txt was the one request
            # this module made with no gap at all. Against the floor rather
            # than `_pace`, because the stated delay is in the file we are
            # about to read and asking `_pace` here would recurse.
            _wait(host_of("https://%s/" % domain),
                  float(conf.get("min_request_interval", 0.0) or 0.0))
            with urllib.request.urlopen(
                    request, timeout=conf["request_timeout"]) as answer:
                if 200 <= answer.status < 300:
                    body = answer.read(256 * 1024).decode("utf-8", "replace")
                    parser.parse(body.splitlines())
        except Exception:
            pass                              # no readable rules: none apply
        _cache[domain] = parser
    return _cache[domain]


def robots_cache_clear():
    """Forget every parsed robots.txt and every host's last-request time.

    The robots cache is process-global on purpose - one read per host per
    process - which makes it state a test can inherit from the test before it.
    `research.crawl_cache_clear` exists for the same reason.
    """
    _robots_for.__defaults__[-1].clear()
    _LAST_REQUEST_AT.clear()


def fetch(url, domain, conf):
    """One page, bounded. Returns (outcome, status, markup, bytes_read)."""
    handler = _BoundedRedirects(domain, conf["max_redirects"], conf)
    opener = urllib.request.build_opener(handler)
    request = urllib.request.Request(url, headers={
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "en,*",
    })
    cap = conf["max_bytes_per_page"]
    try:
        _pace(host_of(url), conf)
        with opener.open(request, timeout=conf["request_timeout"]) as answer:
            status = answer.status
            if not (200 <= status < 300):
                return NON_2XX, status, "", 0
            kind = (answer.headers.get_content_type() or "").lower()
            if kind not in ("text/html", "application/xhtml+xml"):
                return HTTP_INSUFFICIENT, status, "", 0
            raw = answer.read(cap + 1)
            if len(raw) > cap:
                # Refused rather than truncated: half a document is not a
                # document, and this repo has been bitten by a short read
                # already.
                return HTTP_INSUFFICIENT, status, "", len(raw)
            charset = answer.headers.get_content_charset() or "utf-8"
            return HTTP_SUCCESS, status, raw.decode(charset, "replace"), len(raw)
    except urllib.error.HTTPError as e:
        return (BLOCKED if e.code in (401, 403, 429) else NON_2XX), e.code, "", 0
    except (socket.timeout, TimeoutError):
        return TIMEOUT, None, "", 0
    except urllib.error.URLError as e:
        reason = getattr(e, "reason", None)
        if isinstance(reason, (socket.timeout, TimeoutError)):
            return TIMEOUT, None, "", 0
        return RESEARCH_FAILED, None, "", 0
    except Exception:
        return RESEARCH_FAILED, None, "", 0


def wanted_links(markup, base, domain, limit):
    """Pages the site itself links to, in the order we want them."""
    parser = _Links()
    try:
        parser.feed(markup)
    except Exception:
        pass
    found, seen = {}, set()
    for href in parser.hrefs:
        if href.startswith(("mailto:", "tel:", "javascript:", "#")):
            continue
        url = urllib.parse.urljoin(base, href)
        url, _ = urllib.parse.urldefrag(url)
        if not url.startswith(("http://", "https://")):
            continue
        if not same_domain(url, domain) or url in seen:
            continue
        seen.add(url)
        path = urllib.parse.urlsplit(url).path.strip("/").lower()
        if not path or path.count("/") > 2:
            continue
        for field, words in WANTED:
            if field in found:
                continue
            if any(path == w or path.endswith("/" + w) or path.startswith(w + "/")
                   or path == w + "/" for w in words):
                found[field] = url
                break
    ordered = [(field, found[field]) for field, _ in WANTED if field in found]
    return ordered[:limit]


# ------------------------------------------------------------ the read

def _now():
    return datetime.datetime.now(datetime.timezone.utc).replace(
        microsecond=0).isoformat()


def _page(url, field, status, markup, conf):
    text = readable_text(markup, conf["max_text_chars_per_page"])
    return {
        "source_type": "local_http",
        "provider": "local_http",
        "source_url": url,
        "http_status": status,
        "field": field,
        "fact": text,
        "content_hash": hashlib.sha256(text.encode("utf-8")).hexdigest()[:16],
        "chars": len(text),
    }


def research(domain, config=None, now=None):
    """Read one company's site. Free, bounded, and honest about what happened.

    Returns the outcome, the pages retained, and what it cost in requests and
    seconds - the two costs a local read actually has. There is no per-page
    provider charge here, which is the point, but "free" is not "no cost" and
    the numbers are reported rather than implied.
    """
    conf = settings(config)
    started = time.monotonic()
    stats = {"requests": 0, "bytes": 0, "pages_kept": 0, "seconds": 0.0,
             "outcomes": []}
    pages, worst = [], None

    def spent():
        return time.monotonic() - started

    def finish(outcome):
        stats["seconds"] = round(spent(), 2)
        stats["pages_kept"] = len(pages)
        return {"domain": domain, "outcome": outcome, "pages": pages,
                "stats": stats,
                "retrieved_at": now or _now(),
                "fallback_worthy": outcome in FALLBACK_WORTHY}

    home = "https://%s/" % domain
    if not robots_allows(home, domain, conf):
        stats["outcomes"].append("robots")
        return finish(BLOCKED)

    outcome, status, markup, size = fetch(home, domain, conf)
    stats["requests"] += 1
    stats["bytes"] += size
    stats["outcomes"].append(outcome)
    if outcome != HTTP_SUCCESS:
        return finish(outcome)

    text = readable_text(markup, conf["max_text_chars_per_page"])
    if looks_like_an_app(markup, text, conf):
        # Said plainly rather than scored. `urllib` cannot run the page, and a
        # shell is not evidence about the company inside it.
        return finish(JS_RENDERING_REQUIRED)
    if text:
        pages.append(_page(home, "company_website", status, markup, conf))

    for field, url in wanted_links(markup, home, domain,
                                   conf["max_pages"] - 1):
        if spent() > conf["domain_timeout"] or len(pages) >= conf["max_pages"]:
            break
        if not robots_allows(url, domain, conf):
            continue
        outcome, status, page_markup, size = fetch(url, domain, conf)
        stats["requests"] += 1
        stats["bytes"] += size
        stats["outcomes"].append(outcome)
        if outcome != HTTP_SUCCESS:
            worst = worst or outcome
            continue
        page = _page(url, field, status, page_markup, conf)
        if page["chars"]:
            pages.append(page)

    total = sum(p["chars"] for p in pages)
    if not pages:
        return finish(worst or HTTP_INSUFFICIENT)
    if total < conf["min_useful_chars"]:
        # The site answered, and what it says is too thin to qualify anybody
        # on. Not a failure of ours, and not worth paying Apify to re-read.
        return finish(HTTP_INSUFFICIENT)
    return finish(HTTP_SUCCESS)
