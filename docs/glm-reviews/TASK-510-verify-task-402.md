# TASK-510 — Independent verification of TASK-402

## Review metadata

    REVIEWER:           Qwen worker (r9), independent of TASK-402's author (worker 9)
    TARGET:             TASK-402 (GLM first-pass verification of TASK-391)
    BRANCH:             origin/qwen-worker-9-r9
    BRANCH HEAD SHA:    f1b9c357c17f4b557cbdb06f68339c7343ef3e83
    VERIFIED SHA:       git rev-parse origin/qwen-worker-9-r9 → f1b9c357 (unchanged)
    START_MASTER_SHA:   master as of 2026-09-29
    WORKTREE:           .qwen/worktrees/task510-review (detached at f1b9c357)
    ARTIFACT KIND:      finding (read-only verification, no code changes)

---

## 1. Does the artifact exist on this ref?

**YES, with a protocol deviation.**

The artifact lives at:

    docs/qwen-tasks/REVIEW/TASK-402-glm-verify-task-391-skills-runtime-finding.md

It was verified present via `git ls-tree -r --name-only f1b9c357 | grep TASK-402`.

**Protocol deviation:** TASK-402 did NOT write a separate review document to `docs/glm-reviews/`. Other GLM verdicts on this branch follow that convention (TASK-404 → `docs/glm-reviews/TASK-404-verify-task-397.md`, TASK-382 → `docs/glm-reviews/TASK-382-glm-verify-task-367-offer-block.md`, etc.). TASK-402 embedded its entire verdict in the task file's Result section. The content is there and complete, but the convention was not followed. This is a minor housekeeping issue, not a substance issue.

---

## 2. Independent verification of TASK-402's five-way mismatch table

I read every source TASK-402 cites, in the isolated worktree at f1b9c357.

### 2.1 diagnose vs signal_verification (ICP_SYSTEM)

- **generate.py:1488** calls `render_prompt("diagnose", rec)` → reads `prompts/diagnose.md`
- **prompts/diagnose.md**: Thread revival. Input: CRM dump + full thread verbatim. Output: `{died_on, died_because, failure_mode, last_position, what_changed}`. Job: find the specific moment a conversation broke.
- **signal_verification.procedure** = `copyprompts.ICP_SYSTEM` (copyprompts.py:184): ICP classification. Input: company domain + scraped text sources. Output: `{is_agency, confidence, evidence, what_they_actually_are}`. Job: decide if a company is a services agency.
- **VERDICT: CONFIRMED MISMATCH.** Different jobs, different inputs, different outputs. No correspondence.

### 2.2 hook vs account_research (EXTRACT_SYSTEM)

- **generate.py:1501** calls `render_prompt("hook", rec)` → reads `prompts/hook.md`
- **prompts/hook.md**: "Cold lane. Return JSON only: `{\"hook\": \"one specific, checkable fact about them\"}`." One sentence output from a signal event.
- **account_research.procedure** = `copyprompts.EXTRACT_SYSTEM` (copyprompts.py:79): Extracts 3-5 structured facts from scraped sources. Output: JSON with `{facts: [{text, quote, source_index, kind, confidence}], angle, company_hook, usable, why_this_lead}`.
- **VERDICT: CONFIRMED MISMATCH.** This is the closest pair (both extract facts), but the scale, structure, and job differ fundamentally:
  - hook: ONE fact, one sentence, from a signal event, for an opening line
  - EXTRACT_SYSTEM: 3-5 facts with verbatim quotes, source indices, confidence scores, building an evidence base for downstream writers

### 2.3 persona_angle vs campaign_strategy (STRATEGY_SYSTEM)

- **generate.py:1511** calls `render_prompt("persona_angle", rec, contact, client)` → reads `prompts/persona_angle.md`
- **prompts/persona_angle.md**: "Domains lane. Return `{angle: one of the client's configured angle keys, evidence: [traceable items]}`." Picks one angle for one contact.
- **campaign_strategy.procedure** = `copystages.STRATEGY_SYSTEM` (copystages.py:191): Plans a full 9-message outreach sequence (5 emails + 4 LinkedIn). Output: `{emails: {em1-em5}, linkedin: {connect, msg1-msg3}, dropped, repetition_check}`.
- **VERDICT: CONFIRMED MISMATCH.** One selects a single angle from a configured list; the other plans an entire multi-channel sequence. Different scale, different output shape, different job.

