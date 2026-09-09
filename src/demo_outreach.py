#!/usr/bin/env python3
"""Five fictional companies, taken through the real engine, rendered to read.

## What this is for

Everything in this repository can be inspected one module at a time, and that
is exactly the problem: nobody deciding whether to turn sending on wants to run
eight CLIs and correlate the output. This assembles one page that answers the
question a person actually has - *what would go out, to whom, saying what, and
why* - for five contacts chosen so that between them they exercise every path
that matters.

## The five scenarios, and why these five

| | Scenario | Proves |
|---|---|---|
| A | full multichannel | the happy path: both providers, both payloads |
| B | LinkedIn only, MX | a security gateway closes email and nothing else |
| C | LinkedIn only, no address | an unverified address closes email and nothing else |
| D | email only | no usable profile closes LinkedIn and nothing else |
| E | reply, then pause | one reply stops *both* channels for the whole company |

B, C and D are three different reasons for a lost channel and one identical
consequence: the contact stays. That is the invariant worth demonstrating on a
page, because "held, not dropped" is easy to say and easy to get wrong.

## What is real here and what is fictional

**Fictional:** the five companies, their people, their addresses, their
LinkedIn URLs, their MX hostnames and their evidence. Every domain is `.test`.
No real person or company appears.

**Real:** everything done *to* them. ICP scoring, segmentation, persona
routing, timezone resolution, MX classification, channel eligibility,
verification, cadence expansion, lint, QA, duplicate detection, cross-channel
coherence and both provider payloads are the production functions, called the
way production calls them. Where this module supplies a value it supplies an
*input* - a fixture - never an answer.

The one substitution is DNS: `_resolver` returns MX hostnames from a table
instead of asking the network, so `mx.classify()` does the real work on real
hostname shapes with no lookup. That is the same substitution the MX tests
make, and it is why this runs offline.

## Safety

Nothing here sends. `push.payloads()` is called for its return value, which is
a dict; no transport is involved and `--live` does not exist on this command.
The reply in scenario E is a local event applied through `replaysim`, which
mutates an in-memory record and never a provider.

  python -m src.demo_outreach
  python -m src.demo_outreach --json
"""
import argparse
import datetime
import json
import os

from . import (cadence, channels, clients, coherence, duplicates, eligibility,
               evidence, events, geo, icp, lint, mx, personalization, push,
               qa, replaysim, schedule, segments, store, verification)

TODAY = "2026-08-26"
CLIENT = "demo"
CAMPAIGN_ID = "demo-outreach"

# The scenario each company exists to demonstrate.
FULL = "A_double_confirmed_multichannel"
SECOND_INVALID = "B_second_verifier_says_invalid"
ESCALATED = "C_escalated_to_reoon"
HALF_CONFIRMED = "D_one_confirmation_only"
MX_BLOCKED = "E_mx_blocked_before_second_verifier"
NO_LINKEDIN = "F_email_only"
REPLY = "G_reply_pauses_both"
SCENARIOS = (FULL, SECOND_INVALID, ESCALATED, HALF_CONFIRMED, MX_BLOCKED,
             NO_LINKEDIN, REPLY)

SCENARIO_TITLES = {
    FULL: "Double confirmed - multichannel",
    SECOND_INVALID: "Second verifier says invalid - LinkedIn only",
    ESCALATED: "Escalated to Reoon - multichannel after escalation",
    HALF_CONFIRMED: "One confirmation only - email held",
    MX_BLOCKED: "MX blocked before the second verifier ran",
    NO_LINKEDIN: "Email only - no usable profile",
    REPLY: "Reply pauses both channels",
}

SCENARIO_ASKS = {
    FULL: "ContactOut and Deliverable both say valid. Two independent "
          "confirmations, so email may go out - and both providers receive "
          "this contact.",
    SECOND_INVALID: "ContactOut said valid and Deliverable said invalid. Two "
                    "providers disagree, so nothing is sent on the optimistic "
                    "answer. Email closes; LinkedIn is untouched.",
    ESCALATED: "Deliverable could not answer, so Reoon was asked and agreed. "
               "The second confirmation came from the escalation, which is "
               "what it is for.",
    HALF_CONFIRMED: "ContactOut says valid and nobody else has been asked. "
                    "One confirmation of two required: email is HELD, not "
                    "blocked, and one more call would settle it.",
    MX_BLOCKED: "The domain sits behind Proofpoint, so the email channel was "
                "closed before any verifier ran. No verification credit was "
                "spent on an address that could never be written to.",
    NO_LINKEDIN: "No usable profile, so HeyReach never sees this contact. "
                 "EmailBison still does.",
    REPLY: "A reply on day 5. Every later step on both channels stops, and "
           "nothing is deleted.",
}


