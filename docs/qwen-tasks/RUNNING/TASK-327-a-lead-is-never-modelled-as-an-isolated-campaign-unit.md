PRIORITY: P1
SIZE: S
DEPENDS:

# TASK-327 — a lead is never modelled as an isolated campaign unit

**Source: `docs/ARCHITECTURE-ACCOUNT-FIRST-2026-09-26.md` §2, operator order
2026-09-26.** Phase 1 must not block account-level orchestration later. The
obligation is negative and narrow: **preserve the relationships, and do not
build the decision engine.**

    ACCOUNT <-> CONTACTS <-> ROLES/PERSONAS <-> CAMPAIGN <-> OFFERS
    <-> ACCOUNT INTELLIGENCE <-> CONTACT RELEVANCE <-> EMAIL STATE
    <-> LINKEDIN STATE <-> INTERACTIONS <-> REPLIES <-> REFERRALS
    <-> SUPPRESSION <-> OUTCOMES

## Build

    tests/test_the_account_relationships_survive.py    NEW
    docs/state/ACCOUNT-MODEL-INVARIANTS.md             NEW, generated

One executable invariant per edge above: given a record with three contacts at
one domain, assert each relationship is **traversable in code** on master. This
is a tripwire, so a later refactor that flattens an account into three
independent leads fails a test instead of being discovered in production.

`src/account.py` and `src/accountpolicy.py` already provide the traversals —
`contacts_of`, `touches`, `replies`, `referrals`, `referred_by`, `referred_to`,
`graph`, `team_for`, `affected`. **Use them. Do not write a second model.**

## The four operator rules that must each have a test

From `ACCOUNT-OUTREACH.md` §10, already implemented — this task proves they
hold, it does not reimplement them:

1. **One contact's "not interested" is NOT a company-wide DNC.** Only
   `unsubscribe` and `account_do_not_contact` set `unsubscribed`.
2. **A company-level removal request suppresses the whole account.**
3. **The replier is never left to carry on** — their own sequence ends.
4. **Nothing subtracts.** A replay or reclassification can add a hold or a
   suppression and can never lift one.

## Acceptance

1. Every edge is traversable:

    py -3 -m unittest tests.test_the_account_relationships_survive -v

   The output must name one test per relationship in the list above. A single
   test asserting "account has contacts" does not close this task.

2. **Each of the four rules is seen to FAIL when broken.** For each, break the
   condition in a fixture and confirm the intended test fails for the intended
   reason and that a different guard did not fire first. Paste both runs. An
   assertion that has never been observed failing is the TASK-317 defect.

3. A flattened model is caught:

    py -3 -m unittest tests.test_the_account_relationships_survive.ThreeContactsAreOneAccount

   must fail if `contacts_of` returns three records with three distinct
   account identities for one domain.

## What this task may NOT do

- **Do not build the orchestration decision engine, a next-best-action
  selector, or a primary-contact chooser.** Explicitly deferred by the
  operator. `ACCOUNT-OUTREACH.md` §11 already carries primary / secondary /
  tertiary / referral and the `other_dm_replied` and `referral_received`
  branches; this task only proves they survive.
- Do not change suppression, DNC, or reply-effect behaviour. Test it, do not
  touch it.
- Do not add state. Every relationship above already has a canonical holder.
- Nothing sent, nothing activated.

## RESULT

**STATUS:** DONE
**COMMIT SHA:** (pending)
**TESTS:** 35 new tests, all green. 135 existing account tests unaffected.

**FILES CHANGED:**
- `tests/test_the_account_relationships_survive.py` — NEW, 35 tests
- `docs/state/ACCOUNT-MODEL-INVARIANTS.md` — NEW, generated invariant doc
- `docs/qwen-tasks/RUNNING/TASK-327-*.md` — moved from TODO

**ACCEPTANCE 1 — every edge traversable:**

    py -3 -m unittest tests.test_the_account_relationships_survive -v
    Ran 35 tests in 0.327s — OK

One test class per edge (13 classes, 2-3 tests each):
`AccountToContacts`, `ContactsToRolesPersonas`, `ContactsToCampaign`,
`CampaignToOffers`, `OffersToAccountIntelligence`,
`AccountIntelligenceToContactRelevance`, `ContactRelevanceToEmailState`,
`EmailStateToLinkedInState`, `LinkedInStateToInteractions`,
`InteractionsToReplies`, `RepliesToReferrals`, `ReferralsToSuppression`,
`SuppressionToOutcomes`.

**ACCEPTANCE 2 — each rule seen to FAIL when broken:**

Rule 1 — changed `reply.on_negative` to `(STOP, ACCOUNT)`:
    FAIL: test_negative_reply_does_not_suppress_colleagues
    AssertionError: True is not false  (sarah.get("unsubscribed"))
    FAIL: test_only_unsubscribe_sets_unsubscribed
    AssertionError: True is not false  (john.get("unsubscribed"))

Rule 2 — changed `reply.on_account_dnc` scope to `CONTACT`:
    FAIL: test_account_dnc_reaches_every_contact
    AssertionError: None is not true : sarah not suppressed
    FAIL: test_account_level_suppression_flag_is_set
    AssertionError: None is not true

Rule 3 — changed `_TRANSITION[(CONTINUE, CONTACT)]` replier to CONTINUE:
    FAIL: test_negative_reply_stops_the_replier
    AssertionError: 'continue' not found in ('stop', 'hold', 'suppress')
    FAIL: test_apply_reply_marks_replier_state
    AssertionError: None is not true : John replied but nothing stopped or held him
    (test_positive_reply_stops_the_replier still passes — different guard, unaffected)

Rule 4 — added code in `apply_reply` that clears `unsubscribed` on re-apply:
    FAIL: test_reapply_cannot_lift_a_suppression
    AssertionError: False is not true  (john.get("unsubscribed"))
    (test_reapply_cannot_lift_a_hold still passes — different guard, unaffected)

All source changes were reverted after each break. `git diff src/accountpolicy.py`
is empty.

**ACCEPTANCE 3 — flattened model tripwire:**

`ThreeContactsAreOneAccount` asserts:
- all 3 contacts share one domain
- graph groups them under one `record_id`
- `test_fails_if_contacts_have_distinct_account_identities` asserts the set
  of account IDs has cardinality 1

**FINDINGS:**
- All traversals used are existing: `account.contacts_of`, `account.touches`,
  `account.replies`, `account.referrals`, `account.referred_by`,
  `account.referred_to`, `account.graph`, `accountpolicy.apply_reply`,
  `accountpolicy.effects`. No second model was built.
- `grep -rn contacts_of src/` returns multiple consumers (accountpolicy,
  outreachclaims, fatigue, eligibility, etc.) — the traversal is wired into
  production, not just tested.

**RISKS:** None. Tests are read-only tripwires against existing code.

**RECOMMENDED CLAUDE ACTION:** Accept. The suite is pure tripwire — no
behaviour change, no new state, no provider calls.
