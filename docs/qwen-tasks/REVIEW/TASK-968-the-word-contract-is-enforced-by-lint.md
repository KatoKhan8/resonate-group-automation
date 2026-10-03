# TASK-968 — the writer contract becomes the thing that refuses

Written 2026-10-03 for work already finished on `task-word-contract-enforced`,
because the branch carried no task file and `glm_verify_branch.py` extracts its
acceptance from one: no file, no GLM verdict, and UNKNOWN does not pass.

**This file was written AFTER the code and says so.** Every command below was
executed before being written down, and the output is recorded under it.

## THE NUMBER 943 NAMES TWO DIFFERENT TASKS, AND THAT IS A FINDING

The operator's queue calls this branch "the lint contract (with 943)", and
`CLAUDE.md` records *"THE WRITER CONTRACT IS THE ONLY AUTHORITY FOR A BODY'S
WORD COUNT — operator, 2026-10-02, TASK-943"*.

But a file called `docs/qwen-tasks/TODO/TASK-943-name-the-authority-for-sent.md`
exists in history (commit `ae030997`, the ramp lane) and it is a **different
task**: *"the readback must declare which provider field decided SENT, and
refuse without it"*, P0, with four competing candidate fields for email alone.

One id, two tasks. This file takes a free number rather than adding a third
meaning to 943, and the collision is recorded here so the next reader does not
have to rediscover it.

## What the branch does

`src/skills/cold_email_writing.py` carries the contract AS DATA — "a contract
nothing can read is not a contract" — and `src/lint.py` now refuses against it.
Measured through the code:

    WORD_CONTRACT = {"em1": (60, 75, 90), "em2": (45, 60, 90),
                     "em3": (60, 75, 90), "em4": (45, 60, 90),
                     "em5": (45, 65, 90)}      # (floor, target, ceiling)

It also carries its own guard against the defect that produced it: **every step
must have at least thirty allowed lengths**, because the abolished 15-to-60
thread-reply range and a 60-to-90 em2 once intersected to the single value 60 —
an equality presented as a threshold.

## ⚠ THE OPERATOR'S NEW CONTRACT COLLIDES WITH THIS ONE AT em1

The operator set a new contract the same night: **em1 90–140, target 120**;
em2–em5 45–90; em4 target 50.

**This branch's em1 CEILING is 90.** So on the merged master, an em1 of 120
words — the operator's own target — would be REFUSED. The two contracts
intersect at exactly ONE value, 90, which is the same shape this branch exists
to prevent.

Nothing generates a 120-word em1 today, because the new contract is not
implemented anywhere (TASK-964 is TODO), so merging this enforcement is safe
NOW and strictly better than a contract nothing reads. **But `WORD_CONTRACT`
must become `em1: (90, 120, 140)` as part of TASK-964, in the same commit that
teaches the writer the new ladder** — and em4's target becomes 50 there too.
Merging this branch without recording that would leave the operator's own
instruction impossible to satisfy and the reason invisible.

## Acceptance

```
python -c "import sys; sys.path.insert(0,'.'); from src.skills import cold_email_writing as w; c=w.WORD_CONTRACT; assert set(c)=={'em1','em2','em3','em4','em5'}, c; assert all(len(v)==3 and v[0]<=v[1]<=v[2] for v in c.values()), c; assert c['em1'][0]==60 and c['em3'][0]==60 and c['em2'][0]==45, c; print('OK the contract is data and ordered:', c)"
```

```
python -c "import sys; sys.path.insert(0,'.'); from src import lint; KEY='k'; rec=lambda sk,n: {'id':'r','domain':'example.test','contacts':[{'key':KEY,'email':'a@example.test','cadence':{sk:{'channel':'email','generated':True,'subject':'a subject that is fine','body':' '.join(['word']*n)}}}]}; r=rec('em2',41); step=r['contacts'][0]['cadence']['em2']; bad=lint.check_step(r, KEY, step, step_key='em2'); good=lint.check_step(rec('em2',61), KEY, rec('em2',61)['contacts'][0]['cadence']['em2'], step_key='em2'); words_bad=[f for f in (bad or []) if 'word' in str(f).lower()]; assert words_bad, 'an em2 of 41 words was not refused on word count: '+str(bad); words_good=[f for f in (good or []) if 'word' in str(f).lower()]; assert not words_good, 'a 61-word em2 was refused for its length, so the rule refuses everything: '+str(words_good); print('OK 41 refused on words, 61 not:', [str(f)[:60] for f in words_bad][:1])"
```