### 2.4 draft vs cold_email_writing (WRITER_SYSTEM)

- **generate.py:1626** calls `render_prompt("draft", rec, contact, client, day)` → reads `prompts/draft.md`
- **prompts/draft.md**: ~200 lines. Writes ONE email with rich per-record context: `prior_contact` branching, `already_sent`, `siblings`, `sender_identity`, `product` block, `step.purpose`, `angle_wording`, full lint constraints, claims rules.
- **cold_email_writing.procedure** = `copystages.WRITER_SYSTEM` (copystages.py:273): ~80 lines. Batch writer producing ALL 5 emails + 4 LinkedIn messages in one call from a plan. No `prior_contact` branching, no `already_sent`, no `siblings`, no `sender_identity`, no `step.purpose`, no `angle_wording`, minimal lint ("no dashes", "no signature").
- **VERDICT: CONFIRMED MISMATCH.** The draft prompt is 2-3x longer and has fundamentally different context and constraints. Replacing `prompts/draft.md` with `WRITER_SYSTEM` would lose: prior_contact branching, already_sent context, siblings context, sender_identity, product block, step.purpose awareness, angle_wording, and most lint constraints.

### 2.5 linkedin_note vs linkedin_writing (WRITER_SYSTEM)

- **generate.py:1542** (and 1385 in `_regenerate_linkedin_set`) calls `render_prompt("linkedin_note", rec, contact, client, step_key)` → reads `prompts/linkedin_note.md`
- **prompts/linkedin_note.md**: ~150 lines. Writes ONE LinkedIn note with step-level awareness: `step.purpose`, `sender_identity` (with step-1 vs later-step distinction), `product` block, `already_sent`, `siblings`, full rules (300 chars, no email crossover, no "i noticed", ASCII punctuation).
- **linkedin_writing.procedure** = `copystages.WRITER_SYSTEM` (copystages.py:273): Same shared prompt as cold_email_writing. Batch writer for all 4 LinkedIn messages. No step-level awareness, no sender_identity step distinction, no already_sent, no siblings.
- **VERDICT: CONFIRMED MISMATCH.** Same analysis as draft vs cold_email_writing. The linkedin_note prompt is step-aware and context-rich; WRITER_SYSTEM is a batch writer.

### Line number accuracy

TASK-402 cited five line numbers for generate.py's render_prompt calls:

| Stage          | TASK-402 cited | Actual | Delta |
|----------------|---------------|--------|-------|
| diagnose       | 1487          | 1488   | +1    |
| hook           | 1501          | 1501   | 0     |
| persona_angle  | 1510          | 1511   | +1    |
| draft          | 1626          | 1626   | 0     |
| linkedin_note  | 1542, 1385    | 1542, 1385 | 0 |

Two of five are off by one line. Minor and does not affect the substance of any mismatch claim.

---

## 3. Falsification: is any mismatch overstated?

I looked hardest at **hook vs account_research** because both extract facts. Even there:

- `hook` extracts ONE fact from a signal event, returns one sentence in `{"hook": "..."}`.
- `EXTRACT_SYSTEM` extracts 3-5 structured facts from scraped multi-source text, returns JSON with quotes, source indices, confidence scores, angles, company hooks, usability flags.
- The inputs differ (signal event vs scraped sources), the outputs differ (one string vs structured array), and the downstream jobs differ (opening line vs evidence foundation).

**Result: No stage has an overstated mismatch.** All five pairs are genuinely different jobs with different inputs, outputs, and constraints.

---

## 4. Verification of additional claims

### 4.1 generate_campaign.generate() has zero production callers

I searched `src/` for any occurrence of `generate_campaign`:

    grep_search "generate_campaign" in src/ → No matches found

**CONFIRMED.** `src/generate_campaign.py` exists and is consumed by tests, but nothing in `src/` imports or calls it.

### 4.2 Skills' consumer names do not exist in generate.py

The five skills declare consumers: `stage_a`, `stage_b`, `stage_e`, `stage_f`, `stage_f`. I verified each:

    signal_verification.py:  consumer="stage_a"
    account_research.py:     consumer="stage_b"
    campaign_strategy.py:    consumer="stage_e"
    cold_email_writing.py:   consumer="stage_f"
    linkedin_writing.py:     consumer="stage_f"

