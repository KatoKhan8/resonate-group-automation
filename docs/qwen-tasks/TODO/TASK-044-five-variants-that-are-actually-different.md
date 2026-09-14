# TASK-044 - Five variants per step, materially different

The operator's invariant: every meaningful outbound message step generates at
least five variants, and they must NOT be synonym swaps.

## WHAT IS ALREADY DONE

TASK-022 built the carriage: a variant travels from canonical state into the
provider payload, the factory reads the RECORDED `variant_id`, and a variant
whose words are not covered by an approval is reported as missing copy. Five
variants means five approvals.

What does not exist is the GENERATION of five materially different ones.

## GOAL

Generate five variants per message step that test different approaches, and a
check that they actually differ in approach rather than in wording.

## THE DIMENSIONS the operator named

    A  concise / direct
    B  conversational
    C  problem-led
    D  observation / research-led
    E  Productive / value-led

And where appropriate: question-led, insight-led, peer/role framing,
operational framing, commercial framing, curiosity CTA, direct CTA.

## THE CONSTRAINTS THAT OUTRANK VARIETY

Every variant is subject to the same gates as any other copy, and this is
where a variant generator goes wrong:

- no fabricated familiarity, no invented prior conversation, no invented pain,
  no unsupported company claim. `claims.check` refuses all four and a variant
  is not exempt.
- **D, the research-led variant, is the dangerous one.** A model asked for an
  observation-led message with no observation available will invent one.
  Variant D must be UNAVAILABLE when the record carries no licensed
  observation, rather than generated and then rejected - see
  `src/observations.py`, which is what licenses a thing being said.
- Missing research falls back to generic copy. It does not fall back to
  invented research.

## SCOPE

1. Extend `generate` to produce N variants for a step, each with a named
   approach, using the ladder's purpose for that rung as the shared brief.
2. Approach must be RECORDED per variant, so a result can later be attributed
   to an approach rather than to a string.
3. A check that two variants of the same step differ in more than wording -
   reuse whatever TASK-043 builds rather than writing a second comparator.
4. A variant that cannot be supported is NOT generated. Report which and why.
5. Do not call a live model in this task. Build it against a fake and let
   Claude run generation.

## PRODUCTION BOUNDARY

ZERO network, ZERO credentials - `config/.env` does not exist in this
worktree. No provider call. No write to `work/**`. Nothing staged, activated
or sent. Claude owns every live action.

## HANDOFF FORMAT

STATUS / COMMIT SHA / FILES CHANGED / TESTS RUN / TEST RESULTS / BUGS FOUND /
BUGS FIXED / RISKS / OPEN QUESTIONS / RECOMMENDED CLAUDE ACTION

Plus the grep proving each new name is CONSUMED, and confirmation that
deleting the CALL to your new code makes a test fail.

## TESTS REQUIRED

- five variants for a step carry five distinct recorded approaches;
- a record with no licensed observation produces no research-led variant, and
  says so;
- a variant asserting something unsupported is refused by `claims`, not
  merely flagged;
- two variants that are synonym swaps are caught;
- each variant carries its own approval requirement.

## DONE CONDITION

A step can hold five approach-labelled variants, an unsupportable approach is
absent rather than invented, and nothing weakened a claims gate to get there.