def _days_ago(n):
    day = datetime.date.fromisoformat(TODAY) - datetime.timedelta(days=n)
    return day.isoformat()


# ---------------------------------------------------------------- the data
#
# (scenario, id, company, domain, country, city, employees, industry,
#  specialties, description)

COMPANIES = (
    (FULL, "harborlight", "Harborlight Studio", "harborlight.test",
     "United Kingdom", "London", 82, "Marketing and Advertising",
     ["digital marketing", "content marketing", "performance marketing"],
     "We run delivery teams across a portfolio of retainer and project "
     "clients. Resource planning, utilisation and project margin are how the "
     "studio is run."),

    (SECOND_INVALID, "kingsmere", "Kingsmere Creative", "kingsmere.test",
     "United Kingdom", "Leeds", 61, "Design",
     ["branding", "creative studio", "brand strategy"],
     "A creative studio delivering project work for brands, with producers "
     "and account managers across disciplines and one shared resourcing plan."),

    (ESCALATED, "thornbury", "Thornbury Digital", "thornbury.test",
     "Ireland", "Cork", 74, "Marketing and Advertising",
     ["performance marketing", "paid media", "digital marketing"],
     "Paid media and performance work across a client portfolio, with budget "
     "control and project margin reported per client every month."),

    (MX_BLOCKED, "ironbridge", "Ironbridge Consulting", "ironbridge.test",
     "Ireland", "Dublin", 140, "Management Consulting",
     ["management consulting", "advisory", "business transformation"],
     "Practice areas delivering concurrent client projects, with utilisation "
     "and profitability reported per engagement across our delivery teams."),

    (HALF_CONFIRMED, "saltmarsh", "Saltmarsh Design", "saltmarsh.test",
     "United Kingdom", "Manchester", 54, "Design",
     ["branding", "brand strategy", "creative studio"],
     "A creative studio running project based work for brands, with producers "
     "and account managers across disciplines and a shared resourcing plan."),

    (NO_LINKEDIN, "quarrystone", "Quarrystone Engineering", "quarrystone.test",
     "United Kingdom", "Bristol", 96, "Architecture",
     ["architecture", "structural engineering"],
     "An engineering practice running project based work with budget tracking "
     "and capacity planning across concurrent projects and several teams."),

    (REPLY, "wintergreen", "Wintergreen Partners", "wintergreen.test",
     "Ireland", "Dublin", 67, "Professional Services",
     ["professional services", "advisory"],
     "We deliver client projects across multiple teams on retainer and "
     "project work, tracking billable time and project margin every month."),
)

# (name, title, persona, angle, linkedin)
PEOPLE = {
    "harborlight": ("Mara Lindqvist", "Head of Operations", "champion", "ops",
                    "https://www.linkedin.com/in/mara-lindqvist-demo"),
    "kingsmere": ("Ruth Ellery", "Head of Operations", "champion", "ops",
                  "https://www.linkedin.com/in/ruth-ellery-demo"),
    "thornbury": ("Liam Doyle", "Operations Director", "champion", "ops",
                  "https://www.linkedin.com/in/liam-doyle-demo"),
    "ironbridge": ("Ana Ferreira", "Finance Manager", "champion", "finance",
                   "https://www.linkedin.com/in/ana-ferreira-demo"),
    "saltmarsh": ("Ines Kovac", "Head of Operations", "champion", "ops",
                  "https://www.linkedin.com/in/ines-kovac-demo"),
    "quarrystone": ("Peter Nagy", "Operations Manager", "champion", "ops",
                    None),
    "wintergreen": ("Sven Halvorsen", "Head of Operations", "champion", "ops",
                    "https://www.linkedin.com/in/sven-halvorsen-demo"),
}

# What each verifier said, per scenario. These are the *inputs* - the answers
# providers gave - and never the outcome: `verification.decide` reads them and
# reaches its own conclusion, which is the whole point of putting them here
# rather than writing a state onto the contact.
#
# `None` means that provider was never asked. That is a real and important
# case: it is what "one confirmation of two" looks like, and it is different
# from a provider that was asked and could not answer.
VERIFIER_ANSWERS = {
    FULL: {"contactout": "valid", "deliverable": "valid"},
    SECOND_INVALID: {"contactout": "valid", "deliverable": "invalid"},
    ESCALATED: {"contactout": "valid", "deliverable": "unknown",
                "reoon": "valid"},
    HALF_CONFIRMED: {"contactout": "valid"},
    # Nothing was asked at all: MX closed the channel first.
    MX_BLOCKED: {},
    NO_LINKEDIN: {"contactout": "valid", "deliverable": "valid"},
    REPLY: {"contactout": "valid", "deliverable": "valid"},
}

