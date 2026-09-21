#!/usr/bin/env python3
"""Reporting, derived from events rather than from counters kept by hand.

Every number here is computed from the record's own event log, so it cannot
drift from what actually happened. Nothing is invented: a metric that needs
data no provider gives us is absent rather than estimated.

  python -m src.report
  python -m src.report --by persona
"""
import argparse
import collections
import json
from collections import Counter, defaultdict

from . import events, store

DIMENSIONS = ("client", "batch", "persona", "angle", "channel")


def batch_of(rec):
    """The batch a record belongs to, whatever shape the field is in.

    `batch` is a mapping with an `id` on records the intake wrote, and a
    BARE STRING on 527 records in the live store - 50 from older runs and
    477 written by tonight's batch builder. This function raised
    AttributeError on every one of them, which took out `report.rows` and
    with it anything that walks the queue: the digest, the funnel and the
    Slack agent's pipeline readback all died on the same line.

    Read, do not convert. A reader that repairs the rows it reads writes
    while somebody is looking at them.
    """
    batch = rec.get("batch")
    if isinstance(batch, str):
        return batch.strip() or "unbatched"
    return (batch or {}).get("id") or "unbatched"


def contact_index(rec):
    return {c.get("key"): c for c in rec.get("contacts") or []}


def rows(recs=None):
    """One row per event, carrying the dimensions it can be sliced by.

    A row is the unit of reporting. Everything else here is a count of rows.
    """
    recs = recs if recs is not None else store.load()
    out = []
    for rec in recs:
        contacts = contact_index(rec)
        for entry in rec.get("events") or []:
            contact = contacts.get(entry.get("contact")) or {}
            out.append({
                "type": entry.get("type"),
                "at": entry.get("at"),
                "client": rec.get("client"),
                "batch": batch_of(rec),
                "record_id": rec.get("id"),
                "lane": rec.get("lane"),
                "contact": entry.get("contact"),
                "persona": contact.get("persona"),
                "angle": contact.get("angle"),
                "channel": entry.get("channel"),
                "provider": entry.get("provider"),
            })
    return out


def count(rows_, by="client", of=None):
    """Counts of one event type, or of everything, along one dimension."""
    if by not in DIMENSIONS + ("lane", "record_id", "type"):
        raise ValueError(f"cannot group by {by}")
    counts = defaultdict(Counter)
    for row in rows_:
        if of and row["type"] != of:
            continue
        counts[row.get(by) or "unknown"][row["type"]] += 1
    return {k: dict(v) for k, v in counts.items()}


def _delivered(counts):
    """Confirmed deliveries, or None when the question does not arise.

    Three states, and the middle one used to be invisible. `or None` made
    a period with a hundred sends and no delivery confirmation render
    exactly like a period with no delivery instrumentation at all - both
    "n/a", under a note promising this reads n/a rather than 0.

    Nothing sent: None, because "0 delivered" of nothing is not a fact
    about deliverability. Something sent and nothing confirmed: 0, which
    is a real and alarming number. Something confirmed: the count.
    """
    if not counts[events.PUSH_MARKED]:
        return None
    return counts[events.EMAIL_DELIVERED]


def funnel(recs=None, config=None):
    """The counts a campaign is actually judged on, and nothing more.

    Everything after `pushed` needs an event this system can only receive, not
    produce, so those numbers are zero until reply ingestion is wired up.

    `verified` is recomputed rather than read off `contact["sendable"]`.
    `verification.is_sendable` says at length why the stored value is the
    wrong thing to read - a hand edit, a resumed run under an older policy
    or a future UI can write that flag without a provider having said
    anything - and this function was reading it while every other caller
    recomputed. It is the default output of `python -m src.report`.
    """
    from . import lint

    recs = recs if recs is not None else store.load()
    all_rows = rows(recs)
    kinds = Counter(row["type"] for row in all_rows)
    states = Counter(rec.get("state") for rec in recs)
    contacts = [c for rec in recs for c in rec.get("contacts") or []]

    return {
        "domains": len(recs),
        "suppressed": kinds.get(events.RECORD_SUPPRESSED, 0),
        "dropped": states.get("dropped", 0),
        "held": states.get("held", 0),
        "contacts_found": len(contacts),
        "verified": sum(1 for c in contacts if lint.sendable(c)),
        "drafts_generated": kinds.get(events.DRAFT_GENERATED, 0),
        "drafts_approved": kinds.get(events.DRAFT_APPROVED, 0),
        "lint_failures": kinds.get(events.LINT_FAILED, 0),
        "push_prepared": kinds.get(events.PUSH_PREPARED, 0),
        "pushed": kinds.get(events.PUSH_MARKED, 0),
        # These only ever come from outside.
        "delivered": kinds.get(events.EMAIL_DELIVERED, 0),
        "bounced": kinds.get(events.EMAIL_BOUNCED, 0),
        "replies": kinds.get(events.REPLY_RECEIVED, 0),
        "connections_accepted": kinds.get(events.LINKEDIN_CONNECTED, 0),
        "companies_paused": kinds.get(events.COMPANY_PAUSED, 0),
    }


