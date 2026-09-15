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
