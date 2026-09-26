PRIORITY: P0
SIZE: M
DEPENDS:

# TASK-343 — the review preview invents the LinkedIn cadence

Found 2026-09-26 while verifying the fifty, and confirmed against TASK-325's
as-built audit (`docs/LINKEDIN-CADENCE-AS-BUILT-2026-09-26.md`).

## The defect

`work/v2_pages.py` — the generator of the ten and the fifty — **hardcodes the
cadence instead of reading it from the graph:**

    WAITS = {"em1": 1, "em2": 4, "em3": 8, "em4": 12, "em5": 21}
    LI = (("connect", 1, "connection request", 280),
          ("msg1", 3, "after acceptance", 600),
          ("msg2", 8, "capability, correlates to the email", 600),
          ("msg3", 14, "close", 600))

Measured against `src/cadencelibrary.py:PRODUCTIVE_LI_HEAVY_V1` (line 327):

    step   graph day    preview day
    em1    1            1     ok
    em2    4            4     ok
    em3    8            8     ok
    em4    12           12    ok
    em5    21           21    ok
    li1    1            1     ok
    li2    3            3     ok
    li3    6            8     WRONG
    li4    10           14    WRONG
    li5    15           absent from the preview entirely

**The email days are right. The LinkedIn days are invented.** Days 8 and 14 are
not LinkedIn step days in this system at all — 8 is `em3`'s day and 14 is nothing's.

## Why the "four messages" explanation does not cover this

TASK-325 correctly established that the HeyReach graph splits 5 LinkedIn steps
across two branches, that neither branch carries all five, and that **no step is
dropped before the provider.** That conclusion stands and this task does not
reopen it.

But the preview does not *derive* four from the branch structure — it hardcodes
four entries with its own day numbers. The fact that four happens to match the
not-connected branch's four interactions is **coincidence, not correctness.** A
change to the branch structure would not change the preview, and a change to the
cadence days already has not.

## Consequence

The operator reviews and approves from this artifact. The fifty is posted to
`#resonate-os` with approval hash `0c493ab9c3d9d136`, and its LinkedIn section
shows a cadence that does not exist. The 2026-09-26 account-first directive makes
email/LinkedIn coordination the thing to review — *"LinkedIn should complement
Email, not paraphrase it"* — and that judgement is being made against wrong
timing.

This is **not** a send risk: the gates, the graph and the provider payload are
unaffected, and nothing is sent. It is a review-fidelity defect.

## Build

    scripts/preview_cadence.py   NEW, or extend TASK-342's scripts/fifty_xlsx_v2.py
    tests/test_the_preview_reads_the_cadence_it_previews.py   NEW

The preview must **read the cadence from `src/cadencelibrary.py`**, not restate
it. Import `PRODUCTIVE_LI_HEAVY_V1` and render what it says: every step, its real
day, its channel, and — because of the branch split — **which branch each
LinkedIn message sits on**, so a reader can see that a cold prospect walks
`connection_note → message_2 → message_3 → message_4` and an already-connected one
walks `connected_1..connected_4`.

`work/v2_pages.py` is gitignored and therefore not in version control, which is
its own durable-state violation (TASK-342 covers moving the generator into
`scripts/`). **Put the fix in `scripts/`, not in `work/`.**

## Acceptance — RUN each, paste real output

1. The preview's days come from the graph, proved by changing the graph:

    py -3 -c "import sys;sys.path.insert(0,'.');\
    from src.cadencelibrary import PRODUCTIVE_LI_HEAVY_V1 as G;\
    days={s['key']:s['day'] for s in G['steps']};\
    print('graph days:',days)"

   then assert the renderer emits exactly those days. **Name the real key/field if
   the structure differs** — read it, do not assume this shape.

2. **Seen to fail:** monkeypatch one LinkedIn step's day in the graph, re-render,
   and confirm the preview's day CHANGES with it. A preview that still shows the
   old number is still hardcoded. This is the assertion that actually closes the
   task — a test comparing the renderer against a second hardcoded table would
   pass while remaining wrong.

3. All five LinkedIn steps appear, each labelled with its branch.

4. Re-render the fifty into a NEW file and report the corrected LinkedIn day
   labels. **Do not overwrite `work/review/503-FIFTY-v2-2026-09-25.html` or its
   `.xlsx`** — both are posted and hashed, and an approved artifact is immutable.

5. Full suite: wait for `work/suite_verdict.txt`, diff the failing-name SET
   against `docs/state/SUITE-BASELINE-2026-09-26.txt` (128 names). Not a count.

## What this task may NOT do

- **Do not change the cadence.** Not a day, not a step, not the branch structure.
  The graph is correct; the preview is wrong. Directives §4 and §7 forbid
  shortening or altering the LinkedIn cadence, and the account-first
  clarification forbids simplifying the tree.
- Do not regenerate the COPY — no model call. This task changes a renderer.
- Do not overwrite the posted, hashed artifacts.
- Nothing sent, nothing activated.
