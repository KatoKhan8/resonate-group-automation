#!/usr/bin/env python3
"""The demo Slack estate: which channel each alert *would* go to.

Nothing here posts. `notify.plan` records where a notification is routed and
leaves it at `planned`, and `SLACK_LIVE` is not set in demo mode, so the whole
of this module produces rows in `work/notifications.jsonl` and a set of
rendered messages on a screen. That is the point: the architecture is worth
reading before it is worth wiring, and a reader should be able to see the two
levels stay apart without a workspace ever being told anything.

The estate is deliberately uneven:

  * `productive` and `contactout` each have their own channel, and the two are
    different rooms. A positive reply in one appears in one place only.
  * `demo-client` has **no channel at all**. Its positive reply is recorded
    with status `unconfigured` and goes nowhere. It is not redirected to the
    operations channel and it is not redirected to a sibling workspace, and a
    demo that quietly configured every workspace would hide the one property
    most worth demonstrating.

Every company, person and quotation below is fictional.
"""
from .. import notify
from .. import workspaces as ws

OPS_CHANNEL = "#resonate-outbound-ops"

# workspace slug -> the room its own alerts go to. `demo-client` is absent on
# purpose; see the module docstring.
CHANNELS = {
    "productive": "#client-productive-replies",
    "contactout": "#client-contactout-replies",
}


# Eight scenarios. Five reach the global operations channel, two reach a
# client's own room, one reaches nowhere - and the last of those is a *reply*,
# which is the case a reader is most likely to assume must land somewhere.
SCENARIOS = (
    {
        "key": "positive-reply-productive",
        "title": "A positive reply, in the client's own channel",
        "type": notify.POSITIVE_REPLY,
        "workspace": "productive",
        "fields": {
            "campaign_name": "UK services - operations leaders",
            "company": "Harbourline Studio",
            "contact_name": "Marta Kowalski",
            "contact_role": "Operations Director",
            "channel": "email",
            "email_sender": "Anna Novak",
            "linkedin_sender": "Petar Horvat",
            "reply_excerpt": "This is timely - we are looking at capacity "
                             "planning for Q4. Can you send a couple of times "
                             "next week?",
            "previous_touches": [
                "Day 1 - email - Anna Novak",
                "Day 3 - linkedin - Petar Horvat",
                "Day 6 - email - Anna Novak",
            ],
            "paused": "company and contact paused from further outreach",
        },
        "ids": {"record_id": "demo-harbourline",
                "provider_event_id": "demo-bison-9001"},
        "note": "Two different humans ran this sequence and the alert says "
                "which. The three touches are the ones that were confirmed "
                "sent; a planned fourth would not be in this list.",
    },
    {
        "key": "positive-reply-contactout",
        "title": "The other client's positive reply, in the other room",
        "type": notify.POSITIVE_REPLY,
        "workspace": "contactout",
        "fields": {
            "campaign_name": "DACH SaaS - revenue operations",
            "company": "Kestrel Labs",
            "contact_name": "Jonas Weber",
            "contact_role": "Head of Revenue Operations",
            "channel": "linkedin",
            "email_sender": "Ines Duarte",
            "linkedin_sender": "Tomas Novy",
            "reply_excerpt": "Happy to talk. I am not the buyer but I can "
                             "introduce you to the right person here.",
            "previous_touches": ["Day 1 - email - Ines Duarte",
                                 "Day 4 - linkedin - Tomas Novy"],
            "paused": "company and contact paused from further outreach",
        },
        "ids": {"record_id": "demo-kestrel",
                "provider_event_id": "demo-heyreach-4402"},
        "note": "Same event type, different workspace, different channel. "
                "Neither client's alert can reach the other's room; the "
                "router reads one workspace's mapping and has no fallback.",
    },
    {
        "key": "positive-reply-unconfigured",
        "title": "A positive reply with nowhere to go",
        "type": notify.POSITIVE_REPLY,
        "workspace": "demo-client",
        "fields": {
            "campaign_name": "Nordics - facilities services",
            "company": "Fairhaven Works",
            "contact_name": "Elin Sandberg",
            "contact_role": "COO",
            "channel": "email",
            "email_sender": "Ruth Ellis",
            "linkedin_sender": None,
            "reply_excerpt": "Interested. What does onboarding look like?",
            "previous_touches": ["Day 1 - email - Ruth Ellis"],
            "paused": "company and contact paused from further outreach",
        },
        "ids": {"record_id": "demo-fairhaven",
                "provider_event_id": "demo-bison-9002"},
        "note": "This workspace has no channel mapped. The notification is "
                "recorded as unconfigured and posted nowhere - not to the "
                "operations channel, and not to another client's room.",
    },
    {
        "key": "campaign-approval",
        "title": "A campaign asking to be approved",
        "type": notify.CAMPAIGN_APPROVAL_REQUIRED,
        "workspace": "productive",
        "fields": {
            "campaign": "UK services - operations leaders",
            "segment": "uk-services",
            "personas": "champion, decision_maker",
            "geographies": "United Kingdom",
            "companies": 118,
            "contacts": 214,
            "email_eligible": 171,
            "linkedin_eligible": 96,
            "held": 43,
            "qa": "pass",
            "double_verified": 171,
            "mx_summary": "microsoft 74, google 39, other 58",
            "sender_strategy": "4 inboxes across 2 people, 1 LinkedIn profile",
            "estimated_credits": 214,
            "fingerprint": "8c1f2ad4e6b7",
            "review_url": "/campaigns/uk-services",
        },
        "ids": {"campaign_id": "uk-services", "fingerprint": "8c1f2ad4e6b7"},
        "note": "Operational, so it goes to the global channel even though it "
                "names a workspace. The client is not shown its own credit "
                "exposure or QA verdicts, and the fingerprint travels so that "
                "approving from Slack means approving *this* campaign.",
    },
    {
        "key": "qa-failure",
        "title": "A campaign that failed QA",
        "type": notify.CAMPAIGN_QA_FAILED,
        "workspace": "contactout",
        "fields": {
            "campaign": "DACH SaaS - revenue operations",
            "failures": 6,
            "reasons": "3 drafts referenced a touch that was only planned; "
                       "2 exceeded the LinkedIn note limit; 1 had no "
                       "booking link",
            "action": "regenerate the drafts; the lint rule is not widened",
        },
        "ids": {"campaign_id": "dach-saas"},
        "note": "A client is not shown their own drafts failing lint. The "
                "team fixes it and the client sees the campaign when it is "
                "ready.",
    },
    {
        "key": "provider-health",
        "title": "A provider that stopped answering",
        "type": notify.PROVIDER_HEALTH_ISSUE,
        "workspace": None,
        "fields": {
            "provider": "verification escalation",
            "symptom": "4 consecutive timeouts over 6 minutes",
            "effect": "addresses needing a second opinion are held, not "
                      "guessed; no email is generated for them",
            "action": "check the provider status page before rerunning",
        },
        "ids": {"incident_id": "demo-incident-1"},
        "note": "No workspace at all. This one is about the machine rather "
                "than about anybody's campaign, and it names a supplier - "
                "which is another reason it can only go to the global room.",
    },
    {
        "key": "sender-capacity",
        "title": "A sender running out of room",
        "type": notify.SENDER_CAPACITY_WARNING,
        "workspace": "productive",
        "fields": {
            "sender": "Anna Novak",
            "accounts": "anna07, anna12",
            "planned_today": 96,
            "known_limit": "not known for anna12",
            "effect": "the unknown limit is reported as unknown; nothing is "
                      "scheduled against a guessed number",
        },
        "ids": {"sender_id": "anna"},
        "note": "A missing capacity is a warning, not a default. The alert "
                "says the limit is unknown rather than inventing one.",
    },
    {
        "key": "unmatched-reply",
        "title": "A reply nobody can attribute",
        "type": notify.UNMATCHED_REPLY,
        "workspace": "productive",
        "fields": {
            "provider": "emailbison",
            "provider_event_id": "demo-bison-9107",
            "from_domain": "glenmoor.example",
            "why": "the sending address matches an inbox in this workspace "
                   "but the recipient is not in any campaign",
            "action": "a person decides; nothing is auto-attributed",
        },
        "ids": {"provider_event_id": "demo-bison-9107"},
        "note": "Operational. Guessing which prospect this belongs to would "
                "put a stranger's words into a client's channel.",
    },
)


