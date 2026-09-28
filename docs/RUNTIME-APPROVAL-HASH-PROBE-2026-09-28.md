# RUNTIME VERIFICATION OF THE APPROVAL-HASH FINDING

**Measurement only. No file under `src/` was changed, no provider was written
to, and nothing here is a fix.** The wiring belongs to `P0-E`
(`docs/BRIEF-P0E-CANONICAL-PROJECTION-INTEGRATION.md`), which is on master and
is not mine.

    task            runtime verification of the approval-hash finding
    branch          task-runtime-approval-hash-probe
    worktree base   8eabef9cd13dbd2b25300ed98a0920af55359957
    origin/master   388c226b872cf5c06e52fe759126c69bb97c2816 (derived, see 0.2)
    verifies        docs/P0D-PRODUCTION-CALLER-2026-09-28.md
                    branch task-p0d-production-caller, head 01dd7b78
    measured        2026-09-28
    provider writes 0 — interceptor ledger, interceptor proven to fire
    files added     docs/RUNTIME-APPROVAL-HASH-PROBE-2026-09-28.md
                    scripts/runtime_approval_hash_probe.py
    files changed   none under src/, tests/, or any doc owned by another task

---

## 0. THE ANSWER IN ONE PAGE

**RUNTIME AGREES WITH THE STATIC GRAPH. On every one of the five points, and
with no discrepancy of any kind between the two instruments used here.**

The outcome the operator wrote down in advance, and the outcome measured:

    question                 EXPECTED        MEASURED       instrument A / B
    generator                ENTERED         ENTERED        1 / 1
    SequencePlan             CREATED         CREATED        1 / 1
    canonical projection     NOT ENTERED     NOT ENTERED    0 / 0
    approval hash            NOT ENTERED     NOT ENTERED    0 / 0
    provider writes          0               0              interceptor fired

**`sequenceplan.approval_hash` was not entered once by a production entrypoint
that ran the whole generation chain to completion, and not once by the
production entrypoint that builds the EmailBison payload.** P0-D's conclusion
stands, and it now stands on entry counts rather than on edges.

### 0.1 The three things this adds that a call graph could not

1. **The chain EXECUTED, it was not merely reachable.** `generate.run` →
   `generate_record` → `_generate_via_campaign` → `generate_campaign.generate`
   → `sequenceplan.new` → `_adapt_plan_to_cadence`: every one entered exactly
   once, in one invocation of `generate.main()`, on copied production input.
   The plan was built and consumed, and the projections were still never
   entered. Section 3.

2. **The projection half was run too, and the live builder was caught in the
   act.** `python -m src.bisonfactory <campaign>` dry: `sequenceplan.
   for_campaign` ENTERED (1), `derive_bison_sequence` ENTERED (1),
   `bisonfactory._approved_copy` ENTERED **4 times** — and
   `derive_bison_payload` and `approval_hash` ENTERED **0** times in the same
   run. **The words of four provider steps were assembled from
   `rec["cadence"]` while the canonical projection that is supposed to
   assemble them was never called.** That is P0-D's "half-wired: the SHAPE
   flows, the WORDS do not" as a behaviour rather than a reading. Section 4.

3. **Every NOT ENTERED carries a control that fired.** The four tracers that
   report zero are each made to report non-zero, deliberately, in a separately
   labelled control phase, and the provider interceptor is fired against the
   real EmailBison host. Section 5.

### 0.2 Authority for the SHAs in this document

    CLAIM        origin/master is 388c226b, not 8eabef9c
    AUTHORITY    git rev-parse origin/master, after git fetch origin
    MEASURED AT  2026-09-28, this session, after the measurement runs
    STATE        VERIFIED

My brief gave `origin/master = 8eabef9c` as ground truth. It was correct when
the brief was written and was stale by the time I finished — master moved
twice (`3b295ded`, then `388c226b`). This is the second consecutive task to
find its own brief's SHA stale; per invariant 0a the authority is the remote
after a fetch, never a SHA in prose, **including the one in this document.**

    CLAIM        the src/ I measured is byte-identical to the src/ P0-D
                 measured, AND to the src/ on current origin/master
    AUTHORITY    git diff --stat 01dd7b78 HEAD -- src/       (empty)
                 git diff --stat 8eabef9c origin/master -- src/ (empty)
    MEASURED AT  2026-09-28
    STATE        VERIFIED

