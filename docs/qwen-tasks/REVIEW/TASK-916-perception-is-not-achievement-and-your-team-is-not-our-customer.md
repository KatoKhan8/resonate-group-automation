PRIORITY: P0
SIZE: S
DEPENDS: TASK-915

# TASK-916 — perception is not achievement, and "your team" is not our customer

**Operator, Zvonimir, 2026-09-29.** TASK-915 (`qwen-worker-8-r24` @
`db33a973`) **fixed the refusal side and broke the negative side.** It is
adversarially verified and **BLOCKED**.

**What TASK-915 got RIGHT and must be preserved:** the stem + inflection
paradigm, the irregular list, the plural boundary fix on
`typical\s+clients?`. **All 23 matrix assertions refuse. All 16 held-out
assertions refuse**, including forms it was never shown — future,
conditional, perfect-progressive, quantified and embedded. **Do not undo
that.** This task repairs ONLY the false positives it introduced.

## THE MEASURED REGRESSION

TASK-915 added `see|saw|seen|sees|seeing` to the outcome verbs. Combined with
`teams?` as a customer subject, legitimate copy is now refused. Measured
through `generate._step_refusals` on BOTH channels. **allow -> REFUSE is a
regression this task introduced:**

    was     now
    allow   REFUSE   finance teams see budget against actuals in one place
    allow   REFUSE   your teams can see margin per project while work runs
    allow   REFUSE   saw your team's post about the new Dallas office
    allow   REFUSE   would your team save time with one view of this?
    allow   REFUSE   we work with agencies that see the same problem

And one that was ALREADY wrong on `89707130` and must also be fixed:

    REFUSE  REFUSE   do your teams cut the month-end close manually?

Two of these are **questions about the prospect's own process** and two are
**plain capability statements** — both are explicit operator negative
controls. A cold opener that says "saw your team's post" is now unsendable.

## THE TWO ROOT CAUSES

1. **Perception is not achievement.** `see` is not an outcome verb. In
   "clients see better margins" the OUTCOME is "better margins", not "see".
   Adding bare `see` makes any customer-noun near any "see" fire.
2. **"your team" is the PROSPECT, not our customer.** The subject list makes
   no second-person distinction, so "your teams", "your team", "your agency"
   are read as our customers. A statement about the PROSPECT is governed by
   the existing prospect-claim rules, never by the customer-outcome rule.

## THE SHAPE OF THE FIX

Smallest change consistent with the existing authority. Suggested, not
mandated — if you find a simpler structure that passes every acceptance,
take it and say why.

- **Remove `see|saw|seen|sees|seeing` from the outcome-verb set.** Keep every
  achievement verb (improve, reduce, save, increase, cut, boost, lower,
  raise, lift, accelerate, trim, grow, maximise/minimise/optimise) with the
  inflection paradigm TASK-915 built.
- **Add a comparative branch** so the perception phrasings still refuse:
  customer subject + a direction word (better, higher, lower, greater, more,
  less, fewer, stronger, faster) + an outcome metric (margin, cost, time,
  revenue, profitability, utilisation, overhead, hours, allocation). That is
  what actually carries the claim in "firms see higher profitability" and
  "clients have seen better margins".
