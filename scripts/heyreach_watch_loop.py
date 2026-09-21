#!/usr/bin/env python3
"""Emit ONE line whenever campaign 605732's provider truth changes. READ-ONLY.

    py -3 scripts/heyreach_watch_loop.py [--interval 300]

Built for a background monitor, so it prints one line per EVENT and nothing
while the picture is unchanged. Every line is flushed, because a line sitting
in a buffer is a line nobody sees.

WHAT IT EMITS, and the list is deliberately wider than the good news:

    SEND        a lead's leadMessageStatus reached MessageSent/MessageReply
    CONNECT     a lead's leadConnectionStatus reached ConnectionSent/Accepted
    REPLY       a lead replied
    PROGRESS    the provider acted on a lead - `lastActionTime` moved - WITHOUT
                any of the three lifecycle fields changing
    LEAD-ERROR  a lead carries an error_code, or its status went to Failed
    STATUS      the campaign left IN_PROGRESS (paused, finished, failed)
    COHORT      the enrolled lead count moved - the audience changed under us
    READ-ERROR  the provider could not be read (reported, not fatal)

Silence means "nothing changed", and that is only trustworthy because a
failure has its own line. A watcher that emits only on success is
indistinguishable from a watcher whose campaign died an hour ago.

WHY `PROGRESS` EXISTS, added 2026-09-17. The three lifecycle fields describe
connection and message and nothing else, so a campaign working through
`CHECK_IS_CONNECTION`, `VIEW_PROFILE` and `FOLLOW` - thirty hours of this
sequence's graph, before the connection request - produced no line at all.
A campaign being worked and a campaign that died read IDENTICALLY for the
whole ramp. `lastActionTime` is the only per-lead signal this provider offers
that the campaign is alive, and until now nothing read it. It is not a send
and it is never reported as one. See
`docs/THE-LINKEDIN-STALL-IS-THE-GRAPH-2026-09-17.md`.
"""
import argparse
import hashlib
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import liststaging, watchsink                          # noqa: E402
from src.providers import heyreach, load_env                     # noqa: E402

PROVIDER_ID = 605732
SENT_MESSAGE = {"MessageSent", "MessageReply"}
SENT_CONNECTION = {"ConnectionSent", "ConnectionAccepted"}



def milestone(kind, **fields):
    """Raise a campaign_milestone for the LinkedIn campaign. Never fatal.

    Same reason as the EmailBison watcher: a watcher firing was not a
    notification until 2026-09-21. Idempotent through
    `notify.notification_id`, which builds the id from the identifiers, so a
    180s re-poll or a restart cannot raise the same milestone twice.
    """
    try:
        from src import notify as _notify
        _notify.notify("campaign_milestone", "productive",
                       fields=dict(fields, campaign=PROVIDER_ID,
                                   channel="linkedin", milestone=kind),
                       ids={"campaign_id": str(PROVIDER_ID),
                            "milestone": kind})
    except Exception as exc:                                    # noqa: BLE001
        emit(f"MILESTONE-FAILED {PROVIDER_ID} {kind}: "
             f"{type(exc).__name__}: {str(exc)[:100]}")
def h12(value):
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:12]


def emit(line):
    """Stdout only. The DURABLE emitter is built in `main` - see
    `src/watchsink.py` for why printing alone was not a monitor."""
    print(line, flush=True)


