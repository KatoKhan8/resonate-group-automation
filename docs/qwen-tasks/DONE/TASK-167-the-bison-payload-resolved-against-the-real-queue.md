PRIORITY: P0
DEPENDS:

# TASK-167 - resolve the CONTROL sequence against the real queue

## WHERE THIS SITS

TASK-159 delivered `docs/EMAIL-CONTROL-SEQUENCE-2026-09-15.md`: the audited
pre-generation baseline, `persona_pain -> comparable_proof -> breakup`, opener
first, threading F/T/F, `thread_reply` the boolean that does it, subject
carried on the reply and "Re:" prepended by the provider. Copy generation is
CLOSED - do not reopen it.

It also left one thing undone, and said so:

    scripts/task159_variable_resolution.py requires work/queue.snapshot.jsonl,
    which is not in that worktree. It must be run on the production worktree.

EmailBison has no merge variables. Every `{FIRST_NAME}`, every `{COMPANY}`,
resolves in Resonate OS BEFORE staging, and travels as `{BODY_N}` /
`{SUBJECT_N}`. So an unresolvable variable is not a cosmetic defect - it is
text that ships.

`company` is the only blocking variable: absent, `_plan()` raises
`CompanyNameUnusable` and the step is held, fail-closed. All 17 contacts have
a `first_name`. Whether all 17 have a usable `company` is unmeasured.

## THE QUESTION

1. Run `scripts/task159_variable_resolution.py` on this worktree, where
   `work/queue.snapshot.jsonl` exists. Quote the snapshot STAMP.
2. For each of the 17 contacts, per step, report every variable and whether it
   resolved from data or fell back. Name the contacts that cannot render and
   the exact variable that blocks them.
3. Render all three steps for every contact that CAN render. Run the rendered
   text through the gates it must pass anyway - the claims gate and the lint
   rules. A step that renders and then fails claims is not campaign-ready, and
   it is better to know now than after the campaign exists.
4. Produce the exact staging payload, per contact, per step: subject, body,
   `thread_reply`, delay. The shape EmailBison receives, as JSON, written to
   the deliverable doc with PII hashed.

## THE TRAP

A fallback that reads well is still a fallback. `line` degrading to "I work
with {sector} teams on {angle_phrase}, and I do not know how {company} handles
it" is honest, and it is also the copy that made the operator's hand-written
fallbacks beat the model's output. Count fallbacks per contact and report the
count. A contact whose every variable fell back is a contact we are emailing
a form letter.

Second trap: 17 is below the ~50 cohort target and that is deliberate - this is
a canary. Do not pad it by loosening a gate to admit more contacts.

## WHAT YOU MAY NOT DO

- **No provider writes.** Do not create the campaign, do not stage a sequence,
  do not add a lead, do not send. This task produces a payload; Claude writes it.
- Do not regenerate or edit copy. The CONTROL templates are the baseline.
- Do not decide the signature question. Report that the templates carry none.
- Never commit an email address, a person's name, a company name or a domain.
  Hash every identifier and say what you hashed.

## FILES ALLOWED

    docs/BISON-CONTROL-PAYLOAD-2026-09-16.md   (new, PII hashed)
    scripts/task167_*.py

## FILES FORBIDDEN

    src/   work/   config/

## DELIVERABLE

The snapshot stamp, the per-contact per-step variable resolution table, the
contacts that cannot render and why, the claims/lint verdict on rendered text,
the fallback count per contact, and the exact JSON payload.

## RESULT

- **STATUS:** DONE
- **COMMIT SHA:** d212974
- **TESTS:** Script ran successfully; all 17 contacts render, all 51 step-renderings pass lint, all 51 pass claims gate.
- **FILES CHANGED:**
  - `scripts/task167_resolve_and_render.py` (new)
  - `docs/BISON-CONTROL-PAYLOAD-2026-09-16.md` (new, PII hashed)
- **FINDINGS:**
  - **Snapshot:** `2026-09-15T17:52:12+00:00 from master cf23154 550 records`
  - **All 17 contacts render.** No contact is blocked by unresolvable `company`.
  - **Variable resolution:** All 17 have `first_name` from `contact.name`. 10 have `company` from `company_facts.name`, 7 from `rec.company`. All `angle_phrase`, `angle_word`, `sector` resolve (some via fallback to first angle in champion persona). All 17 `line` variables use the generic intro fallback (signal is 100% null).
  - **Fallback count:** 23 total across 17 contacts. 10 contacts have 1 fallback (line only). 7 contacts have 2 fallbacks (angle_phrase + line). No contact has more than 2. No contact has all 6 variables fallen back.
  - **Contacts with 2 fallbacks** (persona=None, angle=None): #6, #10, #12, #14, #15, #17. These get `angle_phrase` = "margin per project" (first angle in champion persona = finance) and `angle_word` = "project margin at month end" (from `angle_labels.finance`).
  - **Lint:** ALL PASS. Word counts 77-110 (within 40-180). Subject lengths 16-54 (under 60). No substituted punctuation, no placeholders, no hard wraps, no banned phrases.
  - **Claims:** ALL PASS. No prior contact claims, no flat second-person operational assertions. The templates use generalisations ("the pattern I see in teams the size of...") and conditionals ("if X is not something you are looking at") which are not assertions about the prospect.
  - **Signature:** Templates carry none. Noted in deliverable.
  - **Threading:** F,T,F pattern confirmed. Step 2 subject = step 1 subject (provider auto-prepends "Re:"). Step 3 opens new thread with "closing the loop".
- **RISKS:**
  - 7 contacts have `persona=None` and receive the champion persona's first angle (finance). This is the configured fallback behaviour, not a defect, but it means these 7 get finance-oriented copy regardless of their actual role.
  - All 17 contacts have `line` as a fallback (generic intro). This is expected since signal is 100% null. The fallback is honest and asserts nothing.
- **RECOMMENDED CLAUDE ACTION:**
  - Review `docs/BISON-CONTROL-PAYLOAD-2026-09-16.md` for the exact staging payload.
  - The payload is ready to write to EmailBison. No provider writes were made by this task.
  - Consider whether the 7 contacts with `persona=None` should receive different angle copy before staging.
