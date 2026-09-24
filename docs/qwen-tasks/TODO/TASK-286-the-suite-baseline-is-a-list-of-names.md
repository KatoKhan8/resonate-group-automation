PRIORITY: P1
DEPENDS:

# TASK-286 — the suite baseline is a list of names, or it is nothing

## The question this answers

**Which tests fail at tonight's master, by name — and which of those are new
since 2026-09-23?**

Not how many. **A baseline that is a COUNT cannot answer the only question
worth asking of it.** `74 failures` and `74 failures` compare equal while a
different 74 tests fail, and that is not hypothetical here: the 2026-09-23
host comparison found **17 host-only failures and 0 local-only ones behind two
counts that differed by exactly 17.** A count says something changed. Only a
set of names says WHAT.

`scripts/suite_baseline.py` already measures names and diffs sets. The last
baselines are `docs/state/SUITE-BASELINE-2026-09-23.json` (74 entries at
`dc395fa1` on `infra`, 11,738 tests) and `-MERGED.json`. Tonight master took
the write ledger, the sealed resume verb, one log per watcher, the slack agent
(researchpack + copylint), `EMAIL_RESUME` into SUPPORTED, `testidentity`, the
forward-book ceiling, four register rows and four cadence templates. **Nobody
has measured the suite since.**

## What to do

1. `py -3 scripts/suite_baseline.py --measure --out
   docs/state/SUITE-BASELINE-2026-09-25.json` at a **clean tree**, at a named
   commit. The script refuses a dirty tree, and that refusal is correct —
   a baseline measured against uncommitted work describes nothing anybody can
   return to. Commit first, then measure.
2. Both passes: **full** (one process, `python -m tests.offline`) and
   **standalone** (each module in its own process). They answer different
   questions, and both must be taken at the SAME commit.
3. `--diff docs/state/SUITE-BASELINE-2026-09-23.json <new>` and report the
   diff **BOTH DIRECTIONS**:

       gone      in 09-23, not in 09-25   (fixed, or no longer collected)
       new       in 09-25, not in 09-23   (a regression, until proved not)
       common    in both

   A one-directional diff hides exactly the case that matters.
4. **Normalise both sides the same way.** On 2026-09-23 the host's failing
   names were passed through the host-value redactor and the local ones were
   not, so every test whose name contains the app username appeared in BOTH
   "host-only" and "local-only". It looked like a divergence and it was a
   measurement artifact. Use `--redact-map`, or state that both sides were
   already normalised identically and how you checked.
5. For **every** name in `new`: say whether it is a real regression, and from
   which of tonight's merges. A new failure with no attribution is not
   triaged, it is listed.
6. Report the order-dependence set: tests that pass in `full` and fail
   standalone, and the reverse. The second class is worse — it will pass
   forever until somebody runs it alone.

Write `docs/state/SUITE-BASELINE-2026-09-25.json` and a short
`docs/SUITE-BASELINE-2026-09-25.md` narrating the diff.

## The acceptance bar

- Both JSONs carry `measured_at_commit`, and it is the same commit for the
  full and standalone passes. If they differ, the diff is void.
- The `new` and `gone` sets are printed **as names**, complete, not truncated
  with "and 12 more".
- Every `new` name is attributed to a merge, or explicitly marked
  UNATTRIBUTED with what was tried.
- `total_entries`, `distinct_tests` and the length of the names list agree. If
  they do not, the parser dropped something.
- `tests_run` is reported and compared to 11,738. A suite that collected far
  fewer tests did not run — that is the finding, not a clean baseline.

## What evidence counts

- `suite_verdict.txt` / the runner's real exit code. **Never** pipe a test run
  into a filter and read the filter's exit code — three "green" runs meant
  nothing here for exactly that reason.
- **Do not grep for `^FAIL:` mid-run.** A running suite shows no failures; the
  grep returns 0 and means nothing. Wait for the verdict file.
- The JSON diff output, pasted.
- The wall-clock: the full suite is about 865 seconds and was marginal against
  a 900-second watchdog. A run that "finished" in 90 seconds collected
  nothing.

## WHAT WOULD MAKE THIS A FALSE PASS

- **Reporting a count.** "74, same as last time" is the defect this task
  exists to end. If your result block has a number and no set, it is rejected.
- **Diffing one direction.** Both, named, in the result block.
- **Measuring on a dirty tree with `--allow-dirty`** because the refusal was
  inconvenient. Commit, then measure.
- **Asymmetric normalisation** producing phantom entries in both directions.
  If a name appears in both `new` and `gone`, suspect the redactor before you
  believe the suite.
- **One pass instead of two.** Full and standalone answer different questions
  and the order-dependence report is the difference between them.
- **A suite that crashed being read as a baseline.** Report the exit code and
  `tests_run`.
- Running two test processes at once. **This machine has already died from a
  runaway `unittest` process** — memory, not context. One at a time, with a
  gap between `discover` and `tests.offline`.

## Boundaries

- One test process at a time. Cap the full-suite run at ONE pass.
- Commit and push before starting a long run, so the run is the only thing at
  risk.
- No provider calls of any kind.

## Files

    ALLOWED    docs/state/SUITE-BASELINE-2026-09-25.json,
               docs/SUITE-BASELINE-2026-09-25.md
    FORBIDDEN  src/*, tests/* (do not fix a failing test in this task —
               name it), work/*, config/.env

This task MEASURES. Fixing a failure it finds is a separate task.

## Result block

    BRANCH:
    COMMIT MEASURED AT (and: was the tree clean?):
    RUNNER EXIT CODE / VERDICT FILE:
    tests_run (vs 11,738) / failures / errors / distinct:
    WALL CLOCK:
    NEW SINCE 09-23 (full list of names):
    GONE SINCE 09-23 (full list of names):
    ATTRIBUTION FOR EACH NEW NAME:
    ORDER-DEPENDENT (full-only) / (standalone-only):
    NORMALISATION: redact-map used, or how symmetry was checked:
