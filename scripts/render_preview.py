#!/usr/bin/env python3
"""Render what the person actually receives.

TASK-045.  The operator: "A template passing lint is not sufficient.  I want
us to be able to inspect what the PERSON ACTUALLY RECEIVES."

Every gate in this system checks a template or a fragment.  Nothing has ever
assembled the whole thing and shown a human the message.  The "hi jacob"
defect survived a green test suite, a sequence readback and a field-for-field
comparison - and would have been obvious in one rendered preview.

This script renders from the SAME code path that builds the provider payload:
`cadence.expand_step` is called by `cadence.build`, which is called by
`push.collect`, whose output feeds `push.payloads` - the exact request bodies
the sender would post.  A preview built by a second renderer previews a
message nobody sends.

TASK-046 extends this with the HeyReach pipeline.  A HeyReach campaign does
NOT go through `cadence.expand_step`.  It goes through:

    heyreachfactory.merge_sequence_copy   builds a graph of MERGE FIELDS
                                          {connection_note}, {connected_1}, ...
    heyreachfactory.custom_fields_for     each lead's own approved words
    heyreach.build_lead_pairs             those words onto the wire as
                                          customUserFields
    HeyReach                              substitutes them into the graph

So the preview renders BOTH paths: the template path (TASK-045) and the merge
field path (TASK-046), selected by the argument.

Usage:
    python scripts/render_preview.py [campaign_name_or_id]

A fixture name (balanced, li_heavy, no_linkedin, missing_variable, heyreach,
heyreach_planted_name) renders through the template path or the HeyReach path.
A canonical campaign id (productive-linkedin-production-v1) loads from work/
and renders through the HeyReach path.

ZERO network, ZERO credentials.  No provider call.  No write to work/**.
Every name, company and address is invented.
"""
import argparse
import os
import re
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src import cadence, cadencelibrary, clients, lint
from src import heyreachfactory
from src.providers import heyreach


# ----------------------------------------------------------------- fixtures
#
# Every name, company, domain and address is invented.  Nothing here is a
# real person or a real company.

def _fixture_config(cadence_name="productive_balanced_v1"):
    """A minimal client config with one persona, two angles."""
    return {
        "cadence": cadence_name,
        "personas": {
            "champion": {
                "cap_per_domain": 2,
                "angles": {
                    "visibility": ("how the numbers behind the work become "
                                   "visible before the month ends"),
                    "margin": ("how project margin stops disappearing between "
                               "the spreadsheet and the actual work"),
                },
            },
        },
        "angle_labels": {
            "visibility": "real-time visibility",
            "margin": "margin protection",
        },
        "tone": {"linkedin": "casual", "email": "professional"},
    }


def _fixture_rec_li_heavy():
    """A record for the LinkedIn-heavy cadence.

    Generated steps carry pre-filled body/note so the preview can show them.
    In production these come from the model; here they are invented copy.
    """
    return {
        "id": "fixture-li-heavy-001",
        "client": "fixture_client",
        "company": "Meridian Logistics Group",
        "domain": "meridianlg.example.com",
        "lane": "cold",
        "state": "active",
        "company_facts": {
            "name": "Meridian Logistics Group",
            "employees": 85,
            "industry": "logistics",
            "revenue": "$12M",
            "offices": ["Rotterdam", "Antwerp"],
        },
        "contacts": [
            {"key": "elena-vasquez",
             "name": "Elena Vasquez",
             "title": "Head of Operations",
             "email": "elena.vasquez@meridianlg.example.com",
             "linkedin": "https://linkedin.example.com/in/elena-vasquez",
             "persona": "champion",
             "angle": "visibility",
             "verdict": "icp_match"},
        ],
        "events": [],
        "cadence": {
            "elena-vasquez": {
                "li1": {"note": ("hi Elena, i work with logistics teams on "
                                 "real-time visibility. curious how Meridian "
                                 "Logistics Group handles it at your size. "
                                 "happy to connect."),
                        "channel": "linkedin", "generated": True},
                "em1": {"subject": "your visibility gap at Meridian Logistics Group",
                        "body": ("Elena, I noticed Meridian Logistics Group "
                                 "runs multi-site operations across Rotterdam "
                                 "and Antwerp.\n\n"
                                 "The pattern I see in logistics teams your "
                                 "size is that utilisation numbers arrive too "
                                 "late to act on. The work itself is rarely "
                                 "the problem - the visibility into it is.\n\n"
                                 "Is that roughly how it works at Meridian "
                                 "Logistics Group today?"),
                        "channel": "email", "generated": True},
                "li2": {"note": ("thanks for connecting Elena. no pitch here. "
                                 "if real-time visibility is on your list "
                                 "this quarter i am happy to share what "
                                 "similar teams did."),
                        "channel": "linkedin", "generated": True},
                "em2": {"subject": "a different angle on the numbers",
                        "body": ("Elena, a different thought for Meridian "
                                 "Logistics Group.\n\n"
                                 "Most logistics teams your size lose margin "
                                 "between the spreadsheet and the actual "
                                 "work. The finance view and the operations "
                                 "view are two separate spreadsheets "
                                 "maintained by two separate people.\n\n"
                                 "Would it be useful to see what that looked "
                                 "like for a team your size?"),
                        "channel": "email", "generated": True},
            },
        },
    }


def _fixture_rec_balanced():
    """A record for the balanced cadence.

    Template steps only - no generated content needed.  This is the fixture
    where the raw-template -> variables -> final-rendered chain is fully
    visible.
    """
    return {
        "id": "fixture-balanced-001",
        "client": "fixture_client",
        "company": "Northbridge Consulting",
        "domain": "northbridge-consulting.example.com",
        "lane": "cold",
        "state": "active",
        "company_facts": {
            "name": "Northbridge Consulting",
            "employees": 42,
            "industry": "management consulting",
            "revenue": "$6M",
            "offices": ["London"],
        },
        "contacts": [
            {"key": "jacob-hartley",
             "name": "Jacob Hartley",
             "title": "Delivery Director",
             "email": "j.hartley@northbridge-consulting.example.com",
             "linkedin": "https://linkedin.example.com/in/jacob-hartley",
             "persona": "champion",
             "angle": "visibility",
             "verdict": "icp_match"},
        ],
        "events": [],
        "cadence": {},
    }


