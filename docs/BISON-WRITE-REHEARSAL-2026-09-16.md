# Bison Write Rehearsal — 2026-09-16

TASK-184. The campaign write Claude is about to perform, rehearsed end to end
against a FAKE provider. No real provider call was made.

## 1. The Real Path

**Entry point:** `bisonfactory.stage(campaign_id, live=True)`

This is the function that creates a campaign and writes a sequence at
EmailBison. It is NOT a hand-rolled HTTP call — it carries the gates, the
action ledger and the spend ledger through `providerwrites.perform`.

**The chain:**

```
bisonfactory.stage(campaign_id, live=True)
  └─ _find_or_create(campaign, report)
       ├─ bison.find_campaigns_by_name(planned)   # orphan recovery
       └─ providerwrites.perform(
              EMAIL_CREATE_CAMPAIGN,
              transport=lambda p: bison.create_campaign(p["name"]),
              ...)
  └─ _ensure_sequence(provider_id, campaign, plan, report)
       ├─ bison.sequence_steps(provider_id)       # read existing
       └─ providerwrites.perform(
              EMAIL_SET_SEQUENCE,
              transport=lambda p: bison.set_sequence(
                  provider_id, p["title"], p["sequence_steps"]),
              readback=lambda: {"steps": [...]},
              ...)
```

**What Claude should call:**

```python
from src import bisonfactory
report = bisonfactory.stage("control-rehearsal", live=True)
```

The campaign row in `work/campaigns.jsonl` must have:
- `campaign_id`: the canonical id
- `client`: "productive"
- `name`: the human-readable name
- `bison_campaign_id`: null (for a new campaign)

## 2. The Derived Campaign Name

The factory derives the name from the campaign row:

```python
bisonfactory.provider_campaign_name(campaign)
# → "{human} [{client}/{campaign_id}]"
```

For the CONTROL cohort:

```
RESONATE - PRODUCTIVE - EMAIL - ZAGREB-HOURS - CONTROL [productive/control-rehearsal]
```

The `[productive/control-rehearsal]` suffix is derived, not chosen. The
identity check in `bison_prewrite_check.py` compares against this derived
name, not the raw canonical name. If the derivation changes, the identity
check tracks it automatically because it calls the same function.

**TASK-170's identity check will recognise it** because the check uses
`bisonfactory.provider_campaign_name(campaign)` to compute the expected name.

## 3. The CONTROL Sequence

Three steps from `cadence.TEMPLATES`:

| Order | Step Key       | Template          | thread_reply | wait_in_days |
|-------|----------------|-------------------|--------------|--------------|
| 1     | em1            | persona_pain      | False        | 3            |
| 2     | em2            | comparable_proof  | True         | 4            |
| 3     | em3            | breakup           | False        | 0*           |

*The last step's wait is declared but unchecked — nothing follows it.

**Threading pattern: F/T/F** — from the `email_five` ladder pattern
`(False, True, False, True, False)` truncated to three, or from the client
config's `thread_reply_pattern` override.

A follow-up step STILL CARRIES `email_subject` — the `thread_reply` flag is
the mechanism, not subject omission. The provider stores both.

## 4. Rehearsal Results (Against FakeBison)

All 15 tests in `tests/test_bison_campaign_write.py` pass:

```
test_derived_name_carries_client_and_campaign_id_suffix ... ok
test_identity_check_will_recognise_the_derived_name ... ok
test_three_steps_in_cadence_order ... ok
test_threading_is_false_true_false ... ok
test_waits_are_declared ... ok
test_new_campaign_has_no_members ... ok
test_write_three_steps_readback_matches ... ok
test_held_steps_carry_wait_in_days ... ok
test_second_write_appends_not_replaces ... ok ← THE CRITICAL TEST
test_orders_interleave_across_writes ... ok
test_refuses_when_campaign_holds_different_steps ... ok
test_passes_when_campaign_holds_identical_steps ... ok
test_blind_retry_doubles_the_sequence ... ok
test_correct_recovery_read_before_write ... ok
test_once_or_twice_check ... ok
```

### What was proven:

1. **Campaign created holding zero leads.** The FakeBison starts with an
   empty member list. Status is `draft` — cannot send.

2. **Sequence written is three CONTROL steps with threading F/T/F.** The
   `thread_reply` booleans are in positions [False, True, False].

3. **Readback returns what was written.** `bison.sequence_steps` returns
   the three steps with correct subjects, bodies, waits, and threading.

4. **A second set_sequence call APPENDS.** This is the critical finding:
   - After first write: 3 steps
   - After second write: **6 steps** (not 3)
   - The provider renumbers orders across writes

## 5. ⚠️ THE APPEND TRAP ⚠️

**`bison.set_sequence` APPENDS. IT DOES NOT REPLACE. NOTHING CAN UNDO IT.**

