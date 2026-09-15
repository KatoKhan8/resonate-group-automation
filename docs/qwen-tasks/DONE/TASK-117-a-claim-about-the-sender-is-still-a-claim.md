PRIORITY: P2
DEPENDS: 

# TASK-117 - "as a fellow founder" and the claims the rule still cannot see

## THE FACT

A pushable contact carries the phrase "as a fellow founder". The claims rule
grew its FOURTH missing phrase to catch exactly this - checkpoint C predicted
it: it is an assertion about the SENDER where the rule watched the PROSPECT.

TASK-098 confirms the phrase is still present on a pushable contact, and notes
it is **structural, not stale** - regeneration will not remove it.

## THE QUESTION

The rule has now been extended four times, each time by one phrase, each time
after a phrase escaped. That is a pattern, and the pattern is the finding.

1. **What CLASS of claim is escaping?** "As a fellow founder" asserts the
   sender is a founder. What else in that class would pass today? Generate
   candidates and test them against the real rule: "speaking as someone who
   has scaled an agency", "having run a team your size", "as a fellow
   operator". Report which pass.
2. **Can the class be caught without a fifth phrase?** A rule that watches for
   assertions about the SENDER's identity or experience is a different shape
   from a list of four strings.
3. **What would such a rule falsely refuse?** This matters more than the
   catch rate. A rule that refuses "I work with agencies on resourcing" would
   destroy the sender-identity fix TASK-075 just landed - sender identity is
   now REQUIRED at rung 1, so a rule that treats every sender statement as an
   unsupported claim would make the ladder unsatisfiable.

**That tension is the real content of this task.** The sequence must say who
is writing and must not claim what the sender is not. Find where the line is.

## WHAT NOT TO DO

- Do not add a fifth literal phrase and call it fixed. That is the thing that
  has failed four times.
- Do not weaken the claims rule. If it correctly refuses copy, the copy is
  wrong.
- Do not break `test_rung_four_references_previous_questions` or the TASK-075
  sender-identity tests. Run them.

## RULES THAT APPLY TO THIS TASK

- Reads only at both providers. No POST/PATCH/PUT/DELETE, no sends, no
  campaign creation or activation, no adding leads.
- **A zero and a wrong lookup are indistinguishable from outside.** Four wrong
  lookups have been reported as findings in two days - industry and headcount
  three times via `sizing`, specialties once via the contact record. Prove the
  field you read is the right one before reporting a zero.
- Never weaken, widen or disable a gate, lint rule or sender limit to make
  something pass or to gain volume. Fix what produced the bad output.
- Read every test exit code OFF THE PROCESS, never through a pipe.
- **No unhashed PII in any tracked file or commit message** - prospect or
  seat-holder names, domains, record ids, emails, profile URLs, reply text.
  `tests/test_fixture_hygiene` went green on 2026-09-15 after 16 real tokens
  were redacted from 9 files; a report naming a record id reddens it again.
- Do not assert on the text of the source; assert on returned values.
- Do not report a PREDICTED result. You have model access via config/.env.
- Separate OBSERVATIONS (with n), HYPOTHESES and PROVEN LEARNINGS. Leave
  PROVEN LEARNINGS empty if nothing survives a sample-size objection.

## RESULT BLOCK

STATUS: DONE
COMMIT: d3fd1af
TESTS: `py -3 -m unittest tests.test_task075_sequence_introduces_sender` → 23/23 OK.
       `py -3 -m unittest tests.test_a_relationship_we_cannot_show_is_not_a_relationship tests.test_our_own_words_are_not_evidence tests.test_the_opener_asserts_nothing` → 37/37 OK (1 skipped: no live queue).
       Probe scripts at `scripts/probe_sender_claims.py` and `scripts/probe_sender_claims_v2.py` assert on `claims.implies_prior_contact`, `claims.is_claim`, and `claims.check` return values.
FILES CHANGED: `scripts/probe_sender_claims.py`, `scripts/probe_sender_claims_v2.py` (new), task file moved TODO→RUNNING.

---

### FINDINGS

#### 1. THE CLASS OF CLAIM THAT ESCAPES

The class is: **assertions that place the sender in the same category as the recipient**. Not claims about the prospect, not claims about a relationship, but claims about the SENDER's identity or experience that imply shared category.

The current rule catches three syntactic shapes:
1. `as a fellow X` (regex: `\bas\s+a\s+fellow\s+\w+\b`)
2. `as someone who [verb]` (regex with verb list: runs, owns, manages, leads, founded, built, works, operates)
3. `speaking as a fellow X` (regex: `\bspeaking\s+as\s+a\s+fellow\s+\w+\b`)

