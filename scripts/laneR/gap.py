"""Lane R step 1d: the brief says 805 for 491-498. The join says 774.

31 contacts carry a `bison_lead_id` and do NOT sit under a record attributed
to 491-498. This names which campaigns they sit under instead, so the number
that goes in the plan has a denominator that survives being asked about.
"""
import json
import os
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import boot  # noqa: E402

COHORT = set(range(491, 499))


def jsonl(path):
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                try:
                    yield json.loads(line)
                except ValueError:
                    continue


def main():
    camps = list(jsonl(boot.CAMPAIGNS))
    rec_to_camps = defaultdict(set)
    camp_rows = {}
    for c in camps:
        raw = str(c.get("bison_campaign_id") or "")
        if not raw.isdigit():
            continue
        cid = int(raw)
        camp_rows[cid] = c
        for r in c.get("record_ids") or []:
            rec_to_camps[str(r)].add(cid)

    pushed = 0
    in_cohort = 0
    elsewhere = Counter()
    unattributed = 0
    li_present = Counter()
    for rec in jsonl(boot.QUEUE):
        rid = str(rec.get("id"))
        cids = rec_to_camps.get(rid, set())
        for c in rec.get("contacts") or []:
            if not isinstance(c, dict) or not c.get("bison_lead_id"):
                continue
            pushed += 1
            if cids & COHORT:
                in_cohort += 1
            elif cids:
                elsewhere[tuple(sorted(cids))] += 1
            else:
                unattributed += 1
                li = str(c.get("linkedin") or "").lower()
                li_present["/in/" if "linkedin.com/in/" in li
                            else "not a profile url"] += 1

    print("contacts carrying bison_lead_id, store-wide :", pushed)
    print("  under a record attributed to 491-498      :", in_cohort)
    print("  under a record attributed ELSEWHERE       :", sum(
        elsewhere.values()))
    for k, n in elsewhere.most_common():
        print("      campaigns %-24s : %d" % (list(k), n))
    print("  under a record attributed to NO campaign  :", unattributed)
    print("      their linkedin shape                  :",
          ", ".join("%s=%d" % kv for kv in li_present.most_common()))
    print()
    print("campaign rows for 503/504/505, record_ids length:")
    for cid in (503, 504, 505):
        row = camp_rows.get(cid)
        if row is None:
            print("  %d : no campaign row in the store" % cid)
        else:
            print("  %d : record_ids=%d  status=%s  heyreach_campaign_id=%r"
                  % (cid, len(row.get("record_ids") or []),
                     row.get("status"), row.get("heyreach_campaign_id")))


if __name__ == "__main__":
    main()
