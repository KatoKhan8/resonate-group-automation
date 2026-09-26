# Account Model Invariants

Generated from `tests/test_the_account_relationships_survive.py`.
One executable invariant per edge in the operator's relationship list.

Source: `docs/ARCHITECTURE-ACCOUNT-FIRST-2026-09-26.md` §2.

    ACCOUNT <-> CONTACTS <-> ROLES/PERSONAS <-> CAMPAIGN <-> OFFERS
    <-> ACCOUNT INTELLIGENCE <-> CONTACT RELEVANCE <-> EMAIL STATE
    <-> LINKEDIN STATE <-> INTERACTIONS <-> REPLIES <-> REFERRALS
    <-> SUPPRESSION <-> OUTCOMES

---

## Edge invariants

Each invariant is a test class in `tests/test_the_account_relationships_survive.py`.
All traversals read through `src/account.py` and `src/accountpolicy.py`.

### ACCOUNT <-> CONTACTS

**Traversal:** `account.contacts_of(rec)`
**Invariant:** Given a record with three contacts at one domain, `contacts_of`
returns all three, including unselected contacts.
**Test class:** `AccountToContacts`

### CONTACTS <-> ROLES/PERSONAS

**Traversal:** `contact["persona"]`, `contact["title"]`, `contact["priority"]`
**Invariant:** Every contact carries a persona, a title, and a priority. Three
contacts at one account have distinct priorities.
**Test class:** `ContactsToRolesPersonas`

### CONTACTS <-> CAMPAIGN

**Traversal:** `campaign["record_ids"]` → `store.load()` → `account.contacts_of(rec)`
**Invariant:** A campaign's record IDs resolve to records that have contacts.
**Test class:** `ContactsToCampaign`

### CAMPAIGN <-> OFFERS

**Traversal:** `rec["cadence"][contact_key][step_key]`
**Invariant:** The cadence on a record carries the offer (channel, subject, body).
**Test class:** `CampaignToOffers`

### OFFERS <-> ACCOUNT INTELLIGENCE

**Traversal:** `rec["company_facts"]`, `account.graph(rec)["domain"]`
**Invariant:** Company facts and domain are on the record and reachable from the graph.
**Test class:** `OffersToAccountIntelligence`

### ACCOUNT INTELLIGENCE <-> CONTACT RELEVANCE

**Traversal:** `contact["persona"]`, `contact["angle"]`
**Invariant:** Every contact has an angle and a persona. Different contacts at
one account have different personas.
**Test class:** `AccountIntelligenceToContactRelevance`

### CONTACT RELEVANCE <-> EMAIL STATE

**Traversal:** `account.touches(rec, contact_key)` filtered by `channel == "email"`
**Invariant:** Email touches for a specific contact are separable from the
full touch list. `confirmed_only=True` filters correctly.
**Test class:** `ContactRelevanceToEmailState`

### EMAIL STATE <-> LINKEDIN STATE

**Traversal:** `account.touches(rec)` filtered by channel
**Invariant:** Both email and LinkedIn touches appear on the same touch graph
and are separable by channel.
**Test class:** `EmailStateToLinkedInState`

### LINKEDIN STATE <-> INTERACTIONS

**Traversal:** `account.graph(rec)["counts"]["touches"]`
**Invariant:** The graph counts confirmed interactions across all channels.
**Test class:** `LinkedInStateToInteractions`

### INTERACTIONS <-> REPLIES

**Traversal:** `account.replies(rec, contact_key)`
**Invariant:** Replies are traversable per contact. A reply from one contact
does not appear in another contact's reply list.
**Test class:** `InteractionsToReplies`

### REPLIES <-> REFERRALS

**Traversal:** `account.referrals(rec)`, `account.referred_by(rec, key)`,
`account.referred_to(rec, key)`
**Invariant:** A referral edge has two traversable ends. `referred_by` and
`referred_to` are mirrors of the same edge.
**Test class:** `RepliesToReferrals`

### REFERRALS <-> SUPPRESSION

**Traversal:** `account.graph(rec)["suppressed"]`,
`graph["by_contact"][key]["state"]`
**Invariant:** Suppression is a separate edge from referrals. A suppressed
contact reads as `SUPPRESSED` in the graph. No suppression by default.
**Test class:** `ReferralsToSuppression`

### SUPPRESSION <-> OUTCOMES

**Traversal:** `accountpolicy.apply_reply(rec, contact_key, outcome)`
**Invariant:** `UNSUBSCRIBE` suppresses the replier only. `ACCOUNT_DNC`
suppresses every contact at the account.
**Test class:** `SuppressionToOutcomes`

---

## Operator rules (ACCOUNT-OUTREACH §10)

### Rule 1: One contact's "not interested" is NOT a company-wide DNC

Only `unsubscribe` and `account_do_not_contact` set `unsubscribed`.
A `NEGATIVE` outcome stops the replier's sequence and leaves colleagues
untouched.

**Test class:** `RuleOne_NegativeIsNotCompanyWide`
**Break proof:** Changed `reply.on_negative` to `(STOP, ACCOUNT)`. Both tests
failed: `sarah.get("unsubscribed")` was `True` instead of `False`.

### Rule 2: A company-level removal request suppresses the whole account

`ACCOUNT_DNC` sets `unsubscribed` on every contact and sets the
account-level `suppression` flag.

**Test class:** `RuleTwo_CompanyRemovalSuppressesAll`
**Break proof:** Changed `reply.on_account_dnc` scope to `CONTACT`. Both tests
failed: Sarah was not suppressed; account-level flag was not set.

### Rule 3: The replier is never left to carry on

Whatever the reply said, the replier's effect is STOP, HOLD, or SUPPRESS -
never CONTINUE.

**Test class:** `RuleThree_ReplierNeverCarriesOn`
**Break proof:** Changed `_TRANSITION[(CONTINUE, CONTACT)]` replier from STOP
to CONTINUE. Two of three tests failed: `plan["replier"]` was `"continue"`
instead of `"stop"`; John had no stopped/paused state.

### Rule 4: Nothing subtracts

A replay or reclassification can add a hold or suppression and can never
lift one.

**Test class:** `RuleFour_NothingSubtracts`
**Break proof:** Added code in `apply_reply` that cleared `unsubscribed` when
a STOP outcome followed a SUPPRESS. The suppression-lift test failed:
`john.get("unsubscribed")` was `False` after re-application.

---

## Flattened model tripwire

**Test class:** `ThreeContactsAreOneAccount`

    py -3 -m unittest tests.test_the_account_relationships_survive.ThreeContactsAreOneAccount

Three contacts at one domain resolve to one account identity
(`rec["id"]`), one domain (`rec["domain"]`), and one graph
(`account.graph(rec)`). If `contacts_of` returned records with distinct
account identities, the `test_fails_if_contacts_have_distinct_account_identities`
test would catch it.

---

## Run

    py -3 -m unittest tests.test_the_account_relationships_survive -v

35 tests, one per edge plus operator rules and the flattened-model tripwire.
