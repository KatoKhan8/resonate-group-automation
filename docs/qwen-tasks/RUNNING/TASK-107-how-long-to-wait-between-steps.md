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
