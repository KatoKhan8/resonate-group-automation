PRIORITY: P4
DEPENDS: 

# TASK-111 - the EmailBison API surface, and what is still guessed

## WHERE THIS STANDS

`docs/BISON-API-CAPABILITY-MAP-2026-09-14.md` and
`docs/BISON-PROVIDER-TRUTH-2026-09-14.md` established a great deal, including
the finding that matters most: **step-level AND variant-level attribution are
REAL**, verified end to end -

    reply 1609180 -> scheduled_email 22290485 -> sequence_step_id 4039
                  -> variant=True, variant_from_step=4037

and that the reply -> step link is **TWO HOPS, not one**: a reply carries
`scheduled_email_id` and NOT `sequence_step_id`. An earlier task called it
"directly supported" and sent the next reader hunting a field that does not
exist.

## WHAT IS STILL UNESTABLISHED

`src/providerwrites.py` lists these as "no documented route" for EmailBison:
create campaign, configure sequence, pause/activate. But `SUPPORTED` now
contains `bison.create_campaign` and `bison.set_sequence`, so two of those
WERE established and the docstring had not caught up - it has now been
corrected, but the underlying question stands:

**Which EmailBison routes are genuinely established, and which are still
guesses?** An endpoint counts as established only when the provider documented
it, the existing code carries its confirmed shape, or a real response has been
read.

## WHAT TO DO

1. Inventory every EmailBison route the codebase references or calls.
2. For each: documented / shape confirmed in code / real response read /
   guessed. Cite the evidence.
3. Probe READ-ONLY routes to confirm shapes. **Do not probe a write route** -
   "guessing a write path against a live client estate is how somebody
   discovers a route by mutating production."
4. Report what a lead-add would need, without performing one.

## WHAT NOT TO DO

- No writes. Not even a "harmless" one to a draft campaign.
- Do not mark a route established because the code has a URL for it. The URL
  being known is exactly the state the write gate calls UNSUPPORTED.

## DELIVERABLE

An updated capability map with an evidence column, and a clear list of what is
still guessed.

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
