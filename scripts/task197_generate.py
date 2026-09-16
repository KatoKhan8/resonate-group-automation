#!/usr/bin/env python3
"""TASK-197: Run generation on the 15 verified records with no cadence.

Loads records from the snapshot, runs generation in memory (no writes to
any queue file), and reports per-record, per-step results including lint
and claims verdicts, plus token cost.
"""
import copy
import hashlib
import json
import os
import sys
import time

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src import (claims, clients, generate, lint, llm, store,
                 events, cadence as cadence_mod)

SNAPSHOT = os.path.join(os.path.dirname(__file__), "..", "work", "queue.snapshot.jsonl")

TARGET_IDS = [
    "8ms-com", "backbone-media", "wearejsa-com", "yesandagency-com",
    "feddirect-com", "chicochamber-com", "directmail-com",
    "seismicproductions-com", "ritway-com", "thecommunity-ca",
    "adc-de", "skyad-com", "invnt-com", "inmobi-com", "eliassen-com",
]


def load_snapshot():
    recs = []
    with open(SNAPSHOT, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                recs.append(json.loads(line))
    return recs


def hash_id(rec_id):
    return hashlib.sha256(rec_id.encode("utf-8")).hexdigest()[:12]


def hash_contact_key(ck):
    return hashlib.sha256(ck.encode("utf-8")).hexdigest()[:10]


def check_step_gates(rec, contact, step_key, step_data, client=None):
    """Run lint + claims + quality on a step and return verdict."""
    key = lint.contact_key(contact)
    result = {"lint": [], "claims": [], "quality": [], "passed": True}

    # Lint
    if step_data.get("channel") == "linkedin":
        failures = [f for f in lint.check_step(rec, key, step_data)
                    if f not in lint.LINKEDIN_HELD_CODES]
        result["lint"] = failures
        if lint.classify_linkedin(failures) == "failed":
            result["passed"] = False
    else:
        failures = lint.check_step(rec, key, step_data)
        result["lint"] = failures
        if lint.classify(failures) == "failed":
            result["passed"] = False

    # Claims
    if step_data.get("channel") == "linkedin":
        text = step_data.get("note") or ""
    else:
        text = f"{step_data.get('subject') or ''}\n{step_data.get('body') or ''}"
    unsupported = claims.check(text, rec, contact)
    result["claims"] = [{"sentence": c.get("sentence", "")[:80],
                         "why": c.get("why", "")[:80]}
                        for c in (unsupported or [])[:3]]
    if unsupported:
        result["passed"] = False

    # Foreign product
    if client:
        invented = claims.foreign_product(text, clients.product(client), rec)
        if invented:
            result["claims"].extend(
                [{"sentence": c.get("sentence", "")[:80],
                  "why": "foreign_product: " + c.get("why", "")[:60]}
                 for c in invented[:2]])
            result["passed"] = False

    return result


def main():
    print("=" * 80)
    print("TASK-197: GENERATION RUN ON 15 VERIFIED RECORDS")
    print("=" * 80)

    recs = load_snapshot()
    targets = [r for r in recs if r["id"] in TARGET_IDS]
    print(f"\nSnapshot: {len(recs)} records, {len(targets)} targets found")

    if len(targets) != 15:
        found_ids = {r["id"] for r in targets}
        missing = set(TARGET_IDS) - found_ids
        print(f"WARNING: expected 15, got {len(targets)}. Missing: {missing}")

    model = llm.from_env()
    print(f"Model: {getattr(model, 'name', '?')} ({type(model).__name__})")

    # Track total token usage
    total_tokens = {"prompt": 0, "completion": 0, "total": 0, "cost_usd": 0.0}
    per_record_tokens = {}
    per_record_results = {}

    generate.clear_company_cache()

    for i, rec in enumerate(targets, 1):
        hid = hash_id(rec["id"])
        company = rec.get("company", "?")
        domain = rec.get("domain", "?")
        print(f"\n{'=' * 80}")
        print(f"  [{i}/15] {company} ({domain})  hash=[{hid}]")
        print(f"{'=' * 80}")

        # Deep copy so we don't mutate the snapshot objects
        work_rec = copy.deepcopy(rec)

        # Load client config
        client = None
        try:
            client = clients.load(work_rec.get("client"))
        except Exception:
            pass

        # Plan first
        ops = generate.plan(work_rec, client)
        print(f"  Plan: {len(ops)} op(s)")
        for op in ops:
            detail = f" [{op.get('contact', '?')}"
            if op.get("day"):
                detail += f" {op['day']}"
            detail += "]"
            print(f"    {op['step']:<16}{detail:<35} {op.get('why', '')}")

        if not ops:
            print("  NOTHING TO GENERATE")
            per_record_results[rec["id"]] = {"ops": 0, "steps": {}}
            continue

        # Snapshot token counters before
        prev_calls = dict(generate.model_calls)

        # Run generation
        t0 = time.time()
        try:
            done = generate.generate_record(work_rec, model, client)
        except llm.NoModelConfigured:
            print("  ERROR: No model configured")
            per_record_results[rec["id"]] = {"error": "no_model"}
            continue
        except llm.ModelError as e:
            print(f"  ERROR: Model error: {e}")
            per_record_results[rec["id"]] = {"error": str(e)[:100]}
            continue
        except Exception as e:
            print(f"  ERROR: Unexpected: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            per_record_results[rec["id"]] = {"error": str(e)[:100]}
            continue
        elapsed = time.time() - t0

        # Check what happened to the record state
        print(f"  Record state after: {work_rec.get('state')}")
        if work_rec.get("hold_reason"):
            print(f"  Hold reason: {work_rec.get('hold_reason')}")
        # Check last log entries
        log = work_rec.get("log") or []
        if log:
            last = log[-1]
            print(f"  Last log: step={last.get('step')} note={str(last.get('note',''))[:80]}")

        print(f"  Generated {len(done)} op(s) in {elapsed:.1f}s")

        # Now check every step in the cadence
        cadence = work_rec.get("cadence") or {}
        step_results = {}
        for contact_key, steps in cadence.items():
            hck = hash_contact_key(contact_key)
            contact = None
            for c in work_rec.get("contacts") or []:
                if lint.contact_key(c) == contact_key:
                    contact = c
                    break
            if not contact:
                continue

            for step_key, step_data in steps.items():
                if not isinstance(step_data, dict):
                    continue
                channel = step_data.get("channel", "?")
                has_body = bool(step_data.get("body") or step_data.get("note"))
                if not has_body:
                    continue

                gates = check_step_gates(work_rec, contact, step_key,
                                         step_data, client)
                step_id = f"{hck}:{step_key}"
                step_results[step_id] = {
                    "channel": channel,
                    "generated": step_data.get("generated", False),
                    "lint_pass": not gates["lint"] or (
                        gates["lint"] and (
                            lint.classify(gates["lint"]) != "failed"
                            if channel == "email"
                            else lint.classify_linkedin(gates["lint"]) != "failed"
                        )
                    ),
                    "lint_failures": gates["lint"],
                    "claims_pass": not gates["claims"],
                    "claims_issues": gates["claims"],
                    "overall_pass": gates["passed"],
                }

                status = "PASS" if gates["passed"] else "FAIL"
                detail = ""
                if channel == "email":
                    subj = (step_data.get("subject") or "")[:50]
                    detail = f" subj='{subj}'"
                else:
                    note = (step_data.get("note") or "")[:50]
                    detail = f" note='{note}'"

                lint_str = ""
                if gates["lint"]:
                    lint_str = f" lint=[{','.join(gates['lint'][:3])}]"
                claims_str = ""
                if gates["claims"]:
                    claims_str = f" claims={len(gates['claims'])} issue(s)"

                print(f"    [{status}] {step_id} ({channel}){detail}{lint_str}{claims_str}")

        per_record_results[rec["id"]] = {
            "hash": hid,
            "company": company,
            "domain": domain,
            "ops_planned": len(ops),
            "ops_done": len(done),
            "steps": step_results,
            "elapsed_s": round(elapsed, 1),
        }

        # Token delta
        new_calls = dict(generate.model_calls)
        delta = {}
        for k in set(list(new_calls.keys()) + list(prev_calls.keys())):
            d = new_calls.get(k, 0) - prev_calls.get(k, 0)
            if d > 0:
                delta[k] = d
        per_record_tokens[rec["id"]] = delta
        if delta:
            print(f"  Model calls: {delta}")

    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)

    total_pass = 0
    total_fail = 0
    total_steps = 0
    needs_approval = []
    needs_regeneration = []
    needs_evidence = []

    for rec_id, result in per_record_results.items():
        if "error" in result:
            continue
        steps = result.get("steps", {})
        for step_id, s in steps.items():
            total_steps += 1
            if s["overall_pass"]:
                total_pass += 1
                needs_approval.append((result["hash"], step_id, s["channel"]))
            else:
                total_fail += 1
                if s["claims_issues"]:
                    needs_evidence.append((result["hash"], step_id, s["claims_issues"]))
                elif not s["lint_pass"]:
                    needs_regeneration.append((result["hash"], step_id, s["lint_failures"]))

    print(f"\n  Total steps generated: {total_steps}")
    print(f"  Pass both gates: {total_pass}")
    print(f"  Fail at least one gate: {total_fail}")
    print(f"\n  Need human approval (pass both): {len(needs_approval)}")
    print(f"  Need regeneration (lint fail): {len(needs_regeneration)}")
    print(f"  Need different evidence (claims fail): {len(needs_evidence)}")

    if needs_regeneration:
        print("\n  LINT FAILURES (need regeneration):")
        for hid, step_id, failures in needs_regeneration:
            print(f"    [{hid}] {step_id}: {failures[:3]}")

    if needs_evidence:
        print("\n  CLAIMS FAILURES (need different evidence):")
        for hid, step_id, issues in needs_evidence:
            for iss in issues[:2]:
                print(f"    [{hid}] {step_id}: {iss.get('why', '?')[:80]}")

    # Model call summary
    print(f"\n  MODEL CALLS BY STEP:")
    for step, count in sorted(generate.model_calls.items()):
        print(f"    {step}: {count}")

    total_calls = sum(generate.model_calls.values())
    print(f"    TOTAL: {total_calls}")

    # Write results to a JSON file for the report
    output = {
        "snapshot_stamp": "2026-09-15T17:52:12+00:00 from master cf23154 550 records",
        "target_count": len(targets),
        "model": getattr(model, "name", "?"),
        "total_steps": total_steps,
        "pass_both_gates": total_pass,
        "fail_at_least_one": total_fail,
        "needs_approval": len(needs_approval),
        "needs_regeneration": len(needs_regeneration),
        "needs_evidence": len(needs_evidence),
        "total_model_calls": total_calls,
        "model_calls_by_step": dict(generate.model_calls),
        "per_record": {},
    }
    for rec_id, result in per_record_results.items():
        hid = result.get("hash", hash_id(rec_id))
        output["per_record"][hid] = result

    out_path = os.path.join(os.path.dirname(__file__), "..",
                            "work", "task197_results.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False, default=str)
    print(f"\n  Results written to: {out_path}")


if __name__ == "__main__":
    main()
