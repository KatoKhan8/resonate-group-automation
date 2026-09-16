# Only the opener owns a subject — 2026-09-16

## The invariant

The operator verified the desired behaviour in the EmailBison UI: **follow-ups
must stay in the original thread, and only the opener owns a subject.**

    em1   NEW EMAIL   thread_reply false, subject_1 + body_1
    em2   FOLLOW-UP   thread_reply TRUE,  body_2, NO new subject
    em3   FOLLOW-UP   thread_reply TRUE,  body_3, NO new subject

No `subject_2`, no `subject_3`, no `subject_4`, no `subject_5`. And no
simulated threading - nothing may construct `Re: subject_2`. The provider's
thread-reply mechanism owns threading.

## The design

Every step's `email_subject` references `{SUBJECT_1}`. The opener sends it as
the subject. The follow-ups are thread replies, so the provider continues the
original thread and prepends `Re:` itself. There is exactly ONE subject
variable per lead - `subject_1` - and no `subject_2` or `subject_3` exists to
be generated, approved, or accidentally sent.

## What changed

### Config (`config/clients/productive.yaml`)

- `thread_reply_pattern` changed from `[false, true, false]` to
  `[false, true, true]`.
- em2 and em3 subjects changed from `{SUBJECT_2}` / `{SUBJECT_3}` to
  `{SUBJECT_1}`.

### Variables (`src/bisonfactory.py`)

- `_variables_for` now accepts a `sequence` parameter. For threaded follow-up
  steps, it writes `subject_{n}` as empty. The provider never receives a
  non-empty follow-up subject.
- `_stale_clearances` extended to clear in-range follow-up subjects
  (`subject_2..N`) for threaded sequences, in addition to out-of-range
  positions. A threaded 3-step sequence clears `subject_2..6` AND `body_4..6`.
- `_sequence_steps` validates the threaded invariant: when the sequence has at
  least one threaded follow-up, every follow-up must either be threaded or
  reference the opener's subject. A mixed shape is refused.

### Comparator (`src/configdiff.py`)

- `_expected_lead_variables` empties follow-up subjects for threaded steps,
  matching `_variables_for`.
- `approved_bison` and `provider_bison` both include `thread_replies` in the
  comparison.
- `REQUIRED_BISON` includes `thread_replies`, so the comparator proves which
  steps are thread replies.

### Approval (`src/approve.py`, `src/approval.py`)

No changes to the fingerprint function. The fingerprint still covers the
subject (because it's part of the step definition). The comparator understands
that the subject for a threaded step is not independent prospect-facing
content.

## The trap

Do not "fix" this by writing `Re:` into a subject yourself. The provider
prepends it, `_comparable_step` already normalises it for comparison, and
`EMAILBISON-COPY-REQUIREMENTS.md` says not to write it. A hand-built `Re:`
chain is simulated threading, which is the thing being forbidden.

## Campaign 485

Campaign 485's sequence cannot be corrected in place. `bison.set_sequence`
APPENDS - no replace, no per-step delete. The campaign must be rebuilt. That
is provider truth making it unusable, which is the operator's stated trigger
for a new campaign. Claude rebuilds the campaign after this lands.

## Tests

`tests/test_threaded_sequence.py` carries 18 tests:

- 4 negative tests (the deliverable that matters most): em2/em3 non-threaded
  with distinct subject is refused, both at the unit level and through the
  full staging entry point.
- 6 stale clearance tests for the threaded shape.
- 4 variable shape tests.
- 4 integration tests driving `stage()` through the real entry point.

## Known breakage

The validation refuses the old mixed config shape (some follow-ups threaded,
others not, with distinct subjects). Test files that use this shape
(`test_compare_bison.py`, `test_no_activation_without_an_exact_match.py`) need
their configs updated to either the threaded shape or a fully non-threaded
shape. These files are outside TASK-219's FILES ALLOWED and need Claude to
update them.