# MX hostnames per domain. Real hostname shapes so `mx.classify` does real
# work; the lookup itself is what is substituted, not the classification.
MX_HOSTS = {
    "harborlight.test": ["aspmx.l.google.com", "alt1.aspmx.l.google.com"],
    "kingsmere.test": ["aspmx.l.google.com"],
    "thornbury.test": ["mx.zoho.eu"],
    "ironbridge.test": ["mx1.ironbridge.test.pphosted.com"],   # Proofpoint
    "saltmarsh.test": ["saltmarsh-test.mail.protection.outlook.com"],
    "quarrystone.test": ["aspmx.l.google.com"],
    "wintergreen.test": ["mx.zoho.eu"],
}

# (fact, source_type, url, age_days, subject, contact_key, authored_by_person)
SIGNALS = {
    "harborlight": [
        ("Harborlight Studio opened a second office in Manchester and moved "
         "four delivery leads there", "company_announcement",
         "https://harborlight.test/news/manchester", 12, evidence.COMPANY,
         None, False),
        ("Harborlight Studio is hiring a resource manager to own scheduling "
         "across the studio", "careers_page",
         "https://harborlight.test/careers/resource-manager", 6,
         evidence.COMPANY, None, False),
    ],
    "kingsmere": [
        ("Kingsmere Creative is hiring a studio producer to hold concurrent "
         "projects together", "careers_page",
         "https://kingsmere.test/careers/producer", 14, evidence.COMPANY,
         None, False),
    ],
    "thornbury": [
        ("Thornbury Digital published its quarterly note on budget control "
         "across the client portfolio", "company_blog",
         "https://thornbury.test/blog/budget-control", 22, evidence.COMPANY,
         None, False),
    ],
    "ironbridge": [
        ("Ironbridge Consulting reported growth across its practice areas and "
         "named two new partners", "press_release",
         "https://ironbridge.test/press/partners", 30, evidence.COMPANY,
         None, False),
    ],
    "saltmarsh": [
        ("Saltmarsh Design is hiring a studio producer to manage concurrent "
         "projects", "careers_page", "https://saltmarsh.test/careers", 20,
         evidence.COMPANY, None, False),
    ],
    "quarrystone": [
        ("Quarrystone Engineering won a mixed use development and is "
         "resourcing a second project team", "news_article",
         "https://quarrystone.test/news/development", 25, evidence.COMPANY,
         None, False),
    ],
    "wintergreen": [
        ("Wintergreen Partners published a note on billable time across its "
         "retainer clients", "company_blog",
         "https://wintergreen.test/blog/billable", 18, evidence.COMPANY,
         None, False),
    ],
}

# Day-1 and day-15 openings, deliberately different from each other. BUILD-SPEC
# section 7 says day 15 is "a different angle from day 1", and a demo whose two
# generated emails share an opening teaches the reader the wrong thing.
OPENINGS = {
    "harborlight": ("noticed you opened a Manchester office and moved four "
                    "delivery leads across",
                    "you are hiring a resource manager, which usually means "
                    "scheduling has outgrown the spreadsheet"),
    "kingsmere": ("saw you are hiring a studio producer to hold the "
                  "concurrent projects together",
                  "a producer role usually appears when the number of live "
                  "projects passed what one plan can hold"),
    "thornbury": ("read your quarterly note on budget control across the "
                  "client portfolio",
                  "budget control per client is where the month end and the "
                  "resourcing plan usually stop agreeing"),
    "ironbridge": ("saw Ironbridge named two new partners off the back of "
                   "growth across the practice areas",
                   "two new partners usually means utilisation stops being "
                   "one person's mental model"),
    "saltmarsh": ("saw you are hiring a studio producer to hold concurrent "
                  "projects together",
                  "a producer role usually appears when the number of live "
                  "projects passed what one plan can hold"),
    "quarrystone": ("saw Quarrystone won the mixed use development and is "
                    "resourcing a second project team",
                    "a second project team is where budget tracking per "
                    "project usually stops agreeing with the month end"),
    "wintergreen": ("read your note on billable time across the retainer "
                    "clients",
                    "the half nobody writes up is what the same numbers do to "
                    "next quarter's resourcing plan"),
}

