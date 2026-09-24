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
from src import emptyrender                                     # noqa: E402
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
    # ONE REFUSED READ MUST NOT BLIND THE WHOLE WATCHER.
    #
    # MEASURED 2026-09-23. This call took the 40-page default while
    # `slackagentreadback` and `hard_stop_check` both walked 400. Campaign 491
    # reached 647 rows - 44 pages - so it raised `PartialInventory`, correctly:
    # the queue really could not be read whole. But it was raising from the
    # top of `snapshot()` with nothing around it, so the refusal took down
    # every OTHER field too. `bison-491.json` read `READ-ERROR 122x` while
    # `emails_sent`, `replied`, `bounced` and `membership` all answered fine,
    # on the largest campaign in the estate, for hours.
    #
    # Two changes, and the second is the one that matters:
    #   - walk as far as the other two readers do, so three readers cannot
    #     disagree about what was sent;
    #   - and when even that refuses, record the queue as UNKNOWN and keep
    #     the rest. `_membership_states` and `_provider_sending_plan` in this
    #     same file already do exactly this; the queue read was the one that
    #     never got the treatment.
    #
    # UNKNOWN IS `None`, NEVER `0`. `queue = []` on a failed read would report
    # 647 rows -> 0 and fire QUEUED as though the provider had emptied the
    # queue. An absence read off a short list is the failure this provider
    # module is most careful about, and a false zero on the send-detection
    # path is the expensive direction.
    try:
        queue = bison.scheduled_emails(
            provider_id, cap=bison.CAMPAIGN_QUEUE_PAGE_CAP) or []
    except bison.PartialInventory as exc:
        emit(f"QUEUE-UNREADABLE {provider_id}: {str(exc)[:160]}")
        queue = None
    # THE BLANK-CONTENT SCAN, ON THE ROWS ALREADY IN HAND.
    #
    # OPERATOR DECISION 2026-09-23, control (b) of the incident gate: every
    # cycle, every scheduled row of every active campaign, halted CRITICAL on
    # any hit. See `docs/INCIDENT-2026-09-23-BLANK-EMAILS.md`.
    #
    # It runs HERE because `snapshot` has already paid for the queue read, so
    # the check costs no extra provider call - which is what makes "every
    # cycle" affordable rather than aspirational.
    #
    # IT DOES NOT CARE WHOSE LEAD IT IS, and that is the whole point. 73 of
    # the 76 blank emails went to leads our factory never created and that no
    # guard of ours had any reason to look at. A check that only examined our
    # own staged leads would have reported this campaign clean while it sent.
    #
    # None when the queue could not be read, distinct from an empty finding.
    # A scan that reports "no blanks" off a queue it could not read is the
    # false clean this whole incident is about.
    blanks = None if queue is None else emptyrender.scan(queue)
    sent_rows = None if queue is None else 0
    for entry in queue or []:
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
        # None when the queue could not be read whole. Distinct from 0, which
        # means the provider has nothing queued.
        "queue_rows": None if queue is None else len(queue),
        "sent_rows": sent_rows,
        # `{"pending": [...], "already": [...]}`, or None if unreadable.
        "blanks": blanks,
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
        # "unknown" rather than "none" when the queue was unreadable: "none"
        # asserts nothing is planned, which is a claim this read cannot make.
        "first_scheduled": "unknown" if queue is None else min(
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


#: Statuses that mean the campaign has stopped working through its sequence.
#: A transition INTO one of these is the event this alerts on.
STOPPED_STATUSES = ("archived", "paused", "stopped")

#: Log STEPS this system writes when IT stops a campaign. Matched exactly,
#: never as a substring of a free-text note - see `_we_did_it`.
OUR_STOP_STEPS = frozenset({"pause", "paused", "archive", "archived",
                            "stop", "stopped", "hard_stop", "kill"})

#: How recently one of those must have been logged to explain a transition.
RECENT_HOURS = 6


def _we_did_it(provider_id, rows=None):
    """Does canonical state record US stopping this campaign, recently?

    Returns `(ours, why)`. `ours` is True only on POSITIVE evidence - a log
    line on our own campaign row naming a pause or an archive. Absence is
    never read as proof that somebody else did it; it is read as "we cannot
    show that we did", which is what the alert says.

    That asymmetry is the point. The register's standing rule is that missing
    evidence is never positive evidence, and the expensive mistake here would
    be telling an operator a third party archived their campaign when our own
    process did it four minutes earlier.
    """
    try:
        import datetime
        from src import campaigns
        rows = campaigns.load() if rows is None else rows
        row = next((r for r in rows
                    if str(r.get("bison_campaign_id")) == str(provider_id)),
                   None)
        if row is None:
            return False, "no local campaign row names this provider campaign"
        # THE STEP, NOT THE NOTE, AND RECENT.
        #
        # This matched any log entry whose NOTE contained "stop", and 495's
        # row carries "0 held by the 2% bounce stop" from 09-21 - an
        # unrelated sentence about a mailbox re-point. So the campaign this
        # alert was built for would have been attributed to us and silenced.
        # Caught by its own test before it ever ran.
        #
        # `step` is a structured verb this system writes; a note is prose and
        # prose about stopping is not a record of having stopped. Recency
        # matters for the same reason: a deliberate pause two days ago does
        # not explain a status change four minutes ago.
        cutoff = (datetime.datetime.now(datetime.UTC)
                  - datetime.timedelta(hours=RECENT_HOURS)).isoformat()
        for entry in reversed(row.get("log") or []):
            step = str(entry.get("step") or "").strip().lower()
            if step not in OUR_STOP_STEPS:
                continue
            when = str(entry.get("at") or "")
            if when < cutoff:
                return False, (f"our campaign row logs {step!r} but at "
                               f"{when}, more than {RECENT_HOURS}h ago")
            return True, (f"our campaign row logs {step!r} at {when}")
        return False, ("our campaign row logs no recent pause, archive or "
                       "stop step")
    except Exception as exc:                                    # noqa: BLE001
        return False, f"canonical state unreadable: {type(exc).__name__}"


def _alert_if_stopped_by_someone_else(provider_id, watched, was, current,
                                      emit):
    """A campaign we did not stop has stopped. CRITICAL, by operator decision.

    MEASURED 2026-09-23. EmailBison 495 went `active` -> `archived` at
    15:57:22Z with 59 of its 60 leads reading `stopped` and 42 of 60 ever
    contacted. Nothing in this system did it: no action-ledger row, no write
    refusal, and our own campaign row's last entry is from 09-21. Nobody was
    told. It was found hours later by reading a heartbeat file by hand while
    looking at something else.

    A campaign stopping is the loudest possible fact about an outbound
    system - it is the difference between sending and not sending - and it
    was the one state change with no alert on it.

    THE PROVIDER NAMES NO ACTOR. Its event feed carries delivery events only
    and holds zero rows mentioning an archive, so "who" is not answerable
    from the API. This therefore reports what it can prove: the transition,
    and whether OUR OWN canonical state can account for it. It never asserts
    a third party.

    Does not un-archive anything. Nothing here writes to the provider.
    """
    if str(current.get("status") or "").lower() not in STOPPED_STATUSES:
        return
    ours, why = _we_did_it(provider_id)
    emit(f"CAMPAIGN-STOPPED {watched} {was} -> {current['status']} "
         f"({'ours' if ours else 'NOT ATTRIBUTABLE TO US'}: {why})")
    if ours:
        return
    try:
        from src import notify
        notify.notify(
            notify.CAMPAIGN_STOPPED_EXTERNALLY, None,
            fields={"campaign": str(provider_id),
                    "was": was, "now": current.get("status"),
                    "emails_sent": current.get("emails_sent"),
                    "leads": current.get("leads"),
                    "why": why,
                    "action": "a campaign stopped and this system cannot show "
                              "it did it. The provider names no actor. Do NOT "
                              "un-archive: find out who first"},
            ids={"campaign_id": str(provider_id), "status": current.get("status")})
    except Exception as exc:                                    # noqa: BLE001
        emit(f"ALERT-FAILED {watched}: {type(exc).__name__}")


#: The ONE route the blank-content halt may use. A fragment, not a whole URL,
#: so a host change cannot silently widen or void it - the contract
#: `providers.allow_writes(only=...)` documents.
PAUSE_ROUTES = ("/pause",)


def _halt_on_blank_content(provider_id, state, emit):
    """Control (b): a campaign about to send an empty email is stopped.

    OPERATOR DECISION 2026-09-23. Returns True if a halt was attempted.

    THE HALT IS ATTEMPTED AND THE ALERT IS SENT EITHER WAY, in that order of
    importance. A pause that refuses - killswitch, an unsupported verb, a
    provider 500 - must not swallow the finding: the whole incident is a
    fault that was real for a day and a half while every reading of it said
    fine. So the alert carries whether the pause succeeded rather than being
    conditional on it.

    ONLY `pending` ROWS HALT. A `sent` blank is already a fact and pausing
    the campaign cannot unsend it; a `stopped` one cannot reach anybody. Both
    are reported in the alert because the counts are the incident and its
    containment, but halting on them would mean every campaign that ever sent
    a blank is permanently unstartable, which would make the control the
    first thing somebody disables.
    """
    blanks = state.get("blanks")
    if not blanks or not blanks["pending"]:
        return False

    pending = blanks["pending"]
    steps = sorted({str(e["step"]) for e in pending if e.get("step")})
    reasons = sorted({f"{f}/{r}" for e in pending for f, r in e["faults"]})
    emit(f"BLANK-CONTENT {provider_id} {len(pending)} row(s) would send "
         f"empty: steps {','.join(steps) or '?'} reasons {','.join(reasons)}")

    paused, why = False, ""
    try:
        from src import providerwrites
        from src import providers as _providers
        # A ROUTE-SCOPED SCOPE, FOR EXACTLY ONE VERB.
        #
        # A watcher is a reader and holds no write scope, which is why this
        # halt refused the first time it was exercised: "no
        # RESONATE_PROVIDER_WRITES and no allow_writes() scope", recorded in
        # `work/provider-write-refusals.jsonl` at 2026-09-23T20:18:58Z. The
        # guard was right and the control was ceremony - it alerted and
        # halted nothing.
        #
        # `only=PAUSE_ROUTES` and not a bare scope, for the reason
        # `allow_writes` states: without it this block would authorise every
        # mutating route for its duration, and a function believed only to
        # pause is one refactor from enrolling, resuming or creating. This
        # loop's job is to stop a campaign that is about to send an empty
        # email. It gets that and nothing else.
        with _providers.allow_writes(
                f"blank-content halt on campaign {provider_id}: rendered "
                f"rows would send empty (OPERATOR DECISION 2026-09-23)",
                only=PAUSE_ROUTES):
            providerwrites.perform(
                providerwrites.EMAIL_PAUSE,
                campaign=str(provider_id),
                payload={"campaign_id": provider_id},
                transport=lambda _p: bison.pause_campaign(provider_id),
                readback=lambda: {"status": str(
                    (bison.campaign(provider_id) or {}).get("status")
                    or "").lower()},
                expected={"status": "paused"},
                step="blank_content_halt", by="bison_watch_loop")
        paused = True
    except Exception as exc:                                  # noqa: BLE001
        why = f"{type(exc).__name__}: {str(exc)[:200]}"
        emit(f"BLANK-CONTENT-HALT-REFUSED {provider_id} {why}")

    try:
        from src import notify as _notify
        _notify.notify(
            _notify.CAMPAIGN_BLANK_CONTENT, None,
            fields={
                "campaign": provider_id,
                "rows_that_would_send_empty": len(pending),
                "rows_already_sent_or_stopped": len(blanks["already"]),
                "steps": ", ".join(steps) or "unknown",
                "reasons": ", ".join(reasons),
                "campaign_paused": "yes" if paused else f"NO - {why}",
            },
            actions=("Read the queue rows before restarting anything.",
                     "docs/INCIDENT-2026-09-23-BLANK-EMAILS.md"))
    except Exception as exc:                                  # noqa: BLE001
        emit(f"BLANK-CONTENT-ALERT-FAILED {provider_id} {type(exc).__name__}")
    return True


def _known(*values):
    """True when every value is a real reading rather than an UNKNOWN.

    The queue fields are `None` when `scheduled_emails` refused, and a
    comparison against an unknown is neither true nor false - it is not a
    question. Guarding with this rather than `or 0` on purpose: a default of
    zero turns "we could not read it" into "there is nothing there", which is
    the exact substitution this watcher exists to catch at the provider.
    """
    return all(v is not None for v in values)


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

        # BEFORE the first-cycle early return, deliberately. Every other
        # check here compares against `previous` and so cannot run on the
        # first poll - but "this campaign is about to send an empty email" is
        # not a transition, it is a standing fact, and a watcher restarted at
        # 21:31 must not wait an interval to notice one. The incident it
        # exists for was true for a day and a half.
        _halt_on_blank_content(watched, current, emit)

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
            # `watched`, NOT `PROVIDER_ID`. The module constant is 487 and
            # this loop runs nine times over nine `--campaign` values, so
            # passing it named campaign 487 in EVERY external-stop alert the
            # estate has ever raised. On 2026-09-23T22:18:46Z the 491 watcher
            # reported 491's own pause as `{"campaign": "487", "emails_sent":
            # 322, "leads": 332}` - 487 has 0 sends and 10 leads. A CRITICAL
            # naming a campaign that is demonstrably fine reads as a false
            # alarm, and that one went unactioned into the morning.
            _alert_if_stopped_by_someone_else(
                watched, watched, previous["status"], current, emit)
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
        # `_known` on both sides before every queue-derived comparison. An
        # unreadable queue is None, and `None > 0` is a TypeError in this
        # language - the watcher would die on the campaign it most needs to
        # watch. Comparing against an unknown also cannot report movement:
        # the difference between 647 and unknown is not a send.
        if _known(current["sent_rows"], previous["sent_rows"]) \
                and current["sent_rows"] > previous["sent_rows"]:
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
        if (_known(current["queue_rows"], previous["queue_rows"])
                and current["queue_rows"] != previous["queue_rows"]
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
