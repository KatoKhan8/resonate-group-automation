#!/usr/bin/env python3
"""The Monday weekly report: 07:30 preview with a stop, 08:00 to the client.

    py -3 -u scripts/weekly_report_loop.py --interval 300
    py -3 scripts/weekly_report_loop.py --once --dry-run   # decide only
    py -3 scripts/weekly_report_loop.py --status           # what it would do

OPERATOR, 2026-09-23, the second increment: "Monday 08:00 local schedule,
07:30 preview in #resonate-os with a stop, PDF via clientreport from the
report's data dict under the new vocabulary."

## WHY A LOOP AND NOT A CALLER SOMEWHERE

`digest_loop.py` exists because `digestwatch` and `digest.announce` were both
written, both tested, and **called by nothing** - measured 2026-09-21, and
the absence would have looked like a quiet night rather than a missing
process. `slackfollowup.due()` shipped the same way. This is the third time,
so the loop is written in the same commit as the module rather than after it.

The agent loop cannot do this work: it blocks in `socketmode.envelopes`
waiting for a mention, and a schedule that fires only when somebody happens
to speak is not a schedule.

## THE STOP IS A HALF HOUR AND THIS PROCESS DOES NOT SHORTEN IT

At 07:30 the preview goes to #resonate-os. At 08:00 the report goes to the
client channel unless a person stopped it. **A tick that first runs after
08:00 does not post** - `weeklyreportwatch.decide` returns MISSED_PREVIEW,
because nobody had the window in which to stop it and an unreviewed client
document is the thing the window exists to prevent. Late is not the same as
approved.

## THE PDF IS BUILT AND WRITTEN, NOT UPLOADED, AND THAT IS A GAP

`src/providers/slack.py` has `post()` and **no file-upload route**. So this
writes the PDF to `work/reports/` and the message names it. Uploading it to
Slack needs a new route in a provider module, which is production's to add;
until it does, a person attaches the file. This is said out loud in the
preview text rather than left for somebody to discover on a Monday.

## IT CONFIRMS THE CHANNEL BEFORE IT POSTS

Between one Monday and the next an operator can rebind a channel. Posting a
client's account figures into a channel that now belongs to somebody else is
a cross-client leak arriving a week late, so the binding is resolved at post
time and a workspace whose channel no longer resolves to it is skipped,
loudly. `slack_followup_loop.py` makes the same check for the same reason.
"""
import argparse
import datetime
import json
import os
import sys
import time
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import (slackscope, watchsink, weeklyreportpdf,         # noqa: E402
                 weeklyreportwatch as watch)
from src.providers import load_env, slack                        # noqa: E402

WATCHER = "weekly-report"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPORT_DIR = os.path.join(ROOT, "work", "reports")


def emit(text):
    sys.stdout.write("%s %s\n" % (datetime.datetime.now(
        tz=datetime.timezone.utc).strftime("%H:%M:%S"), text))
    sys.stdout.flush()


def _report_for(slug):
    """`weekly_report` for one workspace, through the agent's own tools.

    The same function the Slack answer is written from, so the PDF and the
    post cannot disagree. Imported late: `slackagenttools` pulls in the
    provider readbacks, and a --status run should not need them to answer.
    """
    from src import slackagenttools as tools

    # An INTERNAL scope, not a client one. `weekly_report` is scoped by its
    # argument and `_workspace_for` pins a client channel to its own
    # workspace; internal is the scope this loop actually has, and passing
    # the slug explicitly is how the internal caller names which client.
    scope = slackscope.Scope(slackscope.INTERNAL, source="weekly_report_loop")
    return tools.weekly_report(scope, slug)


def _write_pdf(slug, name, report, monday):
    os.makedirs(REPORT_DIR, exist_ok=True)
    raw = weeklyreportpdf.build(report, name)
    target = os.path.join(REPORT_DIR, "weekly-%s-%s.pdf" % (slug, monday))
    with open(target, "wb") as handle:
        handle.write(raw)
    return target, len(raw)


def _preview_text(slug, monday, report, pdf_path, closes_at):
    accounts = report.get("accounts") or {}
    lines = [
        "*Weekly report preview - %s, week of %s*" % (slug, monday),
        "This goes to the client channel at 08:00 local. "
        "*Reply `stop %s` before then to hold it.*" % slug,
        "",
        "Accounts: untouched %s / sequenced %s / engaged %s / replied %s / "
        "meeting %s / won %s / lost %s / do-not-contact %s"
        % tuple(accounts.get(k, 0) for k in
                ("untouched", "sequenced", "engaged", "replied",
                 "meeting", "won", "lost", "do_not_contact")),
    ]
    if accounts.get("unanswerable"):
        lines.append(
            ":warning: %d account(s) *cannot be placed* - the ledger is not "
            "recording this workspace's sends. That is not a count of "
            "untouched accounts." % accounts["unanswerable"])
    if report.get("replies_error"):
        lines.append(":warning: the reply ledger could not be read: %s"
                     % report["replies_error"])
    if report.get("emails_error"):
        lines.append(":warning: the email figures failed: %s"
                     % report["emails_error"])
    lines += [
        "",
        "PDF written to `%s`." % pdf_path,
        "_Slack has no upload route in this codebase yet, so the file is on "
        "disk and a person attaches it._",
        "Stop window closes %s." % closes_at,
    ]
    return "\n".join(lines)


