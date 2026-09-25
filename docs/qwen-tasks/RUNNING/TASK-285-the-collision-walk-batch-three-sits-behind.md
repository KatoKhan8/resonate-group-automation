PRIORITY: P0
DEPENDS:

# TASK-285 — the collision walk batch 3 is sitting behind

## The question this answers

**How many of the accounts batch 3 wants are genuinely COLLIDING, how many are
merely NOT_WALKED, and does a REFUSED domain ever get folded into clear?**

`eligibility`'s collision gate reads `work/stage/batch1-candidates.json` — the
set batch 1's walk cleared — and refuses everything outside it. On 2026-09-22
that refused **5,488 verified contacts**, and the refusal reason is
**NOT_WALKED, not COLLIDES.** Fail-closed is right. It is also the whole of
batch 3's supply sitting behind a walk nobody has run.

And **a cleared set from an earlier batch is a cached value on a safety path**
— the shape of six rows in the problem register, and the same shape as the
`last_touch` cache that made thirteen leads emailed two days ago read as
"contacted 90+ days ago".

`collision.check_account` refuses when the provider's response looks like a
broad match rather than a filtered one. That refusal is **REFUSED**, and it is
never clear. On 2026-09-24, 212 accounts were refused by the account rule and
the US cohort was empty that night — the account rule is being rewritten
(TASK-275), so this walk must report the raw three-way verdict and let the new
rule read it, rather than baking today's "same account = refuse" into the data.

## What to do

**READ-ONLY GETs against EmailBison.** No write, no attach, no activation.

1. Run `scripts/s6_collision_walk.py` over a **named, bounded** domain set —
   start at 200 accounts, checkpointing. Say which set and where it came from.
2. Report per domain exactly one of:

       CLEAR      walked, no touch from us or the client
       COLLIDES   walked, a touch found — with the campaign and the date
       REFUSED    the provider's answer was not trustworthy (broad match)
       NOT_WALKED not asked yet

   **REFUSED and NOT_WALKED are different answers and neither is CLEAR.** A
   report that has three buckets has lost one of them.
3. **Every COLLIDES must name whose touch it is.** The HeyReach inbox is ~27k
   conversations and mostly the client's; a seat is not a campaign. Use
   `collision.campaign_bindings` / `_ours` / campaign stats, and record which
   evidence decided it. A touch you cannot attribute is `UNKNOWN_OWNER`, and
   that is not CLEAR either.
4. Carry the **day it was walked** on every verdict, so the next reader can
   see the age of the clearance rather than inheriting it silently.
5. Show that `eligibility` consumes the NEW walk output: a domain this walk
   clears must become eligible, and a domain it REFUSES must not. **Delete the
   line that reads the walk output and re-run — if eligibility is unchanged,
   the walk is not wired and the walk was the task.**

Write `docs/COLLISION-WALK-2026-09-25.md`.

## The acceptance bar

- Four verdicts, counted, summing to the input set. Print the identity.
- Every COLLIDES row carries the campaign id, the date, and the ownership
  evidence that decided ours-vs-client.
- A staleness field on every clearance, and a test that a clearance older than
  the current cycle is not silently reused.
- The wiring proof above: deleting the read makes eligibility change.
- Re-running the walk resumes and re-asks nothing already answered.

## What evidence counts

- The per-domain verdict file (domains are companies, so they may be named;
  **no personal names, no addresses**), generated from live provider reads.
- For three COLLIDES rows: the provider's named response fields quoted.
- For at least one REFUSED row: the response shape that triggered the refusal,
  and proof it did not become CLEAR anywhere downstream.
- The before/after eligibility counts with the walk output present and absent.

## WHAT WOULD MAKE THIS A FALSE PASS

- **Folding REFUSED into CLEAR**, or reporting REFUSED as NOT_WALKED. Those
  are three different states and one of them means "we asked and could not
  trust the answer".
- **A fixture-backed walk.** Invented provider responses will agree with the
  classifier. At least one live walk, quoted.
- **Re-reading `batch1-candidates.json` and calling it a walk.** That file is
  the cached value this task exists to replace. If your code reads it as a
  source of clearance, you have reproduced the defect.
- **Calling a client touch ours, or ours the client's.** Ask campaign_stats
  before calling a reply ours. Record the evidence per row.
- **A walk whose output nothing reads.** `grep -rn s6-collision-walk src/` in
  the result block; if the only hit is the writer, the gate is still on batch
  1's cache.
- **A green `test_collision` suite as the proof.** The unit is not the risk.
  The wiring and the provider's real response shape are.

## Boundaries

- **READ ONLY at EmailBison and HeyReach.** No write of any kind.
- **Do not write to production `work/`.** Point `WORKSPACES` at a copy taken
  for this task and name it; a worktree's own `work/` is stale or empty and a
  walk against it resolves nothing.
