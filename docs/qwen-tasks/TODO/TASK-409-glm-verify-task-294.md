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

## GLM VERDICT — 2026-09-27, second pass

**START_MASTER_SHA:** 453dcf57 (qwen-worker-12-r9 HEAD)
**REVIEWED_BRANCH:** origin/qwen-worker-r9 (commits 41d2a0ba..3487aeee)
**PROOF_TYPE:** Static + runtime (tests executed, mutation test applied)

### Correction to the first pass

The first GLM pass (commit 29f54986) reported TASK-294 as BLOCKED because
"none of its artifacts exists on ANY ref." **That was wrong.** The artifacts
exist on `origin/qwen-worker-r9`:

    41d2a0ba  scripts/qa/check_lead_pack.py (411 lines)
    41d2a0ba  tests/test_a_pack_fact_must_belong_to_this_company.py (592 lines)
    ace6085b  docs/QA-LEAD-PACK-2026-09-25.md (150 lines)
    3487aeee  TASK-294 moved to REVIEW

The first pass claimed `--diff-filter=A` across all refs found "zero hits."
It found them — the commits are in `git log --all`. The verdict was wrong.

### Finding 1: The check verifies IDENTITY, not presence — CONFIRMED

`check_lead_pack.py` line 149 calls `packfacts.pack_for(rec)`, which calls
`identity_of(row, domain, record_id=record_id)` for each research fact.
`identity_of` (src/packfacts.py:78-113) checks:

1. record_id stamp mismatch → REFUSED
2. SITE_KEYS (companyWebsite, website, companyDomain, domain) present →
   ADMITTED if same_site(), REFUSED otherwise
3. source_url host matches domain → ADMITTED
4. source_url host does not match → UNVERIFIABLE (not REFUSED — LinkedIn
   host is not the company's)
5. No host at all → UNVERIFIABLE

This is domain/host identity matching, not presence. A fact is admitted
only when it can be shown to belong to THAT account.

### Finding 2: The 50-of-71 shape is caught — CONFIRMED

Test `The50Of71Shape.test_a_stranger_fact_with_a_plausible_name_is_refused`:
- Account domain: `acme.com`
- Fact companyWebsite: `https://acmepartners.llc` (plausible name match)
- Result: REFUSED, pack has 0 facts, unused[REFUSED] has 1

Test `The50Of71Shape.test_the_check_classifies_the_lead_as_not_admitted`:
- End-to-end through `check()`: lead goes to `only_unverifiable_or_refused`
- identity_totals: REFUSED=1, ADMITTED=0

Both tests pass.

### Finding 3: Mutation test — 8 failures when identity is broken

Replaced `identity_of` with a presence check (always returns ADMITTED).
Result: 8 of 32 tests fail, including:

- test_a_stranger_fact_with_a_plausible_name_is_refused
- test_the_check_classifies_the_lead_as_not_admitted
- test_a_stranger_fact_is_not_in_the_pack
- test_a_fact_on_somebody_elses_domain_is_refused
- test_a_stamped_row_for_a_different_record_is_refused
- test_a_fact_with_no_website_and_no_host_is_unverifiable
- test_a_linkedin_host_is_unverifiable_not_refused
- test_refused_and_unverifiable_are_reported_apart

The test suite catches the breakage of identity wiring. The tests assert on
verdicts, not on the presence of a script.

### Finding 4: The check is correct but unconsumed

`check_lead_pack.py` is a standalone CLI script. No QA runner imports it
(TASK-292's runner was never built). No production code calls it. It is
importable and testable, but inert until something invokes it.

This is the house pattern: a component that is correct and unconsumed,
indistinguishable from a working safeguard until someone checks. The code
is sound; the wiring to a pipeline is absent.

### Finding 5: Not merged to master

The implementation lives only on `origin/qwen-worker-r9`. It has never been
merged to master. The task file in TODO still names it as unimplemented
because the BLOCKED verdict from the first pass was accepted and the task
was requeued without the correction.

### Disposition

**SAFE TO MERGE** — from a correctness standpoint. The identity check works,
the tests are meaningful, and the mutation test confirms they catch the
right breakage.

**But not yet useful in production** — it needs:
1. Merge to master
2. A consumer (QA runner or pre-push pipeline integration)

### Risks

- The opener_uses_a_pack_fact rule (rule 3) accesses `copylint._WORD`, a
  private module-level regex. If `_WORD` is renamed or removed, rule 3
  breaks with an AttributeError. Low risk — `_WORD` is used internally by
  copylint too — but worth noting.
- The `audit_pack_cache` function delegates to `scripts.packfact_check`,
  which exists on master. No issue.

### RECOMMENDED CLAUDE ACTION

1. Cherry-pick commits 41d2a0ba..3487aeee from origin/qwen-worker-r9
2. Correct the TASK-294 task file to remove the wrong BLOCKED verdict
3. Wire the check into the pre-push pipeline or QA runner (TASK-292)
4. The first GLM pass was wrong; this correction should be recorded
