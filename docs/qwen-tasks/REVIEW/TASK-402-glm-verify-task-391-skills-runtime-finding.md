PRIORITY: P0
SIZE: S
DEPENDS:

# TASK-402 — GLM first-pass verification: TASK-391 (skills-at-runtime finding)

**Operator instruction, 2026-09-27 morning.** Do this alongside TASK-401
(364), before the rest. TASK-400 (the critical-path fix) already treats
TASK-391's conclusion as settled and builds on it — this checkpoint exists
to catch it FAST if that trust is misplaced.

Read `docs/GLM-REVIEW-PROTOCOL.md` yourself and follow it.

## Target

TASK-391 (`docs/qwen-tasks/REVIEW/` on `qwen-worker-3-r9`) — a FINDING, not a
code change: it concludes the five skills' procedures do not match
`src/generate.py`'s five stages (diagnose/hook/persona_angle/draft/
linkedin_note) in shape, content or job, so wiring them directly would be a
regression.

## What GLM's pass must produce

1. Independently confirm the five-way mismatch table TASK-391 built - read
   each of `generate.py`'s five `render_prompt()` call sites and each
   skill's `.procedure`, and confirm or refute that they genuinely don't
   correspond.
2. Falsify, don't confirm: is there ANY stage where the mismatch claim is
   overstated - i.e., a skill that actually WOULD work if wired in, that
   TASK-391 wrongly dismissed?
3. State plainly whether TASK-400 (the critical-path task, already
   dispatched, built on TASK-391's conclusion) is proceeding on solid
   ground.

## Result

STATUS: DONE
ARTIFACT KIND: finding (independent verification, no code changes)
COMMIT: (pending)
TESTS: n/a — read-only verification
FILES CHANGED: this task file only
VERIFIER: GLM first-pass (Qwen worker 9, independent read of source)
START_MASTER_SHA: current qwen-worker-9-r9 HEAD

---

### Independent verification of TASK-391's five-way mismatch table

I read every source TASK-391 cites. Here is what I found, stage by stage.

#### 1. diagnose (generate.py:1487) vs signal_verification (ICP_SYSTEM)

- **generate.py:1487** calls `render_prompt("diagnose", rec)` → reads `prompts/diagnose.md`
- **prompts/diagnose.md**: "Revive lane. You are given one record: the CRM dump and the full thread, verbatim... Order the thread. Find the specific moment it broke." Returns `{died_on, died_because, failure_mode, last_position, what_changed}`.
- **signal_verification.procedure** = `copyprompts.ICP_SYSTEM` (copyprompts.py:184): "You decide one thing: is this company a SERVICES AGENCY THAT RUNS CLIENT PROJECTS?" Returns `{is_agency, confidence, evidence, what_they_actually_are}`.
- **VERDICT: CONFIRMED MISMATCH.** Different jobs (thread revival vs ICP classification), different inputs (CRM thread vs company sources), different outputs (failure analysis vs agency boolean). No correspondence.

#### 2. hook (generate.py:1501) vs account_research (EXTRACT_SYSTEM)

- **generate.py:1501** calls `render_prompt("hook", rec)` → reads `prompts/hook.md`
- **prompts/hook.md**: "Cold lane. You are given the signal that triggered this record, and the company facts already gathered from providers. Return JSON only: `{"hook": "one specific, checkable fact about them"}`." One sentence output.
- **account_research.procedure** = `copyprompts.EXTRACT_SYSTEM` (copyprompts.py:79): "You extract verifiable facts about a company from text scraped from their own website, their LinkedIn company posts, their open roles..." Returns structured JSON with 3-5 facts, each with `{text, quote, source_index, kind, confidence}`, plus `angle`, `company_hook`, `usable`, `why_this_lead`.
- **VERDICT: CONFIRMED MISMATCH.** This is the closest pair (both extract facts), but the jobs are different:
  - `hook`: ONE fact from a signal event, one sentence, for cold outreach opening
  - `EXTRACT_SYSTEM`: 3-5 structured facts from scraped sources, with verbatim quotes and source indices, building an evidence base for downstream writers
  - Inputs differ (signal event vs scraped multi-source text), outputs differ (one string vs structured JSON array), and the downstream job differs (opening line vs evidence foundation).

#### 3. persona_angle (generate.py:1510) vs campaign_strategy (STRATEGY_SYSTEM)

- **generate.py:1510-1511** calls `render_prompt("persona_angle", rec, contact, client)` → reads `prompts/persona_angle.md`
- **prompts/persona_angle.md**: "Domains lane. You are given the client's configured personas and angles, the trimmed company facts, and one contact. Return: `{angle: one of the client's configured angle keys, evidence: [traceable items]}`."
- **campaign_strategy.procedure** = `copystages.STRATEGY_SYSTEM` (copystages.py:191): "You plan a nine message outreach sequence BEFORE any of it is written... THE EMAIL SEQUENCE... THE LINKEDIN SEQUENCE... EACH MESSAGE NEEDS FOUR THINGS: objective, angle, proof, cta." Returns full 9-message plan with 5 emails + 4 LinkedIn messages.
- **VERDICT: CONFIRMED MISMATCH.** One picks a single angle from a configured list for one contact; the other plans an entire multi-channel sequence. Different scale, different output shape, different job.

#### 4. draft (generate.py:1626) vs cold_email_writing (WRITER_SYSTEM)

- **generate.py:1626** calls `render_prompt("draft", rec, contact, client, day)` → reads `prompts/draft.md`
- **prompts/draft.md**: ~200 lines. Writes ONE email with rich per-record context: `prior_contact` branching (first touch vs reply), `already_sent` (confirmed sent messages), `siblings` (other drafts), `sender_identity`, `product` block, `step.purpose`, `angle_wording`, full lint constraints, claims rules, sequence awareness. Returns `{subject, body}`.
- **cold_email_writing.procedure** = `copystages.WRITER_SYSTEM` (copystages.py:273): ~80 lines. Batch writer that produces ALL 5 emails + LinkedIn messages in one call from a plan. No `prior_contact` branching, no `already_sent` awareness, no `siblings` context, no `sender_identity` block, no `step.purpose`, no `angle_wording`, minimal lint (just "no dashes", "no signature"). Returns `{subject, subject_alt, subject_breakup, emails: {em1-em5}, ps, linkedin: {connect, msg1-msg3}, ...}`.
- **VERDICT: CONFIRMED MISMATCH.** The draft prompt is 2-3x longer and has fundamentally different context and constraints. Replacing `prompts/draft.md` with `WRITER_SYSTEM` would lose: prior_contact branching, already_sent context, siblings context, sender_identity, product block, step.purpose awareness, angle_wording, and most lint constraints. TASK-391's claim is correct.

#### 5. linkedin_note (generate.py:1542, also 1385) vs linkedin_writing (WRITER_SYSTEM)

- **generate.py:1542** (and 1385 in `_regenerate_linkedin_set`) calls `render_prompt("linkedin_note", rec, contact, client, step_key)` → reads `prompts/linkedin_note.md`
- **prompts/linkedin_note.md**: ~150 lines. Writes ONE LinkedIn note with rich context: `step.purpose`, `sender_identity` (with step-1 vs later-step distinction), `product` block, `already_sent`, `siblings`, full rules (300 chars, no email crossover, no "i noticed", ASCII punctuation). Returns `{note}`.
- **linkedin_writing.procedure** = `copystages.WRITER_SYSTEM` (copystages.py:273): Same shared prompt as cold_email_writing. Batch writer for all 4 LinkedIn messages in one call. No step-level awareness, no sender_identity step distinction, no already_sent, no siblings.
- **VERDICT: CONFIRMED MISMATCH.** Same analysis as draft vs cold_email_writing. The linkedin_note prompt is step-aware and context-rich; WRITER_SYSTEM is a batch writer.

#### Additional verification: consumer names

The five skills declare consumers: `stage_a`, `stage_b`, `stage_e`, `stage_f`, `stage_f`. I searched `src/generate.py` for these stage names: **zero matches**. The skills' declared consumers do not exist in generate.py's stage vocabulary.

#### Additional verification: generate_campaign.py has zero production callers

I searched `src/` for any import or call of `generate_campaign`: **zero matches**. The file exists at `src/generate_campaign.py` and is consumed by tests, but nothing in `src/` imports or calls it. TASK-391's claim is confirmed.

---

### Falsification attempt: is there ANY stage where the mismatch is overstated?

I looked hardest at **hook vs account_research** because both extract facts. But even there:
- `hook` extracts ONE fact from a signal event, returns one sentence
- `EXTRACT_SYSTEM` extracts 3-5 structured facts from scraped sources, returns JSON with quotes, source indices, confidence scores, angles, company hooks
- The inputs, outputs, and downstream jobs are different

**Result: No stage has an overstated mismatch.** All five pairs are genuinely different jobs with different inputs, outputs, and constraints. TASK-391's finding holds.

---

### Does TASK-400 proceed on solid ground?

TASK-400 explicitly reads TASK-391's finding and builds on it: "Do not retry TASK-391's skill-onto-stage approach." Instead, TASK-400 proposes connecting `generate.py` to `generate_campaign.generate()` at a higher level (either generate.py calls generate_campaign, or generate_campaign's body replaces generate.py's stages while keeping generate.py's store/event/lint/cadence integrations).

This is the correct architectural response to TASK-391's finding. The mismatch is real, so the fix cannot be "swap prompts" — it must be "connect pipelines at the right level."

**Yes, TASK-400 is proceeding on solid ground.** TASK-391's conclusion is settled, and TASK-400's design respects it.

---

### Eight dispositions (GLM review protocol format)

TASK-391's finding is a single architectural conclusion, not a list of defects. The dispositions apply to the finding as a whole and to its consequences:

1. **The five-way mismatch table** — **CONFIRMED.** All five pairs are genuinely different jobs. No stage has an overstated mismatch.

2. **The claim that generate_campaign.generate() has zero production callers** — **CONFIRMED.** Nothing in `src/` imports or calls it.

3. **The claim that the skills' consumer names (stage_a, stage_b, stage_e, stage_f) do not exist in generate.py** — **CONFIRMED.** Zero matches.

4. **The conclusion that wiring skills directly onto generate.py's stages would be a regression** — **CONFIRMED.** The draft and linkedin_note prompts have 2-3x the context and constraints of WRITER_SYSTEM; replacing them would lose prior_contact branching, already_sent awareness, siblings context, sender_identity, step.purpose, and most lint rules.

5. **The recommendation that the fix must happen at the pipeline level, not the prompt level** — **ACCEPTED.** TASK-400's design follows this.

6. **The question TASK-391 raises: are the skills meant for generate.py or generate_campaign.py?** — **UNRESOLVED, but not blocking.** The skills are correctly wired for generate_campaign.py's batch pipeline. If generate_campaign.py becomes the production path (TASK-400's goal), the skills are operational. If generate.py remains the production path, new skills need to be written for its record-centric stages, or generate.py's prompts need to be retired in favor of generate_campaign's pipeline. TASK-400's approach (connect the pipelines) sidesteps this question productively.

7. **The risk that the skills are documentation, not operational stages** — **ACCEPTED DEFERRED RISK.** Until TASK-400 lands, the skills have no production consumer. This is the defect TASK-400 exists to fix.

8. **Overall verdict on TASK-391's finding** — **HOLDS.** The finding is correct, the evidence is sound, and TASK-400 is proceeding on solid ground.

---

### RISKS

None beyond what TASK-391 and TASK-400 already name. The finding is settled.

### RECOMMENDED CLAUDE ACTION

Move TASK-391 from REVIEW to DONE. Its finding is independently verified and TASK-400 already builds on it. No further action needed on the mismatch question itself — TASK-400's pipeline-level fix is the correct response.
