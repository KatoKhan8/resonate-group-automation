#!/usr/bin/env python3
"""The 7-day bounce hard stop, measured from OUR OWN sends and nothing else.

    py -3 scripts/bounce_stop_7day.py
    py -3 scripts/bounce_stop_7day.py --days 7 --json

READ-ONLY. Writes nothing.

## EVERY MAILBOX GETS A VERDICT, AND BLIND IS A VERDICT

Added 2026-10-16, TASK-0140, after this script was measured producing **no
verdict for any mailbox, with nothing on stdout**. It had zero `except`
clauses, and campaign 491 - the THIRD entry in its own `OURS` tuple - is 665
rows, 45 pages, against the `bison.PAGE_CAP` default of 40. So
`bison._paged` raised `PartialInventory` out of `measure()`, past `main()`,
and the standing hard stop had not run since 2026-09-22. Reproduced at the
provider seam with no network call: stdout 0 bytes, 487 and 489 already read
whole and discarded with the exception, 492 through 498 never asked.

    PASS    measured, under THRESHOLD, off a COMPLETE read of every campaign
    STOP    measured AT OR OVER THRESHOLD
    BLIND   could not be measured, and the exception class is in the reason

**A PASS NEEDS A COMPLETE READ AND A STOP DOES NOT.** That asymmetry is
`senderheadroom`'s and it is deliberate: a campaign we could not read may hold
the very bounces that would trip a mailbox, so no mailbox is cleared while one
is unreadable - *REFUSED IS NOT ROOM* - but a mailbox already at or over the
line is over it whatever else arrives, and stopping is the safe direction.

**THE CATCH IS NARROW.** `bison.ProviderError` per campaign, named in the
reason, and `(ValueError, TypeError)` per row around the timestamp only.
Anything else escapes, because a bare `except` around the loop turns a bug in
our own code into a BLIND and hides it.

## EXIT CODES ARE THREE, NOT TWO

    0   CLEAR or NO-DATA - every mailbox measured and under, or nothing to
        measure, with every campaign read whole
    1   STOP   - at least one mailbox at or over the threshold
    2   BLIND  - no stop, but something could not be measured

The old script returned 1 for a trip AND died with 1 on the refusal, so a
reader keyed on the status could not tell a tripped hard stop from a crashed
one. Any non-zero means DO NOT SEND until a human has read the line.

## THE QUESTION, AND WHY THE USUAL ANSWER IS THE WRONG ONE

The standing hard stop is **bounce > 2% on any mailbox over 7 days**. Every
stop checked in this project so far has been LIFETIME, which is what
`bison.sender_emails()` returns: 3437 reads 2.14% over 8,947 sends, and those
8,947 sends are overwhelmingly the client's, made before this system existed.

Lifetime and 7-day are different questions. A mailbox with a bad decade and a
clean week passes the stated rule; a mailbox with a clean decade and a bad
week fails it. Only sends WE caused can answer the rule as written.

## WHERE OUR OWN SENDS ACTUALLY LIVE, AND WHERE THEY DO NOT

**Not in `work/action-ledger.jsonl`.** That ledger holds 136 rows of
`bison.activate`, `heyreach.activate` and `heyreach.add_lead`, it stops on
2026-09-18, and it carries no send and no bounce event of any kind. It records
what was ATTEMPTED against a provider, not what a provider then did. A 7-day
bounce rate cannot be derived from it, and a script that appeared to do so
would be reading activations as sends.

So this reads the per-message queue rows of the campaigns THIS SYSTEM owns.
Each row is one message, carries its own `status`, `sent_at` and sender, and
goes `scheduled` -> `sent` | `bounced` | `stopped`. That is the same witness
`production_status` uses, and it is the only record of what our own sends did.

## UNDEFINED IS NOT ZERO, AND IT IS NOT A PASS EITHER

A mailbox this system has never sent from has NO 7-day bounce rate. It is not
0%, it is unanswerable, and the two must not print the same way: a 0% that
means "we never asked" is exactly the reading that would clear a hold nobody
had evidence to clear. Such a mailbox gets no row and no verdict here - it is
absent, not passing - and a run where NO mailbox sent in the window reports
`NO-DATA` with `0 PASS` rather than a clean bill.

## A SEND WE CANNOT ATTRIBUTE IS STILL A SEND

A `sent` or `bounced` row with no usable `sender_email.id` was previously
dropped with no trace, so a queue of unattributed sends read as a queue of
none and every other mailbox passed off a denominator that was missing them.
Such rows are counted, reported, and they blind the roster for the same reason
an unreadable campaign does: a rate measured over an incomplete denominator
cannot clear anybody. They never suppress a STOP.
"""
import argparse
import collections
import datetime
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from src.providers import bison, load_env                        # noqa: E402

