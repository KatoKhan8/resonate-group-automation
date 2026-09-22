#!/usr/bin/env python3
"""Activate the batch campaigns, after the hard stops, with a readback each.

    py -3 scripts/batch_activate.py --plan
    py -3 scripts/batch_activate.py --live

OPERATOR AUTHORIZATION, 2026-09-22: "activate 491-498 and allow the note-less
connection request". Recorded in
`docs/OPERATOR-AUTHORIZATION-2026-09-22-ACTIVATE-AND-NOTELESS.md`.

**THIS IS THE VERB THAT MAKES A CAMPAIGN SEND.** Everything before it built
something that could be stopped by deleting a row. After it, real people
receive email on the provider's own schedule.

## THE HARD STOPS ARE CHECKED BEFORE THE WRITE

Condition 8 of the batch-1 grant: bounce over 2% on any mailbox over 7 days,
any spam complaint, a reply not stopping the other channel, an unsubscribe
not propagated, verification weakened, credit cap reached. Any one halts.

Checked here, from the provider, immediately before activating:

    every named mailbox's bounce rate       against the 2% line
    the campaign's own counters             bounced / unsubscribed non-zero
                                            on a campaign that has not sent
                                            is a contradiction worth stopping
    the lead count                          `resume_campaign(expect_leads=N)`
                                            refuses when the provider
                                            disagrees, so N is read first

## RESUME, NOT A NEW VERB

`bison.resume_campaign` is what `EMAIL_ACTIVATE` maps to. It carries the
brake set already: an `expect_leads` count read from the provider that
refuses on disagreement, `queued` polled out rather than reported as started,
and `failed` classified rather than defaulted.
"""
import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import campaigns, providers, store                      # noqa: E402
from src.providers import bison, load_env                        # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PREFIX = "productive-email-batch1-"
BOUNCE_HARD_STOP = 0.02


def mailbox_health():
    """provider_account_id -> (rate, sent, bounced), from the provider."""
    out = {}
    rows = bison.sender_emails()
    # `sender_emails` returns (rows, total) like every other paged reader on
    # this adapter. Iterating the tuple walks a list and an int.
    if isinstance(rows, tuple):
        rows = rows[0]
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        sent = int(row.get("emails_sent_count") or 0)
        bounced = int(row.get("bounced_count") or 0)
        out[str(row.get("id"))] = (
            (bounced / sent) if sent else None, sent, bounced)
    return out


def check(row, health):
    """Every hard stop that can be read before the write. Returns reasons."""
    reasons = []
    provider_id = row.get("bison_campaign_id")
    named = [str(s.get("provider_account_id"))
             for s in (row.get("senders") or {}).get("email") or []]
    for seat in named:
        rate, sent, bounced = health.get(seat, (None, 0, 0))
        if rate is not None and rate >= BOUNCE_HARD_STOP:
            reasons.append(f"mailbox {seat} is at {rate * 100:.2f}% bounce "
                           f"({bounced} of {sent}), at or over the 2% stop")
    campaign = bison.campaign(provider_id) or {}
    for field in ("bounced", "unsubscribed"):
        value = int(campaign.get(field) or 0)
        if value and not int(campaign.get("emails_sent") or 0):
            reasons.append(f"campaign reports {field}={value} while "
                           f"emails_sent=0, which is a contradiction")
    return reasons, campaign, named


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--plan", action="store_true")
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--only")
    args = parser.parse_args(argv)

    load_env()
    rows = [r for r in campaigns.load()
            if str(r.get("campaign_id", "")).startswith(PREFIX)]
    if args.only:
        rows = [r for r in rows if r["campaign_id"].endswith(args.only)]
    health = mailbox_health()
    print(f"\nACTIVATE  campaigns {len(rows)}  "
          f"mailboxes readable {len(health)}\n")

    ready, halted = [], []
    for row in sorted(rows, key=lambda r: r.get("bison_campaign_id") or 0):
        reasons, campaign, named = check(row, health)
        leads = int(campaign.get("total_leads") or 0)
        status = campaign.get("status")
        line = (f"  {row['bison_campaign_id']} "
                f"{row['campaign_id'].rsplit('-', 1)[-1]:10s} "
                f"{str(status):8s} leads {leads:>4}  mailboxes {len(named):>3}")
        if reasons:
            halted.append((row, reasons))
            print(line + "  HALTED")
            for reason in reasons:
                print(f"       {reason}")
            continue
        if not leads:
            print(line + "  SKIPPED: holds nobody")
            continue
        ready.append((row, campaign, leads))
        print(line + "  ready")

    print(f"\n  ready {len(ready)}  halted {len(halted)}")
    if not args.live:
        print("\n  PLAN ONLY. Nothing was activated.")
        return 0
    if halted:
        print("\n  REFUSED: a hard stop is open. Condition 8 halts the push, "
              "and it halts all of it - a batch is not part-activated.")
        return 1

    done = []
    with providers.allow_writes(
            "activate 491-498 - OPERATOR AUTHORIZATION 2026-09-22, "
            "docs/OPERATOR-AUTHORIZATION-2026-09-22-ACTIVATE-AND-NOTELESS.md"):
        for row, campaign, leads in ready:
            provider_id = row["bison_campaign_id"]
            try:
                bison.resume_campaign(provider_id, expect_leads=leads)
            except Exception as exc:                            # noqa: BLE001
                print(f"  {provider_id}: REFUSED {type(exc).__name__}: "
                      f"{str(exc)[:170]}")
                continue
            done.append(provider_id)
            print(f"  {provider_id}: activated, {leads} leads")
            time.sleep(0.5)

    print("\nREADBACK, from the provider\n")
    report = []
    for provider_id in done:
        after = bison.campaign(provider_id) or {}
        try:
            queue = bison.scheduled_emails(provider_id) or []
        except Exception:                                       # noqa: BLE001
            queue = []
        dates = sorted(str(r.get("scheduled_date") or "") for r in queue
                       if r.get("scheduled_date"))
        sent = [r for r in queue
                if str(r.get("status") or "").lower() in ("sent", "delivered")
                or r.get("sent_at")]
        report.append({"campaign": provider_id, "status": after.get("status"),
                       "leads": after.get("total_leads"),
                       "queue_rows": len(queue), "sent_rows": len(sent),
                       "first_scheduled": dates[0] if dates else None})
        print(f"  {provider_id}  status {str(after.get('status')):8s} "
              f"leads {after.get('total_leads'):>4}  queue {len(queue):>4}  "
              f"sent {len(sent):>3}  first "
              f"{dates[0] if dates else 'not planned yet'}")

    out = os.path.join(ROOT, "work", "batch-activation-report.json")
    with open(out, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=1)
    print(f"\n  activated {len(done)} of {len(ready)}")
    print(f"  report written to {out}")
    print("\n  ACTIVE IS NOT SENT EITHER. The provider plans at the end of "
          "its sending day; 489 re-planned itself three days early once. A "
          "queue row is the first witness and `sent` on that row is the "
          "second.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
