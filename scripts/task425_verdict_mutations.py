"""Can `task425_artifact.matrix_verdicts` still REFUSE? Six killed mutations.

TASK-425 criterion 1 is certified by a function that reads a run's recorded
measurements and answers PASSED or BLOCKED per matrix run. A function that
answers PASSED on every input would produce exactly the artifact the operator
asked this task to prevent, and it would be indistinguishable from a correct one
on a run that happens to pass.

So each guard is killed in turn, on the RECORDED DATA rather than in the source:
one field of one comparison is changed to the value the guard exists to catch,
`matrix_verdicts` is asked again, and the verdict has to move. A mutation that
leaves the verdict at PASSED is a guard that is not there.

    py -3 scripts/task425_verdict_mutations.py work/rerun.json

Exit code 0 only when every mutation was killed by the verdict it was aimed at.
"""
import copy
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import task425_artifact                                          # noqa: E402


def mutate_a2_deterministic(result):
    """The control's whole job: a deterministic prompt that moved."""
    result["comparisons"]["A2"]["deterministic_stages_changed"] = ["strategy"]
    return "A2", "BLOCKED"


def mutate_a2_not_comparable(result):
    """Two different people are not a comparison. This is the defect that made
    the first full matrix invalid: run A stored c1 and run A2 stored c3."""
    result["comparisons"]["A2"]["comparable"] = False
    return "A2", "NOT COMPARABLE"


def mutate_d_absent(result):
    """A run that did not happen is not a pass."""
    del result["comparisons"]["D"]
    return "D", "NOT RUN"


def mutate_b_no_prompt_moved(result):
    """B changed a fact, so a deterministic prompt HAD to move."""
    result["comparisons"]["B"]["deterministic_stages_changed"] = []
    return "B", "BLOCKED"


def mutate_b_copy_identical(result):
    """B changed a fact and the copy did not move, and the lead did not hold."""
    result["comparisons"]["B"]["copy_identical"] = True
    result["comparisons"]["B"]["steps_whose_copy_changed"] = []
    result["comparisons"]["B"]["held_after"] = []
    return "B", "BLOCKED"


def mutate_c_offer_unchanged(result):
    """C switched the persona, so the selected offer HAD to change."""
    c = result["comparisons"]["C"]
    c["selected_offers_after"] = c.get("selected_offers_before")
    return "C", "BLOCKED"


def mutate_d_claim_survived(result):
    """The load-bearing half and the disappearance half, both inverted: the
    removed row WAS load-bearing and the specific it licensed is still in D's
    copy. Decorative grounding, and a BLOCK."""
    d = result["comparisons"]["D"]
    d["claim_before"]["removed_evidence"] = {
        "source_url": "https://example.invalid/mutation",
        "specifics": ["2"], "why": "mutation"}
    d["claim_before"]["would_be_refused_without_it"] = ["2"]
    d["claim_after"]["specifics_it_licensed"] = ["2"]
    d["held_after"] = []
    return "D", "BLOCKED"


MUTATIONS = (mutate_a2_deterministic, mutate_a2_not_comparable, mutate_d_absent,
             mutate_b_no_prompt_moved, mutate_b_copy_identical,
             mutate_c_offer_unchanged, mutate_d_claim_survived)


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    with open(argv[1], "r", encoding="utf-8") as handle:
        base = json.load(handle)

    clean = task425_artifact.matrix_verdicts(base)
    print("BASELINE, from %s" % argv[1])
    for run in ("A2", "B", "C", "D"):
        print("   %-3s %s" % (run, clean.get(run, {}).get("verdict")))

    print()
    print("MUTATIONS, each aimed at one guard")
    failures = []
    for mutation in MUTATIONS:
        result = copy.deepcopy(base)
        run, wanted = mutation(result)
        got = task425_artifact.matrix_verdicts(result).get(run, {})
        verdict = got.get("verdict")
        killed = verdict == wanted
        # A MUTATION KILLED BY A DIFFERENT GUARD PROVES NOTHING about the guard
        # it was aimed at, so the expected verdict is named rather than "not
        # PASSED".
        print("   %-28s -> %-15s want %-15s %s"
              % (mutation.__name__, verdict, wanted,
                 "KILLED" if killed else "SURVIVED"))
        if not killed:
            failures.append((mutation.__name__, verdict, wanted,
                             got.get("why")))

    print()
    if failures:
        for name, verdict, wanted, why in failures:
            print("SURVIVED: %s gave %r, wanted %r" % (name, verdict, wanted))
            print("   why: %s" % str(why)[:300])
        return 1
    print("every mutation was killed by the verdict it was aimed at: %d/%d"
          % (len(MUTATIONS), len(MUTATIONS)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
