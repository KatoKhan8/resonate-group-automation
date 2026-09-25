# Reverse Reconciliation Report — 2026-09-25

## What was built

`scripts/reverse_reconcile.py` sweeps BACKWARD from provider truth to the
action ledger. For each bound campaign, it reads the provider's leads and
classifies each into one of five mutually exclusive classes:

    MATCHED          ledger row exists and state is consistent
    UNRECORDED       provider acted, no ledger row exists
    STATE_MISMATCH   ledger row exists but disagrees with provider truth
    NOT_OURS         proved by positive evidence (provider campaign name
                     contradicts our binding)
    UNKNOWN          cannot classify (provider read failure, no queue match
                     and no ownership evidence)

The exhaustiveness identity (sum of all classes == total provider rows read)
is printed and asserted in the test suite.

## The ledger-key function imported

`push.push_id(rec, contact_key, step_key, channel)` from `src/push.py`.
This is the SAME function `executionguard._key` uses. It is imported, never
re-implemented. The test `test_imported_key_matches_stored_key` pins this.

## Live sweep status

**NOT YET RUN against live providers.** The task boundaries forbid running
`provider_truth.py` until handoff §6.1 is fixed, and the live sweep requires
provider reads. The script, tests, and classification logic are complete and
tested. The live sweep is owed and should be run from Claude's worktree
against a copy of `work/`:

    py -3 scripts/reverse_reconcile.py --work-dir /path/to/work/copy --json

## Test results

    11 tests, all passing:
    - Exhaustiveness identity holds (classified + UNKNOWN == total)
    - Injected provider row with no ledger key -> UNRECORDED
    - Removing the classification call makes the UNRECORDED test fail
      (proves the wiring, not just the text)
    - Provider read failure -> UNKNOWN + non-zero exit
    - Exhaustiveness holds even after provider failure
    - Each row gets exactly one classification
    - Ledger FAILED + provider active -> STATE_MISMATCH
    - Ledger SENT + provider confirms -> MATCHED
    - Imported key derivation matches stored key
    - Zero campaigns is reported (not silently "0 problems")
    - Script is importable and has run/main entry points

## Would this have caught ISSUE-025's 76 blanks?

**YES.** The incident was caused by `bisonfactory._ensure_leads` attaching
91 foreign leads (already in the client's estate) to campaigns 491-498 when
`bison.create_lead` answered "email has already been taken". The action
ledger has NO record of these attachments - its silence is not evidence.

A reverse sweep over campaigns 491-498 would have:

1. Read ~91 leads from the EmailBison provider for those campaigns
2. For each lead, tried to match against the queue index by email
3. For the ~85 leads that were `sequence_finished` members of the client's
   campaign 352 (created months earlier): NO queue record would match
   (they are the client's leads, not ours)
4. Each unmatched lead with an active provider state would be classified
   as **UNRECORDED**
5. The report would show ~85-91 UNRECORDED rows against campaigns 491-498

The forward reconciler returned "0 unsettled, 0 problems" for these
campaigns because the ledger had no rows to check. The reverse reconciler
would have surfaced the discrepancy: the provider has leads the ledger
never heard of.

**The specific classification for ISSUE-025 rows:**

    provider row       classification    evidence
    -----------------  ----------------  -----------------------------------
    client's lead in   UNRECORDED        provider lead in bound campaign but
    491-498, no queue                    no queue record matches; no ledger
    record match                         key can be derived

These are NOT classified as NOT_OURS because we cannot positively prove who
added them (the campaign IS bound to us). They are UNRECORDED: the provider
acted and the ledger has no row. That is the exact shape of the incident.

## Campaigns walked / unreadable

Cannot be reported until the live sweep runs. The script walks every
campaign in `work/campaigns.jsonl` that has a `heyreach_campaign_id` or
`bison_campaign_id`. Unreadable campaigns are named with the error, never
silently skipped.

## Architecture notes

### Key derivation

The script imports `push.push_id` and uses it to derive ledger keys from
queue records. For each provider lead:

1. Match against the queue index (LinkedIn URL for HeyReach, email for
   EmailBison)
2. For each (step_key, channel) pair from the campaign's cadence, derive
   the key: `push.push_id(rec, contact_key, step_key, channel)`
3. Check the ledger for each derived key
4. Classify: if ANY key shows SENT -> MATCHED; if any key exists but none
   SENT -> depends on provider state; if NO key exists -> UNRECORDED

### NOT_OURS is proved, not assumed

A lead in a bound campaign that matches no queue record is UNKNOWN by
default. NOT_OURS requires positive evidence: the provider's own campaign
name contradicting our binding (via `collision._ours`). Without a
`campaign_name` field to check, the lead is UNKNOWN (promoted to UNRECORDED
if the provider shows activity).

### EmailBison lead reading

The script pages through `GET /campaigns/{id}/leads` directly (using the
same pagination approach as `bison._paged`) to get lead rows with email
addresses. This is necessary because `bison.membership()` returns lead IDs
and statuses but not emails, and the email is needed to match against the
queue index.

### Dry run by default

The script writes a report and settles nothing. There is no `--live` flag
because the reverse reconciler is a diagnostic tool, not a settlement tool.
Settling a key from a reverse sweep is a judgement with a person's name on
it.

## grep -rn reverse_reconcile scripts/ src/

    scripts/reverse_reconcile.py:39:    py -3 scripts/reverse_reconcile.py
    scripts/reverse_reconcile.py:40:    py -3 scripts/reverse_reconcile.py --work-dir ...
    scripts/reverse_reconcile.py:607:   p = argparse.ArgumentParser(prog="reverse_reconcile", ...)

The script is a standalone entry point (like `scripts/reconcile_ledger.py`).
It is also imported by `tests/test_reverse_reconciliation_is_exhaustive.py`.
