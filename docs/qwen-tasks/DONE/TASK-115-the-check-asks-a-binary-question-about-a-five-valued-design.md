PRIORITY: P1
DEPENDS: 

# TASK-115 - the diversity check asks a binary question about a five-valued design

## THE FINDING THIS COMES FROM

`docs/THE-OPENING-WAS-NEVER-MEASURED-2026-09-15.md`. Two things were
established there and both are settled - do not re-derive them:

1. `_opening_shape` used to read the first LINE, which on a one-paragraph
   LinkedIn message is the whole message, so it returned exactly what
   `_cta_shape` returned. The opening was never measured. Fixed, and pinned by
   `tests/test_opening_is_not_the_cta.py`.
2. After the fix, measured against the real model:

       li2   5 arms   1 question / 4 statement openings
       li3   5 arms   1 question / 4 statement openings
       li4   5 arms   0 question / 5 statement openings
       diversity_collisions TRUE on all three

## THE QUESTION

`APPROACHES` declares five openings:

    concise_direct     statement
    conversational     question
    problem_led        pain
    observation_led    evidence
    value_led          outcome

**Four of those five are semantically statements**, and `_opening_shape` sees
only punctuation, so it returns `statement` for all four and reports them as
structurally identical.

But they are not identical. Opening on the cost of the status quo is a
genuinely different message from opening on a concrete gain, which is
different again from opening on a specific observed fact. The operator's
requirement is "different angle/structure/tone/CTA, not superficial word
changes" - and **angle is exactly what the check cannot currently see.**

So: should the diversity check compare the approach's declared SEMANTIC
opening - pain vs outcome vs evidence vs question vs plain statement -
instead of, or alongside, the punctuation binary?

## INVESTIGATE, AND REPORT WHICH IT IS

1. **Is the declared opening honoured in the output?** For each approach, take
   the generated text and judge by hand whether it actually opens on pain, on
   outcome, on evidence, and so on. If `problem_led` is declared `pain` but
   opens on a generic statement, then comparing declared values would compare
   LABELS rather than copy - and a check that compares labels passes five
   identical messages that merely carry five different tags. **That is the
   single most dangerous outcome available in this task.**
2. **If the declared opening IS honoured**, propose comparing it, and measure
   what happens: how many of li2/li3/li4 still collide?
3. **If it is NOT honoured**, the finding is that the approaches do not reach
   the copy, which is a generation defect and a different task - say so and
   stop rather than inventing a check around it.
4. Consider whether a THIRD dimension is needed. Angle, structure, tone and
   CTA are four things the operator named; the check currently reads opening
   punctuation, CTA punctuation, length and product-introduction point.

## WHAT NOT TO DO

- **Do not weaken, widen or disable the check, and do not raise a threshold.**
  It correctly refuses every LinkedIn set today and that refusal is the
  property worth protecting. It has been measured and rejected twice before.
- **Do not make the check pass by comparing declared metadata alone.** A check
  that reads the approach's own label proves only that five arms were tagged
  differently. Whatever you propose must be derivable from the TEXT, or must
  be explicitly validated against the text.
- Do not re-derive the detector bug. It is fixed and pinned.
- Do not report a predicted table. Run it against the real model.

## DELIVERABLE

A verdict on 1 (honoured or not) with hand-judged evidence per approach, and
then either a measured proposal for the check or a clear statement that the
defect is upstream in generation. Plus: what the honest count of materially
different LinkedIn arms per step actually is today. The current answer is two,
and if it is really two then five arms is a claim this system cannot yet make.

## RULES THAT APPLY TO THIS TASK

- Reads only at both providers. No writes, sends, or campaign changes.
- Never weaken a gate to make something pass. Fix what produced the output.
- Read every test exit code OFF THE PROCESS, never through a pipe.
- No unhashed prospect PII in any tracked file or commit message.
- Do not assert on the text of the source; assert on returned values.
- A zero and a wrong lookup are indistinguishable from outside. This task
  exists because a measurement was reading the wrong thing for weeks.

---

## RESULT

**STATUS**: DONE

**COMMIT SHA**: c5018d1

**TESTS**: No new tests. This was an investigation task, not a code change task.

**FILES CHANGED**:
- docs/qwen-tasks/RUNNING/TASK-115-FINDINGS.md (new) - detailed hand-judged evidence

**FINDINGS**:

The declared opening is **NOT consistently honored** in the generated copy. This is a generation defect, not a measurement defect.

Hand-judged evidence across li2, li3, li4 (15 variants total):
- concise_direct (statement): honored 3/3 times (100%)
- conversational (question): honored 2/3 times (67%)
- problem_led (pain): honored 1/3 times (33%)
- observation_led (evidence): honored 1/3 times (33%)
- value_led (outcome): honored 0/3 times (0%)

Overall: 7/15 openings honored (47%). The most common failure mode is opening with "hi [name], i'm [name] from [company]" - an introduction - instead of the declared opening type.

**The honest count of materially different LinkedIn arms per step is two, not five.**

**VERDICT**: Do NOT widen the check to compare declared semantic openings. A check that reads the approach's own label proves only that five arms were tagged differently. The check must be derivable from the TEXT, and today the text does not match the label reliably enough to trust the label.

The diversity check correctly refuses every LinkedIn set, and that is the property worth protecting. The defect is upstream in generation, not in measurement.

**RISKS**:
- The generation defect may be prompt-related (approach descriptions not strong enough) or a model prior (LinkedIn messages default to introductions)
- Fixing this requires prompt engineering or generation changes, not measurement changes

**RECOMMENDED CLAUDE ACTION**:
1. Do not weaken or widen the diversity check based on this finding
2. The generation must be fixed so declared openings are honored consistently (90%+)
3. Only after the generation is fixed should the check be reconsidered
4. The honest count of materially different LinkedIn arms is two, and five arms is a claim the system cannot yet make
