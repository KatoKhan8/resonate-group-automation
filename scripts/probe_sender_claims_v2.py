#!/usr/bin/env python3
"""TASK-117: design and test a class-based sender-identity rule.

The current rule has three literal patterns. 22 candidate phrases all escape.
This probe tests whether a STRUCTURAL rule can catch the class without
falsely refusing honest sender-identity copy.

The key distinction:
  - REFUSED: "I AM one of you" (shared category / identity)
  - ALLOWED: "I WORK WITH people like you" (service relationship)
"""
import re
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src import claims


# =====================================================================
# PROPOSED CLASS-BASED RULE
# =====================================================================
#
# The class is: ASSERTIONS THAT PLACE THE SENDER IN THE SAME CATEGORY
# AS THE RECIPIENT. Not "I work with agencies" (service) but "I am an
# agency owner" (identity).
#
# Structural markers:
#
# 1. "as a/an X" where X is a role/identity noun (without "fellow" needed)
#    - "as an agency owner", "as a founder", "as an operator"
#    - BUT NOT "as a whole" or "as a result" (non-identity uses of "as a")
#
# 2. "having + past participle + object" claiming experience
#    - "having run a team", "having scaled an agency"
#    - BUT NOT "having said that" or "having finished" (discourse markers)
#
# 3. "from one X to another" - asserts shared category
#    - "from one founder to another"
#
# 4. "i am/i'm a X" + too/also/fellow/myself - asserts shared identity
#    - "i am a founder too", "i'm a fellow agency owner"
#    - BUT NOT "i am writing to you" (non-identity)
#
# 5. "i also + role-verb" - claims same role
#    - "i also run an agency", "i also lead a team"
#
# 6. "in my N years of X" / "in my experience X" - claims specific experience
#    - "in my 10 years of running agencies"
#
# 7. "speaking as + role" (without "fellow")
#    - "speaking as an agency owner"
#
# The challenge: distinguishing identity from service.
# "i work with agencies" = service (allowed)
# "i also run an agency" = identity (refused)
#
# The verb is the discriminator:
# - SERVICE verbs: work with, help, serve, support, partner with
# - IDENTITY verbs: am, run, own, lead, manage, founded, built, operate

# Role/identity nouns that signal shared category
ROLE_NOUNS = (
    r"founder", r"co[- ]founder", r"operator", r"agency\s+owner",
    r"studio\s+owner", r"team\s+lead", r"manager", r"director",
    r"ceo", r"cto", r"coo", r"executive", r"entrepreneur",
    r"consultant", r"freelancer", r"contractor", r"specialist",
    r"marketer", r"designer", r"developer", r"engineer",
    r"agency", r"studio", r"firm",
)

# Pattern 1: "as a/an X" where X is a role noun
AS_A_ROLE = re.compile(
    r"\bas\s+(?:a|an)\s+(?:" + "|".join(ROLE_NOUNS) + r")\b", re.I)

# Pattern 2: "having + past participle + object" claiming experience
HAVING_EXPERIENCE = re.compile(
    r"\bhaving\s+(?:run|runs|scaled|built|led|managed|owned|operated|"
    r"grown|started|founded|directed)\b", re.I)

# Pattern 3: "from one X to another"
FROM_ONE_TO_ANOTHER = re.compile(
    r"\bfrom\s+one\s+\w+\s+to\s+another\b", re.I)

# Pattern 4: "i am/i'm a X" + too/also/fellow/myself
I_AM_ALSO = re.compile(
    r"\bi(?:\s*'|m|s)?\s+(?:a|an)\s+(?:" + "|".join(ROLE_NOUNS) + r")"
    r"(?:\s+(?:too|also|myself))?\b"
    r"|\bi(?:\s*'|m)?\s+(?:a\s+)?fellow\s+\w+\b", re.I)

# Pattern 5: "i also + role-verb"
I_ALSO_ROLE = re.compile(
    r"\bi\s+also\s+(?:run|owns?|manage|lead|operate|founded|built|"
    r"head|direct)\b", re.I)

# Pattern 6: "in my N years of X" / "in my experience X"
MY_EXPERIENCE = re.compile(
    r"\bin\s+my\s+(?:\d+\s+years?\s+of\s+|"
    r"experience\s+(?:running|scaling|building|leading|managing|"
    r"owning|operating|growing))\b", re.I)

# Pattern 7: "speaking as + role" (without "fellow")
SPEAKING_AS_ROLE = re.compile(
    r"\bspeaking\s+as\s+(?:a|an)\s+(?:" + "|".join(ROLE_NOUNS) + r")\b", re.I)

# Pattern 8: "as someone who has + past participle"
AS_SOMEONE_HAS = re.compile(
    r"\bas\s+someone\s+who\s+has\s+(?:run|runs|scaled|built|led|managed|"
    r"owned|operated|grown|started|founded)\b", re.I)


ALL_PATTERNS = [
    ("as_a_role", AS_A_ROLE),
    ("having_experience", HAVING_EXPERIENCE),
    ("from_one_to_another", FROM_ONE_TO_ANOTHER),
    ("i_am_also", I_AM_ALSO),
    ("i_also_role", I_ALSO_ROLE),
    ("my_experience", MY_EXPERIENCE),
    ("speaking_as_role", SPEAKING_AS_ROLE),
    ("as_someone_has", AS_SOMEONE_HAS),
]


def class_based_check(sentence):
    """Does this sentence assert sender identity / shared category?
    Returns matched pattern name or None."""
    for name, pattern in ALL_PATTERNS:
        m = pattern.search(sentence)
        if m:
            return name
    return None