def snapshot():
    row = heyreach.campaign_read(PROVIDER_ID) or {}
    rows, total = heyreach.campaign_leads(PROVIDER_ID)
    leads = {}
    for lead in rows or []:
        raw = lead.get("raw") or {}
        url = liststaging.canonical_profile_url(lead.get("profile_url"))
        leads[h12((url or "").lower())] = {
            "message": str(raw.get("leadMessageStatus") or "None"),
            "connection": str(raw.get("leadConnectionStatus") or "None"),
            "campaign": str(raw.get("leadCampaignStatus") or ""),
            "error": lead.get("error_code"),
            # `lead_state` already resolves this to lastActionTime, falling
            # back to failedTime. Carried verbatim: it is compared for
            # movement and never parsed, so a format this system has not seen
            # still reports progress rather than raising.
            "at": lead.get("at"),
        }
    return {"status": str(row.get("status") or "").upper(),
            "total": total, "leads": leads}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--interval", type=float, default=300.0)
    args = parser.parse_args(argv)

    load_env(os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "config", ".env"))

    # Durable from here down. `emit` still prints; the difference is that the
    # line now also lands in `work/watch-events/heyreach-605732.jsonl` and
    # survives the shell that launched this process.
    emit = watchsink.emitter("heyreach", campaign=PROVIDER_ID)

    previous = None
    consecutive_errors = 0
    # Milestones already raised by THIS process. The notification id
    # dedups across restarts; this avoids even building the row twice
    # when several leads cross the same threshold in one sweep.
    fired = set()
    while True:
        try:
            current = snapshot()
            consecutive_errors = 0
        except Exception as exc:
            consecutive_errors += 1
            # Transient provider timeouts are common on this estate today, so
            # one failure is noted only after it repeats - but it IS noted.
            if consecutive_errors in (3, 12):
                emit(f"READ-ERROR 605732 unreadable {consecutive_errors}x: "
                     f"{type(exc).__name__}")
            watchsink.beat("heyreach", campaign=PROVIDER_ID,
                           note=f"READ-ERROR {consecutive_errors}x "
                                f"{type(exc).__name__}")
            time.sleep(args.interval)
            continue

        # EVERY poll, including the ones that emit nothing. `leads` is a dict
        # keyed by a hashed profile - no PII reaches the heartbeat.
        watchsink.beat("heyreach", campaign=PROVIDER_ID,
                       state={"status": current.get("status"),
                              "total": current.get("total"),
                              "leads": len(current.get("leads") or {})})

        if previous is None:
            emit(f"WATCHING 605732 status={current['status']} "
                 f"leads={current['total']} sent=0")
            previous = current
            time.sleep(args.interval)
            continue

        if current["status"] != previous["status"]:
            emit(f"STATUS 605732 {previous['status']} -> {current['status']}")
        if current["total"] != previous["total"]:
            emit(f"COHORT 605732 enrolled {previous['total']} -> "
                 f"{current['total']}")

        for phash, now in current["leads"].items():
            was = previous["leads"].get(phash) or {}
            if now["message"] != was.get("message"):
                if now["message"] in SENT_MESSAGE:
                    label = "REPLY" if now["message"] == "MessageReply" else "SEND"
                    emit(f"{label} 605732 {phash} message={now['message']}")
                    # FIRST on this campaign only. `fired` is per-process and
                    # the id dedups across restarts, so a re-poll cannot
                    # repeat it and neither can tomorrow's process.
                    kind = ("first_reply" if label == "REPLY"
                            else "first_send")
                    if kind not in fired:
                        fired.add(kind)
                        milestone(kind, message=now["message"])
                else:
                    emit(f"LEAD-CHANGE 605732 {phash} "
                         f"message={was.get('message')} -> {now['message']}")
            if (now["connection"] != was.get("connection")
                    and now["connection"] in SENT_CONNECTION):
                emit(f"CONNECT 605732 {phash} "
                     f"connection={now['connection']}")
            if now.get("error") and now.get("error") != was.get("error"):
                emit(f"LEAD-ERROR 605732 {phash} error={now['error']}")
            if now["campaign"] == "Failed" and was.get("campaign") != "Failed":
                emit(f"LEAD-ERROR 605732 {phash} campaignStatus=Failed")
            if (now["campaign"] in ("Finished", "Completed")
                    and was.get("campaign") not in ("Finished", "Completed")
                    and "sequence_finished" not in fired):
                fired.add("sequence_finished")
                milestone("sequence_finished", campaignStatus=now["campaign"])
            # LAST, and only when nothing above fired: the lifecycle lines
            # already say more than this one can. On its own it says the
            # provider did something to this lead that connection and message
            # status cannot express - a profile view, a follow, a check.
            if (now.get("at") != was.get("at")
                    and now["message"] == was.get("message")
                    and now["connection"] == was.get("connection")):
                emit(f"PROGRESS 605732 {phash} lastAction={now.get('at')} "
                     f"(no send; campaignStatus={now['campaign']})")

        previous = current
        time.sleep(args.interval)


if __name__ == "__main__":
    raise SystemExit(main())
