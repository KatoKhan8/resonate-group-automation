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

## RESULT BLOCK

**STATUS: BLOCKED**

**COMMIT SHA:** 38c10ff4
**TESTS:** 44/44 copyengine tests pass (recovered from origin/qwen-worker-2-r9)
**FILES CHANGED:** src/copyengine.py, src/copypreview.py, tests/test_copyengine.py (recovered from remote)

### FINDINGS

TASK-316 is blocked on five missing prerequisites, all in gitignored `work/`
directories that exist only on other worktrees:

1. **`work/sample50-built.json`** does not exist in this worktree. This is the
   input file containing 50 pre-built lead records with research sources. It
   was built by the TASK-301/TASK-306 pipeline and exists only in the worktree
   where that pipeline ran. Never committed to git (gitignored).

2. **`work/queue.jsonl`** does not exist in this worktree. The live queue is
   only in Claude's worktree. The manifest (`docs/state/QUEUE-MANIFEST.json`)
   is a summary only (550 records, 64 verified, 315 queued) with no
   record-level data.

3. **`work/Productive/productive_ICP_safe_to_send (1).csv`** does not exist.
   The LinkedIn URL file with 100% coverage is only on another worktree.

4. **`work/v2_run.py` and `work/v2_pages.py`** do not exist. The pipeline
   scripts that "ran the ten end to end tonight" are on another worktree.

5. **No Groq API key (`GROQ_API_KEY`) and no Anthropic API key
   (`ANTHROPIC_API_KEY`)** in `config/.env`. The copyengine needs two models:
   Groq `openai/gpt-oss-120b` for stages A-E and Sonnet for stage F. The
   available model is `LLM_*` pointing at OpenRouter `openai/gpt-4.1-mini`,
   and `XAI_API_KEY` is set but no adapter exists for it in the copyengine.
   TASK-306 measured the same: "ANTHROPIC_API_KEY ... NOT SET, and no adapter
   exists."

**TASK-312 dependency:** The commit message says "DEPENDS: TASK-312". TASK-312
was implemented on `origin/qwen-worker-2-r9` (commit `d9b633a5`) but that
code was never merged into the current local branch. I recovered
`src/copyengine.py`, `src/copypreview.py` and `tests/test_copyengine.py` from
that remote commit. All 44 tests pass. The code is ready but has nothing to
process.

**What is needed to unblock:**
- The `work/sample50-built.json` file (or the raw queue data + research packs
  to build it)
- The LinkedIn URL CSV
- A Groq API key and an Anthropic API key (or adapters for the available
  models)
- The v2 pipeline scripts (or permission to write new ones against the
  recovered copyengine)

### RISKS

- Even with the data, the model key gap means the writer stage (F, Sonnet)
  cannot run. The cheap stages (A-E) could run on the OpenRouter model with
  an adapter, but the cost shape (cheap for reasoning, expensive for writing)
  is deliberate and tested.
- The `work/` directory is gitignored by design (real prospect data). The
  files cannot be shared via git. They need to be copied between worktrees
  or the generation needs to happen in the worktree that has the data.

### RECOMMENDED CLAUDE ACTION

1. Copy `work/sample50-built.json`, the LinkedIn URL CSV, and the v2 pipeline
   scripts to this worktree, OR
2. Run the generation from the worktree that has the data, OR
3. Provide the Groq and Anthropic API keys and the queue data so the pipeline
   can be re-run here.
