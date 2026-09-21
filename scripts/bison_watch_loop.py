#!/usr/bin/env python3
"""Emit ONE line whenever campaign 487's provider truth changes. READ-ONLY.

    py -3 scripts/bison_watch_loop.py [--interval 300]

Built for a background monitor: one line per EVENT, nothing while the picture
is unchanged, everything flushed.

WHAT IT EMITS, deliberately wider than the good news, because silence has to
mean "unchanged" rather than "died an hour ago":

    SEND        emails_sent rose, or a scheduled-email row reads sent
    REPLY       a reply was recorded
    BOUNCE      a bounce was recorded
    UNSUB       an unsubscribe was recorded
    STATUS      the campaign left `active` (paused, stopped, archived)
    COHORT      the lead count moved - the audience changed under us
    QUEUED      the scheduled-email queue gained or lost rows WITHOUT a send
    TOUCHED     the provider moved the campaign's own `updated_at`
    SCHEDULE-MOVED  the EARLIEST scheduled_date changed - when the first
                prospect hears from us is not the same fact as whether a row
                exists, and 451's moved once overnight
    MEMBERSHIP  the per-lead status distribution changed. An ACTIVE campaign
                whose leads read `sending_paused` is not sending, and the
                campaign row does not say so - see `_membership_states`
    READ-ERROR  the provider could not be read, after it repeats

WHY `QUEUED` AND `TOUCHED` EXIST, added 2026-09-17, and they are the whole
falsifier for why this campaign has sent nothing.

`scheduled_emails` is a LOOKAHEAD queue, not a receipt. Campaign 451's row
appeared carrying `scheduled_date: 2026-09-13T13:19Z` - nineteen minutes after
its window opened - then moved overnight to 16:24Z on the 14th and fired there
twenty seconds late. So a row appears BEFORE anything is sent, and 487 has
none: the provider has not queued this campaign at all, which is a different
and much more specific fact than "it has not sent".

`updated_at` is the same question asked of the campaign row. Sibling campaigns
352 and 328 - ACTIVE, sharing 487's mailbox - move theirs every few minutes
while the provider works them. 487's has not moved since OUR last write at
2026-09-17T10:45:10Z, through 36 minutes of an open window.

Together they make the standing hypothesis testable tomorrow rather than
next week: if the provider assigns a day's leads at or near the window
opening, then at 07:00-07:30Z on 2026-09-18 - 09:00 Europe/Zagreb - 487
should emit TOUCHED and then QUEUED. **If the window opens and both stay
silent, the hypothesis is dead and must be discarded rather than extended a
day.**

TWO WITNESSES FOR A SEND, not one. `emails_sent` is the campaign counter;
`scheduled_emails` returns one ROW PER MESSAGE and a sent one says so. Campaign
451 proved the second is readable before a send is visible in aggregate, and
the counter alone has been wrong on this provider before - `max_emails_per_day`
was silently discarded on create and read back 1000.
"""
import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import watchsink                                       # noqa: E402
from src.providers import bison, load_env                       # noqa: E402

# THE DEFAULT IS 487 AND THE ARGUMENT EXISTS BECAUSE THERE ARE NOW TWO.
# Campaign 489 - the five-contact US cohort - went active 2026-09-18 and
# needs the same watch. One process per campaign rather than one process
# over a list, so a read error on either cannot silence the other.
PROVIDER_ID = 487
SENT_WORDS = {"sent", "delivered"}


def emit(line):
    """Stdout only. The DURABLE emitter is built per campaign in `main` -
    see `src/watchsink.py` for why printing alone was not a monitor.
    """
    print(line, flush=True)


def milestone(campaign_id, kind, **fields):
    """Raise a campaign_milestone, and never let it break the watcher.

    A WATCHER FIRING WAS NOT A NOTIFICATION until 2026-09-21. This loop wrote
    to its own log and heartbeat and called `notify` for nothing, so the first
    provider-confirmed send on 489 - the milestone this whole project had been
    working toward - reached no channel at all. `notify.notify()` plans the
    row and `scripts/notify_deliver_loop.py` delivers it.

    IDEMPOTENT BY CONSTRUCTION. `notify.notification_id` builds the id from
    the identifiers below, so the same occurrence lands on the same row and a
    second write does nothing. That matters here because this loop re-polls
    every 180s and a restart re-reads from a fresh baseline: `first_send` on
    campaign 489 is one occurrence however many times it is noticed.

    WRAPPED, because a notification is not worth an outage. If Slack, the
    store or the routing table fails, the watcher must keep watching - the log
    and the heartbeat are the record of last resort and they do not depend on
    this succeeding.
    """
    try:
        from src import notify as _notify
        _notify.notify("campaign_milestone", "productive",
                       fields=dict(fields, campaign=campaign_id,
                                   milestone=kind),
                       ids={"campaign_id": str(campaign_id),
                            "milestone": kind})
    except Exception as exc:                                    # noqa: BLE001
        emit(f"MILESTONE-FAILED {campaign_id} {kind}: "
             f"{type(exc).__name__}: {str(exc)[:100]}")


