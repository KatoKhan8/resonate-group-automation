#!/usr/bin/env python3
"""The dress rehearsal: everything a campaign would do, assembled for inspection.

This is the module that answers "show me what you are about to send" without
sending it. It gathers the decisions that already exist across the codebase -
which companies were accepted, which contacts were selected and why, what
research was used, what the final copy says, which channels each person is
reachable on, what it would cost - and puts them in one object that a page can
render and a person can read.

It computes nothing new about eligibility. Every verdict here comes from the
module that owns it: `channels` for reachability, `mx` for gateways, `lint` for
copy, `quality` for personalisation, `eligibility` for the send decision,
`waterfall` for spend. A simulator that made its own judgements would be a
second opinion nobody asked for, and the preview would stop matching the run.

Nothing here calls a provider, a model, or DNS. `would_send` is 0 and there is
a test that reads this file to keep it that way.
"""
import argparse
import json
import os

from . import (cadence, campaigns, channels, clients, dossier, duplicates,
               eligibility, enrich, ingest, lint, mx, personalization,
               plan, quality, store, waterfall)

# What the top of the preview page shows, in the order it shows them.
HEADLINE = ("companies", "contacts", "email_eligible", "linkedin_eligible",
            "multichannel", "held", "mx_blocked", "lint_failures",
            "duplicate_bodies", "estimated_credits", "approval_state")


def _records_for(recs, client=None, batch=None, campaign=None):
    """The batch under inspection. Explicit scope beats a silent whole-queue."""
    if campaign is not None:
        ids = set(campaign.get("record_ids") or [])
        return [r for r in recs if r.get("id") in ids]
    out = list(recs)
    if client:
        out = [r for r in out if r.get("client") == client]
    if batch:
        out = [r for r in out if r.get("batch") == batch
               or r.get("batch_id") == batch]
    return out


# ------------------------------------------------------------ the timeline

def timeline_for(rec, contact, config, timeline, duplicate_steps=(),
                 duplicate_reasons=None):
    """Every step in order, including the ones that will not happen.

    A skipped step stays in the list with its reason. Compressing the timeline
    to what will actually go out is how a reviewer ends up approving a cadence
    that silently lost half its touches.
    """
    steps = (timeline.get("contacts") or {}).get(contact.get("key")) or {}
    out = []
    for spec in cadence.STEPS:
        step = steps.get(spec["key"])
        if step is None:
            out.append({"step": spec["key"], "day": spec["day"],
                        "channel": spec["channel"], "status": "not_planned",
                        "reason": "this step is not part of the configured "
                                  "cadence for this contact",
                        "subject": None, "body": None, "note": None})
            continue
        failures = lint.check_step(rec, contact.get("key"), step)
        duplicated = spec["key"] in duplicate_steps
        row = {
            "step": spec["key"],
            "day": step.get("day"),
            "channel": step.get("channel"),
            "status": step.get("status"),
            # Marked on the step itself, not only counted somewhere else on
            # the page: a reviewer reading the timeline has to see it here.
            "duplicate_of": (duplicate_reasons or {}).get(spec["key"]),
            "duplicate": duplicated,
            "generated": bool(step.get("generated")),
            "template": step.get("template"),
            "subject": step.get("subject"),
            "body": step.get("body"),
            "note": step.get("note"),
            "lint": failures,
            "lint_verdict": (lint.classify_linkedin(failures)
                             if step.get("channel") == "linkedin"
                             else lint.classify(failures)),
            "reason": step.get("skipped_reason"),
            "blocked_by": step.get("blocked_by") or [],
        }
        if step.get("status") == "skipped" and not row["reason"]:
            row["reason"] = "; ".join(row["blocked_by"]) or "skipped"
        out.append(row)
    return sorted(out, key=lambda r: (r["day"] or 0, r["step"]))