def by_dimension(dimension, recs=None):
    """Prepared, pushed, replied and paused, sliced one way."""
    all_rows = rows(recs)
    out = defaultdict(lambda: {"ingested": 0, "prepared": 0, "pushed": 0,
                               "replies": 0, "approved": 0, "paused": 0})
    for row in all_rows:
        key = row.get(dimension) or "unknown"
        if row["type"] == events.BATCH_INGESTED:
            out[key]["ingested"] += 1
        elif row["type"] == events.PUSH_PREPARED:
            out[key]["prepared"] += 1
        elif row["type"] == events.PUSH_MARKED:
            out[key]["pushed"] += 1
        elif row["type"] == events.DRAFT_APPROVED:
            out[key]["approved"] += 1
        elif row["type"] in (events.REPLY_RECEIVED, "email_reply", "linkedin_reply"):
            out[key]["replies"] += 1
        elif row["type"] == events.COMPANY_PAUSED:
            out[key]["paused"] += 1
    return {k: dict(v) for k, v in out.items()}


def by_provider(recs=None):
    """Calls planned, made, skipped and failed, per provider, with the credits
    we estimated. Actual credits are only shown where a provider reports them,
    which today is none of them per call."""
    out = defaultdict(lambda: {"planned": 0, "started": 0, "completed": 0,
                               "failed": 0, "skipped": 0,
                               "estimated_credits": 0, "actual_credits": None})
    for rec in (recs if recs is not None else store.load()):
        for entry in rec.get("events") or []:
            provider = entry.get("provider")
            if not provider:
                continue
            kind = entry.get("type")
            if kind == events.PROVIDER_CALL_PLANNED:
                out[provider]["planned"] += 1
            elif kind == events.PROVIDER_CALL_STARTED:
                out[provider]["started"] += 1
            elif kind == events.PROVIDER_CALL_COMPLETED:
                out[provider]["completed"] += 1
            elif kind == events.PROVIDER_CALL_FAILED:
                out[provider]["failed"] += 1
            elif kind == events.PROVIDER_CALL_SKIPPED:
                out[provider]["skipped"] += 1
            elif kind == events.SCRAPE_STARTED:
                out[provider]["started"] += 1
            elif kind == events.SCRAPE_COMPLETED:
                out[provider]["completed"] += 1
            elif kind == events.SCRAPE_FAILED:
                out[provider]["failed"] += 1
            if entry.get("estimated_cost"):
                out[provider]["estimated_credits"] += int(entry["estimated_cost"])
    return {k: dict(v) for k, v in out.items()}


def by_verifier(recs=None):
    """What each verifier actually said, and what the resolver concluded."""
    per_verifier = defaultdict(Counter)
    finals = Counter()
    disagreements = 0
    for rec in (recs if recs is not None else store.load()):
        for contact in rec.get("contacts") or []:
            block = contact.get("verification") or {}
            if not block:
                continue
            finals[block.get("state") or "unknown"] += 1
            if block.get("sendable"):
                finals["sendable"] += 1
            for entry in block.get("evidence") or []:
                per_verifier[entry.get("provider")][entry.get("status")] += 1
        disagreements += len([e for e in rec.get("events") or []
                              if e.get("type") == events.VERIFICATION_DISAGREEMENT])
    return {"per_verifier": {k: dict(v) for k, v in per_verifier.items()},
            "final": dict(finals), "disagreements": disagreements}


