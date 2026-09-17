# The LinkedIn campaign is not stalled. It is 30 hours into a 30-hour ramp.

2026-09-17, read off the provider.

`docs/PRODUCTION-HANDOFF-2026-09-17.md` reports campaign 605732 as
`IN_PROGRESS since 2026-09-16T20:12:25Z` with `0 messages, 0 connection
requests, 0 replies`, and files that under the same heading as EmailBison's
zero: two live campaigns, neither has sent. The email zero is an open question.
**The LinkedIn zero is not. The sequence's own graph forbids a send this
early, and nobody had walked it.**

## The graph, read from `/campaign/GetCampaignSequence`

A lead who is NOT already a connection - which all three are,
`leadConnectionStatus: None` - takes this branch:

    CHECK_IS_CONNECTION   delay 0 HOUR      entry
      -> VIEW_PROFILE     delay 3 HOUR
        -> FOLLOW         delay 3 HOUR
          -> CONNECTION_REQUEST  delay 1 DAY   <- the first contact-initiating
                                                  action in the whole branch
            -> MESSAGE {message_2}  delay 3 HOUR   (only once accepted)

**Thirty hours of declared delay stand between entering the sequence and the
connection request**, before any working-hours clipping. The already-connected
branch reaches `MESSAGE {connected_1}` in 3 hours, but no lead in this cohort
is on it.

So `HEYREACH_SENT = 0` at T+15h is the graph doing exactly what it says.
Reading it as a stall - or as evidence about seat capacity, or as something
needing a fix - would have been chasing a phantom, and the fix would have been
to a CONTROL sequence that is byte-identical to the audited 599020.

## The provider HAS acted, and our own watcher cannot see it

`lastActionTime` per lead:

    4684b25b0372   2026-09-17T09:04:00Z
    4258f756357d   2026-09-17T09:05:39Z
    c01f0c88111c   2026-09-17T09:06:42Z

All three moved off `creationTime` (2026-09-16T20:12:24Z) this morning within
three minutes of each other. Something processed each lead at ~09:04Z. The
lifecycle fields did not move - `Pending` became `InSequence`, connection and
message are both still `None` - because the actions at this depth of the graph
are `CHECK_IS_CONNECTION` and `VIEW_PROFILE`, and **this provider exposes no
per-lead node position**. The three lifecycle fields describe connection and
message only.

Two consequences, and the second is a gap rather than a finding:

- `heyreach_first_send_watch.py` is correct to report 0. It measures sends.
- **Nothing in this system can say which node a lead currently sits on.**
  `lastActionTime` moving is the only signal that the campaign is being worked
  at all, and no tool reads it as such. That is what made a working campaign
  look identical to a dead one.

## The prediction, and how to falsify it

Entry processing at ~09:04Z on 2026-09-17, plus 3h + 3h + 1 DAY, clipped into
whatever sending window the campaign holds:

**The first CONNECTION_REQUEST on 605732 should appear on 2026-09-18, and
`leadConnectionStatus` should read `ConnectionSent` for at least one of the
three leads by the close of that day's window.**

If 2026-09-19 opens with all three still at `None` AND `lastActionTime`
unmoved since 2026-09-17, this explanation is wrong and the campaign is stuck
somewhere the graph does not explain. Investigate then; do not extend the
prediction a day at a time.

## The window nobody chose, and nobody can read

`create_linkedin_cohort_b_campaign.py` calls
`heyreach.create_campaign(name, list_id, account_ids)` - **no `schedule`
argument**. The vendor therefore applied its own default, and
`heyreach.set_schedule` documents at length why that cannot be corrected or
even inspected: `UpdateSchedule` writes a window, and no route on the API
reads one back, so the only record of when this campaign may contact people
would be our own memory of what we asked for.

The observed 09:04Z start is consistent with a window opening at 09:00 in some
timezone, and that is an OBSERVATION, not a configuration anybody can quote.

This is a real gap and it is worth exactly what it costs to fix, which is
nothing: `create_campaign` takes `schedule` in the same call that produces the
id. **The next LinkedIn campaign should pass one explicitly**, so the window
is a decision recorded at a moment somebody owns rather than a vendor default
discovered afterwards from timestamps. 605732 itself is left alone - it is
live, it is working, and changing a live campaign's window through the one
verb that cannot be read back is the opposite of what this repository does.

## What this does not say

It does not say the LinkedIn channel is healthy at scale. Seat 174892 still
sits in 46 campaigns, 13 of them IN_PROGRESS, and its share of a 40/day
connection-request ceiling is still roughly 3. That finding stands untouched.

It says only this: three leads, one seat, a 30-hour ramp, fifteen hours
elapsed. There is nothing to fix here yet, and the next honest checkpoint is
tomorrow.