def snapshot(provider_id=None):
    provider_id = PROVIDER_ID if provider_id is None else provider_id
    row = bison.campaign(provider_id) or {}
    queue = bison.scheduled_emails(provider_id) or []
    sent_rows = 0
    for entry in queue:
        state = str(entry.get("status") or entry.get("state") or "").lower()
        if state in SENT_WORDS or entry.get("sent_at"):
            sent_rows += 1
    # WHAT THE PROVIDER SAYS IT WILL SEND, as opposed to what we infer.
    # The provider documents an endpoint that answers directly; this is the
    # near-term confirmation, not a planner. The window only reaches two days
    # out, so it cannot answer questions about Thursday.
    #
    # `SendingScheduleEmpty` is the provider's ordinary "nothing here" answer,
    # not a transport failure. A monitor that treats it as a failure will
    # alarm every weekend; one that treats it as zero will report a healthy
    # campaign as silent. It is recorded as None (empty) distinct from 0
    # (provider says zero) and distinct from a read error (unknown).
    provider_plan = _provider_sending_plan(provider_id)
    return {
        "status": str(row.get("status") or "").lower(),
        "emails_sent": int(row.get("emails_sent") or 0),
        "replied": int(row.get("replied") or 0),
        "bounced": int(row.get("bounced") or 0),
        "unsubscribed": int(row.get("unsubscribed") or 0),
        "leads": int(row.get("total_leads") or 0),
        "queue_rows": len(queue),
        "sent_rows": sent_rows,
        # Carried verbatim and compared for movement, never parsed: a format
        # this system has not seen still reports a touch rather than raising.
        "updated_at": row.get("updated_at"),
        # A SCHEDULED DATE ON THIS PROVIDER IS AN INTENTION, NOT A COMMITMENT.
        # Canary 451's single row moved once overnight - 2026-09-13T13:19Z to
        # 2026-09-14T16:24Z, with nothing staged in between - and then fired
        # twenty seconds late. So the row appearing is one event and the date
        # it carries is another, and only the first was being watched.
        # `min` because the question this answers is "when does the first
        # prospect hear from us", and it is the number an operator plans on.
        "first_scheduled": min(
            [str(e.get("scheduled_date")) for e in queue
             if e.get("scheduled_date")] or ["none"]),
        # WHAT THE CAMPAIGN SAYS IS NOT WHAT THE LEADS SAY, measured
        # 2026-09-20. Campaign 487 reads `active` with ten rows queued for
        # the 22nd, and all ten of its leads read `sending_paused` in their
        # own `lead_campaign_data`. Campaign 489 - same factory, same day,
        # same shape - reads `in_sequence` on all five, and so do single
        # pages of the client's 327, 328 and 352, which are demonstrably
        # sending. `resume_campaign` confirms the CAMPAIGN's status and
        # nothing else, so this state is invisible to the readback that was
        # supposed to catch it.
        #
        # A dict rather than a count, because the question is which statuses
        # are present and in what proportion, and a single number cannot
        # answer it. None when the campaign is too large for a bounded walk:
        # UNKNOWN is a legitimate answer here and zero is not.
        "membership": _membership_states(provider_id),
        # WHAT THE PROVIDER SAYS IT WILL SEND. A dict keyed by day, with
        # values: int (count), None (empty - nothing scheduled), or "error"
        # (could not read). The disagreement line fires when this says empty
        # but `first_scheduled` says something is planned, or vice versa.
        "provider_plan": provider_plan,
    }