This matters more than it looks. It means the runtime result and the static
result are two instruments pointed at **the same bytes**, so an agreement
between them is about the system and not about two different versions of it.
It also means **P0-B has not landed**: the two commits master gained are
documentation only (`CLAUDE.md`, `WEB-READINESS.md`, the evening handoff, the
P0-E brief, `OPERATING-MODE.md`).

---

## 1. METHOD — TWO INSTRUMENTS, BECAUSE ONE CANNOT DISAGREE WITH ITSELF

`scripts/runtime_approval_hash_probe.py`. It records ENTRY, not reachability,
and it records it twice, independently:

**Instrument A — wrappers.** Each target is replaced by a counting wrapper on
its module attribute. Module attribute assignment is module *global*
assignment, so this also catches a bare same-module call — which matters here
specifically, because `derive_bison_payload` calls `approval_hash(plan)`
unqualified, inside `sequenceplan.py`.

**Instrument B — a code-object profiler.** `sys.setprofile` (and
`threading.setprofile`) records a `call` event whose `frame.f_code` is one of
the ORIGINAL target code objects, captured **before** the wrappers were
installed. This instrument does not know or care how the call was spelled: a
bare name, an alias, a deferred import inside a function body, a reference
bound to a local. **That spelling-blindness is the exact defect that made
TASK-425's grep wrong**, and instrument B exists so that this probe cannot
repeat it in a new form.

The probe prints both columns for every target and **exits non-zero if they
disagree**. They did not disagree, anywhere, in any run.

### 1.1 What is instrumented

    generate.run                            the generator entry
    generate.generate_record
    generate._generate_via_campaign
    generate._adapt_plan_to_cadence         the plan -> record flattening
    generate_campaign.generate              the single versioned entrypoint
    sequenceplan.new                        the canonical plan
    sequenceplan.approval_hash              THE QUESTION
    sequenceplan.derive_preview_data        THE QUESTION
    sequenceplan.derive_bison_payload       THE QUESTION
    sequenceplan.derive_heyreach_payload    THE QUESTION
    sequenceplan.for_campaign               the SHAPE half
    sequenceplan.derive_bison_sequence      the SHAPE half
    bisonfactory._plan                      the live projection
    bisonfactory._approved_copy             the live WORDS builder

### 1.2 The entrypoints used — real CLIs, not a harness

    python -m src.generate --live --client productive --regenerate-whole-set
                           --id 16kagency-com
    python -m src.bisonfactory <campaign id>            (dry, no --live)

Both are driven through their own `main()`, which is how P0-D established the
question. No function under test is called directly by the probe except in the
clearly separated CONTROL phase.

---

## 2. WHAT THIS DOES NOT PROVE — STATED BEFORE THE EVIDENCE

- **THE MODEL IS A LOCAL STUB, AND THIS IS THE MATERIAL DEVIATION.**
  `generate.main()` builds a model only under `--live`, via `llm.from_env()`.
  A real model call on a measurement run is real credit spend, so
  `LLM_BASE_URL` / `LLM_API_KEY` / `LLM_MODEL` were pointed at a loopback
  server speaking `/chat/completions`. **Configuration was redirected; no code
  was changed.** The stub supplies CONTENT. It does not decide whether
  `derive_*` is called — there is no branch anywhere that calls a projection
  conditionally on copy quality — but the honest statement is that this run
  proves the chain for a run whose model answers were synthetic.
  **STATE: the model path is UNPROVEN against a real model here. The control
  flow is VERIFIED.**
- **One record and one campaign, not the estate.** `16kagency-com`
  (1 contact) and one constructed campaign carrying 3 records. A different
  record cannot call a function that has no call site, but I measured three
  records' worth of copy assembly, not 1,582.
