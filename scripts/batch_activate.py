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

    every named mailbox's bounce rate       against the 2% line, and a
                                            mailbox the stop CANNOT JUDGE
                                            is UNKNOWN, which blocks the
                                            send exactly as a failure does
                                            (TASK 0398). There is no flag
                                            that turns UNKNOWN into a pass.
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
import collections
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import (campaigns, haltfile, killswitch,             # noqa: E402
                 providerwrites, providers, store)
from src.providers import bison, load_env                        # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PREFIX = "productive-email-batch1-"
BOUNCE_HARD_STOP = 0.02
# The workspace the killswitch is asked about below. Not a knob: pointing
# it at a workspace that reads "on" needs a new operator authorization.
WORKSPACE = "productive"

# THE THREE VERDICTS, AND WHY THE THIRD HAD TO BE ADDED. TASK 0398.
#
# This stop used to have two answers and a third meaning crammed into
# `None`: `mailbox_health` returned `None` for the rate whenever `sent` was
# zero, `check` asked only `rate is not None and rate >= BOUNCE_HARD_STOP`,
# and a seat absent from the provider read defaulted to `(None, 0, 0)`. So a
# mailbox the stop COULD NOT JUDGE appended no reason, and the campaign
# printed `ready` - indistinguishable from a mailbox judged clean. Measured
# on 2026-10-16, six of seven reachable cases printed `ready`, including a
# mailbox carrying 9 bounces against 0 sends.
#
# UNKNOWN is now a verdict of its own and it BLOCKS. A mailbox we cannot
# judge is not a mailbox we judged clean, and that is invariant 0 applied to
# one inbox: an unreadable authority is UNKNOWN, and UNKNOWN never becomes
# PASS, zero, idle, complete or safe.
HEALTHY = "healthy"
FAILING = "failing"
UNKNOWN = "unknown"


class MailboxVerdict(collections.namedtuple(
        "MailboxVerdict", "verdict rate sent bounced why")):
    """One mailbox's bounce verdict, carrying the reason it reached it.

    A namedtuple rather than a bool-with-a-third-value, because a boolean
    with a third meaning crammed in is the same defect one layer out: the
    caller asks `verdict.blocks` and can still tell FAILING from
    cannot-judge when it prints the reason.
    """

    __slots__ = ()

    @property
    def blocks(self):
        """Only HEALTHY passes. FAILING and UNKNOWN both block the send."""
        return self.verdict != HEALTHY


def classify(sent, bounced, seat="?", seen=True):
    """HEALTHY / FAILING / UNKNOWN for one mailbox. Pure, no provider.

    `seen=False` is the seat that was never in the provider's read at all,
    which is a different ignorance from a seat that is there with no sends -
    both UNKNOWN, both blocking, and the reasons say which.
    """
    if not seen:
        return MailboxVerdict(
            UNKNOWN, None, None, None,
            f"mailbox {seat} is not in the provider's sender read, so its "
            f"bounce rate cannot be asked at all - UNKNOWN is not a pass")
    sent, bounced = int(sent or 0), int(bounced or 0)
    if sent <= 0:
        return MailboxVerdict(
            UNKNOWN, None, sent, bounced,
            f"mailbox {seat} carries {bounced} bounces against {sent} sends, "
            f"so it has no bounce rate - UNDEFINED is not 0%, and "
            f"UNKNOWN is not a pass")
    rate = bounced / sent
    if rate >= BOUNCE_HARD_STOP:
        return MailboxVerdict(
            FAILING, rate, sent, bounced,
            f"mailbox {seat} is at {rate * 100:.2f}% bounce "
            f"({bounced} of {sent}), at or over the 2% stop")
    return MailboxVerdict(
        HEALTHY, rate, sent, bounced,
        f"mailbox {seat} is at {rate * 100:.2f}% bounce "
        f"({bounced} of {sent}), under the 2% stop")


