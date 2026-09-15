#!/usr/bin/env python3
"""TASK-117: probe the claims rule with sender-identity candidates.

Tests what CLASS of sender-identity assertion escapes the current rule,
and what a broader rule would falsely refuse.

Reads only. No provider calls.
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src import claims


def probe_implies_prior_contact(sentences):
    """Test each sentence against implies_prior_contact. Return (sentence, match_text)."""
    results = []
    for s in sentences:
        found = claims.implies_prior_contact(s)
        results.append((s, found))
    return results


def probe_is_claim(sentences):
    """Test each sentence against is_claim. Return (sentence, is_claim_bool)."""
    results = []
    for s in sentences:
        result = claims.is_claim(s)
        results.append((s, result))
    return results


def probe_full_check(sentences, rec=None, contact=None):
    """Test each sentence against claims.check (full pipeline)."""
    if rec is None:
        rec = {"id": "test", "company": "Acme", "domain": "acme.test",
               "contacts": [{"key": "ck-1", "name": "Jane",
                             "title": "Founder"}],
               "company_facts": {"name": "Acme", "industry": "marketing"},
               "events": [], "research": []}
    if contact is None:
        contact = rec["contacts"][0]
    results = []
    for s in sentences:
        problems = claims.check(s, rec, contact)
        results.append((s, problems))
    return results


# --- CANDIDATE CLASSES ---

# Class 1: "as a fellow X" variants (currently caught by pattern)
class1_caught = [
    "as a fellow founder i thought it would be good to connect",
    "as a fellow operator i understand the challenge",
    "as a fellow marketer i wanted to reach out",
    "as a fellow agency owner i know the struggle",
    "speaking as a fellow founder i wanted to connect",
]

# Class 2: "as someone who X" variants (currently caught by pattern)
class2_caught = [
    "as someone who also runs an agency i understand the challenge",
    "as someone who owns a studio i know how it works",
    "as someone who has scaled a team your size i understand",
    "as someone who built an agency from scratch i get it",
]

# Class 3: CANDIDATES THAT MIGHT ESCAPE - sender identity assertions
# that do NOT match the existing three patterns
class3_candidates = [
    # "having X" construction
    "having run a team your size i understand the pressure",
    "having scaled an agency myself i know the challenge",
    "having built a marketing team from zero i get it",
    # "as an X" without "fellow"
    "as an agency owner i understand resourcing",
    "as a founder myself i know what it takes",
    "as an operator who has seen this i can help",
    # "I am a / I'm a" + role (asserts sender identity)
    "i am a founder too so i understand",
    "i'm a fellow agency owner and i get it",
    # "like you" / "like yourself" (asserts shared category)
    "as someone like you who runs an agency i understand",
    # "in my experience" + specific claim
    "in my experience running an agency this always comes up",
    "in my 10 years of running agencies i have seen this",
    # "from one X to another"
    "from one founder to another i know the feeling",
    "from one agency owner to another this resonates",
    # "we who X" (includes sender in a category)
    "we who run agencies know the pressure",
    # "my own" + experience claim
    "in my own agency we solved this exact problem",
    "my own team faced this and we found a way",
    # "i also" + verb that implies role
    "i also run an agency so i understand",
    "i also lead a team and i know the challenge",
    # "speaking as" without "fellow"
    "speaking as someone who has scaled an agency i understand",
    "speaking as an agency owner this resonates",
    # "having been" construction
    "having been in your shoes i understand",
    "having been a founder myself i get it",
]

# Class 4: HONEST COPY that MUST pass (sender identity from TASK-075)
class4_must_pass = [
    "most agencies we work with track time in spreadsheets",
    "i work with agencies on project profitability",
    "our platform connects budgets and time tracking",
    "we built productive so budgets and resourcing talk to each other",
    "curious how you handle resourcing at your size",
    "i help agencies with resourcing and utilisation",
    "we help creative teams connect their budgets and timelines",
    "our team works with agency founders on profitability",
]

# Class 5: Borderline - sender mentions their work but does not assert identity
class5_borderline = [
    "i have spent a decade in this industry",
    "we have worked with over 50 agencies",
    "our approach comes from years of agency work",
    "i started in agency operations before building this",
]


def main():
    print("=" * 78)
    print("TASK-117: SENDER-IDENTITY CLAIM PROBE")
    print("=" * 78)

    # --- Test 1: implies_prior_contact ---
    print("\n--- TEST 1: implies_prior_contact ---")
    print("\nClass 1 (should be caught):")
    for s, match in probe_implies_prior_contact(class1_caught):
        status = "CAUGHT" if match else "ESCAPED"
        print(f"  [{status}] {s!r}")
        if match:
            print(f"           matched: {match!r}")

    print("\nClass 2 (should be caught):")
    for s, match in probe_implies_prior_contact(class2_caught):
        status = "CAUGHT" if match else "ESCAPED"
        print(f"  [{status}] {s!r}")
        if match:
            print(f"           matched: {match!r}")

    print("\nClass 3 (candidates that might escape):")
    escaped = []
    caught = []
    for s, match in probe_implies_prior_contact(class3_candidates):
        status = "CAUGHT" if match else "ESCAPED"
        print(f"  [{status}] {s!r}")
        if match:
            caught.append(s)
            print(f"           matched: {match!r}")
        else:
            escaped.append(s)

    print(f"\n  Summary: {len(caught)} caught, {len(escaped)} escaped out of {len(class3_candidates)}")

    # --- Test 2: Full claims.check ---
    print("\n--- TEST 2: Full claims.check (no prior contact) ---")
    print("\nClass 3 escaped candidates through full check:")
    for s in escaped:
        problems = claims.check(s, {
            "id": "test", "company": "Acme", "domain": "acme.test",
            "contacts": [{"key": "ck-1", "name": "Jane", "title": "Founder"}],
            "company_facts": {"name": "Acme", "industry": "marketing"},
            "events": [], "research": []
        }, {"key": "ck-1", "name": "Jane", "title": "Founder"})
        if problems:
            print(f"  [REFUSED] {s!r}")
            for p in problems:
                print(f"            {p['why']}")
        else:
            print(f"  [PASSED ] {s!r}")

    # --- Test 3: Must-pass copy ---
    print("\n--- TEST 3: Must-pass honest copy ---")
    for s, match in probe_implies_prior_contact(class4_must_pass):
        status = "CAUGHT" if match else "CLEAN"
        print(f"  [{status}] {s!r}")
        if match:
            print(f"           FALSE POSITIVE: {match!r}")

    # --- Test 4: Borderline ---
    print("\n--- TEST 4: Borderline sender experience ---")
    for s, match in probe_implies_prior_contact(class5_borderline):
        status = "CAUGHT" if match else "CLEAN"
        print(f"  [{status}] {s!r}")
        if match:
            print(f"           matched: {match!r}")

    # --- Test 5: is_claim analysis ---
    print("\n--- TEST 5: is_claim for escaped candidates ---")
    for s in escaped:
        result = claims.is_claim(s)
        print(f"  [{'CLAIM' if result else 'NOT CLAIM'}] {s!r}")


if __name__ == "__main__":
    main()
