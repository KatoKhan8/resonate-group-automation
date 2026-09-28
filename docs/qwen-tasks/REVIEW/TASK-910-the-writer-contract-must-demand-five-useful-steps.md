PRIORITY: P0
SIZE: S
DEPENDS:

# TASK-910 — five useful steps or a generation failure, and the normaliser on the canonical path

**Operator ruling, Zvonimir, 2026-09-28. Two minimal corrections and their
regressions. NOTHING ELSE.** This is the last thing between the operator and
the one-account review artifact.

**Land ONLY these three things:**

1. the writer-contract correction in `src/copystages.py`
2. the existing punctuation normaliser on the canonical path in
   `src/generate_campaign.py`
3. narrowly scoped regressions for those two changes

**Do NOT weaken `copylint`. `STEPS_EXPECTED = 5` is correct and stays.** The
operator's words: *"The contradiction was upstream in the writer contract, not
downstream in the gate."*

---

## CORRECTION 1 — the writer contract (`src/copystages.py`, ~line 237)

### The measured defect
The writer obeys its prompt and the gate refuses the result. Raw output, three
attempts, all five keys always present:

    attempt A   em1 385  em2 351  em3 347  em4 0    em5 0
    attempt B   em1 385  em2 0    em3 0    em4 0    em5 0
    attempt C   em1 385  em2 338  em3 275  em4 0    em5 291

Because the prompt currently says:

> **"IF A STEP HAS NO CREDIBLE NEW ANGLE, SAY SO AND SET IT null."** A sequence
> of four good messages beats five where one is filler. That is a real
> outcome, not a failure.

while `copylint.empty_step` refuses any empty step. Three attempts cannot
converge because the two contracts disagree, and the retry loop feeds back a
refusal the prompt tells the model to ignore.

### REMOVE that instruction. REPLACE it with EXACTLY this operator text:

    You must return all five sequence steps. Each step must have a distinct
    useful role in the sequence. Do not invent a new fact merely to create
    another angle. Do not return null or omit a required step. If the
    available evidence cannot support five credible messages without
    fabrication or meaningless repetition, return a generation failure rather
    than an incomplete sequence.

**This is the operator's wording. Do not paraphrase it, do not "improve" it,
do not add to it.**

### The distinction that must survive — read it before editing
The ruling is **NOT** "five unconditionally, filler accepted". The operator was
explicit: **filler is not accepted.**

    REQUIRED      5 complete steps, each with a distinct useful role
    NOT ALLOWED   filler; fabricated facts; unsupported claims; meaningless
                  paraphrases of the previous email

**If five credible messages genuinely cannot be produced, generation FAILS.**
The writer already has `hold` / `hold_reason` in its output schema
(`src/skills/cold_email_writing.py`) — **that is the existing mechanism for
"return a generation failure", and it must be used rather than a new one.** Do
not add a state, a flag, an error class or a config key.

**Do not touch the rest of the prompt.** The step-role description
(`em1` day 1 new thread, `em2` day 4 reply, ... `em5` day 21 new thread) is
correct and stays.

---

## CORRECTION 2 — the normaliser lost its caller (`src/generate_campaign.py`)

`lint.normalise_punctuation` maps the five substituted characters to what a
person would have typed. It is called on the **legacy** path in five places —
`src/generate.py:1396`, `:1559`, `:1648`, `:1649`, and
`src/variantgen.py:609`, `:611` — and has **ZERO callers in
`src/generate_campaign.py`**, the entrypoint TASK-400 made canonical. So
`U+2019` survives into lint and refuses the LinkedIn notes:

    connect  U+2019     msg1  U+2019     msg2  none     msg3  U+2019

**Call the existing function** at the equivalent point the legacy paths use it:
on the generated subject/body/note text after parsing the writer output and
**before** `copylint.check_batch`. Apply it to the email bodies, the subjects,
the `ps_*` values and the LinkedIn notes — everything prospect-facing that the
writer produced.

**Do not write a new normaliser. Do not extend `_PUNCTUATION_MAP`. Do not
touch `src/lint.py` or `src/copylint.py`.**

---

## Acceptance

1. **The prompt no longer contains the contradictory instruction**, and carries
   the operator's replacement text verbatim.
2. **`copylint` is untouched.** `STEPS_EXPECTED` is still 5 and `empty_step`
   still refuses an empty step. Assert this, do not just leave it alone.
3. **U+2019 PASSES after normalisation:** copy containing a curly apostrophe is
   normalised to a straight ASCII apostrophe and **is not refused**.
