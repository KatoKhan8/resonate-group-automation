#!/usr/bin/env python3
"""Apply the operator's CONTROL approval to the email cohort. Authorized.

    py -3 scripts/apply_control_approval.py            # dry run, changes nothing
    py -3 scripts/apply_control_approval.py --live      # write the approvals

WHY THIS FILE EXISTS. Claude Code's auto-mode classifier denies this session's
writes - provider calls and local state mutations alike. It is a harness
control, not a Resonate OS gate, and not something to work around. The operator
authorized the approval in writing (OPERATOR-AUTHORIZATION-2026-09-16.md), so
the work is packaged as one reviewed command.

WHAT IS AUTHORIZED. The EMAIL CONTROL sequence - `persona_pain ->
comparable_proof -> breakup` - for the cohort that survives the collision check
AND whose persona resolves. Not the other contacts. Not the 590 unapproved
steps elsewhere in the estate. Not a bulk mechanism.

THE COHORT IS TEN, and it took two corrections to get there:

  17  rendered by TASK-167, all passing lint and claims
  16  survive TASK-177's per-contact collision check (one domain had 13 prior
      emails at the provider - a real hit, caught by the check)
  11  have a resolved persona, so the angle is their own rather than the
      champion persona's finance default. Claude first reported this as 10 by
      subtracting one contact twice: the collision exclusion was itself one of
      the persona=None contacts.
  10  have an `em2` step at all. One record's cadence runs em1/em3/em5 with no
      em2, so CONTROL's in-thread follow-up cannot exist for it. Excluded
      rather than invented - a two-step CONTROL is not the CONTROL.

So ten, arrived at for a different reason than the ten first reported.

WHY THE STALE APPROVALS ARE REVOKED FIRST. TASK-210 replaced generated copy
with the audited CONTROL text on em1-em3 but left the old `approval.by:
"claude"` stamps behind on eleven steps. An approval carries a fingerprint of
the copy it was taken against, so a stamp left on replaced text is an approval
for a message that no longer exists. `approve.revoke` clears it; then
`approve.approve_step` takes a fresh one, fingerprinting the CONTROL copy that
is actually there.

`approval.by` is never set by hand here. `approve.approve_step` computes the
fingerprint, which is the whole point: an approval that does not match the copy
is detected by `approval.is_approved` rather than trusted.
"""
import argparse
import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import approve, clients, store                 # noqa: E402

MATCHED = os.path.join("work", "approval", "task210_matched.json")
STEPS = ("em1", "em2", "em3")
# The one record whose cadence has no em2. Hashed, so this file carries no PII.
EXCLUDE_REC_HASH = "9d2802e5f931"


def h12(value):
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:12]


def approver():
    """The operator's own address, read from git config rather than written
    here - the PII guard requires every email in a tracked file to be on a
    reserved domain, and an exception for the person who set the rule is not a
    rule. The attribution lands in work/queue.jsonl, which is gitignored."""
    import subprocess
    out = subprocess.run(["git", "config", "user.email"],
                         capture_output=True, text=True).stdout.strip()
    if not out:
        raise SystemExit("REFUSED: git config user.email is unset, so the "
                         "approval would be attributed to nobody.")
    return f"{out} (operator authorisation 2026-09-16)"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--live", action="store_true",
                        help="write the approvals; omit for a dry run")
    args = parser.parse_args(argv)

    if not os.path.exists(MATCHED):
        raise SystemExit(f"REFUSED: {MATCHED} is missing. It is TASK-210's "
                         f"cohort record and lives outside git because it "
                         f"names real contacts. Re-run "
                         f"scripts/task210_identify.py.")
    matched = json.load(open(MATCHED, encoding="utf-8"))
    want = {(m["record_id"], m["contact_key"]) for m in matched}

    by = approver()
    config = clients.load("productive")
    recs = store.load()

    plan, refusals = [], []
    for rec in recs:
        if h12(rec["id"]) == EXCLUDE_REC_HASH:
            continue
        for contact in rec.get("contacts") or []:
            if (rec["id"], contact.get("key")) not in want:
                continue
            cadence = (rec.get("cadence") or {}).get(contact.get("key")) or {}
            for step_key in STEPS:
                step = cadence.get(step_key)
                if not step:
                    refusals.append(
                        f"{h12(rec['id'])}/{step_key}: step does not exist")
                    continue
                if not (step.get("subject") and step.get("body")):
                    refusals.append(
                        f"{h12(rec['id'])}/{step_key}: no subject or body")
                    continue
                # EVERY GATE, ASKED BEFORE ANYTHING IS WRITTEN. why_not covers
                # verification, collision, tenancy, fatigue, caps and the
                # claims/lint verdicts for this step.
                why = approve.why_not(rec, contact.get("key"), step_key,
                                      config=config)
                if why:
                    refusals.append(f"{h12(rec['id'])}/{step_key}: {why}")
                    continue
                prior = (step.get("approval") or {}).get("by")
                plan.append((rec, contact.get("key"), step_key,
                             prior if prior and prior != by else None))

    contacts = len({(id(r), ck) for r, ck, _s, _p in plan})
    stale = [p for p in plan if p[3]]
    print(f"cohort          {contacts} contacts, {len(plan)} steps")
    print(f"approver        {by.split('(')[0].strip()[:3]}... "
          f"(operator authorisation 2026-09-16)")
    print(f"stale to revoke {len(stale)}")
    if refusals:
        print(f"REFUSALS        {len(refusals)}")
        for line in refusals:
            print(f"  - {line}")

    if len(plan) != 30:
        print(f"\nREFUSED: expected 30 steps (10 contacts x 3), planned "
              f"{len(plan)}. The cohort or the copy has moved since TASK-210. "
              f"Nothing was written.")
        return 2

    if not args.live:
        print("\nDRY RUN: every gate passed and nothing was written.")
        print("Re-run with --live to apply the operator's approval.")
        return 0

    revoked = approved = 0
    for rec, contact_key, step_key, prior in plan:
        if prior:
            approve.revoke(rec, contact_key, step_key,
                           why="copy replaced with the audited CONTROL text")
            revoked += 1
        approve.approve_step(rec, contact_key, step_key, by=by, config=config)
        approved += 1
    store.save(recs)

    print(f"\nstale approvals revoked : {revoked}")
    print(f"steps approved          : {approved}")
    print("\nRead back with:")
    print("  py -3 scripts/apply_control_approval.py      # dry run reports 0 "
          "stale and 30 steps already approved")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
