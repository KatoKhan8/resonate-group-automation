PRIORITY: P0
SIZE: M
DEPENDS: TASK-914

# TASK-915 — the customer-outcome class is not a verb list

**Operator, Zvonimir, 2026-09-29.** TASK-914's candidate
(`origin/qwen-worker-5-r23` @ `89707130`) was adversarially verified and
**BLOCKED**. Full evidence: `docs/TASK-914-VERIFICATION-BLOCKED-2026-09-29.md`.

**This task repairs ONE thing: the customer-outcome DETECTOR.** Everything
else on that branch was independently verified sound and **must be preserved
unchanged** — see PRESERVE below. **Do NOT redesign TASK-913. Do NOT build a
second claim framework. No provider writes. No other account.**

## THE MEASURED FAILURE

The detector is **tense-bound and number-bound**. It refuses the past tense
and allows the same assertion in every other form. Measured through the real
gate, `generate._step_refusals`, on BOTH channels, with lint satisfied so the
claim gate is the only variable:

    REFUSED   our clients improved project margins
    ALLOWED   our clients improve project margins
    ALLOWED   our clients are improving project margins
    ALLOWED   our clients can improve project margins
    ALLOWED   our clients usually improve project margins
    ALLOWED   customers reduce costs
    ALLOWED   typical clients see better margins      <- operator variant 8
    ALLOWED   customers usually improve profitability <- operator variant 9

**14 of 23 matrix assertions escape.** Two root causes, both `src/claims.py`:

1. `_OUTCOME_VERBS` holds only past tense / past participle. `improve`,
   `reduce`, `save`, `increase`, `see` are absent, so `_CUSTOMER_OUTCOME_RE`
   cannot fire on them.
2. `_BENCHMARK_PHRASE` has `typical\s+client` inside a trailing `\b`, so it
   matches "typical client" and **fails on the plural "typical clients"**.

**DO NOT fix this by pasting the escaping strings into a list.** A list
extension fails identically on the next phrasing. Model the semantic
structure:

    CUSTOMER SUBJECT  +  OUTCOME / IMPROVEMENT ASSERTION

robust across tense, aspect, modality, adverbs and singular/plural — for the
subject AND for the benchmark phrasing.

## THE SEMANTIC CONTRACT

When no licensed customer-outcome / case-study / benchmark evidence exists, a
prospect-facing assertion that customers, clients, users or teams **achieve,
achieved, are achieving, have achieved, can achieve, usually achieve, or
otherwise experience** a business outcome because of the product is REFUSED.

Outcome predicates include at least: improve/reduce/save/increase margins,
costs, time, revenue, profitability, resource allocation — and the same
assertion shaped as a benchmark, a typical result, or an offer to share one.

## THE MATRIX — every one must REFUSE, on BOTH channels

Run with NO licensed customer-outcome evidence:

    our clients improved project margins
    our clients improve project margins
    our clients are improving project margins
    our clients have improved project margins
    our clients can improve project margins
    our clients usually improve project margins
    customers reduced costs
    customers reduce costs
    customers can reduce costs
    customers usually reduce costs
    customers saved time
    customers save time
    customers can save time
    customers increased revenue
    customers increase revenue
    customers increased profitability
    customers increase profitability
    clients improved resource allocation
    clients improve resource allocation
    a typical client sees better margins
    typical clients see better margins
    a typical client improves margins
    typical clients improve margins

## NEGATIVE CONTROLS — these must NOT be refused by your rule

**Do not turn this into a generic ban on `improve`, `reduce`, `save`,
`increase`, `margin` or `profitability`.** Those words are legitimate when
they are not an unsupported customer-outcome assertion:

    Productive provides real-time project margin visibility.     capability
    Productive tracks quote versus actual burn.                  capability
    Would improving margin visibility be useful?                 question
    Are you trying to reduce the time spent reconciling data?    question
    Your website says you provide retail merchandising services. prospect fact

A question about the PROSPECT's own process is not a customer-outcome claim.
A licensed Productive capability is not a customer-outcome claim.

**The discriminator that proves you modelled the class and not the
vocabulary:** a negative control must be **evidence-insensitive**. Whatever
the existing authority decides about it, that decision must NOT change when
customer-outcome evidence is licensed. A real customer-outcome assertion MUST
change: refused without evidence, released with it. A blanket word ban fails
this test, because it would still refuse with evidence present.

## LICENSED EVIDENCE — unchanged authority

The same assertion MAY pass when the canonical authority genuinely licenses
customer-outcome / case-study / benchmark evidence. **Do not invent evidence.
Do not change `offers.missing()` semantics to satisfy a test.** Use a
controlled fixture: the canonical `offers.missing()` shape with the
`customer case studies` and `verified benchmarks` keys absent.

