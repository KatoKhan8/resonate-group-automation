#!/usr/bin/env python3
"""TASK-120 analysis: what are the 503 steps and 83 approvals?

Dry run only. Reads the queue snapshot, runs plan() with regen_stale_ladder,
and produces a detailed breakdown.
"""
import json
import os
import sys
import hashlib
from collections import Counter, defaultdict

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src import store, clients, generate, approval, lint, cadencelibrary


def load_snapshot():
    """Load the queue snapshot."""
    snap = os.path.join(store.ROOT, "work", "queue.snapshot.jsonl")
    recs = []
    with open(snap, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                recs.append(json.loads(line))
    return recs


def analyze_stale_steps(recs, config):
    """Break down the 503 stale steps by channel, step position, record, and WHY."""
    
    # Counters
    by_channel = Counter()
    by_step_key = Counter()
    by_why = Counter()
    by_record_state = Counter()
    by_channel_and_step = Counter()
    by_why_category = Counter()  # "no_fingerprint" vs "fingerprint_mismatch" vs "other_gate_failure"
    
    # Per-record detail
    records_with_stale = []
    
    # Track which ops are ladder_stale vs other failures
    stale_ops = []
    non_stale_ops = []
    
    for rec in recs:
        ops = generate.plan(rec, config, regen_stale_ladder=True)
        stale_for_record = []
        for op in ops:
            channel = None
            step_key = op.get("day", "")
            
            # Determine channel from step_key
            if step_key.startswith("li"):
                channel = "linkedin"
            elif step_key.startswith("em"):
                channel = "email"
            elif op.get("step") == "linkedin_note" or op.get("step") == "linkedin_set":
                channel = "linkedin"
            elif op.get("step") == "draft":
                channel = "email"
            
            if channel:
                by_channel[channel] += 1
            by_step_key[step_key] += 1
            if channel and step_key:
                by_channel_and_step[(channel, step_key)] += 1
            
            why = op.get("why", "")
            by_why[why[:80]] += 1
            by_record_state[rec.get("state", "unknown")] += 1
            
            if op.get("ladder_stale"):
                # Check if it has a fingerprint or not
                ck = None
                for c in (rec.get("contacts") or []):
                    if op.get("contact") in (c.get("name"), c.get("key")):
                        ck = c.get("key")
                        break
                if ck is None:
                    ck = lint.contact_key({"name": op.get("contact", ""), "key": op.get("contact", "")})
                
                stored_step = ((rec.get("cadence") or {}).get(ck) or {}).get(step_key) or {}
                has_fp = bool(stored_step.get("ladder_fingerprint"))
                
                if has_fp:
                    by_why_category["fingerprint_mismatch"] += 1
                else:
                    by_why_category["no_fingerprint_predates_task083"] += 1
                
                stale_ops.append({
                    "record_id": rec["id"],
                    "state": rec.get("state"),
                    "contact": op.get("contact"),
                    "step": step_key,
                    "channel": channel,
                    "has_fingerprint": has_fp,
                    "why": why,
                })
            else:
                # Non-stale ops: other gate failures that also need regen
                non_stale_ops.append({
                    "record_id": rec["id"],
                    "state": rec.get("state"),
                    "contact": op.get("contact"),
                    "step": step_key,
                    "channel": channel,
                    "why": why,
                })
            
            stale_for_record.append(op)
        
        if stale_for_record:
            records_with_stale.append({
                "id": rec["id"],
                "state": rec.get("state"),
                "n_ops": len(stale_for_record),
            })
    
    return {
        "by_channel": by_channel,
        "by_step_key": by_step_key,
        "by_channel_and_step": by_channel_and_step,
        "by_why_category": by_why_category,
        "by_record_state": by_record_state,
        "records_with_stale": records_with_stale,
        "stale_ops": stale_ops,
        "non_stale_ops": non_stale_ops,
        "total_stale": len(stale_ops),
        "total_non_stale": len(non_stale_ops),
    }


def analyze_approvals(recs, config):
    """Break down the 83 approvals that would be revoked."""
    
    approvals_detail = []
    
    for rec in recs:
        ops = generate.plan(rec, config, regen_stale_ladder=True)
        for op in ops:
            if not op.get("ladder_stale"):
                continue
            
            ck = None
            for c in (rec.get("contacts") or []):
                if op.get("contact") in (c.get("name"), c.get("key")):
                    ck = c.get("key")
                    break
            if ck is None:
                ck = lint.contact_key({"name": op.get("contact", ""), "key": op.get("contact", "")})
            
            step_key = op.get("day", "")
            step_data = ((rec.get("cadence") or {}).get(ck) or {}).get(step_key) or {}
            
            appr = step_data.get("approval")
            if appr and approval.is_approved(rec, ck, step_key, step_data):
                approvals_detail.append({
                    "record_id": rec["id"],
                    "state": rec.get("state"),
                    "contact_key": ck,
                    "step_key": step_key,
                    "channel": step_data.get("channel", "unknown"),
                    "approved_by": appr.get("by", "unknown"),
                    "approved_at": appr.get("at", "unknown"),
                    "fingerprint": appr.get("fingerprint", "")[:16],
                    "has_stored_body": bool(step_data.get("body") or step_data.get("note")),
                })
    
    return approvals_detail


def analyze_fingerprint_status(recs, config):
    """Check whether ANY stored step has a fingerprint."""
    
    total_steps = 0
    steps_with_fp = 0
    steps_without_fp = 0
    channels_with_fp = Counter()
    channels_without_fp = Counter()
    
    for rec in recs:
        cadence_data = rec.get("cadence") or {}
        for contact_key, steps in cadence_data.items():
            if not isinstance(steps, dict):
                continue
            for step_key, step_data in steps.items():
                if not isinstance(step_data, dict):
                    continue
                if not (step_data.get("body") or step_data.get("note")):
                    continue
                total_steps += 1
                fp = step_data.get("ladder_fingerprint")
                channel = step_data.get("channel", "unknown")
                if fp:
                    steps_with_fp += 1
                    channels_with_fp[channel] += 1
                else:
                    steps_without_fp += 1
                    channels_without_fp[channel] += 1
    
    return {
        "total_steps_with_content": total_steps,
        "steps_with_fingerprint": steps_with_fp,
        "steps_without_fingerprint": steps_without_fp,
        "channels_with_fp": dict(channels_with_fp),
        "channels_without_fp": dict(channels_without_fp),
    }


def sample_stale_steps(recs, config, n=10):
    """Sample stale steps and show what they currently hold."""
    
    samples = []
    for rec in recs:
        if len(samples) >= n:
            break
        ops = generate.plan(rec, config, regen_stale_ladder=True)
        for op in ops:
            if len(samples) >= n:
                break
            if not op.get("ladder_stale"):
                continue
            
            ck = None
            for c in (rec.get("contacts") or []):
                if op.get("contact") in (c.get("name"), c.get("key")):
                    ck = c.get("key")
                    break
            if ck is None:
                ck = lint.contact_key({"name": op.get("contact", ""), "key": op.get("contact", "")})
            
            step_key = op.get("day", "")
            step_data = ((rec.get("cadence") or {}).get(ck) or {}).get(step_key) or {}
            
            if not (step_data.get("body") or step_data.get("note")):
                continue
            
            # Get the sequence for this contact
            contact = None
            for c in (rec.get("contacts") or []):
                if c.get("key") == ck:
                    contact = c
                    break
            
            sequence = generate.sequence_for(rec, config, contact) if contact else None
            channel = step_data.get("channel", "unknown")
            _, ordinal, total = generate.position(sequence, step_key) if sequence else (None, None, None)
            current_purpose = generate.purpose_for(channel, ordinal, sequence=sequence) if ordinal else None
            
            sample = {
                "record_id": rec["id"],
                "contact": ck,
                "step_key": step_key,
                "channel": channel,
                "ordinal": ordinal,
                "current_purpose": current_purpose,
                "has_fingerprint": bool(step_data.get("ladder_fingerprint")),
                "stored_fingerprint": (step_data.get("ladder_fingerprint") or "")[:16],
                "approval": step_data.get("approval") is not None,
            }
            
            if channel == "email":
                sample["subject"] = (step_data.get("subject") or "")[:80]
                sample["body_preview"] = (step_data.get("body") or "")[:200]
            else:
                sample["note_preview"] = (step_data.get("note") or "")[:200]
            
            samples.append(sample)
    
    return samples


def main():
    print("TASK-120 ANALYSIS: What exactly would a regeneration change?")
    print("=" * 70)
    
    # Load data
    recs = load_snapshot()
    print(f"\nLoaded {len(recs)} records from snapshot")
    
    # Load client config
    config = clients.load("productive")
    print(f"Client config: productive")
    
    # Get the sequence info
    seq = cadencelibrary.named("productive_li_heavy_v1")
    if seq:
        print(f"Sequence: productive_li_heavy_v1")
        print(f"  Steps: {len(seq)}")
        for s in seq:
            print(f"    {s['key']:6s} day={s['day']:3d}  channel={s['channel']:10s}  generated={s.get('generated', False)}")
    
    # 1. FINGERPRINT STATUS
    print("\n" + "=" * 70)
    print("SECTION 1: FINGERPRINT STATUS - does any stored step have one?")
    print("=" * 70)
    fp_status = analyze_fingerprint_status(recs, config)
    print(f"  Total stored steps with content: {fp_status['total_steps_with_content']}")
    print(f"  Steps WITH fingerprint:          {fp_status['steps_with_fingerprint']}")
    print(f"  Steps WITHOUT fingerprint:       {fp_status['steps_without_fingerprint']}")
    print(f"  Channels with FP:    {fp_status['channels_with_fp']}")
    print(f"  Channels without FP: {fp_status['channels_without_fp']}")
    
    # 2. STALE STEPS BREAKDOWN
    print("\n" + "=" * 70)
    print("SECTION 2: THE 503 STALE STEPS - breakdown")
    print("=" * 70)
    analysis = analyze_stale_steps(recs, config)
    
    print(f"\n  Total stale ops (ladder_stale=True): {analysis['total_stale']}")
    print(f"  Total non-stale ops (other failures): {analysis['total_non_stale']}")
    print(f"  Grand total ops: {analysis['total_stale'] + analysis['total_non_stale']}")
    
    print(f"\n  BY CHANNEL:")
    for ch, count in analysis['by_channel'].most_common():
        print(f"    {ch:12s}: {count}")
    
    print(f"\n  BY STEP KEY:")
    for sk, count in analysis['by_step_key'].most_common():
        print(f"    {sk:6s}: {count}")
    
    print(f"\n  BY CHANNEL x STEP:")
    for (ch, sk), count in sorted(analysis['by_channel_and_step'].items()):
        print(f"    {ch:12s} {sk:6s}: {count}")
    
    print(f"\n  BY WHY CATEGORY:")
    for cat, count in analysis['by_why_category'].most_common():
        print(f"    {cat}: {count}")
    
    print(f"\n  BY RECORD STATE:")
    for state, count in analysis['by_record_state'].most_common():
        print(f"    {state:12s}: {count}")
    
    print(f"\n  RECORDS WITH STALE STEPS: {len(analysis['records_with_stale'])}")
    
    # Non-stale ops breakdown
    print(f"\n  NON-STALE OPS (other gate failures, also need regen):")
    non_stale_by_why = Counter()
    non_stale_by_channel = Counter()
    for op in analysis['non_stale_ops']:
        non_stale_by_why[op['why'][:80]] += 1
        if op['channel']:
            non_stale_by_channel[op['channel']] += 1
    for ch, count in non_stale_by_channel.most_common():
        print(f"    channel {ch}: {count}")
    print(f"    By reason:")
    for why, count in non_stale_by_why.most_common(10):
        print(f"      {why}: {count}")
    
    # 3. APPROVALS BREAKDOWN
    print("\n" + "=" * 70)
    print("SECTION 3: THE 83 APPROVALS - which records, which steps?")
    print("=" * 70)
    approvals = analyze_approvals(recs, config)
    print(f"\n  Total approvals that would be revoked: {len(approvals)}")
    
    by_record = Counter()
    by_step = Counter()
    by_channel = Counter()
    by_state = Counter()
    
    for a in approvals:
        by_record[a['record_id']] += 1
        by_step[a['step_key']] += 1
        by_channel[a['channel']] += 1
        by_state[a['state']] += 1
    
    print(f"\n  BY RECORD (top 20):")
    for rec_id, count in by_record.most_common(20):
        print(f"    {rec_id}: {count}")
    
    print(f"\n  BY STEP KEY:")
    for sk, count in by_step.most_common():
        print(f"    {sk}: {count}")
    
    print(f"\n  BY CHANNEL:")
    for ch, count in by_channel.most_common():
        print(f"    {ch}: {count}")
    
    print(f"\n  BY RECORD STATE:")
    for state, count in by_state.most_common():
        print(f"    {state}: {count}")
    
    # Show individual approvals
    print(f"\n  INDIVIDUAL APPROVALS:")
    for a in approvals:
        print(f"    {a['record_id']:35s} {a['contact_key']:25s} {a['step_key']:5s} "
              f"ch={a['channel']:10s} by={a['approved_by']:6s} at={a['approved_at'][:19]}")
    
    # 4. SAMPLE STALE STEPS
    print("\n" + "=" * 70)
    print("SECTION 4: SAMPLE OF STALE STEPS - what is currently stored?")
    print("=" * 70)
    samples = sample_stale_steps(recs, config, n=15)
    for i, s in enumerate(samples):
        print(f"\n  Sample {i+1}: {s['record_id']} / {s['contact']} / {s['step_key']}")
        print(f"    channel={s['channel']}  ordinal={s['ordinal']}  has_fp={s['has_fingerprint']}")
        print(f"    purpose={s.get('current_purpose', 'N/A')}")
        print(f"    approved={s['approval']}")
        if s['channel'] == 'email':
            print(f"    subject: {s.get('subject', '')}")
            body = s.get('body_preview', '')
            print(f"    body: {body[:150]}...")
        else:
            note = s.get('note_preview', '')
            print(f"    note: {note[:150]}...")
    
    # 5. LADDER PURPOSES
    print("\n" + "=" * 70)
    print("SECTION 5: CURRENT LADDER PURPOSES")
    print("=" * 70)
    
    # Get the sequence
    if seq:
        for spec in seq:
            channel = spec.get("channel")
            same = [s for s in seq if s.get("channel") == channel]
            keys = [s.get("key") for s in same]
            ordinal = keys.index(spec["key"]) + 1
            purpose = generate.purpose_for(channel, ordinal, sequence=seq)
            fp = generate.ladder_fingerprint(channel, ordinal, sequence=seq)
            print(f"  {spec['key']:6s} {channel:10s} ordinal={ordinal} purpose={purpose}")
            print(f"         fingerprint={fp}")


if __name__ == "__main__":
    main()
