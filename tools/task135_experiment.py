"""TASK-135 experiment: does showing the model research facts reduce
unsupported-claim rejections?

Pick records with medium+strong research entries. For each, generate a draft
WITH the research field and WITHOUT it (all other context identical). Run
claims.check on both and compare rejection rates.

Reads from the snapshot, never writes to the queue.
"""
import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from src import claims, clients, generate, lint, llm, store


def load_snapshot(path="work/queue.snapshot.jsonl"):
    records = []
    for line in open(path, encoding="utf-8"):
        records.append(json.loads(line))
    return records


def pick_sample(records, n=8):
    """Records with medium+strong research and at least one contact."""
    candidates = []
    for rec in records:
        r = rec.get("research") or []
        contacts = rec.get("contacts") or []
        if not r or not contacts:
            continue
        usable = [e for e in r if e.get("quality") in ("medium", "strong")]
        if usable:
            candidates.append((rec, contacts[0], len(usable)))
    candidates.sort(key=lambda x: -x[2])
    return candidates[:n]


def render_without_research(step, rec, contact, client, step_key):
    """Render the prompt as it was before TASK-135: no research field."""
    ctx = generate.context_for(step, rec, contact, client, step_key)
    ctx.pop("research", None)
    context_json = json.dumps(ctx, indent=2, ensure_ascii=False)
    prompt_text = generate.prompt_text(step)
    return f"{prompt_text}\n\n{llm.fence(context_json)}"


def render_with_research(step, rec, contact, client, step_key):
    """Render the prompt with the TASK-135 research field."""
    return generate.render_prompt(step, rec, contact, client, step_key)


def hash_id(rec):
    import hashlib
    return hashlib.sha256(rec["id"].encode()).hexdigest()[:12]


def main():
    records = load_snapshot()
    sample = pick_sample(records, n=8)
    model = llm.from_env()

    print(f"Snapshot: {len(records)} records")
    print(f"Sample: {len(sample)} records with medium+strong research")
    print()

    results = []
    for rec, contact, usable_count in sample:
        client = clients.load(rec.get("client"))
        hid = hash_id(rec)
        company = rec.get("company", "?")

        # Determine the step key to use
        cadence = rec.get("cadence") or {}
        step_key = "em1"
        for c in rec.get("contacts") or []:
            if c.get("cadence"):
                steps = list((c.get("cadence") or {}).keys())
                if steps:
                    step_key = steps[0]
                break

        print(f"--- {hid} ({company}) ---")
        print(f"  Research rows: {len(rec.get('research') or [])}, "
              f"usable: {usable_count}")

        rb = generate.research_block(rec, contact)
        print(f"  research_block entries: {len(rb)}")
        if rb:
            print(f"  First fact: {rb[0]['fact'][:100]}...")

        for variant in ("without_research", "with_research"):
            if variant == "without_research":
                prompt = render_without_research(
                    "draft", rec, contact, client, step_key)
            else:
                prompt = render_with_research(
                    "draft", rec, contact, client, step_key)

            try:
                data, _, schema_err = llm.ask(model, "draft", prompt)
                if schema_err:
                    print(f"  [{variant}] SCHEMA ERROR: {schema_err}")
                    continue
                subject = data.get("subject", "")
                body = data.get("body", "")
                candidate_text = f"{subject}\n{body}"

                unsupported = claims.check(candidate_text, rec, contact)
                status = "PASS" if not unsupported else "REJECT"
                reasons = [c[:80] for c in unsupported[:3]] if unsupported else []

                print(f"  [{variant}] {status} "
                      f"(subject={len(subject)}c, body={len(body)}w)")
                if reasons:
                    for r in reasons:
                        print(f"    - {r}")
                else:
                    print(f"    subject: {subject[:60]}")
                    print(f"    body start: {body[:100]}...")
            except Exception as e:
                print(f"  [{variant}] ERROR: {e}")

        print()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
