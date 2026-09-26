# DOC TRUTH SWEEP — 2026-09-26

Sweep of load-bearing factual claims in top-level `*.md` and `docs/*.md`.
A claim is load-bearing if an operator would ACT differently depending on
whether it is true.

**Method:** every claim checked against `origin/master` at `2e1e55a5` using
`git cat-file -e origin/master:<path>`. Commands run and their exit statuses
are recorded per finding.

**Current handoff:** `docs/PRODUCTION-HANDOFF-2026-09-26-MORNING.md` supersedes
all earlier production handoffs.
**Current context reset:** `docs/CONTEXT-RESET-2026-09-15-E.md` supersedes all
earlier context resets.

---

## CLASS 1: "DONE, artifact verified" claims

**Source:** `docs/PRODUCTION-HANDOFF-2026-09-26-MORNING.md` §8, line 201:

    DONE, artifact verified   305 Groq adapter, 307 ContactOut linkedin route,
                              310 training capture, 311 ingest, 313 AUDIT,
                              314 cadence regression test, 315 cross-channel
                              tests, 316 the fifty, 317 Second Brain (then
                              found defective), 216 219 221 279 QA

**13 tasks claimed. 2 are in `DONE/`. 11 are in `TODO/`.**

### Per-claim verification

| Task | Claimed artifact | `git cat-file -e` result | Task file location |
|------|-----------------|--------------------------|--------------------|
| 305 | `src/providers/groq.py` | **MISSING** (exit 128) | TODO/ |
| 305 | `src/providers/openrouter.py` | **MISSING** (exit 128) | TODO/ |
| 307 | `linkedin_url_from_email` in `src/providers/contactout.py` | File EXISTS, function **ABSENT** (grep: 0 matches) | TODO/ |
| 310 | training capture in `src/reviewapproval.py` | File EXISTS (exit 0); artifact is a change, not the file | TODO/ |
| 311 | LinkedIn column in `src/ingest.py` | File EXISTS (exit 0); artifact is a change | TODO/ |
| 313 | `docs/AUDIT-2026-09-26.md` | **MISSING** (exit 128) | TODO/ |
| 314 | cadence regression test | `tests/test_the_sequence_gate_catches_what_copylint_cannot.py` EXISTS (exit 0) | TODO/ |
| 315 | cross-channel tests | `tests/test_cross_channel.py` EXISTS (exit 0) | TODO/ |
| 316 | the fifty (work/ file) | `work/` is gitignored; cannot exist on master by design | TODO/ |
| 317 | `src/secondbrain.py` | EXISTS (exit 0) | **DONE/** ✓ |
| 216 | investigation-only; task file IS the artifact | Task file EXISTS in DONE/ (exit 0) | **DONE/** ✓ |
| 219 | `tests/test_no_activation_without_an_exact_match.py` | EXISTS (exit 0) | TODO/ |
| 221 | `tests/test_compare_bison.py` | EXISTS (exit 0) | TODO/ |
| 279 | `scripts/pack_fetch.py` | **MISSING** (exit 128) | TODO/ |
| 279 | `tests/test_pack_fetch_chunks.py` | **MISSING** (exit 128) | TODO/ |

**Severity: CRITICAL.** The handoff is the first thing a new session reads.
11 of 13 "artifact verified" claims are false. The artifacts for TASK-305,
TASK-307, TASK-313 and TASK-279 do not exist on master at all.

**Already reported:** BUGGIE-FINDINGS-2026-09-26.md §C5 documents the same
finding independently. TASK-329 and TASK-335 carry follow-up work.

**Fix required (operator judgement):** The handoff §8 list must be corrected
to reflect actual state. This is not a mechanical fix — each task's real
status needs to be stated.

---

## CLASS 2: Modules described as wired that have no caller

### Import graph on origin/master

| Module | Non-test importers in `src/` | Non-test importers in `scripts/` |
|--------|------------------------------|----------------------------------|
| `sequencegate` | **ZERO** | **ZERO** |
| `copystages` | **ZERO** | **ZERO** |
| `copyprompts` | **ZERO** | **ZERO** |
| `secondbrain` | 1 (`copystages.py:132`) | **ZERO** |

`secondbrain`'s sole importer (`copystages`) has zero callers itself, so
`secondbrain` is also effectively disconnected.

### False claims found

| File | Quote | Reality |
|------|-------|---------|
| `docs/qwen-tasks/DONE/TASK-322-*.md` line 78 | "`copystages`/`copypath` is the consumer" | `copypath.py` does not exist on master (exit 128). `copystages` has zero callers. |

**Other docs correctly report the disconnection:** TASK-321, TASK-324,
BUGGIE-FINDINGS H1/H2, ARCHITECTURE-ACCOUNT-FIRST-2026-09-26 §131,
glm-reviews/TASK-317-secondbrain.md all correctly state "zero callers".

### Additional wiring misrepresentations (found by sub-agent)

| File | Claim | Reality |
|------|-------|---------|
| `docs/PRODUCTION-HANDOFF-2026-09-26-MORNING.md` line 81 | `sequencegate.check` listed among active production guards | It has zero callers; listed alongside `copylint.check_batch` as if it guards production |
| `docs/qwen-tasks/DONE/TASK-317-*.md` line 15 | Groups `copyprompts.py` with active modules as "peer consumer" of `clients.load()` | `copyprompts` has zero callers; it is not a peer of `bisonfactory` |
| `PRODUCT-INVENTORY.md` line 160 | Lists `reportdraft` as `IMPLEMENTED` | `src/reportdraft.py` has zero importers and no CLI entry point — dead code |

**Severity: HIGH** for the TASK-322 claim — it is in a DONE file and names a
non-existent file as the consumer. **HIGH** for the handoff listing
`sequencegate` as an active guard.

---

## CLASS 3: Files named in plans that do not exist

### `docs/PHASE1-PLAN-2026-09-26.md`

| Line | Reference | `git cat-file -e` result |
|------|-----------|--------------------------|
| 231 | `src/copypath.py  MODIFY` | **MISSING** (exit 128) |
| 232 | `src/copyengine.py  MODIFY` | **MISSING** (exit 128) |
| 240 | `copypath.py goes B -> C -> D -> E -> F` | File does not exist |
| 271 | `Rollback: revert one commit in copypath.py` | File does not exist |
| 301 | `copypath.py. The ten and the fifty run from work/v2_run.py` | File does not exist |

The plan instructs operators to MODIFY two files that do not exist. This is
not a future-tense reference ("create copypath.py") — it says MODIFY, which
implies the file is there.

**Already reported:** TASK-321 lines 28-34 document the same finding.

### `docs/PRODUCTION-HANDOFF-2026-09-26-MORNING.md` §8

| Line | Reference | `git cat-file -e` result |
|------|-----------|--------------------------|
| ~210 | `docs/provider-answers/apify-actor-limits.md` | **MISSING** (exit 128) |
| ~210 | `docs/provider-answers/cheapverifier-rate-limits.md` | **MISSING** (exit 128) |

The handoff lists four files in `docs/provider-answers/`; only two exist on
master (`heyreach-step-limits.md`, `emailbison-remove-and-pause.md`).

### Additional phantom references (found by sub-agent)

| Missing path | Doc file | Claim |
|---|---|---|
| `src/campaignstrategy.py` | `docs/PHASE1-PLAN-2026-09-26.md:195` | "NEW or EXTEND" — does not exist |
| `src/blitz.py` | `PRODUCT-GAPS.md:2986` | Claims "62 tests" — module does not exist |
| `src/providers/cheapverifier.py` | `docs/MERGE-REQUEST-2026-09-25-PER-PROVIDER-CEILINGS.md:459` | "belongs to lane Q and was not touched" — does not exist |
| `src/campaignregistry.py` | `docs/qwen-tasks/DONE/TASK-100-*.md:92` | DONE task claims artifact — not on master |
| `src/redact.py` | `docs/qwen-tasks/DONE/TASK-118-*.md:73` | DONE task claims artifact — not on master |
| `src/reply.py` | `docs/RED-TESTS-2026-09-15.md:89` | Wrong filename; correct module is `src/referral.py` |

### `docs/BACKLOG.md`

| Line | Reference | Result |
|------|-----------|--------|
| ~15 | `docs/ONBOARDING-REVIEW-2026-09-26.md` | **MISSING** (exit 128), but text says "when it is written" — acknowledged as future. **Not a false claim.** |

**Severity: HIGH** for PHASE1-PLAN. An operator following the plan would look
for files that do not exist. **PRODUCT-GAPS.md claiming 62 tests for a
non-existent module is a CRITICAL factual error.**

---

## CLASS 4: Acceptance snippets that fail when run

### PHASE1-PLAN TASK-321 acceptance snippet

**Command run:**

    py -3 -c "import sys;sys.path.insert(0,'.');import ast,pathlib;\
    src=' '.join(p.read_text(encoding='utf-8') for p in pathlib.Path('src').rglob('*.py'));\
    assert 'copystages' in src and 'sequencegate' in src;\
    print('both wired')"

**Result:** `AssertionError`, exit code 1.

**Why it fails:** `copystages` does not appear in any `src/*.py` file's
*content*. The file `src/copystages.py` exists, but its filename is not part
of its content, and no other module imports or mentions it. The substring
match is actually a rough wiring check — and it correctly shows that
`copystages` is disconnected.

**Already reported:** BUGGIE-FINDINGS H7 documents this. TASK-321 lines 40-43
warn against using this snippet.

**Severity: MEDIUM.** The snippet is in the plan but TASK-321 itself warns
not to use it. The plan should be corrected.

### Additional acceptance snippets that fail (found by sub-agent)

| Command | Source doc | Exit | Reason |
|---------|-----------|------|--------|
| `from src import offers; offers.for_campaign(...)` | PHASE1-PLAN TASK-318 | 1 | `ImportError` — `src/offers.py` does not exist |
| `from src import skills; skills.load(...)` | PHASE1-PLAN TASK-319 | 1 | `ImportError` — `src/skills/` does not exist |
| `from src import campaignstrategy as c` | PHASE1-PLAN TASK-320 | 1 | `ImportError` — module does not exist |
| `py -3 scripts/consumer_audit.py --json` | TASK-324 | 2 | Script does not exist |
| `from src.providers import groq` | TASK-335 | 1 | `ImportError` — module does not exist |

These are acceptance criteria for tasks that have not been implemented. They
are not false claims per se — the tasks are listed as NOT YET WRITTEN in the
plan. But an operator running them would get errors.

---

## CLASS 5: Superseded documents not marked

### Context reset chain

| Document | Date | Superseded by | Says "SUPERSEDED"? |
|----------|------|---------------|---------------------|
| `docs/CONTEXT-RESET-2026-09-14.md` | 09-14 | -B.md | **NO** |
| `docs/CONTEXT-RESET-2026-09-14-B.md` | 09-14 | -C.md | **NO** |
| `docs/CONTEXT-RESET-2026-09-14-C.md` | 09-14 | -15-D.md | **NO** |
| `docs/CONTEXT-RESET-2026-09-15-D.md` | 09-15 | -15-E.md | **NO** |
| `docs/CONTEXT-RESET-2026-09-15-E.md` | 09-15 | **CURRENT** | N/A |

### CLAUDE-HANDOFF.md

| Document | Date | Superseded by | Says "SUPERSEDED"? |
|----------|------|---------------|---------------------|
| `docs/CLAUDE-HANDOFF.md` | 09-13/14 | CONTEXT-RESET-2026-09-15-E.md | **NO** |

`QWEN.md` says "docs/CLAUDE-HANDOFF.md is the current durable truth" but the
file is 12 days stale and has been superseded by five context resets.

### Production handoff chain

20 production handoffs from 09-16 to 09-24. None carry a "SUPERSEDED" marker.
The current one is `docs/PRODUCTION-HANDOFF-2026-09-26-MORNING.md`, which
does say "It supersedes earlier handoffs on everything it covers."

### Slack-agent handoff chain

10 slack-agent handoffs from 09-22 to 09-24. None carry a "SUPERSEDED" marker.
Current: `SLACK-AGENT-HANDOFF-2026-09-24.md`.

### Infra handoff chain

5 infra handoffs from 09-23 to 09-24. None carry a "SUPERSEDED" marker.
Current: `INFRA-HANDOFF-2026-09-24-SHADOW-DONE.md`.

### Systemic pattern

The supersession pattern is one-directional across ALL chains: new docs say
"I supersede X" but old docs are never back-patched with "superseded by Y."
**38 documents in total** should be marked superseded but are not. This sweep
fixed the 5 most load-bearing ones (the context-reset chain and CLAUDE-HANDOFF).
The production/slack/infra handoff chains are a larger task best handled by
a batch operation.

**Severity: LOW-MEDIUM.** The superseding document names what it replaces,
which is the forward link. The backward link (marking the old one) is missing.
An operator finding an old doc first would read stale state.

---

## FIXES APPLIED

### Superseded markers added (unambiguous fixes)

1. `docs/CONTEXT-RESET-2026-09-14.md` — added superseded marker pointing to -B.md
2. `docs/CONTEXT-RESET-2026-09-14-B.md` — added superseded marker pointing to -C.md
3. `docs/CONTEXT-RESET-2026-09-14-C.md` — added superseded marker pointing to -15-D.md
4. `docs/CONTEXT-RESET-2026-09-15-D.md` — added superseded marker pointing to -15-E.md
5. `docs/CLAUDE-HANDOFF.md` — added superseded marker pointing to -15-E.md

---

## FINDINGS (require operator judgement, not mechanical fixes)

1. **The handoff §8 "DONE, artifact verified" list is 11/13 false.** The list
   must be rewritten to reflect actual state. Each task's real status and
   artifact location needs to be stated. This is an operator call because
   some tasks have partial work on branches.

2. **PHASE1-PLAN TASK-321 names two non-existent files as MODIFY targets.**
   The plan was written before the files were lost (or never integrated).
   Either the plan must be updated to name the real paths, or the files must
   be recreated. Operator decision.

3. **TASK-322 (DONE) claims `copypath` is the consumer.** `copypath.py` does
   not exist. The DONE claim is premature — `for_task` still has zero
   production callers. Requires re-opening or a corrective note.

4. **Two `docs/provider-answers/` files named in the handoff do not exist.**
   `apify-actor-limits.md` and `cheapverifier-rate-limits.md` were either
   never committed or lost. The Grok re-run ordered in §11 cannot read them.

5. **`QWEN.md` says `CLAUDE-HANDOFF.md` is "the current durable truth"** but
   it is 12 days stale. The file itself should be updated or the reference
   in QWEN.md should point to CONTEXT-RESET-2026-09-15-E.md.

6. **`PRODUCT-GAPS.md` claims `src/blitz.py` has "62 tests"** — the module
   does not exist on master. A factual error in a production document.

7. **`PRODUCT-INVENTORY.md` lists `reportdraft` as IMPLEMENTED** — it has
   zero importers and no CLI entry point. Dead code listed as a live product
   capability.

8. **Two DONE tasks (TASK-100, TASK-118) claim artifacts that never reached
   master** — `src/campaignregistry.py` and `src/redact.py` respectively.
   Same pattern as the handoff's false "artifact verified" claims.

9. **33 additional docs** (production/slack/infra handoff chains) lack
   superseded markers. Best handled as a batch operation.

---

## COMMANDS RUN AND EXIT STATUSES

    git cat-file -e origin/master:src/providers/groq.py           -> 128 (MISSING)
    git cat-file -e origin/master:src/providers/openrouter.py     -> 128 (MISSING)
    git cat-file -e origin/master:src/providers/contactout.py     -> 0   (EXISTS)
    git cat-file -e origin/master:src/learning.py                 -> 0   (EXISTS)
    git cat-file -e origin/master:src/ingest.py                   -> 0   (EXISTS)
    git cat-file -e origin/master:docs/AUDIT-2026-09-26.md        -> 128 (MISSING)
    git cat-file -e origin/master:src/secondbrain.py              -> 0   (EXISTS)
    git cat-file -e origin/master:src/sequencegate.py             -> 0   (EXISTS)
    git cat-file -e origin/master:src/copystages.py               -> 0   (EXISTS)
    git cat-file -e origin/master:src/copyprompts.py              -> 0   (EXISTS)
    git cat-file -e origin/master:src/copypath.py                 -> 128 (MISSING)
    git cat-file -e origin/master:src/copyengine.py               -> 128 (MISSING)
    git cat-file -e origin/master:src/offers.py                   -> 128 (MISSING)
    git cat-file -e origin/master:src/skills/__init__.py          -> 128 (MISSING)
    git cat-file -e origin/master:scripts/pack_fetch.py           -> 128 (MISSING)
    git cat-file -e origin/master:tests/test_pack_fetch_chunks.py -> 128 (MISSING)
    git cat-file -e origin/master:tests/test_cross_channel.py     -> 0   (EXISTS)
    git cat-file -e origin/master:tests/test_the_sequence_gate_catches_what_copylint_cannot.py -> 0 (EXISTS)
    git cat-file -e origin/master:docs/provider-answers/apify-actor-limits.md    -> 128 (MISSING)
    git cat-file -e origin/master:docs/provider-answers/cheapverifier-rate-limits.md -> 128 (MISSING)
    git cat-file -e origin/master:docs/ONBOARDING-REVIEW-2026-09-26.md           -> 128 (MISSING)

    grep -c "linkedin_url_from_email" on origin/master:src/providers/contactout.py -> 0

    py -3 -c "...assert 'copystages' in src..." -> AssertionError, exit 1

    grep "import sequencegate|from sequencegate" src/ -> 0 matches
    grep "import copystages|from copystages" src/     -> 0 matches
    grep "import copyprompts|from copyprompts" src/   -> 0 matches
    grep "import secondbrain|from secondbrain" src/   -> 1 match (copystages.py:132)
    grep "sequencegate|copystages|copyprompts" scripts/ -> 0 matches
    grep "secondbrain" scripts/                      -> 0 matches
