"""The UNION of the crawl logs, identity-checked, as one servable cache.

LANE O, 2026-09-25. **Nothing here crawls, spends or sends.**

## NEITHER LOG ALONE IS COMPLETE, AND THAT IS MEASURED NOT ASSUMED

Lane J's cohort marks 128 domains as already carrying a pack fact. Those
128 come from `work/researchpack-us-CALIBRATION.jsonl` - lane J's own
`_laneJ_build_cohort.py` reads that file and nothing else to build the set -
and lane K's 400-char run got nothing for some of them, because a site that
answered at 09:40 can be down at 11:10. It also runs the other way. So
serving either log by itself hands the push a smaller cohort than this
system has actually researched, and `--report` prints the size of each
one-sided loss before it merges anything.

## PRECEDENCE, AND WHY IT IS BY CAP AND NOT BY CLOCK

Later logs win, but only where they carry facts: a domain that answered
before and refused now keeps the earlier answer rather than losing its pack
to a timeout. Within that, the 2000-character log outranks the 400-character
ones for the same domain even when it is not the newest, because the cap is
the reason this lane re-crawled: a 400-char snippet of a modern site is its
navigation bar, and a pack that serves the menu is what made `marketing` the
word doing the work in 579 of lane K's 4,478 passes.

## IDENTITY IS ASKED AGAIN HERE, FAIL-CLOSED

`webfetch.same_domain` bounds the crawl and lane C's `site.on_this_domain`
checked every page at the moment the fact was made. This asks a THIRD time,
with lane C's `actors.is_this_company` against `source_url`, at the moment
the fact becomes servable - because "cannot happen" is what was said about
the job rows before 50 of 71 turned out to belong to a different company.
A fact whose host cannot be placed on the record's own domain is DROPPED and
counted. Unverifiable is not a pass.

`actors.py` is materialised from lane C's blob, not copied: a copy in this
tree is a fork somebody later edits.

## AND ONE FILE IS NEVER READ

`work/researchpack-pilot-cache.PRE-FIX-DO-NOT-SERVE.json` is quarantined -
50 of its 71 job rows belonged to a different company. It is refused BY NAME
here rather than merely left out of the default arguments, so a future
caller who passes it gets an error instead of a pack.
"""
import argparse
import collections
import importlib.util
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

LANE_C_BRANCH = "worktree-agent-aea4a82ef07084898"
LANE_C_ACTORS = "src/researchpack/actors.py"

#: Refused by name. See the module docstring.
QUARANTINED = ("researchpack-pilot-cache.PRE-FIX-DO-NOT-SERVE.json",)

PROFILE = "site_content"


class Quarantined(RuntimeError):
    """A source this lane will not serve, named rather than silently skipped."""


def lane_c_actors(repo, branch=LANE_C_BRANCH, path=LANE_C_ACTORS):
    sha = subprocess.run(["git", "rev-parse", "%s:%s" % (branch, path)],
                         cwd=repo, capture_output=True, text=True,
                         check=True).stdout.strip()
    body = subprocess.run(["git", "cat-file", "blob", sha], cwd=repo,
                          capture_output=True, check=True).stdout
    target = os.path.join(repo, "work", "lanec-actors-%s.py" % sha[:12])
    os.makedirs(os.path.dirname(target), exist_ok=True)
    with open(target, "wb") as handle:
        handle.write(body)
    name = "src.researchpack.actors_lanec"
    spec = importlib.util.spec_from_file_location(name, target)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module, sha


def read_log(path):
    for base in QUARANTINED:
        if os.path.basename(path) == base:
            raise Quarantined(
                "%s is quarantined: 50 of its 71 job rows belonged to a "
                "different company. It is never served." % base)
    rows = {}
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except ValueError:
                continue
            domain = str(row.get("domain") or "").strip().lower()
            if domain:
                rows[domain] = row       # last write wins within one log
    return rows


