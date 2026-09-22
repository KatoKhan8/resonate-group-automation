#!/usr/bin/env python3
"""The change-request queue. Run this from the MAIN session.

    py -3 scripts/slack_requests.py                     # everything, briefly
    py -3 scripts/slack_requests.py --approved          # what to execute now
    py -3 scripts/slack_requests.py --show <id>         # one ticket in full
    py -3 scripts/slack_requests.py --done <id> --note "what happened"
    py -3 scripts/slack_requests.py --failed <id> --note "why it did not"

OPERATOR, 2026-09-21: "On approval, hand the ticket to the main session's
request queue; report the outcome back in the original thread."

## THIS IS THE HANDOFF, AND IT IS DELIBERATELY A PULL

There was no request queue to hand anything to, so this is it. The Slack
agent writes tickets and never executes one; the main session runs
`--approved`, does the work through the gates that already exist, and writes
the outcome back with `--done` or `--failed`. The agent reads that and
reports it in the thread the request came from.

A PULL rather than a push, because the alternative is the agent trying to
make another session act - and an agent that can make a privileged session
act has the privilege, whatever the diagram says.

## `--done` DOES NOT MEAN "I RAN SOMETHING"

It means the change is confirmed against the thing that holds the truth: a
provider readback for a stop or a pause, the suppression list for a
removal, the approval fingerprint for copy. This repository's register
exists because `active`, `in_sequence` and `scheduled` were each read as a
send at some point. Write what was VERIFIED into `--note`, because the
requester is going to read it.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import slackrequests as requests                       # noqa: E402
from src.providers import load_env                              # noqa: E402


def _line(ticket):
    fields = ticket.get("fields") or {}
    target = (fields.get("lead") or fields.get("account")
              or fields.get("campaign") or fields.get("cadence_or_campaign")
              or fields.get("window") or "?")
    return "%-18s %-16s %-22s %-26s %s" % (
        ticket.get("id"), ticket.get("status"), ticket.get("kind"),
        str(ticket.get("workspace"))[:26], target)


def show_all(status=None):
    rows = requests.load()
    if status:
        rows = [r for r in rows if r.get("status") == status]
    if not rows:
        print("no change requests%s." % (" with status %s" % status
                                         if status else ""))
        return 0
    print("%-18s %-16s %-22s %-26s %s"
          % ("ID", "STATUS", "KIND", "WORKSPACE", "TARGET"))
    for ticket in rows:
        print(_line(ticket))
    awaiting = len([r for r in requests.load()
                    if r.get("status") == requests.AWAITING])
    approved = len(requests.approved_unexecuted())
    print()
    print("%d awaiting the operator, %d approved and not yet executed."
          % (awaiting, approved))
    if approved:
        print("Run --show <id> for the full ticket, then --done or --failed.")
    return 0


def show(ticket_id):
    ticket = requests.get(ticket_id)
    if ticket is None:
        print("no change request %r" % ticket_id)
        return 1
    print(requests.render(ticket))
    path = requests.path_for(ticket)
    print("file: %s%s" % (path, "" if os.path.isfile(path)
                          else "   [MISSING - the journal has it, the "
                               "markdown does not]"))
    return 0


def finish(ticket_id, note, status):
    ticket = requests.get(ticket_id)
    if ticket is None:
        print("no change request %r" % ticket_id)
        return 1
    if ticket.get("status") != requests.APPROVED:
        print("REFUSED: %s is %s, not approved. Only an approved request "
              "can be executed, and marking an unapproved one done would "
              "record a decision nobody made."
              % (ticket_id, ticket.get("status")))
        return 1
    if not note:
        print("REFUSED: --note is required. The requester reads it, and "
              "\"done\" with no evidence is the claim this repository's "
              "register exists to stop.")
        return 1
    updated = requests.record_outcome(ticket_id, note, status=status)
    print("%s is now %s." % (ticket_id, updated["status"]))
    print()
    print("The agent reports this in the original thread on its next pass:")
    print("  %s" % requests.decision_note_for(updated))
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--approved", action="store_true",
                        help="only what is approved and not yet executed")
    parser.add_argument("--pending", action="store_true",
                        help="only what is waiting on the operator")
    parser.add_argument("--show", metavar="ID")
    parser.add_argument("--done", metavar="ID")
    parser.add_argument("--failed", metavar="ID")
    parser.add_argument("--note", help="what was verified, in one sentence")
    args = parser.parse_args(argv)
    load_env()

    if args.show:
        return show(args.show)
    if args.done:
        return finish(args.done, args.note, requests.EXECUTED)
    if args.failed:
        return finish(args.failed, args.note, requests.FAILED)
    if args.approved:
        return show_all(requests.APPROVED)
    if args.pending:
        return show_all(requests.AWAITING)
    return show_all()


if __name__ == "__main__":
    raise SystemExit(main())
