# The email CONTROL, and where it was already sitting

TASK-148 reported that Productive has no validated email CONTROL. That is true
of `config/clients/productive.yaml`, whose `email_sequence` carries
`{SUBJECT_1}` / `{BODY_1}` placeholders and no words at all. It is not true of
the repository.

## The decision

**CONTROL is `cadence.TEMPLATES`: `persona_pain`, `comparable_proof` and
`breakup`.**

These are the pre-generation email templates - literally what this system
would have sent before the generator existed, which is the operator's own
definition of the control arm: *the safest existing baseline we would have
sent without the new generation system.*

## Why these, and not something newer

**They are already claim-audited, and the audit is recorded in the source.**
Two of the three carry comments describing a defect that was found and fixed
in them:

- `breakup` opened "I have written a few times ... and not heard back". That
  is a claim about US, so `claims.py` never saw it - `GENERIC_SUBJECTS` drops
  any sentence opening "I ", because claims about the PROSPECT are its job.
  On a record with no confirmed touch, a first-ever message asserted a history
  of messages. The current wording claims nothing about what we have sent.
- `comparable_proof` and `comparable_proof_short` were missed in that same
  pass and corrected afterwards, for the same reason.

That history is the qualification. A challenger has no equivalent, and
promoting one to CONTROL because it is the only arm present is exactly what
the operator ruled out.

**They carry real variables** - `{first_name}`, `{company}`, `{angle_word}`,
`{angle_phrase}` - so they personalise without asserting anything the record
does not support.

**They are first-touch safe.** None claims a prior message, which matters
because `due(day=21)` returns day3, day5, day10 and day21 in one batch: day10
can be somebody's first email.

## The gap, stated rather than papered over

`cadence.STEPS` marks day1 `generated: True`. **There is no template opener.**
The CONTROL sequence has a middle, a proof and a close, and no first line.

That is a real hole and it is not filled by inventing one. The options, in
preference order:

1. `persona_pain` becomes the opener. Its body is question-led and asserts
   nothing about prior contact, so it reads correctly as a first touch. This
   is reuse of audited copy, not invention.
2. The operator writes one, as they did for the LinkedIn fallbacks - which is
   how the LinkedIn CONTROL came to exist, and why it beat three generated
   challengers across three human reads.

Option 1 is the default and needs no new words. Option 2 is better if the
operator wants an opener written for the job.

## What this does not settle

Threading. `EMAILBISON-COPY-REQUIREMENTS.md` requires a sequence to be ONE
CONVERSATION with same-thread follow-ups via the provider's `thread_reply`,
and these three templates each carry their own subject. Assembling them into a
threaded sequence - which subject opens, which steps reply in-thread, and what
the subject field must contain for a reply - is TASK-159.
