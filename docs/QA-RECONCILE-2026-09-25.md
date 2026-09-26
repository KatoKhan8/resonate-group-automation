# QA Reconciliation Check — TASK-299

**Date:** 2026-09-26
**Check:** `scripts/qa/check_reconcile.py`
**Phase:** `ongoing`
**Subject:** lead

## What this check answers

**Is anybody our store believes we have stopped still being talked to at a
provider — and has every reply and every bounce the providers saw reached
our store?**

Two symmetric rules, both CRITICAL when they fire:

    stopped_here_is_stopped_there
        Every lead our store marks replied/stopped/unsubscribed reads
        NOT in_sequence at BOTH providers.
    provider_event_has_a_store_event
        Every provider reply and every provider bounce has a matching
        event in our store.

## The defect this exists for — ISSUE-041

`inbound._stop_at_provider` gates the LinkedIn stop on
`contact["heyreach_lead_id"]`. **ZERO contacts in the estate carry it.**
Every cross-channel stop reported success having never called
`heyreach.stop_lead_in_campaign` once.

This check is NOT gated on `heyreach_lead_id`. The lead's identity at
HeyReach is resolved from the profile URL: `heyreach.campaigns_for_lead(
profile_url=...)`. Key presence is reported FIRST, per rule, before any
verdict.

## The second trap — ISSUE-042

`inbound.OWNED_CAMPAIGNS` are HeyReach ids compared against an EmailBison
event's campaign id. This check resolves ownership per event from the
registry (`campaigns.jsonl`), per provider, and never by set membership.

## Design

### Key presence

For every rule, before any verdict: how many subjects carried the field
this rule keys on? A rule whose key is present on **zero** subjects is
**VACUOUS**, exits 2, and at phase `ongoing` is a CRITICAL if it persists
across two consecutive cycles.

### Ownership resolution

Ownership is resolved per event from the registry, per provider:

- An EmailBison event's campaign id is compared against `bison_campaign_id`
  in `campaigns.jsonl`.
- A HeyReach event's campaign id is compared against `heyreach_campaign_id`.
- An id compared across providers is not a resolution.

### "Already settled" is its own column

HeyReach 613744 carries the operator's test identity at
`leadCampaignStatus: "Finished"`. A stop against a FINISHED lead returns
"already settled" — a pass by construction. This is counted separately
from stopped.

### Test identity exclusion

`testidentity.matches()` is checked on the id ALONE, not on the row that
also carries the address. An EmailBison event can arrive carrying the lead
id and nothing else — no address, no contact key. `matches(205079)` was
False the moment the lead existed while `matches` on its address was True.

### Event type enumeration

Every event type seen in the window is enumerated by name with a count,
including the ones that normalise to `unknown`. `EMAIL_ACCOUNT_DISCONNECTED`
is named explicitly if it appeared.

## Files

    scripts/qa/__init__.py          the registry
    scripts/qa/check_reconcile.py   the check
    tests/test_a_rule_keyed_on_a_field_nobody_carries_is_vacuous.py
    tests/test_ownership_is_resolved_per_provider_not_by_a_set.py

## Exit codes

    0   PASS         every subject checked, every rule clear
    1   FAIL         at least one subject offends at least one rule
    2   UNCONFIRMED  provider read failed or subject set EMPTY (VACUOUS)
    3   ERROR        the check itself broke

## Boundaries

- **READS ONLY at both providers.** No stop, no pause, no update, no attach.
- **Do not edit `src/inbound.py`, `src/leadstop.py`, `src/replies.py`,
  `src/stoppedcause.py`, `src/providers/*`.** Defects go in FINDINGS.
- **No prospect PII and no reply text in any committed file.**

## What would make this a false pass

- A rule gated on `heyreach_lead_id`. Zero contacts carry it.
- Not reporting key presence.
- Reconciling one direction only.
- Ownership by set membership (ISSUE-042).
- Counting "already settled" as a successful stop.
- Counting the operator's test replies as prospect replies (ISSUE-044).
- A CRITICAL that is not a CRITICAL.
- Fixtures that mock `inbound` or `leadstop`.