```
python -c "import sys; sys.path.insert(0,'.'); from src.skills import cold_email_writing as w; room={k:(v[2]-v[0]+1) for k,v in w.WORD_CONTRACT.items()}; assert min(room.values())>=30, room; print('OK every step has at least thirty allowed lengths:', room)"
```

### NEGATIVE CONTROL

Command 1 fails if the contract stops being an ordered triple per step — which
is what a half-applied edit to those numbers looks like.

Command 2 is the operator's own case: an em2 of 41 words, the length the
approved canary copy actually shipped, must be REFUSED. It fails on master,
where `lint`'s floor is 40 and no 60 or 90 exists as a word bound at all. Its
second half is the control: a 61-word em2 must not be refused for length, or the
rule refuses everything and proves nothing.

Command 3 is the branch's own anti-equality guard: thirty allowed lengths per
step, so no future edit can reduce a range to a single legal value.

**THERE WAS A FOURTH COMMAND AND IT IS DELETED.** It read
`assert w.WORD_CONTRACT['em1'][2] >= 140 or True` and I labelled it "a record,
not a check". GLM's review called it exactly what it was — *"a print statement
wearing an assert"* — and made the sharper point: the em1 bound was then
"accepted by a check that is unfalsifiable by construction". A disclosed
vacuous assertion is still a vacuous assertion sitting in an acceptance list,
and this repository has been burned by those. The em1 collision is recorded in
the prose above, where a record belongs.

## WHAT GLM'S MULTI-PART REVIEW FOUND, AND WHAT EACH FINDING TURNED OUT TO BE

Three parts: 1=FAIL, 2=FAIL, 3=PASS, so the branch FAILED by conjunction. Four
grounds, measured one by one rather than accepted or dismissed as a set:

1. **`lint.is_contract_failure` had no production caller** — TRUE. Its only
   caller was this branch's own test helper, which is the "helper nothing calls"
   shape the branch itself deleted `_selected_offer` for. **Fixed**: the helper
   is removed and the test now asks through `lint.explain_contract`, which
   production DOES call (`lint.explain`, `src/lint.py:405`). One authority, one
   caller, 53/53 green.
2. **Acceptance command 4 was `or True`-vacuous** — TRUE, and mine. Deleted; see
   the negative-control note.
3. **"`lint.word_range` was deleted and a caller may now raise
   AttributeError"** — **REFUTED by measurement.** The function MOVED:
   `src/lint.py:735` calls `writercontract.word_range(...)` and the definition
   lives at `src/skills/cold_email_writing.py:48`. A grep over `src/` and
   `scripts/` finds no remaining `lint.word_range` call — only comments
   describing the move.
4. **The loader ERROR for the deleted
   `test_a_thread_reply_has_its_own_word_range` module** — NOT the branch's.
   Measured: nothing in `tests/`, `src/` or `scripts/` registers that module;
   the only references are prose in the new test's docstrings. The verifier's
   own `_changed_test_files` takes git's changed-file list, which INCLUDES
   deletions, and then runs them. That is a verifier defect and it has its own
   task.

**THE FRESH RUN IS DONE AND IT IS CLEAN.** Finding 1's fix touched `src/lint.py`
and a test, which superseded the first 231/0/0 — so the branch was measured
again at `70e86de2`: **231 failing names against the reference's 231, 0 new, 0
gone**, 2,086 seconds, one `Ran` line, both of refdiff's controls passing, and
both sides measured in neutrally-named trees (`wt-wordcontract` and
`resonate-ops/ref-cd8e00bc`) so A44's path exemption cannot distort either.

The sentence that used to sit here said a fresh run was still required. It was
true when written and GLM's second review quoted it back as a reason to refuse —
correctly, from what it could see. **A task file that goes stale inside one night
is a task file that misleads its own reviewer.**

## THE REMAINING BLOCKER, from the second review: the KEYLESS doors are untested

GLM's part 3 FAILed the branch on this and it is real:

> "none of the four keyless production lint doors the contract exists to gate is
> called by any test on the branch"

Four production callers reach `lint.check(rec, key, step)` **without** a step
key — `approve`, `eligibility`, `executionguard` and `campaigns` — and the
contract only applies to them through `step_key_of`, the recovery that infers
the step from the record. The branch tests that recovery DIRECTLY
(`TestTheKeyIsRecovered`), but the **deleted** 295-line module was the only
place the keyless path itself was driven, and nothing replaced it.

So the gate the contract exists to stand in front of is, for those four doors,
covered by a test of its helper rather than by a test of the door.

**What closes it:** one test per door, or one test that drives at least one of
them end to end — build a record whose stored step is an under-contract body,
call the door the way production calls it (no `step_key`), and assert the
contract refusal comes back. Then mutate `step_key_of` to return None and watch
it go green, which is the proof that the recovery is what carries the contract
through.

That is the branch author's work, not a third repair pass from the gate: it
needs a test under `tests/`, which means another full run before this merges.

## Files

`src/lint.py`, `src/skills/cold_email_writing.py`, `src/copystages.py`,
`src/generate.py`, `prompts/draft.md`, and the tests.

## Not in scope

The new contract's numbers (TASK-964). The SENT authority that the OTHER
TASK-943 is about.

---

# THE REMAINING BLOCKER IS CLOSED — 2026-10-03

`tests/test_the_keyless_doors_get_the_contract.py`, 15 tests, green. NO
production code changed: the branch's `src/` is byte-identical to what GLM
reviewed at `70e86de2`/`e62b0bc2`, because the finding was a missing test and
not a missing gate.

Every command below was executed before being written down, from the
neutrally-named worktree `wt-wordcontract` (A44).

## One test per door, each driven the way production calls it

    src/approve.py:115          approve.why_not                 DRIVEN
    src/eligibility.py:854      eligibility.decide              DRIVEN
    src/executionguard.py:615   executionguard.authorize        DRIVEN
    src/campaigns.py:463        campaigns.check_lint_clean      DRIVEN

em2 at 41 words - the operator's own canary length, four under its 45 floor -
STORED on the record under its real cadence key, and no `step_key` passed
anywhere on any of the four paths. Each door returns the contract refusal
`em2_body_41_words_under_contract_45_to_90`, and each test carries a control
at 61 words through the same door, because a door that refuses every body
proves nothing. Plus `TheFourDoorsAgree`: one body, three record-level doors,
one verdict - the disagreement between generation and approval is the failure
`step_key_of`'s own docstring says it exists to prevent.

## THREE MEASUREMENTS THAT CONTRADICTED WHAT I EXPECTED

**1. The `copy` gate at `executionguard.py:615` is SHADOWED and could not have
been reached as written.** `authorize` calls `eligibility.decide` at line 571,
forty-four lines earlier, with no `step` - so it rebuilds the timeline, lints
the expanded step, and refuses first:

    NotAuthorized(gate="eligibility",
      "eligibility says blocked: ['blocked:lint_failed',
       'blocked:lint:em2_body_41_words_under_contract_45_to_90']")

The first attempt at this test asserted `gate == "copy"` and failed with
`'eligibility' != 'copy'`. BOTH are now driven: the production path (gate
`eligibility`), and line 615 itself with `eligibility.decide` stubbed eligible
so the copy gate is what answers (gate `copy`, compliance in the passed-gate
trace). Asserting only the first would have left line 615 as unproven as the
review found it; asserting only the second would have proved a gate nothing
can reach.

**2. `tests/base.fixture_config` would have made this file vacuous.** It pins
`productive_balanced_v1`, whose keys are `day1`..`day21`, and
`writercontract.word_range("day1")` is **None** - no contract, no refusal, and
every door test green for the wrong reason. Measured:

    productive_li_heavy_v1     li1 em1 li2 em2 li3 em3 li4 em4 li5 em5   <- LIVE
    productive_email_eight_v1  em1 .. em8
    productive_balanced_v1     day1 day3 day5 day8 day10 day15 day21

`clients.load("productive")["cadence"]` is `productive_li_heavy_v1`, so that is
pinned, and `TheContractIsWhatIsBeingMeasured` asserts all three facts - the
canary length is under its floor, the live cadence names `em2`, and a
`day`-keyed step is named by no contract - so the file cannot go vacuous
silently.

**3. A fixture that faked an MX clearance was refused two gates early.** A
contact carrying `mx: {"status": "known_allowed", "email_eligible": True}`
makes `eligibility.decide` answer `skipped:email_channel_disabled`, because
`mx.allows_email` RE-DERIVES from the hostnames rather than trusting the
stored status and `meridian.test` publishes no MX record. With no block at all
it answers "no MX check has been run for this contact" and allows. The guard
was right and the fixture was wrong.

## THE MUTATION PROOF, AND WHY THE ORDERED ONE DOES NOT DISCRIMINATE

`__pycache__` wiped before every run; each mutation asserted to have actually
applied before any verdict from it was believed; every file restored and
verified afterwards.

