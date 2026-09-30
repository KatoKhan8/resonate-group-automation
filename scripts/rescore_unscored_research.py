#!/usr/bin/env python3
"""Score the research rows the free leg retained without a score.

`research._from_the_site_itself` retained every free-crawled page WITHOUT
calling `evidence.make`, so the rows carry no `quality` and no
`relevance_score`. `evidence.select` admits only `quality in USABLE`, so all
of them were inadmissible - gathered, stored, counted, and unable to reach a
prompt. Fixed at the source in `d393a8f7`; this repairs the rows already on
the estate.

MEASURED 2026-09-30, before this ran: 550 of 1,224 research rows across 213
records were unscored - 525 from `local_http`, 25 from `apify`. Rescoring
them yields 296 MEDIUM, 198 weak and 56 unusable, so roughly three hundred
admissible facts were invisible to the copy stage.

THIS INVENTS NOTHING. Each row's score is re-derived from the text ALREADY
STORED on that row, by the same `evidence.make` every other row went through.
No fact is added, no text is edited, no threshold is moved: a row that scores
WEAK stays weak and stays dropped. The provenance the free leg recorded -
`content_hash`, `http_status`, `chars`, `field`, `source_url` - is carried
over unchanged, so a repaired row still traces to the page it came from.

Dry by default. `--live` writes, through `store.transaction`.

    py -3 scripts/rescore_unscored_research.py
    py -3 scripts/rescore_unscored_research.py --live
"""
import argparse
import collections
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import evidence as ev, store

#: Carried over the rescored row. The free leg's own provenance, which
#: `evidence.make` does not produce and which is how a row is traced back to
#: the page it was read from.
KEEP = ("content_hash", "http_status", "chars", "field", "published_at")


def needs_score(row):
    return (row or {}).get("quality") is None or \
        (row or {}).get("relevance_score") is None


def rescore(row, record_id):
    scored = ev.make(fact=row.get("fact"),
                     source_url=row.get("source_url"),
                     source_type=row.get("source_type") or "local_http",
                     provider=row.get("provider") or "local_http",
                     record_id=record_id,
                     published_at=row.get("published_at"),
                     retrieved_at=row.get("retrieved_at"))
    return dict(scored, **{k: v for k, v in (row or {}).items()
                           if k in KEEP and v is not None})


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--live", action="store_true")
    args = ap.parse_args()

    counts = collections.Counter()
    touched = set()

    def walk(records):
        for rec in records:
            rows = rec.get("research") or []
            out, changed = [], False
            for row in rows:
                if not needs_score(row):
                    out.append(row)
                    continue
                new = rescore(row, rec.get("id"))
                counts[new.get("quality")] += 1
                touched.add(rec.get("id"))
                changed = True
                out.append(new)
            if changed:
                rec["research"] = out

    if args.live:
        with store.transaction() as records:
            walk(records)
    else:
        walk(store.load())

    print("records touched :", len(touched))
    print("rows rescored   :", sum(counts.values()))
    for quality, n in counts.most_common():
        mark = "ADMISSIBLE" if quality in ev.USABLE else "dropped"
        print("   %-10s %5d   %s" % (quality, n, mark))
    print("mode            :", "LIVE (written)" if args.live else "dry run")


if __name__ == "__main__":
    main()
