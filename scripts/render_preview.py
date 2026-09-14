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

Usage:
    python scripts/render_preview.py [campaign_name]

The campaign name selects a fixture.  The default fixture uses the balanced
cadence (templates throughout), which is where the raw-template -> variables
-> final-rendered chain is visible.  A second fixture uses the LinkedIn-heavy
cadence with pre-filled generated steps.

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

def render_preview(campaign_name="balanced", config=None, recs=None):
    """Render the full preview for a named campaign fixture.

    Returns the rendered text as a string.
    """
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
                             "no_linkedin, missing_variable")
    args = parser.parse_args(argv)
    text = render_preview(args.campaign)
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