**The ordered mutation — `step_key_of` returns `None`.** My file reds 7 of 15,
each for its own reason, with all three anchors and every 61-word control
green:

    DoorOne   an_under_contract_step_is_not_approvable        False is not true
    DoorTwo   an_under_contract_step_is_blocked_on_lint       'held' != 'blocked'
    DoorThree the_guard_refuses_an_under_contract_body        'sender' != 'eligibility'
    DoorThree the_guards_own_copy_gate_also_carries_...       'sender' != 'copy'
    DoorFour  an_under_contract_step_fails_the_launch_check   every final email passes lint
    DoorFour  the_step_the_door_linted_was_the_expanded_one   None != 'em2'
    Agree     all_three_record_level_doors_refuse_the_same... approve/campaigns True, eligibility False

**But it reds 29 of the 53 tests in `test_word_contract_enforced` too**, because
that file's own helpers reach the contract through the same recovery. So the
ordered mutation proves the recovery is load-bearing and proves NOTHING about
whether the DOORS are covered - it cannot tell this file's contribution from
the existing one's. Recorded because a mutation that reds everything is the
"validator that agrees with you" shape, and reporting it as the proof would
have been exactly the claim GLM refused.

**THE DISCRIMINATING MUTATION IS PER DOOR**: neutralise that one door's lint
call, which is precisely the defect class the review named - "the gate the
contract exists to stand in front of is covered by a test of its helper rather
than by a test of the door". Four mutants, run against both modules:

    MUTANT                                  word_contract_enforced   keyless_doors
    door 1  approve.py:115 -> []            53 ran,  0 FAIL          15 ran,  2 FAIL
    door 2  eligibility.py:854 -> []        53 ran,  0 FAIL          15 ran,  3 FAIL
    door 3  executionguard.py:615 -> []     53 ran,  0 FAIL          15 ran,  1 FAIL
    door 4  campaigns.py:463 -> []          53 ran,  0 FAIL          15 ran,  2 FAIL
    restored                                53 ran,  0 FAIL          15 ran,  0 FAIL

**Every door can be switched off with the pre-existing 53 tests completely
green.** That is the coverage hole, measured, per door - and each mutant is
caught by exactly the tests that name that door. Door 2's mutant also reds
door 3's production-path test, which is correct and is the shadowing above
showing up as an effect rather than as prose.

## What still stands before this merges

A full suite. One runs on this machine at a time and the main session holds the
lock, so this closure carries per-module runs (53 + 15 = 68 green, 0.40 s) and
not a 231-name reference run. The branch adds a file under `tests/`, so the
merge rule admits no shortcut: it gets a new reference.

The em1 collision with the operator's 90-140 contract is unchanged and still
belongs to TASK-964, in the same commit that teaches the writer the new ladder.

## THE "68 GREEN" ABOVE WAS TWO MODULES, NOT THE SIXTEEN THE GATE RUNS

Corrected 2026-10-03 with the measurement, rather than deleted. The sentence
above is true and was never the whole truth: **53 + 15 is this branch's own two
modules.** The gate runs every CHANGED test module, and across those the count
is **232 ran, 4 failures + 1 error** — which is what GLM's second FAIL named,
and it was right to name it. Measured per module, on this branch at `6cffa188`:

    test_campaign_ready_funnel                    ran=27  fails=0
    test_generate                                 ran=56  fails=3   <--
    test_ladder_propagation                       ran=25  fails=0
    test_task910_writer_contract                  ran=16  fails=2   <--
    test_task913_writer_contract_five_plus_five   ran=40  fails=0
    test_the_keyless_doors_get_the_contract       ran=15  fails=0
    test_word_contract_enforced                   ran=53  fails=0
                                                  ------
                                                  ran=232 fails=5

**ALL FIVE ARE MASTER'S, AND THEY ARE ALREADY IN THE REFERENCE.** Run on a
neutral worktree detached at master `7e8eee41`, with nothing from this branch
present, the same two modules give the SAME five names and the same counts
(`test_task910` 2/16, `test_generate` 2+1/56). And all five parse out of
`resonate-ops/logs/reference-228-master-7e8eee41.log` — 228 names read with
`run_suite._parse_failures`, positive control `test_e2e` = 11 names:

    test_em_dash_still_fails_after_normalisation                    IN BASELINE
    test_em_dash_normalised_but_still_caught                        IN BASELINE
    test_a_draft_that_breaks_a_rule_is_regenerated_not_patched      IN BASELINE
    test_the_model_is_told_what_failed_rather_than_the_draft_...     IN BASELINE
    test_the_retry_names_the_banned_phrase_rather_than_the_code     IN BASELINE

