# Why bulk regeneration is not currently delegable, and the one change that fixes it

The operating rule is right: Qwen should own bulk generation, Claude should
own architecture, QA, provider writes and promotion. Bulk copy regeneration
belongs on Qwen's side of that line.

**It cannot run there today, for three reasons, and only one of them is the
quota.** This file names all three because two are structural and will still
be true on 2026-09-20 when the quota resets.

---

## 1. QUOTA - temporary, resets 2026-09-20 19:27 UTC

    Your token-plan 1-week quota has been exhausted.

Verified twice, hours apart, with a real workload: a single "read this file
and describe one function" request returns 429. Four workers exhausted it
between them today after completing TASK-047 through TASK-056.

This one fixes itself, or fixes sooner with a different API key.

## 2. NO MODEL CREDENTIALS IN THE QWEN WORKTREES - structural

`QWEN.md` states it as a property rather than a promise:

    "There are no credentials in this worktree - `config/.env` exists only
     in Claude's - so this is structural, not a promise."

That file holds `BISON_KEY`, `HEYREACH_KEY`, `CONTACTOUT_TOKEN` and the rest
**and `LLM_API_KEY` alongside them.** So a worktree with no provider
authority also has no model access, and `py -3 -m src.generate --live`
cannot run in it at all.

This is not a bug in the isolation. It is the isolation being coarser than
the thing it protects. Qwen reported it itself on TASK-052 and correctly
asked Claude to run the measurement rather than claiming a result.

## 3. `work/` IS FORBIDDEN TO QWEN - structural, and correct

    "Write to `work/` in any worktree. It holds canonical record and
     campaign state and is not in git."

Regeneration writes `work/queue.jsonl` through `store.transaction()`. That
prohibition is right and should not be relaxed: the queue is the canonical
record of every prospect, and `CLAUDE.md` makes `src/store.py` the only door.

---

## THE SEAM THAT IS IN THE WRONG PLACE

`config/.env` conflates two different kinds of authority:

    MODEL ACCESS      LLM_API_KEY, LLM_BASE_URL, LLM_MODEL
                      spends money, writes nothing anybody receives

    PROVIDER ACCESS   BISON_KEY, HEYREACH_KEY, CONTACTOUT_TOKEN,
                      APIFY_TOKEN, REOON_KEY, DELIVERABLE_KEY, BLITZ_API_KEY
                      reaches real people and real credit balances

Those are not the same risk. A model call cannot email a stranger. The whole
argument for keeping Qwen away from `config/.env` is about the second group,
and the first group got caught in it.

**RECOMMENDED, and it is the operator's decision because it changes who can
spend money:** give the Qwen worktrees an `.env` carrying ONLY the three
`LLM_*` variables. Provider keys stay exclusively in Claude's worktree, so
`QWEN.md`'s structural claim about providers remains literally true.

That single change makes delegable:

    bulk copy regeneration            the current blocker
    variant generation                5 variants per step needs ~25 calls
                                      per contact and is pure model work
    live measurement of prompt        TASK-054 is blocked on exactly this
    changes                           and had to be handed back to Claude

## AND THE LEDGER STAYS CLAUDE'S

Even with model access, Qwen must not write `work/`. The protocol that
satisfies both:

    1  Claude exports the records a task needs to a scratch queue
    2  Qwen regenerates against the SCRATCH queue, with `QUEUE` pointed at
       it, and commits nothing from `work/`
    3  Qwen renders previews, runs the gates, and produces a PASS/FAIL report
    4  Claude reviews the report, inspects representative sequences, and
       promotes the scratch result into `work/queue.jsonl`

Step 4 is a real review, not a rubber stamp. Four of the six Qwen tasks
integrated on 2026-09-14 needed correction, including one that silently
rewrote two curly apostrophes as ASCII and would have made `lint` refuse
every ordinary contraction.

---

## WHAT IS DELEGABLE TODAY WITHOUT ANY CHANGE

These need no model call and no `work/` write, and are queued:

    historical cadence and outcome analysis   reads exports
    reply classification analysis             reads exports
    duplicate and repetition detection        pure functions over text
    preview rendering                         reads canonical state
    batch preparation logic                   code, not execution
    copy-quality gate definition and tests    code

Queued as TASK-057 onward. They are real work and they are not the bulk
regeneration, which is what the operating rule actually wanted moved.