def _fixture_rec_no_linkedin():
    """A record with no LinkedIn URL - must be reported, not silently skipped."""
    return {
        "id": "fixture-no-linkedin-001",
        "client": "fixture_client",
        "company": "Ashford Digital",
        "domain": "ashford-digital.example.com",
        "lane": "cold",
        "state": "active",
        "company_facts": {
            "name": "Ashford Digital",
            "employees": 18,
            "industry": "digital marketing",
            "revenue": "$2M",
        },
        "contacts": [
            {"key": "priya-sharma",
             "name": "Priya Sharma",
             "title": "Founder",
             "email": "priya@ashford-digital.example.com",
             "linkedin": None,
             "persona": "champion",
             "angle": "margin",
             "verdict": "icp_match"},
        ],
        "events": [],
        "cadence": {},
    }


def _fixture_rec_missing_variable():
    """A record where company_facts.name is missing - tests fallback behaviour.

    The company field is a domain-shaped string, which company_name() refuses.
    This is the class of defect the preview must surface.
    """
    return {
        "id": "fixture-missing-var-001",
        "client": "fixture_client",
        "company": "keystone-partners.example.com",
        "domain": "keystone-partners.example.com",
        "lane": "cold",
        "state": "active",
        "company_facts": {},
        "contacts": [
            {"key": "sam-okafor",
             "name": "Sam Okafor",
             "title": "COO",
             "email": "sam@keystone-partners.example.com",
             "linkedin": "https://linkedin.example.com/in/sam-okafor",
             "persona": "champion",
             "angle": "visibility",
             "verdict": "icp_match"},
        ],
        "events": [],
        "cadence": {},
    }


# ----------------------------------------- TASK-046: HeyReach pipeline fixtures
#
# The HeyReach campaign does NOT go through cadence.expand_step.  It goes
# through merge_sequence_copy (graph of variables) + custom_fields_for (per-
# lead words) + build_lead_pairs (onto the wire as customUserFields).
#
# Every name, company and domain is invented.

def _fixture_config_heyreach():
    """A client config with linkedin_sequence.fallbacks.

    The fallbacks are what HeyReach sends when a per-lead variable cannot be
    filled.  They assert nothing about the reader - they are true of any
    agency and are the only copy in this system written to be true of a
    stranger.
    """
    return {
        "cadence": "productive_li_heavy_v1",
        "personas": {
            "champion": {
                "cap_per_domain": 2,
                "angles": {
                    "visibility": ("how the numbers behind the work become "
                                   "visible before the month ends"),
                    "margin": ("how project margin stops disappearing between "
                               "the spreadsheet and the actual work"),
                },
            },
        },
        "angle_labels": {
            "visibility": "real-time visibility",
            "margin": "margin protection",
        },
        "tone": {"linkedin": "casual", "email": "professional"},
        "linkedin_sequence": {
            "fallbacks": {
                "connection_note": ("hi, i work with agencies on project "
                                    "profitability and thought it would be "
                                    "good to connect."),
                "connected_1": ("how do you currently get visibility on "
                                "whether a project is making money while it "
                                "is still running?"),
                "connected_2": ("most agencies i speak to find that out at "
                                "the end of a project rather than during it. "
                                "is that how it works for you?"),
                "connected_3": ("we built productive so budgets, time "
                                "tracking and resourcing talk to each other. "
                                "worth a look?"),
                "connected_4": ("happy to leave it here if the timing is "
                                "wrong. is there someone else who owns "
                                "this?"),
                "message_2": ("how do you currently get visibility on "
                              "whether a project is making money while it "
                              "is still running?"),
                "message_3": ("most agencies i speak to find that out at "
                              "the end of a project rather than during it. "
                              "is that how it works for you?"),
                "message_4": ("we built productive so budgets, time "
                              "tracking and resourcing talk to each other. "
                              "worth a look?"),
            },
        },
    }


def _fixture_rec_heyreach():
    """A record with approved LinkedIn copy for the HeyReach pipeline.

    The cadence block carries approved, generated LinkedIn notes for li1..li5.
    These are the words that travel per lead in customUserFields.
    """
    return {
        "id": "fixture-heyreach-001",
        "client": "fixture_client",
        "company": "Cascadia Design Collective",
        "domain": "cascadia-dc.example.com",
        "lane": "cold",
        "state": "active",
        "company_facts": {
            "name": "Cascadia Design Collective",
            "employees": 34,
            "industry": "design agency",
            "revenue": "$4.5M",
            "offices": ["Portland", "Seattle"],
        },
        "contacts": [
            {"key": "maia-torres",
             "name": "Maia Torres",
             "title": "Studio Manager",
             "email": "maia@cascadia-dc.example.com",
             "linkedin": "https://linkedin.example.com/in/maia-torres",
             "persona": "champion",
             "angle": "resource_management",
             "verdict": "icp_match"},
        ],
        "events": [],
        "cadence": {
            "maia-torres": {
                "li1": {"note": ("hi Maia, i work with design studios on "
                                 "who is booked on what next week. curious "
                                 "how Cascadia Design Collective handles "
                                 "resourcing at your size. happy to "
                                 "connect."),
                        "channel": "linkedin",
                        "linkedin_action": "connect",
                        "generated": True,
                        "approval": {"fingerprint": "fixture-approve-li1"}},
                "li2": {"note": ("thanks for connecting Maia. no pitch "
                                 "here. if resourcing visibility is on "
                                 "your list this quarter i am happy to "
                                 "share what similar studios did."),
                        "channel": "linkedin",
                        "linkedin_action": "message",
                        "generated": True,
                        "approval": {"fingerprint": "fixture-approve-li2"}},
                "li3": {"note": ("most studios i speak to find out who is "
                                 "double-booked when a person quits rather "
                                 "than before. is that how it works at "
                                 "Cascadia?"),
                        "channel": "linkedin",
                        "linkedin_action": "message",
                        "generated": True,
                        "approval": {"fingerprint": "fixture-approve-li3"}},
                "li4": {"note": ("we built productive so the schedule, "
                                 "the budget and the resourcing plan talk "
                                 "to each other. worth a look?"),
                        "channel": "linkedin",
                        "linkedin_action": "message",
                        "generated": True,
                        "approval": {"fingerprint": "fixture-approve-li4"}},
                "li5": {"note": ("happy to leave it here if the timing "
                                 "is wrong Maia. is there someone else "
                                 "who owns resourcing at Cascadia Design "
                                 "Collective?"),
                        "channel": "linkedin",
                        "linkedin_action": "message",
                        "generated": True,
                        "approval": {"fingerprint": "fixture-approve-li5"}},
            },
        },
    }