#: Every campaign this system has ever pointed at a prospect. The client's own
#: 327/328/352 are deliberately absent: their sends are not our actions and
#: folding them in would rebuild the lifetime number this script exists to
#: replace.
OURS = (487, 489, 491, 492, 493, 494, 495, 496, 497, 498)

THRESHOLD = 2.0

#: The three answers, and the only three. Named so a rewrite that quietly
#: drops BLIND goes red in the test file rather than going silent in
#: production, which is the failure this script was repaired for.
VERDICTS = ("PASS", "STOP", "BLIND")

#: Pages this check will walk for one campaign. 491 is 45 pages, so the
#: `bison.PAGE_CAP` default of 40 cannot read it at all - the watcher,
#: `slackagentreadback` and `hard_stop_check` all walk 400 on this same
#: endpoint and have since 2026-09-23. Still BOUNDED: past this the campaign
#: is reported BLIND rather than measured in part and called whole.
QUEUE_PAGE_CAP = bison.CAMPAIGN_QUEUE_PAGE_CAP

EXIT_CLEAR, EXIT_STOP, EXIT_BLIND = 0, 1, 2


def window_start(days):
    return (datetime.datetime.now(datetime.timezone.utc)
            - datetime.timedelta(days=days))


def _sender_id(row):
    """The mailbox id, or None when the row cannot be attributed to one.

    `sender_email` is a dict on this route and a bare string on others, and
    `.get` on a string is an `AttributeError` - which is exactly the class of
    unanticipated exception that must NOT be caught into a BLIND. Handled by
    shape instead.
    """
    sender = row.get("sender_email")
    if isinstance(sender, dict):
        sid = sender.get("id")
    else:
        sid = None
    if sid is None:
        return None
    try:
        return int(sid)
    except (TypeError, ValueError):
        return None


def _blank_entry():
    return {"sent": 0, "bounced": 0, "campaigns": set(), "blind": None}


def measure(days=7, campaigns=None, rows_source=None):
    """`(since, per_mailbox, unreadable, unattributed)`. Never raises on a read.

    `unreadable` is one dict per campaign whose read refused, carrying the
    exception CLASS NAME and its message. `unattributed` counts in-window
    `sent`/`bounced` rows with no usable mailbox id.

    `rows_source` IS A SEAM AND NOT A FEATURE. Added 2026-10-16, TASK-0160,
    so `src/stopwatchdog.controls` can drive this function through STOP and
    through BLIND on every scheduled pass with no provider call and no
    network - the control that proves the instrument can still fail. It
    defaults to `bison.scheduled_emails`, resolved at call time so a test
    patching the module attribute is still intercepted, and no production
    caller passes it.
    """
    campaigns = OURS if campaigns is None else campaigns
    read_queue = rows_source or bison.scheduled_emails
    since = window_start(days)
    per = collections.defaultdict(_blank_entry)
    unreadable, unattributed = [], 0
    for cid in campaigns:
        # ONE REFUSED READ MUST NOT BLIND THE WHOLE CHECK, AND MUST NEVER BE
        # SKIPPED. `bison.ProviderError` is the base of `PartialInventory`,
        # `HttpTimeout`, `HttpTransportError`, `MissingKey` and
        # `WorkspaceMismatch` - every way this read can legitimately fail.
        # A `KeyError` or `AttributeError` from our own row handling is not
        # one of them and is left to escape.
        try:
            rows = read_queue(cid, cap=QUEUE_PAGE_CAP)
        except bison.ProviderError as exc:
            unreadable.append({"campaign": cid,
                               "error": type(exc).__name__,
                               "detail": str(exc)})
            continue
        for row in rows or []:
            status = str(row.get("status") or "").lower()
            if status not in ("sent", "bounced"):
                continue
            sid = _sender_id(row)
            stamp = row.get("sent_at") or row.get("scheduled_date")
            # A ROW WE CANNOT DATE CANNOT BE PLACED IN OR OUT OF THE WINDOW.
            # Its mailbox therefore has no measurable rate, so it is blinded
            # by name rather than having the row silently dropped. Narrow:
            # only the parse is guarded.
            when = None
            if stamp:
                try:
                    when = datetime.datetime.fromisoformat(
                        str(stamp).replace("Z", "+00:00"))
                except (ValueError, TypeError) as exc:
                    when = False
                    reason = (f"{type(exc).__name__} parsing sent_at "
                              f"{stamp!r} on campaign {cid}")
            else:
                when = False
                reason = f"no sent_at or scheduled_date on campaign {cid}"
            if when is False:
                if sid is None:
                    unattributed += 1
                else:
                    entry = per[sid]
                    entry["campaigns"].add(cid)
                    if entry["blind"] is None:
                        entry["blind"] = reason
                continue
            if when.tzinfo is None:
                when = when.replace(tzinfo=datetime.timezone.utc)
            if when < since:
                continue
            if sid is None:
                unattributed += 1
                continue
            entry = per[sid]
            entry[status] += 1
            entry["campaigns"].add(cid)
    return since, dict(per), unreadable, unattributed


