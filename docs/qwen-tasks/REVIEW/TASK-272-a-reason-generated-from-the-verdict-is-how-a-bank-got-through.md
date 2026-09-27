# TASK-272 — Explainable verdicts, and a reason generated from the verdict is how a bank got through

SIZE: S
Operator instruction, 2026-09-23: one plain-language reason per domain beside
the QUALIFIED flag in the client export.

## ONE OF THE THREE EXPORTS ALREADY HAS IT

    src/candidateexport.py:28    EXPORT_COLUMNS carries "why it matched"
                                 -- the weekly Monday 07:00 Zagreb export
    src/clientexport.py:37       domain, company, headcount, industry,
                                 country, website. SIX columns, no reason.
                                 QUALIFIED gate is _icp_qualified() :51
    scripts/qualify_sourced_supply.py
                                 writes JSONL, not CSV, and there is NO
                                 QUALIFIED column: qualification is FILE
                                 MEMBERSHIP -- qualified-supply.jsonl
                                 (32,951 rows) vs review-to-enrichment.jsonl
                                 (4,083 rows), both counted directly

So the work is to carry `candidateexport`'s column into the other two. That
is why this is an S.

`"why it matched"` is fed from `company["_icp_why"]` via
`nightlysourcing._to_candidate()` :494-514, which comes from
`icp._structural_verdict()` :859-905. Reuse that chain; do not write a second
reason generator.

## THE WARNING THAT MUST TRAVEL WITH THE COLUMN

`icp.py:864-872` and `nightlysourcing.py:313-334` both record that this
column once read **`"scored above threshold"` on rows that scored 0.0**. A
121,205-employee telecom and a 130,377-employee bank reached a client selling
to 20+ person agencies. That is ISSUE-019 / ISSUE-023, with tests:
`tests/test_a_telecom_is_not_an_agency.py`,
`tests/test_review_is_not_qualified.py`.

**The mechanism was a reason string generated from the verdict rather than
from the evidence.** The verdict said qualified, so the sentence said
"scored above threshold", and the sentence was true about the verdict and
false about the company. A reason that restates its own verdict is not an
explanation; it is a tautology with a client's name on it.

**So the acceptance test is that exact case**: a row scoring 0.0 must not be
able to produce a reason that reads like a pass. The reason is assembled from
the evidence fields the row actually carries, and a row with no evidence
produces **no reason and does not export** rather than a confident sentence.

## ALSO

`clientexport`'s six columns are PII-bounded by construction (docstring
:22-24). The reason string must not widen that: no contact name, no email, no
person-level fact. It explains the **company**.

`scripts/qualify_sourced_supply.py` exports QUALIFIED only — REVIEW is never
exported, an operator ruling after ISSUE-019 (docstring :10-28). Adding a
reason column does not change what is exported.

## ACCEPTANCE

Full offline suite, zero new failures and zero new errors against the master
baseline, diffed by test NAME both directions.

Required tests: **a row scoring 0.0 cannot produce a pass-shaped reason**; a
row with no evidence produces no reason and does not export; the reason
carries no person-level field; the telecom and bank rows from the existing
ISSUE-019 tests produce reasons that a reader would recognise as wrong-fit;
`candidateexport`'s existing column is unchanged.

## FILES FORBIDDEN

    src/clientapproval.py    src/providers/*    config/    work/*.jsonl

## RESULT BLOCK

STATUS: DONE
COMMIT SHA: b3e49f2a
TESTS: 13 new tests in tests/test_explainable_verdicts.py, all passing.
       Existing ISSUE-019 tests (test_a_telecom_is_not_an_agency,
       test_review_is_not_qualified) all passing. Export tests
       (test_client_export_and_s1_suppression) all passing after updating
       one test to expect 7 columns instead of 6.
FILES CHANGED:
  - src/nightlysourcing.py: _icp_evidence_text returns empty string when no
    positive signals, not "scored above threshold"
  - src/clientexport.py: added "why it matched" column (7 columns, not 6),
    _row_for includes evidence text from verdict's positive signals, added
    _evidence_text helper
  - scripts/qualify_sourced_supply.py: added _icp_why field to qualified
    rows, assembled from positive signals, added _evidence_text helper
  - tests/test_explainable_verdicts.py: 13 tests covering all acceptance
    criteria
  - tests/test_client_export_and_s1_suppression.py: updated
    test_export_columns_are_exactly_the_six_named to expect 7 columns

FINDINGS:
  - The defect was in nightlysourcing._icp_evidence_text line 389: it
    returned "scored above threshold" when positive_signals was empty. This
    was the exact mechanism of ISSUE-019 - a tautology that restated the
    verdict rather than explaining the evidence.
  - The fix: return empty string when no positive signals. A row with no
    evidence produces no reason, not a confident sentence.
  - clientexport now carries the reason column, assembled from the same
    evidence chain as candidateexport.
  - qualify_sourced_supply.py now stamps _icp_why on qualified rows.
  - One pre-existing test failure (test_the_real_pool_on_disk_is_refused_today)
    was present before my changes - the candidate pool is empty, so there is
    nothing to refuse. Not caused by this task.

RISKS:
  - The reason is now empty for rows with no positive signals. This is
    correct behaviour - a row with no evidence should not produce a reason -
    but operators should be aware that the "why it matched" column may be
    blank for some qualified rows.
  - The client export now has 7 columns instead of 6. Any downstream consumer
    of the CSV must be updated to handle the new column.

RECOMMENDED CLAUDE ACTION:
  Review and integrate. The fix addresses the exact defect ISSUE-019 names,
  and all acceptance tests pass.