- **The copy did not pass the gates**, so the generation run stored nothing
  (`nothing to generate`). `_adapt_plan_to_cadence` still entered, so the plan
  was consumed; but a run in which the gates PASSED and copy was stored was
  not measured on the generation side. **Section 4 covers that gap from the
  other end**, by running the projection against records whose cadence already
  carries five stored email steps.
- **No provider state was read.** Every provider question in this document is
  **UNKNOWN**, per §26, never clean.
- **I did not re-derive the call graph.** P0-D's static work is not repeated;
  it is verified by a different instrument against identical bytes.

---

## 3. THE GENERATION HALF — MEASURED

    CLAIM        python -m src.generate --live enters the generator, builds a
                 canonical SequencePlan, flattens it onto the record, and
                 enters neither the canonical projection nor the approval hash.
    AUTHORITY    scripts/runtime_approval_hash_probe.py, both instruments,
                 against a COPY of production work/ (1,582 records)
    MEASURED AT  2026-09-28
    STATE        VERIFIED

    CLI      python -m src.generate --live --client productive
                                    --regenerate-whole-set --id 16kagency-com
    exit     0
    model    8 calls, all to 127.0.0.1 (the stub)

    target                                  wrapper profiler
    generate.run                                  1        1
    generate.generate_record                      1        1
    generate._generate_via_campaign               1        1
    generate._adapt_plan_to_cadence               1        1
    generate_campaign.generate                    1        1
    sequenceplan.new                              1        1
    sequenceplan.approval_hash                    0        0
    sequenceplan.derive_preview_data              0        0
    sequenceplan.derive_bison_payload             0        0
    sequenceplan.derive_heyreach_payload          0        0

    first call to generate.run       live=True model=OpenAICompatibleModel
    first call to sequenceplan.new   client='Productive' account='16kagency.com'

Two details worth reading carefully, because each answers an objection:

- **`live=True` and a real `OpenAICompatibleModel`.** This is not the dry
  `NoModel`/`plan()` branch P0-D's own probe exercised. That branch never
  reaches `generate_record` at all, so it could not have answered the
  SequencePlan question. This run took the live branch, through
  `store.transaction()`, into the campaign pipeline.
- **`_adapt_plan_to_cadence` entered.** The plan was not built and abandoned
  before anything could consume it: the production consumer of the plan ran.
  It flattened the words onto `rec["cadence"]` and the plan object was then
  dropped, exactly as P0-D read off the source. **The projections had a plan
  available and were still not called, because nothing calls them.**

---

## 4. THE PROJECTION HALF — WHERE THE PAYLOAD IS ACTUALLY BUILT

This is the half a call graph can only describe and a run can demonstrate.

    CLAIM        python -m src.bisonfactory <campaign> (dry) builds the
                 EmailBison payload's WORDS four times through
                 bisonfactory._approved_copy, reading rec["cadence"], and
                 enters sequenceplan.derive_bison_payload and
                 sequenceplan.approval_hash zero times.
    AUTHORITY    scripts/runtime_approval_hash_probe.py --mode project,
                 both instruments
    MEASURED AT  2026-09-28
    STATE        VERIFIED

    CLI      python -m src.bisonfactory PROBE-CONSTRUCTED-em1-em5   (no --live)
    exit     0        printed: "dry run: nothing was sent"

    target                                  wrapper profiler
    sequenceplan.for_campaign                     1        1   <- SHAPE, wired
    sequenceplan.derive_bison_sequence            1        1   <- SHAPE, wired
    bisonfactory._plan                            1        1
    bisonfactory._approved_copy                   4        4   <- WORDS, LIVE
    sequenceplan.derive_bison_payload             0        0   <- WORDS, DEAD
    sequenceplan.derive_heyreach_payload          0        0
    sequenceplan.derive_preview_data              0        0
    sequenceplan.approval_hash                    0        0

**Read those eight rows together and the §5 "one truth" violation is no longer
an inference.** In a single invocation, the canonical plan's SHAPE projection
was entered and its WORDS projection was not, while a second, independent
words builder ran four times beside it.

### 4.1 The constructed input, labelled rather than hidden

