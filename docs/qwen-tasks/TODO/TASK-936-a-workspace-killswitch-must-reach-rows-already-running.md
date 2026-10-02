# TASK-936 — a workspace killswitch must reach rows already running

SIZE: M

From the 2026-10-02 OSS survey (`docs/OSS-SURVEY-2026-10-02.md`, item 1).
Borrowed idea only, no dependency: a workflow engine called Temporal (MIT)
lets an external signal reach a workflow instance that is already running,
so a cancellation doesn't have to wait for the next decision point. This
task builds the same idea natively, out of two primitives that already
exist and are each independently proven, without adding anything.

## THE GAP, CONFIRMED TODAY, NOT QUOTED FROM THE OLD INCIDENT

CLAUDE.md records that turning `sending.live` off was never a pause, and an
active campaign kept sending through it exactly as documented. That was
09-28. Checked again today, on current `master`:

`src/killswitch.py` exports exactly: `global_state`, `workspace_state`,
`campaign_state`, `account_state`, `contact_state`, `step_state`, `state`,
`require`. Every one of them **answers a question**; none of them **does
anything**. There is no `stop`, `cancel`, or `sweep` in this module. It is,
correctly, a pre-send gate — `executionguard.authorize` consults it before
minting a new send. It has no channel to anything already scheduled at the
provider.

**The obvious fix, `leadstop.sweep()`, does not already cover this — checked,
not assumed.** `sweep()` (`src/leadstop.py:239`) walks every staged contact
and calls `_must_stop()` (`:338-348`), which only returns a reason when
`eligibility.must_not_contact()` yields something in
`executionguard.SUPPRESSION_REASONS` — DNC, bounce, unsubscribe, a reply, an
agency stop. It never calls `killswitch.workspace_state()` or
`killswitch.campaign_state()`. A workspace going dark does not, by itself,
give any contact in that workspace a stop reason, so `sweep()` run today
leaves them exactly where it found them.

## WHAT TO BUILD

A function — propose `leadstop.sweep_killswitched(recs=None, rows=None,
live=False, by="system")`, or fold the check into `_must_stop` itself if
that reads cleaner once you're in the code — that adds exactly one more
stop reason: the contact's workspace (or campaign) currently reads
not-sending per `killswitch.workspace_state()` /
`killswitch.campaign_state()`. Reuse `stop_contact()` and the existing
per-channel resolution in `sweep()` (`_campaign_of(..., requires=...)`,
`:271-273`) — do not write a second stop path. Idempotent for the same
reason the existing sweep is: `stop_contact` reads provider truth first and
writes nothing for someone already stopped (`leadstop.py:16-22`'s own
rationale for why idempotency comes from the provider, not from a local
flag).

**Dry run is the default**, per the house rule — `live=False` must report
what *would* be stopped without writing, exactly like the existing `sweep()`
contract.

## WHAT THIS MUST NOT DO

- Must not change what `killswitch.py` itself returns or how it's consulted
  pre-send. This is additive at the sweep layer, not a rewrite of the gate.
- Must not conflate "killswitched" with the existing suppression reasons in
  `SUPPRESSION_REASONS` — a workspace that comes back online should not have
  left behind a permanent DNC-shaped record for people who were merely
  paused. Use a distinct reason code (new entry under `holdreasons.py`'s
  vocabulary, or a dedicated event type — follow whichever convention
  `_stop_event`/`_record` (`leadstop.py:404-479`) already uses for
  provider-side pauses vs. permanent stops, and if there is no such
  distinction today, say so rather than inventing a disposition that
  `store.STATES` doesn't already have a place for).
- Must not touch `src/providers/*` — this calls the existing `stop_contact`,
  it does not add a new provider verb.

## ACCEPTANCE

Full offline suite, zero new failures and zero new errors against the
`master` baseline, diffed by test NAME both directions.

Required tests: a contact in a workspace where `killswitch.workspace_state()`
reads not-sending is included in a killswitch-sweep dry run with the reason
named; the same contact is untouched by the *existing* `sweep()`'s
suppression-reason path (prove the two are additive, not merged into one
reason); a contact in a workspace that reads sending-live is never touched by
this path; `live=False` writes nothing; re-running after a `live=True` stop
is a no-op (reads provider truth, no duplicate write) — same idempotency
contract as the existing `stop_contact` tests already assert.

## FILES FORBIDDEN

    src/clientapproval.py    src/providers/*    config/    work/*.jsonl