So the branch's name-set diff against that reference should carry **0 new
names** for these five. They are not this branch's regressions; they are
master's, counted in the reference this branch is measured against. The branch
does modify `tests/test_task910_writer_contract.py` and `tests/test_generate.py`
(it lengthened fixture bodies to meet the contract), which is exactly why a
changed-file list attributes them here — and attribution by changed-file list
is the trap CLAUDE.md already records in the other direction.

### What the three defects actually are

**1. The em-dash ban is NOT lost. The two tests pin a superseded mechanism.**
Measured through the code:

    lint.check on a RAW em dash        ['em_dash', ...]        <- still refused
    normalise_punctuation('a—b')       'a, b'                  <- comma, not ' - '
    copylint.DASH_RE on the raw text   True
    copylint.DASH_RE on 'a, b'         False
    an em dash surviving normalisation  False

`_PUNCTUATION_MAP["—"]` became `", "` in `20d9fb12` (2026-09-30), *"The
punctuation normaliser manufactured the exact dash the copy lint bans"* — the
normaliser used to emit `" - "`, which is precisely what `DASH_RE` refuses, so
it was generating the refusal it was meant to prevent. The two tests were
written in `a353f920` (2026-09-28), two days EARLIER, and assert the old chain:
em dash -> `" - "` -> DASH_RE fires. No em dash can reach a prospect either way;
the ban still bites on un-normalised text. **The tests are stale, the guard is
intact**, and reverting the map would resurrect a position this repository
already measured and refuted.

**2. Nine retries is the DESIGNED budget, and the real defect is underneath it.**
`generate_campaign.MAX_WRITER_ATTEMPTS = 10` — raised 3 -> 6 -> 10 in `b946b59c`
(2026-09-30), with the reasoning in its own docstring. 10 writer calls is 1
first draft + **9 retries**, so `assertEqual(len(model.retry_prompts), 1)` pins
a cap that was three versions ago. Measured: `writer_prompts: 10`,
`retry_prompts: 9`, `MAX_DRAFT_ATTEMPTS: 3` (a different constant, on a
different path).

**But the attempts are wasted, and that part is real.** The rejection ledger
accumulates and is never pruned to what the CURRENT draft offends. The reason
list fed to retry 9 is BYTE-IDENTICAL to the one fed to retry 1:

    - step 1 opens with a line no pack fact supports
    - a buzzword or banned phrase -> em1 ('i wanted to reach out')
    - em2/em3/em4 ('i wanted to reach out')
    - day1: you referred to an attachment. Nothing is attached
    - the body is under 40 words
    - you used "i wanted to reach out", which is banned outright...
    - you left an unfilled placeholder in square, curly or angle brackets
    - day15: you referred to an attachment. Nothing is attached

Nine of those ten items come from attempt 0's deliberately-bad draft. Drafts 1
to 9 contain **none** of them — verified by logging each writer answer: call 0
returns the bad body, calls 1-9 return the clean one. So the model is told nine
times to fix defects it fixed on the first retry, and the one complaint that
does apply, `step 1 opens with a line no pack fact supports`, is buried among
them. That is the same defect `b946b59c` was fixing (uninformative retries) in
a new place: the feedback is now *complete* but no longer *current*.

**3. The `KeyError` is defect 2's downstream symptom, not a fixture typo.**
It is in `tests/test_generate.py:250` (`TestTheAcceptanceTest.test_a_draft_that_breaks_a_rule_is_regenerated_not_patched`),
not in `test_task910`. Because every attempt is refused, nothing is stored:

    record state   : verified
    cadence stored : []          <- no 'rowan-blake' key to subscript

`rec()["cadence"]["rowan-blake"]` then raises `KeyError: 'rowan-blake'`. The
blocking gate is the pack-facts one: the `harbourline` fixture has no pack fact
supporting its opener, so the opener can never be licensed and the set can
never pass. A branch named `lane-l-staging-fixtures-packfacts` already exists,
which suggests that fixture gap is known and separately owned.

### Why none of this is fixed in THIS diff

Each fix lands in a file this task is not about — `src/lint.py`'s punctuation
map, `src/generate_campaign.py`'s rejection ledger, the `harbourline` pack-fact
fixture — and two of the three are product decisions already taken by the
operator on 2026-09-30. Changing `src/` here would also void the branch's
in-flight full run and re-cost it, on a merge that is on the critical path.
They are written up as their own task instead; this file carries the
measurement so the next reader does not have to rediscover it.