def contact_card(rec, contact, config, timeline, suppressed=None):
    """One person, as a reviewer needs to see them."""
    verdict = channels.evaluate(rec, contact, config, suppressed)
    findings = duplicates.for_contact(rec, contact.get("key"),
                                      timeline.get("contacts") or {}, config)
    duplicate_steps, duplicate_reasons = set(), {}
    for finding in findings:
        if finding["code"] != duplicates.DUPLICATE_BODY:
            continue
        first, second = finding["steps"]
        duplicate_steps.update(finding["steps"])
        duplicate_reasons[first] = f"the same email as {second}: {finding['why']}"
        duplicate_reasons[second] = f"the same email as {first}: {finding['why']}"
    decision = mx.stored_decision(contact)
    assessment = quality.assess(rec, contact, config)
    research = dossier.build(rec, contact, config)
    return {
        "record_id": rec.get("id"),
        "company": rec.get("company"),
        "domain": rec.get("domain"),
        "contact_key": contact.get("key"),
        "name": contact.get("name"),
        "title": contact.get("title"),
        "persona": contact.get("persona"),
        "angle": contact.get("angle"),
        "email": contact.get("email"),
        "email_verification": (contact.get("verification") or {}).get("state"),
        "mx_provider": decision.get("mx_provider"),
        "mx_classification": decision.get("mx_classification"),
        "mx_records": decision.get("mx_records") or [],
        "email_eligible": verdict["email_eligible"],
        "email_excluded_reason": verdict["email_excluded_reason"],
        "email_excluded_explained": channels.explain(
            verdict["email_excluded_reason"]),
        "linkedin": contact.get("linkedin"),
        "linkedin_eligible": verdict["linkedin_eligible"],
        "linkedin_excluded_reason": verdict["linkedin_excluded_reason"],
        "linkedin_excluded_explained": channels.explain(
            verdict["linkedin_excluded_reason"]),
        "mode": verdict["mode"],
        "held": verdict["held"],
        "why_this_person": dossier.why_this_person(rec, contact, config),
        "why_this_company": dossier.why_this_company(rec, config),
        "company_research": research["company_research"],
        "person_research": research["person_research"],
        "personalization_evidence": research["personalization_evidence"],
        "personalization_quality": assessment,
        "duplicates": findings,
        "duplicate_bodies": sum(1 for f in findings
                                if f["code"] == duplicates.DUPLICATE_BODY),
        "duplicate_subjects": sum(1 for f in findings
                                  if f["code"] == duplicates.DUPLICATE_SUBJECT),
        "timeline": timeline_for(rec, contact, config, timeline,
                                 duplicate_steps, duplicate_reasons),
    }


def company_card(rec, config, paused_set, suppressed):
    accepted = rec.get("state") != "dropped" and not rec.get("drop_reason")
    timeline = cadence.build(rec, config, paused_set=paused_set)
    selected = personalization.selected_contacts(rec, config)
    selected_keys = {c.get("key") for c in selected}
    return {
        "record_id": rec.get("id"),
        "company": rec.get("company"),
        "domain": rec.get("domain"),
        "lane": rec.get("lane"),
        "accepted": accepted,
        "rejected_reason": rec.get("drop_reason"),
        "paused": rec.get("paused") or timeline.get("paused"),
        "contacts_found": len(rec.get("contacts") or []),
        "contacts_selected": len(selected),
        "not_selected": [
            {"contact_key": c.get("key"), "name": c.get("name"),
             "reason": "not in the selected set for this campaign: "
                       "persona, cap or exclusion"}
            for c in (rec.get("contacts") or [])
            if c.get("key") not in selected_keys],
        "waterfall": waterfall.ledger(rec),
        "spend": waterfall.spend(rec),
        "cards": [contact_card(rec, contact, config, timeline, suppressed)
                  for contact in selected],
    }


# ------------------------------------------------------------------ totals

def _approval_state(campaign, recs, config):
    if campaign is None:
        return {"state": "no_campaign",
                "detail": "this is a batch preview; no campaign has been "
                          "created, so nothing has been approved"}
    approval = campaign.get("approval") or {}
    if campaigns.is_frozen(campaign):
        return {"state": "frozen", "detail": (campaign.get("freeze") or {}).get("why")}
    if not approval:
        return {"state": "not_requested",
                "detail": f"status is {campaign.get('status')}"}
    if not campaigns.approval_is_current(campaign, recs, config):
        return {"state": "stale",
                "detail": "the campaign changed after it was approved"}
    return {"state": approval.get("action") or "unknown",
            "detail": f"by {approval.get('by')} at {approval.get('at')}"}


