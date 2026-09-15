#!/usr/bin/env python3
"""TASK-089 diagnostic: render LinkedIn variant prompts at li3 for
concise_direct and problem_led, and diff them.

Also renders email prompts at em3 for comparison.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import cadencelibrary, generate, variantgen

# 1. Show the LinkedIn ladder rungs
print("=" * 70)
print("LINKEDIN_DEFAULT_LADDER rungs:")
print("=" * 70)
for i, rung in enumerate(cadencelibrary.LINKEDIN_DEFAULT_LADDER, 1):
    print(f"\n--- Rung {i} ---")
    print(rung)

print("\n")
print("=" * 70)
print("EMAIL_FIVE_LADDER rungs:")
print("=" * 70)
for i, rung in enumerate(cadencelibrary.EMAIL_FIVE_LADDER, 1):
    print(f"\n--- Rung {i} ---")
    print(rung)

# 2. Render prompts for LinkedIn li3 (ordinal 3)
print("\n\n")
print("=" * 70)
print("LINKEDIN li3 - PURPOSE (rung 3):")
print("=" * 70)
li_purpose = cadencelibrary.LINKEDIN_DEFAULT_LADDER[2]  # 0-indexed
print(li_purpose)

# 3. Render prompts for each approach at li3
context_block = {
    "company": "Test Agency",
    "facts": {"name": "Test Agency", "employees": "50", "industry": "Marketing"},
    "contact": {"name": "Jane Doe", "title": "CEO", "persona": "founder", "angle": "profitability"},
    "public_evidence": "Test Agency helps brands grow through data-driven marketing.",
    "product": "Productive - project profitability software for agencies",
    "angle_wording": "profitability visible on Monday not two weeks late",
}

approaches_to_test = ["concise_direct", "conversational", "problem_led", "observation_led", "value_led"]

print("\n\n")
print("=" * 70)
print("LINKEDIN li3 - RENDERED PROMPTS PER APPROACH:")
print("=" * 70)

li_prompts = {}
for approach in approaches_to_test:
    prompt = variantgen.variant_prompt(approach, "linkedin_note", li_purpose, context_block)
    li_prompts[approach] = prompt
    spec = variantgen.APPROACHES[approach]
    print(f"\n{'=' * 50}")
    print(f"APPROACH: {approach} ({spec['label']})")
    print(f"  opening: {spec['opening']}")
    print(f"  cta: {spec['cta']}")
    print(f"  tone: {spec['tone']}")
    print(f"  length: {spec['length']}")
    print(f"{'=' * 50}")
    print(prompt)

# 4. Render prompts for email em3 (ordinal 3)
print("\n\n")
print("=" * 70)
print("EMAIL em3 - PURPOSE (rung 3):")
print("=" * 70)
em_purpose = cadencelibrary.EMAIL_FIVE_LADDER[2]  # 0-indexed
print(em_purpose)

em_prompts = {}
for approach in approaches_to_test:
    prompt = variantgen.variant_prompt(approach, "draft", em_purpose, context_block)
    em_prompts[approach] = prompt
    spec = variantgen.APPROACHES[approach]
    print(f"\n{'=' * 50}")
    print(f"APPROACH: {approach} ({spec['label']})")
    print(f"  opening: {spec['opening']}")
    print(f"  cta: {spec['cta']}")
    print(f"  tone: {spec['tone']}")
    print(f"  length: {spec['length']}")
    print(f"{'=' * 50}")
    print(prompt)

# 5. Diff the LinkedIn prompts for concise_direct vs problem_led
print("\n\n")
print("=" * 70)
print("DIFF: concise_direct vs problem_led at li3 (LinkedIn)")
print("=" * 70)
cd_lines = li_prompts["concise_direct"].split("\n")
pl_lines = li_prompts["problem_led"].split("\n")

# Find lines that differ
import difflib
diff = difflib.unified_diff(cd_lines, pl_lines,
                            fromfile="concise_direct@li3",
                            tofile="problem_led@li3",
                            lineterm="")
for line in diff:
    print(line)

# 6. Also diff for email em3
print("\n\n")
print("=" * 70)
print("DIFF: concise_direct vs problem_led at em3 (Email)")
print("=" * 70)
cd_lines_em = em_prompts["concise_direct"].split("\n")
pl_lines_em = em_prompts["problem_led"].split("\n")

diff_em = difflib.unified_diff(cd_lines_em, pl_lines_em,
                               fromfile="concise_direct@em3",
                               tofile="problem_led@em3",
                               lineterm="")
for line in diff_em:
    print(line)

# 7. Check: what is the ACTUAL structural difference between the approach descriptions?
print("\n\n")
print("=" * 70)
print("APPROACH STRUCTURAL SPECS:")
print("=" * 70)
for approach in approaches_to_test:
    spec = variantgen.APPROACHES[approach]
    print(f"\n{approach}:")
    print(f"  opening: {spec['opening']}")
    print(f"  cta: {spec['cta']}")
    print(f"  tone: {spec['tone']}")
    print(f"  length: {spec['length']}")
    print(f"  proof: {spec['proof']}")

# 8. Check the linkedin_note prompt template for form instructions
print("\n\n")
print("=" * 70)
print("LINKEDIN_NOTE PROMPT TEMPLATE - checking for form instructions:")
print("=" * 70)
template_text = generate.prompt_text("linkedin_note")
form_words = ["question", "statement", "ask", "closing"]
for word in form_words:
    lines_with = [(i+1, l.strip()) for i, l in enumerate(template_text.split("\n"))
                  if word in l.lower()]
    if lines_with:
        print(f"\n  '{word}' appears in {len(lines_with)} lines:")
        for lineno, line in lines_with:
            print(f"    L{lineno}: {line[:100]}")
