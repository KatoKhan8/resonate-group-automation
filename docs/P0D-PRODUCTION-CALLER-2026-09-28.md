# P0-D — THE PRODUCTION CALLER

**Read-only proof. The wiring is SPECIFIED AND NOT APPLIED.** Section 9 is a
plan. Nothing in `src/` was changed by this task, because P0-B holds
`src/generate.py` and `src/generate_campaign.py` this round.

    task            P0-D, production caller
    branch          task-p0d-production-caller
    base            d0e95d20 (worktree HEAD)
    origin/master   8eabef9cd13dbd2b25300ed98a0920af55359957 (derived, see 0.2)
    measured        2026-09-28
    provider writes 0 — no provider module was imported, no socket opened
    files added     docs/P0D-PRODUCTION-CALLER-2026-09-28.md
                    scripts/p0d_callgraph.py         (read-only probe)
                    scripts/p0d_entrypoint_probe.py  (read-only probe)
    files changed   none under src/, tests/, or any doc owned by another task

---

## 0. THE ANSWER IN ONE PAGE

The question was whether the real orchestration calls the same generator, end
to end:

    account -> research -> qualification -> offer/strategy -> generation
      -> gates -> SequencePlan -> projection

**It is not one answer. The chain breaks in exactly one place, and it is not
where TASK-425 looked.**

    account -> research -> qualification -> offer/strategy -> generation
      -> gates -> SequencePlan(new)                       WIRED
                                                          one entrypoint drives
                                                          all of it

    SequencePlan -> projection                            NOT WIRED
                                                          zero nodes in the
                                                          repository reach both

**Three findings, in descending order of how much they change the picture.**

1. **TASK-425's stated finding is REFUTED on its literal claim.**
   `generate.run` HAS a production caller: `generate.main()`, the module's own
   CLI, bound to `__main__`. It is not a harness and not a test. I ran it
   against production-shaped state and it executed, entered `run()` and planned
   real records. TASK-425 disclosed its method — "Grepped" — and the grep missed
   this because inside `src/generate.py` the call is spelled `run(...)`, not
   `generate.run(...)`. **No qualified-name grep can ever see a same-module
   caller.** Section 2.

2. **There is NO parallel generator, and that is worth saying plainly.**
   Exactly one function writes prospect-facing copy into the record:
   `_adapt_plan_to_cadence` → `store_step`. The old stage writers
   (`generate.draft`, `generate.linkedin_note`,
   `generate._regenerate_linkedin_set`) and `variantgen.generate` have **zero
   callers each** — TASK-400 retired them and they are dead code, not a second
   path. Section 5.

3. **The break is at the last link, and the canonical projection is the dead
   one.** `sequenceplan.derive_bison_payload`, `derive_heyreach_payload` and
   `derive_preview_data` — the three functions that project the canonical plan's
   COPY, and the only callers of `sequenceplan.approval_hash` — have **zero
   callers**. The provider payload is instead built three separate times by
   `bisonfactory`, `push` and `render`, each reading the record's cadence
   directly. Section 6. This is a §5 "One truth" violation, and it is the
   mechanical root cause of launch blocker 1 (approval hash not enforced).

**So the honest verdict on the original question:** the generation path is
`PRODUCTION_ACTIVE` as an entrypoint and `INTEGRATION_TESTED` as an end-to-end
chain — because no single production entrypoint spans generation and the
provider projection. "Changing valid upstream information changes downstream
production output through the real entrypoint" is demonstrable up to
`rec["cadence"]` and requires a **second, separate, manually-ordered command**
to reach a provider payload. That second command is not driven by the first, and
nothing enforces that it runs after it.

### 0.1 What I did NOT prove, stated before the evidence

- **I did not run a live generation.** No model call, no spend. So every claim
  below about the chain from `generate_record` downward is **static reachability
  plus source reading**, not a behavioural causal proof. Static reachability
  proves the EDGE exists; it does not prove the data dependency. Where I mean
  one, I say so.
- **I did not prove the projection break behaviourally either.** I proved that
  no node in the call graph reaches both generation and a provider projection,
  which is a stronger statement than a grep and a weaker one than a failed run.
- **`src.run`'s generate stage is static-only.** Running it needs `--spend`,
  a model and credits. Its reachability is measured; its execution is not.
- Provider state was not read at all this round, so every provider question is
  **UNKNOWN** here rather than clean, per §26. I make no provider claims.

### 0.2 Authority for the SHAs in this document

    CLAIM        origin/master is 8eabef9c, not d0e95d20
    AUTHORITY    git rev-parse origin/master, after git fetch origin
    MEASURED AT  2026-09-28, this session
    STATE        VERIFIED

