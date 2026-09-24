#!/usr/bin/env python3
"""Would tomorrow's UK/EU leads survive copylint rule 1? By name, not in aggregate.

    py -3 scripts/researchpack_copylint_gap.py --work <dir>

## THE QUESTION THIS ANSWERS, AND THE ONE IT REFUSES TO ANSWER INSTEAD

`copylint.check_batch`'s first rule - `step1_without_pack_fact` - is wired
on the send path, so a lead whose step 1 opens on a line no pack fact
supports REFUSES the push. "93% of researched records would pass" is a rate
over the RESEARCHED set. The set going out tomorrow is a different set, and
this repository's recurring failure is exactly a headline number from a
stage that had not asked the next stage's question: 1,508 exportable that
was 114, 19,612 "IN" of which two thirds were under the floor.

So this asks rule 1 of the leads themselves, one at a time, and reports the
denominator it used every time it reports a rate.

## IT DOES NOT RE-IMPLEMENT THE RULE

`copylint.pack_text`, `copylint.first_line` and `copylint._WORD` are
imported and called. A second copy of the matching would be a report that
agrees with itself and not with the gate.

## TWO SOURCES OF FREE-CRAWL RESEARCH, COUNTED SEPARATELY

  queue     `record["research"]` - what `src/research.py` put there through
            `src/webfetch.py`, per account, over previous passes.
  cohort    `work/researchpack-cohort-*-cache.json` - the `site_page` facts
            `scripts/researchpack_cohort.py` read tonight, for this cohort.

They are reported apart and then together, because "covered" from a cache
this lane wrote tonight and "covered" from the estate's own record are
different claims about how ready tomorrow is.
"""
import argparse
import collections
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

UK = {"United Kingdom", "Ireland"}
EU = {"Germany", "Sweden", "France", "Finland", "Netherlands", "Denmark",
      "Norway", "Belgium", "Austria", "Switzerland", "Poland", "Spain",
      "Italy", "Croatia", "Portugal", "Czechia"}
CAPS = {"uk": 2 * 45, "eu": 1 * 45}


def _jsonl(path):
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                yield json.loads(line)


def rule_one_passes(opener, pack):
    """`copylint.check_batch`'s first rule, asked of one lead.

    Lifted verbatim from that function rather than described: a pack with
    no facts fails, and so does an opener sharing no word over four letters
    with any snippet in it.
    """
    from src import copylint
    supported = copylint.pack_text(pack)
    tokens = [t for t in copylint._WORD.findall(str(opener or "").lower())
              if len(t) > 4]
    return bool(supported) and any(t in supported for t in tokens)


def cohort_packs(work_dir):
    """`site_page` facts from every cohort cache this lane has written."""
    out = collections.defaultdict(list)
    for path in sorted(glob.glob(os.path.join(
            work_dir, "researchpack-cohort-*-cache.json"))):
        try:
            with open(path, encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, ValueError):
            continue
        for entry in (data or {}).values():
            if not isinstance(entry, dict):
                continue
            domain = str(entry.get("domain") or "").lower()
            for fact in entry.get("facts") or []:
                if isinstance(fact, dict) and fact.get("snippet"):
                    out[domain].append(fact)
    return out


