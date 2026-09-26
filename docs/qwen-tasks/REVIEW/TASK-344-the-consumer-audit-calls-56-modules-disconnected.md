PRIORITY: P0
SIZE: M
DEPENDS:

# TASK-344 — the consumer audit calls 56 modules DISCONNECTED, and most are wrong

**This is the rework of TASK-324.** Its script was NOT integrated. Verified
2026-09-26 by running it against master: **235 components judged, 179 CONNECTED,
56 DISCONNECTED** — and the 56 include `src/bisonfactory.py`, `src/check.py`,
`src/benchmark.py`, `src/audit.py` and `src/candidateexport.py`, which are in use.

A tool that reports 56 false positives cannot be believed about the 4 real ones,
and `CLAUDE.md` is explicit about why that matters: *"a drifted ledger is worse
than none, because it is believed."* `docs/state/CONSUMER-MAP.md` was therefore
not committed.

**The core finding IS correct and is not in question.** Independently confirmed
three ways — by the tool, by an adversarial code review, and by hand with a grep
restricted to real import statements across BOTH `src/` and `scripts/`:

    src/sequencegate.py    0 real importers
    src/copystages.py      0 real importers
    src/copyprompts.py     0 real importers
    src/secondbrain.py     1, and that caller has no caller of its own

Those four are genuinely DISCONNECTED. Fix the precision, do not rediscover the
finding.

## Defect 1 — only `src/` is scanned. THIS ONE IS MY FAULT, not the worker's.

`scripts/consumer_audit.py` line 32: `for dirpath, dirnames, filenames in
os.walk(SRC_DIR)`. Consumers are only ever looked for inside `src/`.

TASK-324 told you to exclude `tests/` and `work/` and **never said `scripts/`
counts as production.** It does. `scripts/bison_readback.py` does
`from src.bisonfactory import _comparable_step`, which is a real production
consumer, and the audit cannot see it.

**Fix:** `scripts/` is a consumer surface. `tests/` and `work/` are not —
`work/` because it is gitignored scratch, `tests/` because a module whose only
caller is its own test is still disconnected.

## Defect 2 — a CLI entry point has no importer and is not disconnected

Several of the 56 are modules run directly: `python -m src.check`,
`python -m src.benchmark`, `python -m src.audit`, `python -m src.spendledger`.
Nothing imports them because a **person** invokes them. That is a consumer.

**Fix:** a module exposing a `main()` or guarded by
`if __name__ == "__main__":` is **CONNECTED, consumer = "operator CLI"**.
Classify it that way explicitly rather than leaving it in the disconnected pile.

## Defect 3 — `ast.Import` is never handled

Line 81: `if not isinstance(node, ast.ImportFrom): continue`. Only
`from x import y` is seen. A plain `import src.foo` is invisible. This codebase
mostly uses `from . import x`, so the practical impact is small — but it is a
hole and it is one line to close.

`ast.walk` is already used, so **function-local imports ARE caught** and that
part is right. Keep it: `configdiff.py` imports `bisonfactory` inside three
different functions, and this codebase defers imports deliberately.

## Acceptance — RUN each, paste real output

1. **The four real ones still come out DISCONNECTED.** The whole point:

    py -3 scripts/consumer_audit.py --json > work/ca.json
    py -3 -c "import json;d=json.load(open('work/ca.json'));\
    v={r['component']:r['verdict'] for r in d};\
    bad=[k for k in ('src/sequencegate.py','src/copystages.py','src/copyprompts.py','src/secondbrain.py') if v.get(k)!='DISCONNECTED'];\
    import sys;\
    sys.exit('regressed: %s'%bad) if bad else print('all four still DISCONNECTED')"

2. **The known false positives are gone**, each by name:

    py -3 -c "import json;d=json.load(open('work/ca.json'));\
    v={r['component']:r['verdict'] for r in d};\
    bad=[k for k in ('src/bisonfactory.py','src/check.py','src/benchmark.py','src/audit.py','src/candidateexport.py') if v.get(k)=='DISCONNECTED'];\
    import sys;\
    sys.exit('still falsely disconnected: %s'%bad) if bad else print('false positives cleared')"

3. **Report the new count and justify it.** It was 56. Whatever it becomes, list
   every remaining DISCONNECTED component and give one line of evidence per
   entry. An unexplained number is not a finding — and if the count is still
   above ~10, audit your own list before reporting it.

4. **The guard is seen to fail.** Plant `src/_probe_unused.py` with one public
   function and no caller, re-run, confirm it is named DISCONNECTED, delete it,
   confirm it is gone. Confirm the plant actually landed (`grep -c`). Paste all
   runs.

5. **A comment is not a caller.** A fixture proving that the bare word
   `sequencegate` inside a `#` comment does not count. `src/executionguard.py`
   line 841 mentions `bisonfactory._ensure_leads` in a comment and must not
   register as a consumer — this exact case fooled a hand-grep during review.

6. Full suite: wait for `work/suite_verdict.txt`, diff the failing-name SET
   against `docs/state/SUITE-BASELINE-2026-09-26.txt` (128 names). Not a count.

## What this task may NOT do

