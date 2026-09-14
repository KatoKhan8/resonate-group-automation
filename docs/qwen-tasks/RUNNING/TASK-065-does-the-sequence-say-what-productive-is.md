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

STATUS, COMMIT SHA, TESTS, FILES CHANGED, FINDINGS, RISKS, RECOMMENDED
CLAUDE ACTION. FINDINGS must carry the per-SEQUENCE rate with n as records.
