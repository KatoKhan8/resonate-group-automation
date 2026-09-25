"""Lane R step 1: VERIFY the handed population against the production store.

The brief hands three figures and says do not re-derive, do verify:

    491-498      805 store contacts carrying a bison_lead_id
    491-498      805 of those also carrying a `linkedin` field
    503/504/505  690 leads, ZERO with any LinkedIn field

Nothing here touches a provider. It prints counts and writes no names to
stdout; the per-person rows go to work/laneR/ which is gitignored.
"""
import json
import os
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import boot  # noqa: E402

EMAIL_COHORT = [str(n) for n in range(491, 499)]      # 491..498
OUT_OF_SCOPE = ["503", "504", "505"]
OUT = os.path.join(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))), "work", "laneR")

LINKEDIN_KEYS = ("linkedin", "linkedin_url", "linkedin_profile",
                 "profile_url", "linkedin_slug")


def records():
    with open(boot.QUEUE, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except ValueError:
                continue


def contacts_of(rec):
    for c in rec.get("contacts") or []:
        if isinstance(c, dict):
            yield c


def campaign_ids(contact):
    """Every campaign id this contact is recorded against, as strings."""
    out = set()
    for key in ("campaign_id", "campaign", "bison_campaign_id",
                "campaign_id_email", "email_campaign_id"):
        v = contact.get(key)
        if v not in (None, "", []):
            out.add(str(v))
    for ev in contact.get("events") or []:
        if isinstance(ev, dict):
            v = ev.get("campaign_id") or ev.get("campaign")
            if v not in (None, "", []):
                out.add(str(v))
    return out


def linkedin_of(contact):
    for k in LINKEDIN_KEYS:
        v = contact.get(k)
        if isinstance(v, str) and v.strip():
            return k, v.strip()
    return None, None


def main():
    os.makedirs(OUT, exist_ok=True)
    seen_keys = Counter()
    by_campaign = defaultdict(list)
    rec_state = Counter()
    rows = []
    n_rec = n_contact = 0

    for rec in records():
        n_rec += 1
        for c in contacts_of(rec):
            n_contact += 1
            for k in c.keys():
                seen_keys[k] += 1
            cids = campaign_ids(c)
            hit = cids & (set(EMAIL_COHORT) | set(OUT_OF_SCOPE))
            if not hit:
                continue
            lk, lv = linkedin_of(c)
            row = {
                "record_id": rec.get("id"),
                "domain": rec.get("domain"),
                "contact_key": c.get("key") or c.get("contact_key")
                or c.get("email"),
                "campaigns": sorted(cids),
                "cohort": sorted(hit),
                "bison_lead_id": c.get("bison_lead_id"),
                "heyreach_lead_id": c.get("heyreach_lead_id"),
                "linkedin_field": lk,
                "linkedin_value": lv,
                "record_state": rec.get("state") or rec.get("status"),
                "contact_state": c.get("state") or c.get("status"),
                "title": c.get("title"),
                "n_events": len(c.get("events") or []),
            }
            rows.append(row)
            for cid in sorted(hit):
                by_campaign[cid].append(row)
            rec_state[str(row["record_state"])] += 1

    print("records read              :", n_rec)
    print("contacts read             :", n_contact)
    print()
    print("contact keys most common  :",
          ", ".join("%s=%d" % kv for kv in seen_keys.most_common(24)))
    print()

    def report(label, ids):
        sub = [r for r in rows if set(r["cohort"]) & set(ids)]
        with_bison = [r for r in sub if r["bison_lead_id"]]
        with_li = [r for r in sub if r["linkedin_value"]]
        both = [r for r in sub if r["bison_lead_id"] and r["linkedin_value"]]
        with_hr = [r for r in sub if r["heyreach_lead_id"]]
        print("%-14s contacts in cohort      : %d" % (label, len(sub)))
        print("%-14s carrying bison_lead_id  : %d" % ("", len(with_bison)))
        print("%-14s carrying a linkedin fld : %d" % ("", len(with_li)))
        print("%-14s carrying BOTH           : %d" % ("", len(both)))
        print("%-14s carrying heyreach_lead_id: %d" % ("", len(with_hr)))
        per = Counter()
        for r in sub:
            for cid in r["cohort"]:
                if cid in ids:
                    per[cid] += 1
        print("%-14s per campaign            : %s" % (
            "", ", ".join("%s=%d" % kv for kv in sorted(per.items()))))
        print()
        return sub, both

    c491, pop = report("491-498", EMAIL_COHORT)
    report("503/504/505", OUT_OF_SCOPE)

    print("record states across the cohort:",
          ", ".join("%s=%d" % kv for kv in rec_state.most_common()))

    path = os.path.join(OUT, "population-491-498.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump({"cohort": EMAIL_COHORT, "n": len(pop), "rows": pop},
                  fh, indent=1)
    print("\nwrote", path, "with", len(pop), "rows (gitignored)")


if __name__ == "__main__":
    main()