4. **AN EM DASH STILL FAILS.** Copy containing a real em dash normalises to
   `" - "` and `copylint.DASH_RE` **still catches the spaced hyphen**. This is
   the operator's explicit acceptance requirement: the change **must not
   weaken the intentional no-em-dash policy**. *"The tell survives the
   substitution."*
5. **Both cases above are pinned by a regression test** that would fail if the
   normaliser were moved, removed, or widened.
6. **The retry feedback is semantically actionable.** Verify — do not redesign
   the retry system — that the exact rejection string fed back through
   `RETRY_BLOCK` is something the writer can now act on under the new contract,
   i.e. it is no longer told to leave a step null and simultaneously that an
   empty step is forbidden. **State in your result block what the fed-back
   string now is.**
7. **MUTATION:** revert the normaliser call; acceptance 3 must go red for that
   reason with no other guard firing first. Restore and verify
   **byte-identical by sha256**. Files are **CRLF** — an `\n`-anchored regex
   matches zero times and the mutation becomes a silent no-op.

### ACCEPTANCE COMMANDS — run these exactly and paste the real output

**These must stay in THIS section.** GLM's extractor enters at the first
`## Acceptance` heading and stops at the next `## `; only lines beginning
`py -3`, `python`, `grep` or `scripts/` are taken.

    py -3 -m unittest tests.test_generate
    py -3 -m unittest tests.test_copylint
    py -3 -m unittest tests.test_lint
    py -3 -m unittest tests.test_render_preview
    py -3 -m unittest tests.test_task904_opt_out
    py -3 -m unittest tests.test_task905_projection_from_plan
    py -3 -m unittest tests.test_task906_signature_composed_into_copy
    py -3 -m unittest tests.test_task908_approval_hash_covers_sender
    py -3 -m unittest tests.test_approve

**The punctuation assertion, both directions, which is the operator's stated
acceptance** — exits 0 only when the apostrophe is rescued AND the em dash is
still caught:

    py -3 -c "import sys; from src import lint, copylint; a=lint.normalise_punctuation(chr(8216)+'we'+chr(8217)+'re here'+chr(8217)); b=lint.normalise_punctuation('clauses'+chr(8212)+'like this'); ok_a = not copylint.DASH_RE.search(a) and chr(8217) not in a; ok_b = bool(copylint.DASH_RE.search(b)); sys.exit('apostrophe not rescued: %r'%a) if not ok_a else (sys.exit('EM DASH NO LONGER CAUGHT: %r'%b) if not ok_b else print('OK: apostrophe rescued, em dash still caught'))"

    py -3 -c "import sys; from src import copylint; sys.exit('STEPS_EXPECTED changed: %r'%copylint.STEPS_EXPECTED) if copylint.STEPS_EXPECTED!=5 else print('OK: STEPS_EXPECTED still 5')"

    grep -c "beats five where one is filler" src/copystages.py

**The grep must print `0`.** **Read exit codes OFF THE PROCESS, never through
a pipe** — `| tail` masks a failure and reports 0.

## Files
`src/copystages.py` and `src/generate_campaign.py` only, plus your own tests.
**Do NOT touch** `src/copylint.py`, `src/lint.py`, `src/render.py`,
`src/bisonfactory.py`, `src/trailingcontent.py`, `src/optout.py`,
`src/sequenceplan.py` or `src/generate.py`.

## RULES THAT OUTRANK FINISHING

- **START FROM A CLEAN BRANCH OFF `origin/master`**; verify HEAD equals
  `origin/master` before working.
- **NEVER WIDEN A GATE TO MAKE COPY PASS.** That is the whole point of this
  task: the gate was right and the prompt was wrong.
- **A test count is never a PASS.** Name the path, the negative control, the
  killed mutation.
- **Do not report a PREDICTED result.** Run it and measure it.
- **PROVIDER WRITES = 0.** `sending.live` false, freeze active. Nothing sent,
  enrolled or attached.
- Production `work/` is **READ-ONLY**; this task needs no estate data.
- **Write suite logs OUTSIDE the repository.** A suite with no `Ran N tests`
  line is an **absent measurement, not a failure**.
- Baseline `docs/state/SUITE-BASELINE-2026-09-26.txt` compared **AS SETS,
  NEVER COUNTS**, and is **known stale** (TASK-549).
  `test_set_regeneration...replaces_all_notes` fails on master at `5 != 6`
  with no branch — not yours.
- Commit and push to your own branch, **verify the remote with
  `git rev-parse`**. Do NOT merge to master. Do NOT post to Slack.
- Report **CLAIM / AUTHORITY / MEASURED AT / STATE** and your exact branch
  head SHA.

**After this lands, Claude regenerates 2020 Companies / Rachele Crumpler and
delivers the review to `#resonate-os`. Do not generate anything yourself and do
not select another account.**