def mailbox_health():
    """provider_account_id -> MailboxVerdict, from the provider.

    A seat MISSING from the answer is not healthy - `check` classifies it
    UNKNOWN. That is why this returns no default and why nothing here
    substitutes a zero for a read it did not get.
    """
    out = {}
    rows = bison.sender_emails()
    # `sender_emails` returns (rows, total) like every other paged reader on
    # this adapter. Iterating the tuple walks a list and an int.
    if isinstance(rows, tuple):
        rows = rows[0]
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        seat = str(row.get("id"))
        out[seat] = classify(row.get("emails_sent_count"),
                             row.get("bounced_count"), seat=seat)
    return out


def seats_of(row):
    """The mailbox ids this campaign would send from, and the unnameable.

    `bisonfactory.attach_senders` reads the same field and falls back to a
    bare value, so this does too. A sender entry carrying no id at all is
    counted rather than skipped: a seat we cannot NAME is a seat whose
    bounce rate we cannot ask, which is UNKNOWN and blocks. Before TASK
    0398 these became the literal string `"None"`, which is in no provider
    read and therefore passed - the shape every existing test of this
    script drives it with.
    """
    named, unnameable = [], 0
    for sender in (row.get("senders") or {}).get("email") or []:
        ident = (sender.get("provider_account_id")
                 if isinstance(sender, dict) else sender)
        if ident in (None, ""):
            unnameable += 1
            continue
        named.append(str(ident))
    return named, unnameable


def check(row, health):
    """Every hard stop that can be read before the write.

    Returns `(reasons, unknowns, campaign, named)`. The two lists are kept
    APART on purpose: both block, and a reader has to be able to tell a
    mailbox that failed the stop from one the stop could not judge. A
    caller that concatenates them is still fail-closed; one that drops
    `unknowns` has rebuilt the defect.
    """
    reasons, unknowns = [], []
    provider_id = row.get("bison_campaign_id")
    named, unnameable = seats_of(row)
    if unnameable:
        unknowns.append(
            f"{unnameable} of this campaign's email senders carry no "
            f"provider_account_id, so their bounce rate cannot be asked - "
            f"UNKNOWN is not a pass")
    if not named and not unnameable:
        unknowns.append(
            "this campaign names no email sender, so there is no mailbox "
            "whose bounce rate could be checked, and the inbox it would "
            "actually send from is UNKNOWN - which is not a pass")
    for seat in named:
        verdict = health.get(seat) or classify(0, 0, seat=seat, seen=False)
        if verdict.verdict == FAILING:
            reasons.append(verdict.why)
        elif verdict.blocks:
            unknowns.append(verdict.why)
    campaign = bison.campaign(provider_id) or {}
    for field in ("bounced", "unsubscribed"):
        value = int(campaign.get(field) or 0)
        if value and not int(campaign.get("emails_sent") or 0):
            reasons.append(f"campaign reports {field}={value} while "
                           f"emails_sent=0, which is a contradiction")
    return reasons, unknowns, campaign, named


