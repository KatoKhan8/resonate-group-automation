#!/usr/bin/env python3
"""Everything known about one person and their company, assembled for reading.

Three objects the interface asks for by name — `company_research`,
`person_research` and `personalization_evidence` — are built here as *views*
over the single evidence list on the record rather than as three stored copies.
That is a deliberate choice and worth defending: three copies of the same fact
can disagree, and the moment they do, nobody can say which one the copy was
written from. One store, three questions asked of it.

    company_research           what is true about the company
    person_research            what is true about this person specifically
    personalization_evidence   the subset that actually reached the model

Every fact carries provenance, because a fact without a source is a claim, and
this system does not write claims. Scraped text never appears here as prose; it
has already been turned into structured evidence with a URL and a date by
`src/evidence.py`, and that is the only form it travels in.

  python -m src.dossier --record acme --contact acme-c0
"""
import argparse
import json

from . import clientapproval, clients, evidence, personalization, store

# What we can say about a person from role data alone, before any web research.
# Named because it is the honest floor: knowing somebody is Head of Delivery at
# a 40-person agency is real personalisation, and pretending otherwise is what
# drives people to invent a "recent LinkedIn post".
ROLE_FACTS = ("title", "persona", "seniority", "responsibilities", "tenure")


def _provenance(item):
    """The four things that make a fact checkable. Missing ones stay None."""
    return {
        "source_type": item.get("source_type"),
        "source_url": item.get("source_url"),
        "provider": item.get("provider"),
        "published_at": item.get("published_at"),
        "retrieved_at": item.get("retrieved_at"),
    }


def _fact_row(item):
    return {
        "evidence_id": item.get("evidence_id"),
        "fact": item.get("fact"),
        "subject": item.get("subject"),
        "quality": item.get("quality"),
        "freshness": item.get("freshness_bucket"),
        "relevance": item.get("relevance_score"),
        "provenance": _provenance(item),
    }


def company_research(rec):
    """What is true about the company, with where each fact came from."""
    facts = personalization.stored(rec, subject=evidence.COMPANY)
    structured = rec.get("company_facts") or {}
    return {
        "record_id": rec.get("id"),
        "company": rec.get("company"),
        "domain": rec.get("domain"),
        # Structured provider data, which is the first thing the waterfall
        # asks for and the cheapest thing to trust.
        "structured": {
            "industry": structured.get("industry"),
            "employees": structured.get("employees"),
            "specialties": structured.get("specialties") or [],
            "provider": structured.get("provider") or "contactout",
        },
        "hook": rec.get("hook"),
        "facts": [_fact_row(item) for item in evidence.rank(facts)],
        "fact_count": len(facts),
        "researched": personalization.company_researched(rec),
    }


def person_research(rec, contact):
    """What is true about this person, kept separate from their company.

    `available` is False when nothing person-specific was found, and that is
    recorded rather than smoothed over. A person with no public professional
    content is common, and the correct response is to write from their role and
    their company, not to invent a post they never wrote.
    """
    key = contact.get("key")
    facts = personalization.stored(rec, subject=evidence.PERSON,
                                   contact_key=key)
    role = {
        "name": contact.get("name"),
        "title": contact.get("title"),
        "persona": contact.get("persona"),
        "angle": contact.get("angle"),
        "linkedin": contact.get("linkedin"),
    }
    unavailable = []
    if not facts:
        unavailable.append(
            "no publicly accessible person-specific content was retrieved; "
            "nothing about this person is inferred from that absence")
    return {
        "record_id": rec.get("id"),
        "contact_key": key,
        # Role data is person research too, and it needs no web request.
        "role": role,
        "facts": [_fact_row(item) for item in evidence.rank(facts)],
        "fact_count": len(facts),
        "available": bool(facts),
        "unavailable_because": unavailable,
        "researched": personalization.person_researched(rec, key),
    }


def personalization_evidence(rec, contact, config=None, limit=3):
    """Exactly what the model was given, and why each piece was chosen.

    This is the object that answers "why did the system write this sentence?".
    Everything the model saw is in here; anything not in here, it did not see.
    """
    decision = (contact.get("personalization")
                or personalization.decide(rec, contact, config, limit))
    chosen_ids = list(decision.get("selected_evidence_ids") or [])
    by_id = {item.get("evidence_id"): item
             for item in (rec.get("research") or [])}
    selected = [by_id[eid] for eid in chosen_ids if eid in by_id]
    missing = [eid for eid in chosen_ids if eid not in by_id]

    return {
        "record_id": rec.get("id"),
        "contact_key": contact.get("key"),
        "persona": decision.get("persona") or contact.get("persona"),
        "angle": decision.get("angle") or contact.get("angle"),
        "pain_point": decision.get("primary_signal"),
        "reason_for_contact": decision.get("reason"),
        "quality": decision.get("quality"),
        "level": decision.get("level"),
        "selected": [_fact_row(item) for item in selected],
        "selected_evidence_ids": chosen_ids,
        # A selected id with no matching evidence means the record was edited
        # after selection. Surfaced rather than silently dropped.
        "dangling_evidence_ids": missing,
        "considered": len(rec.get("research") or []),
    }


