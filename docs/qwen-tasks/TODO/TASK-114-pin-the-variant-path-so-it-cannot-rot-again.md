PRIORITY: P4
DEPENDS: TASK-089

# TASK-114 - regression tests for the variant path

## WHY

The variant machinery was **622 lines with 453 lines of green tests and had
never generated anything.** TASK-077 ran it against a real model for the first
time and found two defects, one of which meant LinkedIn variants had NEVER
worked. The tests were green throughout.

That is the third time in this repository a green suite was written around its
own assumption. The fix is not more tests; it is tests that would have caught
THIS.

## WHAT TO PIN

1. **The prompt carries the schema.** `variant_prompt()` built a prompt that
   never told the model to return JSON and never gave it the shape -
   `grep -in json src/variantgen.py` returned nothing. Pin that the variant
   path goes through the same prompt contract as the draft path, so the two
   cannot drift apart again.
2. **The arms are structurally different.** The diversity check compares
   opening type, CTA type, tone, length and product-introduction point. Pin
   that a set of near-identical arms is REFUSED - with a fixture built from
   the real collapsed output TASK-087 measured, where every arm opened and
   closed with a question.
3. **The fifth arm is withheld without evidence.** `observation_led` must be
   absent when no licensed observation exists, and present when one does. Pin
   both directions - a test that only proves it is absent would pass if it
   were removed entirely.
4. **Counterfactual.** For each test, break the thing it guards and confirm
   the intended test fails for the intended reason, and that a different guard
   did not fire first. A test that cannot fail proves nothing.

## THE TRAP TO AVOID

**Do not assert on the text of the source.** Searching source for words
produces a test that fails when somebody writes a comment, and that has
happened repeatedly here. Assert on what a function RETURNS or on the import
graph.

And do not write a test that mocks the model into returning perfect JSON and
then declares the JSON contract proven. The defect was that the real model got
a prompt with no schema in it; a mock that returns the right shape regardless
reproduces the exact blindness that let this survive.

## DELIVERABLE

The tests, the counterfactual evidence for each, and a note in the task file
saying which of them would have caught the original TASK-084 defects. If one
of them would not have, say so - that is the useful part.

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