def _provider_sending_plan(provider_id):
    """The provider's near-term sending plan, as the provider states it.

    Returns a dict keyed by day (`today`, `tomorrow`, `day_after_tomorrow`).
    Values: int (count), None (empty - nothing scheduled), or "error" (could
    not read). A read error on one day does not poison the others.
    """
    out = {}
    for day in bison.VALID_DAYS:
        try:
            result = bison.sending_schedule(provider_id, day)
            out[day] = result.get("emails_being_sent", 0)
        except bison.SendingScheduleEmpty:
            out[day] = None
        except Exception:
            out[day] = "error"
    return out


def _membership_states(provider_id):
    """Per-lead status inside this campaign, counted. None if unreadable.

    `membership()` walks and refuses past `PAGE_CAP` rather than returning a
    page - correct, and it means a client-sized campaign has no cheap answer.
    That refusal is caught and reported as None: a watcher must not die on a
    campaign it cannot count, and must not report a partial count as a whole
    one either.
    """
    try:
        rows = bison.membership(provider_id) or {}
    except Exception:
        return None
    out = {}
    for status in rows.values():
        key = str(status)
        out[key] = out.get(key, 0) + 1
    return out


def _check_disagreement(state):
    """Whether the provider's plan disagrees with our inference.

    Returns a string describing the disagreement, or None if they agree.
    Two ways round:
    - We believe a send lands tomorrow (first_scheduled is not "none") and
      the provider reports nothing for tomorrow.
    - The provider reports something for tomorrow but we have no scheduled
      rows (first_scheduled is "none").

    The window only reaches two days out, so we check `tomorrow` and
    `day_after_tomorrow`. `today` is excluded because a send that already
    happened is not a disagreement.
    """
    first = state.get("first_scheduled", "none")
    plan = state.get("provider_plan") or {}
    we_think_sending = first != "none"
    # Check tomorrow and day_after_tomorrow. The provider's window only
    # reaches two days out, and today's sends are already in flight.
    for day in ("tomorrow", "day_after_tomorrow"):
        provider_count = plan.get(day)
        provider_thinks_sending = (isinstance(provider_count, int)
                                   and provider_count > 0)
        if we_think_sending and not provider_thinks_sending:
            return (f"we believe first send at {first} but provider reports "
                    f"{provider_count} for {day}")
        if provider_thinks_sending and not we_think_sending:
            return (f"provider reports {provider_count} for {day} but we "
                    f"have no scheduled rows")
    return None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--interval", type=float, default=300.0)
    parser.add_argument("--campaign", type=int, default=PROVIDER_ID,
                        help="the EmailBison campaign to watch")
    args = parser.parse_args(argv)
    watched = args.campaign

    load_env(os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "config", ".env"))

    # Durable from here down. `emit` still prints, so a person running this in
    # a terminal sees what they always saw; the difference is that the line
    # now also lands in `work/watch-events/bison-<id>.jsonl` and survives the
    # shell. See the module docstring of `src/watchsink.py`.
    emit = watchsink.emitter("bison", campaign=watched)

    previous = None
    errors = 0
    while True:
        try:
            current = snapshot(watched)
            errors = 0
        except Exception as exc:
            errors += 1
            if errors in (3, 12):
                emit(f"READ-ERROR {watched} unreadable {errors}x: "
                     f"{type(exc).__name__}")
            # Beat anyway, with the reason. Alive-and-blind is a different
            # incident from alive-and-nothing-changed and must not read as it.
            watchsink.beat("bison", campaign=watched,
                           note=f"READ-ERROR {errors}x {type(exc).__name__}")
            time.sleep(args.interval)
            continue

        # EVERY poll, including the ones that emit nothing. This is what makes
        # an empty event log readable as "unchanged" rather than "died".
        watchsink.beat("bison", campaign=watched, state=current)

        if previous is None:
            emit(f"WATCHING {watched} status={current['status']} "
                 f"leads={current['leads']} sent={current['emails_sent']}")
            previous = current
            time.sleep(args.interval)
            continue

        if current["status"] != previous["status"]:
            emit(f"STATUS {watched} {previous['status']} -> {current['status']}")
            # The provider's words for a finished sequence. Checked as a set
            # rather than one spelling, because which one it uses is not
            # documented and a missed milestone is silent.
            if str(current["status"]).lower() in ("finished", "completed",
                                                  "complete", "done"):
                milestone(PROVIDER_ID, "sequence_finished",
                          status=current["status"],
                          emails_sent=current["emails_sent"])
        if current["leads"] != previous["leads"]:
            emit(f"COHORT {watched} leads {previous['leads']} -> {current['leads']}")
        if current["emails_sent"] > previous["emails_sent"]:
            emit(f"SEND {watched} emails_sent {previous['emails_sent']} -> "
                 f"{current['emails_sent']}")
            # FIRST only - the 0 -> N transition. Every later send is
            # ordinary and a channel told about each one is a channel nobody
            # reads. Today's 489 send is deliberately NOT back-filled: it is
            # in the register at 13:34:48Z with four witnesses.
            if previous["emails_sent"] == 0:
                milestone(PROVIDER_ID, "first_send",
                          emails_sent=current["emails_sent"],
                          queue_rows=current["queue_rows"])
        if current["sent_rows"] > previous["sent_rows"]:
            emit(f"SEND {watched} queue rows sent {previous['sent_rows']} -> "
                 f"{current['sent_rows']} of {current['queue_rows']}")
        if current["replied"] > previous["replied"]:
            emit(f"REPLY {watched} replied {previous['replied']} -> "
                 f"{current['replied']}")
            if previous["replied"] == 0:
                milestone(PROVIDER_ID, "first_reply",
                          replied=current["replied"])
        if current["bounced"] > previous["bounced"]:
            emit(f"BOUNCE {watched} bounced {previous['bounced']} -> "
                 f"{current['bounced']}")
            if previous["bounced"] == 0:
                milestone(PROVIDER_ID, "first_bounce",
                          bounced=current["bounced"],
                          emails_sent=current["emails_sent"])
        if current["unsubscribed"] > previous["unsubscribed"]:
            emit(f"UNSUB {watched} unsubscribed {previous['unsubscribed']} -> "
                 f"{current['unsubscribed']}")
        # AFTER the send lines, and only when they did not fire. A queue that
        # grew because something was sent is already reported above; this is
        # the other case - the provider planning work it has not done yet,
        # which is the first observable sign it has looked at this campaign.
        if (current["queue_rows"] != previous["queue_rows"]
                and current["sent_rows"] == previous["sent_rows"]):
            emit(f"QUEUED {watched} scheduled rows {previous['queue_rows']} -> "
                 f"{current['queue_rows']} (none sent)")
        if current["updated_at"] != previous["updated_at"]:
            emit(f"TOUCHED {watched} updated_at {previous['updated_at']} -> "
                 f"{current['updated_at']} (sent={current['emails_sent']}, "
                 f"queue={current['queue_rows']})")
        if current["first_scheduled"] != previous["first_scheduled"]:
            emit(f"SCHEDULE-MOVED {watched} first send "
                 f"{previous['first_scheduled']} -> "
                 f"{current['first_scheduled']}")
        # LAST, because it is the slowest-moving of the lot and the one whose
        # movement is most likely to be the answer to a standing question.
        # 487's ten leads have read `sending_paused` since it was activated;
        # whether the provider flips them when the window opens is the
        # falsifier this line exists to catch.
        if current["membership"] != previous["membership"]:
            emit(f"MEMBERSHIP {watched} per-lead status "
                 f"{previous['membership']} -> {current['membership']}")
        # WHAT THE PROVIDER SAYS IT WILL SEND. Two lines:
        #
        # PROVIDER-VOLUME: the provider's near-term sending volume changed.
        # This is the direct answer to "what will actually send", as opposed
        # to our inference from `first_scheduled` or queue rows.
        #
        # DISAGREEMENT: the provider's answer disagrees with our inference.
        # We believe a send lands tomorrow and the provider reports nothing
        # for tomorrow, or vice versa. A disagreement is itself an event:
        # 487's ten openers moved date twice without anybody being told, and
        # both times the first hint was a human re-reading a number.
        if current["provider_plan"] != previous["provider_plan"]:
            emit(f"PROVIDER-VOLUME {watched} provider plan "
                 f"{previous['provider_plan']} -> {current['provider_plan']}")
        disagreement = _check_disagreement(current)
        prev_disagreement = _check_disagreement(previous)
        if disagreement != prev_disagreement:
            if disagreement:
                emit(f"DISAGREEMENT {watched} {disagreement}")
            else:
                emit(f"AGREEMENT {watched} provider plan now matches "
                     f"first_scheduled={current['first_scheduled']}")

        previous = current
        time.sleep(args.interval)


if __name__ == "__main__":
    raise SystemExit(main())
