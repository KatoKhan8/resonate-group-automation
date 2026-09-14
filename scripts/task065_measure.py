#!/usr/bin/env python3
"""TASK-065 measurement harness.

Measures whether generated sequences name the product across >=15 records
and >=2 passes per variant.  Reports per-SEQUENCE and per-step rates.

Variants:
  A  baseline (current code)
  B  product rung brief made more concrete (a SHAPE)
  C  product block carries an example sentence
  D  prompt states a sequence that never names the product has failed
"""
import copy
import json
import os
import re
import sys
import tempfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

SCRATCH_QUEUE = os.path.join(tempfile.gettempdir(), "task065-scratch",
                             "queue.jsonl")

os.environ["QUEUE"] = SCRATCH_QUEUE

from src import clients, generate, llm, store


PRODUCT_NAME = "productive"
MIN_RECORDS = 15
PASSES_PER_VARIANT = 3


def load_env():
    env_path = os.path.join(
        r"C:\Users\Zvonimir\Desktop\resonate-group-automation",
        "config", ".env")
    if not os.path.exists(env_path):
        return
    with open(env_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k, v = k.strip(), v.strip().strip('"').strip("'")
            if k.startswith("LLM_") and v:
                os.environ.setdefault(k, v)


def pick_records(recs, n=MIN_RECORDS):
    """Pick records with contacts that have LinkedIn + angle + persona."""
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


def prepare_record(rec):
    """Deep-copy a record and clear its cadence so generation runs fresh."""
    r = copy.deepcopy(rec)
    r.pop("cadence", None)
    if r.get("state") not in ("queued", "verified", "enriched"):
        r["state"] = "verified"
    return r


def names_product(text):
    return PRODUCT_NAME in (text or "").lower()


def measure_sequence(rec, client_config):
    """Per-step and per-sequence product naming for one generated record."""
    cad = rec.get("cadence") or {}
    contact_keys = list(cad.keys())
    results = []
    for ck in contact_keys:
        steps = cad[ck]
        seq_has_product = False
        step_results = {}
        for sk, sv in steps.items():
            if not sv.get("generated"):
                continue
            text = (sv.get("note") or "") + " " + (sv.get("body") or "")
            has_it = names_product(text)
            step_results[sk] = {"names_product": has_it,
                                "text_len": len(text.strip())}
            if has_it:
                seq_has_product = True
        if step_results:
            results.append({"contact": ck,
                            "sequence_names": seq_has_product,
                            "steps": step_results})
    return results


def run_pass(records, client_config, model, variant="A"):
    """One generation pass across all records. Returns measurement list."""
    all_results = []
    for rec in records:
        prepared = prepare_record(rec)
        try:
            generate.generate_record(prepared, model, client_config)
        except Exception as e:
            all_results.append({"record": rec["id"], "error": str(e)})
            continue
        meas = measure_sequence(prepared, client_config)
        for m in meas:
            m["record"] = rec["id"]
            m["variant"] = variant
        all_results.extend(meas)
    return all_results


def aggregate(results):
    """Aggregate measurement results into per-step and per-sequence rates."""
    step_totals = {}
    seq_total = 0
    seq_naming = 0
    records_measured = set()
    errors = 0
    for r in results:
        if "error" in r:
            errors += 1
            continue
        records_measured.add(r["record"])
        seq_total += 1
        if r["sequence_names"]:
            seq_naming += 1
        for sk, sv in r["steps"].items():
            if sk not in step_totals:
                step_totals[sk] = {"total": 0, "naming": 0}
            step_totals[sk]["total"] += 1
            if sv["names_product"]:
                step_totals[sk]["naming"] += 1
    seq_rate = f"{seq_naming}/{seq_total}" if seq_total else "0/0"
    seq_pct = f"{seq_naming/seq_total*100:.0f}%" if seq_total else "N/A"
    return {
        "n_records": len(records_measured),
        "n_sequences": seq_total,
        "seq_naming": seq_naming,
        "seq_rate": seq_rate,
        "seq_pct": seq_pct,
        "step_totals": step_totals,
        "errors": errors,
    }


def apply_variant(variant, client_config):
    """Apply variant modifications to the client config or generate module.

    Returns a cleanup function to restore original state.
    """
    if variant == "A":
        return lambda: None

    if variant == "B":
        # Make the product rung's brief more concrete - a SHAPE
        # The LinkedIn ladder rung 4 and email ladder rung 3 are the product
        # rungs. Replace their instructions with a concrete shape.
        original_li = generate.LINKEDIN_DEFAULT_LADDER
        original_em = generate.EMAIL_FIVE_LADDER

        new_li = list(original_li)
        new_li[3] = (
            "Name the product and show what it joins up. Shape: "
            "'we built [product] so [capability A], [capability B] and "
            "[capability C] talk to each other instead of living in "
            "separate tools.' Pick the capabilities that fit this person's "
            "angle from product.capabilities."
        )
        generate.LINKEDIN_DEFAULT_LADDER = tuple(new_li)

        new_em = list(original_em)
        new_em[2] = (
            "Name the product and show what it joins up. Shape: "
            "'we built [product] so [capability A], [capability B] and "
            "[capability C] talk to each other instead of living in "
            "separate tools.' Pick the capabilities that fit this person's "
            "angle from product.capabilities. Give one concrete consequence "
            "a team their size would recognise."
        )
        generate.EMAIL_FIVE_LADDER = tuple(new_em)

        def cleanup():
            generate.LINKEDIN_DEFAULT_LADDER = original_li
            generate.EMAIL_FIVE_LADDER = original_em
        return cleanup

    if variant == "C":
        # Add an example sentence to the product block
        original_product_func = clients.product

        def patched_product(config):
            result = original_product_func(config)
            if result and "name" in result:
                result["example"] = (
                    f"we built {result['name']} so budgets, time tracking "
                    f"and resourcing talk to each other"
                )
            return result

        clients.product = patched_product

        def cleanup():
            clients.product = original_product_func
        return cleanup

    if variant == "D":
        # Add a sequence-level instruction to the prompt
        original_render = generate.render_prompt

        def patched_render(step, rec, contact=None, client=None,
                           step_key=None, sequence=None):
            result = original_render(step, rec, contact, client,
                                     step_key, sequence)
            if step in ("draft", "linkedin_note"):
                seq = sequence or generate.sequence_for(
                    rec, client, contact)
                # Find which step owns the product rung
                from src import cadencelibrary
                ladder = generate._resolve_ladder(
                    "email" if step == "draft" else "linkedin", seq)
                product_rung = None
                for i, purpose in enumerate(ladder):
                    if "SAY WHAT THE PRODUCT" in purpose.upper():
                        product_rung = i + 1
                        break
                channel = "email" if step == "draft" else "linkedin"
                step_info = generate.step_block(seq, step_key, channel)
                ordinal = step_info.get("number")
                addendum = (
                    "\n\nSEQUENCE INTEGRITY: A sequence in which NO message "
                    "names the product has failed its job. The product rung "
                    f"is step {product_rung or '?' } of this {channel} "
                    f"ladder. If this is step {ordinal}, it owns that job."
                )
                result = result + addendum
            return result

        generate.render_prompt = patched_render

        def cleanup():
            generate.render_prompt = original_render
        return cleanup

    return lambda: None


def main():
    load_env()

    model = llm.from_env()
    if not model.configured():
        print("ERROR: no model configured")
        return 1

    print(f"Model: {model.name} / {getattr(model, 'model', '?')}")

    client_config = clients.load("productive")
    product_info = clients.product(client_config)
    print(f"Product name: {product_info.get('name', '?')}")

    recs = store.load()
    records = pick_records(recs, n=20)
    print(f"Selected {len(records)} records for measurement")
    print(f"Record IDs: {[r['id'] for r in records]}")
    print()

    variants = ["A", "B", "C", "D"]
    all_results = {}

    for variant in variants:
        print(f"{'='*60}")
        print(f"VARIANT {variant}")
        print(f"{'='*60}")
        cleanup = apply_variant(variant, client_config)
        variant_results = []
        for pass_num in range(1, PASSES_PER_VARIANT + 1):
            print(f"\n  Pass {pass_num}/{PASSES_PER_VARIANT}...")
            results = run_pass(records, client_config, model, variant)
            agg = aggregate(results)
            print(f"    Sequences naming product: "
                  f"{agg['seq_rate']} ({agg['seq_pct']})")
            print(f"    Records measured: {agg['n_records']}, "
                  f"errors: {agg['errors']}")
            for sk in sorted(agg["step_totals"].keys()):
                st = agg["step_totals"][sk]
                pct = f"{st['naming']/st['total']*100:.0f}%" if st["total"] \
                    else "N/A"
                print(f"    {sk}: {st['naming']}/{st['total']} ({pct})")
            variant_results.append({"pass": pass_num, "agg": agg,
                                    "raw": results})
        cleanup()
        all_results[variant] = variant_results
        print()

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    for variant in variants:
        print(f"\nVariant {variant}:")
        for pr in all_results[variant]:
            agg = pr["agg"]
            print(f"  Pass {pr['pass']}: {agg['seq_rate']} "
                  f"({agg['seq_pct']}) "
                  f"n={agg['n_records']} records, "
                  f"{agg['n_sequences']} sequences")

    # Also print the stored baseline for comparison
    print("\n\nStored baseline (already-generated data):")
    stored_results = []
    for rec in recs:
        if not rec.get("cadence"):
            continue
        meas = measure_sequence(rec, client_config)
        for m in meas:
            m["record"] = rec["id"]
        stored_results.extend(meas)
    stored_agg = aggregate(stored_results)
    print(f"  Sequences naming product: "
          f"{stored_agg['seq_rate']} ({stored_agg['seq_pct']})")
    print(f"  n={stored_agg['n_records']} records, "
          f"{stored_agg['n_sequences']} sequences")
    for sk in sorted(stored_agg["step_totals"].keys()):
        st = stored_agg["step_totals"][sk]
        pct = f"{st['naming']/st['total']*100:.0f}%" if st["total"] \
            else "N/A"
        print(f"  {sk}: {st['naming']}/{st['total']} ({pct})")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
