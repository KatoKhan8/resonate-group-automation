# TASK-270 — Lead-recovery levers: the lever is an angle, and it must never be stored

SIZE: M
DEPENDS ON: TASK-247 (three lanes for the estate we already touched)
Operator instruction, 2026-09-23: levers `fresh_face`, `value_first`,
`trigger`, `close` for the re-engagement lane; assign per account from history
and signals; report the split.

## MOST OF THIS ALREADY EXISTS UNDER A DIFFERENT WORD

"Lever" does not exist in this tree. **"Angle" does**, and `src/revival.py`
already answers the question the instruction is asking:

    angles_used(rec)            :146   every angle this account has ACTUALLY
                                       been written with, from confirmed
                                       touches
    angles_available(config)    :161   the client's angle vocabulary
    assess(rec, ...)            :255   NEVER / NOT_YET / NOTHING_NEW / READY
    last_touch(rec)             :135

Its docstring already states the rule the instruction implies: *"Reviving
with the angle that already failed is a repeat."* **A lever assigned without
reading `angles_used` does exactly that**, which is the first thing to get
right and the first required test.

Build on `revival.py`. Do not write a parallel history reader — `src/account.py`
is the canonical account-level accessor (`touches()` :107, `replies()` :149,
`graph()` :267, `timeline()` :375) and a second opinion about what counts as
a touch is how two numbers drift.

## RECOMMEND, DO NOT ASSIGN

`src/playbooks.py` is the account-level play library — `LIBRARY` :104-197,
`recommend()` :302 — and its docstring is explicit: *"It recommends; it does
not assign."* Its only consumers are read-only web surfaces.

That is the A/B/C boundary of TASK-266 showing up again. **The lever is a
recommendation carrying its reason**, not a field that steers a send. If a
lever ever steers copy it arrives through an approved rule, not from here.

## THE TRAP, MEASURED, TWICE

**1. A lane is a function of live provider status and must NEVER be
persisted.** `tests/test_a_reengagement_lane_is_not_a_stored_value.py`
records that on 2026-09-22 the **stored** lane read `REENGAGE 0 / NEVER 1360`
while the live computation read `REENGAGE 985 / NEVER 89`. Same estate, same
moment, two answers, and the stored one was confidently wrong about 985
accounts.

**2. There is already a `lane` field and it is dead.** `store.LANES` is
`("revive", "cold", "domains")` (:28), validated at `new_record()` :1574 and
at `store.validate()` :1613, assigned by CLI argument only
(`ingest.py:226`, `run.py:483`, `web/upload.py:542`). **All 1,542 records in
`work/queue.jsonl` are `domains`.** Declared, validated, filterable, unused.

Do not write the lever onto the record. Compute it, report it, and let the
caller hold it for the length of one answer.

## AND THE LANE IT DEPENDS ON IS NOT IN `src/` YET

The only working classifier is `scripts/reengagement_inventory.py`
`lane_for(row, now, campaign_status)` :177, with `REENGAGE_AFTER_DAYS = 90`
:94. Its `src/` home is **TASK-247, still TODO**. This task is sequenced
after it: a lever assigned to a lane that is computed two different ways in
two places will disagree with itself.

If TASK-247 is still TODO when this is picked up, **say so and stop** — write
the boundary into FINDINGS and take the next task. Do not inline a third copy
of `lane_for`.

## THE FOUR LEVERS

    fresh_face    a sender this account has not seen. Needs the sender
                  history, which account.touches() carries.
    value_first   lead with something useful rather than an ask.
    trigger       a specific, dated, external event. REFUSE this lever
                  when there is no evidence row behind it - a trigger
                  without a trigger is the "scored above threshold" bug
                  in another costume (see TASK-272).
    close         only where the history supports it.

Each recommendation carries **the evidence rows it rests on**, the same way
`revival.assess` does. A lever with no evidence is not returned.

## REPORT THE SPLIT

Per lever, per lane, with the denominator named. **Under 30 accounts in a
cell prints the count and refuses the percentage** — the rule TASK-246
already sets for the learning report, for the same reason.

## ACCEPTANCE

Full offline suite, zero new failures and zero new errors against the master
baseline, diffed by test NAME both directions.

Required tests: an angle already used is never recommended again for the same
account; `trigger` is refused with no evidence row; **nothing writes a lever
onto a record** (assert the store round-trips unchanged); a lane computed
here equals `lane_for`'s answer for the same input; an under-30 cell refuses
its percentage; a recommendation carries its evidence.

## FILES FORBIDDEN

    src/clientapproval.py    src/providers/*    config/    work/*.jsonl
    src/executionguard.py
