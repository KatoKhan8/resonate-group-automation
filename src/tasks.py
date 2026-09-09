#!/usr/bin/env python3
"""The outstanding work in one workspace, assembled rather than stored.

## Why this holds no state

Every task here is already true somewhere else. A campaign waiting for
approval is a campaign whose status is `awaiting_approval`; a person back
from leave is an `out_of_office_recorded` event whose date has passed; a
failing poller is `replywatch` status. None of it is new information, and
storing it again would be a second representation of the same fact.

That matters more than it sounds. A stored task carries a status somebody
has to keep in step - and the moment it drifts, the queue says "handled"
about a campaign that is still sitting at `awaiting_approval`, or keeps
demanding attention for a job that was re-run an hour ago. The failure is
silent in both directions and there is no way to tell which side is wrong.

So a task exists exactly while its condition is true, and it is resolved by
fixing the thing, not by ticking it off. That is also the honest answer to
"is this done": the queue cannot say yes while the work is outstanding.

## No assignee

There is no canonical owner for anything in this system. Adding one here
would invent a concept the rest of the build has no opinion about, and
"assigned to" that nothing enforces is worse than nobody's name at all.
Workspace membership already says who *may* act.

## One task, or a population

Some work is an object: approve this campaign, re-run this job, decide
about this person who is back from leave. Some is a condition over many
records: eleven addresses are waiting for a second verifier. Both belong in
the same list - an operator's morning contains both - but they are not the
same shape, so a task says which it is rather than pretending a population
is one clickable thing.

## What reads this

`web/api.dashboard` groups it into the attention section; `/tasks` lists it
in full. One place decides what counts as outstanding work, so the screen
and the summary cannot disagree about how much there is.
"""
import argparse
import json

from . import (campaigns as campaign_store, clients, events, jobs,
               notify, oooreturn, replywatch, store, verification)

# What kind of work this is. The vocabulary an operator sees.
CAMPAIGN_APPROVAL = "campaign_approval"
CAMPAIGN_REVIEW = "campaign_review"
OOO_RETURN = "ooo_return"
NOT_NOW_RETURN = "not_now_return"
REVIEW_REFERRAL = "review_referral"
REPLY_PROTECTION = "reply_protection"
FAILED_JOB = "failed_job"
VERIFICATION_DISAGREEMENT = "verification_disagreement"
VERIFICATION_PENDING = "verification_pending"

KINDS = (REPLY_PROTECTION, CAMPAIGN_APPROVAL, CAMPAIGN_REVIEW, OOO_RETURN,
         NOT_NOW_RETURN, REVIEW_REFERRAL, FAILED_JOB,
         VERIFICATION_DISAGREEMENT, VERIFICATION_PENDING)

LABEL = {
    REPLY_PROTECTION: "Reply protection is not running",
    CAMPAIGN_APPROVAL: "Campaign waiting for approval",
    CAMPAIGN_REVIEW: "Campaign ready to review",
    OOO_RETURN: "Back from leave",
    NOT_NOW_RETURN: "Asked us to come back now",
    REVIEW_REFERRAL: "Somebody was referred to us",
    FAILED_JOB: "Batch job failed",
    VERIFICATION_DISAGREEMENT: "Verifiers disagree",
    VERIFICATION_PENDING: "Waiting for a second opinion",
}

# Severity is `notify`'s, so one thing is never CRITICAL in Slack and
# something else on a screen.
SEVERITY = {
    REPLY_PROTECTION: notify.CRITICAL,
    CAMPAIGN_APPROVAL: notify.ACTION_REQUIRED,
    CAMPAIGN_REVIEW: notify.ACTION_REQUIRED,
    OOO_RETURN: notify.ACTION_REQUIRED,
    NOT_NOW_RETURN: notify.ACTION_REQUIRED,
    REVIEW_REFERRAL: notify.ACTION_REQUIRED,
    FAILED_JOB: notify.ACTION_REQUIRED,
    VERIFICATION_DISAGREEMENT: notify.WARNING,
    VERIFICATION_PENDING: notify.WARNING,
}

ORDER = {notify.CRITICAL: 0, notify.ACTION_REQUIRED: 1, notify.WARNING: 2,
         notify.INFO: 3}

# An object task points at one thing. A population task is a condition over
# many records, and says so rather than pretending to be clickable.
POPULATION = "population"