def simulate(recs=None, client=None, batch=None, campaign=None, config=None):
    """The whole rehearsal. Read-only, offline, and it would send nothing."""
    recs = store.load() if recs is None else recs
    if config is None:
        try:
            config = clients.load(client or (campaign or {}).get("client"))
        except Exception:
            config = {}
    mine = _records_for(recs, client, batch, campaign)
    suppressed = ingest.load_suppress()
    paused_set = cadence.paused_domains(recs)

    companies = [company_card(rec, config, paused_set, suppressed)
                 for rec in mine]
    cards = [card for company in companies for card in company["cards"]]

    coverage = channels.summarise(mine, config, suppressed=suppressed)
    bands = quality.distribution(mine, config)
    mx_counts = mx.summarise(mine, config)
    sizing = plan.size(None, mine, config)

    lint_failures = sum(1 for card in cards for row in card["timeline"]
                        if row.get("lint"))
    duplicate_bodies = sum(card["duplicate_bodies"] for card in cards)
    duplicate_subjects = sum(card["duplicate_subjects"] for card in cards)
    email_steps = sum(1 for card in cards for row in card["timeline"]
                      if row.get("channel") == "email"
                      and row.get("status") not in ("not_planned",))
    linkedin_steps = sum(1 for card in cards for row in card["timeline"]
                         if row.get("channel") == "linkedin"
                         and row.get("status") not in ("not_planned",))
    skipped = sum(1 for card in cards for row in card["timeline"]
                  if row.get("status") in ("skipped", "blocked"))

    credits = _credit_estimate(mine, config)
    research_use = _research_use(mine)

    return {
        "client": client or (campaign or {}).get("client"),
        "batch": batch,
        "campaign_id": (campaign or {}).get("campaign_id"),
        "generated_at": store.now(),
        # Always zero. This module has no path to a provider.
        "would_send": 0,
        "headline": {
            "companies": len(mine),
            "companies_accepted": sum(1 for c in companies if c["accepted"]),
            "companies_rejected": sum(1 for c in companies
                                      if not c["accepted"]),
            "contacts": coverage["contacts"],
            "email_eligible": coverage["email_eligible"],
            "linkedin_eligible": coverage["linkedin_eligible"],
            "multichannel": coverage[channels.MULTICHANNEL],
            "held": coverage["held"],
            "mx_blocked": mx_counts["blocked"],
            "lint_failures": lint_failures,
            "duplicate_bodies": duplicate_bodies,
            "duplicate_subjects": duplicate_subjects,
            "estimated_credits": credits["expected"],
            "approval_state": _approval_state(campaign, recs, config)["state"],
        },
        "coverage": coverage,
        "personalization": bands,
        "mx": mx_counts,
        "sizing": sizing,
        "credits": credits,
        "research_providers": research_use,
        "steps": {"email": email_steps, "linkedin": linkedin_steps,
                  "skipped_or_blocked": skipped},
        "approval": _approval_state(campaign, recs, config),
        "companies": companies,
    }


def _credit_estimate(recs, config):
    """What running this would cost, from the same table enrichment uses."""
    expected = maximum = 0
    for rec in recs:
        ops = enrich.plan(rec, config) or []
        exposure = enrich.exposure(ops)
        expected += exposure["expected"]
        maximum += exposure["maximum"]
    spent = sum(waterfall.spend(rec)["expected"] for rec in recs)
    return {
        "expected": expected,
        "maximum": maximum,
        "already_spent": spent,
        "unit": "contactout credits and equivalents; Apify bills separately in "
                "compute units and is not counted here",
    }


def _research_use(recs):
    """Which providers actually supplied evidence, counted from the evidence."""
    counts = {}
    for rec in recs:
        for item in rec.get("research") or []:
            provider = item.get("provider") or "unknown"
            counts[provider] = counts.get(provider, 0) + 1
    return counts


# ----------------------------------------------------------------- QA view

def qa_metrics(result):
    """The pre-approval numbers, with nothing hidden behind an average."""
    cards = [card for company in result["companies"] for card in company["cards"]]
    total_steps = 0
    clean_steps = 0
    for card in cards:
        for row in card["timeline"]:
            if row.get("status") == "not_planned":
                continue
            total_steps += 1
            if not row.get("lint"):
                clean_steps += 1
    verified = sum(1 for card in cards
                   if card["email_verification"] == "verified")
    ambiguous = sum(1 for card in cards
                    if card["linkedin_excluded_reason"] in
                    (channels.IDENTITY_UNCERTAIN, channels.DUPLICATE))
    research_failed = sum(1 for company in result["companies"]
                          for card in company["cards"]
                          if not card["company_research"]["facts"]
                          and not card["person_research"]["facts"])
    contacts = len(cards) or None
    duplicate_bodies = sum(card["duplicate_bodies"] for card in cards)
    duplicate_subjects = sum(card["duplicate_subjects"] for card in cards)
    return {
        "lint_pass_rate": (round(clean_steps / total_steps, 3)
                           if total_steps else None),
        "lint_failures": total_steps - clean_steps,
        # Blocking. Each step passes lint; the sequence is the defect.
        "duplicate_email_bodies": duplicate_bodies,
        # Reported, not blocking: the body is what arrives.
        "duplicate_email_subjects": duplicate_subjects,
        "contacts_with_duplicate_copy": sum(1 for card in cards
                                            if card["duplicate_bodies"]),
        "verified_email_rate": (round(verified / contacts, 3)
                                if contacts else None),
        "mx_exclusion_rate": (round(result["mx"]["blocked"] / contacts, 3)
                              if contacts else None),
        "linkedin_coverage": result["coverage"]["linkedin_coverage"],
        "multichannel_coverage": result["coverage"]["multichannel_coverage"],
        "personalization_bands": result["personalization"]["bands"],
        "personalization_held": result["personalization"]["held"],
        "held_count": result["coverage"]["held"],
        "research_failure_count": research_failed,
        "identity_ambiguity_count": ambiguous,
        "steps_considered": total_steps,
    }


