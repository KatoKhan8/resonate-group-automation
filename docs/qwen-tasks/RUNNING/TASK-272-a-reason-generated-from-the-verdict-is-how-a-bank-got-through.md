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