def by_confirmation(recs=None, client=None, config=None):
    """Double verification, counted from what the providers actually said.

    Every number here is recomputed rather than read off `verification.state`:
    a batch enriched under an older policy would otherwise report as fully
    confirmed because that is what its stored states say.

    Provider spend is reported as *operations*, not money. `verification.COSTS`
    is a credit count per call, and a credit is not a price - what a credit
    costs depends on a contract this system has never been told about. Naming
    the operations and refusing to multiply them by an invented rate is the
    honest version of this table.
    """
    from . import verification

    recs = store.load() if recs is None else recs
    if client:
        recs = [r for r in recs if r.get("client") == client]
    policy = verification.policy_for(config)
    required = int(policy.get("required_confirmations") or 1)

    counts = Counter()
    per_provider = defaultdict(Counter)
    operations = Counter()
    with_email = 0

    for rec in recs:
        for contact in rec.get("contacts") or []:
            if not contact.get("email"):
                continue
            with_email += 1
            evidence = verification.all_evidence(contact)
            decision = verification.decide(evidence, policy)
            for entry in evidence:
                per_provider[entry.get("provider")][entry.get("status")] += 1
                operations[entry.get("provider")] += 1
            if decision.get("disagreement"):
                counts["disagreements"] += 1
            if decision["state"] == verification.INVALID:
                counts["invalid"] += 1
            elif decision["state"] == verification.ACCEPT_ALL_UNCLEARED:
                counts["catch_all"] += 1
            elif decision["confirmation_count"] >= decision["required_confirmations"]:
                counts["double_confirmed"] += 1
            else:
                counts["held_awaiting_confirmation"] += 1
            if "reoon" in (decision.get("confirmed_by") or []):
                counts["reoon_escalations"] += 1

    passed = counts.get("double_confirmed", 0)
    return {
        "required_confirmations": required,
        "contacts_with_an_address": with_email,
        "double_confirmed": passed,
        "held_awaiting_confirmation": counts.get("held_awaiting_confirmation", 0),
        "disagreements": counts.get("disagreements", 0),
        "invalid": counts.get("invalid", 0),
        "catch_all": counts.get("catch_all", 0),
        "reoon_escalations": counts.get("reoon_escalations", 0),
        "pass_rate": round(passed / with_email, 3) if with_email else None,
        "per_provider": {k: dict(v) for k, v in sorted(per_provider.items())},
        # Operations, per provider. Deliberately not a currency figure.
        "operations": dict(sorted(operations.items())),
        "credits": {provider: operations[provider]
                    * verification.COSTS.get(provider, 1)
                    for provider in sorted(operations)},
        "cost_note": ("credits are provider units, not money: no per-credit "
                      "price is configured anywhere in this build, and "
                      "inventing one would make the column worse than absent"),
    }


def by_research_source(recs=None):
    """Where the evidence behind a hook or an angle came from."""
    out = Counter()
    for rec in (recs if recs is not None else store.load()):
        facts = rec.get("company_facts") or {}
        if facts:
            out["contactout"] += 1
        for entry in rec.get("research") or []:
            out[entry.get("provider") or "unknown"] += 1
        for entry in rec.get("events") or []:
            if entry.get("type") == events.CONTACT_FOUND and entry.get("source"):
                out[entry["source"]] += 1
    return dict(out)


# ------------------------------------------------------- campaign reporting

def campaign_rows(rows=None):
    """One row per campaign, from the campaign state file."""
    from . import campaigns
    rows = campaigns.load() if rows is None else rows
    out = []
    for campaign in rows:
        given = campaign.get("approval") or {}
        out.append({
            "campaign_id": campaign.get("campaign_id"),
            "client": campaign.get("client"),
            "status": campaign.get("status"),
            "records": len(campaign.get("record_ids") or []),
            "created_at": campaign.get("created_at"),
            "approved_at": given.get("at") if given.get("action") == "approve" else None,
            "approved_by": given.get("by") if given.get("action") == "approve" else None,
            "rejected": given.get("action") == "reject",
            "bison_campaign_id": campaign.get("bison_campaign_id"),
            "heyreach_campaign_id": campaign.get("heyreach_campaign_id"),
            "paused": bool(campaign.get("pause")),
        })
    return out