`PROBE-CONSTRUCTED-em1-em5` is **not a production campaign row.** It is a
clone of `productive-email-control-v2`, written into the COPY only, with two
changes:

- `record_ids` set to three records whose cadence already carries all five
  stored email steps (`ogpartner-dk`, `nineyards-ie`, `16kagency-com`);
- `cadence_steps` taken from `cadencelibrary.named("productive_li_heavy_v1")`
  — the canonical library, which OPERATING-MODE names as correct.

**Why it was needed, and it is not a workaround for my probe.** Every
production campaign row that has `record_ids` also carries a **stale
three-step** cadence declaration, and every row carrying the canonical five
has **no members**. Measured on the copy, 2026-09-28:

    productive-email-control-v2   cadence_steps em1,em2,em3    record_ids 10
    productive-uscold-*-20260925  cadence_steps em1..em5       record_ids 0

So the real rows refuse at `_require_declared_cadence` before `_plan` can
reach `_approved_copy` — reproduced, with the refusal text:

> ``FactoryRefused: `email_sequence.steps` declares ['em1'..'em5'] and the
> cadence's email steps are ['em1','em2','em3'].``

That is **launch blocker 9** doing exactly what OPERATING-MODE says it does,
observed at runtime rather than quoted. It is not mine to fix and I did not
change it; the constructed row routes around it so the question this task was
given could be answered. **Only the MEMBERSHIP is constructed. The cadence
declaration is the canonical library's own and the copy is production's own.**

Two further runs are recorded for completeness, both with the real rows:

    productive-uscold-useast-20260925 (real, 0 members)
      for_campaign 1 · derive_bison_sequence 1 · _plan 1 · _approved_copy 0
      derive_bison_payload 0 · approval_hash 0        exit 0
    productive-email-control-v2 (real, 10 members, 3-step declaration)
      for_campaign 1 · derive_bison_sequence 1 · _plan 1 · _approved_copy 0
      derive_bison_payload 0 · approval_hash 0        exit 1, FactoryRefused

`derive_bison_payload` and `approval_hash` are zero in all three.

### 4.2 One thing OPERATING-MODE says that is now stale

OPERATING-MODE, under LAUNCH BLOCKERS: *"`bisonfactory.stage()` returns before
both `_refuse_copylint` and `_refuse_sequence_gate` when `live=False`, so a
zero-write run never runs the sequence gate at all."*

**That is no longer true of the source on master.** `stage()`'s own comments
now say the dry-run return was moved below both gates, for the operator's
stated reason, and the constructed dry run above reached `_plan` and
`_approved_copy` and printed `dry run: nothing was sent` after the gates rather
than before them. I did not measure the gates' refusal behaviour itself, so:

    CLAIM        the dry-run early return no longer sits above the copylint
                 and sequence gates in bisonfactory.stage
    AUTHORITY    src/bisonfactory.py:104-150 read directly, plus a dry run
                 that reached _approved_copy
    MEASURED AT  2026-09-28
    STATE        VERIFIED as a source and reachability change.
                 UNPROVEN that a bad sequence is now REFUSED on a dry run —
                 that needs its own negative test and is TASK-425's criterion
                 3, not mine.

Recorded because a stale blocker entry sends the next reader to a problem that
has moved. The correction belongs to whoever owns `docs/OPERATING-MODE.md`.

---

## 5. THE CONTROLS — WITHOUT THESE, EVERY ZERO ABOVE IS UNKNOWN

### 5.1 Negative control: the tracers can report NOT ENTERED

`--negative-control` replaces `main()` with a stub that calls nothing.

    target                                  wrapper profiler
    (all fourteen)                                0        0

    generator                NOT ENTERED
    SequencePlan             NOT CREATED
    canonical projection     NOT ENTERED
    approval hash            NOT ENTERED

**STATE: VERIFIED.** The False case is what licenses reading section 3's True
cases as evidence.

### 5.2 Positive control: the four zero-reporting tracers can report ENTERED

