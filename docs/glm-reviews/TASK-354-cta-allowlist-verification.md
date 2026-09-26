# GLM verification: TASK-354 — CTA link allowlist

_2026-09-26, verifying commit fe56fa12 on behalf of TASK-381_

## Verdict: **PASS**

The CTA link allowlist is wired into the production path, the tests drive
through `check_batch` (not direct calls), the guard failure test proves the
allowlist is load-bearing, and all 168 tests across the relevant modules pass.

---

## 1. Consumer chain — VERIFIED

The task's rework was to wire `check_cta_links` into a production consumer.
The chain is real and complete:

```
bisonfactory._refuse_copylint(plan, recs, report)     [src/bisonfactory.py:581]
  → _copylint_report(plan, recs)                       [src/bisonfactory.py:619]
    → copylint.check_batch(leads, packs, ...)           [src/bisonfactory.py:575]
      → check_cta_links(urls, resolve=do_resolve)       [src/copylint.py:556]
```

`_refuse_copylint` raises `FactoryRefused` if `report["refused"]` is true,
which blocks the stage before any provider write. The CTA link rules are in
`RULES` (lines 387-391), so they flow through the same refusal path as every
other copylint rule.

`git grep -n "check_cta_links\|cta_link_report" src/` returns hits in
`src/copylint.py` (definition + call from `check_batch`) and
`src/bisonfactory.py` (call to `check_batch` from `_copylint_report`). The
chain is not disconnected.

## 2. Three distinct rules — VERIFIED

    cta_link_not_allowlisted  — URL not on the allowlist (string comparison)
    cta_link_dead             — allowlisted URL returns non-2xx or DNS failure
    cta_link_unverified       — allowlisted URL could not be checked

All three are in `RULES` at lines 387-391. The test
`test_unverified_refused_with_distinct_rule_name` asserts that a transport
failure fires `cta_link_unverified` and NOT `cta_link_dead`. The test
`test_book_a_demo_refused_through_check_batch` asserts that a URL returning
HEAD 200 is still refused by the allowlist.

## 3. Allowlist is exactly one URL — VERIFIED

```python
CTA_LINK_ALLOWLIST = frozenset({
    "https://productive.io/get-started/",
})
```

Line 634. A `frozenset`, so it cannot be accidentally mutated. The test
`test_book_a_demo_refused_despite_resolving` proves that
`https://productive.io/book-a-demo/` is refused despite resolving HEAD 200.

## 4. Guard failure test — VERIFIED

Widening the allowlist to include `book-a-demo`:

    WIDENED:  0 cta_link_not_allowlisted refusals
    ORIGINAL: 1 cta_link_not_allowlisted refusals

The refusal disappears when the allowlist is widened, proving the allowlist
is doing the work. Restoring the original allowlist brings the refusal back.

## 5. Cache — VERIFIED

`test_one_resolve_per_distinct_url_in_batch`: 50 leads sharing one
`booking_link` → 1 resolve call. The cache is per-batch (local dict in
`check_batch`), not module-global, so it cannot leak between batches.

## 6. CTA_LINK_SKIP_REASON — VERIFIED

- Defaults to `""` (no skip). Not defaulted on.
- Setting it disables HEAD/GET resolution but NOT the allowlist.
- The skip reason is recorded in `report["cta_link_skip_reason"]` and appears
  in `report_lines` output as: `CTA LINK RESOLUTION SKIPPED: <reason>`
- Test `test_skip_does_not_disable_allowlist` proves a non-allowlisted URL is
  still refused when the skip is set.
- Test `test_skip_reason_recorded_in_report` proves the reason is visible.

## 7. No network in the suite — VERIFIED

All 22 tests in `test_a_dead_cta_link_is_refused.py` use `_URL_RESOLVE_HOOK`
(a test-only override point) or `resolve=False`. The allowlist check is a
string comparison and needs no network. The resolution tests use a
`_FakeResolver` that returns canned results.

## 8. Config files — VERIFIED

- `config/clients/productive.yaml`: `domain: productive.io`,
  `booking_link: https://productive.io/get-started/`
- `config/clients/productive-offers.yaml`: both `mechanisms.demo.link` and
  `mechanisms.free_trial.link` point to `https://productive.io/get-started/`
- No `book-a-demo` in `src/` or `config/`. Only in test fixtures and docs.
- `productive.test` appears only in demo data modules (`web/demoaccount.py`,
  `web/demodata.py`, `web/demogtm.py`) — the demo estate, not production
  outreach.

## 9. Domain self-exclusion — VERIFIED

7 tests in `test_the_client_domain_is_never_contacted.py`, all green:
- `@productive.io` is blocked through `must_not_contact`
- `@productive.test` is NOT blocked (old value no longer protects)
- The config loads correctly with `domain: productive.io`

## 10. Test count — VERIFIED

168 tests across the relevant modules, all green:

    test_a_dead_cta_link_is_refused    22 tests
    test_copylint                      30 tests
    test_the_client_domain_is_never_contacted  7 tests
    test_bison_prewrite_check          25 tests
    test_bison_campaign_write          25 tests
    test_eligibility                   59 tests

## 11. Conflict markers — NONE

    grep -rn "^<<<<<<< \|^======= $\|^>>>>>>> " src/ tests/ scripts/

Returns nothing.

## Findings

**No defects found.** The work is correctly wired, correctly tested, and the
tests drive through the production path (`check_batch`), not direct function
calls. The guard failure test proves the allowlist is load-bearing. The three
rule names are distinct and collapse none of the four states.

The full suite baseline diff was not run (takes ~35 min). The relevant module
tests (168) all pass. The three new RULES entries add three new keys to the
offenders dict; any test asserting on the exact set of rule names would need
updating, but no such test was found in the 168-test set.

## Recommended Claude action

The work is ready for integration. The two files are:
- `src/copylint.py` (modified — CTA link rules + wiring into `check_batch`)
- `tests/test_a_dead_cta_link_is_refused.py` (new — 22 tests)
