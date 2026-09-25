"""Lane R: the full gate sweep over 491-498, resumable, reads only.

    python scripts/laneR/sweep.py --limit 150        a bounded slice
    python scripts/laneR/sweep.py --all              the whole cohort

THE ORDER IS CHOSEN BY COST AND BY BLOCKING POWER. H1 runs FIRST here,
unlike `gates.py`, because it is one request and it excludes almost
everybody: asking the email side first spends an EmailBison read on people
the LinkedIn estate has already spoken for.

    H1  `/campaign/GetCampaignsForLead`   already in ANY LinkedIn campaign,
        ours or the client's -> EXCLUDE. A 404 is UNVERIFIABLE, and
        unverifiable is not a pass. (Contract checked: a well-formed profile
        that is not in the estate answers 404, and a real profile in nothing
        answers 0 campaigns - so neither a refusal nor an absence is being
        read as the other.)
    X1  `GET /leads/{id}`                 email membership in 491-498.
        `replied` -> EXCLUDE absolutely. `stopped` -> EXCLUDE: ISSUE-035,
        the word does not say whether we stopped them, they unsubscribed, or
        the provider stopped them ON A REPLY.
    M1  `/lead/GetLead`                   surname AND company must agree.
        Yields `linkedin_id`, the `leadMemberId` a future stop matches on,
        and its SHAPE is recorded - only numeric ids have ever been validated
        against `StopLeadInCampaign`.
    A1  `collision.check_account`         the client's own account rule.
        Recorded BOTH as shipped and person-scoped; see the doc.

Checkpointed every 25 people, so a run interrupted by rate limits or by the
end of the out-of-hours window resumes instead of re-spending.
"""
import argparse
import json
import os
import random
import re
import sys
import time
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import boot      # noqa: E402
import readonly  # noqa: E402
from gates import (ADMITTED, COHORT, DISQUALIFYING, PAIRABLE,  # noqa: E402
                   WORKSPACE, m1_verdict, norm)

OUT = os.path.join(boot.WORKTREE, "work", "laneR")
STATE = os.path.join(OUT, "sweep-state.json")


def shape(value):
    s = str(value or "")
    if not s:
        return "EMPTY"
    if re.fullmatch(r"\d+", s):
        return "numeric"
    if s.startswith("imp_"):
        return "imp_"
    if s.startswith("ACoAA"):
        return "ACoAA"
    return "other"


def person_key(row):
    """One contact's stable identity across resumed runs.

    `contact_key` is the store's own per-person key; the record id is the
    fallback and is NOT unique - 774 contacts sit under 681 records.
    """
    return "%s|%s" % (row.get("record_id"),
                      row.get("contact_key") or row.get("bison_lead_id"))


def load_state():
    if os.path.exists(STATE):
        with open(STATE, encoding="utf-8") as fh:
            return json.load(fh)
    return {"done": {}, "requests": 0}


