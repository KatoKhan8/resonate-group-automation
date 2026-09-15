PRIORITY: P3
DEPENDS: 

# TASK-109 - re-measure INTERESTED, because nobody has

## THE OPEN DEBT

`docs/TAXONOMY-PRECISION-2026-09-14.md` measured the taxonomy on 263 replies,
200 drawn at random from the UNKNOWN pool and hand-labelled:

    INTERESTED       precision 0.44   recall 0.62     more than half wrong
    MEETING_INTENT   precision 1.00   recall 1.00
    OBJECTION        precision 1.00   recall 0.67

The bare adjectives were then removed and replaced with specific
constructions, and the noun-phrase form refused entirely.

**That 0.44 measured the OLD pattern set. The NEW set is UNMEASURED, and
unmeasured is not the same as good.** Checkpoint D records the re-measure as
owed and unqueued. This is it.

## WHAT TO DO

Re-measure INTERESTED precision and recall on a FRESH hand-labelled sample -
not the 263 the patterns were built against, because measuring on the set you
tuned on measures nothing. Draw a new random sample from the UNKNOWN pool,
hand-label it blind to the classifier's output, then score.

Report precision AND recall. If precision improved but recall collapsed, the
patterns bought their accuracy by refusing everything, and that is a different
problem with the same headline number.

## THE DECISION THIS FEEDS

INTERESTED currently **may not carry a learning claim** anywhere in this
repository. If the new set measures well, that restriction can lift. If it
does not, it stays, and every analysis that wants a positive set keeps using
MEETING_INTENT instead.

**Do not lift the restriction yourself.** Report the number; the restriction
is Claude's to lift.

## WHAT NOT TO DO

- Do not tune the patterns on the sample you are measuring with. Label first,
  score second, and do not iterate.
- Do not count an UNKNOWN as a negative.
- Do not reintroduce a bare adjective pattern however well it scores on a
  sample. The noun-phrase ambiguity is structural, not statistical.

## DELIVERABLE

`docs/INTERESTED-REMEASURE-2026-09-15.md`: the new sample, the labelling
method, precision and recall with n, and a clear recommendation on whether the
learning-claim restriction should lift.

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

## RESULT

**STATUS:** DONE

**COMMIT SHA:** 5209e9e

**TESTS:** Not applicable — this is a measurement task, not a code change. The
scoring script (`scripts/task109_score.py`) was run and produced the results
in the deliverable.

**FILES CHANGED:**
- `docs/INTERESTED-REMEASURE-2026-09-15.md` — the deliverable report
- `scripts/task109_collect_unknowns.py` — sample collection script
- `scripts/task109_score.py` — scoring script
- `scripts/task109_labels.json` — hand-labels for the 200-reply sample
- `docs/qwen-tasks/REVIEW/TASK-109-is-the-new-interested-pattern-set-any-good.md` — this file

**FINDINGS:**

The NEW INTERESTED pattern set has **zero recall** on a fresh sample of 200
UNKNOWN replies (seed=109, drawn from a pool of 3,893). The taxonomy fires on
0 of 200 in the sample, and only 20 of 3,893 (0.5%) in the full pool.

| Category | Precision | Recall | n (actual) |
|----------|-----------|--------|------------|
| INTERESTED | 0.00 (undefined) | 0.00 | 15 |
| MEETING_INTENT | 0.00 (undefined) | 0.00 | 1 |
| OBJECTION | 0.00 (undefined) | 0.00 | 2 |

The patterns are so narrow after removing bare adjectives that they catch
almost nothing. The old set measured 0.44 precision / 0.62 recall — wrong
more than half the time but at least it tried. The new set is inert.

**The learning-claim restriction should NOT be lifted.** Not because precision
is bad, but because there is nothing to measure. Zero predictions is not
perfect precision; it is zero coverage.

**RISKS:**
- The measurement is on one sample of 200. A different seed might yield a
  different number of hand-labelled interested replies, but the taxonomy
  would still predict zero because the patterns do not match the language
  in the pool.
- The full-pool scan (3,893 replies) confirmed the taxonomy fires on only
  20, so the zero in the sample is not a fluke.

**RECOMMENDED CLAUDE ACTION:**
- Keep the learning-claim restriction on INTERESTED.
- Decide whether INTERESTED is worth detecting at all. If yes, the options
  are: (a) broaden patterns carefully with negation guards, (b) use a model,
  or (c) accept that INTERESTED stays UNKNOWN and use MEETING_INTENT for
  positive signals.
- The report is in `docs/INTERESTED-REMEASURE-2026-09-15.md`.
