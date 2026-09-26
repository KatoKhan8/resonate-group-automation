PRIORITY: P0
SIZE: S
DEPENDS:

# TASK-325 — document the ACTUAL LinkedIn cadence tree, before anyone changes it

**Operator order, 2026-09-26:** *"Before modifying the LinkedIn cadence itself,
inspect the current implementation and document the actual tree. Do not replace
a working cadence based on assumptions."*

**This task changes NO behaviour.** It reads and writes a document. Any
proposal to change the tree goes under FINDINGS and waits for the operator.

## Why it exists

Three separate claims about the LinkedIn cadence have been in play and they do
not agree:

    "a six-step graph produces only one provider step"   OPERATOR-DIRECTIVES
                                                         §4, from an earlier log
    "the 'one step from six' finding is STALE;
     _refuse_missing() refuses the whole staging now"    PHASE1-PLAN, and the
                                                         handoff §6 agrees
    "five LinkedIn steps in PRODUCTIVE_LI_HEAVY_V1"      handoff §3
    the ten's and the fifty's review pages render
    FOUR LinkedIn messages, at days 1/3/8/14            measured 2026-09-26 by
                                                         Claude against both files

Four rendered messages against five configured steps may be correct (a
connection request plus three messages, with one step not rendered in review)
or may be a silent drop. **Nobody has written down which.** That is the whole
task.

## Deliverable

    docs/LINKEDIN-CADENCE-AS-BUILT-2026-09-26.md    NEW

It must state, from the code and not from memory:

1. The graph `PRODUCTIVE_LI_HEAVY_V1` as configured: every step, its type
   (connection request / message / view / follow), day offset, and whether it
   carries approved copy.
2. Where the graph is defined, by file and symbol.
3. What `heyreachfactory` actually stages, step by step, and what
   `_refuse_missing()` refuses.
4. The provider payload shape that leaves for HeyReach, field by field.
5. **The exact reason the review pages render four messages when the graph has
   five steps.** Name the file and line that decides it. If it is a render-only
   difference, say so and prove it. If a step is dropped before the provider,
   that is a P0 FINDING — write it, commit, stop, do not fix it here.
6. Which steps carry merge variables rather than baked words —
   `docs/CONTEXT-RESET-2026-09-15-E.md` says the HeyReach sequence holds merge
   variables and the words arrive per lead. Confirm or refute against the code.

## Acceptance

1. The graph is read from the code, not transcribed:

    py -3 -c "import sys;sys.path.insert(0,'.');from src import cadence;\
    g=[n for n in dir(cadence) if 'LI_HEAVY' in n or 'PRODUCTIVE_LI' in n];\
    print('graph symbols:',g)"

   If that finds nothing, locate the real definition and report the actual
   import path. Do not conclude the graph is missing — it is referenced by name
   in the handoff and the plan.

2. Configured step count, measured:

    py -3 -c "import sys;sys.path.insert(0,'.');\
    from src import heyreachfactory as H;\
    print('staged steps:', H.describe('PRODUCTIVE_LI_HEAVY_V1'))"

   Use whatever the real entry point is; report the count and the per-step
   types. **A count alone does not close this task — the types and days must be
   listed.**

3. The four-vs-five question is answered in one paragraph naming a file and a
   line number.

4. `docs/LINKEDIN-CADENCE-AS-BUILT-2026-09-26.md` exists, is committed, and is
   verified on `origin/master`.

## What this task may NOT do

- **Do not modify the cadence, the graph, any step, any delay, or any copy.**
- Do not reduce the number of LinkedIn steps. Directives §4 and §7 forbid it,
  and so does the 2026-09-26 account-first clarification.
- Do not touch an active HeyReach campaign. Do not call the provider live.
- Nothing sent, nothing activated.
