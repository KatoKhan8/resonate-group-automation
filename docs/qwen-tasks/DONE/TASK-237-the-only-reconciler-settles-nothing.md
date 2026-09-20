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

## RESULT BLOCK

STATUS: DONE
COMMIT SHA: 4902c207
TESTS: 15 new tests in tests/test_the_reconciler_settles_from_provider_truth.py,
  all pass. 171 related tests across 6 modules pass (1 expected failure,
  pre-existing).

FILES CHANGED:
  - src/actionledger.py: Added UNCONFIRMABLE state (terminal, settled,
    unreservable). Added to settle()'s valid states.
  - scripts/reconcile_ledger.py: Rewritten. Added _check_heyreach_activate
    and _check_bison_activate checkers. Unknown operations settle to
    UNCONFIRMABLE with reason. SENT settlements write confirmed touch.
  - tests/test_the_reconciler_settles_from_provider_truth.py: New, 15 tests
    covering all 5 requirements.

FINDINGS:
  1. The `continue` in the old reconciler was the whole bug. It silently
     skipped any operation not in CHECKABLE, reporting "0 settled, 0 problems"
     while 26 keys rotted. Fixed by replacing `continue` with UNCONFIRMABLE
     settlement.
  2. `_record_confirmed_touch` lives in providerwrites.py, not actionledger.py
     as the task doc suggested. The reconciler constructs a minimal
     Authorization from the ledger row to call it.
  3. Bison identifies leads by email, not LinkedIn URL. Added _email_for()
     helper alongside the existing _profile_for().
  4. UNCONFIRMABLE is terminal (like SENT): it cannot be regressed to SENT
     later, and it blocks re-reservation. This is the right direction - an
     operation that genuinely cannot be confirmed should never read as success.

SCHEDULING RECOMMENDATION (not wired in this task):
  The reconciler should run on a cron schedule, not inside a watch loop.
  Watch loops monitor live campaigns and adding reconciliation work to them
  is a separate decision. A daily cron at a quiet hour (e.g. 03:17 local)
  is sufficient - the keys being settled are already stuck, so urgency is
  low. `py -3 scripts/reconcile_ledger.py --live --by reconciler-cron` is
  the command. The dry-run form should run in CI on every commit.

RISKS:
  - The reconciler makes live provider reads. If the provider is slow or
    rate-limited, the run will be slow. Not a safety issue (it is read-only)
    but an operational one.
  - _record_touch_for constructs an Authorization from ledger row data. If
    the record has been deleted or the step is missing, the touch write will
    fail. The reconciler catches and reports this without failing the run.

RECOMMENDED CLAUDE ACTION:
  Review the UNCONFIRMABLE state addition to actionledger.py. It is terminal,
  which means a key settled to UNCONFIRMABLE can never be re-reserved or
  regressed to SENT. This is the right direction but is a new state that
  other modules may need to handle (e.g. reporting, fatigue counts).
