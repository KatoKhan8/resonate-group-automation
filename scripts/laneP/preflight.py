#!/usr/bin/env python3
"""LANE P preflight: the gates the cohort builder is NOT allowed to skip.

The four gates in `cohort.py` are about the PERSON: is this person in an
email campaign, in a LinkedIn campaign, and is this profile theirs. Three
more gates are about everything else, and each one has refused a real push in
this estate before:

  ACCOUNT    `collision.check_account` + `collision.account_policy`.
             The account is the unit of outreach here. A COLLEAGUE
             mid-sequence in one of the client's email campaigns is a fact
             about the company even when the person we picked is untouched -
             and on LinkedIn we could not stop them if that colleague replied.
             STOP and HOLD both drop the lead; only ALLOW survives, and
             `UNKNOWN` is a HOLD by the module's own rule.

  SUPPRESSION `agencydnc.lookup` plus the client's own suppression roster.
             The roster that matters is `config/suppress.local.txt`, which is
             gitignored because it is the live customer list; the tracked
             `config/suppress.txt` is a template and reading only that would
             be a check that watches nothing.

  SHAPE      `liststaging.validate_lead_row`. HeyReach answers 200 with
             `addedLeadsCount: 0` for a lead missing firstName or lastName.
             A 200 is not a staged lead.

READ ONLY. Writes a preflight report and a plan with the refused leads
removed; performs no provider write.

  py -3 scripts/laneP/preflight.py
"""
import argparse
import collections
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import boot  # noqa: E402

from src import collision, agencydnc, liststaging  # noqa: E402


def suppression_terms():
    """The client roster AND the agency template, both, lowercased."""
    terms = set()
    for name in ("suppress.local.txt", "suppress.txt"):
        path = os.path.join(boot.PROD, "config", name)
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip().lower()
                if line and not line.startswith("#"):
                    terms.add(line)
    return terms


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", default="ENROLLMENT-PLAN.json")
    ap.add_argument("--out", default="ENROLLMENT-PLAN-PREFLIGHT.json")
    ap.add_argument("--workspace",
                    default=os.environ.get("BISON_WORKSPACE_ID"))
    args = ap.parse_args(argv)

    plan = json.load(open(os.path.join(boot.OUT, args.plan), encoding="utf-8"))
    terms = suppression_terms()
    dnc_index = agencydnc.load()

    accounts, report = {}, []
    tally = collections.Counter()
    for co in plan["cohorts"]:
        for campaign in co["campaigns"]:
            keep = []
            for lead in campaign["leads"]:
                domain = str(lead.get("domain") or "").lower().strip()
                verdicts = {}

                # ---- SHAPE
                try:
                    liststaging.validate_lead_row(lead)
                    verdicts["shape"] = "ok"
                except Exception as exc:  # noqa: BLE001
                    verdicts["shape"] = f"refused: {str(exc)[:70]}"

                # ---- SUPPRESSION
                hit = None
                for value in (lead.get("company"), domain,
                              lead.get("linkedin_url")):
                    low = str(value or "").lower()
                    if low and any(t in low for t in terms if len(t) > 4):
                        hit = "suppression roster"
                        break
                found = agencydnc.lookup(lead, dnc_index)
                if found:
                    hit = "agency do-not-contact"
                verdicts["suppression"] = hit or "clear"

                # ---- ACCOUNT
                if not domain:
                    verdicts["account"] = ("HOLD: no domain, so the account "
                                           "question cannot be asked")
                else:
                    if domain not in accounts:
                        try:
                            answer = collision.check_account(
                                domain, expect_workspace=args.workspace)
                            accounts[domain] = collision.account_policy(answer)
                        except Exception as exc:  # noqa: BLE001
                            accounts[domain] = (
                                "HOLD", f"{type(exc).__name__}: "
                                        f"{str(exc)[:70]}")
                    decision, why = accounts[domain]
                    verdicts["account"] = f"{decision}: {why[:90]}"

                # `collision.ALLOW` is the lowercase word "allow". Comparing
                # against "ALLOW" dropped all fourteen leads on the first run
                # while the tally underneath reported eight allowed - a guard
                # that refuses everything is as useless as one that refuses
                # nothing, and this one said so in its own output.
                ok = (verdicts["shape"] == "ok"
                      and verdicts["suppression"] == "clear"
                      and verdicts["account"].lower().startswith(
                          collision.ALLOW.lower()))
                tally["kept" if ok else "dropped"] += 1
                if ok:
                    keep.append(lead)
                else:
                    tally[verdicts["account"].split(":")[0]] += 1
                report.append({"record_id": lead["record_id"],
                               "verdicts": verdicts, "kept": ok})
            campaign["leads"] = keep
            campaign["lead_count"] = len(keep)

    plan["preflight"] = {"kept": tally["kept"], "dropped": tally["dropped"]}
    plan["enrolled_if_executed"] = sum(c["lead_count"] for co in plan["cohorts"]
                                       for c in co["campaigns"])
    with open(os.path.join(boot.OUT, args.out), "w", encoding="utf-8") as f:
        json.dump(plan, f, indent=1)
    with open(os.path.join(boot.OUT, "PREFLIGHT-REPORT.json"), "w",
              encoding="utf-8") as f:
        json.dump(report, f, indent=1)

    print(json.dumps({
        "leads_in": tally["kept"] + tally["dropped"],
        "kept": tally["kept"],
        "dropped": tally["dropped"],
        "by_reason": tally.most_common(),
        "accounts_asked": len(accounts),
        "account_verdicts": collections.Counter(
            v[0] for v in accounts.values()).most_common(),
        "enrolled_if_executed": plan["enrolled_if_executed"],
    }, indent=1))


if __name__ == "__main__":
    main()
