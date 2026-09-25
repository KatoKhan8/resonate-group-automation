PRIORITY: P0
SIZE: L
DEPENDS: TASK-312

# TASK-316 — the 50-lead file for tomorrow morning

Fifty leads from 503 through the v2 engine, same shape as tonight's ten.

## Reuse, do not rebuild

`work/v2_run.py` and `work/v2_pages.py` ran the ten end to end tonight and
work. TASK-312's `src/copyengine.py` is the production path. **Use one of
them; do not write a third.** If the production path is ready, prefer it and
say so; if not, say why and use the working script.

Leads: the next 50 from `work/sample50-built.json`, excluding tonight's ten.

## What the file must carry, per lead

Everything tonight's ten carried: qualification and why, ICP evidence, facts
with source URLs, the hypothesis marked as a hypothesis, the capability and
why, the sequence strategy with an objective per step, all five emails with
threading (em1 new/A, em2 Re:A, em3 new/B, em4 Re:B, em5 new/C), both P.S.
lines with the variant, the mailbox signature, four LinkedIn messages, the
LinkedIn URL, copylint and sequencegate results with refusal reasons.

**One .html with all fifty expanded and one .xlsx.** Not an index of links.

## The numbers the operator will ask for

Written, held and errored counts. Cost by hand, split by model. **How many
distinct capabilities stage D chose** - if it is 1 across fifty leads, stage D
is defaulting and the batch check in `sequencegate` says so. The
qualification spread across the four outcomes.

## Traps, measured tonight

- Sonnet truncates. 700 cut off 4 of 10; 2600 cut off 5 of 10; 4000 was not
  enough once the four LinkedIn messages and three subjects were added.
  **Treat a JSONDecodeError as truncation first.**
- `json.loads(..., strict=False)` - literal newlines inside strings.
- Groq 403s with Cloudflare 1010 on urllib's default user-agent.
- gpt-oss-120b spends max_tokens on reasoning before output.
- LinkedIn URLs: `work/Productive/productive_ICP_safe_to_send (1).csv`,
  column `Url`, 100% coverage. **No ContactOut spend is needed.**

## Rules

**Nothing is sent. No campaign is activated. No provider write except reading.**

## Acceptance

Both files exist, fifty leads, and the counts above reported. Commit the
scripts, push, report the remote SHA and URL. The files themselves stay in
`work/`, which is gitignored and holds real prospect data.