def _channel_for(slug):
    """The client channel this workspace is bound to, RESOLVED NOW.

    `client_channels()` is `{channel: slug}` and it drops a channel bound to
    two workspaces entirely - an ambiguous binding is not a binding. Walking
    it backwards means a workspace that has been unbound, rebound or made
    ambiguous since the preview resolves to nothing, and nothing is posted.
    """
    bound = [channel for channel, owner
             in slackscope.client_channels().items() if owner == slug]
    return bound[0] if len(bound) == 1 else None


def tick(now=None, dry_run=False, only=None):
    """One pass over every bound workspace."""
    slugs = [s for s in sorted(set(slackscope.client_channels().values()))
             if only is None or s == only]
    done = []
    for slug in slugs:
        decision = watch.decide(slug, now=now)
        outcome = decision["outcome"]
        if outcome in (watch.WAITING, watch.ALREADY, watch.STOPPED):
            emit("%-12s %-14s %s" % (slug, outcome, decision["why"]))
            done.append(decision)
            continue
        if outcome == watch.MISSED_PREVIEW:
            # LOUD. A missed Monday is a fault in this loop's uptime, and
            # reporting it quietly is how a client stops getting a document
            # nobody notices stopped arriving.
            emit("%-12s MISSED-PREVIEW %s" % (slug, decision["why"]))
            done.append(decision)
            continue

        monday = decision["monday"]
        try:
            report = _report_for(slug)
        except Exception as exc:                                # noqa: BLE001
            emit("%-12s REPORT-FAILED %s: %s"
                 % (slug, type(exc).__name__, str(exc)[:200]))
            decision["outcome"] = watch.FAILED
            done.append(decision)
            continue

        name = slug
        try:
            pdf_path, size = _write_pdf(slug, name, report, monday)
        except Exception as exc:                                # noqa: BLE001
            emit("%-12s PDF-FAILED %s: %s"
                 % (slug, type(exc).__name__, str(exc)[:200]))
            decision["outcome"] = watch.FAILED
            done.append(decision)
            continue

        if outcome == watch.PREVIEWED:
            text = _preview_text(slug, monday, report, pdf_path,
                                 decision["post_at"])
            channel = watch.PREVIEW_CHANNEL
        else:
            channel = _channel_for(slug)
            if not channel:
                emit("%-12s NO-CHANNEL refusing to post; %s resolves to no "
                     "bound client channel" % (slug, slug))
                decision["outcome"] = watch.FAILED
                done.append(decision)
                continue
            text = ("*Weekly report - week of %s*\nPDF: `%s` (%d bytes)"
                    % (monday, pdf_path, size))

        if dry_run:
            emit("DRY-RUN %-12s %s -> %s" % (slug, outcome, channel))
            emit(text)
            done.append(decision)
            continue

        try:
            slack.post({"kind": "weekly_report", "channel": channel,
                        "text": text})
        except Exception as exc:                                # noqa: BLE001
            # NOT RECORDED. The state only advances on a post that happened,
            # so the next tick tries again inside the same window.
            emit("%-12s POST-FAILED %s %s: %s"
                 % (slug, channel, type(exc).__name__, str(exc)[:200]))
            decision["outcome"] = watch.FAILED
            done.append(decision)
            continue

        if outcome == watch.PREVIEWED:
            watch.record_preview(slug, monday, detail={"pdf": pdf_path})
            emit("%-12s PREVIEWED -> %s (stop window to %s)"
                 % (slug, channel, decision["post_at"]))
        else:
            watch.record_delivery(slug, monday,
                                  detail={"pdf": pdf_path,
                                          "channel": channel})
            emit("%-12s DELIVERED -> %s" % (slug, channel))
        done.append(decision)
    return done


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--interval", type=int, default=300)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--workspace", default=None)
    args = parser.parse_args(argv)

    load_env()

    if args.status:
        slugs = sorted(set(slackscope.client_channels().values()))
        print(json.dumps(watch.status(slugs), indent=2, sort_keys=True))
        return 0

    while True:
        try:
            tick(dry_run=args.dry_run, only=args.workspace)
            watchsink.beat(WATCHER, {"zone": watch.TIMEZONE,
                                     "zone_resolved": watch.zone_is_real()})
        except Exception:                                       # noqa: BLE001
            traceback.print_exc()
        if args.once:
            return 0
        time.sleep(max(30, args.interval))


if __name__ == "__main__":
    raise SystemExit(main())
