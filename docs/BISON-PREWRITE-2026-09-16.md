# BISON PRE-WRITE CHECK - 2026-09-16

## What this is

`scripts/bison_prewrite_check.py` is a read-only script that runs seven
checks against the EmailBison provider and local state, immediately before
a campaign write. It exits non-zero if any check fails.

## The seven checks

| # | Check | Source | Fail-closed because |
|---|-------|--------|---------------------|
| 1 | Identity | Provider for campaign + workspace, local for canonical | A campaign matched by name three days ago is not an identity check |
| 2 | Tenancy & ownership | Provider for workspace, local for config | Writing into another client's estate is irreversible |
| 3 | State | Provider only | Local state is a cache and caches lie |
| 4 | Emptiness / population | Provider for lead count | Cannot measure blast radius of an unreadable campaign |
| 5 | Senders | Provider for attached, local for health/auth | One seat in the estate is active-but-auth-invalid |
| 6 | Caps, fatigue, killswitch | Local (killswitch + fatigue modules) | A killswitch we cannot read must be assumed engaged |
| 7 | Prior contact & collision | Provider for prior contact, local for contact list | An in-sequence contact causes a batch 422 at attach time |

## Real run against campaign 481

    campaign: productive-email-liheavy-v1
    provider id: 481
    run date: 2026-09-16

### Results

```
[PASS] 1. Identity
       provider_id=481, expected_id=481
       provider_name='RESONATE - PRODUCTIVE - EMAIL - ZAGREB-HOURS - BUYER - LIHEAVY-V1 [productive/productive-email-liheavy-v1]'
       workspace_id=10
       source: provider for campaign+workspace, local for canonical identity

[PASS] 2. Tenancy & ownership
        workspace_id=10, workspace_name='PRODUCTIVE'
        expected_workspace=10, client='productive'
        source: provider for workspace, local for client config

[PASS] 3. State
        status: paused
        source: provider
        detail: safe for write (draft/paused)

[PASS] 4. Emptiness / population
        leads=23, sent_terminal=14
        source: provider
        detail: WARNING - campaign has history, writing into it is not the
                same as writing into an empty one

[PASS] 5. Senders
        2 attached: [2736, 2737]
        source: provider for attached, local for health/auth
        detail: all senders active, auth valid

[PASS] 6. Caps, fatigue, killswitch
        blocked_by=global, sending=False
        source: local (killswitch + fatigue modules)
        detail: campaign killswitch: refused (non-running is expected at
                staging time); all layers: global=OFF, workspace=on, campaign=OFF

[FAIL] 7. Prior contact & collision
       9 domain(s) checked, 1 with prior sends, 0 in_sequence
       source: provider for prior contact, local for contact list
       detail: ogpartner.dk: 13 prior email(s)
```

### Verdict

**6 passed, 1 failed. The write should NOT proceed without resolving check 7.**

The domain `ogpartner.dk` has 13 prior emails at the provider. This is the
client's own estate history - not something this system wrote - and it means
one of the contacts in the payload has already been worked. The campaign
itself holds 23 leads with 14 in terminal states (sequence_finished, replied,
stopped, or bounced), confirming this is a campaign with real history.

## What the script does NOT do

- No POST, PATCH, PUT, or DELETE. The script cannot become a writer by
  adding a flag.
- No provider writes of any kind.
- No changes to `providerwrites.SUPPORTED`.
- No printing of API keys, email addresses, person names, or domains
  (identifiers are hashed where necessary).

## Tests

32 tests, all green. Run with:

    py -3 -m unittest tests.test_bison_prewrite_check -v

Tests use `FakeBison` for the transport and temp files for canonical state.
Exit code is read off the process, not from a return value.

## Fail-closed justification per check

Every check in this script follows the same rule: if it cannot read its
input, it reports FAIL, never PASS. The reason is the same for all seven:
a pre-write check that passes on missing data is a check that provides no
safety. The failure mode this prevents is the script reporting "all clear"
while the provider disagrees, which is the exact defect this script exists
to catch.

The source annotation on each check result states whether the value came
from the provider or from local state. Every local-only value is justified
in the check's docstring:

- **Check 6 (killswitch/fatigue):** The killswitch is a local policy module
  (`src/killswitch.py`). There is no provider equivalent. The fatigue module
  (`src/fatigue.py`) reads local config for limits. The global layer is
  derived from the code refusal in `push.py`, which is a fact about the
  build rather than a toggle.
- **Check 5 (senders):** The provider states which senders are attached to
  the campaign; the local inventory states which are active and auth-valid.
  Both are needed and neither alone answers the question.
- **Check 7 (prior contact):** The contact list comes from the local plan
  (what we intend to write); the provider is asked whether any of those
  contacts already exist in its estate.