The task brief gave `origin/master = d0e95d20`. That was stale by the time I
fetched — master has moved. `d0e95d20` is this worktree's base, which is a
different claim. Per invariant 0a: the authority is the remote SHA after a
fetch, never a SHA in prose, **including the one in a task brief and including
the one in this document**.

    CLAIM        TASK-425's head is 2d54e274
    AUTHORITY    git rev-parse origin/task-425-one-account-dry-run
    MEASURED AT  2026-09-28
    STATE        VERIFIED — matches the brief. The 09-28 midday handoff says
                 88649410, which is an earlier commit on the same branch.

---

## 1. METHOD, AND WHY IT IS NOT A GREP

`scripts/p0d_callgraph.py` parses every `.py` file under `src/`, `scripts/` and
`tools/` with `ast` and builds a call graph. It imports nothing from `src`,
calls no provider and writes nothing.

It resolves four call spellings a grep handles badly or not at all:

    from . import generate;  generate.run(...)      ← a grep finds this
    run(...)                 same module            ← a grep CANNOT find this
    from src import generate as g;  g.run(...)      ← aliased
    from . import generate   inside a function body ← deferred import

The last one matters in this repository specifically: `src/generate.py` imports
`generate_campaign` inside four separate function bodies, and `src/approve.py`,
`src/bisonfactory.py`, `src/heyreachfactory.py` and both provider modules do the
same. A top-of-file import scan would report those edges as absent.

Module-level statements are attributed to a synthetic `<module>` scope, so an
`if __name__ == "__main__": raise SystemExit(main())` block is a visible caller
rather than a silently dropped one. That is how finding 1 surfaced.

**`tests/` is parsed only under `--include-tests` and is reported separately.**
A test caller is never a production caller (invariant 0). Every number below is
from a run WITHOUT tests unless it says otherwise.

    modules parsed  545        call edges  19,787

### 1.1 The probe's own negative control

`scripts/p0d_entrypoint_probe.py` wraps `generate.run` in a spy and runs
`generate.main()`. A probe that cannot report "not called" is not a probe, so it
ships with `--negative-control`, which substitutes a `main()` that never calls
`run()`:

    normal run          generate.run() ENTERED  True
    --negative-control  generate.run() ENTERED  False

Both measured 2026-09-28. The False case is what licenses reading the True case
as evidence.

---

## 2. FINDING 1 — `generate.run` HAS A PRODUCTION CALLER

    CLAIM        generate.run has exactly one non-test caller in this
                 repository: generate.main(), the module's own CLI.
    AUTHORITY    scripts/p0d_callgraph.py --callers-of src.generate:run,
                 over src/ scripts/ tools/ with tests EXCLUDED
    MEASURED AT  2026-09-28
    STATE        VERIFIED

    == DIRECT CALLERS of src.generate:run ==
      src.generate:<module>      ← if __name__ == "__main__": SystemExit(main())
      src.generate:main          ← src/generate.py:2836

`src/generate.py:2780` defines `main(argv=None)`; line 2836 calls
`run(model=model, live=a.live, ids=a.ids, limit=a.limit, client=config, ...)`;
line 2889 binds it to `__main__`. So **`python -m src.generate --live` is a
caller of `generate.run`**, it is in git, it is not a harness, it is not a test,
and its own docstring in `run()` refers to it as the command an operator runs.

### 2.1 It executes — not merely reachable

    CLAIM        python -m src.generate executes against production-shaped
                 state, enters generate.run(), plans real records, and writes
                 nothing in its dry mode.
    AUTHORITY    scripts/p0d_entrypoint_probe.py, run against a COPY of
                 production work/ (1,582 records) redirected through
                 store.use_directory
    MEASURED AT  2026-09-28
    STATE        VERIFIED

      generate.main() exit code      0
      generate.run() ENTERED         True
      model class run() received     NoneType   (dry: run() builds NoModel)
      live kwarg                     False
      queue sha256 before/after      dd984f8a9e0d8508 / dd984f8a9e0d8508
      QUEUE UNCHANGED (zero writes)  True

It planned three real records and named real refusals — `linkedin_set`
regeneration on a `campaign_repetition` collision, and five `em1..em5` drafts
refused for `repetition_across_rungs`. That is the production gate set talking
about production data, which is what distinguishes an entrypoint from a stub.

**A copy, never the real `work/`.** The probe refuses to run if `--state`
resolves to the repository's own `work/`, and this worktree's `work/` does not
exist at all — the stale-worktree hazard the brief warned about. Production
`work/` was read once, to copy it, and never opened by the probe.

### 2.2 Why TASK-425 got this wrong, and why it is not carelessness

TASK-425's own words, `docs/TASK-425-FINDINGS-2026-09-28.md:142` on
`origin/task-425-one-account-dry-run` at `2d54e274`:

> ### 0h. `generate.run` has no production caller
> Worth stating beside every claim in this file about "the production
> entrypoint". Grepped: the only callers of `generate.run` in the repository are
> this task's harness and `tests/`.

The finding **names its instrument**: "Grepped". The instrument is the defect.
A grep for `generate.run` cannot match `run(...)` — the spelling of the call at
`src/generate.py:2836`. Reproduced both ways:

    grep -rn "generate\.run" src/           → src/llm.py (comments only)
    ast reverse call graph                  → src.generate:main

This belongs to the class invariant 0 was written for, and it is worth naming as
its own instance: **the identifier a caller uses is not the identifier the
callee is defined under, so absence under a qualified name is not absence.**
It is the same shape as "absence under a guessed identifier is never an
authority" — here the identifier was not guessed, it was simply not the only
one.

The second half of 0h is also imprecise. It says `generate.run` is "the one
`bisonfactory` and `heyreachfactory` consume the output of". They do not consume
its output: they re-read the record. Section 6.

### 2.3 The honest counter-argument, and why it does not rescue the claim

One could argue a module CLI is not a "real production entrypoint" — that the
deployed process is what counts, and that is `python -m src.web`. That argument
is available and it is worth stating, because **it is the strongest case for
TASK-425's conclusion even though its stated reason is wrong.** But it does not
survive the repository's own authority:

    CLAIM        src/store.py names the production entrypoints, and there are
                 two of them: python -m src.web and python -m src.run
    AUTHORITY    src/store.py:975, in store.under_test()'s docstring
    MEASURED AT  2026-09-28
    STATE        VERIFIED

> The production entry points - `python -m src.web`, `python -m src.run` - never
> import it.

That is load-bearing prose, not decoration: `under_test()` decides whether a
write is a test write. So the repository's own answer is that a module CLI IS a
production entrypoint — and by that standard `python -m src.generate` is one
too, being the same construction. Either way the conclusion holds, because
**`python -m src.run` reaches the generator as well** (section 4), and that one
is named explicitly.

---

## 3. PER-LINK VERDICT — LADDER RUNG, AUTHORITY, ENTRYPOINT

Measured with `scripts/p0d_callgraph.py --target`, tests excluded, 2026-09-28.
`YES` means reachable through the call graph from that entrypoint.

    link                  web.app    src.run    src.generate
    account               YES        YES        no
    research              no         YES        no
    qualification         YES        YES        no
    offer                 no         YES        YES
    strategy              no         YES        YES
    generation            no         YES        YES
    gate_copylint         no         YES        YES
    gate_sequencegate     no         YES        YES
    SequencePlan(new)     no         YES        YES
    proj_bison            no         no         no
    proj_heyreach         no         no         no
    proj_preview          no         no         no

**Rung per link. Not one rung for the chain — that is the thing §32 is asking
about and the thing a single verdict hides.**

| Link | Rung | Production entrypoint that drives it | Authority |
|---|---|---|---|
| account | PRODUCTION_ACTIVE | `python -m src.run`; also the web app | `account:graph`, `account:contacts_of` reached from both |
| research | PRODUCTION_ACTIVE | `python -m src.run` | `research:run`, `research:plan` reached |
| qualification | PRODUCTION_ACTIVE | `python -m src.run`; also the web app | `qualify:state_of`, `qualify:company` reached |
| offer selection | INTEGRATION_TESTED | `src.run`, `src.generate` | reached, but only inside `generate_campaign`; see 3.1 |
| strategy | INTEGRATION_TESTED | `src.run`, `src.generate` | `campaignstrategy:for_segment` reached via `_decide_strategy` |
| generation | PRODUCTION_ACTIVE | `python -m src.generate`, `python -m src.run --spend` | section 2.1 executed; section 4 static |
| gate: copylint | INTEGRATION_TESTED | both generation entrypoints | `copylint:check_batch` reached |
| gate: sequencegate | INTEGRATION_TESTED | both generation entrypoints | `sequencegate:check` reached — but see 3.2 |
| SequencePlan (`new`) | IMPLEMENTED | both generation entrypoints construct it | `sequenceplan:new` reached; its projections are dead (§6) |
| projection: EmailBison | **ABSENT as a wired link** | none — `bisonfactory.main` only | zero nodes reach both generation and it (§6.1) |
| projection: HeyReach | **ABSENT as a wired link** | none — `heyreachfactory.stage` only | same |
| projection: preview | **ABSENT** | none | `derive_preview_data` has zero callers |

I use ABSENT rather than IMPLEMENTED for the three projections deliberately.
The code exists and is IMPLEMENTED as code; **as a link in this chain it is
absent**, because no entrypoint traverses it. A rung describes the link, not the
file.

### 3.1 Why offer and strategy are INTEGRATION_TESTED and not higher

