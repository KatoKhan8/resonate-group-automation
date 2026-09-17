#!/usr/bin/env python3
"""Put GLM on real code, one function at a time, and ask it to find defeats.

    py -3 scripts/glm_review.py --target storage           # dry run
    py -3 scripts/glm_review.py --target storage --live
    py -3 scripts/glm_review.py --list

READ-ONLY apart from the report it writes. No provider write, no state change.

WHY A DIFFERENT MODEL, AND WHY ON REAL CODE. The first run of this pattern -
`glm_audit_safety.py` - found two genuine holes in copy guards that had been
written and verified by the same session, which is how `is_approved`'s
three-argument form came to compare a stored step to itself for months. A
second model reading cold cannot repeat the first one's assumptions.

It is asked for DEFEATS and CONCRETE COSTS, never for an opinion on quality.
"Is this good code" has an agreeable answer that is worth nothing. Every target
below asks for a mechanism: an input, a call order, a state, or an arithmetic
consequence at a stated scale.

ONE FUNCTION PER CALL, MEASURED. GLM-5.3 spends most of its output budget on
reasoning tokens - a two-character answer cost 29 completion tokens, 26 of them
reasoning - and an 11.5k-character prompt exceeded the adapter's 60s cap twice,
once returning an empty completion and once timing out. The adapter refused
both rather than handing back an empty string, which is correct and is why this
splits.

THE OUTPUT IS A LEAD, NOT A VERDICT. Everything it returns is checked against
the code and the tests by hand before it changes anything. A model's opinion is
evidence to investigate, never a reason to edit a safety gate - and on the one
occasion it offered to downgrade its own finding if the callers proved clean,
they did.
"""
import argparse
import datetime
import inspect
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src.providers import glm, load_env                          # noqa: E402

SYSTEM = (
    "You are an adversarial reviewer of a production cold-outreach system. "
    "You are looking for DEFEATS and MEASURABLE COSTS, not style. A finding "
    "must name a concrete input, call order, state, or arithmetic consequence "
    "at a stated scale. If you cannot construct one, say NO FINDING - that "
    "answer is worth more than a plausible-sounding guess. Be brief."
)

STORAGE_QUESTION = """This is the persistence path of a system that processes
company records. Context you need, all measured on the real estate today:

- `work/queue.jsonl` is 17,484,788 bytes over 550 records: 31.8 KB per record.
- Every benchmark in this repo assumed 4.2 KB per record.
- The pipeline checkpoints every 5 records.
- The target is 5,000 records, then 100,000, then 1,000,000.
- Evidence about a company lives INSIDE the record, keyed by record id, so the
  same company met in a second cohort reuses nothing already paid for.

Answer, briefly:
1. The arithmetic at 5,000 and at 100,000 records - bytes held, bytes written
   per full pass, and how many full-file writes a pipeline stage performs.
2. The single change with the largest ratio of benefit to risk. Not a rewrite.
3. Any CORRECTNESS or CONCURRENCY defect - two writers, a crash mid-write, a
   partial read - with the exact interleaving that causes it.
4. NO FINDING for any of the above you cannot substantiate.

--- {name} ---
{source}
"""

GENERIC_QUESTION = """This is production code from a cold-outreach system.

Answer, briefly:
1. A concrete defeat or measurable cost, or NO FINDING.
2. If there is one: the exact input, call order or state that triggers it, and
   what the consequence is.
3. The smallest fix, and what it risks.

--- {name} ---
{source}
"""


def _targets():
    """Built lazily so a broken import in one area cannot block the others."""
    from src import store, actionledger, collision
    return {
        "storage": (STORAGE_QUESTION, [
            ("store.save", store.save),
            ("store.load", store.load),
        ]),
        "ledger": (GENERIC_QUESTION, [
            ("actionledger.reserve", actionledger.reserve),
            ("actionledger.settle", actionledger.settle),
        ]),
        "collision": (GENERIC_QUESTION, [
            ("collision.check_account", collision.check_account),
            ("collision.without_our_staging", collision.without_our_staging),
        ]),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--target", default="storage")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--max-tokens", type=int, default=6000)
    # The adapter clamps this to `glm.GLM_TIMEOUT`, so asking for
    # more than the ceiling is harmless and asking for less is the
    # point of the flag. 60 was the ceiling until 2026-09-17 and
    # both storage calls timed out against it.
    parser.add_argument("--timeout", type=int, default=180)
    args = parser.parse_args(argv)

    load_env(os.path.join(ROOT, "config", ".env"))
    targets = _targets()
    if args.list:
        for name, (_q, fns) in sorted(targets.items()):
            print(f"  {name:12s} {[f[0] for f in fns]}")
        return 0
    if args.target not in targets:
        print(f"unknown target {args.target!r}; --list shows them")
        return 2

    question, functions = targets[args.target]
    prompts = [(name, question.format(name=name,
                                      source=inspect.getsource(fn)))
               for name, fn in functions]
    if not args.live:
        for name, prompt in prompts:
            print(f"  {name:28s} {len(prompt)} chars")
        print("\nDRY RUN: GLM was not called.")
        return 0

    findings = []
    for name, prompt in prompts:
        print(f"\n--- {name} ({len(prompt)} chars) ---")
        try:
            result = glm.complete(prompt, system=SYSTEM,
                                  max_tokens=args.max_tokens, timeout=args.timeout)
        except Exception as exc:
            print(f"  {type(exc).__name__}: {str(exc)[:140]}")
            findings.append((name, None, f"{type(exc).__name__}: {exc}"))
            continue
        print(f"  {result['model']} {result['seconds']}s {result['usage']}")
        # The console here is cp1250 and the model answers UTF-8; one arrow
        # once destroyed a successful call's output AFTER it was paid for.
        print(result["content"].encode("ascii", "replace")
              .decode("ascii")[:1500])
        findings.append((name, result, result["content"]))

    stamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
    out = os.path.join(ROOT, "docs",
                       f"GLM-REVIEW-{args.target.upper()}-2026-09-17.md")
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(f"# GLM adversarial review - {args.target}\n\n{stamp}. "
                 f"One call per function.\n\n")
        fh.write("A SECOND OPINION, NOT A VERDICT. Every line below is a lead "
                 "to check against the code and the tests by hand.\n\n---\n\n")
        for name, result, content in findings:
            fh.write(f"## {name}\n\n")
            fh.write(f"`{result['model']}`, {result['seconds']}s, usage "
                     f"{result['usage']}.\n\n" if result else
                     "The call did not return.\n\n")
            fh.write(content + "\n\n")
    print(f"\nwritten to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
