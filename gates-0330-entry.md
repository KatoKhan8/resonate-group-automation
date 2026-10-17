
---

## GATES 0330 -- For the pinned-value reds: which side moved, test or runtime?

**Date:** 2026-10-17
**Worktree:** `C:\Users\Zvonimir\Desktop\resonate-trees\wt-gates-2026-10-16`
**Branch:** `task-gates-0330-pinned-value-sides-2026-10-17`
**Tree flavour:** CRLF (measured via CR count in requirements.txt)
**Authority SHA:** `b1f290c847eb2500b7eb39987ac34f6d6a8d00d2`

### Denominators

| Module | Tests run | Reds reproduced |
|---|---|---|
| `tests/test_the_emailbison_write_door_is_enforced.py` | 19/19 | 1 red |
| `tests/test_the_live_activation_grant.py` | 22/22 | 2 reds |

Red names verified against gates/0310 table: **same 3**. Different set = reported, not force-fitted.

### Reproduction commands

```
rm -rf __pycache__; py -3 -B -m unittest discover -s tests -p "test_the_emailbison_write_door_is_enforced.py" -v
rm -rf __pycache__; py -3 -B -m unittest discover -s tests -p "test_the_live_activation_grant.py" -v
```

Both ran with `py -3 -B` (no pyc). Output matches the dispatcher-supplied failure messages from gates/0310:
- write-door: `bindings dict empty (no campaign_id for controlled campaign)`
- live-grant: `US cohort present in live grants but not in expected set`

### Per-name verdicts

---

#### Red 1: `test_the_live_activation_grant.TheGrantIsEmptyUntilSomebodyDecides.test_the_grant_holds_exactly_what_an_operator_decided`

**Test pins (line 46--49 of test):**
```python
self.assertEqual(
    executionguard.LIVE_ACTIVATION_GRANTS,
    {"productive-linkedin-cohort-v2": frozenset({LINKEDIN_ACTIVATE}),
     "productive-email-control-v3": frozenset({EMAIL_ACTIVATE})})
```
Expected: **exactly 2 entries** (LinkedIn + Email control). Test written at commit `cd451641b`.

**Runtime produces:**
```python
{'productive-email-control-v3': ..., 'productive-email-us-cohort-v1': ..., 'productive-linkedin-cohort-v2': ...}
```
Actual: **3 entries** -- includes `productive-email-us-cohort-v1: frozenset({'bison.activate'})`.

**Which side moved:** RUNTIME. The test has never mentioned `us-cohort-v1` (confirmed by git log / `-S` search). The value was added to `LIVE_ACTIVATION_GRANTS` in `src/executionguard.py` by commit `593069246` ("EmailBison campaign 489 is ACTIVE: five approved US contacts, sender 3437", 2026-09-18T07:38:42+0200) -- **one day after** the test was written at `cd451641b` (2026-09-17T08:14:08+0200). This was a deliberate operator decision per the docstring comment on line 329: "EMAILBISON, SECOND COHORT, GRANTED 2026-09-18".

ARM A (scratch): replacing the pin with the 3-entry value -> **PASS** confirms the test-side expectation is the thing that didn't update.

**Verdict: TEST-STALE.** Runtime contract legitimately changed; the pin was never updated since the grant was widened.

---

#### Red 2: `test_the_live_activation_grant.TheGrantIsEmptyUntilSomebodyDecides.test_each_grant_names_one_channel_only`

**Test expects (lines 58--63):**
```python
expected = {"productive-linkedin-cohort-v2": LINKEDIN_ACTIVATE,
            "productive-email-control-v3": EMAIL_ACTIVATE}
for campaign_id, granted in executionguard.LIVE_ACTIVATION_GRANTS.items():
    self.assertIn(campaign_id, expected)
```
Expects iteration keys to all be in a 2-key dict.

Runtime fails because `'productive-email-us-cohort-v1'` iterates as a key produced by the runtime (from `LIVE_ACTIVATION_GRANTS`, committed at same `593069246`), but the `expected` dict on the test side has only 2 keys. Same mechanism as red 1 -- the runtime grew, the test's `expected` map did not.

ARM A mutation (adding us-cohort-v1 to both sides) -> PASS confirms test-side stale.

**Verdict: TEST-STALE.** Same moving side as red 1. Both stem from the same 2026-09-18 runtime change.

---

#### Red 3: `test_the_emailbison_write_door_is_enforced.TheDoorDidNotWidenWhatThisModuleMaySend.test_resume_is_declared_and_authorised_for_one_campaign_only`

