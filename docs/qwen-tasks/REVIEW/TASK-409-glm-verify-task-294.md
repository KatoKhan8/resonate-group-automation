PRIORITY: P2
SIZE: S
DEPENDS:

# TASK-409 — GLM first-pass verification: TASK-294 (research-pack QA, identity not presence)

**Operator instruction, 2026-09-27 morning: clear the nine REVIEW branches
with a GLM first-pass verdict each; Claude cherry-picks only what passes.**

Read `docs/GLM-REVIEW-PROTOCOL.md` yourself and follow it exactly.

## Target

TASK-294, in REVIEW on `qwen-worker-12-r9` — per-lead research-pack QA with
identity, not presence (matches the same class of bug the 50-of-71
mismatched-company incident named in `src/packfacts.py`'s own docstring).

## What GLM's pass must produce

1. Confirm the QA check actually verifies IDENTITY (exact company/domain
   match), not just presence of a research pack.
2. Reproduce with a deliberately mismatched pack (right shape, wrong
   company) and confirm it is caught, not passed.
3. Any new finding, file:line.

## Result

Use the protocol's own format and eight dispositions. SAFE TO MERGE or
BLOCKED, and why.

---

## GLM FIRST-PASS VERDICT: SAFE TO MERGE

**Reviewer:** TASK-409 on `qwen-worker-12-r9`
**Date:** 2026-09-27
**Target:** TASK-294, implemented on `origin/qwen-worker-r9` (commits `41d2a0ba`,
`ace6085b`, `6f706daa`, `3487aeee`)

### Correction to prior verdict

The BLOCKED verdict previously appended to TASK-294's task file claimed the
artifacts were "never written". That was wrong. All three artifacts exist on
`origin/qwen-worker-r9`:

    scripts/qa/check_lead_pack.py              (commit 41d2a0ba)
    tests/test_a_pack_fact_must_belong_to_this_company.py  (commit 41d2a0ba)
    docs/QA-LEAD-PACK-2026-09-25.md            (commit ace6085b)

Established with `git log --all --diff-filter=A --name-only`: all three have
add commits on that branch. The prior verdict's `--diff-filter=A` search
missed them.

### 1. Identity, not presence — CONFIRMED

The check imports `packfacts.pack_for` (`check_lead_pack.py:130`) which
internally calls `packfacts.identity_of` for every fact. `identity_of`
returns one of three verdicts:

    ADMITTED      source host matches the account domain
    REFUSED       source host is a different company's domain (via SITE_KEYS)
    UNVERIFIABLE  no host information available

The check reports all three separately in `identity_totals` and the
three-set classification. `unverifiable` is NOT counted as covered.

The result document carries `identity_totals: {admitted, refused,
unverifiable}` as separate fields, never summed.

### 2. Negative reproduction — PASSED

A deliberately mismatched pack (right shape, wrong company) was constructed:

    fact:        "Acme Partners LLC opened a new office in Berlin."
    source_url:  https://acmepartners.llc/news/berlin
    published_at: 2026-03-15
    companyWebsite: https://acmepartners.llc
    account domain: acme.com

Result through the full pipeline:

    identity_of verdict:  REFUSED
    pack_for:             0 admitted, 1 refused
    check classification: only_unverifiable_or_refused
    check verdict:        FAIL
    in three_set.admitted: NO
    in three_set.only_unverifiable_or_refused: YES

The 50-of-71 shape is caught.

### 3. Wiring verification — REAL

Breaking `pack_for` (monkey-patched to admit all facts without identity
check) changes the classification from `only_unverifiable_or_refused` to
`admitted`. The tests are connected to the real identity check, not
asserting on data shape alone.

### 4. Test suite — 32/32 PASS

All 32 tests pass in 0.238s, covering:

    IdentityOfStatesThreeAnswersApart     7 tests (all three verdicts)
    PackForAdmitsOnlyThisAccountsFacts    2 tests
    Rule1PackPresent                      2 tests
    Rule2FactHasSourceDateSnippet         4 tests
    Rule3OpenerUsesAPackFact              2 tests
    Rule4NoClaimOutsideThePack            2 tests
    The50Of71Shape                        2 tests (the critical one)
    ThreeSetClassification                2 tests
    ArithmeticCloses                      1 test
    VacuousOnEmptySubjects                1 test
    IdentityColumnsAreSeparate            2 tests
    JoinKeyIsEmail                        2 tests
    MissingElementsAreCountedIndividually 1 test
    CLIExitCodes                          2 tests

### 5. New findings

**FINDING 1 (minor): `unverifiable_report` is dead code.**
`check_lead_pack.py:121` initializes `unverifiable_report` with per-rule
lists, but nothing ever appends to it. The result's `unverifiable` field
is always `{rule: [] for rule in RULES}`. The `identity_totals` counts are
correct (they come from `n_unverifiable` per lead), but the per-rule
unverifiable breakdown was intended and never wired. Not a safety defect —
the identity totals that matter are correct — but a completeness gap.

**FINDING 2 (informational): opener check uses private `_WORD`.**
`check_lead_pack.py:157` accesses `copylint._WORD`, a module-private regex.
If `_WORD` is renamed, the check breaks silently with an AttributeError at
runtime rather than at import time. Low risk within the same codebase.

### Disposition

| # | Finding | Disposition |
|---|---------|-------------|
| 1 | `unverifiable_report` dead code | EXISTING TASK — cosmetic, non-safety |
| 2 | Private `_WORD` access | ACCEPTED DEFERRED RISK — same codebase |

### Verdict

**SAFE TO MERGE.** The QA check verifies identity (exact domain match), not
presence. The 50-of-71 wrong-company shape is caught. The wiring is real —
breaking `pack_for` changes test outcomes. All 32 tests pass. The two
findings are non-safety and do not block integration.