def approval_latency(rows=None):
    """How long each campaign waited between being offered and being decided.

    Only campaigns that carry both timestamps are counted; the rest are named
    as pending rather than folded into an average that would flatter the number.
    """
    from . import campaigns
    rows = campaigns.load() if rows is None else rows
    measured, pending = [], []
    for campaign in rows:
        requested = next((e.get("at") for e in campaign.get("events") or []
                          if e.get("type") == events.CAMPAIGN_APPROVAL_REQUESTED),
                         None)
        decided = next((e.get("at") for e in campaign.get("events") or []
                        if e.get("type") in (events.CAMPAIGN_APPROVED,
                                             events.CAMPAIGN_REJECTED)), None)
        if requested and decided:
            measured.append({"campaign_id": campaign.get("campaign_id"),
                             "requested_at": requested, "decided_at": decided})
        elif requested:
            pending.append(campaign.get("campaign_id"))
    return {"measured": measured, "awaiting_decision": pending}


def daily_summary(recs=None, campaign_rows_=None, date=None):
    """The numbers behind a daily Slack post.

    Every figure here is counted from events this system recorded itself. A
    metric that would need a provider we are not connected to is absent rather
    than zero, because a zero on a dashboard reads as "it happened and there
    were none", not "we cannot see it".
    """
    recs = store.load() if recs is None else recs
    campaign_rows_ = campaign_rows() if campaign_rows_ is None else campaign_rows_
    counts = collections.Counter()
    for rec in recs:
        for entry in rec.get("events") or []:
            counts[entry.get("type")] += 1

    classified = collections.Counter()
    for rec in recs:
        for entry in rec.get("events") or []:
            if entry.get("type") == events.REPLY_CLASSIFIED:
                classified[entry.get("classification")] += 1

    return {
        "date": date,
        "campaigns_running": sum(1 for c in campaign_rows_
                                 if c["status"] in ("running", "launch_ready")),
        "campaigns_awaiting_approval": sum(1 for c in campaign_rows_
                                           if c["status"] == "awaiting_approval"),
        "contacts_processed": sum(len(r.get("contacts") or []) for r in recs),
        "emails_prepared": counts[events.PUSH_PREPARED],
        "emails_pushed": counts[events.PUSH_MARKED],
        "replies": counts[events.REPLY_RECEIVED],
        "positive_replies": counts[events.POSITIVE_REPLY_DETECTED],
        "reply_breakdown": dict(classified),
        "companies_paused": sum(1 for r in recs if r.get("paused")),
        "held": sum(1 for r in recs if r.get("state") == "held"),
        "dropped": sum(1 for r in recs if r.get("state") == "dropped"),
        "slack_sent": counts[events.SLACK_NOTIFICATION_SENT],
        "slack_failed": counts[events.SLACK_NOTIFICATION_FAILED],
        # Absent on purpose. See unavailable().
        "meetings_booked": None,
        "emails_delivered": _delivered(counts),
        "provider_spend": None,
    }


# ------------------------------------------------------------- the funnel
#
# A stage is counted only where there is evidence for it. The two routinely
# faked elsewhere are MEETING, which nothing here observes, and CONTACTED,
# which needs a real send rather than a prepared payload.

FUNNEL = ("domain", "qualified", "contact_found", "selected", "contactable",
          "approved", "active", "contacted", "replied", "positive", "meeting")

# What each stage is called in front of a person. The client report has said
# these words since it was written; the screen showing the same funnel was
# printing `contact_found`, which is not a phrase and is not even grammar.
FUNNEL_LABEL = {
    "domain": "Domains uploaded",
    "qualified": "ICP qualified",
    "contact_found": "Contacts found",
    "selected": "Contacts selected",
    # Not bare "Contactable". The client report's funnel uses that word for
    # the *email*-reachable count, and this stage counts anybody reachable on
    # either channel - 30 against 17 in the demo estate. One word over two
    # numbers, in two documents the same client reads.
    "contactable": "Contactable on either channel",
    "approved": "Approved to send",
    "active": "In an approved campaign",
    "contacted": "Confirmed sent",
    "replied": "Replied",
    "positive": "Positive reply",
    "meeting": "Meeting",
}


