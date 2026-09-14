#!/usr/bin/env python3
"""A wholly fictional campaign, built in memory, for looking at.

Five invented companies on .test domains, eleven invented people, and one of
every case the preview has to survive: a strong company signal, a strong
person signal, a hiring signal, a company with no signal at all, and one whose
only public content is irrelevant. Plus a held contact, a dropped record and a
draft that fails lint, because a preview that only ever shows healthy rows is
not much use for deciding anything.

Nothing here touches the queue, the network or a provider. `build()` returns
records in memory; the preview renders them; the process exits.

  python -m src.preview --demo
"""
import datetime

from . import clients, evidence, personalization, store

TODAY = datetime.date.today().isoformat()


def _days_ago(n):
    day = datetime.date.fromisoformat(TODAY) - datetime.timedelta(days=n)
    return day.isoformat()


COMPANIES = (
    # id, company, domain, industry, employees, the story it tells
    ("northwind", "Northwind Studio", "northwind.test", "Design and delivery",
     48, "expansion"),
    ("belmont", "Belmont Partners", "belmont.test", "Management consulting",
     130, "person_post"),
    ("caldera", "Caldera Group", "caldera.test", "Software services",
     85, "hiring"),
    ("driftwood", "Driftwood Agency", "driftwood.test", "Marketing services",
     22, "no_signal"),
    ("evergreen", "Evergreen Works", "evergreen.test", "Engineering services",
     64, "irrelevant"),
)

PEOPLE = {
    "northwind": [("Mara Lindqvist", "Head of Operations", "champion", "ops"),
                  ("Tomas Weber", "Managing Director", "economic_buyer", "founder")],
    "belmont": [("Ana Ferreira", "Finance Director", "champion", "finance"),
                ("Peter Nagy", "CEO", "economic_buyer", "founder")],
    "caldera": [("Ines Kovac", "Operations Manager", "champion", "ops"),
                ("Sven Halvorsen", "Founder", "economic_buyer", "founder")],
    "driftwood": [("Ruth Castellan", "Finance Manager", "champion", "finance"),
                  ("Owen Pryce", "Owner", "economic_buyer", "founder")],
    "evergreen": [("Lena Broz", "Head of Delivery", "champion", "ops"),
                  ("Karl Adeyemi", "CEO", "economic_buyer", "founder"),
                  ("Nils Ahlberg", "Project Manager", "champion", "ops")],
}

# The evidence each company has, and how good it is meant to be.
SIGNALS = {
    "expansion": [
        ("Northwind Studio opened a Vienna office in August, its second "
         "location outside Sweden, and is moving four delivery leads there.",
         "company_announcement", "https://northwind.test/news/vienna", 12,
         evidence.COMPANY, None, False),
    ],
    "person_post": [
        ("Ana Ferreira wrote about reducing month-end reconciliation from nine "
         "days to three across four legal entities.",
         "public_post", "https://belmont.test/insights/month-end", 9,
         evidence.PERSON, "belmont-ana-ferreira", True),
        ("Belmont Partners lists 12 open roles across delivery and finance.",
         "careers_page", "https://belmont.test/careers", 40,
         evidence.COMPANY, None, False),
    ],
    "hiring": [
        ("Caldera Group is hiring a Head of Resource Management to improve "
         "utilisation across an 85-person delivery team.",
         "careers_page", "https://caldera.test/careers/head-of-resourcing", 5,
         evidence.COMPANY, None, False),
    ],
    "no_signal": [],
    "irrelevant": [
        ("Happy holidays from all of us at Evergreen Works! Grateful for a "
         "wonderful year and excited for another great one.",
         "public_post", "https://evergreen.test/blog/holidays", 250,
         evidence.COMPANY, None, False),
    ],
}

BODY = (
    "Hi {first},\n\n"
    "{opening}\n\n"
    "Most {persona_word} we speak to lose the better part of a day every month "
    "reconciling time before they can answer a question anyone actually asked. "
    "The work is rarely the problem; the visibility into it is.\n\n"
    "Is that roughly how it works with you today, or have you already put "
    "something in place for it?\n")

OPENINGS = {
    "expansion": "Noticed you opened a Vienna office and moved four delivery "
                 "leads there. A second location usually means the numbers "
                 "arrive later than the decisions do.",
    "person_post": "You wrote about cutting month-end reconciliation from nine "
                   "days to three across four entities. That is the part most "
                   "teams never get to.",
    "hiring": "Saw you are hiring a Head of Resource Management to improve "
              "utilisation across the delivery team.",
    # THESE TWO ARE THE NO-EVIDENCE CASES AND MUST NOT ASSERT ANYTHING.
    # They read "You run delivery across several teams at once" - a flat
    # statement about how somebody else's company works, on records that by
    # their own names carry no signal at all. `claims` caught it the day the
    # second-person rule was added, which is the whole point of that rule.
    # The rewrite says the same thing about teams in general and asks.
    "no_signal": "Month-end tends to stop being a formality once delivery "
                 "runs across several teams at once. Curious whether that is "
                 "familiar.",
    "irrelevant": "Month-end tends to stop being a formality once delivery "
                  "runs across several teams at once. Curious whether that is "
                  "familiar.",
}

PERSONA_WORDS = {"champion": "operations leads", "economic_buyer": "founders"}


