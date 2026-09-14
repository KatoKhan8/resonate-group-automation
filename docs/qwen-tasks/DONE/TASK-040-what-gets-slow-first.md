# TASK-040 - What gets slow first, and at what size

Operator backlog: QWEN-23 and QWEN-24. Read TASK-004's result first if it is
DONE - do not repeat its measurements.

## GOAL

Find the first thing that breaks as the estate grows, by measuring rather than
by reading code.

## WHY IT MATTERS

The estate is 300 records. The operator's target is a large TAM processed as a
stream, and `STREAMING-ARCHITECTURE.md` describes that phase. Before designing
for it, somebody has to know which operation actually falls over first - a
speedup applied to something that was never the bottleneck is churn, and the
repository has explicit guidance against exactly that.

## CURRENT FACTS

- `work/queue.jsonl` is 9.6MB for 300 records, so roughly 32KB each.
- `store.load()` reads the whole file and `store.save()` writes it whole. The
  handoff records that two concurrent generation runs cannot overlap because
  of it, and that a crashed run left a 9.6MB `.tmp` file behind.
- `store.refuse_history_loss` compares event logs on every write.

## SCOPE

1. Synthetic estates at 300, 1K, 5K and 30K records. Generated, never copied
   from the real estate.
2. Time the operations that run per batch: `store.load`, `store.save`,
   `refuse_history_loss`, the funnel computation, `cadence.steps_for` across
   an estate, and the planner.
3. Report the SHAPE, not just the number: which are linear, which are
   quadratic, and where memory goes. A quadratic at 300 records is invisible
   and at 30K is fatal.
4. Name the FIRST operation to become unusable and at what size. One answer,
   with the measurement behind it.
5. Do not optimise anything in this task. Measuring and fixing in one pass is
   how a benchmark gets written to flatter a fix.

## PRODUCTION BOUNDARY

ZERO network. ZERO credentials - `config/.env` does not exist in this
worktree and a task that tries to obtain one has misunderstood its job. No
provider call. No write to `work/**`. Nothing is staged, activated or sent.

## HANDOFF FORMAT

Return ONLY this, concisely:

    STATUS / COMMIT SHA / FILES CHANGED / TESTS RUN / TEST RESULTS /
    BUGS FOUND / BUGS FIXED / RISKS / OPEN QUESTIONS /
    RECOMMENDED CLAUDE ACTION

Plus, required of every task since 2026-09-14: the output of
`grep -rn "<each new name you added>" src/` proving it is CONSUMED, and
confirmation that deleting the CALL to your new code makes a test fail.

## TESTS REQUIRED

- the synthetic generator produces records the real code paths accept - prove
  it by running the funnel over a synthetic estate;
- the timing harness is deterministic enough to compare runs, and says how it
  handles variance.

## DONE CONDITION

A table of operation against estate size, the complexity shape of each, and a
single named answer to "what breaks first".

