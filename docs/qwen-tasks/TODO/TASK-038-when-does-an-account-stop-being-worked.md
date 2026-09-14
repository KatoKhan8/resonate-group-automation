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
