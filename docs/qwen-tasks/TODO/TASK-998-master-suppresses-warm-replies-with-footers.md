# TASK-998 — master turns a warm reply with an unsubscribe footer into a suppression

STAGE: QUEUED
PRIORITY: P0
FIXED BY: task-removal-union-2026-10-12 (under review)

## This is a LIVE defect in master, not a hypothetical

Verified 2026-10-12 in a clean detached worktree at master `2bf7b8a5`,
`replies.RULE_HASH = rules-4+ca10b3cccdcb`:

| input | master's verdict |
|---|---|
| `Sounds great, Thursday works. You can unsubscribe from our mailing list at any time.` | **unsubscribe 0.95** |
| `I am out of office until Monday. To unsubscribe from this list click here.` | **unsubscribe 0.95** |
| `Happy to proceed - you may unsubscribe from this list at any time.` | **unsubscribe 0.95** |
| `Great, no more emails required until we sign.` | **unsubscribe 0.95** |

Cause: master's bare `\bunsubscribe\b` in `UNSUBSCRIBE_PATTERNS` outranks both
POSITIVE and OUT_OF_OFFICE in `RULES`. A footer describing a MECHANISM reads
identically to a person asking to leave. Same for
`\bno more (?:emails|messages|mail)\b` against "no more emails required until
we sign".

**The expensive direction.** A real buying signal classified as a removal
request at 0.95 confidence is a lead suppressed and nobody downstream ever asks
why that person went quiet.

## How it was found, which is the part worth keeping

It was NOT found by reading the code. Adversarial review (GLM) refused a branch
for introducing this class of regression; fixing those regressions required
classifying the constructed cases against master, and four of the nine turned
out to be master's own, pre-existing.

So the defect survived every existing test, the 559-reply corpus, and a
measurement that reported "12 positives before, 12 positives after". It was
invisible to all of them for the same reason: **the real corpus contains no warm
reply carrying an unsubscribe footer.** A corpus proves no regression on traffic
already seen; it says nothing about traffic not yet seen.

## Harm: real defect, undemonstrated harm. State it that way.

Searched all 559 real inbound replies for a footer-mechanism phrase
(`you can/may unsubscribe from`, `to unsubscribe from`,
`unsubscribe from our/this/the ... list`, `click here to unsubscribe`,
`no more emails required`): **0 hits**, with a positive control proving the
matcher fires.

So no positive reply is known to have been suppressed by this. **History cannot
be audited**, because `work/learning-replies.jsonl` holds 179,715 rows and no
reply text (TASK-991). The honest summary: the bug is live, the harm is
unproven, and it is unprovable backwards with current local state.

## Acceptance

- A footer or signature mechanism must not produce a removal verdict, and must
  not SILENCE a genuine request elsewhere in the same reply - mask the footer,
  do not reject the message.
- A test corpus of inputs the real traffic does NOT contain, maintained
  deliberately as a second corpus beside the real one.
- The constructed corpus needs both halves: inputs that must not be removals AND
  inputs that must be. A guard that refuses everything passes the first half and
  fails the second, and only the second half proves the mask does not eat
  "I want to unsubscribe".