def verdicts(per, unreadable, unattributed):
    """One verdict per mailbox. `roster_complete` is the second return.

    The roster is complete only when every campaign was read whole AND every
    in-window send could be attributed to a mailbox. While it is not, a rate
    under the threshold proves nothing, so a clean mailbox is BLIND rather
    than PASS - but a mailbox at or over the threshold is STOPPED anyway.
    """
    roster_complete = not unreadable and not unattributed
    if unreadable:
        blocked = ("; ".join(f"campaign {u['campaign']} unreadable "
                             f"({u['error']})" for u in unreadable))
    else:
        blocked = ""
    if unattributed:
        blocked = "; ".join(filter(None, [
            blocked, f"{unattributed} in-window send(s) with no mailbox id"]))

    out = {}
    for sid, e in sorted(per.items()):
        total = e["sent"] + e["bounced"]
        rate = (100.0 * e["bounced"] / total) if total else None
        row = {"sent": e["sent"], "bounced": e["bounced"], "rate": rate,
               "campaigns": sorted(e["campaigns"]), "reason": ""}
        if rate is not None and rate >= THRESHOLD:
            # AT OR OVER. A rule written "> 2%" leaves a mailbox at exactly
            # 2.00% in no class at all, which is a silent gap at the rule's
            # own boundary. Over-inclusive is the safe direction for a stop.
            row["verdict"] = "STOP"
            row["reason"] = (f"{e['bounced']}/{total} = {rate:.2f}% >= "
                             f"{THRESHOLD}%")
        elif e["blind"]:
            row["verdict"] = "BLIND"
            row["reason"] = e["blind"]
        elif not roster_complete:
            row["verdict"] = "BLIND"
            row["reason"] = (f"a pass needs a complete read and this one was "
                             f"not: {blocked}")
        elif rate is None:
            # Counted nothing in the window but was seen, which only happens
            # through a blinded row; handled above. Kept explicit rather than
            # falling through to PASS on a rate of None.
            row["verdict"] = "BLIND"
            row["reason"] = "no dateable send in the window for this mailbox"
        else:
            row["verdict"] = "PASS"
            row["reason"] = f"{e['bounced']}/{total} = {rate:.2f}%"
        out[sid] = row
    return out, roster_complete


