PRIORITY: P2
DEPENDS: 

# TASK-107 - delays: what the estate did, and what it got

## WHAT IS KNOWN

    delays observed   0-14 days between steps, 3-day gaps most common

That is what was configured. Whether a 3-day gap outperforms a 7-day gap is
unmeasured.

HeyReach campaign 599020's own delays are `+0H, +1D, +2D, +2D, +3D, +3D...`
across 24 nodes, and the readback pins them, so any change there is visible.

## WHAT TO ESTABLISH

1. The real distribution of configured inter-step delays across the estate,
   per provider, with campaign counts.
2. **Time to reply**, if the data supports it. TASK-059 reported "No
   time-to-reply data available" - find out whether that is a provider
   limitation or a lookup that was not done. A reply row and a scheduled email
   row both carry timestamps; if the join is possible for the 934 rows that
   carry `scheduled_email_id`, then time-to-reply IS available for those and
   the earlier report was wrong about it. **Check before repeating it.**
3. If time-to-reply is computable: what does the distribution look like, and
   does it suggest that a follow-up sent at day 3 arrives before most replies
   would have arrived anyway?

## WHAT NOT TO DO

- Do not propose a delay change on the strength of a distribution. What was
  configured is not what worked.
- Do not treat a reply with no timestamp as an instant reply.

## DELIVERABLE

`docs/DELAY-ANALYSIS-2026-09-15.md`, and an explicit verdict on whether
time-to-reply is available - because a previous report said it was not, and
that claim is worth either confirming or correcting.

## RULES THAT APPLY TO THIS TASK

- Reads only at both providers. No POST/PATCH/PUT/DELETE, no sends, no
  campaign creation or activation, no adding leads.
- **A zero and a wrong lookup are indistinguishable from the outside.** If you
  measure zero of something, prove you read the right field first. Industry
  and headcount were reported at 0% three separate times by a reader looking
  at `sizing`, which is null everywhere, instead of `company_facts`.
- Say what you SAMPLED. `per_page` is accepted and IGNORED on every EmailBison
  route - you get 15 rows whatever you ask for - and offset pagination is
  refused past ~500 pages. A number without its page budget is not
  reproducible.
- Never use `meta.total` as a sent count. Campaign 274 reports 30,411
  scheduled rows and zero of its first 100 pages are sent. Count rows WHERE
  `sent_at` IS PRESENT.
- **Do not quote 8.49%** - unreproduced. **Do not quote any open rate** -
  `open_tracking` is False estate-wide, which is an ABSENT MEASUREMENT and not
  a zero. **Do not count an UNKNOWN as negative** - 53.4% of unknowns are
  correctly unknown.
- INTERESTED may NOT carry a learning claim: 0.44 precision on the old pattern
  set, and the new set is UNMEASURED, which is not the same as good.
  MEETING_INTENT (1.00) and OBJECTION (1.00) may, with recall stated.
- Never weaken, widen or disable a gate, a lint rule or a sender limit to make
  something pass or to gain volume. Fix what produced the bad output.
- Read every test exit code OFF THE PROCESS, never through a pipe.
- No unhashed PII in any tracked file or commit message - no real names,
  domains, emails, profile URLs or reply text. A seat holder is a real person
  too; Claude leaked one yesterday and the guard caught it.
- Separate OBSERVATIONS (with n), HYPOTHESES, and PROVEN LEARNINGS. Leave
  PROVEN LEARNINGS empty if nothing survives a sample-size objection. TASK-059
  left it empty and was right to.

---

## RESULT BLOCK

**STATUS:** COMPLETE

**COMMIT SHA:** 34c4f09

**TESTS:** No test suite applicable — this is a measurement task, not a code change. The script (`scripts/task107_delay_analysis.py`) was run against live provider APIs (reads only) and the report was generated from cached data.

**FILES CHANGED:**
- `docs/DELAY-ANALYSIS-2026-09-15.md` — the deliverable report
- `scripts/task107_delay_analysis.py` — the collection and analysis script
- `docs/qwen-tasks/RUNNING/TASK-107-how-long-to-wait-between-steps.md` — task moved from TODO to RUNNING

**FINDINGS:**

1. **EmailBison delay distribution (n=122 step instances, 21 campaigns):**
   - 3 days: 35.2% (most common)
   - 5 days: 23.8%
   - 1 day: 11.5%, 2 days: 11.5%
   - 7+ days: 5.7%

2. **HeyReach delay distribution (n=1,218 delay nodes, 83 campaigns, 81 with delays):**
   - 24h (1 day): 35.7% (most common)
   - 120h (5 days): 25.5%
   - 0h (immediate): 14.4%
   - 240h (10 days): 10.0%

3. **Time-to-reply IS computable.** TASK-059's claim was wrong. The `sent_at` field exists on scheduled emails and `date_received` exists on reply rows; the join via `scheduled_email_id` works. 65 pairs computed from a bounded sample (1,500 reply rows, ~10,500 scheduled email rows scanned):
   - Median: 0.0 hours
   - p90: 39.8 hours (1.66 days)
   - 92.3% of replies arrive before day 3
   - 86.2% arrive before day 1
   - 72.3% arrive within 1 hour (likely includes auto-replies)

4. **A day-3 follow-up arrives AFTER most replies.** 92.3% of observed replies arrived before day 3. This does not mean the follow-up is useless — it means the follow-up targets the 7.7% who have not yet replied.

**RISKS:**
- The time-to-reply sample (n=65) is small and biased toward recent sends. The 0.0h values likely include auto-replies that were not separated.
- The HeyReach delay analysis reads `actionDelay`/`actionDelayUnit` from the node graph, which is the configured delay before each action fires — not the actual elapsed time between actions.
- The EmailBison step data covers parent steps only (122 instances), not variants. Campaign 352 alone has 44 steps including variants.

**RECOMMENDED CLAUDE ACTION:**
- The time-to-reply finding corrects TASK-059's record. The correction should be noted in any future analysis that references that report.
- The delay distributions are descriptive, not prescriptive. No delay change should be proposed on this basis alone.
- A larger time-to-reply sample (full reply feed walk, ~270K rows) would strengthen the distribution claims. The collection script supports this with `--reply-pages`.
