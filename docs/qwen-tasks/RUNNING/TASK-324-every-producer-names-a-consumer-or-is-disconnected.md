PRIORITY: P0
SIZE: M
DEPENDS:

# TASK-324 — every producer names a consumer, or is DISCONNECTED

**Source: `docs/OPERATOR-DIRECTIVES-2026-09-26-PHASE1.md` §1, standing policy.**
No intelligence component is complete because it researches, extracts, stores,
scores, indexes, creates provenance, or exposes a function. **Every producer
must have a named production consumer.** A component with zero production
callers is classified `DISCONNECTED` — it is not quietly reimplemented.

This task makes that rule executable, so a sixth disconnected module cannot be
merged. It does **not** wire anything up: it measures, classifies, and refuses.
Wiring is TASK-321's, and inventing a parallel implementation is forbidden.

## What is already known, and must come out of your run as DISCONNECTED

Verified on master at `4268197a`, so your tool must reproduce these or explain
why the finding is stale:

    src/secondbrain.py     `for_task` has ZERO callers. GLM found it, the
                           handoff §6 confirmed it by reproduction.
    src/contextpack.py     590 lines; consumed only by `src/web/api.py`. It is
                           a display module, not a workflow input.
    src/copystages.py      the audit's Bug 4. `copypath.py` goes
                           Stage B -> lint and skips C to F.
    src/sequencegate.py    the audit's Bug 5. `bisonfactory` stages without
                           calling it.

A run that reports these as connected is wrong and must be debugged, not
believed.

## Build

    scripts/consumer_audit.py     NEW
    docs/state/CONSUMER-MAP.md    NEW, generated, never hand-edited
    tests/test_every_producer_has_a_production_consumer.py   NEW

`consumer_audit.py` walks the **import and call graph** of `src/` and emits one
row per public producer:

    COMPONENT / SOURCE / CANONICAL STORE / RETRIEVAL / CONSUMER /
    DECISION OR COPY EFFECT / VALIDATION / VERDICT

`VERDICT` is `CONNECTED` or `DISCONNECTED`, and `DISCONNECTED` requires the
tool to have found no non-test caller.

## The three ways this test can lie, and what you do about each

**1. A test is not a production consumer.** `tests/` and `work/` are excluded
from the caller set. A module whose only caller is its own test is
DISCONNECTED. `work/` is excluded because it is gitignored scratch — the ten
and the fifty were produced by `work/v2_run.py`, which is not in git and
cannot be anything's canonical consumer.

**2. Do not grep source for names.** CLAUDE.md: *"Test behaviour, not the text
of the source. Searching source for words produces a test that fails when
somebody writes a comment, which has happened repeatedly here."* Use `ast` to
resolve imports and call sites. A string match on `"sequencegate"` inside a
comment must not count as a caller — add a fixture proving that exact case
does not count.

**3. A re-export is not a consumer.** `from .x import y` in an `__init__.py`
that nothing then calls keeps a module alive in the import graph while nothing
consumes it. Follow through to a call site.

## Acceptance — RUN each one and paste its real output

1. The four known-disconnected components come out DISCONNECTED:

    py -3 scripts/consumer_audit.py --json > work/consumer-audit.json
    py -3 -c "import json;d=json.load(open('work/consumer-audit.json'));\
    v={r['component']:r['verdict'] for r in d};\
    import sys;\
    [sys.exit('%s reported %s, expected DISCONNECTED'%(k,v.get(k))) for k in \
     ('src/secondbrain.py','src/copystages.py','src/sequencegate.py') \
     if v.get(k)!='DISCONNECTED'];\
    print('all three DISCONNECTED as measured')"

2. **The test fails when it should.** Prove the guard, do not assert its
   presence:

    py -3 -m unittest tests.test_every_producer_has_a_production_consumer

   then add a throwaway `src/_probe_unused.py` exposing one public function
   with no caller, re-run, and **confirm the test FAILS and names
   `_probe_unused`**. Delete the probe. Paste both runs. A guard that has never
   been seen to fail is not known to work — that is the TASK-317 acceptance
   defect, and this task exists because of it.

3. A comment does not count as a caller:

    py -3 -m unittest tests.test_every_producer_has_a_production_consumer.CommentIsNotACaller

4. The generated map is complete:

    py -3 -c "import pathlib;t=pathlib.Path('docs/state/CONSUMER-MAP.md').read_text(encoding='utf-8');\
    assert 'DISCONNECTED' in t and 'CANONICAL STORE' in t;\
    print(t.count('|'),'table cells written')"

5. Full suite, unchanged by this addition. Wait for
   `work/suite_verdict.txt` and diff the failing-name **SET** against the
   baseline, not the count.

## What this task may NOT do

- **Do not wire anything.** Reporting only. `copypath.py`, `bisonfactory.py`
  and `copystages.py` are not modified here.
- **Do not build a second Second Brain**, a parallel store, or a replacement
  for a DISCONNECTED module. Directives §1: wire the existing component or
  document why it should be removed.
- Do not delete a DISCONNECTED module. Classifying is this task; removal is an
  operator decision.
- Nothing sent, nothing activated, no provider call, no model call.

## Completion report

Section 11 of `docs/OPERATOR-DIRECTIVES-2026-09-25.md` in full, with the
REMOTE SHA verified on GitHub.
