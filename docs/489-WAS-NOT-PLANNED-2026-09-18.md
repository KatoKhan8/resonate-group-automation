# 489 did not send today, and the window I chose is why

Read 2026-09-18T15:51Z, nearly three hours into 489's open window.

**The falsifier I wrote this morning fired.** It said rows should appear
shortly after 13:00Z because canary 451's appeared 19 minutes into its own
window. They did not.

    489  status active   leads 5   emails_sent 0   scheduled_emails 0
         updated_at 2026-09-18T05:35:58Z  = the moment of activation,
                                            UNMOVED for ten hours

## What is NOT wrong, checked rather than assumed

- **Sender 3437 is working and has room.** `emails_sent_count` moved
  1,784 -> 1,793 today: nine sent, against a limit of 15. The mailbox is
  connected, healthy and actively sending.
- **489's configuration is correct.** Sender [3437] attached, schedule
  09:00-17:00 America/New_York, three steps with `thread_reply
  [false, true, true]`, all five leads `in_sequence`.
- **Nothing structural separates it from a campaign the provider IS working.**
  Diffed field by field against client campaign 327: the only differences are
  scale and caps (5/day against 1000/day), `plain_text`, and
  `include_auto_replies_in_stats`. `status`, `type`,
  `sequence_prioritization`, `open_tracking`, `can_unsubscribe` and
  `daily_max_sends_per_receiving_domain` are identical.

## The reading that fits every observation

    campaign  window closes UTC   updated_at            sending today?
    327       21:00               2026-09-18T15:51Z     YES, 46,013 sent
    352       03:00               2026-09-18T15:26Z     YES
    328       15:00               2026-09-18T14:59Z     YES
    487       15:00               2026-09-17T15:02Z     no - queued for 23rd
    489       21:00               2026-09-18T05:35Z     no

My first hypothesis this morning was that the scheduler plans **when a window
OPENS**, on the strength of 451's 19-minute precedent. That is refuted: 489's
window opened at 13:00Z and nothing happened.

The reading that fits everything above is that `updated_at` moves when the
provider **SENDS** from a campaign, and that planning happens at or just after
**window CLOSE**:

- 327 and 352 move theirs mid-window because they are sending right now.
- 487 has not moved today at all, because it has nothing to send today - its
  ten openers are queued for the 23rd. It WAS planned at 15:02:48Z on the
  17th, **two minutes after its 15:00Z window close**.
- 489 has not moved because it has sent nothing and its window has not closed.

**489's window closes at 21:00Z.** So the expectation is that it is planned
around then, and that its openers land on the next sending day - **Monday
2026-09-21** - because 21:00Z on a Friday is after Friday's window.

## Classification, because this is inference and not proof

    campaign config, sender state, schedule        DOCUMENTED (provider read)
    489 unplanned after 10h and 3h of open window  OBSERVED
    487 untouched through a full window today      OBSERVED
    3437 sent 9 today, has room                    OBSERVED
    client campaigns worked continuously           OBSERVED
    "planning happens at window close"             INFERRED, one clean
                                                   data point (487 at +2 min)
    why 451's row appeared mid-window on the 13th  UNKNOWN, and it contradicts
                                                   the inference above

I am not asserting the mechanism. The 487 match is two minutes wide and that
is suggestive, not proof, and the 451 account in the previous handoff
disagrees with it.

## The cost of a decision I made, stated plainly

I chose `09:00-17:00 America/New_York` for 489 because its five recipients are
American and the client default of Europe/Zagreb would have written to them at
03:00 local. That reasoning stands and I would make it again.

**It has a cost I did not foresee: that window closes at 21:00Z, which is
after the point at which a same-day send would have to be planned.** A
Europe/Zagreb window closes at 15:00Z. So the recipient-appropriate choice and
the send-today goal were in tension, and I did not notice until the window had
been open for three hours.

## What must NOT be done about it on this inference

**Do not mutate 489's schedule to chase the hypothesis.** Moving the window
close earlier - say to 16:30Z, which is a perfectly reasonable 12:30 Eastern -
would be acting on one data point against a live campaign holding five real
approved people, to save three days. If the inference is wrong it changes
nothing; if it is right it is still a change to a live campaign made on a
guess.

The cheap test costs nothing and answers it: **watch 21:00Z.** If rows appear
within a few minutes of it, the mechanism is established and the window can be
chosen deliberately next time. If 21:00Z passes with `queue 0/0` and
`updated_at` still at 05:35Z, the inference is dead too and the question is
open again.

## What this means today

    REAL_EMAIL_SENDS  0
    487_NEXT_SEND     2026-09-23
    489_NEXT_SEND     UNKNOWN - expected 2026-09-21 if the inference holds

**No email will be sent today.** That is the honest answer, and the previous
framing in the handoff - "489 is the one that could send first" - was true of
the campaign and too optimistic about the date.
