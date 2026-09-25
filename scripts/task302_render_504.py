#!/usr/bin/env python3
"""TASK-302 Stage 1: render campaign 504 from productive.yaml.

Renders every step for every lead through cadence.TEMPLATES and
cadence.template_vars, carrying the template id as a provenance gate.

Usage:
    python scripts/task302_render_504.py [--campaign 504] [--output PATH]

No provider calls. No writes to work/. Reads only.
"""
import argparse
import json
import os
import re
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src import (cadence, campaigns, clients, copylint, packfacts, senders,
                 senderidentity, senderownership, store)


def _load_config(client="productive"):
    return clients.load(client)


def _load_campaign(campaign_id):
    return campaigns.require(str(campaign_id))


def _load_records():
    return store.load()


def _sender_name_for(campaign, contact_key, config):
    """The mailbox owner's display name for this contact, or UNKNOWN."""
    try:
        account = senders.assign(campaign, "email", contact_key)
    except senders.NoSenderAvailable:
        return "UNKNOWN"
    account_id = account.get("id")
    workspace = campaign.get("client") or "productive"
    rows = senderidentity.load()
    acct = senderidentity.account(workspace, "email", account_id, rows)
    if not acct:
        return "UNKNOWN"
    owner_id = senderownership.resolve_owner(acct, rows)
    if not owner_id:
        return "UNKNOWN"
    sender = senderidentity.sender(workspace, owner_id, rows)
    return (sender or {}).get("display_name") or "UNKNOWN"


def _sender_email_for(campaign, contact_key):
    """The email address of the assigned sender, or UNKNOWN."""
    try:
        account = senders.assign(campaign, "email", contact_key)
    except senders.NoSenderAvailable:
        return "UNKNOWN"
    return account.get("external_id") or account.get("id") or "UNKNOWN"


def _pack_fact_gate(rec):
    """Whether this record has a usable pack fact.

    A pack fact is usable when it carries a complete sentence with a verb,
    taken from the site BODY, never nav or menu text.
    """
    pack, _ = packfacts.pack_for(rec)
    facts = pack.get("facts") or []
    if not facts:
        return False, None, facts
    for fact in facts:
        snippet = str(fact.get("snippet") or "").strip()
        if _is_complete_sentence_with_verb(snippet):
            return True, fact, facts
    return False, None, facts


_VERB_INDICATORS = re.compile(
    r"\b(?:is|are|was|were|has|have|had|do|does|did|will|would|could|should|"
    r"can|may|might|shall|must|need|help|offer|provide|serve|specialize|"
    "focus|build|create|deliver|manage|support|work|make|take|bring|get|"
    r"keep|run|start|grow|lead|drive|solve|serve|craft|design|develop)\b",
    re.I)

_NAV_INDICATORS = re.compile(
    r"\b(?:menu|nav|navigation|skip to|main content|order online|footer|"
    r"cookie|sign in|log in|sign up|subscribe|follow us|share|search|"
    r"home|about us|contact|blog|careers|services|products|our team|"
    r"view all|see all|learn more|read more|click here|shop now)\b", re.I)


def _is_complete_sentence_with_verb(snippet):
    """A complete sentence carrying a verb, not nav or menu text."""
    if not snippet or len(snippet) < 20:
        return False
    if _NAV_INDICATORS.search(snippet):
        return False
    if not _VERB_INDICATORS.search(snippet):
        return False
    if "." in snippet[:-1]:
        return True
    if len(snippet.split()) >= 5:
        return True
    return False