def task(kind, workspace, why, where, object_type=None, object_id=None,
         title=None, count=1, due=None):
    return {"kind": kind, "severity": SEVERITY[kind], "workspace": workspace,
            # The label travels with the task so `web/pages` can render it
            # without importing this module. That file imports nothing from
            # the domain and is worth keeping that way.
            "kind_label": LABEL[kind],
            "title": title or LABEL[kind], "why": why, "where": where,
            "object_type": object_type, "object_id": object_id,
            "count": count, "due": due}


def order(rows):
    """Severity first, then whatever is due soonest, then the bigger number."""
    return sorted(rows, key=lambda row: (ORDER.get(row["severity"], 9),
                                         str(row.get("due") or "9999"),
                                         -row["count"]))


def collect(workspace, recs=None, config=None, campaigns=None, today=None,
            verification_counts=None):
    """Everything outstanding in this workspace, most urgent first.

    `recs` and `campaigns` are passed in where the caller already has them -
    the dashboard has both, and loading the estate twice to decorate one
    page is a poor trade. Everything else is cheap enough to read here.
    """
    recs = store.load() if recs is None else recs
    if workspace:
        recs = [r for r in recs if r.get("client") == workspace]
    if config is None and workspace:
        try:
            config = clients.load(workspace)
        except Exception:                                 # noqa: BLE001
            config = None
    if campaigns is None:
        campaigns = [c for c in campaign_store.load()
                     if not workspace or c.get("client") == workspace]

    rows = []
    rows.extend(_reply_protection(workspace))
    rows.extend(_campaigns(workspace, campaigns))
    rows.extend(_returns(workspace, recs, config, today))
    rows.extend(_referrals(workspace, recs))
    rows.extend(_jobs(workspace))
    rows.extend(_verification(workspace, recs, config, verification_counts))
    return order(rows)


def _reply_protection(workspace):
    for watch in replywatch.problems():
        yield task(
            REPLY_PROTECTION, workspace,
            watch["label"] + ". A cadence step can go out to somebody who "
            "has already replied",
            "/health", object_type="provider", object_id=watch["provider"],
            title=f"{watch['provider']} reply polling")


def _campaigns(workspace, campaigns):
    for campaign in campaigns:
        status = campaign.get("status")
        if status == campaign_store.AWAITING_APPROVAL:
            yield task(CAMPAIGN_APPROVAL, workspace,
                       "nothing goes out until somebody approves it",
                       "/approvals", object_type="campaign",
                       object_id=campaign.get("campaign_id"),
                       title=(campaign.get("name")
                              or campaign.get("campaign_id")))
        elif status == campaign_store.READY_FOR_REVIEW:
            yield task(CAMPAIGN_REVIEW, workspace,
                       "built and waiting for a person to read it",
                       "/campaigns", object_type="campaign",
                       object_id=campaign.get("campaign_id"),
                       title=(campaign.get("name")
                              or campaign.get("campaign_id")))


def _returns(workspace, recs, config, today):
    try:
        rows = oooreturn.candidates(recs, today=today, config=config,
                                    workspace=workspace)
    except Exception:                                     # noqa: BLE001
        return
    for row in rows:
        if row["verdict"] != oooreturn.DUE:
            continue
        # Same machinery, two different things to say. Somebody back from
        # leave and somebody who asked to be approached in November are both
        # due, and telling an operator the wrong one is telling them
        # something untrue about a person.
        away = row.get("source") != events.NOT_NOW_RECORDED
        yield task(
            OOO_RETURN if away else NOT_NOW_RETURN, workspace,
            ("they said they would be back by now" if away else
             "the date they asked to be approached on has arrived")
            + ", and their cadence is still stopped until somebody decides",
            "/replies/returns", object_type="contact",
            object_id=row["contact"], due=row.get("return_date"),
            title=row.get("name") or row["contact"])


