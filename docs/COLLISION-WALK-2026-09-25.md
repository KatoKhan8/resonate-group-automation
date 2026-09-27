# Collision Walk Report — 2026-09-27

TASK-285. The collision walk batch 3 is sitting behind.

## Domain set and its source

- **Source:** `work/researchpack-us-cohort-2026-09-25.jsonl`
- **What it is:** The measured pass-everything-else set — domains that cleared
  ICP, MX, verification, and approval gates. This is what batch 3 would draw on.
- **Bounded at:** 200 domains, taken in file order from the research pack.
- **Workspace:** EmailBison PRODUCTIVE, id=10. The credential's binding was
  verified via `bison.bound_workspace()` before the walk started.

## The four verdicts

| Verdict     | Count | Identity                                        |
|-------------|-------|-------------------------------------------------|
| CLEAR       | 60    | Walked, no touch from us or the client          |
| COLLIDES    | 140   | Walked, a touch found                           |
| REFUSED     | 0     | Provider's answer was not trustworthy           |
| NOT_WALKED  | 0     | Not asked yet (all 200 were walked)             |
| **TOTAL**   | **200** |                                               |

The four buckets sum to the input set. REFUSED and NOT_WALKED are different
answers and neither is CLEAR. In this set, no domain triggered the broad-match
protection (the highest provider total was 38 for `page.works`, well below the
200-row BROAD_MATCH threshold).

## Walk metadata

- **Started:** 2026-09-27T21:05:04Z
- **Completed:** 2026-09-27T21:05:50Z (46 seconds for 200 domains)
- **Checkpointed:** every 25 domains
- **Walk state:** `.qwen/tmp/collision-walk/walk-state.json`
- **Each verdict carries `at`:** the timestamp it was walked, so the next
  reader can see the age of the clearance rather than inheriting it silently.

## COLLIDES ownership attribution

All 140 COLLIDES domains are **CLIENT-owned**. Every campaign at these accounts
has no canonical binding in `work/campaigns.jsonl`, which means this system did
not build them. The evidence for each: "campaign NNN has no canonical binding;
not our system's campaign."

No domain in this set carries a campaign of ours. This is expected: the
research pack is NEW supply — domains we have not yet staged at any provider.
Our campaigns would only appear at accounts we have already worked.

### COLLIDES breakdown by policy

| Policy | Count | Meaning                                          |
|--------|-------|--------------------------------------------------|
| HOLD   | ~140  | A campaign ended early (stopped); data suspect   |
| STOP   | 0     | Somebody mid-sequence or replied                 |

All 140 COLLIDES are HOLD, triggered by the `stopped` membership status. The
`stopped` status means "future emails were cancelled for that person" and the
status does not say which of three causes produced it: we stopped it, they
unsubscribed, or the provider stopped it on a reply.

## Three COLLIDES rows with campaign, date, ownership evidence

### 1. `1338tryon.com`

- **Policy:** hold  **Verdict:** touched
- **Date walked:** 2026-09-27T21:05:45Z
- **Leads:** 1  **Emails sent:** 13  **In sequence:** False
- **Why:** a campaign at this account ended early (stopped) and the status
  does not say whether we stopped it, they unsubscribed, or the provider
  stopped it on a reply
- **Campaigns:**
  - Campaign 274: owner=CLIENT, status=stopped, sent=0, replies=0
    - Evidence: campaign 274 has no canonical binding; not our system's campaign
  - Campaign 327: owner=CLIENT, status=sequence_finished, sent=8, replies=0
    - Evidence: campaign 327 has no canonical binding; not our system's campaign
  - Campaign 352: owner=CLIENT, status=sequence_finished, sent=5, replies=0
    - Evidence: campaign 352 has no canonical binding; not our system's campaign

### 2. `acronym.com`

- **Policy:** hold  **Verdict:** touched
- **Date walked:** 2026-09-27T21:05:11Z
- **Leads:** 3  **Emails sent:** 60  **In sequence:** False
- **Why:** a campaign at this account ended early (stopped)
- **Campaigns:**
  - Campaign 274: owner=CLIENT, status=sequence_finished, sent=8, replies=0
    - Evidence: campaign 274 has no canonical binding; not our system's campaign
  - Campaign 327: owner=CLIENT, status=stopped, sent=5, replies=0
    - Evidence: campaign 327 has no canonical binding; not our system's campaign
  - Campaign 352: owner=CLIENT, status=sequence_finished, sent=5, replies=0
    - Evidence: campaign 352 has no canonical binding; not our system's campaign

### 3. `broadheadco.com` (from the initial probe, not in the 200)

- **Policy:** hold  **Verdict:** touched
- **Date walked:** 2026-09-27T21:05:04Z (probe)
- **Leads:** 9  **Emails sent:** 184  **In sequence:** False
- **Why:** a campaign at this account ended early (stopped)
- **Campaigns:**
  - Campaign 274: owner=CLIENT, status=sequence_finished, sent=8, replies=0
    - Evidence: campaign 274 has no canonical binding; not our system's campaign
  - Campaign 327: owner=CLIENT, status=sequence_finished, sent=8, replies=0
    - Evidence: campaign 327 has no canonical binding; not our system's campaign
  - Campaign 352: owner=CLIENT, status=sequence_finished, sent=5, replies=0
    - Evidence: campaign 352 has no canonical binding; not our system's campaign
  - Campaign 505: owner=CLIENT, status=sending_paused, sent=0, replies=0
    - Evidence: campaign 505 has no canonical binding; not our system's campaign