def funnel_for(recs=None, campaign=None, config=None):
    """Counts per funnel stage, with the unobservable ones left at zero."""
    from . import approval, cadence, campaigns, clients, lint, mx, personalization

    recs = store.load() if recs is None else recs
    if campaign is not None:
        ids = set(campaign.get("record_ids") or [])
        recs = [r for r in recs if r.get("id") in ids]
    if config is None and recs:
        try:
            config = clients.load(recs[0].get("client"))
        except Exception:
            config = {}

    stages = {name: 0 for name in FUNNEL}
    stages["domain"] = len(recs)
    approved_campaign = bool(campaign) and campaigns.approval_is_current(
        campaign, recs, config)
    paused_set = cadence.paused_domains(recs)

    for rec in recs:
        if rec.get("state") != "dropped" and not rec.get("drop_reason"):
            stages["qualified"] += 1
        contacts = rec.get("contacts") or []
        stages["contact_found"] += len(contacts)
        stages["selected"] += len(personalization.selected_contacts(rec, config))
        for contact in contacts:
            reachable = lint.sendable(contact) and mx.allows_email(contact,
                                                                   config)[0]
            if reachable or contact.get("linkedin"):
                stages["contactable"] += 1
        timeline = cadence.build(rec, config, paused_set=paused_set,
                                 campaign=campaign).get(
            "contacts") or {}
        for contact_key, steps in timeline.items():
            if any(approval.is_approved(rec, contact_key, key, step)
                   for key, step in steps.items()):
                stages["approved"] += 1
                if approved_campaign:
                    stages["active"] += 1
        for entry in rec.get("events") or []:
            kind = entry.get("type")
            if kind == events.PUSH_MARKED:
                stages["contacted"] += 1
            elif kind == events.REPLY_RECEIVED:
                stages["replied"] += 1
            elif kind == events.POSITIVE_REPLY_DETECTED:
                stages["positive"] += 1
            elif kind == events.MEETING_MARKED:
                stages["meeting"] += 1
    return stages


# ------------------------------------------------------- persona and angle

def _blank_row(extra=None):
    row = {"contacts": 0, "sendable": 0, "touches": 0, "replies": 0,
           "positive": 0, "positive_rate": None}
    row.update(extra or {})
    return row


# Below this many touches a rate is noise dressed as a metric.
MIN_DENOMINATOR = 30


def by_persona(recs=None, config=None):
    """Per persona: contacts, sendable, touches, replies, positives."""
    from . import lint

    recs = store.load() if recs is None else recs
    out = {}
    for rec in recs:
        contacts = {c.get("key"): c for c in rec.get("contacts") or []}
        for contact in contacts.values():
            row = out.setdefault(contact.get("persona") or "unknown",
                                 _blank_row())
            row["contacts"] += 1
            if lint.sendable(contact):
                row["sendable"] += 1
        for entry in rec.get("events") or []:
            contact = contacts.get(entry.get("contact"))
            if not contact:
                continue
            row = out.setdefault(contact.get("persona") or "unknown",
                                 _blank_row())
            kind = entry.get("type")
            if kind == events.PUSH_MARKED:
                row["touches"] += 1
            elif kind == events.REPLY_RECEIVED:
                row["replies"] += 1
            elif kind == events.POSITIVE_REPLY_DETECTED:
                row["positive"] += 1
    for row in out.values():
        if row["touches"] >= MIN_DENOMINATOR:
            row["positive_rate"] = round(row["positive"] / row["touches"], 3)
    return out


def by_angle(recs=None):
    """Per angle: the same, plus how much evidence supported it."""
    recs = store.load() if recs is None else recs
    out = {}
    for rec in recs:
        contacts = {c.get("key"): c for c in rec.get("contacts") or []}
        for contact in contacts.values():
            row = out.setdefault(contact.get("angle") or "unknown",
                                 _blank_row({"with_evidence": 0}))
            row["contacts"] += 1
            decision = contact.get("personalization") or {}
            if decision.get("selected_evidence_ids"):
                row["with_evidence"] += 1
        for entry in rec.get("events") or []:
            contact = contacts.get(entry.get("contact"))
            if not contact:
                continue
            row = out.setdefault(contact.get("angle") or "unknown",
                                 _blank_row({"with_evidence": 0}))
            kind = entry.get("type")
            if kind == events.PUSH_MARKED:
                row["touches"] += 1
            elif kind == events.REPLY_RECEIVED:
                row["replies"] += 1
            elif kind == events.POSITIVE_REPLY_DETECTED:
                row["positive"] += 1
    for row in out.values():
        if row["touches"] >= MIN_DENOMINATOR:
            row["positive_rate"] = round(row["positive"] / row["touches"], 3)
    return out


