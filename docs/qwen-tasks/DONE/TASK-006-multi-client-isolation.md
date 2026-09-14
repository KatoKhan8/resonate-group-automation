# TASK-006 - Prove one client's estate cannot leak into another's

## GOAL

Adversarial tenancy tests: for every read and every write path that takes a
client, prove that a wrong or missing client is refused rather than
defaulted.

## WHY IT MATTERS

`work/campaigns.jsonl` holds rows for three tenants today - `productive`,
`contactout`, `demo-client` - in one file, and `work/queue.jsonl` holds one
estate. The EmailBison credential is bound to a workspace that
`bison.bound_workspace()` reports, and `bisonfactory` refuses a mismatch; the
documented provider behaviour is that `workspace_id` is ACCEPTED AND
DISCARDED by every list route, so a caller can believe it scoped a read and
be holding another tenant's estate. That is the failure mode: not an error, a
wrong answer that looks right.

`docs/MULTI-CLIENT-AUDIT.md` exists; read it first and do not restate it.
This task is the tests that audit implies.

## CURRENT CONTEXT

- `src/clients.py`, `src/workspaces.py`, `src/store.py`, `src/campaigns.py`.
- `executionguard` gate 1 is tenancy.
- HeyReach campaigns carry `organizationUnitId`; Productive's is 118832, and
  48 of the 50 campaigns in that workspace belong to the client, not to us.

## SCOPE

1. Build a two-tenant synthetic estate in a temp directory.
2. For each of: loading records, loading campaigns, campaign material,
   fingerprint, approval, sender assignment, fatigue, collision, suppression
   and the `executionguard` tenancy gate - assert that asking as tenant A
   never returns a row belonging to tenant B.
3. Assert the NEGATIVE cases too: an absent client, an empty-string client, a
   client that does not exist, and a client whose case differs. Each must
   refuse. A silent empty result is NOT a pass - an empty list is
   indistinguishable from "this tenant has nothing", which is the exact
   failure CLAUDE.md calls "an audit that reports clean because it watched
   nothing".
4. Where a path DOES default or return empty instead of refusing, record it
   as a finding with the file and line.

## FILES ALLOWED

`tests/`, `docs/qwen-tasks/`.

## FILES FORBIDDEN

`src/**`. `work/**`. `config/clients/productive.yaml` and every other real
client config - build synthetic tenant configs in temp.

## PRODUCTION CONSTRAINTS

Offline. No provider calls. No credentials.

## TESTS REQUIRED

Every assertion above. For each, break the tenancy check deliberately and
confirm the intended test failed for the intended reason.

## EXPECTED OUTPUT

One test module plus a findings table of any path that defaults rather than
refuses.

## DONE CONDITION

A named test covers each listed path in both directions, and every path that
fails closed is distinguished in the record from every path that merely
returns nothing.

## RESULT

STATUS: DONE
COMMIT SHA: b108210
TESTS: 57 tests in tests/test_multi_client_isolation.py, all passing.
  51 existing tests in tests/test_workspace_isolation_attacks.py still pass.
FILES CHANGED:
  tests/test_multi_client_isolation.py (new, 889 lines)
  docs/qwen-tasks/TODO/TASK-006-multi-client-isolation.md -> RUNNING/ -> DONE/
FINDINGS:
  Paths that default or return empty instead of refusing:

  1. store.list_records(client=None) returns ALL tenants' records.
     File: src/store.py, list_records(). Filter-not-boundary pattern.

  2. store.list_records(client="") returns empty list, not a refusal.
     Silent empty is indistinguishable from 'this tenant has nothing'.
     File: src/store.py, list_records().

  3. store.list_records(client="nosuchclient") returns empty, not refusal.
     File: src/store.py, list_records().

  4. store.list_records(client="Alpha") returns empty, not refusal.
     Case variant silently returns nothing.
     File: src/store.py, list_records().

  5. store.validate() accepts client=None and client="".
     Checks key presence, never that it holds a real client.
     File: src/store.py, validate() at REQUIRED check.

  6. approve.pending() with no argument defaults to store.load() and
     returns both tenants' queues on one screen.
     File: src/approve.py, pending().

  7. campaigns.by_record() is unscoped and maps records from both tenants.
     File: src/campaigns.py, by_record().

  8. fatigue.check(config=None) silently substitutes module defaults.
     Does not verify config matches record's client. Passing alpha's
     config for a bravo record is accepted silently.
     File: src/fatigue.py, check().

  9. collision.check_address(expect_workspace="") and
     collision.check_address(expect_workspace=None) pass through to the
     provider layer. The REQUIRED sentinel only catches 'not passed'.
     File: src/collision.py, check_address().

  10. executionguard.authorize evaluates the copy gate (step expansion)
      BEFORE the tenancy gate. A cross-tenant record with no cadence data
      for a generated step is refused for 'copy', masking the tenancy
      violation. For template steps, the template renders and the tenancy
      gate fires as expected.
      File: src/executionguard.py, authorize().

  Paths that fail closed (refuse correctly):
  - Repo.for_client("") raises UnknownClient
  - Repo.for_client(None) raises UnknownClient
  - Repo.for_client("nosuchclient") raises UnknownClient
  - Repo.for_client("Alpha") raises UnknownClient (uppercase not a slug)
  - clients.load("nosuchclient") raises ConfigError
  - clients.load("Alpha") raises ConfigError
  - Repo.records() filters by client correctly
  - Repo.campaign() refuses foreign ids with CrossClientAccess
  - campaigns.material() only includes campaign's own records
  - campaigns.fingerprint() is tenant-specific
  - senderidentity.sender() refuses cross-workspace with CrossWorkspaceSender
  - executionguard tenancy gate refuses record-campaign client mismatch
  - executionguard tenancy gate refuses empty workspace (email channel)
  - executionguard tenancy gate refuses empty org_unit (LinkedIn channel)
  - executionguard tenancy gate refuses None/empty record client
  - executionguard tenancy gate refuses empty campaign client (ConfigError)

RISKS:
  - The store.list_records filter pattern means any caller that forgets
    the client parameter gets the whole estate. The Repo layer fixes this
    for the web path, but the CLI path still uses the unscoped primitive.
  - fatigue.check accepting any config for any record means a caller that
    passes the wrong client's config gets silent default behaviour.
  - collision.check_address with empty/None workspace reaches the provider
    layer, which in a live system with credentials would read from an
    unpinned estate.
  - The executionguard copy-before-tenancy ordering means a cross-tenant
    record with no written content is refused for the wrong reason.

RECOMMENDED CLAUDE ACTION:
  1. store.validate: add a check that client is a non-empty string, not
     just present. One line.
  2. store.list_records: consider refusing client="" and client=None
     rather than returning empty/all. Or document the filter-not-boundary
     pattern clearly.
  3. fatigue.check: add a check that config matches rec["client"], or
     document that the caller is responsible for passing the right config.
  4. collision.check_address: add an explicit check for empty/None
     workspace before reaching the provider.
  5. executionguard.authorize: consider moving the tenancy gate before
     the copy gate, so a cross-tenant record is refused for tenancy
     regardless of whether it has cadence data.
