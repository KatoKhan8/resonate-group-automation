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

## RESULT

STATUS: DONE
COMMIT SHA: ed8112c
TESTS: tests.test_opening_is_not_the_cta (6/6 pass), tests.test_variantgen (47/47 pass)
FILES CHANGED: scripts/task115_measure_openings.py (measurement harness)
FINDINGS: See below
RISKS: The generation prompt does not reliably enforce the declared opening
RECOMMENDED CLAUDE ACTION: Fix the generation prompt to make the opening instruction impossible to ignore; do NOT weaken the diversity check

---

### VERDICT: The declared openings are NOT reliably honoured

Measured against the real model on aubryandco.com (aubryandco-com), contact Jamal Fraiser, sequence productive_li_heavy_v1, steps li2/li3/li4. Snapshot stamp: 2026-09-14T21:52:15Z from master 0ac5e60.

#### Hand-judged evidence per approach (from the FULL DIVERSITY CHECK texts)

**li2:**

| Approach | Declared | Actual opening | Honoured? |
|----------|----------|----------------|-----------|
| concise_direct | statement | "i'm reaching out from productive where we help agencies see utilisation and capacity across live projects in one place." | ✓ statement of purpose |
| conversational | question | "how do you currently get visibility on utilisation and capacity across your live projects?" | ✓ question |
| problem_led | pain | "i'm jonathon from a&co." | ✗ self-introduction |
| observation_led | evidence | "i noticed your work shaping strategic partnerships and cultural intelligence at a&co." | ✓ specific observation |
| value_led | outcome | "i'm jonathon from productive. we help agencies get clear visibility..." | ✗ self-intro + product pitch |

**li3:**

| Approach | Declared | Actual opening | Honoured? |
|----------|----------|----------------|-----------|
| concise_direct | statement | "i'm reaching out from Productive where we help agencies avoid rebuilding work after the fact..." | ✓ statement |
| conversational | question | "how do you currently handle resource planning across your projects?" | ✓ question |
| problem_led | pain | "without clear visibility on resource planning, teams often scramble to adjust workloads last minute, causing delays and stress." | ✓ pain |
| observation_led | evidence | "i'm jonathon from productive. i noticed how a lack of visibility can lead to rebuilding work..." | ✗ self-intro; "observation" is generic, not about the company |
| value_led | outcome | "this is a quick note from someone working on agency project visibility." | ✗ vague self-introduction |

**li4:**

| Approach | Declared | Actual opening | Honoured? |
|----------|----------|----------------|-----------|
| concise_direct | statement | "i'm reaching out from Productive, which joins up budgeting and profitability..." | ✓ statement |
| conversational | question | "i'm reaching out from productive where we bring budgets, time tracking, and resourcing together..." | ✗ statement, not question |
| problem_led | pain | "i'm jonathon from productive. we help agencies join up budgeting..." | ✗ self-introduction |
| observation_led | evidence | "i'm reaching out from productive where we help agencies join up budgeting..." | ✗ product pitch |
| value_led | outcome | "i'm reaching out from productive, where budgets, time tracking, and resourcing all connect..." | ✗ product pitch |

#### Summary

| Approach | Declared | li2 | li3 | li4 | Honoured |
|----------|----------|-----|-----|-----|----------|
| concise_direct | statement | ✓ | ✓ | ✓ | 3/3 |
| conversational | question | ✓ | ✓ | ✗ | 2/3 |
| problem_led | pain | ✗ | ✓ | ✗ | 1/3 |
| observation_led | evidence | ✓ | ✗ | ✗ | 1/3 |
| value_led | outcome | ✗ | ✗ | ✗ | 0/3 |

**Total: 7/15 honoured.** The model defaults to self-introduction ("hi X, i'm Y from Z") regardless of the approach's declared opening.

### The honest count of materially different LinkedIn arms

The diversity check sees two values on the opening axis: `statement` and `question`. The semantic angles (pain, evidence, outcome) are declared in the prompt but do not reliably reach the copy. When they do reach the copy (problem_led at li3, observation_led at li2), the check still cannot see them because it only reads punctuation.

**The honest count is two.** One arm opens with a statement, one opens with a question. Five arms is a claim this system cannot yet make because three of the five approaches do not reliably produce their declared opening in the text.

### The finding: the defect is UPSTREAM in generation

The approaches declare five semantic openings but the model defaults to self-introduction for three of them (problem_led, observation_led, value_led) most of the time. Adding a check that compares declared values would compare LABELS rather than copy - exactly the dangerous outcome the task warns about.

The check correctly refuses every LinkedIn set today because the opening axis is collapsed to two values. That refusal is the property worth protecting. The fix is not in the check; it is in the generation prompt, which needs to make the opening instruction impossible to ignore.

### What the check should NOT do

- Should NOT compare declared opening values (pain, evidence, outcome) because they do not match the text
- Should NOT be weakened to make the sets pass
- Should NOT add a semantic dimension until the generation reliably produces it

### What needs to happen next (separate task)

The generation prompt needs to enforce the opening instruction. The approach description says "Open with the cost of the status quo" but the model ignores it and opens with "i'm jonathon from a&co." The prompt needs to make the opening instruction structurally impossible to ignore - for example, by requiring the first sentence to match a pattern, or by rejecting variants that open with a self-introduction when the approach declares a different opening.
