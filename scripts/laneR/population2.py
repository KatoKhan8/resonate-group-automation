"""Lane R step 1b: where does campaign membership actually live?

`population.py` found ZERO contacts carrying any email campaign id, against a
brief that names 491-498 as the population. So the cohort boundary is not a
field on the contact. This asks the two stores what they do hold.
"""
import json
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import boot  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))), "work", "laneR")


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
    os.makedirs(OUT, exist_ok=True)

    print("=== campaigns.jsonl ===")
    camps = list(jsonl(boot.CAMPAIGNS))
    print("rows:", len(camps))
    keys = Counter()
    for c in camps:
        for k in c:
            keys[k] += 1
    print("keys:", ", ".join("%s=%d" % kv for kv in keys.most_common()))
    print()
    hdr = ("provider_campaign_id", "channel", "status", "name", "client")
    for c in camps:
        vals = []
        for h in hdr:
            v = c.get(h)
            if h == "name" and isinstance(v, str):
                v = "<name redacted, %d chars>" % len(v)
            vals.append(str(v))
        n_members = 0
        for mk in ("contacts", "leads", "members", "contact_keys"):
            if isinstance(c.get(mk), list):
                n_members = max(n_members, len(c[mk]))
        print(" | ".join(vals), "| members=", n_members)

    print()
    print("=== contacts: linkedin field truthiness ===")
    tot = nonempty = has_bison = both = 0
    li_shapes = Counter()
    for rec in jsonl(boot.QUEUE):
        for c in rec.get("contacts") or []:
            if not isinstance(c, dict):
                continue
            tot += 1
            li = c.get("linkedin")
            ok = isinstance(li, str) and li.strip() != ""
            if ok:
                nonempty += 1
                s = li.strip().lower()
                if "linkedin.com/in/" in s:
                    li_shapes["/in/ slug"] += 1
                elif "linkedin.com/company" in s:
                    li_shapes["company page"] += 1
                elif s.startswith("http"):
                    li_shapes["other http"] += 1
                else:
                    li_shapes["bare/other"] += 1
            else:
                li_shapes["EMPTY/absent"] += 1
            if c.get("bison_lead_id"):
                has_bison += 1
                if ok:
                    both += 1
    print("contacts                       :", tot)
    print("linkedin non-empty             :", nonempty)
    print("carrying bison_lead_id         :", has_bison)
    print("BOTH bison_lead_id + linkedin  :", both)
    print("linkedin value shapes          :",
          ", ".join("%s=%d" % kv for kv in li_shapes.most_common()))


if __name__ == "__main__":
    main()
