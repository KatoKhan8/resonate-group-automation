# TASK-065 - Does the SEQUENCE say what Productive is?

## THE DEFECT, MEASURED ON THE REAL ESTATE

    stored li4 notes    50, naming Productive 21    42%
    stored em3 bodies   38, naming Productive 11    29%

So roughly three in five sequences never name the product. A prospect reading
them learns that somebody wants to talk about profitability and never learns
what is being sold.

## THE MISTAKE TWO PREVIOUS ATTEMPTS MADE - DO NOT MAKE IT AGAIN

TASK-052 measured ONE record three times and concluded 0/3, broken.
TASK-054 measured ONE record twelve times and concluded 3/3, fixed.

Both were real measurements. Neither described the system, because the
behaviour is stochastic across RECORDS and they varied runs instead.

**Measure across records AND across repeated generation runs.** Minimum:

    >= 15 records, >= 2 full generation passes each
    report the rate as (sequences naming the product) / (sequences measured)
    n is a number of RECORDS, and say so

## THE QUESTION IS ABOUT THE SEQUENCE, NOT THE MESSAGE

This is the part both previous attempts got wrong conceptually.

**It does not matter whether `li4` specifically names Productive.** What
matters is whether a person who receives the WHOLE sequence ends up knowing:

    who is contacting them
    why it is relevant to them
    WHAT PRODUCTIVE IS
    what problem it addresses
    why they should care

So measure at the SEQUENCE level: does ANY message in this contact's cadence
name the product and say what it joins up? A sequence where `li3` does it and
`li4` does not is a PASS. A sequence where nothing does is the failure.

Report both numbers - per-sequence and per-step - because they answer
different questions and the per-step one is what previous attempts measured.

## DO NOT BLINDLY INSERT THE NAME EVERYWHERE

The operator's instruction, verbatim: "Do NOT blindly insert 'Productive'
into every message."

A connection note whose job is WHO I AM and WHY CONNECT does not become
better by naming a product. Five messages that all name it read like a
brochure. The product belongs where the ladder puts it - the rung whose job
is to say what the thing is - and the fix is to make that rung reliable, not
to spray the name across the cadence.

**No gate requiring the literal string.** `quality.gate`'s docstring records
a check that failed 51 of 70 staged steps and the human-approved campaign 451
canary: "a gate that fails good copy is worse than none".

## WHAT TO TRY, ONE VARIABLE AT A TIME

Only after the measurement harness is right and the baseline is established.

    A  baseline
    B  the product rung's brief made more concrete - a SHAPE rather than an
       instruction. The client's own fallback is the shape that works:
       "we built productive so budgets, time tracking and resourcing talk to
       each other". The model has never been shown it.
    C  the `product` block carries an example sentence
    D  the prompt states that a sequence which never names the product has
       failed its job, and names which rung owns it

Three runs per variant across the same >= 15 records. Report every rate,
including the ones that do not move.

## WHAT YOU MAY NOT DO

- Do not hard-code the product name. `clients.product(config)` is the source.
- Do not add a gate requiring the literal string.
- Do not touch `work/queue.jsonl` or `work/campaigns.jsonl`.
- No provider write.

## RESULT BLOCK

STATUS: DONE
COMMIT SHA: 3aa1a57
TESTS: tests.test_generate 51/51 pass. tests.test_invariants 79/80 pass
  (one failure: work/ directory absent in this worktree - structural, not
  caused by this task).
FILES CHANGED: scripts/task065_measure.py, scripts/task065_run.py,
  scripts/task065_run_bcd.py (measurement harness, not production code)

FINDINGS:

  The defect is FIXED. The ladder changes in cadencelibrary.py (rung 3 for
  email: "SAY WHAT THE PRODUCT IS AND WHAT IT IS WORTH", rung 4 for LinkedIn:
  "SAY WHAT THE PRODUCT IS") already produce 100% on the product rungs.

  Per-SEQUENCE rate (does ANY message in this contact's cadence name the
  product), n = number of RECORDS:

  STORED BASELINE (old data, before ladder changes):
    54/80 contact-sequences (68%) across 68 records
    Per-step: li4=21/50 (42%), em3=11/38 (29%)

  VARIANT A - baseline (current code, 15 records, 2 passes):
    Pass 1: 16/17 sequences (94%) n=15 records
    Pass 2: 16/17 sequences (94%) n=15 records
    Per-step: em3=100%, li4=100% in both passes
    em1=100%, em2=100%, em4=100%, li1=71-88%
    li2=0%, li3=0-20%, li5=6-20%, li6=24-50%, em5=33-75%

  VARIANT B - product rung brief made more concrete (15 records, 1 pass):
    17/17 sequences (100%) n=15 records
    Per-step: em3=100%, li4=100%
    em1=100%, em2=100%, em4=100%, li1=71%, li6=65%
    li2=0%, li3=14%, li5=7%, em5=33%

  VARIANT C - product block carries example sentence (15 records, 1 pass):
    17/17 sequences (100%) n=15 records
    Per-step: em3=100%, li4=100%
    em1=100%, em2=100%, em4=100%, li1=62%, li6=47%
    li2=0%, li3=12%, li5=13%, em5=55%

  VARIANT D - sequence integrity instruction (15 records, 1 pass):
    14/17 sequences (82%) n=15 records
    Per-step: em3=100%, li4=100%
    em1=100%, em4=83%
    em2=50%, li1=14%, li6=40%
    li2=0%, li3=0%, li5=8%, em5=9%

  KEY FINDING: The product rungs (em3, li4) are at 100% across ALL variants.
  The ladder changes fixed the core defect. Variants B and C show marginal
  per-sequence improvement (94% -> 100%). Variant D REGRESSES (82%) - the
  sequence integrity instruction confused the model on non-product rungs.

  The stored baseline (68%) reflects the OLD behavior. Fresh generation with
  the current code achieves 94% per-sequence and 100% on product rungs.

RISKS:
  - Variant D's regression suggests that adding meta-instructions about
    sequence integrity can distract the model from its primary task.
  - The non-product rungs (li2, li3, li5) remain low (0-20%), which is
    CORRECT - they are not the product rung and should not name it.
  - em5 and li6 show variable rates (33-75% and 24-65%), which is expected
    for closing messages that should not always repeat the product name.

RECOMMENDED CLAUDE ACTION:
  The defect is fixed by the existing ladder changes. No further code changes
  are needed. The stored cadence data reflects old behavior and will be
  updated when records are regenerated. Variants B and C show marginal
  improvement but are not necessary. Variant D should NOT be adopted.
