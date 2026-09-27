PRIORITY: P2
SIZE: M
DEPENDS:

# TASK-417 — Campaign Cadence Drift Check (standing backlog refill, 2026-09-27)

**Auto-refilled by scripts/refill_queue.py, per the operator's 2026-09-27 standing order: the watchdog refills TODO from the template list itself, before the ready queue drops below the 12-task floor.** Source: `docs/qwen-tasks/STANDING-BACKLOG-TEMPLATE.md`, entry `campaign-cadence-drift-check`.

For every ACTIVE campaign per the latest `docs/state/PROVIDER-CAMPAIGNS.json`,
confirm its actual send cadence (real provider timestamps between sends)
matches the canonical cadence library's declared days, not an assumption.
READ-ONLY. Acceptance: real per-campaign timing measured against the
canonical cadence, named drift if any.

---

## RESULT

**STATUS**: DONE
**ARTIFACT KIND**: finding (read-only audit, no code changed)
**COMMIT SHA**: pending
**TESTS**: read-only; no tests applicable
**FILES CHANGED**: this task file only

### Data sources

| Source | What it provides | Limitation |
|--------|-----------------|------------|
| `docs/state/PROVIDER-CAMPAIGNS.json` (generated 2026-09-27T10:17:30Z) | Campaign structure: node types, message variant counts, sequence hash | No per-message timestamps, no node-level delay values |
| `docs/HEYREACH-CADENCES-2026-09-21.md` | Full graph dump with per-node delays for campaign 605732 (V2 CONTROL) | Only campaign whose graph was readable on that date; B1 batch were DRAFT and returned `ProviderError` |
| `src/cadencelibrary.py` | Canonical cadence day positions | Declares intent, not provider-native delays |
| `src/providers/heyreach.py` `linkedin_sequence()` | Translates canonical days into HeyReach graph delays | The translation is where drift can enter |

### ACTIVE campaign inventory

**HeyReach: 34 IN_PROGRESS campaigns** in three groups:

| Group | Hash | Count | Nodes | MESSAGE nodes | Started |
|-------|------|-------|-------|---------------|---------|
| B1 batch (main) | `2f7bb33ee7f6ce5a` | 32 | 20 | 6 × [3,2,4,3,2,4 variants] | 2026-09-22 |
| B1 batch (seat 174892) | `a3d4ce61b9ca79a9` | 1 | 20 | 6 × [3,2,4,3,2,4 variants] | 2026-09-22 |
| V2 CONTROL | `32f8dde79bfa0f27` | 1 | 24 | 7 × [1,1,1,1,1,1,1 variants] | 2026-09-16 |

Groups 1 and 2 have identical structure (same node types, same variant counts). The different hash is copy content, not timing.

**EmailBison: 8 active campaigns** (4 resonate-owned, 4 client_or_other). The provider JSON carries no sequence or delay data — only id, name, status, owner, lead_count. **Email cadence cannot be verified from available data.**

### Canonical cadence (declared)

`PRODUCTIVE_LI_HEAVY_V1` from `src/cadencelibrary.py`:

```
Day  1: li1 (connect)  +  em1 (email)
Day  3: li2 (message)
Day  4: em2
Day  6: li3 (message)
Day  8: em3
Day 10: li4 (message)
Day 12: em4
Day 15: li5 (message)
Day 21: em5
```

LinkedIn message-to-message gaps (from `li_message_delays_from_cadence()`):
- li2→li3: **3 days**
- li3→li4: **4 days**
- li4→li5: **5 days**

### Measured timing per campaign group

#### B1 batch (33 campaigns) — already-connected branch

From `linkedin_sequence()` code at `src/providers/heyreach.py:1299-1308`:

```
connected_1 (3h) → connected_2 (d1=3d) → VIEW_PROFILE (2d)
  → connected_3 (max(d2-2,1)=2d) → connected_4 (d3=5d)
```

| Gap | Canonical | Delivered | Drift |
|-----|-----------|-----------|-------|
| connected_1 → connected_2 | 3d | 3d | **none** |
| connected_2 → connected_3 | 4d | 2d + 2d = 4d | **none** |
| connected_3 → connected_4 | 5d | 5d | **none** |

The already-connected branch compensates for the VIEW_PROFILE between connected_2 and connected_3 by subtracting 2 from d2 (`max(d2-2, 1)`). **No drift.**

#### B1 batch (33 campaigns) — cold branch (connection accepted)

From `linkedin_sequence()` `chain()` at `src/providers/heyreach.py:1271-1278`:

```
message_2 (3h) → VIEW_PROFILE (d1=3d) → message_3 (d2=4d) → message_4 (d3=5d)
```

| Gap | Canonical | Delivered | Drift |
|-----|-----------|-----------|-------|
| message_2 → message_3 | 3d | 3d + 4d = 7d | **+4 days** |
| message_3 → message_4 | 4d | 5d | **+1 day** |

The cold branch does NOT compensate for the VIEW_PROFILE between message_2 and message_3. The VIEW_PROFILE's delay (d1=3d) and message_3's delay (d2=4d) are additive, producing a 7-day gap where the canonical cadence declares 3 days. The already-connected branch compensates (`max(d2-2,1)`); the cold branch does not.