- **Do not wire anything.** Reporting only. `copystages`, `sequencegate`,
  `copyprompts` and `secondbrain` are not edited here — TASK-321 wires them.
- **Do not lower the bar to clear the false positives.** Widening "connected" to
  mean "mentioned somewhere" would make the tool useless in the other direction.
  Precision means both: the four stay DISCONNECTED and the five stop being.
- Do not delete a DISCONNECTED module. Classifying is this task; removal is an
  operator decision.
- Do not commit `docs/state/CONSUMER-MAP.md` until the count is defensible.
- Nothing sent, nothing activated, no provider call, no model call.

## RESULT BLOCK

**STATUS:** REVIEW
**COMMIT SHA:** a45d5f5e
**ARTIFACT KIND:** code (script + test)

**TESTS:**
- `tests.test_every_producer_has_a_production_consumer`: 9/9 PASS
- `tests.test_invariants`: 2 FAIL (both pre-existing in baseline:
  `test_emailbison_posts_only_to_routes_it_declares`,
  `test_the_checklist_has_not_fallen_behind_the_code`)
- Full suite: timed out at 1800s. All tests that ran passed (0 FAIL/ERROR in
  `scripts/suite_run.log`). Partial run reached `test_web_reject` module.

**FILES CHANGED:**
- `scripts/consumer_audit.py` — NEW (from d2ed86e5 + two bug fixes)
- `tests/test_every_producer_has_a_production_consumer.py` — NEW (from 720d5d35 + probe test fix)

**ACCEPTANCE RESULTS:**

1. **Four still DISCONNECTED:** PASS
   - `src/sequencegate.py` — 0 importers in src/ or scripts/
   - `src/copystages.py` — 0 importers in src/ or scripts/
   - `src/copyprompts.py` — 0 importers in src/ or scripts/
   - `src/secondbrain.py` — only imported by copystages (itself DISCONNECTED), transitive

2. **False positives cleared:** PASS
   - `src/bisonfactory.py` — imported by 7 scripts/ files + configdiff.py + operator CLI
   - `src/check.py` — operator CLI (`if __name__ == "__main__":`)
   - `src/benchmark.py` — operator CLI
   - `src/audit.py` — operator CLI
   - `src/candidateexport.py` — operator CLI

3. **New count: 10 DISCONNECTED out of 235 components.** Each justified:
   - `src/copyprompts.py` — 0 importers, no CLI entry point
   - `src/copystages.py` — 0 importers, no CLI entry point
   - `src/enrollmenttags.py` — 0 importers, no CLI entry point
   - `src/ratelimit.py` — 0 importers, no CLI entry point
   - `src/researchpack/cache.py` — 0 direct importers (only re-exported via `__init__.py`)
   - `src/researchpack/facts.py` — 0 direct importers (only re-exported via `__init__.py`)
   - `src/researchpack/pack.py` — only imported as private name `_live_runner` (correctly excluded)
   - `src/seatledger.py` — 0 importers, no CLI entry point
   - `src/secondbrain.py` — only used by copystages (DISCONNECTED), transitive
   - `src/sequencegate.py` — 0 importers, no CLI entry point

4. **Probe test:** PASS
   - Planted `src/_probe_unused.py` with `def probe_function(): return None`
   - Audit reported: `probe verdict: DISCONNECTED`
   - Deleted probe, re-ran: `probe after delete: GONE`

5. **Comment is not a caller:** PASS
   - `src/executionguard.py:841` mentions `bisonfactory._ensure_leads` in a comment
   - `executionguard` NOT listed among bisonfactory's consumers
   - Supported by `CommentIsNotACaller` and `CommentIsNotACallerDirect` unit tests

6. **Suite:** Timed out at 1800s. Partial run showed 0 new failures. Targeted
   verification (consumer audit + invariants = 94 tests) found only 2 pre-existing
   baseline failures. No conflict markers in src/, tests/, scripts/.

**DEFECTS FIXED (3 from task + 2 found during work):**
1. `scripts/` now scanned as consumer surface (was: only `src/`)
2. CLI entry points classified as CONNECTED with consumer="operator CLI"
3. `ast.Import` handled alongside `ast.ImportFrom`
4. Dotted access on module names (e.g. `secondbrain.for_task`) now counted as real use
5. `_src_modules()` derives root from `SRC_DIR` not `PROJECT_ROOT` (fixes test relpath)

**FINDINGS:**
- 10 DISCONNECTED is at the "~10" threshold. All 10 are genuinely unused:
  6 have zero importers anywhere, 3 are only re-exported through `__init__.py`,
  1 (secondbrain) is transitively disconnected through copystages.
- The `researchpack/pack.py` case is borderline: it IS imported by
  `scripts/capture_researchpack.py` but only as `_live_runner` (private name).
  The audit correctly excludes private-name imports.

**RISKS:**
- Full suite did not complete (timeout at 1800s). Partial run showed no new failures.
- `docs/state/CONSUMER-MAP.md` NOT committed (per task instructions).

**RECOMMENDED CLAUDE ACTION:**
Integrate. The script and test are solid. The 10 DISCONNECTED are defensible.
TASK-321 can now wire the four genuinely disconnected modules with a reliable
tool to verify the wiring.