I searched `src/generate.py` for `stage_a|stage_b|stage_e|stage_f`:

    grep → (empty)

**CONFIRMED.** Zero matches. The skills' declared consumers do not exist in generate.py's stage vocabulary.

---

## 5. Would merging delete anything?

`git diff master...f1b9c357 --diff-filter=D --name-only` shows two deleted files:

    docs/qwen-tasks/TODO/TASK-392-signature-per-attested-mailbox-verification.md
    docs/qwen-tasks/TODO/TASK-399-docs-hygiene-pass.md

These are TODO task files moved to REVIEW (task lifecycle management), not production code. No source files, tests, configuration, or documentation outside the task queue would be deleted.

TASK-402's own commit (`cd54811d`) touches only two files:
- `docs/qwen-tasks/REVIEW/TASK-402-...md` (added)
- `docs/qwen-tasks/TODO/TASK-402-...md` (deleted — moved to REVIEW)

**No code deletion. Safe.**

---

## 6. Scope drift

TASK-402's commit is clean: one task file moved from TODO to REVIEW with the verdict filled in. No unrelated changes.

The branch as a whole carries 64 changed files (other tasks), but TASK-402's own contribution is exactly what it claims: a finding with eight dispositions. No scope drift in the task itself.

---

## 7. Are the tests falsifiable?

TASK-402 is a finding task with no code changes and no tests. The appropriate verification is whether the finding's claims are independently reproducible by reading source — which is exactly what this review does. Every claim was verified against the actual source files in the isolated worktree.

---

## 8. Eight dispositions

1. **The five-way mismatch table** — **CONFIRMED.** All five pairs are genuinely different jobs. No stage has an overstated mismatch. Independently verified by reading all five prompt files, all five skill modules, all four prompt constants, and all five render_prompt call sites in generate.py.

2. **The claim that generate_campaign.generate() has zero production callers** — **CONFIRMED.** `grep_search "generate_campaign" in src/` returns zero matches.

3. **The claim that the skills' consumer names (stage_a, stage_b, stage_e, stage_f) do not exist in generate.py** — **CONFIRMED.** `grep "stage_a|stage_b|stage_e|stage_f" src/generate.py` returns zero matches.

4. **The conclusion that wiring skills directly onto generate.py's stages would be a regression** — **CONFIRMED.** The draft and linkedin_note prompts have 2-3x the context and constraints of WRITER_SYSTEM. Replacing them would lose: prior_contact branching, already_sent awareness, siblings context, sender_identity, step.purpose, angle_wording, and most lint constraints.

5. **The recommendation that the fix must happen at the pipeline level, not the prompt level** — **ACCEPTED.** TASK-400's design (connect the pipelines at a higher level) is the correct architectural response.

6. **The question: are the skills meant for generate.py or generate_campaign.py?** — **UNRESOLVED, not blocking.** The skills are correctly wired for generate_campaign.py's batch pipeline. If generate_campaign.py becomes the production path (TASK-400's goal), the skills are operational.

7. **The risk that the skills are documentation, not operational stages** — **ACCEPTED DEFERRED RISK.** Until TASK-400 lands, the skills have no production consumer. This is the defect TASK-400 exists to fix.

8. **Overall verdict on TASK-391's finding** — **HOLDS.** The finding is correct, the evidence is sound, and TASK-400 is proceeding on solid ground.

---

## 9. Issues found

| # | Severity | Issue |
|---|----------|-------|
| 1 | Minor    | Two of five line number citations are off by one (1487→1488, 1510→1511). Does not affect substance. |
| 2 | Minor    | No separate review document in `docs/glm-reviews/`. The verdict is embedded in the task file, which deviates from the convention other GLM reviews on the same branch follow. |

Neither issue affects the correctness of the finding.

---

## 10. Recommendation

**MERGE.**

TASK-402's finding is independently verified. All five mismatches hold, both additional claims are confirmed, the falsification attempt found no overstated mismatch, and the conclusion that TASK-400 proceeds on solid ground follows from the evidence. The artifact is a finding (no code), so there is nothing to disconnect and nothing to wire. The two minor issues (line number precision, missing glm-reviews document) are housekeeping, not substance.