This was measured live on 2026-09-13 on a throwaway campaign: writing one
step, then another, left the campaign holding BOTH. A third write of two
steps left four — renumbered 1, 3, 2, 4, so the orders interleave rather
than following the writes.

**There is no removal verb.** `/campaigns/{id}/sequence-steps` is GET, HEAD,
POST only. PUT is 405. No per-step route exists.

**A campaign whose sequence is written twice sends twice.** The second email
carries the older copy. The only remedy is deleting the campaign.

### The brake that prevents this in production:

`bisonfactory._ensure_sequence` reads `bison.sequence_steps(provider_id)`
BEFORE writing. If the campaign already holds steps:
- **Identical steps** → reports "sequence already staged", does NOT write
- **Different steps** → raises `FactoryRefused` with "APPENDS" in the message

This is tested in `test_refuses_when_campaign_holds_different_steps` and
`test_passes_when_campaign_holds_identical_steps`.

## 6. Recovery Procedure for a Half-Failed Write

**Scenario:** Campaign created, sequence write times out. Did the provider
act? Unknown.

### DO NOT:
- **Do NOT blindly retry.** A blind retry appends a second copy of the
  sequence. The campaign then carries six steps instead of three.

### DO:

1. **Read provider truth first.**
   ```python
   from src.providers import bison
   held = bison.sequence_steps(provider_id)
   ```

2. **Classify what you found:**
   - **Empty list** → sequence was NOT written. Safe to write now.
   - **Three steps matching what you intended** → sequence WAS written.
     The timeout was in the response, not the request. Do NOT write again.
   - **Different steps** → something unexpected. Do NOT write. Investigate.

3. **The once-or-twice check:**
   ```python
   expected_count = 3  # CONTROL has three steps
   if len(held) == expected_count:
       # Written once. Correct. Do nothing.
       pass
   elif len(held) == 0:
       # Not written. Safe to write.
       bison.set_sequence(provider_id, title, steps)
   elif len(held) == 2 * expected_count:
       # Written twice. The trap fired. Delete the campaign and start over.
       raise RuntimeError("sequence doubled — campaign must be rebuilt")
   else:
       # Unknown state. Investigate before acting.
       raise RuntimeError(f"unexpected step count: {len(held)}")
   ```

4. **If the campaign is doubled:** The only remedy is
   `DELETE /api/campaigns/{id}` and re-creating from scratch. There is no
   "remove extra steps" verb.

## 7. Pre-Write Check for a Not-Yet-Created Campaign

`scripts/bison_prewrite_check.py` now handles the case where the campaign
has no `bison_campaign_id` (not yet created at the provider).

**Behaviour: FAIL CLOSED.**

A campaign without a provider id has nothing at the provider to check. The
identity check has no provider campaign to compare against. Passing
vacuously would be the exact defect this closes.

**What runs without a provider id:**
- Check 0 (Pre-creation): FAIL — "campaign has not been created at EmailBison yet"
- Check 1 (Identity): FAIL — shows what the derived name WILL be
- Check 2 (Tenancy): runs against config only — checks workspace is declared
- Check 6 (Caps/killswitch): runs — reads local state
- Checks 3, 4, 5, 7: FAIL — "cannot check — campaign not yet created"

**Exit code: 1** (FAIL).

**After creation:** Re-run the check. With `bison_campaign_id` bound, all
seven checks run against provider truth.

**New tests (3 added to `tests/test_bison_prewrite_check.py`):**
- `test_no_provider_id_fails_closed` — exit code 1, clear reason
- `test_no_provider_id_shows_derived_name` — identity check shows future name
- `test_local_checks_still_run` — tenancy and killswitch still execute

All 35 prewrite check tests pass (32 original + 3 new).

## 8. Summary for Claude

**The write to perform:**

```python
from src import bisonfactory
report = bisonfactory.stage("<campaign-id>", live=True)
```

**What it does:**
1. Creates a new EmailBison campaign in `draft` status
2. Writes the three-step CONTROL sequence (F/T/F threading)
3. Does NOT add leads (not authorized)
4. Does NOT activate (not authorized)
5. The campaign holds zero people and cannot send

**The derived name:**
```
<human name> [productive/<campaign-id>]
```

**If the write fails halfway:**
1. Read `bison.sequence_steps(provider_id)` FIRST
2. If empty → safe to retry the sequence write
3. If three correct steps → already done, do NOT write again
4. If six steps → the append trap fired, delete and rebuild

**Pre-write check:**
```bash
py -3 scripts/bison_prewrite_check.py <campaign-id>
```
Before creation: fails closed with clear reason.
After creation: runs all seven checks against provider truth.

---

*Rehearsed 2026-09-16 against FakeBison. No real provider call was made.*
*Tests: `tests/test_bison_campaign_write.py` (15 tests), `tests/test_bison_prewrite_check.py` (35 tests).*
