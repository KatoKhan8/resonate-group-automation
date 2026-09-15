PRIORITY: P3
DEPENDS: 

# TASK-108 - the 23.8% that no pattern matched

## WHERE THIS SITS

TASK-066 classified 3,869 LinkedIn "unknown" replies by failure mode:

    53.4%  GENUINELY AMBIGUOUS, correctly unknown   "thanks", "hi", "ok"
    23.8%  no pattern matched                        <- THIS TASK
    11.9%  missed positive, most still ambiguous
     4.8%  emoji only
     2.5%  missed negative
     2.3%  missed not_relevant

Unknown moved 73.6% -> 70.0%. **The largest bucket is the classifier being
RIGHT**, and a hypothesis died here: `unknown_direction_count` is 0 across all
76,315 touches, so the unreadable bucket is NOT our own outbound copy.
Extraction is not the defect. It is purely a pattern gap.

## WHAT TO DO

Take the 23.8% "no pattern matched" bucket. Read a random sample by hand - at
least 150 - and classify what they actually are. Then answer:

1. What fraction are genuinely classifiable, and into what?
2. What patterns would catch them, stated as ACTS rather than MANNERS?
3. What is the precision of each proposed pattern on a held-out sample?

## THE RULE THAT DECIDES THIS TASK

**MEETING_INTENT and OBJECTION measured 1.00 precision because they were built
out of ACTS - naming a time, stating a constraint. INTERESTED measured 0.44
because it was built out of MANNERS.** One pattern, a bare
`interesting|intriguing|intrigued`, caused 21 of 29 false positives.

The noun-phrase form is refused entirely and must stay refused: "that's an
intriguing approach" and "this is an interesting waste of my time" are the
same shape and only the noun decides which is which. A genuine positive is
lost with it, on purpose.

**A wrong POSITIVE lets automation keep contacting somebody who said no.**
TASK-067 was rejected for turning 10 of 13 refusals into POSITIVE, and its own
16 tests passed because they only tested "not interested" with a **d** and
never "not interesting" with a **g**. Test the adversarial case or your green
suite means nothing.

## DELIVERABLE

The hand-labelled sample, proposed patterns with MEASURED precision and
recall, and an explicit refusal to propose any pattern that cannot beat the
manners trap. Do not reduce unknown by guessing.

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
