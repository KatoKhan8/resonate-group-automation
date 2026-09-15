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

## RESULT BLOCK

STATUS: DONE
COMMIT: 7fe4460
TESTS: tests.test_opening_is_not_the_cta - 6/6 pass (exit code read off process)
FILES CHANGED: scripts/task115_judge_openings.py (new diagnostic)
FINDINGS: See below.

---

## 1. VERDICT: THE DECLARED OPENING IS PARTIALLY HONURED, AND THAT IS NOT ENOUGH

Measured against the real model on record `aubryandco-com` (hash of company
domain), sequence `productive_li_heavy_v1`, five LinkedIn steps (li2-li6).
Diagnostic script: `scripts/task115_judge_openings.py`.

### Hand-judged table per approach per step

Each cell: does the FIRST SENTENCE of the generated text match the declared
opening type?

```
approach          declared   li2   li3   li4   li5   li6   hit rate
─────────────────────────────────────────────────────────────────────
concise_direct    statement  YES   YES   YES   YES   YES   5/5
conversational    question   YES   YES   NO*   YES   YES   4/5
problem_led       pain       YES   YES   NO    NO    NO    2/5
observation_led   evidence   YES   NO    NO    NO    YES   2/5
value_led         outcome    NO    NO    NO    NO    NO    0/5
```

*li4 conversational opened with a statement instead of a question.

### Per-approach detail

**concise_direct (statement) - 5/5 HONURED.**
Every arm opens with "i'm reaching out from Productive where..." or similar.
Plain statement, every time. The description says "Open with the reason for
writing in one sentence - no preamble" and the model follows it.

**conversational (question) - 4/5 HONURED.**
Four of five arms open with "how do you currently..." The li4 arm opened with
a statement instead. The description says "Open by asking about their current
approach" and the model mostly follows it.

**problem_led (pain) - 2/5 PARTIALLY HONURED.**
li2: "managing utilisation and capacity across live projects can often be a
hidden challenge that costs agencies time and clarity." - This IS pain. It
names the cost of the status quo.
li3: "without clear visibility on resource planning, teams often scramble to
adjust workloads last minute, causing delays and stress." - This IS pain.
li4, li5, li6: Open with "i'm jonathon from productive." - Self-introduction,
not pain. The model ignored the approach's structural instruction.

**observation_led (evidence) - 2/5 PARTIALLY HONURED.**
li2: "i noticed your work shaping strategic partnerships and cultural
intelligence at a&co." - This IS evidence. A specific observed fact.
li6: "i noticed jonathon aubry's unique approach to cultural partnerships and
revenue growth at a&co." - Structurally evidence, but the observation appears
invented (the contact is Jamal Fraiser, not "jonathon aubry"). This is a
separate defect: the observation-led variant is fabricating observations.
li3, li4, li5: Open with self-introduction or generic statement, not a
specific observed fact.

**value_led (outcome) - 0/5 NOT HONURED.**
Every single arm opens with "i'm jonathon from productive" or "i'm reaching
out from productive." Not one arm opens with a concrete outcome or gain.
The description says "Open with what they would gain - a concrete outcome,
not a feature" and the model ignores it completely, every time.

### What the model actually does

