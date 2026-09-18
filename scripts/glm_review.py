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


JOURNAL_QUESTION = """This is an append-only delta log intended to replace a
whole-file rewrite on the checkpoint path of a production outreach system. It
is NOT WIRED yet - this review is why.

Context, all measured:

- Today `store.save` rewrites every record on every checkpoint. At 5,000
  records and 1,000 checkpoints that is 4.4 GB and 211 seconds.
- `store.save` also READS the whole file each checkpoint, to run a digest
  check and two guards: one refusing to drop paid verification evidence, one
  refusing to rewrite event history.
- Checkpoints happen every 5 records. Several processes may run concurrently;
  the existing path holds a file lock and takes an optimistic digest.
- A crash must leave a readable queue. This file holds 300 real companies.

Answer, briefly and concretely:
1. An interleaving of TWO processes appending and/or compacting that loses a
   record, resurrects an old value, or produces a state neither wrote. Give
   the exact order of operations.
2. What breaks if a process dies between writing a compacted base file and
   calling `discard` - and what breaks if it dies between `discard` and the
   base write.
3. Whether `replay`'s last-write-wins can silently revert a record when two
   processes checkpoint overlapping record sets from different reads.
4. Anything about fsync, os.replace, or append atomicity on Windows that
   makes the crash-safety claim in the docstring false.
5. NO FINDING for any of the above you cannot substantiate with a mechanism.

--- {name} ---
{source}
"""


ACTIVATION_QUESTION = """This is the permission layer of a cold-outreach
system, and these functions are the last thing between a staged campaign and
real emails reaching real people at a third-party provider (EmailBison).

Context you need, all of it true today:

- Activation is granted per CANONICAL ROW, not per channel. Two independent
  tables must BOTH agree: `providerwrites._AUTHORIZED_EMAIL_CAMPAIGNS` says
  which provider campaign a named row may reach, and
  `executionguard.LIVE_ACTIVATION_GRANTS` says whether an operator granted the
  ACT at all.
- The provider slot in each allowlist entry is None, meaning "resolve the
  expected provider campaign id from `bison_campaign_id` on the named row".
  So the allowlist is only as safe as that field on a mutable local file.
- `_NEVER_ACTIVATE` holds provider campaigns 481 and 485 and refuses them
  whatever row resolves to them. 485 holds the SAME TEN PEOPLE as the live
  campaign 487. 481 holds nine of those ten plus four people live on campaign
  489. Starting either sends a second, unapproved message to somebody
  mid-conversation.
- These are called through `require_conditional_permission(operation,
  provider_campaign_id, campaign_id)`. Both ids arrive as caller-supplied
  values and may be str, int, None or empty.

Find DEFEATS. For each, give the exact inputs or state, the call order, and
what reaches a prospect as a result. I am specifically asking about:

1. Type and whitespace confusion between str and int ids, and anything where
   `"489"`, `489`, `" 489"` or `"489
"` behave differently.
2. Anything a caller can pass that makes a refusal become an acceptance.
3. What happens if the canonical row is missing, is not a dict, has
   `bison_campaign_id` of 0, None, "", a float, or a value that matches a
   never-activate entry only after normalisation.
4. Whether the two tables can disagree in a way that still permits a write.
5. Exceptions that could escape as something other than a refusal, given that
   a raised WriteRefused is safe and a returned True is not.

Do not comment on style. Every finding must name a mechanism and its
consequence. Answer with either NO FINDING or a numbered list, each item
giving the trigger, the call order, and the prospect-facing result.

--- {name} ---
{source}
"""


def _targets():
    """Built lazily so a broken import in one area cannot block the others."""
    from src import (store, actionledger, collision, bisonevents,
                     executionguard, providerwrites,
                     senderownership, queuejournal)
    return {
        # ADDED 2026-09-17, and reviewed BEFORE it has a caller for the same
        # reason `webhook` was: this one decides what the queue IS after a
        # crash. A dedupe that can be defeated costs a duplicate message; a
        # replay that can be defeated costs the record of who was contacted.
        "journal": (JOURNAL_QUESTION, [
            ("queuejournal.replay", queuejournal.replay),
            ("queuejournal.append", queuejournal.append),
            ("queuejournal.read", queuejournal.read),
        ]),
        # ADDED 2026-09-17, and it is the one target reviewed BEFORE its code
        # has a production caller rather than after. `bisonevents` normalises
        # an unauthenticated inbound payload from the internet and decides
        # whether two deliveries are one event; EmailBison retries five times
        # over 24 hours and replays ten days, so a dedupe that can be defeated
        # is a duplicate state transition against a real person.
        # The predicate that would REPLACE the sender arity rule, reviewed
        # while it still has no caller. If it can be defeated, a prospect
        # hears from two people in one conversation.
        "attestation": (GENERIC_QUESTION, [
            ("senderownership.one_attested_human",
             senderownership.one_attested_human),
            ("senderownership.resolve_owner", senderownership.resolve_owner),
        ]),
        # ADDED 2026-09-18, THE SAME DAY THE CODE WENT LIVE, and it is the
        # highest-consequence target in this file: these two functions decide
        # whether a real campaign starts emailing real people. The grant was
        # widened from ONE canonical row to TWO that day, which is exactly the
        # kind of change whose risk lives in what it stops refusing.
        #
        # The estate makes the stakes concrete. 481 and 485 must never start:
        # 485 holds live 487's own ten leads, and 481 holds nine of them plus
        # four contacts live on 489. A defeat here is a duplicate, unapproved
        # message to somebody we are already mid-conversation with.
        "activation": (ACTIVATION_QUESTION, [
            ("providerwrites._is_the_authorized_email_campaign",
             providerwrites._is_the_authorized_email_campaign),
            ("executionguard.activation_is_granted",
             executionguard.activation_is_granted),
        ]),
        "webhook": (GENERIC_QUESTION, [
            ("bisonevents.normalise", bisonevents.normalise),
            ("bisonevents.event_key", bisonevents.event_key),
        ]),
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
