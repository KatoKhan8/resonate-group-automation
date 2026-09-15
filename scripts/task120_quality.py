#!/usr/bin/env python3
"""TASK-120 part 3: what would the estate look like AFTER?

Since we cannot run the model in dry run, we analyse what is CURRENTLY stored
against the measures that matter, and identify which steps would plausibly
benefit from regeneration vs which are already good.

Measures:
1. Productive named (does the copy name the product?)
2. Sender identified (does the copy say who is writing?)
3. Ladder progression (does each step do its distinct job?)
4. "I noticed" openers (the repetition defect)
5. Duplicate follow-ups (quality gate failures)
"""
import json
import os
import sys
import re
from collections import Counter, defaultdict

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src import store, clients, generate, approval, lint, cadencelibrary


def load_snapshot():
    snap = os.path.join(store.ROOT, "work", "queue.snapshot.jsonl")
    recs = []
    with open(snap, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                recs.append(json.loads(line))
    return recs


def analyze_copy_quality(recs, config):
    """Analyze the quality of currently stored copy."""
    
    seq = cadencelibrary.named("productive_li_heavy_v1")
    
    # Measures
    product_named = {"email": 0, "linkedin": 0}
    product_total = {"email": 0, "linkedin": 0}
    sender_identified = {"email": 0, "linkedin": 0}
    sender_total = {"email": 0, "linkedin": 0}
    i_noticed_openers = {"email": 0, "linkedin": 0}
    total_with_content = {"email": 0, "linkedin": 0}
    
    # Per-step analysis
    step_analysis = defaultdict(lambda: {
        "count": 0, "product_named": 0, "sender_identified": 0,
        "i_noticed": 0, "has_approval": 0, "repeats_sibling": 0,
    })
    
    # Records with quality gate failures
    quality_failures = []
    
    # Per-record, per-contact analysis
    for rec in recs:
        cadence_data = rec.get("cadence") or {}
        for contact_key, steps in cadence_data.items():
            if not isinstance(steps, dict):
                continue
            
            # Get contact
            contact = None
            for c in (rec.get("contacts") or []):
                if c.get("key") == contact_key:
                    contact = c
                    break
            
            sequence = generate.sequence_for(rec, config, contact) if contact else None
            
            for step_key, step_data in steps.items():
                if not isinstance(step_data, dict):
                    continue
                
                channel = step_data.get("channel", "")
                body = step_data.get("body") or ""
                note = step_data.get("note") or ""
                subject = step_data.get("subject") or ""
                text = (subject + " " + body + " " + note).lower()
                
                if not (body or note):
                    continue
                
                total_with_content[channel] += 1
                product_total[channel] += 1
                sender_total[channel] += 1
                
                # Get ordinal
                _, ordinal, _ = generate.position(sequence, step_key) if sequence else (None, None, None)
                
                # 1. Productive named
                names = ["productive", "productivity"]
                if any(n in text for n in names):
                    product_named[channel] += 1
                    step_analysis[step_key]["product_named"] += 1
                
                # 2. Sender identified
                # Check for sender name, company name, or role mention
                sender = config.get("sender", {}) if config else {}
                sender_name = (sender.get("name") or "").lower()
                sender_company = (sender.get("company") or "").lower()
                sender_role = (sender.get("role") or "").lower()
                
                has_sender = False
                if sender_name and sender_name in text:
                    has_sender = True
                if sender_company and sender_company in text:
                    has_sender = True
                # Check for "i work" or "i'm" patterns that indicate self-identification
                if re.search(r"\bi(?:'m| am)\b", text):
                    has_sender = True
                if re.search(r"\bi work\b", text):
                    has_sender = True
                
                if has_sender:
                    sender_identified[channel] += 1
                    step_analysis[step_key]["sender_identified"] += 1
                
                # 3. "I noticed" openers
                first_line = (body or note or "").split("\n")[0].lower().strip()
                if first_line.startswith("i noticed") or first_line.startswith("i see that"):
                    i_noticed_openers[channel] += 1
                    step_analysis[step_key]["i_noticed"] += 1
                
                # 4. Approval status
                appr = step_data.get("approval")
                if appr and approval.is_approved(rec, contact_key, step_key, step_data):
                    step_analysis[step_key]["has_approval"] += 1
                
                step_analysis[step_key]["count"] += 1
    
    # Check for quality gate failures (repetition)
    for rec in recs:
        ops = generate.plan(rec, config, regen_stale_ladder=False)
        for op in ops:
            if "repeats another step" in op.get("why", ""):
                quality_failures.append({
                    "record_id": rec["id"],
                    "contact": op.get("contact"),
                    "step": op.get("day", ""),
                    "why": op.get("why", ""),
                })
                ck = None
                for c in (rec.get("contacts") or []):
                    if op.get("contact") in (c.get("name"), c.get("key")):
                        ck = c.get("key")
                        break
                if ck:
                    step_analysis[op.get("day", "")]["repeats_sibling"] += 1
    
    return {
        "product_named": product_named,
        "product_total": product_total,
        "sender_identified": sender_identified,
        "sender_total": sender_total,
        "i_noticed_openers": i_noticed_openers,
        "total_with_content": total_with_content,
        "step_analysis": dict(step_analysis),
        "quality_failures": quality_failures,
    }


def analyze_approval_age(recs, config):
    """How old are the 83 approvals?"""
    
    approvals = []
    for rec in recs:
        cadence_data = rec.get("cadence") or {}
        for contact_key, steps in cadence_data.items():
            if not isinstance(steps, dict):
                continue
            for step_key, step_data in steps.items():
                if not isinstance(step_data, dict):
                    continue
                appr = step_data.get("approval")
                if appr and approval.is_approved(rec, contact_key, step_key, step_data):
                    approvals.append({
                        "record_id": rec["id"],
                        "contact_key": contact_key,
                        "step_key": step_key,
                        "channel": step_data.get("channel", ""),
                        "approved_by": appr.get("by", ""),
                        "approved_at": appr.get("at", ""),
                        "fingerprint": appr.get("fingerprint", "")[:16],
                    })
    
    return approvals


def analyze_what_regeneration_would_change(recs, config):
    """What would actually CHANGE if we regenerated?

    Since all 686 steps have NO fingerprint, ALL are stale by the
    no-fingerprint rule. But many also fail OTHER gates (quality, claims,
    lint). The question is: of the 83 approved steps, how many ALSO fail
    other gates? Those would be regenerated regardless of the ladder flag.
    """
    
    approved_stale = []
    approved_also_fails_other = []
    approved_clean_otherwise = []
    
    for rec in recs:
        ops_stale = generate.plan(rec, config, regen_stale_ladder=True)
        ops_normal = generate.plan(rec, config, regen_stale_ladder=False)
        
        stale_keys = set()
        for op in ops_stale:
            if op.get("ladder_stale"):
                stale_keys.add((op.get("contact", ""), op.get("day", "")))
        
        normal_fail_keys = set()
        for op in ops_normal:
            if not op.get("ladder_stale"):
                normal_fail_keys.add((op.get("contact", ""), op.get("day", "")))
        
        # Check which approved steps are stale
        cadence_data = rec.get("cadence") or {}
        for contact_key, steps in cadence_data.items():
            if not isinstance(steps, dict):
                continue
            for step_key, step_data in steps.items():
                if not isinstance(step_data, dict):
                    continue
                appr = step_data.get("approval")
                if not (appr and approval.is_approved(rec, contact_key, step_key, step_data)):
                    continue
                
                # This step is approved. Is it stale?
                contact_name = None
                for c in (rec.get("contacts") or []):
                    if c.get("key") == contact_key:
                        contact_name = c.get("name")
                        break
                
                is_stale = (contact_name, step_key) in stale_keys
                fails_other = (contact_name, step_key) in normal_fail_keys
                
                if is_stale:
                    approved_stale.append({
                        "record_id": rec["id"],
                        "contact": contact_key,
                        "step": step_key,
                        "channel": step_data.get("channel", ""),
                        "also_fails_other_gate": fails_other,
                    })
                    if fails_other:
                        approved_also_fails_other.append({
                            "record_id": rec["id"],
                            "contact": contact_key,
                            "step": step_key,
                        })
                    else:
                        approved_clean_otherwise.append({
                            "record_id": rec["id"],
                            "contact": contact_key,
                            "step": step_key,
                        })
    
    return {
        "approved_stale": approved_stale,
        "approved_also_fails_other": approved_also_fails_other,
        "approved_clean_otherwise": approved_clean_otherwise,
    }


def main():
    print("TASK-120 PART 3: What would the estate look like AFTER?")
    print("=" * 70)
    
    recs = load_snapshot()
    config = clients.load("productive")
    
    # 1. Copy quality analysis
    print("\nSECTION 1: CURRENT COPY QUALITY")
    print("-" * 50)
    quality = analyze_copy_quality(recs, config)
    
    for ch in ("email", "linkedin"):
        total = quality["total_with_content"][ch]
        pn = quality["product_named"][ch]
        si = quality["sender_identified"][ch]
        ino = quality["i_noticed_openers"][ch]
        print(f"\n  {ch.upper()} ({total} steps with content):")
        print(f"    Productive named:     {pn}/{total} ({100*pn/total:.0f}%)" if total else "    N/A")
        print(f"    Sender identified:    {si}/{total} ({100*si/total:.0f}%)" if total else "    N/A")
        print(f"    'I noticed' openers:  {ino}/{total} ({100*ino/total:.0f}%)" if total else "    N/A")
    
    print(f"\n  PER-STEP BREAKDOWN:")
    for sk in sorted(quality["step_analysis"].keys()):
        sa = quality["step_analysis"][sk]
        if sa["count"] == 0:
            continue
        print(f"\n    {sk} (n={sa['count']}):")
        print(f"      product named:    {sa['product_named']}/{sa['count']}")
        print(f"      sender identified:{sa['sender_identified']}/{sa['count']}")
        print(f"      'i noticed' open: {sa['i_noticed']}/{sa['count']}")
        print(f"      has approval:     {sa['has_approval']}/{sa['count']}")
        print(f"      repeats sibling:  {sa['repeats_sibling']}/{sa['count']}")
    
    # 2. Quality failures
    print(f"\n\n  QUALITY GATE FAILURES (repetition): {len(quality['quality_failures'])}")
    by_step = Counter()
    for qf in quality["quality_failures"]:
        by_step[qf["step"]] += 1
    for sk, count in by_step.most_common():
        print(f"    {sk}: {count}")
    
    # 3. Approval analysis
    print("\n\nSECTION 2: ALL APPROVALS IN THE ESTATE")
    print("-" * 50)
    all_approvals = analyze_approval_age(recs, config)
    print(f"  Total approved steps in estate: {len(all_approvals)}")
    
    by_ch = Counter()
    by_step = Counter()
    by_rec = Counter()
    for a in all_approvals:
        by_ch[a["channel"]] += 1
        by_step[a["step_key"]] += 1
        by_rec[a["record_id"]] += 1
    
    print(f"  By channel: {dict(by_ch)}")
    print(f"  By step: {dict(by_step.most_common())}")
    print(f"  By record (top 10):")
    for rec_id, count in by_rec.most_common(10):
        print(f"    {rec_id}: {count}")
    
    # 4. What would actually change?
    print("\n\nSECTION 3: WHAT WOULD REGENERATION ACTUALLY CHANGE?")
    print("-" * 50)
    change = analyze_what_regeneration_would_change(recs, config)
    
    print(f"  Approved steps that are ladder-stale: {len(change['approved_stale'])}")
    print(f"    ... also fail another gate:         {len(change['approved_also_fails_other'])}")
    print(f"    ... clean on all other gates:       {len(change['approved_clean_otherwise'])}")
    
    print(f"\n  KEY INSIGHT:")
    print(f"    Of the 83 approved steps that would be revoked:")
    print(f"    - {len(change['approved_also_fails_other'])} would be regenerated ANYWAY (they fail other gates)")
    print(f"    - {len(change['approved_clean_otherwise'])} pass all other gates and are ONLY stale on the ladder fingerprint")
    print(f"    The second group is the real cost: {len(change['approved_clean_otherwise'])} human approvals")
    print(f"    that buy nothing if the regenerated copy does not measurably beat what is stored.")
    
    # 5. Sample the clean-approved steps
    print(f"\n\n  THE {len(change['approved_clean_otherwise'])} APPROVED STEPS THAT PASS ALL OTHER GATES:")
    for a in change["approved_clean_otherwise"]:
        # Find the stored step
        for rec in recs:
            if rec["id"] != a["record_id"]:
                continue
            step_data = ((rec.get("cadence") or {}).get(a["contact"]) or {}).get(a["step"]) or {}
            ch = step_data.get("channel", "")
            if ch == "email":
                subj = (step_data.get("subject") or "")[:60]
                body = (step_data.get("body") or "")[:100]
                print(f"    {a['record_id']:35s} {a['contact']:25s} {a['step']:5s} email")
                print(f"      subject: {subj}")
                print(f"      body: {body}...")
            else:
                note = (step_data.get("note") or "")[:100]
                print(f"    {a['record_id']:35s} {a['contact']:25s} {a['step']:5s} linkedin")
                print(f"      note: {note}...")
            break


if __name__ == "__main__":
    main()
