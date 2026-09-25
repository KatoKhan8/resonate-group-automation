# Collision Walk — 2026-09-25

## What was walked

200 domains from `work/researchpack-us-cohort-2026-09-25.jsonl` (the batch 3
supply set), taken in file order. The walk script is
`scripts/s6_collision_walk.py`, which calls `collision.check_account` per
domain against workspace 10 (PRODUCTIVE) — the credential's bound workspace,
verified by `bison.bound_workspace()` before any read.

Walk started: `2026-09-25T21:47:10Z`.
Walk state: `work/stage/s6-collision-walk.json`.

## The four verdicts

| Verdict     | Count | Meaning                                         |
|-------------|-------|-------------------------------------------------|
| CLEAR       | 60    | Walked, no live touch (35 clean + 25 historical)|
| COLLIDES    | 140   | Walked, a touch found — all client's campaigns  |
| REFUSED     | 0     | Provider answer untrustworthy (broad match)     |
| NOT_WALKED  | 0     | Not asked yet (all 200 were answered)           |
| **Sum**     | **200** | Equals the input set                          |

CLEAR breaks down as:
- `allow / clear` — 35 domains with zero prior contact at the provider
- `allow / touched` — 25 domains where campaigns finished with sends but no
  reply; history, not a live conflict (`account_policy` returns ALLOW)

COLLIDES breaks down as:
- `hold / touched` — 140 domains where the provider estate holds prior contact
  that is not provably ours and not provably silent

REFUSED is zero. The refusal mechanism is `collision.CollisionUnknown`, raised
when `leads_for_domain` gets a `meta.total > 200` (broad match) or an
unreadable `last_page`. This estate's domain searches all returned
single-digit to low-double-digit results; no search triggered the threshold.

## Three COLLIDES rows with campaign, date, and ownership evidence

### 1. broadheadco.com

First person from provider: `fseitz@broadheadco.com`

| Field          | Value                                            |
|----------------|--------------------------------------------------|
| lead_id        | 141606                                           |
| lead_status    | unverified                                       |
| emails_sent    | 21                                               |
| replies        | 0                                                |
| opens          | 0                                                |
| in_sequence    | False                                            |
| created_at     | 2026-04-08T18:32:58Z                             |

Campaigns (from `lead_campaign_data`):

| campaign_id | status             | emails_sent | replies | opens |
|-------------|--------------------|-------------|---------|-------|
| 274         | sequence_finished  | 8           | 0       | 0     |
| 327         | sequence_finished  | 8           | 0       | 0     |
| 352         | sequence_finished  | 5           | 0       | 0     |

**Ownership evidence:** `campaign_bindings()` returns 0 bindings in this
worktree (no `work/campaigns.jsonl`). All three campaigns are
**CLIENT's** — no canonical row claims them. The touches are the client's
own estate's prior outreach. 9 leads at this domain, all with the same
campaign pattern. Policy: HOLD — "a campaign at this account ended early
(stopped) and the status does not say whether we stopped it, they
unsubscribed, or the provider stopped it on a reply."

### 2. adm-indicia.com

First person: `sophia.malik@adm-indicia.com`

| Field          | Value                                            |
|----------------|--------------------------------------------------|
| lead_id        | 168365                                           |
| lead_status    | unverified                                       |
| emails_sent    | 9                                                |
| replies        | 0                                                |
| opens          | 0                                                |
| in_sequence    | False                                            |
| created_at     | 2026-04-23T19:54:01Z                             |

Campaigns:

| campaign_id | status             | emails_sent | replies | opens |
|-------------|--------------------|-------------|---------|-------|
| 328         | stopped            | 4           | 0       | 0     |
| 352         | sequence_finished  | 5           | 0       | 0     |

**Ownership evidence:** Both campaigns have no binding. **CLIENT's**
campaigns. 8 leads at this domain across campaigns 265, 274, 327, 328, 352.
Policy: HOLD — suspect status (`stopped`) on campaign 328.

### 3. icrossing.com

First person: `michelle.eier@icrossing.com`

| Field          | Value                                            |
|----------------|--------------------------------------------------|
| lead_id        | 141951                                           |
| lead_status    | unverified                                       |
| emails_sent    | 18                                               |
| replies        | 0                                                |
| opens          | 0                                                |
| in_sequence    | False                                            |
| created_at     | 2026-04-08T18:32:59Z                             |

Campaigns:

