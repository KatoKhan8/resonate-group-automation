PRIORITY: READ WITH THE 2026-09-29 RACHELE HANDOFF

# TASK-914 REWORK — VERIFIED AND MERGED

**Supersedes `docs/TASK-914-VERIFICATION-BLOCKED-2026-09-29.md`**, which
recorded the blocker this closes. That document stays: it is the measurement
that stopped the first candidate.

    master (merged)   81c5f61a   == origin/master, verified by fetch
    merged branch     qwen-worker-r9 @ 5220bbac
    verified snapshot 525c107a   (code byte-identical to 5220bbac;
                                  5220bbac differs only in a task result block)

Nothing sent by this work. Provider writes 0, enrolments 0, prospect-facing
sends 0, campaign activation 0, `sending.live` false. **No `deliverable`
verification call was made** and no verification credit was spent. **Rachele
email remains HELD** under the unchanged Productive policy.

---

## WHAT LANDED

TASK-913 (writer 5+5 + LinkedIn consumer migration) and TASK-914 (unsupported
customer-outcome claims + email-hold observability), with TASK-914's detector
repaired across three rework rounds.

## THE THREE ROUNDS, AND WHY EACH WAS NEEDED

| round | change | independently measured result |
|---|---|---|
| 914 | past-tense verb list | **14 of 23** matrix assertions escaped |
| 915 | stem + inflection paradigm | refusal fixed; **5 new overblocks** |
| 916 | perception != achievement; `your team` != our customer | overblocking fixed; **2 left** |
| 917 | an outcome claim needs an **OBJECT**; one shared vocabulary | **all green** |

Each round fixed the previous defect and exposed the next. The sequence is
worth keeping because the failures were not random — they walk the same
mistake from both sides:

1. **914 under-matched on FORM.** A verb list is a conjugation, not a class.
2. **915 over-matched on VOCABULARY.** Adding `see` as an outcome verb made
   any customer noun near any "see" fire — it refused
   `saw your team's post about the new Dallas office`, a plain cold opener.
3. **916 still fired on SUBJECT+VERB alone.** `agencies we speak with raise
   this constantly` was refused because `rais` is a stem; `raise` there means
   "bring up". And its comparative branch used a CLOSED metric list, so
   `clients see faster reporting cycles` shipped.
4. **917's single idea fixes both.** *"Our customers improved" is not a claim
   until it names WHAT improved.* One shared `_OUTCOME_METRICS` vocabulary
   serves the achievement branch as a complement requirement and the
   comparative branch as its terminal alternation, so the two cannot drift.

## HOW IT WAS VERIFIED — BY EFFECT, NEVER BY READING A REGEX

Every probe asserts through the real gate, `generate._step_refusals`, on
**both channels**. None reads a verb list, a pattern or a reason string.

**The discriminator is EVIDENCE-SENSITIVITY.** A customer-outcome refusal
must DISAPPEAR when the canonical authority licenses the evidence; a
non-outcome sentence must behave IDENTICALLY with and without it. A blanket
word ban passes a refusal matrix and fails this, which is what makes it the
load-bearing check rather than the sentence counts.

    matrix_914      23 assertions, the operator's own list       PASS
    heldout_914     16 pos / 5 neg, never shown to any worker    PASS
    overblock_915   12 legitimate sentences near outcome verbs   PASS
    heldout2_916     8 pos / 8 neg, fresh text                   PASS
    heldout3_917     8 pos / 8 neg, fresh text                   PASS
    probe_913_chain  writer->plan->Bison->HeyReach, li5 survives PASS
    probe_observability  Part B is decision-neutral              PASS
    probe_mutation   channel parity + four-key cap falsified     PASS

**Three held-out sets** were used because each task document quotes the
previous round's counterexamples: once a sentence is in a task file the
worker has seen it, and a suite that only replays handed strings cannot tell
modelling from pattern-fitting. The held-out sets caught nothing on 917 —
which is the point: on 914 they caught 10 escapes, and on 916 they caught
both remaining defects.

**Mutations, all in-memory, nothing committed:** neutering `claims.check`
stopped BOTH channels refusing; neutering `customer_outcome_claim` turned the
matrix red and confirmed no other guard was masking it; restoring a
four-element LinkedIn cap lost `li5`. All restored, worktrees verified clean.

## ACCEPTANCE LEDGER — measured on MERGED MASTER 81c5f61a

    semantic unsupported-outcome matrix        PASS
    tense / aspect / modal variants            PASS
    singular / plural benchmark variants       PASS
    email protected                            PASS
    LinkedIn protected                         PASS
    plain capabilities not overblocked         PASS
    questions not overblocked                  PASS
    prospect facts not overblocked             PASS
    licensed customer-outcome control allowed  PASS
    CLIENT_SUPPLIED suites green and UNEDITED  PASS  blob-identical to master
    TASK-913 5+5 chain still green             PASS  li5 survives
    observability remains decision-neutral     PASS
    test_generate baseline not worse           PASS  56 / 2 / 1, same names
    no unrelated changes                       PASS  7 src files, 5 tests, 5 docs

`test_only_the_last_subject_may_claim_finality` is red with 3 failures on
merged master and was red identically before — pre-existing, not ours.

## WHAT DID NOT CHANGE

`verification.py` semantics, `lint.sendable`, the Productive verification
policy, `_candidate_steps`'s hold decision, the writer contract,
qualification, Second Brain, Offer Engine. Part B logs the reason and changes
no decision: candidate steps are byte-identical with `store.log` neutered.

Rachele's hold reason still reproduces verbatim: *"contactout says valid but
the primary is missing, and policy does not clear on the secondary alone"*.

## TWO OPERATIONAL NOTES WORTH KEEPING

- **A dead claim pid does not mean a dead worker.** `claim_task.py --reap` is
  deliberately disabled and says why: the recorded pid is the CLAIMING SHELL,
  which exits immediately. TASK-917's claim looked abandoned — dead pid, no
  commit, a worktree on the wrong branch — while live `qwen-code` processes
  were working it. Releasing it would have put two workers on one task.
  **Check for live `qwen-code` processes, not the recorded pid.**
- **Something other than the production session was dispatching.** TASK-917
  and TASK-565 were both claimed at `09:51:4x` by workers this session did not
  dispatch. The pool is not as stopped as the 09-29 handoff records.

## NEXT — UNCHANGED AND STILL GATED

1. Re-run the PRIMARY `deliverable` verifier for `rcrumpler@2020companies.com`.
2. Apply the canonical verification policy, unchanged.
3. If it clears, regenerate the SAME Rachele through the canonical path.
4. Inspect the actual rendered copy; only then the review-only Slack artifact.

**The pre-existing `test_generate` retry defect (`retry_prompts == 2` where
the contract expects 1) remains a HARD BLOCKER before autonomous batching.**
Do not start 5-company batches on the strength of this merge.
