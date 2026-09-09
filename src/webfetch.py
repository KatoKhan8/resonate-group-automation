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

USER_AGENT = ("Mozilla/5.0 (compatible; ResonateResearch/1.0; "
              "+company qualification, respects robots.txt)")

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
    """A redirect chain is bounded, and it may not leave the domain."""

    def __init__(self, domain, limit):
        self.domain = domain
        self.limit = limit
        self.count = 0

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        self.count += 1
        if self.count > self.limit or not same_domain(newurl, self.domain):
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


def robots_allows(url, domain, conf, _cache={}):
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
    if domain not in _cache:
        parser = urllib.robotparser.RobotFileParser()
        parser.parse([])                      # no rules until we read some
        request = urllib.request.Request(
            "https://%s/robots.txt" % domain,
            headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(
                    request, timeout=conf["request_timeout"]) as answer:
                if 200 <= answer.status < 300:
                    body = answer.read(256 * 1024).decode("utf-8", "replace")
                    parser.parse(body.splitlines())
        except Exception:
            pass                              # no readable rules: none apply
        _cache[domain] = parser
    try:
        return _cache[domain].can_fetch(USER_AGENT, url)
    except Exception:
        return True


def fetch(url, domain, conf):
    """One page, bounded. Returns (outcome, status, markup, bytes_read)."""
    handler = _BoundedRedirects(domain, conf["max_redirects"])
    opener = urllib.request.build_opener(handler)
    request = urllib.request.Request(url, headers={
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "en,*",
    })
    cap = conf["max_bytes_per_page"]
    try:
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
