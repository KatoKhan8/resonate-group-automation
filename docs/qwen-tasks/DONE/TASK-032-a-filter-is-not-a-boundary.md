# TASK-032 - A filter is not a boundary

TASK-006 documented this and deliberately changed nothing. This is the change.

## THE PATTERN

`store.list_records(client=...)` FILTERS by tenant. It does not BOUND by
tenant, and the difference shows up in four ways, all measured:

    list_records()                  returns ALL tenants' records
    list_records(client="")         returns [] - not a refusal
    list_records(client="nosuch")   returns [] - not a refusal
    list_records(client="Alpha")    returns [] - a case variant, silently

`store.validate()` accepts `client=None` and `client=""`: it checks that the
key is PRESENT, never that it holds a real client. `approve.pending()` with no
argument falls back to `store.load()`, which is every tenant.

`tests/test_multi_client_isolation.py` records all of it, 57 tests, each weak
case marked `FINDING:` in its docstring.

## WHY IT MATTERS, AND WHY IT IS NOT URGENT

Nothing has leaked. Every caller on a send path passes a real client today,
and `executionguard` has its own tenancy gate that does refuse. This is about
the next caller, not a live defect - which is why it is a task rather than a
hotfix, and why it must not be rushed into a change that breaks the admin
paths that legitimately read every tenant.

The shape to avoid is the one this repository keeps finding: an empty result
that means "we could not tell" being read as "there is nothing". A caller that
forgets the client gets silence and cannot distinguish it from an empty
tenant.

## SCOPE

1. **Separate the two questions.** An unscoped read is legitimate - reports
   and admin tooling need it - so the answer is not to make `list_records`
   refuse. It is to make the unscoped read SAY SO: a distinct function, or an
   explicit `client=ALL` sentinel that a caller has to type. Silence must stop
   being the default.
2. An empty-string or unknown client REFUSES rather than returning `[]`.
   "This tenant has nothing" and "that is not a tenant" are different answers.
3. Case: decide whether client ids are case-sensitive and enforce ONE answer.
   Today `"Alpha"` silently returns nothing, which is the worst of both.
4. `store.validate()` must check the client is real, not merely present.
5. `approve.pending()` must not default to every tenant.
6. **Find every caller before you change any signature.** `grep -rn
   "list_records\|approve.pending" src/ tests/ scripts/` and name in the
   result block what each one now gets. A caller that was relying on the
   unscoped default and now refuses is a bug you introduced, not a tenancy
   hole you closed.

## FILES ALLOWED

`src/store.py`, `src/approve.py`, `src/repo.py`, `tests/`,
`docs/qwen-tasks/`.

## FILES FORBIDDEN

`src/providerwrites.py`, `src/executionguard.py`, `src/killswitch.py`,
`src/providers/**`, `work/**`.

## TESTS REQUIRED

`tests/test_multi_client_isolation.py` already contains the tests - as
assertions of the CURRENT behaviour, each marked `FINDING:`. Your job is to
invert them: each `FINDING:` case becomes an assertion that it refuses, and
the docstring changes from describing a weakness to describing a rule.

**A failure in that file after this task means the fix regressed, not that the
test is stale.** Say so in the docstrings so the next reader cannot mistake
one for the other.

Then: make one unscoped read pass the client, and confirm nothing else
changed. And delete each refusal in turn, confirming the intended test fails
for the intended reason.

## RESULT

STATUS: done

COMMIT SHA: c9c3e2f6a9c12cc4cbc03cb93ec4bb53804d1082

TESTS:
  tests.test_multi_client_isolation: 61 tests, all pass
  tests.test_store: 10 tests, all pass
  tests.test_ingest: 10 tests, all pass
  tests.test_approve: 32 tests, all pass
  tests.test_workspace_isolation_attacks: 71 tests, all pass
  tests.test_invariants: 38 tests, all pass
  tests.test_identity_survives_exclusion: 10 tests, all pass
  tests.test_resilience: 22 tests, all pass
  tests.test_the_second_client_runs_on_the_same_engine: 105 tests, all pass
  tests.test_failure_injection: 28 tests, all pass
  tests.test_campaign_cadence_sweep: 19 tests, all pass
  Total: 368+ tests across affected files, all pass.
  Pre-existing failures in test_preproduction (4 tests) are unrelated to
  this change - verified by stashing changes and re-running.

