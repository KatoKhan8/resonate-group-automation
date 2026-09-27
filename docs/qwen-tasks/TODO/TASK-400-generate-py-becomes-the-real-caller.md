PRIORITY: P0
SIZE: L
DEPENDS:

# TASK-400 — make `src/generate.py` the real caller of `generate_campaign`, critical path

**Operator instruction, 2026-09-27 morning, in direct response to GLM
CHECKPOINT A (TASK-383, `docs/glm-reviews/checkpoint-a-2026-09-27.md`):**
3 of 7 controls FAIL. The new entrypoint (`generate_campaign.generate()`)
and its five wired skills are internally correct — mutation-tested,
sentinel-tested — and externally inert: `src/generate.py` (the actual
`python -m src.generate --live` production path) never calls any of it.
Second Brain facts, the Offer Engine, campaign strategy and the five skills
all currently have zero effect on what a real send would produce.

**READ TASK-391 FIRST** (`docs/qwen-tasks/DONE/` or the REVIEW copy on
`qwen-worker-3-r9` before Claude merges it) — it already tried the smaller
version of this fix (wire the five skills directly into `generate.py`'s five
stages: `diagnose`, `hook`, `persona_angle`, `draft`, `linkedin_note`) and
found it does not work: `generate.py` is record-centric with rich
per-record context (`already_sent`, `siblings`, `prior_contact`,
`step.purpose`) that the skills' batch-oriented procedures have no
equivalent for. **Do not repeat that attempt.** TASK-391's own conclusion is
the starting point: the fix has to happen at the level the operator names
below, not by forcing skills onto stages they were never written for.

## The two acceptable shapes — pick one, name which, and say why

**A. `generate.py` calls `generate_campaign.generate()`.** `generate.py`'s
outer loop (record iteration, `store` integration, event logging, lint,
cadence) stays; its per-record stage-calling body is replaced by a call into
`generate_campaign.generate()` for that record's account, and the SequencePlan
it returns is adapted into whatever `generate.py` currently writes to the
record/store. This keeps `generate.py`'s production integrations
(store/events/lint/cadence, which `generate_campaign.py` does not have) while
retiring its own stage-calling logic.

**B. `generate_campaign.generate()`'s body replaces `generate.py`'s**, and
`generate.py`'s store/event/lint/cadence integrations are added TO
`generate_campaign.py` (which currently has none) rather than the reverse.

**Decide based on which direction loses less real, load-bearing
integration work** — `generate.py`'s store/event/cadence code, or
`generate_campaign.py`'s Second-Brain/offer/skill wiring. State the decision
and the reason before writing code.

## Acceptance — Checkpoint A's own seven controls, reproduced through the REAL entrypoint

Not through `generate_campaign.generate()` called directly — through
whatever `python -m src.generate --live` (or its test-mode equivalent)
actually runs.

1. **One entrypoint.** After this change, is there still a second, unused
   generation path? Name it if so; the goal is one, not two that happen to
   agree.
2. **Second Brain has a real consumer.** A verified Second Brain fact
   changes the output of a real `generate.py` run - reproduce the same
   mutation test TASK-369/375/379 already did, but through `generate.py`.
3. **Canonical research authority unchanged** — still `rec["research"]`,
   still the one store. Do not introduce a second one in this change.
4. **Changing an approved fact changes the resulting artifact** — through
   `generate.py`, not `generate_campaign.generate()` called in isolation.
   This is the section 4 test, reproduced end to end.
5. **No critical logic depends on gitignored `work/`** — unchanged; verify
   your change did not introduce a new one.
6. **No closed wiring loop.** The five skills now have an external consumer
   (a real send path), not just `generate_campaign.py` calling them.
7. **No cross-account research leakage** — unchanged; verify your change
   did not weaken `packfacts.identity_of()`'s exact-identity join.

Plus: the Offer Engine (`NotApproved` fail-closed) and copylint/sequencegate
must still run on this path exactly as they do today - this task connects
the new pipeline, it does not remove any existing safety gate.

## What this task may NOT do

- Do not send, activate, resume, enrol or attach anything. Production
  freeze stays. Test/dry-run mode only for every acceptance check.
- Do not weaken or remove copylint, sequencegate, the Offer Engine gate, or
  any suppression/approval check to make the switch easier.
- Do not retry TASK-391's skill-onto-stage approach — read its finding
  first, it is settled.
- Full suite: wait for `work/suite_verdict.txt`, diff the failing-name SET
  against the current baseline. This is a large change; a new failure here
  blocks, per OPERATING-MODE's own rule.
