# TASK-054 - The model will not write "Productive", and the name may be why

## WHAT IS ALREADY ESTABLISHED - DO NOT REDO IT

TASK-052 established, by rendering the real prompt, that the `product` block
REACHES the model correctly: `product.name` is `"Productive"`, it is in the
rendered string, and both product rungs ask for it.

It then made the instruction explicit - "use the product's name in the
message, not 'our product' or 'our platform'" - and that was MEASURED on
2026-09-14 across three live regenerations of `ogpartner-dk`:

    li4 named Productive: 0 of 3

    "our solution helps founders like you streamline campaign planning..."
    "our solution connects creative project management with real-time..."
    "the product joins up project tracking with resource planning..."

The instruction is being obeyed to the letter. "our product" and "our
platform" are gone - those are exactly the two phrases it forbade - and the
model substituted "our solution" and "the product". Naming two forbidden
phrases taught it two phrases to avoid, and nothing more.

So the brief being explicit is NOT the cause. That candidate is closed.

## THE UNTESTED HYPOTHESIS

**"Productive" is an ordinary English adjective.** A model may be declining
to use it as a proper noun because in a lowercase, casual LinkedIn note it
reads as a word rather than a name - "productive project tracking" is a
sentence about being productive, not about a product.

Two things make this worth testing before anything else:

1. The client's own hand-written fallback copy writes it LOWERCASE:
   "we built productive so budgets, time tracking and resourcing talk to
   each other". A human writing for this client had the same problem and
   solved it by context rather than capitalisation.
2. `tone.linkedin` is "casual, lowercase, human", so the model is being
   asked to lowercase everything AND to use a proper noun that becomes
   invisible when lowercased.

## HOW TO TEST IT - CHEAPLY, ONE VARIABLE AT A TIME

The measurement harness matters more than the fix. Build it first: clear one
record's cadence in a SCRATCH queue, regenerate, count how many of the
product-rung messages contain the name. Three runs per variant, and report
the rate for every variant including the ones that fail.

Variants worth trying, in this order:

    A  baseline, as master stands today                     (expect 0 of 3)
    B  the context tells the model the name is a proper noun and may be
       written lowercase, the way the client's own copy does
    C  the rung gives a shape rather than a rule - the fallback line IS the
       shape: "we built X so A, B and C talk to each other"
    D  the `product` block carries a short example sentence using the name

Do not try them all at once. One variable, three runs, a number.

## THE CONSTRAINT THAT DECIDES THE SHAPE OF THE FIX

**Do NOT add a gate requiring the literal string.** `quality.gate`'s own
docstring records a check that failed 51 of 70 staged steps and the
human-approved campaign 451 canary, and concludes "a gate that fails good
copy is worse than none". "our solution connects project tracking with
resource planning" is honest copy. It is weaker than it should be, not
wrong, and a refusal would cost more than it buys.

**And do not hard-code "Productive" anywhere.** The fix has to work for a
client whose product is called something else. `clients.product(config)` is
the only source of the name.

## COST

Live model calls cost money. `LLM_MODEL` is `openai/gpt-4.1-mini`. Report
the number of calls each variant spent. If a variant is clearly failing after
three runs, stop it and move on rather than gathering more evidence for a
conclusion you already have.

## WHAT YOU MAY NOT DO

- No live provider call, no campaign mutation.
- Do not touch `work/queue.jsonl` or `work/campaigns.jsonl`. Copy to a
  scratch path and point `QUEUE` at the copy.
- Do not change `EMAIL_FIVE_LADDER` rung 5.
- Do not weaken `claims.foreign_product`, which is what stopped an invented
  product called `ProjectSync` reaching a prospect.

## RESULT BLOCK

End this file with STATUS, COMMIT SHA, TESTS, FILES CHANGED, FINDINGS,
RISKS, RECOMMENDED CLAUDE ACTION. FINDINGS must carry the rate per variant.
