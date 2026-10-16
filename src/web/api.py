#!/usr/bin/env python3
"""The service layer: arguments in, plain data out.

## The rule this module exists to hold

**Every decision on this page came from the same function the CLI calls.**
Nothing here computes an ICP score, a sendability, a channel verdict, a lint
result or a payload. It calls `icp.score`, `verification.decide`,
`channels.evaluate`, `lint.check_step`, `qa.report`, `push.payloads` and
arranges what they return into something a template can loop over.

That is not a style preference. A UI that re-derives "is this sendable" has a
second answer to a question with one right answer, and the second one is the
one nobody tests. `tests/test_web_invariants.py` walks this module's call graph
and fails if a decision function is missing from it.

## Scoping

Every function takes a `Repo`, and the repo is already scoped to one client
(see `src/repo.py`). There is no function here that takes a client slug and
looks something up, because that is the shape that lets a handler forget.

## Cost

Nothing on this surface spends. Every function is a pure read over stored
state, and the ones that would spend - enrichment, verification, research - are
job types that refuse without an explicit budget. WEB-READINESS: "Read
endpoints must not spend."
"""
import copy
import datetime
import re

from .. import repo as repo_module
from .. import assignment
from .. import (account, accountpolicy, accountstate, cadence, cadencegraph,
                campaignqa, campaignseg,
                campaigns as campaign_store, channels,
                clientreport, clients, coherence, contested, dmplan,
                duplicates,
                eligibility, exitcriteria, floorledger, gonogo,
                contextpack, discovery, explorer, export, fatigue, gtm,
                ingest, learning,
                playbooks as playbook_module,
                icp, jobs, laneopen, lanes, laneprovenance,
                lanerework,
            lint, mx, notify, outreachclaims, push, qa,
                qualify, queuedepth, report,
                reportdraft, reports as report_store, schedule,
                senderteam, providername, suitefate, tagsync,
                oooreturn as oooreturn_module,
                replywatch, tasks, digestwatch, conversation,
                refresh as refresh_module,
                revival as revival_module,
                quality, scalesim, segments, senderidentity, store, touch,
                priority as priority_module, signals as signals_module,
                variants as variants_module,
                verification, waterfall, workspaces as ws)
from ..providers import slack
from . import security

TODAY = datetime.date(2026, 8, 28)


# ------------------------------------------------------------ the agency
#
# Every screen below this point is scoped to one workspace by a `Repo`. These
# two are not, and the way they stay safe is different and worth naming: they
# take an *email*, ask `workspaces.workspaces_for` which workspaces that person
# may enter, and then build one scoped `Repo` per workspace and read through it.
#
# So there is still no unscoped read. There are N scoped reads over a list the
# membership table produced, which means a user who can reach one workspace
# gets an aggregate of exactly one workspace. A super admin gets all of them
# because `workspaces_for` returns all of them for a super admin, which is the
# one deliberate crossing and is already named in the audit log.
#
# `admin_overview` remains the only genuinely unscoped function in this module.


def global_overview(email):
    """Every workspace this person may enter, and the totals across them.

    Nothing here is invented. A metric this system cannot know - a send, a
    delivery, a meeting - is counted from the events that would establish it
    and comes back 0 with the rest of the estate saying why, rather than being
    estimated from what was planned.
    """
    spaces = ws.workspaces_for(email)
    cards, totals = [], {
        "workspaces": 0, "campaigns": 0, "companies": 0, "contacts": 0,
        "qualified": 0, "contactable": 0, "confirmed_email_touches": 0,
        "confirmed_linkedin_touches": 0, "replies": 0, "positive_replies": 0,
        "meetings": 0, "paused": 0, "held": 0, "pending_approvals": 0,
        "failed_jobs": 0, "senders": 0, "senders_active": 0,
        "email_accounts": 0, "email_accounts_active": 0,
        "linkedin_accounts_active": 0,
        "linkedin_accounts": 0, "credits": 0,
    }
    for space in spaces:
        card = workspace_card(email, space["slug"])
        if card is None:
            continue
        cards.append(card)
        totals["workspaces"] += 1
        for key in totals:
            if key == "workspaces":
                continue
            if key in OPERATIONS_ONLY and not card["can_see_operations"]:
                continue        # never aggregate a number they may not read
            totals[key] += card["metrics"].get(key, 0) or 0

    cards.sort(key=lambda c: (-c["metrics"]["contacts"], c["name"]))
    return {
        "workspaces": cards,
        "totals": totals,
        # The machine tiles appear only if at least one workspace on this
        # page contributed to them. A total assembled from a subset would be
        # a number with a silent denominator.
        "operations_visible": any(c["can_see_operations"] for c in cards),
        # Named so the dashboard can say what it is aggregating rather than
        # implying it is everything.
        "scope": ("every workspace" if _is_super(email)
                  else f"the {len(cards)} workspace(s) you are a member of"),
        "super_admin": _is_super(email),
        # Sources for the tiles this reader actually sees. Listing where the
        # credit total comes from is describing the waterfall ledger to
        # somebody who is not shown the credit total.
        "sources": {k: v for k, v in GLOBAL_METRIC_SOURCES.items()
                    if k not in OPERATIONS_ONLY
                    or any(c["can_see_operations"] for c in cards)},
    }


# Totals that describe how Resonate runs rather than how the client's
# outbound is going. Aggregated only across workspaces where the reader has
# `operations.view`, and hidden entirely where they have it nowhere.
OPERATIONS_ONLY = ("failed_jobs", "credits", "senders", "senders_active",
                   "email_accounts", "email_accounts_active",
                   "linkedin_accounts", "linkedin_accounts_active")


def _is_super(email):
    return bool((ws.user(email) or {}).get("super_admin"))


# Where each number on the global dashboard comes from. Rendered beside the
# tiles, because "traceable source" is a property somebody has to be able to
# check rather than a promise in a commit message.
GLOBAL_METRIC_SOURCES = {
    "companies": "queue records for this workspace's client",
    "qualified": "icp.score verdicts stored by qualify.company",
    "contacts": "selected contacts on those records",
    "contactable": "channels.evaluate: mode is not none",
    "confirmed_email_touches":
        "touch.py: push_marked or email_delivered events",
    "confirmed_linkedin_touches":
        "touch.py: push_marked or linkedin_connected events",
    "replies": "reply_received and reply_classified events",
    "positive_replies": "reply_classified with classification positive",
    "meetings": "meeting_marked events - absent until somebody marks one",
    "paused": "records carrying a pause, from a reply on either channel",
    "held": "channels.evaluate: mode is none",
    "pending_approvals": "campaigns awaiting_approval",
    "failed_jobs": "jobs.jsonl rows with status failed",
    "credits": "the waterfall ledger written by enrich.spend",
}


def workspace_card(email, slug):
    """One workspace's operational summary, read through a scoped repo.

    Returns None when this person may not enter the workspace, so a caller
    iterating a list cannot accidentally include one they were not offered.

    **This is the load-bearing check.** `global_overview` also filters the
    list through `workspaces_for` before it gets here, and the mutation audit
    found that removing that outer filter changes nothing observable - because
    `Repo.for_user` raises for a workspace this person is not in and the card
    is dropped. The outer filter is defence in depth and an optimisation
    (it avoids constructing N repos that will raise); this one is the
    boundary. Anybody tempted to simplify should remove the outer one, never
    this.
    """
    try:
        repo = repo_module.Repo.for_user(email, slug)
    except (ws.NotAMember, repo_module.UnknownClient):
        return None

    entry = ws.workspace(slug) or {}
    recs = repo.records()
    campaigns = repo.campaigns()
    config = repo.config()
    # Read once. `channels.evaluate` loads the suppression file
    # whenever it is not handed one, which across an estate is
    # once per contact.
    suppressed = ingest.load_suppress()

    qualified = contactable = held = paused = 0
    contacts = replies = positive = meetings = 0
    email_touches = linkedin_touches = 0
    credits = 0
    for rec in recs:
        verdict = (rec.get("qualification") or {}).get("verdict") or {}
        if verdict.get("icp_status") == icp.QUALIFIED:
            qualified += 1
        if rec.get("paused"):
            paused += 1
        credits += waterfall.spend(rec)["expected"]
        for entry_ in rec.get("events") or []:
            kind = entry_.get("type")
            # One reply writes three events: the receipt, the classifier's
            # verdict, and - when that verdict is positive - the positive
            # signal. Counting the receipt *and* the verdict as replies, and
            # the verdict *and* the signal as positives, doubled both. Two
            # replies in the demo estate were reported as four on a screen a
            # client can open, while their PDF said two.
            #
            # Count arrivals, exactly as `report.for_client` does, so the
            # dashboard and the document cannot disagree.
            if kind == "reply_received":
                replies += 1
            elif kind == "positive_reply_detected":
                positive += 1
            elif kind == "meeting_marked":
                meetings += 1
        for contact in rec.get("contacts") or []:
            if not contact.get("selected"):
                continue
            contacts += 1
            verdicts = channels.evaluate(rec, contact, config, suppressed)
            if verdicts["mode"] == channels.NONE:
                held += 1
            else:
                contactable += 1
            for step in touch.timeline_rows(rec, contact.get("key")):
                if not step["confirmed"]:
                    continue
                if step["channel"] == "email":
                    email_touches += 1
                elif step["channel"] == "linkedin":
                    linkedin_touches += 1

    roster = senderidentity.roster(slug)
    every_job = jobs.for_client(repo.client)
    return {
        "slug": slug,
        "name": entry.get("name") or slug,
        "client": repo.client,
        "role": repo.role(),
        "metrics": {
            "companies": len(recs),
            "qualified": qualified,
            "contacts": contacts,
            "contactable": contactable,
            "held": held,
            "paused": paused,
            "campaigns": len(campaigns),
            "pending_approvals": len(
                [c for c in campaigns
                 if c.get("status") == campaign_store.AWAITING_APPROVAL]),
            "replies": replies,
            "positive_replies": positive,
            "meetings": meetings,
            "confirmed_email_touches": email_touches,
            "confirmed_linkedin_touches": linkedin_touches,
            "failed_jobs": len([j for j in every_job
                                if j.get("status") == jobs.FAILED]),
            "senders": roster["counts"]["senders"],
            # Active and total both, because the card already shows the
            # active figure in its health line. One card carrying "18
            # inbox(es)" and "22 inbox(es)" with nothing to distinguish them
            # is a card a reader has to reconcile by guessing.
            "senders_active": roster["counts"]["active_senders"],
            "email_accounts": roster["counts"]["email_accounts"],
            "email_accounts_active": roster["counts"]["active_email_accounts"],
            "linkedin_accounts": roster["counts"]["linkedin_accounts"],
            "linkedin_accounts_active":
                roster["counts"]["active_linkedin_accounts"],
            "credits": credits,
        },
        # Two health words rather than one number, because "can this workspace
        # send" and "is this workspace's outreach in order" are different
        # questions with different answers.
        # Whether this person may see the machine *in this workspace*. A
        # client bought outcomes; our inbox count, our failed jobs and our
        # credit spend are not part of what they bought, and the workspace
        # dashboard already declines to show them. This screen did not.
        "can_see_operations": repo.may(ws.OPERATIONS_VIEW),
        "sender_health": _sender_health(roster),
        "campaign_health": _campaign_health(campaigns),
        "capacity": roster["capacity"],
    }


def _sender_health(roster):
    """Whether the infrastructure could carry outreach at all."""
    counts = roster["counts"]
    if not counts["active_senders"]:
        return {"state": "none", "why": "no active sender identity"}
    problems = []
    if not counts["active_email_accounts"]:
        problems.append("no active inbox")
    if not counts["active_linkedin_accounts"]:
        problems.append("no active LinkedIn profile")
    if roster["orphan_accounts"]:
        problems.append(f"{len(roster['orphan_accounts'])} account(s) with no "
                        "owner")
    blocked = sum(h.get(senderidentity.HEALTH_BLOCKED, 0)
                  for h in roster["health"].values())
    if blocked:
        problems.append(f"{blocked} blocked account(s)")
    if problems:
        return {"state": "warn", "why": "; ".join(problems)}
    return {"state": "ok",
            "why": f"{counts['active_email_accounts']} active inbox(es), "
                   f"{counts['active_linkedin_accounts']} active profile(s)"}


def _campaign_health(campaigns):
    if not campaigns:
        return {"state": "none", "why": "no campaign yet"}
    paused = len([c for c in campaigns if (c.get("pause") or {}).get("since")])
    waiting = len([c for c in campaigns
                   if c.get("status") == campaign_store.AWAITING_APPROVAL])
    if paused:
        return {"state": "warn", "why": f"{paused} paused"}
    if waiting:
        return {"state": "warn", "why": f"{waiting} awaiting approval"}
    return {"state": "ok", "why": f"{len(campaigns)} campaign(s)"}


def global_comparison(email, metric="positive_replies"):
    """Workspaces side by side, with the denominator on every row.

    A rate without its denominator is how "ContactOut converts better" gets
    said about eleven contacts. Both numbers travel.
    """
    data = global_overview(email)
    rows = []
    for card in data["workspaces"]:
        metrics = card["metrics"]
        rows.append({
            "slug": card["slug"], "name": card["name"],
            "contacts": metrics["contacts"],
            "contactable": metrics["contactable"],
            "replies": metrics["replies"],
            "positive_replies": metrics["positive_replies"],
            "meetings": metrics["meetings"],
            "confirmed_touches": (metrics["confirmed_email_touches"]
                                  + metrics["confirmed_linkedin_touches"]),
            # (numerator, denominator) pairs, never a bare percentage.
            "reply_rate": (metrics["replies"], metrics["contactable"]),
            "positive_rate": (metrics["positive_replies"],
                              metrics["contactable"]),
        })
    rows.sort(key=lambda r: (-r[metric] if isinstance(r.get(metric), int)
                             else 0, r["name"]))
    return {"rows": rows, "metric": metric, "scope": data["scope"],
            "totals": data["totals"]}


# --------------------------------------------------------------- dashboard

def dashboard(repo):
    """Every number on the operator's first screen, from stored state."""
    recs = repo.records()
    config = repo.config()
    # Read once. `channels.evaluate` loads the suppression file
    # whenever it is not handed one, which across an estate is
    # once per contact.
    suppressed = ingest.load_suppress()
    campaigns = repo.campaigns()

    contacts = [(r, c) for r in recs for c in (r.get("contacts") or [])]
    modes = {"multichannel": 0, "email_only": 0, "linkedin_only": 0,
             "none": 0}
    verification_counts = {"double": 0, "single": 0, "invalid": 0,
                           "catch_all": 0, "disagreement": 0,
                           "reoon_escalations": 0, "none": 0}
    mx_counts = {}
    policy = verification.policy_for(config)

    for rec, contact in contacts:
        verdicts = channels.evaluate(rec, contact, config, suppressed)
        modes[verdicts["mode"]] = modes.get(verdicts["mode"], 0) + 1
        if not contact.get("email"):
            verification_counts["none"] += 1
        else:
            decision = verification.resolve(contact, policy)
            if decision.get("disagreement"):
                verification_counts["disagreement"] += 1
            if "reoon" in (decision.get("confirmed_by") or []):
                verification_counts["reoon_escalations"] += 1
            if decision["state"] == verification.INVALID:
                verification_counts["invalid"] += 1
            elif decision["state"] == verification.ACCEPT_ALL_UNCLEARED:
                verification_counts["catch_all"] += 1
            elif (decision["confirmation_count"]
                  >= decision["required_confirmations"]):
                verification_counts["double"] += 1
            else:
                verification_counts["single"] += 1
        stored = mx.stored_decision(contact) or {}
        label = (stored.get("security_provider")
                 or stored.get("mailbox_provider")
                 or ("unknown" if contact.get("email") else "no address"))
        mx_counts[label] = mx_counts.get(label, 0) + 1

    statuses = {}
    for campaign in campaigns:
        statuses[campaign.get("status")] = statuses.get(campaign.get("status"), 0) + 1

    return {
        "client": repo.client,
        # What to do about all of this. Built from the counts above plus a
        # few cheap lookups rather than recomputed, and rendered first,
        # because a screen that opens with "how many companies do we have"
        # answers a question nobody starts the day with.
        # One module decides what counts as outstanding work, so this
        # summary and the /tasks list cannot disagree about how much there
        # is. The counts above are handed through rather than recomputed.
        "attention": tasks.summarise(tasks.collect(
            repo.workspace, recs=recs, config=config, campaigns=campaigns)),
        # The client-facing cut of this screen speaks in funnel stages, and
        # `report.FUNNEL_LABEL` is where those words already live - the same
        # ones the client report prints, so the screen and the PDF cannot
        # drift into describing one number two ways.
        #
        # Only built for the roles that render it. It reaches into approval,
        # cadence and lint, and the operator's page does not show it.
        "funnel": (None if repo.may(ws.OPERATIONS_VIEW)
                   else _client_funnel(recs, config)),
        # What this role may actually do, so the screen can offer the
        # handful of actions that will work rather than a row of buttons
        # half of which refuse. The handler checks again regardless.
        "permissions": sorted(p for p in ws.PERMISSIONS if repo.may(p)),
        "batches": repo.batches(),
        "records": len(recs),
        "states": repo.stats(),
        "qualification": report.qualification_funnel(recs, repo.client),
        "contacts": len(contacts),
        "modes": modes,
        "verification": verification_counts,
        "mx": dict(sorted(mx_counts.items())),
        "campaigns": {"total": len(campaigns), "by_status": statuses},
        "replies": _reply_counts(recs),
        "cost": cost_summary(repo),
        "jobs": jobs.summarise(jobs.for_client(repo.client)),
        # Part of the contract on every surface, not decoration.
        "would_send": 0,
    }


def _reply_counts(recs):
    from .. import events as event_model
    counts = {"positive": 0, "neutral": 0, "negative": 0, "unknown": 0,
              "unmatched": 0, "total": 0}
    for rec in recs:
        for entry in rec.get("events") or []:
            if entry.get("type") != event_model.REPLY_CLASSIFIED:
                continue
            counts["total"] += 1
            kind = entry.get("classification") or "unknown"
            counts[kind] = counts.get(kind, 0) + 1
    return counts




# The stages a client is shown, in the order the work happens. Fewer than
# `report.FUNNEL` carries: `selected`, `active` and `approved` are internal
# steps between deciding and doing, and "approved to send: 40" beside
# "confirmed sent: 0" is a pair of numbers that needs a paragraph, not a
# tile.
CLIENT_FUNNEL = ("domain", "qualified", "contact_found", "contactable",
                 "contacted", "replied", "positive", "meeting")


def _client_funnel(recs, config):
    """The funnel, already labelled, because `pages` is a renderer.

    `report.FUNNEL_LABEL` is where the client-facing wording lives and the
    client report already prints it, so handing the labels through here is
    what keeps the screen and the PDF describing one number one way.
    """
    counts = report.funnel_for(recs, config=config)
    return {
        "stages": [{"stage": stage,
                    "label": report.FUNNEL_LABEL.get(stage, stage),
                    "count": counts.get(stage, 0)}
                   for stage in CLIENT_FUNNEL],
        "contacted": counts.get("contacted", 0),
        "replied": counts.get("replied", 0),
    }


def cost_summary(repo):
    """Planned and maximum. `actual` stays absent, because nobody reports it."""
    recs = repo.records()
    config = repo.config()
    entries = []
    for rec in recs:
        qualification = rec.get("qualification") or {}
        if qualification.get("verdict"):
            entries.append({"record": rec,
                            "persona_plan": qualification.get("persona_plan") or {},
                            "verdict": qualification["verdict"]})
    planned = (dmplan.for_batch(entries, config) if entries else
               {"expected_credits": 0, "maximum_credits": 0,
                "fallback_exposure": 0, "companies_skipped": 0})
    confirmation = report.by_confirmation(recs, repo.client, config)
    return {
        "expected_credits": planned.get("expected_credits", 0),
        "maximum_credits": planned.get("maximum_credits", 0),
        "fallback_exposure": planned.get("fallback_exposure", 0),
        "companies_costing_nothing": planned.get("companies_skipped", 0),
        "verification_operations": confirmation.get("operations", {}),
        "verification_credits": confirmation.get("credits", {}),
        # No provider reports per-call spend. A zero here would be a claim.
        "actual_cost": None,
        "actual_note": confirmation.get("cost_note"),
    }


# ---------------------------------------------------------------- batches

def batch_list(repo):
    """Every batch with its funnel. One read of the estate, grouped.

    `repo.records(batch=...)` re-parses the whole queue per batch, which
    is invisible at demo scale and 2.5 seconds at 30,000 records.
    """
    grouped = {}
    for rec in repo.records():
        key = rec.get("batch") or rec.get("batch_id")
        grouped.setdefault(key, []).append(rec)
    out = []
    for batch, count in repo.batches().items():
        recs = grouped.get(batch) or []
        out.append({
            "batch": batch,
            "records": count,
            "qualification": report.qualification_funnel(recs, repo.client),
            "states": store.stats(recs),
        })
    return out


def batch_detail(repo, batch):
    recs = repo.records(batch=batch)
    config = repo.config()
    return {
        "batch": batch,
        "records": len(recs),
        "qualification": report.qualification_funnel(recs, repo.client),
        "distribution": report.qualification_distribution(recs, repo.client),
        "decision_makers": report.decision_makers(recs, repo.client),
        "cost": report.credit_exposure(recs, repo.client, config),
        "segments": report.campaign_segments(recs, repo.client),
        "dropped": [{"id": r["id"], "company": r.get("company"),
                     "domain": r.get("domain"), "reason": r.get("drop_reason")}
                    for r in recs if r.get("state") == "dropped"],
    }


def preflight(repo, batch):
    """What the engine intends to do, before it does any of it.

    Two numbers kept apart on purpose: what this costs if it goes normally, and
    what it costs if every conditional call fires. The cap is set against the
    second, because that is the number that can arrive on an invoice.
    """
    recs = repo.records(batch=batch)
    config = repo.config()
    entries = []
    for rec in recs:
        qualification = rec.get("qualification") or {}
        if qualification.get("verdict"):
            entries.append({"record": rec,
                            "persona_plan": qualification.get("persona_plan") or {},
                            "verdict": qualification["verdict"]})
    batch_plan = dmplan.for_batch(entries, config) if entries else {}
    steps = dmplan.for_batch_steps(entries, config) if hasattr(
        dmplan, "for_batch_steps") else []
    free = [
        ("domain normalisation", "every row", "free"),
        ("suppression check", "every row", "free"),
        ("ICP classification", f"{len(recs)} companies", "free"),
        ("segmentation and timezone", f"{len(recs)} companies", "free"),
        ("MX screening", "one DNS lookup per domain, cached a week", "free"),
    ]
    return {
        "batch": batch,
        "records": len(recs),
        "free": free,
        "plan": batch_plan,
        "steps": steps,
        "verification_policy": verification.policy_for(config),
        "would_send": 0,
    }


# --------------------------------------------------------------- senders

class ReassignRefused(RuntimeError):
    """The contact was not moved, and the message says which rule stopped it."""


def reassign_sender(repo, record_id, contact_key, channel, sender_id, by,
                    reason):
    """Move one contact to a different human, on the record, with the reason.

    The only way a stored assignment changes. `assignment.reassign` refuses a
    sender from another workspace and one who owns no active account on the
    channel; this adds the workspace audit entry, because moving a prospect
    between humans mid-cadence is exactly the change somebody asks about
    later.

    What it does *not* do is rewrite history. A confirmed touch keeps the
    sender recorded on its own event, so a message that already went out from
    Anna still says Anna in the timeline and may still be referenced as Anna.
    """
    repo.require(ws.WORKSPACE_MANAGE)
    rec = repo.record(record_id)
    if rec is None:
        return None
    contact = next((c for c in rec.get("contacts") or []
                    if c.get("key") == contact_key), None)
    if contact is None:
        return None
    try:
        entry = assignment.reassign(rec, contact, repo.workspace, channel,
                                    sender_id, by=by, reason=reason,
                                    config=repo.config())
    except (ValueError, assignment.NoEligibleSender) as e:
        raise ReassignRefused(str(e))
    repo.save_records([rec])
    repo.audit("sender.reassigned", "contact", f"{record_id}:{contact_key}",
               before=entry["from"], after=entry["to"],
               reason=entry["reason"],
               metadata={"channel": channel})
    return entry




def sender_roster(repo):
    """This workspace's sender infrastructure. Scoped by the repo it is given."""
    return senderidentity.roster(repo.workspace, config=repo.config())


def sender_assignments(repo):
    """Who is carrying which contacts here, and which pairs are in use."""
    return assignment.summarise(repo.records(), repo.workspace)


# ------------------------------------------------------------------ jobs
#
# `src/jobs.py` is the resumable runner: one slice, a cursor, a budget. This is
# the surface that lets an operator turn the handle from a browser and watch a
# number move, and the interesting part of it is what it will *not* run.
#
# PLAYBOOK section 1 splits the pipeline at a line: everything before the STOP
# is free and re-runnable, everything after it costs money. This build does not
# make paid provider calls at all, so the browser may run the free half and is
# refused - structurally, not by a missing button - on the rest.
#
# The refusal is a table rather than a check inside each handler, for the same
# reason `READ_PERMISSIONS` is: the handler that forgets is the failure mode.


def _classify_one(config):
    """Qualify one company: classify, score, route, plan. Spends nothing.

    `qualify.company` is the same call the CLI makes. One unit is one company,
    which is what makes the cursor mean something an operator can read.
    """
    def work(rec):
        qualify.company(rec, config)
        return "ok"
    return work


# job type -> (label, what one unit does, why it is safe to run here)
RUNNABLE_JOBS = {
    jobs.ICP_CLASSIFY: (
        "ICP classification",
        _classify_one,
        "reads the stored company facts and writes a verdict. No provider is "
        "called and no credit is spent."),
}

# Everything else, and the sentence an operator gets instead of a button.
UNRUNNABLE_JOBS = {
    jobs.ENRICH: "finds decision makers, which is a paid ContactOut call",
    jobs.VERIFY: "verifies addresses, which is a paid verifier call",
    jobs.RESEARCH: "runs an Apify actor, which is a paid scrape",
    jobs.PERSONALIZE: "calls the model, which is a paid LLM request",
    jobs.RENDER: "generates copy, which is a paid LLM request",
    jobs.INGEST: "is done by the upload screen, which parses and commits",
    jobs.SEGMENT: "is part of ICP classification here: the segment ladder is "
                  "decided across the whole batch at once, not per record",
    jobs.PLAN_DM: "is part of ICP classification here: the cost plan falls out "
                  "of routing the personas",
    jobs.QA: "runs on the campaign screen, which reports it live",
    jobs.PREPARE_CAMPAIGN: "is the campaign builder, which is its own screen",
}


class JobRefused(RuntimeError):
    """The job was not started, and the message says which rule stopped it."""


def job_rows(repo, batch=None):
    """Every job this workspace owns, newest first, with its resume point."""
    rows = []
    for job in jobs.for_client(repo.client):
        if batch and job.get("batch") != batch:
            continue
        rows.append({
            "id": job.get("id"),
            "type": job.get("type"),
            "batch": job.get("batch"),
            "status": job.get("status"),
            "created_at": job.get("created_at"),
            "created_by": job.get("created_by"),
            "finished_at": job.get("finished_at"),
            "total": job.get("total") or 0,
            "processed": job.get("processed") or 0,
            "failed": job.get("failed") or 0,
            "held": job.get("held") or 0,
            "slices": job.get("slices") or 0,
            "progress": job.get("progress") or 0.0,
            "cursor": job.get("cursor"),
            "spends": bool(job.get("spends")),
            "budget": job.get("budget"),
            "spent": job.get("spent") or 0,
            # Absent rather than zero: no provider in this stack reports
            # per-call spend, so a number here would be invented.
            "actual_cost": job.get("actual_cost"),
            "error": job.get("error"),
            "failures": (job.get("failures") or [])[:10],
            "log": (job.get("log") or [])[-8:],
        })
    rows.sort(key=lambda r: str(r["created_at"]), reverse=True)
    return {
        "rows": rows,
        "summary": jobs.summarise(jobs.for_client(repo.client)),
        "batches": sorted(repo.batches()),
        "batch": batch,
        "can_run": repo.may(ws.BATCH_RUN),
        "runnable": [{"type": t, "label": RUNNABLE_JOBS[t][0],
                      "why_safe": RUNNABLE_JOBS[t][2]}
                     for t in sorted(RUNNABLE_JOBS)],
        "unrunnable": [{"type": t, "why": why}
                       for t, why in sorted(UNRUNNABLE_JOBS.items())],
        "slice_size": jobs.SLICE,
    }


def run_job(repo, job_type, batch, by="unknown", job_id=None):
    """Advance one job by one slice. Never runs to completion.

    A web request that ran 5,000 records would be a request that times out, so
    this does one slice and returns the number. The cursor is what makes
    calling it again continue rather than start over.
    """
    repo.require(ws.BATCH_RUN)
    if job_type in jobs.SPENDING_TYPES:
        raise JobRefused(
            f"{job_type} can spend credits, and this build does not make paid "
            f"provider calls: it {UNRUNNABLE_JOBS.get(job_type, 'spends')}. "
            "Run it from the CLI with an explicit budget when that changes.")
    if job_type not in RUNNABLE_JOBS:
        why = UNRUNNABLE_JOBS.get(job_type)
        raise JobRefused(
            f"{job_type} is not runnable from here: it {why}" if why
            else f"{job_type} is not a job this screen runs")
    if not batch:
        raise JobRefused("pick a batch to run against")

    items = repo.records(batch=batch)
    if not items:
        raise JobRefused(f"batch {batch!r} holds no records in this workspace")

    config = repo.config()
    job = None
    if job_id:
        job = jobs.get(job_id)
        if job is None or job.get("client") != repo.client:
            # 404-shaped, for the same reason a foreign record is: a job id
            # names a batch, and a batch names companies.
            return None
    else:
        for existing in jobs.for_client(repo.client):
            if (existing.get("type") == job_type
                    and existing.get("batch") == batch
                    and existing.get("status") not in jobs.TERMINAL):
                job = existing
                break
    created = job is None
    if created:
        job = jobs.new(job_type, repo.client, batch=batch, total=len(items),
                       created_by=by,
                       note=RUNNABLE_JOBS[job_type][2])
        jobs.append(job)

    work = RUNNABLE_JOBS[job_type][1](config)
    jobs.run_step(job, items, work, slice_size=jobs.SLICE)

    # The records the work mutated, then the job. Records first: a job that
    # says "done" over records that were not written is the one lie this
    # ordering cannot tell.
    repo.save_records(items)
    if job_type == jobs.ICP_CLASSIFY and job.get("status") in jobs.TERMINAL:
        # The segment ladder is decided across the whole batch - which rung a
        # company lands on depends on how many others share its key - so it can
        # only run once every record in the batch has a verdict.
        qualify.run(repo.records(batch=batch), client=repo.client,
                    config=config, store_result=True)
        repo.save_records(repo.records(batch=batch))

    with jobs.transaction() as rows:
        for i, existing in enumerate(rows):
            if existing.get("id") == job["id"]:
                rows[i] = job
                break
    repo.audit("job.ran", "job", job["id"],
               after={"type": job_type, "batch": batch,
                      "status": job["status"], "processed": job["processed"],
                      "failed": job["failed"]},
               reason="one slice from the batch screen")
    return job


def cancel_job(repo, job_id, by="unknown"):
    """Stop a job. What is done stays done; nothing is rolled back."""
    repo.require(ws.BATCH_RUN)
    job = jobs.get(job_id)
    if job is None or job.get("client") != repo.client:
        return None
    jobs.cancel(job, why=f"cancelled by {by}")
    with jobs.transaction() as rows:
        for i, existing in enumerate(rows):
            if existing.get("id") == job["id"]:
                rows[i] = job
                break
    repo.audit("job.cancelled", "job", job_id,
               after={"status": job["status"]},
               reason="cancelled from the jobs screen")
    return job


# ------------------------------------------------------------- companies

# --------------------------------------------------------------- pagination
#
# A list screen that renders every row is fine at demo scale and is
# thirty thousand rows of HTML at real scale. The data assembles in well
# under a second; the browser is what falls over.
#
# One helper rather than a cap per screen, because "showing 100 of 30,000"
# has to be said the same way everywhere, and a screen that silently
# truncates is worse than one that is slow - the reader cannot tell the
# difference between "these are the rows" and "these are some of them".

PAGE_SIZE = 100
MAX_PAGE_SIZE = 500


def paginate(rows, page=None, size=None):
    """One page of `rows`, with everything the screen needs to say so.

    `page` is 1-based because it appears in a URL a person may edit. A
    page past the end returns empty rather than clamping: silently showing
    page 4 to somebody who asked for page 40 is a lie about where they
    are.
    """
    total = len(rows)
    try:
        size = int(size) if size else PAGE_SIZE
    except (TypeError, ValueError):
        size = PAGE_SIZE
    # A nonsensical size falls back to the default rather than clamping to
    # one: `?size=-4` meant "one row per page", which is a stranger answer
    # than the question deserved.
    if size < 1:
        size = PAGE_SIZE
    size = min(size, MAX_PAGE_SIZE)

    try:
        page = int(page) if page else 1
    except (TypeError, ValueError):
        page = 1
    page = max(1, page)

    start = (page - 1) * size
    window = rows[start:start + size]
    pages = max(1, (total + size - 1) // size)
    return {
        "rows": window,
        "page": page,
        "pages": pages,
        "size": size,
        "total": total,
        "shown": len(window),
        "first": start + 1 if window else 0,
        "last": start + len(window),
        # Said rather than implied. A screen showing 100 of 30,000 that
        # does not say so is a screen somebody will read as complete.
        "truncated": total > len(window),
        "has_previous": page > 1,
        "has_next": start + len(window) < total,
    }

def company_rows(repo, batch=None, filters=None):
    """The ICP review table. Filtering is exact-match on stated vocabulary."""
    recs = repo.records(batch=batch)
    entries = []
    for rec in recs:
        qualification = rec.get("qualification") or {}
        entries.append({
            "record": rec,
            "segment": qualification.get("segment") or {},
            "verdict": qualification.get("verdict") or {},
            "persona_plan": qualification.get("persona_plan") or {},
            "segment_key": qualification.get("segment_key"),
        })
    if filters:
        entries = explorer.apply_filters(entries, filters)
    return [_company_row(e) for e in entries]


def _company_row(entry):
    rec, seg, verdict = entry["record"], entry["segment"], entry["verdict"]
    return {
        "id": rec["id"],
        "company": rec.get("company"),
        "domain": rec.get("domain"),
        "state": rec.get("state"),
        "drop_reason": rec.get("drop_reason"),
        "icp_status": verdict.get("icp_status"),
        "icp_tier": verdict.get("icp_tier"),
        "icp_score": verdict.get("icp_score"),
        "icp_confidence": verdict.get("icp_confidence"),
        "reasons": verdict.get("classification_reasons") or [],
        "contradictions": verdict.get("contradictions") or [],
        "vertical": seg.get("vertical"),
        "industry": (rec.get("company_facts") or {}).get("industry"),
        "employees": seg.get("employees"),
        "employee_band": seg.get("employee_band"),
        "country": (seg.get("country") or "").title() or None,
        "region": seg.get("region"),
        "timezone": seg.get("timezone"),
        "segment_key": entry.get("segment_key"),
        "contacts": len(rec.get("contacts") or []),
    }


def segment_tree(repo, batch=None):
    """Region -> vertical -> band, with counts and channel potential."""
    rows = company_rows(repo, batch)
    tree = {}
    for row in rows:
        region = row.get("region") or "Unknown"
        vertical = row.get("vertical") or "Unknown"
        band = row.get("employee_band") or "UNKNOWN"
        node = tree.setdefault(region, {})
        leaf = node.setdefault(vertical, {})
        bucket = leaf.setdefault(band, {"companies": 0, "segment_keys": set()})
        bucket["companies"] += 1
        if row.get("segment_key"):
            bucket["segment_keys"].add(row["segment_key"])
    # Sets are not JSON, and the page wants a stable order anyway.
    for region in tree.values():
        for vertical in region.values():
            for bucket in vertical.values():
                bucket["segment_keys"] = sorted(bucket["segment_keys"])
    return tree


def segment_health(repo, batch=None):
    """Which segments are too small to be worth writing for, and too big.

    `campaignseg.summarise` has always computed both. The oversized list -
    `eligible_for_splitting` - was calculated on every qualification run
    and then discarded: nothing read it, no screen showed it, and a
    twenty-thousand-company cohort was identified as too broad to write
    one message for and then campaigned as one anyway.

    This reads it. It does not split anything: which dimension to split a
    cohort on is a strategy decision, and the ladder merges upward
    automatically only because merging is the safe direction - a message
    written for a broader group is duller, while one written for a group
    that was split on the wrong axis is wrong.
    """
    repo.require(ws.CONTACTS_VIEW)
    config = repo.config()

    assigned = []
    for rec in repo.records(batch=batch):
        qualification = rec.get("qualification") or {}
        if not qualification.get("segment_key"):
            continue
        assigned.append({
            "segment_key": qualification["segment_key"],
            "segment_rung": qualification.get("segment_rung") or "full",
            "segment_reason": qualification.get("segment_reason") or "",
            "record_id": rec.get("id"),
            "company": rec.get("company"),
        })

    found = campaignseg.summarise(assigned, config)
    members = {}
    for entry in assigned:
        members.setdefault(entry["segment_key"], []).append(entry)

    def rows_for(bucket):
        return [
            {"segment_key": key,
             "companies": value["companies"],
             "rung": value["rung"],
             "reason": value["reason"],
             # A few names, so "too broad" is a claim somebody can look
             # at rather than a number.
             "examples": [m["company"] for m in members.get(key, [])[:4]]}
            for key, value in sorted(bucket.items(),
                                     key=lambda kv: -kv[1]["companies"])]

    return {
        "batch": batch,
        "segments": found["segments"],
        "segmented_companies": found["segmented_companies"],
        "unsegmented_companies": found["unsegmented_companies"],
        "minimum": found["min_segment_size"],
        "maximum": found["max_segment_size"],
        "too_small": rows_for(found["below_minimum"]),
        # The half that was being thrown away.
        "too_broad": rows_for(found["eligible_for_splitting"]),
        "note": found["note"],
        "healthy": (len(found["below_minimum"]) == 0
                    and len(found["eligible_for_splitting"]) == 0),
        # Only for the cohorts that are actually too broad. Computing axes
        # for a healthy segment would be work nobody asked for and a
        # screen nobody reads.
        "axes": {key: split_axes(repo, key, batch)
                 for key in found["eligible_for_splitting"]},
        # The strategy each oversized cohort implies, so the question
        # "should this be split" is asked next to what we would say to it
        # either way.
        "strategies": {key: segment_strategy(repo, key, batch)
                       for key in found["eligible_for_splitting"]},
    }



# Dimensions a cohort can be split on, in the order a person would reach
# for them. Each names the stored field it reads: nothing here derives a
# new attribute, because a split axis invented at this layer would be a
# second opinion about what a company is.
SPLIT_AXES = (
    ("country", "Country", "geography changes the proof and the timing"),
    ("region", "Region", "a broader geography when countries are thin"),
    ("vertical", "Vertical", "the pain is usually vertical-shaped"),
    ("subvertical", "Subvertical", "finer than vertical where it is known"),
    ("employee_band", "Company size",
     "a twenty-person agency and a five-hundred-person one have different "
     "operational problems"),
    ("business_model", "Business model", "how they charge changes the pain"),
    ("company_maturity", "Company stage", "stage changes what is urgent"),
)

# Below this share of known values an axis is not offered. Splitting on a
# dimension that is mostly unknown produces one real cohort and one
# labelled "we did not find out", which is a data-quality report wearing a
# segment.
KNOWN_ENOUGH = 0.60


def split_axes(repo, segment_key, batch=None):
    """How an oversized cohort could be divided, with the counts to judge it.

    Proposes and does nothing. `campaignseg` merges upward on its own
    because merging is safe - a message written for a broader group is
    duller. Splitting is the opposite: split on the wrong axis and the
    copy is wrong rather than dull, so which axis to use is a decision a
    person makes with the numbers in front of them.
    """
    repo.require(ws.CONTACTS_VIEW)
    config = repo.config()
    policy = campaignseg.settings(config)

    members = []
    for rec in repo.records(batch=batch):
        qualification = rec.get("qualification") or {}
        if qualification.get("segment_key") != segment_key:
            continue
        members.append({
            "record_id": rec.get("id"),
            "company": rec.get("company"),
            "segment": qualification.get("segment") or {},
        })

    axes = []
    for field, label, why in SPLIT_AXES:
        counts, unknown = {}, 0
        for entry in members:
            value = (entry["segment"] or {}).get(field)
            if not value or str(value).upper() == "UNKNOWN":
                unknown += 1
                continue
            counts[value] = counts.get(value, 0) + 1

        known = len(members) - unknown
        share = (known / len(members)) if members else 0.0
        children = sorted(
            ({"value": value, "companies": count,
              # A child that is itself too small has not solved the
              # problem, it has moved it.
              "viable": count >= policy["min_segment_size"],
              "still_broad": count > policy["max_segment_size"]}
             for value, count in counts.items()),
            key=lambda c: -c["companies"])

        axes.append({
            "field": field,
            "label": label,
            "why": why,
            "known": known,
            "unknown": unknown,
            "known_share": share,
            "children": children,
            "distinct": len(children),
            "viable_children": len([c for c in children if c["viable"]]),
            # Offered only when most of the cohort actually carries the
            # value, and only when it divides into more than one group.
            "offered": share >= KNOWN_ENOUGH and len(children) > 1,
            "why_not": (None if share >= KNOWN_ENOUGH and len(children) > 1
                        else (f"only {share:.0%} of these companies have a "
                              f"known {label.lower()}"
                              if share < KNOWN_ENOUGH
                              else f"every company here has the same "
                                   f"{label.lower()}")),
        })

    offered = [a for a in axes if a["offered"]]
    offered.sort(key=lambda a: (-a["viable_children"], -a["known_share"]))

    return {
        "segment_key": segment_key,
        "companies": len(members),
        "minimum": policy["min_segment_size"],
        "maximum": policy["max_segment_size"],
        "axes": offered,
        "rejected": [a for a in axes if not a["offered"]],
        "examples": [m["company"] for m in members[:6]],
        # Said in the value, because a caller that only reads `axes` should
        # still be unable to conclude that anything was decided.
        "note": ("Proposals. Nothing here splits a segment: which axis to "
                 "use decides whether the resulting copy is right, and a "
                 "cohort split on the wrong one produces messages that are "
                 "wrong rather than merely broad."),
    }



def segment_strategy(repo, segment_key, batch=None):
    """The approach a segment implies, before a campaign exists.

    Everything here is already decided somewhere else and aggregated here:
    `strategy.for_company` chose the angles per company, `playbooks`
    knows which approaches exist, `campaignseg` knows why these companies
    are one group. This counts them.

    ## It is a hypothesis and says so

    A segment strategy is what we *expect* to work. Until messages have
    gone out and replies have come back it rests on the ICP evidence that
    qualified the companies and on nothing else, so every block carries
    its sample size and the whole object carries `confidence`. A strategy
    presented as established fact is one nobody re-examines.

    ## Supported and typical are not merged

    `strategy` already splits a pain into "this company's own evidence
    fired it" and "typical for the vertical, and nothing here supports
    it". Aggregating those together would turn a guess into a brief, so
    the split survives to the screen - as it does in `contextpack`.
    """
    repo.require(ws.CONTACTS_VIEW)
    config = repo.config()

    members = []
    for rec in repo.records(batch=batch):
        qualification = rec.get("qualification") or {}
        if qualification.get("segment_key") != segment_key:
            continue
        members.append(rec)

    if not members:
        return {"segment_key": segment_key, "companies": 0, "exists": False}

    first = (members[0].get("qualification") or {})
    angles = contextpack.angles(members, config)

    # Personas, counted from the contacts actually selected rather than
    # from the personas the routing plan hoped for.
    personas = {}
    reachable = 0
    suppressed = ingest.load_suppress()
    for rec in members:
        selected = [c for c in rec.get("contacts") or [] if c.get("selected")]
        for contact in selected:
            if contact.get("persona"):
                personas[contact["persona"]] = personas.get(
                    contact["persona"], 0) + 1
        if any(channels.evaluate(rec, c, config, suppressed)["mode"]
               != channels.NONE for c in selected):
            reachable += 1

    # Which approaches the accounts in this segment actually fit. Counted
    # from `playbooks.recommend`, which reads each account's own signals -
    # so a playbook only appears here because accounts qualified for it.
    fits = {}
    for rec in members[:_STRATEGY_SCAN_CAP]:
        found = playbook_module.recommend(
            rec, priority_module.assess(rec, repo.workspace, config,
                                        suppressed=suppressed))
        for row in found["recommended"]:
            fits[row["playbook"]] = fits.get(row["playbook"], 0) + 1
    scanned = min(len(members), _STRATEGY_SCAN_CAP)

    playbook_rows = sorted(
        ({"playbook": key, "accounts": count,
          "name": playbook_module.BY_ID[key]["name"],
          "when": playbook_module.BY_ID[key]["when"],
          "cadence": playbook_module.BY_ID[key]["cadence"],
          "cta": playbook_module.BY_ID[key]["cta"],
          "proof": playbook_module.BY_ID[key]["proof"],
          "share": count / scanned if scanned else 0.0}
         for key, count in fits.items()),
        key=lambda r: -r["accounts"])

    supported = angles["supported"]
    return {
        "segment_key": segment_key,
        "exists": True,
        "companies": len(members),
        "reason": first.get("segment_reason"),
        "rung": first.get("segment_rung"),
        "definition": first.get("segment_parts") or {},

        # The pain we would lead with, and the ones we would not.
        "primary": supported[0] if supported else None,
        "secondary": supported[1:3],
        "hypotheses": angles["unsupported_anywhere"],
        "evidenced_companies": angles["companies_with_supported_angle"],

        "personas": sorted(({"persona": k, "contacts": v}
                            for k, v in personas.items()),
                           key=lambda r: -r["contacts"]),
        "reachable": reachable,

        "playbooks": playbook_rows,
        "scanned": scanned,
        "capped": len(members) > scanned,

        # Said in the object, not only on the screen. A caller reading
        # this must not be able to mistake it for a measured result.
        "confidence": _strategy_confidence(angles, len(members)),
        "note": ("A hypothesis. It rests on the ICP evidence that "
                 "qualified these companies, not on anything that has been "
                 "sent - no message from this segment has produced an "
                 "outcome yet, so nothing here is a measured result."),
    }


# The playbook scan asks each account for its own signals, which is a read
# per account. Capped, and the cap is reported on the value, because a
# strategy that silently described the first hundred of a thousand would
# be a sample presented as a segment.
_STRATEGY_SCAN_CAP = 100


def _strategy_confidence(angles, companies):
    """How much of this segment's strategy rests on its own evidence.

    Not a score anybody should optimise: three words, so a reader knows
    whether they are looking at a brief or at a starting point.
    """
    evidenced = angles["companies_with_supported_angle"]
    if not companies:
        return {"level": "none", "why": "no companies in this segment"}
    share = evidenced / companies
    if not angles["supported"]:
        return {"level": "none",
                "why": ("no company here has an angle its own evidence "
                        "supports - everything available is typical for the "
                        "vertical")}
    if share >= 0.7:
        level = "evidenced"
    elif share >= 0.3:
        level = "mixed"
    else:
        level = "thin"
    return {"level": level,
            "why": (f"{evidenced} of {companies} companies have at least one "
                    f"angle their own evidence supports")}



def refresh_plan(repo, today=None, cap=None):
    """What a refresh run would do for this workspace, and what it would cost.

    Reads. Nothing here calls a provider and nothing writes state -
    `refresh.plan` is a pure function over the records, and the screen it
    feeds is a proposal rather than a receipt.
    """
    repo.require(ws.OPERATIONS_VIEW)
    return refresh_module.plan(repo.records(), today=today,
                               config=repo.config(),
                               workspace=repo.workspace, cap=cap)



def revival_view(repo, today=None):
    """Quiet accounts, and whether there is anything new to say to them.

    Reads. `revival.assess` writes nothing and decides nothing beyond a
    verdict - what gets built from a READY account goes through the
    campaign builder, the approval gate and the eligibility gate exactly
    as a first approach would.
    """
    repo.require(ws.OPERATIONS_VIEW)
    rows = revival_module.candidates(repo.records(), today=today,
                                     config=repo.config(),
                                     workspace=repo.workspace)
    found = revival_module.summarise(rows)
    return {
        "workspace": repo.workspace,
        "summary": found,
        "ready": [r for r in rows if r["verdict"] == revival_module.READY],
        # Counted with their sentences so the screen renders what it is
        # handed. "Nothing new" is the number worth reading twice: it is
        # the queue that would otherwise become a repeat campaign.
        "verdicts": [{"verdict": v,
                      "label": revival_module.VERDICT_LABEL[v],
                      "count": found["counts"][v]}
                     for v in revival_module.VERDICTS],
        "quiet_with_nothing_new": [
            {"record_id": r["record_id"], "company": r["company"],
             "days_since": r.get("days_since"), "why": r["why"]}
            for r in rows if r["verdict"] == revival_module.NOTHING_NEW],
        "note": found["note"],
    }


def campaign_preflight(repo, campaign_id, day=None):
    """What would actually happen if this campaign ran, before anybody
    approves it.

    Two halves, and the second one was missing. `campaigns.validate` answers
    seventeen questions about the campaign itself - approved, linted,
    senders mapped, credentials present - and the campaign page has shown
    those for a long time. What it never showed is the audience: how many
    of these people could receive anything, and why the rest could not.

    A reviewer approving a campaign where eighteen of forty contacts are
    held for verification is approving something different from what they
    think, and "campaign cannot run" is not a sentence anybody can act on.

    Reasons come from `eligibility.decide`, which is the only authority on
    the question, and the prose is `eligibility.HUMAN` rather than anything
    written here - the codes are vocabulary and the sentences already exist.

    Nothing is called and nothing is written. Each contact is asked about
    its next unsent step, so the cost is one decision per contact rather
    than one per step.
    """
    from .. import cadence, eligibility

    campaign = repo.campaign(campaign_id)
    if campaign is None:
        return None
    config = repo.config()
    ids = set(campaign.get("record_ids") or [])
    recs = [r for r in repo.records() if r["id"] in ids]

    verdicts = {eligibility.ELIGIBLE: 0, eligibility.HELD: 0,
                eligibility.BLOCKED: 0, eligibility.SKIPPED: 0}
    would = 0
    reasons = {}
    contacts = 0

    for rec in recs:
        try:
            timeline = cadence.build(rec, config, recs=recs,
                                     campaign=campaign).get("contacts") or {}
        except Exception:                                 # noqa: BLE001
            continue
        for contact_key, steps in timeline.items():
            contact = next((c for c in rec.get("contacts") or []
                            if c.get("key") == contact_key), None)
            if contact is None:
                continue
            contacts += 1
            step_key = next(iter(steps), None)
            if step_key is None:
                continue
            decision = eligibility.decide(
                rec, contact, step_key, campaign=campaign, recs=recs,
                config=config, timeline=timeline)
            verdict = decision.get("verdict")
            verdicts[verdict] = verdicts.get(verdict, 0) + 1
            # "How many could receive this" is circular on the approvals
            # screen: the answer is nobody, because it has not been
            # approved - which is the thing the reader is deciding. So the
            # question they are actually asking is counted separately:
            # once approved, how many are still stopped by something else.
            others = [r for r in (decision.get("reasons") or [])
                      if r != eligibility.HELD_CAMPAIGN_UNAPPROVED]
            if not others:
                would += 1
            for code in decision.get("reasons") or []:
                entry = reasons.setdefault(code, {
                    "code": code,
                    "human": eligibility.HUMAN.get(code, code),
                    "kind": str(code).split(":", 1)[0],
                    "count": 0})
                entry["count"] += 1

    result = campaign_store.validate(campaign_id, recs=recs, config=config,
                                     campaign=campaign)
    return {
        "campaign_id": campaign_id,
        "name": campaign.get("name") or campaign_id,
        "status": campaign.get("status"),
        "accounts": len(recs),
        "contacts": contacts,
        "eligible": verdicts.get(eligibility.ELIGIBLE, 0),
        # Eligible once approved: the same count with the approval gate
        # itself set aside. Never larger than the audience, and never a
        # promise - the gate runs again at send time.
        "eligible_if_approved": would,
        "verdicts": verdicts,
        # Most common first: a reviewer wants the thing stopping most of
        # the audience, not an alphabetical list of codes.
        "reasons": sorted(reasons.values(),
                          key=lambda r: (-r["count"], r["code"])),
        "checks": result.get("checks") or [],
        "blockers": result.get("blockers") or [],
        "ok": result.get("ok"),
    }


def task_queue(repo, today=None):
    """Everything outstanding in this workspace, one row per piece of work.

    The dashboard shows the same list grouped into counts. This is the
    version somebody works down. Both come from `tasks.collect`, so the
    number on the card and the number of rows here cannot drift apart.
    """
    repo.require(ws.OPERATIONS_VIEW)
    rows = tasks.collect(repo.workspace, recs=repo.records(),
                         config=repo.config(), campaigns=repo.campaigns(),
                         today=today)
    return {"workspace": repo.workspace, "tasks": rows,
            "counts": tasks.counts(rows),
            "summary": tasks.summarise(rows)}


def returns_view(repo, today=None):
    """People who said they would be back, and whether today is the day.

    Reads. `oooreturn.assess` writes nothing and lifts nothing - the stop
    an out-of-office wrote is still on the contact after this renders, and
    a person is the one who acts on `DUE`. Everything built from that goes
    through the campaign builder, approval and eligibility exactly as a
    first approach would.

    Scoped to the workspace, like every other view here: an operator must
    not learn who is on holiday at another tenant.
    """
    repo.require(ws.OPERATIONS_VIEW)
    rows = oooreturn_module.candidates(repo.records(), today=today,
                                       config=repo.config(),
                                       workspace=repo.workspace)
    counts = oooreturn_module.summarise(rows)
    return {
        "workspace": repo.workspace,
        "as_of": oooreturn_module.today_iso(today),
        "counts": counts,
        "verdicts": [{"verdict": name,
                      "label": oooreturn_module.VERDICT_LABEL[name],
                      "count": counts[name]}
                     for name in oooreturn_module.VERDICTS],
        "due": [r for r in rows if r["verdict"] == oooreturn_module.DUE],
        # The queue that would otherwise be invisible. An absence with no
        # readable date is not a parsing failure to hide - it is somebody
        # who has to be looked at by hand, and a screen showing only the
        # due ones would bury them for ever.
        "needs_a_person": [r for r in rows
                           if r["verdict"] == oooreturn_module.NEEDS_A_PERSON],
        "waiting": [r for r in rows
                    if r["verdict"] == oooreturn_module.NOT_YET],
    }


# ------------------------------------------------------------ what is stuck


def operational_health(repo):
    """Everything currently failing or owed, in one list.

    Nothing here is new instrumentation. Every one of these paths already
    records its own failure in canonical state - a failed job carries its
    count, the tag outbox carries `last_error`, a refused notification
    carries its reason - so none of it was ever lost. What was missing was
    somewhere to read them together, which is the difference between a
    system that records failures and one that surfaces them.

    Scoped to the workspace throughout. An operator reading this must not
    learn that another tenant's Slack is misconfigured.

    Each row says what failed, what still worked, and whether retrying is
    safe - because "it failed" without "and the reply was still recorded"
    is the sentence that makes somebody re-run a thing that already
    happened.
    """
    repo.require(ws.OPERATIONS_VIEW)
    rows = []

    # Reply protection. First, because it is the only row here that means
    # outreach may still be going out to somebody who has already answered.
    # Silence is not health: a poller that has never run, or that last
    # succeeded hours ago, is a row rather than an absence.
    #
    # Process-global rather than per workspace - there is one set of
    # provider credentials - so it is shown in every workspace's health and
    # says nothing about which tenant the events belonged to.
    for watch in replywatch.problems():
        rows.append({
            "area": "reply protection",
            "what": f"{watch['provider']} reply polling",
            "failed": watch["consecutive_failures"],
            "succeeded": 0,
            "state": watch["state"],
            "detail": watch["last_error"] or watch["label"],
            "retry_safe": True,
            "why_safe": "polling reads and is idempotent on the provider's "
                        "own event id, so running it again re-reads rather "
                        "than re-applies",
            "where": "/replies/returns",
        })

    # The digest, and only when it was asked for and did not happen. Off is
    # not a fault - nobody chose to have one - and a digest that failed to
    # *post* is already a row in the outbox further down, where the same
    # failure counted twice would be two numbers that could disagree.
    for missed in digestwatch.problems(repo.workspace):
        rows.append({
            "area": "reporting",
            "what": "daily digest",
            "failed": 1,
            "succeeded": 0,
            "state": missed["state"],
            "detail": missed["detail"],
            "retry_safe": True,
            "why_safe": "a digest is a summary of state that is already "
                        "recorded, so building it again reads the same "
                        "events and announces the same period once",
            "where": "/notifications",
        })

    # Jobs. A failed job is not a lost batch: it records how many records
    # it processed before it stopped, and it resumes per record.
    for job in jobs.for_client(repo.client):
        failed = job.get("failed") or 0
        if job.get("status") == jobs.FAILED or failed:
            rows.append({
                "area": "batch processing",
                "what": f"{job.get('kind') or 'job'} {job.get('id')}",
                "failed": failed,
                "succeeded": job.get("processed") or 0,
                "state": job.get("status"),
                "detail": job.get("error") or job.get("last_error"),
                "retry_safe": True,
                "why_safe": "jobs resume per record, so re-running skips "
                            "what already succeeded",
                "where": "/jobs",
            })

    # Notifications the outbox could not deliver. A Slack failure never
    # unwinds the reply that caused it, which is the property worth
    # restating here rather than leaving in a docstring.
    # `status=` narrows before the limit, so this is the newest 500
    # *failures* rather than the failures among the newest 500 rows of any
    # kind. Without it a workspace whose failures were older than its last
    # 500 notifications reported "clean" - on a screen whose own docstring
    # says silence is not health, and whose `unwatched` block exists
    # because a health screen that looks clean because it was not watching
    # is worse than none.
    for row in notify.history(repo.workspace, status=notify.FAILED,
                              limit=500):
        if row.get("status") != notify.FAILED:
            continue
        rows.append({
            "area": "slack",
            "what": row.get("type"),
            "failed": row.get("attempts") or 1,
            "succeeded": None,
            "state": row.get("status"),
            "detail": row.get("last_error"),
            "retry_safe": True,
            "why_safe": "notifications are idempotent: the same occurrence "
                        "produces the same id, so a retry cannot duplicate "
                        "the alert. The reply and any pause it caused were "
                        "recorded before this was attempted",
            "where": "/notifications",
        })

    # Provider tags the outbox is still owed. Canonical state is already
    # correct; a missing tag delays a label in somebody else's interface.
    stuck = 0
    blocked = 0
    # `load` returns the newest row per outbox key, as a dict.
    for row in tagsync.load().values():
        if row.get("workspace") != repo.workspace:
            continue
        if row.get("status") == tagsync.FAILED:
            stuck += 1
        elif row.get("status") == tagsync.BLOCKED:
            blocked += 1
    if stuck:
        rows.append({
            "area": "provider tags",
            "what": f"{stuck} tag write(s) owed",
            "failed": stuck,
            "succeeded": None,
            "state": tagsync.FAILED,
            "detail": "the provider refused or could not be reached",
            "retry_safe": True,
            "why_safe": "the outbox is keyed on workspace, record, contact "
                        "and provider, so a retry re-sends the same desired "
                        "state rather than a second one",
            "where": "/diagnostics",
        })
    if blocked:
        rows.append({
            "area": "provider tags",
            "what": f"{blocked} contact(s) cannot be named to a provider",
            "failed": blocked,
            "succeeded": None,
            "state": tagsync.BLOCKED,
            "detail": "no provider lead id, mailbox or profile URL - and a "
                      "name is never identity",
            "retry_safe": False,
            "why_safe": "retrying changes nothing: the contact needs an "
                        "identifier before a provider can be told anything "
                        "about them",
            "where": "/contacts",
        })

    return {
        "workspace": repo.workspace,
        "rows": rows,
        "counts": {
            "areas": len({r["area"] for r in rows}),
            "rows": len(rows),
            "retryable": len([r for r in rows if r["retry_safe"]]),
            "needs_a_person": len([r for r in rows if not r["retry_safe"]]),
        },
        "clean": not rows,
        # What this view cannot see, said rather than implied. A health
        # screen that looks clean because it was not watching is worse
        # than none.
        "unwatched": [
            {"area": "enrichment",
             "why": "no provider is called in this build, so there are no "
                    "enrichment failures to report"},
            {"area": "scheduler",
             "why": "nothing runs on a timer: a weekly run happens when "
                    "somebody asks for one"},
        ],
    }


# ------------------------------------------------------------ ICP review
#
# The queue of companies the engine declined to call either way, plus the ones
# a human has already ruled on. PLAYBOOK section 1: `review` and `unknown` both
# mean zero person credits "until a human decides", so this is the screen where
# that decision gets made and recorded.
#
# Nothing here scores anything. The verdict, the confidence, the missing
# evidence and the contradictions all come off `icp.score` via the stored
# qualification, and whether the decision would actually unlock any spending
# comes off `dmplan.may_enrich` - the same gate the enrichment step asks.

REVIEW_STATUSES = (icp.REVIEW, icp.UNKNOWN)


# What the page shows when nobody has asked for anything. A review queue that
# opens on every company puts the two that need a decision underneath twenty-six
# that do not, and a queue you have to filter before it is a queue is a list.
AWAITING = "awaiting"

# The explicit opt-out from the default. Spelled rather than expressed as an
# empty string, so a link to "everything" is readable in the address bar and a
# blank `?status=` does not quietly mean something different from no `?status=`
# at all.
EVERYTHING = "all"


def icp_queue(repo, status=None, batch=None, decided=None):
    """Companies awaiting an ICP decision, and what deciding would change.

    `status` narrows to one ICP status - or to `awaiting`, which is the
    default and means the two the engine declined to call either way. `batch`
    narrows to one batch, and `decided` to `"yes"` or `"no"`.

    The default is deliberate. "What is left for me to decide" is the question
    this screen exists to answer, and answering it with every company in the
    workspace makes the reader do the filtering.
    """
    if status is None and decided is None:
        status = AWAITING
    config = repo.config()
    rows, counts = [], {s: 0 for s in icp.STATUSES}
    reviewed = 0
    for rec in repo.records(batch=batch):
        qualification = rec.get("qualification") or {}
        verdict = qualification.get("verdict") or {}
        if not verdict:
            continue
        counts[verdict.get("icp_status")] = counts.get(
            verdict.get("icp_status"), 0) + 1
        review = qualify.review_of(rec)
        stale = qualify.stale_review_of(rec)
        if review:
            reviewed += 1
        if status == AWAITING:
            if verdict.get("icp_status") not in REVIEW_STATUSES:
                continue
        elif status and status != EVERYTHING:
            if verdict.get("icp_status") != status:
                continue
        if decided == "yes" and not review:
            continue
        if decided == "no" and review:
            continue
        rows.append(_icp_row(repo, rec, qualification, verdict, review, stale,
                             config))
    rows.sort(key=lambda r: (r["decided"], -(r["score"] or 0), r["domain"]))
    return {
        "rows": rows,
        "counts": counts,
        "reviewed": reviewed,
        "awaiting": sum(counts.get(s, 0) for s in REVIEW_STATUSES) - sum(
            1 for r in rows if r["decided"] and r["status"] in REVIEW_STATUSES),
        "statuses": list(icp.STATUSES),
        "status": status,
        "decided_filter": decided,
        "awaiting_statuses": list(REVIEW_STATUSES),
        "batches": sorted(repo.batches()),
        "can_decide": repo.may(ws.APPROVALS_REVIEW),
        # Named on the page rather than assumed. Whether an acceptance unlocks
        # anything at all is a property of the client's config, and an operator
        # clicking "accept" deserves to know in advance which of the two things
        # it will do.
        "review_enrichment_allowed": dmplan.settings(config)[
            "allow_review_enrichment"],
    }


def _sentence(item):
    """One human-readable line, whatever shape the engine returned."""
    if isinstance(item, dict):
        return str(item.get("why") or item.get("what") or item.get("dimension")
                   or item)
    return str(item)


def _icp_row(repo, rec, qualification, verdict, review, stale, config):
    """One company in the review queue, with the reasons it is here."""
    segment = qualification.get("segment") or {}
    cost = qualification.get("cost_plan") or {}
    # The real gate, asked rather than guessed. `may_enrich` wants the batch
    # approval too; passing an empty batch answers "what does the ICP side of
    # this say", which is what this screen is about, and the reason string
    # names the other gate when that is what is blocking.
    allowed, why = dmplan.may_enrich({}, [], rec, verdict, config)
    return {
        "record_id": rec.get("id"),
        "domain": rec.get("domain"),
        "company": rec.get("company"),
        "batch": rec.get("batch") or rec.get("batch_id"),
        "status": verdict.get("icp_status"),
        "tier": verdict.get("icp_tier"),
        "score": verdict.get("icp_score"),
        "confidence": verdict.get("icp_confidence"),
        "why": (verdict.get("classification_reasons") or [None])[0],
        "vertical": segment.get("vertical"),
        "subvertical": segment.get("subvertical"),
        "country": segment.get("country"),
        "employee_band": segment.get("employee_band"),
        # Flattened to sentences here rather than in the template. `icp.score`
        # returns gaps as plain strings and contradictions as dicts, and a
        # renderer that has to know which is which is a renderer one shape
        # change away from a 500.
        "missing_evidence": [_sentence(g)
                             for g in verdict.get("missing_evidence") or []],
        "contradictions": [_sentence(c)
                           for c in verdict.get("contradictions") or []],
        "positive_signals": list(verdict.get("positive_signals") or [])[:4],
        "negative_signals": list(verdict.get("negative_signals") or [])[:4],
        "planned_contacts": cost.get("planned_contacts") or 0,
        "expected_credits": cost.get("expected_credits") or 0,
        "maximum_credits": cost.get("maximum_credits") or 0,
        "state": qualify.state_of(rec),
        "decided": bool(review),
        "review": review,
        "stale_review": stale,
        "enrichment_allowed": allowed,
        "enrichment_reason": why,
        # What the form sends back, so a decision applies to the verdict that
        # was on the screen rather than to whatever the record says now.
        "fingerprint": qualification.get("inputs_fingerprint"),
    }


class ReviewRefused(RuntimeError):
    """The decision was not applied, and the reason says which gate stopped it."""


def decide_icp(repo, record_id, decision, fingerprint, by, note=""):
    """Record one human decision on one company's verdict.

    Refuses a stale fingerprint with the same reasoning the campaign approval
    uses: the page showed a verdict, and "accept" has to mean "accept *that*".
    A verdict that changed after the page rendered is a different question.
    """
    repo.require(ws.APPROVALS_REVIEW)
    rec = repo.record(record_id)
    if rec is None:
        return None
    qualification = rec.get("qualification") or {}
    if not qualification:
        raise ReviewRefused("this company has not been qualified yet")
    current = qualification.get("inputs_fingerprint")
    if fingerprint and current and fingerprint != current:
        raise ReviewRefused(
            "the verdict changed after this page was rendered; reload and "
            "look at what it says now before deciding")
    review = qualify.record_review(rec, decision, by=by, note=note)
    repo.save_records([rec])
    repo.audit("icp.reviewed", "record", record_id,
               before={"status": review["reviewed_status"],
                       "decided": False},
               after={"status": review["reviewed_status"],
                      "decision": review["decision"]},
               reason=review["note"] or None)
    return review


def company_dossier(repo, record_id):
    """Everything known about one company, before or after enrichment."""
    rec = repo.record(record_id)
    if rec is None:
        return None
    config = repo.config()
    qualification = rec.get("qualification") or {}
    entry = {
        "record": rec,
        "segment": qualification.get("segment") or segments.classify(rec, config),
        "verdict": qualification.get("verdict") or icp.score(rec, config),
        "persona_plan": qualification.get("persona_plan") or {},
        "messaging": qualification.get("messaging") or {},
        "cost_plan": qualification.get("cost_plan") or {},
        "segment_key": qualification.get("segment_key"),
    }
    detail = qualify.dossier(entry, config)
    detail["contacts"] = [contact_view(repo, record_id, c.get("key"))
                          for c in rec.get("contacts") or []]
    detail["events"] = list(rec.get("events") or [])[-40:]
    detail["log"] = list(rec.get("log") or [])[-40:]
    detail["excluded"] = list(rec.get("excluded") or [])
    return detail


# --------------------------------------------------------------- contacts

def contact_rows(repo, batch=None, mode=None, flag=None):
    """The contact review table. Every row carries its exact reasons.

    Two things are read once rather than per contact. `channels.evaluate`
    loads the suppression file whenever it is not handed one, and
    `policy_for` rebuilds the verification policy from config on every
    call - both invisible at demo scale and both once per contact across
    an estate. At 30,000 records this loop took 7.5 seconds.
    """
    config = repo.config()
    suppressed = ingest.load_suppress()
    policy = verification.policy_for(config)
    out = []
    for rec in repo.records(batch=batch):
        for contact in rec.get("contacts") or []:
            verdicts = channels.evaluate(rec, contact, config,
                                         suppressed)
            decision = (verification.resolve(contact, policy)
                        if contact.get("email") else {})
            stored = mx.stored_decision(contact) or {}
            row = {
                "record_id": rec["id"],
                "contact_key": contact.get("key"),
                "name": contact.get("name"),
                "title": contact.get("title"),
                "persona": contact.get("persona"),
                "company": rec.get("company"),
                "domain": rec.get("domain"),
                "batch": rec.get("batch"),
                "email": contact.get("email"),
                "linkedin": contact.get("linkedin"),
                # The columns the import kept and never read. Carried so
                # the export can hand them back - a phone number the file
                # arrived with is otherwise stored, reported on the preview
                # as kept, and reachable by nobody.
                "source": dict(contact.get("source") or {}),
                "oldest_evidence_days": (
                    verification.age_of(contact)["oldest_days"]
                    if contact.get("email") else None),
                "mode": verdicts["mode"],
                "held": verdicts["held"],
                "email_eligible": verdicts["email_eligible"],
                "email_reason": verdicts["email_excluded_reason"],
                "email_reason_text": channels.explain(
                    verdicts["email_excluded_reason"]),
                "linkedin_eligible": verdicts["linkedin_eligible"],
                "linkedin_reason": verdicts["linkedin_excluded_reason"],
                "linkedin_reason_text": channels.explain(
                    verdicts["linkedin_excluded_reason"]),
                "confirmations": decision.get("confirmation_count"),
                "required": decision.get("required_confirmations"),
                "disagreement": bool(decision.get("disagreement")),
                "mx_provider": (stored.get("security_provider")
                                or stored.get("mailbox_provider")),
                "mx_category": stored.get("category"),
            }
            if mode and row["mode"] != mode:
                continue
            if flag and not _flag_matches(row, flag):
                continue
            out.append(row)
    return out


FLAGS = ("held", "mx_blocked", "disagreement", "no_email", "no_linkedin",
         "single_verified", "multichannel")


def _flag_matches(row, flag):
    if flag == "held":
        return row["held"]
    if flag == "mx_blocked":
        return str(row.get("email_reason") or "").startswith("mx_protection")
    if flag == "disagreement":
        return row["disagreement"]
    if flag == "no_email":
        return not row.get("email")
    if flag == "no_linkedin":
        return not row.get("linkedin")
    if flag == "single_verified":
        required = row.get("required") or 0
        return (row.get("confirmations") or 0) < required
    if flag == "multichannel":
        return row["mode"] == channels.MULTICHANNEL
    return True


def contact_view(repo, record_id, contact_key):
    """One contact, with every gate's answer and the evidence behind it."""
    rec, contact = repo.contact(record_id, contact_key)
    if rec is None or contact is None:
        return None
    config = repo.config()
    policy = verification.policy_for(config)
    verdicts = channels.evaluate(rec, contact, config)
    decision = verification.resolve(contact, policy) if contact.get("email") else {}
    block = contact.get("verification") or {}
    stored = mx.stored_decision(contact) or {}

    return {
        "record_id": rec["id"],
        "contact_key": contact.get("key"),
        "name": contact.get("name"),
        "title": contact.get("title"),
        "persona": contact.get("persona"),
        "angle": contact.get("angle"),
        "company": rec.get("company"),
        "domain": rec.get("domain"),
        "mode": verdicts["mode"],
        "held": verdicts["held"],
        "email": {
            "address": contact.get("email"),
            "eligible": verdicts["email_eligible"],
            "reason": verdicts["email_excluded_reason"],
            "reason_text": channels.explain(verdicts["email_excluded_reason"]),
            "sendable": lint.sendable(contact),
            "state": decision.get("state"),
            "why": decision.get("reason"),
            "confirmations": decision.get("confirmation_count"),
            "required": decision.get("required_confirmations"),
            "confirmed_by": decision.get("confirmed_by") or [],
            "disagreement": bool(decision.get("disagreement")),
            "results": block.get("results") or {},
            "providers": block.get("providers") or [],
            # How old the evidence is. There is no freshness rule in this
            # build - nobody has chosen how long a verification is good
            # for - and this is what makes that question answerable rather
            # than answering it. `MANUAL-REVIEW.md` 9b.
            "age": (verification.age_of(contact)
                    if contact.get("email") else None),
        },
        "mx": {
            "provider": (stored.get("security_provider")
                         or stored.get("mailbox_provider")),
            "category": stored.get("category"),
            "status": stored.get("status"),
            "hosts": stored.get("hosts") or [],
            "allows_email": mx.allows_email(contact, config)[0],
            "reason": mx.block_reason(contact, config),
        },
        "linkedin": {
            "url": contact.get("linkedin"),
            "eligible": verdicts["linkedin_eligible"],
            "reason": verdicts["linkedin_excluded_reason"],
            "reason_text": channels.explain(
                verdicts["linkedin_excluded_reason"]),
        },
        "evidence": _evidence(rec, contact_key),
        "personalization": _personalization(rec, contact, config),
        # Both channels in one column. The reason it belongs here rather
        # than on its own screen: "what have they already received, and
        # did they answer" is the question the gates above are being read
        # in service of.
        "conversation": conversation.thread(rec, contact_key,
                                            workspace=repo.workspace),
        "also_known": conversation.also_known(repo.records(), rec, contact),
    }


def _evidence(rec, contact_key):
    company, person = [], []
    for item in rec.get("research") or []:
        row = {
            "fact": item.get("fact"),
            "provider": item.get("provider"),
            "source_type": item.get("source_type"),
            "source_url": item.get("source_url"),
            "published_at": item.get("published_at"),
            "retrieved_at": item.get("retrieved_at"),
            "freshness": item.get("freshness_bucket"),
            "relevance": item.get("relevance_score"),
            "quality": item.get("quality"),
            "evidence_id": item.get("evidence_id"),
        }
        (person if item.get("contact_key") == contact_key else company).append(row)
    return {"company": company, "person": person,
            "person_note": ("empty by design: no person-level web research "
                            "provider is authorised in this build")}


def _personalization(rec, contact, config):
    from .. import quality
    assessed = quality.assess(rec, contact, config)
    return {
        "band": assessed.get("band"),
        "components": assessed.get("components") or {},
        "why": assessed.get("why"),
        "evidence_count": assessed.get("evidence_count"),
        "meets_minimum": assessed.get("meets_minimum"),
        "angle": contact.get("angle"),
        "persona": contact.get("persona"),
    }


# ------------------------------------------------------------- the cadence

def outreach(repo, record_id, contact_key, campaign=None):
    """The final expanded cadence, every step, with each gate's answer."""
    rec, contact = repo.contact(record_id, contact_key)
    if rec is None or contact is None:
        return None
    config = repo.config()
    # Read once. `channels.evaluate` loads the suppression file
    # whenever it is not handed one, which across an estate is
    # once per contact.
    suppressed = ingest.load_suppress()
    recs = repo.records()
    # Cross-channel on, because this is the screen where a person decides
    # whether they would send this - and a preview that hid the reference
    # would be a preview of a different message from the one that goes out.
    timeline = cadence.build(rec, config, recs=recs, workspace=repo.workspace,
                             campaign=campaign, cross_channel=True)
    steps = (timeline.get("contacts") or {}).get(contact_key) or {}
    verdicts = channels.evaluate(rec, contact, config, suppressed)
    senders = assignment.describe(contact)

    rendered = []
    for step_key, step in sorted(steps.items(),
                                 key=lambda kv: kv[1].get("day") or 0):
        channel = step.get("channel")
        text = step.get("note") if channel == "linkedin" else step.get("body")
        failures = lint.check_step(rec, contact_key, step)
        decision = eligibility.decide(rec, contact, step_key, channel=channel,
                                      campaign=campaign, recs=recs,
                                      config=config, step=step)
        cross = step.get("cross_channel") or {}
        assigned = senders.get(channel) or {}
        rendered.append({
            "step": step_key,
            "day": step.get("day"),
            "channel": channel,
            "provider": "EmailBison" if channel == "email" else "HeyReach",
            # Who this step goes out as. The human first, because that is the
            # name in the copy; the account second, because that is what the
            # provider receives.
            "sender": assigned or None,
            # Whether this step may refer to the other channel, and the
            # sentence explaining either answer. Both travel, so a screen
            # cannot show the claim without the evidence.
            "cross_channel": {
                "may_reference": bool(cross.get("may_reference")),
                "reason": cross.get("reference_reason"),
                "explanation": touch.explain(cross) if cross else None,
                "reference": cross.get("reference"),
                "applied": step.get("cross_channel_applied"),
                "previous": cross.get("confirmed_previous_touches") or [],
            } if cross else None,
            "status": step.get("status"),
            "blocked_by": step.get("blocked_by"),
            "subject": step.get("subject"),
            "text": text,
            "words": len((text or "").split()),
            "characters": len(text or ""),
            "angle": step.get("angle") or contact.get("angle"),
            "generated": bool(step.get("generated")),
            "template": step.get("template"),
            "requires": step.get("requires"),
            "lint": failures,
            "lint_ok": not failures,
            "eligible": bool(decision.eligible),
            "eligibility_reasons": decision["reasons"],
        })

    paused = timeline.get("paused")
    return {
        "record_id": rec["id"],
        "contact_key": contact_key,
        "name": contact.get("name"),
        "company": rec.get("company"),
        "mode": verdicts["mode"],
        "paused": bool(paused),
        "pause_reason": (paused or {}).get("reason"),
        "steps": rendered,
        "senders": senders,
        "assignment_stale": assignment.is_stale(contact, repo.workspace),
        # The canonical history, beside the plan. `cadence` says what is meant
        # to happen; this says what did.
        "history": touch.history(rec, contact_key, steps, config),
        "coherence": coherence.for_contact(rec, contact_key, timeline, config,
                                           channel_verdict=verdicts),
        "duplicates": duplicates.for_contact(rec, contact_key, timeline, config),
        "schedule": _schedule_for(rec, config),
    }


def _schedule_for(rec, config):
    segment = segments.classify(rec, config)
    start = TODAY + datetime.timedelta(days=4)
    return schedule.for_company(segment, start, config)


def timezone_preview(repo):
    """The same campaign in four cities, to show DST-safe local scheduling."""
    config = repo.config()
    return schedule.demo(TODAY + datetime.timedelta(days=4), config)


# ------------------------------------------------------------- campaigns

def campaign_rows(repo):
    """Every campaign with its size and state.

    The estate is read once and indexed by id. This used to call
    `repo.records()` inside the loop - a full parse of the queue per
    campaign - and then test membership against `record_ids`, which is a
    *list*, so the scan was O(records x ids) on top. At 30,000 records and
    8 campaigns that was 9.9 seconds; the load itself is 0.3.
    """
    config = repo.config()
    known = {r["id"]: r for r in repo.records()}
    out = []
    for campaign in repo.campaigns():
        wanted = set(campaign.get("record_ids") or [])
        recs = [known[rid] for rid in wanted if rid in known]
        out.append({
            "campaign_id": campaign.get("campaign_id"),
            "name": campaign.get("name"),
            "status": campaign.get("status"),
            "records": len(recs),
            "approval": (campaign.get("approval") or {}).get("action"),
            "fingerprint": campaign.get("fingerprint"),
            "bison_campaign_id": campaign.get("bison_campaign_id"),
            "heyreach_campaign_id": campaign.get("heyreach_campaign_id"),
            "launch": (campaign.get("launch") or {}).get("state"),
            "paused": bool((campaign.get("pause") or {}).get("since")),
            "pause_reason": (campaign.get("pause") or {}).get("reason"),
            "pause_since": (campaign.get("pause") or {}).get("since"),
        })
    return out


# ------------------------------------------------------- campaign builder
#
# A campaign is a segment plus a name. Everything else about it - who is in it,
# which persona, which angle, which channels, what it will cost - was already
# decided upstream by `campaignseg.assign`, `routing.plan`, `strategy` and
# `channels.evaluate`. The builder's whole job is to show what those decided
# and let a person say yes to it.
#
# It deliberately cannot decide anything. There is no field on this screen that
# overrides a segment, moves a company between campaigns or changes a persona:
# a builder that let an operator hand-pick a population would be a second
# answer to "who belongs together", and `campaignseg.why_together` is the
# first one.

def campaign_builder(repo, segment_key=None, batch=None):
    """The segments that could become a campaign, and what each one contains.

    Read-only. Nothing is created until `create_campaign` is called, and this
    is what an operator reads before deciding to call it.
    """
    config = repo.config()
    # Read once. `channels.evaluate` loads the suppression file
    # whenever it is not handed one, which across an estate is
    # once per contact.
    suppressed = ingest.load_suppress()
    taken = {}
    for campaign in repo.campaigns():
        for record_id in campaign.get("record_ids") or []:
            taken[record_id] = campaign.get("campaign_id")

    buckets = {}
    for rec in repo.records(batch=batch):
        qualification = rec.get("qualification") or {}
        key = qualification.get("segment_key")
        if not key:
            continue
        bucket = buckets.setdefault(key, {
            "segment_key": key,
            "rung": qualification.get("segment_rung"),
            "reason": qualification.get("segment_reason"),
            "parts": qualification.get("segment_parts") or {},
            "record_ids": [], "companies": 0, "contacts": 0,
            "personas": {}, "angles": {}, "modes": {},
            "countries": {}, "timezones": {}, "verticals": {},
            "already_in": {},
            "expected_credits": 0, "maximum_credits": 0,
        })
        bucket["companies"] += 1
        bucket["record_ids"].append(rec["id"])
        if rec["id"] in taken:
            where = taken[rec["id"]]
            bucket["already_in"][where] = bucket["already_in"].get(where, 0) + 1

        segment = qualification.get("segment") or {}
        cost = qualification.get("cost_plan") or {}
        bucket["expected_credits"] += cost.get("expected_credits") or 0
        bucket["maximum_credits"] += cost.get("maximum_credits") or 0
        _bump(bucket["verticals"], segment.get("vertical"))
        _bump(bucket["countries"], segment.get("country"))
        _bump(bucket["timezones"], segment.get("timezone"))

        for contact in rec.get("contacts") or []:
            if not contact.get("selected"):
                continue
            bucket["contacts"] += 1
            _bump(bucket["personas"], contact.get("persona"))
            _bump(bucket["angles"], contact.get("angle"))
            # The channel verdict, asked rather than recomputed.
            bucket_mode = channels.evaluate(rec, contact, config, suppressed)["mode"]
            _bump(bucket["modes"], bucket_mode)

    rows = sorted(buckets.values(),
                  key=lambda b: (-b["companies"], b["segment_key"]))
    for row in rows:
        row["unassigned"] = row["companies"] - sum(row["already_in"].values())
        row["buildable"] = row["unassigned"] > 0

    chosen = None
    for row in rows:
        if row["segment_key"] == segment_key:
            chosen = _builder_detail(repo, row, config)
    return {
        "segments": rows,
        "chosen": chosen,
        "batches": sorted(repo.batches()),
        "batch": batch,
        "can_create": repo.may(ws.CAMPAIGN_CREATE),
        "min_segment_size": campaignseg.settings(config)["min_segment_size"],
        "sender_strategy": sender_strategy(repo, chosen),
    }


def sender_strategy(repo, chosen=None):
    """What this campaign's outreach would go out as, and whether it fits.

    Capacity is the interesting part and it is deliberately asymmetric: a
    workspace with a hundred inboxes and six LinkedIn profiles cannot plan the
    two channels against one number. Where a limit is unknown it stays
    unknown, and the warning says which accounts are missing one rather than
    filling the gap with a default.
    """
    config = repo.config()
    roster = senderidentity.roster(repo.workspace, config=config)
    capacity = roster["capacity"]
    companies = (chosen or {}).get("company_count") or 0
    contacts = (chosen or {}).get("contacts") or 0

    # One email step per contact per email step in the cadence, and likewise
    # for LinkedIn. Counted from `cadence.STEPS` rather than assumed, so a
    # cadence change moves this number with it.
    email_steps = len([s for s in cadence.STEPS if s["channel"] == "email"])
    li_steps = len([s for s in cadence.STEPS if s["channel"] == "linkedin"])

    warnings = []
    for channel, per_contact in (("email", email_steps),
                                 ("linkedin", li_steps)):
        cap = capacity[channel]
        if not cap["accounts"]:
            warnings.append(
                f"no active {channel} account: this campaign cannot send on "
                f"{channel} at all")
            continue
        if not cap["complete"]:
            warnings.append(
                f"{cap['accounts_with_no_known_limit']} {channel} account(s) "
                "have no configured daily limit, so the capacity below is a "
                "partial sum and not a ceiling")
        if cap["complete"] and contacts and cap["known_daily_capacity"] < contacts:
            warnings.append(
                f"{contacts} contacts against {cap['known_daily_capacity']} "
                f"{channel} sends a day: this campaign takes at least "
                f"{-(-contacts // max(1, cap['known_daily_capacity']))} days "
                "to work through once")

    return {
        "roster": roster["counts"],
        "capacity": capacity,
        "pairings": roster["pairings"],
        "senders": [
            {"sender_id": p["sender_id"], "display_name": p["display_name"],
             "email_accounts": p["active_email_accounts"],
             "linkedin_accounts": p["active_linkedin_accounts"]}
            for p in roster["senders"] if p["active"]],
        "planned": {
            "companies": companies,
            "contacts": contacts,
            "email_touches": contacts * email_steps,
            "linkedin_touches": contacts * li_steps,
            "email_steps_per_contact": email_steps,
            "linkedin_steps_per_contact": li_steps,
        },
        "warnings": warnings,
        # The three switches the brief asks for. They are read from the client
        # config rather than set on the form, because every one of them is a
        # statement about what a client will let us say to their prospects -
        # and none of them can override the touch history either way.
        "options": {
            "colleague_language": bool(
                (config.get("sender_policy") or {}).get("colleague_language")),
            "cross_channel_continuity": True,
            "same_sender_continuity": True,
        },
    }


# --------------------------------------------------- reporting by sender

def sender_report(repo, dimension="sender_pair"):
    """Outreach outcomes grouped by who sent it.

    Every row carries its denominator, and there are two. `contactable_rate`
    is against contacts assigned to that sender. `reply_rate` and
    `positive_rate` are against contacts actually *reached* - a confirmed
    touch on either channel - because a sender who was given twenty
    prospects and has reached none of them has no reply rate, not a rate of
    zero. Nothing outside the demo estate writes a confirmed touch, so
    those two read `0 of 0` today and the page says so.

    Nothing here is a rate this build can stand behind at these sample sizes,
    and the page says so. What it is for is the shape: which pair, how many,
    how many came back.
    """
    config = repo.config()
    # Read once. `channels.evaluate` loads the suppression file
    # whenever it is not handed one, which across an estate is
    # once per contact.
    from .. import events as event_model

    suppressed = ingest.load_suppress()
    rows = {}
    for rec in repo.records():
        # One message, one reply. `replies.apply` writes a
        # `reply_classified` beside every `reply_received` it reads, and a
        # `positive_reply_detected` beside a positive one - so counting the
        # types together reported every reply twice and every positive
        # twice. `tests/test_web_analytics.py` calls this out as a bug that
        # was found and fixed in the workspace card; it was still here.
        #
        # The receipt is the message arriving, which is the same convention
        # `reply_rows` and `report.for_client` use.
        replies_by_contact, positive_by_contact = {}, {}
        for entry in rec.get("events") or []:
            key = entry.get("contact")
            if entry.get("type") == event_model.REPLY_RECEIVED:
                replies_by_contact[key] = replies_by_contact.get(key, 0) + 1
            elif entry.get("type") == event_model.POSITIVE_REPLY_DETECTED:
                positive_by_contact[key] = positive_by_contact.get(key, 0) + 1

        for contact in rec.get("contacts") or []:
            if not contact.get("selected"):
                continue
            block = assignment.stored(contact)
            key = _sender_key(block, dimension)
            bucket = rows.setdefault(key, {
                "key": key, "contacts": 0, "contactable": 0,
                "confirmed_email": 0, "confirmed_linkedin": 0,
                "replies": 0, "positive": 0, "meetings": 0})
            bucket["contacts"] += 1
            if channels.evaluate(rec, contact, config, suppressed)["mode"] != channels.NONE:
                bucket["contactable"] += 1
            for step in touch.timeline_rows(rec, contact.get("key")):
                if not step["confirmed"]:
                    continue
                if step["channel"] == "email":
                    bucket["confirmed_email"] += 1
                elif step["channel"] == "linkedin":
                    bucket["confirmed_linkedin"] += 1
            bucket["replies"] += replies_by_contact.get(contact.get("key"), 0)
            bucket["positive"] += positive_by_contact.get(contact.get("key"), 0)

    out = []
    for bucket in rows.values():
        reached = bucket["confirmed_email"] + bucket["confirmed_linkedin"]
        out.append({
            **bucket,
            "reached": reached,
            # Pairs, never bare percentages. The denominator for a reply rate
            # is contacts we actually reached, not contacts we assigned.
            "reply_rate": (bucket["replies"], reached),
            "positive_rate": (bucket["positive"], reached),
            "contactable_rate": (bucket["contactable"], bucket["contacts"]),
        })
    out.sort(key=lambda r: (-r["contacts"], r["key"]))
    return {
        "dimension": dimension,
        "dimensions": SENDER_DIMENSIONS,
        "rows": out,
        "note": ("Sample sizes here are small and nothing has been sent from "
                 "this build, so these are the shape of the assignment rather "
                 "than a result. No significance is claimed or computed."),
    }


SENDER_DIMENSIONS = (
    ("sender_pair", "Sender pair (email + LinkedIn)"),
    ("email_sender", "Email human"),
    ("email_account", "Email inbox"),
    ("linkedin_sender", "LinkedIn human"),
    ("linkedin_account", "LinkedIn account"),
)


def _sender_key(block, dimension):
    email = block.get("email") or {}
    linkedin = block.get("linkedin") or {}
    return {
        "sender_pair": f"{email.get('sender_id') or 'none'}"
                       f" + {linkedin.get('sender_id') or 'none'}",
        "email_sender": email.get("sender_id") or "unassigned",
        "email_account": email.get("account_id") or "unassigned",
        "linkedin_sender": linkedin.get("sender_id") or "unassigned",
        "linkedin_account": linkedin.get("account_id") or "unassigned",
    }.get(dimension, "unassigned")


def _bump(counter, value):
    if value in (None, ""):
        value = "unknown"
    counter[value] = counter.get(value, 0) + 1


def _builder_detail(repo, row, config):
    """One segment, opened up: who is in it, and why they are together.

    The "why" is `campaignseg.why_together`, not a sentence written here. A
    builder that explained the grouping in its own words would be explaining
    something other than what produced it.
    """
    recs = [repo.record(rid) for rid in row["record_ids"]]
    recs = [r for r in recs if r is not None]
    entries = []
    for rec in recs:
        qualification = rec.get("qualification") or {}
        entries.append({
            "record": rec,
            "segment": qualification.get("segment") or {},
            "verdict": qualification.get("verdict") or {},
            "persona_plan": qualification.get("persona_plan") or {},
            # The four fields `campaignseg.assign` wrote, handed back in the
            # shape it produced them. `why_together` reads them by name, and
            # rebuilding them here would be re-deciding the grouping.
            "segment_key": qualification.get("segment_key"),
            "segment_parts": qualification.get("segment_parts") or {},
            "segment_rung": qualification.get("segment_rung"),
            "segment_reason": qualification.get("segment_reason"),
        })
    together = None
    if len(entries) >= 2 and entries[0].get("segment_parts"):
        together = campaignseg.why_together(entries[0], entries[1], config)

    in_campaign = {}
    for campaign in repo.campaigns():
        for record_id in campaign.get("record_ids") or []:
            in_campaign[record_id] = campaign.get("campaign_id")

    companies = []
    for entry in entries[:60]:
        rec = entry["record"]
        selected = [c for c in rec.get("contacts") or [] if c.get("selected")]
        companies.append({
            "record_id": rec["id"],
            "company": rec.get("company"),
            "domain": rec.get("domain"),
            "tier": entry["verdict"].get("icp_tier"),
            "score": entry["verdict"].get("icp_score"),
            "country": entry["segment"].get("country"),
            "timezone": entry["segment"].get("timezone"),
            "contacts": len(selected),
            "personas": sorted({c.get("persona") for c in selected
                                if c.get("persona")}),
            "in_campaign": in_campaign.get(rec["id"]),
        })

    return {
        **row,
        "company_rows": companies,
        "company_count": row["companies"],
        "shown": len(companies),
        "why_together": together,
        # A suggested id and name the operator may replace. Derived from the
        # segment key, so two campaigns off one segment cannot collide.
        "suggested_id": _campaign_id_for(repo, row["segment_key"]),
        "suggested_name": str(row["segment_key"]).replace("_", " ").title(),
    }


def _campaign_id_for(repo, segment_key):
    """A slug that is not already taken in this workspace."""
    base = re.sub(r"[^a-z0-9]+", "-", str(segment_key).lower()).strip("-")
    base = base[:48] or "campaign"
    taken = {c.get("campaign_id") for c in repo.campaigns()}
    if base not in taken:
        return base
    for n in range(2, 100):
        candidate = f"{base}-{n}"
        if candidate not in taken:
            return candidate
    return base


class BuildRefused(RuntimeError):
    """The campaign was not created, and the message says what stopped it."""


def create_campaign(repo, segment_key, name, campaign_id=None, by="unknown",
                    batch=None):
    """Create one draft campaign from one segment. Sends nothing.

    Every company in the segment that is not already in a campaign joins this
    one. A record cannot be in two campaigns: `campaigns.check_no_duplicate_
    pushes` would catch that later, but catching it later means the copy was
    already written twice and somebody already read it.
    """
    repo.require(ws.CAMPAIGN_CREATE)
    if not segment_key:
        raise BuildRefused("pick a segment first")
    name = (name or "").strip()[:120]
    if not name:
        raise BuildRefused("a campaign needs a name a person will recognise")

    taken = set()
    for campaign in repo.campaigns():
        taken.update(campaign.get("record_ids") or [])

    record_ids, batches = [], set()
    for rec in repo.records(batch=batch):
        qualification = rec.get("qualification") or {}
        if qualification.get("segment_key") != segment_key:
            continue
        if rec["id"] in taken:
            continue
        record_ids.append(rec["id"])
        batches.add(rec.get("batch") or rec.get("batch_id"))
    if not record_ids:
        raise BuildRefused(
            "every company in this segment is already in a campaign, and a "
            "record in two campaigns is one person written to twice")

    campaign_id = (campaign_id or "").strip() or _campaign_id_for(repo,
                                                                  segment_key)
    if not repo_module.valid_slug(campaign_id):
        raise BuildRefused(
            f"{campaign_id!r} is not a usable campaign id: lower-case letters, "
            "digits, hyphens and underscores, up to 64 characters")
    if repo.campaign(campaign_id) is not None:
        raise BuildRefused(f"a campaign called {campaign_id!r} already exists")

    sample = repo.record(record_ids[0])
    segment = (sample.get("qualification") or {}).get("segment") or {}
    personas = sorted({
        contact.get("persona")
        for record_id in record_ids
        for contact in (repo.record(record_id).get("contacts") or [])
        if contact.get("selected") and contact.get("persona")})

    campaign = campaign_store.new_campaign(
        campaign_id, repo.client, name,
        batch_id=next(iter(sorted(b for b in batches if b)), None),
        created_by=by, personas=personas,
        geos=sorted({c for c in [segment.get("country")] if c}))
    campaign["record_ids"] = record_ids
    campaign["segment_key"] = segment_key
    # Volumes come from the client config, not from this form. A daily send
    # limit is a deliverability decision, and a campaign form is a strange
    # place to make one.
    sending = campaign_store.sending_config(repo.config())
    campaign["daily_volume"] = {
        "email": sending.get("daily_email_volume") or 0,
        "linkedin": sending.get("daily_linkedin_volume") or 0,
    }
    campaign_store.log(campaign, "created",
                       f"built from segment {segment_key}", by=by,
                       records=len(record_ids))
    # Prepared, not left a draft. `orchestrator.prepare` is the only thing
    # that sets `ready_for_review`, and it was unreachable from the web -
    # so a campaign built in the product went draft straight to approved,
    # and `tasks.py`, which files its rows for `ready_for_review` and
    # `awaiting_approval`, never mentioned a campaign awaiting approval.
    # The screen the product calls "everything waiting" was silently
    # missing its most consequential row.
    #
    # It is also the only caller of `assign_cadence_arms`, whose own
    # docstring explains that assignment happens before the approval
    # fingerprint "so what a reviewer approves already includes which arm
    # each contact is in". No campaign built in the product had an arm at
    # all, and the fingerprint a reviewer signed omitted them.
    #
    # `prepare` mutates the records, so they are saved with it. A refusal
    # is surfaced as a refusal rather than swallowed: a campaign that
    # cannot be prepared is not one to leave sitting as a draft that
    # nobody will be told about.
    # Deferred, the way every other `orchestrator` use in this module
    # is: it imports back into the web layer.
    from .. import orchestrator

    mine = [r for r in repo.records() if r["id"] in set(record_ids)]
    try:
        orchestrator.prepare(campaign, mine, repo.config())
    except orchestrator.NotReady as e:
        raise BuildRefused(f"the campaign could not be prepared: {e}")
    repo.save_records(mine)
    repo.save_campaign(campaign)
    repo.audit("campaign.created", "campaign", campaign_id,
               after={"name": name, "segment_key": segment_key,
                      "records": len(record_ids),
                      "status": campaign["status"]},
               reason=f"built from segment {segment_key}")
    return campaign


def campaign_detail(repo, campaign_id):
    campaign = repo.campaign(campaign_id)
    if campaign is None:
        return None
    config = repo.config()
    recs = [r for r in repo.records()
            if r["id"] in (campaign.get("record_ids") or [])]
    contacts = contact_rows(repo)
    mine = [c for c in contacts
            if c["record_id"] in (campaign.get("record_ids") or [])]
    modes = {}
    for row in mine:
        modes[row["mode"]] = modes.get(row["mode"], 0) + 1
    return {
        "campaign": campaign,
        # The audience half of pre-flight. The checklist below answers
        # whether the campaign is in order; this answers who in it could
        # actually receive anything.
        "preflight": campaign_preflight(repo, campaign_id),
        "records": len(recs),
        "contacts": mine,
        "modes": modes,
        "qa": qa.report(campaign, recs, config),
        "validate": campaign_store.validate_rows(campaign, recs, config)
        if hasattr(campaign_store, "validate_rows") else _checklist(campaign, recs, config),
        "mapping": {
            "bison_campaign_id": campaign.get("bison_campaign_id"),
            "heyreach_campaign_id": campaign.get("heyreach_campaign_id"),
            "heyreach_sender_account": (campaign.get("senders") or {})
            .get("linkedin"),
            "status": _mapping_status(campaign),
        },
        # Why these companies, why now, and what a message may say. The
        # rest of this screen answers whether the campaign is in order;
        # this answers whether it should go out at all. Suppression is
        # loaded once here rather than once per contact inside
        # `channels.evaluate`.
        "context": contextpack.build(recs, campaign, repo.workspace, config,
                                     suppressed=ingest.load_suppress()),
        "would_send": 0,
    }


# -------------------------------------------------- full outreach preview
#
# One campaign, every contact, every step of every channel, with the reason
# beside anything that will not run. `/campaigns/<id>` answers "is this
# campaign in order"; this answers "what would actually arrive, at whom, on
# what day, and what would not".
#
# Two rules it is built to, both taken from `src/outreachpage.py`, which is the
# CLI prototype of this screen:
#
# **Nothing is silently omitted.** A step that will not run is rendered in
# place with its reason, not dropped. A timeline that quietly loses its blocked
# steps shows a campaign that is not the campaign.
#
# **Every summary number is reachable.** "3 blocked" at the top is a claim; the
# contact cards underneath name the gate, the step and the reason code.

# A full card is a few KB of HTML. 5,000 contacts would be a page no browser
# opens, so the cards are capped and what was left out is stated - a preview
# that silently shows the first fifty and calls it the campaign is worse than
# one that shows fifty and says so.
OUTREACH_CARD_CAP = 40


def full_outreach(repo, campaign_id=None, cap=OUTREACH_CARD_CAP):
    """The whole campaign as it would go out. Sends nothing, spends nothing."""
    campaigns = repo.campaigns()
    listed = [{"campaign_id": c.get("campaign_id"), "name": c.get("name"),
               "status": c.get("status"),
               "contacts": len(c.get("record_ids") or [])}
              for c in campaigns]
    listed.sort(key=lambda c: str(c["name"] or c["campaign_id"]))

    if campaign_id is None and listed:
        campaign_id = listed[0]["campaign_id"]
    campaign = repo.campaign(campaign_id) if campaign_id else None
    if campaign is None:
        return {"campaigns": listed, "campaign": None, "chosen": campaign_id}

    config = repo.config()
    record_ids = list(campaign.get("record_ids") or [])
    recs = [r for r in repo.records() if r["id"] in record_ids]

    cards, totals = [], {
        "contacts": 0, "steps": 0, "email_steps": 0, "linkedin_steps": 0,
        "will_run": 0, "blocked": 0, "lint_failures": 0, "paused_contacts": 0,
        "unlinted_steps": 0,
    }
    modes, blocked_reasons, days = {}, {}, {}
    for rec in recs:
        for contact in rec.get("contacts") or []:
            if not contact.get("selected"):
                continue
            view = outreach(repo, rec["id"], contact.get("key"),
                            campaign=campaign)
            if view is None:
                continue
            totals["contacts"] += 1
            _bump(modes, view["mode"])
            if view["paused"]:
                totals["paused_contacts"] += 1
            for step in view["steps"]:
                totals["steps"] += 1
                if step["channel"] == "email":
                    totals["email_steps"] += 1
                else:
                    totals["linkedin_steps"] += 1
                if step["eligible"]:
                    totals["will_run"] += 1
                    _bump(days, step["day"])
                else:
                    totals["blocked"] += 1
                    for reason in step["eligibility_reasons"] or ["unstated"]:
                        _bump(blocked_reasons, reason)
                if step["lint"]:
                    totals["lint_failures"] += len(step["lint"])
                if not step["generated"]:
                    totals["unlinted_steps"] += 1
            if len(cards) < cap:
                cards.append(view)

    return {
        "campaigns": listed,
        "chosen": campaign_id,
        "campaign": {
            "campaign_id": campaign.get("campaign_id"),
            "name": campaign.get("name"),
            "status": campaign.get("status"),
            "approval": (campaign.get("approval") or {}).get("action"),
            "launch": (campaign.get("launch") or {}).get("state"),
            "companies": len(recs),
            "segment_key": campaign.get("segment_key"),
            "daily_volume": campaign.get("daily_volume") or {},
        },
        "totals": totals,
        "modes": modes,
        # Sorted, and each reason carried with what it means. These are
        # `eligibility`'s codes, so `eligibility.explain` is the engine's own
        # wording for them - a page that paraphrased would be describing a
        # different rule than the one that fired. A code the engine cannot
        # explain comes back unchanged rather than blank, because a reason
        # nobody can put into words is a bug and an empty cell hides it.
        "blocked_reasons": [
            {"reason": reason, "steps": count,
             "means": eligibility.explain(reason)
             or channels.explain(reason) or ""}
            for reason, count in sorted(blocked_reasons.items(),
                                        key=lambda kv: (-kv[1], kv[0]))],
        "days": dict(sorted((k, v) for k, v in days.items() if k is not None)),
        "cards": cards,
        "shown": len(cards),
        "omitted": max(0, totals["contacts"] - len(cards)),
        "cap": cap,
        # The QA report and the provider payloads, from the same functions the
        # campaign screen and the sender use. A preview that redraws either is
        # a preview of something nobody has tested.
        "qa": qa.report(campaign, recs, config),
        "payloads": provider_preview(repo, campaign_id),
    }


def _checklist(campaign, recs, config):
    out = []
    for name, check in campaign_store.CHECKS:
        try:
            ok, detail = check(campaign, recs, config)
        except Exception as e:
            ok, detail = False, f"{type(e).__name__}: {str(e)[:120]}"
        out.append({"name": name, "ok": bool(ok), "detail": detail})
    return out


def _mapping_status(campaign):
    if campaign.get("bison_campaign_id") and campaign.get("heyreach_campaign_id"):
        return "both providers mapped"
    if campaign.get("bison_campaign_id"):
        return "EmailBison mapped, HeyReach not mapped"
    if campaign.get("heyreach_campaign_id"):
        return "HeyReach mapped, EmailBison not mapped"
    return "not mapped: no provider campaign has been created"


def provider_preview(repo, campaign_id, day=21):
    """The exact request bodies the sender would post. Nothing is sent.

    `push.payloads` is the sender's own builder - not a copy of it - so what
    is on screen is what would go on the wire. A preview that redraws the
    payload is a preview of something nobody has tested.
    """
    campaign = repo.campaign(campaign_id)
    if campaign is None:
        return None
    recs = repo.records()
    ready, skipped = push.collect(recs, day=day, client=repo.client,
                                  campaign_rows=[campaign])
    ids = set(campaign.get("record_ids") or [])
    ready = [item for item in ready if item["record"]["id"] in ids]

    # The sender's own gate, asked one item at a time. `push.payloads`
    # refuses by raising, which is right for a sender and fatal for a
    # screen: an unapproved campaign refuses every item, and the page whose
    # job is to explain that would 500 instead of explaining it.
    #
    # Not a silent fallback. Nothing is softened - the refused item does
    # not reach a payload - and its reason is shown in the section this
    # panel already has for exactly that, beside the steps the collector
    # excluded earlier for reasons of their own.
    sendable = []
    for item in ready:
        try:
            push.verify_before_payload(item, recs=recs, config=repo.config())
        except AssertionError as refusal:
            skipped.append({"id": item["record"]["id"],
                            "contact": item["contact_key"],
                            "step": item["step_key"],
                            "why": str(refusal).split(": ", 1)[-1]})
            continue
        sendable.append(item)

    payloads = push.payloads(
        sendable,
        bison_campaign_id=campaign.get("bison_campaign_id"),
        heyreach_campaign_id=campaign.get("heyreach_campaign_id"),
        linkedin_account_id=0)
    return {
        "campaign_id": campaign_id,
        "ready": len(sendable),
        "skipped": [s for s in skipped if s.get("id") in ids],
        "payloads": payloads,
        "would_send": 0,
        "banner": "PREVIEW ONLY - NOT SENT",
    }


# ------------------------------------------------------------- approvals

def approval_queue(repo):
    from .. import approve
    recs = repo.records()
    pending = approve.pending(recs)
    campaigns = []
    for campaign in repo.campaigns():
        mine = [r for r in recs if r["id"] in (campaign.get("record_ids") or [])]
        current = campaign_store.approval_is_current(campaign, mine,
                                                     repo.config())
        # Who it would reach, on the screen where somebody approves it.
        # A reviewer deciding from a name and a fingerprint is deciding
        # without the one fact that matters: whether the audience can
        # receive anything at all.
        pre = campaign_preflight(repo, campaign.get("campaign_id"))
        campaigns.append({
            "campaign_id": campaign.get("campaign_id"),
            "name": campaign.get("name"),
            "status": campaign.get("status"),
            "approval": campaign.get("approval"),
            "fingerprint": campaign.get("fingerprint"),
            "current": current,
            # An *approval* that is no longer about this plan. Not any
            # decision that is not current: `approval_is_current` answers
            # False for a rejection by construction - a refusal is not a
            # live approval - so `bool(approval) and not current` called
            # every rejected campaign stale. That put a decided campaign
            # on the approvals page under a "stale" tag and counted it on
            # /diagnostics as an approval needing attention, which is the
            # opposite of what a rejection is.
            "stale": ((campaign.get("approval") or {}).get("action")
                      == "approve" and not current),
            "audience": None if pre is None else {
                "contacts": pre["contacts"],
                "eligible": pre["eligible"],
                "eligible_if_approved": pre["eligible_if_approved"],
                "blocked": pre["verdicts"].get("blocked", 0),
                "held": pre["verdicts"].get("held", 0),
                # The commonest reason, in the sentence `eligibility` owns.
                "top_reason": (pre["reasons"][0]["human"]
                               if pre["reasons"] else None),
            },
        })
    return {"steps": pending, "campaigns": campaigns}


# --------------------------------------------------------------- replies

def _referral_row(entry):
    """The referral a reply carried, flattened for a list."""
    if not entry:
        return None
    return {"named": entry.get("named"),
            "status": entry.get("referral_status"),
            "needs_a_person": bool(entry.get("needs_a_person")),
            "email": (entry.get("emails") or [None])[0],
            "linkedin": (entry.get("profiles") or [None])[0]}


def reply_rows(repo, kind=None):
    """One row per reply, carrying the verdict it was given.

    A reply is one message. `replies.classify` writes REPLY_CLASSIFIED
    beside the REPLY_RECEIVED it read, so listing both put the same message
    in an operator's inbox twice - once labelled "unknown", because a
    receipt carries no verdict and never will.

    The receipt is the row, because that is the message arriving; the
    verdict is folded onto it. A reply nothing has classified is still
    "unknown", which is the honest answer for that one.
    """
    from .. import events as event_model
    from .. import oooreturn
    out = []
    for rec in repo.records():
        by_key = {c.get("key"): c for c in rec.get("contacts") or []}
        # The latest dated intention per contact, read once rather than
        # per reply. `oooreturn` already knows which events carry a date
        # and which of two supersedes the other.
        follow_up = {}
        for key in by_key:
            latest = oooreturn.latest_absence(rec, key)
            if latest:
                follow_up[key] = {
                    "return_date": latest.get("return_date"),
                    "status": latest.get("return_status"),
                    "source": latest.get("type"),
                }
        verdicts = {}
        # Referral mentions, keyed the way the verdicts are. A mention is
        # recorded from the evidence rather than from the classification,
        # so it can sit on a reply classified `negative` - which is why
        # this cannot be answered by looking at the tab.
        mentions = {}
        for entry in rec.get("events") or []:
            if entry.get("type") == event_model.REPLY_CLASSIFIED:
                verdicts[(entry.get("contact"), entry.get("channel"),
                          entry.get("at"))] = entry
            elif entry.get("type") == event_model.REFERRAL_MENTIONED:
                mentions[(entry.get("contact"), entry.get("at"))] = entry
        for entry in rec.get("events") or []:
            if entry.get("type") != event_model.REPLY_RECEIVED:
                continue
            verdict = verdicts.get((entry.get("contact"),
                                    entry.get("channel"),
                                    entry.get("at"))) or {}
            classification = verdict.get("classification") or "unknown"
            if kind and classification != kind:
                continue
            contact = by_key.get(entry.get("contact"))
            out.append({
                "record_id": rec["id"],
                "company": rec.get("company"),
                "contact_key": entry.get("contact"),
                "name": (contact or {}).get("name"),
                "channel": entry.get("channel"),
                "provider": entry.get("provider"),
                "at": entry.get("at"),
                "classification": classification,
                "paused": bool(rec.get("paused")),
                "matched": bool(contact),
                # Whether a person has read it. Deliberately not the same
                # question as whether the company is still paused: a reply is
                # handled by somebody looking at it, and a pause is lifted by
                # looking at the company.
                # `handle_reply` marks the first reply event at this
                # timestamp, which is the receipt; older rows may carry it
                # on the verdict instead.
                "handled": entry.get("handled") or verdict.get("handled"),
                # If this reply named a date - back from leave, or come
                # back in November - the Inbox should say so. It is the
                # difference between a conversation that ended and one
                # with a time on it.
                "follow_up": follow_up.get(entry.get("contact")),
                # Who this reply pointed at, if anybody. Absent rather than
                # empty when it pointed at nobody: "no referral" and "a
                # referral naming nobody" are different messages.
                "referral": _referral_row(
                    mentions.get((entry.get("contact"), entry.get("at")))),
            })
    return sorted(out, key=lambda r: r.get("at") or "", reverse=True)


# What a reply still needs from a person, in the order it is asked.
NEEDS_UNMATCHED = "nobody knows who this is"
NEEDS_CLASSIFYING = "nobody has said what it means"
NEEDS_READING = "somebody said yes and nobody has looked"


def needs_attention(row):
    """Why this reply is still somebody's job, or None.

    Derived, never stored: a reply stops needing attention when it is
    matched, classified and read, not when a flag is set.
    """
    if not row["matched"]:
        return NEEDS_UNMATCHED
    if row["classification"] == "unknown":
        return NEEDS_CLASSIFYING
    if row["classification"] == "positive" and not row.get("handled"):
        return NEEDS_READING
    return None


# A filter that is not a classification. `carries` asks what a reply
# *contains*; the tabs ask what it was read as. Keeping them apart is the
# whole reason this exists: a referral inside a polite refusal is
# classified `negative`, and no tab would ever show it.
CARRIES_REFERRAL = "referral"


def reply_inbox(repo, kind=None, carries=None):
    """Replies grouped by what they need, then listed.

    The list was flat and its tabs named five of the nine classifications,
    so a reply classified `out_of_office` or `not_now` was invisible under
    every tab except All. The tabs are built from `replies.CATEGORIES` now,
    so a category added later cannot go missing the same way.

    `carries` is the other question. A referral is recorded from the
    evidence rather than from the winning category, so it can sit on a
    reply classified `negative` - and the tab for it would not contain it.
    """
    from .. import replies as reply_model
    everything = reply_rows(repo)
    counts = {}
    for row in everything:
        counts[row["classification"]] = counts.get(row["classification"], 0) + 1

    waiting = [row for row in everything if needs_attention(row)]
    for row in waiting:
        row["needs"] = needs_attention(row)

    shown = [r for r in everything
             if not kind or r["classification"] == kind]
    if carries == CARRIES_REFERRAL:
        shown = [r for r in shown if r.get("referral")]
    return {
        "rows": shown,
        "attention": waiting,
        "kind": kind,
        "carries": carries,
        # Counted over everything, like the tab counts, so filtering never
        # narrows the number beside the control that would widen it again.
        "referrals": len([r for r in everything if r.get("referral")]),
        "counts": counts,
        "total": len(everything),
        # Every canonical category, whether or not the estate has one
        # today. A tab that appears only once a reply exists is a tab
        # nobody knows to look for.
        "categories": [{"kind": name, "count": counts.get(name, 0)}
                       for name in reply_model.CATEGORIES],
    }


class ActionRefused(RuntimeError):
    """The action did not happen, and the message says which gate stopped it."""


def pause_campaign(repo, campaign_id, why="", by="unknown"):
    """Stop THIS SYSTEM planning further steps for a campaign.

    IT DOES NOT REACH THE PROVIDER, and the audit row now says so. This used to
    record `before={"status": "running"}` and `after={"status": "paused"}` - a
    hardcoded "running" nobody had checked, beside an affirmative statement that
    outreach had stopped. `orchestrator.pause` writes canonical state and makes
    no provider call of any kind: `providerwrites.SUPPORTED` is empty, so
    `heyreach.pause` and `bison.pause` both refuse by name.

    The gap is not theoretical. A campaign already running at the provider keeps
    running after this returns, and an operator reading "paused" in the audit
    trail would reasonably believe otherwise - which is the worst place in the
    system for a claim to be wrong, because it is the control somebody reaches
    for when they want something to stop.

    Pausing is still the safe direction, and `campaign.pause` is still granted
    from reviewer upward while launching is granted to nobody: the person who
    can see something is wrong should be able to stop this system without
    finding somebody more senior first. What they cannot do from here is stop
    the vendor, and HUMAN-ACTIONS-REQUIRED 5e records the out-of-band step.
    """
    repo.require(ws.CAMPAIGN_PAUSE)
    from .. import orchestrator, roles

    campaign = repo.campaign(campaign_id)
    if campaign is None:
        return None
    if (campaign.get("pause") or {}).get("since"):
        raise ActionRefused("this campaign is already paused")
    # READ THE STATUS IT ACTUALLY HAD. The audit row asserted "running"
    # regardless, so a draft or an approved-but-unlaunched campaign recorded a
    # transition that never happened.
    was = campaign.get("status")
    try:
        orchestrator.pause(campaign, why=(why or "").strip()[:200]
                           or f"paused by {by}", by=by, role=roles.ADMIN)
    except Exception as e:                          # noqa: BLE001
        raise ActionRefused(f"{type(e).__name__}: {e}")
    repo.save_campaign(campaign)
    repo.audit("campaign.paused", "campaign", campaign_id,
               before={"status": was},
               # WHAT THIS DID NOT DO, recorded beside what it did. A reader of
               # this row is deciding whether outreach has stopped, and the
               # honest answer is that this system will plan nothing further
               # while the provider is untouched.
               after={"status": campaign.get("status"),
                      "provider_stopped": False},
               reason=(campaign["pause"]["reason"]
                       + "; this system will plan no further steps. The "
                         "provider was not asked to stop: no pause route is "
                         "supported, so a campaign already running there "
                         "continues until somebody pauses it in the vendor UI"))
    return campaign


def resume_campaign(repo, campaign_id, by="unknown"):
    """Restart a paused campaign, if everything it needs still holds.

    `orchestrator.resume` re-runs the full validation rather than simply
    clearing the flag, and refuses with the blockers when it does not pass. A
    pause is not undone by forgetting about it.
    """
    repo.require(ws.CAMPAIGN_PAUSE)
    from .. import orchestrator, roles

    campaign = repo.campaign(campaign_id)
    if campaign is None:
        return None
    if not (campaign.get("pause") or {}).get("since"):
        raise ActionRefused("this campaign is not paused")
    recs = [r for r in repo.records()
            if r["id"] in (campaign.get("record_ids") or [])]
    try:
        orchestrator.resume(campaign, by=by, role=roles.ADMIN, recs=recs,
                            config=repo.config())
    except Exception as e:                          # noqa: BLE001
        raise ActionRefused(f"{type(e).__name__}: {e}")
    repo.save_campaign(campaign)
    repo.audit("campaign.resumed", "campaign", campaign_id,
               after={"status": campaign.get("status")},
               reason=f"resumed by {by}")
    return campaign


def handle_reply(repo, record_id, contact_key, at, by="unknown", note=""):
    """Mark that a person has dealt with one reply. Sends nothing.

    This does not un-pause anything and cannot. A reply pauses both channels
    for the whole company, and that pause is lifted by looking at the company
    - not by ticking the reply off a list. What is recorded here is only that
    somebody read it, which is a different fact and is stored as one.
    """
    repo.require(ws.REPLIES_MANAGE)
    rec = repo.record(record_id)
    if rec is None:
        return None
    target = None
    for entry in rec.get("events") or []:
        if (entry.get("contact") == contact_key and entry.get("at") == at
                and entry.get("type", "").startswith("reply")):
            target = entry
            break
    if target is None:
        return None
    if target.get("handled"):
        raise ActionRefused("this reply has already been marked handled")
    target["handled"] = {"by": by, "at": store.now(),
                         "note": str(note or "")[:300]}
    repo.save_records([rec])
    repo.audit("reply.handled", "record", record_id,
               after={"contact": contact_key, "at": at,
                      "classification": target.get("classification")},
               reason=target["handled"]["note"] or None)
    return target


def slack_previews(repo, campaign_id=None):
    """What would be posted. `delivered` is False and the reason travels."""
    config = repo.config()
    campaign = repo.campaign(campaign_id) if campaign_id else None
    if campaign is None:
        campaigns = repo.campaigns()
        campaign = campaigns[0] if campaigns else None
    if campaign is None:
        return []
    recs = [r for r in repo.records()
            if r["id"] in (campaign.get("record_ids") or [])]
    from .. import orchestrator
    summary = orchestrator.summarise(campaign, recs, config)
    previews = []
    try:
        previews.append({
            "kind": "campaign approval requested",
            "payload": slack.campaign_approval_request(campaign, summary, config),
        })
    except Exception as e:
        previews.append({"kind": "campaign approval requested",
                         "error": f"{type(e).__name__}: {str(e)[:120]}"})
    return [dict(p, delivered=False,
                 why="nothing is posted from this build") for p in previews]


# ------------------------------------------------------------- reporting

def reporting(repo):
    recs = repo.records()
    config = repo.config()
    return {
        # The company count, stated rather than dug out of a funnel stage
        # whose key depends on which lane the batch came in through.
        "records": len(recs),
        "funnel": report.funnel_for(recs, config=config),
        # Labelled here rather than in the template, which may not import an
        # engine module - and should not be carrying a second copy of the
        # names the client report already uses.
        "funnel_labels": dict(report.FUNNEL_LABEL),
        "qualification": report.qualification_funnel(recs, repo.client),
        "distribution": report.qualification_distribution(recs, repo.client),
        "confirmation": report.by_confirmation(recs, repo.client, config),
        "decision_makers": report.decision_makers(recs, repo.client),
        "by_persona": report.by_persona(recs, config),
        "providers": report.by_provider(recs),
        "verifiers": report.by_verifier(recs),
        "unavailable": report.unavailable(),
    }


# ------------------------------------------------------------ client reports
#
# One assembly function, one render function, one history. Everything the PDF
# prints comes from `src/report.py`, so a figure in a document and the same
# figure on a screen cannot disagree - see `src/clientreport.py`.


def report_templates(repo):
    """Which templates this caller may render, and what each contains.

    The gate is `operations.view`. The internal operations report names
    providers, verification counts and held records, and a client-facing role
    that could select it from a dropdown would be reading the vendor stack out
    of a PDF. It is absent from the list rather than present and refused,
    because an option that always fails is worse than no option.
    """
    may_operate = repo.may(ws.OPERATIONS_VIEW)
    listed = []
    for template in clientreport.TEMPLATES:
        if template == clientreport.INTERNAL and not may_operate:
            continue
        listed.append({
            "key": template,
            "label": clientreport.TEMPLATE_LABEL[template],
            "blurb": clientreport.TEMPLATE_BLURB[template],
            "sections": [
                {"key": key, "label": clientreport.SECTION_LABEL[key],
                 "client_safe": key in clientreport.CLIENT_SAFE_SECTIONS}
                for key in clientreport.sections_for(template)],
        })
    return listed


def allowed_template(repo, requested):
    """Resolve a requested template against what this caller may render.

    Anything unrecognised, and anything the caller may not have, falls back to
    the executive report rather than raising. The rule this encodes: a bad or
    forged template parameter produces the *least* privileged document, never
    a refusal a caller could distinguish from a permission probe.
    """
    requested = str(requested or "").strip() or clientreport.EXECUTIVE
    if requested == clientreport.INTERNAL and not repo.may(ws.OPERATIONS_VIEW):
        return clientreport.EXECUTIVE
    if requested not in clientreport.TEMPLATES:
        return clientreport.EXECUTIVE
    return requested


def report_data(repo, campaigns=None, since=None, until=None):
    """Everything a client report prints, counted once, from `report.py`.

    `campaigns` narrows to a set of campaign ids; `since`/`until` are ISO
    dates bounding the events considered. Both narrow the *records* before
    anything is counted, so a filtered report's funnel and its campaign table
    describe the same population - which they would not if each section
    filtered for itself.
    """
    recs = repo.records()
    config = repo.config()
    every_campaign = repo.campaigns()

    chosen = None
    if campaigns:
        wanted = {str(c) for c in campaigns if str(c).strip()}
        chosen = [c for c in every_campaign
                  if str(c.get("campaign_id")) in wanted]
        keep = set()
        for campaign in chosen:
            keep.update(campaign.get("record_ids") or [])
        recs = [r for r in recs if r["id"] in keep]
    else:
        chosen = list(every_campaign)

    data = report.for_client(repo.client, recs, config=config)

    # The campaign table, built from the same narrowed set.
    rows = []
    for campaign in chosen:
        mine = [r for r in recs if r["id"] in (campaign.get("record_ids") or [])]
        counted = _campaign_counts(mine, since, until)
        rows.append({
            "campaign_id": campaign.get("campaign_id"),
            "name": campaign.get("name") or campaign.get("campaign_id"),
            "status": campaign.get("status"),
            "companies": len(mine),
            "contacts": sum(len(r.get("contacts") or []) for r in mine),
            **counted,
        })
    rows.sort(key=lambda r: (-(r.get("contacts") or 0), str(r.get("name"))))
    data["campaign_rows"] = rows

    # The audience dimensions, from the analytics rows the screens use, so a
    # breakdown in the PDF matches the same breakdown in the browser.
    data.update(_audience_breakdowns(repo, recs))

    # Operator-only blocks. Assembled unconditionally and dropped by the
    # template: `clientreport.sections_for` decides what renders, and an
    # executive report has no section that could print any of this.
    data["verification"] = _verification_counts(
        recs, verification.policy_for(config))
    # Five sections that were written, rendered and never assembled. Each
    # one reads a key `report_data` did not produce, so four rates could
    # not be computed at all and five sections printed an excuse about the
    # period. None of this is new measurement: it is the event log and
    # `account.graph`, read the way every other number here is read.
    data["linkedin"] = _linkedin_counts(recs)
    data["pipeline"] = _pipeline_rows(repo, recs)
    data["accounts"] = _account_counts(recs, client=repo.client)
    data["by_sender"] = _sender_rows(repo)
    data["months"] = _months(recs)
    data["mx"] = mx.summarise(recs, config).get("by_provider") or {}
    data["providers"] = _provider_usage(recs)
    data["operations"] = _operations_counts(repo, recs)
    return data


def _campaign_counts(recs, since=None, until=None):
    from .. import events as event_model

    sent = replies_ = positive = 0
    for rec in recs:
        for entry in rec.get("events") or []:
            at = str(entry.get("at") or "")
            if since and at[:10] < since:
                continue
            if until and at[:10] > until:
                continue
            kind = entry.get("type")
            if kind == event_model.PUSH_MARKED:
                sent += 1
            elif kind == event_model.REPLY_RECEIVED:
                replies_ += 1
            elif kind == event_model.POSITIVE_REPLY_DETECTED:
                positive += 1
    return {"sent": sent, "replies": replies_, "positive": positive}


def _audience_breakdowns(repo, recs):
    """Contacts by each audience dimension, counted from the analytics rows."""
    rows = analytics_rows(repo)
    keep = {r["id"] for r in recs}
    rows = [r for r in rows if r.get("record_id") in keep]
    out = {}
    for key, field in (("by_vertical", "vertical"),
                       ("by_industry", "industry"),
                       ("by_country", "country"),
                       ("by_size", "employee_band"),
                       ("by_tier", "icp_tier")):
        counts = {}
        for row in rows:
            value = row.get(field)
            if value in (None, "", "None"):
                continue
            counts[str(value)] = counts.get(str(value), 0) + 1
        if counts:
            out[key] = counts
    return out


def _linkedin_counts(recs):
    """The LinkedIn half of the report, counted from confirmed events.

    Four numbers, and the distinction between two of them is the whole
    reason this is not one number. A connection *request* is the `day3`
    step; a *message* is any other confirmed LinkedIn touch. Rolling them
    together would make an acceptance rate whose denominator included
    messages sent after the acceptance.

    Acceptance is `LINKEDIN_CONNECTED`, which only a provider writes. It is
    never inferred from a later message having gone out, which is the
    tempting shortcut: a message can be queued by a cadence that never
    checked, so treating one as proof of acceptance would report an
    acceptance nobody reported.
    """
    from .. import events as event_model

    counts = {"requests": 0, "accepted": 0, "messages": 0, "replies": 0}
    for rec in recs:
        for item in account.touches(rec, confirmed_only=True):
            if item.get("channel") != "linkedin":
                continue
            if item.get("step") == LINKEDIN_REQUEST_STEP:
                counts["requests"] += 1
            else:
                counts["messages"] += 1
        for entry in rec.get("events") or []:
            if event_model.is_acceptance(entry):
                counts["accepted"] += 1
            elif (entry.get("type") == event_model.REPLY_RECEIVED
                  and entry.get("channel") == "linkedin"):
                counts["replies"] += 1
    return counts


def _pipeline_rows(repo, recs):
    """Everyone who replied positively, and nothing about what they said.

    Read from `POSITIVE_REPLY_DETECTED` rather than from a classification
    scan, because that event is written once per positive reply and a
    classification is written for every reply there is.

    No reply text. There is none stored, and a pipeline table that quoted
    one would be quoting something this build does not keep.
    """
    from .. import events as event_model

    rows = []
    for rec in recs:
        by_key = {c.get("key"): c for c in rec.get("contacts") or []}
        for entry in rec.get("events") or []:
            if entry.get("type") != event_model.POSITIVE_REPLY_DETECTED:
                continue
            contact = by_key.get(entry.get("contact")) or {}
            senders = assignment.describe(contact) or {}
            channel = entry.get("channel") or ""
            named = (senders.get(channel) or {}).get("sender_name")
            rows.append({
                "contact": contact.get("name") or entry.get("contact"),
                "company": rec.get("company"),
                "title": contact.get("title"),
                "channel": channel,
                # The sender on the channel the reply came in on. Absent
                # rather than guessed: a reply on a channel nobody was
                # assigned to has no sender to name.
                "sender": named,
                "status": accountpolicy.OUTCOME_LABEL.get(
                    accountpolicy.classify_outcome(rec, entry.get("contact")),
                    "replied"),
            })
    rows.sort(key=lambda r: (str(r["company"] or ""), str(r["contact"] or "")))
    return rows


def _account_counts(recs, client=None):
    """Companies, not contacts, in THE OPERATOR'S VOCABULARY.

    Read through `account.graph`, the canonical answer to every
    account-level question, rather than by walking the event log again with
    a second opinion about what counts as contacted.

    ## THE OLD KEYS ARE RETIRED, NOT ALIASED

    OPERATOR, 2026-09-23. This used to emit `targeted / contacted / engaged
    / positive`, and `slackagenttools` answered the same question in eight
    different words. **Both spelled `engaged` and meant different things**:
    here it was "at least one reply", there it is deliberately short of a
    reply. An alias would have carried that collision forward under a
    forwarding address, so the four old keys are gone and every reader takes
    `accountstate.state_of` - the one state machine, called from both.

    `multi_dm` and `referrals` survive unchanged. They are not states; they
    are facts about how an account was worked, and no other key says them.

    `unanswerable` is counted apart and NEVER folded into `untouched`. On
    this path it should stay zero - the report is built from the same event
    log `account.graph` reads, so `untouched` is assertable and `ledger_ok`
    is left `None` - but it is emitted anyway, because a tile that only
    appears when it is non-zero is a tile nobody notices has appeared.
    """
    counts = accountstate.empty_counts()
    counts.update({"unanswerable": 0, "multi_dm": 0, "referrals": 0})

    # The meetings ledger is hand-fed and workspace-scoped; it is the only
    # source for MEETING and it is read here rather than guessed at, so the
    # PDF and the Monday post cannot disagree about which accounts met us.
    met = set()
    try:
        from .. import slackmeetings
        met = {str(row.get("domain") or "").lower()
               for row in (slackmeetings.by_domain(workspace=client) or [])}
    except Exception:                                           # noqa: BLE001
        met = set()

    for rec in recs:
        graph = account.graph(rec)
        people = graph["contacts"]
        worked = [c for c in people if c["confirmed_touches"]]
        here = 1 if str(rec.get("domain") or "").lower() in met else 0
        state, _evidence = accountstate.state_of(rec, graph, here)
        if state is None:
            counts["unanswerable"] += 1
        else:
            counts[state] = counts.get(state, 0) + 1
        if len(worked) > 1:
            counts["multi_dm"] += 1
        counts["referrals"] += len(graph["referrals"])
    return counts


def _sender_rows(repo):
    """Per sender, per channel. Reuses the sender report rather than
    counting it again - the last audit found three places counting one
    reply differently, and this is not becoming a fourth."""
    rows = []
    for row in sender_report(repo, dimension="sender")["rows"]:
        for channel, touches in (("email", row["confirmed_email"]),
                                 ("linkedin", row["confirmed_linkedin"])):
            if not touches:
                continue
            rows.append({"sender": row["key"], "channel": channel,
                         "touches": touches,
                         # Replies are per contact, not per channel: the
                         # report cannot attribute a reply to one of a
                         # sender's two channels, and splitting it would
                         # be inventing an attribution.
                         "replies": row["replies"], "positive": row["positive"]})
    return rows


def _months(recs):
    """Activity by calendar month, from the events that carry a date.

    An undated event is left out rather than filed under the current
    month, which would move history every time the report was run.
    """
    from .. import events as event_model

    buckets = {}

    def bucket(at):
        stamp = str(at or "")[:7]
        if len(stamp) != 7 or stamp[4] != "-":
            return None
        return buckets.setdefault(stamp, {"month": stamp, "contacted": set(),
                                          "touches": 0, "replies": 0,
                                          "positive": 0})

    for rec in recs:
        for item in account.touches(rec, confirmed_only=True):
            found = bucket(item.get("at"))
            if found is None:
                continue
            found["touches"] += 1
            found["contacted"].add((rec.get("id"), item.get("contact_key")))
        for entry in rec.get("events") or []:
            kind = entry.get("type")
            if kind == event_model.REPLY_RECEIVED:
                found = bucket(entry.get("at"))
                if found is not None:
                    found["replies"] += 1
            elif kind == event_model.POSITIVE_REPLY_DETECTED:
                found = bucket(entry.get("at"))
                if found is not None:
                    found["positive"] += 1

    return [{**row, "contacted": len(row["contacted"])}
            for row in sorted(buckets.values(), key=lambda r: r["month"])]


def _verification_counts(recs, policy=None):
    """The verification picture, recomputed rather than read off a flag.

    Two defects it was written to fix, and both were the same shape.

    It counted `invalid` from `contact["verification"]["status"]`, a key
    `verification.apply` has never written - it writes `state`. So the
    client report's "Invalid - not used" tile was structurally zero
    forever, which is indistinguishable from "we checked and found none".

    And it counted `double` from the *length of the provider list* - two
    providers having been asked - while the operator dashboard counts
    confirmations obtained. Two providers both answering `unknown` were
    reported to a client as "Double verified". The words on that tile
    describe the safety property this whole build rests on, so they have
    to mean what `verification.decide` means by them.

    Recomputed from the evidence for the same reason `lint.sendable`
    recomputes: a stored verdict can outlive the evidence under it.
    """
    counts = {"double": 0, "single": 0, "invalid": 0, "disagreement": 0,
              "addresses": 0}
    for rec in recs:
        for contact in rec.get("contacts") or []:
            if not contact.get("email"):
                continue
            counts["addresses"] += 1
            decision = verification.resolve(contact, policy)
            if decision["state"] == verification.INVALID:
                counts["invalid"] += 1
            if decision.get("disagreement"):
                counts["disagreement"] += 1
            confirmed = decision.get("confirmation_count") or 0
            required = decision.get("required_confirmations") or 1
            if confirmed >= required:
                counts["double"] += 1
            elif confirmed:
                counts["single"] += 1
    return counts


def _provider_usage(recs):
    """Calls per provider, counted from the spend ledger, never estimated."""
    usage = {}
    for rec in recs:
        for spend in rec.get("spends") or []:
            name = spend.get("provider") or "unknown"
            bucket = usage.setdefault(name, {"calls": 0, "successes": 0,
                                             "failures": 0, "cost": None})
            bucket["calls"] += 1
            if spend.get("ok") is False:
                bucket["failures"] += 1
            else:
                bucket["successes"] += 1
    return usage


def _operations_counts(repo, recs):
    every_job = jobs.for_client(repo.client)
    notifications = {}
    for row in notify.history(repo.workspace, limit=100000):
        notifications[row["status"]] = notifications.get(row["status"], 0) + 1
    return {
        "jobs": len(every_job),
        "failed_jobs": len([j for j in every_job
                            if j.get("status") == jobs.FAILED]),
        "held": len([r for r in recs if r.get("state") == "held"]),
        "unmatched": len([r for r in reply_rows(repo) if not r["matched"]]),
        "notifications": notifications,
    }


def client_reports(repo):
    """The Client Reports screen: what can be built, and what has been."""
    campaigns = [{"campaign_id": c.get("campaign_id"),
                  "name": c.get("name") or c.get("campaign_id"),
                  "status": c.get("status")}
                 for c in repo.campaigns()]
    campaigns.sort(key=lambda c: str(c["name"]))
    return {
        "workspace": repo.workspace,
        "workspace_name": (ws.workspace(repo.workspace) or {}).get("name")
                          or repo.workspace,
        "templates": report_templates(repo),
        "campaigns": campaigns,
        "history": report_store.for_workspace(repo.workspace, limit=50),
        "summary": report_store.summarise(repo.workspace),
        "can_generate": repo.may(ws.REPORTING_VIEW),
        "defaults": _report_defaults(repo),
    }


def _report_defaults(repo):
    """The workspace's saved report settings, or the template's own defaults.

    Stored as a workspace policy so it travels with the workspace rather than
    living in somebody's browser - a monthly report that renders differently
    depending on who pressed the button is not a monthly report.
    """
    policy = ws.policy(repo.workspace)
    template = policy.get("reporting.default_template") \
        or clientreport.EXECUTIVE
    if template not in clientreport.TEMPLATES:
        template = clientreport.EXECUTIVE
    raw = policy.get("reporting.default_sections")
    sections = ([s.strip() for s in str(raw).split(",") if s.strip()]
                if raw else clientreport.default_sections(template))
    return {"template": template,
            "sections": clientreport.resolve_sections(template, sections)}


def generate_report(repo, template=None, sections=None, campaigns=None,
                    since=None, until=None, by="unknown", demo=False):
    """Build one PDF and record that it was built. Returns (row, bytes).

    The template is resolved through `allowed_template` rather than trusted,
    and the sections through `clientreport.resolve_sections`, which drops any
    key the template does not offer. Those two calls are the whole reason a
    forged form field cannot put the provider table into a client's document.

    A failure is recorded too, with status `failed` and the error class. A
    report history that only lists successes cannot answer "why did the
    January report never arrive".
    """
    template = allowed_template(repo, template)
    chosen = clientreport.resolve_sections(template, sections)
    report_id = report_store.new_id()
    period = clientreport._period_label(since, until)
    names = [c["name"] for c in
             ({"name": (x.get("name") or x.get("campaign_id"))}
              for x in repo.campaigns()
              if not campaigns
              or str(x.get("campaign_id")) in {str(c) for c in campaigns})]
    label = "All campaigns" if not campaigns else ", ".join(names[:4]) or "-"

    meta = {
        "workspace_name": (ws.workspace(repo.workspace) or {}).get("name")
                          or repo.workspace,
        "workspace_slug": repo.workspace,
        "template": template,
        "period": period,
        "campaign_label": label,
        "generated_by": by,
        "report_id": report_id,
        "generated_at": store.now()[:10],
        "demo": bool(demo),
    }
    try:
        data = report_data(repo, campaigns, since, until)
        raw = clientreport.build(data, meta, chosen)
    except Exception as e:                                  # noqa: BLE001
        row = report_store.record(
            repo.workspace, template, chosen, by, period, campaigns,
            report_id=report_id, status=report_store.FAILED,
            error=f"{type(e).__name__}: {e}"[:300])
        repo.audit("report.failed", "report", report_id,
                   metadata={"template": template, "error": type(e).__name__})
        return row, None

    row = report_store.record(
        repo.workspace, template, chosen, by, period, campaigns,
        report_id=report_id, bytes_written=len(raw))
    repo.audit("report.generated", "report", report_id,
               metadata={"template": template, "period": period,
                         "sections": len(chosen), "bytes": len(raw)})
    return row, raw


def simulation(size=5000):
    """The 5,000-domain simulator, offline, no providers."""
    return scalesim.qualify_scale(size)


# ------------------------------------------------------------- diagnostics

def diagnostics(repo):
    recs = repo.records()
    config = repo.config()
    stale = [c for c in approval_queue(repo)["campaigns"] if c["stale"]]
    unmatched = [r for r in reply_rows(repo) if not r["matched"]]
    holds = [r for r in recs if r.get("state") == "held"]
    mapping = [c for c in repo.campaigns()
               if not (c.get("bison_campaign_id") and c.get("heyreach_campaign_id"))]
    return {
        "jobs": jobs.summarise(jobs.for_client(repo.client)),
        "stale_approvals": stale,
        "unmatched_replies": unmatched,
        "held_records": [{"id": r["id"], "company": r.get("company")}
                         for r in holds],
        "unmapped_campaigns": [{"campaign_id": c.get("campaign_id"),
                                "name": c.get("name"),
                                "status": _mapping_status(c)}
                               for c in mapping],
        "credentials": security.credential_status(),
        "live_sending": False,
        # Read from `feature_flags` rather than recomputed, because the
        # defect this closes was two surfaces answering the same question
        # differently. A second computation that agrees today is how that
        # comes back.
        "slack_posting": next((f["state"] for f in feature_flags()
                               if f["flag"] == "slack_posting"), False),
    }


# --------------------------------------------- workspaces, users, settings

def workspace_settings(repo):
    """This workspace's own rules, plus what a provider mapping points at.

    Every value here comes from the workspace's client config, which is what
    makes ICP rules, personas, geographies, timezone policy, the verification
    waterfall, MX policy and campaign defaults independent per tenant without a
    second mechanism. No credential is read: `credential_status()` reports
    presence by name and is gated on `provider_settings.view` at the handler.
    """
    entry = ws.workspace(repo.workspace) or {}
    campaigns = repo.campaigns()
    bison = next((c.get("bison_campaign_id") for c in campaigns
                  if c.get("bison_campaign_id")), None)
    heyreach = next((c.get("heyreach_campaign_id") for c in campaigns
                     if c.get("heyreach_campaign_id")), None)
    config = repo.config()
    overrides = ws.policy(repo.workspace)
    editable = []
    for key, spec in sorted(ws.POLICY_KEYS.items()):
        editable.append({
            "key": key,
            "label": spec["label"],
            "kind": spec["kind"],
            "why": spec["why"],
            "choices": list(spec.get("choices") or ()),
            "min": spec.get("min"),
            "max": spec.get("max"),
            "max_items": spec.get("max_items"),
            "max_length": spec.get("max_length"),
            "blank_is_none": bool(spec.get("blank_is_none")),
            "value": _config_at(config, key),
            "overridden": key in overrides,
            # The recorded reason, when there is one. `settings` remains
            # the authority on what is in force; this only says why.
            "decision": gtm.for_policy_key(repo.workspace, key),
        })
    return {
        "workspace": {"slug": repo.workspace,
                      "name": entry.get("name") or repo.workspace,
                      "client": entry.get("client") or repo.client,
                      "created_at": entry.get("created_at"),
                      "created_by": entry.get("created_by")},
        "config": config,
        "mapping": {"bison": bison, "heyreach": heyreach},
        "campaigns": len(campaigns),
        "records": len(repo.records()),
        "editable": editable,
        "overrides": overrides,
        "can_manage": repo.may(ws.WORKSPACE_MANAGE),
        "unexplained": gtm.unexplained(repo.workspace, overrides),
        "can_manage_providers": repo.may(ws.PROVIDER_SETTINGS_MANAGE),
        # What to call the provider campaign when somebody creates it by
        # hand, so an employee looking at EmailBison can tell which
        # campaigns Resonate is filling. A label, never an identity.
        "mappable": [{"campaign_id": c.get("campaign_id"),
                      "suggested_names": providername.describe(
                          repo.workspace, c.get("campaign_id"),
                          segment=(c.get("segment_key")
                                   if isinstance(c, dict) else None)),
                      "name": c.get("name"),
                      "bison": c.get("bison_campaign_id"),
                      "heyreach": c.get("heyreach_campaign_id")}
                     for c in campaigns],
    }


def _config_at(config, dotted):
    """The value a dotted key currently resolves to, or None."""
    node = config or {}
    for part in dotted.split("."):
        if not isinstance(node, dict):
            return None
        node = node.get(part)
    return node


def update_policy(repo, updates, by="unknown"):
    """Change this workspace's policy overrides. All of them, or none.

    The client config file is not touched. See `workspaces.POLICY_KEYS` for
    what may be changed here and, more to the point, what may not.
    """
    repo.require(ws.WORKSPACE_MANAGE)
    return ws.set_policy(repo.workspace, updates, actor=by)


def personas_view(repo):
    """Who this workspace treats as a decision maker, and where that came
    from.

    `source` is the part worth showing. A persona set edited here replaces
    the client file's rather than merging with it - the way every other
    override replaces the value it names - so an operator has to be able to
    see which of the two they are looking at before they change it.
    """
    config = repo.config()
    overridden = "personas" in ws.policy(repo.workspace)
    rows = []
    for name, body in sorted((config.get("personas") or {}).items()):
        rows.append({
            "name": name,
            "titles": list(body.get("titles") or []),
            "cap_per_domain": body.get("cap_per_domain") or 1,
            "angles": dict(body.get("angles") or {}),
            # Named because a persona with no angle still selects people;
            # what it cannot do is say anything specific to them.
            "no_angles": not (body.get("angles") or {}),
        })
    return {
        "workspace": repo.workspace,
        "personas": rows,
        "source": "this workspace" if overridden else "the client file",
        "overridden": overridden,
        "can_manage": repo.may(ws.WORKSPACE_MANAGE),
        "limits": {"personas": ws.MAX_PERSONAS, "titles": ws.MAX_TITLES,
                   "angles": ws.MAX_ANGLES, "cap": ws.MAX_CAP},
    }


def _angles_from_lines(text):
    """`name: what it says`, one per line - the shape the client file uses.

    A line with no colon is refused rather than guessed at. Guessing would
    make the angle name the whole sentence, and the angle name is a key
    that reports group by.
    """
    angles = {}
    for line in str(text or "").splitlines():
        line = line.strip()
        if not line:
            continue
        if ":" not in line:
            raise ws.NotOverridable(
                f"{line[:40]!r} is not an angle. Write "
                "`name: what it says`, one per line.")
        name, _, phrase = line.partition(":")
        angles[name.strip()] = phrase.strip()
    return angles


def save_persona(repo, name, titles, cap, angles_text, by="unknown"):
    """Add or replace one persona. The rest of the set is untouched.

    Read from `repo.config()` rather than from the override, so the first
    edit to a workspace still running on its client file starts from what
    that file says instead of wiping it.
    """
    repo.require(ws.WORKSPACE_MANAGE)
    current = _deep(repo.config().get("personas") or {})
    key = str(name or "").strip().lower()
    if not key:
        raise ws.NotOverridable("a persona needs a name")
    current[key] = {
        "titles": [t.strip() for t in str(titles or "").split(",")
                   if t.strip()],
        "cap_per_domain": cap,
        "angles": _angles_from_lines(angles_text),
    }
    ws.set_policy(repo.workspace, {"personas": current}, actor=by)
    return current


def remove_persona(repo, name, by="unknown"):
    """Take one out. Removing the last one removes the override entirely,
    which puts the workspace back on its client file rather than leaving it
    with a persona set of nobody."""
    repo.require(ws.WORKSPACE_MANAGE)
    current = _deep(repo.config().get("personas") or {})
    if str(name or "").strip().lower() not in current:
        return None
    current.pop(str(name).strip().lower())
    # Passed as it is. `coerce_personas` is the one thing that decides an
    # empty set means no override, and saying it twice would make neither
    # saying testable.
    ws.set_policy(repo.workspace, {"personas": current}, actor=by)
    return current


def _deep(value):
    return copy.deepcopy(value)


def set_provider_mapping(repo, campaign_id, bison=None, heyreach=None,
                         by="unknown"):
    """Point one campaign at the provider campaigns it corresponds to.

    This records a pointer. It creates nothing at EmailBison or HeyReach and
    changes nothing there - creating a provider campaign is a mutation this
    build does not perform, and a mapping that claimed to have made one would
    be the most dangerous sentence on this screen.
    """
    repo.require(ws.PROVIDER_SETTINGS_MANAGE)
    campaign = repo.campaign(campaign_id)
    if campaign is None:
        return None
    before = {"bison": campaign.get("bison_campaign_id"),
              "heyreach": campaign.get("heyreach_campaign_id")}
    campaign["bison_campaign_id"] = (bison or "").strip()[:80] or None
    campaign["heyreach_campaign_id"] = (heyreach or "").strip()[:80] or None
    # A mapping change invalidates an approval taken against the old one: the
    # campaign somebody approved would now be submitted somewhere else.
    if campaign.get("approval") and before != {
            "bison": campaign["bison_campaign_id"],
            "heyreach": campaign["heyreach_campaign_id"]}:
        campaign_store.log(campaign, "mapping_changed",
                           "the provider mapping changed after approval",
                           by=by)
    repo.save_campaign(campaign)
    repo.audit("provider_mapping.changed", "campaign", campaign_id,
               before=before,
               after={"bison": campaign["bison_campaign_id"],
                      "heyreach": campaign["heyreach_campaign_id"]},
               reason="set from the workspace settings screen")
    return campaign


def workspace_people(repo):
    """Who is in this workspace and what their role carries."""
    entry = ws.workspace(repo.workspace) or {}
    rows = ws.load()
    # Deliberately no user directory. A workspace admin at one tenant listing
    # every address at every other tenant is a disclosure with no upside: to
    # add somebody you already know who they are, so the form takes an address
    # rather than offering a list of everybody who exists.
    return {
        "workspace": {"slug": repo.workspace,
                      "name": entry.get("name") or repo.workspace},
        "memberships": sorted(ws.memberships(workspace_slug=repo.workspace,
                                             rows=rows),
                              key=lambda m: (m["role"], m["email"])),
        # Pre-authorised addresses that have not signed in yet. They grant
        # nothing and appear in no permission check; they are shown so an
        # administrator can see that access was offered, to whom, and by
        # whom - and withdraw it.
        "invitations": sorted(ws.invitations(workspace_slug=repo.workspace,
                                             status=ws.PENDING, rows=rows),
                              key=lambda i: (i["role"], i["email"])),
        "roles": list(ws.assignable_roles()),
        "permissions": {r: ws.permissions_of(r) for r in ws.ROLES},
    }


def workspace_list(email):
    """The workspaces this person may enter, with who else is in each."""
    rows = ws.load()
    mine = ws.workspaces_for(email, rows)
    by_space = {}
    for space in mine:
        by_space[space["slug"]] = sorted(
            ws.memberships(workspace_slug=space["slug"], rows=rows),
            key=lambda m: m["email"])
    return {"workspaces": mine, "memberships": by_space}


def audit_entries(workspace=None, limit=300):
    """The durable log. Scoped by the caller, never widened here."""
    return ws.audit(workspace_slug=workspace, limit=limit)


def audit_total(workspace=None):
    """How many entries exist, as against how many a page shows."""
    return ws.audit_total(workspace_slug=workspace)


def admin_overview():
    """Every workspace at once. Only reachable by a super admin.

    This is the one function in this module that is not scoped to a tenant, and
    it is deliberately the only one: a reader auditing "what can cross a
    workspace boundary" has exactly one place to look.
    """
    rows = ws.load()
    spaces = ws.workspaces(rows)
    recs = store.load()
    all_campaigns = campaign_store.load()
    by_client = {}
    for rec in recs:
        bucket = by_client.setdefault(rec.get("client"),
                                      {"records": 0, "contacts": 0})
        bucket["records"] += 1
        bucket["contacts"] += len(rec.get("contacts") or [])

    listed = []
    for space in spaces:
        client = space.get("client") or space["slug"]
        counts = by_client.get(client) or {"records": 0, "contacts": 0}
        listed.append({
            "slug": space["slug"], "name": space.get("name") or space["slug"],
            "client": client,
            "members": len(ws.memberships(workspace_slug=space["slug"],
                                          rows=rows)),
            "records": counts["records"], "contacts": counts["contacts"],
            "campaigns": len([c for c in all_campaigns
                              if c.get("client") == client]),
        })

    people = []
    for person in sorted(ws.users(rows), key=lambda u: u["email"]):
        people.append({
            "email": person["email"], "name": person.get("name"),
            "super_admin": bool(person.get("super_admin")),
            "workspaces": sorted(
                f'{m["workspace"]}:{m["role"]}'
                for m in ws.memberships(email=person["email"], rows=rows)),
        })

    every_job = jobs.load()
    failed_jobs = [{
        "id": j.get("id"), "type": j.get("type"), "client": j.get("client"),
        "batch": j.get("batch"), "error": j.get("error"),
        "processed": j.get("processed") or 0, "failed": j.get("failed") or 0,
        "failures": (j.get("failures") or [])[:3],
    } for j in every_job if j.get("status") == jobs.FAILED]

    return {
        "workspaces": listed,
        "users": people,
        "roles": role_matrix(),
        "totals": {"records": len(recs),
                   "contacts": sum(len(r.get("contacts") or []) for r in recs),
                   "campaigns": len(all_campaigns)},
        "jobs": {"jobs": len(every_job),
                 "failed": len(failed_jobs),
                 "spending": len([j for j in every_job if j.get("spends")])},
        "failed_jobs": failed_jobs,
        "credentials": security.credential_status(),
        "audit_entries": len(ws.audit(limit=100000)),
        "demo": all(r.get("demo") for r in recs) if recs else False,
        "providers": provider_health(recs),
        "costs": spend_ledger(recs),
        "unmatched": unmatched_events(recs),
        "suppression": global_suppression(),
        "security_events": security_events(),
        "flags": feature_flags(),
        "status": system_status(recs, all_campaigns, every_job),
    }


# ------------------------------------------ the super admin's control centre
#
# Everything below is unscoped, and every one of them is reached only from
# `/admin`, which `_require_super_admin` guards. They are grouped here rather
# than scattered so that "what can a super admin see that nobody else can" has
# one place to read.


def role_matrix():
    """Which permission each role carries. Read from `workspaces`, not typed.

    A table written out by hand here would be a second statement of the
    permission model, and the second one is the one that goes stale.
    """
    return {
        "permissions": list(ws.PERMISSIONS),
        "roles": [
            {"role": role,
             "permissions": sorted(ws.permissions_of(role)),
             "count": len(ws.permissions_of(role))}
            for role in ws.ROLES],
    }


def provider_health(recs=None):
    """What each provider was asked to do, and how it answered.

    Counted off the records' own waterfall ledgers and the process-level
    observability counters. There is no health *check* here: this build makes
    no provider call, so a green light would be a light for a call nobody
    made. What is reported is what the stored history says.
    """
    from .. import observability

    recs = store.load() if recs is None else recs
    by_provider = {}
    for rec in recs:
        # `waterfall.ledger` rather than reaching into the record. The ledger's
        # shape is that module's business, and a second reader that knows it is
        # a second thing to change when it moves.
        for entry in waterfall.ledger(rec):
            provider = entry.get("provider") or "unknown"
            bucket = by_provider.setdefault(provider, {
                "provider": provider, "calls": 0, "credits": 0,
                "outcomes": {}})
            bucket["calls"] += 1
            bucket["credits"] += entry.get("expected_cost") or 0
            outcome = entry.get("result") or entry.get("stage") or "unknown"
            bucket["outcomes"][outcome] = bucket["outcomes"].get(outcome, 0) + 1
    return {
        "providers": sorted(by_provider.values(),
                            key=lambda p: (-p["calls"], p["provider"])),
        "configured": security.credential_status(),
        "observability": observability.snapshot(),
        "note": ("this build makes no provider call, so these are the stored "
                 "history and the process counters - not a live health check"),
    }


def spend_ledger(recs=None):
    """Every credit this system believes it has spent, and on what.

    CLAUDE.md: every paid call goes through `enrich.spend()`, which writes the
    waterfall ledger. This reads that ledger and nothing else, so a provider
    call that skipped `spend()` is *absent* here rather than estimated - which
    is the honest failure mode, because an audit that reports clean because it
    watched nothing is worse than no audit.
    """
    recs = store.load() if recs is None else recs
    by_client, by_call, by_stage = {}, {}, {}
    total, reported = 0, []
    for rec in recs:
        client = rec.get("client") or "unknown"
        # `waterfall.spend` is the engine's own arithmetic over one record.
        # Adding it up here rather than re-deriving it keeps one answer to
        # "what did this cost".
        summary = waterfall.spend(rec)
        total += summary["expected"]
        by_client[client] = by_client.get(client, 0) + summary["expected"]
        if summary["reported"] is not None:
            reported.append(summary["reported"])
        for entry in waterfall.ledger(rec):
            credits = entry.get("expected_cost") or 0
            call = entry.get("call") or "unknown"
            row = by_call.setdefault(call, {"call": call, "calls": 0,
                                            "credits": 0})
            row["calls"] += 1
            row["credits"] += credits
            stage = entry.get("stage") or "unknown"
            by_stage[stage] = by_stage.get(stage, 0) + credits
    return {
        "total_credits": total,
        # None, not zero. No provider in this stack reports what a call
        # actually cost, and a zero here would read as "it was free".
        "reported_cost": sum(reported) if reported else None,
        "by_client": dict(sorted(by_client.items())),
        "by_stage": dict(sorted(by_stage.items(), key=lambda kv: -kv[1])),
        "by_call": sorted(by_call.values(),
                          key=lambda r: (-r["credits"], r["call"])),
        # Named rather than left to be inferred: no provider in this stack
        # reports what a call actually cost, so this is what the ledger says
        # was planned and spent, in credits, not an invoice.
        "note": ("credits from the waterfall ledger, which is what "
                 "enrich.spend() wrote. No provider reports a currency amount, "
                 "so there is no money figure here to give."),
    }


def unmatched_events(recs=None):
    """Provider events that named nothing this system holds.

    An event that cannot be matched is left unmatched rather than attached to
    the closest guess, because a guess here pauses the wrong company. They
    belong to no workspace, which is why they surface only here.
    """
    from .. import observability

    counts = observability.counts()
    recent = [e for e in observability.recent(50)
              if e.get("type") in ("event_unknown", "webhook_rejected")]
    return {
        "unknown_events": counts.get("event_unknown", 0),
        "rejected_webhooks": counts.get("webhook_rejected", 0),
        "duplicates": counts.get("event_duplicate", 0),
        "recent": recent,
        "note": ("counters are per process and reset on restart; the "
                 "persisted ones are in work/observability.jsonl"),
    }


def global_suppression():
    """The do-not-contact list, which is global and not a workspace's to edit."""
    from .. import ingest

    try:
        entries = sorted(ingest.load_suppress())
    except Exception:                              # noqa: BLE001
        entries = []
    return {
        "count": len(entries),
        # Enough to confirm the list is loaded and to spot an obvious mistake,
        # without turning an admin screen into a place to read a client list.
        "sample": entries[:40],
        "path": ingest.SUPPRESS,
        "note": ("global and cross-workspace on purpose: a domain somebody "
                 "asked us to stop contacting must stay stopped in every "
                 "workspace, not only the one that heard about it"),
    }


def security_events(limit=60):
    """Refusals, across every workspace. Written by `app._refusal`.

    A refusal that leaves no trace is a refusal nobody can review, and
    somebody walking record ids looking for one that answers 200 is exactly
    the pattern that is invisible in a status code the attacker already has.
    """
    # Narrowed by the audit reader rather than here, so the total is
    # refusals rather than refusals-among-the-last-5,000-writes. Somebody
    # walking record ids slowly is exactly the pattern that scrolls out of
    # a fixed window of routine activity first.
    rows = ws.audit(limit=5000, action="security.refused")
    by_kind, by_actor = {}, {}
    for entry in rows:
        kind = (entry.get("metadata") or {}).get("kind") or "unknown"
        by_kind[kind] = by_kind.get(kind, 0) + 1
        actor = entry.get("actor") or "anonymous"
        by_actor[actor] = by_actor.get(actor, 0) + 1
    return {
        "total": ws.audit_total(action="security.refused"),
        "shown": len(rows),
        "by_kind": dict(sorted(by_kind.items(), key=lambda kv: -kv[1])),
        "by_actor": dict(sorted(by_actor.items(), key=lambda kv: -kv[1])[:10]),
        "recent": rows[:limit],
    }


# What is on and what is off, in one place, read from the code that decides it
# rather than from a config file that claims to. A flag page that reports its
# own copy of the answer is a flag page that can be wrong.
def feature_flags():
    import os

    from .. import push

    return [
        {"flag": "live_sending", "state": False,
         "why": "push.run(live=True) raises LiveSendNotEnabled",
         "controlled_by": "src/push.py"},
        {"flag": "campaign.launch", "state": False,
         "why": "granted to no role below super admin, and refused below that",
         "controlled_by": "src/workspaces.py"},
        {"flag": "paid_enrichment", "state": False,
         "why": "no web surface runs a spending job type",
         "controlled_by": "src/web/api.py RUNNABLE_JOBS"},
        # Derived, not asserted. `state` was computed from the environment
        # and `why` was a constant saying the switch was off, so with
        # SLACK_LIVE set this row read "on" beside "SLACK_LIVE is unset" -
        # a sending-safety surface contradicting the thing it had just
        # displayed.
        {"flag": "slack_posting", "state": bool(os.environ.get("SLACK_LIVE")),
         "why": ("SLACK_LIVE is set, so a post with a token reaches Slack"
                 if os.environ.get("SLACK_LIVE")
                 else "SLACK_LIVE is unset, so posts are planned and printed"),
         "controlled_by": "SLACK_LIVE"},
        {"flag": "demo_mode", "state": None,
         "why": "set per process by --demo; shown in the header of every page",
         "controlled_by": "py -m src.web --demo"},
        {"flag": "web_debug", "state": bool(os.environ.get("WEB_DEBUG")),
         "why": "prints a traceback on a 500 instead of swallowing it",
         "controlled_by": "WEB_DEBUG"},
    ]


def system_status(recs=None, campaigns=None, every_job=None):
    """Where the state actually lives, and how much of it there is."""
    import os

    from .. import campaigns as campaign_store

    recs = store.load() if recs is None else recs
    campaigns = campaign_store.load() if campaigns is None else campaigns
    every_job = jobs.load() if every_job is None else every_job

    def described(path_):
        return {"path": path_, "exists": os.path.exists(path_),
                "bytes": os.path.getsize(path_)
                if os.path.exists(path_) else 0}

    return {
        "files": {
            "queue": described(store.queue_path()),
            "campaigns": described(campaign_store.path()),
            "jobs": described(jobs.path()),
            "workspaces": described(ws.path()),
            "audit": described(ws.audit_path()),
        },
        "counts": {"records": len(recs), "campaigns": len(campaigns),
                   "jobs": len(every_job),
                   "workspaces": len(ws.workspaces()),
                   "users": len(ws.users())},
        "python": __import__("sys").version.split()[0],
        # Named because it is the thing that changes when this leaves a laptop.
        "note": ("one process, a file store and a lock. DATABASE-MIGRATION.md "
                 "is explicit that files stop being enough when two processes "
                 "need to write at once, which is the day a worker is added.")
    }


# ------------------------------------------------------ advanced reporting

# Every dimension an operator can group by, and where the value comes from.
# Company dimensions repeat down onto each of that company's contacts, which
# is what lets one row set answer both "how many companies in DACH" and "what
# share of DACH contacts are sendable" with denominators that agree.
COMPANY_DIMENSIONS = (
    ("batch", "Batch"),
    ("region", "Region"),
    ("country", "Country"),
    ("timezone", "Timezone"),
    ("vertical", "Vertical"),
    ("subvertical", "Subvertical"),
    ("industry", "Industry"),
    ("employee_band", "Employee band"),
    ("icp_tier", "ICP tier"),
    ("icp_status", "ICP status"),
    # Whether we may write to this company at all. Client-facing on
    # purpose: a client is entitled to know which of their accounts are
    # off limits and why, and "we are not contacting these" is an outcome
    # rather than a method.
    ("outreach_state", "Outreach state"),
)

# How we rank accounts and what we are ranking on. Operator-only, for the
# same reason `personalization` is: it names internal method. A client
# reads which of their accounts we may work; how we ordered the rest is
# ours.
ACCOUNT_DIMENSIONS = (
    ("priority_tier", "Priority tier"),
    ("live_signal", "Live signal"),
)

CONTACT_DIMENSIONS = (
    ("persona", "Persona"),
    ("angle", "Angle"),
    ("mode", "Channel strategy"),
    ("mx_provider", "Email security provider"),
    ("mx_category", "MX category"),
    ("email_source", "Contact provider"),
    ("verifier", "Confirming verifier"),
    # "Personalisation strategy vs performance, where measurable" - the
    # qualifier is load-bearing. Nothing has been sent from this build, so
    # there is no performance to correlate against yet; what this dimension
    # gives now is the population split, and the reply columns fill in the day
    # a campaign runs. Building it later would mean building it against data
    # already collected under a scheme nobody recorded.
    ("personalization", "Personalisation band"),
)

DIMENSIONS = (COMPANY_DIMENSIONS + ACCOUNT_DIMENSIONS
              + CONTACT_DIMENSIONS)

# What a client-facing role may group by. The four that are missing -
# `mx_provider`, `mx_category`, `email_source` and `verifier` - are the vendor
# stack, and a dropdown listing them names every supplier in the pipeline. A
# breakdown screen is an odd place to disclose that, so it does not: the
# dimension list is narrowed on the server, and a dimension outside the list
# falls back rather than being honoured.
CLIENT_DIMENSIONS = COMPANY_DIMENSIONS


def analytics_rows(repo, filters=None):
    """One row per contact, carrying its company's dimensions too.

    Nothing here decides anything: the channel verdict comes from
    `channels.evaluate`, the verification state from `verification.resolve` and
    the segment from what `qualify.run` already stored. This function joins and
    counts, which is the only arithmetic a reporting surface is allowed.
    """
    from .. import events as event_model
    config = repo.config()
    policy = verification.policy_for(config)
    # Read once for the whole report rather than once per contact inside
    # `channels.evaluate`, which is what it does when it is not handed one.
    suppressed = ingest.load_suppress()
    signal_index = signals_module.index(repo.workspace)
    rows = []
    for rec in repo.records():
        qualification = rec.get("qualification") or {}
        seg = qualification.get("segment") or {}
        verdict = qualification.get("verdict") or {}
        replies = {}
        for entry in rec.get("events") or []:
            if entry.get("type") == event_model.REPLY_CLASSIFIED:
                replies.setdefault(entry.get("contact"), []).append(
                    entry.get("classification") or "unknown")
        company = {
            "record_id": rec["id"],
            "company": rec.get("company"),
            "domain": rec.get("domain"),
            "batch": rec.get("batch"),
            "state": rec.get("state"),
            "region": seg.get("region") or "Unknown",
            "country": (seg.get("country") or "").title() or "Unknown",
            "timezone": seg.get("timezone") or "Unknown",
            "vertical": seg.get("vertical") or "Unknown",
            "subvertical": seg.get("subvertical") or "UNKNOWN",
            "industry": seg.get("industry") or "Unknown",
            "employee_band": seg.get("employee_band") or "UNKNOWN",
            "icp_tier": verdict.get("icp_tier") or "none",
            "icp_status": verdict.get("icp_status") or "unknown",
        }
        # Priority and eligibility, joined rather than recomputed: the same
        # `assess` the account screen and the campaign brief read, so a
        # breakdown cannot disagree with the page it was opened from.
        found = priority_module.assess(rec, repo.workspace, config,
                                       suppressed=suppressed,
                                       signal_index=signal_index)
        company["priority_tier"] = found["tier"]
        company["outreach_state"] = (
            "eligible" if found["eligibility"]["eligible"]
            else (found["eligibility"]["blocked"] or "not eligible"))
        # Whether anything is happening *at* the company. Our own touches
        # are engagement, not observation, and counting them here would
        # make every contacted account look like it had a signal.
        company["live_signal"] = ("yes" if any(
            s["scope"] != signals_module.ENGAGEMENT
            and s["freshness"] != signals_module.STALE
            for s in found["signals"]) else "no")
        contacts = rec.get("contacts") or []
        if not contacts:
            rows.append(dict(company, contact_key=None, has_contact=False,
                             persona="none", angle="none", mode="none",
                             mx_provider="no address", mx_category="none",
                             email_source="none", verifier="none",
                             personalization="none",
                             email_eligible=False, linkedin_eligible=False,
                             held=False, sendable=False, double_verified=False,
                             replies=[], positive=0))
            continue
        for contact in contacts:
            verdicts = channels.evaluate(rec, contact, config, suppressed)
            decision = (verification.resolve(contact, policy)
                        if contact.get("email") else {})
            stored = mx.stored_decision(contact) or {}
            confirmed = decision.get("confirmed_by") or []
            kinds = replies.get(contact.get("key")) or []
            rows.append(dict(
                company,
                contact_key=contact.get("key"),
                has_contact=True,
                persona=contact.get("persona") or "none",
                angle=contact.get("angle") or "none",
                mode=verdicts["mode"],
                mx_provider=(stored.get("security_provider")
                             or stored.get("mailbox_provider")
                             or ("unknown" if contact.get("email")
                                 else "no address")),
                mx_category=stored.get("category") or "none",
                email_source=contact.get("email_source") or "none",
                verifier=("+".join(sorted(confirmed)) if confirmed else "none"),
                # `quality.assess` is the engine's own judgement of how well
                # this message is grounded in evidence. Asked, not recomputed.
                personalization=(quality.assess(rec, contact, config)
                                 .get("band") or "none"),
                email_eligible=bool(verdicts["email_eligible"]),
                linkedin_eligible=bool(verdicts["linkedin_eligible"]),
                held=bool(verdicts["held"]),
                sendable=verdicts["mode"] != channels.NONE,
                double_verified=bool(
                    decision.get("confirmation_count", 0)
                    >= decision.get("required_confirmations", 99)),
                replies=kinds,
                positive=len([k for k in kinds if k == "positive"]),
            ))
    for field, value in (filters or {}).items():
        if value:
            rows = [r for r in rows if str(r.get(field)) == str(value)]
    return rows


def _measure(rows):
    """Counts first, and every rate carried with the pair it came from."""
    companies = {r["record_id"] for r in rows}
    contacts = [r for r in rows if r["has_contact"]]
    sendable = [r for r in contacts if r["sendable"]]
    return {
        "companies": len(companies),
        "contacts": len(contacts),
        "sendable": len(sendable),
        "email_eligible": len([r for r in contacts if r["email_eligible"]]),
        "linkedin_eligible": len([r for r in contacts
                                  if r["linkedin_eligible"]]),
        "held": len([r for r in contacts if r["held"]]),
        "double_verified": len([r for r in contacts if r["double_verified"]]),
        "replies": sum(len(r["replies"]) for r in contacts),
        "positive": sum(r["positive"] for r in contacts),
        # Every percentage on a page is rendered from one of these pairs, so
        # the numerator and the denominator are both on screen next to it.
        "rates": {
            "sendable": (len(sendable), len(contacts)),
            "email_eligible": (len([r for r in contacts if r["email_eligible"]]),
                               len(contacts)),
            "linkedin_eligible": (
                len([r for r in contacts if r["linkedin_eligible"]]),
                len(contacts)),
            "double_verified": (
                len([r for r in contacts if r["double_verified"]]),
                len(contacts)),
            "reply": (sum(len(r["replies"]) for r in contacts), len(sendable)),
            "positive": (sum(r["positive"] for r in contacts), len(sendable)),
        },
    }


def analytics(repo, dimension=None, filters=None, dimensions=None):
    """Filtered totals plus one breakdown, with every denominator stated.

    `dimensions` narrows what may be grouped or filtered by. It is not a UI
    hint: a value outside the list is dropped from the filters and the grouping
    falls back, so a client-facing role cannot reach an operator's dimension by
    editing the query string.
    """
    dimensions = tuple(dimensions or DIMENSIONS)
    known = dict(dimensions)
    dimension = dimension or dimensions[0][0]
    if dimension not in known:
        dimension = dimensions[0][0]
    filters = {k: v for k, v in (filters or {}).items() if k in known}
    rows = analytics_rows(repo, filters)
    groups = {}
    for row in rows:
        groups.setdefault(str(row.get(dimension)), []).append(row)
    breakdown = [dict(_measure(group), value=value)
                 for value, group in sorted(groups.items())]
    breakdown.sort(key=lambda b: (-b["contacts"], b["value"]))
    every = analytics_rows(repo)
    return {
        "dimension": dimension,
        "dimension_label": known[dimension],
        "dimensions": dimensions,
        "filters": {k: v for k, v in filters.items() if v},
        "totals": _measure(rows),
        "breakdown": breakdown,
        "choices": {field: sorted({str(r.get(field)) for r in every})
                    for field, _ in dimensions},
        # Nothing was sent, so no delivery-side rate can be reported at all.
        # A zero here would read as "we sent and nobody replied".
        "unavailable": report.unavailable(),
    }


def comparison(repo, dimension=None, left=None, right=None, dimensions=None):
    """Two slices side by side, each with its own sample size.

    A comparison with no denominators is how "DACH converts better than UK"
    gets said about eleven contacts. Both sample sizes travel with the numbers,
    and a slice smaller than `SMALL_SAMPLE` is labelled as one.
    """
    dimensions = tuple(dimensions or DIMENSIONS)
    known = dict(dimensions)
    dimension = dimension or dimensions[0][0]
    if dimension not in known:
        dimension = dimensions[0][0]
    rows = analytics_rows(repo)
    values = sorted({str(r.get(dimension)) for r in rows})
    left = left if left in values else (values[0] if values else None)
    right = right if right in values else (values[1] if len(values) > 1
                                           else left)
    sides = []
    for value in (left, right):
        group = [r for r in rows if str(r.get(dimension)) == str(value)]
        sides.append(dict(_measure(group), value=value,
                          small_sample=len(group) < SMALL_SAMPLE))
    return {
        "dimension": dimension,
        "dimension_label": known[dimension],
        "dimensions": dimensions,
        "values": values,
        "left": sides[0],
        "right": sides[1],
        "small_sample_threshold": SMALL_SAMPLE,
    }


# Below this many contacts a difference between two slices is noise. Named
# rather than inlined, because the number is a judgement and should be
# arguable in one place.
SMALL_SAMPLE = 30


# ------------------------------------------------------------ exports

# How many imported columns an export will carry back. A file with two
# hundred columns is a file whose export nobody can open, and the cap is
# stated rather than applied quietly - see `export_contacts`.
# Which LinkedIn step is a connection request rather than a message.
# `cadence.STEPS` says day3 carries the note; everything else on that
# channel is a message, and the acceptance rate's denominator is the
# requests alone.
LINKEDIN_REQUEST_STEP = "day3"

MAX_SOURCE_COLUMNS = 20


def export_contacts(repo, batch=None):
    """Contact-level CSV. Written through the same guard the CLI export uses.

    The columns an import did not recognise come back too, prefixed
    `source:`. They are kept on the contact, the upload screen says they
    are kept, and until now nothing could hand them back - so a phone
    number, a CRM id or an owner name arrived, was stored, and was
    reachable by nobody. They are still never read to decide anything.
    """
    rows = contact_rows(repo, batch)
    headers = ["record_id", "contact_key", "company", "domain", "batch",
               "name", "title", "persona", "email", "linkedin", "mode",
               "email_eligible", "email_reason", "linkedin_eligible",
               "linkedin_reason", "confirmations", "required",
               # So an operator can sort a spreadsheet and answer the one
               # question in `MANUAL-REVIEW.md` 9b: would you send to the
               # oldest of these today? Blank means undated, which a
               # legacy verdict is - not new.
               "oldest_evidence_days", "mx_provider",
               "mx_category", "held"]

    extra = sorted({key for row in rows for key in (row.get("source") or {})})
    dropped = extra[MAX_SOURCE_COLUMNS:]
    extra = extra[:MAX_SOURCE_COLUMNS]
    body = []
    for row in rows:
        source = row.get("source") or {}
        body.append([row.get(h) for h in headers]
                    + [source.get(name) for name in extra])
    if dropped:
        # Said in the header rather than silently omitted. A column that
        # vanishes from an export is indistinguishable from one the file
        # never had.
        headers = headers + [f"source:{name}" for name in extra] + [
            f"source:{len(dropped)} more columns not exported"]
        body = [line + [None] for line in body]
    else:
        headers = headers + [f"source:{name}" for name in extra]
    return export.to_csv(headers, body)


def export_analytics(repo, dimension=None, filters=None, dimensions=None):
    """The breakdown exactly as rendered, including both halves of each rate."""
    data = analytics(repo, dimension, filters, dimensions)
    headers = ["value", "companies", "contacts", "sendable",
               "sendable_denominator", "email_eligible", "linkedin_eligible",
               "double_verified", "held", "replies", "positive"]
    body = []
    for entry in data["breakdown"]:
        body.append([entry["value"], entry["companies"], entry["contacts"],
                     entry["sendable"], entry["rates"]["sendable"][1],
                     entry["email_eligible"], entry["linkedin_eligible"],
                     entry["double_verified"], entry["held"],
                     entry["replies"], entry["positive"]])
    return export.to_csv(headers, body)


# ------------------------------------------------------------------- Slack
#
# Two levels, and the web layer keeps them apart the same way `notify` does.
# `slack_overview` is unscoped and reachable only from `/admin/slack`, which
# `_require_super_admin` guards. Everything else below takes a `Repo` and can
# therefore only ever see one workspace, because a `Repo` cannot be built for
# a workspace the caller is not a member of.


def slack_overview(rows=None):
    """Every workspace's Slack routing at once, for the super admin.

    The point of the table is the column that is usually empty. A workspace
    with no channel is not a workspace whose alerts go somewhere sensible by
    default - it is a workspace whose positive replies reach nobody, and the
    only place that is visible is here.

    Collisions are reported rather than resolved. Two workspaces pointing at
    one channel is a decision somebody may have made on purpose (two brands,
    one client, one room) and it is not this function's place to pick a
    winner - but it is very much its place to say so out loud, because the
    same shape is what an accidental copy-paste looks like.
    """
    rows = ws.load() if rows is None else rows
    notifications = notify.load()
    spaces = ws.workspaces(rows)
    listed, channels_seen = [], {}
    for space in spaces:
        slug = space["slug"]
        channel = notify.workspace_channel(slug, rows)
        if channel:
            channels_seen.setdefault(channel, []).append(slug)
        toggles = []
        for event_type, (key, _default) in sorted(
                notify.WORKSPACE_TOGGLES.items()):
            allowed, why = notify.workspace_allows(event_type=event_type,
                                                   slug=slug, rows=rows)
            toggles.append({"event": event_type, "key": key,
                            "allowed": allowed, "why": why,
                            "label": _toggle_label(key)})
        mine = [n for n in notifications if n.get("workspace") == slug]
        listed.append({
            "slug": slug,
            "name": space.get("name") or slug,
            "channel": channel,
            "configured": bool(channel),
            "toggles": toggles,
            "notifications": len(mine),
            "last": max((n.get("at") for n in mine), default=None),
        })

    ops = notify.ops_channel()
    return {
        "ops_channel": ops,
        "ops_channel_var": notify.OPS_CHANNEL_VAR,
        "ops_configured": bool(ops),
        "live": slack.live(),
        "workspaces": listed,
        "unconfigured": [w["slug"] for w in listed if not w["configured"]],
        "collisions": {channel: slugs
                       for channel, slugs in sorted(channels_seen.items())
                       if len(slugs) > 1},
        "routes": [{"event": event_type,
                    "destination": notify.ROUTES[event_type][0],
                    "severity": notify.ROUTES[event_type][1]}
                   for event_type in notify.EVENT_TYPES],
        "summary": notify.summarise(rows=notifications),
        "recent": notify.history(limit=25, rows=notifications),
        "channel_key": notify.WORKSPACE_CHANNEL_KEY,
    }


def workspace_slack(repo):
    """One workspace's Slack status: the channel, the toggles, the last alert.

    Scoped by construction. `notify.status_for` reads the workspace it is
    given and no other, and the slug here comes from the `Repo`, which came
    from a membership check.
    """
    status = notify.status_for(repo.workspace)
    toggles = []
    for event_type, (key, _default) in sorted(
            notify.WORKSPACE_TOGGLES.items()):
        allowed, why = notify.workspace_allows(slug=repo.workspace,
                                               event_type=event_type)
        toggles.append({"event": event_type, "key": key, "allowed": allowed,
                        "why": why, "label": _toggle_label(key)})
    mine = notify.history(repo.workspace, limit=100000)
    return {
        "workspace": repo.workspace,
        "channel": status["channel"],
        "configured": status["configured"],
        "live": status["live"],
        "toggles": toggles,
        "last_alert": status["last_alert"],
        "summary": notify.summarise(repo.workspace, rows=mine),
        "recent": mine[:10],
        "channel_key": notify.WORKSPACE_CHANNEL_KEY,
        "can_manage": repo.may(ws.WORKSPACE_MANAGE),
    }


def _toggle_label(key):
    """The policy's own label, never its identifier and never a tuple.

    `WORKSPACE_TOGGLES` values are (key, default) pairs, and unpacking one as
    a bare key put `('slack.notify_reports', False)` on the dashboard.
    """
    if isinstance(key, (tuple, list)):                       # defensive
        key = key[0] if key else ""
    spec = ws.POLICY_KEYS.get(key) or {}
    return spec.get("label") or str(key)


def notification_history(repo=None, event_type=None, status=None, limit=200):
    """The notification log, for one workspace or - for a super admin - all.

    `repo=None` is the unscoped read and is reachable only through the
    super-admin branch in the handler. Passing a `Repo` is the ordinary case
    and it can only produce that workspace's rows.
    """
    scope = repo.workspace if repo is not None else None
    rows = notify.history(scope, event_type or None, status or None,
                          limit=limit)
    return {
        "scope": scope,
        "rows": [_notification_row(r) for r in rows],
        "summary": notify.summarise(scope),
        "event_types": list(notify.EVENT_TYPES),
        "statuses": list(notify.STATUSES),
        "filters": {"type": event_type or "", "status": status or ""},
        "live": slack.live(),
    }


def announce_report(repo, kind, by, **detail):
    """Two notifications for one report, and they say different things.

    The operations channel gets the fact that a report was produced, by whom,
    and for which workspace - that is an audit trail somebody watches across
    every client. The workspace's own channel gets a note that its report is
    ready, and only if that workspace switched the kind on.

    They are two rows rather than one message copied to two rooms, because
    they carry different fields and a shared row would eventually leak the
    wrong half into the wrong room.
    """
    workspace = repo.workspace
    operational = notify.notify(
        notify.REPORT_GENERATED, workspace,
        fields={"report": kind, "by": by, **detail},
        ids={"workspace": workspace, "report": kind,
             "at": detail.get("at")})
    available = notify.notify(
        notify.REPORT_AVAILABLE, workspace,
        fields={"report": kind, "period": detail.get("period")},
        ids={"workspace": workspace, "report": kind,
             "at": detail.get("at")})
    return {"operational": operational, "workspace": available}


def slack_demo():
    """The eight fictional scenarios and where each one would go.

    Reachable only in demo mode. The routing decision is asked of `notify`
    rather than written down here, so a demo that disagreed with the engine
    would be a demo of nothing.
    """
    from .demoslack import scenarios

    listed = scenarios()
    return {
        "scenarios": listed,
        "ops_channel": notify.ops_channel(),
        "live": slack.live(),
        "workspaces": sorted({s["workspace"] for s in listed if s["workspace"]}),
        "to_global": len([s for s in listed if s["destination"] == "global"]),
        "to_workspace": len([s for s in listed
                             if s["destination"] == "workspace"]),
        "nowhere": len([s for s in listed if s["status"] == "unconfigured"]),
    }


def _notification_row(row):
    """One line of the history table.

    The rendered text goes with it, because "which channel did this go to and
    what did it say" is one question and answering half of it sends the reader
    to the JSONL file.
    """
    return {
        "id": row.get("id"),
        "at": row.get("at"),
        "workspace": row.get("workspace"),
        "type": row.get("type"),
        "destination": row.get("destination"),
        "severity": row.get("severity"),
        "status": row.get("status"),
        "channel": row.get("channel"),
        "why": row.get("why"),
        "attempts": row.get("attempts") or 0,
        "last_error": row.get("last_error"),
        "text": notify.render(row),
    }


def report_row(repo, report_id):
    """One report from this workspace's history, or None.

    Scoped by construction: the row must name this workspace. A report id from
    another workspace returns None, and the handler answers 404 - a report id
    that exists elsewhere must not be distinguishable from one that never
    existed.
    """
    if not report_id:
        return None
    row = report_store.get(str(report_id))
    if row is None or row.get("workspace") != repo.workspace:
        return None
    return row


def report_filename(repo, row):
    return clientreport.filename({
        "workspace_slug": repo.workspace,
        "template": row.get("template"),
        "period": row.get("period"),
    })


def regenerate_report(repo, row, by="unknown", demo=False):
    """Rebuild a historic report from its stored settings.

    The bytes were never stored - see `src/reports.py` - so a download
    re-renders from the settings the row carries. That is the honest
    behaviour: if the underlying numbers have since been corrected, the
    document a client downloads today shows the corrected ones rather than
    quietly preserving a figure the system no longer stands behind.

    The download is counted on the original row, and the rebuild does not
    create a second history entry. Downloading a report is not generating one.
    """
    template = allowed_template(repo, row.get("template"))
    sections = clientreport.resolve_sections(template, row.get("sections"))
    period = row.get("period") or "All time"
    since = until = None
    if " to " in period:
        since, _, until = period.partition(" to ")
    meta = {
        "workspace_name": (ws.workspace(repo.workspace) or {}).get("name")
                          or repo.workspace,
        "workspace_slug": repo.workspace,
        "template": template,
        "period": period,
        "campaign_label": (", ".join(row.get("campaigns") or [])
                           or "All campaigns"),
        "generated_by": row.get("by") or by,
        "report_id": row.get("id"),
        "generated_at": store.now()[:10],
        "demo": bool(demo),
    }
    try:
        data = report_data(repo, row.get("campaigns"), since, until)
        raw = clientreport.build(data, meta, sections)
    except Exception as e:                                  # noqa: BLE001
        updated = report_store.mark(row["id"], report_store.FAILED,
                                    error=f"{type(e).__name__}: {e}"[:300])
        repo.audit("report.failed", "report", row["id"],
                   metadata={"stage": "download",
                             "error": type(e).__name__})
        return updated or row, None

    updated = report_store.mark(row["id"], report_store.DOWNLOADED,
                                bytes=len(raw))
    repo.audit("report.downloaded", "report", row["id"],
               metadata={"template": template, "bytes": len(raw)})
    return updated or row, raw


# ----------------------------------------------------- workspace onboarding
#
# What a workspace still needs before it can run outreach. Every item is
# checked against stored state rather than remembered as a flag: a checklist
# that a person ticks is a checklist that says "senders configured" about a
# workspace with no senders.


class WorkspaceRefused(RuntimeError):
    """A workspace was not created, and the message says why."""


def create_workspace(slug, name, domain, booking_link=None, by="unknown"):
    """A new client: the workspace row and a starter config, together.

    Both or neither. A workspace with no config cannot load a client and a
    config with no workspace is a file nobody owns, and having one without
    the other is the state somebody discovers three screens later.

    The starter carries a name, a domain and a booking link. It carries no
    market and no personas on purpose - the readiness list is meant to say
    those are missing, and a placeholder ICP is a placeholder that gets
    used to select real people.
    """
    slug = str(slug or "").strip().lower()
    if not clients.valid_slug(slug):
        raise WorkspaceRefused(
            "a workspace name is lower case letters, digits and hyphens, "
            "two characters or more - " + (slug or "nothing") + " is not")
    if ws.workspace(slug):
        raise WorkspaceRefused(f"the workspace {slug} already exists")
    if clients.exists(slug):
        raise WorkspaceRefused(
            f"config/clients/{slug}.yaml already exists, so this name "
            "belonged to somebody before")
    if not str(name or "").strip():
        raise WorkspaceRefused("a workspace needs a display name")

    # The file first. A failed write leaves no workspace row behind, which
    # is the direction worth failing in: a row with no config is a tenant
    # that half exists.
    clients.create(slug, name, domain or "", booking_link or "",
                   created_by=by)
    try:
        entry = ws.ensure(slug, name, client=slug, created_by=by)
    except Exception:                                     # noqa: BLE001
        import os
        try:
            os.remove(clients.path_for(slug))
        except OSError:
            pass
        raise
    return entry


def onboarding(repo):
    """The readiness checklist for one workspace.

    Nothing here calls a provider. Every step is answered from what is already
    stored, so completing the list costs nothing and can be done entirely
    offline - which is the point: a workspace should be able to reach "ready
    to review a campaign" without a single paid call.

    `blocked_by` names the step that has to happen first, so the list reads as
    a sequence rather than as a wall of red.
    """
    config = repo.config()
    recs = repo.records()
    campaigns = repo.campaigns()
    roster = senderidentity.roster(repo.workspace)
    counts = roster.get("counts") or {}
    policy = ws.policy(repo.workspace)
    entry = ws.workspace(repo.workspace) or {}
    members = ws.memberships(workspace_slug=repo.workspace)

    qualified = [r for r in recs
                 if ((r.get("qualification") or {}).get("verdict") or {})
                 .get("status") == "qualified"]
    approved = [c for c in campaigns
                if c.get("status") == campaign_store.APPROVED]
    channel = notify.workspace_channel(repo.workspace)

    steps = [
        _step("workspace", "Workspace created", True,
              f"{entry.get('name') or repo.workspace}, created "
              f"{entry.get('created_at') or 'at an unrecorded time'}",
              "/workspaces"),
        _step("members", "People invited", bool(members),
              f"{len(members)} member(s)", "/users",
              "Nobody can review a campaign for a workspace they cannot "
              "enter."),
        _step("icp", "ICP configured",
              bool((config.get("market") or {}).get("must")),
              (config.get("market") or {}).get("must")
              or "no market rule in the client config", "/settings",
              "Qualification is what stops person-level credits being spent "
              "on companies that were never a fit."),
        _step("personas", "Personas configured", bool(config.get("personas")),
              f"{len(config.get('personas') or {})} persona(s)", "/settings"),
        _step("senders", "Sender identities configured",
              bool(counts.get("senders")),
              f"{counts.get('senders') or 0} human identity(ies)", "/senders",
              "A sender is a person. Inboxes and LinkedIn profiles belong to "
              "one."),
        _step("email_accounts", "Email infrastructure configured",
              bool(counts.get("email_accounts")),
              f"{counts.get('email_accounts') or 0} inbox(es)", "/senders"),
        _step("linkedin_accounts", "LinkedIn infrastructure configured",
              bool(counts.get("linkedin_accounts")),
              f"{counts.get('linkedin_accounts') or 0} profile(s)", "/senders",
              "LinkedIn capacity is usually the limit on a campaign, not "
              "list size."),
        _step("slack", "Slack channel mapped", bool(channel),
              channel or "no channel; positive replies are recorded and go "
                         "nowhere", "/settings",
              "Never inferred from the workspace name, and never falls back "
              "to another client's room.", optional=True),
        _step("reporting", "Report defaults chosen",
              bool(policy.get("reporting.default_template")),
              policy.get("reporting.default_template")
              or "using the executive template", "/reporting/client",
              optional=True),
        _step("batch", "Domains uploaded", bool(recs),
              f"{len(recs)} company(ies)", "/upload",
              blocked_by=None if recs else "icp"),
        _step("qualified", "Companies qualified", bool(qualified),
              f"{len(qualified)} qualified of {len(recs)}", "/icp",
              blocked_by=None if recs else "batch"),
        _step("campaign", "Campaign built", bool(campaigns),
              f"{len(campaigns)} campaign(s)", "/campaigns",
              blocked_by=None if qualified else "qualified"),
        _step("approved", "Campaign approved", bool(approved),
              f"{len(approved)} approved", "/approvals",
              blocked_by=None if campaigns else "campaign"),
    ]

    required = [s for s in steps if not s["optional"]]
    done = [s for s in required if s["done"]]
    return {
        "workspace": repo.workspace,
        "workspace_name": entry.get("name") or repo.workspace,
        "steps": steps,
        "done": len(done),
        "total": len(required),
        "complete": len(done) == len(required),
        "next": next((s for s in steps
                      if not s["done"] and not s["optional"]), None),
        # Named rather than implied. Finishing this list does not enable
        # sending, and a checklist that read as "ready to go live" would be
        # the most misleading screen in the product.
        "note": ("Completing this list makes a workspace ready to build and "
                 "review a campaign. It does not enable sending: live "
                 "outreach is disabled in this build, and turning it on is a "
                 "separate authorised procedure."),
    }


def _step(key, label, done, detail, where, why=None, optional=False,
          blocked_by=None):
    return {"key": key, "label": label, "done": bool(done), "detail": detail,
            "where": where, "why": why, "optional": optional,
            "blocked_by": blocked_by}


# ------------------------------------------------------------ system health
#
# Unscoped, and reached only from the super admin's console. Every component
# reports one of five states, and the one that matters most is
# NEEDS_LIVE: a provider that has only ever been exercised against a recorded
# contract is not healthy and is not broken - it is unvalidated. Saying so is
# the difference between a status page and a decoration.

HEALTHY = "healthy"
DEGRADED = "degraded"
UNCONFIGURED = "unconfigured"
NEEDS_LIVE = "live validation required"
FAILED_STATE = "failed"
# Configured, contract exercised offline, and never called in this build.
# Distinct from healthy on purpose: nothing here has spoken to a wire.
NOT_CALLED = "configured, not called"

STATE_ORDER = (HEALTHY, NOT_CALLED, NEEDS_LIVE, UNCONFIGURED, DEGRADED,
               FAILED_STATE)


# Which files hold rows, so an absent one can be judged. The rest are
# append-only logs: they come into existence on the first write, and their
# absence means nothing has happened yet.
_ROW_FILES = {"queue": "records", "campaigns": "campaigns",
              "workspaces": "workspaces", "jobs": "jobs"}


def _state_store_health(status):
    """Healthy, and if not, which file and why - not an unrelated note.

    `all(exists)` reported *degraded* on a fresh install, because
    `jobs.jsonl` does not exist until a job runs. Worse, the explanation
    beside it was the standing note about one process and a lock, which has
    nothing to do with a missing file - so the state and its reason were
    about different things.
    """
    absent = [name for name, entry in status["files"].items()
              if not entry["exists"]]
    # A store missing while its rows are loaded is a real fault. A log that
    # nothing has written to yet is the correct representation of nothing.
    broken = [name for name in absent
              if status["counts"].get(_ROW_FILES.get(name, ""), 0)]
    if broken:
        return DEGRADED, (
            f"{', '.join(sorted(broken))} absent on disk while rows are "
            f"loaded from it. That is a fault, not a fresh install. "
            + status["note"])
    empty = [name for name in absent if name not in broken]
    note = status["note"]
    if empty:
        note = (f"{', '.join(sorted(empty))} not written yet - an append-only "
                f"log comes into existence on its first write. " + note)
    return HEALTHY, note


def system_health():
    """Every component, its state, and why it is in that state."""
    from .. import config as app_config

    components = []

    status = system_status()
    state, why = _state_store_health(status)
    components.append(_component(
        "State store", state,
        f"{status['counts']['records']} records, "
        f"{status['counts']['campaigns']} campaigns, "
        f"{status['counts']['workspaces']} workspaces",
        why))

    every_job = jobs.load()
    failed = [j for j in every_job if j.get("status") == jobs.FAILED]
    components.append(_component(
        "Jobs", DEGRADED if failed else HEALTHY,
        f"{len(every_job)} job(s), {len(failed)} failed",
        "Jobs run in this process and resume from a checkpoint. The worker "
        "split is described in DEPLOYMENT-PLAN.md."))

    components.append(_component(
        "Scheduler", NEEDS_LIVE, "not running",
        "Nothing schedules work in this build. Cadence timing is computed "
        "and displayed; no process advances it."))

    components.append(_component(
        "Reply poller", NEEDS_LIVE, "not running",
        "Inbound events are applied when handed to src/inbound.py. No "
        "process polls a provider for them yet."))

    ops_channel = notify.ops_channel()
    posting = slack.live()
    components.append(_component(
        "Slack", (UNCONFIGURED if not ops_channel
                  else HEALTHY if posting else NEEDS_LIVE),
        f"posting {'live' if posting else 'disabled'}; operations channel "
        f"{ops_channel or 'not set'}",
        "Notifications are routed, recorded and rendered. None is posted "
        "while SLACK_LIVE is unset."))

    rows = report_store.load()
    broken = [r for r in rows if r.get("status") == report_store.FAILED]
    components.append(_component(
        "Report generation", DEGRADED if broken else HEALTHY,
        f"{len(rows)} generated, {len(broken)} failed",
        "PDFs render on request from stored settings; no bytes are archived, "
        "so a corrected figure corrects the document."))

    configuration = app_config.report()
    components.append(_component(
        "Configuration",
        FAILED_STATE if configuration["blockers"] else HEALTHY,
        f"mode {configuration['mode']}"
        + (f"; missing {', '.join(configuration['blockers'])}"
           if configuration["blockers"] else ""),
        "Demo mode needs no credentials. Production fails closed - see "
        "python -m src.config."))

    return {
        "components": components,
        "providers": provider_states(),
        "configuration": configuration,
        "worst": _worst([c["state"] for c in components]),
    }


def _component(name, state, detail, why):
    return {"name": name, "state": state, "detail": detail, "why": why}


def _worst(states):
    if not states:
        return HEALTHY
    return max(states,
               key=lambda s: STATE_ORDER.index(s) if s in STATE_ORDER else 0)


# (display name, environment variable, is the offline contract exercised,
#  has the live wire ever been validated, one line about what it is for)
#
# The fourth column is the honest one. "Offline contract" means the suite
# exercises a recorded response; it does not mean anybody has ever spoken to
# the wire. Deliverable is the one provider where those differ, and it is
# marked so rather than being quietly rounded up.
PROVIDERS = (
    ("ContactOut", "CONTACTOUT_TOKEN", True, True,
     "company-first enrichment. People-count is free; everything else burns "
     "credits"),
    ("AI Ark", "AIARK_KEY", True, True, "enrichment"),
    ("Reoon", "REOON_KEY", True, True,
     "escalation verifier, reached only when two providers disagree"),
    ("Deliverable", "DELIVERABLE_KEY", True, False,
     "verification. Endpoints and auth are documented; the response shape "
     "has never been read from a live answer, and verify() refuses to spend "
     "a credit until one has been read"),
    ("EmailBison", "BISON_KEY", True, True, "email sending platform"),
    ("HeyReach", "HEYREACH_KEY", True, True, "LinkedIn platform"),
    ("Apify", "APIFY_TOKEN", True, True,
     "research actors. Bounded and SSRF-guarded"),
    ("Slack", "SLACK_BOT_TOKEN", True, True,
     "notifications and interactive approvals"),
)


def provider_states():
    """Configured, contract-validated, and what still needs a live call.

    Never returns a value, only a variable name and a boolean - the same
    discipline as security.credential_status. A configuration screen that
    printed what a key is set to is a configuration screen that ends up in a
    screenshot.
    """
    import os

    listed = []
    for name, variable, offline, live, note in PROVIDERS:
        present = bool((os.environ.get(variable) or "").strip())
        shape = bool((os.environ.get("DELIVERABLE_RESULT_SHAPE") or "").strip())
        confirmed = live or (name == "Deliverable" and shape)
        listed.append({
            "name": name,
            "variable": variable,
            "configured": present,
            "offline_contract": offline,
            "live_contract": confirmed,
            # Never "healthy". Nothing in this build calls a provider, so
            # claiming health would be inventing the one fact this screen
            # exists to report. A configured provider whose contract has been
            # validated is exactly that and no more.
            "state": (UNCONFIGURED if not present
                      else NEEDS_LIVE if not confirmed
                      else NOT_CALLED),
            "note": note,
        })
    return listed


# -------------------------------------------- what we wrote to a provider
#
# `provider_states` above says which providers are CONFIGURED. This says what
# this system actually DID to one, and it is the only reader of
# `work/provider-writes.jsonl` anywhere in `src/web/`.
#
# WHY IT IS A SEPARATE LEDGER FROM EVERY OTHER PROVIDER NUMBER ON THIS
# SURFACE, and the reason is a measured defect rather than a design taste.
# `provider_health` walks `waterfall.ledger(rec)` - a PER-RECORD list at
# `rec["waterfall"]`, written by `enrich.spend()` for paid enrichment calls.
# A provider WRITE never touches it. So the admin page renders "No provider
# call has been made. This build does not make one from any surface" when
# that list is empty, which it is and always will be, while
# `providerwrites.perform` has written a row for every pause and every resume
# since 2026-09-24. Two ledgers, one question, and the screen was reading the
# one that cannot answer it.
#
# THIS FUNCTION ASSERTS NOTHING OF ITS OWN. Every value it returns is a field
# `providerwrites._ledger` wrote, carried through under the name that module
# gave it. The one thing it computes is an age, and an age it cannot compute
# is `None` rather than zero.

#: The ledger is absent, unreadable, present-and-empty, or has rows. Four
#: states, because collapsing them is the defect this page exists to avoid:
#: "no data" rendered as "zero" is an answer where there is none.
LOG_ABSENT = "absent"
LOG_UNREADABLE = "unreadable"
LOG_EMPTY = "empty"
LOG_ROWS = "rows"

#: Every `outcome` string `providerwrites.perform` can write, with what each
#: one PROVES about the provider. Measured at `b1f290c84`, not inferred:
#: `_perform` has exactly ONE return statement (`providerwrites.py:2642`) and
#: it is guarded by `if verdict != ACCEPTED: raise WriteUnverified` two lines
#: above it, so `accepted` is the only success class the ledger can hold.
#:
#: `drifted` and `unknown` are `_classify` verdicts and they do NOT appear
#: here, because they never reach the ledger as an outcome - they arrive
#: inside an `unverified` row's `detail` text ("read-back says drifted").
#: Rendering a bucket for them would be rendering a column that is always 0.
#:
#: `performed` is the wrapper's fallback for a `_perform` that returns no
#: class. It is UNREACHABLE at `b1f290c84` and is listed anyway, because the
#: wrapper would write it the day somebody adds a second return.
REACHED = "reached the provider"
NOT_REACHED = "did not reach the provider"
NEEDS_A_PERSON = "needs a person"

OUTCOMES = {
    "refused": (NOT_REACHED,
                "a guard said no before the transport was called, so nothing "
                "was asked of the provider"),
    "accepted": (REACHED,
                 "the transport returned and the mandatory read-back agreed "
                 "with what was asked for"),
    "unverified": (NEEDS_A_PERSON,
                   "the provider may have acted and nothing confirms the "
                   "state it is in. providerwrites says: do NOT retry, read "
                   "provider truth and settle it by hand"),
    "failed": (NEEDS_A_PERSON,
               "the write raised something other than a refusal, so whether "
               "the provider acted is not recorded"),
    "performed": (NEEDS_A_PERSON,
                  "recorded as performed with no outcome class. No code path "
                  "writes this today"),
}


def _log_age(stamp, now=None):
    """Seconds since `stamp`, or None when that cannot be computed.

    None, never 0. `_ledger` writes `at` with a fixed
    `%Y-%m-%dT%H:%M:%SZ` format, so anything else in that field is a row
    this function must not date - and a zero here would read as "just now",
    which is the most misleading possible answer about a provider write.
    """
    if not stamp:
        return None
    try:
        when = datetime.datetime.strptime(str(stamp), "%Y-%m-%dT%H:%M:%SZ")
    except (TypeError, ValueError):
        return None
    when = when.replace(tzinfo=datetime.timezone.utc)
    current = now or datetime.datetime.now(datetime.timezone.utc)
    return int((current - when).total_seconds())


def _read_provider_log(path):
    """`(state, rows, damaged)` - and the three absences stay apart.

    `store.read_jsonl` is deliberately NOT used, and the reason is this
    page's entire purpose. It returns `[]` for a missing file, so ABSENT and
    EMPTY arrive indistinguishable; and it raises on the first unparseable
    line, so one bad byte loses every row in the file including the ones
    before it.

    A damaged line is COUNTED and never skipped. A provider write nobody can
    read is not an absence of a provider write, and a reader that drops it
    silently turns a damaged ledger into a clean one.
    """
    import json as _json
    import os as _os

    if not _os.path.exists(path):
        return LOG_ABSENT, [], 0
    try:
        with open(path, encoding="utf-8") as handle:
            lines = handle.read().splitlines()
    except OSError:
        # UNKNOWN, and it must never become zero. The file is there and its
        # contents cannot be established, which is strictly less information
        # than an empty file.
        return LOG_UNREADABLE, [], 0
    rows, damaged = [], 0
    for line in lines:
        if not line.strip():
            continue
        try:
            parsed = _json.loads(line)
        except ValueError:
            damaged += 1
            continue
        if isinstance(parsed, dict):
            rows.append(parsed)
        else:
            damaged += 1
    if not rows and not damaged:
        return LOG_EMPTY, [], 0
    return LOG_ROWS, rows, damaged


def provider_write_log(repo, limit=200, now=None):
    """Every provider write this workspace is recorded as having attempted.

    Read-only, and nothing here writes: no state, no ledger row, no audit
    entry, no file. That is not a promise, it is the reason this was the
    first page built - a read cannot reproduce any of the three defects
    found on this surface, all of which were on write routes.

    `provider_settings.view` rather than `operations.view`. The rows name
    the vendor verb (`bison.pause`, `heyreach.pause`), which is the vendor
    stack, and that is the permission the settings screen already uses to
    decide whether a client-facing role sees it. It is also strictly the
    narrower of the two: `operations.view` reaches workspace REVIEWER and
    this reaches OPERATOR.

    Scoped to one tenant by `row["tenant"]`, which is what
    `providerwrites.perform` is passed as `tenant=campaign.get("client")`.
    Rows naming another tenant, or no tenant at all, are NOT shown and NOT
    counted - and the view says so rather than looking complete.
    """
    repo.require(ws.PROVIDER_SETTINGS_VIEW)
    import os

    from .. import providerwrites

    path = providerwrites.ledger_path()
    state, every, damaged = _read_provider_log(path)

    mine = [r for r in every if str(r.get("tenant") or "") == str(repo.client)]
    mine.sort(key=lambda r: str(r.get("at") or ""), reverse=True)

    rows = []
    for entry in mine[:limit]:
        outcome = str(entry.get("outcome") or "")
        meaning, why = OUTCOMES.get(outcome, (None, None))
        rows.append({
            "at": entry.get("at"),
            # None when the stamp is missing or not the format `_ledger`
            # writes. The page renders that as UNKNOWN, never as 0.
            "age_seconds": _log_age(entry.get("at"), now),
            "operation": entry.get("operation"),
            "outcome": outcome,
            # None for an outcome string this function has never been told
            # about. A new verb-outcome added to providerwrites must surface
            # as unrecognised rather than being filed into whichever bucket
            # happened to be first.
            "means": meaning,
            "why": why,
            "campaign": entry.get("campaign"),
            "by": entry.get("by"),
            "detail": entry.get("detail"),
            "pid": entry.get("pid"),
            "argv": entry.get("argv"),
        })

    counts = {}
    for entry in mine:
        key = str(entry.get("outcome") or "")
        counts[key] = counts.get(key, 0) + 1

    return {
        "workspace": repo.workspace,
        "state": state,
        # The file name only. A configuration screen that prints an absolute
        # path is a screen that names somebody's home directory in a
        # screenshot, and the name is the part a reader needs.
        "ledger_name": os.path.basename(path),
        "rows": rows,
        "shown": len(rows),
        "mine": len(mine),
        "limit": limit,
        "counts": counts,
        # Counted on this workspace's rows only, so it cannot report another
        # tenant's trouble.
        "needs_a_person": len([r for r in rows if r["means"] == NEEDS_A_PERSON]),
        "unrecognised": len([r for r in rows if r["means"] is None]),
        "damaged": damaged,
        # The newest row's age, or None. The page says UNKNOWN for None.
        "newest_age_seconds": next(
            (r["age_seconds"] for r in rows if r["age_seconds"] is not None),
            None),
        "undated": len([r for r in rows if r["age_seconds"] is None]),
        # What this view cannot see, said rather than implied - the discipline
        # `operational_health` already applies, and the list it is missing.
        "cannot_see": [
            {"area": "another tenant",
             "why": "rows naming a different tenant, or naming none at all, "
                    "are not shown here and are not in any count on this "
                    "page"},
            {"area": "a write that left no row",
             "why": "the ledger writer swallows OSError, so a full or "
                    "read-only volume loses a row silently. An empty ledger "
                    "means no row was recorded, which is weaker than no "
                    "write having happened"},
            {"area": "which provider campaign was written to",
             "why": "the ledger row carries this system's own campaign id "
                    "and not the provider's, so a pause cannot be traced to "
                    "the EmailBison or HeyReach campaign it reached"},
            {"area": "a write made outside this system",
             "why": "a campaign paused by hand in the vendor UI leaves no "
                    "row anywhere. This page is what WE did, never what "
                    "happened there"},
        ],
    }

# ----------------------------------------------- are the lane workers working
#
# WHY THIS IS A SCREEN. On 2026-10-15 the operator asked four times whether
# the lanes were running and every honest answer needed a shell, because the
# three authorities a person reaches for are each wrong in a different
# direction: a lane's `.out` file is 0 bytes until its task ENDS, the `DONE`
# folder's count is wrong in both directions, and a queue listing says
# nothing about what is in flight. This assembles the two that are right -
# the watcher's own log line, and the CPU time of what is alive under that
# watcher - and refuses the three that are not.
#
# IT IS NOT A WORKSPACE SCREEN AND IS NOT SCOPED TO ONE. The lane estate is a
# fact about this machine: the same seven rows for every tenant, naming no
# contact, no company, no campaign and no provider. That is why it is gated
# the way `/admin/health` is - an account-level check - rather than by a
# workspace permission, which would be a permission on data no workspace
# owns. `src.lanes` holds the reading; this function only shapes it and adds
# what the page is required to say it cannot see.

#: What this page deliberately does NOT read, and what reading it has cost.
#: Each one is an authority somebody has already believed.
REFUSED_AUTHORITIES = (
    ("the task's `.out` file size",
     "`cmd.exe` creates it at START and nothing is flushed into it until the "
     "task ends, so a working lane's file is 0 bytes. The webapp lane's own "
     "0030 run proved it: 30 minutes of work, an empty file throughout"),
    ("the `queue/<lane>/DONE/` folder",
     "its count is wrong in BOTH directions - a task has finished with no "
     "DONE record at all, and a file has been moved in by hand under a name "
     "no watcher writes. The watcher log's DONE line is the authority"),
    ("a spinner, a heartbeat or a last-modified time",
     "all three are satisfied by a process that is stuck. CPU time that "
     "moves between two samples is not"),
    ("the process command line",
     "it would answer which lane a process belongs to, and it carries file "
     "paths and has carried a credential. The probe reads a parent pid, an "
     "image name and a CPU time, and the image name never leaves it"),
)


def _clock_label(offset_hours):
    """`UTC+02:00`, or None. A reset time with no zone beside it is a trap.

    The provider states `08:07:16` and says nothing about which clock that
    is. Converting it without saying what was converted from would hand the
    reader the same trap one layer down.
    """
    if offset_hours is None:
        return None
    sign = "-" if offset_hours < 0 else "+"
    total = int(round(abs(offset_hours) * 60))
    return "UTC%s%02d:%02d" % (sign, total // 60, total % 60)


def lane_rework(root=None, now=None, commits=None, branch_lanes=None,
                cwd=None, lanes_wanted=None, include_reflog=False):
    """Whether each dispatched brief's work had already landed. Read-only.

    A SEPARATE CALL FROM `lane_board`, and the reason is latency with a
    number attached: the full read takes ~13s on this estate because the
    positive lane attribution asks git which branches contain each candidate
    commit, once per commit. Passing `branch_lanes={}` skips that and takes
    ~1.8s - and reports ONE MORE re-dispatch than the full read, because the
    attribution is what refuses `qwen/0060` convicted by `glm`'s
    `93162471d`. So the slow read is the correct one, the page says how long
    it took, and the fast one is not the default.

    `elapsed_seconds` travels with the data because an operator looking at a
    page that took thirteen seconds is owed the reason, and because a figure
    that silently got faster has usually stopped reading something.

    `include_reflog` IS OFF IN THE ROUTE AND THAT IS A MEASUREMENT, not an
    oversight: `git log --all --reflog --since --until` takes 88.5s in this
    repository against 0.25s without, timed 2026-10-16, so six killed
    dispatches would cost nine minutes of render. With it off, an empty
    commit window is reported as NOT READ rather than as empty - see
    `lanerework.commits_between` - so the landing verdict stays NOT
    DETERMINED instead of becoming a LOST this page could not prove. Turn it
    on for a one-shot measurement, never for a page.
    """
    import time

    began = time.time()
    # `lanes_wanted` exists for a test and is None in the route, the same
    # way `lane_board` takes `root` and `lock_path`: the real lane list comes
    # from the estate, and a test that needed the real estate would not be a
    # test.
    data = lanerework.rework(root=root, now=now, commits=commits,
                             branch_lanes=branch_lanes, cwd=cwd,
                             lanes_wanted=lanes_wanted,
                             include_reflog=include_reflog)
    data["elapsed_seconds"] = round(time.time() - began, 1)

    # The words travel WITH the data, the same way `lane_board` carries its
    # verdict text, so the renderer holds no table of its own. A verdict
    # `src.lanerework` has not named arrives as None and the page says
    # "unrecognised" - it is never filed into whichever bucket came first.
    for lane in data["lanes"]:
        for row in lane["rows"]:
            label, why = lanerework.VERDICT_TEXT.get(row["verdict"],
                                                     (None, None))
            row["verdict_label"] = label
            row["verdict_why"] = why
            row["field_text"] = lanerework.FIELD_TEXT.get(row["field"])
            row["attribution_text"] = lanerework.ATTRIBUTION_TEXT.get(
                row["attribution"])
        label, why = lanerework.VERDICT_TEXT.get(lane["state"], (None, None))
        lane["state_label"] = label
        lane["state_why"] = why
        # The lane's WORST landing verdict, not its most common one. None
        # where the lane had no killed dispatch, which the page renders as
        # "nothing to answer" and never as LANDED.
        lane["landing_state"] = lanerework.landing_state(lane)
        lane["landing_state_label"] = (
            lanerework.LANDING_TEXT[lane["landing_state"]][0]
            if lane["landing_state"] else None)
    data["killed_rows"] = lanerework.killed_dispatches(data)
    data["landing_glossary"] = [
        {"verdict": key, "label": label, "why": why}
        for key, (label, why) in
        ((verdict, lanerework.LANDING_TEXT[verdict])
         for verdict in lanerework.LANDING_ORDER)]
    data["landing_authorities"] = [
        {"key": key, "name": name, "why": why}
        for key, (name, why) in (
            (key, lanerework.LANDING_AUTHORITIES[key])
            for key in ("entry", "commit", "artefact", "requeued",
                        "lane_mtime"))]
    # THE LANE-FILE CLOCK'S OWN GLOSSARY AND ITS CONTROLS.
    #
    # The words come from `src.lanerework`, so the page holds no table of its
    # own and cannot drift from the reader - the same rule the suffix and
    # verdict glossaries above already follow.
    data["clock_glossary"] = [
        {"state": state, "label": label, "why": why}
        for state, (label, why) in lanerework.LANE_MTIME_TEXT.items()]
    # C4 OF TASK 0250: the controls are computed against the rows that are
    # about to be rendered, and the renderer REFUSES the column when any of
    # them fails. Computed here rather than in the template because a
    # template that could decide this could also decide to skip it.
    data["clock_controls"] = lanerework.clock_controls(
        data.get("killed_rows"))
    data["clock_controls_ok"] = all(check["ok"]
                                    for check in data["clock_controls"])
    data["clock_controls_failed"] = [check["name"] for check
                                     in data["clock_controls"]
                                     if not check["ok"]]
    # EVERY VERDICT TOKEN THE WATCHERS HAVE WRITTEN, by content, with the
    # denominator. The finding this carries is a subtraction the page prints:
    # tokens written minus tokens described.
    tokens = lanes.watcher_tokens()
    data["tokens"] = tokens
    data["token_rows"] = [
        {"token": token, "count": count,
         "short": lanes.done_meaning(token)[0],
         "why": lanes.done_meaning(token)[1],
         "described": lanes.done_meaning(token)[2]}
        for token, count in sorted(tokens["tokens"].items(),
                                   key=lambda kv: (-kv[1], kv[0]))]
    data["blind_spots"] = lanerework.blind_spots(data)
    data["both_runs"] = lanerework.both_runs_recorded(data)
    data["clashes"] = lanerework.rung_clashes(data)
    data["unrecognised"] = sorted(
        {row["verdict"] for lane in data["lanes"] for row in lane["rows"]
         if row["verdict"] not in lanerework.VERDICT_TEXT})
    return data


def lane_suite_fates(now=None, probe=None, table=None, root=None,
                     lock_path=None):
    """Whether the session that launched each suite ever learned the result.

    THE QUESTION THE LOCK PANEL CANNOT ANSWER. `lane_board` already carries
    `locks`, which says whether a lock will ever be released. This says
    whether a RESULT was ever read, and the two are independent: on 2026-10-16
    one suite died with its lock stranded and nobody reading it, and another
    released its lock perfectly and still went unread for thirty minutes.

    Read-only and side-effect-free, and it takes no CPU samples at all -
    which is deliberate. `webapp/0140` departed from its own brief because a
    delta-based rule makes the state a panel exists for invisible on every
    first page load; nothing here depends on having been loaded before.
    """
    import os

    data = suitefate.panel(root=root, now=now, probe=probe, table=table,
                           lock_path=lock_path)
    if data.get("state") != lanes.PRESENT:
        return data

    # The words travel WITH the data, exactly as the verdict, outcome and
    # lock vocabularies already do, so this page holds no table of its own.
    # A fate `src.suitefate` has not named arrives as None and the page says
    # "unrecognised" rather than filing it into whichever bucket is first.
    for row in data["rows"]:
        label, why = suitefate.FATE_TEXT.get(row["fate"], (None, None))
        row["fate_label"] = label
        row["fate_why"] = why
        label, why = suitefate.LOCKD_TEXT.get(row["lock_disposition"],
                                              (None, None))
        row["lock_label"] = label
        row["lock_meaning"] = why
        label, why = suitefate.TIME_TEXT.get(row["result_clock"],
                                             (None, None))
        row["clock_label"] = label
        row["clock_why"] = why
        # RELATIVE, never absolute: an absolute path is somebody's home
        # directory in a screenshot. The tree's basename is the part a
        # reader needs in order to recognise the lane.
        row["tree_shown"] = (os.path.basename(
            (row.get("log_file") or row.get("worktree") or "")
            .replace("\\", "/").rstrip("/").rsplit("/scripts", 1)[0]) or None)

    unrecognised = sorted({row["fate"] for row in data["rows"]
                           if row["fate"] not in suitefate.FATE_TEXT})
    data.update({
        "root_name": os.path.basename(data["root"]) if data["root"] else None,
        "unrecognised_fates": unrecognised,
        # THE COST, in the unit a person acts on. Minutes of suite time whose
        # answer reached nobody.
        "unread_minutes": round(data["unread_seconds"] / 60.0, 1),
        # How many launches this instrument cannot place at all. Published
        # beside the cost rather than behind it: `suppression/0280` measured
        # 45 verdict files at the fixed path with no identity, and
        # `build_verdict` is structurally unable to write a pid, SHA or
        # timestamp - so the hole is a property of the format, not of a lane.
        "hole": data["unknown"],
        "hole_share": (round(100.0 * data["unknown"] / data["total"], 1)
                       if data["total"] else None),
        # The number that proves the two states are independent rather than
        # asserting it. Non-zero on both sides means neither can stand in
        # for the other.
        "independent": (data["unread_lock_released"] > 0
                        and data["unread_lock_stranded"] > 0),
    })
    return data


def lane_board(now=None, probe=None, samples=None, root=None,
               lock_path=None):
    """Seven lanes, one row each, and nothing collapsed into a green tick.

    Read-only and side-effect-free: no file is written, no provider is
    reached, no socket is opened and no credential is read. The CPU samples
    that produce a delta live in memory for the life of this process, which
    is why a first load has no delta and says so instead of showing one.
    """
    import os

    # `samples` is the in-memory CPU sample store. The route leaves it None
    # so the process's own store is used - which is what makes a second page
    # load produce a delta. A test supplies its own, because a shared store
    # would carry one test's sample into the next one's assertion.
    # `root` and `lock_path` exist for a test and are None in the route:
    # the estate root then comes from the environment and the lock path
    # from `suitelock.path()`. A test that needed the real estate or the
    # real machine-wide lock on disk would not be a test.
    data = lanes.board(now=now, probe=probe, samples=samples, root=root,
                       lock_path=lock_path)
    rows = data["lanes"]

    # Counted off the verdicts rather than restated, so a new verdict cannot
    # be silently absorbed into one of these buckets.
    tally = {}
    for row in rows:
        tally[row["verdict"]] = tally.get(row["verdict"], 0) + 1
    unrecognised = [v for v in tally if v not in lanes.VERDICT_TEXT]

    # The words travel WITH the data, so the renderer holds no table of its
    # own. A verdict or a suffix `src.lanes` has not named arrives as None
    # and the page says "unrecognised" - it is never filed into whichever
    # bucket happened to be first.
    for row in rows:
        label, why = lanes.VERDICT_TEXT.get(row["verdict"], (None, None))
        row["verdict_label"] = label
        row["verdict_why"] = why
        short, meaning = lanes.DONE_MEANINGS.get(
            row["last_done_suffix"], (None, None))
        row["done_short"] = short
        row["done_meaning"] = meaning
        # The clock's two state words, carried the same way and for the same
        # reason: a state `src.lanes` has not named arrives at the page as
        # None and renders "unrecognised" there. It is never filed into
        # whichever of the three UNKNOWNs happened to be first, because the
        # three have three different repairs.
        clock = row["clock"]
        label, why = lanes.TIMEOUT_TEXT.get(clock["timeout_state"],
                                            (None, None))
        clock["timeout_label"] = label
        clock["timeout_why"] = why
        label, why = lanes.ELAPSED_TEXT.get(clock["elapsed_state"],
                                            (None, None))
        clock["elapsed_label"] = label
        clock["elapsed_why"] = why
        # THE OPEN `START`'s own timeout words, carried the same way. The
        # cell prints the `watcher up` line it read the cap from, so the
        # STATE beside it has to be the same three-way reading the clock
        # uses - one rule, one glossary, no second copy to drift.
        cell = row["open_start"]
        label, why = lanes.TIMEOUT_TEXT.get(cell["timeout_state"],
                                            (None, None))
        cell["timeout_label"] = label
        cell["timeout_why"] = why

    # ------------------------------- briefs consumed by a provider refusal
    #
    # THE MOST EXPENSIVE MISREPORT THIS ESTATE HAS MEASURED, assembled here
    # because it is an ESTATE fact and not a lane one: on 2026-10-16 three
    # lanes lost three, two and three briefs inside seven minutes, and the
    # number a person needs is the total. Every row carries the DONE line
    # that produced it, so none of this is a count standing on its own.
    refusals = sorted(
        (row for lane_row in rows for row in lane_row["refused"]),
        key=lambda row: (row["at"], row["lane"]))
    by_date = {}
    for row in refusals:
        by_date[row["date"]] = by_date.get(row["date"], 0) + 1
    for row in refusals:
        # The two clocks, named. A reset printed without its zone is the trap
        # the operator was handed by hand once already.
        row["reset_from"] = _clock_label(row["reset"]["provider_offset_hours"])
        row["reset_to"] = _clock_label(row["reset"]["local_offset_hours"])

    # ---------------------------------------------- the open START, TASK 0266
    #
    # THE CONTROLS ARE COMPUTED HERE AND NOT IN THE TEMPLATE, for the reason
    # `webapp/0250` gave for its clock controls: a template that could decide
    # whether to run them could also decide to skip them. The renderer is
    # handed a boolean and refuses the column on it.
    #
    # `blind_probe_verdict` is C4 TAKEN rather than waited for. Leaving C4 to
    # be satisfied by whichever lane happened to be unmeasurable would make
    # the control pass by luck on a good day and refuse the column on a
    # better one - and an instrument that cannot report its own blindness is
    # failure family five, which is the one this cell exists to avoid.
    open_cells = [row["open_start"] for row in rows]
    data["open_controls"] = laneopen.controls(
        open_cells, probe_blind=laneopen.blind_probe_verdict(now))
    data["open_controls_ok"] = all(check["ok"]
                                   for check in data["open_controls"])
    data["open_controls_failed"] = [check["name"]
                                    for check in data["open_controls"]
                                    if not check["ok"]]
    # Every open dispatch on the estate, worst first, so a reader asking
    # "is anything abandoned right now" needs no per-lane scan. The lane
    # rows carry the same objects; this is an ordering, not a second copy.
    data["open_rows"] = sorted(
        (row for cell in open_cells for row in cell["open"]),
        key=lambda row: (laneopen.OPEN_ORDER.index(row["verdict"]),
                         row["start_at"]))
    data["open_glossary"] = laneopen.describe()["verdicts"]
    data["open_tally"] = {}
    for row in data["open_rows"]:
        data["open_tally"][row["verdict"]] =             data["open_tally"].get(row["verdict"], 0) + 1

    depths = [r["queue_depth"] for r in rows if r["queue_depth"] is not None]
    data.update({
        # THE FLOOR, AND WHERE IT WAS READ FROM. `data` already carries
        # `floor`, `floor_state`, `floor_path` and `floor_line` from
        # `lanes.board`, which reads the operator's own file rather than
        # holding a constant. Two things are added here and both are about
        # rendering: the sentence that explains the state, taken from
        # `src.lanes` so the page cannot drift from the reader, and a
        # RELATIVE path - the absolute one is somebody's home directory in a
        # screenshot, exactly as with `root_name` above.
        "floor_path_shown": os.path.join("queue", "README.md"),
        "floor_state_why": lanes.FLOOR_STATE_TEXT.get(data.get("floor_state")),
        "tally": tally,
        "refusals": refusals,
        "refused_total": len(refusals),
        "refused_by_lane": [{"lane": r["lane"], "count": r["refused_count"]}
                            for r in rows if r["refused_count"]],
        # Per DAY, because the window recurs: the GLM plan's limit is rolling
        # and five hours wide, so this is a cost per outage and not a one-off.
        "refused_by_date": [{"date": d, "count": by_date[d]}
                            for d in sorted(by_date)],
        "refused_first": refusals[0]["at"] if refusals else None,
        "refused_last": refusals[-1]["at"] if refusals else None,
        # ------------------------------------- the split inside REFUSED
        #
        # NOT A SECOND OPINION ON THE CLASSIFICATION. Every row here is a
        # refusal by its own output and stays one; what these three count is
        # whether the board may say the task NEVER RAN, which it asserted on
        # all eight for sixteen hours. The three buckets are exhaustive and
        # disjoint by construction - True, False and None of one field - so a
        # row cannot fall out of the split without the totals disagreeing
        # with `refused_total`, which is what the control checks.
        "refused_never_ran": len([r for r in refusals
                                  if r["never_ran_supportable"] is True]),
        # The session was alive long enough to act and its output does not
        # say whether it did. NOT "it worked": UNKNOWN, and UNKNOWN is the
        # reason the brief cannot simply be re-queued without a person
        # checking the lane's branch and its own file first.
        "refused_ran_unknown": len([r for r in refusals
                                    if r["never_ran_supportable"] is False]),
        # Neither, because the interval could not be measured. Kept apart
        # from both rather than folded into the safer-sounding one.
        "refused_elapsed_unknown": len([r for r in refusals
                                        if r["never_ran_supportable"]
                                        is None]),
        # THE SIZE OF THE UNRECORDED WINDOW, which is the number that says
        # how much this matters: 193 lane-minutes on 2026-10-16, of which
        # 142.8 are in three rows. None where any row's interval is unknown,
        # because a total over a subset is not the total.
        "refused_unaccounted_seconds": (
            None if any(r["elapsed_seconds"] is None for r in refusals)
            else sum(r["elapsed_seconds"] for r in refusals)),
        "refused_longest_seconds": (
            max([r["elapsed_seconds"] for r in refusals
                 if r["elapsed_seconds"] is not None], default=None)),
        "never_ran_window_seconds": lanes.NEVER_RAN_WINDOW_SECONDS,
        # THE SENTENCE THE OPERATOR NEEDS. True means the brief is not in its
        # lane queue and not in RUNNING, so nothing will ever run it again.
        "briefs_still_missing": sum(r["briefs_still_missing"] for r in rows),
        # And the one that is NOT zero-shaped: a queue folder that could not
        # be read cannot prove a brief missing OR present.
        "briefs_missing_unknown": sum(r["briefs_missing_unknown"]
                                      for r in rows),
        # A closed failure whose own output could not be read. Shown beside
        # the refusal total, because it is the part of the total that is
        # UNKNOWN rather than the part that is zero.
        "unclassifiable_failures": sum(r["unclassifiable_failures"]
                                       for r in rows),
        "closed_failures_capped": sum(r["closed_failures_capped"]
                                      for r in rows),
        # A refusal whose stated reset could not be checked against the
        # second clock on its own line. Not an error - most lines carry one
        # and these did - but a conversion nobody checked is a conversion.
        "reset_uncorroborated": len([r for r in refusals
                                     if not (r["clock_check"] or {})
                                     .get("agrees")]),
        # The watcher's own `N consecutive failures` line, per lane. THE
        # MITIGATION: it is the only reason the 2026-10-16 loss stopped at
        # nine briefs instead of the whole queue. It is also the three-in-a-
        # row signal, and it is printed as a HINT - the verdict came from
        # each task output, never from a run of failures.
        "failure_guards": [dict(r["failure_guard"], lane=r["lane"])
                           for r in rows if r["failure_guard"]],
        # From `src.lanes`, so the page renders the same words the reader
        # computes with. A fourth outcome would appear here on its own.
        "outcome_glossary": [
            {"outcome": key, "label": label, "implies": why}
            for key, (label, why) in sorted(lanes.OUTCOME_TEXT.items())],
        # The directory's NAME, never its path. A screen that prints an
        # absolute path is a screen that names somebody's home directory in
        # a screenshot, and the name is the part a reader needs.
        "root_name": os.path.basename(data["root"]) if data["root"] else None,
        # Both glossaries come from `src.lanes`, so the page renders the
        # same words the reader computes with and cannot drift from them.
        "verdict_glossary": [
            {"label": label, "why": why}
            for label, why in lanes.VERDICT_TEXT.values()],
        "suffix_glossary": [
            {"suffix": key, "short": short, "why": why}
            for key, (short, why) in sorted(lanes.DONE_MEANINGS.items())],
        # A verdict this page has not been told how to render. Named rather
        # than bucketed - the defect `provider_write_log` was built around.
        "unrecognised_verdicts": sorted(unrecognised),
        "lane_count": len(rows),
        "queued_total": sum(depths),
        # None, not 0: a depth nobody could read is not an empty queue, and
        # the count of rows it could not read is shown beside the total.
        "queue_unreadable": len([r for r in rows
                                 if r["queue_depth"] is None]),
        "owed_markers": len([r for r in rows if r["owed"]["hits"]]),
        # The scope of the owed detector is a heuristic, and this is how a
        # reader can see where it is weakest: a lane whose last `## ` heading
        # is not dated is a lane whose last entry is probably WIDER than the
        # scope searched.
        "owed_scope_shaky": len([r for r in rows
                                 if r["owed"]["state"] == lanes.PRESENT
                                 and not r["owed"]["heading_dated"]]),
        "refused": [{"authority": a, "why": w} for a, w in
                    REFUSED_AUTHORITIES],
        "cannot_see": [
            {"area": "whether the work is any good",
             "why": "`exit0` means the task process exited 0 and the lane "
                    "file grew. That is the watcher's whole test. Nothing "
                    "here reads what was written"},
            {"area": "which process is the task",
             "why": "no file records the task's pid - the watcher names it "
                    "only in the line it writes while killing it. The CPU "
                    "figure is therefore the SUM over everything currently "
                    "claiming descent from this lane's watcher, which also "
                    "includes whatever is reading this page from inside that "
                    "lane"},
            {"area": "lineage, as a proof",
             "why": "a parent pid cannot establish it: Windows reuses a pid, "
                    "and a process whose real parent has exited keeps a "
                    "parent pid that may now name something else. The "
                    "watcher's own kill has the same limit and says so"},
            {"area": "a watcher that was never started",
             "why": "a lane with a queue folder and no log has never run, "
                    "and that is shown - but a lane with neither is not "
                    "discoverable from here at all"},
            {"area": "a refusal that exited 0",
             "why": "only a DONE the watcher counted a FAILURE has its output "
                    "opened, so a provider refusal that somehow exited 0 "
                    "would not be classified here. The watcher's own rule "
                    "makes that nearly unreachable - exit 0 with no "
                    "lane-file growth becomes NOWORK, which IS examined - "
                    "but nearly is not never"},
            {"area": "whether a restored brief is byte-identical",
             "why": "the DONE copy and the queue copy are each given a fresh "
                    "size and nothing here hashes either. `Move-Item` "
                    "preserves bytes, which is what makes the DONE copy "
                    "usable at all; two sizes that agree is evidence the "
                    "restore is the same file and is not proof of it"},
            {"area": "which provider refused",
             "why": "the refusal line names no provider and neither does any "
                    "watcher record. The lane's model is in the harness "
                    "notice above the error, and the board does not read it: "
                    "a verdict that consulted the model would fire on the "
                    "next lane running the same one"},
            {"area": "what a lane meant",
             "why": "the owed-gate column matches a fixed set of phrases in "
                    "a prose file. It reports the line it matched and judges "
                    "nothing: no marker is NOT evidence that nothing is "
                    "owed, and a matched line can be saying the opposite"},
        ],
    })

    # -------------------------------------- who wrote the names in DONE\
    #
    # The reverse of every figure above: not "what does the board count"
    # but "what is in the folder the board refuses to count, and who put it
    # there". Attached to the board because it is the EVIDENCE that the
    # refusal is worth anything - a reader told the page ignores `DONE\`
    # has no way to see what ignoring it is worth until the untraceable
    # files are named.
    #
    # Read-only. Nothing in any `DONE\` folder is created, renamed, moved or
    # removed by this call or by anything it reaches.
    data["done_folders"] = laneprovenance.reconcile(data.get("root"))

    # -------------------------------------------------- the provenance table
    #
    # LAST, AND OVER THE PAYLOAD AS IT NOW STANDS. The paths are walked from
    # `data` itself rather than from a list written by hand, so a figure
    # added above arrives in the table on its next render - as UNKNOWN if
    # nobody gave it a row, which is the state the brief requires and the
    # one a hand-written list cannot produce.
    #
    # `provenance` is inserted into `data` after the walk, so the table does
    # not describe itself recursively; its own rows are covered by the
    # `lane_board.provenance.*` pattern in the registry.
    paths = laneprovenance.paths_of(data, "lane_board")
    paths |= {"lane_board.provenance"}
    data["provenance"] = laneprovenance.table(paths)
    return data


def queue_depth(now=None, probe=None, samples=None, root=None, board=None,
                offset_hours=None):
    """Queue depth twice - raw, and consumable - with the floor re-derived.

    `board` IS THE BOARD, PASSED IN. The route already has it, and the
    liveness half of this answer comes from the process table that board
    read: taking a second look would put two readings of one table on one
    page, which is how two numbers there disagree. When nothing is handed in
    `src.queuedepth` reads its own, which is what a test does.

    Read-only, and nothing here calls the floor ledger. `floor_ledger` is
    the sampler and it is a different screen; a panel that appended a row to
    the history it was measuring would be `0130`'s own refusal broken.
    """
    data = queuedepth.consumable(root=root, now=now, probe=probe,
                                 samples=samples, board_data=board,
                                 offset_hours=offset_hours)

    # The words travel WITH the data, so the renderer holds no table of its
    # own. A state `src.queuedepth` has not named arrives as None and the
    # page prints the raw token rather than filing it into whichever bucket
    # came first.
    for row in data["lanes"]:
        label, why = queuedepth.STATE_TEXT.get(row["state"], (None, None))
        row["state_label"] = label
        row["state_why"] = why
        label, why = queuedepth.WATCHER_TEXT.get(row["watcher"], (None, None))
        row["watcher_label"] = label
        row["watcher_label_why"] = why
        # Each UNKNOWN with its own repair, in the order it was found. One
        # empty cell for four different causes tells a reader nothing.
        row["unknown_text"] = [
            {"why": token, "text": queuedepth.UNKNOWN_TEXT.get(token)}
            for token in row["unknown_because"]]
    # WHY the floor is UNKNOWN when it is, in `src.lanes`' own words. Never
    # 3: the floor is the operator's, from his own file.
    data["floor_state_why"] = lanes.FLOOR_STATE_TEXT.get(
        data.get("floor_state"))
    data["floor_path_shown"] = "/".join(lanes.FLOOR_README)
    return data


# ------------------------------------------------------- suppression, scoped
#
# `global_suppression` is the do-not-contact list and is deliberately
# cross-workspace: a domain somebody asked us to stop contacting must stay
# stopped everywhere. What was missing is the other half - which of *this*
# workspace's companies and contacts are actually stopped, and why.
#
# The two are different questions and this one is answerable per tenant, so it
# is scoped by `Repo` like everything else.


def suppression(repo):
    """Who is stopped in this workspace, and what stopped them.

    Four sources, and they are not the same thing:

      reply        somebody answered. Pauses the whole company, both channels
      unsubscribe  an explicit request. Permanent
      dropped      the record was dropped with a reason before outreach
      global       the domain is on the cross-workspace do-not-contact list

    A screen that merged them would let "paused because they replied" read as
    "asked us to stop", and those need different handling by a person.
    """
    from .. import ingest

    recs = repo.records()
    try:
        global_list = set(ingest.load_suppress())
    except Exception:                                       # noqa: BLE001
        global_list = set()

    rows = []
    for rec in recs:
        domain = (rec.get("domain") or "").lower()
        paused = rec.get("paused") or {}
        if paused:
            rows.append(_suppression_row(
                rec, "reply" if paused.get("reason") == "reply_received"
                else "paused", paused.get("reason"), paused.get("since"),
                "company"))
        if rec.get("state") == "dropped":
            rows.append(_suppression_row(
                rec, "dropped", rec.get("drop_reason"), None, "company"))
        if domain and domain in global_list:
            rows.append(_suppression_row(
                rec, "global", "on the cross-workspace do-not-contact list",
                None, "company"))
        for contact in rec.get("contacts") or []:
            if contact.get("unsubscribed"):
                rows.append(_suppression_row(
                    rec, "unsubscribe", "explicit request", None, "contact",
                    contact))

    rows.sort(key=lambda r: (r["kind"], str(r["company"])))
    counts = {}
    for row in rows:
        counts[row["kind"]] = counts.get(row["kind"], 0) + 1
    return {
        "workspace": repo.workspace,
        "rows": rows,
        "counts": counts,
        "total": len(rows),
        "companies": len(recs),
        "global_count": len(global_list),
        "note": ("A reply pauses a company; it is not a request to stop. An "
                 "unsubscribe is. They are listed separately because a person "
                 "handles them differently."),
    }


def _suppression_row(rec, kind, why, since, scope, contact=None):
    return {
        "kind": kind,
        "scope": scope,
        "record_id": rec.get("id"),
        "company": rec.get("company"),
        "domain": rec.get("domain"),
        "contact": (contact or {}).get("name"),
        "contact_key": (contact or {}).get("key"),
        "why": why,
        "since": since,
    }


# ------------------------------------------------------------- global search
#
# Bounded on purpose, in three ways, because an unbounded search over every
# workspace's records is both a performance problem and a tenancy one:
#
#   * it only ever reads workspaces the caller is a member of, through the
#     same `Repo.for_user` every other read goes through
#   * it stops at `SEARCH_CAP` matches per kind and says so, rather than
#     scanning to the end of a five-thousand-domain batch
#   * it refuses a query shorter than `SEARCH_MIN`, because a one-character
#     query is a full scan wearing a filter

SEARCH_CAP = 25
SEARCH_MIN = 2


def search(email, query, workspace=None):
    """Workspaces, campaigns, companies and contacts the caller may see.

    `workspace` narrows to one; without it the search covers every workspace
    the caller is a member of - which is what makes it useful to somebody who
    works across clients, and what makes the membership check the only thing
    standing between it and a cross-tenant read.
    """
    term = str(query or "").strip().lower()
    if len(term) < SEARCH_MIN:
        return {"query": query or "", "results": [], "counts": {},
                "truncated": {}, "why": (
                    f"a search needs at least {SEARCH_MIN} characters; "
                    f"shorter than that is a full scan wearing a filter")}

    mine = ws.workspaces_for(email)
    if workspace:
        mine = [w for w in mine if w["slug"] == workspace]

    results, truncated = [], {}
    for space in mine:
        try:
            repo = repo_module.Repo.for_user(email, space["slug"])
        except Exception:                                   # noqa: BLE001
            # Not a member any more, or the workspace went away between the
            # listing and the read. Skipped rather than raised: a search must
            # not become a way to learn that a workspace exists.
            continue

        # What this role may see, asked per workspace rather than once.
        #
        # The route is gated on WORKSPACE_VIEW, and its comment reasons
        # only about tenancy - true, and the wrong question. A viewer is
        # the client-facing role that CONTACTS_VIEW deliberately denies,
        # and is refused /contacts, /companies and /campaigns; search
        # answered all three anyway, with names, titles, addresses,
        # domains, record and contact ids in the hrefs, and every campaign
        # id and status. Matching on `contact.email` made it an
        # address-confirmation oracle as well.
        #
        # Per workspace, because a person may be an operator in one and a
        # viewer in another, and the role follows the workspace.
        may_contacts = repo.may(ws.CONTACTS_VIEW)
        may_operations = repo.may(ws.OPERATIONS_VIEW)

        if term in space["slug"].lower() or term in (space.get("name") or "").lower():
            results.append(_hit("workspace", space["slug"], space.get("name"),
                                space["slug"], "/workspaces", space["slug"]))

        found = 0
        for campaign in (repo.campaigns() if may_operations else []):
            haystack = f"{campaign.get('name') or ''} {campaign.get('campaign_id') or ''}".lower()
            if term in haystack:
                if found >= SEARCH_CAP:
                    truncated["campaign"] = True
                    break
                results.append(_hit(
                    "campaign", campaign.get("campaign_id"),
                    campaign.get("name"), campaign.get("status"),
                    "/campaigns/" + str(campaign.get("campaign_id")),
                    space["slug"]))
                found += 1

        companies = contacts = 0
        for rec in (repo.records() if may_contacts else []):
            haystack = f"{rec.get('company') or ''} {rec.get('domain') or ''}".lower()
            if term in haystack:
                if companies >= SEARCH_CAP:
                    truncated["company"] = True
                else:
                    results.append(_hit(
                        "company", rec.get("id"), rec.get("company"),
                        rec.get("domain"), "/companies/" + str(rec.get("id")),
                        space["slug"]))
                    companies += 1
            for contact in rec.get("contacts") or []:
                blob = (f"{contact.get('name') or ''} "
                        f"{contact.get('email') or ''} "
                        f"{contact.get('title') or ''}").lower()
                if term not in blob:
                    continue
                if contacts >= SEARCH_CAP:
                    truncated["contact"] = True
                    break
                results.append(_hit(
                    "contact", contact.get("key"), contact.get("name"),
                    contact.get("title") or contact.get("email"),
                    f"/contacts/{rec.get('id')}/{contact.get('key')}",
                    space["slug"]))
                contacts += 1

    counts = {}
    for hit in results:
        counts[hit["kind"]] = counts.get(hit["kind"], 0) + 1
    return {"query": query, "results": results, "counts": counts,
            "truncated": truncated, "why": None,
            "workspaces": [w["slug"] for w in mine]}


def _hit(kind, identifier, label, detail, where, workspace):
    return {"kind": kind, "id": identifier, "label": label, "detail": detail,
            "where": where, "workspace": workspace}


# ------------------------------------------------------- account outreach
#
# The account view. `full_outreach` above is the campaign-wide contact list;
# this is one company, every decision maker, every human who has touched them,
# and what each message may say about the others.
#
# Everything here reads `src/account.py`, which derives from the record's own
# events - so this screen and the contact view cannot disagree.


def account_view(repo, record_id, campaign_id=None):
    """One company as an orchestration map.

    Scoped by `repo.record`, so a record id belonging to another workspace
    returns None and the handler answers 404 - the same shape as every other
    object read here.
    """
    rec = repo.record(record_id)
    if rec is None:
        return None

    config = repo.config()
    rows = senderidentity.load()
    graph = account.graph(rec, repo.workspace, rows, config)
    campaign = repo.campaign(campaign_id) if campaign_id else None
    if campaign is None:
        campaign = next((c for c in repo.campaigns()
                         if record_id in (c.get("record_ids") or [])), None)

    team = senderteam.team_for(repo.workspace,
                               (campaign or {}).get("campaign_id"), rows=rows)

    # Per contact: who is assigned, what may be claimed, and how tired they
    # are. Assembled here rather than in the page so the same numbers back the
    # screen, the QA check and the approval summary.
    # Scored once and used twice: the panel and the playbook
    # recommendation are the same assessment, so they cannot disagree.
    assessment = priority_module.assess(rec, repo.workspace, config)
    people = []
    for entry in graph["contacts"]:
        senders = entry.get("senders") or {}
        sender_id = ((senders.get("email") or {}).get("sender_id")
                     or (senders.get("linkedin") or {}).get("sender_id"))
        claims = outreachclaims.available(rec, entry["key"], repo.workspace,
                                          sender_id, config, rows)
        pacing = fatigue.contact_check(rec, entry["key"], config=config)
        people.append({
            **entry,
            "claims": claims,
            "claims_allowed": [c for c in claims if c["allowed"]],
            "claims_refused": [c for c in claims if not c["allowed"]],
            "fatigue": pacing,
        })

    return {
        "record_id": record_id,
        "company": rec.get("company"),
        "domain": rec.get("domain"),
        "workspace": repo.workspace,
        "campaign": ({"campaign_id": campaign.get("campaign_id"),
                      "name": campaign.get("name"),
                      "status": campaign.get("status")}
                     if campaign else None),
        "campaigns": [{"campaign_id": c.get("campaign_id"),
                       "name": c.get("name")}
                      for c in repo.campaigns()
                      if record_id in (c.get("record_ids") or [])],
        "contacts": people,
        "timeline": account.timeline(rec, repo.workspace, rows),
        "referrals": graph["referrals"],
        "team": senderteam.describe(team, repo.workspace, rows),
        "touched_by": account.team_for(rec, repo.workspace, rows),
        "counts": graph["counts"],
        "paused": graph["paused"],
        "suppressed": graph["suppressed"],
        "account_fatigue": fatigue.account_check(rec, config=config),
        "limits": fatigue.limits(config),
        # Why this account, and why now - beside the eligibility verdict,
        # never folded into it. A screen that showed a priority without
        # saying whether anything may be sent would be inviting somebody
        # to write to a suppressed account.
        "priority": assessment,
        # Which approach fits, and what it rests on. A recommendation only:
        # nothing here selects a cadence or writes anything.
        "playbooks": playbook_module.recommend(rec, assessment),
    }


def account_rows(repo, batch=None, engaged_only=False):
    """Every account, for the list at the top of the outreach screen."""
    listed = []
    rows = senderidentity.load()
    for rec in repo.records(batch=batch):
        graph = account.graph(rec, repo.workspace, rows)
        counts = graph["counts"]
        if engaged_only and not counts["engaged"]:
            continue
        listed.append({
            "record_id": rec.get("id"),
            "company": rec.get("company"),
            "domain": rec.get("domain"),
            "decision_makers": counts["decision_makers"],
            "contacted": counts["contacted"],
            "engaged": counts["engaged"],
            "positive": counts["positive"],
            "touches": counts["touches"],
            "planned": counts["planned"],
            "referrals": counts["referrals"],
            "team": graph["team"],
            "channels": graph["channels"],
            "paused": bool(graph["paused"]),
            "last": (graph["confirmed_touches"][-1]["at"]
                     if graph["confirmed_touches"] else None),
        })
    listed.sort(key=lambda a: (-a["positive"], -a["engaged"], -a["touches"],
                               str(a["company"])))
    return listed


def cadence_view(repo, campaign_id=None, template=None):
    """A cadence graph, rendered as something a person can read.

    Either the campaign's stored graph or a named template built from this
    workspace's own senders. A template is a shape; the humans in it come from
    the roster, because a template carrying one client's staff is a template
    nobody else can use.
    """
    rows = senderidentity.load()
    campaign = repo.campaign(campaign_id) if campaign_id else None
    team = senderteam.team_for(repo.workspace,
                               (campaign or {}).get("campaign_id"), rows=rows)
    people = senderidentity.senders(repo.workspace, rows, active_only=True)
    # A template previewed with somebody off the team validates as two red
    # blocks on an untouched stock shape, which teaches a reader that the
    # blocks are decoration. Prefer the team; fall back to the roster only
    # when the team cannot carry the channel, and let it block honestly then.
    authorised = set(senderteam.members(team) or ())

    def _pool(lookup):
        able = [s["sender_id"] for s in people
                if lookup(repo.workspace, rows, s["sender_id"])]
        on_team = [s for s in able if s in authorised]
        return on_team or able

    email_people = _pool(senderidentity.email_accounts)
    linkedin_people = _pool(senderidentity.linkedin_accounts)

    stored = (campaign or {}).get("cadence_graph")
    if stored:
        graph = stored
        source = "campaign"
    else:
        key = template or "standard"
        try:
            graph = cadencegraph.from_template(
                key,
                email_sender=(email_people or ["unassigned"])[0],
                linkedin_sender=(linkedin_people or ["unassigned"])[0],
                second_email=(email_people[1:2] or email_people
                              or ["unassigned"])[0],
                second_linkedin=(linkedin_people[1:2] or linkedin_people
                                 or ["unassigned"])[0])
        except cadencegraph.CadenceError:
            return None
        source = "template"

    names = {s["sender_id"]: s.get("display_name") or s["sender_id"]
             for s in senderidentity.senders(repo.workspace, rows)}
    findings = cadencegraph.validate(graph, senderteam.members(team),
                                     repo.config(), names)

    nodes = []
    for node in cadencegraph.walk(graph):
        nodes.append(_cadence_node(node, names, graph))
    # Anything the happy path does not reach still has to be shown: a branch
    # nobody can see is a branch nobody reviews.
    seen = {n["key"] for n in nodes}
    for key, node in sorted((graph.get("nodes") or {}).items()):
        if key not in seen:
            nodes.append(_cadence_node(node, names, graph, off_path=True))

    # Grouped by phase. A thirty-nine node cadence rendered as one column is
    # a wall; the same nodes under six headings is a sequence somebody can
    # read.
    grouped = []
    for group in cadencegraph.phases_of(graph):
        rendered = [_cadence_node(node, names, graph) for node in
                    group["nodes"]]
        grouped.append({
            "phase": group["phase"],
            "nodes": rendered,
            "touches": len([n for n in rendered if n["contacts"]]),
            "senders": sorted({n["sender"] for n in rendered
                               if n.get("sender")}),
            "channels": sorted({n["channel"] for n in rendered
                                if n.get("channel")}),
        })

    return {
        "campaign": ({"campaign_id": campaign.get("campaign_id"),
                      "name": campaign.get("name")} if campaign else None),
        "campaigns": [{"campaign_id": c.get("campaign_id"),
                       "name": c.get("name")} for c in repo.campaigns()],
        "phases": grouped,
        "source": source,
        "template": template or ("" if stored else "standard"),
        "templates": [{"key": k, "name": v["name"]}
                      for k, v in cadencegraph.TEMPLATES.items()],
        "graph": graph,
        "nodes": nodes,
        "summary": cadencegraph.describe(graph),
        "findings": findings,
        "blocking": cadencegraph.blocking(findings),
        "team": senderteam.describe(team, repo.workspace, rows),
        "conditions": cadencegraph.CONDITIONS,
        "node_types": [dict(cadencegraph.NODE[k]) for k in
                       cadencegraph.NODE_KEYS],
    }


def _cadence_node(node, names, graph, off_path=False):
    kind = cadencegraph.NODE.get(node["type"], {})
    branches = []
    for label, target in sorted((node.get("next") or {}).items()):
        branches.append({
            "on": label,
            "target": target,
            "target_label": ((graph.get("nodes") or {}).get(target) or {})
            .get("label"),
        })
    return {
        "key": node["key"],
        "type": node["type"],
        "label": node.get("label"),
        "channel": node.get("channel"),
        "contacts": bool(kind.get("contacts")),
        "validated": bool(kind.get("validated", True)),
        "day": node.get("day"),
        "wait_days": node.get("wait_days"),
        "sender_id": node.get("sender_id"),
        "sender": names.get(node.get("sender_id"), node.get("sender_id")),
        "role": node.get("contact_role"),
        "template": node.get("template"),
        "condition": node.get("condition"),
        "condition_why": cadencegraph.CONDITIONS.get(node.get("condition")),
        "branches": branches,
        "off_path": off_path,
    }


# --------------------------------------------------------- the report editor
#
# CREATE -> GENERATE DRAFT -> EDIT -> PREVIEW -> EXPORT.
#
# The draft holds narrative and nothing else. Every number is recomputed here
# from `report_data`, which reads `src/report.py` - so an edit cannot change a
# metric, because there is nowhere in a draft to put one. See
# `src/reportdraft.py`.


def report_editor(repo, draft_id=None):
    """The editor screen: this draft, its blocks, and its versions."""
    drafts = reportdraft.for_workspace(repo.workspace)
    draft = None
    if draft_id:
        draft = reportdraft.get(draft_id)
        if draft is None or draft.get("workspace") != repo.workspace:
            return None
    elif drafts:
        draft = drafts[0]

    listed = report_templates(repo)
    if draft is None:
        return {"draft": None, "drafts": drafts, "templates": listed,
                "campaigns": _report_campaigns(repo),
                "workspace": repo.workspace,
                "can_edit": repo.may(ws.REPORTING_EXPORT)}

    data = report_data(repo, draft.get("campaigns"),
                       *_period_bounds(draft.get("period")))
    seeded = reportdraft.seed_narrative(draft, data)
    narrative = dict(draft.get("narrative") or {})

    blocks = []
    for key in reportdraft.NARRATIVE_KEYS:
        blocks.append({
            "key": key,
            "label": reportdraft.NARRATIVE_LABEL[key],
            "why": reportdraft.NARRATIVE_WHY[key],
            "value": narrative.get(key) or "",
            "suggested": seeded.get(key) or "",
            "edited": bool(narrative.get(key)),
        })

    available = clientreport.sections_for(draft["template"])
    chosen = draft.get("sections") or available
    sections = [{"key": key, "label": clientreport.SECTION_LABEL[key],
                 "on": key in chosen,
                 "order": chosen.index(key) if key in chosen else len(chosen)}
                for key in available]
    sections.sort(key=lambda s: (not s["on"], s["order"]))

    return {
        # The template by the name the picker above it uses, not by its key.
        "draft": dict(draft, template_label=clientreport.TEMPLATE_LABEL.get(
            draft["template"], draft["template"])),
        "drafts": drafts,
        "templates": listed,
        "campaigns": _report_campaigns(repo),
        "workspace": repo.workspace,
        "blocks": blocks,
        "sections": sections,
        "recommendations": draft.get("recommendations") or [],
        "recommendation_kinds": [
            {"key": k, "label": reportdraft.RECOMMENDATION_LABEL[k]}
            for k in reportdraft.RECOMMENDATIONS],
        "custom": draft.get("custom") or [],
        "versions": list(reversed(draft.get("history") or [])),
        # The counted figures, shown beside the editor so somebody writing a
        # summary is looking at the numbers it has to agree with - and so it
        # is obvious that they are read-only.
        "metrics": _editor_metrics(data),
        "can_edit": (repo.may(ws.REPORTING_EXPORT)
                     and draft.get("status") != reportdraft.FINAL),
        "can_finalise": repo.may(ws.REPORTING_EXPORT),
    }


def _report_campaigns(repo):
    return [{"campaign_id": c.get("campaign_id"),
             "name": c.get("name") or c.get("campaign_id")}
            for c in repo.campaigns()]


def _period_bounds(period):
    if period and " to " in str(period):
        since, _, until = str(period).partition(" to ")
        return since.strip(), until.strip()
    return None, None


def _editor_metrics(data):
    """The counted figures. Read-only, and labelled as such on the screen."""
    return [
        ("Companies assessed", data.get("domains_uploaded")),
        ("ICP qualified", data.get("domains_qualified")),
        ("Contacts found", data.get("contacts_found")),
        ("Contactable", clientreport._reachable(data)),
        ("Confirmed sent", data.get("emails_pushed")),
        ("Replies", data.get("replies")),
        ("Positive replies", data.get("positive_replies")),
        ("Meetings", data.get("meetings")),
    ]


def create_draft(repo, template, by, period=None, campaigns=None,
                 sections=None):
    """Start a draft, with the narrative pre-filled from counted facts."""
    template = allowed_template(repo, template)
    data = report_data(repo, campaigns, *_period_bounds(period))
    # Seeded at creation so the editor opens on something to react to rather
    # than a set of empty boxes - and so the draft is honestly version 1.
    draft = reportdraft.create(
        repo.workspace, template, by, period, campaigns, sections,
        narrative=reportdraft.seed_narrative({}, data))
    repo.audit("report.draft_created", "report_draft", draft["id"],
               metadata={"template": template, "period": draft["period"]})
    return draft


def edit_draft(repo, draft_id, by, narrative=None, sections=None,
               recommendations=None, custom=None):
    """Apply an edit. Refuses a draft belonging to another workspace."""
    draft = reportdraft.get(draft_id)
    if draft is None or draft.get("workspace") != repo.workspace:
        return None
    updated = reportdraft.edit(draft_id, by, narrative, sections, custom,
                              recommendations)
    repo.audit("report.draft_edited", "report_draft", draft_id,
               metadata={"version": updated["version"]})
    return updated


def finalise_draft(repo, draft_id, by):
    draft = reportdraft.get(draft_id)
    if draft is None or draft.get("workspace") != repo.workspace:
        return None
    updated = reportdraft.finalise(draft_id, by)
    repo.audit("report.draft_finalised", "report_draft", draft_id,
               metadata={"version": updated["version"]})
    return updated


def render_draft(repo, draft_id, by="unknown", demo=False):
    """The PDF for a draft. Returns (row, bytes).

    Numbers recomputed here, narrative read from the draft. A report exported
    twice a week apart shows the corrected figures and the same words, which
    is the behaviour worth having: the prose was somebody's, the numbers were
    never anybody's to type.
    """
    # At the service rather than only on the route: this writes history and
    # audits it, so it is an export, not a read.
    repo.require(ws.REPORTING_EXPORT)
    draft = reportdraft.get(draft_id)
    if draft is None or draft.get("workspace") != repo.workspace:
        return None, None

    template = allowed_template(repo, draft["template"])
    sections = clientreport.resolve_sections(template, draft.get("sections"))
    since, until = _period_bounds(draft.get("period"))
    meta = {
        "workspace_name": (ws.workspace(repo.workspace) or {}).get("name")
                          or repo.workspace,
        "workspace_slug": repo.workspace,
        "template": template,
        "period": draft.get("period") or "All time",
        "campaign_label": (", ".join(draft.get("campaigns") or [])
                           or "All campaigns"),
        "generated_by": by,
        "report_id": draft["id"] + " v" + str(draft.get("version") or 1),
        "generated_at": store.now()[:10],
        "demo": bool(demo),
        "narrative": draft.get("narrative") or {},
        "recommendations": draft.get("recommendations") or [],
        "custom": draft.get("custom") or [],
    }
    if (draft.get("narrative") or {}).get("title"):
        meta["title"] = draft["narrative"]["title"]

    try:
        data = report_data(repo, draft.get("campaigns"), since, until)
        raw = clientreport.build(data, meta, sections)
    except Exception as e:                                  # noqa: BLE001
        row = report_store.record(
            repo.workspace, template, sections, by, draft.get("period"),
            draft.get("campaigns"), status=report_store.FAILED,
            error=f"{type(e).__name__}: {e}"[:300])
        repo.audit("report.failed", "report", row["id"],
                   metadata={"draft": draft_id, "error": type(e).__name__})
        return row, None

    row = report_store.record(repo.workspace, template, sections, by,
                              draft.get("period"), draft.get("campaigns"),
                              bytes_written=len(raw))
    repo.audit("report.exported", "report", row["id"],
               metadata={"draft": draft_id,
                         "version": draft.get("version"),
                         "bytes": len(raw)})
    return row, raw


# --------------------------------------------------------- contact outreach
#
# The contact-scoped half of the orchestration pair. `account_view` answers
# "what is happening at this company"; this answers "what is happening to this
# person, and what may the next message say".
#
# It reads the same `account.graph` the account view does, so the two cannot
# disagree about who has touched whom.


def _engagement_of(repo, rec, contact):
    """Engagement state, cold-outreach eligibility, and provider sync.

    Three separate questions that an operator otherwise answers by reading
    three screens: what this person's last reply meant, whether anything may
    go out to them now, and whether the providers have been told.
    """
    from .. import accountpolicy as policy, tagsync

    key = contact.get("key")
    contact_action, contact_why = policy.contact_state(contact)
    account_action, account_why = policy.account_state(rec)
    outcome = policy.classify_outcome(rec, key)
    replies = account.replies(rec, key)
    blocked = eligibility._replied(rec, contact) or         eligibility._paused(rec, contact, repo.config())

    sync = {}
    try:
        for provider, row in tagsync.status_for(rec.get("id"), key).items():
            sync[provider] = ({"status": row["status"],
                               "stage": row["stage"],
                               "why": row.get("why"),
                               "attempts": row.get("attempts") or 0}
                              if row else None)
    except Exception:                                       # noqa: BLE001
        sync = {}

    return {
        "outcome": outcome if replies else None,
        "outcome_label": (policy.OUTCOME_LABEL.get(outcome)
                          if replies else "No reply recorded"),
        "contact_state": contact_action,
        "contact_why": (contact_why or {}).get("reason"),
        "account_state": account_action,
        "account_why": (account_why or {}).get("reason"),
        "last_reply_at": replies[-1]["at"] if replies else None,
        "active_conversation": bool(replies) and account_action == policy.HOLD,
        # The authority. Import-time cleaning is not this; this is asked
        # again for every step, immediately before it could go out.
        "cold_eligible": blocked is None,
        "blocked_reason": blocked,
        "blocked_why": (eligibility.HUMAN.get(blocked)
                        if blocked else None),
        "provider_sync": sync,
    }


def _sender_label(sender_id, workspace, rows=None):
    """A human's display name, falling back to the id rather than to blank."""
    if not sender_id:
        return None
    entry = senderidentity.sender(workspace, sender_id, rows) or {}
    return entry.get("display_name") or sender_id


def _step_why(step):
    """Why this step would not go out, in English.

    `eligibility.explain` is the engine's own sentence for its own codes,
    and a bare code on an operator screen is the defect this exists to stop.
    `blocked_by` is the cadence layer's answer, used only where
    eligibility had nothing to say.
    """
    for reason in step.get("eligibility_reasons") or []:
        return eligibility.explain(reason) or reason
    return step.get("blocked_by") or None


def contact_outreach(repo, record_id, contact_key, campaign_id=None):
    """One decision maker: their team, their timeline, their safe context.

    Scoped through `repo.contact`, so a contact belonging to another
    workspace returns None and the handler answers 404.
    """
    rec, contact = repo.contact(record_id, contact_key)
    if rec is None or contact is None:
        return None

    config = repo.config()
    rows = senderidentity.load()
    graph = account.graph(rec, repo.workspace, rows, config)
    entry = graph["by_contact"].get(contact_key) or {}

    campaign = repo.campaign(campaign_id) if campaign_id else None
    if campaign is None:
        campaign = next((c for c in repo.campaigns()
                         if record_id in (c.get("record_ids") or [])), None)

    senders = assignment.describe(contact) or {}
    next_sender = ((senders.get("email") or {}).get("sender_id")
                   or (senders.get("linkedin") or {}).get("sender_id"))
    context = outreachclaims.bundle(rec, contact_key, repo.workspace,
                                    next_sender, campaign, config, rows)

    # The planned cadence, kept visually separate from what happened. A
    # screen that mixed them is how a planned step becomes a claimed one.
    planned = []
    view = outreach(repo, record_id, contact_key, campaign=campaign)
    for step in (view or {}).get("steps") or []:
        planned.append({
            "step": step.get("step"),
            "day": step.get("day"),
            "channel": step.get("channel"),
            "sender": (step.get("sender") or {}).get("display_name")
            if isinstance(step.get("sender"), dict) else step.get("sender"),
            "state": step.get("status") or "planned",
            "would_send": step.get("eligible"),
            "why": _step_why(step),
            "copy": step.get("text") or step.get("body") or step.get("note"),
            "cross_channel": step.get("cross_channel"),
        })

    team = senderteam.team_for(repo.workspace,
                               (campaign or {}).get("campaign_id"), rows=rows)

    return {
        "record_id": record_id,
        "contact_key": contact_key,
        "contact": entry.get("name") or contact.get("name") or contact_key,
        "title": contact.get("title"),
        "persona": contact.get("persona"),
        "company": rec.get("company"),
        "domain": rec.get("domain"),
        "priority": entry.get("priority") or account.PRIMARY,
        "state": entry.get("state"),
        "campaign": ({"campaign_id": campaign.get("campaign_id"),
                      "name": campaign.get("name")} if campaign else None),
        "eligibility": {
            "email": bool(contact.get("email")),
            "linkedin": bool(contact.get("linkedin")),
            "verification": (contact.get("verification") or {}).get("status"),
        },
        # Four different sender facts, never collapsed into one "assigned".
        "next_sender": {
            "email": senders.get("email"),
            "linkedin": senders.get("linkedin"),
        },
        "heard_from": entry.get("sender_names") or [],
        # Where this person stands, and whether cold outreach may reach
        # them. Both come from the canonical state the reply policy wrote -
        # nothing here re-derives an engagement level from event text.
        "engagement": _engagement_of(repo, rec, contact),
        "team": senderteam.describe(team, repo.workspace, rows),
        # Display names, not ids. The touch carries `sender_id` because that
        # is what identity is; a screen showing "mark" where every other
        # panel says "Mark Weber" reads as two different people.
        "history": [dict(t, sender=_sender_label(t.get("sender_id"),
                                                 repo.workspace, rows))
                    for t in entry.get("confirmed_touches") or []],
        "planned": planned,
        "replies": entry.get("replies") or [],
        "context": context,
        "suggested": outreachclaims.suggested(context),
        "fatigue": fatigue.contact_check(rec, contact_key, config=config),
        "account": {
            "record_id": record_id,
            "company": rec.get("company"),
            "counts": graph["counts"],
            "contacts": [{"key": c["key"], "name": c["name"],
                          "title": c["title"], "state": c["state"],
                          "positive": c["positive"]}
                         for c in graph["contacts"]],
            "referrals": graph["referrals"],
            "paused": graph["paused"],
        },
    }


# ------------------------------------------------- replies, in account context
#
# A reply used to be a row about one person. Under account-based outreach the
# operator's next question is always "and what does that mean for everybody
# else at that company", so the answer travels with the row.


def referred_people(repo, rec, contact_key):
    """Anybody this contact pointed us at, and whether we can add them.

    The decision is made now rather than read from the status recorded when
    the reply arrived: somebody may have added that person, or suppressed
    them, since.
    """
    from .. import agencydnc, events as event_model, hygiene, referral

    history = hygiene.index(repo.records(), workspace=repo.workspace)
    agency = agencydnc.Index()
    out = []
    for entry in rec.get("events") or []:
        if entry.get("type") != event_model.REFERRAL_MENTIONED:
            continue
        if entry.get("contact") != contact_key:
            continue
        answer = referral.promotable(rec, entry, history=history,
                                     agency=agency)
        out.append({
            "event_id": entry.get("id"),
            "at": entry.get("at"),
            "named": entry.get("named"),
            "status": entry.get("referral_status"),
            "email": answer["email"],
            "linkedin": answer["linkedin"],
            "promotable": answer["status"] == referral.READY,
            "why": answer["why"],
            # What the reply contained, when it contained more than one
            # person and `promotable` therefore refused to pair them up.
            # Without this the refusal is a dead end: `email` and `linkedin`
            # are both None in that case, so the screen would name the
            # objection and show neither of the identifiers it is about.
            "candidates": answer.get("candidates") or {},
            "hygiene": answer.get("hygiene"),
            "existing": answer.get("contact"),
        })
    return out


def add_referred_contact(repo, record_id, contact_key, event_id,
                         by="unknown"):
    """Add the person a reply pointed at, as a contact on this account.

    A person's decision, which is what makes it allowed to write the
    referral edge `account.referrals` reads - that edge has always been
    "written by a person" rather than "never written", and this is the
    person. The classifier still cannot reach it.

    The contact arrives with nothing granted. No verification evidence, so
    `lint.sendable` is false; not selected, so no cadence expands for them;
    and every gate an imported contact passes is still in front of them.
    Adding somebody is not contacting them.
    """
    from .. import agencydnc, events as event_model, hygiene, identity, referral

    repo.require(ws.CONTACTS_VIEW)
    repo.require(ws.BATCH_CREATE)
    rec = repo.record(record_id)
    if rec is None:
        return None
    entry = next((e for e in rec.get("events") or []
                  if e.get("id") == event_id
                  and e.get("type") == event_model.REFERRAL_MENTIONED), None)
    if entry is None:
        return None

    answer = referral.promotable(
        rec, entry,
        history=hygiene.index(repo.records(), workspace=repo.workspace),
        agency=agencydnc.Index())
    if answer["status"] != referral.READY:
        raise ActionRefused(answer["why"])

    person = {
        # THE NAME `promotable` VOUCHED FOR, not the first of a comma-joined
        # list. `named` holds every name the reply mentioned; taking the first
        # of them and pairing it with whichever identifier came first is the
        # same guess the promotion check now refuses to make, one field over -
        # and the name is what appears in the greeting.
        "name": answer.get("name"),
        "email": answer["email"],
        "linkedin": answer["linkedin"],
        # Not selected. Somebody chooses who a campaign opens with, and
        # that choice is not made by the person who was referred.
        "selected": False,
        "source": {
            "added_by": by,
            "from": "referral",
            "referred_by": entry.get("contact"),
            "reply_at": entry.get("at"),
            "mention": event_id,
        },
    }
    person = {k: v for k, v in person.items() if v is not None}
    # The same helper an import uses. Safe on an append because
    # `identity.contact_key` returns a key the contact already has - so the
    # keys the cadence, the event log and the approvals all reference are
    # not re-derived - and it handles a collision with somebody already
    # here rather than overwriting them.
    rec["contacts"] = identity.assign_keys(
        list(rec.get("contacts") or []) + [person])
    added = rec["contacts"][-1]

    # Idempotent on the mention it came from. An event id is a hash of
    # provider, type, record, contact, channel and time - not of who was
    # referred - so two people added from one reply inside the same second
    # would be one edge, and the second person would silently have none.
    event_model.record(rec, event_model.REFERRAL_RECORDED,
                       contact_key=entry.get("contact"),
                       channel=entry.get("channel"), at=store.now(),
                       provider_event_id=f"{event_id}:added",
                       referred_to=added.get("key"), note=f"added by {by}")
    repo.save_records([rec])
    repo.audit("referral.contact_added", "record", record_id,
               after={"contact": added.get("key"),
                      "referred_by": entry.get("contact")},
               reason=f"referred by {entry.get('contact')}, added by {by}")
    return added


def reply_context(repo, record_id, contact_key):
    """One reply, with the account it landed in and what it does to it."""
    rec, contact = repo.contact(record_id, contact_key)
    if rec is None or contact is None:
        return None

    config = repo.config()
    rows = senderidentity.load()
    graph = account.graph(rec, repo.workspace, rows, config)
    entry = graph["by_contact"].get(contact_key) or {}
    outcome = accountpolicy.classify_outcome(rec, contact_key)
    effect = accountpolicy.affected(rec, contact_key, outcome, config)

    campaign = next((c for c in repo.campaigns()
                     if record_id in (c.get("record_ids") or [])), None)
    senders = assignment.describe(contact) or {}
    referred = referred_people(repo, rec, contact_key)
    last = (entry.get("confirmed_touches") or [None])[-1]

    return {
        "record_id": record_id,
        "contact_key": contact_key,
        "contact": entry.get("name") or contact.get("name"),
        "title": contact.get("title"),
        "company": rec.get("company"),
        "campaign": ({"campaign_id": campaign.get("campaign_id"),
                      "name": campaign.get("name")} if campaign else None),
        # Anybody this person pointed us at, with the decision made now
        # rather than when the reply arrived.
        "referred": referred,
        "outcome": outcome,
        "outcome_label": accountpolicy.OUTCOME_LABEL.get(
            outcome, outcome.replace("_", " ").title()),
        "positive": entry.get("positive"),
        "replies": entry.get("replies") or [],
        "channel": (last or {}).get("channel"),
        "sender": _sender_display(senders, (last or {}).get("channel")),
        "last_touch": last,
        "effect": effect,
        "account": {
            "counts": graph["counts"],
            "paused": graph["paused"],
            "contacts": [{"key": c["key"], "name": c["name"],
                          "title": c["title"], "state": c["state"],
                          "positive": c["positive"],
                          "planned": len(c["touches"])
                          - len(c["confirmed_touches"])}
                         for c in graph["contacts"]],
            "referrals": graph["referrals"],
        },
        "notification": notify.last_for(repo.workspace, notify.POSITIVE_REPLY),
    }


def _sender_display(senders, channel):
    entry = (senders or {}).get(channel) or {}
    return entry.get("display_name") or entry.get("sender_id")


def reply_policies(repo):
    """The reply policies in force for this workspace, for a settings screen."""
    config = repo.config()
    return {
        "policies": accountpolicy.policies(config),
        "actions": [{"key": a, "label": accountpolicy.ACTION_LABEL[a]}
                    for a in accountpolicy.ACTIONS],
        "current_behaviour": accountpolicy.CURRENT_BEHAVIOUR,
        # What each outcome actually does, resolved through the policies
        # above. The screen used to list the policies beside a warning that
        # none of them was wired in; now it can show the consequence.
        "outcomes": [
            {"outcome": outcome,
             "label": accountpolicy.OUTCOME_LABEL[outcome],
             **{k: v for k, v in accountpolicy.effects(outcome, config).items()
                if k in ("replier", "account", "review",
                         "activate_referred")}}
            for outcome in accountpolicy.OUTCOMES],
        "effect_label": dict(accountpolicy.EFFECT_LABEL),
    }


# ------------------------------------------------------- copy experiments


def campaign_experiments(repo, campaign_id=None, demo=False):
    """Every message step's experiment, evaluated. Reads; changes nothing.

    A campaign with a stored cadence graph is evaluated against its own
    records. Nothing writes `cadence_graph` yet - that is the disconnected
    link named in `PRODUCT-GAPS.md` - so today that is no campaign at all.

    **The demo cadence is a demo fallback and takes `demo` to say so.** It
    carries planted totals, and a screen that produced fictional numbers
    for a real workspace because a field happened to be empty is the shape
    this repository has been finding all week. The label under it was
    honest and it was still the wrong default: an operator asking what
    their campaign is doing should be told nothing is configured, not shown
    somebody else's numbers with a caption. Demo mode says so explicitly,
    from `--demo`, and a real process never reaches it.
    """
    campaign = repo.campaign(campaign_id) if campaign_id else None
    graph = (campaign or {}).get("cadence_graph")
    planted = None

    if graph is None and not demo:
        return {
            "campaign": {"campaign_id": (campaign or {}).get("campaign_id"),
                         "name": (campaign or {}).get("name")},
            "steps": [],
            "planted": False,
            "no_cadence_graph": True,
            "minimum_variants": variants_module.MINIMUM_VARIANTS,
            "minimum_per_variant": variants_module.settings(
                repo.config())["minimum_per_variant"],
        }

    if graph is None:
        from . import democadence, demovariants

        graph = demovariants.attach(democadence.build())
        planted = demovariants

    config = repo.config()
    recs = [r for r in repo.records()
            if r["id"] in ((campaign or {}).get("record_ids") or [])]

    steps = []
    for key, node in sorted((graph.get("nodes") or {}).items()):
        if not variants_module.is_message_node(node):
            continue
        entries = variants_module.experiment_of(node)
        objective = (node.get("objective")
                     or variants_module.DEFAULT_OBJECTIVE)
        if planted is not None:
            results = planted.results_for(key, node)
            progress = planted.PROGRESS.get(key)
        else:
            results = variants_module.results_from(recs, key, objective)
            progress = _experiment_progress(recs, key)
        verdict = variants_module.evaluate(node, results, config, progress,
                                           objective)
        shares = variants_module.allocation_of(node, config)
        by_id = {row["variant_id"]: row for row in verdict["rows"]}
        steps.append({
            "step": key,
            "label": node.get("label") or key,
            "channel": cadencegraph.NODE[node["type"]]["channel"],
            "type": node["type"],
            "day": node.get("day"),
            "objective": objective,
            "objective_label": variants_module.OBJECTIVE_LABEL.get(
                objective, objective),
            "variants": [
                {**entry,
                 "share": shares.get(entry["variant_id"]),
                 "style_name": variants_module.style_name(node["type"],
                                                          entry.get("style")),
                 "style_label": variants_module.STYLES_FOR.get(
                     node["type"], {}).get(entry.get("style"),
                                           entry.get("style")),
                 "result": by_id.get(entry["variant_id"])}
                for entry in (entries or [])],
            "verdict": verdict,
            "state": verdict["state"],
            "state_label": variants_module.STATE_LABEL.get(
                verdict["state"], verdict["state"]),
            "leader": verdict.get("leader"),
            "progress": progress,
            "shifted": abs(max(shares.values(), default=0.0)
                           - min(shares.values(), default=0.0)) > 0.001,
        })
    return {
        "campaign": {"campaign_id": (campaign or {}).get("campaign_id"),
                     "name": (campaign or {}).get("name")},
        "steps": steps,
        "planted": planted is not None,
        "no_cadence_graph": False,
        "minimum_variants": variants_module.MINIMUM_VARIANTS,
        # The evaluator's own floor, so the screen can decline to print a
        # rate the evaluator would refuse to act on. Read from config
        # rather than hard-coded: a workspace that raised the floor has
        # raised it for the screen too.
        "minimum_per_variant": variants_module.settings(
            repo.config())["minimum_per_variant"],
    }


def _experiment_progress(recs, step_key):
    """How much of the eligible population has run this step.

    Confirmed touches over selected contacts. Returns None when there is
    nobody to be a denominator, because 0/0 is not 0%.
    """
    eligible = sum(1 for rec in recs
                   for c in account.contacts_of(rec) if c.get("selected"))
    if not eligible:
        return None
    done = sum(1 for rec in recs
               for c in account.contacts_of(rec)
               for t in account.touches(rec, c.get("key"), confirmed_only=True)
               if t.get("step") == step_key)
    return min(1.0, done / float(eligible))


# --------------------------------------------------- plan-level campaign QA
#
# `qa.report` checks the drafts. This checks the plan: the cadence, the
# senders, the roles, the pacing and the claims. A reviewer sees both before
# approving, because neither is visible from the other.


def campaign_plan_qa(repo, campaign_id, template=None):
    """The plan-level review for one campaign, for the approval screen."""
    campaign = repo.campaign(campaign_id)
    if campaign is None:
        return None
    rows = senderidentity.load()
    graph = campaign.get("cadence_graph")
    if graph is None and template:
        try:
            graph = cadencegraph.from_template(
                template,
                email_sender=_first_sender(repo, "email", rows),
                linkedin_sender=_first_sender(repo, "linkedin", rows),
                second_email=_first_sender(repo, "email", rows, 1),
                second_linkedin=_first_sender(repo, "linkedin", rows, 1))
        except cadencegraph.CadenceError:
            graph = None
    return campaignqa.review(repo, campaign, graph=graph, rows=rows)



# ------------------------------------------------------------ gtm decisions


def strategy_centre(repo):
    """What was decided about how this workspace is worked, and why.

    Gated on `operations.view`: this is agency reasoning about a client,
    not a client-facing summary of it. A viewer sees outcomes; the argument
    behind the targeting is not one of them.
    """
    repo.require(ws.OPERATIONS_VIEW)
    overrides = ws.policy(repo.workspace)
    found = gtm.summarise(repo.workspace, overrides)
    found["history"] = gtm.history(repo.workspace)
    found["can_record"] = repo.may(ws.WORKSPACE_MANAGE)
    found["areas_available"] = [{"area": a, "label": gtm.AREA_LABEL[a]}
                                for a in gtm.AREAS]
    found["bases_available"] = [
        {"basis": b, "label": gtm.BASIS_LABEL[b],
         "needs_evidence": b in gtm.CHECKABLE}
        for b in gtm.BASES]
    found["policy_keys"] = sorted(ws.POLICY_KEYS)
    # The settings a person has changed and not explained. Named here
    # rather than only on the settings screen, because the person who
    # would write the explanation is the one reading this page.
    found["unexplained_detail"] = [
        {"key": key,
         "label": (ws.POLICY_KEYS.get(key) or {}).get("label") or key,
         "value": overrides.get(key)}
        for key in found["unexplained"]]
    return found


def record_decision(repo, area, decided, why, basis=None, evidence=None,
                    policy_key=None, supersedes=None):
    """Write down a GTM decision. Changes no configuration whatsoever.

    Deliberately inert. Recording "we are moving up-market" moves no
    threshold and excludes no company - `workspaces.set_policy` is the only
    thing that changes what the machine does, and a decision store that
    also enforced would be a second configuration quietly disagreeing with
    the first.

    `workspace.manage` rather than an operator permission: an operator runs
    the machine, and this is a statement about which direction it is
    pointed.
    """
    repo.require(ws.WORKSPACE_MANAGE)

    if policy_key and policy_key not in ws.POLICY_KEYS:
        raise gtm.DecisionRefused(
            f"{policy_key} is not a setting this workspace can change, so a "
            "decision cannot be attached to it")

    entry = gtm.decision(
        repo.workspace, (area or "").strip(), decided=decided, why=why,
        basis=(basis or gtm.JUDGEMENT).strip() or gtm.JUDGEMENT,
        evidence=evidence, policy_key=(policy_key or "").strip() or None,
        decided_by=repo.actor)

    if supersedes:
        entry = gtm.supersede(repo.workspace, supersedes, entry)
    else:
        gtm.record(entry)

    repo.audit("gtm.decided", "workspace", repo.workspace,
               after={"area": entry["area"], "basis": entry["basis"],
                      "policy_key": entry["policy_key"],
                      "supersedes": entry.get("supersedes")},
               reason=entry["decided"][:200])
    return entry


# ------------------------------------------------------------------ learning


def learning_rows(repo):
    """One row per account: its cohort dimensions and what happened to it.

    Built here rather than in `learning` because this is where the
    workspace scope lives. `repo.records()` has already narrowed to one
    tenant and this never widens it - a cohort assembled across workspaces
    would be one client's performance informing another's targeting.

    "Contacted" means a *confirmed* touch. A planned or approved step is
    not outreach that happened, and counting it would inflate every
    denominator and quietly deflate every rate.
    """
    from .. import account as account_module

    rows = []
    for rec in repo.records():
        qualification = rec.get("qualification") or {}
        segment = qualification.get("segment") or {}
        verdict = qualification.get("verdict") or {}

        contacted = bool(account_module.touches(rec, confirmed_only=True))
        outcomes = {learning.REPLIED: False, learning.POSITIVE: False,
                    learning.MEETING: False}
        for contact in account_module.contacts_of(rec):
            key = contact.get("key")
            if not account_module.replies(rec, key):
                continue
            outcomes[learning.REPLIED] = True
            if accountpolicy.classify_outcome(rec, key) == accountpolicy.POSITIVE:
                outcomes[learning.POSITIVE] = True

        personas = {c.get("persona") for c in account_module.contacts_of(rec)
                    if c.get("selected") and c.get("persona")}
        rows.append({
            "record_id": rec.get("id"),
            "country": (segment.get("country") or "").title() or None,
            "region": segment.get("region"),
            "vertical": segment.get("vertical"),
            "industry": segment.get("industry"),
            "employee_band": segment.get("employee_band"),
            "icp_tier": verdict.get("icp_tier"),
            # One persona per row or none: an account worked through two
            # personas belongs to neither cohort cleanly, and inventing a
            # "champion+buyer" cohort would be inventing a segment.
            "persona": next(iter(personas)) if len(personas) == 1 else None,
            learning.CONTACTED: contacted,
            **outcomes,
        })
    return rows


def cohort_performance(repo, dimensions=None, objective=None):
    """What the cohorts on these dimensions have actually done.

    Reports and recommends. Nothing here changes targeting, a campaign or
    the ICP - see `src/learning.py`, and GTM-STRATEGY.md for why a
    performance number is not a strategy decision.
    """
    repo.require(ws.OPERATIONS_VIEW)
    chosen = tuple(d for d in (dimensions or ("country", "vertical"))
                   if d in learning.DIMENSIONS)
    if not chosen:
        chosen = ("country", "vertical")
    config = repo.config()
    rows = learning_rows(repo)
    described = learning.describe(rows, chosen, config,
                                  objective or learning.DEFAULT_OBJECTIVE)
    return {
        **described,
        "accounts": len(rows),
        "contacted": len([r for r in rows if r[learning.CONTACTED]]),
        "recommendations": learning.recommend(described, config),
        "available_dimensions": [
            {"key": key, "chosen": key in chosen}
            for key in learning.DIMENSIONS],
    }



# ----------------------------------------------------------------- discovery


def discovery_view(repo, run=None):
    """This week's proposals, and what the delta did to them.

    Read-only and costs nothing. Enrichment is what costs money and it
    happens after the first approval gate, so this screen is deliberately
    the last thing before a decision rather than a step that has already
    spent something.
    """
    repo.require(ws.OPERATIONS_VIEW)
    from .. import clientreview as review_module

    runs = discovery.runs(repo.workspace)
    current = run or (runs[0]["run"] if runs else None)

    # This run's proposals, and everything *earlier* runs proposed. The
    # split matters: a run's own rows must not exclude themselves as
    # already-seen, and rows from previous weeks must.
    proposed, earlier = [], set()
    for row in discovery.load(repo.workspace):
        if current is not None and row.get("run") == current:
            proposed.append(row)
        elif row.get("domain"):
            earlier.add(row["domain"])

    universe = discovery.known(repo, seen=earlier,
                               suppressed=ingest.load_suppress())
    decided = review_module.decided(repo.workspace)
    found = discovery.delta(proposed, universe, decided)

    return {
        **found,
        "run": current,
        "runs": runs,
        "decided": len(decided),
        "can_export": repo.may(ws.CONTACTS_EXPORT),
        "statuses": [{"key": s, "label": review_module.STATUS_LABEL[s],
                      "effect": review_module.EFFECT[s]}
                     for s in review_module.STATUSES],
        # The file that would go to the client. Built here so the screen
        # can say how many rows it carries without generating it twice.
        "review_rows": len(found["new"]),
    }


def discovery_csv(repo, run=None):
    """The review file for this run's new candidates.

    `contacts.export` rather than a discovery permission: this is
    contact-adjacent data leaving the building, and that is the
    permission that already governs data leaving.
    """
    repo.require(ws.CONTACTS_EXPORT)
    from .. import clientreview as review_module

    found = discovery_view(repo, run)
    # The run these candidates belong to. The batch is part of the
    # candidate id, so a file named for the wrong run comes back with ids
    # that match nothing and every row is refused as one we never sent.
    batch = run or found.get("run") or "run"
    return {
        "filename": f"resonate-review-{repo.workspace}-{batch}.csv",
        "csv": review_module.to_csv(repo.workspace, batch, found["new"]),
        "rows": len(found["new"]),
        "batch": batch,
    }



# ------------------------------------------------------------------ audience


def audience_overview(repo, batch=None):
    """What this market universe is, in one screen.

    A thirty-thousand-domain upload is not thirty thousand rows to read.
    It is a shape: how many survived normalisation, how many are a fit,
    how many can be reached, and where they are. Somebody who uploads a
    list should be able to answer "what did I just give you" without
    scrolling.

    Every number is counted from stored state. Nothing here classifies,
    scores or spends - `qualify` decided the verdicts, `channels` decided
    reachability, and this joins and counts, which is the only arithmetic
    an overview is allowed.

    The stages are deliberately not a funnel of *outcomes*. They stop at
    "could be worked", because everything after that belongs to a campaign
    and a campaign is a decision somebody makes.
    """
    repo.require(ws.CONTACTS_VIEW)
    config = repo.config()
    suppressed = ingest.load_suppress()
    recs = repo.records(batch=batch)

    known = qualified = contactable = with_people = 0
    stopped = 0
    by_status = {}
    for rec in recs:
        qualification = rec.get("qualification") or {}
        verdict = qualification.get("verdict") or {}
        status = verdict.get("icp_status")
        if qualification:
            known += 1
            by_status[status or "unknown"] = by_status.get(
                status or "unknown", 0) + 1
            if status == "qualified":
                qualified += 1

        # Counted among companies that are a fit, not among all of them.
        # Contacts exist on companies we later rejected, and counting
        # those against the qualified total produced "122% of 27" - a
        # share above one, which is a denominator that does not mean what
        # the row says it means.
        fit = status == "qualified"
        contacts = [c for c in rec.get("contacts") or [] if c.get("selected")]
        if fit and contacts:
            with_people += 1
        reachable = fit and any(
            channels.evaluate(rec, contact, config, suppressed)["mode"]
            != channels.NONE for contact in contacts)
        if reachable:
            contactable += 1
        state, _ = accountpolicy.account_state(rec)
        if state in (accountpolicy.STOP, accountpolicy.HOLD):
            stopped += 1

    # Each stage says what it is *of*, because a stage count with no
    # denominator is the figure people quote and nobody can check.
    total = len(recs)
    stages = [
        ("Companies in the audience", total, total,
         "every row that survived import"),
        ("Understood", known, total,
         "an ICP verdict has been recorded"),
        ("A fit", qualified, known,
         "qualified against this client's ICP"),
        ("Decision makers found", with_people, qualified,
         "a fit, with at least one contact selected"),
        ("Reachable", contactable, with_people,
         "a fit, reachable on a verified channel"),
    ]

    return {
        "batch": batch,
        "batches": sorted(repo.batches()),
        "total": total,
        "stages": [{"label": label, "count": count, "of": of,
                    "share": (count / of) if of else None, "why": why}
                   for label, count, of, why in stages],
        "by_status": by_status,
        # Not part of the ladder: an account we may not write to has not
        # failed a stage, it has been ruled out of one.
        "not_workable": stopped,
        "distribution": report.qualification_distribution(recs, repo.client),
        "empty": total == 0,
    }


def _first_sender(repo, channel, rows, index=0):
    """A sender who can carry this channel, for previewing a template."""
    people = senderidentity.senders(repo.workspace, rows, active_only=True)
    lookup = (senderidentity.email_accounts if channel == "email"
              else senderidentity.linkedin_accounts)
    able = [s["sender_id"] for s in people
            if lookup(repo.workspace, rows, s["sender_id"])]
    if not able:
        return "unassigned"
    return able[min(index, len(able) - 1)]


# ------------------------------------------------------- account intelligence


class SignalRefused(RuntimeError):
    """The signal was not recorded, and the message says what was wrong."""


# The shortest thing that can still be quoted back to a prospect. Not a
# style rule: "yes", "growing" and "saw it" are all things somebody would
# type into a required field to get past it, and none of them is evidence.
MINIMUM_EVIDENCE = 12


def record_signal(repo, record_id, signal_type, evidence, observed_at=None,
                  confidence=None, contact_key=None, source_ref=None):
    """Write down something a person observed about an account.

    Four refusals, each for its own reason:

    - the permission, asked before anything is read
    - the record, resolved through `repo` so an id from another workspace
      is a 404 and not a write
    - the type, which may not be an engagement signal: reply state comes
      from the event log and a handwritten copy of it would be the copy
      that goes stale
    - the evidence, which has to be long enough to quote

    The date defaults to today rather than to nothing. Undated signals are
    treated as one half-life old, and that default is right for a signal
    whose date was never known - not for one a person is entering as they
    see it.
    """
    repo.require(ws.SIGNALS_RECORD)

    rec = repo.record(record_id)
    if rec is None:
        return None

    if signal_type not in signals_module.enterable():
        # Two different failures, and they deserve two different
        # sentences: an engagement type is a rule, an unrecognised one is
        # a mistake. Telling somebody who mistyped a type that "engagement
        # comes from the event log" explains the wrong thing.
        if signal_type in signals_module.SCOPE_OF:
            raise SignalRefused(
                "engagement is read from the event log, not entered by hand")
        raise SignalRefused(f"unknown signal type: {signal_type}")

    evidence = (evidence or "").strip()
    if len(evidence) < MINIMUM_EVIDENCE:
        raise SignalRefused(
            "say what was actually observed - something specific enough to "
            "quote back, like '7 open delivery roles on the careers page'")

    confidence = confidence or signals_module.MEDIUM
    if confidence not in signals_module.CONFIDENCE:
        raise SignalRefused(f"unknown confidence: {confidence}")

    if contact_key and not any(
            c.get("key") == contact_key for c in account.contacts_of(rec)):
        raise SignalRefused("that contact is not on this account")

    entry = signals_module.signal(
        repo.workspace, signal_type, record_id=record_id,
        contact_key=contact_key or None, evidence=evidence,
        source=signals_module.MANUAL, source_ref=(source_ref or "").strip()
        or None,
        observed_at=(observed_at or "").strip() or store.now(),
        confidence=confidence, created_by=repo.actor)
    signals_module.record(entry)
    # The evidence is the point of the entry, so it is what the audit line
    # carries. It is a quotable observation, not a secret.
    repo.audit("signal.recorded", "record", record_id,
               after={"type": signal_type, "confidence": confidence},
               reason=evidence[:200])
    return entry


def signal_form(repo, record_id=None):
    """What the entry form may offer: the types, and whether it may write."""
    return {
        "may_record": repo.may(ws.SIGNALS_RECORD),
        "record_id": record_id,
        "types": [{"type": t, "label": signals_module.LABEL[t],
                   "scope": signals_module.SCOPE_OF[t]}
                  for t in signals_module.enterable()],
        "confidence": list(signals_module.CONFIDENCE),
        "minimum_evidence": MINIMUM_EVIDENCE,
    }


def signal_dashboard(repo, tier=None, limit=200):
    """Prioritised accounts, why, and whether they may actually be worked.

    Scoped by `repo.records()`, so an account outside this workspace cannot
    reach it. Scoring happens here rather than in the template, and the list
    is capped rather than silently truncated - `shown` and `total` both
    travel so the screen can say which it is looking at.
    """
    config = repo.config()
    # Once for the page, not once per contact: `channels.evaluate` reads
    # the suppression file whenever it is not handed one.
    suppressed = ingest.load_suppress()
    signal_index = signals_module.index(repo.workspace)
    rows = []
    for rec in repo.records():
        found = priority_module.assess(rec, repo.workspace, config,
                                       suppressed=suppressed,
                                       signal_index=signal_index)
        rows.append({
            "record_id": found["record_id"],
            "company": found["company"],
            "domain": rec.get("domain"),
            "score": found["score"],
            "tier": found["tier"],
            "tier_label": found["tier_label"],
            "why_now": found["why_now"],
            "eligible": found["eligibility"]["eligible"],
            "blocked": found["eligibility"]["blocked"],
            "signals": found["signals"],
            "fresh": len([s for s in found["signals"]
                          if s["freshness"] == signals_module.FRESH]),
        })
    rows.sort(key=lambda r: (-r["score"], str(r["company"] or "")))
    listed = [r for r in rows if r["tier"] == tier] if tier else rows

    by_type = {}
    for row in rows:
        for entry in row["signals"]:
            if entry["freshness"] == signals_module.STALE:
                continue
            bucket = by_type.setdefault(
                entry["type"], {"type": entry["type"],
                                "label": entry["label"], "count": 0,
                                "accounts": set()})
            bucket["count"] += 1
            bucket["accounts"].add(row["record_id"])

    return {
        "accounts": listed[:limit],
        "shown": min(len(listed), limit),
        "total": len(rows),
        "filtered": bool(tier),
        "tier": tier,
        "tiers": [{"key": key, "label": priority_module.TIER_LABEL[key],
                   "count": len([r for r in rows if r["tier"] == key])}
                  for key in priority_module.TIERS],
        "signal_types": sorted(
            ({**v, "accounts": len(v["accounts"])} for v in by_type.values()),
            key=lambda r: -r["count"]),
        "counts": {
            "accounts": len(rows),
            "with_signals": len([r for r in rows if r["signals"]]),
            "with_fresh": len([r for r in rows if r["fresh"]]),
            "not_eligible": len([r for r in rows if not r["eligible"]]),
        },
    }


# ---------------------------------------------------------------------------
# The floor nobody could prove was breached.
#
# WHY THIS IS A SECOND SCREEN AND NOT A COLUMN ON THE FIRST. `/admin/lanes`
# answers queue depth RIGHT NOW. That number goes green the instant somebody
# tops a queue up, and the hours that were lost leave no trace in any file in
# this estate - which is why the 89.9 lane-hours lost to an empty queue over
# 2026-10-15 had to be reconstructed by hand from logs, and why two further
# breaches that happened while that reconstruction was running were found by a
# person reading `queue/` at 02:46 rather than by any instrument.
#
# THIS PAGE WRITES. It is the only screen in this application that does, and
# the write is the point: one row per lane per render, appended to a ledger
# under `runtime/`, never rewritten. `lane_board` above documents itself as
# side-effect-free and stays that way - the sampler is kept here so that
# promise is not quietly broken on the page that made it.
#
# `src.floorledger` holds the arithmetic and every refusal. This function
# shapes it for rendering and adds the one thing a shaper must add: the
# coverage, in a form the page can print ABOVE every total.

#: What this page cannot answer, however long the ledger runs.
LEDGER_CANNOT_SEE = (
    ("anything before the ledger's first row",
     "the ledger starts when it was created and the estate did not. That "
     "stretch is UNKNOWN, it is not zero, and the only thing that shrinks it "
     "is time"),
    ("whether a sample was missed or the lane was quiet",
     "this ledger grows when the page is RENDERED. A stretch with no sample "
     "in it is a fact about how often somebody looked, and it is reported as "
     "UNKNOWN rather than as a lane that stopped breaching the floor"),
    ("why a queue was below the floor",
     "a depth of 1 because nobody wrote a brief and a depth of 1 because six "
     "were just consumed look identical here. The watcher log on "
     "`/admin/lanes` is where that is read"),
    ("whether a queued brief is any good",
     "depth is a count of files. A deep queue of stale briefs is worse than "
     "an empty one, and nothing here opens one"),
    ("a reading taken in the same second as its neighbours",
     "two renders inside one second produce a stretch with no duration, and "
     "a stretch with no duration is dropped before the run builder sees it. "
     "So a compliant reading sandwiched between two breaches in the same "
     "second does not split the run. The below-floor total is unaffected - "
     "the dropped stretch was zero seconds - and only the shape of the run "
     "moves. Measured, not predicted"),
)


def floor_ledger(now=None, probe=None, samples=None, write=True,
                 window_seconds=None, max_gap_seconds=None):
    """One sample per lane appended, then what the ledger can prove.

    `write=False` for a reader that must not grow the history. The default
    writes, because the page is the sampler.
    """
    import os

    window = (floorledger.WINDOW_SECONDS if window_seconds is None
              else window_seconds)
    gap = (floorledger.MAX_SAMPLE_GAP_SECONDS if max_gap_seconds is None
           else max_gap_seconds)
    report = floorledger.render(now=now, probe=probe, samples=samples,
                                window_seconds=window, max_gap_seconds=gap,
                                write=write)
    board = report["board"]
    ledger = report["ledger"]
    estate = report["estate"]

    # The depth and verdict as they are RIGHT NOW, from the board, so a
    # reader can see the current state beside the history. Kept apart from
    # every ledger figure: the current reading is not in the history yet, and
    # the stretch since the last row is UNKNOWN.
    current = {row["lane"]: row for row in board.get("lanes", [])}

    # THE ONE CONDITION THAT LICENSES ANY TOTAL ON THIS PAGE. Zero rows is
    # not zero breaches, so a ledger that is absent, empty, unreadable or
    # bigger than the reader will hold produces NO numbers at all - not a
    # clean estate, not a zero, not a dash in a table of otherwise real
    # figures. This repository has shipped an instrument with no data
    # printing a clean bill before.
    reasons = {
        floorledger.ABSENT: "the ledger file does not exist yet, so nothing "
                            "is known about any window. ZERO ROWS IS NOT "
                            "ZERO BREACHES",
        floorledger.EMPTY: "the ledger file exists and has no rows in it, so "
                           "nothing is known about any window. An empty "
                           "ledger is not a clean estate",
        floorledger.UNREADABLE: "the ledger file could not be opened. Its "
                                "contents are UNKNOWN and no total may be "
                                "computed from a file nobody read",
        floorledger.OVERSIZE: "the ledger is larger than this reader will "
                              "hold (%s bytes against a cap of %s). It was "
                              "NOT truncated to a tail, because a tail would "
                              "make the coverage line below a statement "
                              "about this reader's buffer instead of about "
                              "the estate"
                              % (ledger.get("bytes"), ledger.get("max_bytes")),
    }
    # ONE GATE, AND IT IS THE READER'S. `floorledger.totals_licensed` is
    # the only thing that decides, and `render` has already applied it - when
    # it refuses, `estate` was never built, so there is no number here for
    # this function to shape even by mistake.
    totals_available = bool(report["licensed"] and estate)
    no_totals_why = None
    if not totals_available:
        no_totals_why = reasons.get(
            ledger["state"],
            "the ledger is readable and holds no row this reader could "
            "place, so no window is covered")

    lanes_out = []
    for row in (estate["lanes"] if estate else []):
        cover = row["coverage"]
        now_row = current.get(row["lane"], {})
        lanes_out.append({
            "lane": row["lane"],
            "rows": cover["rows"],
            "first": _stamp(cover["first"]),
            "last": _stamp(cover["last"]),
            "covers_window": row["covers_window"],
            "covered_seconds": cover["covered_seconds"],
            "unknown_seconds": row["unknown_seconds"],
            "observed_seconds": row["observed_seconds"],
            "holes": [{"from": _stamp(hole["from"]),
                       "to": _stamp(hole["to"]),
                       "seconds": hole["seconds"],
                       "why": hole["why"],
                       "why_text": floorledger.HOLE_TEXT.get(hole["why"],
                                                             hole["why"])}
                      for hole in cover["holes"]],
            "depth_zero_seconds": row["depth_zero_seconds"],
            "below_floor_seconds": row["below_floor_seconds"],
            "within_floor_seconds": row["within_floor_seconds"],
            "undecidable_seconds": row["undecidable_seconds"],
            "by_bucket": _buckets(row["below_floor_by_bucket"]),
            "other_states": [{"state": state, "seconds": seconds}
                             for state, seconds in row["other_states"]],
            "longest_run": _run(row["longest_below_floor_run"]),
            "floors_seen": row["floors_seen"],
            # NOW, from the board. Not part of the history and labelled as
            # such wherever it is shown.
            "current_depth": now_row.get("queue_depth"),
            "current_state": now_row.get("verdict"),
            "current_below_floor": now_row.get("below_floor"),
        })

    shaped = {
        "at": _stamp(report["at"]),
        "root_name": (os.path.basename(board["root"]) if board.get("root")
                      else None),
        "board_state": board.get("state"),
        # The NAME of the ledger, never its absolute path - the same rule as
        # `root_name` on the lane board, for the same reason.
        "ledger_name": os.path.join(floorledger.RUNTIME_DIR,
                                    floorledger.LEDGER_NAME),
        "ledger_state": ledger["state"],
        "ledger_rows": len(ledger["rows"]),
        "ledger_lines": ledger["lines"],
        # THE COUNT OF UNPARSEABLE ROWS, printed whether it is zero or not.
        # A row that could not be read is not skipped: it makes the stretch
        # it sits in UNKNOWN, and a reader has to see how many there are
        # before trusting anything below.
        "damaged_rows": len(ledger["damaged"]),
        "damaged": [{"line_number": entry["line_number"],
                     "at": entry["at"]} for entry in ledger["damaged"][:50]],
        "append_state": report["append"]["state"],
        "append_why": floorledger.APPEND_TEXT.get(report["append"]["state"]),
        "append_written": report["append"]["written"],
        "floor": report["floor"],
        "floor_state": report["floor_state"],
        "floor_state_why": lanes.FLOOR_STATE_TEXT.get(report["floor_state"]),
        "floor_path_shown": os.path.join("queue", "README.md"),
        "floor_line": report["floor_line"],
        "window_seconds": window,
        "max_gap_seconds": gap,
        "totals_available": totals_available,
        "no_totals_why": no_totals_why,
        "lanes": lanes_out,
        "lane_count": len(lanes_out),
        "estate": ({
            "covers_window": estate["covers_window"],
            "lanes_not_covering": estate["lanes_not_covering"],
            "totals": estate["totals"],
            "by_bucket": _buckets(estate["below_floor_by_bucket"]),
            "longest_run": _run(estate["longest_below_floor_run"]),
            "floors_seen": estate["floors_seen"],
        } if estate else None),
        "bucket_glossary": [
            {"bucket": key, "label": label, "why": why}
            for key, (label, why) in sorted(floorledger.BUCKET_TEXT.items())],
        "hole_glossary": [{"why": key, "text": text} for key, text
                          in sorted(floorledger.HOLE_TEXT.items())],
        "cannot_see": [{"area": area, "why": why}
                       for area, why in LEDGER_CANNOT_SEE],
    }
    # OVER THIS PAGE'S OWN PAYLOAD, not the board's. The ledger reshapes
    # almost every field it takes from the board, so a table computed on the
    # board's paths would describe keys this page does not render and miss
    # the ones it does.
    paths = laneprovenance.paths_of(shaped, "floor_ledger")
    paths |= {"floor_ledger.provenance"}
    shaped["provenance"] = laneprovenance.table(paths)
    return shaped


def _stamp(when):
    return None if when is None else when.strftime(lanes._STAMP)


def _buckets(mapping):
    """The WORKING / IDLE / neither split, in the reader's own words."""
    return [{"bucket": key,
             "label": floorledger.BUCKET_TEXT[key][0],
             "why": floorledger.BUCKET_TEXT[key][1],
             "seconds": mapping.get(key, 0)}
            for key in (floorledger.WORKING, floorledger.IDLE_,
                        floorledger.OTHER)]


def _run(run):
    if not run:
        return None
    return {"lane": run["lane"], "from": _stamp(run["from"]),
            "to": _stamp(run["to"]), "seconds": run["seconds"],
            "buckets": sorted(run["buckets"].items())}


# ---------------------------------------------------------------------------
# The nine CANARY-01 exit criteria.
#
# Gated the way `/admin/health` and `/admin/lanes` are - an account-level
# check rather than a workspace permission - and for the same reason. These
# nine are a fact about one client's first live send and about artifacts on
# this machine; a workspace permission would be a permission over data no
# workspace owns, and `operations.view` reaches a client-facing REVIEWER.
#
# `src.exitcriteria` holds the reading. This function only shapes it and adds
# what the page is required to say it cannot see.

#: What this page deliberately does NOT do, and why each one would be worse
#: than an UNKNOWN. Every item here is a measurement somebody has already
#: asked this page for.
EXIT_CRITERIA_REFUSALS = (
    ("re-derive any of the nine",
     "not one verdict here is measured by this page. Each is read out of an "
     "artifact somebody else recorded, at a named age - because a second "
     "instrument measuring the same criterion is a second authority, and "
     "two authorities for one number is this repository's own named defect"),
    ("resolve a disagreement between two authorities",
     "a criterion two live authorities answer DIFFERENTLY renders UNKNOWN / "
     "CONTESTED, naming both files, both verdicts and both measuring tasks - "
     "whatever the verdicts are and whatever the files' ranks. Not resolved "
     "by rank, not by recency and not by which document is longer. "
     "CONTESTED is a different instruction from UNKNOWN: measuring again "
     "does not fix it, and the operator naming an authority does"),
    ("let a silent designated authority veto another one's answer",
     "a criterion the designated authority does not mention, but which "
     "another authority answers, renders that other verdict - MARKED with "
     "the file it came from. Criteria 4 and 8 are the live instance: "
     "`EXIT-CRITERIA-2026-10-16.md` re-audited criteria 3, 5 and 9 only, so "
     "it was never going to answer either, and treating its silence as a "
     "veto would have left two answered criteria reading UNKNOWN"),
    ("register an authority it found on disk",
     "the scan that finds a file the configuration does not name changes NO "
     "verdict and NO tally. It changes one sentence above the table. The "
     "same scan finds `LANE-webapp.md`, whose prose about these criteria "
     "parses as a verdict block - a page that promoted what it found would "
     "become an authority on itself"),
    ("assert the conjunction over a set it may not have read in full",
     "when the scan announces an unregistered authority, or could not run at "
     "all, a conjunction that would otherwise read MET reads UNKNOWN. The "
     "page has just said it may not have opened every authority; it has no "
     "standing to then settle what those authorities would settle"),
    ("render a verdict the authority took back",
     "a struck-through, superseded, void or revoked verdict renders "
     "WITHDRAWN, with the value it held shown as history. A page that "
     "silently resurrects a withdrawn MET is worse than one that omits the "
     "row, and `EXIT-CRITERIA-2026-10-16.md` carries exactly that shape"),
    ("show a verdict whose measurement date it could not establish",
     "that renders STALE, in its own state, and never the value it carried. "
     "MET with no date is not a verdict - it is a memory, and two claims in "
     "this estate were wrong on 2026-10-15 from being re-read instead of "
     "re-measured"),
    ("read a block a heading calls history",
     "an appendix, a first pass or a superseded section is not the current "
     "entry wherever it sits in the file. These documents are not purely "
     "append-only and 'the last block wins' read the retained first pass of "
     "the designated authority"),
    ("treat an absent file as a pass",
     "absence of a record is a refusal, never a pass. That is the "
     "provider-write guard's own rule and it applies identically here"),
    ("say anything about WHEN a verdict was invalidated",
     "a verdict is invalidated by a commit, not by the clock, and this page "
     "reads no git ref. `stale` is the artifact's age against a 24-hour "
     "horizon and is a prompt to re-measure - never a verdict, and it does "
     "not change one"),
)


def exit_criteria(now=None):
    """Nine rows, and the one question that gates a first live send.

    Read-only and side-effect-free: no file is written, no provider is
    reached, no socket is opened and no credential is read.
    """
    data = exitcriteria.report(now=now)
    data["refused"] = [{"what": what, "why": why}
                       for what, why in EXIT_CRITERIA_REFUSALS]
    # THE HEADLINE IS THE CONJUNCTION, NOT A FRACTION. CANARY-01 activates
    # only when all nine are true, so the nine have ONE answer, and
    # "3 of 9 are MET" is a partial pass written as a score - it invites a
    # reader to feel a third of the way there when there is no such
    # position. `EXIT-NINE-AT-ONCE-2026-10-16.md` exits 2 on exactly this
    # question and the page must not render that as nine independent rows
    # with no overall verdict.
    #
    # Computed in `src.exitcriteria`, not here, so the renderer holds no
    # second opinion about what nine verdicts add up to.
    data["headline"] = (
        "the conjunction over all %d criteria is %s"
        % (len(exitcriteria.CRITERIA), data["conjunction_label"]))
    data["counted"] = (
        "%d MET, %d NOT MET, %d UNKNOWN, %d WITHDRAWN, %d STALE - over the "
        "%d authorities named above and no others"
        % (data["tally"][exitcriteria.MET],
           data["tally"][exitcriteria.NOT_MET],
           data["tally"][exitcriteria.UNKNOWN],
           data["tally"][exitcriteria.WITHDRAWN],
           data["tally"][exitcriteria.STALE],
           len(data["authority_set"])))
    # THIS PAGE'S EXPOSURE IS A DIFFERENT ONE AND THE TABLE SAYS SO. It reads
    # no watcher log, no `.out`, no `DONE\` folder and no process, so no
    # false DONE entry can move a figure on it - and every figure instead
    # rests on a document that can go STALE with no interlock, or be
    # CONTESTED by a second document, or carry a WITHDRAWN verdict in an
    # appendix its body still states.
    paths = laneprovenance.paths_of(data, "exit_criteria")
    paths |= {"exit_criteria.provenance"}
    data["provenance"] = laneprovenance.table(paths)
    return data


# ---------------------------------------------------------------------------
# Can this send right now?
#
# Gated exactly as the criteria page above is, and for the same reason: this
# is a fact about one client's first live send and about documents on this
# machine, so no workspace permission can express reading it.
#
# `src.gonogo` holds the reading. This function shapes it and adds what the
# page is required to say about itself. NOTHING here recomputes a verdict -
# the one decision on the whole path is `gonogo.verdict_of`, and it lives in
# the domain module precisely so this layer and the renderer cannot hold a
# second opinion about what nineteen rows add up to.


def go_no_go(now=None):
    """GO or NO-GO, and if NO-GO the shortest list that would change it.

    Read-only and side-effect-free: no file is written, no provider is
    reached, no socket is opened, no credential is read and no git command is
    run.
    """
    data = gonogo.report(now=now)
    # THE HEADLINE IS ONE WORD AND A LIST, NOT A SCORE. "13 of 19 rows
    # resolved" is a partial pass written as a fraction, and there is no such
    # position on the morning of a first live send: one UNKNOWN row dominates
    # any number of passes. Computed in `src.gonogo`.
    data["headline"] = ("CANARY-01 %s right now"
                        % ("CAN send" if data["verdict"] == gonogo.GO
                           else "cannot send"))
    data["counted"] = (
        "%d MET, %d NOT MET, %d UNKNOWN, %d WITHDRAWN, %d STALE - over the "
        "%d source documents named above and no others"
        % (data["tally"][gonogo.MET], data["tally"][gonogo.NOT_MET],
           data["tally"][gonogo.UNKNOWN], data["tally"][gonogo.WITHDRAWN],
           data["tally"][gonogo.STALE], len(data["sources"])))
    data["refused"] = [{"what": what, "why": why}
                       for what, why in gonogo.REFUSALS]
    # THIS PAGE'S EXPOSURE, STATED IN THE SAME TABLE EVERY OTHER PAGE USES.
    # It reads four documents and nothing else - no process, no watcher log,
    # no provider and no git - so the ways it can be wrong are exactly: a
    # document that has gone stale with no interlock, a document two lanes
    # disagree about, and a document whose shape changed under the parser.
    # All three are rendered rather than hidden.
    paths = laneprovenance.paths_of(data, "go_no_go")
    paths |= {"go_no_go.provenance"}
    data["provenance"] = laneprovenance.table(paths)
    return data


# ---------------------------------------------------------------------------
# The canary send log.
#
# `contacts.view` rather than `operations.view`, and the reason is semantic
# rather than a tightening: every row here carries a real prospect's address,
# so the rows ARE contact rows and the permission that governs seeing a
# contact governs seeing this.
#
# NOT because it is narrower - that was the first claim written here and it
# is false. `workspaces._REVIEWER` grants `contacts.view` and
# `operations.view` TOGETHER, so both are held by reviewer and up and
# neither reaches further. The only role either one excludes is VIEWER, the
# client-facing role, and that exclusion is what matters on this page.
#
# `src.canarysend` holds the reading. This function only scopes it to the
# tenant and supplies the client config the cadence timeline needs.


def canary_send(repo, now=None, approved_cohort=None):
    """What went out, to whom, from which sender, and did anything refuse.

    Read-only and side-effect-free: no file is written, no provider is
    reached, no socket is opened and no credential is read.

    THE CONFIG IS NOT OPTIONAL HERE and it is not a convenience. Without it
    `canarysend` cannot build a cadence timeline, and BLOCKED, HELD and
    PAUSED exist only on a timeline - so a config-less read shows confirmed
    sends and not one refusal. When it cannot be loaded the records come
    back in `blind` and the refusal count is UNKNOWN rather than zero, which
    is why this is a `try` that records the failure instead of one that
    carries on quietly.
    """
    repo.require(ws.CONTACTS_VIEW)

    from .. import canarysend as canary_module

    try:
        config = clients.load(repo.client)
    except Exception:
        # Named by its consequence rather than swallowed: every record then
        # lands in `blind`, the page says refusals are not visible, and the
        # refused count renders UNKNOWN.
        config = None

    data = canary_module.report(
        repo.records(), now=now, config=config, tenant=repo.client,
        approved_cohort=approved_cohort)
    data["client"] = repo.client
    return data


def contested_figures(root=None):
    """Every figure two named authorities give differently, both values kept.

    Read-only and side-effect-side-free: it opens the named authority
    documents for reading and nothing else. No provider, no socket, no
    credential, no git command, and NOTHING is written to
    `_STANDING-RULES.md`, `CONTINUITY.md`, `CONTINUITY-LOG-*` or any
    `DECISIONS-*` document - two of those are under an mtime guard and one
    outranks every brief.

    `root` exists for a test. In the route it is None and the estate root
    comes from the environment.

    THE WORDS TRAVEL WITH THE DATA, the same way the lane board's do, so the
    renderer holds no table of its own and a verdict `src.contested` has not
    named arrives at the page as None rather than being filed into whichever
    bucket came first.
    """
    data = contested.contested(root=root)
    data["recommendations"] = contested.recommendations(data)
    # One worked refusal, computed rather than described: a sum over all
    # three figures, which cannot be computed and names the rows that
    # blocked it. The page prints this to show the refusal is executed and
    # not merely promised - which is this repository's recurring defect.
    data["worked_total"] = contested.total(
        data, [row["key"] for row in data["figures"]])
    data["unrecognised_verdicts"] = sorted(
        {row["verdict"] for row in data["figures"]
         if row["verdict"] not in contested.FIGURE_TEXT})
    data["unrecognised_citation_states"] = sorted(
        {claim["state"] for row in data["figures"] for claim in row["claims"]
         if claim["state"] not in contested.CITATION_TEXT})
    # A recommendation's STANDING is a third vocabulary and gets the same
    # treatment: a standing `src.contested` has not named is reported as
    # unrecognised rather than coloured by whichever map answers first.
    data["unrecognised_standings"] = sorted(
        {rec["standing"] for rec in data["recommendations"]
         if rec["standing"] not in contested.RECOMMENDATION_TEXT})
    return data