def _fixture_rec_heyreach_second():
    """A second lead for the HeyReach fixture - shows per-lead variation."""
    return {
        "id": "fixture-heyreach-002",
        "client": "fixture_client",
        "company": "Bastion Digital",
        "domain": "bastion-dg.example.com",
        "lane": "cold",
        "state": "active",
        "company_facts": {
            "name": "Bastion Digital",
            "employees": 58,
            "industry": "digital agency",
            "revenue": "$9M",
            "offices": ["Manchester"],
        },
        "contacts": [
            {"key": "declan-reilly",
             "name": "Declan Reilly",
             "title": "Head of Operations",
             "email": "declan@bastion-dg.example.com",
             "linkedin": "https://linkedin.example.com/in/declan-reilly",
             "persona": "champion",
             "angle": "operations",
             "verdict": "icp_match"},
        ],
        "events": [],
        "cadence": {
            "declan-reilly": {
                "li1": {"note": ("hi Declan, i work with agency operations "
                                 "leads on utilisation visibility. curious "
                                 "how Bastion Digital tracks it across "
                                 "projects. happy to connect."),
                        "channel": "linkedin",
                        "linkedin_action": "connect",
                        "generated": True,
                        "approval": {"fingerprint": "fixture-approve-li1"}},
                "li2": {"note": ("thanks for connecting Declan. no pitch. "
                                 "if utilisation visibility is on your "
                                 "radar this quarter, happy to share what "
                                 "similar teams did."),
                        "channel": "linkedin",
                        "linkedin_action": "message",
                        "generated": True,
                        "approval": {"fingerprint": "fixture-approve-li2"}},
                "li3": {"note": ("most agency ops leads i speak to find "
                                 "out about margin erosion at the end of "
                                 "a project rather than during it. is "
                                 "that how it works at Bastion?"),
                        "channel": "linkedin",
                        "linkedin_action": "message",
                        "generated": True,
                        "approval": {"fingerprint": "fixture-approve-li3"}},
                "li4": {"note": ("we built productive so budgets, time "
                                 "tracking and resourcing talk to each "
                                 "other. worth a look?"),
                        "channel": "linkedin",
                        "linkedin_action": "message",
                        "generated": True,
                        "approval": {"fingerprint": "fixture-approve-li4"}},
                "li5": {"note": ("happy to leave it here if the timing "
                                 "is wrong Declan. is there someone else "
                                 "who owns this at Bastion Digital?"),
                        "channel": "linkedin",
                        "linkedin_action": "message",
                        "generated": True,
                        "approval": {"fingerprint": "fixture-approve-li5"}},
            },
        },
    }


def _fixture_rec_heyreach_planted_name():
    """A record where one lead's words contain ANOTHER lead's name.

    This is the hi-jacob defect class: the graph was built from one contact's
    approved words, so every lead received "hi Jacob" even if they were not
    Jacob.  In the merge-field pipeline, this means one lead's custom fields
    contain another lead's name.

    Two contacts in one record: Rachel's words contain "Declan" (the other
    contact's first name), which the preview must flag at the top.
    """
    return {
        "id": "fixture-heyreach-planted-001",
        "client": "fixture_client",
        "company": "Keystone Partners",
        "domain": "keystone-p.example.com",
        "lane": "cold",
        "state": "active",
        "company_facts": {
            "name": "Keystone Partners",
            "employees": 22,
            "industry": "consulting",
            "revenue": "$3M",
            "offices": ["Dublin"],
        },
        "contacts": [
            {"key": "rachel-okafor",
             "name": "Rachel Okafor",
             "title": "Delivery Director",
             "email": "rachel@keystone-p.example.com",
             "linkedin": "https://linkedin.example.com/in/rachel-okafor",
             "persona": "champion",
             "angle": "delivery",
             "verdict": "icp_match"},
            {"key": "declan-murphy",
             "name": "Declan Murphy",
             "title": "Project Manager",
             "email": "declan.m@keystone-p.example.com",
             "linkedin": "https://linkedin.example.com/in/declan-murphy",
             "persona": "champion",
             "angle": "delivery",
             "verdict": "icp_match"},
        ],
        "events": [],
        "cadence": {
            "rachel-okafor": {
                # Rachel's words contain "Declan" - the OTHER contact's name.
                # This is the hi-jacob defect: her copy was used to build
                # the graph, and Declan would receive "hi Declan" from
                # Rachel's words while Rachel would receive them too.
                "li1": {"note": ("hi Declan, i work with consulting teams "
                                 "on budget burn visibility. curious how "
                                 "Keystone Partners handles it. happy to "
                                 "connect."),
                        "channel": "linkedin",
                        "linkedin_action": "connect",
                        "generated": True,
                        "approval": {"fingerprint": "fixture-approve-li1"}},
                "li2": {"note": ("thanks for connecting Declan. no pitch. "
                                 "if budget visibility is on your list, "
                                 "happy to share what similar teams did."),
                        "channel": "linkedin",
                        "linkedin_action": "message",
                        "generated": True,
                        "approval": {"fingerprint": "fixture-approve-li2"}},
                "li3": {"note": ("most consulting leads i speak to find "
                                 "out about scope creep at month end. is "
                                 "that how it works at Keystone Partners?"),
                        "channel": "linkedin",
                        "linkedin_action": "message",
                        "generated": True,
                        "approval": {"fingerprint": "fixture-approve-li3"}},
                "li4": {"note": ("we built productive so budgets, time "
                                 "tracking and resourcing talk to each "
                                 "other. worth a look?"),
                        "channel": "linkedin",
                        "linkedin_action": "message",
                        "generated": True,
                        "approval": {"fingerprint": "fixture-approve-li4"}},
                "li5": {"note": ("happy to leave it here if the timing "
                                 "is wrong. is there someone else who "
                                 "owns this?"),
                        "channel": "linkedin",
                        "linkedin_action": "message",
                        "generated": True,
                        "approval": {"fingerprint": "fixture-approve-li5"}},
            },
            "declan-murphy": {
                "li1": {"note": ("hi Declan, i work with consulting teams "
                                 "on scope creep and thought it would be "
                                 "good to connect."),
                        "channel": "linkedin",
                        "linkedin_action": "connect",
                        "generated": True,
                        "approval": {"fingerprint": "fixture-approve-li1"}},
                "li2": {"note": ("thanks for connecting. no pitch. "
                                 "if scope visibility is on your list, "
                                 "happy to share what similar teams did."),
                        "channel": "linkedin",
                        "linkedin_action": "message",
                        "generated": True,
                        "approval": {"fingerprint": "fixture-approve-li2"}},
                "li3": {"note": ("most consulting leads i speak to find "
                                 "out about scope creep at month end. is "
                                 "that how it works for you?"),
                        "channel": "linkedin",
                        "linkedin_action": "message",
                        "generated": True,
                        "approval": {"fingerprint": "fixture-approve-li3"}},
                "li4": {"note": ("we built productive so budgets, time "
                                 "tracking and resourcing talk to each "
                                 "other. worth a look?"),
                        "channel": "linkedin",
                        "linkedin_action": "message",
                        "generated": True,
                        "approval": {"fingerprint": "fixture-approve-li4"}},
                "li5": {"note": ("happy to leave it here if the timing "
                                 "is wrong. is there someone else who "
                                 "owns this?"),
                        "channel": "linkedin",
                        "linkedin_action": "message",
                        "generated": True,
                        "approval": {"fingerprint": "fixture-approve-li5"}},
            },
        },
    }


