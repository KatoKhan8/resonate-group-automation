#!/usr/bin/env python3
"""TASK-065 full measurement. Runs all variants and saves results."""
import copy
import json
import os
import sys
import tempfile
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
os.environ["QUEUE"] = os.path.join(tempfile.gettempdir(),
                                   "task065-scratch", "queue.jsonl")

# Load LLM env
env_path = os.path.join(
    r"C:\Users\Zvonimir\Desktop\resonate-group-automation", "config", ".env")
with open(env_path, encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k, v = k.strip(), v.strip().strip('"').strip("'")
        if k.startswith("LLM_") and v:
            os.environ.setdefault(k, v)

from src import cadencelibrary, clients, generate, llm, store

RESULTS_PATH = os.path.join(tempfile.gettempdir(),
                            "task065-scratch", "results.json")
N_RECORDS = 15
N_PASSES = {"A": 2, "B": 1, "C": 1, "D": 1}


def pick_records(recs, n=N_RECORDS):
    candidates = []
    for r in recs:
        if r.get("state") in ("dropped", "pushed"):
            continue
        contacts = r.get("contacts") or []
        if not contacts:
            continue
        c = contacts[0]
        if c.get("linkedin") and c.get("angle") and c.get("persona"):
            candidates.append(r)
    return candidates[:n]


def prepare(rec):
    r = copy.deepcopy(rec)
    r.pop("cadence", None)
    if r.get("state") not in ("queued", "verified", "enriched"):
        r["state"] = "verified"
    return r


def measure(rec):
    cad = rec.get("cadence") or {}
    results = []
    for ck, steps in cad.items():
        seq_has = False
        step_data = {}
        for sk, sv in steps.items():
            if not sv.get("generated"):
                continue
            text = (sv.get("note") or "") + " " + (sv.get("body") or "")
            has_it = "productive" in text.lower()
            step_data[sk] = has_it
            if has_it:
                seq_has = True
        if step_data:
            results.append({"contact": ck, "seq_names": seq_has,
                            "steps": step_data})
    return results


def run_one_pass(records, model, client_config):
    all_meas = []
    for rec in records:
        prepared = prepare(rec)
        try:
            generate.generate_record(prepared, model, client_config)
        except Exception as e:
            all_meas.append({"record": rec["id"], "error": str(e)})
            continue
        for m in measure(prepared):
            m["record"] = rec["id"]
            all_meas.append(m)
    return all_meas


def aggregate(measurements):
    seq_total = 0
    seq_naming = 0
    step_totals = {}
    records_ok = set()
    errors = 0
    for m in measurements:
        if "error" in m:
            errors += 1
            continue
        records_ok.add(m["record"])
        seq_total += 1
        if m["seq_names"]:
            seq_naming += 1
        for sk, has_it in m["steps"].items():
            if sk not in step_totals:
                step_totals[sk] = {"total": 0, "naming": 0}
            step_totals[sk]["total"] += 1
            if has_it:
                step_totals[sk]["naming"] += 1
    return {"n_records": len(records_ok), "n_seq": seq_total,
            "seq_naming": seq_naming, "steps": step_totals,
            "errors": errors}


def apply_variant(variant):
    if variant == "A":
        return lambda: None

    if variant == "B":
        orig_li = generate.LINKEDIN_LADDER
        orig_em = generate.EMAIL_LADDER
        new_li = list(orig_li)
        new_li[3] = ("Name the product and show what it joins up. "
                     "Shape: 'we built [product] so [capability A], "
                     "[capability B] and [capability C] talk to each "
                     "other instead of living in separate tools.' "
                     "Pick the capabilities that fit this person's "
                     "angle from product.capabilities.")
        generate.LINKEDIN_LADDER = tuple(new_li)
        generate.LADDERS = {"email": generate.EMAIL_LADDER,
                            "linkedin": generate.LINKEDIN_LADDER}
        new_em = list(orig_em)
        new_em[2] = ("Name the product and show what it joins up. "
                     "Shape: 'we built [product] so [capability A], "
                     "[capability B] and [capability C] talk to each "
                     "other instead of living in separate tools.' "
                     "Pick the capabilities that fit this person's "
                     "angle from product.capabilities. Give one concrete "
                     "consequence a team their size would recognise.")
        generate.EMAIL_LADDER = tuple(new_em)
        generate.LADDERS = {"email": generate.EMAIL_LADDER,
                            "linkedin": generate.LINKEDIN_LADDER}
        def cleanup():
            generate.LINKEDIN_LADDER = orig_li
            generate.EMAIL_LADDER = orig_em
            generate.LADDERS = {"email": orig_em, "linkedin": orig_li}
        return cleanup

    if variant == "C":
        orig_fn = clients.product
        def patched(config):
            result = orig_fn(config)
            if result and "name" in result:
                result["example"] = ("we built " + result["name"] +
                                     " so budgets, time tracking and "
                                     "resourcing talk to each other")
            return result
        clients.product = patched
        return lambda: setattr(clients, "product", orig_fn) or None

    if variant == "D":
        orig_render = generate.render_prompt
        def patched(step, rec, contact=None, client=None,
                    step_key=None, sequence=None):
            result = orig_render(step, rec, contact, client,
                                 step_key, sequence)
            if step in ("draft", "linkedin_note"):
                seq = sequence or generate.sequence_for(
                    rec, client, contact)
                ch = "email" if step == "draft" else "linkedin"
                ladder = generate._resolve_ladder(ch, seq)
                product_rung = None
                for i, purpose in enumerate(ladder):
                    if "SAY WHAT THE PRODUCT" in purpose.upper():
                        product_rung = i + 1
                        break
                step_info = generate.step_block(seq, step_key, ch)
                ordinal = step_info.get("number")
                addendum = ("\n\nSEQUENCE INTEGRITY: A sequence in which "
                            "NO message names the product has failed its "
                            "job. The product rung is step " +
                            str(product_rung or "?") + " of this " + ch +
                            " ladder.")
                if ordinal == product_rung:
                    addendum += (" This IS that step - it MUST name the "
                                 "product.")
                result = result + addendum
            return result
        generate.render_prompt = patched
        return lambda: setattr(generate, "render_prompt",
                               orig_render) or None

    return lambda: None


def main():
    model = llm.from_env()
    if not model.configured():
        print("ERROR: no model configured")
        return 1

    client_config = clients.load("productive")
    recs = store.load()
    records = pick_records(recs)
    record_ids = [r["id"] for r in records]
    print(f"Model: {model.name}/{getattr(model, 'model', '?')}")
    print(f"Records: {len(records)} {record_ids}")

    all_results = {}
    for variant in ["A", "B", "C", "D"]:
        print(f"\n{'='*50}")
        print(f"VARIANT {variant}")
        print(f"{'='*50}")
        cleanup = apply_variant(variant)
        variant_passes = []
        n_passes = N_PASSES.get(variant, 2)
        for p in range(1, n_passes + 1):
            t0 = time.time()
            meas = run_one_pass(records, model, client_config)
            agg = aggregate(meas)
            elapsed = time.time() - t0
            pct = (f"{agg['seq_naming']/agg['n_seq']*100:.0f}%"
                   if agg["n_seq"] else "N/A")
            print(f"  Pass {p}: {agg['seq_naming']}/{agg['n_seq']} "
                  f"({pct}) n={agg['n_records']} recs, "
                  f"{elapsed:.0f}s, errors={agg['errors']}")
            for sk in sorted(agg["steps"].keys()):
                st = agg["steps"][sk]
                sp = (f"{st['naming']/st['total']*100:.0f}%"
                      if st["total"] else "N/A")
                print(f"    {sk}: {st['naming']}/{st['total']} ({sp})")
            variant_passes.append({"pass": p, "agg": agg,
                                   "elapsed": elapsed})
        cleanup()
        all_results[variant] = {"passes": variant_passes,
                                "record_ids": record_ids}

    # Stored baseline
    stored_meas = []
    for rec in recs:
        if not rec.get("cadence"):
            continue
        for m in measure(rec):
            m["record"] = rec["id"]
            stored_meas.append(m)
    stored_agg = aggregate(stored_meas)
    all_results["stored_baseline"] = {"agg": stored_agg}

    with open(RESULTS_PATH, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2)
    print(f"\nResults saved to {RESULTS_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
