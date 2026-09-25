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

# (name, old, new, the test that MUST be the one to catch it).
#
# The expected test name is the point. "something went red" is not evidence
# that the guard is tested - a different guard firing first, or a typo
# raising NameError, produces the same green summary. The harness fails when
# the intended test is not among the failures.
MUTATIONS = [
    ("M1 StageEmpty refusal removed",
     "if status == DONE and attempted > 0 and produced == 0:",
     "if False:",
     "test_an_empty_stage_recorded_done_is_refused"),
    ("M2 empty ledger allowed through",
     "    if committed:\n        return True",
     "    if True:\n        return True",
     "test_an_empty_ledger_refuses_paid_work"),
    ("M3 blocked stage still yields an ETA",
     "    if blocked:\n        return {",
     "    if False:\n        return {",
     "test_a_blocked_stage_makes_the_eta_unmeasurable"),
    ("M4 denominator name check removed",
     "    if name not in DENOMINATORS:",
     "    if False:",
     "test_an_unnamed_denominator_is_refused"),
    ("M5 a batch mixing geo or persona allowed",
     "    if len(pairs) > 1:",
     "    if False:",
     "test_a_batch_mixing_geo_is_refused"),
    ("M6 produced-over-denominator check removed",
     "    if produced and produced > value:",
     "    if False:",
     "test_producing_more_than_the_denominator_is_refused"),
    ("M7 identifiers no longer reported as leaks",
     "                if value in haystack:",
     "                if False:",
     "test_an_identifier_is_a_leak_at_any_length"),
    ("M8 names matched as substrings again",
     "            elif _whole_token(value, haystack):",
     "            elif value in haystack:",
     "test_a_name_is_matched_on_whole_tokens_not_substrings"),
    ("M9 structural check accepts any new field",
     "            problems.append({\"path\": path, \"key\": key,",
     "            return\n            problems.append({\"path\": path, \"key\": key,",
     "test_a_field_the_format_grew_later_fails_closed"),
    ("M10 slice label no longer has to be derived",
     "    if slice_.get(\"label\") != expected:",
     "    if False:",
     "test_a_label_that_drifted_from_its_fields_is_refused"),
    # --- the operator's 2026-09-25 slicing rule ---
    ("M11 the under-50 emit refusal removed",
     "    if 0 < len(rows) < MIN_COHORT:",
     "    if False:",
     "test_assert_emittable_refuses_a_short_batch"),
    ("M12 a short pair is emitted instead of held",
     "        if len(chunks) == 1 and len(chunks[0]) < MIN_COHORT:",
     "        if False:",
     "test_a_batch_under_fifty_is_never_emitted"),
    ("M13 persona stops being a pinned dimension",
     "    return (zone, persona_of(row, config))",
     "    return (zone,)",
     "test_a_batch_mixing_persona_is_refused"),
    ("M14 an industry at the threshold is merged away",
     "           if len(idx) >= MERGE_INDUSTRY_BELOW}",
     "           if False}",
     "test_an_industry_at_or_above_the_threshold_keeps_its_own_batch"),
    # --- the LinkedIn decision ---
    ("M15 a supplier URL counts as discovered",
     "    return LINKEDIN_FROM_SUPPLIER",
     "    return LINKEDIN_FROM_DISCOVERY",
     "test_a_supplier_url_does_not_satisfy_the_gate"),
    ("M16 the excluded cohort range is wrong",
     "LINKEDIN_EXCLUDED_CAMPAIGNS = range(491, 499)",
     "LINKEDIN_EXCLUDED_CAMPAIGNS = range(591, 599)",
     "test_the_491_to_498_cohort_is_permanently_excluded"),
    # --- the campaign tag must show the mix ---
    ("M17 the tag names only the leading industry",
     "                      \"+\".join(_slug(i) for i in industries)])",
     "                      _slug(industries[0]) if industries else \"\"])",
     "test_every_merged_industry_appears_in_the_tag"),
    ("M18 a drifted campaign tag is accepted",
     "    if slice_.get(\"campaign_tag\") != expected_tag:",
     "    if False:",
     "test_a_drifted_tag_is_refused_structurally"),
]


def digest(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()[:12]


def run_suite():
    """Run the module in a fresh interpreter that cannot reuse bytecode.

    PYTHONDONTWRITEBYTECODE, AND IT IS NOT A TIDINESS SETTING.

    Without it this harness reported the WRONG GUARD. Mutations are written
    milliseconds apart; Windows filesystem timestamps are coarser than that,
    so CPython's `.pyc` staleness check - source mtime and size - saw no
    change and re-imported the PREVIOUS mutation's bytecode. M8 was reported
    as caught by M7's test, and both looked like a pass. Applying M8 by hand
    showed the intended test catching it all along.

    A mutation harness that silently tests the previous mutation is worse
    than no harness, because its green is indistinguishable from a real one.
    """
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    for base, dirs, _files in os.walk(ROOT):
        for name in list(dirs):
            if name == "__pycache__":
                shutil.rmtree(os.path.join(base, name), ignore_errors=True)
                dirs.remove(name)
    proc = subprocess.run([sys.executable, "-B", "-m", "unittest", MODULE],
                          cwd=ROOT, capture_output=True, text=True, env=env)
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

        for name, old, new, expected in MUTATIONS:
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
            elif not any(expected in line for line in failed):
                # A DIFFERENT GUARD FIRED FIRST, which is not the same thing
                # as this one being tested. This is how the stale-bytecode
                # defect above was found: M8 went red under M7's test name
                # and read as a pass.
                print(f"  *** CAUGHT BY THE WRONG TEST. Expected "
                      f"{expected}. ***")
                unguarded.append(f"{name} (wrong test)")
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