def _referrals(workspace, recs):
    """Referrals nobody has read yet.

    An exact match is not work: the reply pointed at somebody already on
    the account, and turning that into a referral edge is a person's
    decision rather than a queue item. Everything else needs somebody - a
    name is not an identity, and a candidate is an invitation to add a
    contact rather than permission to.

    It stops being a task when the reply it came from is marked handled,
    which is the canonical "somebody looked at this" and already lives on
    the receipt. A second flag saying the same thing is how the inbox and
    this queue would start disagreeing about the same reply.
    """
    for rec in recs:
        handled = set()
        for entry in rec.get("events") or []:
            if (entry.get("type") == events.REPLY_RECEIVED
                    and entry.get("handled")):
                handled.add((entry.get("contact"), entry.get("at")))
        for entry in rec.get("events") or []:
            if entry.get("type") != events.REFERRAL_MENTIONED:
                continue
            if not entry.get("needs_a_person"):
                continue
            if (entry.get("contact"), entry.get("at")) in handled:
                continue
            named = entry.get("named") or "somebody unnamed"
            yield task(
                REVIEW_REFERRAL, workspace,
                str(entry.get("reason") or "").strip()
                or "a reply pointed at somebody else",
                # `carries`, not `kind`. The tab filters on what a reply
                # was read as; this filters on what it contains, and a
                # referral inside a polite refusal is classified
                # `negative` - so the tab would open a page without it.
                "/replies?carries=referral", object_type="contact",
                # The referrer, not the person they named. The named one is
                # evidence rather than a contact, so there is nothing else
                # this could point at.
                object_id=entry.get("contact"),
                title=f"{named} at {rec.get('company') or rec.get('id')}")


def _jobs(workspace):
    for job in jobs.for_client(workspace):
        if job.get("status") == jobs.FAILED or (job.get("failed") or 0):
            yield task(
                FAILED_JOB, workspace,
                "jobs resume per record, so re-running skips what already "
                "worked",
                "/jobs", object_type="job", object_id=job.get("id"),
                title=f"{job.get('kind') or 'job'} {job.get('id')}")


def _verification(workspace, recs, config, counts):
    """Two populations rather than one task per address.

    A workspace can hold thousands of contacts waiting for a second
    verifier. Nobody works through those one at a time - the answer is to
    run the waterfall, not to open ten thousand rows - so this reports the
    condition and its size.

    Counted here rather than taken from the dashboard, which keeps a
    similar-looking bucket that means something else: its `single` includes
    addresses no vendor has looked at yet. This row says "one vendor
    passed", so it counts addresses where one vendor passed. A number has
    to mean what its label says, and the two differed by eight in the
    fictional estate - which is how this was found.
    """
    if counts is None:
        counts = {"single": 0, "disagreement": 0}
        policy = verification.policy_for(config)
        for rec in recs:
            for contact in rec.get("contacts") or []:
                if not contact.get("email"):
                    continue
                decision = verification.resolve(contact, policy)
                if decision.get("disagreement"):
                    counts["disagreement"] += 1
                elif (decision["confirmation_count"]
                      < decision["required_confirmations"]
                      and decision["confirmation_count"]):
                    counts["single"] += 1

    if counts.get("disagreement"):
        yield task(VERIFICATION_DISAGREEMENT, workspace,
                   "two vendors gave different answers about the same "
                   "address, and it is held until that is settled",
                   "/contacts", object_type=POPULATION,
                   count=counts["disagreement"])
    if counts.get("single"):
        yield task(VERIFICATION_PENDING, workspace,
                   "one vendor passed. Two independent passes are required "
                   "before an address may be written to",
                   "/contacts", object_type=POPULATION,
                   count=counts["single"])


def summarise(rows):
    """One row per kind, for a screen with no room for the whole list.

    Grouped rather than recounted, so the summary and the list cannot
    disagree about how much work there is.
    """
    grouped = {}
    for row in rows:
        entry = grouped.get(row["kind"])
        if entry is None:
            grouped[row["kind"]] = {
                "kind": row["kind"], "key": row["kind"],
                "severity": row["severity"], "label": LABEL[row["kind"]],
                "count": row["count"], "why": row["why"],
                "where": row["where"]}
        else:
            entry["count"] += row["count"]
    return order(list(grouped.values()))


def counts(rows):
    return {kind: sum(r["count"] for r in rows if r["kind"] == kind)
            for kind in KINDS if any(r["kind"] == kind for r in rows)}


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="python -m src.tasks",
        description="What is outstanding in one workspace.")
    parser.add_argument("--client", required=True)
    parser.add_argument("--today")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    rows = collect(args.client, today=args.today)
    if args.json:
        print(json.dumps({"workspace": args.client, "counts": counts(rows),
                          "tasks": rows}, indent=2))
        return 0
    if not rows:
        print("  nothing outstanding")
        return 0
    for row in rows:
        where = row["object_id"] or f'{row["count"]} records'
        print(f"  {row['severity']:16} {LABEL[row['kind']]:34} {where}")
        print(f"    {row['why']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