def _contact(record_id, name, title, persona, angle, sendable=True):
    key = f"{record_id}-{name.lower().replace(' ', '-')}"
    email = f"{name.split()[0].lower()}@{record_id}.test"
    # Each answer names the address it is about, exactly as
    # `verification.result` records it for a real provider call. Evidence is
    # counted only for the mailbox it was obtained for, so evidence written
    # without one describes nothing and confirms nothing - which is what the
    # fiction used to do, and it made every demo contact quietly unverified
    # the moment that binding existed.
    return {
        "key": key, "name": name, "title": title, "persona": persona,
        "angle": angle,
        "email": email,
        "linkedin": f"https://www.linkedin.com/in/{key}",
        "sendable": sendable,
        "verification": {
            "state": "verified" if sendable else "held",
            "evidence": [
                {"provider": "contactout", "email": email,
                 "status": "valid" if sendable else "accept_all"},
                {"provider": "deliverable", "email": email,
                 "status": "valid" if sendable else "unknown"},
                {"provider": "reoon", "email": email,
                 "status": "valid" if sendable else "unknown"},
            ]},
    }


def build(config=None):
    """The demo campaign, its records and its config. All fictional."""
    config = config or clients.load("demo")
    policy = personalization.settings(config)
    recs = []

    for rid, company, domain, industry, employees, story in COMPANIES:
        rec = store.new_record(rid, "cold", "demo", company, domain)
        rec["state"] = "drafted"
        rec["hook"] = f"{company} runs delivery across several teams"
        rec["company_facts"] = {
            "name": company, "industry": industry, "employees": employees,
            "offices": ["Stockholm"] if story == "expansion" else [],
            "specialties": ["delivery", "consulting"],
            "email_domain": domain,
        }
        rec["contacts"] = [_contact(rid, *person) for person in PEOPLE[rid]]

        # Caldera's buyer never cleared verification.
        if rid == "caldera":
            rec["contacts"][1] = _contact(rid, *PEOPLE[rid][1], sendable=False)
        # Driftwood was dropped before the campaign was built.
        if rid == "driftwood":
            rec["state"] = "dropped"
            rec["drop_reason"] = "out of geo: flagged and dropped by a human"

        angle_words = []
        for persona in ("champion", "economic_buyer"):
            angles = clients.angles_for(config, persona) or {}
            angle_words.extend(str(v) for v in angles.values())

        rec["research"] = []
        for (fact, source_type, url, age, subject, contact_key, authored) \
                in SIGNALS[story]:
            rec["research"].append(evidence.make(
                fact, url, source_type, "apify", rid, contact_key=contact_key,
                published_at=_days_ago(age), subject=subject,
                persona="operations", angle_words=angle_words,
                authored_by_person=authored, today=TODAY,
                policy=policy["freshness"],
                min_relevance=policy["min_relevance_score"],
                retrieved_at=_days_ago(1), confidence=0.94))
        if story != "no_signal":
            rec["research_state"] = {"company_done": True,
                                     "company_at": _days_ago(1)}
        _fake_provider_trail(rec, story)
        _write_drafts(rec, story, rid)
        recs.append(rec)

    for rec in recs:
        personalization.apply(rec, config)

    campaign = {
        "campaign_id": "demo-preview", "client": "demo",
        "name": "Demo Q3 - fictional", "status": "awaiting_approval",
        "created_at": store.now(), "created_by": "U0DEMOADMIN1",
        "record_ids": [r["id"] for r in recs],
        "daily_volume": {"email": 20, "linkedin": 10},
        "senders": {"email": [{"id": "bison-a", "daily_limit": 25},
                              {"id": "bison-b", "daily_limit": 25}],
                    "linkedin": [{"id": "hr-a", "daily_limit": 15}]},
        "bison_campaign_id": "8100", "heyreach_campaign_id": "6100",
        "approval": None, "fingerprint": None,
        "launch": {"state": "not_launched", "at": None},
        "pause": None, "log": [], "events": [],
    }
    return campaign, recs, config


def _fake_provider_trail(rec, story):
    """Event history so the preview's provider waterfall has something true
    to show. These are ordinary recorded events, not special-cased display."""
    from . import events
    events.record(rec, events.PROVIDER_CALL_COMPLETED, provider="contactout",
                  operation="decision-makers", reason="primary")
    if story in ("no_signal", "irrelevant"):
        events.record(rec, events.PROVIDER_CALL_SKIPPED, provider="apify",
                      operation="research",
                      reason="structured evidence sufficed")
    else:
        events.record(rec, events.SCRAPE_COMPLETED, provider="apify",
                      operation="website-content-crawler", reason=story)
    if story == "hiring":
        events.record(rec, events.PROVIDER_CALL_COMPLETED, provider="aiark",
                      operation="people_search",
                      reason="contactout_no_target_persona")
    else:
        events.record(rec, events.PROVIDER_CALL_SKIPPED, provider="aiark",
                      operation="people_search",
                      reason="ContactOut answered")


def _write_drafts(rec, story, rid):
    """Generated steps, as phase 5 would leave them."""
    from . import cadence
    for contact in rec["contacts"]:
        stored = rec.setdefault("cadence", {}).setdefault(contact["key"], {})
        first = contact["name"].split()[0]
        for step_key in cadence.GENERATED_KEYS:
            body = BODY.format(
                first=first, opening=OPENINGS[story],
                persona_word=PERSONA_WORDS.get(contact["persona"], "leaders"))
            # Evergreen's day-15 draft never got expanded: it fails lint.
            if rid == "evergreen" and step_key == "day15":
                body = ("Hi {{first_name}}, quick one about {{company}} and "
                        "how you run delivery.\n")
            stored[step_key] = {
                "channel": "email", "generated": True,
                "subject": f"quick question about {rec['company']}",
                "body": body,
            }