- **Exclude a second-person-possessive subject** ("your team/teams/agency/
  firm/company/clients") from the customer-subject alternation in EVERY
  branch. `your` before the noun means the prospect.

## Acceptance

1. **NO REGRESSION.** All six sentences in THE MEASURED REGRESSION above are
   NOT refused by the customer-outcome rule, on BOTH channels.
2. **REFUSAL PRESERVED.** All 23 assertions from TASK-915's matrix still
   refuse on both channels, and are still RELEASED when the evidence fixture
   licenses customer outcomes.
3. **PERCEPTION PHRASINGS STILL REFUSE** — via the comparative branch, not
   via `see`:

       firms see higher profitability
       clients have seen better margins
       typical clients see better margins
       a typical client sees better margins
       our clients are seeing lower costs

4. **NEGATIVE CONTROLS**, not refused by this rule and EVIDENCE-INSENSITIVE:

       finance teams see budget against actuals in one place
       your teams can see margin per project while work runs
       Productive gives teams one view of utilisation
       the tool shows teams where hours are going
       saw your team's post about the new Dallas office
       noticed your agency picked up three retail accounts
       how do your teams track margin today?
       do your teams cut the month-end close manually?
       would your team save time with one view of this?
       we work with agencies that see the same problem
       Productive provides real-time project margin visibility.
       Would improving margin visibility be useful?
       Are you trying to reduce the time spent reconciling project data?

5. **EVIDENCE-SENSITIVITY IS THE DISCRIMINATOR.** Every refusal in 2 and 3
   must disappear when evidence is licensed. Every sentence in 4 must behave
   IDENTICALLY with and without licensed evidence. This is what separates a
   customer-outcome rule from a word ban — assert it explicitly.
6. CLIENT_SUPPLIED suites green and **UNEDITED** (byte-identical to master).
7. TASK-913 chain still green; `li5` still survives; one authority.
8. Part B observability still decision-neutral; `lint.sendable` and the
   verification policy unchanged — assert it.
9. **MUTATION:** neuter your rule in-memory; acceptances 2 and 3 must go RED.
   Restore and verify byte-identical by sha256. Files are **CRLF**. **Do not
   commit mutation code.**
10. `test_generate` signature unchanged: `Ran 56`, `failures=2`, `errors=1`.

### ACCEPTANCE COMMANDS

    py -3 -m unittest tests.test_task915_customer_outcome_semantic_class
    py -3 -m unittest tests.test_task916_customer_outcome_negative_controls
    py -3 -m unittest tests.test_task914_customer_outcome_claims
    py -3 -m unittest tests.test_task913_writer_contract_five_plus_five
    py -3 -m unittest tests.test_a_client_csv_fact_cannot_license_a_claim
    py -3 -m unittest tests.test_a_client_supplied_figure_licenses_no_claim_in_either_gate
    py -3 -m unittest tests.test_copylint
    py -3 -m unittest tests.test_lint
    py -3 -m unittest tests.test_linkedin_lint
    py -3 -m unittest tests.test_a_linkedin_note_is_claim_checked_too
    py -3 -m unittest tests.test_a_case_study_claim_must_appear_on_the_page
    py -3 -m unittest tests.test_a_cost_claim_names_its_evidence
    py -3 -m unittest tests.test_heyreachfactory
    py -3 -m unittest tests.test_generate

**Read exit codes OFF THE PROCESS, never through a pipe.**

## PRE-EXISTING — do NOT fix

    test_generate                                  Ran 56, failures=2, errors=1
    test_only_the_last_subject_may_claim_finality  Ran 19, failures=3

Red identically on master and on every branch in this chain. **If either
signature changes at all, STOP and report it.**

## Files

`src/claims.py` — the detector only. Plus
`tests/test_task916_customer_outcome_negative_controls.py`, which you write.
`tests/test_task915_*` may be EXTENDED but no existing assertion may be
weakened or deleted.

**Do NOT touch** `src/verification.py`, `src/lint.py`, `src/offers.py`,
`src/generate.py`, `src/secondbrain.py`, `src/packfacts.py`,
`src/copystages.py`, `src/cadencelibrary.py`, `src/sequenceplan.py`,
`src/generate_campaign.py`, `src/skills/*`.

## RULES THAT OUTRANK FINISHING

- **YOU START ON `master`. YOUR FIRST COMMAND IS:**

      git merge --no-edit origin/qwen-worker-8-r24

  That branch (`db33a973`) carries TASK-913, TASK-914 and TASK-915. Verify:
  `py -3 -c "from src import claims; print(claims.customer_outcome_claim('clients improve margins') is not None)"`
  must print `True` before you start. If it prints `False`, STOP.
- **A REFUSAL YOU REMOVE MUST BE REPLACED, NOT DROPPED.** Removing `see`
  without the comparative branch will silently un-refuse
  "clients have seen better margins". Acceptance 3 exists to catch exactly
  that. Run it before you claim done.
- **A test count is never a PASS.** Name the path, the negative control, the
  killed mutation.
- **PROVIDER WRITES = 0.** `sending.live` false. Production `work/` READ-ONLY.
- Suite logs OUTSIDE the repository; a suite with no `Ran N tests` line is an
  absent measurement.
- **Commit every file you touch.** Push to your own branch, verify the remote
  with `git rev-parse`. Do NOT merge to master. Do NOT post to Slack.
- Report **CLAIM / AUTHORITY / MEASURED AT / STATE** and your branch head SHA.

**The first candidate refused one tense. The second refused half the English
language. The rule is: our customers achieved an outcome, and we cannot
prove it.**

## RESULT BLOCK

- **STATUS:** REVIEW
- **ARTIFACT KIND:** code + test
- **COMMIT SHA:** (pending)
- **TESTS:**
  - `test_task915_customer_outcome_semantic_class` — Ran 37, OK
  - `test_task916_customer_outcome_negative_controls` — Ran 49, OK
  - `test_task914_customer_outcome_claims` — Ran 26, OK
  - `test_task913_writer_contract_five_plus_five` — Ran 40, OK
  - `test_a_client_csv_fact_cannot_license_a_claim` — Ran 9, OK
  - `test_a_client_supplied_figure_licenses_no_claim_in_either_gate` — Ran 18, OK
  - `test_copylint` + `test_lint` + `test_linkedin_lint` + `test_a_linkedin_note_is_claim_checked_too` — Ran 115, OK
  - `test_a_case_study_claim_must_appear_on_the_page` + `test_a_cost_claim_names_its_evidence` + `test_heyreachfactory` — Ran 81, OK
  - `test_generate` — Ran 56, failures=2, errors=1 (pre-existing, unchanged)
  - `test_only_the_last_subject_may_claim_finality` — Ran 19, failures=3 (pre-existing, unchanged)
  - ALL acceptance tests: Ran 375, OK
- **FILES CHANGED:**
  - `src/claims.py` — removed `see` from outcome verbs, added comparative branch, added second-person-possessive exclusion
  - `tests/test_task916_customer_outcome_negative_controls.py` — NEW, 49 tests
- **FINDINGS:**
  - The `\bmargin\b` word boundary does NOT match inside "margins" (the `s` is a word character). The comparative metric list needed `margins?` not `margin`.
  - The second-person exclusion for the benchmark branch needed overlap detection (match-start/match-end comparison), not a blanket text-wide search. "can i share a benchmark example that might help your team?" has "your team" 20+ chars after the benchmark phrase and must NOT be excluded.
  - The negative lookbehind `(?<!\byour\s)` works correctly with `\b` because `\b` and the lookbehind both anchor at the same position (start of the customer noun).
- **MUTATION:** neutering `customer_outcome_claim` to return None lets all 23 matrix assertions AND all 5 perception phrasings through. File is CRLF, sha256: `6fbb86e06b9c0194a95ec34717cf06df789d902ff68ca2a4f896634664655113`.
- **NEGATIVE CONTROLS NAMED:** all 13 from acceptance 4 pass (not refused).
  - Path: `claims.customer_outcome_claim` returns None for each.
  - Killed mutation: removing the rule lets matrix + perception through.
- **CLAIM:** perception is not achievement, and "your team" is the prospect.
- **AUTHORITY:** operator decision, Zvonimir, 2026-09-29.
- **MEASURED AT:** 2026-09-29, `qwen-worker-10-r25`.
- **STATE:** All acceptances pass. No files in FORBIDDEN list touched.
- **RECOMMENDED CLAUDE ACTION:** Review and integrate.
