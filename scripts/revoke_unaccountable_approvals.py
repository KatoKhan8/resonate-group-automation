"""Revoke the approvals that were never approvals, explicitly and with a reason.

OPERATOR INSTRUCTION, 2026-10-02: "49 odobrenja pod zvonimir@example.test i 12 pod
'claude' nisu odobrenja: poništi ih eksplicitno s razlogom u zapisu."

THE COUNTS IN THAT INSTRUCTION CAME FROM MY OWN PARTIAL MEASUREMENT and are
low: I had counted `em1` only. Across all steps the real figures are 147 under
`zvonimir@example.test` and 73 under `claude` - 220 stamps on 55 records. The
operator named the two IDENTITIES, so the identities are the criterion and the
counts are corrected here rather than used as a limit.

WHAT EACH ONE IS, MEASURED, because the two are not the same problem:

* `claude` - `approval.is_accountable_approver("claude")` is already **False**, so
  these 73 stamps are already inert. Removing them makes an implicit refusal
  explicit; it changes no send decision.
* `zvonimir@example.test` - `is_accountable_approver` returns **True** and
  `personally_reviewed` returns **True**. `_looks_like_an_address` checks only the
  SHAPE `local@domain.tld`, so a reserved-TLD address that can never receive mail
  passes as an accountable human who read the copy. These 147 are a real hole.

HOW THE REVOCATION IS WRITTEN. The stamp is MOVED to `approval_revoked` and the
`approval` key is deleted, rather than annotated in place. Two reasons, and the
first is the one that matters: a revocation that leaves `fingerprint` where
`is_approved` reads it would come back the moment the sender-binding rule is ever
relaxed, and a revocation that can be undone by a future refactor is a note, not a
revocation. Second, `eligibility` then reports `held:draft_not_approved` instead of
`held:approval_stale`, which is the true statement - there is no approval.

Nothing is deleted: the original stamp survives under `approval_revoked` with the
reason beside it, because an audit that loses what it revoked cannot be checked.
"""
import datetime
import json
import os
import sys

sys.path.insert(0, os.getcwd())

from src import approval, store                                  # noqa: E402

STEPS = ("em1", "em2", "em3", "em4", "em5",
         "day1", "day3", "day7", "day15", "day30", "li1")

REVOKED_BY = "zvonimir@resonategroup.co (operator instruction 2026-10-02)"

REASONS = {
    "test-address": (
        "revoked: approved under zvonimir@example.test, a reserved-TLD address "
        "that can never receive mail. approval.is_accountable_approver accepted "
        "it as an accountable approver and approval.personally_reviewed as a "
        "human who read the copy, because _looks_like_an_address checks only the "
        "shape local@domain.tld. Nobody can be held to this approval."),
    "bare-token": (
        "revoked: approved by the bare token 'claude', which "
        "approval.is_accountable_approver already refuses, so the stamp was "
        "already inert. Removed so the record says so rather than relying on a "
        "reader to know."),
}


def classify(who):
    head = str(who or "").split("(", 1)[0].strip().lower()
    if "example.test" in head:
        return "test-address"
    if head == "claude":
        return "bare-token"
    return None


def main():
    dry = "--apply" not in sys.argv
    now = datetime.datetime.now(datetime.timezone.utc).isoformat(
        timespec="seconds")
    touched = []

    def walk(recs):
        for rec in recs:
            cadence = rec.get("cadence") or {}
            for contact_key, steps in cadence.items():
                if not isinstance(steps, dict):
                    continue
                for step_key in STEPS:
                    step = steps.get(step_key)
                    if not isinstance(step, dict):
                        continue
                    stamp = step.get("approval")
                    if not isinstance(stamp, dict):
                        continue
                    kind = classify(stamp.get("by"))
                    if not kind:
                        continue
                    yield rec, contact_key, step_key, step, stamp, kind

    if dry:
        recs = store.load()
        for rec, ck, sk, step, stamp, kind in walk(recs):
            touched.append((rec.get("id"), ck, sk, kind, stamp.get("by")))
        print(f"  DRY RUN: {len(touched)} stamps would be revoked on "
              f"{len({t[0] for t in touched})} records")
        by_kind = {}
        for t in touched:
            by_kind[t[3]] = by_kind.get(t[3], 0) + 1
        for k, n in sorted(by_kind.items()):
            print(f"    {n:5d}  {k}")
        print("  pass --apply to write")
        return 0

    with store.transaction() as recs:
        for rec, ck, sk, step, stamp, kind in walk(recs):
            revoked = dict(stamp)
            revoked["revoked_at"] = now
            revoked["revoked_by"] = REVOKED_BY
            revoked["revoked_reason"] = REASONS[kind]
            step["approval_revoked"] = revoked
            del step["approval"]
            touched.append((rec.get("id"), ck, sk, kind, stamp.get("by")))
    print(f"  WROTE: {len(touched)} stamps revoked on "
          f"{len({t[0] for t in touched})} records")

    # READBACK, against the file rather than the objects just written.
    fresh = store.load()
    left = 0
    revoked_found = 0
    for rec in fresh:
        for ck, steps in (rec.get("cadence") or {}).items():
            if not isinstance(steps, dict):
                continue
            for sk in STEPS:
                step = steps.get(sk)
                if not isinstance(step, dict):
                    continue
                stamp = step.get("approval")
                if isinstance(stamp, dict) and classify(stamp.get("by")):
                    left += 1
                r = step.get("approval_revoked")
                if isinstance(r, dict) and r.get("revoked_reason"):
                    revoked_found += 1
    print(f"  READBACK: {left} unaccountable stamps remain (must be 0), "
          f"{revoked_found} carry a revocation reason")
    return 0 if left == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