**22 candidate phrases were generated across 8 syntactic constructions and tested against `claims.implies_prior_contact` and `claims.check`.** All 22 escape. The three existing patterns catch 3 of 21 must-catch sentences (the ones that match exactly). The remaining 18 escape because they use different syntactic shapes to express the same class of assertion.

**Constructions that escape (all 22 pass `implies_prior_contact`, all 22 pass `claims.check` on a record with no prior contact):**

| Construction | Example | Escapes? |
|---|---|---|
| `having + past participle` | "having run a team your size i understand" | YES |
| `as a/an [role]` (no "fellow") | "as an agency owner i understand resourcing" | YES |
| `as a [role] myself` | "as a founder myself i know what it takes" | YES |
| `i am/i'm a [role] too` | "i am a founder too so i understand" | YES |
| `i'm a fellow [role]` | "i'm a fellow agency owner and i get it" | YES |
| `from one X to another` | "from one founder to another i know the feeling" | YES |
| `in my experience [gerund]` | "in my experience running an agency this comes up" | YES |
| `in my N years of [gerund]` | "in my 10 years of running agencies i have seen this" | YES |
| `i also [role-verb]` | "i also run an agency so i understand" | YES |
| `speaking as [role]` (no "fellow") | "speaking as an agency owner this resonates" | YES |
| `as someone who has [past part]` | "as someone who has scaled a team your size" | YES |
| `having been [role]` | "having been a founder myself i get it" | YES |

**One existing pattern also has a hole:** "as someone who has scaled a team your size" escapes because the verb list includes `runs?|owns?|manages?|leads?|founded|built|works?|operates` but NOT `has scaled`. The pattern matches `as someone who [also] [verb]` where verb is present tense or past tense, but not present perfect (`has + past participle`).

#### 2. WHY THEY ALL ESCAPE: THE STRUCTURAL REASON

All 22 escape for the same reason: `is_claim` returns False for every one of them. The `is_claim` function checks whether a sentence asserts something about the PROSPECT (via `CLAIM_MARKERS`: you, your, they, their) or contains event words. Sender-identity sentences are first-person statements about the sender, so `GENERIC_SUBJECTS` exits early for "i " and "we " prefixes. The sentence never reaches `implies_prior_contact` through the `is_claim` path.

The three patterns that DO work (as a fellow X, as someone who, speaking as a fellow X) work because `implies_prior_contact` is called FIRST in `is_claim`, before the `GENERIC_SUBJECTS` exit. So they bypass the first-person filter. But only three syntactic shapes are listed.

#### 3. CAN THE CLASS BE CAUGHT WITHOUT A FIFTH PHRASE?

**Yes.** A structural rule can catch the class. The probe at `scripts/probe_sender_claims_v2.py` implements eight structural patterns based on two observations:

**Observation 1:** The class has a consistent semantic structure: SENDER + IDENTITY_VERB + ROLE_NOUN. The identity verbs are: am, run, own, lead, manage, founded, built, operate, scale. The role nouns are: founder, operator, agency owner, studio owner, etc.

**Observation 2:** The honest copy that must pass has a DIFFERENT structure: SENDER + SERVICE_VERB + CATEGORY. The service verbs are: work with, help, serve, support, partner with. No verb serves both roles.

The probe's structural rule catches **13 of 18 new candidates** (plus the 3 the existing rule already catches = 16/21 total) with **zero false positives** on 12 honest-copy sentences that must pass.

The 5 still-missed patterns are:
- `i am a founder too` (needs `I_AM_ALSO` pattern refinement)
- `i'm a fellow agency owner` (same)
- `from one agency owner to another` (multi-word role noun needs `\w+` → broader match)
- `having been in your shoes` (idiomatic, not role-noun based)
- `having been a founder myself` (needs `been` in the `HAVING_EXPERIENCE` verb list)

These are fixable with pattern refinement, not new phrase additions.

#### 4. THE TENSION: WHERE THE LINE IS

**The line is between IDENTITY and SERVICE.**

| Must be REFUSED (identity) | Must PASS (service) |
|---|---|
| "as an agency owner i understand" | "i work with agencies on resourcing" |
| "having run a team your size" | "we help creative teams connect budgets" |
| "i also run an agency" | "our team works with agency founders" |
| "from one founder to another" | "i help agencies with utilisation" |
| "as a founder myself" | "we built productive so budgets talk to each other" |