def verify(path, profile):
    """Can PRODUCTION'S cache reader serve what was just written?

    A file in the right shape is not a served pack. `researchpack.cache.get`
    is what lane C's `build` calls, at the key `site_content`, and it checks
    freshness off `retrieved_at` on READ - so a cache whose date field is
    missing or stale is a file full of facts that serves nothing, and the
    call site cannot tell that from "we never looked".

    Asked here, against the file that was just written, with the env var a
    caller would actually set. The control is the half that matters: without
    it this passes for a reader that returns an entry for every string.
    """
    import importlib
    os.environ["RESEARCH_PACK_CACHE"] = os.path.abspath(path)
    if HERE not in sys.path:
        sys.path.insert(0, HERE)
    cache = importlib.import_module("src.researchpack.cache")
    data = cache.load()
    if not data:
        raise RuntimeError("production's cache reader read nothing from %s"
                           % path)
    domain = next(iter(data)).split("::")[0]
    hit = cache.get(domain, profile=profile)
    if not hit or not hit.get("facts"):
        raise RuntimeError(
            "production's cache reader found nothing at %s::%s - the key "
            "lane C's build asks for. The file is not servable."
            % (domain, profile))
    if int(hit.get("cost") or 0):
        raise RuntimeError("a free-crawl entry is carrying a cost")
    if not hit.get("retrieved_at"):
        raise RuntimeError(
            "no pack-level retrieved_at: `published_at` is null on every "
            "site fact by design, so this IS the date and a QA check that "
            "reads it at pack level would find nothing")
    for one in hit["facts"]:
        if one.get("published_at") is not None:
            raise RuntimeError("a crawled page is carrying a published_at")
        if not one.get("source_url") or not one.get("snippet"):
            raise RuntimeError("a fact without a source or a snippet")
    if cache.get("this-domain-is-not-in-the-cache.invalid",
                 profile=profile) is not None:
        raise RuntimeError("the reader serves a domain that is not there")
    print("")
    print("servable: production's own cache reader returns %d fact(s) at "
          "<domain>::%s, cost 0, pack-level retrieved_at present, every "
          "published_at null; and returns nothing for a domain that is not "
          "in the file" % (len(hit["facts"]), profile))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--log", action="append", default=[], required=True,
                    help="a crawl log, lowest precedence first; repeat")
    ap.add_argument("--out", required=True, help="the cache JSON to write")
    ap.add_argument("--profile", default=PROFILE)
    ap.add_argument("--json", default="", help="the report, as JSON")
    args = ap.parse_args(argv)

    actors, sha = lane_c_actors(HERE)
    print("lane C actors.py blob %s (loaded, not forked)" % sha)

    logs = []
    for path in args.log:
        rows = read_log(path)
        with_facts = sum(1 for r in rows.values() if r.get("facts"))
        logs.append((os.path.basename(path), rows))
        print("%-52s %6d row(s), %6d with a fact"
              % (os.path.basename(path), len(rows), with_facts))

    # WHAT EACH LOG ALONE WOULD MISS, before anything is merged.
    packed = [{d for d, r in rows.items() if r.get("facts")}
              for _name, rows in logs]
    union = set().union(*packed) if packed else set()
    print("")
    print("union of fact-carrying domains: %d" % len(union))
    for (name, _rows), mine in zip(logs, packed):
        print("  %-50s has %6d, misses %6d the others have"
              % (name, len(mine), len(union - mine)))

    merged, verdicts = {}, collections.Counter()
    dropped_facts = kept_facts = 0
    source_of = collections.Counter()
    for name, rows in logs:
        for domain, row in rows.items():
            facts = row.get("facts") or []
            if not facts:
                # A LOG THAT GOT NOTHING NEVER EVICTS A LOG THAT DID. A site
                # down for one run is not a reason to lose its pack.
                continue
            admitted = []
            for fact in facts:
                if actors.is_this_company(fact, domain, "source_url"):
                    admitted.append(fact)
                    verdicts["admitted"] += 1
                else:
                    # FAIL-CLOSED. Not "probably fine because same_domain
                    # ran": a fact whose host cannot be placed on this
                    # record's domain goes out under somebody else's name.
                    verdicts["refused_or_unverifiable"] += 1
            if not admitted:
                verdicts["domains_left_with_nothing"] += 1
                continue
            merged[domain] = {
                "domain": domain,
                "profile": args.profile,
                # PACK-LEVEL, AND IT IS THE DATE. `published_at` is null on
                # every site fact by design - a crawled page carries no
                # publication date worth trusting - so a QA check that reads
                # "source, date and snippet" PER FACT refuses every one of
                # them. The date is here.
                "retrieved_at": row.get("retrieved_at"),
                "facts": admitted,
                "cost": 0,
                "source_log": name,
            }
    for entry in merged.values():
        source_of[entry["source_log"]] += 1
        kept_facts += len(entry["facts"])
    dropped_facts = verdicts["refused_or_unverifiable"]

    tmp = args.out + ".tmp"
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump({"%s::%s" % (d, args.profile): e
                   for d, e in merged.items()}, handle, indent=1, default=str)
    os.replace(tmp, args.out)

    verify(args.out, args.profile)

    print("")
    print("served: %d domain(s), %d fact(s)" % (len(merged), kept_facts))
    print("  facts refused by is_this_company: %d" % dropped_facts)
    print("  domains left with nothing after identity: %d"
          % verdicts["domains_left_with_nothing"])
    print("  which log each served domain came from: %s"
          % source_of.most_common())
    print("written to %s" % args.out)

    report = {"logs": [n for n, _ in logs],
              "union_fact_carrying_domains": len(union),
              "served_domains": len(merged), "served_facts": kept_facts,
              "facts_refused_by_identity": dropped_facts,
              "domains_left_with_nothing": verdicts["domains_left_with_nothing"],
              "source_of_served_domain": source_of.most_common(),
              "one_sided_losses": {
                  name: len(union - mine)
                  for (name, _r), mine in zip(logs, packed)}}
    if args.json:
        with open(args.json, "w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=1, default=str)
        print("report written to %s" % args.json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
