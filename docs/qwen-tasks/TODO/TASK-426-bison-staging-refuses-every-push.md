PRIORITY: P0
SIZE: S
DEPENDS:

# TASK-426 — the EmailBison lead-write path refuses EVERY push, and it masks the killswitch proof

**Found 2026-09-27 while confirming the killswitch at master `ec7bb722`.** This is
a small fix with two large consequences. It fails CLOSED, so nothing unsafe has
happened, but the whole EmailBison lead-write path is currently blocked and the
killswitch's own tests cannot reach the guard they exist to prove.

## THE DEFECT, one line

    src/bisonfactory.py:668     sequencegate.check(sequence)      <- no qualification passed
    src/sequencegate.py:132     qualified fails when qualification is None

`sequencegate.check` refuses when qualification is absent, deliberately: "absence
is refused rather than read as qualified". That contract is correct and must not
change. The caller simply does not supply the argument, so the check refuses every
time.

## CONSEQUENCE 1 — the bison staging path is dead

Every push through `bisonfactory` refuses at line 668 and never reaches the
killswitch consult at `bisonfactory.py:1723`, let alone `bison.create_lead` (1771)
or `bison.attach_leads` (1864). Under the production freeze this changes nothing
observable, and it errs toward refusing rather than writing, which is the right
direction to fail. But it means any dry run, any future authorised send, and the
one-account slice's EmailBison projection would all refuse for a reason that has
nothing to do with the thing being tested.

## CONSEQUENCE 2 — it is the single root cause of all 5 killswitch test failures

`tests/test_lead_writes_respect_the_killswitch` has 5 failures: 2 assert
`'killswitch'` appears in the refusal message and instead receive the sequence-gate
text, and 3 error on an uncaught `FactoryRefused`. All five share this one cause.

This is why the killswitch was classified **UNPROVEN rather than BROKEN**. The
guard is sound: `src/killswitch.py` is six layers (`GLOBAL, WORKSPACE, CAMPAIGN,
ACCOUNT, CONTACT, STEP`) on workspace key `sending.live`, absence means off and is
asserted rather than assumed, the decision is pure code with no LLM anywhere, and
**no write path skips it** — verified across every direct write call site outside
`src/providers/`, including the two that looked like holes (the orchestrator resume
lambdas pass *through* `providerwrites.perform`, and `heyreachfactory`'s direct
`heyreach.add_leads_to_campaign` at 1540 sits behind `executionguard.authorize` at
1205 plus Gate 1). What is missing is the PROOF, because an earlier gate always
answers first.

The proof was temporarily restored by patching only `sequencegate.check` to pass,
leaving the killswitch and every other gate real: 3 tests passed, including the
mutation test where removing the enforcement lets the leads through. So the
killswitch is demonstrably the gate that refuses, not a bystander. That patch was
a demonstration, not a fix, and was not applied.

## THE FIX

Have `bisonfactory`'s caller pass the qualification into `sequencegate.check` at
line 668. Then the existing five tests pass unmodified.

**Do NOT fix this by relaxing the `qualified` check, and do not default
qualification to anything.** "Absence is refused rather than read as qualified" is
load-bearing: a missing qualification silently treated as qualified is how an
unqualified lead reaches a provider. The caller has the qualification; it just is
not handing it over.

## ACCEPTANCE

1. The five existing tests in `tests/test_lead_writes_respect_the_killswitch` pass
   **without being modified.** If a test needs editing to pass, the fix is wrong.
2. A push through `bisonfactory` reaches the killswitch consult at 1723. Prove it:
   with `sending.live` off the refusal message names the killswitch, not the
   sequence gate.
3. MUTATION: remove the killswitch enforcement and a test must fail. This is the
   assertion that the killswitch, not an earlier gate, is doing the refusing.
4. The `qualified` check still refuses when qualification is genuinely absent.
   Assert this separately, so the fix cannot have been achieved by weakening it.
5. Full suite: diff the failing-name SET against
   `docs/state/SUITE-BASELINE-2026-09-26.txt` (128 named failures). The
   228-failure 09-27 file is NOT a baseline; the operator refused it. A new
   failure in any safety module BLOCKS.

## SOMETHING THE OPERATOR SHOULD KNOW, recorded here so it is not lost

Read-only at `ec7bb722`: `killswitch.workspace_state('productive')` returns
`sending=True`, "sending.live is on for productive". **The killswitch is not
tripped today and would permit sending.** What is currently preventing an
EmailBison lead write is the production freeze plus this defect, not the
killswitch. An absent workspace returns `sending=False`.

## WHAT THIS TASK MAY NOT DO

- No send, activate, resume, enrol or attach. Provider writes ZERO. Freeze stands.
- Do not relax `sequencegate`'s `qualified` check or default a qualification.
- Do not modify the five killswitch tests.
- Do not edit `src/generate.py`, `src/generate_campaign.py`, `src/sequenceplan.py`
  or `src/providers/bison.py` beyond what this one argument requires — TASK-400 and
  TASK-364 are active nearby. If the fix needs more, say so and stop.