After the measured phase is frozen, the probe calls all four directly, on the
plan the production run actually built:

    target                                  wrapper profiler
    sequenceplan.derive_preview_data              1        1
    sequenceplan.derive_bison_payload             1        1
    sequenceplan.derive_heyreach_payload          1        1
    sequenceplan.approval_hash                    4        4

    returns: three dicts, and approval_hash = f90411ee0437951f

**Read the 4 on `approval_hash`.** Three of those four are the *bare,
same-module* `approval_hash(plan)` calls inside the three `derive_*`
functions, plus one direct call. **That is the spelling a qualified-name grep
cannot see**, and both instruments caught all four. So the zero in sections 3
and 4 is a measured absence of entry, not a measurement that was blind to the
spelling the call uses.

    CLAIM        the approval-hash tracer detects the bare same-module call
                 spelling, which is the spelling production would use
    AUTHORITY    control phase, 4 recorded entries against 4 expected
    MEASURED AT  2026-09-28
    STATE        VERIFIED

### 5.3 Positive control: the provider-write interceptor fires on the real host

A deliberate `POST` to the real EmailBison base, `providers.bison.base()`:

    deliberate write   POST https://send.resonategroup.co/api/leads
    recorded           True
    outcome            ProviderWriteRefused - "a mutating provider call with
                       no explicit authorization (no RESONATE_PROVIDER_WRITES
                       and no allow_writes() scope)"
    socket opened      none

**The refusal came from production's own guard, not from the probe's.** The
interceptor calls `providers.refuse_unauthorized_write(method, url)` before
deciding anything itself, precisely so the real guard is exercised rather than
bypassed; the probe's own refusal sits behind it and was not needed.

    CLAIM        provider writes during the measured phases = 0, from an
                 interceptor proven to fire against the real host
    AUTHORITY    the interceptor ledger at providers.request's single
                 transport chokepoint, plus a socket-level guard
    MEASURED AT  2026-09-28
    STATE        VERIFIED

    provider calls, generation run    8, all to 127.0.0.1 (the model stub)
    provider calls, projection runs   0
    non-loopback socket connects      0
    prospect-facing writes            0

---

## 6. THE PRODUCTION STORE WAS NOT TOUCHED

    CLAIM        work/queue.jsonl and work/campaigns.jsonl in the production
                 checkout are byte-identical before and after all runs
    AUTHORITY    sha256 from a FRESH PROCESS either side (pid 94920, pid 88720)
    MEASURED AT  2026-09-28
    STATE        VERIFIED

    queue.jsonl      before dd984f8a9e0d85082c36bd7912d7798c926867085342ca4096da069be08caee2
                     after  dd984f8a9e0d85082c36bd7912d7798c926867085342ca4096da069be08caee2
    campaigns.jsonl  before ca7189676232c772a5f5d44a520ed154b5fcecfd09eaa944097b404b73dea370
                     after  ca7189676232c772a5f5d44a520ed154b5fcecfd09eaa944097b404b73dea370

**A hash comparison is weak evidence on a file 23 loops write, so it is not
the primary instrument here.** The primary instrument is a write guard:
`builtins.open` is wrapped for the whole run and REFUSES, by name, any
write-mode open of a path under any `work/` directory that is not the copy.
Zero such attempts occurred in any measured phase.

    forbidden work/ write attempts, MEASURED phases    0
    forbidden work/ write attempts, CONTROL phase      1  (see 6.1)

The store itself was redirected with `store.use_directory(<copy>)`, and the
probe refuses to start if `--state` resolves to the production `work/`, to the
worktree's own `work/`, or to any directory named `work`.

**The worktree has no `work/` of its own** — the stale-worktree hazard the
brief warned about did not arise, and `WORKSPACES` moved with the copy because
`use_directory` clears it, with `work/workspaces.jsonl` copied in.

### 6.1 Incidental finding — one state file does NOT move with `use_directory`

The single refused write is worth reporting rather than filtering out.

    CLAIM        providers._log_refusal writes to
                 <repo>/work/provider-write-refusals.jsonl regardless of
                 store.use_directory, because PROVIDER_WRITE_REFUSALS is not
                 in store.STATE_OVERRIDES
    AUTHORITY    src/providers/__init__.py:714-716, and the probe's write
                 guard catching the attempt at runtime
    MEASURED AT  2026-09-28
    STATE        VERIFIED

    path attempted   <worktree>/work/provider-write-refusals.jsonl
    override read    PROVIDER_WRITE_REFUSALS
    in STATE_OVERRIDES?  no  (grep -c in src/store.py -> 0)

