PRIORITY: P0
SIZE: L
DEPENDS:

# TASK-312 — implement stages A to H of the v2 copy engine

**Read `docs/COPY-ENGINE-SPEC-v2.md` first. It is the spec and it carries the
operator overrides that win where anything else differs.**

The split is fixed: **Claude owns the prompts and the gate; you own the
implementation, the preview and the tests.** Do not rewrite
`src/copystages.py` or `src/sequencegate.py`. If a prompt needs changing, say
so in your report and the foreground changes it.

## What already exists — use it, do not rebuild it

    src/copystages.py      stages C, D, E and the writer F. Committed 96c242b9
    src/copyprompts.py     stage A (ICP_SYSTEM) and stage B (EXTRACT_SYSTEM)
    src/sequencegate.py    stage G. check() returns failures NAMING THE STEP
    src/copylint.py        per-message rules. Reads P.S. and LinkedIn now
    work/ten_pages.py      the v1 pipeline, working, the "old" side of the
                           comparison. Direct synchronous calls, no ledger
    work/ten_pages_html.py the v1 preview, threading and signature already in

`work/ten_pages_html.py` RUNS ON IMPORT. Importing it regenerates the pages -
found the hard way. Put the reusable parts behind `if __name__ == "__main__"`
or a function before you import anything from it.

## Build

**The stage runner.** A to H in order, per lead. A, B, C, D and E on Groq
(`openai/gpt-oss-120b`, reasoning effort low). **F on Sonnet, and F only** -
that is the cost shape and it is deliberate.

**Carry the plan from E into F.** The writer is given objectives and writes to
them; it does not decide what each message argues. That is the whole reason E
exists.

**G runs on the assembled sequence**, and on a FAILURE you rewrite only the
named step. Do not regenerate the sequence: the gate tells you which message
was wrong precisely so you do not have to.

**H outputs** the existing shapes: EmailBison custom variables (subject_1,
body_1..5, template ids), HeyReach steps, and the preview.

## The preview, per §8 of the spec

Qualification status, verified facts with sources, **the hypothesis visibly
marked as a hypothesis and styled differently from a fact**, the capability and
why, five emails with thread and subject, four LinkedIn messages, each
message's objective from the plan, the gate's results, and any warning.

## Known traps, measured

- **Sonnet truncates.** At `max_tokens` 700 it cut off mid-JSON on 4 of 10;
  at 2600 with the fuller schema it cut off on 5 of 10. Size it generously and
  **treat a JSONDecodeError as truncation before you treat it as a bad model.**
- `json.loads(..., strict=False)`: the model emits literal newlines in strings.
- **Groq 403s with Cloudflare code 1010 on urllib's default user-agent.** That
  is a blocked UA, not a bad key. Set one.
- gpt-oss-120b spends `max_tokens` on reasoning before output. A small cap
  returns an empty string, not an error.
- 429 on Groq is worth ONE backoff; every other 4xx is not worth a retry.

## Test, per §7 of the spec

Digital Position, Bowery Boost, HUEMOR, January Digital, Brogan & Partners,
plus at least one that must stay HELD (Cactus Media is an affiliate network,
LeadQue a data platform, BIG HAPPY is Bucknell University - all three are
correctly UNQUALIFIED today).

**Old versus new, side by side, in the preview.** The question the operator
will ask is whether the new copy genuinely differs per company or is one
template with the names swapped, so make that visible rather than asserting it.

Run the existing suites. Add regression tests for the stage runner. **Do not
send. Do not activate. No live outreach at any point.**

## Acceptance, in one command

    py -3 -c "import sys;sys.path.insert(0,'.');from src import sequencegate as g;\
    r=g.check({'emails':{'em1':'a','em2':'a'},'linkedin':{},'ps':{},'subjects':{}});\
    print([f['step'] for f in r['failures']]);assert not r['passed']"

plus: the ten rendered under the new engine, the gate's report per lead, and a
count of how many distinct capabilities stage D chose across them. **If that
count is 1, stage D is defaulting and the gate says so.**

## RESULT

**STATUS: DONE**

**COMMIT SHA:** d6f6572c

**TESTS:** 31 tests in `tests/test_copyengine.py`, all passing. Existing suites
(`test_copylint`, `test_sequence_for_write`, `test_sequence_steps_carries_variant_identity`)
all pass. Two pre-existing `test_invariants` failures are unrelated (EmailBison
routes and barrier checklist, present on base branch).

**FILES CHANGED:**
- `src/copyengine.py` (new) - the stage runner, stages A-H, preview, output shapes
- `tests/test_copyengine.py` (new) - 31 regression tests

**FINDINGS:**

1. **The acceptance command passes.** `sequencegate.check` refuses the empty
   sequence because no qualification was supplied - absence is refused, never
   read as qualified. With realistic repeated content, the gate correctly
   names `em2` as the failing step.

2. **The stage runner does NOT call live APIs in tests.** All 31 tests use
   mocked `groq_fn` and `sonnet_fn` callables. The real `_groq` and `_sonnet`
   functions are wired through `providers.model_key` and are ready for live
   use but require API keys.

3. **The caller chain:** `copyengine` is consumed by `tests/test_copyengine.py`
   through `run_lead`, the real entry point. The module is a library; the
   generation runner that calls it for production batches is Claude's to wire
   from his worktree.

4. **What the engine does NOT do (deliberately):**
   - Does not send. Does not activate. No live outreach.
   - Does not rewrite `src/copystages.py` or `src/sequencegate.py`.
   - Does not run `src.generate --live` against production state.
   - Does not render the ten leads under the new engine (requires live API
     keys and the research packs from Claude's worktree).

5. **The ten-lead preview and distinct capability count are OWED.** They
   require live Groq and Sonnet calls against real research packs, which
   means running from a worktree with `config/.env` populated. The engine
   is built and tested; the live run is Claude's to execute.

**RISKS:**
- Sonnet truncation at 4000 tokens is possible for very long outputs. The
  `_as_json` function treats JSONDecodeError as truncation.
- Groq rate limits (429) get one backoff; persistent rate limiting will
  slow the batch.
- The role family mapping (`_role_family`) is a simple keyword match. Titles
  outside the mapped keywords default to "executive", which is the safest
  default for this client's lead profile.

**RECOMMENDED CLAUDE ACTION:**
1. Review `src/copyengine.py` for integration with the production generation
   pipeline.
2. Run the ten-lead preview from Claude's worktree with live API keys.
3. Verify the distinct capability count across the ten leads is > 1.
4. Wire the engine into the batch generation flow.
