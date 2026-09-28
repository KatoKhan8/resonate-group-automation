PRIORITY: P1
SIZE: M
DEPENDS:

# TASK-391 — skills consumed at runtime by the REAL production entrypoint

TASK-375 wired all five skills into `generate_campaign.py` — but TASK-375
and TASK-379 (GLM) both independently confirmed `generate_campaign.generate()`
has zero production callers. The actual production path is `src/generate.py`
(record-centric, `python -m src.generate --live`, its own
diagnose/hook/persona_angle/draft pipeline). **The skills are wired into a
pipeline nothing runs, not the pipeline that runs.**

## Trace first

1. Read `src/generate.py`'s stage functions (`diagnose`, `hook`,
   `persona_angle`, `draft`, and whatever else calls a model). Which raw
   prompt constants do they use, and do any already resemble one of the five
   skills' procedures?
2. Do NOT assume the five skills map cleanly onto `generate.py`'s stages —
   `generate_campaign.py`'s pipeline (ICP → extract → hypothesis → match →
   strategy → writer) may not be `generate.py`'s pipeline. Name the mismatch
   if there is one, honestly, rather than forcing a skill onto a stage it
   was not written for.

## Build only what the trace supports

Wire whichever skills genuinely correspond to a `generate.py` stage, the
same way TASK-375 did: `skills.load(name).procedure` replaces the raw
constant, proven by a sentinel-injection test showing the patched procedure
reaches the model through `generate.py`'s real call path — not a direct
call to the skill.

## Acceptance

1. Name, with file:line, each `generate.py` stage and whether a skill now
   feeds it, or why not (no corresponding skill exists).
2. Sentinel test per wired skill: patch procedure, run `generate.py`'s real
   entrypoint, prove the model saw the patch. Guard-failure: revert, confirm
   the test fails for the right reason, restore.
3. Full suite: wait for `work/suite_verdict.txt`, diff the failing-name SET.

## What this task may NOT do

- Do not change generate.py's stage logic or prompts, only which system
  prompt source each stage reads from.
- Nothing sent, nothing activated. Production freeze - generate.py --live
  is the real send path; this task runs it in dry/test mode only.

---

## TRACE RESULT

### The five stages in `src/generate.py` that call the model

| # | Stage | File:Line | Prompt source | What it does |
|---|-------|-----------|---------------|--------------|
| 1 | `diagnose` | `src/generate.py:1486` | `prompts/diagnose.md` via `render_prompt("diagnose", rec)` | Analyses a dead CRM thread to find the exact moment it broke. Revive lane only. |
| 2 | `hook` | `src/generate.py:1500` | `prompts/hook.md` via `render_prompt("hook", rec)` | Finds one specific, checkable fact about the company from the signal. Cold lane only. |
| 3 | `persona_angle` | `src/generate.py:1508` | `prompts/persona_angle.md` via `render_prompt("persona_angle", rec, contact, client)` | Matches a contact to one of the client's configured persona angles with traceable evidence. Domains lane only. |
| 4 | `linkedin_note` | `src/generate.py:1540` (in-function) | `prompts/linkedin_note.md` via `render_prompt("linkedin_note", rec, contact, client, step_key)` | Writes ONE LinkedIn message at a time. Per-step, per-contact. |
| 5 | `draft` | `src/generate.py:1611` | `prompts/draft.md` via `render_prompt("draft", rec, contact, client, day)` | Writes ONE email at a time (subject + body). Per-step, per-contact. |

All five read their prompt text from `prompts/*.md` files via `prompt_text(name)` at `src/generate.py:168-170`, and assemble record-specific context via `context_for(step, ...)` at `src/generate.py:581-720`.

### The five skills and what they wrap

| Skill | Procedure source | Consumer | Pipeline |
|-------|-----------------|----------|----------|
| `signal_verification` | `copyprompts.ICP_SYSTEM` | `stage_a` | `generate_campaign.py` |
| `account_research` | `copyprompts.EXTRACT_SYSTEM` | `stage_b` | `generate_campaign.py` |
| `campaign_strategy` | `copystages.STRATEGY_SYSTEM` | `stage_e` | `generate_campaign.py` |
| `cold_email_writing` | `copystages.WRITER_SYSTEM` | `stage_f` | `generate_campaign.py` |
| `linkedin_writing` | `copystages.WRITER_SYSTEM` | `stage_f` | `generate_campaign.py` |

### The mismatch — named honestly

The two pipelines are architecturally different. This is not a naming difference; it is a structural one.

**`generate.py` writes ONE item at a time.** Each stage call produces a single JSON object: `{"died_on":..., "died_because":...}` for diagnose, `{"hook": "..."}` for hook, `{"angle": "...", "evidence": [...]}` for persona_angle, `{"note": "..."}` for linkedin_note, `{"subject": "...", "body": "..."}` for draft. The prompt is assembled per-step with record-specific context (prior_contact, already_sent, siblings, angle_wording, sender_identity, product, diagnosis, hook, tone, research).

**The skills write a BATCH.** `cold_email_writing` and `linkedin_writing` both wrap `copystages.WRITER_SYSTEM`, which expects a plan as input and returns a complex JSON with ALL five emails, three subjects, two P.S. lines, and four LinkedIn messages in one call. `signal_verification` returns `{"is_agency": bool, ...}` — a different question than any `generate.py` stage asks. `account_research` returns 3-5 structured facts with quotes and source indices — a different shape than `hook`'s one-sentence output. `campaign_strategy` plans a nine-message sequence — a stage that does not exist in `generate.py` at all.

### Stage-by-stage mapping

1. **`diagnose` → NO SKILL.** Revive-lane specific. Analyses a dead CRM thread. No skill covers thread diagnosis.

2. **`hook` → NO SKILL.** Both `hook` and `account_research` find facts, but:
   - `hook` extracts ONE checkable fact from a signal trigger (`prompts/hook.md`: `{"hook": "one sentence"}`)
   - `account_research` extracts 3-5 structured facts with verbatim quotes from scraped sources (`copyprompts.EXTRACT_SYSTEM`: `{"facts": [...], "angle": ..., "company_hook": ...}`)
   - Different input (signal vs. sources), different output shape, different prompt. Forcing `EXTRACT_SYSTEM` onto `hook` would make the model return a multi-fact JSON that `generate.py:1501-1503` cannot parse (it reads `data["hook"]`).

3. **`persona_angle` → NO SKILL.** Matches a contact to a configured angle. `signal_verification` asks "is this an agency?" (a different question). No skill performs persona-angle matching.

4. **`draft` → `cold_email_writing` DOES NOT MAP.** Both write emails, but:
   - `draft` writes ONE email per call: `{"subject": "...", "body": "..."}` from `prompts/draft.md`
   - `cold_email_writing` writes ALL five emails + LinkedIn in one call: complex JSON from `copystages.WRITER_SYSTEM`
   - The context assembly is different: `context_for("draft", ...)` at `src/generate.py:640-720` builds `prior_contact`, `already_sent`, `siblings`, `angle_wording`, `sender_identity`, `product`, `tone`, `diagnosis`, `hook`, `sizing`. `copystages.writer_user()` at `src/copystages.py:368-379` builds a different context from a plan, facts, and capability sentence.
   - Swapping `WRITER_SYSTEM` into `draft` would make the model return a batch JSON; `generate.py:1637-1640` reads `data["subject"]` and `data["body"]` — the parse would fail.

5. **`linkedin_note` → `linkedin_writing` DOES NOT MAP.** Same structural mismatch as draft:
   - `linkedin_note` writes ONE note per call: `{"note": "..."}` from `prompts/linkedin_note.md`
   - `linkedin_writing` writes ALL four LinkedIn messages in one call from `copystages.WRITER_SYSTEM`
   - Swapping would break the parse at `generate.py:1558` (`data["note"]`).

### Conclusion

**Zero skills can be wired into `generate.py`'s stages.** The task anticipated this: "Do NOT assume the five skills map cleanly onto `generate.py`'s stages... Name the mismatch if there is one, honestly, rather than forcing a skill onto a stage it was not written for."

The mismatch is real and structural. The skills were designed for a batch pipeline (`generate_campaign.py`) that plans a full sequence and writes all messages at once. `generate.py` is a record-centric pipeline that writes one message at a time with rich per-step context. The prompt texts, output schemas, and context assembly are all different. Wiring a skill procedure into a `generate.py` stage would break the JSON parse at the other end.

TASK-375 wired the skills into the correct pipeline for those skills (`generate_campaign.py`). That pipeline has zero production callers, which is a separate problem (the skills are consumed within their pipeline, just the pipeline itself is not called). The answer to "skills are wired into a pipeline nothing runs" is to wire callers to `generate_campaign.py`, not to force the skills into a different pipeline whose architecture they do not fit.

---

## RESULT BLOCK

- **STATUS:** DONE (finding — no code artifact, the trace proves a negative)
- **KIND OF ARTIFACT:** finding (read-only investigation)
- **COMMIT SHA:** 7e4d7ab7 (task claim only; no code changes)
- **TESTS:** N/A — no code changed, no wiring performed
- **FILES CHANGED:** only the task file moved TODO → RUNNING
- **FINDINGS:**
  1. `generate.py` has five model-calling stages: `diagnose` (1486), `hook` (1500), `persona_angle` (1508), `linkedin_note` (~1540), `draft` (1611). All read from `prompts/*.md` files.
  2. All five skills wrap prompts from `copystages`/`copyprompts` designed for `generate_campaign.py`'s batch architecture.
  3. No skill maps cleanly onto any `generate.py` stage. The mismatch is structural: one-item-at-a-time vs. batch, different output schemas, different context assembly.
  4. Wiring a skill procedure into a `generate.py` stage would break the JSON parse (the model would return a different shape than the stage reads).
  5. The real problem is that `generate_campaign.py` has zero callers, not that the skills are in the wrong pipeline. The skills are correctly placed for their architecture.
- **RISKS:** The finding is a negative (nothing to wire), which is harder to verify than a positive. The evidence is the structural analysis above: prompt texts, output schemas, context assembly, and parse code at specific file:line references.
- **RECOMMENDED CLAUDE ACTION:**
  1. Accept the finding: the skills do not map onto `generate.py`'s stages.
  2. The real problem is `generate_campaign.py`'s lack of callers. A separate task should either wire callers to it or decommission it.
  3. If the intent is to unify the two pipelines, that is a larger task than "wire skills" — it is "redesign generate.py to be batch-oriented" or "redesign the skills to be per-item."