**Why `tests/test_invariants.py` cannot see it, which is the more useful half.**
`test_every_state_override_is_in_the_move_together_set` only treats an
override as state when the 200 characters after it contain `queue_path()`.
This one falls back to `os.path.join(ROOT, "work", ...)` instead, so the
invariant test passes and is blind to it by construction. That is the same
shape as everything invariant 0 exists for: a green test that cannot fail for
this case.

The consequence is bounded — a refusal *log* line, not row state — but it is
the class of defect the `STATE_OVERRIDES` comment was written about, and a
test writing into a real `work/` is how it gets discovered expensively. Not
mine to fix; recorded here and worth a task.

---

## 7. AGREEMENT OR DISAGREEMENT — THE ANSWER THE BRIEF ASKED FOR

**RUNTIME AGREES WITH THE STATIC GRAPH.** Every P0-D claim in scope was
confirmed by a different instrument against identical source bytes:

| P0-D claim | Runtime |
|---|---|
| `generate.run` has a production caller, `generate.main` | AGREES — entered, `live=True`, real model object |
| `generate_campaign.generate` is the single versioned entrypoint reached from it | AGREES — entered once via `_generate_via_campaign` |
| the canonical `SequencePlan` is built | AGREES — `sequenceplan.new` entered once |
| the plan is flattened and discarded | AGREES — `_adapt_plan_to_cadence` entered; no projection followed |
| `derive_bison_payload` / `derive_heyreach_payload` / `derive_preview_data` have no live caller | AGREES — 0 entries across four runs on two entrypoints |
| `approval_hash` is never computed in production | AGREES — 0 entries; tracer proven to catch its bare same-module spelling |
| the SHAPE half IS wired (`for_campaign` → `derive_bison_sequence`) | AGREES — both entered in the projection run |
| the payload's WORDS are rebuilt independently by `bisonfactory` | AGREES — `_approved_copy` entered 4 times in the same run |
| no single entrypoint spans generation and projection | AGREES — two CLIs, disjoint target sets, neither touched the other's |

**No discrepancy was found, between the two instruments or between runtime and
the graph.** Had one appeared, this document would say so and stop; the probe
exits non-zero on instrument disagreement precisely so a discrepancy cannot be
quietly smoothed over.

### 7.1 What this changes for launch blocker 1 and for P0-E

    CLAIM        "approval hash not enforced" has a mechanical root cause that
                 is now confirmed at runtime: no production entrypoint
                 computes one.
    AUTHORITY    this document, sections 3, 4 and 5
    MEASURED AT  2026-09-28
    STATE        VERIFIED

`require(campaign_id)` passing no hash at its three call sites is a *symptom*.
The producer is absent, so there is nothing for a call site to pass. **P0-E's
acceptance items 1 and 2 are therefore the right shape, and the ladder rung for
`SequencePlan → provider projection` is ABSENT AS A LINK, confirmed twice by
two instruments — not IMPLEMENTED, not INTEGRATION_TESTED.**

The reusable measurement for P0-E's proof: `--mode project` on this probe
already asserts exactly what item 2 needs. When the wiring lands, the same
command must show `derive_bison_payload ≥ 1`, `approval_hash ≥ 1`, and
`bisonfactory._approved_copy == 0`. **That last one is the half a passing
integration test would miss**, because a new caller can be added while the old
builder keeps running beside it, and the run would look wired.

---

## 8. THE LADDER, HONESTLY

