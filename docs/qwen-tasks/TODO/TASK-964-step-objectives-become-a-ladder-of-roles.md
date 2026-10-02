# TASK-964 — `step_objectives` becomes a ladder of ROLES, not of words

Operator's design, 2026-10-02 night, after reading bigfish's five emails
(*"prolazi gateove, ne bih ga poslao"* — the measured reasons are in
`resonate-ops/copy-review/FINDING-bigfish-2026-10-02.md`).

**THREE LADDERS WERE NAMED TONIGHT AND THIS IS THE ONE THAT STANDS.** The
operator first said visibility / budget / resourcing / proof / breakup, then
replaced it with the roles below. The offer record carries a third
(`step_objectives` in `config/clients/productive-offers.yaml`: for Offer B
*project visibility, time, resourcing, AI Time Tracking as mechanism, one
operational view*) and `sequencegate` already reads it. **Part of this task is
making the offer record carry the ROLE ladder, so there is one authority and not
three** — the role ladder is about what a step DOES, the offer's words are about
what it is ABOUT, and a step needs both, but only one of them may be the thing
the gate enforces as the ladder.

## The ladder

| step | role |
|---|---|
| em1 | the OFFER |
| em2 | a smaller tangible piece of the SAME offer |
| em3 | PROOF — a named client and a number |
| em4 | an easy-answer question with an EXPLICIT EXIT |
| em5 | BREAKUP in a NEW THREAD, keeping the offer, closing with the em1 fact |

## What lint must refuse

1. **Two steps sharing a role.** Measured on bigfish against the operator's
   earlier ladder: one rung appeared in four of five steps. The refusal names
   both steps and the role.
2. **An ask that does not descend.** The CTA in step *n* may not be bigger than
   in step *n−1*. This needs an ORDERING over asks, and the ordering is the hard
   part of this task — "reply with a yes" is smaller than "book 30 minutes", but
   nothing in the repository ranks them today. Define the order explicitly as
   config, smallest to largest, and refuse a step whose ask outranks its
   predecessor. **If the ask cannot be identified in a body, that is UNKNOWN and
   it REFUSES** — a step whose ask cannot be read is not a step with a small ask.
3. **A bump that does not reference the thread.** Measured on bigfish: not one
   of em2–em5 carries a back-reference. em5 is the exception by design — it is a
   NEW thread — so the rule is "a same-thread step references the thread, and
   em5 must NOT".
4. **The same proof in two steps.** Proofs rotate; a sequence that leans on one
   client twice is refused.

## The contract

| step | words | target | thread |
|---|---|---|---|
| em1 | 90–140 | 120 | new |
| em2 | 45–90 | — | same |
| em3 | 45–90 | — | same |
| em4 | 45–90 | 50 | same |
| em5 | 45–90 | — | **new thread** |

Default cadence gaps **3 / 4 / 5 / 6 days** (days 0, 3, 7, 12, 18), as cadence
config rather than as constants.

**TWO MEASUREMENTS THAT CONTRADICT THIS CONTRACT AND MUST BE RESOLVED WITH THE
OPERATOR, NOT SILENTLY:**

- **Their own em1s are twice the contract.** The five internal Resonate
  campaigns each carry exactly one order-1 step with a body, read tonight
  through `bison.sequence_steps`: **261, 281, 279, 246 and 72 words**. Four of
  the five are 2× the 90–140 band the same operator just set, and the fifth is
  below it. If those are the exemplars of structure, the contract and the
  exemplars disagree by a factor of two.
- **The existing word authority is 60–90 for em1–em3** (writer contract,
  operator, 2026-10-02, TASK-943). This order makes em1 90–140. One of the two
  has to be retired in the contract itself, or A21 — two authorities for one
  number — comes back on a different line.

## Evidence: proofs rotate, so one row is not enough

**At least TWO licensed proof rows per client before a sequence may pass em3**,
because em3's role is a named client and a number and rule 4 forbids reusing one
across steps.

**Until Productive supplies names and numbers, em3 is HELD — never invented.**
Today bigfish's artefact carries **0 research rows**, so there is nothing to
cite at all. The licence class to use already exists and must be reused rather
than invented: the 2026-09-27 decision admits `CLIENT_SUPPLIED` for
qualification and strategy but NOT for a prospect-facing claim, while
`CLIENT_APPROVED` is the class that has already licensed one mechanism for copy.
A social-proof row enters the admitted pack as `CLIENT_APPROVED` with the source
file AND the row recorded.

## THE QUESTION FOR THE CLIENT, which blocks em1's second block

**Which Productive offer GIVES before it ASKS — the equivalent of "a free map of
100 accounts"?** Without it em1 has no block 2 and the ladder's first rung is an
assertion rather than an offer. This is a client question, it is not answerable
from the repository, and it is recorded here so it is asked rather than guessed.

## Acceptance

```
python -c "import json,sys; sys.path.insert(0,'.'); from src import sequencegate as g; steps=json.load(open('tests/fixtures/bigfish-converged-copy.json',encoding='utf-8'))['steps']; v=g.role_ladder(steps); assert v['refused'], 'bigfish was not refused by the role ladder'; print('OK refused:', v['why'][:160])"
```

```
python -c "import sys; sys.path.insert(0,'.'); from src import copylint as c; order=c.ask_order(); assert len(order)>=3, order; big=c.ask_rank('Can we book 30 minutes on Thursday?'); small=c.ask_rank('Worth a look?'); assert big is not None and small is not None, (big, small); assert big > small, (big, small); assert c.ask_rank('No question at all here.') is None, 'a body with no ask must read UNKNOWN, not smallest'; print('OK the asks are ordered and an unreadable ask is UNKNOWN')"
```

```
python -c "import sys; sys.path.insert(0,'.'); from src import copylint as c; assert c.describes_their_own_company('Hi Rowan, big fish is a UK-based digital marketing agency.','big fish'), 'the defect sentence was not refused'; assert not c.describes_their_own_company('Teams like yours at big fish run four studios on one plan.','big fish'), 'legitimate personalisation was refused - this is the control'; print('OK one refused, one allowed')"
```

```
python -c "import sys; sys.path.insert(0,'.'); from src import copylint as c; body='Did any of that land? If not, I will close the loop. Worth a look?'; assert c.question_count(body)>1; assert c.refuses_multiple_questions(body), 'two questions passed'; one='Following up on my note - worth a look?'; assert not c.refuses_multiple_questions(one), 'a single CTA question was refused'; print('OK at most one question, and it is the CTA')"
```

### NEGATIVE CONTROL

Every command fails today with `AttributeError`: `role_ladder`, `ask_order`,
`ask_rank`, `describes_their_own_company`, `question_count` and
`refuses_multiple_questions` do not exist. Each one carries its opposite case in
the same line, so **a rule that refuses everything fails these commands too** —
command 2's UNKNOWN case, command 3's `good` sentence and command 4's single-CTA
string are those controls.

`tests/fixtures/bigfish-converged-copy.json` must be committed from the
artefact: it is the "before" half of the operator's before/after, and command 1
is the proof that today's copy does not pass tomorrow's gate.

## Files

`src/sequencegate.py`, `src/copylint.py`, the offer record and the cadence
config, the fixture, and tests.

## Deliverable beyond the code

**Regenerate bigfish AND savagebrands, all five steps, under these rules, and
put before/after for both into `resonate-ops/copy-review/`.** Expect em3 to come
back HELD on both until Productive supplies two proof rows — that is the correct
outcome, and the report says so rather than filling the gap.

## Not in scope

The stop proof (TASK-965). The exemplar files (TASK-966, blocked on content).
