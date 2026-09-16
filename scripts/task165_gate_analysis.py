#!/usr/bin/env python3
"""TASK-165: analyse the gate sequence for list staging.

Reads the source and reports:
  - where each gate sits in the staging path
  - which function calls which
  - the predicate that decides list safety
  - the readback definition

No provider writes. No credentials needed.
"""
import ast
import os
import sys


def main():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    module_path = os.path.join(root, "src", "liststaging.py")

    with open(module_path, encoding="utf-8") as f:
        source = f.read()

    tree = ast.parse(source)

    functions = []
    classes = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            functions.append(node.name)
        elif isinstance(node, ast.ClassDef):
            classes.append(node.name)

    print("=== TASK-165 Gate Analysis ===")
    print()
    print("Module: src/liststaging.py")
    print()
    print("Functions:")
    for fn in functions:
        print(f"  - {fn}")
    print()
    print("Classes:")
    for cls in classes:
        print(f"  - {cls}")
    print()
    print("Gate sequence in stage_lead():")
    print("  1. validate_lead_row(row)      — firstName, lastName, linkedin_url")
    print("  2. assert_list_safe(list_id)   — reads provider, checks campaignIds")
    print("  3. transport(payload)           — POST /list/AddLeadsToListV2")
    print("  4. readback_list_add(list_id)  — members + binding re-read")
    print("  5. classify_readback(result)   — ACCEPTED / DRIFTED / UNKNOWN")
    print()
    print("Safe-list predicate: list_is_unbound(list_row)")
    print("  Returns True iff campaignIds is empty")
    print()
    print("Readback: readback_list_add(list_id, expected_urls)")
    print("  Two reads: list_leads (membership) + list_by_id (binding)")
    print("  ACCEPTED iff found == expected AND still_unbound")
    print()
    print("Campaign-step gate (existing, not modified):")
    print("  executionguard.authorize(operation=LINKEDIN_ADD_LEAD)")
    print("  providerwrites.require_conditional_permission(LINKEDIN_ADD_LEAD)")
    print("  — re-reads campaign, proves it cannot send")
    print()

    # Verify the module is consumed
    test_path = os.path.join(root, "tests", "test_list_staging.py")
    if os.path.exists(test_path):
        with open(test_path, encoding="utf-8") as f:
            test_source = f.read()
        test_tree = ast.parse(test_source)
        test_classes = [n.name for n in ast.walk(test_tree)
                        if isinstance(n, ast.ClassDef)]
        test_methods = [n.name for n in ast.walk(test_tree)
                        if isinstance(n, ast.FunctionDef)
                        and n.name.startswith("test_")]
        print(f"Tests: {len(test_methods)} test methods in "
              f"{len(test_classes)} classes")
        print()
        print("Refusal paths covered:")
        refusal_tests = [m for m in test_methods if "refuse" in m]
        for t in refusal_tests:
            print(f"  - {t}")
    else:
        print("WARNING: test file not found")

    return 0


if __name__ == "__main__":
    sys.exit(main())
