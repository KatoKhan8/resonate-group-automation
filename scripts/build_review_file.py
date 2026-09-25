#!/usr/bin/env python3
"""Build the operator's review file for one or more campaigns.

TASK-304: retroactive review files for campaigns 491, 492, 494, 496.
TASK-301: the standing column spec for every review file.

USAGE

    # From cached provider data (no live API call):
    python -m scripts.build_review_file 491 492 494 496 \\
        --provider-data work/review/provider-readback.json

    # With a live provider read (requires BISON_API_KEY):
    python -m scripts.build_review_file 491 --live

OUTPUT

    work/review/<campaign_id>-review.xlsx
    work/review/<campaign_id>-review.html
    work/review/<campaign_id>-review.csv

    And the file hash, which the operator quotes back to approve:
        APPROVED 491 <hash>

DATA REQUIREMENTS

The review file is built from PROVIDER READBACK, not from local render.
The body text is what the provider will send, read back after the
variables are written onto the leads. This is the whole point of the
gate: a review file built from our CSV certifies our intent, which is
not the thing that failed.

The provider data JSON has this shape:

    {
      "491": {
        "campaign": { ... campaign row from work/campaigns.jsonl ... },
        "senders": [{"email": "...", "name": "..."}],
        "sequence_steps": [
          {"step_key": "em1", "email_subject": "{SUBJECT_1}",
           "email_body": "<p>{BODY_1}</p>", "thread_reply": false},
          ...
        ],
        "leads": [
          {
            "lead_id": 12345,
            "record_id": "rec-abc",
            "contact_key": "john-doe",
            "custom_variables": {
              "subject_1": "...", "body_1": "...",
              "subject_2": "", "body_2": "...",
              "subject_3": "...", "body_3": "..."
            },
            "profile": {
              "email": "john@example.com",
              "first_name": "John",
              "last_name": "Doe",
              "title": "CEO",
              "company": "Acme Agency"
            }
          }
        ]
      }
    }

For the 83 leads with no copy variables: the operator decided that our
variables must be WRITTEN onto the existing provider lead and READ BACK
before the review file is built. That is Stage 2 (Claude's job, not
ours). The script refuses to render a lead whose custom_variables carry
no subject_1/body_1 - it reports the lead as HELD rather than sending
generic copy.
"""
import argparse
import json
import os
import sys

# Allow running from project root.
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src import reviewfile


def _render_provider_step(template_step, variables):
    """Render a provider template step with the lead's variables.

    The provider stores `{SUBJECT_1}` and `<p>{BODY_1}</p>` as the
    sequence template. The lead's custom_variables carry the actual words.
    This function simulates what the provider does at send time.
    """
    subject_tmpl = template_step.get("email_subject", "")
    body_tmpl = template_step.get("email_body", "")

    # Build the variable map: upper-case names as the provider uses them.
    var_map = {}
    for k, v in (variables or {}).items():
        var_map[k.upper()] = str(v or "")
        var_map[k.lower()] = str(v or "")

    # Simple {VARIABLE} substitution.
    import re
    def _sub(match):
        name = match.group(1)
        return var_map.get(name, var_map.get(name.lower(), ""))

    subject = re.sub(r"\{(\w+)\}", _sub, subject_tmpl)
    body = re.sub(r"\{(\w+)\}", _sub, body_tmpl)
    # Strip HTML tags for the review file (the operator reads plain text).
    body_plain = re.sub(r"<[^>]+>", "", body).strip()
    return {"subject": subject, "body": body_plain}


def _join_pack_facts(record, variables):
    """The personalisation block for one lead.

    Joins the record's research pack facts with which ones were used in
    the copy. A fact is USED if its snippet text appears in any step body.
    """
    facts = (record or {}).get("facts") or []
    if not facts:
        return []

    # Collect all body text for traceability.
    all_text = ""
    for key in ("body_1", "body_2", "body_3", "body_4", "body_5"):
        all_text += " " + str(variables.get(key, ""))
    all_text_lower = all_text.lower()

    result = []
    for fact in facts:
        snippet = str(fact.get("snippet") or "")
        # A fact is USED if a meaningful portion of its snippet appears
        # in the rendered copy.
        words = snippet.lower().split()
        used = False
        feeds = ""
        if len(words) >= 3:
            # Check if any 3-word window from the snippet appears in copy.
            for i in range(len(words) - 2):
                window = " ".join(words[i:i + 3])
                if window in all_text_lower:
                    used = True
                    # Find which step body contains it.
                    for key in ("body_1", "body_2", "body_3"):
                        if window in str(variables.get(key, "")).lower():
                            step_num = key.split("_")[1]
                            feeds = f"step {step_num}"
                            break
                    break
        result.append({
            "source_url": fact.get("source_url", ""),
            "retrieved_at": fact.get("retrieved_at", ""),
            "snippet": snippet[:200],  # truncate for readability
            "used": "USED" if used else "NOT USED",
            "feeds_sentence": feeds,
        })
    return result