def queue_packs(records):
    """`record["research"]` as a pack, and only its FREE-CRAWL rows.

    A row with no `provider` is counted as free-crawl only when it carries
    `source_type: local_http`. Anything that names another provider is a
    different question and is excluded rather than assumed.
    """
    out = {}
    for record in records:
        domain = str(record.get("domain") or "").lower()
        facts = []
        for row in record.get("research") or []:
            if not isinstance(row, dict):
                continue
            if (row.get("provider") or row.get("source_type")) != "local_http":
                continue
            if row.get("fact"):
                facts.append({"snippet": row.get("fact"),
                              "source_url": row.get("source_url"),
                              "kind": "site_page"})
        if facts:
            out[domain] = facts
    return out


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--work", default=os.path.join(ROOT, "work"))
    parser.add_argument("--client", default="productive")
    parser.add_argument("--out", default=None)
    args = parser.parse_args(argv)

    work_dir = os.path.abspath(args.work)
    os.environ["QUEUE"] = os.path.join(work_dir, "queue.jsonl")
    os.environ["CLIENT_APPROVAL"] = os.path.join(work_dir,
                                                 "client-approval.jsonl")
    from src import clientapproval as ca, copylint, store

    stage = os.path.join(work_dir, "stage")
    icp = {str(r.get("domain", "")).lower(): r
           for r in _jsonl(os.path.join(stage, "s3-icp.jsonl"))}

    leads = []
    for row in _jsonl(os.path.join(stage, "s7-copy.jsonl")):
        if row.get("state") != "rendered":
            continue
        email = str(row.get("email", "")).lower()
        domain = email.split("@")[-1]
        country = (icp.get(domain) or {}).get("country") or "unknown"
        cohort = "uk" if country in UK else "eu" if country in EU else None
        if not cohort:
            continue
        if not ca.is_approved(domain, args.client):
            continue
        variables = row.get("variables") or {}
        leads.append({"email": email, "domain": domain, "cohort": cohort,
                      "country": country,
                      "opener": copylint.first_line(variables.get("body_1"))})

    records = store.load()
    by_domain = {}
    for record in records:
        domain = str(record.get("domain") or "").lower()
        by_domain.setdefault(domain, record)
    qpacks = queue_packs(records)
    cpacks = cohort_packs(work_dir)

    capped, per = [], collections.Counter()
    for lead in leads:
        if per[lead["cohort"]] < CAPS[lead["cohort"]]:
            per[lead["cohort"]] += 1
            capped.append(lead)
    no_record = [x for x in leads if x["domain"] not in by_domain]

    sets = collections.OrderedDict((
        ("all UK/EU rendered + approved", leads),
        ("under the cohort caps (90 uk / 45 eu)", capped),
        ("with NO queue record at all", no_record),
    ))

    report = collections.OrderedDict()
    for label, pool in sets.items():
        domains = {x["domain"] for x in pool}
        rows = []
        for lead in pool:
            qfacts = qpacks.get(lead["domain"]) or []
            cfacts = cpacks.get(lead["domain"]) or []
            rows.append({
                "email": lead["email"], "domain": lead["domain"],
                "cohort": lead["cohort"],
                "has_queue_record": lead["domain"] in by_domain,
                "queue_free_crawl_facts": len(qfacts),
                "cohort_free_crawl_facts": len(cfacts),
                "rule1_queue": rule_one_passes(lead["opener"],
                                               {"facts": qfacts}),
                "rule1_cohort": rule_one_passes(lead["opener"],
                                                {"facts": cfacts}),
                "rule1_either": rule_one_passes(lead["opener"],
                                                {"facts": qfacts + cfacts}),
                "opener_empty": not lead["opener"].strip(),
            })
        report[label] = {
            "leads": len(pool),
            "domains": len(domains),
            "with_queue_record": sum(1 for r in rows if r["has_queue_record"]),
            "with_queue_free_crawl": sum(1 for r in rows
                                         if r["queue_free_crawl_facts"]),
            "with_cohort_free_crawl": sum(1 for r in rows
                                          if r["cohort_free_crawl_facts"]),
            "with_any_free_crawl": sum(
                1 for r in rows if r["queue_free_crawl_facts"]
                or r["cohort_free_crawl_facts"]),
            "rule1_pass_queue": sum(1 for r in rows if r["rule1_queue"]),
            "rule1_pass_cohort": sum(1 for r in rows if r["rule1_cohort"]),
            "rule1_pass_either": sum(1 for r in rows if r["rule1_either"]),
            "openers_empty": sum(1 for r in rows if r["opener_empty"]),
            "rows": rows,
        }

    for label, row in report.items():
        print("\n%s" % label.upper())
        print("  leads                         %4d over %d domain(s)"
              % (row["leads"], row["domains"]))
        print("  match a queue record          %4d  (%d do not)"
              % (row["with_queue_record"], row["leads"] - row["with_queue_record"]))
        print("  carry free-crawl, queue       %4d" % row["with_queue_free_crawl"])
        print("  carry free-crawl, this lane   %4d" % row["with_cohort_free_crawl"])
        print("  carry free-crawl, either      %4d  %5.1f%%"
              % (row["with_any_free_crawl"],
                 100.0 * row["with_any_free_crawl"] / (row["leads"] or 1)))
        print("  PASS copylint rule 1, queue   %4d  %5.1f%%"
              % (row["rule1_pass_queue"],
                 100.0 * row["rule1_pass_queue"] / (row["leads"] or 1)))
        print("  PASS copylint rule 1, either  %4d  %5.1f%%"
              % (row["rule1_pass_either"],
                 100.0 * row["rule1_pass_either"] / (row["leads"] or 1)))
        print("  step 1 opener is empty        %4d" % row["openers_empty"])

    out = args.out or os.path.join(
        work_dir, "researchpack-copylint-gap-ukeu.json")
    with open(out, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=1, default=str, ensure_ascii=False)
    print("\nwrote %s  (names real prospects; work/ is gitignored)" % out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
