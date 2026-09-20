# 487 was paused by an audit agent's live provider call

**P0. Campaign 487 will not send on 2026-09-22 in its present state.**

---

## CORRECTED 2026-09-20T15:10Z. THE CAUSE IS KNOWN AND MY CENTRAL CLAIM WAS WRONG.

This document originally argued that 487's LEADS went `sending_paused` first
and the campaign followed - "the campaign row was wrong and the lead rows
were right". **That does not survive the cause being known, and it was never
established.**

An audit agent (the "Buggie" crew, verifying its own finding #1) passed a
bare dict to `orchestrator.pause`. `campaigns.get()` returned None, the
repeat guard did not fire, `providerwrites.perform` reached the REAL
transport, `providers.key()` loaded `config/.env`, and a live
`PATCH /api/campaigns/487/pause` hit send.resonategroup.co at
**2026-09-20T12:44:45Z**. Its own report records this.

So the simple explanation holds: **the pause set the campaign AND its ten
leads together.** No divergence between campaign status and lead status was
demonstrated.

My error was one of ordering, and it is worth naming precisely. The campaign
was read `active` at 12:14:28Z. The membership was read separately, some
minutes later, and I did not stamp that read. It sat close enough to
12:44:45Z that I cannot place it on either side - so "the leads were paused
while the campaign was still active" was an inference from two observations
whose order I never established. The watcher's own log is against me: it read
`status=active` at 12:23:34Z and saw the transition at 12:47:36Z, with
nothing in between.

**What survives, and why the instrumentation still earns its place:**
`resume_campaign` confirms the CAMPAIGN's status and nothing else, so a
resume that leaves ten leads `sending_paused` would report as success. That
is a real gap whether or not the two have ever diverged in this estate, and
it is the acceptance test the recovery now runs on. The `MEMBERSHIP` event
and `_membership_states` stay for that reason - not because a divergence was
proved.

The rest of this document is the original, with measured facts intact. Where
it argues the leads-first sequence, read the correction above.

---

Found 2026-09-20 between 12:14Z and 12:49Z, by asking a question nothing had
asked: what does the PROVIDER say about each LEAD, as distinct from what it
says about the campaign.

## The timeline, every line measured

    2026-09-17T06:26:50Z  487 created
    2026-09-18             10 leads read `in_sequence`
                           - recorded in THE-LOADED-GUN-IS-SMALLER-THAN-IT
                             -LOOKED-2026-09-18, line 23: "campaign 487
                             10 leads in_sequence 10"
    2026-09-19T16:04:58Z  campaign touched; the ten queued rows moved from
                           2026-09-23 to 2026-09-22
    2026-09-20T12:14:28Z  campaign reads `active`
    2026-09-20T12:23:34Z  watcher reads `active` (its own log)
    2026-09-20T12:44:45Z  AN AUDIT AGENT'S LIVE `PATCH /campaigns/487/pause`
                           REACHES THE PROVIDER. Campaign and all ten leads
                           read `paused` / `sending_paused` from here.
                           (My own membership read is unstamped and sits near
                           this line on an order I never established - see
                           the correction at the top.)
    2026-09-20T12:47:36Z  captured durably by the watcher:
                           STATUS 487 active -> paused
                           TOUCHED 487 updated_at ... (sent=0, queue=10)

**487 was live and stopped being live.** This is a regression, not a campaign
that never started.

## What it is not

    this session's writes ZERO. `work/action-ledger.jsonl` holds nothing
                          after 2026-09-19, and every provider call in THIS
                          session was a GET. The write came from a separate
                          audit process, not from here - which is exactly why
                          "nothing of ours wrote" was true and useless: the
                          transport has no guard, so ANY process that imports
                          `src` and reaches `providers.request` can mutate a
                          real campaign with the real key.
    the sender            2736 reads `Connected`, daily_limit 15, unchanged
                          across all 704 samples of
                          `bison-mailbox-utilisation.jsonl` including the
                          ones either side of 12:44:45Z. The mailbox is fine.
    a workspace event     487 IS THE ONLY CAMPAIGN IN THE ESTATE THAT
                          CHANGED. All 25 campaigns read: 352 updated
                          12:50:01Z and 328 at 10:55:04Z, both `active` and
                          being worked normally. Nothing else moved.
    the calendar          it is Sunday and 487's window is Mon-Fri, but 489
                          has a Mon-Fri window too and reads `active` with
                          all five leads `in_sequence`. A closed window does
                          not produce this.
    the cohort            still 10 leads, still 10 queued rows, still dated
                          2026-09-22T07:39Z. The queue survived the pause.
    the copy              all ten queued rows carry EXACTLY the approved
                          text, verified today by
                          `scripts/queued_copy_readback.py`. 15 of 15 across
                          both campaigns.

## The lead status was the leading indicator and nothing was reading it

`resume_campaign` confirms the CAMPAIGN's status and nothing else - its own
docstring is careful about `queued` versus `failed` and says nothing about
membership, because nothing had ever looked. So for at least some hours, and
possibly since the 19th, 487 read `active` at the campaign level while every
one of its leads was individually paused. **The campaign row was wrong and
the lead rows were right.**

The control is unambiguous, one page of leads each, read at 12:47Z:

    campaign 327   15 of 15 `in_sequence`     client, sending
    campaign 328   15 of 15 `in_sequence`     client, sending
    campaign 352   15 of 15 `in_sequence`     client, sending, 2 already sent
    campaign 489    5 of 5  `in_sequence`     ours, healthy
    campaign 487   10 of 10 `sending_paused`  ours

`scripts/bison_watch_loop.py` now carries `_membership_states` and emits
`MEMBERSHIP` when the distribution moves, so this is instrumented rather than
noticed. Both bison watchers were restarted onto it.

## Why nobody saw the earlier half of this

The watchers were alive and writing into a closed pipe - see
`docs/` for the commit "Five monitors were alive and writing every event into
a closed pipe", found earlier the same morning. The schedule move at
2026-09-19T16:04:58Z WOULD have emitted `SCHEDULE-MOVED`, and it went
nowhere. The status change at 12:44:45Z was captured because the durable sink
had been in place for twenty-five minutes.

That is the whole argument for the sink, made by the estate rather than by
an assertion.

## What must not be done

**Do not resume 487 autonomously.** Three reasons, in order:

1. **The cause is unattributed.** The provider may have paused it, or a
   PERSON may have paused it in the EmailBison UI - this is a shared
   workspace whose other campaigns are the operator's own. The API cannot
   tell those apart. Resuming a campaign a human deliberately paused would be
   overriding a decision, not recovering from a fault.
2. `/campaigns/{id}/resume` is, in `WRITE_ROUTES`' own words, "THE ONE ROUTE
   HERE THAT REACHES A PERSON". It sends to every lead the campaign holds.
3. `resume_campaign`'s docstring records a measured failure mode: "a campaign
   whose next sending window is days away fails this way within seconds",
   moving to `failed`. 487's window opens Monday 07:00Z. A resume attempted
   now could leave it strictly worse than paused.

**Do not run `scripts/make_481_inert.py --live` this week either** - but for
a reason that has now IMPROVED rather than worsened. See below.

## One question this incident answered for free

`make_481_inert.py` was held because it was unmeasured whether a stop in
campaign 481 would touch the same lead's membership in LIVE 487 - "if the
provider models it per LEAD rather than per (lead, campaign) it would kill
the live cohort".

**It models it per (lead, campaign), and the provider says so in its own
shape.** Lead 203708 carries three independent entries:

    lead_campaign_data = [
      {"campaign_id": 481, "status": "sending_paused"},
      {"campaign_id": 485, "status": "stopped"},
      {"campaign_id": 487, "status": "sending_paused"}
    ]

One person, three campaigns, three different statuses, `stopped` in one of
them while the others are not. `_status_in` has filtered this array by
campaign id all along and its docstring already warned that reading element
zero returns another campaign's answer. The data model was never in doubt
once anybody printed it.

That removes the stated risk from `make_481_inert.py`. It stays held anyway
while 487 is in an unexplained state, because adding a second unattributed
change to a campaign nobody can yet explain is how an incident becomes two.

## What an operator has to decide

**Was 487 paused by a person?** That one answer routes everything:

    YES, deliberately    -> 487 stays paused, the cohort is stood down, and
                            the ten approved contacts return to inventory.
    YES, by accident     -> resume it, with a human on the command, and watch
                            the membership line flip back to `in_sequence`.
    NO / unknown         -> a provider-side fault. Resume is still the
                            remedy, but it is attempted INSIDE the Monday
                            window rather than on a Sunday, and the
                            `MEMBERSHIP` event is the acceptance test:
                            campaign `active` is NOT sufficient evidence and
                            never was.

489 is untouched and needs no decision. Its five are scheduled 2026-09-24
and all five leads read `in_sequence`.

## Classification

    487 read `in_sequence` on the 18th               MEASURED (doc, 09-18)
    487 reads `sending_paused` on all ten now        MEASURED
    487 campaign status active -> paused 12:44:45Z   MEASURED
    no write of ours touched it                      MEASURED
    sender 2736 healthy and unchanged throughout     MEASURED
    487 is the only campaign in the estate to move   MEASURED
    the provider models status per (lead, campaign)  MEASURED, from its
                                                     own payload shape
    WHY it was paused                                UNKNOWN
    whether a person did it                          UNKNOWN, and the API
                                                     cannot distinguish it
    whether resume restores `in_sequence`            UNKNOWN - and the
                                                     MEMBERSHIP event is now
                                                     the test for it