PERSONA_WORDS = {"champion": "operations leads", "economic_buyer": "founders"}


def _resolver(domain):
    """MX hostnames from the table above. Never a lookup.

    Stands in for `mx.resolve`, which `for_domain` calls with the domain
    alone. Substituting the lookup and nothing else is the point: everything
    downstream - suffix matching, category, policy - is the real code working
    on real hostname shapes.

    Raises rather than returning [] for an unknown domain, because that is
    what `resolve` does, and "no answer" and "no MX" are different facts.
    """
    hosts = MX_HOSTS.get(mx.normalise_host(domain))
    if hosts is None:
        raise mx.MXError(f"no demo MX table entry for {domain}")
    return list(hosts)


def _body(first, opening, persona_word, company):
    """One email, in the shape the drafting prompt's contract asks for.

    Four parts, per BUILD-SPEC section 8: name the specific thing, one
    concrete new piece of information, one question answerable in a line, no
    calendar link. Written here rather than generated because generating it
    would need a live model, which this command must not use.
    """
    return (
        f"Hi {first}, {opening}.\n\n"
        f"Most {persona_word} we speak to at that point are running "
        f"scheduling in one place, budgets in another and month end in a "
        f"third, and the reconciliation is what eats the week.\n\n"
        f"Productive puts the three in one system, so project margin is "
        f"visible on the Monday rather than two weeks after the month "
        f"closes.\n\n"
        f"Is resourcing across teams something {company} is trying to solve "
        f"this quarter?"
    )


def _contact(rid, scenario, config):
    """One fictional contact, carrying what each verifier actually said.

    The verification block is built by `verification.apply` from
    `VERIFIER_ANSWERS`, never written by hand. That matters here more than
    anywhere else on the page: a demo that asserts its own verdicts proves
    nothing about the resolver, and this one is specifically about the
    resolver. The scenario supplies the provider answers; the engine reaches
    the conclusion.
    """
    name, title, persona, angle, profile = PEOPLE[rid]
    first, last = name.split(" ", 1)
    key = f"{rid}-{first.lower()}-{last.lower().replace(' ', '-')}"
    local = f"{first.lower()}.{last.lower().replace(' ', '')}"
    domain = next(c[3] for c in COMPANIES if c[1] == rid)
    email = f"{local}@{domain}"

    contact = {
        "key": key,
        "name": name,
        "title": title,
        "linkedin": profile,
        "email": email,
        "email_source": "provider",
        "persona": persona,
        "angle": angle,
        "primary": True,
        "selected": True,
    }

    answers = VERIFIER_ANSWERS.get(scenario) or {}
    evidence = []
    for provider in ("contactout", "deliverable", "reoon"):
        status = answers.get(provider)
        if status is None:
            continue                      # never asked, which is its own fact
        fields = {"reason": f"demo fixture: {provider} said {status}",
                  "at": _days_ago(1)}
        if provider == "reoon":
            fields["safe_to_send"] = status == verification.S_VALID
            fields["catch_all"] = False
            fields["score"] = 92 if status == verification.S_VALID else 51
        evidence.append(verification.result(provider, status, email, **fields))

    policy = verification.policy_for(config)
    verification.apply(contact, verification.decide(evidence, policy), evidence)
    return contact


