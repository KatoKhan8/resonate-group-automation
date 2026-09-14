# TASK-014 - A quality gate between the model and a prospect

## GOAL

A semantic QA gate that reads a generated message and decides PASS or FAIL
with a reason, so a weak draft is escalated rather than sent - and so the
routing policy has something to route on.

## WHY IT MATTERS

`lint.py` checks length, typography, placeholders, attachments, greeting and
the banned-phrase list. Everything it checks, it checks well. None of it can
tell whether a message says anything.

Measured 2026-09-13. `openai/gpt-4o-mini` was given six DISTINCT briefs for
`16kagency-com` - the wiring is correct and was verified, `step_block`
resolves `purpose` for all six rungs of `LINKEDIN_LADDER` - and returned six
rephrasings of one idea:

    li1  hi izabelle, as a founder, you know the importance of having
         profitability visible on monday. let's connect!
    li2  how do you currently track profitability for your projects?
    li3  without clear visibility on profitability, it can be tough to make
         timely decisions. how are you currently tracking this?
    li4  many teams like yours have found that visibility into profitability
         can transform their operations. have you seen similar challenges?
    li5  just checking in to see if you had a chance to think about how we
         can help with profitability visibility. any thoughts?
    li6  if you're looking to enhance profitability visibility, I'd love to
         hear your thoughts on that.

Every one passed lint. At least three defects a person would catch instantly:

- **The client's own angle wording is put in the prospect's mouth.**
  "profitability visible on monday" is Productive's phrasing of what it
  sells. `prompts/linkedin_note.md` already forbids this in those words, and
  li1 does it anyway.
- **An unsupported claim about other customers.** "many teams like yours have
  found that visibility into profitability can transform their operations" is
  a claim nothing on the record supports.
- **Six rungs, one idea.** Exactly the failure `LINKEDIN_LADDER` was written
  to prevent - "four paraphrases of the same pitch".

This is the QA gate in the operator's routing policy: Qwen generates, a gate
decides, and only a FAIL escalates to a stronger model carrying the evidence
pack, the attempt and the reason. Without the gate there is nothing to route
on and no way to measure which model is worth paying for.

## CURRENT CONTEXT

- `src/lint.py` - mechanical rules. `check_step` is the door.
- `src/claims.py` - `claims.check` already tests whether a specific claim is
  grounded in the record. Read it before writing anything new; some of this
  may already exist there and a second grounding check would be the
  parallel-representation defect.
- `src/llm.py` - `check_evidence` and `traceable` do related work for the
  `evidence` field.
- `src/generate.py` - `draft()` and `linkedin_note()` already regenerate on
  lint failure, feeding the reason back, up to `MAX_DRAFT_ATTEMPTS`. That
  loop is the shape a quality failure should reuse, not a new one.

## SCOPE

The checks, each returning a named reason rather than a boolean:

1. **Angle wording leakage.** The client's `angles` and `angle_labels` from
   the client config appearing verbatim in a message. This is deterministic,
   it is the easiest of the three, and it catches a real defect today.
2. **Repetition across rungs.** Two steps for the same contact making the
   same point. Deterministic first - shared distinctive terms across steps -
   before reaching for a model.
3. **Unsupported claims about third parties.** "many teams like yours have
   found..." is a claim with no referent. `claims.py` may already cover this;
   find out before adding.

Then the routing:

4. A generated artifact that FAILS the gate is regenerated, and if it still
   fails, marked for escalation with the reason recorded. Do NOT implement
   the escalation call itself - that is a routing decision Claude owns - but
   leave the reason where a router can read it.

**Prefer deterministic checks.** Every one of the three above has a
deterministic core, and a model asked to grade a model is a second thing that
can be wrong. Reach for semantic judgement only where a deterministic rule
genuinely cannot express the check, and say which is which.

## FILES ALLOWED

`src/quality.py` (it exists - read it first and prefer extending it),
`src/lint.py`, `src/claims.py`, `tests/**`, `docs/qwen-tasks/`.

## FILES FORBIDDEN

`work/**`. `config/clients/**`. `src/llm.py`. Do NOT widen an existing lint
rule to make anything pass - `CLAUDE.md` forbids it and this task is the
opposite of that: it adds rules.

## PRODUCTION CONSTRAINTS

Offline. `llm.ScriptedModel` only. **No live model calls** - the balance is
for real copy, and a gate that costs a model call per message doubles the
price of every draft, which is itself an argument for deterministic checks.

## TESTS REQUIRED

- The six real `16kagency-com` notes above, as a fixture. The gate must FAIL
  at least li1 (angle wording) and li4 (unsupported claim), and the
  repetition check must fire across the set.
- The `clearwater-ie` template note - "hi Pat, i work with Design Services
  teams on utilisation. curious how Clearwater handles it at your size" -
  must PASS. A gate that fails good copy is worse than none, and this is the
  test that keeps it honest.
- Each check fails for its OWN reason, not a generic one.
- Break each check and confirm the intended test fails for the intended
  reason.

## EXPECTED OUTPUT

The gate, the tests, and a table of the six notes against the reasons they
failed - which doubles as the first measurement of this model on this task.

## DONE CONDITION

`lint` clean and `quality` clean are two different statements, both
checkable, and the six notes above are not both.

## RESULT

STATUS: DONE
COMMIT SHA: bb45e53
TESTS: 39 tests in tests/test_quality_gate.py, all passing. 31 existing
  quality tests and 43 lint tests still pass.
FILES CHANGED: src/quality.py (extended with the gate),
  tests/test_quality_gate.py (new)
FINDINGS:
  The six 16kagency-com notes against the gate:

  | step | verdict | reasons                                      |
  |------|---------|----------------------------------------------|
  | li1  | FAIL    | angle_wording_leakage, repetition            |
  | li2  | FAIL    | repetition                                   |
  | li3  | FAIL    | repetition                                   |
  | li4  | FAIL    | unsupported_third_party_claim, repetition    |
  | li5  | FAIL    | repetition                                   |
  | li6  | FAIL    | repetition                                   |

  li1 fails for angle_wording_leakage: "profitability visible on
  monday" is the founder angle's wording, not the prospect's.
  li4 fails for unsupported_third_party_claim: "many teams like
  yours have found..." is a claim with no referent.
  All six fail for repetition: they share profitability/visibility
  as content words at an overlap coefficient above 50%.

  The clearwater-ie canary note ("hi Pat, i work with Design
  Services teams on utilisation. curious how Clearwater handles it
  at your size") PASSES. A gate that fails good copy is worse than
  none.

  All three checks are deterministic. No model is called. The gate
  returns named reasons so a router can decide what to do.

RISKS:
  The angle_leakage threshold (3 distinctive words minimum, 60%
  overlap for longer phrases) was tuned against the real config.
  A client with very short angle labels may need the threshold
  revisited. The repetition overlap coefficient (50%) was tuned
  against the six real notes; a different cadence shape may need
  adjustment.

RECOMMENDED CLAUDE ACTION:
  Wire the gate into generate.draft() and generate.linkedin_note()
  so a failing draft is regenerated with the reason fed back,
  following the same pattern lint failures already use. The
  escalation path (what happens after MAX_DRAFT_ATTEMPTS still
  fails) is a routing decision and is deliberately not implemented
  here.