def _client_approval(rec):
    """The client-approval state for this account, with who, when, source."""
    domain = rec.get("domain") or ""
    client = rec.get("client") or "productive"
    row = clientapproval.state_of(domain, client)
    if not row:
        return {"state": "pending", "who": None, "at": None, "source": None}
    return {"state": row.get("state"), "who": row.get("who"),
            "at": row.get("at"), "source": row.get("source")}


def build(rec, contact, config=None, limit=3):
    """The whole dossier for one contact. Calls nothing; reads stored state."""
    if config is None:
        try:
            config = clients.load(rec.get("client"))
        except Exception:
            config = {}
    return {
        "record_id": rec.get("id"),
        "contact_key": contact.get("key"),
        "client_approval": _client_approval(rec),
        "company_research": company_research(rec),
        "person_research": person_research(rec, contact),
        "personalization_evidence": personalization_evidence(rec, contact,
                                                             config, limit),
    }


def for_record(rec, config=None, selected_only=True, limit=3):
    contacts = (personalization.selected_contacts(rec, config) if selected_only
                else (rec.get("contacts") or []))
    return [build(rec, contact, config, limit) for contact in contacts]


def why_this_person(rec, contact, config=None):
    """The short answer, in the order a human would want it.

    Every line is either a stored fact or an explicit absence. Nothing here is
    generated prose about a person.
    """
    lines = []
    if contact.get("title"):
        lines.append(f"{contact['title']} — the {contact.get('persona') or 'role'} "
                     "we target for this angle")
    person = person_research(rec, contact)
    for row in person["facts"][:3]:
        published = row["provenance"].get("published_at") or "undated"
        lines.append(f"{row['fact']} ({published}, "
                     f"{row['provenance'].get('source_type') or 'unknown source'})")
    if not person["available"]:
        lines.append("no person-specific public content was found, so the copy "
                     "leans on the role and the company")
    return lines


def why_this_company(rec, config=None):
    lines = []
    company = company_research(rec)
    structured = company["structured"]
    if structured.get("industry") or structured.get("employees"):
        lines.append(f"{structured.get('industry') or 'industry unknown'}, "
                     f"{structured.get('employees') or 'size unknown'} people")
    if company.get("hook"):
        lines.append(company["hook"])
    for row in company["facts"][:3]:
        published = row["provenance"].get("published_at") or "undated"
        lines.append(f"{row['fact']} ({published}, "
                     f"{row['provenance'].get('source_type') or 'unknown source'})")
    if not company["facts"] and not company.get("hook"):
        lines.append("no company research was retained: this record has "
                     "nothing specific to lead with")
    return lines


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--record", required=True)
    p.add_argument("--contact")
    p.add_argument("--json", action="store_true")
    a = p.parse_args(argv)

    rec = store.get(a.record)
    if rec is None:
        print(f"REFUSED: no such record: {a.record}")
        return 2
    contacts = [c for c in (rec.get("contacts") or [])
                if not a.contact or c.get("key") == a.contact]
    if not contacts:
        print(f"REFUSED: no such contact on {a.record}: {a.contact}")
        return 2

    for contact in contacts:
        result = build(rec, contact)
        if a.json:
            print(json.dumps(result, indent=2, ensure_ascii=False))
            continue
        print(f"\n{contact.get('name') or '(no name)'} — {contact.get('title') or ''}")
        print("  WHY THIS PERSON")
        for line in why_this_person(rec, contact):
            print(f"    - {line}")
        print("  WHY THIS COMPANY")
        for line in why_this_company(rec):
            print(f"    - {line}")
        chosen = result["personalization_evidence"]
        print(f"  EVIDENCE GIVEN TO THE MODEL "
              f"({len(chosen['selected'])} of {chosen['considered']})")
        for row in chosen["selected"]:
            print(f"    - {row['fact']}")
            print(f"      {row['provenance'].get('source_url') or 'no url'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
