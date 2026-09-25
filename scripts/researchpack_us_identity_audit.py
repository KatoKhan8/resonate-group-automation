"""Re-ask the identity question of every fact in the log, independently.

LANE K, 2026-09-25. The acceptance bar is explicit: a fact that fails or
cannot establish company identity must not be counted as coverage, and
unverifiable is not a pass.

`site.research` already drops a page whose host is not the record's domain
and reports `off_domain_pages_dropped`. This does NOT trust that counter.
The counter and the dropping are the same code, so a bug in one hides in
the other - lane C wrote `off_domain` as "cannot happen through
webfetch.same_domain today, counted rather than assumed", and the reason
it is counted is that "cannot happen" is what was said about the job rows
before 50 of 71 turned out to belong to a different company.

So this walks the WRITTEN facts - the ones in the cache a pack build will
serve - and asks `site.on_this_domain` of each `source_url` again, from the
log rather than from the crawl. A fact that fails is named, not counted.

It also reports the two ways a fact could be unusable rather than
misattributed: no source url and no snippet. `facts.make` raises on both, so
the expected answer is zero and a non-zero one means something wrote a fact
without going through `make`.
"""
import argparse
import collections
import json
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from scripts.researchpack_us_crawl import lane_c_site         # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--log", required=True)
    ap.add_argument("--cache", help="also audit the consolidated cache")
    args = ap.parse_args(argv)

    site, sha = lane_c_site(HERE)
    print("lane C site.py blob %s" % sha)

    def audit(pairs, what):
        facts = bad_host = no_url = no_snippet = 0
        reported_drops = 0
        offenders = []
        kinds = collections.Counter()
        for domain, row in pairs:
            reported_drops += int(row.get("off_domain_pages_dropped") or 0)
            for one in row.get("facts") or []:
                facts += 1
                kinds[one.get("kind")] += 1
                url = one.get("source_url")
                if not url:
                    no_url += 1
                if not str(one.get("snippet") or "").strip():
                    no_snippet += 1
                if not site.on_this_domain(url, domain):
                    bad_host += 1
                    if len(offenders) < 10:
                        offenders.append((domain, url))
        print("")
        print("%s: %d fact(s), kinds %s" % (what, facts, dict(kinds)))
        print("  source_url NOT on the company's own domain   %d" % bad_host)
        print("  no source url                                %d" % no_url)
        print("  no snippet                                   %d" % no_snippet)
        print("  off-domain pages the crawler itself dropped  %d"
              % reported_drops)
        for domain, url in offenders:
            print("    MISATTRIBUTED  %s  <-  %s" % (domain, url))
        return bad_host + no_url + no_snippet

    pairs = []
    with open(args.log, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            pairs.append((row.get("domain"), row))
    failures = audit(pairs, "the crawl log")

    if args.cache and os.path.exists(args.cache):
        with open(args.cache, encoding="utf-8") as handle:
            data = json.load(handle)
        failures += audit([(e.get("domain"), e) for e in data.values()],
                          "the consolidated cache")

    print("")
    if failures:
        print("FAIL: %d fact(s) would be served under a company they do not "
              "belong to, or with no provenance." % failures)
        return 1
    print("Every served fact carries a source url and a snippet and is on "
          "the company's own domain. Identity was re-asked of the written "
          "facts, not inherited from the crawl's own counter.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