**Named drift: COLD-BRANCH EXPANSION.** The cold path delivers LinkedIn messages at approximately day 1, day 8, day 13 from connection request (gaps 7d, 5d) instead of the canonical day 3, day 6, day 10 (gaps 3d, 4d). The cold path also delivers only 3 LinkedIn messages after the connection request, while the already-connected path delivers 4 — the cadence's li5 has no cold-branch equivalent.

This is structural, not accidental: it is baked into `linkedin_sequence()` and has been since the function was written. It is NOT a provider-side deviation — the provider is executing exactly what was written. The drift is between the canonical cadence's declared day positions and what the graph builder produces for the cold path.

#### V2 CONTROL (1 campaign, hash `32f8dde79bfa0f27`)

From `docs/HEYREACH-CADENCES-2026-09-21.md` (§605732), the full graph dump shows:

Already-connected branch: connected_1(3h) → connected_2(3d) → VIEW_PROFILE(2d) → connected_3(5d) → connected_4(7d)

Cold branch: message_2(3h) → VIEW_PROFILE(3d) → message_3(2d) → message_4(7d)

| Gap | Canonical (li_heavy_v1) | V2 CONTROL | Δ |
|-----|------------------------|------------|---|
| msg 1→2 (already connected) | 3d | 3d | 0 |
| msg 2→3 (already connected) | 4d | 2d+5d = 7d | +3d |
| msg 3→4 (already connected) | 5d | 7d | +2d |
| msg 2→3 (cold) | 3d | 3d+2d = 5d | +2d |
| msg 3→4 (cold) | 4d | 7d | +3d |

**V2 CONTROL is a deliberately wider cadence**, not drift from the canonical. It was built separately (started 2026-09-16, six days before the B1 batch) as a cohort experiment control. Its delays (3, 5, 7) are intentionally different from the canonical (3, 4, 5). The V2 also has 7 MESSAGE nodes (1 variant each) vs the B1 batch's 6 MESSAGE nodes (2-4 variants each) — it is a different experiment structure entirely.

### EmailBison campaigns

8 active campaigns. The provider JSON does not expose sequence delays or per-step timing. The internal campaign IDs are `null` for all HeyReach campaigns, so there is no link to internal campaign state that might carry the EmailBison cadence.

**Email cadence verification is BLOCKED on available data.** To measure it, either:
1. A live `GET /campaign/{id}` read from EmailBison with step-level delay data, or
2. Per-lead event timestamps from `work/queue.jsonl` (only in Claude's worktree) showing actual send times.

### Summary

| Campaign group | Count | Branch | Drift | Severity |
|---------------|-------|--------|-------|----------|
| B1 batch (hash `2f7bb3...`) | 32 | already-connected | **none** | — |
| B1 batch (hash `2f7bb3...`) | 32 | cold (accepted) | **+4d, +1d** | structural, in builder |
| B1 batch (hash `a3d4ce...`) | 1 | already-connected | **none** | — |
| B1 batch (hash `a3d4ce...`) | 1 | cold (accepted) | **+4d, +1d** | structural, in builder |
| V2 CONTROL (hash `32f8dd...`) | 1 | both | **+2d to +3d** | intentional experiment |
| EmailBison (8 campaigns) | 8 | n/a | **unverifiable** | data not available |

### FINDINGS

1. **COLD-BRANCH EXPANSION (structural).** `linkedin_sequence()` in `src/providers/heyreach.py` does not compensate for the VIEW_PROFILE delay between message_2 and message_3 on the cold branch, unlike the already-connected branch which uses `max(d2-2, 1)`. The cold path delivers a 7-day gap where the canonical cadence declares 3 days. This affects all 33 B1-batch campaigns for every prospect who was NOT already a LinkedIn connection.

2. **EMAILBISON CADENCE UNVERIFIABLE.** The `PROVIDER-CAMPAIGNS.json` does not carry EmailBison sequence or delay data. No per-lead event timestamps are available in any `docs/state/` file. Live-state access (`work/queue.jsonl`) is in Claude's worktree only.

3. **V2 CONTROL IS INTENTIONALLY DIFFERENT.** Campaign 605732 runs delays (3, 5, 7) vs canonical (3, 4, 5). This is a cohort experiment control, not drift.

### RISKS

- The cold-branch expansion means prospects who were NOT already connections receive LinkedIn messages at roughly double the intended spacing. This is the MAJORITY of cold outreach prospects. The cadence experiment comparing different intensities is confounded if the cold branch's actual spacing is wider than declared.
- No EmailBison cadence verification is possible from this worktree. If the email side also has drift, it is invisible here.

### RECOMMENDED CLAUDE ACTION

1. Decide whether the cold-branch expansion is intentional (in which case the canonical cadence's day positions should be updated to match reality) or a defect (in which case `linkedin_sequence()`'s `chain()` should compensate like the already-connected branch does).
2. For EmailBison cadence verification: run a live read from Claude's worktree with access to `work/queue.jsonl` or a direct EmailBison API call that returns per-step timing.