def build(config=None):
    """The five records, the campaign, and the config. All in memory."""
    config = config or clients.load(CLIENT)
    policy = personalization.settings(config)
    recs = []

    for (scenario, rid, company, domain, country, city, employees, industry,
         specialties, description) in COMPANIES:
        rec = store.new_record(rid, "domains", CLIENT, company, domain)
        rec["state"] = "drafted"
        rec["scenario"] = scenario
        rec["batch"] = CAMPAIGN_ID
        rec["hook"] = SIGNALS[rid][0][0]
        rec["company_facts"] = {
            "name": company, "industry": industry,
            "specialties": list(specialties), "description": description,
            "employees": employees, "country": country, "city": city,
            "state": None, "offices": [city], "founded": 2011,
            "email_domain": domain,
        }
        rec["contacts"] = [_contact(rid, scenario, config)]

        angle_words = []
        for persona in ("champion", "economic_buyer"):
            angle_words.extend(str(v) for v in
                               (clients.angles_for(config, persona) or {}).values())

        rec["research"] = [
            evidence.make(fact, url, source_type, "apify", rid,
                          contact_key=contact_key, published_at=_days_ago(age),
                          subject=subject, persona="operations",
                          angle_words=angle_words, authored_by_person=authored,
                          today=TODAY, policy=policy["freshness"],
                          min_relevance=policy["min_relevance_score"],
                          retrieved_at=_days_ago(1), confidence=0.93)
            for (fact, source_type, url, age, subject, contact_key, authored)
            in SIGNALS[rid]
        ]
        rec["research_state"] = {"company_done": True, "company_at": _days_ago(1)}
        _drafts(rec, rid, company)
        recs.append(rec)

    # --- the real engine, in the order production runs it -----------------
    cache = {}
    for rec in recs:
        personalization.apply(rec, config)
        mx.apply_to_record(rec, config, cache=cache, resolver=_resolver,
                           save=False)
        channels.apply_to_record(rec, config)

    campaign = {
        "campaign_id": CAMPAIGN_ID, "client": CLIENT,
        "name": "Demo outreach - fictional", "status": "awaiting_approval",
        "created_at": store.now(), "created_by": "U0DEMOADMIN1",
        "record_ids": [r["id"] for r in recs],
        "daily_volume": {"email": 20, "linkedin": 10},
        "senders": {"email": [{"id": "bison-a", "daily_limit": 25}],
                    "linkedin": [{"id": "hr-a", "daily_limit": 15}]},
        "bison_campaign_id": "8100", "heyreach_campaign_id": "6100",
        "approval": None, "fingerprint": None,
        "launch": {"state": "not_launched", "at": None},
        "pause": None, "log": [], "events": [],
    }
    return campaign, recs, config


def _drafts(rec, rid, company):
    """The two generated emails, as phase 5 would leave them."""
    day1_opening, day15_opening = OPENINGS[rid]
    for contact in rec["contacts"]:
        stored = rec.setdefault("cadence", {}).setdefault(contact["key"], {})
        first = contact["name"].split()[0]
        word = PERSONA_WORDS.get(contact["persona"], "leaders")
        for step_key, opening in (("day1", day1_opening),
                                  ("day15", day15_opening)):
            stored[step_key] = {
                "channel": "email", "generated": True,
                "subject": f"resourcing across teams at {company}"
                           if step_key == "day1"
                           else f"one more thought on {company}",
                "body": _body(first, opening, word, company),
                "angle": contact.get("angle"),
            }


# ---------------------------------------------------------- the approval

def approve_steps(recs, config):
    """A fictional human approves the exact words, per step.

    Not a shortcut: a demo whose steps are all `unapproved` shows an empty
    EmailBison payload and teaches the reader nothing about what the sender
    would receive. This is `approve.approve_record`, the same call the review
    screen makes, on records that exist only in this process.
    """
    from . import approve
    return [approve.approve_record(rec, by="U0DEMOADMIN1", config=config)
            for rec in recs]


def approve_campaign(campaign, recs, config):
    """And then signs the campaign, through the path the Slack button uses.

    Last, because `campaigns._step_material` puts each step's `approved` flag
    and each record's `paused` flag into the fingerprint. Signing before either
    settles leaves a signature describing a campaign that no longer exists -
    which is the check working, not failing, but it makes for a page that
    reports a stale approval it caused itself.

    `demo.yaml` names `U0DEMOADMIN1` as its only approver, so the permission
    check is exercised rather than bypassed.
    """
    from . import orchestrator
    orchestrator.request_approval(campaign, recs, config)
    return orchestrator.decide(
        campaign, "U0DEMOADMIN1", "approve",
        fingerprint=campaign.get("fingerprint"),
        interaction_id="demo-outreach-approval", config=config, recs=recs)


# ------------------------------------------------------------- the reply

REPLY_DAY = 5


