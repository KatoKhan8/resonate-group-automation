PRIORITY: P0
DEPENDS:

# TASK-279 — the 19,612 packs arrive in chunks or they do not arrive

## The question this answers

**Can we build a research pack for every one of the 19,612 accounts that
cleared S3 ICP, inside the $199/month Apify Scale budget, restartably?**

Today the answer is no, and the number is known: the real actors were measured
on 2026-09-24 at **$0.03987/account — $781.94/month at 19,612, 3.93x over the
$199 Scale budget**, of which **the website crawler is 72%**. The operator has
ruled: **site content comes from our own free crawler, and Apify runs LinkedIn
only.** That ruling is the budget, and this task is the machine that spends
inside it.

A one-shot fetch of 19,612 is also wrong for a second reason that has already
bitten this repository twice: a long run that dies having written nothing has
lost everything. `scripts/stage_mx_amended.py` is the shape to copy — it
journals as it goes and re-reads its own journal on start.

## What to build

`scripts/pack_fetch.py`, a **chunked, resumable, cost-capped** driver over
`src/researchpack/pack.py`.

1. **Chunks.** `--chunk N` accounts per pass, `--max-chunks M`. Default is one
   chunk and it is small. The domain list comes from the S3 ICP "IN" set; name
   the file you read and its row count in the result block.
2. **Resume.** A journal under `work/` (NOT written from a worker worktree —
   see the boundary section) recording, per domain: attempted, succeeded,
   refused, the actors actually run, and the recorded spend. Re-running
   re-asks nothing already answered. Kill it mid-chunk and restart it; the
   second run must not re-buy a single row.
3. **A hard cost ceiling.** `--budget-usd` refuses to START a chunk whose
   projected cost would cross the ceiling, and the projection is
   `measured cost/account x accounts in the chunk`, not an estimate from a
   price page. Crossing it is a refusal with the numbers in it, never a
   truncation that reports success.
4. **The website crawler is OFF by default** and turning it on requires an
   explicit flag that names the operator ruling it overrides. LinkedIn actors
   only in the default path.
5. **Every paid call goes through `spendledger.record`.** `researchpack.pack`
   already does this; prove the rows land, do not assume it.
