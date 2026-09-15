#!/usr/bin/env python3
"""TASK-120: verify the 560 vs 503 discrepancy."""
import json
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src import store, clients, generate, lint


def load_snapshot():
    snap = os.path.join(store.ROOT, "work", "queue.snapshot.jsonl")
    recs = []
    with open(snap, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                recs.append(json.loads(line))
    return recs


def main():
    recs = load_snapshot()
    config = clients.load("productive")
    
    # Count stale ops from plan() directly
    total_stale_from_plan = 0
    total_linkedins_set = 0
    total_linkedins_set_replaced = 0
    
    # Count stale ops the way run() does
    total_stale_from_run = 0
    
    for rec in recs:
        ops = generate.plan(rec, config, regen_stale_ladder=True)
        
        stale_in_record = 0
        linkedin_set_in_record = 0
        for op in ops:
            if op.get("ladder_stale"):
                stale_in_record += 1
            if op.get("step") == "linkedin_set":
                linkedin_set_in_record += 1
        
        total_stale_from_plan += stale_in_record
        
        # run() counts the same way
        total_stale_from_run += stale_in_record
        
        if linkedin_set_in_record > 0:
            total_linkedins_set += linkedin_set_in_record
            # Each linkedin_set replaces some number of individual notes
            # We can figure out how many by checking the "why" field
            for op in ops:
                if op.get("step") == "linkedin_set":
                    # The why field says something like "notes pass individually but collide..."
                    pass
    
    print(f"Stale ops from plan() with ladder_stale=True: {total_stale_from_plan}")
    print(f"Stale ops from run() counting method:         {total_stale_from_run}")
    print(f"linkedin_set ops in plan() output:            {total_linkedins_set}")
    print()
    
    # Now let's see what run() actually reports
    result = generate.run(model=None, live=False, client=config, regen_stale_ladder=True)
    print(f"run() reports stale_steps: {result['stale_steps']}")
    print(f"run() reports stale_with_approval: {result['stale_with_approval']}")
    
    # The discrepancy: plan() has linkedin_set ops that replace individual linkedin_note ops.
    # When a linkedin_set op is created, the individual linkedin_note ops are REMOVED from the list.
    # So the stale count from plan() should match run().
    # Unless... the linkedin_set op itself is not counted as stale.
    
    # Let's check: how many individual linkedin_note ops were removed?
    # We need to compare plan() with and without the set consolidation.
    
    # Actually, let's just count the ops by type
    by_op_type = Counter()
    by_op_type_stale = Counter()
    for rec in recs:
        ops = generate.plan(rec, config, regen_stale_ladder=True)
        for op in ops:
            step = op.get("step", "unknown")
            by_op_type[step] += 1
            if op.get("ladder_stale"):
                by_op_type_stale[step] += 1
    
    print(f"\nAll ops by type:")
    for step, count in by_op_type.most_common():
        stale = by_op_type_stale.get(step, 0)
        print(f"  {step:20s}: {count:4d} total, {stale:4d} stale")
    
    print(f"\nSum of stale by type: {sum(by_op_type_stale.values())}")


if __name__ == "__main__":
    main()