def save_state(state):
    tmp = STATE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(state, fh, indent=1)
    os.replace(tmp, STATE)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=100)
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--seed", type=int, default=20260925)
    ap.add_argument("--pause", type=float, default=0.12)
    a = ap.parse_args()

    readonly.install(os.path.join(boot.PROD, "config", ".env"))
    readonly.selftest()
    print("seal ok: StopLeadInCampaign and AddLeadsToCampaignV2 refused "
          "before the first read.")

    from src.providers import bison, heyreach

    rows = json.load(open(os.path.join(OUT, "cohort-491-498.json"),
                          encoding="utf-8"))["rows"]
    pool = [r for r in rows if r["bison_lead_id"] and r["profile_url"]]
    random.Random(a.seed).shuffle(pool)

    state = load_state()
    done = state["done"]
    todo = [r for r in pool if person_key(r) not in done]
    if not a.all:
        todo = todo[:a.limit]
    print("cohort %d  already swept %d  this run %d\n"
          % (len(pool), len(done), len(todo)))

    for i, r in enumerate(todo, 1):
        # KEYED PER PERSON, NOT PER RECORD. 774 contacts sit under 681
        # records, so a record-id key silently collapses the 93 records that
        # hold more than one contact - the first 150-person run swept 150 and
        # reported 147, which is what that collapse looks like from outside.
        key = person_key(r)
        rec = {"record_id": r["record_id"], "domain": r["domain"],
               "contact_key": r.get("contact_key"),
               "profile_url": r["profile_url"],
               "bison_lead_id": r["bison_lead_id"],
               "verdict": "unverifiable"}

        # ---- H1 ---------------------------------------------------------
        try:
            camps, _t = heyreach.campaigns_for_lead(r["profile_url"])
        except Exception as exc:                        # noqa: BLE001
            rec["verdict"] = "excluded:H1_unverifiable"
            rec["detail"] = type(exc).__name__
            done[key] = rec
            continue
        rec["n_linkedin_campaigns"] = len(camps)
        if camps:
            rec["in_sequence_there"] = sum(
                1 for c in camps
                if str(c.get("leadStatus")) in heyreach.RUNNING_LEAD_STATUSES)
            rec["verdict"] = "excluded:H1_already_on_linkedin"
            done[key] = rec
            continue

        # ---- X1 ---------------------------------------------------------
        try:
            data = bison.lead(int(r["bison_lead_id"]))
            data = data.get("data") if isinstance(data.get("data"), dict) \
                else data
            entries = data.get("lead_campaign_data") or []
        except Exception as exc:                        # noqa: BLE001
            rec["verdict"] = "excluded:X1_unverifiable"
            rec["detail"] = type(exc).__name__
            done[key] = rec
            continue
        mine = [e for e in entries if str(e.get("campaign_id")) in COHORT]
        rec["cohort_statuses"] = sorted({norm(e.get("status")) for e in mine})
        rec["n_outside"] = len(entries) - len(mine)
        if not mine:
            rec["verdict"] = "excluded:X1_not_in_cohort"
            done[key] = rec
            continue
        bad = set(rec["cohort_statuses"]) & DISQUALIFYING
        if bad:
            rec["verdict"] = "excluded:X1_%s" % sorted(bad)[0]
            done[key] = rec
            continue
        if not set(rec["cohort_statuses"]) & PAIRABLE:
            rec["verdict"] = "excluded:X1_unknown_status"
            done[key] = rec
            continue

        # ---- M1 ---------------------------------------------------------
        try:
            prof = heyreach.lead_profile(r["profile_url"])
        except Exception as exc:                        # noqa: BLE001
            rec["verdict"] = "excluded:M1_unverifiable"
            rec["detail"] = type(exc).__name__
            done[key] = rec
            continue
        verdict, why = m1_verdict(r, prof)
        rec["m1"], rec["why"] = verdict, why
        rec["member_id"] = prof.get("linkedin_id")
        rec["member_id_shape"] = shape(rec["member_id"])
        if verdict != ADMITTED:
            rec["verdict"] = "excluded:M1_%s" % verdict
            done[key] = rec
            continue
        if not rec["member_id"]:
            rec["verdict"] = "excluded:M1_no_member_id"
            done[key] = rec
            continue
        rec["verdict"] = "passes:person_gates"
        done[key] = rec

        if a.pause:
            time.sleep(a.pause)
        if i % 25 == 0:
            state["requests"] = state.get("requests", 0) + readonly.total()
            save_state(state)
            print("  ... %d/%d swept, %d provider requests this run"
                  % (i, len(todo), readonly.total()))

    state["requests"] = state.get("requests", 0)
    save_state(state)

    v = Counter(x["verdict"] for x in done.values())
    print("\n=== cumulative, %d of %d people swept ===" % (len(done),
                                                           len(pool)))
    for k, c in v.most_common():
        print("  %-42s %4d   %5.1f%%" % (k, c, 100.0 * c / len(done)))

    survivors = [k for k, x in done.items()
                 if x["verdict"] == "passes:person_gates"]
    print("\n  survivors of the person gates : %d" % len(survivors))
    shapes = Counter(done[k].get("member_id_shape") for k in survivors)
    print("  their member_id shapes        : %s" % dict(shapes))
    doms = Counter(done[k]["domain"] for k in survivors)
    print("  distinct accounts behind them : %d" % len(doms))
    print("\n" + readonly.report())


if __name__ == "__main__":
    main()
