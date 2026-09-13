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

STATUS: TODO
COMMIT SHA:
TESTS:
FILES CHANGED:
FINDINGS:
RISKS:
RECOMMENDED CLAUDE ACTION:
