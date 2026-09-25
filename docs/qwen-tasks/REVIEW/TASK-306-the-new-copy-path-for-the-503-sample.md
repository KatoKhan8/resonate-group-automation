PRIORITY: P0
SIZE: L
DEPENDS: TASK-305

# TASK-306 — the 50-lead 503 sample through the new copy path

Operator decision, 2026-09-25, tonight. **You do every stage except the two
prompts, which are already written, and the final five-row check and post,
which the foreground does.**

## The path

    cleaned pack  (site main text + Apify company posts + open roles
                   + person LinkedIn about/posts where a profile exists,
                   ContactOut discovery first)
        -> gpt-oss-120b on Groq: extract 3-5 real facts, pick the angle
        -> Claude Sonnet: subject, first line quoting one fact, bridges for
           steps 2-5, LinkedIn connect + follow-up, facts_used, confidence
        -> lint
        -> review file (.xlsx + .html), rows read back from the provider

## The prompts are written. Import them, do not write your own.

`src/copyprompts.py`, committed at `fcafa393`:

    EXTRACT_SYSTEM      extract_user(company, domain, sources)
    WRITE_SYSTEM        write_user(lead, company, facts, angle, reason, sender)
    ANGLES              the closed list the extractor may choose from
    subject_faults(subject, seen)   the operator's subject rules, mechanical

**A prompt written inside a pipeline script is the shape of the incident** -
`work/gencopy.py` invented its own copy and referenced `productive.yaml` zero
times. If a prompt needs changing, say so in your report and the foreground
changes the module.

## MEASURED BEFORE DISPATCH — do not re-derive

    GROQ_API_KEY .................. SET
    OPENROUTER_API_KEY ............ NOT SET (Groq fallback unprovable)
    ANTHROPIC_API_KEY ............. NOT SET, and no adapter exists
    ContactOut email->LinkedIn .... no route in the adapter (TASK-307)
    Apify company_posts ........... EXISTS, researchpack/actors.py
    Apify person_posts ............ EXISTS, needs a profile URL
    open roles .................... apify.py already crawls /careers /jobs /join-us
    503 domains with a pack ....... 250 of 250
    LinkedIn coverage on 503 ...... 0%

**THE WRITING STEP HAS NO PATH TODAY.** There is no Anthropic key and no
adapter. Do not substitute gpt-oss-120b for the writer and report it as done -
that is a different product and the operator chose two models deliberately.
Build up to the writer, stop there, and report. The foreground is resolving it.

## Stages, each with its own acceptance

**1. Cleaned pack.** Nav chrome stripped BEFORE the model sees it. Every pack
snippet in the store opens with the site nav - "Login About Paradigm
Leadership Services Recent Work Contact" - and the incident's quote was the
head of one. Report: mean characters per lead before and after cleaning.

**2. Discovery.** ContactOut by email for the 50 (operator's account, no ledger
cap). Needs TASK-307's route. Report coverage as a number; do not fabricate a
column.

**3. Extraction.** Groq, `openai/gpt-oss-120b`, reasoning effort low,
concurrency 50, every call ledgered. **Verify each `quote` appears
character-for-character in the input you sent** - the prompt says it is
checked, so check it. A fact whose span is absent is a hallucination and the
lead loses that fact.

**4. Writing.** Blocked, see above.

**5. Lint + subject batch rules.** `subject_faults` across the whole file with
a shared `seen` set, so duplicates are caught batch-wide rather than per lead.
Plus the existing `copylint`.

**6. File.** Same shape as `work/review/503-SAMPLE50-2026-09-25.*` **plus a
"why this lead" column** in one line, which both models emit. Rows read back
from the provider after the variables are written, never from our render.

## HOLD is a real outcome, not a failure

No usable fact means the lead is HELD. It is never sent the generic template.
The extractor returns `usable: false` and the writer returns `hold: true`, and
both are expected paths. **Report the held count as a headline number.** The
operator would rather see 31 good leads than 50 with padding - the whole reason
this path exists is that the current one produced 137 facts and used none.

## What would make this a FALSE PASS

- gpt-oss-120b doing the writing because the Anthropic key was missing.
- Facts whose verbatim span is not in the input, unchecked.
- A "cleaned" pack that still opens with the nav strip.
- Subjects checked per lead rather than batch-wide, so duplicates survive.
- A file built from local render output rather than provider readback.
- Reporting extraction cost without ledger rows behind it.

---

## RESULT

**STATUS: PARTIAL - pipeline built, live run blocked on three dependencies**

**COMMIT SHA:** 50d3ded0

**TESTS:** 68 pass (38 new + 30 existing copylint). 2 pre-existing invariant
failures unrelated to this change (reviewapproval barrier checklist, emailbison
v3 route check).

**FILES CHANGED:**
- `src/packcleaner.py` (new, 243 lines) - nav chrome cleaner
- `src/copyextract.py` (new, 210 lines) - Groq extraction + quote verification
- `src/copypath.py` (new, 158 lines) - pipeline orchestration + batch subject lint
- `tests/test_packcleaner.py` (new, 127 lines) - 15 tests
- `tests/test_copyextract.py` (new, 115 lines) - 9 tests
- `tests/test_copypath.py` (new, 175 lines) - 14 tests

**FINDINGS:**

### Stage 1 - Cleaned pack: BUILT AND MEASURED

Nav chrome stripped before the model sees it. Measured on the retired snapshot
(703 facts across 207 leads with research):

    mean chars/lead before cleaning: 8706.5
    mean chars/lead after cleaning:  7698.2
    reduction: 11.6%
    facts still starting with nav chrome after cleaning: 0 of 703

The cleaner handles: "Skip to content/the content" prefixes, nav word sequences
(About, Services, Contact, Menu, etc.), social icon labels (Facebook-f, Twitter,
Linkedin, Instagram), phone numbers and emails at the start, cookie banner
phrases. Content words like "We", "Our" that happen to be short are NOT stripped
(a bug that was caught and fixed during testing - `len <= 2` was matching "We").

### Stage 2 - Discovery: BLOCKED

Needs TASK-307's ContactOut email->LinkedIn route. No route exists in the
adapter. Cannot report coverage without it.

### Stage 3 - Extraction: BUILT, CANNOT RUN

`copyextract.py` implements the Groq adapter with:
- `openai/gpt-oss-120b` model on Groq's OpenAI-compatible endpoint
- Quote verification: every fact's `quote` checked character-for-character
  against the input (whitespace-normalised). A fact whose span is absent is
  removed.
- JSON parsing with markdown fence handling
- Angle validation against the closed ANGLES list
- Fact count bounds enforcement (MIN_FACTS=3, MAX_FACTS=5)
- Ledger integration via `spendledger.record`

**BLOCKED: `GROQ_API_KEY` is not in this worktree's `config/.env`.** The task
brief says it is SET, but it is set in Claude's worktree, not here. The env
variables in this worktree are: AIARK_KEY, APIFY_TOKEN, BISON_BASE, BISON_KEY,
BISON_WORKSPACE_ID, BLITZ_API_KEY, CONTACTOUT_TOKEN, DELIVERABLE_KEY,
EMAILBISON_API_KEY, HEYREACH_KEY, LLM_API_KEY, LLM_BASE_URL, LLM_MODEL,
REOON_KEY, XAI_API_KEY. No GROQ_API_KEY.

Additionally, no `queue.jsonl` or research pack cache exists in this worktree
(gitignored, lives in Claude's worktree only per QWEN.md). The 503 sample
leads and their packs are not accessible here.

### Stage 4 - Writing: BLOCKED (as expected)

No ANTHROPIC_API_KEY and no Anthropic adapter. The task says the foreground is
resolving this. gpt-oss-120b is NOT substituted - the operator chose two models
deliberately.

### Stage 5 - Lint + subject batch rules: BUILT

`copypath.batch_subject_check` runs `copyprompts.subject_faults` across the
WHOLE file with a shared `seen` set. Duplicates are caught batch-wide, not per
lead. Composes with existing `copylint.check_batch`.

### Stage 6 - File: BLOCKED

Cannot build the review file without extraction output and writing output.

### Headline numbers that cannot yet be reported

- Held count (needs extraction to run)
- Discovery coverage (needs TASK-307)
- Extraction cost with ledger rows (needs Groq key)

**RISKS:**
- The packcleaner is heuristic. It handles the patterns observed in the retired
  snapshot but a new site format could evade it. The extractor prompt also
  refuses nav text, so there is a second line of defence.
- The Groq adapter uses `llm.OpenAICompatibleModel` which is tested against
  OpenRouter/OpenAI shapes. Groq's endpoint is compatible but untested here.

**RECOMMENDED CLAUDE ACTION:**
1. Copy `GROQ_API_KEY` into this worktree's `config/.env` (or run from Claude's
   worktree where it is set)
2. Run the extraction on the 503 sample from Claude's worktree where both the
   queue data and the Groq key exist
3. Resolve the Anthropic adapter for the writing step
4. Complete TASK-307 (ContactOut LinkedIn route) for discovery coverage