**Test assertion (line 330):**
```python
self.assertTrue(bindings,
    f"none of {authorized} carries a bison_campaign_id, so there is no provider campaign...")
```
Asserts the `bindings` dict is non-empty. Currently empty (`{}`).

**How bindings are built (lines 313--322):**
```python
authorized = [c for _, c in providerwrites._AUTHORIZED_EMAIL_CAMPAIGNS]
bindings = {}
for want_canonical in authorized:
    bound = (_campaigns.get(want_canonical) or {}).get("bison_campaign_id")
    if bound:
        bindings[want_canonical] = str(bound)
```

The `_AUTHORIZED_EMAIL_CAMPAIGNS` tuple in `providerwrites.py` contains 10 rows (verified: `(487, control-v3), (489, us-cohort-v1), (491..498 batch)`). But `bindings` stays empty because `campaigns.get(canonical)` returns either `None` or a row without `bison_campaign_id`.

`campaigns.get()` loads canonical campaign state from `work/campaigns.jsonl` (tracked by the system but **outside this worktree**; under `resonate-ops` repo, gitignored here per CLAUDE.md). The bison campaign IDs are assigned at factory-creation time and stored in that file.

ARM B (scratch): mocking `campaigns.get()` to return `{"bison_campaign_id": "487"}` for the first authorized row -> `bindings = {...}` -> **assert True passes**, confirming the test logic is sound and the emptiness comes solely from missing runtime data.

Since both the test's resolution path AND the runtime data live through `work/campaigns.jsonl`, and I cannot read that file per external-model rules (rule 1 of `_EXTERNAL-MODEL-RULES.md`):

**Verdict: UNDETERMINED.** Missing authority is `work/campaigns.jsonl` -- specifically whether campaigns 487, 489, 491-498 have `bison_campaign_id` populated. If they don't exist yet in canonical state, the test should handle zero bindings gracefully (current code uses `if bound:` to skip unbound rows, suggesting this was designed for that case). If they do exist but lack the field, it's a data-integrity question in how the factory writes the row. Cannot verify without reading the file.

### Movement summary table

| Name | Test pin | Runtime produces | Side moved | Commit that moved | Verdict |
|---|---|---|---|---|---|
| `test_the_grant_holds_exactly_what_an_operator_decided` | 2 entries | 3 entries (added `us-cohort-v1`) | **RUNTIME** | `593069246` (2026-09-18) | **TEST-STALE** |
| `test_each_grant_names_one_channel_only` | 2-key expected map | 3 keys iterate | **RUNTIME** | `593069246` (2026-09-18) | **TEST-STALE** |
| `test_resume_is_declared_and_authorised_for_one_campaign_only` | `bindings` non-empty | `bindings == {}` | **UNKNOWN** | N/A | **UNDETERMINED** |

### Scratch files

- `gates-0330-scratch/test_grant_pin_mutation_A.py` -- ARM A: test-pin replacement verifies TEST-STALE
- `gates-0330-scratch/test_bindings_injection_B.py` -- ARM B: mock campaign.get verifies data gap

All scratch files are untracked. No tracked file edited.

### Operator recommendation

For reds 1 & 2: re-baseline the test pin in `tests/test_the_live_activation_grant.py` lines 46-49 to include `"productive-email-us-cohort-v1": frozenset({EMAIL_ACTIVATE})`. These are documented operator decisions (2026-09-18 second cohort grant); the test is simply stale.

For red 3: requires resolving why `work/campaigns.jsonl` doesn't carry `bison_campaign_id` for the 10 authorized campaigns. This may be an operational question (factory hasn't written bindings) or a design question (the test should tolerate zero bindings). An existing operator member must inspect the canonical state.

### Controls checklist

[x] Reproduce: 3 red names matched (1 + 2) across two single-module offline runs
[x] Other-answer arms: ARM A printed TEST-STALE (pins replaceable); ARM B printed UNDETERMINED (data gap)
[x] Plant check: both scratch mutations verified applied (PASS when pin updated, PASS when binding injected)
[x] Denominators: 19 tests, 22 tests; both counts printed; SHA `b1f290c84` cited throughout
[x] pyc discipline: `__pycache__` deleted before every verdict run; `py -3 -B` used
[x] No network, provider, Apify, Slack, campaign, send or activation call
[x] No tracked file edited; no lint/test rule weakened; no merge/cherry-pick/push
