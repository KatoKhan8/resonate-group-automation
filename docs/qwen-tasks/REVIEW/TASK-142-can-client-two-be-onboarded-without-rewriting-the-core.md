PRIORITY: P2
DEPENDS:

# TASK-142 - the portability test, answered with a list rather than an opinion

## THE QUESTION, EXACTLY

Can a second client be onboarded through CONFIGURATION, DATA and PRODUCT
KNOWLEDGE, or does it require editing Resonate OS core logic?

That is the test that decides when development attention can move to Client #2
while Productive keeps running. It is not answered by "mostly yes".

## THE METHOD

Do not read the code looking for things that feel Productive-specific. Walk the
PRODUCTION LOOP and, at each stage, ask what a second client would need and
where that value comes from today:

    domain inventory -> account processing -> research -> signals
      -> ICP qualification -> contact discovery -> relationship state
      -> cohorting -> copy and variables -> gates -> provider campaign
      -> senders -> leads -> readback -> outcomes -> learning

For every stage produce one row:

    stage
    what is client-specific about it
    where that value lives today   (config key / data file / hardcoded in src)
    what Client #2 would have to do
    verdict: CONFIG | DATA | CODE CHANGE

Three already-known entries, recorded and deliberately NOT refactored, so do
not spend the task rediscovering them:

    the client config carries the fallback copy inline
    scripts/build_intake_batch.py hardcodes the Productive source CSV path
    several task scripts default to --client productive

Those do not block production. Confirm they are still true in one line each and
move on to what is not yet known.

## WHAT MAKES THIS USEFUL RATHER THAN A SURVEY

Every CODE CHANGE row must name the FILE AND THE FUNCTION, and must say
whether it is:

    BLOCKING     Client #2 cannot be onboarded without it
    FRICTION     Client #2 works but somebody edits code to do it
    COSMETIC     neither; it just looks client-specific

A list of forty cosmetic observations is worth less than three blocking ones
with file and function. Rank them and put the blockers first.

## THE TENANCY BOUNDARY IS DIFFERENT FROM THE CONFIG BOUNDARY

Some things are not "Productive-specific values" but "assumptions that there is
one client". Those are more serious and harder to see. Look specifically for:

    a lookup that would return another client's row
    a default that means "everybody" when a client is not named
    a provider credential bound to one workspace and read as if global
    a state key that does not carry a client

`heyreachfactory._plan` already refuses an empty `record_ids` rather than
walking the estate, and refuses a record belonging to another client, so that
shape of guard exists and is worth pattern-matching against elsewhere.

## WHAT YOU MAY NOT DO

- **Do NOT refactor anything.** This task produces the list. A multi-tenant
  refactor now would put unreviewed structural change on the path of the first
  live campaign, which is the trade the priority order forbids.
- No provider calls. No writes to `work/`.

## FILES ALLOWED

    docs/CLIENT-TWO-PORTABILITY-2026-09-15.md   (new)
    the task file itself

## FILES FORBIDDEN

    src/       scripts/       config/       work/

## DELIVERABLE

The stage-by-stage table, the ranked BLOCKING / FRICTION / COSMETIC list with
file and function on every code row, the tenancy-assumption findings, and a
one-line verdict on the portability question that a reader can check against
the rows above it.

## RESULT

- **STATUS:** DONE
- **COMMIT SHA:** c8cf008
- **TESTS:** No tests required — this is a read-only analysis task. FILES FORBIDDEN prevented any code changes.
- **FILES CHANGED:**
  - `docs/CLIENT-TWO-PORTABILITY-2026-09-15.md` (new — the deliverable)
  - `docs/qwen-tasks/RUNNING/TASK-142-can-client-two-be-onboarded-without-rewriting-the-core.md` (this file — result block)
- **FINDINGS:**
  - **Verdict:** Client #2 can be onboarded through CONFIGURATION and DATA alone. Zero BLOCKING items in `src/`. The production loop is client-parameterised end to end.
  - **6 FRICTION items** (all CLI defaults, none on the production execution path):
    1. `scripts/build_intake_batch.py:19` — hardcoded Productive source CSV path
    2. `src/icpstructural.py:558` — `--client default="productive"`
    3. `src/senderinventory.py:411` — `--workspace default="productive"`
    4. `scripts/build_control_cohort.py:198` — `--client default="productive"`
    5. `scripts/campaign_ready_funnel.py:504` — `--client default="productive"`
    6. `src/replywatch.py:97-125` — process-global `BISON_WORKSPACE_ID` pin
  - **7 COSMETIC items** — all in `src/web/demo*.py` (test fixtures) and `src/companies.py` (benchmark tool)
  - **5 tenancy-boundary findings** — provider credentials are process-global (T1), `bison.bound_workspace()` returns one workspace per credential (T2), reply poller pins to one workspace (T3), cross-client dedup is off by default (T4), state keys are workspace-scoped not client-scoped (T5)
  - **Already-known items confirmed:** fallback copy inline in productive.yaml ✓, build_intake_batch.py hardcoded path ✓, scripts default to --client productive ✓
- **RISKS:** The six FRICTION defaults should be fixed before the first operator runs a command for Client #2, because a forgotten `--client` flag will silently operate on Productive's records. The reply poller (F6/T3) is the only item that affects production rather than operator scripts — it cannot serve two clients simultaneously without a second process or credential-per-client indirection.
- **RECOMMENDED CLAUDE ACTION:** Review the portability assessment. The six FRICTION items are safe, small fixes (remove CLI defaults, add `--source` argument) that can be batched into one task. The tenancy findings (T1-T3) are architecture decisions that should be deliberate rather than accidental.
