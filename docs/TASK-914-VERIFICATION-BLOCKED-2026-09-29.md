PRIORITY: READ BEFORE RE-DISPATCHING TASK-914

# TASK-914 — ADVERSARIALLY VERIFIED, **BLOCKED**, NOT MERGED

    verified at   master          1c0af337
                  origin/master   1c0af337
                  branch          origin/qwen-worker-5-r23   89707130
                  merge-base      6190f846

    VERDICT       DO NOT MERGE
    reason        the customer-outcome detector is TENSE-BOUND.
                  Two of the operator's own nine listed adversarial
                  variants still ship.

Nothing sent by this work. Provider writes 0, enrolments 0, prospect-facing
sends 0, campaign activation 0. **No `deliverable` verification call was made** —
Phase 4 is gated on TASK-914 being verified, and it is not. No credit spent.

---

## THE BLOCKER

`claims.customer_outcome_claim()` matches only PAST-TENSE outcome verbs
(`_OUTCOME_VERBS` = improved, increased, reduced, saved, …). The semantic class
the task defines — *a customer/client outcome, improvement, benchmark or
typical-result claim without licensed supporting evidence* — is not bounded by
tense. Present and habitual phrasing is how cold copy actually says this, and
it passes every gate.

Measured through `generate._step_refusals()`, the real LinkedIn branch, with
`lint` satisfied so the claim gate is the only variable:

    REFUSED  our clients improved project margins ...        (past)
    ALLOWED  our clients improve project margins ...         (present)
    ALLOWED  customers reduce costs once reporting is ...    (present)
    ALLOWED  typical clients see better margins ...          <-- operator-listed
    ALLOWED  customers usually improve profitability ...     <-- operator-listed
    ALLOWED  clients can improve project margins ...         (modal)

The last two are items 8 and 9 of the nine variants the task explicitly
requires to be refused.

Two distinct root causes, both in `src/claims.py`:

1. **Tense.** `_OUTCOME_VERBS` carries only past tense / past participle.
   `improve`, `reduce`, `save`, `increase`, `see` are absent, so
   `_CUSTOMER_OUTCOME_RE` cannot fire on them.
2. **Plural.** `_BENCHMARK_PHRASE` has `typical\s+client` inside a trailing
   `\b`, so it matches "typical client" and **fails on "typical clients"** —
   the plural is the form a message actually uses.

This is not the hardcoded-sentence failure the task warned against: the
detector generalises across subjects and objects. It fails to generalise
across tense and number.

## WHAT IS SOUND AND SHOULD BE KEPT ON REWORK

Verified independently, not taken from the worker's report:

- **Channel parity is real and load-bearing.** Email and LinkedIn both call
  `claims.check`. Mutation: with `claims.check` neutered in-memory, BOTH
  channels stopped refusing the past-tense regression; restored, both refuse
  again. The wiring is correct — only the detector is too narrow.
- **Negative controls pass. No overblocking.** A plain Productive capability
  statement ("Productive shows margin per project while the work is running")
  is allowed on both channels. So are a bare question and a prospect fact.
- **The licensed-evidence model is respected.** With the two relevant
  `offers.missing()` gaps filled, the same claims pass through. No evidence was
  invented; the gaps were substituted in a controlled fixture.
- **Part B observability is observability only.** Proved by effect: the
  candidate steps are byte-identical with `store.log` live and neutered.
  `store.log` is in-memory only (appends to `rec["log"]`, no disk write).
  `lint.sendable` stays False, the HOLD stands, `verification` semantics and
  the Productive policy are untouched. Rachele's reason reproduces verbatim:
  *"contactout says valid but the primary is missing, and policy does not clear
  on the secondary alone"*.

## TASK-913 ON THIS BRANCH — VERIFIED PASS