def _fixture_rec_heyreach_missing_field():
    """A record where li3 has no approval - tests missing variable reporting.

    The missing approval means custom_fields_for reports li3's roles as
    missing, and the preview shows which steps would fire the fallback.
    """
    return {
        "id": "fixture-heyreach-missing-001",
        "client": "fixture_client",
        "company": "Ashford Digital",
        "domain": "ashford-d.example.com",
        "lane": "cold",
        "state": "active",
        "company_facts": {
            "name": "Ashford Digital",
            "employees": 18,
            "industry": "digital marketing",
            "revenue": "$2M",
        },
        "contacts": [
            {"key": "priya-sharma",
             "name": "Priya Sharma",
             "title": "Founder",
             "email": "priya@ashford-d.example.com",
             "linkedin": "https://linkedin.example.com/in/priya-sharma",
             "persona": "champion",
             "angle": "margin",
             "verdict": "icp_match"},
        ],
        "events": [],
        "cadence": {
            "priya-sharma": {
                "li1": {"note": ("hi Priya, i work with agency founders "
                                 "on margin visibility. curious how "
                                 "Ashford Digital handles it. happy to "
                                 "connect."),
                        "channel": "linkedin",
                        "linkedin_action": "connect",
                        "generated": True,
                        "approval": {"fingerprint": "fixture-approve-li1"}},
                "li2": {"note": ("thanks for connecting Priya. no pitch. "
                                 "if margin visibility is on your list, "
                                 "happy to share what similar teams did."),
                        "channel": "linkedin",
                        "linkedin_action": "message",
                        "generated": True,
                        "approval": {"fingerprint": "fixture-approve-li2"}},
                # li3 deliberately missing approval - tests the missing path
                "li3": {"note": ("this note has no approval so it should "
                                 "not reach the wire"),
                        "channel": "linkedin",
                        "linkedin_action": "message",
                        "generated": True},
                "li4": {"note": ("we built productive so budgets, time "
                                 "tracking and resourcing talk to each "
                                 "other. worth a look?"),
                        "channel": "linkedin",
                        "linkedin_action": "message",
                        "generated": True,
                        "approval": {"fingerprint": "fixture-approve-li4"}},
                "li5": {"note": ("happy to leave it here if the timing "
                                 "is wrong. is there someone else who "
                                 "owns this?"),
                        "channel": "linkedin",
                        "linkedin_action": "message",
                        "generated": True,
                        "approval": {"fingerprint": "fixture-approve-li5"}},
            },
        },
    }


# ----------------------------------------- TASK-046: HeyReach rendering engine

# The two branches a prospect walks, stated as the roles they visit.
# Already connected: connected_1 -> connected_2 -> connected_3 -> connected_4
# Not connected (cold, after acceptance): connection_note -> message_2 ->
#                                          message_3 -> message_4
ALREADY_CONNECTED_BRANCH = ("connected_1", "connected_2",
                            "connected_3", "connected_4")
NOT_CONNECTED_BRANCH = ("connection_note", "message_2",
                        "message_3", "message_4")

# Which cadence step fills which role.  From heyreachfactory.COPY_MAPPING.
_ROLE_TO_STEP_KEY = {}
for _step_key, _mapping in heyreachfactory.COPY_MAPPING.items():
    _roles = _mapping["role"]
    if isinstance(_roles, str):
        _roles = (_roles,)
    for _role in _roles:
        _ROLE_TO_STEP_KEY[_role] = _step_key


def _resolve_heyreach_text(role, custom_fields, fallbacks):
    """What the person reads for one role, from one lead's custom fields.

    Returns (text, source) where source is "lead" if the lead supplied the
    variable, or "fallback" if HeyReach would send the fallbackMessage.
    """
    value = (custom_fields or {}).get(role)
    if value and str(value).strip():
        return str(value), "lead"
    fallback = (fallbacks or {}).get(role, "")
    return str(fallback), "fallback"


def _detect_heyreach_issues(all_contacts, fallbacks, graph_is_variables=True):
    """Flag anything that would embarrass us, loudly and at the top.

    Returns a list of issue strings.  Empty means nothing was found.

    The checks:
    1. A literal person or company name in a lead's words that matches
       another lead's name or company - the hi-jacob defect class.
    2. A {{double brace}} in any text - HeyReach uses single braces.
    3. A variable no lead supplies (every contact would get the fallback).
    4. Two rendered steps that read the same for the same lead.
    """
    issues = []
    all_roles = list(heyreachfactory.REQUIRED_ROLES)

    # Collect every name and company across all contacts for cross-checking.
    all_names = set()
    all_companies = set()
    for contact_info in all_contacts:
        contact = contact_info.get("contact") or {}
        rec = contact_info.get("rec") or {}
        name = (contact.get("name") or "").strip()
        first = name.split()[0] if name else ""
        if first and len(first) > 2:
            all_names.add(first)
        company = (rec.get("company") or "").strip()
        if company:
            all_companies.add(company)

    for contact_info in all_contacts:
        contact = contact_info.get("contact") or {}
        rec = contact_info.get("rec") or {}
        fields = contact_info.get("custom_fields") or {}
        contact_key = contact.get("key", "?")

        # Check 1: literal names from OTHER contacts in this lead's words.
        own_name = (contact.get("name") or "").strip()
        own_first = own_name.split()[0] if own_name else ""
        own_company = (rec.get("company") or "").strip()
        for role in all_roles:
            text = str(fields.get(role) or "")
            if not text:
                continue
            for name in all_names:
                if name == own_first:
                    continue
                if re.search(r'\b' + re.escape(name) + r'\b', text,
                             re.IGNORECASE):
                    issues.append(
                        f"LITERAL NAME: lead {contact_key!r}, role "
                        f"{role!r} contains name {name!r} from another "
                        f"contact - the hi-jacob defect class")
            for company in all_companies:
                if company == own_company:
                    continue
                if company.lower() in text.lower():
                    issues.append(
                        f"LITERAL COMPANY: lead {contact_key!r}, role "
                        f"{role!r} contains company {company!r} from "
                        f"another record")

        # Check 2: {{double brace}} - HeyReach uses single braces.
        for role in all_roles:
            text = str(fields.get(role) or "")
            if "{{" in text or "}}" in text:
                issues.append(
                    f"DOUBLE BRACE: lead {contact_key!r}, role {role!r} "
                    f"contains '{{{{' or '}}}}' - HeyReach uses single "
                    f"braces for merge fields")

        # Check 3: missing variables - every step uses the fallback.
        for role in all_roles:
            value = fields.get(role)
            if not value or not str(value).strip():
                issues.append(
                    f"MISSING VARIABLE: lead {contact_key!r} supplies no "
                    f"words for {role!r} - every step on this branch "
                    f"will send the fallback text")

        # Check 4: two steps that read the same WITHIN THE SAME BRANCH.
        # Duplicates across branches are by design: li2 fills both
        # connected_1 and message_2, but a prospect walks only one branch.
        for branch_roles in (ALREADY_CONNECTED_BRANCH, NOT_CONNECTED_BRANCH):
            rendered_texts = {}
            for role in branch_roles:
                text, _ = _resolve_heyreach_text(role, fields, fallbacks)
                if text:
                    normalised = " ".join(text.split())
                    if normalised in rendered_texts:
                        issues.append(
                            f"DUPLICATE TEXT: lead {contact_key!r}, roles "
                            f"{rendered_texts[normalised]!r} and {role!r} "
                            f"render identical text on the same branch - "
                            f"a prospect reads the same sentence twice")
                    else:
                        rendered_texts[normalised] = role

    return issues