def gated_resume(provider_id, campaign_id, leads, tenant=None):
    """The two gates that already exist, before the verb. TASK 0200.

    TASK-331's suppression revalidation first, then the killswitch. In
    that order on purpose: the freeze refuses everything today, and a
    killswitch consulted first would mask the per-contact reason - the
    operator would read a workspace verdict where a named lead stopped
    the resume. A refusal raises and is printed by the caller, counted
    and named per campaign, never silently dropped. No third gate is
    built here: this is the same CONDITIONAL entry `perform` runs.
    """
    revalidate = providerwrites.CONDITIONAL[providerwrites.EMAIL_RESUME]
    revalidate(provider_id, campaign_id)
    killswitch.require(workspace=WORKSPACE)
    haltfile.require_released()
    # TASK 0395: AND THROUGH THE DOOR, which is the guard the three
    # lines above are not. The brake stays here, ahead of it, because
    # an early consult refuses before anything is minted - but it is
    # not the consult that matters: `perform` pulls the brake again at
    # its step 2c, one statement before the transport, and that is the
    # only one that closes the window on a brake pulled while a write
    # is already in flight. Same route as the orchestrator's own resume
    # (src/orchestrator.py, `_resume_at_providers`), so ownership
    # default-refuse, the write ledger and the read-back classification
    # apply here too. `expect_leads` is still the count read from the
    # provider, so a cohort that changed under us refuses.
    return providerwrites.perform(
        providerwrites.EMAIL_RESUME,
        gate=providerwrites.grant(
            providerwrites.EMAIL_RESUME, by="scripts/batch_activate.py",
            why=("activating %s per OPERATOR AUTHORIZATION 2026-09-22, "
                 "docs/OPERATOR-AUTHORIZATION-2026-09-22-ACTIVATE-AND-"
                 "NOTELESS.md" % campaign_id)),
        campaign=str(campaign_id), tenant=tenant,
        provider_campaign_id=provider_id,
        payload={"campaign_id": provider_id},
        transport=lambda _p, pid=provider_id, n=leads:
            bison.resume_campaign(pid, expect_leads=n),
        readback=lambda pid=provider_id:
            {"status": (bison.campaign(pid) or {}).get("status")},
        expected={"status": "running"}, by="scripts/batch_activate.py")


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
    judged = collections.Counter(v.verdict for v in health.values())
    print(f"\nACTIVATE  campaigns {len(rows)}  "
          f"mailboxes in the provider read {len(health)}  "
          f"(healthy {judged[HEALTHY]}  failing {judged[FAILING]}  "
          f"unjudgeable {judged[UNKNOWN]})\n")

    ready, halted, unjudgeable = [], [], []
    for row in sorted(rows, key=lambda r: r.get("bison_campaign_id") or 0):
        reasons, unknowns, campaign, named = check(row, health)
        leads = int(campaign.get("total_leads") or 0)
        status = campaign.get("status")
        line = (f"  {row['bison_campaign_id']} "
                f"{row['campaign_id'].rsplit('-', 1)[-1]:10s} "
                f"{str(status):8s} leads {leads:>4}  mailboxes {len(named):>3}")
        if reasons or unknowns:
            # BOTH BLOCK, AND THE THREE STATES STAY DISTINGUISHABLE HERE.
            # A campaign stopped because a mailbox is bouncing and one
            # stopped because no mailbox could be judged are different
            # facts about the estate and print differently; neither is
            # ready.
            halted.append((row, reasons + unknowns))
            if unknowns:
                unjudgeable.append(row)
            print(line + ("  HALTED" if reasons
                          else "  HALTED: UNKNOWN, not clean"))
            for reason in reasons + unknowns:
                print(f"       {reason}")
            continue
        if not leads:
            print(line + "  SKIPPED: holds nobody")
            continue
        ready.append((row, campaign, leads))
        print(line + "  ready")

    print(f"\n  ready {len(ready)}  halted {len(halted)}"
          f"  of which unjudgeable {len(unjudgeable)}")
    if not args.live:
        print("\n  PLAN ONLY. Nothing was activated.")
        return 0
    if halted:
        print("\n  REFUSED: a hard stop is open. Condition 8 halts the push, "
              "and it halts all of it - a batch is not part-activated.")
        if unjudgeable:
            print(f"  {len(unjudgeable)} of those is UNKNOWN rather than "
                  "failing: the stop could not judge a mailbox it would have "
                  "sent from. That blocks the send. It is not a warning and "
                  "there is no flag that turns it into a pass - the fix is "
                  "to make the mailbox readable, not to proceed.")
        return 1

    done = []
    with providers.allow_writes(
            "activate 491-498 - OPERATOR AUTHORIZATION 2026-09-22, "
            "docs/OPERATOR-AUTHORIZATION-2026-09-22-ACTIVATE-AND-NOTELESS.md"):
        for row, campaign, leads in ready:
            provider_id = row["bison_campaign_id"]
            try:
                gated_resume(provider_id, row.get("campaign_id"), leads,
                             row.get("client"))
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
