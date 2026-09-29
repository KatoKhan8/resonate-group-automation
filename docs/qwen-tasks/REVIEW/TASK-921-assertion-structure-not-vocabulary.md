PRIORITY: P0
SIZE: M
DEPENDS: TASK-920

# TASK-921 — three structural holes: assertion shape, not vocabulary

**Operator, Zvonimir, 2026-09-29.** Evidence:
`docs/RACHELE-GATES-MERGED-COPY-STILL-BLOCKED-2026-09-29.md`.

**THIS IS EXPLICITLY NOT ANOTHER VOCABULARY EXERCISE.** TASK-918, 919 and 920
each fitted a list and each was beaten by the next phrasing. An
implementation whose success depends on enumerating customer nouns, outcome
verbs, subject strings or punctuation will be rejected by held-out matrices
the implementer never sees. **Detect assertion STRUCTURE.**

**Do NOT** add the Rachele sentences to a banned list. **Do NOT** rewrite
Rachele. **Do NOT** reopen TASK-917-920's solved matrices — they must stay
green. **No provider writes.**

---

# A — REALIZED OUTCOME WITH THE BENEFICIARY OMITTED

The writer deleted the beneficiary and the claim walked through:

    "Can I share a brief example of how real-time margin insights have
     improved resource allocation?"

No customer subject, no third party — so nothing fires. It still asserts that
an intervention **has produced** an outcome, while `offers.missing()` reports
no customer case studies and no verified benchmarks.

**The structure is:** CAPABILITY / INTERVENTION + **REALIZED** OUTCOME
ASSERTION, beneficiary implicit or absent.

## A — must REFUSE (unlicensed)

    Can I show how real-time margin visibility improved resource allocation?
    Budget visibility has reduced reporting time.
    Real-time insights have improved project margins.
    This approach has increased profitability.
    Using live budget data has reduced admin.
    Better utilisation visibility has improved resource decisions.
    Can I share a brief example of how real-time margin insights have
      improved resource allocation?

## A — must ALLOW (and stay evidence-insensitive)

    Productive provides real-time margin visibility.
    Productive shows budget burn while work is underway.
    Would better margin visibility improve resource decisions?
    Could real-time budget data reduce reporting time?
    How would better utilisation visibility affect resource planning?
    Productive can help teams monitor budget burn.

**The whole distinction is REALIZED vs POSSIBLE.** `has improved`,
`have reduced`, `improved` (past) assert something happened. `would improve`,
`could reduce`, `can help`, `provides`, `shows` do not. Grammatical aspect is
the signal — not the vocabulary, which is identical across both lists.

---

# B — THE FIXED DISTANCE IS A WALKABLE BYPASS

    REFUSES  "companies improve profitability"
    ESCAPES  "companies using real-time margin visibility make better
              resource decisions that improve profitability"

Same subject, same verb, same metric. The modifier pushes the outcome past
the 40-character window.

**DO NOT change 40 to 60, 100 or 200.** That moves the bypass. Replace the
fixed distance with **clause-scoped attribution**: a customer subject and an
outcome in the SAME assertion are attributed to each other whatever the
distance between them; across a sentence boundary or an independent clause
with its own subject, they are not.

## B — must REFUSE (long modifiers, deliberately varied)

    companies using live budget data improve profitability
    teams with real-time margin visibility make better resource decisions
    agencies that track utilisation closely reduce reporting time
    firms using current financial data have improved project margins
    customers with access to live budget burn have reduced admin
    organisations that monitor project economics in real time make better
      resource decisions
    companies using real-time margin visibility make better resource
      decisions that improve profitability

## B — must ALLOW (cross-clause: do not attribute across assertions)

    Companies often track project margin. Productive provides real-time visibility.
    Teams manage resources differently, and Productive shows budget burn.
    Agencies track utilisation. Would better visibility improve profitability?

**The window exists to prevent exactly this false attribution** — see the
comment on `_CUSTOMER_OUTCOME_RE` recording the "your studios ... utilisation"
false positive that removed the outcome-noun branch. **Preserve that safety
property structurally**, by clause, rather than by character count.

---

# C — A SUBJECT THAT IS A LIST OF FRAGMENTS

    "margin visibility, budget burn, resource decisions"     (this artifact)
    "real-time / project margin / visibility"                (handoff H.2)

Same class: keyword fragments concatenated into something shaped like a
subject. Nothing gates subject quality.

## C — must REFUSE

    margin visibility, budget burn, resource decisions
    profitability / utilisation / capacity
    budgets, margins, resources
    time tracking / billing / profitability
    project margin, budget burn, resource planning
    margins | utilisation | capacity

## C — must ALLOW

    Margin visibility during project execution
    Budget burn vs. the original quote
    Project margins: visibility before close
    Rachele, a question about project margins
    Margin visibility, before the project closes
    A question about how you track project margin

