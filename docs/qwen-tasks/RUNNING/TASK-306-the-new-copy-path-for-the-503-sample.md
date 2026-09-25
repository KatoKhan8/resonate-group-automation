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
