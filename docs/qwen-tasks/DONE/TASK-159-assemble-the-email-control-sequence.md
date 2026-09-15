PRIORITY: P0
DEPENDS:

# TASK-159 - assemble the CONTROL sequence from copy that already exists

## THE DECISION IS MADE. THIS IS ASSEMBLY.

`docs/EMAIL-CONTROL-2026-09-15.md` settles which copy is CONTROL:
`cadence.TEMPLATES` -> `persona_pain`, `comparable_proof`, `breakup`. They are
the pre-generation baseline, already claim-audited, carrying real variables,
and none asserts a prior message.

**Do not choose different copy. Do not write new copy.** If you conclude the
CONTROL is wrong, say so under FINDINGS and stop - that is an operator
decision, not yours.

## WHAT TO PRODUCE

A sequence SPECIFICATION complete enough that Claude can write it to
EmailBison without making a copy decision afterwards.

### 1. The opener

There is no template for day 1 - `cadence.STEPS` marks it `generated: True`.
The document names `persona_pain` as the default opener, because it is
question-led and asserts nothing about prior contact. Confirm that reading
against the actual body text, or say precisely why it fails as a first line.

### 2. Threading, per step

`EMAILBISON-COPY-REQUIREMENTS.md` is the contract and it outranks anything you
conclude: a sequence is ONE CONVERSATION, same-thread follow-ups use the
provider's `thread_reply` rather than a new subject every step, no name is
hardcoded, no greeting may render empty.

For each step say whether it OPENS the thread or REPLIES in it, and name the
field that carries that. `docs/BISON-API-ROUTE-EVIDENCE-2026-09-15.md` and
`docs/BISON-ATTRIBUTION-BOUNDARY-2026-09-15.md` already record the route
inventory - read them rather than re-probing.

A thread reply does not get a new subject. Say what the subject field must
contain for one, established rather than assumed.

### 3. Variables, and what an empty one does

These templates use `{first_name}`, `{company}`, `{angle_word}` and
`{angle_phrase}`. EmailBison has its own merge syntax. Map each one, and for
each say what renders when the value is missing.

**"Hey ," is a defect.** A greeting that can render empty fails the standing
contract. Give the fallback for every variable that can be absent.

### 4. The 17

`docs/BISON-COHORT-LIVE-2026-09-15.md` holds the cohort. For each of the 17,
does every variable this sequence needs resolve? Name the ones that do not - a
contact who cannot fill a variable is not in the first batch, and finding that
now is cheaper than finding it at the gate.

## WHAT YOU MAY NOT DO

- No provider writes. No campaign creation, no sequence write, no send.
- Reads only at EmailBison, and only what the recorded route evidence already
  establishes.
- Do not run generation against the real queue.
- Do not weaken or widen lint, claims or quality to let copy through.
- Do not write to `work/`.

## FILES ALLOWED

    docs/EMAIL-CONTROL-SEQUENCE-2026-09-15.md   (new)
    scripts/task159_*.py
    the task file itself

## FILES FORBIDDEN

    src/   work/   config/

## DELIVERABLE

The opener decision with its reasoning, the per-step threading with the field
that carries it, the variable map with empty-render behaviour and fallbacks,
and the per-contact resolution check across the 17.

## RESULT

**STATUS:** DONE

**COMMIT SHA:** 242885f

**TESTS:**
- `tests.test_cadence` — 31 tests, all pass
- `tests.test_invariants` — 80 tests, all pass
- `scripts/task159_variable_resolution.py` compiles clean; requires
  `work/queue.snapshot.jsonl` to run (not present in this worktree —
  must be run on production worktree)
- No conflict markers in src/, tests/, scripts/, or deliverable

**FILES CHANGED:**
- `docs/EMAIL-CONTROL-SEQUENCE-2026-09-15.md` (new) — the specification
- `scripts/task159_variable_resolution.py` (new) — per-contact variable check
- Task file moved from TODO/ to RUNNING/

**FINDINGS:**

1. **Opener: `persona_pain` works as first touch.** Question-led, no
   reference to prior messages, `{line}` degrades to an honest introduction
   ("I work with {sector} teams on {angle_phrase}, and I do not know how
   {company} handles it"). No new copy needed.

2. **Threading: F, T, F.** Step 1 opens, step 2 follows up in-thread
   (`thread_reply: True`), step 3 opens a new thread. The field is
   `thread_reply` boolean on each parent sequence step (PROVIDER FACT).
   A thread-reply step still carries `email_subject` — the flag is the
   mechanism, not subject omission. The provider auto-prepends "Re:" on
   all 153 same-thread follow-ups measured in the estate.

3. **Subject on thread reply:** same as step 1's rendered subject. The
   provider prepends "Re:" automatically. Do not write "Re:" yourself.

4. **EmailBison has no `{FIRST_NAME}` or `{COMPANY}` merge variable.**
   All rendering happens in Resonate OS before staging. Text travels as
   `{BODY_N}` / `{SUBJECT_N}` custom variables. The greeting is baked
   into the body text.

5. **Variable fallbacks:**
   - `first_name` → "there" (also refused by `_plan()` before reaching this)
   - `company` → NONE, raises `CompanyNameUnusable` (fail-closed, step held)
   - `angle_word` → "the numbers behind the work"
   - `angle_phrase` → "how the work is tracked"
   - `sector` → "services"
   - `line` → generic intro using sector + angle_phrase + company

6. **`company` is the only blocking variable.** A record with only a
   domain-shaped company name and no `company_facts.name` cannot render.
   The step is held, not sent. The script checks all 17 against the
   snapshot.

7. **All 17 contacts have names** (9 from provider lead rows, 8 from
   cold-cohort verification). `first_name` resolves for all 17.

8. **Signature not included.** The CONTROL templates carry no signature.
   Sender identity is Ivan, founder, Productive. Whether to append a
   signature is an operator decision.

9. **The variable resolution script must be run on production** before
   staging. It requires `work/queue.snapshot.jsonl` which is not in this
   worktree (gitignored).

**RISKS:**
- `company` may be unresolvable for some of the 8 cold-cohort contacts
  if they lack `company_facts.name`. The script will identify them.
- The F,T,F threading pattern is a design choice, not evidence-backed.
  The estate cannot separate same-thread from new-thread at any position.
- 17 contacts is below the ~50 target. Enough for a canary.
- The signature gap: templates have none, the ladder now instructs the
  generator to include one. CONTROL templates predate that fix.

**RECOMMENDED CLAUDE ACTION:**
1. Run `scripts/task159_variable_resolution.py` on the production worktree
   to confirm all 17 contacts have resolvable variables
2. Review `docs/EMAIL-CONTROL-SEQUENCE-2026-09-15.md`
3. Decide on signature (append or not)
4. Create the campaign and stage the sequence
5. Read back from EmailBison before promoting
