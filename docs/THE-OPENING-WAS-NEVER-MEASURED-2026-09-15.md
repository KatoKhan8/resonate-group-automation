# The opening was never measured, and the real cap is the vocabulary

TASK-089, integrated 2026-09-15. Every number below was measured against the
real model on a real record, not predicted.

---

## 1. THE FINDING THAT REFRAMES TASK-087

`_opening_shape` took the first **line** of a message and asked whether it
ended with a question mark. A LinkedIn message is **one paragraph**, so its
first line is the entire message, and its last character is the *closing*
punctuation.

    OLD opening == CTA on every single-paragraph message.  PROVEN.

So the two structural dimensions of the diversity check were **one dimension
read twice**. The opening was never measured at all.

That is why TASK-087 reported every LinkedIn arm as `opening=question
cta=question` and concluded the arms had collapsed into one shape. They had
not been measured. A diversity check whose two axes are secretly the same axis
can only ever see half the structure, and two genuinely different arms - one
opening on a statement, one on a question - are invisible to it as long as
both happen to close the same way.

`tests/test_opening_is_not_the_cta.py` pins this. It asserts on returned
values rather than on source text, and it was confirmed **non-inert**: restore
the old implementation and 4 of its 6 tests fail.

## 2. WHAT IS NOW TRUE, MEASURED

Five variants generate on every LinkedIn step, `observation_led` included:

    step   arms   openings              CTAs
    li2      5    1 question, 4 statement   3 question, 2 statement
    li3      5    1 question, 4 statement   3 question, 2 statement
    li4      5    0 question, 5 statement   2 question, 3 statement

    diversity_collisions: TRUE on all three steps - still refused

**Two things improved and one did not.** Five arms now generate where LinkedIn
once produced zero, and the CTA axis genuinely varies. The opening axis is
still almost entirely collapsed, and on li4 it is completely collapsed.

## 3. THE ROOT CAUSE, AND IT IS NOT THE PROMPT

`APPROACHES` declares five openings:

    concise_direct     statement
    conversational     question
    problem_led        pain
    observation_led    evidence
    value_led          outcome

**Four of those five are semantically statements.** "Pain", "evidence" and
"outcome" are different *angles*, and they are genuinely different - opening
on the cost of the status quo is not the same message as opening on a
concrete gain. But `_opening_shape` can only see punctuation, so it returns
`statement` for all three and reports them as identical.

**The measurement vocabulary is coarser than the design vocabulary.** The
approaches differ in ways the check cannot see, and exactly one approach
(`conversational`) asks for the only other shape the check can recognise. So
structural diversity on the opening axis is capped at two values with a
four-to-one split, and no amount of prompt work will move it.

This is not an argument for weakening the check. It is an argument that the
check is asking a binary question about a five-valued design.

## 4. WHAT WAS AND WAS NOT DONE

Taken from `qwen-worker-r7` as named files:

    src/variantgen.py                      the detector fix, and approach
                                           descriptions rewritten from FORM
                                           instructions to CONTENT jobs
    scripts/task089_diagnose_linkedin.py   the measurement harness
    tests/test_opening_is_not_the_cta.py   written by Claude, non-inert

**A correction I made and then reversed.** I first reverted the worker's
change to `conversational` - which sets `"opening": "question"` and tells the
model to open by asking - on the grounds that TASK-087 forbade putting form
instructions back. That was wrong, and re-measuring showed it: with the change
reverted, **all fifteen arms opened with a statement.**

TASK-087's rule is "the approach controls STRUCTURE; the rung controls
CONTENT." The prohibition was on form instructions in the *rung*, which is
shared by every arm and therefore forces them all into one shape. An approach
is per-arm, and structure is precisely its job. Restored.

## 5. WHAT THE WORKER CLAIMED, AND WHAT IS ACTUALLY TRUE

The result block said LinkedIn "now differentiates on structure" with "3
different opening/CTA combinations" and called it "a massive improvement".

Re-run against the model, the openings are 4:1 statement on two steps and 5:0
on the third, and `diversity_collisions` is TRUE everywhere. The honest status
is **partial**: the detector bug is fixed and five arms generate, but the
opening axis is still collapsed and the check still correctly refuses the
sets.

The worker also measured with its own change in place and reported the varied
openings that produced - which was fair - but it did not notice that most of
the apparent improvement came from fixing the detector rather than from
changing the copy. Those are different achievements and only one of them is
about the copy.

## 6. WHAT THIS DOES NOT CHANGE

The diversity check still refuses every LinkedIn set, and that is still the
property worth protecting. **No threshold was raised and none should be.**
TASK-115 carries the real question: whether the check should compare the
approach's declared *semantic* opening - pain vs outcome vs evidence vs
question - instead of, or alongside, the punctuation binary it reads today.

Until then, the operator requirement of five genuinely different variants is
**met on generation and not met on structure**, and the honest count of
materially different LinkedIn arms per step is two, not five.