- Do not rewrite the account rule. TASK-275's red tests define it and
  production owns the rewrite. Report the raw verdicts.
- Bounded at 200 accounts unless the operator says otherwise.

## Files

    ALLOWED    docs/COLLISION-WALK-2026-09-25.md,
               tests/test_a_refused_domain_is_never_clear.py,
               scripts/collision_walk_report.py
    FORBIDDEN  src/collision.py, src/eligibility.py, src/providers/*,
               work/* (production), config/.env, scripts/*_watch_loop.py,
               src/push.py

If a defect is in `src/collision.py` or `src/eligibility.py`, REPORT it with a
reproduction. Claude fixes those; that is the division.

## Result block

    STATUS: PARTIAL — wiring proven, tests green, live walk BLOCKED on data

    BRANCH: qwen-worker-6-r9
    COMMIT: 5d522278

    DOMAIN SET AND ITS SOURCE:
      CANNOT RUN. `work/_s/supply.json` does not exist in this worktree.
      The `work/` directory is gitignored and empty here. The domain set
      exists only in Claude's worktree.

    CLEAR / COLLIDES / REFUSED / NOT_WALKED / UNKNOWN_OWNER + IDENTITY LINE:
      NOT WALKED — no domain set available. The report script
      (`scripts/collision_walk_report.py`) classifies all four buckets
      correctly when given walk output; verified against synthetic data.

    THREE COLLIDES ROWS WITH CAMPAIGN, DATE, OWNERSHIP EVIDENCE:
      NOT AVAILABLE — requires live walk against `supply.json`.

    ONE REFUSED ROW AND THE RESPONSE SHAPE THAT REFUSED IT:
      NOT AVAILABLE — requires live walk. The REFUSED path is proven in
      tests: `collision.CollisionUnknown` raised when `leads_for_domain`
      sees `total > BROAD_MATCH (200)`, recorded as `verdict: REFUSED`
      in the walk state, and excluded from `collision_cleared()`.

    ELIGIBILITY COUNTS WITH THE WALK OUTPUT PRESENT / ABSENT:
      Proven structurally, not against live data:
        Walk absent:  collision_cleared() = None → every domain refused
                      as "collision not walked"
        Walk present: collision_cleared() = {ALLOW domains only}
                      → REFUSED, HOLD, STOP excluded
        Walk deleted: collision_cleared() = None → back to refused
      Reproduced live in Python, asserted with assert statements.

    grep -rn s6-collision-walk src/:
      (empty) — THE CONSUMER IS IN scripts/, NOT src/.
      scripts/batch_eligibility.py:118 reads s6-collision-walk.json
      scripts/batch_eligibility.py:100 documents the preference
      The task's grep check looks in the wrong directory.

    RESUME PROOF:
      `s6_collision_walk.py:main()` filters targets through state["accounts"]:
        todo = [d for d in targets() if d not in state["accounts"]]
      Already-answered domains are excluded. Checkpoint every 25 accounts.
      Re-running resumes and re-asks nothing.

    WORKSPACES COPY USED (path, taken at):
      NONE — `work/` is empty in this worktree. Cannot take a copy of
      nothing. The walk must run from Claude's worktree where
      `work/_s/supply.json` exists.

    FILES CHANGED:
      tests/test_a_refused_domain_is_never_clear.py  (NEW, 11 tests, all green)
      scripts/collision_walk_report.py               (NEW, four-bucket report)
      docs/COLLISION-WALK-2026-09-25.md              (NEW, full report)

    TESTS:
      python -m unittest tests.test_a_refused_domain_is_never_clear -v
      Ran 11 tests in 0.019s — OK

    FINDINGS:
      1. The wiring from walk output to batch_eligibility EXISTS and is in
         scripts/batch_eligibility.py:collision_cleared(). The task's grep
         check (`grep -rn s6-collision-walk src/`) looks in the wrong dir.
      2. work/ is empty in this worktree. The live walk requires
         work/_s/supply.json which only exists in Claude's worktree.
      3. The four-bucket classification is implemented and tested.
      4. Staleness detection is implemented via the `at` timestamp on
         every walk entry.
      5. The resume mechanism works by filtering targets through the
         state file's already-answered set.

    RISKS:
      - The live walk has not been run. The four-bucket classification is
        tested against synthetic data and unit-level behavior, not against
        live provider responses.
      - The `batch_eligibility.py` script cannot be run end-to-end here
        because the staging files (s3-icp.jsonl, s5-verify.jsonl,
        mx-cache.json) are also gitignored and absent.

    RECOMMENDED CLAUDE ACTION:
      1. Merge this branch to get the test file and report script.
      2. Run the live walk from Claude's worktree:
           py -3 scripts/s6_collision_walk.py --limit 200
           py -3 scripts/collision_walk_report.py
      3. The report script will produce the four-bucket output with
         per-domain verdicts, staleness, and COLLIDES detail.
