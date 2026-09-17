#!/usr/bin/env python3
"""Ask GLM to attack the copy-approval guards. Independent second opinion.

    py -3 scripts/glm_audit_safety.py                 # dry run, prints the prompt
    py -3 scripts/glm_audit_safety.py --live          # calls GLM

READ-ONLY apart from the report it writes. No provider write, no state change.

WHY A DIFFERENT MODEL. The guards below were written and then verified by the
same session that wrote them, and the verification was the author checking
their own work - which is exactly how `is_approved`'s three-argument form came
to compare a stored step to itself and agree unconditionally for months. A
second model reading the code cold cannot repeat the first one's assumptions.
It can be wrong; it cannot be wrong in the same direction for the same reason.

WHAT IT IS ASKED. Not "is this good code" - an agreeable answer to that is
worthless. It is asked for concrete defeats: an input, a sequence of calls, or
a state that gets unapproved words to a prospect while these functions report
success. A claim with no mechanism is explicitly rejected in the prompt.

THE OUTPUT IS A LEAD, NOT A VERDICT. Anything it finds is checked against the
code and the tests by hand before it changes anything. A model's opinion is
evidence to investigate, never a reason to edit a safety gate.
"""
import argparse
import datetime
import inspect
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import approve, bisonfactory, collision, heyreachfactory  # noqa: E402
from src.providers import glm, load_env                            # noqa: E402

REPORT = os.path.join("docs", "GLM-SAFETY-AUDIT-2026-09-17.md")

SYSTEM = (
    "You are auditing safety-critical code in a cold-outreach system. Its one "
    "invariant: the words a prospect reads must be exactly the words a human "
    "approved, proven by fingerprint. You are looking for DEFEATS, not style. "
    "A finding must name a concrete input, call order or state that gets "
    "unapproved words to a prospect while these functions report success. If "
    "you cannot construct one, say NO DEFEAT FOUND for that function - that "
    "answer is worth more than a plausible-sounding guess."
)

QUESTION = """Here are four functions from a live outreach system.

`_certified_copy` decides whether one email step's words may be staged to the
provider. `approve_step` records an operator approval. `_step_copy` is the
LinkedIn equivalent of the first. `_ledger_is_silent` decides whether a
campaign of ours has provably never sent anything.

Context you need:
- `approval.fingerprint(step)` hashes a step's channel, subject, body and note.
  It does NOT hash `message` or `linkedin_action`. This is known.
- Custom variables reach the provider per lead; the sequence holds only
  placeholders like {{SUBJECT_1}} and {{BODY_1}}.
- The action ledger APPENDS; it never edits history.
- These run per contact, at staging time and again at activation.

For EACH function, answer:
1. A concrete defeat, or NO DEFEAT FOUND.
2. If there is a defeat: the exact steps, and what a prospect would receive.
3. Which of the four is weakest, and why.

Be brief. No preamble.

--- _certified_copy ---
{certified}

--- approve_step ---
{approve_step}

--- _step_copy ---
{step_copy}

--- _ledger_is_silent ---
{ledger}
"""


def build_prompt():
    return QUESTION.format(
        certified=inspect.getsource(bisonfactory._certified_copy),
        approve_step=inspect.getsource(approve.approve_step),
        step_copy=inspect.getsource(heyreachfactory._step_copy),
        ledger=inspect.getsource(collision._ledger_is_silent),
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--live", action="store_true",
                        help="call GLM; omit to print the prompt only")
    parser.add_argument("--max-tokens", type=int, default=3000)
    args = parser.parse_args(argv)

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    load_env(os.path.join(root, "config", ".env"))

    prompt = build_prompt()
    print(f"prompt chars: {len(prompt)}")
    if not args.live:
        print("\nDRY RUN: GLM was not called. Re-run with --live.")
        return 0

    # GLM-5.3 spends most output tokens on reasoning - a two-character answer
    # cost 29 completion tokens, 26 of them reasoning - so the budget is sized
    # for the thinking, not the visible answer.
    result = glm.complete(prompt, system=SYSTEM, max_tokens=args.max_tokens,
                          timeout=60)
    print(f"\nmodel     : {result['model']} "
          f"(requested {result['requested_model']})")
    print(f"seconds   : {result['seconds']}")
    print(f"usage     : {result['usage']}")
    print(f"finish    : {result['finish_reason']}")
    print("\n" + "=" * 70)
    print(result["content"])

    stamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
    os.makedirs(os.path.join(root, "docs"), exist_ok=True)
    with open(os.path.join(root, REPORT), "w", encoding="utf-8") as fh:
        fh.write("# GLM safety audit - copy-approval guards\n\n")
        fh.write(f"Model {result['model']} (requested "
                 f"{result['requested_model']}), {stamp}.\n"
                 f"Usage {result['usage']}.\n\n")
        fh.write("A SECOND OPINION, NOT A VERDICT. Everything below is a lead "
                 "to check against the code and the tests by hand. A model's "
                 "opinion is evidence to investigate, never a reason to edit "
                 "a safety gate.\n\n---\n\n")
        fh.write(result["content"])
        fh.write("\n")
    print(f"\nwritten to {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