def for_client(client, recs=None, rows=None, config=None):
    """Everything a client can be told, with the unknowable named as such."""
    from . import clients, lint, mx, personalization

    recs = store.load() if recs is None else recs
    mine = [r for r in recs if r.get("client") == client]
    if config is None:
        try:
            config = clients.load(client)
        except Exception:
            config = {}
    rows = campaign_rows() if rows is None else rows
    theirs = [c for c in rows if c.get("client") == client]

    contacts = [c for r in mine for c in (r.get("contacts") or [])]
    email_only = linkedin_only = multichannel = 0
    for rec in mine:
        for contact in rec.get("contacts") or []:
            has_email = (bool(contact.get("email")) and lint.sendable(contact)
                         and mx.allows_email(contact, config)[0])
            has_linkedin = bool(contact.get("linkedin"))
            if has_email and has_linkedin:
                multichannel += 1
            elif has_email:
                email_only += 1
            elif has_linkedin:
                linkedin_only += 1

    counts = collections.Counter()
    classifications = collections.Counter()
    for rec in mine:
        for entry in rec.get("events") or []:
            counts[entry.get("type")] += 1
            if entry.get("type") == events.REPLY_CLASSIFIED:
                classifications[entry.get("classification")] += 1

    return {
        "client": client,
        "campaigns": len(theirs),
        "funnel": funnel_for(mine, config=config),
        "domains_uploaded": len(mine),
        "domains_qualified": sum(1 for r in mine if r.get("state") != "dropped"),
        "contacts_found": len(contacts),
        "contacts_selected": sum(len(personalization.selected_contacts(r, config))
                                 for r in mine),
        # Two different questions, and they were answered by one number.
        #
        #   contacts_verified        the address survived double verification
        #   contacts_email_reachable ...and email security allows the domain
        #
        # A report saying "contactable by email after double verification and
        # email-security screening" while counting the first is claiming a
        # screen it did not apply, and it overstates the reachable audience
        # by exactly the contacts that screen removed.
        "contacts_verified": sum(1 for c in contacts if lint.sendable(c)),
        "contacts_email_reachable": multichannel + email_only,
        "contacts_mx_blocked": mx.summarise(mine, config)["blocked"],
        "contacts_email_only": email_only,
        "contacts_linkedin_only": linkedin_only,
        "contacts_multichannel": multichannel,
        "emails_planned": counts[events.PUSH_PREPARED],
        "emails_pushed": counts[events.PUSH_MARKED],
        "replies": counts[events.REPLY_RECEIVED],
        "reply_breakdown": dict(classifications),
        "positive_replies": counts[events.POSITIVE_REPLY_DETECTED],
        "companies_paused": sum(1 for r in mine if r.get("paused")),
        "by_persona": by_persona(mine, config),
        "by_angle": by_angle(mine),
        # Named rather than guessed at: nothing here observes a calendar.
        "meetings": counts[events.MEETING_MARKED] or None,
        "emails_delivered": _delivered(counts),
        "provider_spend": None,
    }


# ------------------------------------------------- the qualification surface
#
# Everything below is derived from what qualification stored on the record, so
# it is available before a single person has been looked up - which is the
# whole point of company-first. Three kinds of number live here and they are
# never mixed:
#
#   planned      what the DM plan says we intend to do and spend
#   actual       what has happened, counted from the event log
#   unavailable  named in `unavailable()`, never rendered as zero
#
# A dashboard that shows a planned number beside an actual one without saying
# which is which teaches people to read a forecast as a result.

def _verdict_of(rec):
    return ((rec.get("qualification") or {}).get("verdict") or {})


def _segment_of(rec):
    return ((rec.get("qualification") or {}).get("segment") or {})


def qualification_funnel(recs=None, client=None):
    """Upload to qualified, with the drop between each step.

    The interesting figure is never a single count - it is the fall between
    them, which is the first thing anybody asks about a batch.
    """
    recs = store.load() if recs is None else recs
    if client:
        recs = [r for r in recs if r.get("client") == client]

    qualified = [r for r in recs if r.get("qualification")]
    statuses = collections.Counter(_verdict_of(r).get("icp_status")
                                   for r in qualified)
    tiers = collections.Counter(_verdict_of(r).get("icp_tier")
                                for r in qualified)
    confidence = collections.Counter(_verdict_of(r).get("icp_confidence")
                                     for r in qualified)

    dropped = [r for r in recs if r.get("state") == "dropped"]
    reasons = collections.Counter(r.get("drop_reason") or "unstated"
                                  for r in dropped)

    return {
        "uploaded": len(recs),
        "dropped_at_ingest": len(dropped),
        "drop_reasons": dict(reasons),
        "classified": len(qualified),
        "not_yet_classified": len(recs) - len(qualified),
        "by_status": {k: v for k, v in statuses.items() if k},
        "by_tier": {k: v for k, v in tiers.items() if k},
        "by_confidence": {k: v for k, v in confidence.items() if k},
        "needs_manual_review": sum(
            1 for r in qualified
            if _verdict_of(r).get("icp_status") in ("review", "unknown")),
    }