def _format_heyreach_graph(fallbacks):
    """Show the graph structure: variables, not words."""
    lines = []
    lines.append("")
    lines.append(_sep("-"))
    lines.append("  GRAPH STRUCTURE (campaign-level, carries VARIABLES)")
    lines.append(_sep("-"))
    lines.append("")
    lines.append("  The HeyReach sequence is campaign-level.  The graph")
    lines.append("  carries merge fields like {connection_note}, not one")
    lines.append("  contact's words.  Each lead supplies their own words")
    lines.append("  via customUserFields on the wire.")
    lines.append("")
    lines.append("  ROLES AND THE VARIABLES THEY CARRY:")
    for role in heyreachfactory.REQUIRED_ROLES:
        var = heyreachfactory.merge_variable_of(role)
        step_key = _ROLE_TO_STEP_KEY.get(role, "?")
        lines.append(f"    {role:20s} -> {{{var}}}  (from cadence step "
                     f"{step_key})")
    lines.append("")
    lines.append("  TWO BRANCHES A PROSPECT WALKS:")
    lines.append("    Already connected:  " +
                 " -> ".join(ALREADY_CONNECTED_BRANCH))
    lines.append("    Not yet connected:  " +
                 " -> ".join(NOT_CONNECTED_BRANCH))
    lines.append("")
    lines.append("  FALLBACKS (what HeyReach sends when a variable is "
                 "not filled):")
    for role in heyreachfactory.REQUIRED_ROLES:
        fb = (fallbacks or {}).get(role, "(none declared)")
        lines.append(f"    {role}:")
        for line in str(fb).splitlines():
            lines.append(f"      {line}")
    return "\n".join(lines)


def _format_heyreach_lead(rec, contact, custom_fields, fallbacks, missing,
                          branch_label):
    """Format one lead's rendering for one branch."""
    lines = []
    lines.append("")
    lines.append(_sep("="))
    lines.append(f"  LEAD: {(contact or {}).get('name', '?')}")
    lines.append(f"  Company: {rec.get('company', '?')}")
    lines.append(f"  Domain: {rec.get('domain', '?')}")
    lines.append(f"  Title: {(contact or {}).get('title', '?')}")
    li_url = (contact or {}).get("linkedin") or "NOT PROVIDED"
    lines.append(f"  LinkedIn: {li_url}")
    lines.append(f"  Branch: {branch_label}")
    if missing:
        lines.append("")
        for ck, step_key, role in missing:
            lines.append(f"  *** MISSING: step {step_key!r} -> role "
                         f"{role!r} has no approved copy ***")
    lines.append(_sep("="))

    roles = (ALREADY_CONNECTED_BRANCH if "ALREADY" in branch_label.upper()
             else NOT_CONNECTED_BRANCH)

    for role in roles:
        text, source = _resolve_heyreach_text(role, custom_fields, fallbacks)
        fallback = (fallbacks or {}).get(role, "(none)")
        step_key = _ROLE_TO_STEP_KEY.get(role, "?")
        var = heyreachfactory.merge_variable_of(role)

        lines.append("")
        lines.append(f"  --- {role} (cadence step: {step_key}) ---")
        lines.append(f"    Graph variable:  {{{var}}}")
        lines.append(f"    Lead's words:    "
                     f"{(custom_fields or {}).get(role, '(not supplied)')!r}")
        if source == "fallback":
            lines.append(f"    *** FALLBACK FIRED - lead did not supply "
                         f"this variable ***")
        lines.append(f"    Fallback text: {fallback!r}")
        lines.append(f"    RESULT (what the person reads):")
        for line in text.splitlines():
            lines.append(f"      {line}")

    return "\n".join(lines)


def _format_heyreach_wire(rec, contact, custom_fields):
    """Show what goes on the wire: the customUserFields build_lead_pairs
    produces."""
    row = {
        "linkedin_url": contact.get("linkedin", ""),
        "note": (custom_fields or {}).get("connection_note", ""),
        "record_id": rec.get("id", ""),
        "contact_key": contact.get("key", ""),
        "client": rec.get("client", ""),
        "first_name": (contact.get("key") or "").split("_")[0],
        "last_name": "",
        "company": rec.get("company", ""),
        "title": contact.get("title", ""),
        "custom_fields": dict(custom_fields or {}),
    }
    pairs = heyreach.build_lead_pairs([row], linkedin_account_id=0)
    lines = []
    lines.append("")
    lines.append(_sep("-"))
    lines.append(f"  WIRE FORMAT (customUserFields from build_lead_pairs)")
    lines.append(f"  Lead: {(contact or {}).get('name', '?')}")
    lines.append(_sep("-"))
    for pair in pairs:
        fields = (pair.get("lead") or {}).get("customUserFields") or []
        for field in fields:
            name = field.get("name", "?")
            value = field.get("value", "")
            display = value if len(str(value)) <= 70 else (
                str(value)[:67] + "...")
            lines.append(f"    {name}: {display!r}")
    return "\n".join(lines)