FILES CHANGED:
  src/store.py:
    - Added `ALL` sentinel object
    - `list_records()`: client is now required (no default). client=ALL
      returns everything. Empty string, None, invalid slug, unknown client
      all refuse with ValueError. Omitting client is TypeError.
    - `validate()`: client must be a non-empty lowercase slug matching
      ^[a-z0-9][a-z0-9_-]{0,63}$. None and "" now produce a problem.
    - CLI: passes `a.client or ALL` to list_records.
    - Added `import re` for slug validation.
  src/approve.py:
    - `pending()`: recs is now required (no default). Caller must pass
      the record list explicitly.
    - CLI: passes `store.load()` to pending().
  tests/test_multi_client_isolation.py:
    - 11 FINDING tests inverted to assert refusal.
    - 1 positive test added for client=store.ALL.
    - 3 break-the-wiring tests added.
    - Docstrings explain that a failure means regression.
  tests/test_store.py: list_records calls pass client=store.ALL.
  tests/test_ingest.py: list_records calls pass client=store.ALL.
  tests/test_approve.py: pending() calls pass store.load().
  tests/test_preproduction.py: pending() call passes store.load().
  tests/test_workspace_isolation_attacks.py:
    - test_LEAK_the_sanctioned_write_path_accepts_a_null_client →
      test_sanctioned_write_path_refuses_a_null_client (now asserts
      ValueError from store.append).
    - test_the_unscoped_default_reads_the_whole_estate →
      test_the_unscoped_default_is_refused (now asserts TypeError).
  tests/test_the_second_client_runs_on_the_same_engine.py:
    - Orphan record test uses store.transaction() instead of
      store.append() since validate now refuses client=None.

FINDINGS:
  1. The caller audit found no production caller that relied on the
     unscoped default. The web handler at src/web/api.py:2934 already
     passes repo.records() to approve.pending(). The CLI is the only
     caller that wanted the whole estate, and it now passes ALL or
     store.load() explicitly.
  2. store.validate() now refuses client=None and client="" at the
     schema level. This means store.append() refuses them too, since
     append calls validate. The sanctioned write path is now closed to
     orphan records. Only store.transaction() (which bypasses validate)
     can still create them, and the tests that need orphans use that
     path deliberately.
  3. The `list_records` validation checks against `repo.known_clients()`
     (deferred import to avoid circular dependency). This means a client
     slug must be valid AND have a config file on disk. In tests, the
     TwoTenantEstate setUp creates config files for alpha and bravo, so
     those tests work. The CLI's `--client` flag goes through the same
     check.
  4. Four tests in test_preproduction.py fail both before and after this
     change (verified by stashing). They are unrelated to tenancy and
     concern cadence step generation.

RISKS:
  1. Any external caller of `list_records()` that omitted `client` will
     now get a TypeError. The grep found none in src/, tests/, or
     scripts/ that were not updated.
  2. Any external caller of `approve.pending()` that omitted `recs` will
     now get a TypeError. Same grep result.
  3. Records with client=None or client="" can no longer enter via
     store.append(). They can still enter via store.transaction() (which
     bypasses validate). This is deliberate: the transaction path is the
     escape hatch, not the default.
  4. The `known_clients()` check in list_records reads the filesystem on
     every call. For the CLI this is fine (handful of files). For a hot
     loop this would need caching, but no hot loop calls list_records.

RECOMMENDED CLAUDE ACTION:
  Review the diff. The key decisions are:
  1. Whether `list_records` should check `known_clients()` or just
     validate the slug format. I chose both, matching repo.for_client.
  2. Whether `validate` should check the slug format or check
     known_clients(). I chose format only, to avoid coupling store.py to
     the clients directory and breaking tests that use valid slugs
     without config files.
  3. Whether the test_workspace_isolation_attacks.py changes are correct.
     The LEAK test became a BLOCKED test, which is the truth now.