def _summary(result):
    """One sentence. This is the line the operator reads before a batch."""
    counts = collections.Counter(e["verdict"] for e in
                                 result["mailboxes"].values())
    n_stop, n_pass, n_blind = counts["STOP"], counts["PASS"], counts["BLIND"]
    days = result["days"]
    unread = [str(u["campaign"]) for u in result["unreadable"]]
    if result["verdict"] == "STOP":
        worst = max((e for e in result["mailboxes"].values()
                     if e["verdict"] == "STOP"), key=lambda e: e["rate"])
        # A STOP MUST NOT HIDE A BLIND. An unreadable campaign alongside a
        # stopped mailbox produced NO blinded mailbox and therefore no BLIND
        # in this sentence, which is the same disappearance this script was
        # repaired for, one level up.
        if n_blind or unread or result["unattributed"]:
            tail = (f", {n_blind} BLIND and STILL BLIND on "
                    f"{len(unread) + bool(result['unattributed'])} read(s)")
        else:
            tail = ""
        return (f"7-DAY BOUNCE STOP: {n_stop} mailbox(es) STOPPED, worst "
                f"{worst['rate']:.2f}%, {n_pass} PASS{tail} - do not send "
                f"from a stopped mailbox.")
    if result["verdict"] == "BLIND":
        if not result["mailboxes"] and len(unread) == len(result["campaigns"]):
            return (f"7-DAY BOUNCE STOP IS BLIND: 0 of "
                    f"{len(result['campaigns'])} campaigns could be read, so "
                    f"no mailbox has a verdict and the {THRESHOLD}% stop did "
                    f"NOT run.")
        why = (f"campaign(s) {', '.join(unread)} unreadable" if unread
               else f"{result['unattributed']} send(s) with no mailbox id")
        return (f"7-DAY BOUNCE STOP IS BLIND for {n_blind} of "
                f"{len(result['mailboxes'])} mailbox(es): {why}, so no "
                f"mailbox can be cleared ({n_stop} STOPPED anyway).")
    if result["verdict"] == "NO-DATA":
        return (f"7-DAY BOUNCE STOP: 0 PASS, 0 STOP, 0 BLIND - no mailbox "
                f"sent for us in {days}d across "
                f"{len(result['campaigns'])} campaigns read whole, so every "
                f"rate is UNDEFINED and UNDEFINED is not a pass.")
    return (f"7-DAY BOUNCE STOP: {n_pass} mailbox(es) PASS under "
            f"{THRESHOLD}% over {days}d, 0 STOPPED, 0 BLIND - all "
            f"{len(result['campaigns'])} campaigns read whole.")


def run(days=7, campaigns=None, rows_source=None):
    """The whole check as one dict. The only thing `main` adds is printing."""
    campaigns = OURS if campaigns is None else campaigns
    since, per, unreadable, unattributed = measure(days, campaigns,
                                                   rows_source)
    mailboxes, roster_complete = verdicts(per, unreadable, unattributed)
    seen = {e["verdict"] for e in mailboxes.values()}
    if "STOP" in seen:
        verdict, code = "STOP", EXIT_STOP
    elif "BLIND" in seen or not roster_complete:
        verdict, code = "BLIND", EXIT_BLIND
    elif mailboxes:
        verdict, code = "CLEAR", EXIT_CLEAR
    else:
        verdict, code = "NO-DATA", EXIT_CLEAR
    result = {"since": since.isoformat(), "days": days,
              "threshold": THRESHOLD, "campaigns": list(campaigns),
              "mailboxes": mailboxes, "unreadable": unreadable,
              "unattributed": unattributed,
              "roster_complete": roster_complete,
              "verdict": verdict, "exit_code": code}
    result["summary"] = _summary(result)
    return result


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    load_env()
    result = run(args.days, OURS)

    if args.json:
        print(json.dumps(result, indent=1, default=str))
        return result["exit_code"]

    since = result["since"]
    print(f"\n7-DAY BOUNCE STOP  since {since}  threshold {THRESHOLD}%")
    print(f"  source: per-message queue rows of campaigns "
          f"{', '.join(str(c) for c in result['campaigns'])}, "
          f"walked to {QUEUE_PAGE_CAP} pages\n")
    for entry in result["unreadable"]:
        # BLIND IS REPORTED, NEVER SKIPPED. A campaign we could not read is
        # not a campaign with no bounces.
        print(f"  BLIND on campaign {entry['campaign']} - NOT proven clean - "
              f"{entry['error']}: {entry['detail'][:140]}")
    if result["unattributed"]:
        print(f"  BLIND: {result['unattributed']} in-window send(s) carry no "
              f"mailbox id, so no rate has a complete denominator")
    if result["unreadable"] or result["unattributed"]:
        print()
    for sid, e in result["mailboxes"].items():
        rate = "UNDEFINED" if e["rate"] is None else f"{e['rate']:.2f}%"
        print(f"  {e['verdict']:<5} mailbox {sid:<6} sent {e['sent']:>4}  "
              f"bounced {e['bounced']:>3}  rate {rate:>9}  "
              f"campaigns {e['campaigns']}")
        if e["verdict"] == "BLIND":
            print(f"        why: {e['reason']}")
    if not result["mailboxes"]:
        print("  No mailbox has a 7-day rate. UNDEFINED is not 0% and it is "
              "not a pass.")
    print(f"\n  {result['summary']}")
    print(f"  verdict {result['verdict']}  exit {result['exit_code']}")
    return result["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