The branch also carries TASK-913 (merged from `qwen-worker-3-r22`). It is
sound and is NOT the reason for the block:

    ONE AUTHORITY   cadencelibrary.LINKEDIN_WRITER_KEYS = li1..li5
                    generate_campaign re-exports the same object
                    generate._PLAN_LINKEDIN_ORDER  REMOVED
    WRITER          5 emails + 5 LinkedIn, none empty
    SEQUENCEPLAN    em1..em5, li1..li5
    BISON           1 lead, 5 email steps, every body non-empty
    HEYREACH        li1..li5, li5 SURVIVES, COPY_MAPPING li5 -> connected_4
    approval hash   f27e9b71a306ba1d   (synthetic fixture, not Rachele)

Falsified: restoring a four-key cap in memory loses `li5` and only four keys
survive; restored, five return. No production four-element cap remains in
`generate.py`, `sequenceplan.py` or `generate_campaign.py`.

Residual, non-blocking: `src/skills/linkedin_writing.py` and
`src/skills/campaign_strategy.py` still describe `connect`/`msg1..msg3` in
their `purpose`, `examples_good` and `output` fields, and `generate.py:2056`
says "connect, msg1 to msg3" in a docstring. **These are inert** —
`generate_campaign` uses `email_skill.procedure` (which is
`copystages.WRITER_SYSTEM`) as the system prompt, and nothing in `src/` reads
`examples_good` or `output`. Stale documentation, not a second authority.
`copyprompts.COHORT_SYSTEM` remains dead-path debt; caller evidence unchanged,
not reopened.

## SCOPE — NO UNRELATED WORK

11 files on the branch side, +1196/-39. Every one classifies:

    TASK-913 migration   cadencelibrary.py, copystages.py, sequenceplan.py,
                         generate_campaign.py, skills/cold_email_writing.py
    TASK-914 claim fix   claims.py
    both                 generate.py  (li consumer + claim parity + Part B)
    tests                test_task913_… (436), test_task914_… (353)
    docs                 two task result blocks

The `-309` on `docs/PRODUCTION-HANDOFF-2026-09-29-RACHELE.md` seen in a
two-dot diff is an artifact: the branch predates that file. A merge does not
delete it.

## ACCEPTANCE LEDGER

    TASK-913 5+5 contract                     PASS
    SequencePlan 5+5                          PASS
    Bison / HeyReach projection 5+5           PASS
    LinkedIn claim authority wired            PASS
    email claim path not regressed            PASS
    supported-claim negative control          PASS
    plain-capability negative control         PASS
    CLIENT_SUPPLIED boundary suites           PASS  18 + 9, green and UNEDITED
    verification policy unchanged             PASS
    observability does not alter decision     PASS
    no relevant regression                    PASS
    test_generate signature not worse         PASS  see below
    unsupported outcome claim regression      **FAIL**  <-- THE BLOCKER

## test_generate — UNCHANGED, EXACTLY

    master   1c0af337   Ran 56   failures=2   errors=1
    branch   89707130   Ran 56   failures=2   errors=1

Same three defects, same names. TASK-914 does not make it worse. The
pre-existing retry defect (`retry_prompts == 2` where the contract expects 1)
is untouched and remains a hard blocker before autonomous batching.

Also pre-existing on BOTH master and branch, so not a branch regression:
`test_only_the_last_subject_may_claim_finality` — 3 failures, identical names.

## WHAT REWORK MUST DO

1. Cover the semantic class across **tense, aspect and modality**, not a verb
   list: present, habitual, modal and gerund forms of the same assertion.
2. Fix the `typical\s+client` plural boundary.
3. Keep the negative controls green — a capability statement must stay
   allowed, and the licensed-evidence path must still pass through.
4. Re-run the nine operator variants **and** their present/habitual forms
   through `generate._step_refusals()`, not through the detector alone.

The delivered suite `tests/test_task914_customer_outcome_claims.py` is 26
tests and green, and the defect class still escapes — it exercises only the
past-tense forms. A rework that only adds verbs to the list will fail the same
way on the next phrasing; assert the class, not the vocabulary.

## STATE AT WRITING

    master unchanged, clean, == origin/master
    branch unchanged, clean, NOT merged
    all mutations were in-memory monkeypatches; nothing left in the branch
    RACHELE EMAIL remains HELD, policy untouched
