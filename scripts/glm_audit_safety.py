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

# ONE FUNCTION PER CALL, AND THE REASON IS MEASURED. All four at once is an
# 11.5k-character prompt, and GLM-5.3 spends most of its output budget on
# reasoning tokens - a two-character answer cost 29 completion tokens, 26 of
# them reasoning. The whole-file prompt exceeded the adapter's 60s per-attempt
# cap twice: once returning an empty completion with finish_reason="length",
# once timing out outright. The adapter refused both rather than handing back
# "" as an answer, which is correct and is also why this is split.
#
# Smaller prompts are better auditing anyway: a model asked about one function
# cannot hedge by talking about a different one.
QUESTION = """Here is one function from a live outreach system.

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

Answer:
1. A concrete defeat, or NO DEFEAT FOUND.
2. If there is a defeat: the exact steps, and what a prospect would receive.

Be brief. No preamble. Under 200 words.

--- {name} ---
{source}
"""


TARGETS = [
    ("_certified_copy", bisonfactory._certified_copy),
    ("approve_step", approve.approve_step),
    ("_step_copy", heyreachfactory._step_copy),
    ("_ledger_is_silent", collision._ledger_is_silent),
]


# PROBLEM-REGISTER ISSUE-008, and the same value as `glm_review`: the model
# spends most of its output budget on reasoning rather than on the answer, and
# 6,000 returned an EMPTY completion with `finish_reason='length'` twice.
DEFAULT_MAX_TOKENS = 16000


class PromptCarriesNoSource(RuntimeError):
    """A review prompt was built that does not contain the code under review.

    The same guard, the same signature and the same name as `glm_review`'s,
    deliberately. These two harnesses are near-identical and a guard present in
    only one of them is how the next sourceless review gets run. See
    `glm_review.PromptCarriesNoSource` for the incident this records.
    """


def build_prompt(question, name, fn):
    """Render one prompt, refusing if the code did not make it in.

    `question` is a parameter rather than the module constant so the refusal
    is testable and so the two harnesses share one shape.
    """
    source = inspect.getsource(fn)
    prompt = question.format(name=name, source=source)
    if source not in prompt:
        raise PromptCarriesNoSource(
            f"the prompt for {name} does not contain its source, so the model "
            f"would be asked to review code it cannot see. The question "
            f"template needs a {{source}} placeholder. Nothing was sent.")
    return prompt


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--live", action="store_true",
                        help="call GLM; omit to print the prompt only")
    parser.add_argument("--max-tokens", type=int,
                        default=DEFAULT_MAX_TOKENS)
    args = parser.parse_args(argv)

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    load_env(os.path.join(root, "config", ".env"))

    if not args.live:
        for name, fn in TARGETS:
            print(f"  {name:20s} prompt chars: "
                  f"{len(build_prompt(QUESTION, name, fn))}")
        print("\nDRY RUN: GLM was not called. Re-run with --live.")
        return 0

    findings = []
    for name, fn in TARGETS:
        prompt = build_prompt(QUESTION, name, fn)
        print(f"\n--- {name} ({len(prompt)} chars) ---")
        try:
            result = glm.complete(prompt, system=SYSTEM,
                                  max_tokens=args.max_tokens, timeout=60)
        except Exception as exc:
            print(f"  {type(exc).__name__}: {str(exc)[:140]}")
            findings.append((name, None, f"{type(exc).__name__}: {exc}"))
            continue
        print(f"  {result['model']} {result['seconds']}s "
              f"{result['usage']}")
        # THE CONSOLE IS cp1250 ON THIS MACHINE and the model answers in
        # UTF-8. A single "->" arrow crashed the whole run AFTER a successful
        # 31.9s call, losing an answer that had already been paid for. The
        # report is written from `findings` regardless; this print is a
        # convenience and must never be what fails.
        safe = result["content"].encode("ascii", "replace").decode("ascii")
        print(safe[:1200])
        findings.append((name, result, result["content"]))

    stamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
    os.makedirs(os.path.join(root, "docs"), exist_ok=True)
    with open(os.path.join(root, REPORT), "w", encoding="utf-8") as fh:
        fh.write("# GLM safety audit - copy-approval guards\n\n")
        fh.write(f"{stamp}. One call per function.\n\n")
        fh.write("A SECOND OPINION, NOT A VERDICT. Everything below is a lead "
                 "to check against the code and the tests by hand. A model's "
                 "opinion is evidence to investigate, never a reason to edit "
                 "a safety gate.\n\n---\n\n")
        for name, result, content in findings:
            fh.write(f"## {name}\n\n")
            if result is not None:
                fh.write(f"`{result['model']}`, {result['seconds']}s, "
                         f"usage {result['usage']}.\n\n")
            else:
                fh.write("The call did not return.\n\n")
            fh.write(content)
            fh.write("\n\n")
    print(f"\nwritten to {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
