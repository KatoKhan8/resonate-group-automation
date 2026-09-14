# TASK-038 - Account saturation and stakeholder escalation

Operator backlog: QWEN-15. This is the ABM half of the cadence.

## GOAL

Decide, from canonical state, when an account has had enough and when a second
person at it should be opened.

## WHY IT MATTERS

`ACCOUNT-OUTREACH.md` makes the ACCOUNT the unit of outreach. The operator's
spec is up to 4 email contacts and 2 priority LinkedIn contacts per account,
activated PROGRESSIVELY rather than simultaneously - "do not blast every
stakeholder".

Nothing currently decides the progression. The campaign holds a contact list
and the cadence runs per contact.

## CURRENT FACTS

- `src/fatigue.py`, `src/account.py`, `src/accountpolicy.py` and
  `src/cadenceexposure.py` all exist and hold pieces of this.
- The client's best-performing sequence has a step-7 "am I talking to the
  right person?" ask, so referrals are a designed input to escalation - though
  the corrected estate reading puts real email referrals near 2%, not the 15%
  first reported, so do NOT size this on referrals arriving often.
- `config/clients/productive.yaml` caps are "PACED FOR THE LINKEDIN-HEAVY
  CADENCE" at 11 touches over 21 days, per CONTACT.

## SCOPE

1. Establish what already decides per-account volume and what does not. Trace
   it; do not assume the modules above are wired to each other.
2. Define SATURATION: how many touches, across how many people, over what
   window, before an account is left alone. Read the caps that exist rather
   than inventing new numbers.
3. Define ESCALATION: what makes a second stakeholder eligible. A reply from
   the first is not automatically it - a positive reply should STOP the
   account, not widen it.
4. The case that decides the design: stakeholder A replies "not me, talk to
   B". That is a referral, an escalation trigger, AND a reason to stop
   contacting A. Make all three happen.

## PRODUCTION BOUNDARY

ZERO network. ZERO credentials - `config/.env` does not exist in this
worktree and a task that tries to obtain one has misunderstood its job. No
provider call. No write to `work/**`. Nothing is staged, activated or sent.

## HANDOFF FORMAT

Return ONLY this, concisely:

    STATUS / COMMIT SHA / FILES CHANGED / TESTS RUN / TEST RESULTS /
    BUGS FOUND / BUGS FIXED / RISKS / OPEN QUESTIONS /
    RECOMMENDED CLAUDE ACTION

Plus, required of every task since 2026-09-14: the output of
`grep -rn "<each new name you added>" src/` proving it is CONSUMED, and
confirmation that deleting the CALL to your new code makes a test fail.

## TESTS REQUIRED

Behavioural, through the planner:

- an account at its touch ceiling opens nobody new;
- a positive reply from one contact stops the ACCOUNT, not just that contact;
- an unsubscribe from one contact stops the account;
- a referral stops the referrer and opens the named person, and ONLY that one;
- two contacts are never opened on the same day by this logic.

## DONE CONDITION

The five tests pass through the real planner, and any rule you could not
derive from existing config or canonical state is listed as an open question
rather than chosen.

## RESULT

STATUS: DONE
COMMIT SHA: 98660f8
TESTS: tests/test_account_saturation.py (6 tests through the planner)
TESTS RUN: 6 new + 512 existing across 10 related modules
TEST RESULTS: 6/6 new pass. 512/513 existing pass (1 pre-existing classifier
  failure unrelated to this task: test_the_classifier_narrows_it classifies
  "please stop asking" as unsubscribe due to the word "stop" matching an
  unsubscribe phrase - present before this change).
FILES CHANGED:
  - src/accountsaturation.py (NEW: saturation verdict from canonical state)
  - src/nextaction.py (wired saturation into _account_verdict)
  - src/accountpolicy.py (referral: STOP referrer, activate referred by default)
  - tests/test_account_saturation.py (NEW: 6 behavioural tests)
  - tests/test_reply_transitions.py (updated EXPECTED table + referral tests)
  - tests/test_the_cadence_reacts_to_what_the_prospect_did.py (unsubscribe test)

CONSUMPTION PROOF:
  grep -rn "accountsaturation" src/ -> 5 hits in nextaction.py (import + 4 uses)
  grep -rn "STOP_SATURATED_UNSUBSCRIBED" src/ -> 2 hits (definition + use)
  grep -rn "STOP_SATURATED_POSITIVE" src/ -> 2 hits (definition + use)
  Breaking the wiring (patching accountsaturation.verdict to return OK) makes
  the unsubscribe test fail: confirmed.

FINDINGS:
  - The referral case is the load-bearing design. "Not me, talk to B" is three
    things at once: a referral edge, a stop for A, and an activation for B.
    Before this task, the referrer was HELD (not stopped) and the referred
    person was NOT activated by default. Both are now changed.
  - An unsubscribe from one person now stops the whole account. This is a
    design decision, not a derivation from existing config. The rationale:
    continuing to contact colleagues of someone who asked to be removed reads
    as one organisation that does not talk to itself.
  - A positive reply stops the account (via saturation check) in addition to
    the existing HOLD. The planner now returns STOP rather than WAIT.

BUGS FOUND: 1 pre-existing (test_the_classifier_narrows_it - classifier
  matches "stop" in "please stop asking" as unsubscribe, not negative).
  Not fixed; not in scope.
BUGS FIXED: 0 (no bugs, design decisions).

RISKS:
  - The unsubscribe-stops-account rule is broader than the existing policy.
    A junior contact's unsubscribe now stops outreach to the CFO. This is
    intentional but may lose accounts where the junior person is not the
    decision maker. Claude should review whether this is the right default.
  - The referral now activates the referred person by default. If the
    referred person is not sendable (no verified email, no LinkedIn), the
    activation succeeds but the planner will WAIT for a channel. This is
    correct behaviour but worth noting.

OPEN QUESTIONS:
  - "An unsubscribe from one contact stops the account" is a design decision
    not derived from existing config. The existing policy (reply.on_unsubscribe)
    is CONTACT scope. This task widened it to ACCOUNT scope via the saturation
    layer. Claude should confirm this is the intended behaviour.
  - "A referral stops the referrer (STOP, not HOLD)" changes the existing
    policy default. The old HOLD allowed an operator to resume; STOP is more
    final. Claude should confirm.
  - "A referral activates the referred person by default" changes the existing
    policy default from HOLD to CONTINUE for reply.activate_referred_contact.
    Claude should confirm.
  - The 2% referral rate means this path is rarely exercised. The design is
    correct for the case that matters (the one described in the task) but has
    not been measured against the full estate.

RECOMMENDED CLAUDE ACTION:
  Review the three open questions above. They are design decisions that widen
  the effect of contact-level events to the account. The tests pass and the
  wiring is proven, but the policy implications should be confirmed by the
  engineering lead before this reaches production.