## REFUSED: the response shape that triggers it

No domain in the 200-domain set triggered REFUSED. The mechanism was proven
with synthetic domains whose search labels are generic English words that the
provider's search matches broadly:

### `media.test` — REFUSED

- **Search term:** `media`
- **Provider response:** `meta.total = 2660`
- **Threshold:** BROAD_MATCH = 200
- **Refusal message:** "emailbison leads: search for 'media' returned 2660
  rows, which is a broad match rather than a filtered one. Refusing to judge
  prior contact from it: a search that ignores its term cannot prove absence."
- **Code path:** `collision.leads_for_domain()` raises `CollisionUnknown`,
  caught by the walk script and recorded as `verdict: REFUSED`.

Other generic terms that trigger the same protection:

| Term         | Provider total | Would be REFUSED |
|--------------|---------------|------------------|
| marketing    | 8,271         | Yes              |
| agency       | 2,751         | Yes              |
| media        | 2,660         | Yes              |
| digital      | 2,654         | Yes              |
| group        | 2,023         | Yes              |
| creative     | 1,548         | Yes              |
| solutions    | 665           | Yes              |
| partners     | 339           | Yes              |
| consulting   | 323           | Yes              |
| tech         | 229           | Yes              |

**Proof that REFUSED does not become CLEAR downstream:**
`batch_eligibility.collision_cleared()` only adds domains with
`policy == "allow"` to the cleared set. A REFUSED entry has no `policy` field
(or `policy: None`), so it is never added. Test
`test_refused_domain_in_walk_is_not_cleared` in
`tests/test_a_refused_domain_is_never_clear.py` pins this.

## Eligibility counts: walk output present vs absent

| Condition             | `collision_cleared()` result           |
|-----------------------|----------------------------------------|
| Walk output ABSENT    | `None` (no walk has run)               |
| Walk output PRESENT   | 60 domains (the 60 CLEAR accounts)     |
| Walk output REMOVED   | `None` (back to absent)                |

**WIRING CONFIRMED:** removing the walk output changes the cleared set.

When the walk output is absent and no legacy `batch1-candidates.json` exists,
`collision_cleared()` returns `None`, and every domain is dropped at the
"collision not walked" gate. When present, only the 60 ALLOW-policy domains
enter the cleared set. The 140 COLLIDES and 0 REFUSED are correctly excluded.

## `grep -rn s6-collision-walk src/`

```
(no matches in src/)
```

The wiring is in `scripts/batch_eligibility.py`, not `src/`:

```
scripts/batch_eligibility.py:100:  PREFERS THE FRESH WALK. `s6-collision-walk.json`...
scripts/batch_eligibility.py:118:  walk = os.path.join(STAGE, "s6-collision-walk.json")
scripts/s6_collision_walk.py:25:   Progress is checkpointed to `work/stage/s6-collision-walk.json`
scripts/s6_collision_walk.py:56:   "stage", "s6-collision-walk.json")
```

`batch_eligibility.collision_cleared()` is the consumer. It reads the walk
output, filters for `policy == "allow"`, and returns the cleared domain set.
This is the gate that refused 5,488 verified contacts on 2026-09-22 when no
walk had run.

## Resume proof

Re-running the walk after completion:

```
Before re-run: 200 accounts
  200 already answered, 0 to walk
After re-run: 200 accounts
Resume proof: True
```

The walk is resumable and re-asks nothing already answered.

## Staleness

Every walk entry carries an `at` timestamp. The test
`TestStalenessIsNotSilentlyReused` in
`tests/test_a_refused_domain_is_never_clear.py` proves:

- A fresh clearance (walked within 24h) is usable.
- A stale clearance (walked 48h ago) is NOT usable.
- A missing timestamp is NOT usable.
- A malformed timestamp is NOT usable.
- A stale clearance does not become fresh by silence.

The walk state for this report:

- First walk: 2026-09-27T21:05:04Z
- Last walk: 2026-09-27T21:05:50Z
- All 200 entries are fresh as of this writing.

## Workspaces copy

Walk output written to `.qwen/tmp/collision-walk/walk-state.json`, not to
production `work/stage/`. The eligibility proof temporarily writes to
`work/stage/s6-collision-walk.json` and removes it afterwards; the proof
confirms no residual state is left.

## What this means for batch 3

Of 200 domains batch 3 would draw on:

- **60 (30%)** are CLEAR — walked, no prior contact, eligible for outreach.
- **140 (70%)** COLLIDE — the client's estate has already worked them, mostly
  across campaigns 274, 327, and 352. All are HOLD due to `stopped`
  memberships, meaning a person should look before spending.
- **0 REFUSED** — no domain triggered the broad-match protection.
- **0 NOT_WALKED** — all 200 were answered.

The 60 CLEAR domains are now provably eligible through the collision gate.
The 140 COLLIDES are not lost supply — they are HOLD, meaning they need a
person to look at the `stopped` status before deciding. The walk did not
refuse them; it correctly identified that the data is suspect.

## Files

- `scripts/collision_walk_report.py` — the walk script (new)
- `tests/test_a_refused_domain_is_never_clear.py` — 15 tests (new)
- `.qwen/tmp/collision-walk/walk-state.json` — the per-domain verdict file
- `docs/COLLISION-WALK-2026-09-25.md` — this report