When the approach description is short and the structural instruction is
clear (concise_direct: "open with the reason"; conversational: "open by
asking"), the model follows. When the structural instruction competes with
the model's learned habit of opening LinkedIn messages with a
self-introduction, the model defaults to self-introduction. This happens
roughly half the time for problem_led, observation_led, and value_led.

## 2. SHOULD THE CHECK COMPARE DECLARED SEMANTIC OPENINGS?

**Not yet.** Two reasons:

**Reason 1: Comparing declared values would compare labels, not copy.**
The task file names this as "the single most dangerous outcome available in
this task." value_led declares "outcome" but opens with self-introduction
every single time. A check that reads the declared value would call this
"outcome" and treat it as different from "statement" - but the TEXT is a
statement. Five arms carrying five different tags but opening with the same
self-introduction would pass a check that compared declared values. That is
exactly the failure mode the task warns against.

**Reason 2: Even when the semantic opening IS honoured, the text is still a
statement to any punctuation-based detector.** problem_led on li2 genuinely
opens on pain. But the first sentence ends with a period. A semantic
classifier would need to distinguish "pain statement" from "outcome statement"
from "evidence statement" from "generic statement" - and the generation does
not reliably produce the first three of those four.

## 3. THE DEFECT IS UPSTREAM IN GENERATION

The approaches declare five opening types. The model reliably produces two:
statement and question. The other three (pain, evidence, outcome) are
produced roughly 40% of the time (8 out of 15 non-conversational,
non-concise_direct arms across the five steps). The other 60% of the time,
the model opens with self-introduction regardless of what the approach
declared.

This is a generation defect. The approach descriptions are clear about what
the opening should be, but the model's learned prior for LinkedIn messages
("start by introducing yourself") overrides the instruction roughly half the
time. Fixing this requires either:
- Stronger prompt engineering (e.g., explicit negative instruction: "Do NOT
  open with a self-introduction. Open with [the specific angle].")
- A post-generation gate that checks whether the first sentence matches the
  declared opening type and regenerates if it does not.
- A different model that follows structural instructions more reliably.

None of these are check changes. The check is doing its job correctly by
refusing sets where four of five arms are structurally identical.

## 4. THE HONEST COUNT OF MATERIALLY DIFFERENT LINKEDIN ARMS PER STEP

By structural shape (opening × CTA), measured across five steps:

```
step   arms   distinct opening×cta combos   materially different?
li2      5    3 (statement×question,         NO - 4 arms share
                 question×statement,          statement opening
                 statement×statement)
li3      5    3 (same pattern)               NO
li4      5    2 (statement×question,         NO - all 5 share
                 statement×statement)         statement opening
li5      5    3 (same as li2)                NO
li6      5    4 (best spread)                NO - still 4/5 statement
```

By semantic content (including angle when honoured in the first sentence):

```
step   statement-only   question   pain    evidence   outcome
li2    2 (cd, ol)       1 (cv)     1 (pl)  -          -
li3    2 (cd, ol)       1 (cv)     1 (pl)  -          -
li4    4 (cd, cv, ol, vl)  -       -       -          -
li5    3 (cd, pl, vl)   1 (cv)     -       -          -
li6    2 (cd, vl)       1 (cv)     1 (pl)  1 (ol)     -
```

The honest count is **two to three materially different arms per step**, not
five. Two of those are reliable (concise_direct and conversational). The
other three approaches produce a genuinely different opening roughly 40% of
the time.

**Five arms is a claim this system cannot yet make.** The generation produces
five labelled variants, but only two to three of them are structurally or
semantically different in their opening. The diversity check correctly
refuses these sets, and that refusal is the property worth protecting.

## 5. WHAT ABOUT A THIRD DIMENSION?

The operator named four things: angle, structure, tone, CTA. The check
currently reads opening punctuation, CTA punctuation, length, and
product-introduction point.

Adding "angle" as a dimension is exactly what this task investigated. The
finding is that angle is not reliably present in the text, so a check that
measures angle would be measuring labels, not copy. Until the generation
reliably produces different angles, the check cannot measure them.

A third dimension is not needed today. What is needed is for the generation
to reliably deliver on the angles the approaches declare. Once it does, the
check can be extended to measure them - but the measurement must be derived
from the TEXT, not from the approach's declared metadata.

## 6. RECOMMENDED CLAUDE ACTION

1. **Do not change the diversity check.** It is correct to refuse these sets.
2. **File a generation task** to make the model reliably follow the approach's
   structural instruction. The specific defect: value_led never opens with an
   outcome (0/5), problem_led opens with pain 2/5, observation_led opens with
   evidence 2/5. The model defaults to self-introduction when the approach
   description does not override its learned prior strongly enough.
3. **Investigate the observation_led fabrication.** On li6, the "licensed
   observation" was replaced with an invented one about "jonathon aubry" who
   is not the contact. This is a separate and more serious defect.
4. **The honest answer to the task's question**: the check should compare
   semantic openings, but it cannot do so yet because the generation does not
   reliably produce them. The defect is upstream. Fix generation first, then
   extend the check.