They are reached, and by a real entrypoint. I hold them one rung down because
neither is a pipeline stage an operator can run or inspect on its own: both
execute only inside `generate_campaign.generate`, so a strategy change cannot be
observed without a paid generation run. That is a statement about
observability, and it is why I did not certify them from a static edge.

`src/run.py:36` — `STAGES = ("enrich", "qualify", "personas", "generate",
"render", "push")` — carries no `account`, `research`, `offer` or `strategy`
stage. Those four run as side effects of other stages, which is why the table
above shows `research` reachable from `src.run` while no `research` stage
exists.

### 3.2 The sequence gate is reachable and, on a dry run, not reached

Recorded because it is already known and my measurement agrees with it rather
than adding to it. OPERATING-MODE, under LAUNCH BLOCKERS:

> `bisonfactory.stage()` returns before both `_refuse_copylint` and
> `_refuse_sequence_gate` when `live=False`, so a zero-write run never runs the
> sequence gate at all.

Static reachability says `sequencegate:check` is reachable. Reachable is not
executed, and on the `live=False` path it is not executed. **This is the exact
shape of the whole P0-D question one level down**, and it is why I report
reachability and execution as two different claims throughout. Not mine to fix.

---

## 4. `src.run` IS A SECOND DRIVER OF THE GENERATOR — AND NOT A SECOND GENERATOR

    CLAIM        src/run.py's generate stage calls generate.generate_record
                 directly, not generate.run.
    AUTHORITY    src/run.py:311, confirmed by the reverse call graph
    MEASURED AT  2026-09-28
    STATE        VERIFIED (static; this stage was not executed)

    == DIRECT CALLERS of src.generate:generate_record ==
      src.generate:run             ← the CLI path
      src.run:stage_generate       ← src/run.py:311, the batch path
      scripts.task065_measure, scripts.task065_run,
      scripts.task065_run_bcd, scripts.task197_generate   ← one-off scripts

So there are **two production drivers entering the generator at two different
depths**:

    python -m src.generate --live
      -> generate.main -> generate.run -> generate_record
           -> _generate_via_campaign -> generate_campaign.generate

    python -m src.run --spend
      -> run.run -> run.stage_generate -> generate_record
           -> _generate_via_campaign -> generate_campaign.generate

**This is NOT the "parallel generator" the brief forbids as a solution and asked
me to name if found.** Both reach the same `generate_campaign.generate` through
the same `_generate_via_campaign`. There is one copy engine. Entering it one
level lower is a different defect, and a smaller one.

### 4.1 What the lower entry actually skips

Read off `generate.run`'s body (`src/generate.py:2624-2727`) against
`run.stage_generate` (`src/run.py:274-322`). `run()` does four things its callee
does not:

1. `clear_company_cache()` at the start of the pass (TASK-162). `stage_generate`
   does not, so a `src.run` batch carries one company-evidence cache across
   every record in the run instead of per pass.
2. Refuses a live run with no model **before any record is touched**, by name,
   `llm.NoModelConfigured`. `stage_generate` instead branches to `plan()` when
   `model is None`, which is a reasonable different choice, not a defect.
3. Wraps each record in `store.transaction()` — and its own comment says why:
   *"so the evidence and history loss guards still run - durability bought by
   defeating them would be one loss traded for another."* **`stage_generate`
   does not open a transaction around the generate call.** It relies on
   `run.run`'s `checkpoint()`/`store.save` mechanism instead.
4. Counts ladder-stale steps and approvals that would be revoked, for the
   operator's impact report.

**Item 3 is the one worth a task.** Two write paths into the same records where
one runs the evidence and history loss guards per record and the other does not
is the "two answers to one question" shape, and the blunt one wins silently. I
did not verify behaviourally whether `run.run`'s checkpoint path reaches the
same guards — **that is UNKNOWN and I am not reporting it as clean.** It needs
its own measurement.

    CLAIM        run.stage_generate does not wrap generate_record in
                 store.transaction, while generate.run does
    AUTHORITY    src/run.py:274-322 and src/generate.py:2705-2718, read directly
    MEASURED AT  2026-09-28
    STATE        VERIFIED as a source difference.
                 UNPROVEN as a consequence — whether the guards are actually
                 bypassed was not measured.

---

## 5. THERE IS EXACTLY ONE GENERATOR — MEASURED, NOT ASSUMED

The brief asked me to name every place a second generation path exists. **There
is none, and this is the strongest good news in this document.**

    CLAIM        exactly one live function writes prospect-facing copy into a
                 record: _adapt_plan_to_cadence, via store_step.
    AUTHORITY    reverse call graph on src.generate:store_step, the only writer
                 into rec["cadence"], tests excluded
    MEASURED AT  2026-09-28
    STATE        VERIFIED

    == DIRECT CALLERS of src.generate:store_step ==
      src.generate:_adapt_plan_to_cadence     ← LIVE
      src.generate:draft                      ← dead, see below
      src.generate:linkedin_note              ← dead
      src.generate:_regenerate_linkedin_set   ← dead