def render_heyreach_preview(campaign_name="heyreach", config=None, recs=None):
    """Render the HeyReach pipeline preview.

    Returns the rendered text as a string.  This goes through the REAL
    pipeline: merge_sequence_copy -> custom_fields_for -> build_lead_pairs.
    """
    out = []
    out.append(_sep("#"))
    out.append("  CAMPAIGN PREVIEW - WHAT THE PERSON ACTUALLY RECEIVES")
    out.append(f"  Campaign: {campaign_name}")
    out.append("  Pipeline: HeyReach merge fields (customUserFields)")
    out.append("  Graph: merge_sequence_copy -> variables, never words")
    out.append("  Per-lead: custom_fields_for -> approved words per role")
    out.append("  Wire: build_lead_pairs -> customUserFields on the wire")
    out.append(_sep("#"))

    if config is None:
        config = _fixture_config_heyreach()

    if recs is None:
        if campaign_name == "heyreach_planted_name":
            recs = [_fixture_rec_heyreach_planted_name()]
        elif campaign_name == "heyreach_missing_field":
            recs = [_fixture_rec_heyreach_missing_field()]
        elif campaign_name == "heyreach":
            recs = [_fixture_rec_heyreach(), _fixture_rec_heyreach_second()]
        else:
            recs = [_fixture_rec_heyreach()]

    fallbacks = ((config.get("linkedin_sequence") or {}).get("fallbacks")
                 or {})
    cadence_steps = cadence.steps_for(config=config)

    # Collect per-contact fields through the REAL pipeline.
    all_contacts = []
    for rec in recs:
        for contact in rec.get("contacts") or []:
            if not contact.get("linkedin"):
                continue
            key = contact.get("key")
            fields, missing = heyreachfactory.custom_fields_for(
                rec, key, cadence_steps=cadence_steps, config=config)
            all_contacts.append({
                "rec": rec,
                "contact": contact,
                "custom_fields": fields,
                "missing": missing,
            })

    # Issue detection at the top.
    issues = _detect_heyreach_issues(all_contacts, fallbacks)
    if issues:
        out.append("")
        out.append("  " + _sep("!"))
        out.append("  ISSUES DETECTED - READ BEFORE PROMOTING")
        out.append("  " + _sep("!"))
        for issue in issues:
            out.append(f"  !!! {issue}")
        out.append("  " + _sep("!"))
    else:
        out.append("")
        out.append("  No issues detected.")

    # Graph structure.
    out.append(_format_heyreach_graph(fallbacks))

    # Per-lead rendering.
    for contact_info in all_contacts:
        rec = contact_info["rec"]
        contact = contact_info["contact"]
        fields = contact_info["custom_fields"]
        missing = contact_info["missing"]

        # Already connected branch.
        out.append(_format_heyreach_lead(
            rec, contact, fields, fallbacks, missing,
            "ALREADY CONNECTED"))

        # Not connected branch.
        out.append(_format_heyreach_lead(
            rec, contact, fields, fallbacks, missing,
            "NOT YET CONNECTED (cold path, after connection accepted)"))

        # Wire format.
        out.append(_format_heyreach_wire(rec, contact, fields))

    out.append("")
    out.append(_sep("#"))
    out.append("  END OF HEYREACH PREVIEW")
    out.append(_sep("#"))
    return "\n".join(out)


def _try_load_campaign(campaign_id):
    """Try to load a campaign from work/ and render it.

    Returns (text, error).  If work/ is empty or the campaign is not found,
    error is a string explaining why.
    """
    from src import campaigns as campaigns_mod, store

    try:
        rows = campaigns_mod.load()
    except Exception as e:
        return None, (f"could not load campaigns from work/: {e}. "
                      f"The work/ directory may be empty in this worktree")
    campaign = campaigns_mod.get(campaign_id, rows)
    if campaign is None:
        available = [r.get("campaign_id") for r in rows]
        return None, (f"no campaign {campaign_id!r} found in work/. "
                      f"Available: {available or '(none)'}")

    client = campaign.get("client")
    if not client:
        return None, f"campaign {campaign_id!r} names no client"

    try:
        config = clients.load(client)
    except Exception as e:
        return None, f"could not load config for client {client!r}: {e}"

    try:
        recs = store.load()
    except Exception as e:
        return None, (f"could not load records from work/: {e}. "
                      f"The work/ directory may be empty in this worktree")

    # Check if this is a HeyReach campaign.
    if not campaign.get("heyreach_campaign_id"):
        return None, (f"campaign {campaign_id!r} has no "
                      f"heyreach_campaign_id - it is not a HeyReach "
                      f"campaign. The template preview path handles "
                      f"email-only campaigns")

    # Run _plan to get the graph and per-contact fields.
    try:
        plan = heyreachfactory._plan(campaign, recs, config)
    except heyreachfactory.FactoryRefused as e:
        return None, f"factory refused: {e}"

    # Build the preview from the plan.
    fallbacks = ((config.get("linkedin_sequence") or {}).get("fallbacks")
                 or {})
    rec_map = {r.get("id"): r for r in recs}

    out = []
    out.append(_sep("#"))
    out.append("  CAMPAIGN PREVIEW - WHAT THE PERSON ACTUALLY RECEIVES")
    out.append(f"  Campaign: {campaign_id}")
    out.append(f"  Client: {client}")
    out.append(f"  HeyReach campaign id: "
               f"{campaign.get('heyreach_campaign_id')}")
    out.append(f"  Status: {campaign.get('status', '?')}")
    out.append(f"  Record ids: {campaign.get('record_ids') or []}")
    out.append("  Pipeline: HeyReach merge fields (customUserFields)")
    out.append(_sep("#"))

    # Collect contacts from the plan.
    all_contacts = []
    for pc in plan.get("contacts") or []:
        rec = rec_map.get(pc["record_id"])
        if not rec:
            continue
        contact = None
        for c in rec.get("contacts") or []:
            if c.get("key") == pc["contact_key"]:
                contact = c
                break
        if not contact:
            continue
        all_contacts.append({
            "rec": rec,
            "contact": contact,
            "custom_fields": pc.get("custom_fields") or {},
            "missing": pc.get("missing") or [],
            "unsupported": pc.get("unsupported") or [],
        })

    pushable_count = len(plan.get("pushable") or [])
    total_count = len(all_contacts)
    out.append("")
    out.append(f"  Contacts: {total_count} total, {pushable_count} pushable")
    missing_count = len(plan.get("missing") or [])
    unsupported_count = len(plan.get("unsupported") or [])
    if missing_count:
        out.append(f"  Missing copy: {missing_count} role(s)")
    if unsupported_count:
        out.append(f"  Unsupported claims: {unsupported_count}")

    # Issue detection.
    #
    # THE COUNTS ABOVE ARE ISSUES TOO. This printed "Unsupported claims: 7"
    # and then "No issues detected" four lines later, because the two were
    # computed separately - and in a tool whose entire purpose is being READ
    # before a promotion, a reader who skims to the verdict is told the
    # opposite of what the numbers say. A contact excluded for an unsupported
    # claim is a contact that cannot be pushed; that is the definition of an
    # issue.
    issues = _detect_heyreach_issues(all_contacts, fallbacks)
    if unsupported_count:
        issues.insert(0, (
            f"{unsupported_count} contact(s) carry copy asserting something "
            f"the record does not support, and are NOT pushable"))
    if missing_count:
        issues.insert(0, (
            f"{missing_count} role(s) have no approved copy, so those "
            f"contacts are NOT pushable"))
    if issues:
        out.append("")
        out.append("  " + _sep("!"))
        out.append("  ISSUES DETECTED - READ BEFORE PROMOTING")
        out.append("  " + _sep("!"))
        for issue in issues:
            out.append(f"  !!! {issue}")
        out.append("  " + _sep("!"))
    else:
        out.append("")
        out.append("  No issues detected.")

    # Graph structure.
    out.append(_format_heyreach_graph(fallbacks))

    # Per-lead rendering - show up to 5 leads.
    shown = 0
    for contact_info in all_contacts:
        if shown >= 5:
            remaining = total_count - shown
            out.append("")
            out.append(f"  ... {remaining} more contact(s) not shown")
            break
        rec = contact_info["rec"]
        contact = contact_info["contact"]
        fields = contact_info["custom_fields"]
        missing = contact_info["missing"]

        out.append(_format_heyreach_lead(
            rec, contact, fields, fallbacks, missing,
            "ALREADY CONNECTED"))
        out.append(_format_heyreach_lead(
            rec, contact, fields, fallbacks, missing,
            "NOT YET CONNECTED (cold path, after connection accepted)"))
        out.append(_format_heyreach_wire(rec, contact, fields))
        shown += 1

    out.append("")
    out.append(_sep("#"))
    out.append("  END OF HEYREACH PREVIEW")
    out.append(_sep("#"))
    return "\n".join(out), None


