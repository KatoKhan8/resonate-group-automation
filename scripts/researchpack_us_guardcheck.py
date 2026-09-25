"""Prove the two guards on the free-crawl path FIRE, rather than that they are present.

LANE K, 2026-09-25. The US walk recorded zero `UNSAFE_URL` refusals over
16,247 domains, which is the right answer for a file of real company domains
and is indistinguishable from a gate that was never wired in. This repository
has shipped an inert matcher past eighteen green tests before.

So: drive `pack_one` - the SAME function the walk calls, not a copy of it -
with hostile rows and assert on the effect.

    py -3 scripts/researchpack_us_guardcheck.py

Nothing here reaches the network. Every case below is refused BEFORE the
crawler is invoked, and the crawler is replaced by one that raises if it is
ever called, so a refusal that did not happen shows up as a failure rather
than as a quiet pass.

Two guards, asked separately:

* `apify.check_url` - scheme, credentials, port, loopback names, internal
  suffixes, literal private and reserved addresses, and DNS resolution into
  a blocked network. Imported and called, never edited, nothing widened.
* `site.on_this_domain` - the company-identity question asked of every page
  kept, fail-closed on a missing domain or host.
"""
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from scripts.researchpack_us_crawl import lane_c_site, pack_one   # noqa: E402

#: Each is `(domain, what the refusal must be about)`. The second element is
#: matched as a substring of the recorded reason, so a case that is refused
#: for a DIFFERENT reason than the one it exists to prove fails too - a red
#: result has to be red for the intended reason.
HOSTILE = [
    ("localhost", "loopback"),
    ("ip6-localhost", "loopback"),
    ("intranet.local", "internal"),
    ("payroll.corp", "internal"),
    ("box.lan", "internal"),
    ("127.0.0.1", "private or reserved"),
    ("10.0.0.7", "private or reserved"),
    ("192.168.1.1", "private or reserved"),
    ("169.254.169.254", "private or reserved"),      # cloud metadata
    # The expectation here was written as "no host in url" and the guard
    # did BETTER: urlsplit parses the brackets as an IPv6 literal, so it is
    # refused as the loopback address it actually is. The expectation was
    # corrected to what the guard proves, not the other way round.
    ("[::1]", "private or reserved"),
]

#: `pack_one` builds `https://<domain>/`, so a scheme, a port or credentials
#: can only arrive embedded in the "domain" field - which is exactly how a
#: sourcing file would carry them.
EMBEDDED = [
    ("evil.test:8080", "port 8080"),
    ("user:pass@evil.test", "credentials in url"),
]


class NeverCalled:
    """A crawler that proves the refusal happened before the network did."""

    def research(self, domain, config=None, now=None, crawler=None):
        raise AssertionError(
            "the crawler was reached for %r - the SSRF gate did not fire"
            % (domain,))


def main():
    site, sha = lane_c_site(HERE)
    print("lane C site.py blob %s" % sha)

    failures = []

    # --- guard one: check_url, on the walk's own code path ---------------
    for domain, because in HOSTILE + EMBEDDED:
        row = pack_one({"domain": domain}, NeverCalled())
        ok = row.get("outcome") == "UNSAFE_URL" and because in (
            row.get("refused") or "")
        print("  %-28s %-12s %s" % (domain, row.get("outcome"),
                                    row.get("refused") or row.get("error")))
        if not ok:
            failures.append("%s was not refused for %r (got %r / %r)"
                            % (domain, because, row.get("outcome"),
                               row.get("refused")))

    # A real public domain must NOT be refused, or the gate is refusing
    # everything and the zero above would mean nothing.
    row = pack_one({"domain": "example.com"}, NeverCalled())
    if row.get("outcome") == "UNSAFE_URL":
        failures.append("example.com was refused by check_url (%r) - a gate "
                        "that refuses everything proves nothing"
                        % row.get("refused"))
    else:
        # It got past the gate and hit NeverCalled, which is the wanted shape.
        print("  %-28s %-12s %s" % ("example.com", row.get("outcome"),
                                    (row.get("error") or "")[:60]))

    # --- guard two: on_this_domain, fail-closed --------------------------
    cases = [
        (("https://acme.com/about", "acme.com"), True),
        (("https://www.acme.com/about", "acme.com"), True),
        (("https://blog.acme.com/x", "acme.com"), True),
        (("https://acme.com.evil.net/x", "acme.com"), False),
        (("https://notacme.com/x", "acme.com"), False),
        ((None, "acme.com"), False),
        (("https://acme.com/x", ""), False),
        (("https://acme.com/x", None), False),
    ]
    for (url, domain), wanted in cases:
        got = site.on_this_domain(url, domain)
        print("  on_this_domain(%-30r, %-10r) -> %s" % (url, domain, got))
        if got is not wanted:
            failures.append("on_this_domain(%r, %r) was %r, wanted %r"
                            % (url, domain, got, wanted))

    if failures:
        print("")
        for line in failures:
            print("FAIL: %s" % line)
        return 1
    print("")
    print("both guards fired on every case, and neither refused a public "
          "domain. The crawler was never reached.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