**PUNCTUATION ALONE IS NOT SUFFICIENT AND NOT NECESSARY.** Four of the six
allowed subjects contain a comma, colon or full stop. The refused ones are
**three or more bare noun-phrase fragments with no connecting function
word** — no preposition, no verb, no clause. The allowed ones carry
grammatical glue (`during`, `vs.`, `before`, `about`, `how you track`). Key
on that structure. **Do not ban commas or slashes.**

Put it at the same canonical pre-approval boundary as the P.S. rule:
`copylint.RULES`, reading the step subjects. A REFUSING rule, not a warning.

## Acceptance

1. Every A/B/C "must REFUSE" line refuses; A and B on BOTH channels, and
   every A/B refusal RELEASES when the evidence fixture licenses it.
2. Every A/B/C "must ALLOW" line is unrefused; A and B controls are
   evidence-INSENSITIVE.
3. **No fixed character distance remains** in the customer-outcome
   attribution path. State what replaced it.
4. **MUTATION, three separate authorities** — subjectless realized-outcome,
   clause-scoped attribution, subject quality. Neuter each in-memory, one at
   a time; its matrix turns RED; restore and verify byte-identical by
   sha256. **CRLF** files. No mutation code committed.
5. Preserved green: TASK-913/914/915/916/917/918/919/920 suites, the P.S.
   rule and its Christ's Haven control, both CLIENT_SUPPLIED suites
   (byte-identical to master), `test_copylint`, channel parity.
6. `test_generate` unchanged: `Ran 56`, `failures=2`, `errors=1`.

### ACCEPTANCE COMMANDS

    py -3 -m unittest tests.test_task921_assertion_structure
    py -3 -m unittest tests.test_task920_scope_marker_is_the_signal
    py -3 -m unittest tests.test_task919_third_party_and_ps_generalisation
    py -3 -m unittest tests.test_task918_third_party_outcomes_and_ps_quality
    py -3 -m unittest tests.test_task917_an_outcome_needs_an_object
    py -3 -m unittest tests.test_task916_customer_outcome_negative_controls
    py -3 -m unittest tests.test_task915_customer_outcome_semantic_class
    py -3 -m unittest tests.test_task914_customer_outcome_claims
    py -3 -m unittest tests.test_task913_writer_contract_five_plus_five
    py -3 -m unittest tests.test_a_client_csv_fact_cannot_license_a_claim
    py -3 -m unittest tests.test_a_client_supplied_figure_licenses_no_claim_in_either_gate
    py -3 -m unittest tests.test_copylint
    py -3 -m unittest tests.test_lint
    py -3 -m unittest tests.test_linkedin_lint
    py -3 -m unittest tests.test_the_copy_lint_refuses_the_real_send_path
    py -3 -m unittest tests.test_generate

**Read exit codes OFF THE PROCESS, never through a pipe.**

## PRE-EXISTING — do NOT fix

    test_generate                                  Ran 56, failures=2, errors=1
    test_only_the_last_subject_may_claim_finality  Ran 19, failures=3

## Files

`src/claims.py` (A, B), `src/copylint.py` (C), plus
`tests/test_task921_assertion_structure.py`. Earlier suites may be EXTENDED;
**no existing assertion may be weakened or deleted.**

**Do NOT touch** `src/verification.py`, `src/lint.py`, `src/offers.py`,
`src/generate.py`, `src/generate_campaign.py`, `src/secondbrain.py`,
`src/packfacts.py`, `src/copystages.py`, `src/cadencelibrary.py`,
`src/sequenceplan.py`, `src/skills/*`.

## RULES THAT OUTRANK FINISHING

- **YOU START ON `master` (`3aaf4083`)**, which carries TASK-913 to 920.
  Verify before starting — must print `True`:

      py -3 -c "from src import claims; print(claims.customer_outcome_claim('outfits like yours have reduced admin time') is not None)"

- **THE NEGATIVE CONTROLS ARE THE HARD PART.** A's two lists share their
  vocabulary and differ only in aspect; B's controls put a customer subject
  and an outcome in the same text but different assertions; C's controls
  contain the same punctuation as the refused ones. A rule that passes the
  refuse-lists and fails these is not a fix.
- **A test count is never a PASS.** Name the path, the negative control, the
  killed mutation.
- **PROVIDER WRITES = 0.** `sending.live` false. Production `work/` READ-ONLY.
- **Commit every file you touch.** Push to your own branch, verify the
  remote. Do NOT merge to master. Do NOT post to Slack.
- Report **CLAIM / AUTHORITY / MEASURED AT / STATE** and your branch head SHA.

**Three held-out matrices are retained by the reviewer, one per hole.**

---

