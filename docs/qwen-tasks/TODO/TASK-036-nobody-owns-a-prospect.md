# TASK-036 - No prospect has a human owner

Carried as OPEN P1 since the context-reset checkpoint and untouched.

## GOAL

Make `sender_id` real, so a reply can be routed to the person whose name is on
the email.

## WHY IT MATTERS

`sender_id` is NULL on all 285 sender rows. `src/assignment.py` exists to
decide which human owns a prospect and cannot, because the field it keys on is
empty everywhere.

The consequence is not cosmetic. When a prospect replies, nobody is
identifiable as the person they were talking to; `senderidentity` and
`senderteam` have nothing to resolve; and the LinkedIn side has the same
question in a sharper form, where the seat IS who the prospect sees.

## CURRENT FACTS

- 285 sender rows in `work/senders.jsonl`, `sender_id` null on every one.
- `provider_account_id` IS populated - 225 Productive EmailBison inboxes carry
  one, are active, and 222 report health `ok`. So the PROVIDER identity exists
  and the HUMAN identity does not.
- The checkpoint is explicit that this does not block staging: "What
  `sender_id` blocks is which HUMAN owns a prospect, not which inbox sends."

## SCOPE

1. Establish what `sender_id` is meant to BE - a person, a mailbox, or a team -
   by reading `assignment.py`, `senderidentity.py` and `senderteam.py`. They
   may disagree; if they do, that disagreement is the finding.
2. Decide where the value comes from. It may be derivable from what the
   provider already gives (the inbox's own owner), in which case this is a
   backfill and not a new field.
3. If it CANNOT be derived, say so plainly and stop there. Inventing an owner
   is worse than an empty field: a wrong owner routes a real reply to the
   wrong person.
4. Do not write `work/senders.jsonl`. Produce the backfill as a script that
   reports what it WOULD write, and let Claude run it.

## PRODUCTION BOUNDARY

ZERO network. ZERO credentials - `config/.env` does not exist in this
worktree and a task that tries to obtain one has misunderstood its job. No
provider call. No write to `work/**`. Nothing is staged, activated or sent.

## HANDOFF FORMAT

Return ONLY this, concisely:

    STATUS / COMMIT SHA / FILES CHANGED / TESTS RUN / TEST RESULTS /
    BUGS FOUND / BUGS FIXED / RISKS / OPEN QUESTIONS /
    RECOMMENDED CLAUDE ACTION

Plus, required of every task since 2026-09-14: the output of
`grep -rn "<each new name you added>" src/` proving it is CONSUMED, and
confirmation that deleting the CALL to your new code makes a test fail.

## TESTS REQUIRED

- a sender with a derivable owner resolves to it;
- a sender with none resolves to UNKNOWN and never to a guess;
- `assignment` routes a reply to the owner when there is one and refuses when
  there is not.

## DONE CONDITION

Either every sender resolves to an owner with evidence, or a written statement
of which ones cannot and why, with no guessed values anywhere.
