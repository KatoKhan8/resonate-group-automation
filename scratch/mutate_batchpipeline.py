"""Break one guard, run the suite, restore. Assert the mutation APPLIED.

Not committed as a test: it rewrites a source file, and a thing that rewrites
source has no business running inside `unittest discover`. It is here so the
claim "these guards are tested" can be re-checked rather than believed.

    py -3 scratch/mutate_batchpipeline.py
"""
import hashlib
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGET = os.path.join(ROOT, "src", "batchpipeline.py")
BACKUP = TARGET + ".mutation-backup"
MODULE = "tests.test_a_batch_is_not_through_a_stage_that_returned_nothing"

MUTATIONS = [
    ("M1 StageEmpty refusal removed",
     "if status == DONE and attempted > 0 and produced == 0:",
     "if False:"),
    ("M2 empty ledger allowed through",
     "    if committed:\n        return True",
     "    if True:\n        return True"),
    ("M3 blocked stage still yields an ETA",
     "    if blocked:\n        return {",
     "    if False:\n        return {"),
    ("M4 denominator name check removed",
     "    if name not in DENOMINATORS:",
     "    if False:"),
    ("M5 mixed batch allowed",
     "    if len(keys) > 1:",
     "    if False:"),
    ("M6 produced-over-denominator check removed",
     "    if produced and produced > value:",
     "    if False:"),
]


def digest(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()[:12]


def run_suite():
    proc = subprocess.run([sys.executable, "-m", "unittest", MODULE],
                          cwd=ROOT, capture_output=True, text=True)
    lines = proc.stderr.strip().splitlines()
    failed = [ln for ln in lines if ln.startswith(("FAIL:", "ERROR:"))]
    return (lines[-1] if lines else "?"), failed


def main():
    shutil.copy2(TARGET, BACKUP)
    before = digest(TARGET)
    unguarded = []
    try:
        verdict, failed = run_suite()
        print(f"BASELINE  {verdict}  ({len(failed)} failing)")
        if failed:
            print("  REFUSING to mutate: the baseline is not green.")
            return 1

        for name, old, new in MUTATIONS:
            source = open(BACKUP, encoding="utf-8").read()
            hits = source.count(old)
            if hits != 1:
                print(f"\n{name}: MUTATION DID NOT APPLY - {hits} matches.")
                unguarded.append(name + " (did not apply)")
                continue
            with open(TARGET, "w", encoding="utf-8", newline="") as fh:
                fh.write(source.replace(old, new))
            # THE MUTATION MUST HAVE CHANGED THE FILE. A patch that silently
            # no-ops leaves the suite green, and a green suite then reads as
            # "the guard is redundant" when it means "nothing was tested".
            assert digest(TARGET) != before, f"{name}: file unchanged"
            verdict, failed = run_suite()
            print(f"\n{name}\n  {verdict}")
            for line in failed:
                print(f"  {line}")
            if not failed:
                print("  *** NO TEST CAUGHT THIS. The guard is untested. ***")
                unguarded.append(name)
    finally:
        shutil.copy2(BACKUP, TARGET)
        os.remove(BACKUP)
        assert digest(TARGET) == before, "RESTORE FAILED"
        print(f"\nrestored, digest {digest(TARGET)}")

    if unguarded:
        print(f"\nUNGUARDED: {len(unguarded)}")
        for name in unguarded:
            print(f"  {name}")
        return 1
    print(f"\nall {len(MUTATIONS)} mutations were caught")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
