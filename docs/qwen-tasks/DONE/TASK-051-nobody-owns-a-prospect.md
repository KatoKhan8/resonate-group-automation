# TASK-051 - `sender_id` is null on all 285 sender rows

## THE FINDING

Every sender row in the estate carries `sender_id: null`. No prospect has a
human owner, so per-human attribution is impossible: a reply cannot be routed
to the person whose inbox it answers, per-sender volume cannot be enforced
against a real seat, and a sending identity cannot be tied to the human
accountable for it.

It was recorded as P1 at two consecutive context resets and has been queued
as TASK-036 without being worked.

## WHY IT IS NOT MERELY COSMETIC

`tests/test_push.py` pins that an EMPTY variable is DROPPED rather than sent
blank - so today the sender variables are simply absent from the EmailBison
payload, and `tests/test_preproduction.py` asserts exactly that absence with
a comment saying "the sender variables are absent because no seat carries a
`sender_id` yet".

That is two tests encoding a defect as expected behaviour. When the field is
populated they will both change meaning, and that is the point: find them,
read them, and decide deliberately what each should assert afterwards.

## GOAL

A sender row carries the identity of the human who owns it, that identity
reaches the provider payload, and a reply can be attributed back to them.

## WHERE TO LOOK, AND IN WHAT ORDER

1. `src/senderinventory.py`, `src/senderidentity.py`, `src/senders.py`,
   `src/senderteam.py`. Four modules with overlapping names - establish which
   one OWNS the sender record before writing anything. `CLAUDE.md`: "Prefer
   canonical state to a second representation of it."
2. Where the 285 rows come from, and whether the provider supplies anything
   that identifies a human. EmailBison's `sender-emails` payload carries
   `name` and `email`; read `src/providers/bison.py` around `sender_emails`
   first, including the long comment about `workspace_id` being accepted and
   discarded, because it tells you what that endpoint can and cannot be
   trusted to scope.
3. How a sender is bound to a campaign, and whether the binding already
   carries a person.

## THE HARD PART, STATED HONESTLY

There may be no provider field that names a human. If so, the answer is not
to invent one: it is to say clearly what the provider supplies, what would
have to be operator-entered, and where that entry would live. A design note
with the chain traced is a COMPLETE result for this task. Do not fabricate
an identity to make a field non-null - a guessed owner is worse than a null
one, because a null is visibly missing and a guess is not.

## READ-ONLY AT THE PROVIDER

You may read EmailBison sender rows. You may not write anything anywhere, to
any provider. Do not touch `work/queue.jsonl` or `work/campaigns.jsonl`.

If you cannot read the provider, say so and work from the code and the
stored rows. Do not stop.

## RESULT BLOCK

End this file with STATUS, COMMIT SHA, TESTS, FILES CHANGED, FINDINGS,
RISKS, RECOMMENDED CLAUDE ACTION.
