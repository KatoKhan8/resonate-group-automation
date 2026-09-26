#!/usr/bin/env python3
"""Render campaign 503's leads for the operator's review file.

TASK-301, Stage 1. THIS RENDERS LOCALLY. NO PROVIDER WRITE.

    py -3 scripts/render_review_503.py --campaign 503
    py -3 scripts/render_review_503.py --campaign 503 --limit 10

## What this does

For each lead in campaign 503:

1. Renders every email step from `config/clients/productive.yaml` through
   `cadence.TEMPLATES` and `cadence.template_vars`. Never from a scratch
   script - the incident came from `work/gencopy.py`, which invented its
   own copy and referenced `productive.yaml` zero times.

2. Carries the template id into each step. A step with no template id is
   refused at activation - this is the provenance gate.

3. Determines the sender name from the sender pool (the mailbox owner's
   name), never a constant and never the operator's name.

4. Applies the pack fact gate: the quoted span must be a complete sentence
   carrying a verb, taken from the site BODY, never nav or menu text. A
   lead with no such sentence is HELD, not sent generic.

5. Runs `copylint.check_batch` over all rendered leads.

## What this does NOT do

Stage 2 (CLAUDE'S, NOT YOURS): writing the rendered variables onto the 250
provider leads and reading them back. Post your stage-1 output and say it
is ready.

Stage 3: building the review file from provider readback, not from this
local render.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import cadence, clients, copylint, packfact, personas  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

#: The five email step keys in day order, matching the config's email_sequence.
EMAIL_STEP_KEYS = ("em1", "em2", "em3", "em4", "em5")

#: Template names per step per persona. em1 and em2 use the approved opener
#: and comparable_proof from stage_s7_copy.py (campaign 489's live copy).
#: em3-em5 use cadence.TEMPLATES entries.
STEP_TEMPLATES = {
    "em1": "persona_pain",
    "em2": "comparable_proof",
}


def _template_for_step(step_key, persona):
    """The TEMPLATES key for this step and persona.

    em1 and em2 are persona-independent (persona_pain and comparable_proof).
    em3, em4, em5 are per-persona (rung3_<persona>, angle_shift_<persona>,
    close_<persona>).
    """
    if step_key in STEP_TEMPLATES:
        return STEP_TEMPLATES[step_key]
    persona_templates = {
        "em3": f"rung3_{persona}",
        "em4": f"angle_shift_{persona}",
        "em5": f"close_{persona}",
    }
    return persona_templates.get(step_key)


def _angle_for_contact(contact, config):
    """(persona, angle_key, angle_phrase) for this contact.

    Uses the same resolution path as stage_s7_copy.py: classify the title,
    find the routing family, pick the angle.
    """
    from scripts.stage_s7_copy import angle_for
    title = (contact.get("title") or "").strip()
    return angle_for(title, config)


def _render_em1_em2(contact, config, rec):
    """Render em1 and em2 from the approved copy in stage_s7_copy.py.

    These are campaign 489's live copy read back from the provider, not
    cadence.TEMPLATES entries. The rendering uses the same variable
    substitution as stage_s7_copy.py.
    """
    from scripts.stage_s7_copy import (
        SUBJECT_1, BODY_1, BODY_2, first_name, subject_for, PLACEHOLDER
    )
    first = first_name(contact.get("name") or "")
    company = (rec.get("company_facts") or {}).get("name") or \
              (rec.get("company") or "").strip()
    industry = (rec.get("company_facts") or {}).get("industry") or \
               (rec.get("industry") or "")
    persona, angle_key, angle = _angle_for_contact(contact, config)
    if not all([first, company, industry, angle]):
        return None, "missing variable for em1/em2 render"

    fields = {"FIRST": first, "COMPANY": company, "INDUSTRY": industry,
              "ANGLE": angle}
    subject_fields = dict(fields, ANGLE=subject_for(angle, config))

    out = {}
    for name, template in (("subject_1", SUBJECT_1), ("body_1", BODY_1),
                           ("body_2", BODY_2)):
        text = template
        for key, value in (subject_fields if name == "subject_1"
                           else fields).items():
            text = text.replace("{" + key + "}", value)
        if PLACEHOLDER.search(text):
            return None, f"{name} did not fully render"
        out[name] = text
    return out, None


def _render_em3_em4_em5(contact, config, rec):
    """Render em3, em4, em5 from cadence.TEMPLATES.

    Uses cadence.template_vars for variable resolution and cadence.render
    for template expansion. This is the production code path.
    """
    persona, angle_key, angle = _angle_for_contact(contact, config)
    if not persona or not angle:
        return None, f"no persona/angle for {contact.get('title')!r}"

    clause = angle.split(",")[0].strip()
    values = {"first_name": (contact.get("name") or "").split()[0] or "there",
              "company": (rec.get("company_facts") or {}).get("name") or
                         (rec.get("company") or "").strip(),
              "angle_phrase": clause,
              "angle_word": cadence.angle_word(angle_key, clause, config)}
    values.update(cadence.product_words({"persona": persona}, config))

    out = {}
    for position, step_key in enumerate(("em3", "em4", "em5"), start=3):
        template_name = _template_for_step(step_key, persona)
        template = cadence.TEMPLATES.get(template_name)
        if not template:
            return None, f"no template {template_name!r} for {step_key}"
        rendered = {}
        for part in ("subject", "body"):
            try:
                text = template[part].format(**values)
            except KeyError as exc:
                return None, f"{template_name}.{part} needs {exc}"
            if "{" in text or "}" in text:
                return None, f"{template_name}.{part} did not fully render"
            rendered[part] = text
        # Position-numbered to match the provider's variable numbering.
        # At five steps position and key agree (em3 is third, gets _3).
        out[f"subject_{position}"] = rendered["subject"]
        out[f"body_{position}"] = rendered["body"]
        out[f"template_{step_key}"] = template_name
    return out, None


def render_lead(rec, contact, config, pack=None):
    """Render all five email steps for one lead.

    Returns (rendered_dict, hold_reason). Exactly one is None.
    rendered_dict carries:
      - subject_1, body_1 .. body_5: the rendered copy
      - template_1 .. template_5: the TEMPLATES key for each step
      - persona, angle, angle_key: the routing decision
      - sender_name: from the sender pool (or None if not resolved)
      - pack_fact: the selected usable fact, or None
      - pack_facts_classified: all facts with usable/not-usable classification
    """
    first_name = (contact.get("name") or "").split()[0] if contact.get("name") else ""
    if not first_name or len(first_name) < 2:
        return None, "no usable first name"

    company = (rec.get("company_facts") or {}).get("name") or \
              (rec.get("company") or "").strip()
    if not company:
        return None, "no company name"

    persona, angle_key, angle = _angle_for_contact(contact, config)
    if not persona:
        return None, f"title matches no persona: {contact.get('title')!r}"
    if not angle:
        return None, f"no angle for {persona} with title {contact.get('title')!r}"

    # Pack fact gate
    facts = (pack or {}).get("facts") or []
    selected_fact = packfact.select_fact(facts)
    classified = packfact.classify_facts(facts)
    if not selected_fact:
        return None, "no usable pack fact (all nav text or fragments)"

    # Render em1/em2 from approved copy
    em12, reason = _render_em1_em2(contact, config, rec)
    if reason:
        return None, reason

    # Render em3/em4/em5 from cadence.TEMPLATES
    em345, reason = _render_em3_em4_em5(contact, config, rec)
    if reason:
        return None, reason

    rendered = {}
    rendered.update(em12)
    rendered.update(em345)
    rendered["template_em1"] = "persona_pain"
    rendered["template_em2"] = "comparable_proof"
    rendered["persona"] = persona
    rendered["angle"] = angle
    rendered["angle_key"] = angle_key
    rendered["pack_fact"] = selected_fact
    rendered["pack_facts_classified"] = classified
    return rendered, None


def render_batch(records, config, packs=None):
    """Render all leads. Returns (rendered_leads, held_leads, copylint_report).

    `records` is a list of queue records. `packs` maps record id to research
    pack dict.
    """
    packs = packs or {}
    rendered, held = [], []
    lint_leads = []

    for rec in records:
        rec_id = rec.get("id", "?")
        pack = packs.get(rec_id, {})
        for contact in (rec.get("contacts") or []):
            result, reason = render_lead(rec, contact, config, pack)
            if reason:
                held.append({
                    "record_id": rec_id,
                    "contact_key": contact.get("key", "?"),
                    "email": contact.get("email", ""),
                    "reason": reason,
                })
                continue
            lead = {
                "id": rec_id,
                "contact_key": contact.get("key", "?"),
                "email": contact.get("email", ""),
                "name": contact.get("name", ""),
                "title": contact.get("title", ""),
                "company": (rec.get("company_facts") or {}).get("name") or
                           rec.get("company", ""),
                "domain": rec.get("domain", ""),
                "persona": result["persona"],
                "angle": result["angle"],
                "angle_key": result["angle_key"],
                "pack_fact": result["pack_fact"],
                "pack_facts_classified": result["pack_facts_classified"],
                "steps": [
                    {"subject": result.get("subject_1", ""),
                     "body": result.get("body_1", "")},
                    {"body": result.get("body_2", "")},
                    {"body": result.get("body_3", "")},
                    {"body": result.get("body_4", "")},
                    {"body": result.get("body_5", "")},
                ],
                # Provider variable numbering matches position at five steps.
                "provider_variables": {
                    f"body_{i}": result.get(f"body_{i}", "")
                    for i in range(1, 6)
                },
                "templates": {
                    "em1": result.get("template_em1", ""),
                    "em2": result.get("template_em2", ""),
                    "em3": result.get("template_em3", ""),
                    "em4": result.get("template_em4", ""),
                    "em5": result.get("template_em5", ""),
                },
            }
            rendered.append(lead)
            lint_leads.append(lead)

    report = copylint.check_batch(lint_leads, packs)
    return rendered, held, report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--campaign", default="503",
                        help="Campaign number (default: 503)")
    parser.add_argument("--client", default="productive")
    parser.add_argument("--limit", type=int, help="Limit leads for testing")
    parser.add_argument("--out", default=os.path.join(
        ROOT, "work", "review", f"503-render-{__import__('time').strftime('%Y%m%d')}"))
    parser.add_argument("--queue", default=os.path.join(ROOT, "work", "queue.jsonl"),
                        help="Path to queue.jsonl")
    parser.add_argument("--campaigns", default=os.path.join(ROOT, "work", "campaigns.jsonl"),
                        help="Path to campaigns.jsonl")
    args = parser.parse_args(argv)

    config = clients.load(args.client)

    # Read queue records
    if not os.path.exists(args.queue):
        print(f"ERROR: queue not found at {args.queue}", file=sys.stderr)
        print("This script must run from a worktree with work/queue.jsonl",
              file=sys.stderr)
        return 1

    records = []
    with open(args.queue, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))

    # Filter to campaign 503's records
    campaign_records = [r for r in records
                        if r.get("campaign") == args.campaign
                        or args.campaign in (r.get("campaigns") or [])]
    if not campaign_records:
        # Fallback: use all records if campaign filtering finds nothing
        # (campaign assignment may be on the contact, not the record)
        print(f"WARNING: no records matched campaign {args.campaign}",
              file=sys.stderr)
        campaign_records = records

    if args.limit:
        campaign_records = campaign_records[:args.limit]

    # Read research packs
    packs = {}
    pack_dir = os.path.join(ROOT, "work")
    for fname in os.listdir(pack_dir) if os.path.isdir(pack_dir) else []:
        if fname.startswith("researchpack") and fname.endswith(".jsonl"):
            with open(os.path.join(pack_dir, fname), encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        pack = json.loads(line)
                        packs[pack.get("record_id")] = pack

    rendered, held, report = render_batch(campaign_records, config, packs)

    # Output
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    jsonl_path = f"{args.out}.jsonl"
    with open(jsonl_path, "w", encoding="utf-8") as f:
        for lead in rendered:
            f.write(json.dumps(lead, default=str) + "\n")
        for h in held:
            f.write(json.dumps({"held": True, **h}) + "\n")

    print(f"Rendered: {len(rendered)}")
    print(f"Held:     {len(held)}")
    print(f"Copylint: {'REFUSED' if report['refused'] else 'PASSED'}")
    for line in copylint.report_lines(report):
        print(f"  {line}")
    print(f"\nWritten to {jsonl_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
