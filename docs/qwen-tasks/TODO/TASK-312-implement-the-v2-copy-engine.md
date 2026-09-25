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