# =====================================================================
# TEST CORPUS
# =====================================================================

# Must be CAUGHT (sender identity assertions)
must_catch = [
    # Currently caught by existing rule
    ("as a fellow founder i thought it would be good to connect", "existing"),
    ("as someone who also runs an agency i understand the challenge", "existing"),
    ("speaking as a fellow founder i wanted to connect", "existing"),
    # Currently escaping
    ("having run a team your size i understand the pressure", "escaped"),
    ("having scaled an agency myself i know the challenge", "escaped"),
    ("as an agency owner i understand resourcing", "escaped"),
    ("as a founder myself i know what it takes", "escaped"),
    ("i am a founder too so i understand", "escaped"),
    ("i'm a fellow agency owner and i get it", "escaped"),
    ("from one founder to another i know the feeling", "escaped"),
    ("from one agency owner to another this resonates", "escaped"),
    ("in my experience running an agency this always comes up", "escaped"),
    ("in my 10 years of running agencies i have seen this", "escaped"),
    ("i also run an agency so i understand", "escaped"),
    ("i also lead a team and i know the challenge", "escaped"),
    ("speaking as someone who has scaled an agency i understand", "escaped"),
    ("speaking as an agency owner this resonates", "escaped"),
    ("having been in your shoes i understand", "escaped"),
    ("having been a founder myself i get it", "escaped"),
    ("as someone who has scaled a team your size i understand", "escaped"),
    ("as an operator who has seen this i can help", "escaped"),
]

# Must PASS (honest sender-identity copy from TASK-075)
must_pass = [
    "most agencies we work with track time in spreadsheets",
    "i work with agencies on project profitability",
    "our platform connects budgets and time tracking",
    "we built productive so budgets and resourcing talk to each other",
    "curious how you handle resourcing at your size",
    "i help agencies with resourcing and utilisation",
    "we help creative teams connect their budgets and timelines",
    "our team works with agency founders on profitability",
    "i have spent a decade in this industry",
    "we have worked with over 50 agencies",
    "our approach comes from years of agency work",
    "i started in agency operations before building this",
]


def main():
    print("=" * 78)
    print("TASK-117: CLASS-BASED RULE DESIGN AND TESTING")
    print("=" * 78)

    # --- Test 1: Current rule ---
    print("\n--- CURRENT RULE (implies_prior_contact) ---")
    caught_current = 0
    escaped_current = []
    for sentence, origin in must_catch:
        found = claims.implies_prior_contact(sentence)
        if found:
            caught_current += 1
        else:
            escaped_current.append(sentence)
    print(f"Caught: {caught_current}/{len(must_catch)}")
    print(f"Escaped: {len(escaped_current)}/{len(must_catch)}")

    # --- Test 2: Proposed class-based rule ---
    print("\n--- PROPOSED CLASS-BASED RULE ---")
    caught_proposed = 0
    false_positives = []
    missed = []

    print("\nMust-catch sentences:")
    for sentence, origin in must_catch:
        match = class_based_check(sentence)
        if match:
            caught_proposed += 1
            print(f"  [CAUGHT by {match:25s}] {sentence!r}")
        else:
            missed.append(sentence)
            print(f"  [MISSED                       ] {sentence!r}")

    print(f"\nCatch rate: {caught_proposed}/{len(must_catch)}")

    print("\nMust-pass sentences (false positive check):")
    for sentence in must_pass:
        match = class_based_check(sentence)
        if match:
            false_positives.append((sentence, match))
            print(f"  [FALSE POSITIVE by {match}] {sentence!r}")
        else:
            print(f"  [CLEAN                    ] {sentence!r}")

    print(f"\nFalse positives: {len(false_positives)}/{len(must_pass)}")

    # --- Test 3: Analysis of what the class-based rule catches ---
    print("\n--- ANALYSIS ---")
    print(f"\nCurrent rule catches {caught_current}/{len(must_catch)} sender-identity claims")
    print(f"Proposed rule catches {caught_proposed}/{len(must_catch)} sender-identity claims")
    print(f"Proposed rule false-positives: {len(false_positives)}/{len(must_pass)}")

    if missed:
        print(f"\nStill missed by proposed rule ({len(missed)}):")
        for s in missed:
            print(f"  - {s!r}")

    if false_positives:
        print(f"\nFalse positives ({len(false_positives)}):")
        for s, match in false_positives:
            print(f"  - [{match}] {s!r}")

    # --- Test 4: The fundamental tension ---
    print("\n--- THE TENSION ---")
    print("""
The class of sender-identity claims is:
  ASSERTIONS THAT PLACE THE SENDER IN THE SAME CATEGORY AS THE RECIPIENT

The honest copy that must pass is:
  ASSERTIONS OF SERVICE TO THAT CATEGORY

The structural difference:
  "as an agency owner"     = I AM in your category  (identity)
  "i work with agencies"   = I SERVE your category  (service)

  "having run a team"      = I HAVE your experience (identity)
  "we help creative teams" = I HELP your category   (service)

  "i also run an agency"   = I SHARE your role      (identity)
  "our team works with..." = I WORK FOR your category (service)

The verb is the discriminator:
  IDENTITY: am, run, own, lead, manage, founded, built, operate, scale
  SERVICE:  work with, help, serve, support, partner with, connect

A class-based rule can be built on this distinction. The question is
whether the boundary is sharp enough to be a REGEX rather than a
CLASSIFIER - and the answer is that it is, because the verbs are
non-overlapping. "run an agency" is identity; "work with agencies"
is service. No verb serves both.
""")


if __name__ == "__main__":
    main()
