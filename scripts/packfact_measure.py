#!/usr/bin/env python3
"""Measure GATE 3 against the real 400-character research-pack cache.

    py scripts/packfact_measure.py work/researchpack-us-*.jsonl
    py scripts/packfact_measure.py work/researchpack-us-*.jsonl --isolate
    py scripts/packfact_measure.py --shipped work/review/raw

Three questions, and every number the incident document quotes about the
cache comes from here rather than from a paragraph somebody wrote once:

  default     how many cached rows hold a quotable body sentence and how
              many are HELD, with a sample of each so the accepted spans
              can be read and judged as prose by a person.
  --isolate   for each named rule, a real cached span that THAT RULE ALONE
              refuses. This is where `SINGLE_RULE` in
              `tests/test_a_navigation_bar_is_not_a_pack_fact.py` came
              from, and re-running it is how you find out that a rule has
              stopped being load-bearing.
  --shipped   replay the spans that actually went to prospects on
              503/504/505, read out of the provider snapshots, and assert
              the gate refuses every one. Reads snapshot FILES only.

READS ONLY, and only files. It touches no provider.

A NOTE ON WHICH FILES TO PASS. `work/researchpack-us-cohort-2026-09-25
.jsonl` is a per-domain SUMMARY carrying `"facts": 3` - an integer - and it
sits beside three files with almost the same name carrying the real list.
Rows whose `facts` is not a list are skipped and counted separately, so a
glob that catches the summary reports it rather than crashing on it or,
worse, scoring it as three usable facts.
"""
import argparse
import collections
import glob
import json
import os
import re
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src import packfact  # noqa: E402

#: How the openers that shipped name the line they quote.
SHIPPED_SPAN = re.compile(r"the line about (.+?) is what made me write", re.S)


def _rows(paths):
    for path in paths:
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    yield json.loads(line)


def measure(paths, sample=12):
    counts = collections.Counter()
    accepted, held = [], []
    for row in _rows(paths):
        counts["rows"] += 1
        if not isinstance(row.get("facts"), list):
            counts["not_a_pack"] += 1
            continue
        if not packfact.facts_of(row):
            continue
        counts["with_facts"] += 1
        found = packfact.quotable_in_pack(row)
        if found:
            counts["quotable"] += 1
            if len(accepted) < sample:
                accepted.append((row.get("domain"), found[0][0]))
        else:
            counts["held"] += 1
            if len(held) < sample:
                spans = packfact.sentences_in(
                    packfact.facts_of(row)[0].get("snippet"))
                held.append((row.get("domain"), spans[0] if spans else ""))
    return counts, accepted, held


def isolate(paths, per_rule=3):
    """Real spans that exactly ONE rule refuses, one bucket per rule."""
    found = collections.defaultdict(list)
    for row in _rows(paths):
        for fact in packfact.facts_of(row):
            for span in packfact.sentences_in(fact.get("snippet")):
                tokens = packfact._words(span)
                fired = [n for n, rule in packfact.RULES if rule(span, tokens)]
                if len(fired) == 1 and len(found[fired[0]]) < per_rule:
                    found[fired[0]].append(span)
    return found


def shipped(snapshot_dir, campaigns=("503", "504", "505")):
    spans = []
    for cid in campaigns:
        path = os.path.join(snapshot_dir, "bison-%s.json" % cid)
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as f:
            snapshot = json.load(f)
        for lead in snapshot.get("leads") or []:
            variables = {c.get("name"): c.get("value")
                         for c in lead.get("custom_variables") or []}
            match = SHIPPED_SPAN.search(str(variables.get("body_1") or ""))
            if match:
                spans.append((cid, match.group(1).strip()))
    return spans


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("packs", nargs="*", default=())
    ap.add_argument("--isolate", action="store_true")
    ap.add_argument("--shipped", metavar="SNAPSHOT_DIR")
    a = ap.parse_args(argv)

    if a.shipped:
        spans = shipped(a.shipped)
        accepted = [(c, s) for c, s in spans
                    if packfact.is_body_sentence(s)]
        print("spans that shipped to real prospects: %d" % len(spans))
        print("ACCEPTED by gate 3 (must be 0):        %d" % len(accepted))
        for cid, span in accepted[:20]:
            print("   [%s] %r" % (cid, span))
        why = collections.Counter()
        for _cid, span in spans:
            for reason in packfact.reasons_against(span):
                why[reason.split(":")[0]] += 1
        for reason, count in why.most_common(12):
            print("   %6d  %s" % (count, reason))
        return 1 if accepted else 0

    paths = []
    for pattern in a.packs:
        paths += sorted(glob.glob(pattern)) or [pattern]
    if not paths:
        ap.error("name at least one research-pack file")

    if a.isolate:
        found = isolate(paths)
        missing = []
        for name, _rule in packfact.RULES:
            print("=== %s (%d found)" % (name, len(found[name])))
            for span in found[name]:
                print("   %r" % span[:150])
            if not found[name]:
                missing.append(name)
        if missing:
            print()
            print("NO REAL SPAN ISOLATES: %s" % ", ".join(missing))
            print("Either the rule is doing nothing its neighbours are not "
                  "already doing, or the cache no longer contains the chrome "
                  "it was written for. Both are worth knowing before it is "
                  "trusted.")
        return 1 if missing else 0

    counts, accepted, held = measure(paths)
    with_facts = max(counts["with_facts"], 1)
    print("pack rows read          : %d" % counts["rows"])
    if counts["not_a_pack"]:
        print("rows that are NOT packs : %d  (`facts` is not a list - a "
              "summary file was in the glob)" % counts["not_a_pack"])
    print("rows carrying facts     : %d" % counts["with_facts"])
    print("rows with a quotable    : %d  (%.1f%%)"
          % (counts["quotable"], 100.0 * counts["quotable"] / with_facts))
    print("rows HELD               : %d  (%.1f%%)"
          % (counts["held"], 100.0 * counts["held"] / with_facts))
    print()
    print("--- accepted spans: read these and judge them as prose ---")
    for domain, span in accepted:
        print("   [%s] %s" % (domain, span[:150]))
    print()
    print("--- HELD rows: the first candidate span in each ---")
    for domain, span in held:
        print("   [%s] %s" % (domain, span[:130]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
