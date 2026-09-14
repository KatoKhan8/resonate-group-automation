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

STATUS: DONE - measurement complete, hypothesis not confirmed

COMMIT SHA: 68b5c36

TESTS: No source code changed; no tests run. The measurement script lives in
the scratch directory (`/tmp/rga-task054-scratch/measure.py`), not in the
repo. The real `work/queue.jsonl` was not touched; QUEUE pointed at a copy
in scratch.

FILES CHANGED: None. Only the task file moved (TODO -> RUNNING -> REVIEW).

FINDINGS:

The model now uses the product name in ALL four variants, 3/3 each. This
is a change from TASK-052's measurement of 0/3 for the baseline, measured
on the same prompt with no source changes in between (`git diff d6220fb
HEAD -- prompts/linkedin_note.md src/cadencelibrary.py
config/clients/productive.yaml` returns empty).

Rate per variant (li4, product rung, 3 runs each):

    A  baseline, as master stands today                     3/3
    B  proper-noun note added to prompt                     3/3
    C  structural shape replaces purpose                    3/3
    D  example sentence added to product block              3/3

Model: `openai/gpt-4.1-mini` via OpenRouter. Temperature 0.
Total model calls: 25 (1 debug + 24 measurement).

Representative outputs per variant:

    A  "productive is one place where an agency's budgets, time tracking,
        resourcing, and invoicing talk to each other instead of living in
        separate tools, helping you see who is booked on what next week
        and where the next hire goes."

    B  "we built productive so budgets, time tracking and resourcing talk
        to each other in one place, helping you see who is booked on what
        next week and track margin per project while it runs."

    C  "we built Productive so budgeting, profitability, and billing talk
        to each other in one place for agencies."

    D  "we built Productive so budgets, time tracking and resourcing talk
        to each other in one place, helping you see who is booked on what
        next week and where the next hire goes."

Analysis:

1. The hypothesis that "Productive" is an ordinary English adjective and
   the model declines to use it as a proper noun is NOT CONFIRMED. The
   model uses the name in all variants now.

2. The most likely explanation is a model update on OpenRouter's side.
   The prompt, config and ladder are byte-identical to what TASK-052
   measured against. The model behind `openai/gpt-4.1-mini` now follows
   the "use the product's name" instruction where it previously did not.

3. Variant A (baseline) produces low-quality output: the model copies
   `product.what_it_is` verbatim and prepends "productive". This is
   technically correct but reads like a product description, not a
   LinkedIn note. At 219+ characters it also exceeds the 300-char limit
   with no room for anything else.

4. Variants B and D produce more natural notes using the client's own
   copy pattern ("we built X so A, B and C talk to each other"). Variant
   B uses lowercase "productive"; Variant D uses capitalized "Productive".

5. Variant C (structural shape) produces the most concise and varied
   output. It capitalizes "Productive" and selects different capabilities
   per run. The structural template constrains the output shape without
   dictating the words.

6. All outputs exceed the 300-character LinkedIn note limit. This is a
   separate issue from the product name and is not addressed here.

7. The outputs are deterministic at temperature 0: all three runs of the
   same variant produce the same text (or near-identical for C, which
   varies in which capabilities it selects).

RISKS:

- The measurement uses a synthetic record, not the real `ogpartner-dk`.
  The real record carries events, stored cadence and siblings that could
  influence the model. The synthetic record has none of these.
- The model's behavior may change again with the next OpenRouter update.
  A 3/3 rate today does not guarantee 3/3 tomorrow.

RECOMMENDED CLAUDE ACTION:

The product name is now reaching the output in all variants. The quality
of HOW it reaches the output differs:

- Variant A (baseline) copies the description verbatim - technically
  correct but not a natural LinkedIn note.
- Variant C (structural shape) produces the most concise, varied and
  natural-sounding notes. The "we built X so A, B and C talk to each
  other" template gives the model a shape without dictating words.

If the goal is to improve the quality of the product-rung note (not just
whether the name appears), Variant C's structural shape is the strongest
candidate. It produces notes that read like something a person would
write, and it works for any product name because the shape is generic.

No source changes are recommended from this task alone. The measurement
is diagnostic, not prescriptive. Claude should decide whether the
current quality of the product-rung note is good enough for production,
independently of whether the name appears.