def _sender_for_lead(lead_data, senders):
    """Which sender mailbox this lead uses.

    The campaign's sender pool is round-robin or hash-assigned. For the
    review file we read the sender off the lead data if present, or
    assign from the pool by lead_id hash.
    """
    if lead_data.get("sender_email"):
        return (lead_data.get("sender_email"),
                lead_data.get("sender_name", ""))
    if not senders:
        return ("unknown", "unknown")
    # Deterministic assignment by lead_id.
    lead_id = str(lead_data.get("lead_id", ""))
    idx = hash(lead_id) % len(senders)
    s = senders[idx]
    return (s.get("email", ""), s.get("name", ""))


def build_from_provider_data(campaign_id, data, packs=None):
    """Build the review file from cached provider readback data.

    Returns the reviewfile.build() result dict.
    """
    packs = packs or {}
    campaign_data = data.get(str(campaign_id))
    if not campaign_data:
        raise ValueError(f"no provider data for campaign {campaign_id}")

    campaign = campaign_data.get("campaign", {})
    senders = campaign_data.get("senders", [])
    sequence_steps = campaign_data.get("sequence_steps", [])
    leads = campaign_data.get("leads", [])
    n_steps = len(sequence_steps)

    # Determine cohort tag from campaign metadata.
    cohort_tag = campaign.get("batch_id", "") or campaign.get("name", "")

    held = []
    built_leads = []

    for lead_data in leads:
        variables = lead_data.get("custom_variables", {})
        profile = lead_data.get("profile", {})

        # REFUSE TO RENDER A BLANK LEAD. If the lead has no subject_1/body_1,
        # it would render blank. Report it as HELD, not sent generic.
        has_copy = (variables.get("subject_1") or variables.get("body_1"))
        if not has_copy:
            held.append({
                "lead_id": lead_data.get("lead_id"),
                "record_id": lead_data.get("record_id"),
                "reason": "no copy variables - needs Stage 2 provider write",
            })
            continue

        sender_email, sender_name = _sender_for_lead(lead_data, senders)

        # Render each step from the provider template + lead variables.
        steps = []
        for step_tmpl in sequence_steps:
            rendered = _render_provider_step(step_tmpl, variables)
            steps.append(rendered)

        # Pack facts for the personalisation block.
        record_id = lead_data.get("record_id", "")
        pack = packs.get(record_id, {})
        pack_facts = _join_pack_facts(pack, variables)

        built_leads.append({
            "sender_mailbox": sender_email,
            "sender_name": sender_name,
            "lead_email": profile.get("email", ""),
            "name": f"{profile.get('first_name', '')} "
                    f"{profile.get('last_name', '')}".strip(),
            "title": profile.get("title", ""),
            "company": profile.get("company", ""),
            "cohort_tag": cohort_tag,
            "persona": lead_data.get("persona", ""),
            "steps": steps,
            "linkedin": lead_data.get("linkedin", {}),
            "pack_facts": pack_facts,
        })

    has_linkedin = any(lead.get("linkedin", {}).get("profile_url")
                       for lead in built_leads)
    result = reviewfile.build(campaign_id, built_leads, n_steps=n_steps,
                              has_linkedin=has_linkedin)
    result["held"] = held
    result["held_count"] = len(held)
    result["rendered_count"] = len(built_leads)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="python -m scripts.build_review_file",
        description="Build the operator's review file for campaigns")
    parser.add_argument("campaign_ids", nargs="+",
                        help="Campaign IDs to build review files for")
    parser.add_argument("--provider-data", required=True,
                        help="Path to cached provider readback JSON")
    parser.add_argument("--packs", default=None,
                        help="Path to research packs JSON (optional)")
    parser.add_argument("--output-dir", default=None,
                        help="Output directory (default: work/review/)")
    parser.add_argument("--live", action="store_true",
                        help="Read from live provider (not yet implemented)")
    args = parser.parse_args(argv)

    if args.live:
        print("ERROR: --live is not yet implemented. "
              "Use --provider-data with cached readback.", file=sys.stderr)
        return 1

    # Load provider data.
    with open(args.provider_data, "r", encoding="utf-8") as f:
        provider_data = json.load(f)

    # Load packs if provided.
    packs = {}
    if args.packs:
        with open(args.packs, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    pack = json.loads(line)
                    packs[pack.get("record_id", "")] = pack

    output_dir = args.output_dir or os.path.join(ROOT, "work", "review")
    os.makedirs(output_dir, exist_ok=True)

    for campaign_id in args.campaign_ids:
        try:
            result = build_from_provider_data(campaign_id, provider_data,
                                              packs)
        except ValueError as e:
            print(f"Campaign {campaign_id}: {e}", file=sys.stderr)
            continue

        xlsx_path, html_path, csv_path = reviewfile.write(result, output_dir)

        print(f"Campaign {campaign_id}:")
        print(f"  Rendered: {result['rendered_count']} leads")
        print(f"  Held:     {result['held_count']} leads")
        print(f"  Steps:    {result['n_steps']}")
        print(f"  Hash:     {result['file_hash']}")
        print(f"  Files:    {xlsx_path}")
        print(f"            {html_path}")
        print(f"            {csv_path}")
        if result["held"]:
            print(f"  HELD leads (need Stage 2 provider write):")
            for h in result["held"][:5]:
                print(f"    lead {h['lead_id']} ({h['record_id']}): "
                      f"{h['reason']}")
            if len(result["held"]) > 5:
                print(f"    ... and {len(result['held']) - 5} more")
        print()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