## CHANNEL PARITY

One authority protects EMAIL and LINKEDIN. **Do not add a LinkedIn-only
regex.** Prove refusal through the actual gate path on both channels.

## PRESERVE — verified sound, do not touch

- **TASK-913 chain.** writer 5+5 -> SequencePlan 5+5 -> Bison 5 email steps ->
  HeyReach `li1..li5`, **li5 survives**. One authority
  `cadencelibrary.LINKEDIN_WRITER_KEYS`. **No four-element cap.**
- **Channel-parity wiring** in `generate._step_refusals` — already correct and
  mutation-proved load-bearing. Only the detector is wrong.
- **TASK-914 Part B observability** — verified decision-neutral. Keep it.
  Candidate steps are byte-identical with `store.log` neutered; the HOLD
  stands. **Do NOT change** `verification.py` semantics, `lint.sendable`
  semantics, or the Productive verification policy. Rachele stays HELD.
- **CLIENT_SUPPLIED boundary.** Productive knowledge guides strategy, offer
  and value proposition and licenses NOTHING about a prospect. Both boundary
  suites stay green and **UNEDITED**.

## Acceptance

1. Every one of the 23 matrix assertions above is REFUSED in an EMAIL body.
2. Every one is REFUSED in a LINKEDIN message, through the same authority.
3. Each refusal is RELEASED when the evidence fixture licenses customer
   outcomes — proving an evidence rule, not a word ban.
4. **NEGATIVE CONTROL:** each of the five controls is evidence-INSENSITIVE,
   and the capability statements and questions are not refused at all.
5. **NEGATIVE CONTROL:** `test_a_client_csv_fact_cannot_license_a_claim` and
   `test_a_client_supplied_figure_licenses_no_claim_in_either_gate` stay green
   and **UNEDITED** — assert the files are byte-identical to master.
6. TASK-913's 5+5 chain still green, `li5` still survives.
7. Part B observability still decision-neutral; `lint.sendable` and the
   verification policy unchanged — assert it, do not merely avoid touching it.
8. **MUTATION:** neuter your claim rule in-memory; acceptances 1 and 2 must go
   RED for that reason. Restore and verify byte-identical by sha256. Files are
   **CRLF** — an `\n`-anchored regex matches zero times and the mutation
   becomes a silent no-op. **Do not commit mutation code.**
9. `test_generate` signature unchanged: `Ran 56`, `failures=2`, `errors=1`.

### ACCEPTANCE COMMANDS

    py -3 -m unittest tests.test_task915_customer_outcome_semantic_class
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

Both are red identically on master `1d524ad7` and on `89707130`. They are NOT
yours. **If either signature changes at all, STOP and report it.**

## Files

`src/claims.py` — the detector, and only the detector. Plus
`tests/test_task915_customer_outcome_semantic_class.py`, which you write.

**Do NOT touch** `src/verification.py`, `src/lint.py`, `src/offers.py`,
`src/secondbrain.py`, `src/packfacts.py`, `src/copystages.py`,
`src/cadencelibrary.py`, `src/sequenceplan.py`, `src/generate_campaign.py`,
`src/skills/*`. `src/generate.py` should need NO change — the parity wiring is
already correct; if you believe it does, say why before editing it.

## RULES THAT OUTRANK FINISHING

- **YOU START ON `master`. YOUR FIRST COMMAND IS:**

      git merge --no-edit origin/qwen-worker-5-r23

  That branch (`89707130`) carries BOTH TASK-913 and TASK-914 and must be
  preserved. **Do not re-merge TASK-913 by hand** — it is already inside that
  merge. Verify before you start: `git log --oneline -1` should show the
  merge, and `py -3 -c "from src import claims; print(hasattr(claims,
  'customer_outcome_claim'))"` must print `True`. If it prints `False` the
  merge did not land and you must STOP rather than reimplement TASK-914.
- **NEVER WIDEN A GATE.** This task only ever makes the system refuse MORE —
  except that a genuinely licensed claim must still pass.
- **A test count is never a PASS.** Name the path, the negative control, the
  killed mutation.
- **PROVIDER WRITES = 0.** `sending.live` false. Production `work/` READ-ONLY.
- Suite logs OUTSIDE the repository; a suite with no `Ran N tests` line is an
  absent measurement.
- **Commit every file you touch.** Push to your own branch, verify the remote
  with `git rev-parse`. Do NOT merge to master. Do NOT post to Slack.
- Report **CLAIM / AUTHORITY / MEASURED AT / STATE** and your branch head SHA.

**The previous candidate refused one tense and shipped five others. The class
is the contract, not the conjugation.**
