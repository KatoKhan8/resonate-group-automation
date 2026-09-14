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