# ------------------------------------------------------- variable analysis

def _template_placeholders(text):
    """The {variable} names a template references."""
    return sorted(set(re.findall(r"\{(\w+)\}", text)))


def _analyse_variables(spec, values):
    """What the template needs vs what was supplied.

    Returns (supplied, missing, fallbacks) where fallbacks is a list of
    variable names whose value came from a fallback rather than the record.
    """
    template = cadence.TEMPLATES.get(spec.get("template"), {})
    needed = set()
    for text in template.values():
        needed.update(_template_placeholders(text))

    supplied = {k: v for k, v in values.items() if k in needed}
    missing = needed - set(values.keys())

    # Detect fallback firings: values that are the known fallback defaults.
    fallbacks = []
    if values.get("sector") == "services" and "industry" not in (
            (values.get("_facts") or {}).get("industry") or ""):
        fallbacks.append("sector")
    if values.get("first_name") == "there":
        fallbacks.append("first_name")
    return sorted(supplied.keys()), sorted(missing), fallbacks


# -------------------------------------------------------- rendering engine

def _render_step_for_preview(rec, contact, spec, config, accepted=False,
                             campaign=None):
    """Render one step through the production code path.

    This calls `cadence.expand_step` directly - the SAME function that
    `cadence.build` calls, which is what `push.collect` calls, whose output
    feeds `push.payloads` - the exact request bodies the sender would post.

    Returns a dict with the raw template, variables, rendered output, and
    any issues detected.
    """
    values = None
    raw_template = None
    issues = []

    template_name = spec.get("template")
    if template_name and not spec.get("generated"):
        raw_template = cadence.TEMPLATES.get(template_name, {})
        try:
            values = cadence.template_vars(rec, contact, config)
        except cadence.CompanyNameUnusable as e:
            issues.append(f"COMPANY NAME UNUSABLE: {e}")
            values = None
    elif spec.get("generated"):
        # For generated steps, the stored copy IS the message.
        key = lint.contact_key(contact)
        stored = ((rec.get("cadence") or {}).get(key) or {}).get(
            spec["key"]) or {}
        values = {"_stored": True}

    # THE SAME CODE PATH. expand_step is what cadence.build calls, which is
    # what push.collect calls, whose items feed push.payloads.
    # Skip if template_vars already failed - expand_step will fail the same way.
    if values is not None or spec.get("generated") or not template_name:
        try:
            step = cadence.expand_step(rec, contact, spec, config,
                                       accepted=accepted, campaign=campaign)
        except cadence.CompanyNameUnusable as e:
            issues.append(f"COMPANY NAME UNUSABLE: {e}")
            step = None
        except cadence.CadenceError as e:
            issues.append(f"CADENCE ERROR: {e}")
            step = None
    else:
        step = None

    if step is None and not any("UNUSABLE" in i or "ERROR" in i for i in issues):
        issues.append("step returned None (generated content not yet written)")

    supplied, missing, fallbacks = [], [], []
    if values is not None and raw_template:
        supplied, missing, fallbacks = _analyse_variables(spec, values)

    return {
        "spec": spec,
        "raw_template": raw_template,
        "variables": {k: v for k, v in (values or {}).items()
                      if not k.startswith("_")},
        "supplied": supplied,
        "missing": missing,
        "fallbacks": fallbacks,
        "rendered": step,
        "issues": issues,
    }


# ------------------------------------------------------------- formatting

def _sep(char="=", width=78):
    return char * width


def _format_lead_header(rec, contact, branch_label=""):
    lines = [
        "",
        _sep("="),
        f"  LEAD: {(contact or {}).get('name', '?')}",
        f"  Company: {rec.get('company', '?')}",
        f"  Domain: {rec.get('domain', '?')}",
        f"  Title: {(contact or {}).get('title', '?')}",
        f"  Persona: {(contact or {}).get('persona', '?')}",
        f"  Angle: {(contact or {}).get('angle', '?')}",
        f"  Email: {(contact or {}).get('email', '?')}",
        f"  LinkedIn: {(contact or {}).get('linkedin') or 'NOT PROVIDED'}",
    ]
    if branch_label:
        lines.append(f"  Branch: {branch_label}")
    if not (contact or {}).get("linkedin"):
        lines.append("")
        lines.append("  *** WARNING: No LinkedIn URL - all LinkedIn steps "
                      "will be BLOCKED ***")
    lines.append(_sep("="))
    return "\n".join(lines)


def _format_step(result):
    """Format one rendered step for human reading."""
    spec = result["spec"]
    lines = []
    lines.append("")
    lines.append(f"  --- Step: {spec['key']} | Day {spec['day']} | "
                 f"{spec['channel'].upper()} ---")

    if result["issues"]:
        for issue in result["issues"]:
            lines.append(f"  !!! {issue}")

    rendered = result["rendered"]
    if rendered is None:
        lines.append("  (not rendered - content not yet written)")
        return "\n".join(lines)

    status = rendered.get("status", "?")
    lines.append(f"  Status: {status}")

    if rendered.get("requires"):
        lines.append(f"  Requires: {rendered['requires']}")
    if rendered.get("blocked_by"):
        lines.append(f"  Blocked by: {rendered['blocked_by']}")
    if rendered.get("linkedin_state"):
        lines.append(f"  LinkedIn state: {rendered['linkedin_state']}")
    if rendered.get("skipped_reason"):
        lines.append(f"  Skipped: {rendered['skipped_reason']}")

    if result["raw_template"]:
        lines.append("")
        lines.append("  RAW TEMPLATE:")
        for field, text in sorted(result["raw_template"].items()):
            lines.append(f"    {field}:")
            for line in str(text).splitlines():
                lines.append(f"      {line}")

    if result["variables"] and not result["variables"].get("_stored"):
        lines.append("")
        lines.append("  VARIABLES SUPPLIED:")
        for k, v in sorted(result["variables"].items()):
            marker = ""
            if k in result["fallbacks"]:
                marker = "  *** FALLBACK ***"
            if k in result["missing"]:
                marker = "  *** MISSING ***"
            lines.append(f"    {k}: {v!r}{marker}")

    if result["missing"]:
        lines.append("")
        lines.append(f"  *** MISSING VARIABLES: "
                     f"{', '.join(result['missing'])} ***")

    if result["fallbacks"]:
        lines.append("")
        lines.append(f"  *** FALLBACKS FIRED: "
                     f"{', '.join(result['fallbacks'])} ***")

    lines.append("")
    lines.append("  FINAL RENDERED COPY:")
    if rendered.get("channel") == "email":
        lines.append(f"    Subject: {rendered.get('subject', '(none)')}")
        lines.append(f"    Body:")
        for line in (rendered.get("body") or "").splitlines():
            lines.append(f"      {line}")
    else:
        lines.append(f"    Note:")
        for line in (rendered.get("note") or "").splitlines():
            lines.append(f"      {line}")

    if rendered.get("template"):
        lines.append(f"    [template: {rendered['template']}]")
    if rendered.get("generated"):
        lines.append(f"    [generated]")

    return "\n".join(lines)


# --------------------------------------------------------- main entry point

# The fixture names that route to the HeyReach pipeline.
HEYREACH_FIXTURES = frozenset((
    "heyreach", "heyreach_planted_name", "heyreach_missing_field",
))


def _is_campaign_id(name):
    """Does this look like a canonical campaign id rather than a fixture?"""
    return "-" in name and name not in HEYREACH_FIXTURES


def render_preview(campaign_name="balanced", config=None, recs=None):
    """Render the full preview for a named campaign fixture or campaign id.

    Routes to the template path (TASK-045) or the HeyReach path (TASK-046)
    based on the name.  A canonical campaign id loads from work/.

    Returns the rendered text as a string.
    """
    if _is_campaign_id(campaign_name):
        text, error = _try_load_campaign(campaign_name)
        if error:
            return (f"ERROR: {error}\n\n"
                    f"The preview could not render this campaign. "
                    f"This is a finding if the campaign exists in work/ "
                    f"on the production worktree.")
        return text

    if campaign_name in HEYREACH_FIXTURES:
        return render_heyreach_preview(
            campaign_name, config=config, recs=recs)

    out = []
    out.append(_sep("#"))
    out.append("  CAMPAIGN PREVIEW - WHAT THE PERSON ACTUALLY RECEIVES")
    out.append(f"  Campaign fixture: {campaign_name}")
    out.append("  Rendered from cadence.expand_step - the SAME code path")
    out.append("  that builds the provider payload via push.payloads()")
    out.append(_sep("#"))

    if config is None:
        if campaign_name == "li_heavy":
            config = _fixture_config("productive_li_heavy_v1")
        else:
            config = _fixture_config("productive_balanced_v1")

    if recs is None:
        if campaign_name == "li_heavy":
            recs = [_fixture_rec_li_heavy()]
        elif campaign_name == "no_linkedin":
            recs = [_fixture_rec_no_linkedin()]
        elif campaign_name == "missing_variable":
            recs = [_fixture_rec_missing_variable()]
        else:
            recs = [_fixture_rec_balanced()]

    for rec in recs:
        for contact in rec.get("contacts") or []:
            has_linkedin = bool(contact.get("linkedin"))
            sequence = cadence.steps_for(campaign=None, config=config,
                                         rec=rec, contact=contact)

            # --- Branch 1: not connected (default) ---
            out.append(_format_lead_header(rec, contact,
                                           "NOT CONNECTED (default)"))
            for spec in sequence:
                result = _render_step_for_preview(
                    rec, contact, spec, config, accepted=False)
                out.append(_format_step(result))

            # --- Branch 2: connected (LinkedIn branch) ---
            if has_linkedin:
                out.append("")
                out.append(_format_lead_header(
                    rec, contact,
                    "CONNECTED (connection_accepted=True)"))
                for spec in sequence:
                    result = _render_step_for_preview(
                        rec, contact, spec, config, accepted=True)
                    out.append(_format_step(result))
            else:
                out.append("")
                out.append("  *** LinkedIn connected branch: SKIPPED "
                           "because no LinkedIn URL was provided ***")

    out.append("")
    out.append(_sep("#"))
    out.append("  END OF PREVIEW")
    out.append(_sep("#"))
    return "\n".join(out)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Render what the person actually receives")
    parser.add_argument("campaign", nargs="?", default="balanced",
                        help="Campaign fixture name: balanced, li_heavy, "
                             "no_linkedin, missing_variable, heyreach, "
                             "heyreach_planted_name, "
                             "heyreach_missing_field; or a canonical "
                             "campaign id like "
                             "productive-linkedin-production-v1")
    args = parser.parse_args(argv)
    text = render_preview(args.campaign)
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