| Claim | Rung | Why not the next rung up |
|---|---|---|
| `generate.main` → `generate.run` → `SequencePlan` executes | **INTEGRATION_TESTED** | executed end to end through the real CLI on copied production input, with a negative control — but with a STUB MODEL, so it is not LIVE_VALIDATED |
| `approval_hash` is not computed in production | **VERIFIED as an absence** | two instruments, two entrypoints, four runs, with the tracer proven to fire on the bare spelling |
| the canonical projections have no live caller | **VERIFIED as an absence** | same |
| the SHAPE half is wired | **INTEGRATION_TESTED** | entered in a real dry run; no causal proof that changing the plan's shape changes the payload |
| `bisonfactory._approved_copy` is the live words builder | **VERIFIED** | entered 4 times while the canonical one entered 0 |
| provider writes = 0 | **VERIFIED** | interceptor ledger, interceptor fired against the real host, socket guard at 0 |
| production `work/` untouched | **VERIFIED** | write guard at 0 in every measured phase, plus fresh-process sha256 either side |
| a bad sequence is refused on a dry run | **UNKNOWN** | not measured; TASK-425 criterion 3, different owner |
| provider state | **UNKNOWN** | not read. Not clean. |

**A test count is not a PASS and no test count appears in this document.**

---

## 9. WHAT THE NEXT SESSION SHOULD NOT RE-DERIVE

- The approval hash is **not computed in production**, confirmed statically
  (P0-D) and at runtime (here), against identical source bytes. Do not measure
  it a third time; measure it again only when P0-E's wiring lands, with
  `scripts/runtime_approval_hash_probe.py --mode project`.
- `python -m src.generate --live` **does** run the whole chain into
  `sequenceplan.new`. The dry `NoModel` branch does not reach
  `generate_record` at all, so a probe that omits `--live` cannot answer the
  SequencePlan question — P0-D's probe was dry and correctly claimed less.
- The stored campaign rows are split: those with members declare three email
  steps and refuse at `_require_declared_cadence`; those declaring five have
  no members. That is launch blocker 9, reproduced, and it blocks any
  end-to-end projection run on a real row today.
- `bisonfactory.stage()` no longer returns above the copylint and sequence
  gates on `live=False`. The OPERATING-MODE blocker text saying it does is
  stale.
- `PROVIDER_WRITE_REFUSALS` does not move with `store.use_directory`, and the
  invariant test cannot see it.
- Provider state was not read here. Anything about a provider is UNKNOWN.

---

## 10. CONSTRAINT COMPLIANCE

    READ-ONLY on src/           HELD — git status shows no src/ file modified
    no edits to generate.py     HELD — P0-B's two files untouched
    provider writes = 0         HELD — interceptor ledger, interceptor fired
    COPIED production input     HELD — store.use_directory(<copy>); the probe
                                refuses the real work/ by path and by name
    production work/ unchanged  HELD — write guard 0 in every measured phase;
                                fresh-process sha256 identical either side
    WORKSPACES not stale        HELD — moved with the copy; workspaces.jsonl
                                copied in; this worktree has no work/ at all
    no merge to master          HELD
    no Slack post               HELD
    files owned only            docs/RUNTIME-APPROVAL-HASH-PROBE-2026-09-28.md
                                scripts/runtime_approval_hash_probe.py
    forbidden files untouched   src/ entirely, tests/task425fixture.py,
                                docs/P0A-*, docs/P0B-*, docs/P0C-*, docs/P0D-*,
                                docs/OPERATING-MODE.md, docs/SEND-LEDGER-*,
                                docs/CROSS-CHANNEL-STOP-*, docs/TEN-ACCOUNT-*,
                                docs/PERMANENT-OPERATOR-EXCLUSION-*,
                                docs/CREDENTIAL-EXPOSURE-*

One deviation, declared rather than buried: **the model was a loopback stub**,
for the reason in section 2. No credential was printed, and the stub's key is
the literal string `probe-stub-not-a-credential`.

---

## 11. THE ONE-LINE HANDOFF

**Runtime AGREES with the static graph. Through the real CLI, on copied
production input: the generator ENTERED, a canonical SequencePlan CREATED and
consumed, the canonical projection NOT ENTERED, `approval_hash` NOT ENTERED,
provider writes 0 — and in the same repository the EmailBison payload's words
were assembled four times by `bisonfactory._approved_copy` while the canonical
projection that should assemble them was never called. Every zero carries a
control that fired.**
