PRIORITY: HARD CANARY GATE — NOT SATISFIED

# TASK-565 — INCIDENT FIXTURES DELIVERED, GATE NOT MET

    branch       qwen-worker-8-r31 @ bae3cd25 (pushed)
    verified at  master d70a43c0, isolated worktree, production ledgers copied
    RESULT       19 tests, 13 pass, 2 FAIL, 4 ERROR
    VERDICT      NOT SATISFIED - this is a hard canary gate

All ten incidents have a class, which is real progress. The gate is not met
for three separate reasons, in descending order of seriousness.

## 1. THE BOUNDARY CONDITION IS NOT EVIDENCED

TASK-565's acceptance is not "a test exists". It is:

> for each fixture you must prove that **removing or bypassing the ACTUAL
> LOWEST-LAYER GUARD makes that fixture FAIL**.

The file contains three incidental mentions of mutation and no per-fixture
mutation proof. Nothing shows that any of the thirteen passing fixtures would
go red if the guard it claims to depend on were removed. The task warns about
exactly this failure - "a bypass mutation left a test green because a
DIFFERENT guard produced a HELD instead of a BLOCK" - so a passing fixture
without its mutation is not yet evidence.

## 2. THREE FIXTURES CALL AN API THAT DOES NOT EXIST

    AttributeError: module 'src.eligibility' has no attribute 'block_reason'
    AttributeError: module 'src.eligibility' has no attribute 'is_sendable'

`src.eligibility` exposes no such names. This is the failure `CLAUDE.md`
names directly - *"CREDENTIAL NAMES COME FROM config.VARIABLES. NEVER GUESS
ONE"* - in its general form: a plausible name was invented rather than read.
Incident 6, *a prospect who replied "no thank you" receiving another
message*, is therefore **completely untested**: both its fixture and its
control error out.

## 3. TWO SAFETY FIXTURES FAIL, AND ONE FAILS FOR AN INSTRUCTIVE REASON

### Incident 8, the direct provider bypass — `ProviderWriteRefused not raised`

    providers.refuse_unauthorized_write(
        "POST", "https://api.emailbison.com/campaigns/123/leads")

Two defects in one line, and together they reproduce TASK-564's finding:

- **The host is wrong.** EmailBison's real base is
  `https://send.resonategroup.co/api`. `api.emailbison.com` is not a guarded
  host and never will be.
- **The guard was never armed.** `_prospect_facing_hosts` is populated when
  `src.providers.bison` / `heyreach` are imported. The fixture imports
  neither, so the set is empty, `is_prospect_facing` returns False, and the
  guard returns early.

So the fixture proves the bypass exists rather than proving the guard holds -
which is the opposite of its job, and is precisely the class recorded in
`docs/PROVIDER-WRITE-SURFACE-2026-09-29.md` finding 1.

### Incident 5, an unsupported figure on a LinkedIn message

    AssertionError: 'test-001' not found in []

`copylint.check_batch` returned no offenders because the lead is the wrong
shape: it passes `steps` as a dict of step keys, while the canonical lead
carries `steps` as a LIST and LinkedIn copy under `linkedin`. The rule was
never exercised, so a green run here would have proved nothing either.

The remaining error, `'list' object has no attribute 'get'`, is the same
class of shape mismatch in incident 1's control.

## WHAT IS ACTUALLY GOOD HERE

Ten incident classes are present and named. Incidents 2, 3, 4, 7, 9 and 10
have passing fixtures whose shapes look right. That is a usable foundation;
it is not yet the gate.

## WHAT REWORK MUST DO

1. **Per fixture, a mutation.** Remove or neuter the lowest-layer guard the
   fixture depends on, in memory, and show the fixture goes RED for that
   reason. Restore. This is the acceptance, not an extra.
2. **Read the API before calling it.** `eligibility` has no `is_sendable` or
   `block_reason`; find the real entry point for "may this contact receive
   another message" and use it.
3. **Fix incident 8 properly:** import the provider module so the guard is
   armed, and use the real base `send.resonategroup.co`. Then ALSO add the
   unarmed case as its own expected-failure fixture, because that bypass is
   real and should be pinned until it is closed.
4. **Fix the lead shapes** in incidents 1 and 5 against `copylint.check_batch`
   as `generate_campaign` calls it: `steps` a list, LinkedIn under `linkedin`,
   `pack.facts` populated.

## CONSEQUENCE

**TASK-565 remains OPEN and the live canary remains gated.** TASK-564 is
satisfied and recorded. Nothing was sent by this work; provider writes 0.