def apply_reply(recs, config, campaign=None):
    """Scenario E: one positive reply, through the real pause path.

    `replaysim.simulate` is the production rehearsal: it applies a neutral
    event and reports what every later step becomes. Nothing about a provider
    is touched.
    """
    rec = next(r for r in recs if r.get("scenario") == REPLY)
    contact_key = rec["contacts"][0]["key"]

    # The scenario is "a reply after an early step", so the early steps have to
    # have gone out. Marking them pushed through `push.mark_pushed` is what
    # actually happened to them - it writes the same push id and event a real
    # send would - and it is what makes the before/after readable: two
    # completed steps, a reply, and then everything after it stopping. Without
    # this every step is unsent, the pause blocks all seven, and the page shows
    # a campaign that was paused before it began.
    for step_key, channel in (("day1", "email"), ("day3", "linkedin")):
        push.mark_pushed(rec, contact_key, step_key,
                         push.push_id(rec, contact_key, step_key, channel))
    before = _timeline_snapshot(rec, config, recs)
    result = replaysim.simulate(rec, contact_key, scenario="positive_email",
                                recs=recs, config=config, campaign=campaign)
    after = _timeline_snapshot(rec, config, recs)
    return {"record_id": rec["id"], "contact_key": contact_key,
            "reply_day": REPLY_DAY, "before": before, "after": after,
            "simulation": result}


def _timeline_snapshot(rec, config, recs):
    """Every step and its status, for a before/after comparison."""
    timeline = cadence.build(rec, config, recs=recs)
    out = []
    for contact_key, steps in timeline["contacts"].items():
        for step_key, step in sorted(steps.items(),
                                     key=lambda kv: kv[1].get("day") or 0):
            out.append({"contact_key": contact_key, "step": step_key,
                        "day": step.get("day"), "channel": step.get("channel"),
                        "status": step.get("status"),
                        "why": step.get("blocked_by")})
    return out


# ------------------------------------------------------------ the gather

def gather(config=None):
    """Everything the page renders, as data. No HTML, no files, no network."""
    campaign, recs, config = build(config)
    suppressed = None

    # Order matters, and it is the documented one (WEB-READINESS: "approve
    # drafts" then "campaign approval"). The campaign fingerprint covers each
    # step's `approved` flag and each record's `paused` flag, so both have to
    # settle before the campaign is signed or the signature is stale the
    # moment it is given. Steps are approved first so the before-reply
    # snapshot shows a campaign a human had actually blessed - otherwise the
    # page shows steps stopping that were never going to run anyway.
    approve_steps(recs, config)
    reply = apply_reply(recs, config, campaign)
    approval = approve_campaign(campaign, recs, config)
    paused_set = cadence.paused_domains(recs)

    cards, coherence_reports = [], []
    for rec in recs:
        timeline = cadence.build(rec, config, recs=recs, paused_set=paused_set)
        for contact in rec["contacts"]:
            card = _card(rec, contact, timeline, config, recs, campaign,
                         suppressed)
            cards.append(card)
            coherence_reports.append(card["coherence"])

    ready, skipped = push.collect(recs, day=21, client=CLIENT)
    payloads = push.payloads(
        ready,
        bison_campaign_id=campaign["bison_campaign_id"],
        heyreach_campaign_id=campaign["heyreach_campaign_id"],
        linkedin_account_id=7001)

    return {
        "campaign": campaign,
        "generated_at": store.now(),
        "today": TODAY,
        "cards": cards,
        "totals": _totals(cards),
        "segments": _segments(recs, config),
        "coherence": coherence.summarise(coherence_reports),
        "reply": reply,
        "approval": approval,
        "qa": qa.report(campaign, recs, config),
        "push": {
            "ready": len(ready),
            "skipped": skipped,
            "payloads": payloads,
        },
        "schedule": schedule.for_batch(
            [dict(segments.classify(r, config), domain=r["domain"])
             for r in recs],
            datetime.date.fromisoformat(TODAY) + datetime.timedelta(days=6),
            config),
        # Part of the contract, not decoration. Anything else is a bug.
        "would_send": 0,
    }