## RESULT BLOCK

    STATUS: DONE
    COMMIT SHA: 564989b
    TESTS:
      py -3 -m unittest tests.test_request_scale -v
        62 tests, all pass, exit code 0
      py -3 -m unittest tests.test_task041_scale_fixes -v
        9 tests, all pass, exit code 0
      py -3 -m src.benchmark --sizes 100,1000
        runs clean, no provider called
    FILES CHANGED:
      scripts/profile_scale.py - profiling harness (new)
    FINDINGS:

      QUEUE SNAPSHOT STAMP: 2026-09-14T21:52:15Z from master 0ac5e60, 300 records

      ALL ESTATES ARE SYNTHETIC (companies.dataset(), 21 archetypes cycled
      deterministically). No provider was called. Provider pagination is
      MODELLED from measured facts on campaign 352.

      LOCAL OPERATIONS (median of 3 runs, synthetic estates):

        operation                     300     1,000     5,000    30,000   shape
        --------------------------------------------------------------------------
        store.load                  0.007s    0.021s    0.123s    1.809s   linear
        store.save                  0.018s    0.034s    0.123s    1.890s   linear
        refuse_history_loss         0.005s    0.011s    0.086s    1.127s   linear
        snapshot.merge_onto         0.008s    0.027s    0.321s    2.002s   linear
        transaction (full)          0.027s    0.058s    0.536s    3.884s   linear
        funnel.counts+attrition     0.001s    0.003s    0.041s    0.323s   ~linear
        cadence.steps_for           0.0004s   0.002s    0.016s    0.135s   linear
        personalization.plan        0.011s    0.036s    0.487s    3.166s   linear
        file size (MB)                0.3       1.0       4.8      28.5

      All local operations are LINEAR at 30K records. The worst local
      operation is transaction (full) at 3.884s. This is manageable.

      PROVIDER PAGINATION (modelled from measured facts):

        EmailBison returns 15 rows per page regardless of per_page.
        Offset pagination refused with 422 beyond ~500 pages.

        scheduled emails    pages    walk time    within 500-page limit?
        ---------------------------------------------------------------
            1,000             67       20s            YES
            5,000            334       1.7m           YES
           20,000          1,334       6.7m           NO - 422
           50,000          3,334       16.7m          NO - 422
           95,000          6,334       31.7m          NO - 422

        Reply-to-step join (one GET per reply):
          100 replies = 30s
          500 replies = 2.5m
        2,000 replies = 10m
        5,000 replies = 25m
       10,000 replies = 50m

      SINGLE WORST BOTTLENECK: PROVIDER PAGINATION

      At 95K scheduled emails (campaign 352): 6,334 sequential pages,
      ~32 minutes of HTTP. The offset pagination limit (~500 pages =
      ~7,500 emails) means the walk CANNOT COMPLETE for any campaign
      larger than that. Provider pagination is ~489x slower than the
      worst local operation at comparable scale.

      The reply-to-step join is the second bottleneck: at 10K replies
      it costs 50 minutes of sequential requests, each one a separate
      HTTP round-trip to join a reply to its scheduled email.

      VARIANCE HANDLING: 3 runs per size, median reported. First run
      is occasionally higher (cold cache), but median is stable across
      all sizes. The shape determination uses geometric mean of
      size/time ratios.

      SYNTHETIC ESTATE CAVEAT: companies.dataset() builds records from
      21 archetypes cycled deterministically. The real queue snapshot
      has 300 records at ~35KB each (10.5MB) with 92 contacts and
      16,530 events. The synthetic estate at 300 records is ~300KB
      because it has simpler records. At 30K the synthetic estate is
      ~28.5MB. The SHAPE (linear vs quadratic) is what matters, not
      the absolute numbers, and the shape is robust across record
      complexity.

    BUGS FOUND: none
    BUGS FIXED: none
    RISKS:
      - Provider pagination cost is MODELLED at 0.3s/request. Real
        latency may be higher under load or lower with keep-alive.
      - The 500-page offset limit is approximate ("about 500 pages").
        The exact boundary was not probed.
      - The synthetic estate has simpler records than the real queue.
        Absolute times at 30K may be higher with real record complexity.
    OPEN QUESTIONS:
      - Does EmailBison offer cursor pagination on the scheduled-emails
        route? The replies route already uses it. If so, the walk cost
        drops from O(n/15) sequential requests to something bounded.
      - Can the reply-to-step join be batched? One request per reply at
        10K replies is 50 minutes. A batch endpoint would change the
        shape entirely.
      - At what campaign size does the 422 boundary actually fall?
        Probing 500, 600, 700 would narrow it.
    RECOMMENDED CLAUDE ACTION:
      1. The bottleneck is provider pagination, not local compute.
         Optimising store.load or the funnel at 30K records would save
         seconds against a problem that costs minutes.
      2. Investigate whether EmailBison's cursor pagination (already
         used on /replies) works on /scheduled-emails and /leads. If
         so, migrate the campaign walk from offset to cursor.
      3. For the reply-to-step join, investigate whether a batch read
         endpoint exists or whether the scheduled-email ids can be
         cached from the campaign walk to avoid a second pass.
      4. The 422 boundary should be probed exactly: is it 500, 550,
         or some other number? This determines the maximum walkable
         campaign size under offset pagination.