And those last three have no callers at all:

    == DIRECT CALLERS of src.generate:draft ==                    NONE
    == DIRECT CALLERS of src.generate:linkedin_note ==            NONE
    == DIRECT CALLERS of src.generate:_regenerate_linkedin_set == NONE
    == DIRECT CALLERS of src.variantgen:generate ==               NONE

`generate.run`'s own comment claims this and the measurement agrees:

> THIS IS NOT A FALLBACK TO THE OLD WRITER. `plan()` enumerates what WOULD be
> asked; it generates no copy and never calls `draft()`, `linkedin_note()` or
> `_regenerate_linkedin_set()`.

**TASK-400 succeeded at the thing it was for.** The old three-writer stage
pipeline is retired, not shadowing. `variantgen.generate` is dead too.

Two qualifications, so this is not read as broader than it is:

- **Dead is not deleted.** Four functions that can write copy into a record
  remain callable in `src/generate.py`. They are a hazard to a future caller,
  not to a current run. Naming them is P0-B's business this round, not mine.
- `scripts/` holds four one-off drivers into `generate_record`
  (`task065_measure`, `task065_run`, `task065_run_bcd`, `task197_generate`).
  These are measurement scripts, not a pipeline, and they enter the one engine.

---

## 6. THE REAL BREAK — THE CANONICAL PROJECTION IS THE DEAD ONE

This is the finding that matters most, and TASK-425 did not look here.

`src/sequenceplan.py` opens by declaring itself the single truth:

> Preview, the XLSX workbook, the approval hash, the EmailBison payload and the
> HeyReach payload are projections of this plan. Each derives from it; none
> re-implements it.

Measured against that claim:

    CLAIM        the three functions that project the canonical plan's COPY
                 have zero callers, and they are the only callers of
                 sequenceplan.approval_hash.
    AUTHORITY    reverse call graph, tests excluded
    MEASURED AT  2026-09-28
    STATE        VERIFIED

    == DIRECT CALLERS of src.sequenceplan:derive_bison_payload ==     NONE
    == DIRECT CALLERS of src.sequenceplan:derive_heyreach_payload ==  NONE
    == DIRECT CALLERS of src.sequenceplan:derive_preview_data ==      NONE

    == DIRECT CALLERS of src.sequenceplan:approval_hash ==
      src.sequenceplan:derive_bison_payload      ← itself dead
      src.sequenceplan:derive_heyreach_payload   ← itself dead
      src.sequenceplan:derive_preview_data       ← itself dead

**`sequenceplan.approval_hash` is therefore never computed in production.** Its
only three callers are dead. That is the mechanical root cause of launch blocker
1 — "Approval hash not enforced: `require(campaign_id)` passes no hash at all
three call sites". The call sites pass no hash because **nothing produces one.**
I am not claiming this is the whole of blocker 1; I am claiming the hash
function has no live producer, and that is measured.

`src/generate_campaign.py:121` asserts the opposite in its own docstring —
"approval hash) derive from it via `sequenceplan.derive_*`". That sentence is
false in production. A doc saying "integrated" is not wiring (§4).

### 6.1 Nothing reaches both ends

    CLAIM        zero nodes in the repository reach both
                 generate_campaign.generate and a provider projection
                 (bisonfactory.stage or heyreachfactory.stage).
    AUTHORITY    full call graph, every node, both reachability sets computed
    MEASURED AT  2026-09-28
    STATE        VERIFIED

    NODES REACHING BOTH generation AND a provider projection:
       NONE

    reach generation only:      21 nodes
    reach a projection only:    16 nodes

    nodes reaching bisonfactory:stage, excluding scripts/:
       src.bisonfactory:main        ← its own CLI, and nothing else

`bisonfactory.stage` is driven by `bisonfactory.main` and by five one-off
scripts (`batch1_push`, `batch_preflight`, `repoint_to_all_mailboxes`,
`write_control_campaign`, `write_control_campaign_v3`).
`heyreachfactory.stage` is driven by `scripts/write_heyreach_sequence.py`
**and nothing in `src/` at all.**

### 6.2 How the copy actually reaches a provider payload, and why that is not a rescue

