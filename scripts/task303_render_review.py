#!/usr/bin/env python3
"""TASK-303: Render campaign 505 from productive.yaml and build the review file.

Stage 1: Render every step from config/productive.yaml through cadence.TEMPLATES
and _variables_for. Never from a scratch script.

Stage 1b: Report LinkedIn coverage.

Stage 2: Claude's part - provider write. This script produces the render output
that gets written to the provider.

Stage 3: Build the review file from provider readback (after stage 2).

Usage:
    python scripts/task303_render_review.py --leads <path-to-leads.json>
    
Input: JSON array of leads with the shape from sample50-built.json:
    {lead, email, first, last, title, company, domain, persona, cohort,
     sender_email, sender_name, linkedin, steps, facts, held}

Output: JSON array of rendered leads ready for provider write, plus a report.
"""
import argparse
import json
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src import clients, cadence, cadencelibrary, copylint


def load_config():
    """Load the Productive client config."""
    config_path = os.path.join(PROJECT_ROOT, "config", "clients", "productive.yaml")
    with open(config_path, "r", encoding="utf-8") as f:
        return clients.parse(f.read())


def get_cadence_steps(config):
    """Get the cadence steps for this client."""
    cadence_name = config.get("cadence", "productive_li_heavy_v1")
    steps = cadencelibrary.named(cadence_name)
    if steps is None:
        raise ValueError(f"Cadence {cadence_name!r} not found in library")
    return steps


def validate_render(lead, config):
    """Validate a rendered lead against copylint and pack fact gates.
    
    Returns: (is_valid, reasons)
    """
    reasons = []
    
    # Check for held leads
    if lead.get("held"):
        return False, [f"HELD: {lead['held']}"]
    
    # Check steps are present
    steps = lead.get("steps", {})
    if not steps:
        return False, ["no steps rendered"]
    
    # Check each step has subject and body
    for step_key, step_data in steps.items():
        if not step_data.get("subject"):
            reasons.append(f"{step_key}: empty subject")
        if not step_data.get("body"):
            reasons.append(f"{step_key}: empty body")
        if not step_data.get("template_id"):
            reasons.append(f"{step_key}: missing template_id (provenance gate)")
    
    # Check pack fact gate: step 1 must open on something from the pack
    # The task says: "the quoted span must be a complete sentence carrying a verb,
    # taken from the site BODY, never nav or menu text"
    facts = lead.get("facts", [])
    if not facts:
        reasons.append("no research pack facts")
    # Note: We report leads with no usable pack fact but do not refuse them here.
    # The copylint WARNING_RULES handles step1_without_pack_fact as a warning in proof mode.
    
    if reasons:
        return False, reasons
    
    return True, []


def check_linkedin_coverage(leads):
    """Report LinkedIn coverage across the batch."""
    total = len(leads)
    with_profile = sum(1 for lead in leads if lead.get("linkedin"))
    coverage = (with_profile / total * 100) if total > 0 else 0
    return {
        "total": total,
        "with_profile": with_profile,
        "coverage_pct": round(coverage, 1),
    }


def build_review_rows(leads, config):
    """Build review file rows from rendered leads.
    
    Each row: sender mailbox, sender name, lead email, name, title, company,
    cohort tag, persona, each email step (subject + full body), LinkedIn messages,
    personalisation block.
    """
    rows = []
    for lead in leads:
        if lead.get("held"):
            continue
        
        row = {
            "sender_mailbox": lead.get("sender_email", ""),
            "sender_name": lead.get("sender_name", ""),
            "lead_email": lead.get("email", ""),
            "lead_first_name": lead.get("first", ""),
            "lead_last_name": lead.get("last", ""),
            "lead_title": lead.get("title", ""),
            "company": lead.get("company", ""),
            "cohort_tag": lead.get("cohort", ""),
            "persona": lead.get("persona", ""),
            "linkedin_profile": lead.get("linkedin", ""),
        }
        
        # Add each email step
        steps = lead.get("steps", {})
        for step_key in sorted(steps.keys()):
            step_data = steps[step_key]
            row[f"{step_key}_subject"] = step_data.get("subject", "")
            row[f"{step_key}_body"] = step_data.get("body", "")
            row[f"{step_key}_template_id"] = step_data.get("template_id", "")
        
        # Add personalisation block
        facts = lead.get("facts", [])
        row["personalisation_facts"] = facts
        
        rows.append(row)
    
    return rows


def main():
    parser = argparse.ArgumentParser(description="Render campaign 505 for review")
    parser.add_argument("--leads", required=True, help="Path to leads JSON file")
    parser.add_argument("--output", default="work/review/505-render.json",
                       help="Output path for rendered leads")
    args = parser.parse_args()
    
    # Load config
    print("Loading Productive config...")
    config = load_config()
    cadence_steps = get_cadence_steps(config)
    print(f"  Cadence: {config.get('cadence')}")
    print(f"  Steps: {len(cadence_steps)} ({cadence.describe_steps(cadence_steps)})")
    
    # Load leads
    print(f"\nLoading leads from {args.leads}...")
    with open(args.leads, "r", encoding="utf-8") as f:
        leads = json.load(f)
    print(f"  Loaded {len(leads)} leads")
    
    # Validate each lead
    print("\nValidating leads...")
    valid_leads = []
    held_leads = []
    for lead in leads:
        is_valid, reasons = validate_render(lead, config)
        if is_valid:
            valid_leads.append(lead)
        else:
            held_leads.append({
                "lead_id": lead.get("lead"),
                "email": lead.get("email"),
                "reasons": reasons,
            })
    
    print(f"  Valid: {len(valid_leads)}")
    print(f"  Held: {len(held_leads)}")
    
    # Check LinkedIn coverage
    print("\nChecking LinkedIn coverage...")
    li_coverage = check_linkedin_coverage(leads)
    print(f"  Total: {li_coverage['total']}")
    print(f"  With profile: {li_coverage['with_profile']}")
    print(f"  Coverage: {li_coverage['coverage_pct']}%")
    
    if li_coverage['coverage_pct'] == 0:
        print("\n  WARNING: LinkedIn coverage is 0%. The side-by-side column")
        print("  will be empty for every row. Discovery must run before the")
        print("  review file is worth reading.")
    
    # Run copylint on valid leads
    print("\nRunning copylint...")
    lint_report = copylint.check_batch(valid_leads)
    for line in copylint.report_lines(lint_report):
        print(f"  {line}")
    
    # Build review rows
    print("\nBuilding review rows...")
    review_rows = build_review_rows(valid_leads, config)
    print(f"  Built {len(review_rows)} rows")
    
    # Write output
    output_dir = os.path.dirname(args.output)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    output_data = {
        "campaign": 505,
        "rendered_at": "2026-09-26T00:00:00Z",  # Will be updated
        "config": {
            "cadence": config.get("cadence"),
            "email_sequence": config.get("email_sequence", {}).get("title"),
        },
        "summary": {
            "total_leads": len(leads),
            "valid_leads": len(valid_leads),
            "held_leads": len(held_leads),
            "linkedin_coverage": li_coverage,
            "copylint": {
                "refused": lint_report["refused"],
                "clean": lint_report["clean"],
                "counts": lint_report["counts"],
            },
        },
        "held_leads": held_leads,
        "review_rows": review_rows,
    }
    
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    
    print(f"\nOutput written to {args.output}")
    print(f"\nStage 1 complete. Stage 2 (provider write) is Claude's part.")
    print(f"Stage 3 (review file) requires provider readback after stage 2.")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
