"""Would a longer snippet fix the single-word problem? Measured, not argued.

LANE K, 2026-09-25. §2.1 of the merge request says a fact's snippet is the
first 400 characters of the page and that on a modern site that is the
navigation bar, and that this is why `marketing` is the word carrying a
third of the rule-1 passes. That is a diagnosis. **A diagnosis nobody tests
is a story**, and the recommendation it leads to - raise
`facts.SNIPPET_CHARS`, or teach `webfetch.readable_text` to skip the leading
menu - costs somebody a change to shared code.

So this measures the counterfactual on a live sample before anybody is asked
to make it. Nothing is changed and nothing is spent: it reads the same pages
`webfetch.research` reads, then builds the pack text at several snippet
lengths and asks `copylint`'s own rule-1 question of each.

WHAT IT DOES NOT DO. It does not edit `facts.SNIPPET_CHARS`, and it does not
call `facts.make` at a different limit - `make` is lane C's and master's
code and this lane does not fork it. It slices the page text the way `clean`
would and reports what rule 1 would then say. The identity question is still
asked, through `site.on_this_domain`, so a page off the company's domain is
dropped here exactly as it is in the real pack.

    py -3 scripts/researchpack_snippet_probe.py --cohort <lane J's file> \
        --sample 120 --lengths 400,1000,2000,8000
"""
import argparse
import json
import os
import random
import sys
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from src import cadence, clients, copylint, webfetch          # noqa: E402
from src.researchpack import facts as packfacts               # noqa: E402
from src.providers import apify                               # noqa: E402
from scripts.researchpack_us_crawl import lane_c_site, read_cohort  # noqa: E402
from scripts.researchpack_us_rule1 import (openers_for, rule1_tokens,
                                           matched, NAV_WORDS)  # noqa: E402


def _nav_hits(snippet):
    low = " %s " % str(snippet or "").lower()
    return sum(1 for w in NAV_WORDS if " %s " % w in low)


def probe(rec, site, lengths):
    """One domain, read once, scored at every snippet length."""
    domain = rec["domain"]
    try:
        apify.check_url("https://%s/" % domain, allowed_domain=domain)
    except Exception:                          # noqa: BLE001 - classified
        return None
    try:
        result = webfetch.research(domain) or {}
    except Exception:                          # noqa: BLE001 - classified
        return None
    pages = [p for p in (result.get("pages") or [])
             if site.on_this_domain(p.get("source_url"), domain)]
    if not pages:
        return None

    config = probe.config
    openers = openers_for(rec, config)
    if not openers:
        return None

    out = {"domain": domain, "pages": len(pages), "by_length": {}}
    for limit in lengths:
        # The same normalisation `facts.clean` applies, at a different cap.
        text = " ".join(packfacts.clean(p.get("fact"), limit) for p in pages)
        supported = copylint._norm(text)
        thinnest = None
        for _persona, _angle, opener in openers:
            hit = matched(rule1_tokens(opener, True), supported)
            if hit and (thinnest is None or len(hit) < len(thinnest)):
                thinnest = hit
        out["by_length"][limit] = {
            "passes": bool(thinnest),
            "distinct_words": len(thinnest or []),
            "words": thinnest or [],
            # DENSITY, NOT A FLAG. `navigation_led` asks whether a snippet
            # carries three or more items of menu furniture, which is a fair
            # question of a 400-character snippet and a meaningless one of
            # an 8,000-character page: a longer text contains more of
            # everything, so the flag rises with the limit whatever the
            # prose does. A first version of this probe printed exactly that
            # and it read as "longer snippets are MORE navigational", which
            # is an artefact of the threshold and not a finding.
            #
            # So the comparable number is menu items per 400 characters of
            # the FIRST page, which is what the flag was really measuring.
            "nav_per_400": round(
                400.0 * _nav_hits(packfacts.clean(pages[0].get("fact"), limit))
                / max(1, len(packfacts.clean(pages[0].get("fact"), limit))), 2),
        }
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--cohort", required=True)
    ap.add_argument("--client", default="productive")
    ap.add_argument("--sample", type=int, default=120)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--seed", type=int, default=20260925)
    ap.add_argument("--lengths", default="400,1000,2000,8000")
    ap.add_argument("--json", default="")
    args = ap.parse_args(argv)

    lengths = [int(x) for x in args.lengths.split(",") if x.strip()]
    site, sha = lane_c_site(HERE)
    probe.config = clients.load(args.client)
    print("lane C site.py blob %s; facts.SNIPPET_CHARS is %d today"
          % (sha, packfacts.SNIPPET_CHARS))

    rows = read_cohort(args.cohort)
    random.Random(args.seed).shuffle(rows)      # a seeded sample, so it repeats
    rows = rows[:args.sample]

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        got = [r for r in pool.map(lambda r: probe(r, site, lengths), rows) if r]

    print("%d of %d sampled domains answered with a page on their own domain"
          % (len(got), len(rows)))
    print("")
    print("DENOMINATOR: domains that ANSWERED, not domains attempted. The "
          "walk's rate is lower because it counts every attempt.")
    print("")
    print("snippet   passes rule 1     of those, on ONE word   menu items /400ch")
    report = {}
    for limit in lengths:
        passes = [g["by_length"][limit] for g in got]
        n = sum(1 for p in passes if p["passes"])
        ones = sum(1 for p in passes if p["passes"] and p["distinct_words"] == 1)
        density = sum(p["nav_per_400"] for p in passes) / (len(passes) or 1)
        report[limit] = {"passes": n, "single_word": ones,
                         "nav_per_400": round(density, 2),
                         "domains_that_answered": len(got)}
        print("%7d   %4d  %5.1f%%        %4d  %5.1f%%              %5.2f"
              % (limit, n, 100.0 * n / (len(got) or 1),
                 ones, 100.0 * ones / (n or 1), density))

    if args.json:
        with open(args.json, "w", encoding="utf-8") as handle:
            json.dump({"lengths": report, "detail": got}, handle, indent=1,
                      default=str)
        print("written to %s" % args.json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