def _render_lead(rec, contact, campaign, config, cadence_steps):
    """Render every step for one contact. Returns a dict or None."""
    contact_key = cadence.lint.contact_key(contact) if hasattr(cadence, 'lint') else contact.get("key", "")
    from src import lint as _lint
    contact_key = _lint.contact_key(contact)

    sender_name = _sender_name_for(campaign, contact_key, config)
    sender_email = _sender_email_for(campaign, contact_key)

    pack, unused = packfacts.pack_for(rec)
    has_pack_fact, used_fact, all_facts = _pack_fact_gate(rec)

    rendered_steps = []
    for spec in cadence_steps:
        if spec.get("channel") != "email":
            continue
        step = cadence.expand_step(rec, contact, spec, config,
                                   campaign=campaign)
        if step is None:
            rendered_steps.append({
                "step_key": spec["key"],
                "day": spec["day"],
                "channel": "email",
                "subject": None,
                "body": None,
                "template_id": None,
                "status": "RENDER_FAILED",
            })
            continue
        rendered_steps.append({
            "step_key": spec["key"],
            "day": step.get("day"),
            "channel": step.get("channel", "email"),
            "subject": step.get("subject"),
            "body": step.get("body"),
            "template_id": step.get("template"),
            "generated": step.get("generated", False),
            "status": "rendered",
        })

    company_facts_block = []
    for fact in all_facts:
        company_facts_block.append({
            "source_url": fact.get("source_url"),
            "snippet": fact.get("snippet"),
            "used": (fact == used_fact) if used_fact else False,
        })

    return {
        "record_id": rec.get("id"),
        "contact_key": contact_key,
        "sender_email": sender_email,
        "sender_name": sender_name,
        "lead_email": contact.get("email"),
        "name": contact.get("name"),
        "title": contact.get("title"),
        "company": rec.get("company_facts", {}).get("name") or rec.get("company"),
        "domain": rec.get("domain"),
        "persona": contact.get("persona"),
        "angle": contact.get("angle"),
        "cohort_tag": _cohort_tag(rec, contact),
        "has_pack_fact": has_pack_fact,
        "used_fact_snippet": used_fact.get("snippet") if used_fact else None,
        "steps": rendered_steps,
        "personalisation_block": company_facts_block,
        "status": "rendered" if has_pack_fact else "HELD",
    }


def _cohort_tag(rec, contact):
    parts = []
    persona = contact.get("persona") or "unknown"
    parts.append(persona)
    angle = contact.get("angle")
    if angle:
        parts.append(angle)
    return "-".join(parts)


def render_campaign(campaign_id, config=None):
    """Render every lead in a campaign. Returns the full report."""
    if config is None:
        config = _load_config()
    campaign = _load_campaign(campaign_id)
    recs = _load_records()
    by_id = {r.get("id"): r for r in recs}

    cadence_steps = cadence.steps_for(campaign, config=config)
    record_ids = campaign.get("record_ids") or []

    rendered_leads = []
    held_leads = []
    for rid in record_ids:
        rec = by_id.get(rid)
        if not rec:
            continue
        if rec.get("dropped") or rec.get("paused"):
            continue
        for contact in rec.get("contacts") or []:
            if not contact.get("email") or not contact.get("sendable"):
                continue
            result = _render_lead(rec, contact, campaign, config, cadence_steps)
            if result is None:
                continue
            if result["status"] == "HELD":
                held_leads.append(result)
            else:
                rendered_leads.append(result)

    all_leads = rendered_leads + held_leads

    lint_leads = []
    packs = {}
    for lead in all_leads:
        lead_id = "%s/%s" % (lead["record_id"], lead["contact_key"])
        lint_leads.append({
            "id": lead_id,
            "steps": [{"body": s.get("body")} for s in lead["steps"]
                       if s.get("body")],
        })
        rec = by_id.get(lead["record_id"])
        if rec:
            pack, _ = packfacts.pack_for(rec)
            packs[lead_id] = pack

    lint_report = copylint.check_batch(lint_leads, packs,
                                        steps_expected=len([s for s in cadence_steps if s.get("channel") == "email"]))

    return {
        "campaign_id": campaign_id,
        "total_leads": len(all_leads),
        "rendered": len(rendered_leads),
        "held_no_pack_fact": len(held_leads),
        "leads": all_leads,
        "copylint": lint_report,
        "cadence_steps": [{"key": s["key"], "day": s["day"],
                           "channel": s["channel"]}
                          for s in cadence_steps],
    }


def main():
    parser = argparse.ArgumentParser(description="TASK-302: render campaign")
    parser.add_argument("--campaign", default="504",
                        help="Campaign ID to render")
    parser.add_argument("--output", default=None,
                        help="Output file path (default: stdout)")
    args = parser.parse_args()

    report = render_campaign(args.campaign)

    output = json.dumps(report, indent=2, default=str)
    if args.output:
        os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"Wrote {report['total_leads']} leads to {args.output}")
    else:
        print(output)

    print(f"\n--- Summary ---")
    print(f"Total leads: {report['total_leads']}")
    print(f"Rendered: {report['rendered']}")
    print(f"Held (no pack fact): {report['held_no_pack_fact']}")
    print(f"Copylint refused: {report['copylint']['refused']}")
    print(f"Copylint clean: {report['copylint']['clean']}")
    for line in copylint.report_lines(report["copylint"]):
        print(f"  {line}")


if __name__ == "__main__":
    main()
