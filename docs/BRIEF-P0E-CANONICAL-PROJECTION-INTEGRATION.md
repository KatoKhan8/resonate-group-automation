# P0-E — CANONICAL PROJECTION INTEGRATION

**Operator instruction, Zvonimir, 2026-09-28. THE NEXT P0 AFTER P0-B.**
Do not start while P0-B is modifying `src/generate.py` and
`src/generate_campaign.py` — the overlap would collide and could silently
revert P0-B's work.

## Why this exists — the defect, measured

**CLAIM** The approval hash is never computed in production.
**AUTHORITY** `sequenceplan.derive_bison_payload`, `derive_heyreach_payload`
and `derive_preview_data` have **zero callers**, and they are the **only**
callers of `sequenceplan.approval_hash` — whole-repository call graph,
`docs/P0D-PRODUCTION-CALLER-2026-09-28.md`, branch
`task-p0d-production-caller` head `01dd7b78`.
**MEASURED AT** 2026-09-28. **STATE** VERIFIED (static). Runtime confirmation
is a separate task, branch `task-runtime-approval-hash-probe`.

That is the **mechanical root cause of launch blocker 1** ("approval hash not
enforced"). The plan's *shape* half is wired; its *words* half is write-only —
built, flattened into `rec["cadence"]`, discarded. **The provider payload is
then rebuilt three further times, independently, by `bisonfactory`, `push` and
`render`, none derived from the plan.** That is three parallel implementations
of a projection the "one truth" invariant (§5) says must have exactly one.

## The target chain

    generation -> gates -> ONE canonical SequencePlan
      -> approval bound to the exact approved content
        -> canonical EmailBison / HeyReach projection
          -> provider write gate

**Remove or make unreachable the three independent downstream payload
builders. No parallel implementations.** A second builder left reachable is
the defect, not a fallback.

## Acceptance — all eleven, each proven, not asserted

     1. the real production CLI consumes the canonical SequencePlan
     2. the EmailBison projection derives ONLY from that plan
     3. the HeyReach projection derives ONLY from that plan
     4. the preview derives ONLY from that plan
     5. the approval hash is actually calculated on the real path
     6. approval is bound to the EXACT provider-bound content
     7. changing approved content INVALIDATES approval
     8. regenerated copy CANNOT reuse an old approval
     9. bypassing canonical projection FAILS
    10. the intercepted provider payload MATCHES the canonical plan
    11. provider writes remain 0 throughout verification

**Mutation-test the approval boundary and the canonical-projection boundary.**
Break each deliberately; confirm the intended test went red for the intended
reason, that a different guard did not fire first, and that the source was
restored byte-identical by hash.

Items 7 and 8 are the ones most likely to pass vacuously — an approval that is
never computed cannot be invalidated, so prove the hash exists on the real
path (item 5) **before** claiming either of them.

## Standing constraints

- **PROVIDER WRITES = 0** throughout. Interceptor on the single chokepoint,
  fired deliberately at least once so a zero count means something.
- `sending.live` is False for productive. **The freeze remains active.**
- **Do not weaken any gate** — not `sequencegate`, not `copylint`, not claim
  validation, not a threshold, and not by making a check inert.
- Do not start the ten-account run.
- Copied production input only; verify production `work/queue.jsonl` and
  `work/campaigns.jsonl` byte-identical by sha256 from a fresh process —
  content, not mtime.
- Report every claim as **CLAIM / AUTHORITY / MEASURED AT / STATE**. A test
  count is never a PASS. Classify on the ladder ABSENT / IMPLEMENTED /
  UNIT_TESTED / INTEGRATION_TESTED / LIVE_VALIDATED / PRODUCTION_ACTIVE.

## Prior art to read first, not to redo

- `docs/P0D-PRODUCTION-CALLER-2026-09-28.md` — the call graph, the per-link
  ladder rungs, and a wiring plan **specified and deliberately not applied**
  (four steps, smallest first). Step 1 repoints one *reader* in
  `bisonfactory.py` and touches neither of P0-B's files; steps 2-4 sequence
  after P0-B lands.
- `docs/RUNTIME-APPROVAL-HASH-PROBE-2026-09-28.md` when it exists — runtime
  confirmation of the same finding.
- One smaller defect found alongside and **not** part of this task:
  `src/run.py:311` enters the same engine one level lower
  (`generate_record`), skipping `generate.run`'s per-record
  `store.transaction`, whose own comment says it exists so "the evidence and
  history loss guards still run." Consequence UNPROVEN. Its own task.
