# Suite baseline — 2026-09-22

**The number the register can carry, and the list that makes the next one
diffable.** `SUITE-BASELINE-2026-09-22.json` beside this file holds every
failing test by name; this file says what they are.

    runner      py -3 -m tests.offline
    branch      infra, off master c75b4b60
    measured    11,098 tests · 80 failures · 36 errors · 116 entries
    distinct    112 test methods (115 detail blocks; subTests inflate entries)

---

## 1. WHY THE 83 COULD NOT BE DIFFED, AND WHY THIS FILE EXISTS

The brief asks to diff 113 against yesterday's 83 by name. **It could not be
done, because no name-level record of the 83 was ever written.** What exists
is three counts in prose:

    r53  2026-09-21 12:14Z   10,671 tests   50 F + 33 E =  83
    r58  2026-09-21 19:10Z   10,769 tests   76 F + 44 E = 120
    this 2026-09-22          11,098 tests   80 F + 36 E = 116

Searched for a stored list: `docs/`, `docs/state/`, and the pool logs in
`../pool-logs/`. The sweep logs are 71-byte dispatch records and carry no test
names. So "83" is a scalar with no members, and a scalar cannot be diffed —
you can only subtract it, which tells you a net and hides an equal number of
fixes and regressions.

**This is the same defect the problem register keeps naming.** A derived
report is only as good as its last verification, and a baseline that is a
number rather than a list is a report nobody can check. The fix is the JSON
beside this file: every failure by fully-qualified name, so the next session
diffs sets instead of subtracting integers.

The test count also grew by 427 between r53 and now, so the raw deltas were
never comparing the same suite.

---

## 2. THE HEADLINE: 110 OF 115 ARE STABLE, 5 WERE RUN ORDER

Every failing module was re-run **alone** and compared against its count in
the full run. All 33 agree exactly — except one.

    module                        full   alone   delta
    test_invariants                  7       2      -5
    every other module (32)        108     108      +0

So the baseline is not noisy, with one exception, and the exception is in a
safety module.

### The 5 were the production-state barrier, and the cause is measured

`TestTheBarrierCoversEveryWriter` drives every self-writing module and asserts
each refuses to write the real `work/` directory. Two of those writers —
`spendledger` and `observability` — resolve their own path beside
`store.queue_path()` rather than taking one. With `QUEUE` still pointing at
some earlier module's temp directory they write **there**, the barrier
correctly does not fire, and the test fails with "ProductionStateUnderTest not
raised" while the barrier is in perfect health.

Reproduced directly, not inferred:

    clean environment                       5/5 OK
    QUEUE=<tmp> ...                         4 failures
    SPEND_LEDGER=<tmp> ...                  1 failure, exactly `spendledger`

50 test modules call `store.use_directory`. Which one leaked is not the
interesting question — depending on all 50 is.

**FIXED** in this branch: the class pins its own environment in `setUp` and
restores it in `tearDown`, so it tests the real paths its docstring already
claimed it tested. Cleared rather than asserted-clean, because a test that
skips on a dirty environment tests nothing on a dirty environment, and this is
the barrier that stops a test writing real client state.

Verified not vacuous: with `refuse_production_write` stubbed to a no-op the
class produces **10 failures** across all nine writers plus the dedicated
`test_the_barrier_actually_refuses_under_test`.

---

## 3. CLASSIFICATION

    cluster                       n    class              action
    ------------------------------------------------------------------
    threading-invariant          28    changed contract   TASK-256
    verification roles           ~19   changed contract   TASK-250 (exists)
    run-order / barrier           5    environment        FIXED here
    PII guard                     3    REAL DEFECT        production session
    account fatigue               6    unclassified
    the long tail                ~54   unclassified

### 3.1 The threading invariant — 28 tests, one cause, and a latent defect

All 28 raise `bisonfactory.FactoryRefused`:

    step 3 is not a thread reply but carries a distinct subject
    ('{SUBJECT_3}' vs opener '{SUBJECT_1}')

Across `test_bison_campaign_write` (11), `test_render_preview` (11) and
`test_task081_thread_reply` (6). The guard arrived with **TASK-219 at
`4c9d63d3`, 2026-09-16** — *"only the opener owns a subject"* — a deliberate
tightening of the EMAILBISON-COPY-REQUIREMENTS contract that CLAUDE.md carries
as standing.