def slack_preview(result, campaign, config):
    """The approval message that would be posted, rendered and not sent."""
    from .providers import slack

    headline = result["headline"]
    qa = qa_metrics(result)
    summary = {
        "client": result["client"],
        "name": (campaign or {}).get("name"),
        "domains": headline["companies"],
        "contacts": headline["contacts"],
        "sendable": headline["email_eligible"],
        "held": headline["held"],
        "dropped": headline["companies_rejected"],
        "suppressed": 0,
        "email_senders": [s.get("id") for s in
                          ((campaign or {}).get("senders") or {}).get("email")
                          or []],
        "linkedin_senders": [s.get("id") for s in
                             ((campaign or {}).get("senders") or {}).get("linkedin")
                             or []],
        "daily_volume": (campaign or {}).get("daily_volume") or {},
        "cadence": (config or {}).get("cadence"),
        "estimate": result["credits"],
        "fingerprint": ((campaign or {}).get("approval") or {}).get("fingerprint"),
    }
    payload = slack.campaign_approval_request(campaign or {}, summary, config)
    # The extra lines this preview adds over the existing approval message.
    payload = dict(payload)
    payload["preview_lines"] = [
        f"email eligible {headline['email_eligible']} · "
        f"linkedin eligible {headline['linkedin_eligible']} · "
        f"multichannel {headline['multichannel']}",
        f"held {headline['held']} · MX excluded {headline['mx_blocked']} · "
        f"lint failures {headline['lint_failures']}",
        (f"BLOCKED: {headline['duplicate_bodies']} pair(s) of email steps send "
         f"the same message twice"
         if headline["duplicate_bodies"] else
         "no two email steps send the same message")
        + (f" · {result['headline']['duplicate_subjects']} shared subject "
           "line(s)" if result["headline"]["duplicate_subjects"] else ""),
        f"personalisation "
        + " · ".join(f"{band} {count}" for band, count
                     in result["personalization"]["bands"].items()),
        f"estimated credits {result['credits']['expected']} "
        f"(max {result['credits']['maximum']})",
    ]
    payload["qa"] = qa
    payload["delivered"] = False
    payload["why_not_delivered"] = ("this is a preview; nothing is posted to "
                                    "Slack by the simulator")
    return payload


def reporting_preview(result):
    """The client report as it would read today, with pre-send metrics at zero.

    Zero and None mean different things here and the difference is kept:
    zero is "this has not happened yet", None is "this system cannot see it".
    """
    headline = result["headline"]
    return {
        "client": result["client"],
        "campaign_state": result["approval"]["state"],
        "companies_researched": sum(1 for c in result["companies"]
                                    if c["waterfall"] or c["cards"]),
        "companies_uploaded": headline["companies"],
        "companies_accepted": headline["companies_accepted"],
        "contacts_found": result["sizing"]["contacts_found"],
        "contacts_selected": result["sizing"]["contacts_selected"],
        "personas": _persona_counts(result),
        "email_coverage": result["coverage"]["email_coverage"],
        "linkedin_coverage": result["coverage"]["linkedin_coverage"],
        "mx_exclusions": headline["mx_blocked"],
        "emails_generated": result["steps"]["email"],
        "linkedin_steps_generated": result["steps"]["linkedin"],
        # Not started rather than invented. Nothing has been sent.
        "emails_sent": 0,
        "linkedin_actions": 0,
        "replies": 0,
        "positive_replies": 0,
        # Not observable at all, which is a different statement from zero.
        "meetings": None,
        "provider_usage": result["research_providers"],
        "cost": result["credits"],
    }


def _persona_counts(result):
    counts = {}
    for company in result["companies"]:
        for card in company["cards"]:
            persona = card.get("persona") or "unknown"
            counts[persona] = counts.get(persona, 0) + 1
    return counts


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--client")
    p.add_argument("--batch")
    p.add_argument("--campaign")
    p.add_argument("--json", action="store_true")
    a = p.parse_args(argv)

    campaign = campaigns.get(a.campaign) if a.campaign else None
    if a.campaign and campaign is None:
        print(f"REFUSED: no such campaign: {a.campaign}")
        return 2
    result = simulate(client=a.client, batch=a.batch, campaign=campaign)
    if a.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0
    for name in HEADLINE:
        print(f"  {name:<20} {result['headline'][name]}")
    print(f"  would send           {result['would_send']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
