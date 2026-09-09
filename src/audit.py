#!/usr/bin/env python3
"""Answering "why did this person receive this message?" from stored state.

Every fact needed to answer that already exists — in the record's log, its
event stream, the campaign's log, the verification evidence, the MX decision,
the approval and the push mark. What did not exist is a way to read them as one
ordered story, and a story is what somebody asks for when a prospect writes
back annoyed, or a client asks who signed this off.

Nothing here derives anything. If the trail cannot answer a question, it says
so rather than reconstructing a plausible answer, because an audit trail that
guesses is worse than none.

  python -m src.audit --record acme --contact acme-c0
  python -m src.audit --campaign q3-cold --json
"""
import argparse
import json

from . import campaigns, clients, store

# Where each line came from, so a reader can tell a recorded fact from a
# derived one at a glance.
SOURCES = ("record_log", "record_event", "campaign_log", "campaign_event",
           "verification", "mx", "approval", "push", "research")


def _at(entry):
    return entry.get("at") or ""


def _line(at, source, what, **fields):
    line = {"at": at or "", "source": source, "what": what}
    line.update({k: v for k, v in fields.items() if v not in (None, "", [], {})})
    return line


def for_contact(rec, contact_key, campaign=None, config=None):
    """One person's whole story, oldest first."""
    lines = []
    contact = None
    for candidate in rec.get("contacts") or []:
        if candidate.get("key") == contact_key:
            contact = candidate
            break

    for entry in rec.get("log") or []:
        lines.append(_line(_at(entry), "record_log", entry.get("step") or "log",
                           note=entry.get("note")))

    for entry in rec.get("events") or []:
        if entry.get("contact") not in (None, contact_key):
            continue
        lines.append(_line(_at(entry), "record_event", entry.get("type"),
                           channel=entry.get("channel"), step=entry.get("step"),
                           provider=entry.get("provider"),
                           event_id=entry.get("id")))

    if contact is not None:
        for entry in (contact.get("verification") or {}).get("evidence") or []:
            lines.append(_line(entry.get("at"), "verification",
                               f"{entry.get('provider')} said "
                               f"{entry.get('status')}",
                               email=entry.get("email"),
                               reason=entry.get("reason")))
        decision = contact.get("mx") or {}
        if decision:
            lines.append(_line(decision.get("checked_at"), "mx",
                               decision.get("status"),
                               provider=decision.get("security_provider"),
                               why=decision.get("why")))
        for step_key, step in ((rec.get("cadence") or {}).get(contact_key)
                               or {}).items():
            given = step.get("approval") or {}
            if given:
                lines.append(_line(given.get("at"), "approval",
                                   f"{step_key} {given.get('action')}",
                                   by=given.get("by"),
                                   fingerprint=given.get("fingerprint")))
            if step.get("status") == "pushed":
                lines.append(_line(step.get("pushed_at"), "push",
                                   f"{step_key} pushed",
                                   push_id=step.get("push_id"),
                                   channel=step.get("channel")))
            for evidence_id in step.get("evidence_ids") or []:
                lines.append(_line(step.get("generated_at"), "research",
                                   f"{step_key} used evidence",
                                   evidence_id=evidence_id))

    if campaign is not None:
        for entry in campaign.get("log") or []:
            lines.append(_line(_at(entry), "campaign_log",
                               entry.get("step") or "log",
                               note=entry.get("note"), by=entry.get("by")))
        for entry in campaign.get("events") or []:
            lines.append(_line(_at(entry), "campaign_event", entry.get("type"),
                               by=entry.get("by"), why=entry.get("why")))

    lines.sort(key=lambda line: (line["at"], SOURCES.index(line["source"])
                                 if line["source"] in SOURCES else 99))
    return lines


