# QA Lead Pack Check — 2026-09-25

**TASK-294.** Lane F, the per-lead research pack check.

## What was built

`scripts/qa/check_lead_pack.py` — a QA check that runs before every push
and answers: **does every lead in this batch carry at least one research
fact that is provably about THAT company, with a source, a date and a
snippet — and does the copy's first line actually use one?**

### The four rules

| Rule | What it checks |
|------|----------------|
| `pack_present` | At least one admitted fact for this lead's account |
| `fact_has_source_date_snippet` | Each admitted fact carries all THREE |
| `opener_uses_a_pack_fact` | The first line of step 1 references a pack fact |
| `no_claim_outside_the_pack` | No company claim in any step traces to nothing |

### The report that is not a rule

**Identity** — per lead: `admitted` / `refused` / `unverifiable` counts,
reported separately and **never summed into "covered"**. `unverifiable` is
NOT a pass.

### The three sets

Every lead lands in exactly one of:

| Set | Meaning |
|-----|---------|
| `admitted` | Carries at least one admitted pack fact |
| `uncovered` | Carries only unverifiable or refused facts (or zero facts) |
| `no_record` | Matches no queue record at all |

These three MUST add to the subject count. A join that silently drops the
leads with no record is the defect lane D measured at 31%.

## Design decisions

### Identity is imported, not reimplemented

`src.packfacts.identity_of` is the ONE test both the send path and this
check ask. A second copy of an identity test is how the two come to
disagree about who a fact belongs to. The 50-of-71 precedent — where
`companyName` admitted a stranger's open roles into a client's email —
is what this rule prevents.

```python
from src.packfacts import identity_of, pack_for, ADMITTED, REFUSED, UNVERIFIABLE
```

### `unverifiable` is NOT a pass

"We could not ask" and "we asked and the answer was no" are different
problems with different fixes. Folding them together reports the second
as the first. The output says "NOT a pass" explicitly.

### The join key

Rendered rows are joined to queue records by **email address** — the same
key `scripts/packfact_check.py` uses. Lane D measured 291 of 927 rendered
rows matching no queue record at all; a join that matches everything is a
join that is not asking.

### `subjects == 0` is VACUOUS, exit 2

If the join produces zero leads, that is the finding and not a clean run.
The result states WHY the set was empty.

## Tests

`tests/test_a_pack_fact_must_belong_to_this_company.py` — 26 tests, all
passing. One constructed failure per rule:

| Test | Rule | What it asserts |
|------|------|-----------------|
| `test_lead_with_zero_admitted_facts_fires` | `pack_present` | A lead whose only fact belongs to another company fires |
| `test_fact_missing_source_fires` | `fact_has_source_date_snippet` | Missing source is counted |
| `test_fact_missing_date_fires` | `fact_has_source_date_snippet` | Missing date is counted |
| `test_fact_with_all_three_does_not_fire` | `fact_has_source_date_snippet` | A well-formed fact passes |
| `test_generic_opener_fires` | `opener_uses_a_pack_fact` | A generic opener with no pack reference fires |
| `test_opener_referencing_pack_fact_does_not_fire` | `opener_uses_a_pack_fact` | An opener using a pack fact passes |
| `test_invented_specific_fires` | `no_claim_outside_the_pack` | An invented $50M figure fires |
| `test_fact_from_different_company_is_refused` | identity | `identity_of` returns REFUSED for a different domain |
| `test_plausible_name_same_domain_is_admitted` | identity | Same domain, different name → ADMITTED |
| `test_no_website_no_source_is_unverifiable` | identity | No identity signal → UNVERIFIABLE |
| `test_refused_fact_does_not_count_as_admitted` | identity + `pack_present` | Refused fact → uncovered |
| `test_unverifiable_is_not_a_pass` | identity + `pack_present` | Unverifiable fact → uncovered |
| `test_unmatched_row_lands_in_no_record` | three sets | No queue match → `no_record` set |
| `test_mixed_sets_sum_to_subjects` | arithmetic | Three sets sum to subjects |
| `test_empty_rendered_is_vacuous` | vacuous | Zero subjects → VACUOUS verdict |
| `test_cache_with_wrong_company_rows_reports_them` | negative control | Cache audit finds wrong-company rows |
| 8 `identity_of` direct tests | identity | All three verdicts, www normalisation, record_id mismatch, LinkedIn host |

## The negative control

`--audit-pack-cache` runs `identity_of` over a research-pack cache and
reports the 50-of-71 shape. Against the quarantined pre-fix pilot cache
(`work/researchpack-pilot-cache.PRE-FIX-DO-NOT-SERVE.json`), lane D
measured:

```
source                       this    other  unknown
company_slug                   13        2        2
open_roles                     21       50        0

accounts where NO row was this company: 9
```

**50 of 71 job rows refused on identity**, reproducing the measurement
exactly. Five of the eight accounts that returned job rows had every one
of their ten rows belonging to somebody else.

The quarantined cache file is not present in this worktree (it lives in
production `work/` which is Claude's). The negative control is owed from
Claude's worktree.

## The 128 — LIVE RUN OWED

The production data (`work/stage/s7-copy.jsonl` and `work/queue.jsonl`)
is not present in this worktree. Per QWEN.md:

> **So: do not run `py -3 -m src.generate --live` expecting it to change
> production state. It will not.** Generation against the real queue is
> Claude's, run from Claude's worktree.

The live run command is:

```
py -3 scripts/qa/check_lead_pack.py \
    --phase pre_push \
    --workspaces <path-to-production-work-copy> \
    --json work/qa/<run>/lead_pack.json
```

The result block reports what the tests prove and what the live run is
owed to deliver.

## What this does NOT do

- **It does not call any provider.** No EmailBison, no HeyReach, no Apify.
  Zero Apify calls — the free-crawl route was chosen precisely so today's
  push costs no Apify credits.
- **It does not edit lane D's files.** `src/packfacts.py`,
  `scripts/packfact_check.py`, `src/copylint.py` are read-only. Defects
  go in FINDINGS as proposed tasks.
- **It does not write to `work/`** except `work/qa/<run>/`.
- **It does not commit prospect PII.** No snippets, no real names. Ids
  and snippets go under `work/qa/<run>/`; counts go in the doc.

## Files

| File | Purpose |
|------|---------|
| `scripts/qa/__init__.py` | The QA registry |
| `scripts/qa/check_lead_pack.py` | The check |
| `tests/test_a_pack_fact_must_belong_to_this_company.py` | 26 tests |
