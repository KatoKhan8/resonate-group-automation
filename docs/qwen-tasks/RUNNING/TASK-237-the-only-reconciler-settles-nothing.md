PRIORITY: P1
DEPENDS:

# TASK-237 - the only reconciler can settle nothing, and the pool is growing

Priority P1. PROBLEM-REGISTER ISSUE-003. Buggie 2026-09-20, re-measured the
same evening.

## The defect

`scripts/reconcile_ledger.py` is the only thing that settles an action-ledger
reservation. It declares:

    CHECKABLE = ("heyreach.add_lead",)

and skips anything else:

    if operation not in CHECKABLE:
        continue

**Every stuck key is `bison.activate` or `heyreach.activate`.** So it
settles zero, every time it runs, and reports success doing it.

Nothing schedules it either, and the three live watch loops do not import
`actionledger` at all.

## Measured, and it is growing

    2026-09-20 morning (Buggie)    18 unresolved
    2026-09-20 evening             26 unresolved

    136 rows total: 64 attempted, 41 abandoned, 26 unresolved, 5 failed

## What it costs, stated precisely

**No confirmed touch exists for any of the fifteen people in 487 and 489.**
`_record_confirmed_touch` runs on settlement, and nothing settles. Fatigue
and reporting both read confirmed touches, so both are working from a record
of exposure that does not include anybody we have actually enrolled.

## What it does NOT cost, and do not re-litigate this

**An `unresolved` key cannot produce a duplicate send.** Three independent
refusals stop it - `require_clear`, `reserve` under the lock, and
`perform`'s ATTEMPTED-only check. Buggie attacked this specifically and it
held; it is REFUTED-001 in the problem register.

So this is a REPORTING and RECONCILIATION defect, not a safety hole. Fix it
as one. Do not add a guard against a duplicate that cannot happen.

## The objective

A reservation for an operation that can be checked against the provider gets
settled from provider truth, and one that cannot is reported as such rather
than skipped in silence.

Falsifiable requirements:

1. `bison.activate` and `heyreach.activate` are checkable: the reconciler
   asks the provider what the campaign's status and membership actually are
   and settles the key accordingly.
2. **A key it cannot settle is REPORTED, with the reason.** The current
   `continue` is the whole bug - a reconciler whose report says "0 settled,
   0 problems" while 26 keys rot is worse than one that does not run.
3. Settling an activate key writes the confirmed touch, and a test proves
   the touch appears for a lead in an activated campaign.
4. An operation genuinely outside the provider's ability to confirm settles
   to an explicit UNCONFIRMABLE state that says why - never to success.
5. The reconciler is idempotent: running it twice settles the same keys once
   and does not double-write a confirmed touch.

## Then, and only after the above passes

Say in the RESULT BLOCK what should schedule this and how often. **Do not
wire it into a watch loop in this task.** The watchers are live and
monitoring real campaigns; adding work to them is a separate decision with a
separate review.

## Hard limits

- **READ ONLY against the providers.** Settling reads status and membership;
  it never pauses, resumes, activates or attaches.
- Do not settle a key by assuming the action succeeded because it was
  attempted. The whole point is that provider truth decides.
- Do not delete or rewrite existing ledger rows. Append the settlement.

## Where to read first

`src/actionledger.py` (`reserve`, `settle`, `_record_confirmed_touch`),
`scripts/reconcile_ledger.py`, `src/providers/bison.py::campaign` and
`membership`, `src/providers/heyreach.py::campaign_status`, and
`work/BUGGIE-FINDINGS-2026-09-20.md` under P2 idempotency.

## Acceptance

All five requirements have tests; 1, 2 and 4 fail before the change; a dry
run against the real ledger reports what it WOULD settle and writes nothing.