def _card(rec, contact, timeline, config, recs, campaign, suppressed):
    """One contact, with every question a reviewer asks answered in order."""
    contact_key = contact["key"]
    segment = segments.classify(rec, config)
    verdict = icp.score(rec, config, segment=segment)
    verdicts = channels.evaluate(rec, contact, config, suppressed)
    steps = (timeline.get("contacts") or {}).get(contact_key) or {}

    paused_at = REPLY_DAY if rec.get("scenario") == REPLY else None
    coherence_report = coherence.for_contact(
        rec, contact_key, timeline, config,
        channel_verdict=verdicts, paused_at=paused_at)

    rendered = []
    for step_key, step in sorted(steps.items(),
                                 key=lambda kv: kv[1].get("day") or 0):
        rendered.append(_step(rec, contact, contact_key, step_key, step,
                              config, recs, campaign))

    stored_mx = mx.stored_decision(contact) or {}
    return {
        "scenario": rec.get("scenario"),
        "scenario_title": SCENARIO_TITLES.get(rec.get("scenario")),
        "scenario_ask": SCENARIO_ASKS.get(rec.get("scenario")),
        "record_id": rec["id"],
        "contact_key": contact_key,
        "company": rec.get("company"),
        "domain": rec.get("domain"),
        "name": contact.get("name"),
        "title": contact.get("title"),
        "persona": contact.get("persona"),
        "angle": contact.get("angle"),

        "company_facts": rec.get("company_facts") or {},
        "icp": {
            "score": verdict.get("icp_score"),
            "status": verdict.get("icp_status"),
            "tier": verdict.get("icp_tier"),
            "confidence": verdict.get("icp_confidence"),
            "reasons": verdict.get("classification_reasons") or [],
            "positive": verdict.get("positive_signals") or [],
            "negative": verdict.get("negative_signals") or [],
            "missing": verdict.get("missing_evidence") or [],
            "contradictions": verdict.get("contradictions") or [],
            "scoring_version": verdict.get("scoring_version"),
        },
        "segment": segment,
        "why_person": _why_person(rec, contact, config),

        "email": {
            "address": contact.get("email"),
            "verdict": contact.get("verdict"),
            "verification": contact.get("verification") or {},
            "sendable": lint.sendable(contact),
            "mx": stored_mx,
            "eligible": verdicts["email_eligible"],
            "reason": verdicts["email_excluded_reason"],
            "reason_text": channels.explain(verdicts["email_excluded_reason"]),
        },
        "linkedin": {
            "url": contact.get("linkedin"),
            "eligible": verdicts["linkedin_eligible"],
            "reason": verdicts["linkedin_excluded_reason"],
            "reason_text": channels.explain(
                verdicts["linkedin_excluded_reason"]),
        },
        "mode": verdicts["mode"],
        "held": verdicts["held"],

        "evidence": _evidence(rec, contact_key, config),
        "personalization": _personalization(rec, contact, config),

        "timeline": rendered,
        "coherence": coherence_report,
        "duplicates": duplicates.for_contact(rec, contact_key, timeline, config),
        "paused": bool(timeline.get("paused")),
        "pause_reason": (timeline.get("paused") or {}).get("reason"),
        "events": [e for e in (rec.get("events") or [])
                   if e.get("contact") in (None, contact_key)],
    }


def _step(rec, contact, contact_key, step_key, step, config, recs, campaign):
    """One cadence step, with every gate's answer attached."""
    channel = step.get("channel")
    text = step.get("note") if channel == "linkedin" else step.get("body")
    # `check_step`, not `check`: it is the single door that dispatches on
    # channel, and `check` is the email half. Linting a LinkedIn note with the
    # email rules reports a missing subject on something that never has one.
    failures = lint.check_step(rec, contact_key, step)
    decision = eligibility.decide(rec, contact, step_key, channel=channel,
                                 campaign=campaign, recs=recs, config=config,
                                 step=step)
    return {
        "step": step_key,
        "day": step.get("day"),
        "channel": channel,
        "provider": "EmailBison" if channel == "email" else "HeyReach",
        "status": step.get("status"),
        "blocked_by": step.get("blocked_by"),
        "generated": bool(step.get("generated")),
        "template": step.get("template"),
        "subject": step.get("subject"),
        "text": text,
        "words": len((text or "").split()),
        "characters": len(text or ""),
        "angle": step.get("angle") or contact.get("angle"),
        "lint": failures,
        "lint_ok": not failures,
        "eligible": bool(decision.eligible),
        "eligibility_verdict": decision["verdict"],
        "eligibility_reasons": decision["reasons"],
        "requires": step.get("requires"),
        "note": step.get("note"),
    }


def _why_person(rec, contact, config):
    """The reason this person and not somebody else at the company."""
    titles = []
    for persona in ("champion", "economic_buyer"):
        block = ((config.get("personas") or {}).get(persona) or {})
        if contact.get("persona") == persona:
            titles = list(block.get("titles") or [])
    return {
        "persona": contact.get("persona"),
        "title": contact.get("title"),
        "matched_titles": titles,
        "why": (f"{contact.get('title')} matches the "
                f"{contact.get('persona')} persona for this client, which "
                f"owns the problem the angle is about"),
        "angle": contact.get("angle"),
        "person_research_available": bool(
            (rec.get("research_state") or {}).get("person_done")),
        "person_research_note": (
            "no authorised provider supplies public professional content for "
            "a named person in this build, so the copy leans on the role and "
            "the company signal"),
    }