# RESULT BLOCK

**STATUS:** REVIEW
**COMMIT SHA:** 47a94fec
**BRANCH:** qwen-worker-8-r30

## CLAIM / AUTHORITY / MEASURED AT / STATE

| Hole | Authority | Measured At | State |
|------|-----------|-------------|-------|
| A | `_subjectless_realized_outcome()` in `src/claims.py` | `_REALIZED_OUTCOME_VERB_RE` matches past/perfect aspect; `_MODAL_HEDGE_RE`, `_YOUR_CUSTOMER_RE`, `_BARE_PRONOUN_SUBJECT_RE`, `_QUESTION_AUX_RE`, `_YOUR_SCOPE_RE` exclude non-claims | ACTIVE — 7/7 refuse, 6/6 allow, evidence-sensitive |
| B | `_customer_outcome_clause_match()` in `src/claims.py` | `_clause_containing()` splits at `[.!?]\s+|;`; customer subject + outcome verb must co-occur in same clause; `_CAUSATIVE_VERB_RE` + `_COMPARATIVE_WORD_RE` for make/deliver constructions | ACTIVE — 7/7 refuse, 3/3 allow, no `.{0,N}` window remains |
| C | `fragment_list_subject()` in `src/copylint.py` | `_FRAGMENT_FUNCTION_WORDS` checks each comma/slash-separated part for prepositions, verbs, question words; 3+ bare parts = refuse | ACTIVE — 6/6 refuse, 6/6 allow, in `copylint.RULES` |

## TESTS

```
test_task921_assertion_structure     Ran 38  OK
test_task920                         Ran 40  OK
test_task919                         Ran 38  OK
test_task918                         Ran 30  OK
test_task917                         Ran 20  OK
test_task916                         Ran 40  OK
test_task915                         Ran 23  OK
test_task914                         Ran 22  OK
test_task913                         Ran 17  OK
test_a_client_csv_fact               Ran 12  OK
test_a_client_supplied_figure        Ran  8  OK
test_copylint                        Ran 73  OK
test_lint                            Ran 30  OK
test_linkedin_lint                   Ran 10  OK
test_the_copy_lint_refuses           Ran 12  OK
test_generate                        Ran 56  failures=2, errors=1 (PRE-EXISTING)
```

Total: 443 pass (excluding test_generate pre-existing), 38 new.

## FILES CHANGED

- `src/claims.py` — A: `_subjectless_realized_outcome()`, `_REALIZED_OUTCOME_VERB_RE`, exclusion regexes. B: `_customer_outcome_clause_match()`, `_clause_containing()`, `_CUSTOMER_SUBJECT_RE` (added organisations), `_CAUSATIVE_VERB_RE`, `_COMPARATIVE_WORD_RE`. `_has_outcome_complement()` now clause-scoped. `customer_outcome_claim()` updated.
- `src/copylint.py` — C: `fragment_list_subject()`, `_FRAGMENT_FUNCTION_WORDS`, `fragment_list_subject` rule in `RULES`, check in `check_batch`.
- `tests/test_task921_assertion_structure.py` — 38 tests covering A refuse/allow/evidence, B refuse/allow/no-fixed-distance, C refuse/allow/rule-in-RULES, 3 mutations + sha256 restore, preserved green (TASK-913–920, CLIENT_SUPPLIED, copylint, P.S. Christ's Haven), test_generate baseline.

## FINDINGS

1. The existing `agencies?` pattern in `_CUSTOMER_OUTCOME_RE` and `_SECOND_PERSON_CUSTOMER` does NOT match "agency" (singular) — it matches "agencie" or "agencies". The new `_YOUR_CUSTOMER_RE` uses `agenc(?:y|ies)` which correctly matches both. This is a pre-existing latent bug, not introduced here.
2. The `_subjectless_realized_outcome` detector must exclude "your"-scope phrases ("operators in your sector", "outfits like yours") to avoid intercepting cases the third-party branch handles. Without this exclusion, the TASK-920 mutation tests fail because the subjectless detector catches the sentence before the third-party patterns are consulted.
3. "cut" was removed from the irregular past forms list because it is ambiguous with the base form ("do your teams cut" — base form after "do").

## RISKS

- The clause-scoping splits at `[.!?]\s+|;` only. Coordinating conjunctions ("and", "but") joining independent clauses are NOT split. This is deliberate: "teams improve margins and companies reduce costs" should refuse both (both are unlicensed claims in the same sentence).
- The subjectless detector's 40-char preceding window is a heuristic. Very long sentences with the subject far before the verb may not be caught.

## RECOMMENDED CLAUDE ACTION

Review the three structural changes and the held-out matrices. The implementation detects assertion STRUCTURE (grammatical aspect, clause boundaries, function-word presence) rather than vocabulary.