def why_contacted(rec, contact_key, campaign=None, config=None):
    """The short answer, with the long one attached.

    Deliberately conservative: `answered` is False whenever a link in the chain
    is missing, and the missing link is named. An audit that says "I don't know
    who approved this" is doing its job.
    """
    trail = for_contact(rec, contact_key, campaign, config)
    pushes = [line for line in trail if line["source"] == "push"]
    approvals = [line for line in trail if line["source"] == "approval"]
    evidence = [line for line in trail if line["source"] == "research"]
    verification = [line for line in trail if line["source"] == "verification"]

    missing = []
    if not pushes:
        missing.append("no push was ever recorded for this person")
    if not approvals:
        missing.append("no draft approval is stored")
    if campaign is None:
        missing.append("no campaign was supplied, so nobody signed it off")
    elif not (campaign.get("approval") or {}):
        missing.append("the campaign itself carries no approval")
    if not verification:
        missing.append("no verification evidence is stored for this address")

    return {
        "record_id": rec.get("id"),
        "contact_key": contact_key,
        "answered": not missing,
        "unanswered": missing,
        "pushes": pushes,
        "approved_by": [line.get("by") for line in approvals if line.get("by")],
        "campaign_approved_by": ((campaign or {}).get("approval") or {}).get("by"),
        "campaign_fingerprint": ((campaign or {}).get("approval")
                                 or {}).get("fingerprint"),
        "evidence_used": [line.get("evidence_id") for line in evidence],
        "trail": trail,
    }


def for_campaign(campaign, recs=None):
    """Who did what to this campaign, and when. Decisions only, not traffic."""
    recs = store.load() if recs is None else recs
    lines = []
    for entry in campaign.get("log") or []:
        lines.append(_line(_at(entry), "campaign_log", entry.get("step") or "log",
                           note=entry.get("note"), by=entry.get("by")))
    for entry in campaign.get("events") or []:
        lines.append(_line(_at(entry), "campaign_event", entry.get("type"),
                           by=entry.get("by"), why=entry.get("why"),
                           actor=entry.get("actor")))
    lines.sort(key=lambda line: line["at"])
    return {
        "campaign_id": campaign.get("campaign_id"),
        "status": campaign.get("status"),
        "frozen": campaigns.is_frozen(campaign),
        "approval": campaign.get("approval"),
        "records": len(campaign.get("record_ids") or []),
        "trail": lines,
    }


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--record")
    p.add_argument("--contact")
    p.add_argument("--campaign")
    p.add_argument("--json", action="store_true")
    a = p.parse_args(argv)

    campaign = campaigns.get(a.campaign) if a.campaign else None
    if a.campaign and campaign is None:
        print(f"REFUSED: no such campaign: {a.campaign}")
        return 2

    if a.record:
        rec = store.get(a.record)
        if rec is None:
            print(f"REFUSED: no such record: {a.record}")
            return 2
        if not a.contact:
            print("REFUSED: --record needs --contact")
            return 2
        result = why_contacted(rec, a.contact, campaign)
        if a.json:
            print(json.dumps(result, indent=2, ensure_ascii=False))
            return 0
        print(f"{result['record_id']} / {result['contact_key']}: "
              + ("fully accounted for" if result["answered"]
                 else "NOT fully accounted for"))
        for gap in result["unanswered"]:
            print(f"  unanswered: {gap}")
        for line in result["trail"]:
            print(f"  {line['at']:<26} {line['source']:<15} {line['what']}")
        return 0

    if campaign is not None:
        result = for_campaign(campaign)
        if a.json:
            print(json.dumps(result, indent=2, ensure_ascii=False))
            return 0
        print(f"{result['campaign_id']} ({result['status']}"
              + (", FROZEN" if result["frozen"] else "") + ")")
        for line in result["trail"]:
            print(f"  {line['at']:<26} {line['source']:<15} {line['what']}"
                  + (f" [{line['by']}]" if line.get("by") else ""))
        return 0

    print("REFUSED: pass --record with --contact, or --campaign")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