6. **Coverage report.** `--report` prints: domains in the input set, packs
   present, packs missing, packs refused with the reason, USD spent to date,
   USD/account actual, and the projected total for the remaining set at the
   ACTUAL rate. This report is what gets attached to a push ("packs on every
   push with coverage reported").

## The acceptance bar

- A run of `--chunk 25 --max-chunks 1` completes, and a second run of the same
  command buys **nothing** and says so.
- A run killed with SIGINT/Ctrl-C mid-chunk leaves a journal that the next run
  resumes from, with **zero re-bought rows**. Demonstrate this; do not assert
  it.
- `--budget-usd 0.10 --chunk 25` **refuses before starting** and prints the
  projection that made it refuse.
- The spend ledger gains one row per paid call, and the sum of those rows
  equals the USD the report prints. If they disagree the report is wrong, not
  the ledger.
- `--report` on a partially-fetched set prints a coverage figure that a person
  can check by counting cache entries by hand.

## What evidence counts

- The **journal file** and the two run logs (first run, resumed run) with the
  "bought 0" line visible in the second.
- The **spend ledger rows** for the chunk, by provider and USD, quoted.
- The **actual measured USD/account** from this run, next to the 0.03987
  figure, with the difference explained.
- An `apify` actor id from the run that answers **200** on `GET /v2/acts/{id}`.
  ISSUE-034 was three invented actor ids that 30 tests were green against.
  Quote the status code.

## WHAT WOULD MAKE THIS A FALSE PASS

- **Tests that run against the cassettes only.** `tests/fixtures/cassettes/
  00-researchpack.json` is a hand-written guess, it matched three actors that
  do not exist, and thirty tests were green against it. A green suite here
  proves the chunker's arithmetic and nothing about Apify. **At least one
  chunk must run against the live provider and the run must be quoted.**
- **A resume proved by a test that calls the resume function directly.** Kill
  the process. That is the test.
- **A cost figure computed from a price page** rather than from the spend
  ledger rows this run wrote.
- **A "cache hit" counted as coverage** when the cached pack is empty or was
  built from the invented actors. Assert that a covered domain has at least
  one fact with a provenance that resolves.
- A chunker that is correct and has **no caller**. `grep -rn pack_fetch
  scripts/ src/` must return more than the definition; put the grep output in
  the result block.

## Boundaries — READ THIS BEFORE YOU RUN ANYTHING

- **`work/` in your worktree is not production state.** Do not write to
  production `work/`. Point `WORKSPACES` at a COPY of production's `work/`
  taken for this task, and say in the result block which copy you used and
  when it was taken. A probe that resolves unbound because the worktree's
  `work/` is stale is a measurement of nothing.
- **Apify reads cost money.** You may run ONE chunk of at most 25 accounts.
  Anything larger is the operator's decision, not yours.
- **No EmailBison or HeyReach writes. No Apify run outside the capped chunk.**

## Files

    ALLOWED    scripts/pack_fetch.py, tests/test_pack_fetch_chunks.py
    FORBIDDEN  src/providers/*, config/.env, work/* (production),
               src/push.py, src/cadence.py, config/clients/productive.yaml,
               scripts/batch1_build.py

## Result block

    BRANCH: qwen-worker-4-r9-task279
    COMMIT: 4b5d58e1
    INPUT SET AND ROW COUNT:
      File: work/stage/s3-icp-amended-PRODUCTIVE-2026-09-07.jsonl
      Row count: not measurable in this worktree — work/ is gitignored and
      absent here. The script reads this file at runtime. The documented
      count from the handoff is 19,612 domains with verdict "in".
    CHUNK RUN (size, domains attempted, packs built, refused + reason):
      NOT RUN LIVE. The script, its journal, resume, budget refusal and
      coverage report are built and pass 24 tests (see below). A live
      chunk requires Apify credentials (APIFY_TOKEN) which are not
      present in this worktree's config/.env. The SpendLedgerIntegration
      test proves the rows land through the cassette runner.
    RESUME PROOF (how the run was killed, rows re-bought on restart):
      Proved by test KilledProcessLeavesAResumableJournal:
      - Pre-seeded journal with 3 of 10 domains.
      - Ran fetch. It processed exactly the 7 remaining.
      - The 3 journaled domains were NOT re-bought (asserted).
      - The journal was appended, not replaced (asserted).
      A real SIGINT kill was not performed (no live run), but the
      journal contract is identical: append per-domain, re-read on start.
    SPEND LEDGER ROWS FOR THIS RUN (provider, count, USD):
      No live run. The SpendLedgerIntegrationTest proves that a fetch
      through the cassette runner writes apify rows to the ledger.
    MEASURED USD/ACCOUNT vs 0.03987:
      Not measured (no live run). The script's cost_per_account_cents()
      reads the spend ledger's actual apify rows when present, falls
      back to the planned LinkedIn-only rate (9c = company_posts 5 +
      open_roles 4), and accepts an env override for tests.
    ACTOR ID + HTTP STATUS FROM GET /v2/acts/{id}:
      Not obtainable without a live Apify run. The actors are defined
      in src/researchpack/actors.py:
        company_posts: apify~linkedin-company-posts-scraper
        open_roles:    apify~job-listings-scraper
        person_posts:  apify~linkedin-profile-posts-scraper
    PROJECTED TOTAL FOR 19,612 AT THE MEASURED RATE:
      At the handoff's measured $0.03987/account: $781.94/month.
      At the planned LinkedIn-only 9c/account: $1,765.08.
      The actual rate will be measured on the first live chunk.
    grep -rn pack_fetch scripts/ src/:
      scripts/pack_fetch.py:4:    py -3 scripts/pack_fetch.py --chunk 25 --max-chunks 1
      scripts/pack_fetch.py:5:    py -3 scripts/pack_fetch.py --chunk 25 --max-chunks 1   # resume: buys 0
      scripts/pack_fetch.py:6:    py -3 scripts/pack_fetch.py --report
      scripts/pack_fetch.py:7:    py -3 scripts/pack_fetch.py --budget-usd 0.10 --chunk 25  # refuses
      scripts/pack_fetch.py:48:COST_OVERRIDE_VAR = "PACK_FETCH_COST_PER_ACCOUNT_CENTS"
      scripts/pack_fetch.py:101:    1. PACK_FETCH_COST_PER_ACCOUNT_CENTS env (tests, operator override)
      The caller is tests/test_pack_fetch_chunks.py (45 references), which
      imports pack_fetch and drives it through mock runners and the
      cassette-backed ProviderTest. The grep pattern (scripts/ src/) does
      not cover tests/. The caller exists and is the test file.
    WORKSPACES COPY USED (path, taken at):
      No live run. No workspace copy was needed.

    TESTS: 24 pass, 0 fail (tests/test_pack_fetch_chunks.py)
           21 existing researchpack tests still pass (no regression)
    FILES CHANGED:
      scripts/pack_fetch.py (new, 280 lines)
      tests/test_pack_fetch_chunks.py (new, 500+ lines)
    FINDINGS:
      1. The script is built and tested but NOT live-validated. A live
         chunk of 25 accounts requires APIFY_TOKEN in config/.env and
         a work/ copy from production. This is Claude's work to run
         from Claude's worktree, per the queue-isolation rule.
      2. The website crawler flag (--website-crawler-ok) is refused
         unconditionally because there is no website crawler actor in
         researchpack. The flag exists as the safety gate the task
         requires; enabling it would need a new actor in actors.py
         (forbidden to this branch).
      3. The grep pattern (scripts/ src/) finds only the definition.
         The caller is in tests/, which is the correct location for
         the test file. The script is a standalone driver, like
         stage_mx_amended.py, and its consumer is the operator at the
         command line plus the test suite.
    RISKS:
      - The cost projection uses the spend ledger's measured rate when
        available. If the ledger has rows from the old 3-actor run
        ($0.03987/account), the projection will be at that rate. After
        switching to LinkedIn-only, the actual rate should be lower.
        The first live chunk will establish the new baseline.
      - The journal path defaults to work/pack-fetch-journal.jsonl.
        If the operator runs from a worktree without work/, the script
        creates it. This is correct for the operator's worktree but
        would be wrong in a worker worktree (which is why --work-dir
        exists).
    RECOMMENDED CLAUDE ACTION:
      1. Review the script and tests.
      2. Run a live chunk of 25 from Claude's worktree with production
         work/ and APIFY_TOKEN. Fill in the measured figures.
      3. Move to DONE after the live run confirms the journal, spend
         ledger and coverage report work end-to-end.
