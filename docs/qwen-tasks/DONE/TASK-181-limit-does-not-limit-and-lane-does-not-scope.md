PRIORITY: P1
DEPENDS:

# TASK-181 - two flags that do not mean what an operator reads them to mean

## WHERE THIS SITS

TASK-171 found both of these while explaining a run that did not add up. They
are small, they are in the operator's hand, and each one already caused a
wrong belief this morning.

    --limit 20   processed NINE records. The limit bounds the SCAN WINDOW,
                 not the work done. An operator bounding a risky run to 20
                 records has not bounded it to 20 records.

    --lane domains   does NOT scope the enrich or qualify stages at all.
                 Claude passed it and the run moved records in `drafted` and
                 `verified`, which are not in that lane. The transitions were
                 forward and harmless this time. That was luck.

Both matter more than their size because `--cap` is the flag that bounds SPEND,
and an operator who has learnt that `--limit` and `--lane` do not bound what
they appear to bound has no reason left to trust that `--cap` does.

## THE QUESTION

1. **`--limit`.** Read the handling in `src/run.py` and the selection
   predicates the stages apply. Establish exactly what it bounds today and
   where the nine came from against a limit of 20.
2. **Then decide what it should mean, and say why.** "Records processed" is the
   reading an operator has; "records scanned" is the implementation. One of
   them is a bug and the other is a documentation gap, and which it is depends
   on whether anything depends on the current behaviour. Check before choosing.
3. **`--lane`.** Establish which stages it scopes and which ignore it. Then
   make it scope enrich and qualify, or make the CLI refuse the combination it
   silently ignores. A flag that is accepted and ignored is worse than one that
   errors.
4. **Prove `--cap` does bound spend.** It is the only one of the three with
   money behind it, `enrich.require_cap` exists to refuse an unbounded spend,
   and after the other two findings it deserves a test rather than a reading.
   Write a test that spends over the cap and asserts the refusal, against a
   fake provider.
5. **Tests for all three**, and a line in the operator-facing help for each
   flag that says what it actually bounds.

## THE TRAP

Changing what `--limit` means changes what every recorded bounded run in this
repository actually did. TASK-163 measured five records with `--limit 5` and
Claude ran `--limit 20` and got nine. If you change the semantics, say plainly
in the deliverable that those recorded runs described a different flag, so
nobody reads an old result as if it were the new behaviour.

Second trap: do not make `--lane` scope a stage by filtering AFTER the stage
has already called a provider. Scoping that happens after the cost is not
scoping. Find where selection happens and scope there.

## WHAT YOU MAY NOT DO

- No provider writes, no paid provider calls, no credit spend. Every test here
  runs against a fake.
- Do not change what a stage DOES, only which records it selects and how many.
- Do not relax `enrich.require_cap`.
- Do not run a live stage over the estate - a full free run is already in
  flight and a second concurrent writer to `work/` is how state gets corrupted.
  If you need a measurement, use a copy.

## FILES ALLOWED

    src/run.py
    tests/test_run_flags.py   (new)
    docs/FLAG-SEMANTICS-2026-09-16.md   (new)

## FILES FORBIDDEN

    work/   config/   src/providerwrites.py

## DELIVERABLE

What each flag bounds today with the code path, the bug-or-docs verdict for
`--limit` with its reason, `--lane` either scoping or refusing, the cap test
that proves spend is bounded, and the help text for all three.

## RESULT

**STATUS:** DONE

**COMMIT SHA:** d41ed5c

**TESTS:** 30 tests in `tests/test_run_flags.py`, all green. 80 invariant
tests also green. Tests drive the real `run()` entry point, the real
`Budget` class, and the real `stage_enrich` entry point. `record_has_work`
is called from `run()` at line 368 - grep confirms the wiring.

**FILES CHANGED:**
- `src/run.py` - `record_has_work` function, lane filtering in `run()`,
  limit filtering via `record_has_work`, help text for all three flags
- `tests/test_run_flags.py` (new) - 30 tests across 4 classes
- `docs/FLAG-SEMANTICS-2026-09-16.md` (new) - full documentation of the
  findings and fixes

**FINDINGS:**

1. **`--limit` was a bug, not a docs gap.** The operator reads "process at
   most N records." The implementation scanned N and processed however many
   needed work. Nothing in the codebase depends on the scan-window
   semantics - the stages already skip done records, so the limit was
   double-counting the skip. Fixed: `record_has_work` filters to active
   records first, then the limit applies.

2. **`--lane` was a bug, not a docs gap.** Lane was only passed to
   `ingest.run()`. The processing stages received the full target list.
   Fixed: lane filtering now happens in `run()` before any stage runs.

3. **`--cap` was correct.** `enrich.require_cap` refuses unbounded spend.
   `enrich.Budget` refuses calls over the cap. `--cap 0` refuses unpriced
   calls too. 11 tests prove it through the real entry points.

4. **Impact on recorded runs:** Any previous run reporting "N records with
   `--limit M`" described the scan window. If M > active records, the real
   processing count was lower. TASK-163 measured five records with
   `--limit 5`; if any of the first 5 were already done, the real count
   was lower than 5.

**RISKS:** Changing `--limit` semantics means old recorded runs described
a different flag. The docs file states this plainly.

**RECOMMENDED CLAUDE ACTION:** Review the `record_has_work` predicate for
agreement with stage predicates. The qualify rework and personas unkeyed
second-predicates are the subtle ones.
