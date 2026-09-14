# TASK-052 - The rung told to name the product does not name it

## THE FINDING, MEASURED

On 2026-09-14 the client config gained a `product:` block and the prompt
started carrying it. Before that change the word "Productive" appeared ZERO
times in the rendered prompt; now it appears, `product.name` is
`"Productive"`, and `EMAIL_FIVE_LADDER` rung 3 and
`LINKEDIN_DEFAULT_LADDER` rung 4 both say "Name it".

Regenerated live on `ogpartner-dk` afterwards:

    li4  "our platform connects creative project tracking with real-time
          budget insights to help founders keep control without extra admin."

    em3  "Our product provides real-time visibility into project
          profitability and resource use, connecting financial data with
          creative workflows."

Neither names it. Both say "our platform" or "our product". That is an
improvement on the previous run - which invented a product called
`ProjectSync` - and it is still not what the rung asks for.

The operator's requirement: "Early enough in the conversation, the prospect
must understand what Productive is."

## GOAL

Establish WHY the model declines to use the name, and fix the cause.

## WHAT TO ESTABLISH FIRST - THIS IS MOST OF THE TASK

Do not jump to a fix. Three candidate causes, and they need different fixes:

1. **The model is not reading `product.name` as a name it may use.** Test by
   rendering the prompt and reading the `product` block as it appears in the
   JSON context. Is `name` adjacent to `what_it_is`, or separated by enough
   structure that it reads as metadata?

2. **A rule elsewhere in the prompt discourages it.** `prompts/draft.md` and
   `prompts/linkedin_note.md` both carry long "never" sections. Read them as
   the model would. Is there anything that reads as "do not name things", or
   that makes naming feel like a claim needing evidence?

3. **It is a model preference and the brief needs to be explicit.** Test by
   varying ONLY the rung text and regenerating.

Report which one it is with evidence. If it is more than one, say so.

## HOW TO TEST WITHOUT SPENDING THE PRODUCTION LEDGER

Copy `work/queue.jsonl` to a scratch path, point the `QUEUE` environment
variable at the copy, clear the stored cadence steps for one record, and run
`py -3 -m src.generate --live --id <record>`. That is exactly how the
copy-progression fix was proved on 2026-09-14. Never point `QUEUE` at the
real file.

`LLM_MODEL` is `openai/gpt-4.1-mini`. Live model calls cost money, so change
one thing at a time and say what each run cost in calls.

## THE CONSTRAINT THAT DECIDES THE SHAPE OF THE FIX

**Do NOT add a gate that requires the literal string "Productive".** This
repository's precedent is explicit and was paid for: `quality.gate`'s
docstring records a check that failed 51 of 70 staged steps and the
human-approved campaign 451 canary, and concludes "a gate that fails good
copy is worse than none". A message that says "our platform" is honest copy,
not a defect - it is merely weaker than it should be.

The fix belongs in the BRIEF, and it is verified by MEASURING how often the
name appears across several regenerations, not by a pass/fail rule.

Report the rate before and after: "N of M regenerated product-rung messages
named Productive, before; K of M after."

## WHAT YOU MAY NOT DO

- No live provider call, no campaign mutation.
- Do not touch `work/queue.jsonl` or `work/campaigns.jsonl`.
- Do not change `EMAIL_FIVE_LADDER` rung 5.
- Do not weaken `claims.foreign_product`, which is what stopped
  `ProjectSync` reaching a prospect.

## RESULT BLOCK

End this file with STATUS, COMMIT SHA, TESTS, FILES CHANGED, FINDINGS,
RISKS, RECOMMENDED CLAUDE ACTION.