def qualification_distribution(recs=None, client=None, dimensions=None):
    """Vertical, geography and size, counted from the stored segment.

    `UNKNOWN` is reported rather than dropped: a distribution that silently
    omits what it could not classify reads as complete when it is not.
    """
    recs = store.load() if recs is None else recs
    if client:
        recs = [r for r in recs if r.get("client") == client]
    dimensions = dimensions or ("vertical", "subvertical", "industry",
                                "business_model", "delivery_model",
                                "employee_band", "company_maturity",
                                "country", "region", "timezone")
    out = {}
    for dimension in dimensions:
        counts = collections.Counter()
        for rec in recs:
            segment = _segment_of(rec)
            if not segment:
                continue
            counts[segment.get(dimension) or "UNKNOWN"] += 1
        out[dimension] = dict(sorted(counts.items(),
                                     key=lambda kv: (-kv[1], kv[0])))
    return out


def decision_makers(recs=None, client=None):
    """Planned against found, with the two kept apart.

    `found` counts contacts that actually exist on records. Before enrichment
    runs that is zero, and zero-found-against-2000-planned is the correct
    reading of a batch that has been qualified and not yet enriched.
    """
    recs = store.load() if recs is None else recs
    if client:
        recs = [r for r in recs if r.get("client") == client]

    planned = 0
    companies_planned = 0
    for rec in recs:
        plan = (rec.get("qualification") or {}).get("persona_plan") or {}
        cap = plan.get("max_contacts_to_enrich") or 0
        planned += cap
        if cap:
            companies_planned += 1

    found = sum(len(r.get("contacts") or []) for r in recs)
    return {
        "planned_contacts": planned,
        "planned_dm_searches": companies_planned,
        "companies_with_no_planned_spend": sum(
            1 for r in recs if r.get("qualification")
            and not ((r.get("qualification") or {}).get("persona_plan")
                     or {}).get("max_contacts_to_enrich")),
        "found_contacts": found,
        "enrichment_has_run": bool(found),
    }


def credit_exposure(recs=None, client=None, config=None):
    """Expected, maximum and fallback exposure - and actual, which is None.

    `actual` is not zero and not an estimate copied across. No provider in
    this stack reports per-call spend, so the honest value is absent, and
    `unavailable()` says why.
    """
    from . import dmplan

    recs = store.load() if recs is None else recs
    if client:
        recs = [r for r in recs if r.get("client") == client]

    companies = []
    for rec in recs:
        qualification = rec.get("qualification") or {}
        if not qualification.get("verdict"):
            continue
        companies.append({"record": rec,
                          "persona_plan": qualification.get("persona_plan") or {},
                          "verdict": qualification["verdict"]})
    if not companies:
        return {"expected_credits": 0, "maximum_credits": 0,
                "fallback_exposure": 0, "by_tier": {},
                "actual_credits": None,
                "actual_note": "no provider reports per-call spend"}

    batch = dmplan.for_batch(companies, config)
    return {
        "expected_credits": batch["expected_credits"],
        "maximum_credits": batch["maximum_credits"],
        "fallback_exposure": batch["fallback_exposure"],
        "by_tier": batch["by_tier"],
        "companies_requiring_enrichment": batch["companies_requiring_enrichment"],
        "companies_skipped": batch["companies_skipped"],
        # Deliberately None rather than 0 - see the docstring.
        "actual_credits": None,
        "actual_note": "no provider reports per-call spend",
    }


def campaign_segments(recs=None, client=None):
    """How the batch divides into campaigns, and how big each one is."""
    recs = store.load() if recs is None else recs
    if client:
        recs = [r for r in recs if r.get("client") == client]
    counts = collections.Counter()
    for rec in recs:
        key = (rec.get("qualification") or {}).get("segment_key")
        if key:
            counts[key] += 1
    return {"segments": len(counts),
            "by_segment": dict(sorted(counts.items(),
                                      key=lambda kv: (-kv[1], kv[0])))}


