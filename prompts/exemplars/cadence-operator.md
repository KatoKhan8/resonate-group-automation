# The operator's own five-step cadence

**THIS IS STRUCTURE. DO NOT COPY THE CONTENT.** Nothing below is a sentence to
reuse. It is the shape of a sequence the operator ran himself: how many steps,
how far apart, and what job each step does. Every word of generated copy still
comes from the record's own evidence through `claims.check`, and this file
licenses nothing.

The sequence it is taken from was sent by the operator, by hand, to one real
company. The company is not named here and neither is the person: the same
anonymisation rule as `em1-operator.md`, for the same reason - a file in git is
published.

## Five steps, and the days

| step | day | gap from the previous | role | thread |
|---|---|---|---|---|
| em1 | 0 | - | the OFFER | opens thread A |
| em2 | 3 | +3 | a smaller tangible piece of the SAME offer | reply inside thread A |
| em3 | 7 | +4 | PROOF - a named client and a number | opens thread B |
| em4 | 12 | +5 | an easy-answer question with an EXPLICIT EXIT | reply inside thread B |
| em5 | 18 | +6 | BREAKUP, keeping the offer | a NEW thread |

Five steps and no more. Eighteen days end to end. The gaps WIDEN as the
sequence runs - 3, 4, 5, 6 - so the sequence gets quieter rather than more
insistent, and the last step is the furthest from the one before it.

## The roles are the ladder, and the ladder is enforced

The role column is `sequencegate.ROLE_LADDER`, which is the authority:

    ("offer", "smaller_piece", "proof", "easy_question", "breakup")

`sequencegate.role_ladder()` applies all five of its refusals - two steps
sharing a rung, an ask that does not descend, a bump with no thread reference,
the same proof in two steps, and a rung that cannot be read at all. So this
table is not advice. A sequence whose em3 argues the offer again is refused for
sharing em1's rung, and a step that misses its own rung is named with the
NEAREST rung it does read as, so a drifting em3 is reported as another em2
rather than as a second em1.

**The ask DESCENDS across the sequence.** `config/copy-ask-ladder.yaml` is the
authority on the order and `copylint.ask_rank` reads it: em1 may ask for the
largest thing in the ladder, and every later step asks for something smaller or
the same. A step that asks for MORE than the step before it is refused
`ask_does_not_descend`. em5 asks for nothing but permission to stop.

**em2 and em4 are REPLIES, not new arguments.** They carry no new rung of their
own (operator, 2026-09-30, `thread_reply_rungs: [2, 4]` on the offer record),
they reference the thread they sit in, and they are 15 to 60 words where em1 is
90 to 140. A bump with no thread reference is refused `bump_without_thread`.
em5 is the exception: it opens a NEW thread deliberately, because a breakup
that arrives under a subject nobody opened is a breakup nobody reads.

## Where this differs from the cadence in the code, measured

`cadencelibrary.PRODUCTIVE_LI_HEAVY_V1` is what the system actually schedules
today. Its email steps, read from the module on 2026-10-03, fall on library
days 1, 4, 8, 12 and 21 - which as offsets from the first email is 0, +3, +7,
+11, +20.

| step | operator's offset | the code's offset | delta |
|---|---|---|---|
| em1 | 0 | 0 | - |
| em2 | +3 | +3 | none |
| em3 | +7 | +7 | none |
| em4 | +12 | +11 | one day earlier in the code |
| em5 | +18 | +20 | two days later in the code |

The first three steps already agree exactly. The two that differ are **not
changed by this file**: a cadence day offset decides when a real email is
scheduled to a real person, the live sequence is the authority on it, and
changing it belongs to a task that can say what the change does to the forward
book rather than to a prompt exemplar. The delta is recorded here so that
nobody has to rediscover it, and so that "the operator's cadence" and "the
cadence that runs" are not assumed to be the same eighteen days.

## What the sequence does NOT do

- No sixth step, no revival inside the same run.
- No attachment and no link in any step.
- No more than one question per step. `copylint.refuses_multiple_questions`
  enforces it, and the measured failure was three questions in one body.
- No step restates an earlier one. `followup_adds_value` refuses a step that
  repeats what another already said, which is the half of "a sequence is one
  conversation" that a per-message lint cannot see.
- No step describes the prospect's own company back to them.
  `copylint.describes_their_own_company` refuses the two definitional shapes
  and allows legitimate personalisation.