**Classification: changed contract. Update the fixtures, never the guard** —
the same rule TASK-250 states for the verification roles.

**But there is a real defect underneath it, and it is worth its own row.**
The invariant says: if any follow-up is threaded, every follow-up must either
be threaded or reuse the opener's subject. The ladder default is

    THREAD_REPLY_PATTERNS["email_five"] = (False, True, False, True, False)

Steps 3 and 5 are **not** threaded. So the shipped default ladder is
incompatible with the shipped invariant for any sequence whose follow-ups
carry their own subjects — the system's own default configuration cannot build
a sequence.

**Production is not affected today, and I checked rather than assumed.** Both
real client configs override the pattern with all-threaded follow-ups:

    config/clients/productive.yaml   thread_reply_pattern: [False, True, True]
    config/clients/demo.yaml         thread_reply_pattern: [False, True, True, True, True]

which is why 491-498 built and activated on 09-21/22 with the guard six days
old. **A client added without that override inherits the broken default.**
That is latent, not theoretical, and it is exactly the shape the register's
closing section describes.

### 3.2 The PII guard — 3 tests, REAL DEFECT, not mine to fix

`test_fixture_hygiene.TestNoRealDataAnywhereInGit`, 3 of 13 red.

ISSUE-006 closed this at `cecd4223` on 2026-09-20 reporting 13/13 green, with
the finding *"a red guard catches nothing"*. **132 commits later it is red
again**, and every file it flags landed on 09-21 or 09-22 — after that fix.
None is mine; checked against both commits on this branch.

Files flagged: `docs/HEYREACH-CADENCES-2026-09-21.md`,
`docs/SLACK-AGENT-HANDOFF-2026-09-22.md`, `docs/qwen-tasks/TODO/TASK-249-…`,
`scripts/batch1_build.py`, `src/clientapproval.py`,
`tests/test_a_client_can_never_reach_another_client.py`,
`tests/test_client_approval_is_a_gate.py`.

Left for the production session: those are its active files, and redacting
identifiers out of `src/clientapproval.py` touches live client semantics.

**This is the cost of a large baseline, stated plainly.** ISSUE-006's guard is
no longer silently red — it is loudly red in a room where 111 other tests are
also shouting. A baseline this size does not just slow work down; it is where
a safety guard goes to hide. That is the argument for section 5, and it is the
reason this file exists at all.

### 3.3 The long tail

~54 entries across 28 modules, 1-6 each, not yet root-caused: `test_e2e` (14),
`test_preproduction` (6), `test_a_gated_step_is_waiting_not_absent` (5),
`test_two_providers_disagreeing_is_not_a_headcount` (5),
`test_for_prompt_quality` (5), and 23 modules with 1-3.

**Not classified, and deliberately not guessed at.** Several carry messages
that look like TASK-250's verification-role change (`'held' != 'approved'`,
`None != 'accept_all'` in `test_e2e` and `test_enrich`), but "looks like" is
not a classification and this register's first rule is that a row is confirmed
only with a reproduction. They are named in the JSON and they are next.

---

## 4. WHAT CHANGED IN THIS BRANCH

    test_invariants                       -5   environment, fixed (section 2)
    test_a_review_call_carries_its_source +11  new, green (GLM harness)

Nothing was retired and nothing was weakened. No test was deleted, no
assertion loosened, no guard widened.

---

## 5. THE NUMBER THE REGISTER SHOULD CARRY

    2026-09-22   11,098 tests   111 failure/error entries   107 distinct tests

That is the measured 116 less the 5 order-dependent barrier entries, and it is
**a floor to work down from, not an achievement**. Two thirds of it is two
known contract changes:

    threading invariant (TASK-219)   28
    verification roles  (TASK-250)   ~19  — task already written, not started
    ------------------------------------
                                     ~47 of 111

Both are fixture work with a stated rule — *update the fixtures, not the
policy* — and neither is hard. It is simply never been anybody's turn.

**The rule this file asks the register to adopt:** a baseline is a LIST, and a
count without one is not a baseline. Regenerate the JSON on every measurement
and diff sets. Then "113 against 83" becomes answerable instead of arithmetic.
