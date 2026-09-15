PRIORITY: P1
DEPENDS:

# TASK-143 - 34% of research rows are page furniture, and one measurement says it does not matter

## THE TWO FACTS THAT HAVE TO BE HELD TOGETHER

    navigation / junk rows            237 of 695   (34%)
    records whose FIRST THREE are junk  47 of 203

`research.for_prompt` takes `[:3]` in stored order with no quality ordering, so
those 47 records show the model menu fragments where facts should be.

And:

    TASK-135's quality-filtering change is INTEGRATED and it moved NO
    claims-gate outcome. 26 drafts, 13 records, zero unsupported-claim
    rejections in either arm.

Both are true. The obvious reading - "the junk does not matter" - is one
hypothesis and the sample was 13 records. The other reading is that the claims
gate is not the place where junk evidence does its damage, and nobody has
looked at the place where it would.

**Do not re-investigate whether the model can SEE the evidence.** It can;
`generate.py:490` passes `public_evidence` from `research.for_prompt(rec)` with
`field`, `source_url`, `retrieved_at` and `fact`. `docs/CRAWLER-AUDIT-2026-09-15.md`
Part 1 is wrong about this and Part 3 corrects it. Settled.

## THE QUESTION

Where does junk evidence actually surface, and is it worth more filtering?

Three candidate answers, and the task is to find which is true:

1. **Nowhere.** The model ignores unusable evidence and writes from the
   structured company data instead. Then the junk is cosmetic and the finding
   is "stop worrying about it", which is a real result worth writing down.
2. **In the copy, silently.** The draft is grammatical, passes lint, passes
   claims, and says something bland because the evidence gave it nothing. The
   cost is a weak message rather than a rejected one - which is invisible to
   every gate and visible to a human read, and three human reads have already
   said the generated copy loses to the fallbacks.
3. **In the rejection rate.** Drafts fail repetition or lint more often on
   junk-fed records. 377 of ~440 recorded rejections are repetition, so this
   is checkable.

## HOW TO TELL THEM APART

Against `work/queue.snapshot.jsonl`. **Quote the STAMP.**

Split the 203 records with evidence into JUNK-FED (first three rows are
navigation) and FACT-FED. Then compare, on the copy that already exists in the
estate, with no generation required:

    rejection reasons by class          (repetition, lint, claims, none)
    how often the draft names a fact from the evidence at all
    how often the draft falls back to generic product language
    length, and the vocabulary shared with every other draft

**A comparison of 47 against 156 is not a coin flip - say what the difference
would have to be to be worth acting on BEFORE you compute it**, and hold to
that. This repository has a standing rule against optimising to noisy tiny
samples, and the honest outcome "the difference is inside the noise" is a
result.

## IF THE ANSWER IS (2)

Then the useful deliverable is not a filter - it is the measurement that
tells a generation task what "good evidence" means. Say what a fact would have
to look like to be worth putting in front of the model, with examples from the
real rows, both kinds.

## WHAT YOU MAY NOT DO

- Do not run `py -3 -m src.generate --live`. Generation against the real queue
  is Claude's, from Claude's worktree; a run here writes to an isolated queue
  that never reaches production. If your finding needs generation, say so
  under FINDINGS and Claude runs it.
- No provider calls. No writes to `work/`.
- Do not widen or weaken any gate.

## FILES ALLOWED

    docs/RESEARCH-QUALITY-IMPACT-2026-09-15.md   (new)
    scripts/task143_*.py
    the task file itself

## FILES FORBIDDEN

    src/       work/       config/

## DELIVERABLE

The pre-stated threshold, the two-group comparison, the verdict among the
three candidates with the numbers behind it, and - if the answer is (2) - what
good evidence looks like, in examples.