def _evidence(rec, contact_key, config):
    """Company and person evidence, kept apart and fully attributed."""
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
        (person if item.get("contact_key") == contact_key
         else company).append(row)
    return {"company": company, "person": person,
            "person_note": ("empty by design: no person-level web research "
                            "provider is authorised in this build")}


def _personalization(rec, contact, config):
    """What the generator was shown, and how specific it managed to be."""
    from . import quality
    assessed = quality.assess(rec, contact, config)
    return {
        "band": assessed.get("band"),
        "components": assessed.get("components"),
        "why": assessed.get("why"),
        "evidence_count": assessed.get("evidence_count"),
        "meets_minimum": assessed.get("meets_minimum"),
        "minimum_band": assessed.get("minimum_band"),
        "held": assessed.get("held"),
        "warnings": assessed.get("warnings") or [],
        "angle": contact.get("angle"),
        "angle_why": (f"the {contact.get('angle')} angle is the one this "
                      f"client maps to the {contact.get('persona')} persona"),
    }


def _totals(cards):
    modes = {}
    for card in cards:
        modes[card["mode"]] = modes.get(card["mode"], 0) + 1
    return {
        "companies": len({c["record_id"] for c in cards}),
        "contacts": len(cards),
        "multichannel": modes.get(channels.MULTICHANNEL, 0),
        "email_only": modes.get(channels.EMAIL_ONLY, 0),
        "linkedin_only": modes.get(channels.LINKEDIN_ONLY, 0),
        "held": sum(1 for c in cards if c["held"]),
        "mx_blocked": sum(1 for c in cards
                          if (c["email"]["reason"] or "").startswith(
                              "mx_protection")),
        "paused": sum(1 for c in cards if c["paused"]),
        "coherence_pass": sum(1 for c in cards
                              if c["coherence"]["verdict"] == "pass"),
        "coherence_failed": sum(1 for c in cards
                                if c["coherence"]["verdict"] == coherence.BLOCK),
        "lint_failures": sum(1 for c in cards for s in c["timeline"]
                             if not s["lint_ok"]),
        "steps": sum(len(c["timeline"]) for c in cards),
    }


def _segments(recs, config):
    out = []
    for rec in recs:
        segment = segments.classify(rec, config)
        schedulable, why = geo.schedulable(segment, config)
        out.append({
            "record_id": rec["id"], "company": rec.get("company"),
            "vertical": segment.get("vertical"),
            "employee_band": segment.get("employee_band"),
            "country": segment.get("country"),
            "region": segment.get("region"),
            "timezone": segment.get("timezone"),
            "schedulable": schedulable, "schedulable_why": why,
        })
    return out


def main(argv=None):
    from . import outreachpage
    p = argparse.ArgumentParser(prog="python -m src.demo_outreach",
                                description=__doc__)
    p.add_argument("--json", action="store_true",
                   help="print the gathered data instead of writing the page")
    p.add_argument("--out", help="where to write the page")
    p.add_argument("--reveal-emails", action="store_true",
                   help="show addresses unmasked (they are fictional)")
    args = p.parse_args(argv)

    result = gather()
    if args.json:
        print(json.dumps(result, indent=2, default=str))
        return 0

    path = args.out or os.path.join(
        os.environ.get("OUT", "out"), "demo-outreach.html")
    outreachpage.write(result, path, reveal=args.reveal_emails)

    totals = result["totals"]
    print(f"\n  {path}\n")
    print(f"  companies        {totals['companies']}")
    print(f"  contacts         {totals['contacts']}")
    print(f"  multichannel     {totals['multichannel']}")
    print(f"  email only       {totals['email_only']}")
    print(f"  linkedin only    {totals['linkedin_only']}")
    print(f"  held             {totals['held']}")
    print(f"  blocked by MX    {totals['mx_blocked']}")
    print(f"  paused           {totals['paused']}")
    print(f"  cadence steps    {totals['steps']}")
    print(f"  lint failures    {totals['lint_failures']}")
    print(f"  coherence pass   {totals['coherence_pass']}"
          f" / blocked {totals['coherence_failed']}")
    print(f"  QA verdict       {result['qa']['verdict']}")
    print(f"  EmailBison       {result['push']['payloads']['emailbison']['count']}"
          f" lead row(s)")
    print(f"  HeyReach         {result['push']['payloads']['heyreach']['count']}"
          f" lead pair(s)")
    print(f"  would send       {result['would_send']}")
    print("\n  Nothing was sent. No provider, model or network was touched.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
