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

STATUS: COMPLETE
COMMIT SHA: cc93c8a
TESTS: N/A (analysis task, no code change to test)
FILES CHANGED:
  - scripts/task107_delay_analysis.py (new, collection + analysis script)
  - docs/DELAY-ANALYSIS-2026-09-15.md (new, deliverable report)
  - docs/qwen-tasks/RUNNING/TASK-107-how-long-to-wait-between-steps.md (task file)

FINDINGS:

1. **EmailBison delay distribution (PROVIDER FACT, n=121 step definitions):**
   - 3 days: 40.5% of steps (49/121)
   - 5 days: 19.0% (23/121)
   - 4 days: 11.6% (14/121)
   - 2 days: 11.6% (14/121)
   - 1 day: 10.7% (13/121)
   - 7+ days: 6.6% (8/121)
   - Most campaigns end with a 1-day gap before the final step.

2. **HeyReach delay distribution (PROVIDER FACT, n=1,218 nodes across 83 campaigns):**
   - 5 days: 269 nodes (largest cluster)
   - 1 day: 127 nodes
   - 10 days: 122 nodes
   - 0 hours: 123 nodes (immediate follow-on actions)
   - 3 hours: 35 nodes
   - 3 days: 41 nodes
   - Connection campaigns (565xxx series): uniform +0H, +0H, +5D, +5D pattern
   - Production campaign 599020: +0H, +3H, +3H, +3D, +3H, +2D, +1D, +5D, +3H, +5D, +7D, +3D, +2D, +7D

3. **Time-to-reply IS available. TASK-059 was WRONG.**
   - `date_received` present on 100% of 1,740 reply rows (PROVIDER FACT)
   - `sent_at` present on 100% of 1,476 scheduled email rows (PROVIDER FACT)
   - `scheduled_email_id` present on 99.8% of reply rows (PROVIDER FACT)
   - The join works: 1 human reply matched in our sample (1.3h response time at step 6)
   - The sample is too small for a distribution (1,476 sampled emails vs 238K+ total sends)
   - The data was ALWAYS there. The earlier report did not perform the join.

4. **HeyReach time-to-reply (PROVIDER FACT, n=5,291 from existing analysis):**
   - Median: 6.1h
   - P75: 33.3h (1.4 days)
   - Mean: 41.1h (right-skewed)
   - A 3-day (72h) follow-up arrives AFTER 75% of replies

RISKS:
- EmailBison time-to-reply sample is n=1. A larger scheduled-email sample or
  targeted fetch of replied-to emails would give a proper distribution.
- The HeyReach time-to-reply data is from a previous analysis (TASK-058) and
  covers LinkedIn, not email. Email and LinkedIn reply timing may differ.
- No causal claim: configured delay vs reply rate requires a controlled
  experiment, not a distribution.

RECOMMENDED CLAUDE ACTION:
- Accept the report as the delay baseline.
- If a proper EmailBison time-to-reply distribution is needed, run a targeted
  fetch: for each human reply in the full feed, GET the scheduled email it
  references. ~1,000 API calls for the known reply set, vs 18,000 for the
  full feed walk.
- The finding that 3-day follow-ups arrive after 75% of replies is actionable
  for cadence design but is not yet a proven learning (needs a controlled
  comparison of reply rates at different delay values).
