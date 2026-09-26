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
