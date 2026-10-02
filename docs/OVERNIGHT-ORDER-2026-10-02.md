# The overnight order, 2026-10-02 night → morning

Operator's own words, recorded first so that a context reset or an account limit
cannot lose it. **Serial. One suite on the machine. Until morning.**

## A. The merge queue as it stands

OS authority (new run + multi-part GLM) → lint contract (with 943) → 942 rework
→ guard → 936 → the five on older bases.

Each against **the reference on the CURRENT master**, each through **GLM**, and
**NEEDS_CLAUDE and UNKNOWN do not pass.**

## B. Copy — a new branch `task-copy-exemplars`, AFTER A because it touches `src/lint`

1. `prompts/exemplars/em1-operator.md`: **16 operator em1s from 02-10**,
   anonymized (recipient names, domains and companies replaced), with the
   five-block anatomy: **who I am + a fact about them / an offer that GIVES, with
   a concrete deliverable and a list of personas / proof with a name and a
   number / ONE CTA / signature.**
2. `prompts/exemplars/cadence-operator.md`: the **Volteum** cadence, five steps,
   days **0 / 3 / 7 / 12 / 18**, with the role per step: offer / smaller
   tangible piece / proof with a named client and a number / easy-answer
   question with an explicit exit / breakup in a new thread keeping the offer
   and closing with the em1 fact.
3. `step_objectives` becomes a ladder of ROLES, not of words. Lint refuses: two
   steps of the same role; an ask that does not descend (the CTA of step n
   larger than n−1); a bump with no reference to the thread; the same proof in
   two steps; **more than one question per email**; an em1 that describes the
   prospect's company to the recipient.
4. Contract: **em1 90–140 target 120, em2–em5 45–90, em4 target 50, em5 a new
   thread.** Cadence **3/4/5/6 days** as config.
5. Entry gates: **em1 with no research row → HELD `research_required`; em3
   without TWO licensed proof rows → HELD `proof_required`. Invent neither.**
6. The writer sees both exemplars in `WRITER_SYSTEM` as STRUCTURE, with an
   explicit prohibition on copying content.

Tests with mutations for every rule. GLM before the merge.

## C. The stop proof by effect — a branch off master, in the queue after B

A negative reply on EMAIL for a record active on both channels must, within
fifteen minutes, call `bison.stop_lead` AND `heyreach.stop_lead` for that lead,
with a mock transport that records the calls. **Unknown calls nothing but
raises a notification.** The same in the other direction from LinkedIn. A
mutation removing one provider's call must fail the test. **If the path does not
exist for a channel, that is P0 ahead of phase 0.**

> Measured already, 2026-10-02: the path DOES exist for both channels —
> `inbound._stop_at_provider` iterates email and linkedin — so it is not P0 on
> that ground. And the "unknown calls nothing" clause contradicts a deliberate
> design (the stop is attempted BEFORE classification because it can only mean
> somebody receives less); TASK-965 carries that with its consequence stated.

## D. When the send path is joined

**Phase 0 on savagebrands with five GENERATED emails under the new rules**,
copy-review on. **If em1 or em3 is HELD for want of an offer or a proof, record
that as EXPECTED and generate the rest — it is a finding for the client, not a
defect.** Then phase 1.

## E. Slack

Copy-review files and generated emails go to **`#resonate-os-output`** under the
standing permission. **Engineering: nothing to Slack.**

## Constraints, unchanged

No provider write. Qwen does not run. **Nobody touches the reference checkout.**
Kill by PID after reading that process's cwd. **The handoff is updated before
stopping — and if the account limit falls, the handoff comes FIRST.**

## What the morning handover must contain

Master SHA · the merges with their GLM verdicts · the phase 0/1 result with
paths · before/after copy for bigfish and savagebrands · open defects ·
decisions for the operator · and the queue's Qwen/GLM numbers.