def qualification_report(client=None, recs=None, config=None):
    """The whole pre-enrichment picture, for a dashboard that does not exist yet."""
    recs = store.load() if recs is None else recs
    return {
        "client": client,
        "funnel": qualification_funnel(recs, client),
        "distribution": qualification_distribution(recs, client),
        "decision_makers": decision_makers(recs, client),
        "credits": credit_exposure(recs, client, config),
        "segments": campaign_segments(recs, client),
        "unavailable": unavailable(),
    }


def unavailable():
    """Named so nobody builds a dashboard tile for a number we cannot have."""
    return {
        "meetings_booked": "needs a calendar or CRM integration, or someone "
                           "marking it in Slack",
        "opens": "only if the sending platform reports them, and they are unreliable",
        "actual_credits_per_record": "ContactOut reports usage per account, "
                                     "not per call",
        "decision_makers_found": "planned until enrichment runs; the found "
                                 "count is zero because nobody has been "
                                 "looked up, not because nobody exists",
        "email_and_linkedin_eligibility": "needs contacts, verification and "
                                          "MX classification, all of which "
                                          "run after DM enrichment",
    }


def main(argv=None):
    p = argparse.ArgumentParser(prog="python -m src.report")
    p.add_argument("--by", choices=list(DIMENSIONS) + ["provider", "verifier",
                                                       "research", "persona",
                                                       "angle", "funnel"],
                   default=None)
    p.add_argument("--client")
    p.add_argument("--campaign")
    p.add_argument("--json", action="store_true")
    a = p.parse_args(argv)

    recs = store.load()
    if a.client:
        result = for_client(a.client, recs)
        if a.json:
            print(json.dumps(result, indent=2, sort_keys=True))
            return 0
        print(f"client {result['client']}")
        for key, value in sorted(result.items()):
            if isinstance(value, int) or value is None:
                print(f"  {key:<26} "
                      + ("not observable" if value is None else str(value)))
        print("\n  funnel:")
        for stage in FUNNEL:
            print(f"    {stage:<16} {result['funnel'][stage]}")
        return 0
    if a.campaign:
        from . import campaigns as _campaigns
        campaign = _campaigns.get(a.campaign)
        if campaign is None:
            print(f"REFUSED: no such campaign: {a.campaign}")
            return 2
        stages = funnel_for(recs, campaign)
        if a.json:
            print(json.dumps(stages, indent=2))
            return 0
        for stage in FUNNEL:
            print(f"  {stage:<16} {stages[stage]}")
        return 0
    if a.by == "funnel":
        stages = funnel_for(recs)
        for stage in FUNNEL:
            print(f"  {stage:<16} {stages[stage]}")
        return 0
    if a.by == "persona":
        for name, row in sorted(by_persona(recs).items()):
            print(f"  {name:<18} " + ", ".join(f"{k}={v}" for k, v in row.items()
                                               if v not in (0, None)))
        return 0
    if a.by == "angle":
        for name, row in sorted(by_angle(recs).items()):
            print(f"  {name:<18} " + ", ".join(f"{k}={v}" for k, v in row.items()
                                               if v not in (0, None)))
        return 0
    if a.by == "provider":
        for name, counts in sorted(by_provider(recs).items()):
            print(f"  {name:<14} " + ", ".join(f"{k}={v}" for k, v in counts.items()
                                               if v not in (0, None)))
        return 0
    if a.by == "verifier":
        stats = by_verifier(recs)
        for name, counts in sorted(stats["per_verifier"].items()):
            print(f"  {name:<14} " + ", ".join(f"{k}={v}" for k, v in counts.items()))
        print(f"  {'final':<14} " + ", ".join(f"{k}={v}" for k, v in stats["final"].items()))
        print(f"  {'disagreements':<14} {stats['disagreements']}")
        return 0
    if a.by == "research":
        for name, count in sorted(by_research_source(recs).items()):
            print(f"  {name:<14} {count}")
        return 0
    if a.by:
        print(f"by {a.by}:")
        for key, counts in sorted(by_dimension(a.by, recs).items()):
            detail = ", ".join(f"{k}={v}" for k, v in counts.items() if v)
            print(f"  {str(key):<24} {detail or 'nothing yet'}")
        return 0

    stats = funnel(recs)
    print("campaign")
    for key, value in stats.items():
        print(f"  {key:<22} {value}")
    print("\nnot available from this system:")
    for key, why in unavailable().items():
        print(f"  {key:<22} {why}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