The data path is not severed — it runs through the store, which is canonical
(`CLAUDE.md`: "work/queue.jsonl holds record state ... those two files are the
only state"). Traced by reading:

    generate_campaign.generate
      -> sequenceplan.new(...)                  the canonical plan, in memory
      -> generate._adapt_plan_to_cadence        FLATTENS it into rec["cadence"]
                                                via store_step
      -> the plan object is then DISCARDED
         (only plan["stored_pairs"] is kept, as a return report)

    bisonfactory._plan
      -> _approved_copy(source, contact_key, ...)   re-reads rec["cadence"]
      -> lead["copy"]  ->  custom variables  ->  provider

**Joining through the store is architecturally legitimate.** The defect is not
the store. It is these three things:

1. **No single entrypoint spans the join**, so §4's test — "changing valid
   upstream information changes downstream production output through the real
   entrypoint" — cannot be exercised in one invocation. It takes two commands,
   in an order nothing enforces, with no freshness check between them.
2. **The canonical plan is write-only.** It is constructed, flattened and
   dropped. Nothing downstream ever sees the plan; everything re-derives from
   the flattened record. So a field that exists only on the plan reaches
   nothing, and `approval_hash` is exactly such a field.
3. **The payload is built three times, independently**, and the canonical
   fourth is the dead one. Section 6.3.

### 6.3 Every place a second projection exists — named, as asked

    CLAIM        four independent projections of the same copy exist, and the
                 canonical one is the only one with no callers.
    AUTHORITY    reverse call graph plus import inspection of src/push.py and
                 src/render.py
    MEASURED AT  2026-09-28
    STATE        VERIFIED

| # | Projection | Copy source | Driven by | State |
|---|---|---|---|---|
| 1 | `sequenceplan.derive_bison_payload` / `derive_heyreach_payload` / `derive_preview_data` | the canonical plan | **nothing** | **DEAD — 0 callers** |
| 2 | `bisonfactory._plan` → `_approved_copy` (+ `for_campaign`/`derive_bison_sequence` for the SHAPE) | `rec["cadence"]` | `bisonfactory.main`, 5 scripts | LIVE |
| 3 | `push.emailbison_rows` / `push.heyreach_rows` / `push.payloads` → `providers.bison`, `providers.heyreach` **directly** | `push.stored_step`, i.e. `rec["cadence"]` | `src.run` push stage, `push.main` | LIVE |
| 4 | `render.emailbison_rows` | render results | `src.run` render stage, `render.main` | LIVE |

Neither `src/push.py` nor `src/render.py` imports `sequenceplan` at all —
verified by reading their import blocks. Each carries its own
`emailbison_rows`, so there are **three functions named `emailbison_rows` or
equivalent in three modules**, none derived from the plan.

**One genuine piece of good news, and it is the half TASK-364 fixed.** The
plan's SHAPE half IS consumed correctly: `sequenceplan.for_campaign` →
`derive_bison_sequence` / `derive_heyreach_sequence` is called by
`bisonfactory._plan` and `heyreachfactory._plan`, exactly as the module
docstring requires, and `bisonfactory` retired its `sequence` key in favour of
`provider_sequence` to stop a write path reading an underived sequence. So
`sequenceplan.py` is half-wired: **the SHAPE flows, the WORDS do not.** That
distinction is the whole finding, and a single verdict on the module would hide
it in either direction.

### 6.4 `push` can reach a provider adapter directly — bounded, but named

`src/push.py` imports `providers.bison` and `providers.heyreach` directly and
builds payloads without `bisonfactory`, so it does not pass through
`bisonfactory`'s `_refuse_copylint`, `_refuse_sequence_gate` or the killswitch
gate at `_ensure_leads`.

**It cannot currently send, and the refusal is structural in three independent
places** — which is the right number, because the outer two are in the runner
and would not protect `push`'s own CLI:

    CLAIM        push.run refuses live=True unconditionally, at the top of the
                 function, before loading any record.
    AUTHORITY    src/push.py:492-498, read directly
    MEASURED AT  2026-09-28
    STATE        VERIFIED

    def run(day=21, live=False, ...):
        if live:
            raise LiveSendNotEnabled(
                "live push is not implemented in this build. ... No code here
                 can reach EmailBison or HeyReach.")

So `python -m src.push --live` is refused by `push.run` itself, not merely by
the runner — the refusal sits below `push.main`, so its own CLI inherits it.
`run.run()` and `run.stage_push` each raise the same exception independently.

I still report the projection as **bounded rather than safe**, for one narrower
reason: the bound is a `raise` in a build that "does not implement" live push,
not a gate that consulted the killswitch. `push.run` says so itself — it returns
`killswitch.state(...)` as a *report* and its comment explains that enforcement
"belongs to whatever sends". If live push is ever implemented here, the
killswitch and `bisonfactory`'s copylint and sequence gates do not come with it.
That is a note for whoever implements it, not an open question today.

---

## 7. THE DEPLOYED PROCESS REACHES NO GENERATION AT ALL

    CLAIM        the deployed entrypoint is python -m src.web, and it reaches
                 no generation function.
    AUTHORITY    Procfile, railway.json startCommand, and the call graph
    MEASURED AT  2026-09-28
    STATE        VERIFIED

    Procfile        web: python -m src.web --host 0.0.0.0 --port $PORT
    railway.json    "startCommand": "python -m src.web --host 0.0.0.0 ..."

    src.web.app:main    does NOT reach  -

Every `generate` hit in `src/web/` is report generation (`generate_report`,
`regenerate_report`, `"generated": bool(...)`) — the weekly client report, not
copy. `src/web/` never imports `src/generate.py`.

**A stale doc claim, recorded because it would mislead the next reader.**
`WEB-READINESS.md:541` shows:

    POST /api/batches/{id}/generate    generate.run(...)        [spends]

No such route exists. `src/web/app.py` has `/batches` and `/batches/`
(OPERATIONS_VIEW, read paths); there is no POST `.../generate` handler and no
call to `generate.run` anywhere in `src/web/`. `WEB-READINESS.md:24` carries the
same claim in a table. I did not edit those files — not mine, and the correction
belongs with whoever owns them.

So: `orchestrator`, `supervisor` and `jobs` also reach no generation
(measured). The only processes that generate copy are the two CLIs.

---

## 8. THE LADDER, HONESTLY, AND WHAT WOULD MOVE IT

| Claim | Rung | Why not the next rung up |
|---|---|---|
| `generate.run` has a production caller | **PRODUCTION_ACTIVE** | executed, dry, against production-shaped state, with a negative control |
| `src.run --spend` drives the generator | **INTEGRATION_TESTED** | static reachability only; running it costs credits |
| account → … → gates → `SequencePlan(new)` under one entrypoint | **INTEGRATION_TESTED** | every edge measured; no behavioural causal proof from me, and TASK-425's own causal matrix is MEASURED, NOT CERTIFIED |
| `SequencePlan` → provider projection | **ABSENT as a link** | zero nodes reach both ends |
| `approval_hash` computed in production | **ABSENT** | its only three callers are dead |
| one generator, no parallel path | **VERIFIED** | reverse graph on the sole writer, `store_step` |
| provider state | **UNKNOWN** | not read this round, by constraint. Not clean. |

**What would move the chain to LIVE_VALIDATED**, stated so it is not mistaken
for something my document delivered: one command, from a changed upstream fact
to a changed provider payload, with the payload read back and provider writes
proven zero by an interceptor proven to fire. Section 9 step 4 specifies it. It
was not run.

---

## 9. THE WIRING PLAN — **SPECIFIED, NOT APPLIED**

**NOTHING BELOW IS IMPLEMENTED. No file under `src/` was touched by P0-D.**
P0-B holds `src/generate.py` and `src/generate_campaign.py` this round; step 1
touches neither, and steps 2-4 must wait for P0-B to land regardless.

Ordered smallest-first. Each step is independently verifiable and none of them
is a TASK-425 adapter or a second generator.

### Step 1 — the smallest change that connects the chain (do this one first)

**Give the canonical plan a consumer, by making projection #2 read it.**

The join already works through the store, so the missing piece is not a new
pipeline — it is that the plan's COPY projections have no caller. One function
changes:

    src/bisonfactory.py, in _plan():
      replace   copy, missing = _approved_copy(source, contact.get("key"), ...)
      with      the copy read from sequenceplan.derive_bison_payload(plan),
                where `plan` is the canonical plan for this record

For that, the plan has to survive generation, which is step 2. So step 1 is
**strictly: add the persistence, then repoint one reader.** Do not repoint
first; a reader pointed at a plan nothing stored fails closed on every record
and looks like a cadence bug.

Files: `src/bisonfactory.py` only. **Not** `src/generate.py`,
**not** `src/generate_campaign.py` — P0-B's files stay untouched by step 1.

### Step 2 — persist the canonical plan (needs P0-B landed)

`_generate_via_campaign` currently flattens the plan and drops it. Store it
beside the record it belongs to, through `src/store.py`, never directly.

    src/generate.py, _generate_via_campaign, after _adapt_plan_to_cadence:
      persist `plan` (minus per-contact duplication already on the record)
      keyed by record id + generation_stamp

Two constraints that are not negotiable:

- **Through `store.py`.** A new state file gets a `STATE_OVERRIDES` entry in the
  same change, or a test will write it into the real `work/`. That tuple in
  `src/store.py:95` exists because this has happened repeatedly.
- **The flattening stays.** `rec["cadence"]` remains the canonical record state
  and `store_step` remains the only writer, because `store_step` carries the
  approval-history rule and bypassing it "silently deleted seventy-two audit
  records once already" (`_adapt_plan_to_cadence`'s own docstring). Step 2 ADDS
  a durable plan; it does not move the copy off the record.

Files: `src/generate.py`, `src/store.py`. **Conflicts with P0-B — sequence
after it.**

### Step 3 — one entrypoint that spans the join

Add a projection stage to `src/run.py` so a single command traverses generation
→ projection:

    src/run.py:36
      STAGES = ("enrich", "qualify", "personas", "generate", "render",
                "prepare_campaign", "push")

    new stage_prepare_campaign(recs, live=False, notes=...):
      calls bisonfactory.stage(..., live=False)

**Two things this must not do.** It must not raise the dry-run/sequence-gate
question OPERATING-MODE already has open (§3.2 above) — the stage inherits
whatever `stage()` does with `live=False`, and fixing that is a different task
with a different owner. And it must not become a send path: `live` stays
plumbed from `--live`, which `run.run` already refuses.

Files: `src/run.py`. Independent of P0-B.

### Step 4 — the acceptance test, which is the actual deliverable

None of steps 1-3 is proof. The test, in the form §4 and §0b require:

1. **A/A2 control first.** Same account, same inputs, twice, through the new
   single entrypoint. The provider payload must be byte-identical. **A control
   that fails open is not a control** (§0b) — assert equality, and assert the
   checker can report inequality.
2. **Then the causal run.** Change one upstream fact. Assert the **provider
   payload** changes — not the record, not the plan, the payload. That is the
   §4 test and nothing weaker substitutes.
3. **A killed mutation.** Break the new plan→payload read; the intended test
   goes red for the intended reason; restore the source and verify it is
   byte-identical.
4. **Provider writes = 0**, by an interceptor **proven to fire** — a zero from
   an interceptor that never triggered is column three of the authority
   registry, not evidence.

Files: one new `tests/test_*.py`. Name it for the behaviour, not the task
number.

### What this plan deliberately does NOT do

- **No TASK-425 adapter.** Nothing makes the harness look like production. The
  harness is not mentioned in any step.
- **No second generator.** Step 1 repoints a READER. No step adds a path that
  writes copy.
- **No new cadence, no widened gate, no relaxed refusal.** Step 3 inherits the
  existing `live=False` behaviour rather than improving it, precisely so that
  the open sequence-gate question stays one question with one owner.
- **Projections 3 and 4 are not consolidated.** `push` and `render` keep their
  own row builders for now. Retiring them is real work with real blast radius
  and it belongs in `docs/BACKLOG.md`, not smuggled into a wiring fix.

---

## 10. CONSTRAINT COMPLIANCE

    READ-ONLY on src/          HELD — git status shows no src/ file modified
    provider writes = 0        HELD — no provider module imported, no socket
    no provider reads          HELD — none attempted, so provider state is
                               UNKNOWN in this document, never clean
    no merge to master         HELD
    no Slack post              HELD
    files owned only           docs/P0D-PRODUCTION-CALLER-2026-09-28.md,
                               scripts/p0d_callgraph.py,
                               scripts/p0d_entrypoint_probe.py
    forbidden files untouched  tests/task425fixture.py, docs/TASK-425-*,
                               docs/OPERATING-MODE.md, docs/SEND-LEDGER-*,
                               docs/CROSS-CHANNEL-STOP-*, docs/TEN-ACCOUNT-*,
                               docs/P0A-*, docs/P0B-*, docs/P0C-*
    stale worktree work/       AVOIDED — this worktree has no work/ at all; the
                               probe used a COPY of production's, and refuses
                               to run against the real one

Both probe scripts are read-only by construction: `p0d_callgraph.py` parses with
`ast` and imports nothing from `src`; `p0d_entrypoint_probe.py` imports `src`
but runs only the dry path and asserts the queue's sha256 is unchanged
afterwards.

---

## 11. WHAT THE NEXT SESSION SHOULD NOT RE-DERIVE

- `generate.run` **has** a production caller. Do not re-grep for it; use
  `scripts/p0d_callgraph.py --callers-of src.generate:run`.
- There is **one** generator. `generate.draft`, `generate.linkedin_note`,
  `generate._regenerate_linkedin_set` and `variantgen.generate` are dead.
- The break is `SequencePlan → projection`, and `approval_hash` has no live
  producer. That is where the work is.
- `src/web/` reaches no generation. `WEB-READINESS.md:24` and `:541` claim a
  route that does not exist.
- `push` cannot send: `push.run` refuses `live=True` at its first statement, so
  `python -m src.push --live` is refused too. Measured, not inferred.
- Provider state was not read here. Anything this document says about a provider
  is UNKNOWN, which is not a PASS.

---

## 12. THE ONE-LINE HANDOFF

**The generation path is wired and TASK-425's grep was the wrong instrument.
The chain breaks one link later, at `SequencePlan → projection`, where the
canonical projection has zero callers and `approval_hash` has no live producer.
The wiring for that break is specified in section 9 and IS NOT APPLIED.**
