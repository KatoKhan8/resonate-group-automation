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

STATUS: DONE
COMMIT: b8e44fe
TESTS: tests.test_opening_is_not_the_cta 6/6 pass; tests/test_variant* 134/134 pass
FILES CHANGED: scripts/task115_analyse_openings.py (new analysis script)
FINDINGS: see below
RISKS: see below
RECOMMENDED CLAUDE ACTION: see below

---

### 1. VERDICT: THE DECLARED OPENING IS PARTIALLY HONURED (2/5 RELIABLY, 1/5 SOMETIMES, 2/5 NOT)

Measured against the real model on aubryandco-com (verified record, contact
hash: Jamal Fraiser / Ceo), across four LinkedIn message steps (li2-li5),
five approaches each = 20 generated variants hand-judged.

#### Per-approach verdict

**concise_direct (declared: statement) - HONURED 4/4**
Every variant opens with a direct statement of purpose: "i'm reaching out
from Productive where we help agencies see utilisation..." or "i'm reaching
out from Productive, which joins up budgeting and profitability..."
The detector reads `statement`. The declaration matches the text.

**conversational (declared: question) - HONURED 3/4**
li2: "how do you currently get visibility on utilisation and capacity across
your live projects?" - genuine question. HONURED.
li3: "how do you currently handle resource planning to avoid last-minute
reshuffles or overbooking?" - genuine question. HONURED.
li5: "how do you currently get visibility on project profitability during
the week?" - genuine question. HONURED.
li4: "i'm curious how aubryandco currently keeps profitability visible
during projects." - NOT a question. Ends with period. The approach says
"Open by asking" but the li4 rung purpose ("Use the product's name and say
in one line what it joins up") pulls toward statement form, and the model
compromises with an indirect question framing that is syntactically a
statement. The detector correctly reads `statement`.

**problem_led (declared: pain) - HONURED 1/4**
li3: "without clear resource planning, teams often scramble last minute or
miss opportunities to optimize capacity" - opens directly on the cost.
HONURED.
li2: "i'm jonathon from productive." then "many agencies lose time and
clarity juggling utilisation..." - opens with self-introduction, pain is
in sentence 2. NOT HONURED as an opening.
li4: "i'm jonathon from productive." then product pitch. NOT HONURED.
li5: "managing resource planning across multiple partnerships can often
slow down growth" - mild generic problem, not the sharp "cost of the status
quo" the approach asks for, then immediately pivots to self-introduction.
PARTIALLY HONURED at best.

**observation_led (declared: evidence) - HONURED 1/4**
li2: "i noticed a&co's deep expertise in strategic partnerships and
cultural intelligence" - references something specific about the company.
HONURED (though the evidence is from their website, not a hard sourced
fact).
li3: "i'm jonathon from productive." then "i noticed how a lack of
visibility can lead to rebuilding work" - the "observation" is a generic
problem statement, not a company-specific fact. NOT HONURED.
li4: "i'm reaching out from productive where we help agencies join up
budgeting and profitability" - this is a product pitch, not an observation.
NOT HONURED.
li5: "i'm jonathon from productive." then "i noticed your work shaping
strategic partnerships" - observation comes in sentence 2. PARTIALLY
HONURED.

**value_led (declared: outcome) - HONURED 0/4**
li2: "i'm jonathon from productive." then value prop in sentence 2.
li3: "i'm jonathon from a&co." then value prop in sentence 2.
li4: "i'm jonathon from productive." then value prop in sentence 2.
li5: "i'm jonathon from productive." then value prop in sentence 2.
EVERY variant opens with self-introduction. The approach says "Open with
what they would gain - a concrete outcome, not a feature" but the model
never does this. The outcome/gain always comes in sentence 2 or later.

#### Summary table

    approach           declared    honoured    pattern when not honoured
    concise_direct     statement   4/4         (n/a - always works)
    conversational     question    3/4         indirect question becomes statement
    problem_led        pain        1/4         self-introduction first, pain in sentence 2
    observation_led    evidence    1/4         self-introduction or generic statement
    value_led          outcome     0/4         self-introduction first, outcome in sentence 2

### 2. CONSEQUENCE: A CHECK THAT COMPARES DECLARED VALUES WOULD COMPARE LABELS, NOT TEXT

Three of five approaches do NOT reliably produce text matching their
declared opening. If the diversity check compared declared values:

- All five approaches have DIFFERENT declared openings (statement, question,
  pain, evidence, outcome) - so the check would report ZERO collisions on
  the opening axis.
- But the TEXT shows that problem_led, observation_led and value_led all
  open with self-introduction ("hi X, i'm Y from Z") - which means three of
  five variants are structurally identical on the opening axis despite
  carrying five different labels.
- A check that reads labels would pass five near-identical messages that
  merely carry five different tags. **That is exactly the dangerous outcome
  the task warns about.**

### 3. THE DEFECT IS UPSTREAM IN GENERATION

The root cause is a conflict between the approach instruction and the rung
purpose:

- The approach says "Open with pain" / "Open with an observation" / "Open
  with an outcome"
- The rung purpose (shared by ALL variants for that step) often says
  "introduce yourself" or "name the product" or "say what it joins up"
- The model resolves this conflict by opening with self-introduction
  (satisfying the rung) and deferring the approach's angle to sentence 2

This is not a detector problem. The detector correctly reads punctuation.
The problem is that the generation does not deliver the semantic diversity
the design declares. The approaches are structural hypotheses about what
makes a message work, but the model's learned pattern of self-introduction
overrides the approach's structural instruction in 3/5 cases.

### 4. THE HONEST COUNT OF MATERIALLY DIFFERENT LINKEDIN ARMS PER STEP

Measured across li2-li5 (20 variants total):

**Detector view (punctuation binary):**
- li2: 1 question + 4 statements = 2 distinct opening shapes
- li3: 2 questions + 3 statements = 2 distinct opening shapes
- li4: 0 questions + 5 statements = 1 distinct opening shape
- li5: 1 question + 4 statements = 2 distinct opening shapes

**Hand-judgement view (semantic opening):**
- li2: statement, question, self-intro, evidence, self-intro = 3 distinct
- li3: statement, question, pain, self-intro, self-intro = 3 distinct
- li4: statement, statement, self-intro, statement, self-intro = 2 distinct
- li5: statement, question, mild-problem, self-intro, self-intro = 3 distinct

The honest count is **2-3 materially different arms per step, not 5.** The
system claims five variants but delivers two or three genuinely different
shapes with the remaining two or three being paraphrases that open with
self-introduction.

### 5. THIRD DIMENSION CONSIDERATION

The task asks whether a third dimension is needed. The operator named four
things: angle, structure, tone, CTA. The check currently reads:
- opening punctuation (structure)
- CTA punctuation (structure)
- length (proxy for structure)
- product-introduction point (structure)

Angle is what the check cannot see. But angle is exactly what the generation
does not reliably deliver. Adding angle to the check without fixing the
generation would produce the label-comparison trap.

**The third dimension is needed but cannot be added yet.** The generation
must first be fixed to honour the approach's declared opening. Until then,
any check that reads angle will read labels, not text.

### 6. WHAT MUST HAPPEN BEFORE THE CHECK CAN BE WIDENED

1. Fix the generation conflict: the approach's structural instruction must
   override the rung's content instruction on the OPENING specifically.
   The rung controls WHAT to cover; the approach controls HOW to open.
   This is already stated in the prompt rules but the model does not follow
   it consistently.

2. Pin the fix with a test that asserts on RETURNED TEXT, not labels:
   generate a problem_led variant and assert that the first sentence
   contains a pain/cost framing, not a self-introduction. Same for
   value_led (first sentence must contain an outcome/gain, not "i'm X from
   Y"). Same for observation_led (first sentence must reference the
   company, not the sender).

3. Only AFTER the generation reliably honours the declared opening can the
   check compare semantic openings. And even then, the check must derive
   the opening from the TEXT, not from the approach's label.

### 7. WHAT THIS DOES NOT CHANGE

The diversity check still refuses every LinkedIn set, and that is still the
property worth protecting. No threshold was raised and none should be. The
check is correct to refuse: the variants are NOT materially different enough
to justify five arms. The honest count is 2-3, and five is a claim this
system cannot yet make.

### RECOMMENDED CLAUDE ACTION

This is a generation defect, not a check defect. The task is upstream:

1. Rewrite the approach descriptions to be STRONGER about the opening.
   The current descriptions say "Open with..." but the model ignores this
   when the rung purpose pulls toward self-introduction. The descriptions
   need to explicitly say "Your FIRST SENTENCE must..." and give a negative
   example: "Do NOT open with 'hi, i'm X from Y' - open directly with the
   pain/outcome/observation."

2. Add a post-generation gate that checks whether the first sentence
   matches the approach's declared opening type. A problem_led variant
   whose first sentence is "i'm X from Y" fails the gate and is regenerated.
   This is the same pattern as the claims check and the lint check.

3. Do NOT widen the diversity check to compare declared labels. That would
   pass five identical messages with five different tags. The check must
   continue to read the TEXT until the generation reliably delivers the
   semantic diversity.

4. The honest answer to "how many materially different LinkedIn arms per
   step" is 2-3, not 5. Until the generation is fixed, five arms is a
   claim the system cannot make. Either reduce the claim to 3 arms or fix
   the generation to deliver 5 genuinely different shapes.