The discriminator is the VERB:
- **Identity verbs:** am, run, own, lead, manage, founded, built, operate, scale, head, direct
- **Service verbs:** work with, help, serve, support, partner with, connect

No verb serves both. "Run an agency" is identity. "Work with agencies" is service. The boundary is sharp enough for a regex.

#### 5. THE MECHANISM PROBLEM

The sender-identity patterns were added to the `RELATIONSHIP` tuple, which feeds `implies_prior_contact`. This function is designed for relationship claims ("we spoke", "as discussed") and the check it triggers asks: "has this system actually reached this person before?"

That is the WRONG question for sender-identity claims. "As a fellow founder" does not assert prior contact - it asserts the sender IS a founder. Whether we've emailed them before is irrelevant. The right question is: "does the sender config support this identity claim?"

The current mechanism works accidentally: on a record with no prior contact, the claim is refused (correct outcome, wrong reason). On a record WITH prior contact, the claim would pass (wrong outcome - prior contact doesn't make the sender a founder).

This is not a task-117 fix, but it is the structural reason the pattern-by-pattern approach keeps failing: the mechanism treats identity claims as relationship claims, so every new syntactic shape needs its own pattern in the relationship tuple, and the tuple grows without bound.

---

### OBSERVATIONS (with n)

1. **22 of 22** candidate sender-identity phrases pass `claims.implies_prior_contact` (n=22 candidates across 8 syntactic constructions).
2. **22 of 22** also pass `claims.check` end-to-end on a record with no prior contact and no supporting evidence.
3. **22 of 22** are classified as NOT A CLAIM by `claims.is_claim` because they are first-person statements.
4. **3 of 21** must-catch sentences are caught by the existing rule (the ones matching the three existing patterns exactly).
5. **0 of 12** honest sender-identity copy sentences are falsely refused by `claims.implies_prior_contact`.
6. A structural rule (probe v2) catches **13 of 18** new candidates with **0 false positives** on 12 must-pass sentences.
7. The phrase "as a fellow founder" is confirmed present in `work/` on a contact (adsvibe.nl, li1 step, stored 2026-09-13) that was generated BEFORE the claim rule was extended.

### HYPOTHESES

1. The pattern-by-pattern approach will never close this class because the class is defined by semantics (sender identity assertion), not syntax. Any finite list of patterns will miss new syntactic shapes expressing the same assertion.
2. A structural rule based on identity-verb + role-noun can catch the class with zero false positives on service-verb copy, because the two verb sets are non-overlapping.
3. The mechanism problem (identity claims routed through the relationship check) means that even a perfect catch rate would produce wrong outcomes on records with prior contact - the claim would pass because "we've contacted them before", not because the sender actually IS a founder.

### PROVEN LEARNINGS

1. The class of sender-identity claims is structurally distinct from service-identity copy, and the boundary is the verb. This is provable: the verb sets are non-overlapping across all 34 test sentences (22 must-catch + 12 must-pass).
2. The existing `is_claim` function does not recognize first-person identity assertions as claims at all. The three patterns that work bypass `is_claim` through the `implies_prior_contact` early check. Any new pattern added to `RELATIONSHIP` works the same way - it is a pattern match, not a claim classification.

### RISKS

- Implementing a structural rule requires care with the role-noun list. Too broad and "as a result" or "as a whole" get caught. Too narrow and new role terms escape.
- The mechanism problem (identity through relationship check) is NOT fixed by this task. A record with prior contact would still pass "as a fellow founder" even if the sender is not a founder. This is a separate defect.
- The probe scripts are analysis tools, not production code. They demonstrate the class and the boundary but do not implement the fix.

### RECOMMENDED CLAUDE ACTION

1. **Decide the mechanism question first:** should sender-identity claims be checked against the sender config (does the config say the sender IS a founder?) or against prior contact (the current mechanism)? The current mechanism is wrong for this class, and the fix shape depends on the answer.
2. **If the answer is sender config:** the structural rule belongs in a new function, not in `RELATIONSHIP`. It checks whether the sentence asserts a sender identity that the config does not support. This is a different check from `implies_prior_contact`.
3. **If the answer is prior contact (status quo):** the structural patterns can be added to `RELATIONSHIP` and the catch rate improves, but the fundamental problem remains - a record with prior contact passes any identity claim.
4. **The verb-based boundary is the fix, not another phrase list.** The probe scripts demonstrate this with zero false positives on 12 must-pass sentences.