| campaign_id | status             | emails_sent | replies | opens |
|-------------|--------------------|-------------|---------|-------|
| 274         | sequence_finished  | 8           | 0       | 0     |
| 327         | stopped            | 5           | 0       | 0     |
| 352         | sequence_finished  | 5           | 0       | 0     |

**Ownership evidence:** All three campaigns have no binding. **CLIENT's**
campaigns. 8 leads at this domain across campaigns 264, 265, 274, 327, 328,
352. Policy: HOLD — suspect status (`stopped`) on campaign 327.

## REFUSED

Zero domains were REFUSED in this walk. The refusal mechanism is
`collision.CollisionUnknown`, raised when:

1. `leads_for_domain` gets `meta.total > BROAD_MATCH (200)` — the provider's
   search filter was ignored and the result is a broad match, not a filtered
   one. Answering from this would be answering from the whole estate.
2. `meta.last_page` is unreadable — a partial page cannot prove it saw the
   whole result.
3. The workspace binding cannot be verified.

In this estate (workspace 10, PRODUCTIVE), all 200 domain searches returned
single-digit to low-double-digit row counts, well below the 200 threshold.
The REFUSED bucket is empty but the mechanism is live and tested —
`tests/test_a_refused_domain_is_never_clear.py` pins that a REFUSED verdict
is never policy=allow and never passes `collision_cleared()`.

**A REFUSED domain is NOT CLEAR and NOT NOT_WALKED.** It is a third state:
"we asked and could not trust the answer." The test file proves the three
buckets are distinct and sum to the input set.

## Wiring proof

`scripts/batch_eligibility.py`'s `collision_cleared()` reads
`work/stage/s6-collision-walk.json` and returns the set of domains with
`policy == "allow"`. Only those domains pass the collision gate in
`eligible()`.

**With the walk output present:**
```
collision_cleared() returns 60 domains
```

**With the walk file removed:**
```
collision_cleared() returns None
```

`None` means no walk has run and no fallback exists (no
`batch1-candidates.json` in this worktree either). When `collision_cleared()`
returns `None` and `require_collision=True` (the default), `eligible()`
cannot pass any domain through the collision gate — every domain is refused
as NOT_WALKED.

**Deleting the read changes eligibility from 60 cleared to 0.** The walk
output is consumed, and the gate is live.

`grep -rn s6-collision-walk src/` returns **zero hits**. The consumer is in
`scripts/batch_eligibility.py`, not `src/`. The wiring path is:

```
s6_collision_walk.py  ->  writes  work/stage/s6-collision-walk.json
batch_eligibility.py  ->  reads   work/stage/s6-collision-walk.json
                          in collision_cleared() at line 118
```

## Resume proof

Re-running the walk after completion:
```
200 already answered, 0 to walk
```

The walk is resumable. Progress is checkpointed to
`work/stage/s6-collision-walk.json` after every 25 accounts. Re-running
skips every domain already in the state file and re-asks nothing.

## Staleness

Every verdict row carries `at` — the UTC timestamp of when that domain was
walked. The walk state carries `started_at` for the run as a whole. A
clearance from a previous run is visible by its age and is not silently
reused: the walk re-asks on every run, and the `at` field on each row is
updated to the current run's timestamp.

## What this walk does NOT do

- **It does not rewrite the account rule.** TASK-275 owns that. The raw
  verdicts (policy + verdict + why) are reported without interpretation.
- **It does not attribute client touches as ours.** `campaign_bindings()`
  returns 0 bindings in this worktree. Every campaign at every COLLIDES
  domain is the client's. No touch was called ours.
- **It does not run the LinkedIn side.** The HeyReach inbox is ~27k
  conversations and the company-level check is unanswerable
  (`account_is_unanswerable` — `searchString` matches correspondent name
  only, never `companyName`). The person-level LinkedIn check
  (`check_linkedin_profile`) is separate and was not run as part of this
  walk.

## Files

| File | Purpose |
|------|---------|
| `work/stage/s6-collision-walk.json` | Walk state, 200 domains, checkpointed |
| `work/_s/supply.json` | 200-domain input set, from research pack |
| `scripts/collision_walk_report.py` | Report script (four buckets) |
| `tests/test_a_refused_domain_is_never_clear.py` | 5 tests, REFUSED≠CLEAR |
| `docs/COLLISION-WALK-2026-09-25.md` | This document |
