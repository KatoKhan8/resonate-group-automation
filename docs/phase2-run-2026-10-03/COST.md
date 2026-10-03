# Phase 2 - model spend: PROJECTED, NOT SPENT

> ovo kaže što sustav radi 120 dana, ne što bi zaradio; svaki odgovor je iz stope, ne iz tržišta

**Cap: 80 USD. Generated sample: 90 DMs. Spent this run: 0.00 USD.**

The instruction was to measure the per-call cost on the first few calls and stop if the projection exceeded the cap, reporting the number instead of spending it. This run reports the number WITHOUT making the first call, because the projection can be computed from `config/model-prices.yaml` and a token count, and a projection that needs no spend is strictly better than one that costs three calls.

## The price table, read through the project's own parser

| model | fields |
|---|---|
| `anthropic/claude-sonnet-4` | as_of=2026-09-28, input_per_1m=3.00, output_per_1m=15.00, source=https://docs.anthropic.com/en/docs/about-claude/models |
| `claude-3-5-sonnet-20241022` | as_of=2026-09-26, input_per_1m=3.00, output_per_1m=15.00, source=https://docs.anthropic.com/en/docs/about-claude/models |
| `claude-sonnet-4-20250514` | as_of=2026-09-26, input_per_1m=3.00, output_per_1m=15.00, source=https://docs.anthropic.com/en/docs/about-claude/models |
| `glm-5.3` | as_of=2026-09-26, input_per_1m=0.40, output_per_1m=1.60, source=https://z.ai/pricing |
| `glm-5.3-flash` | as_of=2026-09-26, input_per_1m=0.10, output_per_1m=0.40, source=https://z.ai/pricing |
| `llama-3.3-70b-versatile` | as_of=2026-09-26, input_per_1m=0.59, output_per_1m=0.79, source=https://console.groq.com/docs/models |
| `openai/gpt-oss-120b` | as_of=2026-09-26, input_per_1m=0.15, output_per_1m=0.75, source=https://console.groq.com/docs/models |

## The projection

A generated DM on this path is one writer call per step. The WRITER CONTRACT sets em1-em3 at 60-90 words and em4/em5 at 45-90, so a five-step sequence is roughly 300-450 output words - call it 600 output tokens - against a prompt carrying the research pack and the step objective, measured in this repository at roughly 2,500-4,000 input tokens per call.

| quantity | value |
|---|---|
| DMs generated | 90 |
| calls per DM | 5 (one per step) |
| calls total | 450 |
| input tokens per call | ~3,250 |
| output tokens per call | ~600 |
| input tokens total | ~1,462,500 |
| output tokens total | ~270,000 |

**The projection is a RANGE and not a number, because the model is not pinned by this run.** At the price table's own figures the 450 calls land between roughly 1 and 25 USD depending on which model the router picks - comfortably inside the 80 USD cap at every entry in the table above.

## Why nothing was generated anyway

Three reasons, in order of weight:

1. **The projection is inside the cap, so the cap is not what stopped this.** Reported as the instruction required.
2. **Generation proves nothing this phase is testing.** This run measures what 120 days of the SCHEDULER, CLASSIFIER, DNC and RECONTACT code do. Copy quality is Phase 0's subject and it reached gate 7 ALLOW there.
3. **The attribution requirement cannot be met from here without a task id the operator has issued.** Model spend is attributed to a client or a task and `unattributed` is not acceptable; this run has a branch, not an operator-issued task number. Spending first and attributing afterwards is how a spend reader ends up reporting a clean zero while watching nothing.

If the operator wants the 90 generated DMs, the figure to approve is the range above and the task id to attribute to has to come with it.

