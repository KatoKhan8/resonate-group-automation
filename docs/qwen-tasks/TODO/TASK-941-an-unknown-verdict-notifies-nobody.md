PRIORITY: P0
SIZE: M
DEPENDS:

# TASK-941 — An `unknown` verdict pauses the cadence and notifies nobody

Found 2026-10-02 by reading the execution path while fixing TASK-939, and measured there rather
than inferred from the classifier's output.

## The defect

In `replies.apply`, only `is_positive(verdict)` calls `_announce`. An `unknown` verdict is written
to an event, pauses the cadence, and **nobody is told**. `notify.UNMATCHED_REPLY`
(`unmatched_reply_needs_review`, GLOBAL / ACTION_REQUIRED) is raised ONLY by `inbound.py` when
ATTRIBUTION fails — never when CLASSIFICATION fails. Those are different failures and only one of
them has a queue.

So the system's honest answer — "a human wrote something and I do not know what it means" — is the
one answer that reaches no human.

## The scale, measured on the full 899-reply corpus

| rules | `unknown` |
|---|---|
| master `rules-4+63ac5f605770` | 324 |
| TASK-939 branch `rules-4+ca10b3cccdcb` | 278 |
| pending `rules-4+400872bcd6e6` | 292 |
| the two branches merged `rules-4+c7e9695c4436` | 274 |

Even after both classifier branches land, **274 replies sit in `unknown` and not one of them
raises a notification.** Thirteen of those are clear removal or refusal signals already named by
id for a separate task: 1543719, 1501282, 1609175, 1608522, 1607793, 1602676, 1602498, 1512247,
1577849, 1570426, 1609395, 1520259, 1609184.

## Why this is P0 rather than a backlog item

The compliance exposure is not that the classifier is imperfect — it will always be imperfect. It
is that imperfection has **no outlet**. Two rows measured tonight show what that costs when it goes
unseen:
- a reply whose entire human content is the word `remove` read as `referral` on master, on evidence
  taken from its own confidentiality footer, and the person was on no suppression list;
- a reply whose entire human content is `Stop` read as `positive 0.75` on master, on evidence that
  was **a sentence we wrote**, quoted back in the thread.

Both are now classified correctly, but both were invisible for the same reason the remaining 274
are invisible: nothing escalates a verdict the system is not confident about.

## Acceptance

1. An `unknown` verdict on a reply from a real person raises a named notification to a human queue,
   with the reply id, the campaign, the contact and the stripped human text.
2. The notification is distinguishable from `unmatched_reply_needs_review`. Attribution failure and
   classification failure are different questions and must not share one queue, or the one that
   fires often will train people to ignore the one that matters.
3. An automated reply (`ooo`, autoresponder, `is_automated()` true) does NOT raise it. 128 `ooo`
   rows exist in the corpus; a queue that fires on those is a queue nobody reads.
4. The cadence pause behaviour does not change. This task adds an outlet, it does not change a
   send decision.
5. Prove it fires: a test with an `unknown` verdict asserts the notification was raised, and a
   mutation removing the call makes the test go red on EFFECT (the notification record), not on
   message text.
6. Prove it does not over-fire: measured against the corpus, state how many notifications the rule
   would have raised over the 899 rows. If the answer is 274 all at once, say so and propose the
   batching or triage the operator would need — do not quietly rate-limit it.
7. READ-ONLY toward providers. No write to any suppression or DNC file.

## Warning

This touches the send path's notification layer. The repo rule is two notification levels with no
fallback between them (`docs/SLACK-NOTIFICATIONS.md`); read it before adding a type. Adding a
notification type that is raised 274 times on first run would be worse than the silence it
replaces, so point 6 is not optional.
