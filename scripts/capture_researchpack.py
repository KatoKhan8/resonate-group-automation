#!/usr/bin/env python3
"""Capture REAL Apify responses for the research pack's cassettes.

    py -3 scripts/capture_researchpack.py --status          # decide only
    py -3 scripts/capture_researchpack.py --domain acme.test --live

## IT COSTS CREDITS AND IT IS NOT RUN BY ANYTHING

`--live` starts real actor runs. Without it this prints what it WOULD run
and exits, which is the same default the rest of this codebase uses for
anything that spends.

## WHY IT EXISTS

`tests/fixtures/cassettes/00-researchpack.json` is hand written to Apify's
documented schema and says so in its first entry. It is NOT a capture, and
it cannot be one yet: `src/providers/apify.py` records that every actor run
this repository ever started was rejected with 400 `invalid-input` for a
missing `proxyConfiguration`, so **no Apify actor has ever returned
evidence here and nobody in this codebase has seen the real output shape.**

`src/researchpack/actors.py` sets `proxyConfiguration` on every input, so
the runs this starts should be the first that survive. Until somebody runs
it, the cassettes are a documented guess and the tests say so rather than
implying otherwise.

## WHAT IT WRITES, AND WHAT IT DOES NOT

It writes the raw dataset rows to the path given by `--out`, for a person
to read, redact and paste into the cassette. **It does not edit the
cassette.** A capture that rewrote its own fixture would let a shape change
land with no human in front of it, and the rows are somebody's real posts:
they need reading before they become a fixture in git.

`docs/`-bound output would carry real company names into a tracked file,
which `tests/test_fixture_hygiene.py` refuses - correctly. Default output
is under `work/`, which is gitignored.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import researchpack, store                             # noqa: E402
from src.providers import load_env                              # noqa: E402
from src.researchpack import actors                             # noqa: E402


def default_out():
    return os.path.join(os.path.dirname(store.queue_path()),
                        "researchpack-capture")


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--domain", default=None)
    parser.add_argument("--company-url", default=None)
    parser.add_argument("--champion", default=None)
    parser.add_argument("--exec", dest="exec_profile", default=None)
    parser.add_argument("--client", default="unattributed")
    parser.add_argument("--out", default=None)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--status", action="store_true")
    args = parser.parse_args(argv)

    load_env()
    planned = [("company_posts", args.company_url
                or ("https://%s" % args.domain if args.domain else "?")),
               ("open_roles", args.domain or "?")]
    if args.champion:
        planned.append(("person_posts", args.champion))
    if args.exec_profile:
        planned.append(("person_posts", args.exec_profile))

    print("actors this would run, and the planned cost:")
    for name, target in planned:
        spec = actors.ACTORS[name]
        print("  %-14s %-4d %s" % (name, spec["cost"], target))
    print("  %-14s %-4d TOTAL (ledger cents)"
          % ("", actors.cost_of([n for n, _ in planned])))

    if args.status or not args.live:
        print("\nnot live: nothing was started and nothing was charged. "
              "Pass --live to capture.")
        return 0
    if not args.domain:
        print("--live needs --domain", file=sys.stderr)
        return 2

    out_dir = args.out or default_out()
    os.makedirs(out_dir, exist_ok=True)
    captured = {}

    def recorder(actor, payload, limit):
        from src.researchpack.pack import _live_runner
        rows = _live_runner(actor, payload, limit)
        captured[actor] = rows
        return rows

    pack = researchpack.build(args.domain, live=True, client=args.client,
                              champion=args.champion,
                              exec_profile=args.exec_profile,
                              company_url=args.company_url, runner=recorder)

    for actor, rows in captured.items():
        name = actor.replace("~", "-").replace("/", "-") + ".json"
        target = os.path.join(out_dir, name)
        with open(target, "w", encoding="utf-8") as handle:
            json.dump(rows, handle, indent=1, default=str, ensure_ascii=False)
        print("wrote %d row(s) -> %s" % (len(rows or []), target))

    print("\ncost recorded for this account: %d" % pack["cost"])
    print("facts usable after provenance filtering: %d" % pack["fact_count"])
    print("\nREAD THESE BEFORE THEY BECOME A FIXTURE. They are somebody's "
          "real posts and this script deliberately does not edit the "
          "cassette for you.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