def install(rows=None):
    """Map the demo channels and plan the eight scenarios.

    Idempotent, because `notify.plan` is: the notification id is derived from
    the event type, the workspace and the identifiers, so installing the demo
    estate twice produces the same eight rows rather than sixteen.
    """
    import os

    os.environ.setdefault(notify.OPS_CHANNEL_VAR, OPS_CHANNEL)
    for slug, channel in CHANNELS.items():
        ws.set_policy(slug, {notify.WORKSPACE_CHANNEL_KEY: channel},
                      actor="demo")
    planned = []
    for scenario in SCENARIOS:
        planned.append(notify.plan(scenario["type"], scenario["workspace"],
                                   fields=scenario["fields"],
                                   ids=scenario["ids"], rows=rows))
    return planned


def scenarios():
    """The scenarios with their routing decision attached, for the screen.

    The decision is asked for rather than remembered: `destination_for` is the
    same function the live path calls, so a demo that showed a different
    answer from the engine would be a demo of nothing.
    """
    listed = []
    for scenario in SCENARIOS:
        decision = notify.destination_for(scenario["type"],
                                          scenario["workspace"])
        row = notify.get(notify.notification_id(
            scenario["type"], scenario["workspace"], **scenario["ids"]))
        listed.append({
            "key": scenario["key"],
            "title": scenario["title"],
            "type": scenario["type"],
            "workspace": scenario["workspace"],
            "destination": decision["destination"],
            "severity": decision["severity"],
            "channel": decision["channel"],
            "status": decision["status"],
            "why": decision["why"],
            "note": scenario["note"],
            "text": notify.render(row) if row else None,
        })
    return listed
